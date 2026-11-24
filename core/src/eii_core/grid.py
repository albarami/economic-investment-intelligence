"""Stored-frame selection. No database access. The product never imports the custodian frame.

The base cell of a point is the stored cell that is the point's resolution-9
cell, or that cell's resolution-8 parent, or none. A missing cell is never
replaced by a nearest or neighbouring cell. Selection uses the resolution stored
on the row. An empty selection is an empty tuple.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from fractions import Fraction

import h3
from eii_core.shapes import Point, Polygon, point_in_polygon, within_radius

type Frame = Sequence[tuple[int, int]]


def base_cell(latitude: float, longitude: float, frame: Frame) -> int | None:
    """Return the stored resolution-9 cell or its stored resolution-8 parent."""
    fine_text = h3.latlng_to_cell(latitude, longitude, 9)
    fine = h3.str_to_int(fine_text)
    parent = h3.str_to_int(h3.cell_to_parent(fine_text, 8))
    stored = {cell: resolution for cell, resolution in frame}
    if fine in stored and stored[fine] == 9:
        return fine
    if parent in stored and stored[parent] == 8:
        return parent
    return None


def cells_in_polygon(polygon: Polygon, frame: Frame) -> tuple[int, ...]:
    """Stored cells whose centres lie inside the polygon, at the stored resolution."""
    return _selected(
        lambda centre: point_in_polygon(_float_point(centre), polygon),
        frame,
    )


def cells_in_circle(
    latitude: float, longitude: float, radius_m: float, frame: Frame
) -> tuple[int, ...]:
    """Stored cells whose centres lie within the great-circle cut-off."""
    centre = (latitude, longitude)
    return _selected(
        lambda point: within_radius(centre, point, radius_m),
        frame,
    )


def resolution_8_children(cell: int) -> tuple[int, ...]:
    """The seven resolution-9 children of a stored resolution-8 cell."""
    text = h3.int_to_str(cell)
    if h3.get_resolution(text) != 8:
        raise ValueError("resolution-8 cell required")
    children = tuple(
        sorted(h3.str_to_int(item) for item in h3.cell_to_children(text, 9))
    )
    return children


def cell_centre(cell: int) -> tuple[float, float]:
    """Latitude and longitude of the index centre the library names."""
    latitude, longitude = h3.cell_to_latlng(h3.int_to_str(cell))
    return (latitude, longitude)


def _selected(
    holds: Callable[[tuple[float, float]], bool], frame: Frame
) -> tuple[int, ...]:
    chosen: list[int] = []
    for cell, _resolution in frame:
        centre = cell_centre(cell)
        if holds(centre):
            chosen.append(cell)
    return tuple(sorted(set(chosen)))


def _float_point(centre: tuple[float, float]) -> Point:
    return (Fraction(centre[0]), Fraction(centre[1]))
