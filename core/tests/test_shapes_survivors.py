"""Invented coordinates for survivors of the exact-geometry module.

Expected numbers are hand-worked literals. Nothing here is a real place.
"""

from __future__ import annotations

import math
import struct
from decimal import ROUND_DOWN, Decimal, localcontext
from fractions import Fraction

import pytest

from eii_core.shapes import (
    GeometryTextError,
    _as_ccw,
    _as_point,
    _closed,
    _exact,
    canonical_ring,
    decode_geometry,
    exact_point,
    great_circle_m,
    reduce_six,
    representative_point,
    ring_is_simple,
)

REFUSED = "geometry text refused"
THREE = "A polygon requires three vertices"
NONZERO = "A polygon requires nonzero area"


def full_message(error: BaseException, expected: str) -> None:
    """Compare the whole refusal with a hand-written literal."""
    assert str(error) == expected


def _pair(lat: int | Fraction, lon: int | Fraction) -> tuple[Fraction, Fraction]:
    return (Fraction(lat), Fraction(lon))


def test_reduce_six_keeps_each_accepted_kind() -> None:
    assert reduce_six(1.5) == Decimal("1.500000")
    assert reduce_six(2) == Decimal("2.000000")
    assert reduce_six(Fraction(1, 2)) == Decimal("0.500000")
    assert reduce_six(Fraction(1, 3)) == Decimal("0.333333")
    with localcontext() as ctx:
        ctx.rounding = ROUND_DOWN
        assert reduce_six(Decimal("1.2345678")) == Decimal("1.234568")


def test_reduce_six_refusals_use_the_full_text() -> None:
    with pytest.raises(ValueError) as infinite:
        reduce_six(math.inf)
    full_message(infinite.value, REFUSED)
    with pytest.raises(ValueError) as quiet:
        reduce_six(Decimal("NaN"))
    full_message(quiet.value, REFUSED)
    with pytest.raises(TypeError) as text:
        reduce_six("4")
    full_message(text.value, REFUSED)
    with pytest.raises(TypeError) as flag:
        reduce_six(True)
    full_message(flag.value, REFUSED)


def test_canonical_triangle_of_area_one_half_stays_counterclockwise() -> None:
    # Shoelace of (0,0), (0,1), (1/2,0) is 1/2, so the ring is not reversed.
    assert canonical_ring(((0, 0), (0, 1), (Fraction(1, 2), 0))) == (
        _pair(0, 0),
        _pair(0, 1),
        _pair(Fraction(1, 2), 0),
        _pair(0, 0),
    )


def test_canonical_square_of_area_one_is_kept() -> None:
    # Shoelace is 1. A zero test written as == 1 would refuse this square.
    assert canonical_ring(((0, 0), (0, 1), (1, 1), (1, 0))) == (
        _pair(0, 0),
        _pair(0, 1),
        _pair(1, 1),
        _pair(1, 0),
        _pair(0, 0),
    )


def test_canonical_negative_area_is_reversed() -> None:
    # Shoelace of (0,0), (1,0), (0,1) is -1. Reversal gives (0,0), (0,1), (1,0).
    assert canonical_ring(((0, 0), (1, 0), (0, 1))) == (
        _pair(0, 0),
        _pair(0, 1),
        _pair(1, 0),
        _pair(0, 0),
    )


def test_canonical_refusals_use_the_full_text() -> None:
    with pytest.raises(ValueError) as few:
        canonical_ring(((0, 0), (1, 0)))
    full_message(few.value, THREE)
    with pytest.raises(ValueError) as flat:
        canonical_ring(((0, 0), (1, 0), (2, 0)))
    full_message(flat.value, NONZERO)


def test_representative_point_is_the_lowest_vertex() -> None:
    assert representative_point(((1, 1), (1, 0), (0, 0), (0, 1))) == _pair(0, 0)


def test_ring_is_simple_on_the_small_cases() -> None:
    assert ring_is_simple(()) is False
    assert ring_is_simple(((0, 0), (1, 0))) is False
    assert ring_is_simple(((0, 0), (1, 0), (0, 1))) is True


def test_great_circle_matches_the_hand_worked_distances() -> None:
    # One degree due north, haversine with radius 6371008.8.
    assert great_circle_m((0.0, 0.0), (1.0, 0.0)) == 111195.0802335329
    # (0,0) to (1,1), same radius and the haversine formula.
    assert great_circle_m((0.0, 0.0), (1.0, 1.0)) == 157249.59847404022
    # The sum is one unit past 1, so the clamp leaves pi times the radius 6371008.8.
    assert great_circle_m((-105.0, -360.0), (105.0, -180.0)) == 20015114.442035925
    # A non-finite latitude makes the sum NaN. min keeps the first argument, 1.
    assert great_circle_m((float("nan"), 0.0), (0.0, 0.0)) == 20015114.442035925


def test_exact_accepts_a_fraction_a_decimal_and_a_decimal_text() -> None:
    assert exact_point(Fraction(1, 2), 0) == (Fraction(1, 2), Fraction(0))
    assert _exact(Fraction(1, 2)) == Fraction(1, 2)
    assert exact_point(Decimal("1.5"), Decimal("-2.25")) == (
        Fraction(3, 2),
        Fraction(-9, 4),
    )
    assert exact_point("0.5", 2) == (Fraction(1, 2), Fraction(2))
    assert exact_point("1E+2", 0) == (Fraction(100), Fraction(0))


def test_exact_refusals_use_the_full_text() -> None:
    with pytest.raises(ValueError) as decimal_nan:
        exact_point(Decimal("NaN"), 0)
    full_message(decimal_nan.value, REFUSED)
    with pytest.raises(ValueError) as text_nan:
        exact_point("NaN", 0)
    full_message(text_nan.value, REFUSED)
    with pytest.raises(ValueError) as bad_text:
        exact_point("nope", 0)
    full_message(bad_text.value, REFUSED)
    with pytest.raises(ValueError) as infinite:
        exact_point(math.inf, 0)
    full_message(infinite.value, REFUSED)
    with pytest.raises(TypeError) as flag:
        exact_point(True, 0)
    full_message(flag.value, REFUSED)
    with pytest.raises(TypeError) as alien:
        exact_point(["nope"], 0)
    full_message(alien.value, REFUSED)


def test_as_point_converts_whichever_coordinate_is_not_a_fraction() -> None:
    converted = _as_point((Decimal("1.5"), Decimal("-2.25")))
    assert converted == (Fraction(3, 2), Fraction(-9, 4))
    assert type(converted[0]) is Fraction and type(converted[1]) is Fraction
    mixed = _as_point((Fraction(1), Decimal("0.5")))
    assert mixed == (Fraction(1), Fraction(1, 2))
    assert type(mixed[0]) is Fraction and type(mixed[1]) is Fraction
    swapped = _as_point((Decimal("1.5"), Fraction(1)))
    assert swapped == (Fraction(3, 2), Fraction(1))
    assert type(swapped[0]) is Fraction and type(swapped[1]) is Fraction


def test_closed_and_counterclockwise_rings() -> None:
    assert _closed(()) == ()
    opened = (_pair(0, 0), _pair(1, 0), _pair(0, 1))
    assert _closed(opened) == (*opened, _pair(0, 0))
    # Shoelace of this winding is -2, so the canonical orientation starts (0,0),(0,1).
    clockwise = (_pair(0, 0), _pair(1, 0), _pair(1, 1), _pair(0, 1), _pair(0, 0))
    assert _as_ccw(clockwise) == (
        _pair(0, 0),
        _pair(0, 1),
        _pair(1, 1),
        _pair(1, 0),
        _pair(0, 0),
    )
    small = (_pair(0, 0), _pair(0, 1), _pair(Fraction(1, 2), 0), _pair(0, 0))
    assert _as_ccw(small) == small
    flat = (_pair(0, 0), _pair(1, 0), _pair(2, 0), _pair(0, 0))
    assert _as_ccw(flat) == flat


def _polygon_bytes(rings: tuple[tuple[tuple[float, float], ...], ...]) -> bytes:
    chunks = [struct.pack("<BI", 1, 3), struct.pack("<I", len(rings))]
    for ring in rings:
        chunks.append(struct.pack("<I", len(ring)))
        for longitude, latitude in ring:
            chunks.append(struct.pack("<dd", longitude, latitude))
    return b"".join(chunks)


# (longitude, latitude). A triangle of area 1/2 in that order.
_TRIANGLE = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0))


def _hex(blob: bytes) -> str:
    return blob.hex().upper()


def test_decode_reads_a_polygon_of_exact_integers() -> None:
    decoded = decode_geometry(_hex(_polygon_bytes((_TRIANGLE,))))
    assert decoded == (
        (
            (
                _pair(0, 0),
                _pair(0, 1),
                _pair(1, 1),
                _pair(0, 0),
            ),
        ),
    )


def test_decode_reads_an_empty_multipolygon_and_refuses_a_nested_one() -> None:
    empty = struct.pack("<BI", 1, 6) + struct.pack("<I", 0)
    assert decode_geometry(_hex(empty)) == ()
    nested = (
        struct.pack("<BI", 1, 6)
        + struct.pack("<I", 1)
        + struct.pack("<BI", 1, 6)
        + struct.pack("<I", 1)
        + _polygon_bytes((_TRIANGLE,))
    )
    with pytest.raises(GeometryTextError) as caught:
        decode_geometry(_hex(nested))
    full_message(caught.value, REFUSED)


def test_decode_refusals_use_the_full_text() -> None:
    samples = (
        "",
        "0G",
        "01 03",
        "0103",
        _hex(struct.pack("<BI", 1, 3) + struct.pack("<I", 0)),
        _hex(
            struct.pack("<BI", 1, 3)
            + struct.pack("<I", 1)
            + struct.pack("<I", 3)
            + struct.pack("<dd", 0.0, 0.0)
            + struct.pack("<dd", 1.0, 0.0)
            + struct.pack("<dd", 0.0, 1.0)
        ),
        _hex(struct.pack("<BI", 1, 3)),
        _hex(
            struct.pack("<BI", 1, 6)
            + struct.pack("<I", 2)
            + _polygon_bytes((_TRIANGLE,))
        ),
        _hex(
            _polygon_bytes(
                (((math.inf, 0.0), (1.0, 0.0), (0.0, 1.0), (math.inf, 0.0)),)
            )
        ),
    )
    for text in samples:
        with pytest.raises(GeometryTextError) as caught:
            decode_geometry(text)
        full_message(caught.value, REFUSED)


def test_odd_length_and_lowercase_are_refused() -> None:
    for text in ("010", "0A0", _hex(_polygon_bytes((_TRIANGLE,))).lower()):
        with pytest.raises(GeometryTextError) as caught:
            decode_geometry(text)
        full_message(caught.value, REFUSED)


def test_a_space_inside_a_valid_polygon_is_refused() -> None:
    whole = _hex(_polygon_bytes((_TRIANGLE,)))
    with pytest.raises(GeometryTextError) as caught:
        decode_geometry(whole[:4] + "  " + whole[4:])
    full_message(caught.value, REFUSED)


def test_a_count_past_the_signed_range_is_refused() -> None:
    blob = struct.pack("<BI", 1, 6) + struct.pack("<I", 1 << 31)
    with pytest.raises(GeometryTextError) as caught:
        decode_geometry(_hex(blob))
    full_message(caught.value, REFUSED)
