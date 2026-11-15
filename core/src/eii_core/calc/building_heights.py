"""C42 / MTH-123: the PUB-106 height order, overlap choice and fallback errors.

Reads no file, network, clock or random source; callers pass the values. The
closed list of height sources is `recorded`, `floor_count`, `3dglobfp`, `wsf3d`
and `none`. Heights are estimates, never a data value (FE-50, FE-52). A height
in metres and each error statistic are rounded once here, half-up, to
HEIGHT_PLACES decimals of a metre, and never pass through a float.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext

from .public_series import CALC_CONTEXT, ZERO, finite

ORDER = ("recorded", "floor_count", "3dglobfp", "wsf3d")
FALLBACKS = ORDER[1:]
NONE_SOURCE = "none"
HEIGHT_SOURCES = frozenset((*ORDER, NONE_SOURCE))
ORDER_EXHAUSTED = "order_exhausted"
NO_PAIRS = "no_pairs"
HEIGHT_PLACES = 2
_METRES_QUANTUM = Decimal(1).scaleb(-HEIGHT_PLACES)


@dataclass(frozen=True)
class HeightChoice:
    """The height the order gives one building, or `none` with its reason."""

    height: Decimal | None
    source: str
    reason: str


@dataclass(frozen=True)
class FallbackError:
    """One fallback's measured error; no pair gives count 0 and a reason."""

    count: int
    mean_signed: Decimal | None
    mean_absolute: Decimal | None
    median_absolute: Decimal | None
    reason: str


def _positive(value: Decimal, name: str) -> None:
    """Every height, floor count and storey height is a positive finite Decimal."""
    finite(value)
    if value <= ZERO:
        raise ValueError(f"{name} must be positive")


def metres(value: Decimal) -> Decimal:
    """Round a height or error statistic once, half-up, to HEIGHT_PLACES."""
    finite(value)
    with localcontext(CALC_CONTEXT):
        return value.quantize(_METRES_QUANTUM)


def floor_height(floor_count: Decimal, storey_height: Decimal) -> Decimal:
    """A floor count times one stated storey height (PUB-106)."""
    _positive(floor_count, "floor_count")
    _positive(storey_height, "storey_height")
    with localcontext(CALC_CONTEXT):
        return metres(floor_count * storey_height)


def choose_height(candidates: Mapping[str, Decimal | None]) -> HeightChoice:
    """The first present candidate in PUB-106's order, or `order_exhausted`."""
    if set(candidates) - set(ORDER):
        raise ValueError("candidate outside the closed order")
    present = {name: value for name, value in candidates.items() if value is not None}
    for name, value in present.items():
        _positive(value, name)
    for name in ORDER:
        if name in present:
            return HeightChoice(metres(present[name]), name, "")
    return HeightChoice(None, NONE_SOURCE, ORDER_EXHAUSTED)


def largest_overlap(
    candidates: Iterable[tuple[Decimal, str, int, Decimal]],
) -> tuple[Decimal, str, int, Decimal] | None:
    """The largest overlap area; a residual tie takes the lowest (file, row)."""
    rows = list(candidates)
    for area, _file, _row, _height in rows:
        finite(area)
        if area < ZERO:
            raise ValueError("overlap area must not be negative")
    if not rows:
        return None
    with localcontext(CALC_CONTEXT):
        return min(rows, key=lambda item: (-item[0], item[1], item[2]))


def fallback_errors(
    rows: Iterable[Mapping[str, Decimal | None]],
) -> dict[str, FallbackError]:
    """Each fallback's error over the buildings holding it and a recorded height.

    The pairs come from the candidate rows, never from the chosen height, so a
    recorded win still counts its fallback. Signed error is the fallback minus
    the recorded height in metres; the median of an even count is the mean of
    the two central values. A fallback with no pair gives count 0 and a reason.
    """
    pairs: dict[str, list[tuple[Decimal, Decimal]]] = {name: [] for name in FALLBACKS}
    for row in rows:
        if set(row) - set(ORDER):
            raise ValueError("candidate outside the closed order")
        recorded = row.get("recorded")
        if recorded is None:
            continue
        _positive(recorded, "recorded")
        recorded_height = metres(recorded)
        for name in FALLBACKS:
            value = row.get(name)
            if value is not None:
                _positive(value, name)
                pairs[name].append((metres(value), recorded_height))
    result: dict[str, FallbackError] = {}
    with localcontext(CALC_CONTEXT):
        for name in FALLBACKS:
            found = pairs[name]
            if not found:
                result[name] = FallbackError(0, None, None, None, NO_PAIRS)
                continue
            errors = [fallback - recorded for fallback, recorded in found]
            absolutes = sorted(abs(error) for error in errors)
            total = len(errors)
            middle = total // 2
            median = (
                absolutes[middle]
                if total % 2
                else (absolutes[middle - 1] + absolutes[middle]) / 2
            )
            result[name] = FallbackError(
                total,
                metres(sum(errors, ZERO) / total),
                metres(sum(absolutes, ZERO) / total),
                metres(median),
                "",
            )
    return result
