"""Fix-pass-2 plants. Invented coordinates. Each refusal is asserted through make_area."""

from __future__ import annotations

import math

import pytest
from product.tests.make_area_support import (
    ORIGIN,
    SHAPE_INSIDE,
    RecordingStore,
    allowed_tables,
    context,
    geometry_rows,
)

from eii_product.store.registry import PACKAGED
from eii_product.tools.make_area import INVALID_ARGUMENT, RegisteredShape, make_area
from eii_product.tools.routing import RoutingTilesUnavailable

PIN = {
    "latitude": float(ORIGIN[0]),
    "longitude": float(ORIGIN[1]),
    "mode": "walk",
    "cutoff": 5,
}
DISTANCE = {
    "latitude": float(ORIGIN[0]),
    "longitude": float(ORIGIN[1]),
    "mode": "distance",
    "cutoff": 250,
}


def _polygon(ring: list[list[object]]) -> dict[str, object]:
    return {
        "features": [
            {"geometry": {"type": "Polygon", "coordinates": [ring]}},
        ]
    }


def _routing_refusal(answer: object) -> None:
    store = RecordingStore(PACKAGED, geometry_rows())

    def route(mode: str, minutes: int, latitude: object, longitude: object) -> object:
        del mode, minutes, latitude, longitude
        return answer

    with pytest.raises(
        RoutingTilesUnavailable, match="routing tiles unavailable"
    ) as caught:
        make_area(store, PIN, context(PACKAGED, routing=route))
    error = caught.value
    assert str(error) == "routing tiles unavailable"
    assert error.__cause__ is None
    assert error.__context__ is None
    allowed_tables(PACKAGED, store.calls)


def test_empty_features_are_the_routing_refusal() -> None:
    _routing_refusal({"features": []})


def test_missing_geometry_is_the_routing_refusal() -> None:
    _routing_refusal({"features": [{"type": "Feature"}]})


def test_missing_coordinates_are_the_routing_refusal() -> None:
    _routing_refusal({"features": [{"geometry": {"type": "Polygon"}}]})


def test_position_with_three_numbers_is_the_routing_refusal() -> None:
    _routing_refusal(
        _polygon([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 0.0, 0.0]])
    )


def test_nan_position_is_the_routing_refusal() -> None:
    _routing_refusal(
        _polygon([[math.nan, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [math.nan, 0.0]])
    )


def test_boolean_position_is_the_routing_refusal() -> None:
    """True must not count as 1. As 1 this ring would be the unit square."""
    _routing_refusal(
        _polygon([[0.0, 0.0], [1.0, 0.0], [1.0, True], [0.0, True], [0.0, 0.0]])
    )


def test_two_vertices_are_the_routing_refusal() -> None:
    _routing_refusal(_polygon([[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]]))


def test_zero_area_routed_ring_is_the_routing_refusal() -> None:
    _routing_refusal(_polygon([[0.0, 0.0], [2.0, 0.0], [1.0, 0.0], [0.0, 0.0]]))


def test_bow_tie_routed_ring_is_the_routing_refusal() -> None:
    """Unequal lobes, so the signed area is not zero and simplicity is the refusal."""
    _routing_refusal(
        _polygon([[0.0, 0.0], [3.0, 2.0], [0.0, 2.0], [2.0, 0.0], [0.0, 0.0]])
    )


class _FixedShape:
    """One registered ring. The lookup does not touch the store."""

    def __init__(self, ring: tuple[tuple[object, object], ...]) -> None:
        self._ring = ring

    def find(self, shape_id: str) -> RegisteredShape:
        del shape_id
        return RegisteredShape(self._ring)


def _shape_refusal(ring: tuple[tuple[object, object], ...]) -> None:
    store = RecordingStore(PACKAGED, geometry_rows())
    result = make_area(
        store,
        {"shape_id": SHAPE_INSIDE},
        context(PACKAGED, shapes=_FixedShape(ring)),
    )
    assert result.status == INVALID_ARGUMENT
    assert result.payload is None
    assert store.calls == []


def test_self_intersecting_registered_ring_is_invalid_argument() -> None:
    """(lon, lat) (0,0)-(3,2) crosses (0,2)-(2,0). The signed area is not zero."""
    _shape_refusal(((0, 0), (2, 3), (2, 0), (0, 2), (0, 0)))


def test_registered_ring_with_fewer_than_four_positions_is_invalid_argument() -> None:
    _shape_refusal(((0, 0), (1, 0), (0, 0)))


def test_nan_registered_ring_is_invalid_argument() -> None:
    _shape_refusal(((0.0, 0.0), (1.0, 0.0), (1.0, math.nan), (0.0, 0.0)))


def test_zero_area_registered_ring_is_invalid_argument() -> None:
    _shape_refusal(((0, 0), (1, 0), (2, 0), (0, 0)))


def _pin_key_refusal(request: dict[str, object]) -> None:
    store = RecordingStore(PACKAGED, geometry_rows())
    result = make_area(store, request, context(PACKAGED))
    assert result.status == INVALID_ARGUMENT
    assert result.payload is None
    assert store.calls == []


def test_unknown_pin_key_is_invalid_argument_with_no_read() -> None:
    _pin_key_refusal({**DISTANCE, "extra": "no"})


def test_pin_key_in_another_case_is_invalid_argument_with_no_read() -> None:
    _pin_key_refusal({**DISTANCE, "Mode": "distance"})


def test_payload_cells_and_snap_cells_are_not_one_list() -> None:
    store = RecordingStore(PACKAGED, geometry_rows())
    result = make_area(
        store,
        {"shape_id": SHAPE_INSIDE},
        context(PACKAGED),
    )
    assert result.payload is not None
    report = result.payload["snap_report"]
    assert isinstance(report, dict)
    left = result.payload["units"]["cells"]
    right = report["cells"]
    assert isinstance(left, list)
    assert isinstance(right, list)
    assert left == right
    assert left is not right
    left.append("plant")
    assert "plant" not in right
