"""Closed request schema of make_area. Invented values only."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from eii_product.tools.make_area import INVALID_ARGUMENT, validate_request

DISTANCE = (250, 500, 1000)
WALK = (5, 10, 15)
DRIVE = (5, 10, 15)
DRIVE_STAFFING = (20, 30)
SITUATIONS = (
    "weekday_lunch",
    "weekday_evening",
    "friday_evening",
    "ramadan_iftar",
)
PLAYBOOK = "staffing_and_pay"
OTHER_PLAYBOOK = "labour_market"
HOURS = frozenset({"hour_09", "hour_12"})
DAYS = frozenset({"weekday", "friday"})


def _pin(**extra: object) -> dict[str, object]:
    body: dict[str, object] = {
        "latitude": 0.0,
        "longitude": 0.0,
        "mode": "distance",
        "cutoff": 250,
    }
    body.update(extra)
    return body


def _refused(request: Mapping[str, object], playbook: str | None = None) -> None:
    with pytest.raises(ValueError, match=INVALID_ARGUMENT):
        validate_request(request, playbook, HOURS, DAYS)


def test_drive_cutoff_above_30_is_refused() -> None:
    """TST-256: the closed schema refuses a drive above 30 minutes."""
    from eii_product.tools.make_area import DRIVE_LIMIT_MINUTES

    assert DRIVE_LIMIT_MINUTES == 30
    _refused(_pin(mode="drive", cutoff=45), None)
    _refused(_pin(mode="drive", cutoff=45), PLAYBOOK)


def test_closed_cutoffs_only() -> None:
    """Every allowed pair passes. Each planted outsider is refused."""
    for cutoff in DISTANCE:
        validate_request(_pin(mode="distance", cutoff=cutoff), None)
    for cutoff in WALK:
        validate_request(_pin(mode="walk", cutoff=cutoff), None)
    for cutoff in DRIVE:
        validate_request(_pin(mode="drive", cutoff=cutoff), None)
        validate_request(_pin(mode="drive", cutoff=cutoff), PLAYBOOK)
    for cutoff in DRIVE_STAFFING:
        validate_request(_pin(mode="drive", cutoff=cutoff), PLAYBOOK)
    for situation in SITUATIONS:
        summer = situation != "ramadan_iftar"
        validate_request(
            _pin(mode="drive", cutoff=10, situation=situation, summer=summer),
            None,
        )
    validate_request(
        _pin(mode="drive", cutoff=10, hour_key="hour_09", day_key="weekday"),
        None,
        HOURS,
        DAYS,
    )
    _refused(
        _pin(mode="drive", cutoff=10, hour_key="hour_09", day_key="not_a_day"),
        None,
    )
    _refused(
        _pin(mode="drive", cutoff=10, hour_key="not_listed", day_key="weekday"),
        None,
    )
    _refused(
        _pin(
            mode="drive",
            cutoff=10,
            situation=None,
            hour_key="hour_09",
            day_key="weekday",
        ),
        None,
    )
    _refused(_pin(mode="distance", hour_key=None), None)
    validate_request(
        {"place_key": "SYN-place", "mode": "walk", "cutoff": 5},
        None,
    )
    _refused(_pin(mode="distance", cutoff=300), None)
    _refused(_pin(mode="walk", cutoff=20), None)
    _refused(_pin(mode="drive", cutoff=7), None)
    _refused(_pin(mode="drive", cutoff=True), None)
    _refused(_pin(mode="drive", cutoff=10.0), None)
    _refused(_pin(mode="drive", cutoff="10"), None)
    _refused(_pin(mode="drive", situation="unknown_key", summer=False), None)
    _refused({"mode": "distance", "cutoff": 250}, None)
    _refused(
        {
            "shape_id": "ab" * 32,
            "latitude": 0.0,
            "longitude": 0.0,
            "mode": "distance",
            "cutoff": 250,
        },
        None,
    )
    _refused({"shape_id": "ab" * 32, "mode": "walk"}, None)
    _refused({"shape_id": "ab" * 32, "cutoff": 250}, None)
    _refused({"shape_id": "ab" * 32, "situation": "weekday_lunch"}, None)
    _refused(_pin(mode="distance", situation="weekday_lunch", summer=False), None)
    _refused(_pin(mode="walk", hour_key="hour_09", day_key="weekday"), None)
    _refused(_pin(latitude=True), None)
    _refused(_pin(latitude=91.0), None)
    _refused(_pin(longitude=181.0), None)
    _refused(_pin(latitude=float("nan")), None)
    _refused(_pin(mode="drive; drop table grid_cell"), None)
    _refused(_pin(mode="SELECT"), None)


def test_distance_outside_the_list_and_walk_20_are_refused() -> None:
    _refused(_pin(mode="distance", cutoff=300), None)
    _refused(_pin(mode="walk", cutoff=20), None)


def test_drive_20_and_30_only_in_staffing_and_pay() -> None:
    for cutoff in DRIVE_STAFFING:
        validate_request(_pin(mode="drive", cutoff=cutoff), PLAYBOOK)
        _refused(_pin(mode="drive", cutoff=cutoff), None)
        _refused(_pin(mode="drive", cutoff=cutoff), OTHER_PLAYBOOK)


def test_summer_with_ramadan_iftar_is_refused() -> None:
    _refused(
        _pin(mode="drive", cutoff=10, situation="ramadan_iftar", summer=True),
        PLAYBOOK,
    )
    validate_request(
        _pin(mode="drive", cutoff=10, situation="ramadan_iftar", summer=False),
        None,
    )


def test_shape_enters_only_by_identifier() -> None:
    validate_request({"shape_id": "ab" * 32}, None)
    _refused({"ring": [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [0.0, 0.0]]}, None)
    _refused(
        {"type": "Polygon", "coordinates": [[[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]]]},
        None,
    )
    _refused(
        {
            "shape_id": "ab" * 32,
            "geometry": {"type": "Polygon", "coordinates": []},
        },
        None,
    )


def test_request_carries_exactly_the_fields_of_its_shape() -> None:
    _refused({}, None)
    _refused({"shape_id": "ab" * 32, "latitude": 0.0, "longitude": 0.0}, None)
    _refused({"latitude": 0.0, "longitude": 0.0}, None)
    _refused(_pin(place_key="SYN-place"), None)
    _refused(
        _pin(mode="drive", situation="weekday_lunch", summer=False, hour_key="hour_09"),
        None,
    )
    _refused(_pin(mode="drive", hour_key="hour_09"), None)
    _refused(_pin(mode="drive", summer=True), None)
    validate_request({"shape_id": "cd" * 32}, PLAYBOOK)


def test_a_refusal_reads_and_routes_nothing() -> None:
    """Schema refusals leave the store and the router untouched."""
    from product.tests.make_area_support import (
        RecordingStore,
        context,
        geometry_rows,
    )

    from eii_product.store.registry import PACKAGED
    from eii_product.tools.make_area import make_area

    samples: tuple[tuple[Mapping[str, object], str | None], ...] = (
        (_pin(mode="drive", cutoff=45), None),
        (_pin(mode="drive", cutoff=45), PLAYBOOK),
        (_pin(mode="distance", cutoff=300), None),
        (_pin(mode="walk", cutoff=20), None),
        (_pin(mode="drive", cutoff=7), None),
        (_pin(mode="drive", cutoff=20), None),
        (_pin(mode="drive", cutoff=30), OTHER_PLAYBOOK),
        (_pin(mode="drive", situation="ramadan_iftar", summer=True), None),
        ({"ring": [[0.0, 0.0]]}, None),
        ({"shape_id": "ab" * 32, "mode": "walk"}, None),
        ({}, None),
        (
            _pin(
                mode="drive",
                cutoff=10,
                situation=None,
                hour_key="hour_09",
                day_key="weekday",
            ),
            None,
        ),
        (_pin(mode="distance", hour_key=None), None),
    )

    def through_the_tool(tool, request, playbook) -> None:
        store = RecordingStore(PACKAGED, geometry_rows())
        routed: list[object] = []

        def route(*args: object) -> None:
            routed.append(args)

        result = tool(
            store,
            request,
            context(PACKAGED, routing=route, playbook_key=playbook),
        )
        assert result.status == INVALID_ARGUMENT
        assert store.calls == []
        assert routed == []

    for request, playbook in samples:
        through_the_tool(make_area, request, playbook)

    def reads_then_answers(store, request, ctx):
        store.fetch(ctx.inventory.lookup("make_area_grid_cells"), {})
        return make_area(store, request, ctx)

    with pytest.raises(AssertionError):
        through_the_tool(
            reads_then_answers,
            _pin(mode="drive", cutoff=45),
            None,
        )
