"""Invented pins. Paths the first survivor tests do not reach."""

from __future__ import annotations

import sys
import tempfile
import types
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest
from product.tests.make_area_support import _polygon_bytes

import h3
from eii_core.shapes import GEOMETRY_REFUSED, GeometryTextError, representative_point
from eii_product.store.protocol import QueryResult
from eii_product.tools.areas import INVALID_ARGUMENT
from eii_product.tools.make_area import (
    ArgumentError,
    MakeAreaContext,
    PinRequest,
    _coordinate,
    _decimal_number,
    _exact_finite_decimal,
    _frame,
    _ok,
    _pin_outline,
    _registered_ring,
    _resolve,
    _routing,
    _with_cell,
    decode_area,
    make_area,
    read_land,
    validate_request,
)
from eii_product.tools.routing import (
    ROUTING_TILES_UNAVAILABLE,
    _pairs_from_engine,
    _stored_number,
    _stored_pair,
)


def full_message(error: BaseException, expected: str) -> None:
    """Compare the whole refusal with a hand-written literal."""
    assert str(error) == expected


def test_an_integer_point_becomes_a_decimal() -> None:
    parsed = validate_request(
        {"mode": "distance", "cutoff": 250, "latitude": 1, "longitude": 2},
        None,
    )
    assert parsed.latitude == Decimal(1)
    assert parsed.longitude == Decimal(2)


def test_zero_keeps_a_positive_sign() -> None:
    assert _exact_finite_decimal(Fraction(0)).as_tuple().sign == 0


def test_a_decimal_coordinate_is_kept() -> None:
    assert _decimal_number(Decimal("1.5")) == Decimal("1.5")


def test_a_request_missing_only_the_mode_is_refused() -> None:
    with pytest.raises(ArgumentError) as caught:
        validate_request(
            {"cutoff": 250, "latitude": Decimal("1"), "longitude": Decimal("2")}, None
        )
    full_message(caught.value, INVALID_ARGUMENT)


class _TextSubclass(str):
    """A text subclass that compares equal to a known mode."""


def test_a_mode_of_a_text_subclass_is_refused() -> None:
    with pytest.raises(ArgumentError) as caught:
        validate_request(
            {
                "mode": _TextSubclass("distance"),
                "cutoff": 250,
                "latitude": Decimal("1"),
                "longitude": Decimal("2"),
            },
            None,
        )
    full_message(caught.value, INVALID_ARGUMENT)


def test_an_unknown_situation_is_refused() -> None:
    with pytest.raises(ArgumentError) as caught:
        validate_request(
            {
                "mode": "drive",
                "cutoff": 10,
                "latitude": Decimal("1"),
                "longitude": Decimal("2"),
                "situation": "nope",
                "summer": False,
            },
            None,
        )
    full_message(caught.value, INVALID_ARGUMENT)


def test_a_longitude_with_a_place_key_is_refused() -> None:
    with pytest.raises(ArgumentError) as caught:
        validate_request(
            {
                "mode": "distance",
                "cutoff": 250,
                "longitude": Decimal("2"),
                "place_key": "SYN-pin",
            },
            None,
        )
    full_message(caught.value, INVALID_ARGUMENT)


def test_a_non_text_place_key_is_refused() -> None:
    with pytest.raises(ArgumentError) as caught:
        validate_request(
            {"mode": "distance", "cutoff": 250, "place_key": 1},
            None,
        )
    full_message(caught.value, INVALID_ARGUMENT)


def test_a_non_text_shape_id_is_refused() -> None:
    with pytest.raises(ArgumentError) as caught:
        validate_request({"shape_id": 1}, None)
    full_message(caught.value, INVALID_ARGUMENT)


def test_distance_outline_is_a_circle_and_walk_uses_the_route() -> None:
    seen: list[tuple[object, ...]] = []

    def route(mode: str, minutes: int, latitude: Decimal, longitude: Decimal) -> tuple:
        seen.append((mode, minutes, latitude, longitude))
        return (
            (Decimal(0), Decimal(0)),
            (Decimal(0), Decimal(1)),
            (Decimal(1), Decimal(0)),
            (Decimal(0), Decimal(0)),
        )

    context = MakeAreaContext(
        "abcdef0123456789", "public_only", None, object(), object(), routing=route
    )
    pin = PinRequest("distance", 250, Decimal("1"), Decimal("2"), None, None)
    assert _pin_outline(pin, Decimal("1"), Decimal("2"), context) == {
        "type": "Circle",
        "coordinates": [Decimal("2"), Decimal("1")],
        "radius_m": 250,
    }
    walk = PinRequest("walk", 5, Decimal("1"), Decimal("2"), None, None)
    body = _pin_outline(walk, Decimal("1.5"), Decimal("2.5"), context)
    assert body["type"] == "Polygon"
    assert seen == [("walk", 5, Decimal("1.5"), Decimal("2.5"))]
    _with_cell(walk, Decimal("3"), Decimal("4"), 0, (), context)
    assert seen[1] == ("walk", 5, Decimal("3"), Decimal("4"))


def test_a_missing_tile_folder_is_refused() -> None:
    context = MakeAreaContext(
        "abcdef0123456789", "public_only", None, object(), object()
    )
    with pytest.raises(ArgumentError) as caught:
        _routing(context, "walk", 5, Decimal("1"), Decimal("2"))
    full_message(caught.value, INVALID_ARGUMENT)


class _Name:
    def __init__(self, name: str) -> None:
        self.name = name


class _Inventory:
    def __init__(self) -> None:
        self.names = (
            _Name("make_area_municipalities"),
            _Name("make_area_grid_cells"),
            _Name("make_area_gazetteer_point"),
        )

    def lookup(self, name: str) -> _Name:
        for item in self.names:
            if item.name == name:
                return item
        raise KeyError(name)


def test_a_blank_municipality_row_does_not_drop_the_next() -> None:
    triangle = ((0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (0.0, 0.0))
    text = _polygon_bytes((triangle,)).hex().upper()

    class Store:
        def fetch(self, query: object, params: object) -> QueryResult:
            return QueryResult(("id", "geometry"), ((1, None), (2, text)))

    polygons = read_land(Store(), _Inventory())
    assert len(polygons) == 1
    assert polygons[0][0] == ((0, 0), (0, 1), (1, 0), (0, 0))


def test_a_non_text_geometry_uses_the_full_refusal() -> None:
    class Store:
        def fetch(self, query: object, params: object) -> QueryResult:
            return QueryResult(("id", "geometry"), ((1, 5),))

    with pytest.raises(GeometryTextError) as caught:
        read_land(Store(), _Inventory())
    full_message(caught.value, GEOMETRY_REFUSED)


def test_a_grid_row_must_be_two_integers() -> None:
    class Store:
        def fetch(self, query: object, params: object) -> QueryResult:
            return QueryResult(("cell", "resolution"), ((1, "8"),))

    with pytest.raises(ArgumentError) as caught:
        _frame(Store(), _Inventory())
    full_message(caught.value, INVALID_ARGUMENT)


def test_a_pin_without_a_latitude_is_refused() -> None:
    pin = PinRequest("distance", 250, None, Decimal("2"), None, None)
    context = MakeAreaContext(
        "abcdef0123456789", "public_only", None, object(), object()
    )
    with pytest.raises(ArgumentError) as caught:
        _resolve(object(), pin, context)
    full_message(caught.value, INVALID_ARGUMENT)


def test_a_shape_report_is_omitted_when_the_flag_is_off() -> None:
    context = MakeAreaContext(
        "abcdef0123456789", "public_only", None, object(), object()
    )
    result = _ok(
        context,
        "polygon",
        None,
        None,
        "ab" * 32,
        None,
        4,
        {"type": "Polygon", "coordinates": []},
        (4,),
        False,
    )
    assert result.payload is not None
    assert result.payload["snap_report"] is None
    assert result.payload["area_id"] == f"ma1/abcdef0123456789/polygon/{'ab' * 32}"


def test_staffing_reaches_the_store() -> None:
    class Store:
        def fetch(self, query: object, params: object) -> QueryResult:
            raise RuntimeError("fetched")

    context = MakeAreaContext(
        "abcdef0123456789", "public_only", "staffing_and_pay", _Inventory(), object()
    )
    with pytest.raises(RuntimeError, match="fetched"):
        make_area(
            Store(),
            {
                "mode": "drive",
                "cutoff": 20,
                "latitude": Decimal("1"),
                "longitude": Decimal("2"),
                "situation": "weekday_lunch",
                "summer": False,
            },
            context,
        )


def _as_object(value: object) -> object:
    return value


def test_refused_numbers_and_rings_use_the_full_text() -> None:
    with pytest.raises(ArgumentError) as number:
        _decimal_number(_as_object(1))
    full_message(number.value, INVALID_ARGUMENT)
    with pytest.raises(ArgumentError) as kind:
        _exact_finite_decimal(_as_object(1))
    full_message(kind.value, INVALID_ARGUMENT)
    with pytest.raises(ArgumentError) as third:
        _exact_finite_decimal(Fraction(1, 3))
    full_message(third.value, INVALID_ARGUMENT)
    with pytest.raises(ArgumentError) as ring:
        _registered_ring(((1, 1), (2, 2)))
    full_message(ring.value, INVALID_ARGUMENT)


def test_a_missing_place_is_refused_and_a_found_place_keeps_lat_then_lon() -> None:
    context = MakeAreaContext(
        "abcdef0123456789", "public_only", None, _Inventory(), object()
    )
    pin = PinRequest("distance", 250, None, None, "SYN-pin", None)

    class Empty:
        def fetch(self, query: object, params: object) -> QueryResult:
            return QueryResult(("place_key", "longitude", "latitude"), ())

    with pytest.raises(ArgumentError) as missing:
        _resolve(Empty(), pin, context)
    full_message(missing.value, INVALID_ARGUMENT)

    class Found:
        def fetch(self, query: object, params: object) -> QueryResult:
            return QueryResult(
                ("place_key", "longitude", "latitude"),
                (("SYN-pin", Decimal("2"), Decimal("1")),),
            )

    assert _resolve(Found(), pin, context) == (Decimal("1.000000"), Decimal("2.000000"))


def test_a_shape_inside_the_land_keeps_its_stored_cell() -> None:
    ring = (
        (Decimal("0.2"), Decimal("0.2")),
        (Decimal("0.2"), Decimal("0.8")),
        (Decimal("0.8"), Decimal("0.2")),
        (Decimal("0.2"), Decimal("0.2")),
    )
    square = (
        (0.0, 0.0),
        (0.0, 2.0),
        (2.0, 2.0),
        (2.0, 0.0),
        (0.0, 0.0),
    )
    land = _polygon_bytes((square,)).hex().upper()
    centre = representative_point(ring)
    cell = h3.str_to_int(h3.latlng_to_cell(float(centre[0]), float(centre[1]), 9))

    class Shapes:
        def find(self, shape_id: str) -> object:
            from eii_product.tools.make_area import RegisteredShape

            return RegisteredShape(ring)

    class Store:
        def fetch(self, query: object, params: object) -> QueryResult:
            if query.name == "make_area_municipalities":
                return QueryResult(("id", "geometry"), ((1, land),))
            return QueryResult(("cell", "resolution"), ((cell, 9),))

    context = MakeAreaContext(
        "abcdef0123456789", "public_only", None, _Inventory(), Shapes()
    )
    result = make_area(Store(), {"shape_id": "ab" * 32}, context)
    assert result.status == "OK"
    assert result.payload is not None
    assert result.payload["record"]["anchor_cell"] == str(cell)
    assert result.payload["record"]["shape"] == "polygon"
    assert result.payload["snap_report"] is not None


def test_outline_receives_the_drive_arguments() -> None:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)
        (path / "config.json").write_text("{}", encoding="utf-8")
        seen: list[dict[str, object]] = []

        class Actor:
            def __init__(self, config: str) -> None:
                assert config == str(path / "config.json")

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
            context = MakeAreaContext(
                "abcdef0123456789",
                "public_only",
                None,
                object(),
                object(),
                tile_folder=path,
            )
            ring = _routing(context, "drive", 10, Decimal("1.5"), Decimal("2.5"))
        finally:
            if previous is None:
                sys.modules.pop("valhalla", None)
            else:
                sys.modules["valhalla"] = previous
    assert ring[0] == (Fraction(0), Fraction(0))
    assert seen[0]["costing"] == "auto"
    assert seen[0]["contours"] == [{"time": 10}]
    assert seen[0]["locations"] == [{"lat": 1.5, "lon": 2.5}]


def test_a_partial_drive_form_and_a_non_bool_summer_are_refused() -> None:
    point = {
        "mode": "drive",
        "cutoff": 10,
        "latitude": Decimal("1"),
        "longitude": Decimal("1"),
    }
    with pytest.raises(ArgumentError) as partial:
        validate_request({**point, "situation": "weekday_lunch"}, None)
    full_message(partial.value, INVALID_ARGUMENT)
    with pytest.raises(ArgumentError) as summer:
        validate_request({**point, "situation": "weekday_lunch", "summer": 1}, None)
    full_message(summer.value, INVALID_ARGUMENT)


def test_a_non_finite_decimal_and_a_foreign_coordinate_are_refused() -> None:
    with pytest.raises(ArgumentError) as infinite:
        _coordinate(Decimal("NaN"))
    full_message(infinite.value, INVALID_ARGUMENT)
    with pytest.raises(ArgumentError) as foreign:
        _coordinate(("nope",))
    full_message(foreign.value, INVALID_ARGUMENT)


def test_a_signed_zero_identifier_does_not_match_the_rebuilt_one() -> None:
    square = ((-1.0, -1.0), (-1.0, 2.0), (2.0, 2.0), (2.0, -1.0), (-1.0, -1.0))
    land = _polygon_bytes((square,)).hex().upper()

    class Store:
        def fetch(self, query: object, params: object) -> QueryResult:
            if query.name == "make_area_municipalities":
                return QueryResult(("id", "geometry"), ((1, land),))
            return QueryResult(("cell", "resolution"), ())

    context = MakeAreaContext(
        "abcdef0123456789", "public_only", None, _Inventory(), object()
    )
    area_id = "ma1/abcdef0123456789/distance/250/none/-0.000000/1.000000"
    result = decode_area(Store(), area_id, context)
    assert result.status == "INVALID_ARGUMENT"
    assert result.reason is None
    assert result.release_id == "abcdef0123456789"


def test_short_engine_rows_and_a_non_finite_stored_decimal_are_refused() -> None:
    answer = {
        "features": [
            {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1.0, 2.0, 3.0]]],
                }
            }
        ]
    }
    with pytest.raises(ValueError) as short:
        _pairs_from_engine(answer)
    full_message(short.value, ROUTING_TILES_UNAVAILABLE)
    with pytest.raises(TypeError) as foreign:
        _stored_pair(1)
    full_message(foreign.value, ROUTING_TILES_UNAVAILABLE)
    with pytest.raises(ValueError) as infinite:
        _stored_number(Decimal("NaN"))
    full_message(infinite.value, ROUTING_TILES_UNAVAILABLE)
