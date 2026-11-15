"""B5: the geometry of the two matching rules. No height arithmetic lives here.

The representative point is shapely's `point_on_surface`, an interior point
guaranteed inside the polygon (the frame's gazetteer uses it the same way). The
choice among several containing 3D-GloBFP footprints is made by the calc
function `largest_overlap`, never here.
"""

from __future__ import annotations

import math
from decimal import Decimal
from importlib import import_module
from typing import TYPE_CHECKING

from shapely import point_on_surface
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from eii_core.calc.building_heights import height_value, largest_overlap

from .model import HeightError

if TYPE_CHECKING:
    from .read import WsfGrid


def representative_point(geometry: BaseGeometry) -> Point:
    """The footprint's interior point, guaranteed inside it."""
    return point_on_surface(geometry)


def globfp_candidates(
    point: Point,
    footprint: BaseGeometry,
    files: tuple[tuple[str, tuple[tuple[BaseGeometry, Decimal], ...]], ...],
) -> list[tuple[Decimal, str, int, Decimal]]:
    """(overlap area, file name, row index, height) per containing footprint."""
    geometries: list[BaseGeometry] = []
    index: list[tuple[str, int, Decimal]] = []
    for file_name, rows in files:
        for row_index, (candidate, height) in enumerate(rows):
            geometries.append(candidate)
            index.append((file_name, row_index, height))
    if not geometries:
        return []
    tree = import_module("shapely.strtree").STRtree(geometries)
    found: list[tuple[Decimal, str, int, Decimal]] = []
    for hit in tree.query(point):
        candidate = geometries[int(hit)]
        if candidate.covers(point):
            file_name, row_index, height = index[int(hit)]
            area = candidate.intersection(footprint).area
            found.append((Decimal(str(area)), file_name, row_index, height))
    return found


def globfp_height(
    point: Point,
    footprint: BaseGeometry,
    files: tuple[tuple[str, tuple[tuple[BaseGeometry, Decimal], ...]], ...],
) -> Decimal | None:
    """The height of the overlap winner, or none when no footprint contains."""
    winner = largest_overlap(globfp_candidates(point, footprint, files))
    if winner is None:
        return None
    _area, _file, _row, height = winner
    return height


def wsf_value(grid: WsfGrid, point: Point) -> Decimal | None:
    """The cell mean holding the point; no-data or outside gives no value."""
    inverse = ~grid.transform
    column, row = inverse @ (point.x, point.y)
    col, row_i = math.floor(column), math.floor(row)
    if col < 0 or row_i < 0 or col >= grid.width or row_i >= grid.height:
        return None
    value = Decimal(str(grid.data[row_i, col]))
    if value == grid.nodata:
        return None
    return value


def wsf3d_height(
    point: Point, files: tuple[tuple[str, WsfGrid], ...]
) -> Decimal | None:
    """The one file's cell value; two or more files giving a value refuse.

    A file whose cell at the point is a no-data cell or outside its raster
    gives no value and does not take part; one whose value is not a usable
    height gives no value either, and the bad value is handed on so the
    choice can count it.
    """
    found: list[Decimal] = []
    usable: list[Decimal] = []
    for _name, grid in sorted(files, key=lambda item: item[0]):
        value = wsf_value(grid, point)
        if value is None:
            continue
        found.append(value)
        if height_value(value) is not None:
            usable.append(value)
    if len(usable) > 1:
        raise HeightError("wsf3d_overlap")
    if usable:
        return usable[0]
    return found[0] if found else None


__all__ = [
    "globfp_candidates",
    "globfp_height",
    "representative_point",
    "wsf3d_height",
    "wsf_value",
]
