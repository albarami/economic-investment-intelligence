"""Malformed invented GIS inputs, with complete refusal messages."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from custodian.tests.test_gis_layers import _grid, _point, _square
from custodian.tests.test_gis_layers_survivors import _any, _refusal
from custodian.tests.test_gis_paged import _qars_feature

from eii_custodian.publicdata.gis import layers as subject


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: subject.zoning_rows([{"layer_name": None}]), "layer name"),
        (
            lambda: subject.zoning_rows(
                [{"layer_name": "Zoning", "features": [{"attributes": {"ZONING": 3}}]}]
            ),
            "zoning_code",
        ),
        (lambda: subject.rail_rows([{"layer_id": True}]), "rail layer"),
        (lambda: subject.rail_rows([{"layer_id": "2"}]), "rail layer"),
        (lambda: subject.rail_rows([{"layer_id": 3}]), "rail layer"),
        (
            lambda: subject.health_rows(
                [{"layer_name": None, "geometry": "point", "features": []}]
            ),
            "health layer",
        ),
        (
            lambda: subject.health_rows(
                [{"layer_name": "SYN", "geometry": "line", "features": []}]
            ),
            "health layer",
        ),
        (lambda: subject.land_price_rows([], "SYN"), "service name year"),
        (
            lambda: subject.land_price_rows(
                [{"attributes": {"DIST_NO": True, "District_No": True}}], "SYN2026"
            ),
            "district numbers differ",
        ),
        (
            lambda: subject.land_price_rows(
                [{"attributes": {"DIST_NO": "3", "District_No": "3"}}], "SYN2026"
            ),
            "district numbers differ",
        ),
        (lambda: subject.poi_rows([{"geometry": _point(1, 2)}], []), "attributes"),
        (lambda: subject.poi_rows([{"attributes": {3: "SYN"}}], []), "attributes"),
        (lambda: subject.poi_rows([{"attributes": {}}], []), "geometry"),
        (
            lambda: subject.poi_rows([{"attributes": {}, "geometry": {3: "SYN"}}], []),
            "geometry",
        ),
        (
            lambda: subject.zoning_rows([{"layer_name": "Zoning", "features": None}]),
            "features",
        ),
        (
            lambda: subject.zoning_rows([{"layer_name": "Zoning", "features": [None]}]),
            "features",
        ),
        (
            lambda: subject.zoning_rows(
                [{"layer_name": "Zoning", "features": [{3: "SYN"}]}]
            ),
            "features",
        ),
    ],
    ids=[
        "zoning-name",
        "zoning-code",
        "rail-bool",
        "rail-string",
        "rail-unknown",
        "health-name",
        "health-kind",
        "year",
        "district-bool",
        "district-string",
        "attributes-missing",
        "attributes-key",
        "geometry-missing",
        "geometry-key",
        "features-missing",
        "feature-item",
        "feature-key",
    ],
)
def test_row_refusals(call: Callable[[], object], message: str) -> None:
    _refusal(call, message)


@pytest.mark.parametrize("value", [True, -1, 1.5, "0"])
def test_date_refusal(value: object) -> None:
    feature = {
        "attributes": {"SHAPE.AREA": 1, "STARTDATE": value},
        "geometry": _square(),
    }
    _refusal(lambda: subject.parcel_rows([feature]), "date")


@pytest.mark.parametrize("value", [True, "7", 7.5, None])
def test_address_number_refusal(value: object) -> None:
    feature = _qars_feature()
    _any(feature["attributes"])["ZONE_NO"] = value
    _refusal(lambda: subject.address_rows([feature], _grid(10.25, 20.5)), "number")


@pytest.mark.parametrize("value", [True, "1", None])
def test_area_refusal(value: object) -> None:
    feature = {"attributes": {"SHAPE.AREA": value}, "geometry": _square()}
    _refusal(lambda: subject.parcel_rows([feature]), "area")


@pytest.mark.parametrize("value", [None, "", 3])
def test_poi_name_refusal(value: object) -> None:
    feature = {"attributes": {"ENAME": value}, "geometry": _point(10.25, 20.5)}
    _refusal(lambda: subject.poi_rows([feature], _grid(10.25, 20.5)), "text")


@pytest.mark.parametrize("value", [True, "1", None])
def test_coordinate_refusal(value: object) -> None:
    geometry = _point(1, 2)
    geometry["x"] = value
    _refusal(lambda: subject.geometry_shape(geometry, "point"), "coordinate")
    _refusal(
        lambda: subject.poi_rows(
            [{"attributes": {"ENAME": "SYN"}, "geometry": geometry}], []
        ),
        "coordinate",
    )


@pytest.mark.parametrize(
    "reference",
    [None, {}, {"wkid": 2932}, {"wkid": True}, {"wkid": 4326.0}, {"wkid": "4326"}],
)
def test_spatial_reference_refusal(reference: object) -> None:
    geometry = _point(1, 2)
    geometry["spatialReference"] = reference
    _refusal(lambda: subject.geometry_shape(geometry, "point"), "spatial_reference")
    _refusal(
        lambda: subject.poi_rows(
            [{"attributes": {"ENAME": "SYN"}, "geometry": geometry}], []
        ),
        "spatial_reference",
    )


@pytest.mark.parametrize("grid", [[], [{"cell": True}], [{"cell": "SYN"}], [{}]])
def test_cell_refusal(grid: list[dict[str, object]]) -> None:
    feature = {"attributes": {"ENAME": "SYN"}, "geometry": _point(10.25, 20.5)}
    _refusal(lambda: subject.poi_rows([feature], grid), "cell")


@pytest.mark.parametrize(
    "paths",
    [None, [], "SYN", [None], [[]], [[[1, 2]]], [["SYN", [3, 4]]], [[[1], [3, 4]]]],
)
def test_paths_and_rings_refusal(paths: object) -> None:
    geometry = {"spatialReference": {"wkid": 4326}, "paths": paths}
    _refusal(lambda: subject.geometry_shape(geometry, "line"), "geometry")


def test_unknown_geometry_kind() -> None:
    _refusal(lambda: subject.geometry_shape(_point(1, 2), "invented"), "geometry")


def test_asymmetric_single_line_coordinates() -> None:
    geometry = {"spatialReference": {"wkid": 4326}, "paths": [[[1, 2], [3, 4]]]}
    assert subject.geometry_shape(geometry, "line").wkt == "LINESTRING (1 2, 3 4)"


@pytest.mark.parametrize(
    "body", [b"\xff", b"{", b"[]", b"{}", b'{"layers":null}', b'{"layers":[null]}']
)
def test_parse_body_refusals(body: bytes) -> None:
    # prepare() constructs the envelope after _paged_declared validates responses;
    # malformed envelopes cannot arrive there through transport. Exercise its parser directly.
    _refusal(lambda: subject._parse_body(body), "layer body")


@pytest.mark.parametrize(
    ("field", "value"),
    [("layer_id", True), ("layer_id", "0"), ("layer_name", None), ("geometry", None)],
)
def test_parse_body_field_refusals(field: str, value: object) -> None:
    layer = {"layer_id": 0, "layer_name": "SYN", "geometry": "point", "features": []}
    layer[field] = value
    body = json.dumps({"layers": [layer]}).encode()
    _refusal(lambda: subject._parse_body(body), "layer body")


def test_parse_body_preserves_unicode_and_empty_layers() -> None:
    assert subject._parse_body(b'{"layers":[]}') == ()
    body = '{"layers":[{"layer_id":3,"layer_name":"تجريبي","geometry":"point","features":[{"invented":1}]}]}'
    assert subject._parse_body(body.encode()) == (
        subject.ParsedLayer(3, "تجريبي", "point", ({"invented": 1},)),
    )


@pytest.mark.parametrize("cell", [True, "SYN"])
def test_frame_grid_rejects_before_ownership(cell: object) -> None:
    # _cell also raises LayerError("cell") when the ownership lookup finds no
    # match, hiding a weakened _frame_grid check from the public row caller.
    _refusal(lambda: subject._frame_grid([{"cell": cell}]), "cell")


def test_oversized_date_refusal_is_not_float_division() -> None:
    feature = {
        "attributes": {"SHAPE.AREA": 1, "STARTDATE": 10**400},
        "geometry": _square(),
    }
    _refusal(
        lambda: subject.parcel_rows([feature]),
        "timestamp out of range for platform time_t",
        OverflowError,
    )
