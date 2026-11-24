"""One test for each status make_area can return. Invented fixture."""

from __future__ import annotations

import pytest
from product.tests.make_area_support import (
    NO_CELL,
    ORIGIN,
    OUTSIDE,
    SHAPE_CROSS,
    SHAPE_OTHER,
    SHAPE_OUT,
    RecordingStore,
    box_route,
    context,
    geometry_rows,
)

from eii_product.store.registry import PACKAGED
from eii_product.tools.make_area import INVALID_ARGUMENT, RELEASE_MODE, make_area


def _run(request: dict, **overrides):
    store = RecordingStore(PACKAGED, geometry_rows())
    routed: list[object] = []

    def route(mode, minutes, latitude, longitude):
        routed.append((mode, minutes, latitude, longitude))
        return box_route(mode, minutes, latitude, longitude)

    result = make_area(store, request, context(PACKAGED, routing=route, **overrides))
    return result, store, routed


def test_status_ok() -> None:
    result, _store, _routed = _run(
        {
            "latitude": float(ORIGIN[0]),
            "longitude": float(ORIGIN[1]),
            "mode": "distance",
            "cutoff": 250,
        }
    )
    assert result.status == "OK"
    assert result.payload is not None


def test_pin_outside_the_land_area_is_out_of_scope() -> None:
    result, _store, _routed = _run(
        {
            "latitude": float(OUTSIDE[0]),
            "longitude": float(OUTSIDE[1]),
            "mode": "walk",
            "cutoff": 5,
        }
    )
    assert result.status == "OUT_OF_SCOPE"


def test_drawn_shape_not_wholly_inside_is_out_of_scope() -> None:
    refused, _store, _routed = _run({"shape_id": SHAPE_OUT})
    assert refused.status == "OUT_OF_SCOPE"
    accepted, _store, _routed = _run({"shape_id": SHAPE_CROSS})
    assert accepted.status == "OK"

    def accept_outside(status: str) -> str:
        return "OK"

    def expect_refused(status: str) -> None:
        assert status == "OUT_OF_SCOPE"

    expect_refused(refused.status)
    with pytest.raises(AssertionError):
        expect_refused(accept_outside(refused.status))


def test_pin_on_land_without_a_base_cell_is_not_out_of_scope() -> None:
    result, _store, _routed = _run(
        {
            "latitude": float(NO_CELL[0]),
            "longitude": float(NO_CELL[1]),
            "mode": "walk",
            "cutoff": 10,
        }
    )
    assert result.status == "OK"
    assert result.status != "OUT_OF_SCOPE"


def test_drive_at_hour_on_pin_without_base_cell() -> None:
    requests = (
        {"situation": "weekday_lunch", "summer": False},
        {"hour_key": "hour_09", "day_key": "weekday"},
        {"hour_key": "hour_09", "day_key": "friday"},
    )
    for extra in requests:
        result, store, routed = _run(
            {
                "latitude": float(NO_CELL[0]),
                "longitude": float(NO_CELL[1]),
                "mode": "drive",
                "cutoff": 10,
                **extra,
            }
        )
        assert result.status == "NO_DATA"
        assert result.reason == "point_without_base_cell"
        assert result.payload is None
        assert routed == []
        assert "traffic_hourly" not in " ".join(store.calls)

    def with_outline(result):
        return type(result)(
            result.tool,
            result.status,
            result.reason,
            result.release_id,
            {"outline": {}, "record": {}},
        )

    def expect_bare(result) -> None:
        assert result.payload is None

    sample, _store, _routed = _run(
        {
            "latitude": float(NO_CELL[0]),
            "longitude": float(NO_CELL[1]),
            "mode": "drive",
            "cutoff": 10,
            "situation": "friday_evening",
            "summer": True,
        }
    )
    expect_bare(sample)
    with pytest.raises(AssertionError):
        expect_bare(with_outline(sample))


def test_public_only_drive_with_a_key_on_a_pin_with_a_base_cell_is_invalid_argument() -> (
    None
):
    for extra in (
        {"situation": "weekday_evening", "summer": False},
        {"hour_key": "hour_12", "day_key": "weekday"},
    ):
        result, store, routed = _run(
            {
                "latitude": float(ORIGIN[0]),
                "longitude": float(ORIGIN[1]),
                "mode": "drive",
                "cutoff": 10,
                **extra,
            }
        )
        assert result.status == INVALID_ARGUMENT
        assert result.payload is None
        assert routed == []
        assert "traffic_hourly" not in " ".join(store.calls)


def test_order_of_checks() -> None:
    schema, store, _routed = _run(
        {
            "latitude": float(OUTSIDE[0]),
            "longitude": float(OUTSIDE[1]),
            "mode": "drive",
            "cutoff": 45,
        }
    )
    assert schema.status == INVALID_ARGUMENT
    assert store.calls == []
    other, _store, _routed = _run({"shape_id": SHAPE_OTHER})
    assert other.status == INVALID_ARGUMENT
    outside, _store, _routed = _run(
        {
            "latitude": float(OUTSIDE[0]),
            "longitude": float(OUTSIDE[1]),
            "mode": "drive",
            "cutoff": 10,
            "hour_key": "hour_09",
            "day_key": "weekday",
        }
    )
    assert outside.status == "OUT_OF_SCOPE"
    missing, _store, _routed = _run(
        {
            "latitude": float(NO_CELL[0]),
            "longitude": float(NO_CELL[1]),
            "mode": "drive",
            "cutoff": 10,
            "day_key": "weekday",
            "hour_key": "hour_09",
        }
    )
    assert missing.status == "NO_DATA"

    def swapped(status: str) -> str:
        if status == "NO_DATA":
            return INVALID_ARGUMENT
        return status

    def expect_no_data(status: str) -> None:
        assert status == "NO_DATA"

    expect_no_data(missing.status)
    with pytest.raises(AssertionError):
        expect_no_data(swapped(missing.status))


def test_unknown_shape_and_shape_of_another_seat_are_invalid_argument() -> None:
    unknown, _store, _routed = _run({"shape_id": "99" * 32})
    other, _store, _routed = _run({"shape_id": SHAPE_OTHER})
    assert unknown.status == INVALID_ARGUMENT
    assert other.status == INVALID_ARGUMENT


def test_tool_never_returns_suppressed() -> None:
    samples = (
        {
            "latitude": float(ORIGIN[0]),
            "longitude": float(ORIGIN[1]),
            "mode": "distance",
            "cutoff": 1000,
        },
        {"shape_id": SHAPE_OUT},
        {
            "latitude": float(NO_CELL[0]),
            "longitude": float(NO_CELL[1]),
            "mode": "drive",
            "cutoff": 5,
            "situation": "ramadan_iftar",
            "summer": False,
        },
    )
    for request in samples:
        result, _store, _routed = _run(request)
        assert result.status != "SUPPRESSED"


def test_non_public_mode_makes_no_area_and_reads_nothing() -> None:
    result, store, routed = _run(
        {
            "latitude": float(ORIGIN[0]),
            "longitude": float(ORIGIN[1]),
            "mode": "distance",
            "cutoff": 250,
        },
        release_mode="protected",
    )
    assert result.status == RELEASE_MODE
    assert result.reason == "release_not_public_only"
    assert result.payload is None
    assert store.calls == []
    assert routed == []
    assert result.status not in {"OK", "OUT_OF_SCOPE", "NO_DATA", INVALID_ARGUMENT}
