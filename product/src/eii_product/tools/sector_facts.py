"""Public reads and thin calculation adapters; no display arithmetic here.

Churn years come from the calculation layer. C4 component mappings use the
publisher's stored indicator keys; unknown rows are never guessed.

The ``trade`` topic is S3-T06 part A of decision 0040's "public-source fact
bindings": the Comtrade reporter-row binding only. Its production read (the
``sector_facts_comtrade`` SQL and toml), its ``PACKAGED`` registration, document
08's Reads row and packaged parity stay gated on S2-T23 box 1, which records the
value's decimal(p,s) contract, the reviewed (measure, unit) map and the
registry's url and licence. Until then ``TRADE_UNITS`` is empty and the topic
reads nothing. The source chain keeps ``licence_basis: provider_terms`` and the
recorded terms words as the registry holds them; nothing is repaired.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, ValidationError

from eii_core import calc
from eii_core.calc.facts import (
    CalculationFact,
    Measure,
    MeasureMismatch,
    NoData,
    SourceChain,
)
from eii_core.calc.public_methods import AnnualEnergy
from eii_core.calc.public_series import C2_CALENDAR, bulk_months, complete_years
from eii_core.calc.sector_economics import Component
from eii_core.facts import SIZE_BAND, UNITS, Fact, validate_chain
from eii_core.reasons import closed_code
from eii_core.reasons import reason as closed_reason
from eii_product.store import ReleaseStore
from eii_product.store.protocol import Param
from eii_product.store.registry import PACKAGED, Inventory

from .fact_builder import STORED_UNITS, build_calculated, build_published

TOPICS = (
    "unit_economics",
    "licences",
    "churn",
    "zone_momentum",
    "pay_decomposition",
    "employer_scale",
    "market_context",
    "visitor_markets",
    "trade",
)
COMTRADE_TABLE = "pub_comtrade_trade"
COMTRADE_QUERY = "sector_facts_comtrade"
# The release keeps Qatar as reporter under this key (document 03 "7.3 Columns").
COMTRADE_REPORTER = "QAT"
# The catalogue key of pub_comtrade_trade without period, which stays Fact.period.
COMTRADE_QUALIFIERS = (
    "series_role",
    "reporter_code",
    "partner_code",
    "partner2_code",
    "frequency",
    "flow_code",
    "classification",
    "classification_revision",
    "product_code",
    "aggregation_level",
    "customs_code",
    "transport_mode_code",
    "valuation_basis",
    "measure",
)
# Reviewed (measure, unit) -> fact unit. Empty until S2-T23 box 1 records it.
TRADE_UNITS: Mapping[tuple[str, str], str] = {}
# Locked to fdi_estimates (document 03 section 9); never a trade unit.
FDI_LOCKED_UNITS = frozenset({"usd_million", "announced_jobs"})
_TOKEN = r"[A-Za-z0-9_-]+"


class ScenarioInputs(BaseModel):
    """C4 typed inputs, reserved for S7-T01; no scenario output yet."""

    model_config = ConfigDict(strict=True, extra="forbid")
    monthly_rent: Decimal | int
    seats: int
    average_bill: Decimal | int
    opening_days: int = 30
    expected_covers_per_day: Decimal | int | None = None
    monthly_staff_cost: Decimal | int | None = None
    U: Decimal | int = 0
    incentive_key: str | None = None


class TradeInputs(BaseModel):
    """Closed trade selection; source codes are matched verbatim, no period."""

    model_config = ConfigDict(strict=True, extra="forbid")
    flow: str
    product_scope: str
    partner: str | None = None


class Inputs(BaseModel):
    """Closed tool input. Stored activity keys are matched verbatim."""

    model_config = ConfigDict(strict=True, extra="forbid")
    activity: str
    topic: Literal[
        "unit_economics",
        "licences",
        "churn",
        "zone_momentum",
        "pay_decomposition",
        "employer_scale",
        "market_context",
        "visitor_markets",
        "trade",
    ]
    geography: str
    scenario_inputs: ScenarioInputs | None = None
    trade: TradeInputs | None = None


def _read(store: ReleaseStore, name: str, **params: Param) -> list[dict[str, Any]]:
    return _fetch(store, PACKAGED, "sector_facts_" + name, params)


def _fetch(
    store: ReleaseStore, inventory: Inventory, name: str, params: Mapping[str, Param]
) -> list[dict[str, Any]]:
    result = store.fetch(inventory.lookup(name), params)
    return [dict(zip(result.columns, row, strict=True)) for row in result.rows]


class Context:
    """One call's facts, resolved sources and blocks; no release data is written."""

    def __init__(self, store: ReleaseStore, inputs: Inputs) -> None:
        self.store = store
        self.inputs = inputs
        self.facts: dict[str, Fact] = {}
        self.blocks: list[dict[str, Any]] = []
        self.payload: dict[str, Any] = {}
        self.chains: dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]] = {}

    def chain(
        self, table: str, suffix: str = ""
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        ref = "lin_" + table + suffix
        if ref not in self.chains:
            lines = _read(self.store, "lineage", lineage=ref)
            sources = _read(
                self.store,
                "sources",
                sources=list(dict.fromkeys(r["source_id"] for r in lines)),
            )
            self.chains[ref] = lines, sources
        lines, sources = self.chains[ref]
        return ref, lines, sources

    def measure(
        self, row: Mapping[str, Any], table: str, value: str, unit: str, geography: str
    ) -> Measure:
        ref, lines, sources = self.chain(table)
        reason = validate_chain(ref, lines, sources)
        if reason is not None:
            raise ValueError(reason)
        if "source_id" in row and row["source_id"] not in {
            line["source_id"] for line in lines
        }:
            raise ValueError("source_missing")
        links = []
        for line in lines:
            source = next(s for s in sources if s["source_id"] == line["source_id"])
            method, version = line["transform"].split("@")
            links.append(
                SourceChain(
                    ref,
                    table,
                    method,
                    version,
                    source["publisher"],
                    source["title"],
                    source["url"],
                    source["licence"],
                    str(source["retrieved_on"]),
                    source["sha256"],
                )
            )
        if type(row[value]) not in (int, float, Decimal):
            raise ValueError("number_required")
        return Measure(
            Decimal(str(row[value])),
            unit,
            row["period"],
            geography,
            "national" if geography == "national" else "public",
            "public",
            tuple(links),
        )

    def block(
        self,
        name: str,
        values: list[Fact | None],
        status: str = "NO_DATA",
        reason: str | None = None,
    ) -> None:
        valid = []
        for fact in values:
            if fact is not None:
                try:
                    # Revalidate at assembly; model_construct/model_copy cannot bypass DAT-90.
                    checked = Fact.model_validate(fact.model_dump())
                except ValueError as error:
                    reason = closed_reason(error, "fact_invalid")
                    continue
                lines, sources = self.chains.get(checked.lineage_ref, ([], []))
                broken = validate_chain(checked.lineage_ref, lines, sources)
                if broken is not None:
                    reason = closed_code(broken, "chain_refused")
                    continue
                self.facts[checked.fact_id] = checked
                valid.append(checked.fact_id)
        block: dict[str, Any] = dict(
            block=name,
            status="OK" if valid else status,
            fact_ids=list(dict.fromkeys(valid)),
        )
        if reason is not None:
            block["reason_key"] = reason
        self.blocks.append(block)

    def calculated(
        self,
        result: CalculationFact,
        *,
        qualifiers: Mapping[str, str] | None = None,
        count: int | None = None,
        suffix: str = "",
        caveats: tuple[str, ...] = (),
        numerator_table: str | None = None,
    ) -> Fact | None:
        table = result.sources[0].table if numerator_table is None else numerator_table
        ref, lines, sources = self.chain(table, suffix)
        return build_calculated(
            result,
            release_id=self.store.release_id,
            lineage_ref=ref,
            lineage_rows=lines,
            source_rows=sources,
            qualifiers=qualifiers
            if qualifiers is not None
            else {"activity": self.inputs.activity},
            count=count,
            caveat_keys=caveats,
            numerator_table=table,
        )


def _licences(ctx: Context) -> None:
    args, store = ctx.inputs, ctx.store
    code = args.geography.removeprefix("municipality:")
    local = _read(store, "licence_local", activity=args.activity, geography=code)
    totals = _read(store, "licence_municipality", geography=code)
    national = _read(store, "licence_activity", activity=args.activity)
    all_national = _read(store, "licence_national")
    residents = _read(store, "residents", geography=code)
    ctx.block("national_density", [])
    if not local or not totals or not national or not all_national:
        ctx.block("licences", [])
        return
    if any(len(rows) != 1 for rows in (local, totals, national, all_national)):
        ctx.block("licences", [])
        return
    table = "pub_licence_active"
    try:
        a = ctx.measure(local[0], table, "active_count", "count", args.geography)
        b = ctx.measure(totals[0], table, "active_count", "count", args.geography)
        c = ctx.measure(national[0], table, "active_count", "count", "national")
        d = ctx.measure(all_national[0], table, "active_count", "count", "national")
        quotient = cast(dict[str, Any], calc.location_quotient(a, b, c, d))
    except (ValueError, MeasureMismatch):
        ctx.block("quotient", [])
        return
    status = quotient.get("status")
    if isinstance(status, NoData):
        ctx.block("quotient", [], reason=status.reason)
        ctx.block(
            "licence_count",
            [ctx.calculated(quotient["count"], count=local[0]["active_count"])],
        )
    else:
        ctx.block(
            "quotient",
            [
                ctx.calculated(f, count=local[0]["active_count"])
                for f in (quotient["value"], *quotient["interval"])
            ],
        )
    density: Fact | None = None
    density_reason = None
    # PUB-72 explicitly fixes this snapshot to the residents year; no inferred year selection.
    if (
        len(residents) == 1
        and a.period == "2025-05"
        and residents[0]["period"] == "2025"
    ):
        try:
            population = ctx.measure(
                residents[0],
                "pub_population_municipality",
                "value",
                "count",
                args.geography,
            )
            computed = calc.licence_density(replace(a, period="2025"), population)
            density = ctx.calculated(
                computed,
                suffix="_density",
                count=local[0]["active_count"],
                caveats=("licence_activity_not_firm", "snapshot_may_2025"),
            )
        except ValueError as error:
            density_reason = closed_reason(error)
    ctx.block("density", [density], reason=density_reason)


def _churn(ctx: Context) -> None:
    args = ctx.inputs
    code = args.geography.removeprefix("municipality:")
    active = _read(ctx.store, "licence_local", activity=args.activity, geography=code)
    national = _read(ctx.store, "churn_national")
    all_cancelled = _read(ctx.store, "churn_total")
    dated_cancelled = _read(ctx.store, "churn_dated_total")
    stored = _read(ctx.store, "bulk_months", flag=True)
    try:
        flags = bulk_months(
            {
                r["period"]: ctx.measure(
                    r, "pub_licence_cancelled", "cancelled_count", "count", "national"
                ).value
                for r in national
            }
        )
    except ValueError:
        flags = ()
    if flags and set(flags) == {r["period"] for r in stored}:
        ref, lines, sources = ctx.chain("pub_licence_cancelled")
        ctx.block(
            "bulk_months",
            [
                build_published(
                    value=month,
                    unit="calendar_month",
                    metric_key="bulk_month",
                    period=month,
                    geography={"kind": "national"},
                    release_id=ctx.store.release_id,
                    lineage_ref=ref,
                    lineage_rows=lines,
                    source_rows=sources,
                    qualifiers={},
                    caveat_keys=("calculated",),
                )
                for month in flags
            ],
        )
    national_result = None
    for year, months in complete_years():
        rows = _read(
            ctx.store,
            "churn_local",
            activity=args.activity,
            geography=code,
            months=list(months),
        )
        if any(row["period"] not in months for row in rows):
            raise ValueError("churn_month_outside_request")
        name = "churn_" + year
        if any(len(values) != 1 for values in (active, all_cancelled, dated_cancelled)):
            ctx.block(name, [])
            continue
        try:
            stock = ctx.measure(
                active[0], "pub_licence_active", "active_count", "count", args.geography
            )

            def cancellation(row: Mapping[str, Any], geography: str) -> Measure:
                return ctx.measure(
                    row, "pub_licence_cancelled", "cancelled_count", "count", geography
                )

            result = calc.licence_churn(
                stock,
                {r["period"]: cancellation(r, args.geography) for r in rows},
                {r["period"]: cancellation(r, "national") for r in national},
                C2_CALENDAR,
                cancellation(dict(all_cancelled[0], period=stock.period), "national"),
                cancellation(dict(dated_cancelled[0], period=stock.period), "national"),
            )
        except ValueError:
            ctx.block(name, [])
            continue
        national_result = result
        values = [
            ctx.calculated(
                cast(CalculationFact, result["active_count"]),
                suffix="_churn",
                count=active[0]["active_count"],
            )
        ]
        for key in ("including_ratio", "including_percent", "excluding_percent"):
            fact = cast(CalculationFact, result[key])
            values.append(
                ctx.calculated(
                    replace(fact, period=year, base_period=stock.period),
                    suffix="_churn",
                    numerator_table="pub_licence_cancelled",
                    count=active[0]["active_count"],
                )
            )
        for treatment in ("including", "excluding"):
            interval = result[treatment + "_interval"]
            if isinstance(interval, NoData):
                ctx.block(
                    name + "_" + treatment + "_interval", [], reason=interval.reason
                )
            else:
                for fact in cast(tuple[CalculationFact, CalculationFact], interval):
                    values.append(
                        ctx.calculated(
                            replace(fact, period=year, base_period=stock.period),
                            suffix="_churn",
                            numerator_table="pub_licence_cancelled",
                            count=active[0]["active_count"],
                            qualifiers={
                                "activity": args.activity,
                                "treatment": treatment,
                            },
                        )
                    )
        ctx.block(name, values)
    if national_result is not None:
        ctx.block(
            "churn_national",
            [
                ctx.calculated(f, qualifiers={}, suffix="_churn")
                for key in ("undated_count", "bulk_share_percent")
                if isinstance(f := national_result[key], CalculationFact)
            ],
        )
        share = national_result["bulk_share_percent"]
        if isinstance(share, NoData):
            ctx.block("bulk_share", [], reason=share.reason)


def _fixed(
    ctx: Context, name: str, table: str, geography: str, params: dict[str, Param]
) -> None:
    rows = _read(ctx.store, name, **params)
    ref, lines, sources = ctx.chain(table)
    facts: list[Fact | None] = []
    for row in rows:
        if row["source_id"] not in {line["source_id"] for line in lines}:
            continue
        unit = STORED_UNITS.get(row.get("unit", "count"))
        if unit is None:
            continue
        qualifiers: dict[str, str] = {
            key: row[key]
            for key in (
                "table_code",
                "indicator",
                "size_class",
                "nationality_group",
                "breakdown_key",
                "facility_type",
                "trade_type",
            )
            if key in row
        }
        qualifiers["activity"] = ctx.inputs.activity
        if "size_class" in row:
            size = row["size_class"]
            size_unit = "size_band" if SIZE_BAND.fullmatch(size) else "published_text"
            facts.append(
                build_published(
                    value=size,
                    unit=size_unit,
                    metric_key="size_class",
                    period=row["period"],
                    geography={"kind": "national"},
                    release_id=ctx.store.release_id,
                    lineage_ref=ref,
                    lineage_rows=lines,
                    source_rows=sources,
                    qualifiers=qualifiers,
                )
            )
        facts.append(
            build_published(
                value=row.get("value", row.get("facility_count")),
                unit=unit,
                metric_key=row.get("indicator", "facilities"),
                period=row["period"],
                geography={"kind": "national"}
                if geography == "national"
                else {"kind": "public", "public_code": geography},
                release_id=ctx.store.release_id,
                lineage_ref=ref,
                lineage_rows=lines,
                source_rows=sources,
                qualifiers=qualifiers,
                caveat_keys=("dated_census",) if name == "census" else (),
            )
        )
    ctx.block(name, facts)


def _pay(ctx: Context) -> None:
    rows = _read(ctx.store, "wages", table_code="wage_occ", periods=["2020", "2025"])
    by_period: dict[str, dict[str, dict[str, dict[str, Any]]]] = {
        "2020": {},
        "2025": {},
    }
    for row in rows:
        if row["period"] not in by_period:
            ctx.block("pay_decomposition", [])
            return
        by_period[row["period"]].setdefault(row["breakdown_key"], {})[
            row["indicator"]
        ] = row
    try:
        pairs = []
        for groups in by_period.values():
            pairs.append(
                {
                    group: (
                        ctx.measure(
                            cells["paid_workers"],
                            "pub_wage_table",
                            "value",
                            "count",
                            "national",
                        ),
                        ctx.measure(
                            cells["monthly_average_wage"],
                            "pub_wage_table",
                            "value",
                            "qar_per_month",
                            "national",
                        ),
                    )
                    for group, cells in groups.items()
                }
            )
        result = calc.decomposition(pairs[0], pairs[1])
    except (ValueError, KeyError):
        ctx.block("pay_decomposition", [])
        return
    ctx.block(
        "pay_decomposition",
        [
            ctx.calculated(
                f,
                qualifiers={"table_code": "wage_occ"},
                caveats=("named_table", "composition_not_wages"),
            )
            for f in result.values()
            if isinstance(f, CalculationFact)
        ],
    )


def _momentum(ctx: Context) -> None:
    rows = _read(ctx.store, "utility", periods=["2021", "2025"])
    totals = _read(ctx.store, "utility_national", periods=["2021", "2025"])

    def energy(row: Mapping[str, Any], national: bool = False) -> AnnualEnergy:
        geography = "national" if national else "zone:" + row["zone_code"]
        reading = ctx.measure(row, "pub_zone_utility", "value", "kwh", geography)
        return AnnualEnergy(
            geography,
            {"2021": 2021, "2025": 2025}[row["period"]],
            reading.value,
            national or row["completeness"] == "complete",
            reading,
        )

    try:
        national = {r["period"]: energy(r, True) for r in totals}
        result = cast(
            dict[str, Any],
            calc.zone_momentum(
                [energy(r) for r in rows], national["2021"], national["2025"]
            ),
        )
    except (ValueError, KeyError):
        ctx.block("zone_momentum", [])
        return
    # The order is the calculator's order of identifiers, never a rank computed here.
    ctx.payload["zone_order"] = [
        key.removeprefix("zone:") for key in result["order_unrounded"]
    ]
    ctx.block(
        "national_momentum",
        [
            ctx.calculated(
                result["national_ratio"],
                qualifiers={"utility": "electricity"},
                caveats=("activity_proxy_not_population",),
            )
        ],
    )
    for values in result["zones"].values():
        ctx.block(
            "zone_momentum",
            [
                ctx.calculated(
                    f,
                    qualifiers={"utility": "electricity"},
                    caveats=("activity_proxy_not_population",),
                )
                for f in values.values()
                if isinstance(f, CalculationFact)
            ]
            if isinstance(values, dict)
            else [],
        )


def _norms(ctx: Context) -> None:
    rows = _read(ctx.store, "accounts", activity=ctx.inputs.activity)
    employee_keys = list(
        dict.fromkeys(
            row["indicator"]
            for row in rows
            if row["indicator"].startswith("employees:")
        )
    )
    employees = _read(
        ctx.store,
        "account_employees",
        activity=ctx.inputs.activity,
        indicators=employee_keys,
    )
    # Published component labels match the pinned C4 replay and the release's
    # URL-encoded indicator suffixes (publicdata/series/figures.py).
    component_keys = {
        "food": ("goods", "intermediate_goods:Food%20Stuff"),
        "beverages": ("goods", "intermediate_goods:Beverages"),
        "building_rent": ("services", "intermediate_services:Rents%20of%20Buildings"),
    }
    component_totals = {
        group: _read(
            ctx.store,
            "account_components",
            activity=ctx.inputs.activity,
            indicators=list(
                dict.fromkeys(
                    row["indicator"]
                    for row in rows
                    if row["indicator"].startswith("intermediate_" + group + ":")
                )
            ),
        )
        for group in ("goods", "services")
    }
    if not rows:
        ctx.block("unit_economics", [], status="OUT_OF_SCOPE")
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["period"], {})[row["indicator"]] = row
    for period, cells in grouped.items():
        totals = [
            row
            for row in employees
            if row["period"] == period and row["unit"] == "count"
        ]
        if len(totals) != 1:
            ctx.block(
                "unit_economics",
                [],
                reason="employee_total_ambiguous" if totals else "missing_input",
            )
            continue

        def measure(row: Mapping[str, Any], unit: str) -> Measure:
            if STORED_UNITS.get(row["unit"]) != unit:
                raise MeasureMismatch("unit")
            return ctx.measure(row, "pub_sector_accounts", "value", unit, "national")

        try:
            components = []
            for key, (group, indicator) in component_keys.items():
                total_rows = [
                    row for row in component_totals[group] if row["period"] == period
                ]
                if indicator in cells and len(total_rows) == 1:
                    components.append(
                        Component(
                            key,
                            group,
                            measure(cells[indicator], "qar_thousand"),
                            measure(total_rows[0], "qar_thousand"),
                            group,
                        )
                    )
            result = calc.sector_norms(
                employees=measure(totals[0], "count"),
                productivity=measure(cells["productivity_of_employee"], "qar"),
                compensation_thousand=measure(cells["compensation"], "qar_thousand"),
                surplus_thousand=measure(cells["operating_surplus"], "qar_thousand"),
                goods_percent=measure(cells["goods_share"], "percent"),
                services_percent=measure(cells["services_share"], "percent"),
                components=components,
            )
        except KeyError:
            ctx.block("unit_economics", [], reason="input_key_missing")
            continue
        except ValueError as error:
            ctx.block("unit_economics", [], reason=closed_reason(error))
            continue
        ctx.block(
            "unit_economics",
            [
                ctx.calculated(f, caveats=("national_average", "world_cup_year"))
                for f in result.values()
                if isinstance(f, CalculationFact)
            ],
        )
    ctx.block("scenario", [])


def trade_unit(
    row: Mapping[str, Any], units: Mapping[tuple[str, str], str]
) -> str | None:
    """The reviewed fact unit of a row's closed (measure, unit) pair, or None."""
    unit = units.get((row["measure"], row["unit"]))
    if unit is None or unit in FDI_LOCKED_UNITS or unit not in UNITS:
        return None
    return unit


def comtrade_refusal(
    row: Mapping[str, Any],
    lineage_sources: Collection[str],
    units: Mapping[tuple[str, str], str],
) -> str | None:
    """The closed reason a reporter row yields no fact, or None when it binds."""
    if row["series_role"] != "reporter":
        return "trade_series_role"
    if row["reporter_code"] != COMTRADE_REPORTER:
        return "trade_reporter_invalid"
    if row["source_id"] not in lineage_sources:
        return "source_missing"
    if row["value"] is None:
        return "trade_coverage_gap"
    if type(row["value"]) not in (int, Decimal):
        return "number_required"
    if units.get((row["measure"], row["unit"])) in FDI_LOCKED_UNITS:
        return "trade_unit_locked"
    if trade_unit(row, units) is None:
        return "trade_unit_unmapped"
    if type(row["aggregation_level"]) is not int or any(
        type(row[key]) is not str
        for key in COMTRADE_QUALIFIERS
        if key != "aggregation_level"
    ):
        return "trade_qualifier_invalid"
    return None


def comtrade_fact(
    ctx: Context,
    row: Mapping[str, Any],
    units: Mapping[tuple[str, str], str],
    caveats: tuple[str, ...] = (),
) -> Fact | None:
    """One reporter cell; the stored value passes byte for byte."""
    ref, lines, sources = ctx.chain(COMTRADE_TABLE)
    if comtrade_refusal(row, {line["source_id"] for line in lines}, units):
        return None
    qualifiers = {key: str(row[key]) for key in COMTRADE_QUALIFIERS}
    qualifiers["activity"] = ctx.inputs.activity
    return build_published(
        value=row["value"],
        unit=cast(str, trade_unit(row, units)),
        metric_key="trade_reporter_measure",
        period=row["period"],
        geography={"kind": "national"},
        release_id=ctx.store.release_id,
        lineage_ref=ref,
        lineage_rows=lines,
        source_rows=sources,
        qualifiers=qualifiers,
        caveat_keys=caveats,
    )


def _outside(row: Mapping[str, Any], request: TradeInputs) -> bool:
    return (
        row["flow_code"] != request.flow
        or row["product_code"] != request.product_scope
        or (request.partner is not None and row["partner_code"] != request.partner)
    )


def trade_reporter(
    ctx: Context, inventory: Inventory, units: Mapping[tuple[str, str], str]
) -> None:
    """Bind Comtrade reporter cells; never a sum, a conversion or a zero."""
    request = cast(TradeInputs, ctx.inputs.trade)
    if inventory.get(COMTRADE_QUERY) is None:
        # Gated on S2-T23 box 1: no packaged read exists, so nothing is read.
        ctx.block("trade_reporter", [])
        return
    rows: Sequence[Mapping[str, Any]] = _fetch(
        ctx.store,
        inventory,
        COMTRADE_QUERY,
        dict(
            flow=request.flow,
            product_code=request.product_scope,
            partner=request.partner or "",
        ),
    )
    if any(_outside(row, request) for row in rows):
        raise ValueError("trade_row_outside_request")
    keys = [tuple(row[k] for k in (*COMTRADE_QUALIFIERS, "period")) for row in rows]
    if len(keys) != len(set(keys)):
        ctx.block("trade_reporter", [], reason="duplicate_row_key")
        return
    gap = not rows or any(row["value"] is None for row in rows)
    built = [comtrade_fact(ctx, row, units) for row in rows]
    ctx.block(
        "trade_reporter",
        [fact for fact in built if fact is not None],
        reason="trade_coverage_gap" if gap else None,
    )


def sector_facts(store: ReleaseStore, raw: Mapping[str, object]) -> dict[str, Any]:
    """Return the BE-49 envelope; invalid arguments are refused before a read."""
    try:
        args = Inputs.model_validate(dict(raw))
        if re.fullmatch(_TOKEN, args.activity) is None:
            raise ValueError("activity")
        if (
            re.fullmatch(
                r"national|(?:municipality|zone):[A-Za-z0-9_-]+", args.geography
            )
            is None
        ):
            raise ValueError("geography")
        if args.scenario_inputs is not None and args.topic != "unit_economics":
            raise ValueError("scenario")
        if (args.trade is not None) != (args.topic == "trade"):
            raise ValueError("trade")
        if args.trade is not None and (
            args.geography != "national"
            or re.fullmatch(_TOKEN, args.trade.flow) is None
            or re.fullmatch(r"TOTAL|[0-9]{2}", args.trade.product_scope) is None
            or (
                args.trade.partner is not None
                and re.fullmatch(_TOKEN, args.trade.partner) is None
            )
        ):
            raise ValueError("trade")
    except ValidationError as error:
        faults = error.errors(include_input=False, include_url=False)
        field = faults[0]["loc"][0] if faults and faults[0]["loc"] else None
        if field not in Inputs.model_fields:
            field = None
        raise ValueError(closed_code(field, "INVALID_ARGUMENT")) from None
    except ValueError as error:
        raise ValueError(closed_reason(error, "INVALID_ARGUMENT")) from None
    ctx = Context(store, args)
    if args.topic == "licences":
        _licences(ctx)
    elif args.topic == "churn":
        _churn(ctx)
    elif args.topic == "employer_scale":
        _fixed(
            ctx,
            "employer_scale",
            "pub_establishment_size",
            "national",
            {"activity": args.activity},
        )
        _fixed(
            ctx,
            "census",
            "pub_census_2015_municipality",
            args.geography,
            {"geography": args.geography.removeprefix("municipality:")},
        )
    elif args.topic == "market_context":
        _fixed(
            ctx,
            "market_context",
            "pub_trade_wr",
            "national",
            {"activity": args.activity},
        )
    elif args.topic == "visitor_markets":
        _fixed(
            ctx,
            "hotels",
            "pub_hotels_municipality",
            args.geography,
            {"geography": args.geography.removeprefix("municipality:")},
        )
        _fixed(ctx, "visitors", "pub_visitor_markets", "national", {})
    elif args.topic == "pay_decomposition":
        _pay(ctx)
    elif args.topic == "zone_momentum":
        _momentum(ctx)
    elif args.topic == "trade":
        trade_reporter(ctx, PACKAGED, TRADE_UNITS)
    else:
        _norms(ctx)
    return dict(
        tool="sector_facts",
        call_id=str(uuid4()),
        release_id=store.release_id,
        engine=store.engine,
        status="OK"
        if any(b["status"] == "OK" for b in ctx.blocks)
        else "OUT_OF_SCOPE"
        if any(b["status"] == "OUT_OF_SCOPE" for b in ctx.blocks)
        else "NO_DATA",
        blocks=ctx.blocks,
        facts=list(ctx.facts.values()),
        payload=ctx.payload,
        caveat_keys=[],
    )
