"""The tool's own result. Invented fixture."""

from __future__ import annotations

import math
from decimal import Decimal

import pytest
from product.tests.make_area_support import (
    FRAME,
    ORIGIN,
    SHAPE_INSIDE,
    MapShapes,
    RecordingStore,
    box_route,
    context,
    geometry_rows,
)

from eii_core.grid import cell_centre
from eii_core.shapes import point_in_polygon, within_radius
from eii_product.store.registry import PACKAGED
from eii_product.tools.areas import canonical_json
from eii_product.tools.make_area import RegisteredShape, make_area


def _one(request: dict, shapes=None):
    store = RecordingStore(PACKAGED, geometry_rows())
    result = make_area(
        store,
        request,
        context(PACKAGED, routing=box_route, shapes=shapes or MapShapes()),
    )
    return result


def test_result_carries_no_fact_and_no_provenance_word() -> None:
    result = _one(
        {
            "latitude": float(ORIGIN[0]),
            "longitude": float(ORIGIN[1]),
            "mode": "distance",
            "cutoff": 250,
        }
    )
    assert result.status == "OK"
    assert not hasattr(result, "facts")
    text = canonical_json(result.payload).decode("utf-8")
    for word in ("provenance", "synthetic", "public", "simulated", "observed"):
        assert word not in text.lower()

    def labelled(payload):
        copy = dict(payload)
        copy["snap_report"] = {
            "cells": [],
            "note": "SNAPPED_TO_WHOLE_UNITS",
            "provenance": "synthetic",
        }
        return copy

    def expect_plain(payload) -> None:
        encoded = canonical_json(payload).decode("utf-8").lower()
        assert "provenance" not in encoded
        assert "synthetic" not in encoded

    expect_plain(result.payload)
    with pytest.raises(AssertionError):
        expect_plain(labelled(result.payload))


def test_snap_report_is_sorted_identifiers_and_the_sentence_key() -> None:
    result = _one({"shape_id": SHAPE_INSIDE})
    report = result.payload["snap_report"]
    assert report["note"] == "SNAPPED_TO_WHOLE_UNITS"
    assert report["cells"] == sorted(report["cells"])
    assert all(isinstance(cell, str) for cell in report["cells"])

    def with_count(report):
        return {"cells": report["cells"], "note": report["note"], "cells_inside": 3}

    def expect_key(report) -> None:
        assert set(report) == {"cells", "note"}
        assert report["note"] == "SNAPPED_TO_WHOLE_UNITS"

    expect_key(report)
    with pytest.raises(AssertionError):
        expect_key(with_count(report))


def test_result_holds_no_count_numeral() -> None:
    """Every number in the result is visited. Geometry and the request may hold one."""
    result = _one(
        {
            "latitude": float(ORIGIN[0]),
            "longitude": float(ORIGIN[1]),
            "mode": "distance",
            "cutoff": 250,
        }
    )
    found = _numbers(_result_tree(result))
    assert any(path[:2] == ("payload", "outline") for path, _value in found)
    assert any(path[:3] == ("payload", "record", "request") for path, _value in found)
    _allow_only_geometry_and_request(result)

    def with_count(payload):
        report = dict(payload["snap_report"])
        report["cells_inside"] = 3
        copy = dict(payload)
        copy["snap_report"] = report
        return copy

    counted = _result_tree(result)
    counted["payload"] = with_count(result.payload)
    with pytest.raises(AssertionError):
        _allow_only_geometry_and_request_tree(counted)


def test_outline_preserves_exact_finite_coordinates() -> None:
    boundary = math.ldexp(math.nextafter(1.0, 2.0), -10)
    digits = (
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        9,
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        9,
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        9,
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        9,
        0,
    )
    long_decimal = Decimal((0, digits, -38))
    ring = (
        (Decimal("-0.02"), Decimal("-0.02")),
        (Decimal("-0.02"), Decimal("0.004")),
        (boundary, long_decimal),
        (Decimal("-0.02"), Decimal("-0.02")),
    )

    class Exact:
        def find(self, shape_id):
            del shape_id
            return RegisteredShape(ring)

    result = _one({"shape_id": "9a" * 32}, shapes=Exact())
    assert result.status == "OK"
    pairs = {
        (point[1], point[0]) for point in result.payload["outline"]["coordinates"][0]
    }
    assert (Decimal.from_float(boundary), long_decimal) in pairs


def test_public_points_are_selected_against_the_outline() -> None:
    anchor = next(cell for cell, resolution in FRAME if resolution == 9)
    centre = cell_centre(anchor)
    span = Decimal("0.00001")
    lat = Decimal(str(centre[0]))
    lon = Decimal(str(centre[1]))
    ring = (
        (lat - span, lon - span),
        (lat - span, lon + span),
        (lat + span, lon + span),
        (lat + span, lon - span),
        (lat - span, lon - span),
    )

    class One:
        def find(self, shape_id):
            del shape_id
            return RegisteredShape(ring)

    result = _one({"shape_id": "ab" * 32}, shapes=One())
    assert result.status == "OK"
    assert str(anchor) in result.payload["units"]["cells"]
    outline = tuple(
        (point[1], point[0]) for point in result.payload["outline"]["coordinates"][0]
    )
    assert point_in_polygon((lat, lon), (outline,))
    import h3

    outside = h3.cell_to_boundary(h3.int_to_str(anchor))[0]
    assert within_radius((centre[0], centre[1]), (outside[0], outside[1]), 50_000)
    assert not point_in_polygon(
        (Decimal(str(outside[0])), Decimal(str(outside[1]))), (outline,)
    )

    def by_cell_union(point) -> bool:
        return True

    def expect_outside(selected) -> None:
        assert selected is False

    expect_outside(
        point_in_polygon(
            (Decimal(str(outside[0])), Decimal(str(outside[1]))), (outline,)
        )
    )
    with pytest.raises(AssertionError):
        expect_outside(by_cell_union(outside))


_ALLOWED = (
    ("payload", "outline"),
    ("payload", "record", "requested_shape"),
    ("payload", "record", "request"),
)


def _result_tree(result) -> dict:
    return {
        "tool": result.tool,
        "status": result.status,
        "reason": result.reason,
        "release_id": result.release_id,
        "payload": result.payload,
    }


def _numbers(value, path=()):
    found = []
    if type(value) is bool:
        return found
    if type(value) in (int, float, Decimal):
        found.append((path, value))
        return found
    if type(value) is dict:
        for key, item in value.items():
            found.extend(_numbers(item, (*path, key)))
        return found
    if type(value) in (list, tuple):
        for index, item in enumerate(value):
            found.extend(_numbers(item, (*path, index)))
    return found


def _allowed(path) -> bool:
    return any(path[: len(prefix)] == prefix for prefix in _ALLOWED)


def _allow_only_geometry_and_request(result) -> None:
    _allow_only_geometry_and_request_tree(_result_tree(result))


def _allow_only_geometry_and_request_tree(tree) -> None:
    for path, _value in _numbers(tree):
        assert _allowed(path), path
