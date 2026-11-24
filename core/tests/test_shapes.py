"""Invented coordinates for exact shapes. Nothing here is a real place."""

from __future__ import annotations

import struct
from decimal import Decimal
from fractions import Fraction

import pytest

from eii_core.shapes import (
    GEOMETRY_REFUSED,
    GeometryTextError,
    canonical_ring,
    decode_geometry,
    exact_point,
    point_in_land,
    point_in_polygon,
    point_in_ring,
    polygon_inside_land,
    reduce_six,
    ring_sha256,
    within_radius,
)

POLY = (
    "0103000000010000000400000000000000000000000000000000000000"
    "000000000000E03F0000000000000000000000000000E03F000000000000D03F"
    "00000000000000000000000000000000"
)
MULTI = (
    "010600000002000000010300000001000000040000000000000000000000"
    "0000000000000000000000000000E03F0000000000000000000000000000E03F"
    "000000000000D03F00000000000000000000000000000000010300000001000000"
    "04000000000000000000F03F0000000000000000000000000000F83F000000000000"
    "0000000000000000F83F000000000000D03F000000000000F03F0000000000000000"
)
HOLED = (
    "0103000000020000000500000000000000000000000000000000000000"
    "000000000000F03F0000000000000000000000000000F03F000000000000F03F"
    "0000000000000000000000000000F03F00000000000000000000000000000000"
    "05000000000000000000D03F000000000000D03F000000000000E83F000000000000"
    "D03F000000000000E83F000000000000E83F000000000000D03F000000000000E83F"
    "000000000000D03F000000000000D03F"
)
POINT_TYPE = "0101000000000000000000E03F000000000000D03F"
OPEN_RING = (
    "0103000000010000000400000000000000000000000000000000000000"
    "000000000000E03F0000000000000000000000000000E03F000000000000D03F"
    "000000000000D03F000000000000D03F"
)


def _square(lat0, lon0, lat1, lon1):
    return (
        exact_point(lat0, lon0),
        exact_point(lat0, lon1),
        exact_point(lat1, lon1),
        exact_point(lat1, lon0),
        exact_point(lat0, lon0),
    )


def _land():
    left = (_square(0, 0, 1, 1),)
    right = (_square(0, 1, 1, 2),)
    return (left, right)


def test_point_inside_outside_on_edge_and_on_vertex() -> None:
    ring = _square(0, 0, 2, 2)
    assert point_in_ring(exact_point(1, 1), ring)
    assert not point_in_ring(exact_point(3, 1), ring)
    assert point_in_ring(exact_point(0, 1), ring)
    assert point_in_ring(exact_point(0, 0), ring)


def test_shared_edge_is_inside_the_land() -> None:
    assert point_in_land(exact_point("0.5", 1), _land())


def test_point_outside_the_union_is_refused_even_inside_a_cell() -> None:
    """DAT-146: the land is the municipalities, not a stored cell's geometry."""
    cell = (_square(0, 2, 1, 3),)
    point = exact_point("0.5", "2.5")
    assert point_in_polygon(point, cell)
    assert not point_in_land(point, _land())

    def cell_union(candidate, land):
        del land
        return point_in_polygon(candidate, cell)

    def expect_outside(holds) -> None:
        assert holds(point, _land()) is False

    expect_outside(point_in_land)
    with pytest.raises(AssertionError):
        expect_outside(cell_union)


def test_polygon_containment_cases() -> None:
    land = _land()
    inside = _square("0.2", "0.2", "0.4", "0.4")
    assert polygon_inside_land(inside, land)
    across = (
        exact_point("0.2", "0.2"),
        exact_point("0.2", "1.8"),
        exact_point("0.8", "1.8"),
        exact_point("0.8", "0.2"),
        exact_point("0.2", "0.2"),
    )
    assert polygon_inside_land(across, land)
    vertex_out = (
        exact_point("0.2", "0.2"),
        exact_point("0.2", "2.2"),
        exact_point("0.8", "0.2"),
        exact_point("0.2", "0.2"),
    )
    assert not polygon_inside_land(vertex_out, land)

    def accept_vertex_out(ring, municipalities):
        del municipalities
        return True

    def expect_rejected(holds) -> None:
        assert holds(vertex_out, land) is False

    expect_rejected(polygon_inside_land)
    with pytest.raises(AssertionError):
        expect_rejected(accept_vertex_out)


def test_edge_that_leaves_the_union_is_not_inside() -> None:
    separated = ((_square(0, 0, 1, 1),), (_square(0, 3, 1, 4),))
    bridge = (
        exact_point("0.2", "0.2"),
        exact_point("0.2", "3.5"),
        exact_point("0.8", "3.5"),
        exact_point("0.8", "0.2"),
        exact_point("0.2", "0.2"),
    )
    assert not polygon_inside_land(bridge, separated)


def test_polygon_that_surrounds_a_gap_is_not_inside() -> None:
    outer = _square(0, 0, 4, 4)
    hole = _square(1, 1, 3, 3)
    land = ((outer, hole),)
    around = (
        exact_point("0.5", "0.5"),
        exact_point("0.5", "3.5"),
        exact_point("3.5", "3.5"),
        exact_point("3.5", "0.5"),
        exact_point("0.5", "0.5"),
    )
    assert point_in_land(exact_point("0.5", "0.5"), land)
    assert not point_in_land(exact_point(2, 2), land)
    assert not polygon_inside_land(around, land)


def test_polygon_inside_the_union_does_not_consult_cells() -> None:
    """DAT-146: land without a base cell is still inside the union."""
    assert polygon_inside_land(_square("0.2", "0.2", "0.4", "0.8"), _land())


def test_concave_notch_is_outside() -> None:
    ring = (
        exact_point(0, 0),
        exact_point(0, 3),
        exact_point(3, 3),
        exact_point(3, 0),
        exact_point(2, 0),
        exact_point(2, 2),
        exact_point(1, 2),
        exact_point(1, 0),
        exact_point(0, 0),
    )
    assert not point_in_ring(exact_point("1.5", "0.5"), ring)
    assert point_in_ring(exact_point("2.5", "1.5"), ring)


def test_sixth_decimal_step_either_side_of_an_edge() -> None:
    ring = _square(0, 0, 1, 1)
    assert point_in_ring(exact_point(Decimal("0.000001"), "0.5"), ring)
    assert not point_in_ring(exact_point(Decimal("-0.000001"), "0.5"), ring)
    assert point_in_ring(exact_point(0, "0.5"), ring)


def test_circle_boundary_is_closed() -> None:
    """A centre exactly at the cut-off is inside. The comparison is ``<=``."""
    centre = (0.0, 0.0)
    far = (0.0, 1.0)
    from eii_core.shapes import great_circle_m

    radius = great_circle_m(centre, far)
    assert within_radius(centre, far, radius)
    assert within_radius(centre, (0.0, 0.5), radius)
    assert not within_radius(centre, (0.0, 1.5), radius)

    def strictly_within(origin, point, cutoff):
        return great_circle_m(origin, point) < cutoff

    def expect_closed(holds) -> None:
        assert holds(centre, far, radius) is True

    expect_closed(within_radius)
    with pytest.raises(AssertionError):
        expect_closed(strictly_within)


def test_canonical_form_and_hash() -> None:
    ring = ((0, 0), (0, 1), (1, 1), (1, 0))
    started = ((1, 1), (1, 0), (0, 0), (0, 1))
    wound = ((0, 0), (1, 0), (1, 1), (0, 1))
    assert canonical_ring(ring) == canonical_ring(started)
    assert canonical_ring(ring) == canonical_ring(wound)
    assert ring_sha256(ring) == ring_sha256(started)
    changed = ((0, 0), (0, 1), (1, 1), (2, 0))
    assert ring_sha256(ring) != ring_sha256(changed)


def test_six_place_reduction_of_a_tie() -> None:
    """Half even: the seventh digit 5 keeps the even sixth digit."""
    assert reduce_six(Decimal("1.2345675")) == Decimal("1.234568")
    assert reduce_six(Decimal("1.2345665")) == Decimal("1.234566")


def test_geometry_text_decodes_a_polygon_and_a_multipolygon() -> None:
    polygon = decode_geometry(POLY)
    multi = decode_geometry(MULTI)
    assert len(polygon) == 1 and len(polygon[0]) == 1 and len(polygon[0][0]) == 4
    assert polygon[0][0][1] == exact_point(0, Decimal("0.5"))
    assert len(multi) == 2
    assert multi[1][0][0] == exact_point(0, 1)


def test_decoded_coordinates_are_exact() -> None:
    """0.1 has no short decimal equal to its double. The rational is the double."""
    raw = bytes.fromhex("9A9999999999B93F")
    expected = _ieee_fraction(raw)
    blob = (
        "01030000000100000004000000"
        + "9A9999999999B93F"
        + "0000000000000000"
        + "000000000000E03F0000000000000000"
        + "000000000000E03F000000000000D03F"
        + "9A9999999999B93F0000000000000000"
    )
    point = decode_geometry(blob)[0][0][0]
    assert point[1] == expected

    def rounded(text: str):
        value = struct.unpack("<d", bytes.fromhex(text[18:34]))[0]
        return Decimal(str(value))

    assert rounded(blob) != expected


def test_geometry_text_refusals() -> None:
    with pytest.raises(GeometryTextError, match=GEOMETRY_REFUSED):
        decode_geometry(POLY.lower())
    with pytest.raises(GeometryTextError, match=GEOMETRY_REFUSED):
        decode_geometry("00" + POLY[2:])
    with pytest.raises(GeometryTextError, match=GEOMETRY_REFUSED):
        decode_geometry(POINT_TYPE)
    with pytest.raises(GeometryTextError, match=GEOMETRY_REFUSED):
        decode_geometry(POLY[:-2])
    with pytest.raises(GeometryTextError, match=GEOMETRY_REFUSED):
        decode_geometry(POLY + "00")
    with pytest.raises(GeometryTextError, match=GEOMETRY_REFUSED):
        decode_geometry(OPEN_RING)


def test_point_in_an_inner_ring_is_outside() -> None:
    polygon = decode_geometry(HOLED)[0]
    hole_point = exact_point(Decimal("0.5"), Decimal("0.5"))
    edge_point = exact_point(Decimal("0.25"), Decimal("0.5"))
    assert not point_in_polygon(hole_point, polygon)
    assert point_in_polygon(edge_point, polygon)

    def drop_holes(point, rings):
        return point_in_ring(point, rings[0])

    def expect_outside(holds) -> None:
        assert holds(hole_point, polygon) is False

    expect_outside(point_in_polygon)
    with pytest.raises(AssertionError):
        expect_outside(drop_holes)


def test_request_that_encloses_a_hole_is_not_inside() -> None:
    """The bounded witness search accepts this ring. Exact containment refuses it."""
    outer = (
        exact_point("-0.2", "-0.4"),
        exact_point("-0.2", "2.4"),
        exact_point("1.2", "1"),
        exact_point("-0.2", "-0.4"),
    )
    hole = (
        exact_point(0, 0),
        exact_point(0, 2),
        exact_point(1, 1),
        exact_point(0, 0),
    )
    request = (
        exact_point("-0.1", "-0.2"),
        exact_point("-0.1", "2.2"),
        exact_point("1.1", "1"),
        exact_point("-0.1", "-0.2"),
    )
    land = ((outer, hole),)
    assert not polygon_inside_land(request, land)
    touches = (
        exact_point("-0.15", "-0.2"),
        exact_point("-0.15", "0.3"),
        exact_point(0, 0),
        exact_point("-0.15", "-0.2"),
    )
    assert polygon_inside_land(touches, land)
    shares = (
        exact_point("-0.2", "-0.4"),
        exact_point("-0.2", "2.4"),
        exact_point("-0.05", "1"),
        exact_point("-0.2", "-0.4"),
    )
    assert polygon_inside_land(shares, land)
    buried = (
        exact_point("0.4", "0.9"),
        exact_point("0.4", "1.1"),
        exact_point("0.6", "1"),
        exact_point("0.4", "0.9"),
    )
    assert not polygon_inside_land(buried, land)


def _ieee_fraction(raw: bytes) -> Fraction:
    bits = int.from_bytes(raw, "little")
    sign = -1 if bits >> 63 else 1
    exponent = (bits >> 52) & 0x7FF
    fraction = bits & ((1 << 52) - 1)
    if exponent == 0:
        return Fraction(sign * fraction, 1 << 1074)
    mantissa = fraction + (1 << 52)
    shift = exponent - 1075
    if shift >= 0:
        return Fraction(sign * mantissa * (1 << shift), 1)
    return Fraction(sign * mantissa, 1 << -shift)
