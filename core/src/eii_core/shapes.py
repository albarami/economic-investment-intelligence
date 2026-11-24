"""Exact polygons and circles. No database access and no third-party import.

The canonical ring keeps the area spike's rule: drop a repeated closing vertex,
require three vertices and a nonzero area, reverse a clockwise ring, and close
it. A ring is then rotated so its lexicographically smallest vertex is first.
The spike does not rotate; the rotation is what makes a different start vertex
the same form.

A point on an edge or a vertex is inside the shape. A point on an edge that two
municipalities share is inside the land area. An inner ring is a hole and is not
land: a point strictly inside it is outside that polygon.

A circle is the closed disk of one great-circle function. A point whose distance
equals the cut-off is inside. The comparison is ``<=`` and it is the only one.

A ring is simple when no two non-adjacent edges share a point and adjacent
edges share only their common vertex. ``ring_is_simple`` decides that on these
exact rationals. ``canonical_ring`` does not, so the hash of a valid ring stays.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import struct
from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction

type Point = tuple[Fraction, Fraction]
type Ring = tuple[Point, ...]
type Polygon = tuple[Ring, ...]

GEOMETRY_REFUSED = "geometry text refused"
SIX_PLACES = Decimal("0.000001")
# IUGG mean radius. The circle test uses this constant inside one function.
EARTH_RADIUS_M = 6371008.8

_LAT = 0
_LON = 1


class GeometryTextError(ValueError):
    """The geometry text was refused. The message carries no coordinate."""


def exact_point(latitude: object, longitude: object) -> Point:
    """Convert a coordinate pair exactly once. A float becomes its rational."""
    return (_exact(latitude), _exact(longitude))


def reduce_six(value: object) -> Decimal:
    """Reduce to six decimal places, half even.

    A float is converted with ``Decimal.from_float`` (the exact decimal of the
    binary value) and only then quantised. Half even is the project's six-place
    rule for an exact decimal. A tie at the seventh place keeps the even digit.
    """
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(GEOMETRY_REFUSED)
        number = Decimal.from_float(value)
    elif type(value) is Decimal:
        number = value
    elif type(value) is int and not isinstance(value, bool):
        number = Decimal(value)
    elif type(value) is Fraction:
        number = Decimal(value.numerator) / Decimal(value.denominator)
    else:
        raise TypeError(GEOMETRY_REFUSED)
    if not number.is_finite():
        raise ValueError(GEOMETRY_REFUSED)
    return number.quantize(SIX_PLACES, rounding=ROUND_HALF_EVEN)


def canonical_ring(points: Sequence[tuple[object, object]]) -> Ring:
    """Return the canonical ring. See the module note for the spike rule."""
    ring = [exact_point(lat, lon) for lat, lon in points]
    while len(ring) > 1 and ring[-1] == ring[0]:
        ring.pop()
    if len(ring) < 3:
        raise ValueError("A polygon requires three vertices")
    area = _shoelace(ring)
    if area == 0:
        raise ValueError("A polygon requires nonzero area")
    if area < 0:
        ring = ring[:1] + list(reversed(ring[1:]))
    start = min(range(len(ring)), key=lambda index: ring[index])
    rotated = ring[start:] + ring[:start]
    return (*rotated, rotated[0])


def ring_is_simple(points: Sequence[tuple[object, object]]) -> bool:
    """True when the ring is a simple polygon on exact rational coordinates.

    No two non-adjacent edges share any point. Two adjacent edges share only
    their common vertex: a fold-back, a repeated non-consecutive vertex, or a
    vertex on a non-adjacent edge is not simple. Orientation and on-segment
    tests use the exact rationals. There is no float, tolerance or sample.
    ``canonical_ring`` does not call this, so a caller chooses the refusal and
    ``ring_sha256`` of an already valid ring does not change.
    """
    if len(points) == 0:
        return False
    vertices = [exact_point(point[0], point[1]) for point in points]
    if vertices[0] == vertices[-1]:
        vertices = vertices[:-1]
    count = len(vertices)
    if count < 3:
        return False
    for index in range(count):
        if _adjacent_overlap(
            vertices[index],
            vertices[(index + 1) % count],
            vertices[(index + 2) % count],
        ):
            return False
    for left in range(count):
        for right in range(left + 1, count):
            if _cycle_adjacent(left, right, count):
                continue
            if _edges_share_point(
                vertices[left],
                vertices[(left + 1) % count],
                vertices[right],
                vertices[(right + 1) % count],
            ):
                return False
    return True


def ring_sha256(points: Sequence[tuple[object, object]]) -> str:
    """SHA-256 of the canonical ring text. One changed coordinate changes it."""
    ring = canonical_ring(points)
    body = ";".join(
        f"{lat.numerator}/{lat.denominator},{lon.numerator}/{lon.denominator}"
        for lat, lon in ring
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def representative_point(points: Sequence[tuple[object, object]]) -> Point:
    """A vertex of the canonical ring. It lies on the shape, so it is inside."""
    ring = canonical_ring(points)
    return ring[0]


def point_in_ring(point: Point, ring: Sequence[Point]) -> bool:
    """Even-odd test. A point on an edge or a vertex is inside."""
    closed = _closed(_as_ring(ring))
    point = _as_point(point)
    if _on_boundary(point, closed):
        return True
    return _ray_inside(point, closed)


def point_in_polygon(point: Point, rings: Polygon) -> bool:
    """Inside the outer ring and not strictly inside a hole."""
    rings = tuple(_as_ring(ring) for ring in rings)
    point = _as_point(point)
    if not point_in_ring(point, rings[0]):
        return False
    return all(not _strictly_inside(point, hole) for hole in rings[1:])


def point_in_land(point: Point, municipalities: Sequence[Polygon]) -> bool:
    """Inside the union of the municipality polygons. Shared edges count."""
    return any(point_in_polygon(point, polygon) for polygon in municipalities)


def polygon_inside_land(ring: Sequence[Point], land: Sequence[Polygon]) -> bool:
    """True only when no part of the ring lies outside the union.

    Vertices, every piece of every edge, and the interior are tested. A ring
    that surrounds a gap or a hole of the union is not inside. The test is
    exact: no edge may cross a land boundary, no hole of the land may lie
    inside the ring, and the interior must lie on land. A point on the
    boundary of the union is inside.
    """
    closed = _closed(_as_ring(ring))
    unique = closed[:-1]
    for vertex in unique:
        if not point_in_land(vertex, land):
            return False
    for start, end in itertools.pairwise(closed):
        if not _segment_inside(start, end, land):
            return False
    for edge in _boundary(land):
        if _complement_inside(edge[0], edge[1], closed):
            return False
    return True


def great_circle_m(start: tuple[float, float], end: tuple[float, float]) -> float:
    """Great-circle distance in metres. Both arguments are latitude, longitude."""
    lat1, lon1 = math.radians(start[0]), math.radians(start[1])
    lat2, lon2 = math.radians(end[0]), math.radians(end[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    haversine = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    bounded = min(1.0, haversine)
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(bounded))


def within_radius(
    centre: tuple[float, float], point: tuple[float, float], radius_m: float
) -> bool:
    """Closed disk. A point at a distance equal to the cut-off is inside."""
    return great_circle_m(centre, point) <= radius_m


def decode_geometry(text: str) -> tuple[Polygon, ...]:
    """Decode upper-case little-endian ISO WKB hex with no spatial reference.

    A polygon (type 3) and a multipolygon (type 6) are admitted. Coordinates are
    IEEE-754 doubles converted once to rationals. X is longitude and y is
    latitude. The first ring is the outer ring; later rings are holes.
    """
    if (
        len(text) < 2
        or len(text) % 2 != 0
        or any(character in "abcdef" for character in text)
        or any(character not in "0123456789ABCDEF" for character in text)
    ):
        raise GeometryTextError(GEOMETRY_REFUSED)
    try:
        blob = bytes.fromhex(text)
    except ValueError:
        raise GeometryTextError(GEOMETRY_REFUSED) from None
    polygons, offset = _parse_value(blob, 0, allow_multi=True)
    if offset != len(blob):
        raise GeometryTextError(GEOMETRY_REFUSED)
    return polygons


def _exact(value: object) -> Fraction:
    if type(value) is Fraction:
        return value
    if type(value) is Decimal:
        if not value.is_finite():
            raise ValueError(GEOMETRY_REFUSED)
        return Fraction(value)
    if type(value) is str:
        try:
            number = Decimal(value)
        except ArithmeticError:
            raise ValueError(GEOMETRY_REFUSED) from None
        if not number.is_finite():
            raise ValueError(GEOMETRY_REFUSED)
        return Fraction(number)
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(GEOMETRY_REFUSED)
        return Fraction(value)
    if type(value) is int and not isinstance(value, bool):
        return Fraction(value)
    raise TypeError(GEOMETRY_REFUSED)


def _shoelace(ring: Sequence[Point]) -> Fraction:
    total = Fraction(0)
    wrapped = (*ring[1:], ring[0])
    for start, end in zip(ring, wrapped, strict=False):
        total += start[_LON] * end[_LAT] - end[_LON] * start[_LAT]
    return total


def _as_point(point: Point) -> Point:
    if type(point[0]) is Fraction and type(point[1]) is Fraction:
        return point
    return exact_point(point[0], point[1])


def _as_ring(ring: Sequence[Point]) -> Ring:
    return tuple(_as_point(point) for point in ring)


def _closed(ring: Sequence[Point]) -> Ring:
    if len(ring) == 0:
        return ()
    if ring[0] == ring[-1]:
        return tuple(ring)
    return (*ring, ring[0])


def _cycle_adjacent(left: int, right: int, count: int) -> bool:
    return right == left + 1 or (left == 0 and right == count - 1)


def _adjacent_overlap(start: Point, end: Point, far: Point) -> bool:
    """True when adjacent edges share more than their common vertex."""
    if start == end or end == far:
        return True
    if _on_segment(far, start, end):
        return True
    return _on_segment(start, end, far)


def _orient(start: Point, end: Point, point: Point) -> Fraction:
    return _cross(
        end[_LON] - start[_LON],
        end[_LAT] - start[_LAT],
        point[_LON] - start[_LON],
        point[_LAT] - start[_LAT],
    )


def _edges_share_point(left: Point, right: Point, near: Point, far: Point) -> bool:
    """True when two segments share any point, including an endpoint."""
    if (
        _on_segment(near, left, right)
        or _on_segment(far, left, right)
        or _on_segment(left, near, far)
        or _on_segment(right, near, far)
    ):
        return True
    side_left = _orient(left, right, near)
    side_right = _orient(left, right, far)
    side_near = _orient(near, far, left)
    side_far = _orient(near, far, right)
    if side_left == 0 or side_right == 0 or side_near == 0 or side_far == 0:
        return False
    if (side_left > 0) == (side_right > 0):
        return False
    return (side_near > 0) != (side_far > 0)


def _on_segment(point: Point, start: Point, end: Point) -> bool:
    cross = (end[_LON] - start[_LON]) * (point[_LAT] - start[_LAT]) - (
        end[_LAT] - start[_LAT]
    ) * (point[_LON] - start[_LON])
    if cross != 0:
        return False
    dot = (point[_LON] - start[_LON]) * (end[_LON] - start[_LON]) + (
        point[_LAT] - start[_LAT]
    ) * (end[_LAT] - start[_LAT])
    if dot < 0:
        return False
    length = (end[_LON] - start[_LON]) ** 2 + (end[_LAT] - start[_LAT]) ** 2
    return dot <= length


def _on_boundary(point: Point, closed: Sequence[Point]) -> bool:
    return any(
        _on_segment(point, start, end) for start, end in itertools.pairwise(closed)
    )


def _ray_inside(point: Point, closed: Sequence[Point]) -> bool:
    inside = False
    latitude = point[_LAT]
    longitude = point[_LON]
    for start, end in itertools.pairwise(closed):
        if (start[_LAT] > latitude) == (end[_LAT] > latitude):
            continue
        numerator = (start[_LON] - longitude) * (end[_LAT] - start[_LAT]) + (
            latitude - start[_LAT]
        ) * (end[_LON] - start[_LON])
        denominator = end[_LAT] - start[_LAT]
        if numerator == 0 or (numerator > 0) == (denominator > 0):
            inside = not inside
    return inside


def _strictly_inside(point: Point, ring: Sequence[Point]) -> bool:
    closed = _closed(ring)
    if _on_boundary(point, closed):
        return False
    return _ray_inside(point, closed)


def _cross(
    left_x: Fraction, left_y: Fraction, right_x: Fraction, right_y: Fraction
) -> Fraction:
    return left_x * right_y - left_y * right_x


def _segment_t(start: Point, end: Point, other: Point, far: Point) -> Fraction | None:
    dx = end[_LON] - start[_LON]
    dy = end[_LAT] - start[_LAT]
    sx = far[_LON] - other[_LON]
    sy = far[_LAT] - other[_LAT]
    denom = _cross(dx, dy, sx, sy)
    if denom == 0:
        return None
    qx = other[_LON] - start[_LON]
    qy = other[_LAT] - start[_LAT]
    tee = _cross(qx, qy, sx, sy) / denom
    you = _cross(qx, qy, dx, dy) / denom
    if tee < 0 or tee > 1 or you < 0 or you > 1:
        return None
    return tee


def _vertex_t(start: Point, end: Point, vertex: Point) -> Fraction | None:
    if not _on_segment(vertex, start, end):
        return None
    dx = end[_LON] - start[_LON]
    dy = end[_LAT] - start[_LAT]
    if dx == 0 and dy == 0:
        return None
    if abs(dx) >= abs(dy):
        return (vertex[_LON] - start[_LON]) / dx
    return (vertex[_LAT] - start[_LAT]) / dy


def _lerp(start: Point, end: Point, tee: Fraction) -> Point:
    return (
        start[_LAT] + tee * (end[_LAT] - start[_LAT]),
        start[_LON] + tee * (end[_LON] - start[_LON]),
    )


def _edges(land: Sequence[Polygon]) -> tuple[tuple[Point, Point], ...]:
    found: list[tuple[Point, Point]] = []
    for polygon in land:
        for ring in polygon:
            closed = _closed(ring)
            found.extend(itertools.pairwise(closed))
    return tuple(found)


def _segment_inside(start: Point, end: Point, land: Sequence[Polygon]) -> bool:
    if start == end:
        return point_in_land(start, land)
    marks = [Fraction(0), Fraction(1)]
    for edge_start, edge_end in _edges(land):
        tee = _segment_t(start, end, edge_start, edge_end)
        if tee is not None:
            marks.append(tee)
        for vertex in (edge_start, edge_end):
            projected = _vertex_t(start, end, vertex)
            if projected is not None:
                marks.append(projected)
    ordered = sorted(set(marks))
    for left, right in itertools.pairwise(ordered):
        if left == right:
            continue
        if not point_in_land(_lerp(start, end, (left + right) / 2), land):
            return False
    return True


def _signed_area(ring: Sequence[Point]) -> Fraction:
    return _shoelace(list(_closed(ring)[:-1]))


def _reversed_closed(ring: Sequence[Point]) -> Ring:
    body = list(_closed(ring)[:-1])
    flipped = [body[0], *reversed(body[1:])]
    return (*flipped, flipped[0])


def _as_ccw(ring: Sequence[Point]) -> Ring:
    closed = _closed(ring)
    if _signed_area(closed) < 0:
        return _reversed_closed(closed)
    return closed


def _as_cw(ring: Sequence[Point]) -> Ring:
    closed = _as_ccw(ring)
    return _reversed_closed(closed)


def _boundary(land: Sequence[Polygon]) -> tuple[tuple[Point, Point], ...]:
    counts: dict[tuple[Point, Point], int] = {}
    for polygon in land:
        oriented = (_as_ccw(polygon[0]), *(_as_cw(hole) for hole in polygon[1:]))
        for ring in oriented:
            for start, end in itertools.pairwise(ring):
                if start == end:
                    continue
                counts[(start, end)] = counts.get((start, end), 0) + 1
    kept: list[tuple[Point, Point]] = []
    for edge, count in counts.items():
        if count > counts.get((edge[1], edge[0]), 0):
            kept.append(edge)
    return tuple(kept)


def _complement_inside(start: Point, end: Point, closed: Sequence[Point]) -> bool:
    """True when the non-land side of a union boundary lies inside the ring.

    The midpoint is the exact halfway point. There is no search and no step
    limit. A shared boundary whose interior stays on the land side is not a
    contained gap.
    """
    mid = _lerp(start, end, Fraction(1, 2))
    if _on_boundary(mid, closed):
        return _interior_faces_complement(start, end, closed)
    return point_in_ring(mid, closed)


def _interior_faces_complement(
    start: Point, end: Point, closed: Sequence[Point]
) -> bool:
    land_lat = end[_LAT] - start[_LAT]
    land_lon = end[_LON] - start[_LON]
    ccw = _signed_area(closed) > 0
    mid = _lerp(start, end, Fraction(1, 2))
    for left, right in itertools.pairwise(closed):
        if not _on_segment(mid, left, right):
            continue
        edge_lat = right[_LAT] - left[_LAT]
        edge_lon = right[_LON] - left[_LON]
        if _cross(land_lon, land_lat, edge_lon, edge_lat) != 0:
            continue
        dot = land_lat * edge_lat + land_lon * edge_lon
        if dot == 0:
            continue
        interior_on_land = (dot > 0) == ccw
        return not interior_on_land
    return False


def _parse_value(
    blob: bytes, offset: int, *, allow_multi: bool
) -> tuple[tuple[Polygon, ...], int]:
    if offset >= len(blob) or blob[offset] != 1:
        raise GeometryTextError(GEOMETRY_REFUSED)
    if offset + 5 > len(blob):
        raise GeometryTextError(GEOMETRY_REFUSED)
    type_code = struct.unpack_from("<I", blob, offset + 1)[0]
    cursor = offset + 5
    if type_code == 3:
        polygon, cursor = _parse_polygon_body(blob, cursor)
        return (polygon,), cursor
    if type_code == 6 and allow_multi:
        return _parse_multi(blob, cursor)
    raise GeometryTextError(GEOMETRY_REFUSED)


def _parse_multi(blob: bytes, offset: int) -> tuple[tuple[Polygon, ...], int]:
    count, cursor = _u32(blob, offset)
    polygons: list[Polygon] = []
    for _ in range(count):
        parsed, cursor = _parse_value(blob, cursor, allow_multi=False)
        polygons.extend(parsed)
    return tuple(polygons), cursor


def _parse_polygon_body(blob: bytes, offset: int) -> tuple[Polygon, int]:
    count, cursor = _u32(blob, offset)
    if count < 1:
        raise GeometryTextError(GEOMETRY_REFUSED)
    rings: list[Ring] = []
    for _ in range(count):
        ring, cursor = _parse_ring(blob, cursor)
        rings.append(ring)
    return tuple(rings), cursor


def _parse_ring(blob: bytes, offset: int) -> tuple[Ring, int]:
    count, cursor = _u32(blob, offset)
    if count < 4:
        raise GeometryTextError(GEOMETRY_REFUSED)
    points: list[Point] = []
    for _ in range(count):
        point, cursor = _parse_point(blob, cursor)
        points.append(point)
    if points[0] != points[-1]:
        raise GeometryTextError(GEOMETRY_REFUSED)
    return tuple(points), cursor


def _parse_point(blob: bytes, offset: int) -> tuple[Point, int]:
    if offset + 16 > len(blob):
        raise GeometryTextError(GEOMETRY_REFUSED)
    longitude = struct.unpack_from("<d", blob, offset)[0]
    latitude = struct.unpack_from("<d", blob, offset + 8)[0]
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        raise GeometryTextError(GEOMETRY_REFUSED)
    return (Fraction(latitude), Fraction(longitude)), offset + 16


def _u32(blob: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(blob):
        raise GeometryTextError(GEOMETRY_REFUSED)
    return struct.unpack_from("<I", blob, offset)[0], offset + 4
