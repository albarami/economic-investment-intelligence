"""Whole frame cells only; H3 centre containment, with no parent compaction."""

import math

import h3

from .shapes import Ring


def _nonempty(cells: set[str]) -> tuple[str, ...]:
    if not cells:
        raise ValueError("The shape covers no frame cell")
    return tuple(sorted(cells))


def snap_polygon(outline: Ring, frame: tuple[str, ...]) -> tuple[str, ...]:
    polygon = h3.LatLngPoly(outline)
    selected: set[str] = set()
    for resolution in {h3.get_resolution(cell) for cell in frame}:
        selected.update(h3.h3shape_to_cells(polygon, resolution))
    return _nonempty(selected.intersection(frame))


def snap_radius(
    pin_cell: str, radius_m: float, frame: tuple[str, ...]
) -> tuple[str, ...]:
    if not math.isfinite(radius_m) or radius_m <= 0:
        raise ValueError("Radius must be finite and positive")
    center = h3.cell_to_latlng(pin_cell)
    return _nonempty(
        {
            cell
            for cell in frame
            if h3.great_circle_distance(center, h3.cell_to_latlng(cell), unit="m")
            <= radius_m
        }
    )
