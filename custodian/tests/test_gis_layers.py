"""Release rows of the GIS centre layers. Invented features only.

Registry rows are part R and are not in this workspace. Tests build entries
and hand-made features. Field names are the kept lists under B2.
"""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from custodian.tests.repository_root import repository_root

import h3
from eii_custodian.publicdata.additions.common import Coverage
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.report import coverage_count_line, pin_share_line
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.gis.fields import declaration_for
from eii_custodian.publicdata.gis.layers import (
    CONTEXT_ROLE,
    LayerError,
    address_parcel_share,
    address_rows,
    assign_feature_keys,
    context_tables,
    health_rows,
    land_price_rows,
    landmark_rows,
    parcel_rows,
    parse_guide_price,
    pattern_class,
    poi_rows,
    rail_rows,
    read_layer,
    require_release_columns,
    zoning_rows,
)

_ROOT = repository_root(Path(__file__))
_GIS = "https://services.gisqatar.org.qa/server/rest/services/Vector/QARS/MapServer"
_SURVEY_MS = 1579046400000
_INVENTED_AS_OF = "2026-11-17"

# The registry column vocabulary for each declared service field type.
_REGISTRY_KIND = {
    "esriFieldTypeString": "string",
    "esriFieldTypeSmallInteger": "integer",
    "esriFieldTypeInteger": "integer",
    "esriFieldTypeDouble": "number",
    "esriFieldTypeDate": "integer",
    "esriFieldTypeGeometry": "object",
}


def test_gis_registry_rows_match_the_reviewed_fields() -> None:
    """J21: every gis_ row's columns, service path and layer equal the reviewed file."""
    entries = {
        entry.key: entry for entry in load_registry() if entry.key.startswith("gis_")
    }
    for key, entry in entries.items():
        declaration = declaration_for(entry.source_id)
        if declaration is None:
            assert entry.skip_reason or entry.kind == "citation_only", key
            continue
        layer = declaration.layers[0]
        assert urlsplit(entry.url).path == layer.service_path, key
        assert entry.layer == layer.layer_id, key
        assert [name for name, _ in entry.columns] == [
            field.name for field in layer.fields
        ], key
        assert [kind for _, kind in entry.columns] == [
            _REGISTRY_KIND[field.esri_type] for field in layer.fields
        ], key


def test_planted_pin_column_in_a_release_table_fails() -> None:
    with pytest_raises_layer("PIN"):
        require_release_columns(
            [{"feature_key": "fea-abcd-efab-cdef-abcd", "PIN": 1001}]
        )


def test_guide_price_parses_a_plain_number_and_refuses_any_other() -> None:
    assert parse_guide_price("ResidentialPrices", "1,250.50") == Decimal("1250.50")
    assert parse_guide_price("CommercialPrices", "99") == Decimal("99.00")
    assert parse_guide_price("ResidentialCityCenter", "12.5") == Decimal("12.50")
    assert parse_guide_price("CommercialPrices", "1.015") == Decimal("1.02")
    try:
        parse_guide_price("ResidentialPriceVillas", "12a")
    except LayerError as error:
        assert "ResidentialPriceVillas" in str(error)
        assert str(error).endswith("99a")
        assert "12" not in str(error)
    else:
        raise AssertionError("bad price stored")
    try:
        parse_guide_price("ResidentialPrices", "rent")
    except LayerError as error:
        assert "ResidentialPrices" in str(error)
        assert pattern_class("rent") in str(error)
        assert "rent" not in str(error).casefold()
    else:
        raise AssertionError("rent label stored")


def test_land_price_rows_use_field_names_and_per_ft2() -> None:
    feature = {
        "attributes": {
            "DIST_NO": 14,
            "District_No": 14,
            "ANAME": "حي تجريبي",
            "ENAME": "SYN DISTRICT",
            "ResidentialPrices": "1,000",
            "ResidentialCityCenter": "2,000.50",
            "ResidentialPriceFlats": "3,000",
            "ResidentialPriceVillas": "4,000",
            "CommercialPrices": "5,000",
        },
        "geometry": _square(),
    }
    rows = land_price_rows([feature], "LandPricing2026", as_of=_INVENTED_AS_OF)
    assert {row["use_category"] for row in rows} == {
        "ResidentialPrices",
        "ResidentialCityCenter",
        "ResidentialPriceFlats",
        "ResidentialPriceVillas",
        "CommercialPrices",
    }
    assert {row["price_basis"] for row in rows} == {"per_ft2"}
    assert {row["period"] for row in rows} == {"2026"}
    assert {row["district_key"] for row in rows} == {"14"}
    villas = next(
        row for row in rows if row["use_category"] == "ResidentialPriceVillas"
    )
    prices = next(row for row in rows if row["use_category"] == "ResidentialPrices")
    assert villas["guide_price"] == Decimal("4000.00")
    assert prices["guide_price"] == Decimal("1000.00")
    assert "rent" not in json.dumps(rows, default=str).casefold()
    require_release_columns(rows)


def test_land_price_period_is_exactly_one_year_of_the_service_name() -> None:
    """J22: the period is the one year of the service's own name, or a refusal."""
    feature = {
        "attributes": {
            "DIST_NO": 14,
            "District_No": 14,
            "ResidentialPrices": "1",
            "ResidentialCityCenter": "1",
            "ResidentialPriceFlats": "1",
            "ResidentialPriceVillas": "1",
            "CommercialPrices": "1",
        },
        "geometry": _square(),
    }
    rows = land_price_rows([feature], "LandPricing2026", as_of=_INVENTED_AS_OF)
    assert {row["period"] for row in rows} == {"2026"}
    for name in ("InventedPricing", "LandPricing2025to2026", "LandPricing12345"):
        with pytest_raises_layer("service name"):
            land_price_rows([feature], name, as_of=_INVENTED_AS_OF)


def test_address_outside_the_grid_is_left_out_and_early_survey_date_is_blank() -> None:
    inside = _load("qars_features.json")[0]
    outside = json.loads(json.dumps(inside))
    outside["geometry"]["x"] = 11.75
    outside["geometry"]["y"] = 21.5
    early = json.loads(json.dumps(inside))
    early["attributes"]["SURVEYED_DATE"] = -55813363200000
    early["attributes"]["BUILDING_NO"] = 4
    rows = address_rows([inside, outside, early], _grid(10.25, 20.5))
    assert [row["building_number"] for row in rows] == ["3", "4"]
    assert rows[0]["survey_date"] == "2020-01-15"
    assert rows[1]["survey_date"] is None


def test_address_and_parcel_drop_pin_and_keep_published_dates() -> None:
    grid = _grid(10.25, 20.5)
    address = address_rows([_load("qars_features.json")[0]], grid)
    assert set(address[0]) == {
        "feature_key",
        "zone_number",
        "street_number",
        "building_number",
        "building_subtype",
        "survey_date",
        "lon",
        "lat",
        "cell",
    }
    assert address[0]["survey_date"] == "2020-01-15"
    assert address[0]["zone_number"] == "7"
    assert "PIN" not in address[0]
    parcel = parcel_rows([_load("parcel_ring.json")])
    assert parcel[0]["area_m2"] == Decimal("250.50")
    assert parcel[0]["start_date"] == "2020-01-15"
    assert parcel[0]["end_date"] is None
    assert "PIN" not in parcel[0]
    assert "PDAREA" not in parcel[0]
    assert isinstance(parcel[0]["geometry"], bytes)
    require_release_columns(address)
    require_release_columns(parcel)
    with pytest_raises_layer("available"):
        require_release_columns([{**parcel[0], "available": "yes"}])
    again = address_rows([_load("qars_features.json")[0]], grid)
    assert again[0]["feature_key"] == address[0]["feature_key"]
    assert not str(address[0]["feature_key"]).startswith("1001")


def test_same_release_columns_get_distinct_stable_keys() -> None:
    row = {"zone_number": "7", "lon": Decimal("10.250000"), "lat": Decimal("20.500000")}
    keyed = assign_feature_keys([dict(row), dict(row)])
    assert keyed[0]["feature_key"] != keyed[1]["feature_key"]
    assert str(keyed[1]["feature_key"]).endswith("_2")
    again = assign_feature_keys([dict(row), dict(row)])
    assert [item["feature_key"] for item in again] == [
        item["feature_key"] for item in keyed
    ]


def test_zoning_keeps_published_nulls_and_hides_ruleid() -> None:
    detailed = {
        "layer_name": "Khor_Wakra_Zoning",
        "features": [
            {
                "attributes": {
                    "ZONING_COD": "SYN-A",
                    "LU_ENG": "SYN USE",
                    "LU_ARB": "استخدام تجريبي",
                    "P_COM_SHOP": "Y",
                    "P_COM_OFF": None,
                    "P_RES_VIL": "Y",
                    "P_RES_APA": None,
                    "P_RES_HOT": None,
                    "HEIGHT": None,
                    "HEIGHTS": "SYN-H",
                    "SET_NOW_FR": 1.5,
                    "SET_NOW_RE": 2,
                    "SET_NOW_S1": 0,
                    "SET_NOW_S2": 0,
                    "SET_W_FR": 1,
                    "SET_W_RE": 1,
                    "SET_W_S1": 1,
                    "SET_W_S2": 1,
                    "BUILD_COV": "cache",
                    "ENTRANCE": "cache",
                    "MINIMUM_LO": "cache",
                    "LANDUSE": 3,
                    "SUB_LANDUS": 4,
                    "ZONE_ID": "SYN-Z",
                },
                "geometry": _square(),
            },
            {
                "attributes": {
                    "ZONING_COD": "SYN-B",
                    "LU_ENG": None,
                    "LU_ARB": None,
                    "P_COM_SHOP": None,
                    "P_COM_OFF": None,
                    "P_RES_VIL": None,
                    "P_RES_APA": None,
                    "P_RES_HOT": None,
                    "HEIGHT": "SYN-OTHER",
                    "HEIGHTS": None,
                    "SET_NOW_FR": 0,
                    "SET_NOW_RE": 0,
                    "SET_NOW_S1": 0,
                    "SET_NOW_S2": 0,
                    "SET_W_FR": 0,
                    "SET_W_RE": 0,
                    "SET_W_S1": 0,
                    "SET_W_S2": 0,
                    "BUILD_COV": None,
                    "ENTRANCE": None,
                    "MINIMUM_LO": None,
                    "LANDUSE": None,
                    "SUB_LANDUS": None,
                    "ZONE_ID": None,
                },
                "geometry": _square(),
            },
        ],
    }
    plain = {
        "layer_name": "Zoning",
        "features": [
            {
                "attributes": {
                    "ZONING": "SYN-C",
                    "CODE": 2,
                    "RULEID": 5,
                    "STARTDATE": _SURVEY_MS,
                },
                "geometry": _square(),
            }
        ],
    }
    rows = zoning_rows([detailed, plain])
    first, second, third = rows
    assert first["zoning_code"] == "SYN-A"
    assert first["source_layer"] == "Khor_Wakra_Zoning"
    assert isinstance(first["permitted_uses"], str)
    assert isinstance(first["height_rule"], str)
    assert isinstance(first["setback_rule"], str)
    assert first["height_rule"] is not None
    assert "SYN-H" in str(first["height_rule"])
    assert "null" in str(first["height_rule"]).casefold() or "None" not in str(
        first["permitted_uses"]
    )
    uses = json.loads(str(first["permitted_uses"]))
    assert uses["P_COM_OFF"] is None
    assert uses["LU_ENG"] == "SYN USE"
    neighbour = json.loads(str(second["height_rule"]))
    assert neighbour["HEIGHT"] == "SYN-OTHER"
    assert json.loads(str(first["height_rule"]))["HEIGHT"] is None
    assert third["zoning_code"] == "SYN-C"
    assert third["permitted_uses"] is None
    assert third["height_rule"] is None
    assert third["setback_rule"] is None
    assert third["source_layer"] == "Zoning"
    for row in rows:
        assert "RULEID" not in row
        assert "BUILD_COV" not in row
        assert "approval" not in row
        assert "permit" not in row
    require_release_columns(rows)


def test_rail_rows_have_no_operating_column() -> None:
    rows = rail_rows(
        [
            {
                "layer_id": 2,
                "layer_name": "QRAIL.Metro_Stations",
                "features": [
                    {
                        "attributes": {
                            "STATION_NAME_ENGLISH": "SYN STATION",
                            "STATION_NAME_ARABIC": "محطة تجريبية",
                        },
                        "geometry": _point(10.25, 20.5),
                    }
                ],
            },
            {
                "layer_id": 0,
                "layer_name": "QRAIL.Metro_Tracks_Detailed",
                "features": [
                    {
                        "attributes": {"TRACK_NAME": "SYN TRACK"},
                        "geometry": {
                            "paths": [[[0, 0], [1, 1]]],
                            "spatialReference": {"wkid": 4326},
                        },
                    }
                ],
            },
        ]
    )
    assert [row["feature_kind"] for row in rows] == ["planned_station", "line"]
    assert rows[0]["name_en"] == "SYN STATION"
    assert rows[1]["name_ar"] is None
    for row in rows:
        assert "OPERATIONAL_DATE" not in row
        assert "operates" not in row
    with pytest_raises_layer("operates"):
        require_release_columns([{**rows[0], "operates": True}])


def test_poi_category_stays_null_and_landmarks_use_reviewed_points() -> None:
    grid = _grid(10.25, 20.5)
    poi = poi_rows(
        [
            {
                "attributes": {
                    "ENAME": "SYN SHOP",
                    "ANAME": "متجر تجريبي",
                    "ZONE_NO": 7,
                    "STREET_NO": 12,
                    "BUILDING_NO": 3,
                },
                "geometry": _point(10.25, 20.5),
            }
        ],
        grid,
    )
    assert poi[0]["category"] is None
    assert poi[0]["name"] == "SYN SHOP"
    assert "POI_KEY" not in poi[0]
    assert "ZONE_NO" not in poi[0]
    landmarks = landmark_rows(
        [
            {
                "attributes": {"ENAME": "SYN MARK", "ANAME": "معلم تجريبي"},
                "geometry": _point(10.25, 20.5),
            }
        ],
        grid,
    )
    assert landmarks[0]["kind"] == "landmark"
    assert landmarks[0]["name_en"] == "SYN MARK"
    assert landmarks[0]["source_id"] == "gis_landmarks"
    assert "phone" not in landmarks[0]
    assert "EMAIL" not in landmarks[0]


def test_landmark_outside_the_grid_is_left_out() -> None:
    inside = {
        "attributes": {"ENAME": "SYN MARK", "ANAME": "معلم تجريبي"},
        "geometry": _point(10.25, 20.5),
    }
    outside = {
        "attributes": {"ENAME": "SYN FAR", "ANAME": "معلم بعيد"},
        "geometry": _point(11.75, 21.5),
    }
    rows = landmark_rows([inside, outside], _grid(10.25, 20.5))
    assert [row["name_en"] for row in rows] == ["SYN MARK"]


def test_landmark_keys_are_content_based() -> None:
    """J24: the same landmarks in another order give the same lm- keys."""
    souq = {
        "attributes": {"ENAME": "SYN SOUQ", "ANAME": "سوق تجريبي"},
        "geometry": _point(10.25, 20.5),
    }
    fort = {
        "attributes": {"ENAME": "SYN FORT", "ANAME": "حصن تجريبي"},
        "geometry": _point(10.35, 20.5),
    }
    grid = _grid(10.25, 20.5) + _grid(10.35, 20.5)
    first = landmark_rows([souq, fort], grid)
    second = landmark_rows([fort, souq], grid)
    assert [row["place_key"] for row in first] == [row["place_key"] for row in second]
    assert len({row["place_key"] for row in first}) == 2
    for row in first:
        assert str(row["place_key"]).startswith("lm-")
        assert not str(row["place_key"]).startswith("lm-1")


def test_pin_share_counts_points_inside_the_same_pin() -> None:
    parcel = {
        "attributes": {"PIN": 1001},
        "geometry": _square(),
    }
    inside = {"attributes": {"PIN": 1001}, "geometry": _point(0.2, 0.2)}
    outside = {"attributes": {"PIN": 1001}, "geometry": _point(3, 3)}
    share = address_parcel_share([inside, outside], [parcel])
    assert share.inside == 1
    assert share.total == 2
    assert share.line == "address_points_inside_same_pin: 1/2"
    assert share.line == pin_share_line(share.inside, share.total)
    assert pin_share_line(1, 2) == "address_points_inside_same_pin: 1/2"
    assert "threshold" not in share.line


def test_district_numbers_that_differ_fail() -> None:
    feature = {
        "attributes": {
            "DIST_NO": 14,
            "District_No": 15,
            "ResidentialPrices": "1",
            "ResidentialCityCenter": "1",
            "ResidentialPriceFlats": "1",
            "ResidentialPriceVillas": "1",
            "CommercialPrices": "1",
        },
        "geometry": _square(),
    }
    try:
        land_price_rows([feature], "LandPricing2026", as_of=_INVENTED_AS_OF)
    except LayerError as error:
        assert str(error) == "district numbers differ"
        assert "14" not in str(error)
        assert "15" not in str(error)
    else:
        raise AssertionError("differing district numbers stored")


def test_health_rows_split_a_centre_from_a_catchment() -> None:
    """J22: the layers publish no period, so it is null with a coverage note."""
    result = health_rows(
        [
            {
                "layer_name": "PHCC.PHCC_LOCATION_2026",
                "geometry": "point",
                "features": [
                    {
                        "attributes": {
                            "HC_NAME": "SYN CENTRE",
                            "A_HC_NAME": "مركز تجريبي",
                        },
                        "geometry": _point(10.25, 20.5),
                    }
                ],
            },
            {
                "layer_name": "PHCC.PHCC_CATCHMENT_2026_Q",
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
    rows = result.rows
    assert {row["feature_kind"] for row in rows} == {"centre", "catchment"}
    assert {row["period"] for row in rows} == {None}
    assert {row["name_en"] for row in rows} == {"SYN CENTRE", "SYN CATCHMENT"}
    assert result.coverage == (Coverage("period_not_published", 2),)
    assert [
        coverage_count_line("gis_phcc", note.reason, note.count)
        for note in result.coverage
    ] == ["COVERAGE gis_phcc period_not_published 2"]
    require_release_columns(rows)
    assert health_rows([]).coverage == ()


def test_context_has_no_release_table() -> None:
    assert "no flow" in CONTEXT_ROLE
    assert context_tables() == {}


def test_read_layer_refuses_an_off_list_host_and_a_token(tmp_path: Path) -> None:
    called = False

    def transport(url: str) -> Response:
        nonlocal called
        called = True
        raise AssertionError(url)

    base = next(entry for entry in load_registry() if entry.kind == "paged_layer")
    entry = replace(
        base,
        key="gis_address",
        source_id="gis_address",
        skip_reason="",
        url="https://evil.example/Vector/QARS/MapServer",
        fetch_host="evil.example",
        terms_url="",
    )
    refused = read_layer(entry, transport)
    assert refused.failure == "blocked_host"
    assert called is False
    assert refused.layers == ()

    def token(url: str) -> Response:
        body = {"error": {"code": 499, "message": "Token Required", "details": []}}
        return Response(final_url=url, body=json.dumps(body).encode(), hops=())

    allowed = replace(
        entry,
        url=_GIS,
        fetch_host=urlsplit(_GIS).hostname or "",
    )
    unread = read_layer(allowed, token)
    assert unread.failure == "unavailable"
    assert unread.layers == ()
    assert list(tmp_path.iterdir()) == []


class _Raises:
    def __init__(self, text: str) -> None:
        self.text = text

    def __enter__(self) -> LayerError:
        return LayerError("")

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        assert exc_type is LayerError
        assert isinstance(exc, LayerError)
        assert self.text in str(exc)
        return True


def pytest_raises_layer(text: str) -> _Raises:
    return _Raises(text)


def _load(name: str) -> list[dict[str, object]] | dict[str, object]:
    path = _ROOT / "custodian" / "tests" / "fixtures" / "gis" / name
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return [item for item in loaded if isinstance(item, dict)]
    if isinstance(loaded, dict):
        return loaded
    raise AssertionError(name)


def _grid(lon: float, lat: float) -> list[dict[str, object]]:
    cell = h3.str_to_int(h3.latlng_to_cell(lat, lon, 9))
    return [{"cell": cell}]


def _point(lon: float, lat: float) -> dict[str, object]:
    return {"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}


def _square() -> dict[str, object]:
    return {
        "rings": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        "spatialReference": {"wkid": 4326},
    }
