"""Invented pins. Routing refusals, registry rows and request checks."""

from __future__ import annotations

import sys
import tempfile
import types
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from eii_product.tools.areas import INVALID_ARGUMENT
from eii_product.tools.make_area import (
    PUBLIC_ONLY,
    RELEASE_MODE,
    ArgumentError,
    DriveOptions,
    MakeAreaContext,
    MakeAreaResult,
    _decimal,
    _encoded_cell_matches,
    _exact_finite_decimal,
    _floats,
    _pair,
    canonical_payload,
    decode_area,
    make_area,
    validate_before_read,
    validate_request,
)
from eii_product.tools.registry import _placeholder, parity_cases
from eii_product.tools.routing import (
    ROUTING_TILES_UNAVAILABLE,
    RoutingTilesUnavailable,
    _as_dict,
    _as_list,
    _coordinate_pairs,
    _engine_number,
    _pairs_from_engine,
    _ready,
    _stored_number,
    accepted_ring,
    outline,
)

_SHAPE = "ab" * 32
_REFUSED = ROUTING_TILES_UNAVAILABLE
_RING = (
    (Fraction(0), Fraction(0)),
    (Fraction(0), Fraction(1)),
    (Fraction(1), Fraction(0)),
    (Fraction(0), Fraction(0)),
)


def full_message(error: BaseException, expected: str) -> None:
    """Compare the whole refusal with a hand-written literal."""
    assert str(error) == expected


def _square() -> list[list[Decimal]]:
    return [
        [Decimal(0), Decimal(0)],
        [Decimal(0), Decimal(1)],
        [Decimal(1), Decimal(0)],
        [Decimal(0), Decimal(0)],
    ]


def test_parity_cases_keep_the_drive_pin_and_the_shape() -> None:
    cases = parity_cases(_SHAPE)
    assert cases[1].inputs == (
        ("place_key", "SYN-pin"),
        ("mode", "drive"),
        ("cutoff", 10),
    )
    assert cases[2].inputs == (("shape_id", _SHAPE),)
    assert cases[0].inputs[1] == ("mode", "walk")


def test_the_placeholder_copies_the_status_and_no_facts() -> None:
    class Store:
        engine = "engine-a"
        release_id = "abcdef0123456789"

    result = MakeAreaResult("make_area", "OK", None, "abcdef0123456789", None)
    held = _placeholder(Store(), result)
    assert held.engine == "engine-a"
    assert held.call_id == "make_area"
    assert held.duration_ms == 0
    assert held.tool == "make_area"
    assert held.status == "OK"
    assert held.release_id == "abcdef0123456789"
    assert held.facts == ()


def test_a_stored_square_is_the_counterclockwise_ring() -> None:
    assert accepted_ring(_square()) == _RING


def test_routing_refusals_use_the_full_text() -> None:
    with pytest.raises(RoutingTilesUnavailable) as bad_ring:
        accepted_ring("nope")
    full_message(bad_ring.value, _REFUSED)
    with pytest.raises(TypeError) as kind:
        _coordinate_pairs(1)
    full_message(kind.value, _REFUSED)
    with pytest.raises(TypeError) as flag:
        _engine_number(True)
    full_message(flag.value, _REFUSED)
    with pytest.raises(ValueError) as infinite:
        _engine_number(float("inf"))
    full_message(infinite.value, _REFUSED)
    _engine_number(1.5)
    _engine_number(1)
    with pytest.raises(TypeError) as engine_text:
        _engine_number("x")
    full_message(engine_text.value, _REFUSED)
    with pytest.raises(ValueError) as short_row:
        _coordinate_pairs([[1, 2, 3]])
    full_message(short_row.value, _REFUSED)
    with pytest.raises(TypeError) as stored_flag:
        _stored_number(True)
    full_message(stored_flag.value, _REFUSED)
    with pytest.raises(ValueError) as stored_infinite:
        _stored_number(float("inf"))
    full_message(stored_infinite.value, _REFUSED)
    with pytest.raises(TypeError) as stored_text:
        _stored_number("x")
    full_message(stored_text.value, _REFUSED)
    with pytest.raises(TypeError) as fraction_miss:
        _stored_number(object())
    full_message(fraction_miss.value, _REFUSED)
    _stored_number(Fraction(1, 2))
    _stored_number(1)
    _stored_number(1.5)
    with pytest.raises(KeyError) as missing:
        _pairs_from_engine({})
    full_message(missing.value, "'routing tiles unavailable'")
    with pytest.raises(KeyError) as no_geometry:
        _pairs_from_engine({"features": [{}]})
    full_message(no_geometry.value, "'routing tiles unavailable'")
    with pytest.raises(KeyError) as no_coordinates:
        _pairs_from_engine({"features": [{"geometry": {"type": "Polygon"}}]})
    full_message(no_coordinates.value, "'routing tiles unavailable'")
    with pytest.raises(ValueError) as empty:
        _pairs_from_engine({"features": []})
    full_message(empty.value, _REFUSED)
    with pytest.raises(ValueError) as kind_name:
        _pairs_from_engine(
            {"features": [{"geometry": {"type": "Point", "coordinates": []}}]}
        )
    full_message(kind_name.value, _REFUSED)
    with pytest.raises(ValueError) as holes:
        _pairs_from_engine(
            {
                "features": [
                    {
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [1, 0], [0, 1], [0, 0]], []],
                        }
                    }
                ]
            }
        )
    full_message(holes.value, _REFUSED)
    with pytest.raises(TypeError) as row:
        _pairs_from_engine(
            {
                "features": [
                    {
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[(0, 0), (1, 0), (0, 1), (0, 0)]],
                        }
                    }
                ]
            }
        )
    full_message(row.value, _REFUSED)
    with pytest.raises(TypeError) as not_list:
        _as_list({})
    full_message(not_list.value, _REFUSED)
    with pytest.raises(TypeError) as not_dict:
        _as_dict([])
    full_message(not_dict.value, _REFUSED)


def test_an_unreadable_folder_is_not_ready() -> None:
    original = Path.is_dir

    def boom(self: Path) -> bool:
        raise OSError("down")

    Path.is_dir = boom
    try:
        assert _ready(Path("invented-folder")) is False
    finally:
        Path.is_dir = original


def test_a_folder_without_config_is_not_ready() -> None:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        assert _ready(path) is False
        (path / "config.json").write_text("{}", encoding="utf-8")
        assert _ready(path) is True


def test_drive_asks_for_auto_and_walk_asks_for_pedestrian() -> None:
    with tempfile.TemporaryDirectory() as folder:
        _drive_and_walk(Path(folder))


def _drive_and_walk(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    seen: list[dict[str, object]] = []

    class Actor:
        def __init__(self, path: str) -> None:
            assert path == str(tmp_path / "config.json")

        def isochrone(self, request: dict[str, object]) -> dict[str, object]:
            seen.append(request)
            return {
                "features": [
                    {
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]
                            ],
                        }
                    }
                ]
            }

    module = types.ModuleType("valhalla")
    module.Actor = Actor
    previous = sys.modules.get("valhalla")
    sys.modules["valhalla"] = module
    try:
        assert outline(tmp_path, "drive", 10, 1.0, 2.0) == (
            (0.0, 0.0),
            (0.0, 1.0),
            (1.0, 0.0),
            (0.0, 0.0),
        )
        assert outline(tmp_path, "walk", 5, 1.0, 2.0) == (
            (0.0, 0.0),
            (0.0, 1.0),
            (1.0, 0.0),
            (0.0, 0.0),
        )

        class Down:
            def __init__(self, path: str) -> None:
                raise ValueError(path)

        module.Actor = Down
        with pytest.raises(RoutingTilesUnavailable) as caught:
            outline(tmp_path, "walk", 5, 1.0, 2.0)
        full_message(caught.value, _REFUSED)
    finally:
        if previous is None:
            sys.modules.pop("valhalla", None)
        else:
            sys.modules["valhalla"] = previous
    assert seen[0]["costing"] == "auto"
    assert seen[0]["costing_options"] == {"auto": {"speed_types": []}}
    assert seen[1]["costing"] == "pedestrian"
    assert seen[1]["costing_options"] == {"pedestrian": {"speed_types": []}}


def test_a_distance_pin_keeps_the_cutoff_and_the_point() -> None:
    parsed = validate_request(
        {
            "mode": "distance",
            "cutoff": 250,
            "latitude": Decimal("-90"),
            "longitude": Decimal("180"),
        },
        None,
    )
    assert parsed.mode == "distance"
    assert parsed.cutoff == 250
    assert parsed.latitude == Decimal("-90")
    assert parsed.longitude == Decimal("180")
    assert parsed.place_key is None
    assert parsed.drive is None


def test_edges_of_the_coordinate_box_are_accepted() -> None:
    parsed = validate_request(
        {
            "mode": "walk",
            "cutoff": 5,
            "latitude": Decimal("90"),
            "longitude": Decimal("-180"),
        },
        None,
    )
    assert parsed.latitude == Decimal("90")
    assert parsed.longitude == Decimal("-180")


def test_a_boolean_coordinate_and_a_past_limit_are_refused() -> None:
    with pytest.raises(ArgumentError) as flag:
        validate_request(
            {"mode": "distance", "cutoff": 250, "latitude": True, "longitude": 0},
            None,
        )
    full_message(flag.value, INVALID_ARGUMENT)
    with pytest.raises(ArgumentError) as over:
        validate_request(
            {
                "mode": "drive",
                "cutoff": 31,
                "latitude": Decimal("1"),
                "longitude": Decimal("2"),
            },
            None,
        )
    full_message(over.value, INVALID_ARGUMENT)


def test_staffing_minutes_need_the_playbook_key() -> None:
    request = {
        "mode": "drive",
        "cutoff": 20,
        "latitude": Decimal("1"),
        "longitude": Decimal("2"),
        "situation": "weekday_lunch",
        "summer": False,
    }
    parsed = validate_before_read(request, "staffing_and_pay", object(), object())
    assert parsed.cutoff == 20
    assert parsed.drive == DriveOptions("weekday_lunch", False, None, None)


def test_a_clock_pin_keeps_both_keys() -> None:
    parsed = validate_request(
        {
            "mode": "drive",
            "cutoff": 10,
            "place_key": "SYN-pin",
            "hour_key": "h1",
            "day_key": "d1",
        },
        None,
        frozenset({"h1"}),
        frozenset({"d1"}),
    )
    assert parsed.drive == DriveOptions(None, None, "h1", "d1")
    assert parsed.place_key == "SYN-pin"
    assert DriveOptions(None, None, "h1", None).keyed() is True
    again = validate_before_read(
        {
            "mode": "drive",
            "cutoff": 10,
            "place_key": "SYN-pin",
            "hour_key": "h1",
            "day_key": "d1",
        },
        None,
        object(),
        object(),
        frozenset({"h1"}),
        frozenset({"d1"}),
    )
    assert again.drive == DriveOptions(None, None, "h1", "d1")


def test_a_point_and_a_place_key_together_are_refused() -> None:
    with pytest.raises(ArgumentError) as caught:
        validate_request(
            {
                "mode": "distance",
                "cutoff": 250,
                "latitude": Decimal("1"),
                "place_key": "SYN-pin",
            },
            None,
        )
    full_message(caught.value, INVALID_ARGUMENT)


def test_a_private_release_names_the_full_reason() -> None:
    context = MakeAreaContext("abcdef0123456789", "private", None, object(), object())
    result = make_area(object(), {}, context)
    decoded = decode_area(object(), "ma1/x", context)
    assert result.tool == "make_area"
    assert result.status == RELEASE_MODE
    assert result.reason == "release_not_public_only"
    assert result.payload is None
    assert decoded.status == RELEASE_MODE
    assert decoded.reason == "release_not_public_only"
    assert (
        canonical_payload(result)
        == b'{"payload":null,"reason":"release_not_public_only","status":"RELEASE_MODE"}'
    )


def test_a_geometry_key_is_invalid_before_a_read() -> None:
    context = MakeAreaContext("abcdef0123456789", PUBLIC_ONLY, None, object(), object())
    result = make_area(object(), {"ring": 1}, context)
    assert result.status == INVALID_ARGUMENT
    assert result.reason is None
    assert result.release_id == "abcdef0123456789"


def test_exact_decimals_and_pairs_keep_the_worked_values() -> None:
    assert _exact_finite_decimal(Fraction(1, 20)) == Decimal("0.05")
    assert _exact_finite_decimal(Fraction(1)) == Decimal("1")
    assert _exact_finite_decimal(Fraction(-1, 2)) == Decimal("-0.5")
    assert _floats((Fraction(1), Fraction(2))) == (1.0, 2.0)
    assert _decimal(2) == Decimal(2)
    assert _pair(Decimal("1"), Decimal("2")) == (Decimal("1"), Decimal("2"))
    with pytest.raises(ArgumentError) as text:
        _decimal("1")
    full_message(text.value, INVALID_ARGUMENT)
    with pytest.raises(ArgumentError) as missing:
        _pair(None, Decimal("2"))
    full_message(missing.value, INVALID_ARGUMENT)


def test_an_encoded_cell_must_equal_the_anchor_text() -> None:
    assert _encoded_cell_matches(None, {"record": {"anchor_cell": None}}) is True
    assert _encoded_cell_matches(4, {"record": {"anchor_cell": "4"}}) is True
    assert _encoded_cell_matches(5, {"record": {"anchor_cell": "4"}}) is False
    assert _encoded_cell_matches(1, {"record": []}) is False
    assert _encoded_cell_matches(1, {"record": {"anchor_cell": 1}}) is False
