"""C47 / MTH-125: the PUB-106 height order, overlap choice and fallback errors.

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

from .public_series import CALC_CONTEXT, ZERO, count, finite

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
    """Every count the manifest and the PASS line carry, in one place.

    `tied_height_buildings` counts the buildings whose winning 3D-GloBFP
    overlap ties another candidate's area at a different height.
    """

    by_source: dict[str, int]
    none_reasons: dict[str, int]
    no_value_reasons: dict[str, int]
    fallback_buildings: int
    tied_height_buildings: int


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


def positive_height(value: Decimal) -> bool:
    """True when the value is a positive finite Decimal, with no rounding.

    The one predicate the heights readers apply to published height text:
    it never rounds or compares a rounded form, so a long digit text keeps
    every digit on its way in. A non-Decimal is a defect of the caller.
    """
    if type(value) is not Decimal:
        raise ValueError("finite Decimal required")
    return value.is_finite() and value > ZERO


def scaled_cell(stored: Decimal, scale: Decimal) -> Decimal:
    """A stored raster value times its declared scale, a Decimal throughout.

    The stored value is a finite Decimal on entry and the scale a positive
    finite Decimal; the product is computed once in the calculation context
    and handed back unchecked, so a stored value that is no usable height is
    the caller's own value rule to drop, and an overflow stays finite.
    """
    if type(stored) is not Decimal or not stored.is_finite():
        raise ValueError("finite Decimal required")
    if type(scale) is not Decimal or not scale.is_finite():
        raise ValueError("finite Decimal required")
    if scale <= ZERO:
        raise ValueError("scale must be positive")
    with localcontext(CALC_CONTEXT):
        return +(stored * scale)


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


def error_from_pairs(pairs: Iterable[tuple[Decimal, Decimal]]) -> FallbackError:
    """Signed and absolute error statistics for one list of fallback pairs."""
    found = list(pairs)
    if not found:
        return FallbackError(0, None, None, None, NO_PAIRS)
    with localcontext(CALC_CONTEXT):
        errors = [fallback - recorded for fallback, recorded in found]
        absolutes = sorted(abs(error) for error in errors)
        total = len(errors)
        middle = total // 2
        median = (
            absolutes[middle]
            if total % 2
            else (absolutes[middle - 1] + absolutes[middle]) / 2
        )
        return FallbackError(
            total,
            metres(sum(errors, ZERO) / total),
            metres(sum(absolutes, ZERO) / total),
            metres(median),
            "",
        )


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
    return {name: error_from_pairs(pairs[name]) for name in FALLBACKS}


def errors_by_class(
    pairs: Iterable[tuple[Decimal, Decimal, str]],
) -> dict[str, FallbackError]:
    """One fallback's error statistics within each named class."""
    grouped: dict[str, list[tuple[Decimal, Decimal]]] = {}
    for fallback, recorded, class_name in pairs:
        if not class_name:
            raise ValueError("class name required")
        grouped.setdefault(class_name, []).append((fallback, recorded))
    return {
        class_name: error_from_pairs(grouped[class_name])
        for class_name in sorted(grouped)
    }


GBA_EXCLUSIONS = (
    "geometry_null",
    "geometry_empty",
    "geometry_invalid",
    "height_null",
    "height_nodata",
    "height_non_finite",
    "height_non_positive",
)
GBA_COUNTERS = ("rows_in_bounds", "rows_kept", *GBA_EXCLUSIONS, "bbox_null")


def gba_exclusion(geometry_reason: str, value: Decimal | None, nodata: Decimal) -> str:
    """Geometry first, then height; exactly one outcome for each bounded row."""
    if geometry_reason:
        return geometry_reason
    if value is None:
        return "height_null"
    if value.is_finite() and value == nodata:
        return "height_nodata"
    if not value.is_finite():
        return "height_non_finite"
    if not positive_height(value):
        return "height_non_positive"
    return ""


def gba_read_counts(outcomes: Iterable[str]) -> dict[str, int]:
    """Count an exclusive row partition, including kept rows."""
    counts = dict.fromkeys(GBA_COUNTERS, 0)
    for reason in outcomes:
        if reason and reason not in GBA_EXCLUSIONS:
            raise ValueError("gba row outcome")
        counts["rows_in_bounds"] += 1
        counts[reason or "rows_kept"] += 1
    return counts


def sum_gba_read_counts(files: Iterable[Mapping[str, int]]) -> dict[str, int]:
    """Verify the bounded partition; sum it and the separate NULL-bbox count."""
    total = dict.fromkeys(GBA_COUNTERS, 0)
    for counts in files:
        if set(counts) != set(GBA_COUNTERS):
            raise ValueError("gba row accounting")
        for value in counts.values():
            count(value)
        if counts["rows_in_bounds"] != counts["rows_kept"] + sum(
            counts[name] for name in GBA_EXCLUSIONS
        ):
            raise ValueError("gba row accounting")
        for name in GBA_COUNTERS:
            total[name] += counts[name]
    return total


def tied_height(matches: Iterable[tuple[Decimal, str, int, Decimal]]) -> bool:
    """A winning-area tie at a different raw height, shared by both reports."""
    rows = list(matches)
    winner = largest_overlap(rows)
    return winner is not None and any(
        match[0] == winner[0] and match[-1] != winner[-1] for match in rows
    )


def gba_match_counts(
    rows: Iterable[tuple[Decimal | None, Iterable[tuple[Decimal, str, int, Decimal]]]],
) -> dict[str, int]:
    """Count recorded buildings, match outcomes and distinct shared footprints.

    largest_overlap accepts zero area, so there is no separate no_overlap
    outcome: no_footprint means no covering candidate. A shared footprint is
    one distinct (file, row) winning for more than one recorded building.
    """
    counts = dict.fromkeys(
        (
            "recorded_buildings",
            "matched",
            "no_footprint",
            "unusable_height",
            "recorded_height_unusable",
            "tied_height",
            "shared_footprint",
        ),
        0,
    )
    winners: dict[tuple[str, int], int] = {}
    for recorded, candidates in rows:
        if recorded is None:
            continue
        counts["recorded_buildings"] += 1
        matches = list(candidates)
        winner = largest_overlap(matches)
        if winner is None:
            counts["no_footprint"] += 1
            continue
        key = (winner[1], winner[2])
        winners[key] = winners.get(key, 0) + 1
        if tied_height(matches):
            counts["tied_height"] += 1
        if height_value(winner[-1]) is None:
            counts["unusable_height"] += 1
        elif height_value(recorded) is None:
            counts["recorded_height_unusable"] += 1
        else:
            counts["matched"] += 1
    counts["shared_footprint"] = sum(count > 1 for count in winners.values())
    if counts["recorded_buildings"] != sum(
        counts[name]
        for name in (
            "matched",
            "no_footprint",
            "unusable_height",
            "recorded_height_unusable",
        )
    ):
        raise ValueError("gba match accounting")
    return counts


def height_counts(
    choices: Iterable[HeightChoice],
    globfp_matches: Iterable[Iterable[tuple[Decimal, str, int, Decimal]]],
) -> HeightCounts:
    """Counts by source, none reasons, dropped values and fallback buildings.

    The one place every count the manifest and the PASS line carry is
    computed, from the chosen heights alone (rules 16 and 17). Each building's
    3D-GloBFP match list decides the tied-height count: a building counts once
    when its winning overlap ties another candidate's area at a different
    height. The match list is a required argument and pairs one row with each
    choice by index; a list whose length differs from the choices is refused.
    """
    rows = list(choices)
    match_rows = list(globfp_matches)
    if len(match_rows) != len(rows):
        raise ValueError("match list length differs from the choices")
    by_source = {name: 0 for name in (*ORDER, NONE_SOURCE)}
    none_reasons: dict[str, int] = {}
    no_value: dict[str, int] = {}
    fallback_buildings = 0
    tied_height_buildings = 0
    for choice, matches in zip(rows, match_rows, strict=True):
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
        if tied_height(matches):
            tied_height_buildings += 1
    return HeightCounts(
        by_source,
        none_reasons,
        no_value,
        fallback_buildings,
        tied_height_buildings,
    )
