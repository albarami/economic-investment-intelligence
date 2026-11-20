"""Validate the declared QNG scheme and enumerate intersecting national-land tiles."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from .snapshot_policy import SnapshotRefusal, level_allowed


@dataclass(frozen=True, order=True)
class Tile:
    level: int
    row: int
    column: int

    def key(self) -> tuple[int, int, int]:
        return self.level, self.row, self.column


@dataclass(frozen=True)
class Scheme:
    x: float
    y: float
    resolutions: tuple[float | None, ...]
    extent: tuple[float, float, float, float]

    @property
    def levels(self) -> tuple[int, ...]:
        return tuple(
            level
            for level, resolution in enumerate(self.resolutions)
            if resolution is not None
        )

    def compatible(self, other: Scheme) -> bool:
        # A dated image may have its own coverage extent without changing its grid.
        return (self.x, self.y, self.resolutions) == (
            other.x,
            other.y,
            other.resolutions,
        )


def _number(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise SnapshotRefusal("metadata_number")
    return float(value)


def read_scheme(body: bytes) -> Scheme:
    try:
        data = json.loads(body)
        tile = data["tileInfo"]
        extent = data["fullExtent"]
        if tile["rows"] != 512 or tile["cols"] != 512 or tile["format"] != "JPEG":
            raise SnapshotRefusal("metadata_tile_format")
        for spatial in (tile["spatialReference"], extent["spatialReference"]):
            if spatial.get("latestWkid", spatial.get("wkid")) != 2932:
                raise SnapshotRefusal("metadata_crs")
        lods = tile["lods"]
        levels = {
            row["level"]: _number(row["resolution"])
            for row in lods
            if type(row["level"]) is int and 0 <= row["level"] <= 10
        }
        if 10 not in levels or len([row for row in lods if row["level"] <= 10]) != len(
            levels
        ):
            raise SnapshotRefusal("metadata_levels")
        resolutions = tuple(levels.get(n) for n in range(11))
        declared = tuple(
            resolution for resolution in resolutions if resolution is not None
        )
        if (
            not 0.52 <= levels[10] <= 0.54
            or any(value <= 0 for value in declared)
            or any(a <= b for a, b in pairwise(declared))
        ):
            raise SnapshotRefusal("metadata_resolution")
        bounds = tuple(
            _number(extent[name]) for name in ("xmin", "ymin", "xmax", "ymax")
        )
        xmin, ymin, xmax, ymax = bounds
        if not xmin < xmax or not ymin < ymax:
            raise SnapshotRefusal("metadata_extent")
        return Scheme(
            _number(tile["origin"]["x"]),
            _number(tile["origin"]["y"]),
            resolutions,
            (xmin, ymin, xmax, ymax),
        )
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        raise SnapshotRefusal("metadata_incompatible") from None


def enumerate_tiles(
    scheme: Scheme,
    land_qng: BaseGeometry,
    *,
    levels: tuple[int, ...] | None = None,
) -> tuple[Tile, ...]:
    selected = scheme.levels if levels is None else levels
    for level in selected:
        level_allowed(level)
        if scheme.resolutions[level] is None:
            raise SnapshotRefusal("metadata_level_missing")
    if (
        land_qng.is_empty
        or not land_qng.is_valid
        or land_qng.geom_type not in {"Polygon", "MultiPolygon"}
    ):
        raise SnapshotRefusal("boundary_invalid")
    # Enumerate the whole country; extent differences are recorded as coverage gaps.
    xmin, ymin, xmax, ymax = land_qng.bounds
    if scheme.x > xmin or scheme.y < ymax:
        raise SnapshotRefusal("metadata_origin_coverage")
    result = []
    for level in sorted(set(selected)):
        resolution = scheme.resolutions[level]
        if resolution is None:
            raise SnapshotRefusal("metadata_level_missing")
        span = 512 * resolution
        for row in range(
            max(0, math.floor((scheme.y - ymax) / span)),
            math.floor((scheme.y - ymin) / span) + 1,
        ):
            for column in range(
                max(0, math.floor((xmin - scheme.x) / span)),
                math.floor((xmax - scheme.x) / span) + 1,
            ):
                cell = box(
                    scheme.x + column * span,
                    scheme.y - (row + 1) * span,
                    scheme.x + (column + 1) * span,
                    scheme.y - row * span,
                )
                if cell.intersects(land_qng):
                    result.append(Tile(level, row, column))
    if not result:
        raise SnapshotRefusal("boundary_no_tiles")
    return tuple(result)
