"""Closed registry and parity entries for the available Public tools and stage."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from eii_product.assistant.catalogue.schema import Catalogue
from eii_product.store.normalise import Fact, ToolResult
from eii_product.store.parity import ParityCase, ToolDescriptor
from eii_product.store.protocol import NormalValue, ReleaseStore, ToolInput
from eii_product.store.registry import PACKAGED
from eii_product.tools.areas import canonical_json
from eii_product.tools.make_area import (
    QUERY_NAMES,
    MakeAreaContext,
    MakeAreaResult,
    canonical_payload,
    make_area,
)
from eii_product.tools.resolve import QUERY_NAMES as RESOLVE_QUERY_NAMES
from eii_product.tools.resolve import ResolveContext, ResolveResult, resolve
from eii_product.tools.scan_places import QUERY_NAMES as SCAN_PLACES_QUERIES
from eii_product.tools.scan_places import ScanPlacesContext, scan_places
from eii_product.tools.sector_facts import TOPICS, sector_facts
from eii_product.tools.stage import stage

TOOL_KEY = "make_area"
RESOLVE_KEY = "resolve"


def tool_keys() -> tuple[str, ...]:
    """The closed list of registered tools."""
    return (
        TOOL_KEY,
        RESOLVE_KEY,
        "sector_facts",
        "stage",
        "scan_places",
        "night_lights",
        "venue_busyness",
        "population_age_sex",
    )


def parity_cases(shape_id: str) -> tuple[ParityCase, ...]:
    """Public-only cases. The pin is a gazetteer key and the polygon a shape id."""
    return (
        ParityCase(
            TOOL_KEY,
            (("place_key", "SYN-pin"), ("mode", "walk"), ("cutoff", 5)),
        ),
        ParityCase(
            TOOL_KEY,
            (("place_key", "SYN-pin"), ("mode", "drive"), ("cutoff", 10)),
        ),
        ParityCase(TOOL_KEY, (("shape_id", shape_id),)),
    )


def resolve_parity_cases() -> tuple[ParityCase, ...]:
    """The pack's parity strings, each language, place and activity."""
    return (
        ParityCase(
            RESOLVE_KEY, (("text", "Lusail"), ("lang", "en"), ("kind", "place"))
        ),
        ParityCase(
            RESOLVE_KEY, (("text", "Lusail"), ("lang", "ar"), ("kind", "place"))
        ),
        ParityCase(
            RESOLVE_KEY,
            (("text", "Italian restaurant"), ("lang", "en"), ("kind", "activity")),
        ),
        ParityCase(
            RESOLVE_KEY,
            (("text", "Italian restaurant"), ("lang", "ar"), ("kind", "activity")),
        ),
    )


def resolve_descriptor(
    context: ResolveContext, payloads: list[bytes]
) -> ToolDescriptor:
    """Bind the context into ``run``. The placeholder carries no facts."""

    def run(store: ReleaseStore, inputs: Mapping[str, ToolInput]) -> ToolResult:
        result = resolve(store, dict(inputs), context)
        payloads.append(_resolve_payload(result))
        return _resolve_placeholder(store, result)

    return ToolDescriptor(RESOLVE_KEY, run, RESOLVE_QUERY_NAMES)


def require_cases(tools: Sequence[ToolDescriptor], cases: Sequence[ParityCase]) -> None:
    """Refuse a registered tool that has no parity case."""
    from eii_product.store.protocol import StoreRefusal

    covered = {case.tool for case in cases}
    for tool in tools:
        if tool.key not in covered:
            raise StoreRefusal("tool case missing")


def descriptor(context: MakeAreaContext, payloads: list[bytes]) -> ToolDescriptor:
    """Bind the context into ``run``. The placeholder carries no facts."""

    def run(store: ReleaseStore, inputs: Mapping[str, ToolInput]) -> ToolResult:
        result = make_area(store, dict(inputs), context)
        payloads.append(canonical_payload(result))
        return _placeholder(store, result)

    return ToolDescriptor(TOOL_KEY, run, QUERY_NAMES)


def _resolve_payload(result: ResolveResult) -> bytes:
    body = {
        "status": result.status,
        "reason": result.reason,
        "payload": result.payload,
    }
    return canonical_json(body)


def _resolve_placeholder(store: ReleaseStore, result: ResolveResult) -> ToolResult:
    return ToolResult(
        store.engine,
        "resolve",
        0,
        RESOLVE_KEY,
        result.status,
        store.release_id,
        (),
    )


def _placeholder(store: ReleaseStore, result: MakeAreaResult) -> ToolResult:
    return ToolResult(
        store.engine,
        "make_area",
        0,
        TOOL_KEY,
        result.status,
        store.release_id,
        (),
    )


def sector_facts_descriptor() -> ToolDescriptor:
    """Bind the Public-fact tool; parity names are semantic fact ids."""

    def run(store: ReleaseStore, inputs: Mapping[str, ToolInput]) -> ToolResult:
        result = sector_facts(store, inputs)
        return ToolResult(
            store.engine,
            result["call_id"],
            0,
            "sector_facts",
            result["status"],
            store.release_id,
            tuple(
                Fact(f.fact_id, f.unit, cast(NormalValue, f.value))
                for f in result["facts"]
            ),
        )

    return ToolDescriptor(
        "sector_facts",
        run,
        tuple(q.name for q in PACKAGED.queries if q.name.startswith("sector_facts_")),
    )


def sector_facts_parity_cases() -> tuple[ParityCase, ...]:
    """The two contract cases plus the topics needed for query coverage."""
    return tuple(
        ParityCase(
            "sector_facts",
            (
                ("activity", "561" if topic == "unit_economics" else "SYN-restaurant"),
                ("topic", topic),
                (
                    "geography",
                    "municipality:SYN-local"
                    if topic
                    in {"licences", "churn", "employer_scale", "visitor_markets"}
                    else "national",
                ),
            )
            + (
                (("trade", {"flow": "SYN-M", "product_scope": "TOTAL"}),)
                if topic == "trade"
                else ()
            ),
        )
        for topic in TOPICS
    )


def stage_descriptor(catalogue: Catalogue) -> ToolDescriptor:
    """Store-free stage validation participates in the existing parity harness."""

    def run(store: ReleaseStore, inputs: Mapping[str, ToolInput]) -> ToolResult:
        result = stage(inputs, catalogue)
        return ToolResult(
            store.engine, "stage", 0, "stage", result["status"], store.release_id, ()
        )

    return ToolDescriptor("stage", run, ())


def stage_parity_cases() -> tuple[ParityCase, ...]:
    return (
        ParityCase("stage", (("directive", "hour"), ("hour_key", "INVENTED-hour"))),
    )


def scan_places_descriptor(
    context: ScanPlacesContext, payloads: list[bytes]
) -> ToolDescriptor:
    """Record the full envelope; scalar parity alone does not prove its metadata."""
    import json

    def run(store: ReleaseStore, inputs: Mapping[str, ToolInput]) -> ToolResult:
        result = scan_places(store, inputs, context)
        body = result.model_dump(mode="json")
        del body["engine"], body["call_id"]
        payloads.append(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )
        return ToolResult(
            store.engine,
            result.call_id,
            0,
            "scan_places",
            result.status,
            store.release_id,
            tuple(
                Fact(f.fact_id, f.unit, cast(NormalValue, f.value))
                for f in result.facts
            ),
        )

    return ToolDescriptor("scan_places", run, SCAN_PLACES_QUERIES)


def scan_places_parity_cases(area_id: str) -> tuple[ParityCase, ...]:
    """Restaurants around the flagship pin: caller supplies an invented analogue."""
    return (
        ParityCase(
            "scan_places",
            (
                ("area_id", area_id),
                ("categories", ["place_category:SYN-food"]),
                ("limit", 50),
                ("include_neighbours", True),
            ),
        ),
    )


def public_card_descriptors(context: MakeAreaContext) -> tuple[ToolDescriptor, ...]:
    """Own the closed card reads; scoped parity execution belongs to pass three."""
    from eii_product.tools.public_context_tools import run_card

    owned = {
        "night_lights": (
            "night_lights_cells",
            "make_area_grid_cells",
            "make_area_municipalities",
            "public_lineage_for_table",
            "sector_facts_sources",
        ),
        "population_age_sex": (
            "population_age_sex_rows",
            "population_age_sex_bands",
            "make_area_grid_cells",
            "make_area_municipalities",
            "public_lineage_for_table",
            "sector_facts_sources",
        ),
        "venue_busyness": (
            "venue_busyness_rows",
            "venue_busyness_places",
            "public_lineage_for_table",
            "sector_facts_sources",
        ),
    }

    def descriptor_for(key: str, queries: tuple[str, ...]) -> ToolDescriptor:
        def run(store: ReleaseStore, inputs: Mapping[str, ToolInput]) -> ToolResult:
            result = run_card(store, key, inputs, context)
            facts = result.facts if hasattr(result, "facts") else ()
            return ToolResult(
                store.engine,
                key,
                0,
                key,
                result.status,
                store.release_id,
                tuple(
                    Fact(f.fact_id, f.unit, cast(NormalValue, f.value)) for f in facts
                ),
            )

        return ToolDescriptor(key, run, queries)

    return tuple(descriptor_for(key, queries) for key, queries in owned.items())


def public_layer_descriptors() -> tuple[ToolDescriptor, ...]:
    """Layer descriptors are not tools and never enter tool_keys()."""
    from eii_product.api.public_layers import PUBLIC_LAYER_KEYS, read_layer

    def descriptor_for(key: str) -> ToolDescriptor:
        extras = {
            "public_places": ("layer_public_places_fsq",),
            "fdi_projects": ("layer_fdi_gazetteer",),
            "land_prices": ("layer_district_geometry",),
            "property_prices": ("layer_district_geometry",),
            "night_lights": ("layer_night_lights_months",),
            # S3-T12: the sealed table list first, so an absent table is never read.
            "accidents": ("public_release_manifest", "layer_zone_geometry"),
            "zone_electricity_growth": (
                "layer_zone_geometry",
                "sector_facts_utility",
                "sector_facts_utility_national",
            ),
        }
        queries = (
            (() if key == "zone_electricity_growth" else ("layer_" + key,))
            + extras.get(key, ())
            + ("public_lineage_for_table", "sector_facts_sources")
            + (("sector_facts_lineage",) if key == "zone_electricity_growth" else ())
        )

        def run(store: ReleaseStore, inputs: Mapping[str, ToolInput]) -> ToolResult:
            month = inputs.get("month_key")
            result = read_layer(store, key, month if isinstance(month, str) else None)
            return ToolResult(
                store.engine,
                "layer:" + key,
                0,
                "layer:" + key,
                str(result["status"]),
                store.release_id,
                tuple(
                    Fact(f["fact_id"], f["unit"], cast(NormalValue, f["value"]))
                    for f in result["facts"]
                ),
            )

        return ToolDescriptor("layer:" + key, run, queries)

    return tuple(descriptor_for(key) for key in PUBLIC_LAYER_KEYS)


def public_transport_queries() -> tuple[str, ...]:
    """S3-T24 read ownership; live Public proof executes these beside the readers."""
    return (
        "public_release_manifest",
        "sector_facts_lineage",
        "sector_facts_sources",
        "layer_night_lights_months",
    )
