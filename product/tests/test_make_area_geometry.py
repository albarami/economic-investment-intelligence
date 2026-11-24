"""Public-only geometry. The fixture is invented."""

from __future__ import annotations

from decimal import Decimal

import pytest
from product.tests.make_area_support import (
    EDGE_PIN,
    FRAME,
    NO_CELL,
    ORIGIN,
    SHAPE_EMPTY,
    RecordingStore,
    box_route,
    context,
    geometry_rows,
)

from eii_core.grid import cell_centre
from eii_product.store.registry import PACKAGED
from eii_product.tools.make_area import make_area


def _store() -> RecordingStore:
    return RecordingStore(PACKAGED, geometry_rows())


def _call(store: RecordingStore, request: dict, **overrides):
    routed: list[tuple] = []

    def route(mode, minutes, latitude, longitude):
        routed.append((mode, minutes, latitude, longitude))
        return box_route(mode, minutes, latitude, longitude)

    result = make_area(
        store,
        request,
        context(PACKAGED, routing=route, **overrides),
    )
    return result, routed


def test_units_whole_and_deterministic() -> None:
    store = _store()
    request = {
        "latitude": float(ORIGIN[0]),
        "longitude": float(ORIGIN[1]),
        "mode": "distance",
        "cutoff": 250,
    }
    first, _routed = _call(store, request)
    second, _again = _call(store, request)
    cells = first.payload["units"]["cells"]
    assert first.status == "OK"
    assert cells == second.payload["units"]["cells"]
    assert cells == sorted(cells)
    frame = {cell: resolution for cell, resolution in FRAME}
    assert all(int(cell) in frame for cell in cells)

    def compacted(answer):
        parent = int(cells[0]) + 1
        return (*answer, str(parent))

    def expect_stored(values) -> None:
        assert all(int(cell) in frame for cell in values)

    expect_stored(cells)
    with pytest.raises(AssertionError):
        expect_stored(compacted(cells))


def test_base_cell_is_always_in_the_cell_set() -> None:
    store = _store()
    result, _routed = _call(
        store,
        {
            "latitude": float(EDGE_PIN[0]),
            "longitude": float(EDGE_PIN[1]),
            "mode": "walk",
            "cutoff": 5,
        },
    )
    anchor = result.payload["record"]["anchor_cell"]
    assert anchor in result.payload["units"]["cells"]

    def without_union(cells, base):
        return [cell for cell in cells if cell != base]

    def expect_member(cells, base) -> None:
        assert base in cells

    expect_member(result.payload["units"]["cells"], anchor)
    with pytest.raises(AssertionError):
        expect_member(without_union(result.payload["units"]["cells"], anchor), anchor)


def test_distance_cells_from_the_base_cell_centre_and_outline_from_the_pin() -> None:
    store = _store()
    result, _routed = _call(
        store,
        {
            "latitude": float(EDGE_PIN[0]),
            "longitude": float(EDGE_PIN[1]),
            "mode": "distance",
            "cutoff": 250,
        },
    )
    outline = result.payload["outline"]
    assert outline["coordinates"] == [EDGE_PIN[1], EDGE_PIN[0]]
    centre = cell_centre(int(result.payload["record"]["anchor_cell"]))
    assert outline["coordinates"] != [Decimal(str(centre[1])), Decimal(str(centre[0]))]
    from eii_core.grid import cells_in_circle

    from_centre = [
        str(cell) for cell in cells_in_circle(centre[0], centre[1], 250, FRAME)
    ]
    from_pin = [
        str(cell)
        for cell in cells_in_circle(float(EDGE_PIN[0]), float(EDGE_PIN[1]), 250, FRAME)
    ]
    assert result.payload["units"]["cells"] == from_centre
    assert result.payload["units"]["cells"] != from_pin


def test_walk_and_drive_start_at_the_pin() -> None:
    store = _store()
    for mode, cutoff in (("walk", 5), ("drive", 10)):
        _result, routed = _call(
            store,
            {
                "latitude": float(EDGE_PIN[0]),
                "longitude": float(EDGE_PIN[1]),
                "mode": mode,
                "cutoff": cutoff,
            },
        )
        assert routed[-1][2] == EDGE_PIN[0]
        assert routed[-1][3] == EDGE_PIN[1]

    def from_centre(mode, minutes, latitude, longitude):
        del latitude, longitude
        centre = cell_centre(int(_result.payload["record"]["anchor_cell"]))
        return box_route(
            mode, minutes, Decimal(str(centre[0])), Decimal(str(centre[1]))
        )

    def expect_pin(route) -> None:
        ring = route("walk", 5, EDGE_PIN[0], EDGE_PIN[1])
        assert ring[0] == (EDGE_PIN[0], EDGE_PIN[1])

    expect_pin(box_route)
    with pytest.raises(AssertionError):
        expect_pin(from_centre)


def test_polygon_selecting_no_cell_is_ok() -> None:
    store = _store()
    result, _routed = _call(store, {"shape_id": SHAPE_EMPTY})
    assert result.status == "OK"
    assert result.payload["units"]["cells"] == []
    assert result.payload["outline"]["type"] == "Polygon"

    def nonempty(cells):
        if not cells:
            raise ValueError("The shape covers no frame cell")
        return cells

    def expect_empty(cells) -> None:
        assert nonempty(cells) == []

    with pytest.raises(ValueError, match="no frame cell"):
        expect_empty(result.payload["units"]["cells"])


def test_pin_without_base_cell() -> None:
    store = _store()
    result, _routed = _call(
        store,
        {
            "latitude": float(NO_CELL[0]),
            "longitude": float(NO_CELL[1]),
            "mode": "distance",
            "cutoff": 500,
        },
    )
    assert result.status == "OK"
    assert result.payload["record"]["anchor_cell"] is None
    assert result.payload["units"] == {}
    assert result.payload["snap_report"] is None
    assert "protected" not in result.payload["record"]

    def nearest(answer):
        answer["record"]["anchor_cell"] = str(FRAME[0][0])
        answer["cells"] = [str(FRAME[0][0])]
        answer["snap_report"] = {
            "cells": answer["cells"],
            "note": "SNAPPED_TO_WHOLE_UNITS",
        }
        return answer

    def expect_absent(payload) -> None:
        assert payload["record"]["anchor_cell"] is None
        assert payload["units"] == {}
        assert payload["snap_report"] is None

    expect_absent(result.payload)
    with pytest.raises(AssertionError):
        expect_absent(nearest(dict(result.payload)))
