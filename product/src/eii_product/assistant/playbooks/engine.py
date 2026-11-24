"""Public bundle execution and BE-27 byte comparison."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from eii_core.calc.public_context import NightLightsDisplay, PopulationDisplay
from eii_core.facts import Fact, fact_id
from eii_product.assistant.catalogue.schema import Catalogue
from eii_product.assistant.playbooks.inputs import Inputs
from eii_product.assistant.playbooks.models import Bundle, Evidence
from eii_product.assistant.playbooks.registry import Definition
from eii_product.assistant.templates.status import status_key
from eii_product.ledger.local import LocalLedger, tool_entry
from eii_product.store.protocol import ReleaseStore
from eii_product.store.registry import PACKAGED
from eii_product.tools.areas import canonical_json
from eii_product.tools.make_area import (
    ArgumentError,
    MakeAreaContext,
    ShapeMiss,
    make_area,
)
from eii_product.tools.resolve import ResolveContext, resolve
from eii_product.tools.sector_facts import _read, sector_facts
from eii_product.tools.stage import stage


def comparable(value: object) -> object:
    """Remove precisely the BE-27 envelope exclusions, preserving list order."""
    if isinstance(value, date):
        return value.isoformat()
    if type(value) is float:
        return Decimal(str(value))
    if isinstance(value, Mapping):
        return {
            key: comparable(item)
            for key, item in value.items()
            if key not in {"engine", "call_id", "duration_ms", "timings"}
        }
    if isinstance(value, (list, tuple)):
        return [comparable(item) for item in value]
    return value


def require_identical(left: object, right: object) -> None:
    """A content or ordering difference fails the playbook proof."""
    if canonical_json(comparable(left)) != canonical_json(comparable(right)):
        raise ValueError("bundle_mismatch")


class UnregisteredShapes:
    """Sessionless tooling cannot look up a registered shape."""

    def find(self, shape_id: str) -> ShapeMiss:
        return ShapeMiss("unknown")


def execute(
    store: ReleaseStore,
    definition: Definition,
    inputs: dict[str, Any],
    catalogue: Catalogue,
    ledger: LocalLedger,
    answer_id: str,
    *,
    area_context: MakeAreaContext | None = None,
) -> Bundle:
    """Execute the declared Public calls; verify the ledger before returning."""
    if ledger is None:
        raise ValueError("ledger_required")
    selected = Inputs.model_validate(inputs)
    inputs = selected.model_dump(exclude_none=True)
    bundle = Bundle(store.release_id, dict(inputs), definition.name)
    context = area_context or MakeAreaContext(
        store.release_id, "public_only", definition.name, PACKAGED, UnregisteredShapes()
    )
    if context.release_id != store.release_id:
        raise ArgumentError("INVALID_ARGUMENT")
    headline = "wider" if selected.mode == "drive" else "near"
    bundle.area_roles = {"headline": None, "near": None, "wider": None}
    areas: list[str] = []
    entries = []
    for call in definition.calls:
        arguments = dict(call.arguments)
        identities: list[str] = []
        payload: object = None
        if call.tool == "resolve":
            arguments.update(text=inputs["activity"], lang=inputs["lang"])
            resolved = resolve(store, arguments, ResolveContext(PACKAGED))
            status, payload = resolved.status, resolved.payload
        elif call.tool == "make_area":
            if call.key == headline:
                arguments = selected.area_request()
            elif selected.pin is not None:
                arguments.update(latitude=selected.pin.lat, longitude=selected.pin.lon)
            else:
                # A shape carries no clicked origin for a distinct drive context.
                # Do not invent a centre, an origin or a duplicate context area.
                status = "NO_DATA"
                payload = {"reason": "context_pin_absent"}
            if selected.pin is not None or call.key == headline:
                area = make_area(store, arguments, context)
                if area.status == "INVALID_ARGUMENT":
                    raise ArgumentError("INVALID_ARGUMENT")
                if area.status not in {"OK", "NO_DATA", "OUT_OF_SCOPE"}:
                    raise ValueError("area_status_invalid")
                status, payload = area.status, area.payload
                area_id = None if area.payload is None else area.payload.get("area_id")
                if isinstance(area_id, str):
                    areas.append(area_id)
                    bundle.area_roles[call.key] = area_id
                    if call.key == headline:
                        bundle.area_roles["headline"] = area_id
        elif call.tool == "stage":
            if arguments["directive"] == "fly":
                arguments["target"] = {"area_id": bundle.area_roles["headline"]}
            else:
                arguments["area_ids"] = list(areas)
            if (arguments["directive"] == "rings" and not areas) or (
                arguments["directive"] == "fly"
                and bundle.area_roles["headline"] is None
            ):
                status = "NO_DATA"
            else:
                result = stage(arguments, catalogue)
                status, payload = result["status"], result["payload"]
                bundle.stage.append(result["payload"]["directive"])
        elif call.tool in {"night_lights", "population_age_sex"}:
            # Import here: the existing Public outcome boundary imports this route.
            from eii_product.tools.public_context_tools import (
                CARD_MODELS,
                chain,
                read,
                run_card,
            )

            arguments["area_id"] = bundle.area_roles["headline"]
            if call.tool == "night_lights":
                months = read(store, "layer_night_lights_months")
                if months:
                    arguments["month_key"] = months[-1]["period"]
            facts: tuple[Fact, ...]
            if arguments["area_id"] is None or (
                call.tool == "night_lights" and "month_key" not in arguments
            ):
                status, payload = "NO_DATA", None
                facts = ()
            else:
                arguments = (
                    CARD_MODELS[call.tool]
                    .model_validate(arguments)
                    .model_dump(exclude_none=True)
                )
                card = run_card(store, call.tool, arguments, context)
                status, payload = card.status, card.payload
                from eii_product.api.results import PublicResult

                if not isinstance(card, PublicResult):
                    raise ValueError("public_card_invalid")
                facts = card.facts
            identities = [fact.fact_id for fact in facts]
            if facts:
                table = (
                    "pub_night_lights"
                    if call.tool == "night_lights"
                    else "pub_pop_agesex_grid"
                )
                _, lines, sources = chain(store, table)
                for fact in facts:
                    metric = (
                        NightLightsDisplay.metric_key
                        if call.tool == "night_lights"
                        else PopulationDisplay.metric_key
                    )
                    bundle.facts[fact.fact_id] = Evidence(fact, metric, lines, sources)
            bundle.cards.append(
                dict(
                    card_id=call.key,
                    kind=call.tool,
                    status=status,
                    fact_ids=identities,
                    caveat_keys=list(
                        dict.fromkeys(key for fact in facts for key in fact.caveat_keys)
                    ),
                    template_key=status_key(status),
                    area_id=bundle.area_roles["headline"],
                    area_role=headline,
                )
            )
        else:
            arguments["activity"] = inputs["activity"]
            result = sector_facts(store, arguments)
            status, payload = result["status"], result["payload"]
            identities = [fact.fact_id for fact in result["facts"]]
            for fact in result["facts"]:
                lines = _read(store, "lineage", lineage=fact.lineage_ref)
                sources = _read(
                    store,
                    "sources",
                    sources=list(dict.fromkeys(row["source_id"] for row in lines)),
                )
                metric = unit_economics_metric(fact, inputs["activity"])
                bundle.facts[fact.fact_id] = Evidence(fact, metric, lines, sources)
            for block in result["blocks"]:
                bundle.cards.append(
                    dict(
                        card_id=call.key + "_" + str(len(bundle.cards)),
                        kind=block["block"],
                        status=block["status"],
                        fact_ids=block["fact_ids"],
                        caveat_keys=list(
                            dict.fromkeys(
                                key
                                for identity in block["fact_ids"]
                                for key in bundle.facts[identity].fact.caveat_keys
                            )
                        ),
                        template_key=status_key(block["status"]),
                    )
                )
        entry = tool_entry(
            answer_id=answer_id,
            tool=call.tool,
            arguments=arguments,
            release_id=store.release_id,
            engine=store.engine,
            status=status,
            fact_ids=identities,
        )
        ledger.write(entry)
        ledger.require_entry(entry)
        entries.append(entry)
        bundle.steps.append(
            {"key": call.key, "tool": call.tool, "status": status, "payload": payload}
        )
    ledger.require_entries(entries)
    return bundle


def unit_economics_metric(fact: Fact, activity: str) -> str:
    """Recover the closed C4 binding by its semantic identity, never its value."""
    matches = [
        key
        for key in (
            "compensation_percent",
            "surplus_percent",
            "goods_percent",
            "services_percent",
            "food",
            "beverages",
            "building_rent",
        )
        if fact.fact_id
        == fact_id(
            release_id=fact.release_id,
            metric_key=key,
            geography=fact.geography,
            period=fact.period,
            qualifiers={"activity": activity},
        )
    ]
    if len(matches) != 1:
        raise ValueError("fact_binding_invalid")
    return matches[0]
