"""Closed source geometry bounds, orientation and exact vertex preservation."""

import json
from copy import deepcopy
from fractions import Fraction
from itertools import pairwise
from pathlib import Path

import pytest

from eii_core.calc.source_geometry import validate_source_geometry

OUTER = [[0.123456789, 0], [3, 0], [3, 3], [0, 3], [0.123456789, 0]]
HOLE = [[1, 1], [1, 2], [2, 2], [2, 1], [1, 1]]
ISLAND = [[4, 0], [5, 0], [5, 1], [4, 1], [4, 0]]


@pytest.mark.parametrize(
    "case",
    json.loads(Path("web/tests/fixtures/source-orientation.json").read_text()),
    ids=lambda case: case["name"],
)
def test_shared_binary_orientation(case):
    geometry = deepcopy(case["geometry"])
    if case["accepted"]:
        assert validate_source_geometry(geometry) is geometry
    else:
        with pytest.raises(ValueError, match="source_geometry_invalid"):
            validate_source_geometry(geometry)
    assert geometry == case["geometry"]


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Point", "coordinates": [1, 2]},
        {"type": "LineString", "coordinates": [[1, 2], [3, 4]]},
        {"type": "Polygon", "coordinates": [OUTER, HOLE]},
        {"type": "MultiPolygon", "coordinates": [[OUTER, HOLE], [ISLAND]]},
    ],
)
def test_geometry_is_unchanged(geometry):
    before = deepcopy(geometry)
    assert validate_source_geometry(geometry) == before
    assert geometry == before


@pytest.mark.parametrize(
    "geometry",
    [
        {"type": "Polygon", "coordinates": [OUTER[:-1]]},
        {"type": "Polygon", "coordinates": [list(reversed(OUTER))]},
        {"type": "Polygon", "coordinates": [OUTER, list(reversed(HOLE))]},
        {"type": "Polygon", "coordinates": []},
        {"type": "Polygon", "coordinates": [HOLE, OUTER]},
        {"type": "Polygon", "coordinates": [OUTER] * 65},
        {"type": "MultiPolygon", "coordinates": [[OUTER]] * 65},
        {"type": "LineString", "coordinates": [[1, 2]] * 4097},
        {"type": "MultiPolygon", "coordinates": [[OUTER] + [HOLE] * 63] * 64},
        {"type": "Point", "coordinates": [1, 2, 3]},
        {"type": "Point", "coordinates": [True, 2]},
        {"type": "Point", "coordinates": [float("nan"), 2]},
        {"type": "Point", "coordinates": [181, 2]},
        {"type": "Point", "coordinates": [1, 91]},
        {"type": "Point", "coordinates": [1, 2], "extra": True},
        {"type": "GeometryCollection", "coordinates": []},
        {"type": "MultiPolygon", "coordinates": [[[[[1, 2]]]]]},
    ],
)
def test_geometry_refusals(geometry):
    with pytest.raises(ValueError, match="source_geometry_invalid"):
        validate_source_geometry(geometry)


def test_closed_limits_are_inclusive():
    assert validate_source_geometry(
        {"type": "LineString", "coordinates": [[1, 2]] * 4096}
    )
    assert validate_source_geometry(
        {"type": "MultiPolygon", "coordinates": [[OUTER]] * 64}
    )
    assert validate_source_geometry(
        {"type": "Polygon", "coordinates": [OUTER] + [HOLE] * 63}
    )


_EXACT_FIXTURE = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "web/tests/fixtures/source-geometry-exact.json"
    ).read_text()
)


@pytest.mark.parametrize("case", _EXACT_FIXTURE["cases"], ids=lambda case: case["name"])
def test_shared_exact_orientation(case):
    geometry = deepcopy(case["geometry"])
    before = deepcopy(geometry)
    ring = (
        geometry["coordinates"][0][0]
        if geometry["type"] == "MultiPolygon"
        else geometry["coordinates"][0]
    )
    area = sum(
        Fraction(a[0]) * Fraction(b[1]) - Fraction(b[0]) * Fraction(a[1])
        for a, b in pairwise(ring)
    )
    assert (area > 0) - (area < 0) == case["sign"]
    assert case["accepted"] == (case["sign"] > 0)
    if case["accepted"]:
        assert validate_source_geometry(geometry) is geometry
    else:
        with pytest.raises(ValueError, match=r"^source_geometry_invalid$"):
            validate_source_geometry(geometry)
    assert geometry == before


@pytest.mark.parametrize("case", _EXACT_FIXTURE["cases"], ids=lambda case: case["name"])
def test_shared_exact_hole_orientation(case):
    source = case["geometry"]
    ring = (
        source["coordinates"][0][0]
        if source["type"] == "MultiPolygon"
        else source["coordinates"][0]
    )
    geometry = {"type": "Polygon", "coordinates": [OUTER, ring]}
    before = deepcopy(geometry)
    if case["sign"] < 0:
        assert validate_source_geometry(geometry) is geometry
    else:
        with pytest.raises(ValueError, match=r"^source_geometry_invalid$"):
            validate_source_geometry(geometry)
    assert geometry == before
