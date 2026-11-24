"""Exact area outlines, selecting whole source cells through core predicates."""

from dataclasses import dataclass
from decimal import Decimal

from eii_core.shapes import (
    Ring,
    canonical_ring,
    exact_point,
    point_in_polygon,
    ring_is_simple,
    within_radius,
)
from eii_product.tools.make_area import DISTANCE_M


class OutlineError(ValueError):
    def __init__(self) -> None:
        super().__init__("area_outline_invalid")


@dataclass(frozen=True)
class CircleOutline:
    latitude: Decimal
    longitude: Decimal
    radius_m: Decimal | int | float


@dataclass(frozen=True)
class PolygonOutline:
    ring: Ring


def _position(raw: object) -> tuple[Decimal, Decimal]:
    if type(raw) is not list or len(raw) != 2:
        raise OutlineError()
    lon, lat = raw
    if type(lon) is not Decimal or type(lat) is not Decimal:
        raise OutlineError()
    if not lon.is_finite() or not lat.is_finite():
        raise OutlineError()
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        raise OutlineError()
    return lat, lon


def read_outline(raw: object) -> CircleOutline | PolygonOutline:
    if type(raw) is not dict:
        raise OutlineError()
    if raw.get("type") == "Circle":
        if set(raw) != {"type", "coordinates", "radius_m"}:
            raise OutlineError()
        lat, lon = _position(raw["coordinates"])
        radius = raw["radius_m"]
        if type(radius) not in (int, Decimal) or radius not in DISTANCE_M:
            raise OutlineError()
        return CircleOutline(lat, lon, radius)
    if raw.get("type") == "Polygon":
        if set(raw) != {"type", "coordinates"}:
            raise OutlineError()
        coordinates = raw["coordinates"]
        if type(coordinates) is not list or len(coordinates) != 1:
            raise OutlineError()
        positions = coordinates[0]
        if type(positions) is not list or len(positions) < 4:
            raise OutlineError()
        points = [_position(item) for item in positions]
        if points[0] != points[-1]:
            raise OutlineError()
        try:
            ring = canonical_ring(points)
        except (TypeError, ValueError):
            raise OutlineError() from None
        if not ring_is_simple(ring):
            raise OutlineError()
        return PolygonOutline(ring)
    raise OutlineError()


def covers(
    outline: CircleOutline | PolygonOutline,
    lat: Decimal | float | int,
    lon: Decimal | float | int,
) -> bool:
    if isinstance(outline, CircleOutline):
        return within_radius(
            (float(outline.latitude), float(outline.longitude)),
            (float(lat), float(lon)),
            float(outline.radius_m),
        )
    if isinstance(outline, PolygonOutline):
        return point_in_polygon(exact_point(lat, lon), (outline.ring,))
    raise OutlineError()
