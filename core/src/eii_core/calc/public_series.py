"""Exact arithmetic for document 07 cards C2, C3, C4, C5 and C9."""

from collections.abc import Mapping, Sequence
from decimal import (
    ROUND_HALF_UP,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from fractions import Fraction
from statistics import median
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from .facts import CalculationFact, Measure, NoData

# Every field is explicit: never inherit mutable decimal.DefaultContext settings.
CALC_CONTEXT = Context(
    prec=50,
    rounding=ROUND_HALF_UP,
    Emin=-999999,
    Emax=999999,
    capitals=1,
    clamp=0,
    flags=[],
    traps=[InvalidOperation, DivisionByZero, Overflow],
)

Group = tuple[Decimal, Decimal]
ZERO = Decimal(0)
C2_CALENDAR = tuple(f"{2015 + i // 12}-{i % 12 + 1:02}" for i in range(125))


def finite(value: Decimal) -> None:
    """Reject missing, non-decimal and non-finite numeric cells."""
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError("finite Decimal required")


def count(value: int) -> None:
    """Counts cannot be fractional, negative or booleans."""
    if type(value) is not int or value < 0:
        raise ValueError("non-negative integer count required")


class Approximate(Decimal):
    """A fifty-digit irrational result, never an exact source decimal."""


Number = Decimal | Fraction
BOUNDARY_DISTANCE = Fraction(1, 10**40)


def decimal_value(value: Number) -> Decimal:
    """Convert only for an explicitly approximate calculation."""
    if isinstance(value, Decimal):
        return value
    with localcontext(CALC_CONTEXT):
        return Decimal(value.numerator) / Decimal(value.denominator)


def subtract(left: Number, right: Number) -> Number:
    if isinstance(left, Approximate) or isinstance(right, Approximate):
        with localcontext(CALC_CONTEXT):
            return Approximate(decimal_value(left) - decimal_value(right))
    return exact(left) - exact(right)


def divide(left: Number, right: Number) -> Number:
    if isinstance(left, Approximate) or isinstance(right, Approximate):
        with localcontext(CALC_CONTEXT):
            return Approximate(decimal_value(left) / decimal_value(right))
    return exact(left) / exact(right)


def compare(left: Number, right: Number) -> int:
    first = Fraction(left) if isinstance(left, Approximate) else exact(left)
    second = Fraction(right) if isinstance(right, Approximate) else exact(right)
    distance = first - second
    if (isinstance(left, Approximate) or isinstance(right, Approximate)) and abs(
        distance
    ) <= BOUNDARY_DISTANCE:
        raise ValueError("undecidable comparison boundary")
    return (distance > 0) - (distance < 0)


def exact(value: Decimal | Fraction) -> Fraction:
    """Admit finite Decimal source cells or exact internal rational values."""
    if type(value) is Fraction:
        return value
    if not isinstance(value, Decimal):
        raise ValueError("finite Decimal required")
    finite(value)
    return Fraction(value)


def rounded(value: Decimal | Fraction, places: int) -> str:
    """Round the exact rational once, half up; zero has no negative sign."""
    if isinstance(value, Approximate):
        scaled = Fraction(value) * Fraction(10) ** places
        boundary = Fraction(scaled.numerator // scaled.denominator) + Fraction(1, 2)
        if abs(scaled - boundary) / (Fraction(10) ** places) <= BOUNDARY_DISTANCE:
            raise ValueError("undecidable rounding boundary")
    else:
        scaled = exact(value) * Fraction(10) ** places
    magnitude = abs(scaled.numerator)
    denominator = scaled.denominator
    whole = (2 * magnitude + denominator) // (2 * denominator)
    sign = int(scaled < 0 and whole != 0)
    digits = tuple(int(c) for c in str(whole))
    return format(Decimal((sign, digits, -places)), "f")


def ratio(numerator: Decimal | Fraction, denominator: Decimal | Fraction) -> Fraction:
    """Divide exact inputs only by a positive denominator."""
    numerator, denominator = exact(numerator), exact(denominator)
    if denominator <= ZERO:
        raise ValueError("non-positive denominator")
    return numerator / denominator


def growth(
    before: Decimal | Fraction, after: Decimal | Fraction, *, partial_year: bool = False
) -> Fraction:
    """Percentage change; never annualise or compare a partial year."""
    if partial_year:
        raise ValueError("partial year cannot be compared")
    return (ratio(after, before) - 1) * 100


def weighted_mean(groups: Mapping[str, Group]) -> tuple[Fraction, Fraction]:
    """Return paid workers and their weighted mean, without rounding."""
    with localcontext(CALC_CONTEXT):
        for workers_count, wage in groups.values():
            finite(workers_count)
            finite(wage)
            if (
                workers_count < 0
                or workers_count != workers_count.to_integral_value()
                or wage < 0
            ):
                raise ValueError("invalid group cell")
        workers = sum(
            (Fraction(count) for count, _ in (groups[k] for k in sorted(groups))),
            Fraction(0),
        )
        bill = sum(
            (
                Fraction(count) * Fraction(wage)
                for count, wage in (groups[k] for k in sorted(groups))
            ),
            Fraction(0),
        )
        return workers, ratio(bill, workers)


def _kitagawa(
    before: Mapping[str, Group], after: Mapping[str, Group]
) -> dict[str, Fraction]:
    """Unrounded Kitagawa split. Display rounding is `decomposition`'s job."""
    with localcontext(CALC_CONTEXT):
        if before.keys() != after.keys():
            raise ValueError("different groups")
        n0, mean0 = map(exact, weighted_mean(before))
        n1, mean1 = map(exact, weighted_mean(after))
        within, mix = Fraction(0), Fraction(0)
        for group in sorted(before):
            count0, wage0 = map(Fraction, before[group])
            count1, wage1 = map(Fraction, after[group])
            s0, s1 = count0 / n0, count1 / n1
            within += (s0 + s1) / 2 * (wage1 - wage0)
            mix += (wage0 + wage1) / 2 * (s1 - s0)
        change = mean1 - mean0
        if within + mix != change:
            raise ValueError("within + mix != change")
        fixed_mean = sum(
            (
                Fraction(before[g][0]) / n0 * Fraction(after[g][1])
                for g in sorted(before)
            ),
            Fraction(0),
        )
        return {
            "mean_before_unrounded": mean0,
            "mean_after_unrounded": mean1,
            "change_unrounded": change,
            "within_unrounded": within,
            "mix_unrounded": mix,
            "fixed_composition_mean_unrounded": fixed_mean,
            "fixed_composition_change_unrounded": fixed_mean - mean0,
            "groups": Fraction(len(before)),
        }


@overload
def decomposition(
    before: Mapping[str, Group], after: Mapping[str, Group]
) -> dict[str, Fraction]: ...


@overload
def decomposition(
    before: Mapping[str, tuple[Measure, Measure]],
    after: Mapping[str, tuple[Measure, Measure]],
) -> dict[str, CalculationFact | Fraction | NoData]: ...


def decomposition(
    before: Mapping[str, Group] | Mapping[str, tuple[Measure, Measure]],
    after: Mapping[str, Group] | Mapping[str, tuple[Measure, Measure]],
) -> dict[str, Fraction] | dict[str, CalculationFact | Fraction | NoData]:
    """C3 on typed rows: group -> (workers Measure, wage Measure).

    Display money is rounded once, half-up, to the riyal. Components kept for
    a further calculation are named `*_unrounded`.
    """
    from .facts import Measure, MeasureMismatch, NoData, emit, require_aligned

    sample = next(iter(before.values()), None)
    if isinstance(sample, tuple) and sample and isinstance(sample[0], Decimal):

        def decimals(
            rows: Mapping[str, Group | tuple[Measure, Measure]],
        ) -> dict[str, Group]:
            parsed: dict[str, Group] = {}
            for key, cell in rows.items():
                left, right = cell
                if type(left) is not Decimal or type(right) is not Decimal:
                    raise ValueError("invalid group cell")
                parsed[key] = (left, right)
            return parsed

        exact = _kitagawa(decimals(before), decimals(after))
        return {
            "mean_before": exact["mean_before_unrounded"],
            "mean_after": exact["mean_after_unrounded"],
            "change": exact["change_unrounded"],
            "within": exact["within_unrounded"],
            "mix": exact["mix_unrounded"],
            "groups": exact["groups"],
            "fixed_composition_change": exact["fixed_composition_change_unrounded"],
        }

    def pairs(
        rows: Mapping[str, tuple[object, object]],
    ) -> list[tuple[str, Measure, Measure]]:
        parsed: list[tuple[str, Measure, Measure]] = []
        for group, cell in rows.items():
            if (
                type(group) is not str
                or not isinstance(cell, tuple)
                or len(cell) != 2
                or not isinstance(cell[0], Measure)
                or not isinstance(cell[1], Measure)
            ):
                raise ValueError("invalid group cell")
            parsed.append((group, cell[0], cell[1]))
        if not parsed:
            raise ValueError("invalid group cell")
        workers = tuple(worker for _, worker, _ in parsed)
        wages = tuple(wage for _, _, wage in parsed)
        require_aligned(workers, unit="count")
        require_aligned(wages, unit="qar_per_month")
        require_aligned((*workers, *wages))
        return parsed

    before_rows = sorted(pairs(before), key=lambda row: row[0])
    after_rows = sorted(pairs(after), key=lambda row: row[0])
    if before_rows[0][1].period == after_rows[0][1].period:
        raise MeasureMismatch("period")
    if (before_rows[0][1].geography, before_rows[0][1].geography_kind) != (
        after_rows[0][1].geography,
        after_rows[0][1].geography_kind,
    ):
        raise MeasureMismatch("geography")
    before_groups = {
        group: (worker.value, wage.value) for group, worker, wage in before_rows
    }
    after_groups = {
        group: (worker.value, wage.value) for group, worker, wage in after_rows
    }
    exact = _kitagawa(before_groups, after_groups)
    inputs = tuple(
        cell for row in (*before_rows, *after_rows) for cell in (row[1], row[2])
    )
    geography = before_rows[0][1].geography
    kind = before_rows[0][1].geography_kind
    period = after_rows[0][1].period

    base_period = before_rows[0][1].period

    def money(name: str, value: Fraction) -> CalculationFact:
        return emit(
            value,
            unit="qar_per_month",
            places=0,
            metric_key=name,
            release_id="published",
            geography=geography,
            geography_kind=kind,
            period=base_period if name == "mean_before" else period,
            base_period="" if name in ("mean_before", "mean_after") else base_period,
            base_geography=geography,
            base_geography_kind=kind,
            inputs=inputs,
        )

    def percent(name: str, value: Fraction | None) -> CalculationFact | NoData:
        if value is None:
            return NoData("no_denominator")
        return emit(
            value,
            unit="percent",
            places=1,
            metric_key=name,
            release_id="published",
            geography=geography,
            geography_kind=kind,
            period=period,
            base_period=base_period,
            base_geography=geography,
            base_geography_kind=kind,
            inputs=inputs,
        )

    change = exact["change_unrounded"]
    mean0 = exact["mean_before_unrounded"]
    mean1 = exact["mean_after_unrounded"]
    with localcontext(CALC_CONTEXT):
        mix_share = exact["mix_unrounded"] / change * 100 if change != 0 else None
        fixed = exact["fixed_composition_change_unrounded"]
        fixed_percent = ratio(fixed, mean0) * 100
        return {
            "mean_before": money("mean_before", mean0),
            "mean_after": money("mean_after", mean1),
            "change": money("change", change),
            "within": money("within", exact["within_unrounded"]),
            "mix": money("mix", exact["mix_unrounded"]),
            "fixed_composition_change": money("fixed_composition_change", fixed),
            "mix_share_percent": percent("mix_share", mix_share),
            "fixed_composition_percent": percent(
                "fixed_composition_percent", fixed_percent
            ),
            "change_percent": percent(
                "change_percent", (ratio(mean1, mean0) - 1) * 100
            ),
            **{key: value for key, value in exact.items() if key != "groups"},
            "populated_groups": emit(
                Decimal(
                    sum(
                        before_groups[g][0] > 0 or after_groups[g][0] > 0
                        for g in before_groups
                    )
                ),
                unit="count",
                places=0,
                metric_key="populated_groups",
                release_id="published",
                geography=geography,
                geography_kind=kind,
                period=period,
                inputs=inputs,
            ),
        }


def unit_value(
    rows: Sequence[tuple[Decimal, Decimal, str]],
) -> tuple[Fraction | None, int, int]:
    """Return QAR/kg, other-unit count and non-positive-kg count (PUB-45)."""
    with localcontext(CALC_CONTEXT):
        value, weight = Fraction(0), Fraction(0)
        other, missing = 0, 0
        for qar, kg, unit in rows:
            finite(qar)
            finite(kg)
            if qar < 0:
                raise ValueError("negative import value")
            if unit != "kg":
                other += 1
            elif kg <= ZERO:
                missing += 1
            else:
                value += Fraction(qar)
                weight += Fraction(kg)
        return (value / weight if weight > ZERO else None), other, missing


def bulk_months(totals: Mapping[str, Decimal]) -> tuple[str, ...]:
    """C2 calendar includes zero-row months; undated rows never enter it."""
    calendar = C2_CALENDAR
    for month, value in totals.items():
        finite(value)
        if month not in calendar or value < 0 or value != value.to_integral_value():
            raise ValueError("invalid cancellation month/count")
    with localcontext(CALC_CONTEXT):
        threshold = 3 * median(totals.get(month, ZERO) for month in calendar)
        return tuple(month for month in calendar if totals.get(month, ZERO) > threshold)
