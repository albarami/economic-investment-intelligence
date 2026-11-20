"""Measure GlobalBuildingAtlas against recorded heights (decision 0064 item 25)."""

from __future__ import annotations

from decimal import Decimal, localcontext

from eii_core.calc.building_heights import (
    NO_PAIRS,
    FallbackError,
    errors_by_class,
    height_value,
    largest_overlap,
    metres,
)
from eii_core.calc.public_series import CALC_CONTEXT, ZERO

from .match import globfp_candidates, globfp_index, representative_point
from .model import Building
from .read import SourceResult


def _error_block(error: FallbackError) -> dict[str, object]:
    return {
        "count": error.count,
        "mean_absolute_error_m": (
            None if error.mean_absolute is None else str(error.mean_absolute)
        ),
        "mean_signed_error_m": (
            None if error.mean_signed is None else str(error.mean_signed)
        ),
        "median_absolute_error_m": (
            None if error.median_absolute is None else str(error.median_absolute)
        ),
        "reason": error.reason,
    }


def _pair_error(pairs: list[tuple[Decimal, Decimal]]) -> FallbackError:
    if not pairs:
        return FallbackError(0, None, None, None, NO_PAIRS)
    with localcontext(CALC_CONTEXT):
        errors = [fallback - recorded for fallback, recorded in pairs]
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


def _class_name(
    gba: tuple[tuple[str, tuple[tuple[object, Decimal, str], ...]], ...],
    file_name: str,
    row_index: int,
) -> str:
    for name, rows in gba:
        if name == file_name:
            return rows[row_index][2]
    return "unknown"


def gba_calibration(
    buildings: list[Building],
    result: SourceResult,
) -> dict[str, object]:
    """GBA heights compared to recorded heights, overall and by class."""
    if result.state == "absent":
        return {
            "state": "absent",
            "reason": result.reason,
            "order_status": "pending_owner_decision",
        }
    index = globfp_index(
        tuple(
            (name, tuple((geometry, height) for geometry, height, _class_name in rows))
            for name, rows in result.gba
        )
    )
    pairs: list[tuple[Decimal, Decimal]] = []
    class_pairs: list[tuple[Decimal, Decimal, str]] = []
    for building in buildings:
        recorded = building.recorded
        if recorded is None:
            continue
        recorded_height = height_value(recorded)
        if recorded_height is None:
            continue
        point = representative_point(building.geometry)
        matches = globfp_candidates(point, building.geometry, index)
        winner = largest_overlap(matches)
        if winner is None:
            continue
        gba_height = winner[-1]
        class_name = _class_name(result.gba, winner[1], winner[2])
        pairs.append((gba_height, recorded_height))
        class_pairs.append((gba_height, recorded_height, class_name))
    return {
        "state": "measured",
        "reason": "",
        "order_status": "pending_owner_decision",
        "overall": _error_block(_pair_error(pairs)),
        "by_class": {
            name: _error_block(error)
            for name, error in sorted(errors_by_class(class_pairs).items())
        },
        "terms_read_on": result.terms_read_on,
        "terms_words": result.terms_words,
    }


__all__ = ["gba_calibration"]
