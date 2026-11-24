"""Exact inclusion and closed outline parsing; no approximated circle."""

import math
from decimal import Decimal as D

import pytest

from eii_core.shapes import canonical_ring, great_circle_m
from eii_product.tools.area_outline import (
    CircleOutline,
    OutlineError,
    PolygonOutline,
    covers,
    read_outline,
)
from eii_product.tools.make_area import DISTANCE_M


def test_circle_boundary_and_next_float():
    pin, centre = (1.0, 1.0), (1.01, 1.02)
    distance = great_circle_m(pin, centre)
    assert covers(CircleOutline(D(1), D(1), distance), *centre)
    assert not covers(CircleOutline(D(1), D(1), math.nextafter(distance, 0.0)), *centre)
    assert DISTANCE_M == {250, 500, 1000}
    with pytest.raises(OutlineError):
        read_outline(
            {"type": "Circle", "coordinates": [D(1), D(1)], "radius_m": distance}
        )


def test_polygon_vertex_edge_and_circle_lon_lat():
    polygon = read_outline(
        {
            "type": "Polygon",
            "coordinates": [
                [[D(0), D(0)], [D(2), D(0)], [D(2), D(1)], [D(0), D(1)], [D(0), D(0)]]
            ],
        }
    )
    assert isinstance(polygon, PolygonOutline)
    assert polygon.ring == canonical_ring(((0, 0), (0, 2), (1, 2), (1, 0), (0, 0)))
    assert covers(polygon, 0, 1) and covers(polygon, 1, 2)
    assert not covers(polygon, 1.1, 1)
    circle = read_outline(
        {"type": "Circle", "coordinates": [D(2), D(1)], "radius_m": 500}
    )
    assert circle == CircleOutline(D(1), D(2), 500)
    assert covers(circle, 1, 2) and not covers(circle, 2, 1)


@pytest.mark.parametrize(
    "raw",
    [
        {"type": "Circle", "coordinates": [D(1), D(1)], "radius_m": 500, "extra": 0},
        {"type": "Circle", "coordinates": [1.0, D(1)], "radius_m": 500},
        {"type": "Circle", "coordinates": [D("NaN"), D(1)], "radius_m": 500},
        {"type": "Circle", "coordinates": [D(1), D(1)], "radius_m": True},
        {"type": "Circle", "coordinates": [D(1), D(1)], "radius_m": 501},
        {"type": "Circle", "coordinates": [D(1), D(1)], "radius_m": D("NaN")},
        {"type": "Circle", "coordinates": [D(181), D(1)], "radius_m": 500},
        {"type": "Point", "coordinates": [D(1), D(1)]},
        {"type": "Polygon", "coordinates": []},
        {"type": "Polygon", "coordinates": [[[D(0), D(0)]]] * 2},
        {
            "type": "Polygon",
            "coordinates": [[[D(0), D(0)], [D(1), D(0)], [D(1), D(1)], [D(0), D(1)]]],
        },
    ],
)
def test_outline_guard_plants(raw):
    with pytest.raises(OutlineError):
        read_outline(raw)
