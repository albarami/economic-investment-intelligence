"""Exact requested outlines are retained independently of whole-cell snaps."""

import math
from dataclasses import dataclass

import h3

type Point = tuple[float, float]  # latitude, longitude
type Ring = tuple[Point, ...]


def canonical_ring(points: Ring) -> Ring:
    ring = list(points)
    while len(ring) > 1 and ring[-1] == ring[0]:
        ring.pop()
    if len(ring) < 3:
        raise ValueError("A polygon requires three vertices")
    area = sum(
        a[1] * b[0] - b[1] * a[0]
        for a, b in zip(ring, ring[1:] + ring[:1], strict=True)
    )
    if area == 0:
        raise ValueError("A polygon requires nonzero area")
    if area < 0:
        ring = ring[:1] + list(reversed(ring[1:]))
    return (*ring, ring[0])


@dataclass(frozen=True)
class Circle:
    """Analytical circle: no polygon approximation replaces the exact shape."""

    center: Point
    radius_m: float

    def point(self, bearing: float) -> Point:
        angular = (
            self.radius_m
            / h3.great_circle_distance((0.0, 0.0), (0.0, 1.0), unit="m")
            * math.pi
            / 180
        )
        lat, lon = map(math.radians, self.center)
        heading = math.radians(bearing)
        out_lat = math.asin(
            math.sin(lat) * math.cos(angular)
            + math.cos(lat) * math.sin(angular) * math.cos(heading)
        )
        out_lon = lon + math.atan2(
            math.sin(heading) * math.sin(angular) * math.cos(lat),
            math.cos(angular) - math.sin(lat) * math.sin(out_lat),
        )
        return math.degrees(out_lat), math.degrees(out_lon)


@dataclass(frozen=True)
class Area:
    exact: Circle | Ring
    cells: tuple[str, ...]


def drawn_area(outline: Ring, frame: tuple[str, ...]) -> Area:
    from .snap import snap_polygon

    exact = canonical_ring(outline)
    return Area(exact, snap_polygon(exact, frame))


def radius_area(
    point: Point, radius_m: float, pin_cell: str, frame: tuple[str, ...]
) -> Area:
    from .snap import snap_radius

    return Area(Circle(point, radius_m), snap_radius(pin_cell, radius_m, frame))
