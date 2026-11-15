"""C42 / MTH-123: the PUB-106 height order, overlap choice and fallback errors.

Reads no file, network, clock or random source; callers pass the values. The
closed list of height sources is `recorded`, `floor_count`, `3dglobfp`, `wsf3d`
and `none`. Heights are estimates, never a data value (FE-50, FE-52). A height
in metres and each error statistic are rounded once here, half-up, to
HEIGHT_PLACES decimals of a metre, and never pass through a float. A fallback
value that is not a positive finite number, or that rounds to zero at the
stated places, is no value for that source for that building, counted by name,
and never a crash.
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
    """The height the order gives one building, or `none` with its reason.

    `dropped` names each fallback source whose candidate was no value: a
    value that is not positive and finite, or that rounds to zero.
    """

    height: Decimal | None
    source: str
    reason: str
    dropped: tuple[str, ...] = ()


@dataclass(frozen=True)
class FallbackError:
    """One fallback's measured error; no pair gives count 0 and a reason."""

    count: int
    mean_signed: Decimal | None
    mean_absolute: Decimal | None
    median_absolute: Decimal | None
    reason: str


@dataclass(frozen=True)
class HeightCounts:
    """Every count the manifest and the PASS line carry, in one place."""

    by_source: dict[str, int]
    none_reasons: dict[str, int]
    no_value_reasons: dict[str, int]
    fallback_buildings: int


def _positive(value: Decimal, name: str) -> None:
    """Every height, floor count and storey height is a positive finite Decimal."""
    finite(value)
    if value <= ZERO:
        raise ValueError(f"{name} must be positive")


def metres(value: Decimal) -> Decimal:
    """Round a height or error statistic once, half-up, to HEIGHT_PLACES.

    A rounded zero is written unsigned: "-0.00" is never returned.
    """
    finite(value)
    with localcontext(CALC_CONTEXT):
        rounded = value.quantize(_METRES_QUANTUM)
        return rounded if rounded else ZERO.quantize(_METRES_QUANTUM)


def height_value(value: Decimal) -> Decimal | None:
    """The usable, already rounded height a fallback candidate gives, or none.

    A value that is not a positive finite Decimal, that rounds to zero at the
    stated places, or that overflows the calculation context is no value.
    A non-Decimal is a defect of the caller, not data, and still raises.
    """
    if type(value) is not Decimal:
        raise ValueError("finite Decimal required")
    if not value.is_finite():
        return None
    try:
        rounded = metres(value)
    except ArithmeticError:
        return None
    return rounded if rounded > ZERO else None


def floor_height(floor_count: Decimal, storey_height: Decimal) -> Decimal:
    """A floor count times one stated storey height (PUB-106)."""
    _positive(floor_count, "floor_count")
    _positive(storey_height, "storey_height")
    with localcontext(CALC_CONTEXT):
        return metres(floor_count * storey_height)


def choose_height(candidates: Mapping[str, Decimal | None]) -> HeightChoice:
    """The first usable candidate in PUB-106's order, or `order_exhausted`.

    A fallback value that is no usable height is dropped and named in
    `dropped`, never a crash; a recorded value still refuses.
    """
    if set(candidates) - set(ORDER):
        raise ValueError("candidate outside the closed order")
    present: dict[str, Decimal] = {}
    dropped: list[str] = []
    for name in ORDER:
        raw = candidates.get(name)
        if raw is None:
            continue
        usable = height_value(raw)
        if usable is not None:
            present[name] = usable
        elif name == "recorded":
            raise ValueError(f"{name} must be positive")
        else:
            dropped.append(name)
    for name in ORDER:
        if name in present:
            return HeightChoice(present[name], name, "", tuple(dropped))
    return HeightChoice(None, NONE_SOURCE, ORDER_EXHAUSTED, tuple(dropped))


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
        recorded_height = height_value(recorded)
        if recorded_height is None:
            raise ValueError("recorded must be positive")
        for name in FALLBACKS:
            raw = row.get(name)
            if raw is not None:
                usable = height_value(raw)
                if usable is not None:
                    pairs[name].append((usable, recorded_height))
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


def height_counts(choices: Iterable[HeightChoice]) -> HeightCounts:
    """Counts by source, none reasons, dropped values and fallback buildings.

    The one place every count the manifest and the PASS line carry is
    computed, from the chosen heights alone (rules 16 and 17).
    """
    by_source = {name: 0 for name in (*ORDER, NONE_SOURCE)}
    none_reasons: dict[str, int] = {}
    no_value: dict[str, int] = {}
    fallback_buildings = 0
    for choice in choices:
        if choice.source not in HEIGHT_SOURCES:
            raise ValueError("height source outside the closed list")
        by_source[choice.source] += 1
        if choice.source == NONE_SOURCE:
            if not choice.reason:
                raise ValueError("a none choice needs its reason")
            none_reasons[choice.reason] = none_reasons.get(choice.reason, 0) + 1
        elif choice.source in FALLBACKS:
            fallback_buildings += 1
        for name in choice.dropped:
            if name not in FALLBACKS:
                raise ValueError("candidate outside the closed order")
            reason = f"{name}_value_not_positive"
            no_value[reason] = no_value.get(reason, 0) + 1
    return HeightCounts(by_source, none_reasons, no_value, fallback_buildings)
