"""Typed calculation results, not a second application wire schema.

The release owner (task S3-T06 for the fact a tool returns, and the release
build for DAT-93 identifiers and DAT-94 registry resolution) attaches canonical
fact identifiers. Here every supplied source-chain link is validated in memory.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal, localcontext
from fractions import Fraction
from functools import cmp_to_key

from .public_series import (
    CALC_CONTEXT,
    Approximate,
    Number,
    compare,
    divide,
    exact,
    finite,
    rounded,
    subtract,
)

_CLASS_RANK = {"public": 0, "synthetic": 1, "simulated": 2}
# Higher rank is weaker. A still-to-test input can never come out observed.
_EVIDENCE_RANK = {"observed": 0, "inferred": 1, "still_to_test": 2}
NUMERIC_UNITS = (
    "count",
    "qar",
    "qar_thousand",
    "qar_million",
    "qar_per_month",
    "qar_per_kg",
    "kwh",
    "ratio",
    "percent",
    "index",
    "riders",
)
BAND_UNITS = ("wage_band", "size_band", "volume_band")
MEASURE_UNITS = (*NUMERIC_UNITS, "kg", "quantity")
# DAT-90 plus the method-card reasons: missing_input (MTH-09),
# too_few_licences (MTH-16), and the coverage-specific card reasons.
PACK_NO_DATA_REASONS = frozenset(
    {
        "series_too_short",
        "forecast_below_zero",
        "no_denominator",
        "snapshot_not_kept",
        "inputs_not_entered",
        "not_coverable",
        "open_top_band",
        "holds_constant_in_design",
        "no_land_deals",
        "ratio_input_withheld",
        "no_competing_jobs",
        "point_without_base_cell",
        "zone_without_district",
        "coverage_by_workplace_not_published",
        "cells_differ_between_years",
        "no_zoning_cover",
        "missing_input",
        "too_few_licences",
    }
)
_RATIO_PLACES = 2
_MONTH = re.compile(r"[1-9][0-9]{3}-(0[1-9]|1[0-2])")
_YEAR = re.compile(r"[1-9][0-9]{3}")


def least_real(input_classes: Iterable[str]) -> str:
    """Least-real class. Public is more real than Synthetic, then Simulated."""
    input_classes = tuple(input_classes)
    if not input_classes or any(
        type(c) is not str or c not in (*_CLASS_RANK, "user_input")
        for c in input_classes
    ):
        raise ValueError("invalid input classes")
    classes = tuple(c for c in input_classes if c != "user_input")
    if not classes:
        raise ValueError("release input class required")
    return max(classes, key=_CLASS_RANK.__getitem__)


def weakest_evidence(statuses: Iterable[str]) -> str:
    """Weakest evidence status of the inputs. Still-to-test never becomes observed."""
    statuses = tuple(statuses)
    if not statuses or any(
        type(status) is not str or status not in _EVIDENCE_RANK for status in statuses
    ):
        raise ValueError("invalid evidence status")
    return max(statuses, key=_EVIDENCE_RANK.__getitem__)


class MeasureMismatch(ValueError):
    """A card refused inputs whose unit, period or geography do not match."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        super().__init__(f"{kind} mismatch")


class WithdrawnProduction(ValueError):
    """Decision 0026 item 12 withdrew the production value and output per establishment."""

    def __init__(self, derivation: str) -> None:
        self.derivation = derivation
        super().__init__(f"withdrawn production derivation: {derivation}")


@dataclass(frozen=True)
class SourceChain:
    lineage_ref: str
    table: str
    method: str
    version: str
    publisher: str
    dataset: str
    url: str
    licence: str
    retrieved: str
    sha256: str

    def __post_init__(self) -> None:
        for value in (
            self.lineage_ref,
            self.table,
            self.method,
            self.version,
            self.publisher,
            self.dataset,
            self.url,
            self.licence,
            self.retrieved,
            self.sha256,
        ):
            if type(value) is not str or not value.strip():
                raise ValueError("incomplete source chain")
        if self.licence.strip().lower() == "none":
            raise ValueError("incomplete source chain")
        if not self.url.startswith(("https://", "http://")):
            raise ValueError("incomplete source chain")
        if not re.fullmatch(r"[a-f0-9]{64}", self.sha256):
            raise ValueError("invalid source hash")
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.retrieved):
            raise ValueError("invalid retrieval date")
        date.fromisoformat(self.retrieved)


@dataclass(frozen=True)
class RegistrySource:
    """Registry fields only. Retrieval date and file hash are not in the registry."""

    lineage_ref: str
    publisher: str
    dataset: str
    licence: str
    url: str

    def __post_init__(self) -> None:
        for value in (
            self.lineage_ref,
            self.publisher,
            self.dataset,
            self.licence,
            self.url,
        ):
            if type(value) is not str or not value.strip():
                raise ValueError("incomplete source chain")
        if not self.url.startswith(("https://", "http://")):
            raise ValueError("incomplete source chain")


SourceLink = SourceChain


@dataclass(frozen=True)
class NoData:
    reason: str
    status: str = "NO_DATA"

    def __post_init__(self) -> None:
        if self.reason not in PACK_NO_DATA_REASONS or self.status != "NO_DATA":
            raise ValueError("unknown NO_DATA reason")


@dataclass(frozen=True)
class Suppressed:
    """C20 withheld branch: a value and its reason, never a number."""

    reason: str
    status: str = "SUPPRESSED"
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.reason) is not str or not self.reason.strip():
            raise ValueError("suppression reason required")
        if self.status != "SUPPRESSED":
            raise ValueError("invalid suppression")


def _geography(value: str, kind: str) -> None:
    if type(value) is not str or type(kind) is not str:
        raise MeasureMismatch("geography")
    if kind == "national":
        valid = value == "national"
    elif kind == "public":
        valid = (
            re.fullmatch(r"(zone|municipality|district|place):.+", value) is not None
        )
    elif kind in ("release_units", "user_scenario", "area_shape"):
        valid = value.startswith(kind + ":") and bool(value[len(kind) + 1 :])
    else:
        valid = False
    if not valid:
        raise MeasureMismatch("geography")


def _band(value: Decimal | str, unit: str) -> tuple[int, int]:
    if type(value) is not str:
        raise ValueError("band value required")
    if unit == "wage_band":
        order = tuple(f"B{i:02}" for i in range(1, 13))
    elif unit == "size_band":
        order = ("no_payroll", "s01_09", "s10_49", "s50_plus")
    else:
        raise ValueError("unsupported comparison band")
    parts = value.split("..")
    if len(parts) not in (1, 2) or any(part not in order for part in parts):
        raise ValueError("invalid band")
    low, high = order.index(parts[0]), order.index(parts[-1])
    if low > high:
        raise ValueError("invalid band range")
    return low, high


@dataclass(frozen=True)
class Measure:
    """One typed input. The caller supplies the input class, never a result class."""

    value: Decimal
    unit: str
    period: str
    geography: str
    geography_kind: str
    input_class: str
    sources: tuple[SourceLink, ...]
    evidence_status: str = "observed"
    metric_key: str = "input"

    def __post_init__(self) -> None:
        _geography(self.geography, self.geography_kind)
        if type(self.unit) is not str or self.unit not in (*MEASURE_UNITS, *BAND_UNITS):
            raise ValueError("unsupported numeric unit")
        if self.unit in BAND_UNITS:
            _band(self.value, self.unit)
        else:
            if type(self.value) is not Decimal:
                raise ValueError("numeric value required")
            finite(self.value)
        if type(self.input_class) is not str or self.input_class not in (
            *_CLASS_RANK,
            "user_input",
        ):
            raise ValueError("invalid input classes")
        if (
            type(self.evidence_status) is not str
            or self.evidence_status not in _EVIDENCE_RANK
        ):
            raise ValueError("invalid evidence status")
        if self.input_class == "user_input" and self.evidence_status != "inferred":
            raise ValueError("user inputs must be inferred")
        if not isinstance(self.sources, tuple) or not self.sources:
            raise ValueError("invalid source chain")
        for source in self.sources:
            if not isinstance(source, SourceChain):
                raise ValueError("invalid source chain")
            source.__post_init__()
        for text in (self.period, self.geography, self.geography_kind, self.metric_key):
            if type(text) is not str or not text.strip():
                raise ValueError("missing metadata or lineage")


@dataclass(frozen=True)
class WithheldInput:
    """A Public value the source withheld. It is not a numeric fact."""

    metric_key: str
    release_id: str
    geography: str
    geography_kind: str
    period: str
    unit: str
    reason: str
    sources: tuple[SourceLink, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.sources, tuple) or not self.sources:
            raise ValueError("invalid source chain")
        _geography(self.geography, self.geography_kind)
        for source in self.sources:
            if not isinstance(source, SourceChain):
                raise ValueError("invalid source chain")
            source.__post_init__()
        for text in (
            self.metric_key,
            self.release_id,
            self.geography,
            self.geography_kind,
            self.period,
            self.unit,
            self.reason,
        ):
            if type(text) is not str or not text.strip():
                raise ValueError("missing metadata or lineage")


def require_aligned(
    rows: Iterable[Measure],
    *,
    unit: str | None = None,
    period: bool = True,
    geography: bool = True,
) -> None:
    """Refuse a card input whose unit, period or geography does not match."""
    rows = tuple(rows)
    if not rows:
        raise ValueError("missing metadata or lineage")
    for row in rows:
        if not isinstance(row, Measure):
            raise MeasureMismatch("unit")
        if unit is not None and row.unit != unit:
            raise MeasureMismatch("unit")
    if period and len({row.period for row in rows}) != 1:
        raise MeasureMismatch("period")
    if geography and len({(row.geography, row.geography_kind) for row in rows}) != 1:
        raise MeasureMismatch("geography")


def emit(
    value: Number,
    *,
    unit: str,
    places: int,
    metric_key: str,
    release_id: str,
    geography: str,
    geography_kind: str,
    period: str,
    inputs: Iterable[Measure],
    base_period: str = "",
    base_geography: str = "",
    base_geography_kind: str = "",
) -> CalculationFact:
    """Round once for display. The class and the chains come only from the inputs."""
    inputs = tuple(inputs)
    if not isinstance(value, Approximate):
        value = exact(value)
    if not inputs:
        raise ValueError("missing metadata or lineage")
    for row in inputs:
        row.__post_init__()
    if (geography, geography_kind) not in {
        (r.geography, r.geography_kind) for r in inputs
    }:
        raise MeasureMismatch("geography")
    periods = {r.period for r in inputs}
    if ".." in period:
        first, last = period.split("..")
        if first > last or not all(first <= p <= last for p in periods):
            raise MeasureMismatch("period")
    elif period not in periods:
        raise MeasureMismatch("period")
    if base_period and base_period not in periods:
        raise MeasureMismatch("period")
    if base_geography and (base_geography, base_geography_kind) not in {
        (r.geography, r.geography_kind) for r in inputs
    }:
        raise MeasureMismatch("geography")
    classes = tuple(row.input_class for row in inputs)
    status = weakest_evidence(tuple(row.evidence_status for row in inputs))
    sources = tuple(dict.fromkeys(source for row in inputs for source in row.sources))
    shown = Decimal(rounded(value, places))
    fact = CalculationFact(
        value=shown,
        unit=unit,
        metric_key=metric_key,
        release_id=release_id,
        geography=geography,
        geography_kind=geography_kind,
        period=period,
        input_classes=classes,
        sources=sources,
        evidence_status=status,
        base_period=base_period,
        base_geography=base_geography,
        base_geography_kind=base_geography_kind,
        places=places,
    )
    object.__setattr__(fact, "exact_unrounded", value)
    return fact


@dataclass(frozen=True)
class CalculationFact:
    value: Decimal | str
    unit: str
    metric_key: str
    release_id: str
    geography: str
    period: str
    input_classes: tuple[str, ...]
    sources: tuple[SourceLink, ...]
    evidence_status: str = "observed"
    geography_kind: str = ""
    base_geography: str = ""
    base_geography_kind: str = ""
    base_period: str = ""
    places: int | None = None
    exact_unrounded: Number | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        _geography(self.geography, self.geography_kind)
        least_real(self.input_classes)
        if (
            type(self.evidence_status) is not str
            or self.evidence_status not in _EVIDENCE_RANK
        ):
            raise ValueError("invalid evidence status")
        if "user_input" in self.input_classes and self.evidence_status != "inferred":
            raise ValueError("user inputs must be inferred")
        if not isinstance(self.sources, tuple):
            raise ValueError("invalid source chain")
        if (
            not all(
                type(text) is str and text.strip()
                for text in (
                    self.metric_key,
                    self.release_id,
                    self.geography,
                    self.period,
                )
            )
            or not self.sources
        ):
            raise ValueError("missing metadata or lineage")
        for source in self.sources:
            if not isinstance(source, SourceChain):
                raise ValueError("invalid source chain")
            source.__post_init__()
        if type(self.unit) is not str:
            raise ValueError("unsupported numeric unit")
        if self.unit == "direction":
            if type(self.value) is not str or self.value not in (
                "higher",
                "lower",
                "equal",
            ):
                raise ValueError("invalid direction")
        elif self.unit in BAND_UNITS:
            _band(self.value, self.unit)
        else:
            if self.unit not in NUMERIC_UNITS:
                raise ValueError("unsupported numeric unit")
            if type(self.value) is not Decimal:
                raise ValueError("numeric value required")
            finite(self.value)
            if self.unit == "count" and self.value != self.value.to_integral_value():
                raise ValueError("fractional count")

    @property
    def provenance(self) -> str:
        return least_real(self.input_classes)


@dataclass(frozen=True, kw_only=True)
class ComparisonContext:
    metric_key: str
    before_geography: str = ""
    before_geography_kind: str = ""
    before_period: str = ""
    after_geography: str = ""
    after_geography_kind: str = ""
    after_period: str = ""
    sources: tuple[SourceChain, ...] = ()


@dataclass(frozen=True, kw_only=True)
class Comparison(ComparisonContext):
    difference: CalculationFact | NoData | Suppressed
    ratio: CalculationFact | NoData | Suppressed
    direction: CalculationFact | NoData | Suppressed
    difference_unrounded: Number | None = None
    ratio_unrounded: Number | None = None


@dataclass(frozen=True, kw_only=True)
class BandComparison(ComparisonContext):
    direction: CalculationFact | NoData | Suppressed


def _adjacent(before: str, after: str) -> bool:
    if _YEAR.fullmatch(before) and _YEAR.fullmatch(after):
        return int(after) == int(before) + 1
    if not _MONTH.fullmatch(before) or not _MONTH.fullmatch(after):
        return False
    y0, m0 = map(int, before.split("-"))
    y1, m1 = map(int, after.split("-"))
    return y1 * 12 + m1 == y0 * 12 + m0 + 1


def _side_sources(fact: CalculationFact | WithheldInput) -> tuple[SourceLink, ...]:
    return fact.sources


def compare_public_facts(
    before: CalculationFact | WithheldInput | None,
    after: CalculationFact | WithheldInput | None,
) -> Comparison | BandComparison:
    """Validate both sides before any withheld/missing branch; preserve their chains."""
    sides = tuple(side for side in (before, after) if side is not None)
    if not sides:
        raise ValueError("both comparison inputs missing")
    for side in sides:
        side.__post_init__()
        if isinstance(side, CalculationFact) and (
            side.provenance != "public" or "user_input" in side.input_classes
        ):
            raise ValueError("Public release inputs only")
    sources = tuple(dict.fromkeys(source for side in sides for source in side.sources))
    context = ComparisonContext(
        metric_key=sides[0].metric_key,
        before_geography=before.geography if before else "",
        before_geography_kind=before.geography_kind if before else "",
        before_period=before.period if before else "",
        after_geography=after.geography if after else "",
        after_geography_kind=after.geography_kind if after else "",
        after_period=after.period if after else "",
    )

    def result(
        difference: CalculationFact | NoData | Suppressed,
        quotient: CalculationFact | NoData | Suppressed,
        direction: CalculationFact | NoData | Suppressed,
        delta: Number | None = None,
        multiple: Number | None = None,
    ) -> Comparison:
        return Comparison(
            metric_key=context.metric_key,
            before_geography=context.before_geography,
            before_geography_kind=context.before_geography_kind,
            before_period=context.before_period,
            after_geography=context.after_geography,
            after_geography_kind=context.after_geography_kind,
            after_period=context.after_period,
            sources=sources,
            difference=difference,
            ratio=quotient,
            direction=direction,
            difference_unrounded=delta,
            ratio_unrounded=multiple,
        )

    if before is None or after is None:
        missing = NoData("missing_input")
        return result(missing, missing, missing)
    if (before.release_id, before.metric_key, before.unit) != (
        after.release_id,
        after.metric_key,
        after.unit,
    ):
        raise ValueError("incompatible comparison")
    same_area_series = (
        before.geography == after.geography
        and before.geography_kind == after.geography_kind
        and _adjacent(before.period, after.period)
    )
    same_month_areas = (
        before.geography != after.geography
        and before.period == after.period
        and before.geography_kind == after.geography_kind
        and _MONTH.fullmatch(before.period) is not None
    )
    if not (same_area_series or same_month_areas):
        raise ValueError("incompatible period/geography")
    if isinstance(before, WithheldInput) or isinstance(after, WithheldInput):
        reasons = tuple(
            side.reason for side in sides if isinstance(side, WithheldInput)
        )
        held = Suppressed(reasons[0], reasons=reasons)
        return result(held, held, held)
    status = weakest_evidence((before.evidence_status, after.evidence_status))
    base = replace(
        after,
        sources=sources,
        evidence_status=status,
        base_geography=before.geography,
        base_geography_kind=before.geography_kind,
        base_period=before.period,
    )
    if before.unit in BAND_UNITS:
        low0, high0 = _band(before.value, before.unit)
        low1, high1 = _band(after.value, after.unit)
        direction = (
            "equal"
            if (low0, high0) == (low1, high1)
            else "higher"
            if low1 > high0
            else "lower"
            if high1 < low0
            else None
        )
        return BandComparison(
            metric_key=context.metric_key,
            before_geography=context.before_geography,
            before_geography_kind=context.before_geography_kind,
            before_period=context.before_period,
            after_geography=context.after_geography,
            after_geography_kind=context.after_geography_kind,
            after_period=context.after_period,
            sources=sources,
            direction=replace(
                base,
                metric_key=base.metric_key + ".direction",
                value=direction,
                unit="direction",
            )
            if direction is not None
            else NoData("not_coverable"),
        )
    value0 = (
        before.exact_unrounded if before.exact_unrounded is not None else before.value
    )
    value1 = after.exact_unrounded if after.exact_unrounded is not None else after.value
    if not isinstance(value0, (Decimal, Fraction)) or not isinstance(
        value1, (Decimal, Fraction)
    ):
        raise ValueError("numeric comparison required")

    def number(value: Number, suffix: str, unit: str, places: int) -> CalculationFact:
        return emit(
            value,
            unit=unit,
            places=places,
            metric_key=before.metric_key + suffix,
            release_id=before.release_id,
            geography=after.geography,
            geography_kind=after.geography_kind,
            period=after.period,
            inputs=_measures_from(before, after),
            base_period=before.period,
            base_geography=before.geography,
            base_geography_kind=before.geography_kind,
        )

    with localcontext(CALC_CONTEXT):
        delta = subtract(value1, value0)
        places = before.places
        if places is None:
            places = (
                0 if before.unit == "count" else 1 if before.unit == "percent" else 2
            )
        difference = number(delta, ".difference", before.unit, places)
        multiple = divide(value1, value0) if compare(value0, Fraction(0)) != 0 else None
        quotient = (
            number(multiple, ".ratio", "ratio", _RATIO_PLACES)
            if multiple is not None
            else NoData("no_denominator")
        )
        direction = (
            "higher"
            if compare(value1, value0) > 0
            else "lower"
            if compare(value1, value0) < 0
            else "equal"
        )
        return result(
            difference,
            quotient,
            replace(
                base,
                metric_key=base.metric_key + ".direction",
                value=direction,
                unit="direction",
            ),
            delta,
            multiple,
        )


def _measures_from(
    before: CalculationFact, after: CalculationFact
) -> tuple[Measure, ...]:
    """Rebuild the input rows so emit derives the class and cannot be given one."""

    def one(fact: CalculationFact) -> Measure:
        value = fact.value if isinstance(fact.value, Decimal) else Decimal(0)
        return Measure(
            value,
            fact.unit if fact.unit in NUMERIC_UNITS else "count",
            fact.period,
            fact.geography,
            fact.geography_kind,
            fact.provenance,
            fact.sources,
            fact.evidence_status,
            fact.metric_key,
        )

    return (one(before), one(after))


def order_changes(
    changes: Sequence[Comparison | BandComparison],
) -> tuple[Comparison | BandComparison, ...]:
    """Largest absolute distance of the unrounded ratio from 1, then metric key."""

    def key(change: Comparison | BandComparison) -> tuple[bool, Number, str]:
        if isinstance(change, BandComparison) or isinstance(
            change.ratio, (NoData, Suppressed)
        ):
            return True, Decimal(0), change.metric_key
        value = change.ratio_unrounded
        if not isinstance(value, (Decimal, Fraction)) or type(value) not in (
            Decimal,
            Fraction,
            Approximate,
        ):
            raise ValueError("numeric ratio required")
        with localcontext(CALC_CONTEXT):
            difference = subtract(value, Fraction(1))
            score = (
                Approximate(-abs(difference))
                if isinstance(difference, Decimal)
                else -abs(difference)
            )
            return False, score, change.metric_key

    def ordered(
        left: Comparison | BandComparison, right: Comparison | BandComparison
    ) -> int:
        missing0, score0, name0 = key(left)
        missing1, score1, name1 = key(right)
        if missing0 != missing1:
            return 1 if missing0 else -1
        order = compare(score0, score1)
        return order if order else (name0 > name1) - (name0 < name1)

    for change in changes:
        key(change)
    return tuple(sorted(changes, key=cmp_to_key(ordered)))
