"""Complete GIS rows and calculations on the existing invented builders."""

from __future__ import annotations

import time
from collections.abc import Callable
from decimal import ROUND_DOWN, Decimal, localcontext
from typing import Any

import pytest
from custodian.tests.test_gis_layers import _grid, _point, _square
from custodian.tests.test_gis_paged import _entry, _LayerTransport, _qars_feature
from shapely import from_wkb

from eii_custodian.publicdata.fetch.transport import Response, TransportFault
from eii_custodian.publicdata.gis import layers as subject


def _any(value: object) -> Any:
    return value


def _refusal(
    call: Callable[[], object],
    expected: str,
    error_type: type[Exception] = subject.LayerError,
) -> None:
    with pytest.raises(error_type) as caught:
        call()
    assert str(caught.value) == expected
    if isinstance(caught.value, subject.LayerError):
        assert caught.value.detail == expected


def test_read_layer_success_and_retry() -> None:
    transport = _LayerTransport([_qars_feature()], max_count=2)
    attempts = 0

    def retry_once(url: str) -> Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TransportFault("unreachable", url)
        return transport(url)

    result = subject.read_layer(_entry("gis_address"), retry_once)
    assert result.failure is None
    assert len(result.layers) == 1
    layer = result.layers[0]
    assert (layer.layer_id, layer.layer_name, layer.geometry) == (0, "QARS", "point")
    assert layer.features == (_qars_feature(),)
    assert attempts == 4


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "not-a-string"), (12, "not-a-string"), ("12-AB/!", "99-aa/!"), ("", "")],
)
def test_pattern_shape(value: object, expected: str) -> None:
    assert subject.pattern_class(value) == expected


def test_rounding_does_not_inherit_decimal_context() -> None:
    with localcontext() as context:
        context.rounding = ROUND_DOWN
        assert subject.parse_guide_price("CommercialPrices", "1.015") == Decimal("1.02")
        parcel = {"attributes": {"SHAPE.AREA": 1.015}, "geometry": _square()}
        assert subject.parcel_rows([parcel])[0]["area_m2"] == Decimal("1.02")
        point = {
            "attributes": {"ENAME": "SYN POINT"},
            "geometry": _point(10.2500016, 20.5),
        }
        row = subject.poi_rows([point], _grid(10.25, 20.5))[0]
        assert row["lon"] == Decimal("10.250002")


def test_feature_keys_exclude_previous_key_and_number_duplicates() -> None:
    rows = [
        {"invented": "value", "feature_key": "invented-old"},
        {"invented": "value"},
        {"invented": "value", "feature_key": None},
    ]
    assert subject.assign_feature_keys(rows) == [
        {"invented": "value", "feature_key": "fea-024b-2248-68ae-a35a"},
        {"invented": "value", "feature_key": "fea-024b-2248-68ae-a35a_2"},
        {"invented": "value", "feature_key": "fea-024b-2248-68ae-a35a_3"},
    ]
    assert rows[0]["feature_key"] == "invented-old"


def test_land_price_refusal_keeps_field_name() -> None:
    _refusal(
        lambda: subject.land_price_rows(
            [{"attributes": {"DIST_NO": 3, "District_No": 3}}], "Invented2026"
        ),
        "ResidentialPrices: not-a-string",
    )


def test_address_optional_subtype() -> None:
    feature = _qars_feature()
    rows = subject.address_rows([feature], _grid(10.25, 20.5))
    assert rows[0]["building_subtype"] == "4"
    _any(feature["attributes"])["BUILDING_NO_SUBTYPE"] = None
    assert (
        subject.address_rows([feature], _grid(10.25, 20.5))[0]["building_subtype"]
        is None
    )


def test_parcel_dates_are_utc_even_with_local_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with monkeypatch.context() as changed:
        changed.setenv("TZ", "EST5")
        time.tzset()
        try:
            rows = subject.parcel_rows(
                [
                    {
                        "attributes": {
                            "SHAPE.AREA": 3,
                            "STARTDATE": 0,
                            "ENDDATE": 86400 * 1000,
                        },
                        "geometry": _square(),
                    }
                ]
            )
            assert rows[0]["start_date"] == "1970-01-01"
            assert rows[0]["end_date"] == "1970-01-02"
        finally:
            changed.undo()
            time.tzset()


def test_zoning_published_fields_and_geometry() -> None:
    result = subject.zoning_rows(
        [
            {
                "layer_name": "Khor_Wakra_Zoning",
                "features": [
                    {
                        "attributes": {
                            "ZONING_COD": "SYN-A",
                            "LU_ARB": "تجريبي",
                            "HEIGHTS": "SYN-H",
                        },
                        "geometry": _square(),
                    }
                ],
            }
        ]
    )[0]
    assert (
        result["permitted_uses"]
        == '{"LU_ARB": "تجريبي", "LU_ENG": null, "P_COM_OFF": null, "P_COM_SHOP": null, "P_RES_APA": null, "P_RES_HOT": null, "P_RES_VIL": null}'
    )
    assert result["height_rule"] == '{"HEIGHT": null, "HEIGHTS": "SYN-H"}'
    assert (
        result["setback_rule"]
        == '{"SET_NOW_FR": null, "SET_NOW_RE": null, "SET_NOW_S1": null, "SET_NOW_S2": null, "SET_W_FR": null, "SET_W_RE": null, "SET_W_S1": null, "SET_W_S2": null}'
    )
    assert from_wkb(result["geometry"]).wkt == "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"


def test_rail_names_and_geometry_for_every_kind() -> None:
    rows = subject.rail_rows(
        [
            {
                "layer_id": 2,
                "features": [
                    {
                        "attributes": {
                            "STATION_NAME_ENGLISH": "SYN STATION",
                            "STATION_NAME_ARABIC": "محطة تجريبية",
                        },
                        "geometry": _point(1, 2),
                    }
                ],
            },
            {
                "layer_id": 0,
                "features": [
                    {
                        "attributes": {"TRACK_NAME": "SYN TRACK"},
                        "geometry": {
                            "spatialReference": {"wkid": 4326},
                            "paths": [[[1, 2], [3, 4]], [[5, 6], [7, 8]]],
                        },
                    }
                ],
            },
            {"layer_id": 1, "features": [{"attributes": {}, "geometry": _square()}]},
        ]
    )
    assert [(row["feature_kind"], row["name_en"], row["name_ar"]) for row in rows] == [
        ("planned_station", "SYN STATION", "محطة تجريبية"),
        ("line", "SYN TRACK", None),
        ("protection_zone", None, None),
    ]
    assert [from_wkb(row["geometry"]).wkt for row in rows] == [
        "POINT (1 2)",
        "MULTILINESTRING ((1 2, 3 4), (5 6, 7 8))",
        "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
    ]


def test_health_names_match_their_kind_and_geometry() -> None:
    result = subject.health_rows(
        [
            {
                "layer_name": "SYN CENTRE",
                "geometry": "point",
                "features": [
                    {
                        "attributes": {
                            "HC_NAME": "SYN CENTRE",
                            "A_HC_NAME": "مركز تجريبي",
                        },
                        "geometry": _point(1, 2),
                    }
                ],
            },
            {
                "layer_name": "SYN CATCHMENT",
                "geometry": "polygon",
                "features": [
                    {
                        "attributes": {
                            "ENAME": "SYN CATCHMENT",
                            "ANAME": "نطاق تجريبي",
                        },
                        "geometry": _square(),
                    }
                ],
            },
        ]
    )
    assert [
        (
            row["feature_kind"],
            row["name_en"],
            row["name_ar"],
            from_wkb(row["geometry"]).geom_type,
        )
        for row in result.rows
    ] == [
        ("centre", "SYN CENTRE", "مركز تجريبي", "Point"),
        ("catchment", "SYN CATCHMENT", "نطاق تجريبي", "Polygon"),
    ]


def test_poi_coordinates_and_arabic() -> None:
    grid = _grid(10.25, 20.5)
    row = subject.poi_rows(
        [
            {
                "attributes": {"ENAME": "SYN SHOP", "ANAME": "متجر تجريبي"},
                "geometry": _point(10.25, 20.5),
            }
        ],
        grid,
    )[0]
    assert row["name_ar"] == "متجر تجريبي"
    assert row["lon"] == Decimal("10.250000")
    assert row["lat"] == Decimal("20.500000")
    assert row["cell"] == grid[0]["cell"]


def test_landmark_keys_and_duplicate_suffixes() -> None:
    feature = {
        "attributes": {"ENAME": "SYN MARK", "ANAME": "معلم تجريبي"},
        "geometry": _point(10.25, 20.5),
    }
    rows = subject.landmark_rows([feature, feature, feature], _grid(10.25, 20.5))
    assert [row["place_key"] for row in rows] == [
        "lm-ec8a-078b-f17a-27b5",
        "lm-ec8a-078b-f17a-27b5_2",
        "lm-ec8a-078b-f17a-27b5_3",
    ]


def test_pin_share_multiple_inside_and_unmatched_pin() -> None:
    parcels = [{"attributes": {"PIN": "SYN-PARCEL"}, "geometry": _square()}]
    addresses = [
        {"attributes": {"PIN": "SYN-PARCEL"}, "geometry": _point(0.2, 0.3)},
        {"attributes": {"PIN": "SYN-PARCEL"}, "geometry": _point(0, 0)},
        {"attributes": {"PIN": "SYN-UNMATCHED"}, "geometry": _point(0.2, 0.3)},
    ]
    share = subject.address_parcel_share(addresses, parcels)
    assert (share.inside, share.total, share.line) == (
        2,
        3,
        "address_points_inside_same_pin: 2/3",
    )


def test_canonical_nested_values() -> None:
    value = {
        "z": [Decimal("1E+3"), b"\xab\xcd", None, True, 2, 1.25],
        "a": "تجريبي",
        3: {"b": "SYN"},
    }
    expected = '{"3":{"b":"SYN"},"a":"تجريبي","z":["1000","abcd",null,true,2,1.25]}'
    assert subject._canonical(value) == expected.encode("utf-8")
    _refusal(
        lambda: subject.assign_feature_keys([{"invented": object()}]),
        "feature key value",
    )
