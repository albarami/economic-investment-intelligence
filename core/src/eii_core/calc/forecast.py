"""C30 request-time series contract and fact handoff. No store or wire IDs."""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import TypedDict

from .facts import (
    NUMERIC_UNITS,
    CalculationFact,
    NoData,
    SourceChain,
    Suppressed,
    _geography,
)
from .forecast_backtest import METHOD, METHOD_VERSION, Backtest, backtest
from .forecast_list import (
    DEFINITION_VERSION,
    ERROR_PLACES,
    RANGE_CAVEAT,
    Definition,
    definition,
)
from .forecast_models import CANDIDATE_VERSION, CANDIDATES
from .public_methods import reliability
from .public_series import CALC_CONTEXT, count, finite, rounded


def _text(*values: str) -> None:
    if any(type(value) is not str or not value.strip() for value in values):
        raise ValueError("exact nonempty text required")


def period_step(period: str, frequency: str) -> tuple[str, str]:
    """Validate a complete period (or adjacent month pair), return origin/next."""
    _text(period, frequency)
    if "/" in period:
        parts = period.split("/")
        if frequency != "month" or len(parts) != 2:
            raise ValueError("invalid period pair")
        before, after = parts
        if period_step(before, "month")[1] != after:
            raise ValueError("nonadjacent period pair")
        return period_step(after, "month")
    patterns = {
        "year": r"[1-9][0-9]{3}",
        "month": r"[1-9][0-9]{3}-(0[1-9]|1[0-2])",
        "quarter": r"[1-9][0-9]{3}-Q[1-4]",
    }
    if frequency not in patterns or re.fullmatch(patterns[frequency], period) is None:
        raise ValueError("invalid period")
    year = int(period[:4])
    if frequency == "year":
        target = str(year + 1)
    else:
        size = 12 if frequency == "month" else 4
        part = int(period[5:] if frequency == "month" else period[-1])
        next_year, next_part = (year + 1, 1) if part == size else (year, part + 1)
        target = (
            f"{next_year}-{next_part:02}"
            if frequency == "month"
            else f"{next_year}-Q{next_part}"
        )
    if target.startswith("10000"):
        raise ValueError("period outside supported years")
    return period, target


@dataclass(frozen=True)
class ForecastPoint:
    period: str
    value: Decimal
    measure: str
    release_id: str
    unit: str
    deal_count: int | None = None
    bulk_month: bool = False
    carried_forward: bool = False
    complete: bool = True
    published: bool = True

    def __post_init__(self) -> None:
        _text(self.period, self.measure, self.release_id)
        if type(self.unit) is not str:
            raise ValueError("exact text required")
        finite(self.value)
        if self.unit == "count" and (
            self.value < 0 or self.value != self.value.to_integral_value()
        ):
            raise ValueError("invalid count history")
        if self.deal_count is not None:
            count(self.deal_count)
        if any(
            type(flag) is not bool
            for flag in (
                self.bulk_month,
                self.carried_forward,
                self.complete,
                self.published,
            )
        ):
            raise ValueError("boolean required")


@dataclass(frozen=True)
class HomeFamily:
    table: str
    partition: str
    measure: str
    breakdown: str
    column: str
    role: str

    def __post_init__(self) -> None:
        _text(
            self.table,
            self.partition,
            self.measure,
            self.breakdown,
            self.column,
            self.role,
        )


# Document 03 section 7.2 keys, not query names or SQL.
TABLE_GRAINS = {
    "pub_licence_issued": ("municipality_code", "activity_code", "period"),
    "pub_licence_cancelled": ("municipality_code", "activity_code", "period"),
    "pub_property_sale": ("district_key", "period", "property_type"),
    "pub_hotel_monthly": ("period", "star_class", "indicator"),
    "fdi_projects": ("project_key",),
    "pub_building_permits": (
        "municipality_code",
        "period",
        "document_type",
        "permit_type",
        "building_type",
    ),
    "pub_register_snapshot": ("registration_number", "period"),
    "worker_pay": ("unit_id", "period", "measure", "band_from"),
    "resident_pay": (
        "unit_id",
        "period",
        "measure",
        "housing_class",
        "band_from",
        "band_to",
    ),
    "month_change": ("unit_id", "period", "table_name", "measure"),
    "occupation_pay": (
        "unit_id",
        "period",
        "measure",
        "basis",
        "occupation_group",
        "band_from",
    ),
}


@dataclass(frozen=True, kw_only=True)
class ReleaseAdmission:
    """In-memory manifest evidence supplied by the future verified reader.

    This validates bindings; it does not read or verify any mounted bytes.
    A caller cannot promote a statically open S2-T17 entry with this object.
    """

    release_id: str
    table: str
    table_sha256: str
    schema_sha256: str
    grain: tuple[str, ...]
    source_hashes: tuple[tuple[str, str], ...]
    feed_names: tuple[str, ...] = ()
    window_period: str = ""
    window_key: str = ""

    def __post_init__(self) -> None:
        if any(
            type(v) is not str or not v.strip() for v in (self.release_id, self.table)
        ):
            raise ValueError("invalid release admission")
        for digest in (self.table_sha256, self.schema_sha256):
            if type(digest) is not str or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
                raise ValueError("invalid release admission digest")
        if (
            type(self.grain) is not tuple
            or not self.grain
            or any(type(v) is not str or not v for v in self.grain)
        ):
            raise ValueError("invalid release admission grain")
        if type(self.source_hashes) is not tuple:
            raise ValueError("invalid release admission sources")
        for pair in self.source_hashes:
            if (
                type(pair) is not tuple
                or len(pair) != 2
                or type(pair[0]) is not str
                or not pair[0]
                or type(pair[1]) is not str
                or re.fullmatch(r"[a-f0-9]{64}", pair[1]) is None
            ):
                raise ValueError("invalid release admission source hash")
        if (
            type(self.feed_names) is not tuple
            or any(
                type(name) is not str or not name.strip() for name in self.feed_names
            )
            or len(set(self.feed_names)) != len(self.feed_names)
        ):
            raise ValueError("invalid release admission feeds")
        if type(self.window_key) is not str or (
            self.window_key and re.fullmatch(r"[a-f0-9]{64}", self.window_key) is None
        ):
            raise ValueError("invalid release window key")
        if type(self.window_period) is not str:
            raise ValueError("invalid release window period")
        if self.window_period:
            parts = self.window_period.split("/")
            if len(parts) != 2:
                raise ValueError("invalid release window period")
            try:
                for part in parts:
                    period_step(part, "month")
            except ValueError:
                raise ValueError("invalid release window period") from None
            if parts[0] > parts[1]:
                raise ValueError("invalid release window period")


@dataclass(frozen=True, kw_only=True)
class ForecastSeries:
    key: str
    table: str
    subject: str
    geography: str
    geography_kind: str
    level: str
    frequency: str
    measure: str
    unit: str
    input_class: str
    source_geography: str
    breakdown: tuple[tuple[str, str], ...]
    source_breakdown: tuple[tuple[str, str], ...]
    sources: tuple[SourceChain, ...]
    points: tuple[ForecastPoint, ...]
    municipality: str = ""
    partition: str = ""
    protected_table: str = ""
    families: tuple[HomeFamily, ...] = ()
    reconciliation_open: bool = False
    admission: ReleaseAdmission | None = None
    window_key: str = ""
    window_period: str = ""
    generator: str = ""
    generator_version: str = ""
    history_route: str = ""

    def __post_init__(self) -> None:
        _text(
            self.key,
            self.table,
            self.subject,
            self.geography,
            self.geography_kind,
            self.level,
            self.frequency,
            self.measure,
            self.input_class,
            self.source_geography,
        )
        for text in (
            self.unit,
            self.municipality,
            self.partition,
            self.protected_table,
            self.window_key,
            self.window_period,
            self.generator,
            self.generator_version,
            self.history_route,
        ):
            if type(text) is not str:
                raise ValueError("exact text required")
        _geography(self.geography, self.geography_kind)
        object.__setattr__(self, "points", tuple(self.points))
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "families", tuple(self.families))
        object.__setattr__(
            self, "breakdown", tuple(tuple(pair) for pair in self.breakdown)
        )
        object.__setattr__(
            self,
            "source_breakdown",
            tuple(tuple(pair) for pair in self.source_breakdown),
        )
        for pair in (*self.breakdown, *self.source_breakdown):
            if len(pair) != 2:
                raise ValueError("invalid breakdown")
            _text(*pair)
        if not self.sources:
            raise ValueError("missing source chain")
        for source in self.sources:
            if type(source) is not SourceChain:
                raise ValueError("invalid source chain")
            source.__post_init__()
        for family in self.families:
            if type(family) is not HomeFamily:
                raise ValueError("invalid home family")
            family.__post_init__()
        for point in self.points:
            if type(point) is not ForecastPoint:
                raise ValueError("invalid point")
            point.__post_init__()
        if len({point.release_id for point in self.points}) > 1:
            raise ValueError("mixed release ids")
        if type(self.reconciliation_open) is not bool:
            raise ValueError("boolean required")
        periods = tuple(
            period_step(point.period, self.frequency)[0] for point in self.points
        )
        if any(periods[i - 1] >= periods[i] for i in range(1, len(periods))):
            raise ValueError("periods must be ordered and unique")
        if self.key == "stayer_index":
            if any("/" not in point.period for point in self.points):
                raise ValueError("stayer pair required")
            if any(
                self.points[i - 1].period.split("/")[1]
                != self.points[i].period.split("/")[0]
                for i in range(1, len(self.points))
            ):
                raise ValueError("broken stayer pair chain")
        elif any("/" in point.period for point in self.points):
            raise ValueError("unexpected period pair")


@dataclass(frozen=True)
class ForecastNotOffered:
    reason: str = "forecast_not_offered"

    def __post_init__(self) -> None:
        if type(self.reason) is not str or self.reason != "forecast_not_offered":
            raise ValueError("invalid forecast decline")


@dataclass(frozen=True)
class ForecastOpen:
    """Known open registry entry; its reason is metadata, never a numeric fact."""

    key: str
    reason: str
    state: str = "open"
    status: str = "NO_DATA"
    facts: tuple[CalculationFact, ...] = ()

    def __post_init__(self) -> None:
        spec = definition(self.key)
        if (
            spec is None
            or spec.state != "open"
            or self.reason != spec.open_reason
            or self.state != "open"
            or self.status != "NO_DATA"
            or self.facts != ()
        ):
            raise ValueError("invalid open forecast entry")


def forecast_source_refusal(key: str) -> ForecastOpen | ForecastNotOffered | None:
    """Check a key before any reader or series is constructed.

    None permits further admission checks, never asserts mounted availability.
    In particular a source-less entry needs no invented history or source chain.
    """
    spec = definition(key)
    if spec is None:
        return ForecastNotOffered()
    if spec.state == "open":
        return ForecastOpen(key, spec.open_reason)
    return None


def _release_evidence(series: ForecastSeries) -> None:
    evidence = series.admission
    if type(evidence) is not ReleaseAdmission:
        raise ValueError("release admission required")
    evidence.__post_init__()
    if (
        evidence.table != series.table
        or evidence.grain != TABLE_GRAINS.get(series.table)
        or any(point.release_id != evidence.release_id for point in series.points)
        or evidence.source_hashes
        != tuple((source.lineage_ref, source.sha256) for source in series.sources)
    ):
        raise ValueError("release admission mismatch")
    if any(not point.published for point in series.points):
        raise ValueError("unpublished series input")
    if series.input_class == "synthetic" and (
        not re.fullmatch(r"[a-f0-9]{64}", series.window_key)
        or not series.window_period
        or not series.generator.strip()
        or not series.generator_version.strip()
    ):
        raise ValueError("released window or generator metadata required")
    if series.input_class == "synthetic":
        if (
            evidence.window_key != series.window_key
            or evidence.window_period != series.window_period
        ):
            raise ValueError("release window admission mismatch")
        first, last = evidence.window_period.split("/")
        if any(
            month < first or month > last
            for point in series.points
            for month in point.period.split("/")
        ) or (
            series.points and period_step(series.points[-1].period, "month")[0] != last
        ):
            raise ValueError("history outside admitted release window")


def _ranking(series: ForecastSeries) -> bool:
    return series.input_class == "public" and not any(
        key in ("sex", "nationality") for key, _ in series.breakdown
    )


def _released_binding(series: ForecastSeries) -> bool:
    if series.key in (
        "employment_by_occupation_residence",
        "employment_by_occupation_workplace",
    ):
        basis, partition = (
            ("residence", "op_res_quartile")
            if series.key == "employment_by_occupation_residence"
            else ("workplace", "op_work_quartile")
        )
        groups = (*(str(group) for group in range(10)), "unmapped", "other")
        if len(series.breakdown) != 2:
            return False
        group = dict(series.breakdown).get("occupation_group", "")
        return (
            series.table == series.protected_table == "occupation_pay"
            and series.partition == partition
            and group in groups
            and series.breakdown == (("basis", basis), ("occupation_group", group))
            and len(series.families) == 1
            and series.families[0].table == "occupation_pay"
            and series.families[0].partition == partition
            and series.families[0].measure in ("net", "basic")
            and series.families[0].column == "earner_count"
            and series.families[0].role == "single"
            and series.families[0].breakdown
            == f"basis={basis};occupation_group={group};band=ALL"
        )
    table = series.protected_table if series.key == "stayer_index" else series.table
    if table not in ("worker_pay", "resident_pay"):
        return False
    prefix = "wp" if table == "worker_pay" else "rp"
    allowed: tuple[str, ...]
    columns: tuple[tuple[str, str, str], ...]
    if series.key == "stayer_index":
        allowed = (prefix + "_all_money", prefix + "_all_quartile")
        columns = (("stayer_wage_index", "single", "cohort"),)
    elif series.key == "pay_level":
        allowed = (prefix + "_all_money",)
        columns = (
            ("wage_bill", "numerator", "ALL"),
            ("earner_count", "denominator", "ALL"),
        )
    else:
        allowed = (
            prefix + ("_all_money" if series.key == "wage_bill" else "_all_count"),
        )
        columns = ((series.measure, "single", "ALL"),)
    return (
        series.partition in allowed
        and len(series.families) == len(columns)
        and all(
            family.table == table
            and family.partition == series.partition
            and family.measure in ("net", "basic")
            and (family.column, family.role, family.breakdown) == expected
            for family, expected in zip(series.families, columns, strict=True)
        )
        and len({family.measure for family in series.families}) == 1
    )


def _admitted(series: ForecastSeries, spec: Definition) -> bool:
    unit = "count" if series.measure == "project_count" else spec.unit
    return (
        spec.state != "open"
        and series.table in spec.tables
        and series.input_class == spec.input_class
        and series.frequency == spec.frequency
        and series.level in spec.levels
        and series.subject in spec.subjects
        and series.measure in spec.measures
        and series.unit in NUMERIC_UNITS
        and (unit is None or series.unit == unit)
        and all(
            p.measure == series.measure and p.unit == series.unit for p in series.points
        )
        and all(source.table == series.table for source in series.sources)
        and (
            series.input_class != "public"
            or (
                series.geography == series.source_geography
                and series.breakdown == series.source_breakdown
            )
        )
        and (
            (series.level == "national" and series.geography_kind == "national")
            or (
                series.level in ("municipality", "district", "zone")
                and series.geography_kind == "public"
                and series.geography.startswith(series.level + ":")
            )
            or (
                series.level == "area"
                and series.geography_kind in ("area_shape", "release_units")
            )
        )
        # Released geography vocabulary; DAT-137 / PRV-55 further limit stayers
        # through spec.levels to municipality or national, never caller labels alone.
        and (
            series.input_class != "synthetic"
            or series.geography == "national"
            or series.geography.startswith(
                ("municipality:", "area_shape:", "release_units:")
            )
        )
        and (
            series.key != "property_prices"
            or (
                series.geography_kind == "public"
                and series.geography.startswith("district:")
                and bool(series.municipality)
                and all(p.deal_count is not None for p in series.points)
            )
        )
        and (
            series.key != "announced_investment"
            or all(p.complete for p in series.points)
        )
        and (
            series.key != "establishments_by_area" or series.history_route == "snapshot"
        )
        and (
            spec.state != "released"
            or (
                _released_binding(series)
                and type(series.admission) is ReleaseAdmission
                and set(series.admission.feed_names) == set(spec.confirmed_sources)
            )
        )
    )


def _history(series: ForecastSeries) -> tuple[ForecastPoint, ...]:
    start = 0
    for i in range(1, len(series.points)):
        if (
            period_step(series.points[i - 1].period, series.frequency)[1]
            != period_step(series.points[i].period, series.frequency)[0]
        ):
            start = i
    return series.points[start:]


@dataclass(frozen=True, kw_only=True)
class ForecastLineage:
    """Derived method metadata alongside, never replacing, the input pipelines.

    Internal handoff only: these fields do not amend DAT-93 wire qualifiers.
    """

    method: str
    version: str
    series_version: str
    candidate_version: str
    series_key: str
    indicator: str
    model: str
    horizon: int
    subject: str
    origin: str
    admission: ReleaseAdmission
    families: tuple[HomeFamily, ...]
    window_key: str
    generator: str
    generator_version: str

    def __post_init__(self) -> None:
        spec = definition(self.series_key)
        if (
            self.method != METHOD
            or self.version != METHOD_VERSION
            or self.series_version != DEFINITION_VERSION
            or self.candidate_version != CANDIDATE_VERSION
            or spec is None
            or self.indicator not in spec.measures
            or self.model not in CANDIDATES
            or type(self.horizon) is not int
            or self.horizon != spec.horizon
            or type(self.admission) is not ReleaseAdmission
        ):
            raise ValueError("invalid forecast derivation")
        self.admission.__post_init__()


@dataclass(frozen=True, kw_only=True)
class ForecastFact(CalculationFact):
    derivation: ForecastLineage

    def __post_init__(self) -> None:
        super().__post_init__()
        if type(self.derivation) is not ForecastLineage:
            raise ValueError("missing forecast derivation")
        self.derivation.__post_init__()


class _FactFields(TypedDict):
    value: Decimal
    unit: str
    metric_key: str
    release_id: str
    geography: str
    period: str
    input_classes: tuple[str, ...]
    sources: tuple[SourceChain, ...]
    evidence_status: str
    geography_kind: str
    places: int


def _fact(
    series: ForecastSeries,
    exact: Decimal,
    metric: str,
    period: str,
    unit: str,
    places: int,
    derivation: ForecastLineage | None = None,
) -> CalculationFact:
    fields: _FactFields = dict(
        value=Decimal(rounded(exact, places)),
        unit=unit,
        metric_key=metric,
        release_id=series.points[0].release_id,
        geography=series.geography,
        period=period,
        input_classes=(series.input_class,),
        sources=series.sources,
        evidence_status="inferred",
        geography_kind=series.geography_kind,
        places=places,
    )
    fact = (
        CalculationFact(
            **fields,
        )
        if derivation is None
        else ForecastFact(**fields, derivation=derivation)
    )
    object.__setattr__(fact, "exact_unrounded", exact)
    return fact


def _facts(
    series: ForecastSeries, spec: Definition, computation: Backtest, target: str
) -> tuple[CalculationFact, ...]:
    with localcontext(CALC_CONTEXT):
        if type(series.admission) is not ReleaseAdmission:
            raise ValueError("release admission required")
        derivation = ForecastLineage(
            method=METHOD,
            version=METHOD_VERSION,
            series_version=DEFINITION_VERSION,
            candidate_version=CANDIDATE_VERSION,
            series_key=series.key,
            indicator=series.measure,
            model=computation.model,
            horizon=spec.horizon,
            subject=series.subject,
            origin=period_step(series.points[-1].period, series.frequency)[0],
            admission=series.admission,
            families=series.families,
            window_key=series.window_key,
            generator=series.generator,
            generator_version=series.generator_version,
        )
        places = 0 if series.unit == "count" else spec.places
        exact = (
            computation.forecasts[0],
            max(Decimal(0), computation.low[0]),
            max(Decimal(0), computation.high[0]),
            computation.error,
            Decimal(computation.tested),
            Decimal(computation.inside[0]),
            Decimal(computation.tested),
        )
        metrics = (
            "forecast_value",
            "forecast_low",
            "forecast_high",
            "forecast_backtest_error",
            "forecast_backtest_points",
            "forecast_inside",
            "forecast_tested",
        )
        units = (
            series.unit,
            series.unit,
            series.unit,
            "ratio" if computation.scale else series.unit,
            "count",
            "count",
            "count",
        )
        scales = (places, places, places, ERROR_PLACES, 0, 0, 0)
        return tuple(
            _fact(series, value, metric, target, unit, scale, derivation)
            for value, metric, unit, scale in zip(
                exact, metrics, units, scales, strict=True
            )
        )


@dataclass(frozen=True, eq=False)
class ForecastQualifiers(Mapping[str, str | int]):
    """Immutable qualifiers; no mutable dictionary behind a validated result."""

    model: str
    horizon: int

    def __getitem__(self, key: str) -> str | int:
        if key == "model":
            return self.model
        if key == "horizon":
            return self.horizon
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(("model", "horizon"))

    def __len__(self) -> int:
        return 2


@dataclass(frozen=True, kw_only=True)
class ForecastResult:
    series: ForecastSeries
    computation: Backtest
    model: str
    horizon: int
    origin: str
    target: str
    qualifiers: Mapping[str, str | int]
    method: str
    version: str
    series_key: str
    measure: str
    table: str
    breakdown: tuple[tuple[str, str], ...]
    sources: tuple[SourceChain, ...]
    families: tuple[HomeFamily, ...]
    history: tuple[ForecastPoint, ...]
    value: CalculationFact
    low: CalculationFact
    high: CalculationFact
    error: CalculationFact
    points: CalculationFact
    inside: CalculationFact
    tested: CalculationFact
    low_clamped: bool
    high_clamped: bool
    caveats: tuple[str, ...]
    public_only_ranking: bool
    history_deal_counts: tuple[CalculationFact, ...]
    reliability: str

    @property
    def facts(self) -> tuple[CalculationFact, ...]:
        return (
            self.value,
            self.low,
            self.high,
            self.error,
            self.points,
            self.inside,
            self.tested,
        )

    def __post_init__(self) -> None:
        with localcontext(CALC_CONTEXT):
            self.series.__post_init__()
            _text(self.reliability, *self.caveats, *self.qualifiers)
            for pair in self.breakdown:
                _text(*pair)
            spec = definition(self.series.key)
            if (
                spec is None
                or not _admitted(self.series, spec)
                or not self.series.points
            ):
                raise ValueError("inadmissible result")
            _release_evidence(self.series)
            _text(
                self.model,
                self.origin,
                self.target,
                self.method,
                self.version,
                self.series_key,
                self.measure,
                self.table,
            )
            if type(self.horizon) is not int or self.horizon != spec.horizon:
                raise ValueError("invalid horizon")
            if (
                self.model != self.computation.model
                or self.model not in CANDIDATES
                or dict(self.qualifiers)
                != {"model": self.model, "horizon": self.horizon}
                or type(self.qualifiers.get("horizon")) is not int
                or type(self.qualifiers.get("model")) is not str
            ):
                raise ValueError("invalid qualifiers")
            object.__setattr__(
                self, "qualifiers", ForecastQualifiers(self.model, self.horizon)
            )
            if (
                self.method,
                self.version,
                self.series_key,
                self.measure,
                self.table,
                self.breakdown,
                self.sources,
                self.families,
            ) != (
                METHOD,
                METHOD_VERSION,
                self.series.key,
                self.series.measure,
                self.series.table,
                self.series.breakdown,
                self.series.sources,
                self.series.families,
            ):
                raise ValueError("inconsistent lineage or categories")
            if self.history != _history(self.series) or (
                self.origin,
                self.target,
            ) != period_step(self.series.points[-1].period, self.series.frequency):
                raise ValueError("inconsistent history or target")
            if self.series.reconciliation_open or any(
                p.carried_forward for p in self.series.points
            ):
                raise ValueError("withheld window")
            if self.computation.forecasts[0] < 0:
                raise ValueError("negative forecast")
            expected = _facts(self.series, spec, self.computation, self.target)
            for actual, required in zip(self.facts, expected, strict=True):
                if (
                    type(actual) is not ForecastFact
                    or actual != required
                    or actual.exact_unrounded != required.exact_unrounded
                ):
                    raise ValueError("inconsistent companion fact")
            if (
                self.computation.inside[0] > self.computation.tested
                or self.computation.low[0] > self.computation.high[0]
            ):
                raise ValueError("invalid interval counts or ends")
            fresh = backtest(
                (point.value for point in self.history),
                season=spec.season,
                horizon=spec.horizon,
                candidates=CANDIDATES,
            )
            if type(self.computation) is not Backtest or self.computation != fresh:
                raise ValueError("backtest does not match admitted history")
            if (
                type(self.low_clamped) is not bool
                or type(self.high_clamped) is not bool
                or self.low_clamped != (self.computation.low[0] < 0)
                or self.high_clamped != (self.computation.high[0] < 0)
            ):
                raise ValueError("invalid clamp marks")
            if self.caveats != (RANGE_CAVEAT, *spec.caveats):
                raise ValueError("invalid forecast caveats")
            if type(
                self.public_only_ranking
            ) is not bool or self.public_only_ranking != (_ranking(self.series)):
                raise ValueError("invalid Public-only ranking")
            if self.history_deal_counts != _deal_counts(self.series, self.history):
                raise ValueError("missing property deal counts")
            if self.reliability != _reliability(self.series, self.history):
                raise ValueError("invalid reliability")


def _deal_counts(
    series: ForecastSeries, points: tuple[ForecastPoint, ...]
) -> tuple[CalculationFact, ...]:
    return tuple(
        _fact(series, Decimal(p.deal_count), "deal_count", p.period, "count", 0)
        for p in points
        if series.key == "property_prices" and p.deal_count is not None
    )


def _reliability(series: ForecastSeries, points: tuple[ForecastPoint, ...]) -> str:
    with localcontext(CALC_CONTEXT):
        counts = tuple(p.deal_count for p in points if p.deal_count is not None)
        if series.unit == "count":
            counts += tuple(int(p.value) for p in points)
        return reliability(min(counts) if counts else None)


def forecast_series(
    series: ForecastSeries,
) -> ForecastResult | NoData | Suppressed | ForecastNotOffered | ForecastOpen:
    """Fixed production candidates. Refusals precede fitting; origin is released history."""
    series.__post_init__()
    refusal = forecast_source_refusal(series.key)
    if refusal is not None:
        return refusal
    spec = definition(series.key)
    if spec is None or not _admitted(series, spec) or series.reconciliation_open:
        return ForecastNotOffered()
    _release_evidence(series)
    if any(point.carried_forward for point in series.points):
        return Suppressed("CARRIED_FORWARD")
    retained = _history(series)
    computation = backtest(
        (p.value for p in retained),
        season=spec.season,
        horizon=spec.horizon,
        candidates=CANDIDATES,
    )
    if isinstance(computation, NoData):
        return computation
    with localcontext(CALC_CONTEXT):
        if spec.nonnegative and computation.forecasts[0] < 0:
            return NoData("forecast_below_zero")
        origin, target = period_step(retained[-1].period, series.frequency)
        value, low, high, error, points, inside, tested = _facts(
            series, spec, computation, target
        )
        return ForecastResult(
            series=series,
            computation=computation,
            model=computation.model,
            horizon=spec.horizon,
            origin=origin,
            target=target,
            qualifiers={"model": computation.model, "horizon": spec.horizon},
            method=METHOD,
            version=METHOD_VERSION,
            series_key=series.key,
            measure=series.measure,
            table=series.table,
            breakdown=series.breakdown,
            sources=series.sources,
            families=series.families,
            history=retained,
            value=value,
            low=low,
            high=high,
            error=error,
            points=points,
            inside=inside,
            tested=tested,
            low_clamped=computation.low[0] < 0,
            high_clamped=computation.high[0] < 0,
            caveats=(RANGE_CAVEAT, *spec.caveats),
            public_only_ranking=_ranking(series),
            history_deal_counts=_deal_counts(series, retained),
            reliability=_reliability(series, retained),
        )
