"""Measure GlobalBuildingAtlas against recorded heights (decision 0064 item 25)."""

from __future__ import annotations

from decimal import Decimal

from eii_core.calc.building_heights import (
    FallbackError,
    error_from_pairs,
    errors_by_class,
    height_value,
    largest_overlap,
)

from .landmark_select import KINDS
from .landmarks import LandmarkHeight
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
        gba_height = height_value(winner[-1])
        if gba_height is None:
            continue
        class_name = _class_name(result.gba, winner[1], winner[2])
        pairs.append((gba_height, recorded_height))
        class_pairs.append((gba_height, recorded_height, class_name))
    return {
        "state": "measured",
        "reason": "",
        "order_status": "pending_owner_decision",
        "overall": _error_block(error_from_pairs(pairs)),
        "by_class": {
            name: _error_block(error)
            for name, error in sorted(errors_by_class(class_pairs).items())
        },
        "terms_read_on": result.terms_read_on,
        "terms_words": result.terms_words,
    }


__all__ = ["gba_calibration"]


def landmark_calibration(
    landmarks: tuple[LandmarkHeight, ...], pending: str
) -> dict[str, object]:
    """Readiness is cleared only for the nonempty, receipt-verified list."""
    by_kind = dict.fromkeys(KINDS, 0)
    for row in landmarks:
        by_kind[row.height_kind] += 1
    return {
        "landmark_count": len(landmarks),
        "pending": pending or ("" if landmarks else "landmark_list_empty"),
        "by_kind": by_kind,
    }
