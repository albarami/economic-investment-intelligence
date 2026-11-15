"""Exact frame invariants; no geometric tolerance or repair."""

import re
from collections.abc import Mapping, Sequence

from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


class FrameError(ValueError):
    """A named source or frame check refused the build."""


def safe_key(value: str) -> str:
    if not value:
        raise FrameError("missing key")
    if re.search(r"(?<![0-9])[0-9]{8}(?![0-9])|(?<![0-9])[0-9]{11}(?![0-9])", value):
        raise FrameError("forbidden digit run")
    return value


def check_cover(polygons: Sequence[BaseGeometry], expected: BaseGeometry) -> None:
    for i, polygon in enumerate(polygons):
        if (
            polygon.is_empty
            or not polygon.is_valid
            or polygon.geom_type not in {"Polygon", "MultiPolygon"}
        ):
            raise FrameError("invalid polygon")
        for other in polygons[:i]:
            if polygon.intersection(other).area > 0:
                raise FrameError("polygon overlap")
    if not unary_union(polygons).equals(expected):
        raise FrameError("polygon gap or outside frame")


def containing(point: BaseGeometry, polygons: Mapping[str, BaseGeometry]) -> str:
    keys = [key for key, polygon in polygons.items() if polygon.covers(point)]
    if len(keys) != 1:
        raise FrameError("centre must be in exactly one polygon")
    return keys[0]
