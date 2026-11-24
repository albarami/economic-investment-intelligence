"""Closed RFC 7946 source geometry; check without repairing or rounding it."""

import math
from fractions import Fraction
from itertools import pairwise
from typing import Any

POSITION_LIMIT = 16384
PART_LIMIT = 64
RING_LIMIT = 64
VERTEX_LIMIT = 4096


def validate_source_geometry(raw: object) -> dict[str, Any]:
    """Retain source order and values, or refuse the complete geometry."""

    def refuse() -> None:
        raise ValueError("source_geometry_invalid")

    if type(raw) is not dict or set(raw) != {"type", "coordinates"}:
        refuse()
    assert isinstance(raw, dict)
    count = 0

    def position(point: object) -> None:
        nonlocal count
        if type(point) is not list or len(point) != 2:
            refuse()
        assert isinstance(point, list)
        lon, lat = point
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in point):
            refuse()
        if not -180 <= lon <= 180 or not -90 <= lat <= 90:
            refuse()
        count += 1
        if count > POSITION_LIMIT:
            refuse()

    def path(points: object, minimum: int) -> None:
        if type(points) is not list or not minimum <= len(points) <= VERTEX_LIMIT:
            refuse()
        assert isinstance(points, list)
        for point in points:
            position(point)

    def polygon(rings: object) -> None:
        if type(rings) is not list or not 1 <= len(rings) <= RING_LIMIT:
            refuse()
        assert isinstance(rings, list)
        for index, ring in enumerate(rings):
            path(ring, 4)
            if ring[0] != ring[-1]:
                refuse()
            # Exact binary source numbers, never an orientation tolerance.
            area = sum(
                Fraction(a[0]) * Fraction(b[1]) - Fraction(b[0]) * Fraction(a[1])
                for a, b in pairwise(ring)
            )
            if area == 0 or (area > 0) != (index == 0):
                refuse()

    kind, coordinates = raw["type"], raw["coordinates"]
    if kind == "Point":
        position(coordinates)
    elif kind == "LineString":
        path(coordinates, 2)
    elif kind == "Polygon":
        polygon(coordinates)
    elif kind == "MultiPolygon":
        if type(coordinates) is not list or not 1 <= len(coordinates) <= PART_LIMIT:
            refuse()
        for part in coordinates:
            polygon(part)
    else:
        refuse()
    return raw
