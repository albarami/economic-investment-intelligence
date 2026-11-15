"""Decimal arithmetic for document 07 cards C2, C3, C4, C5 and C9."""

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

Group = tuple[Decimal, Decimal]
ZERO = Decimal(0)


def rounded(value: Decimal, places: int) -> str:
    """Round once, half up, at the output boundary."""
    return str(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Divide only by a positive denominator."""
    if denominator <= ZERO:
        raise ValueError("non-positive denominator")
    return numerator / denominator


def growth(before: Decimal, after: Decimal, *, partial_year: bool = False) -> Decimal:
    """Percentage change; never annualise or compare a partial year."""
    if partial_year:
        raise ValueError("partial year cannot be compared")
    return (ratio(after, before) - 1) * 100


def weighted_mean(groups: Mapping[str, Group]) -> tuple[Decimal, Decimal]:
    """Return paid workers and their weighted mean, without rounding."""
    workers = sum((count for count, _ in groups.values()), ZERO)
    bill = sum((count * wage for count, wage in groups.values()), ZERO)
    return workers, ratio(bill, workers)


def decomposition(
    before: Mapping[str, Group], after: Mapping[str, Group]
) -> dict[str, Decimal]:
    """Kitagawa average-weight split on the same populated groups (C3)."""
    if before.keys() != after.keys():
        raise ValueError("different groups")
    n0, mean0 = weighted_mean(before)
    n1, mean1 = weighted_mean(after)
    within, mix = ZERO, ZERO
    for group, (count0, wage0) in before.items():
        count1, wage1 = after[group]
        s0, s1 = count0 / n0, count1 / n1
        within += (s0 + s1) / 2 * (wage1 - wage0)
        mix += (wage0 + wage1) / 2 * (s1 - s0)
    return {
        "mean_before": mean0,
        "mean_after": mean1,
        "change": mean1 - mean0,
        "within": within,
        "mix": mix,
        "groups": Decimal(len(before)),
    }


def unit_value(
    rows: Sequence[tuple[Decimal, Decimal, str]],
) -> tuple[Decimal | None, int, int]:
    """Return QAR/kg, other-unit count and non-positive-kg count (PUB-45)."""
    value, weight = ZERO, ZERO
    other, missing = 0, 0
    for qar, kg, unit in rows:
        if unit != "kg":
            other += 1
        elif kg <= ZERO:
            missing += 1
        else:
            value += qar
            weight += kg
    return (value / weight if weight > ZERO else None), other, missing


def bulk_months(totals: Mapping[str, Decimal]) -> tuple[str, ...]:
    """C2 calendar includes zero-row months; undated rows never enter it."""
    calendar = tuple(f"{2015 + i // 12}-{i % 12 + 1:02}" for i in range(125))
    threshold = 3 * median(totals.get(month, ZERO) for month in calendar)
    return tuple(month for month in calendar if totals.get(month, ZERO) > threshold)
