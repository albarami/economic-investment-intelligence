"""Declared GIS layer paging. Invented responses only; no source record is copied.

Registry rows for these sources are part R and are not in this workspace.
Each test builds the entry it needs. Kept fields are the lists under B2.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from eii_custodian.publicdata.fetch.build import fetch_entry
from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.snapshots import checked_times, read_snapshot
from eii_custodian.publicdata.fetch.transport import Response

_GIS = "https://services.gisqatar.org.qa/server/rest/services/Vector/QARS/MapServer"
_QARS_FIELDS = (
    "ZONE_NO",
    "STREET_NO",
    "BUILDING_NO",
    "PIN",
    "BUILDING_NO_SUBTYPE",
    "SURVEYED_DATE",
    "SHAPE",
)
_NEVER = (
    "EMP_NUM",
    "SURVEYED_BY",
    "JOB",
    "GFCODE",
    "REMARKS",
    "COMMENTS",
    "WATER_NO",
    "ELECTRICITY_NO",
    "QTEL_ID",
    "QARS",
    "DATE_LUPD",
    "GLOBALID",
)
# 2020-01-15T00:00:00Z as epoch milliseconds. Thirteen digits, not eight or eleven.
_SURVEY_MS = 1579046400000


def test_utility_field_refuses_before_cache(tmp_path: Path) -> None:
    base = next(entry for entry in load_registry() if entry.kind == "paged_layer")
    entry = replace(
        base,
        key="gis_address",
        source_id="gis_address",
        skip_reason="",
        columns=(("ZONE_NO", "integer"),),
        terms_url="",
    )
    requests: list[str] = []

    def transport(url: str) -> Response:
        requests.append(url)
        if "returnCountOnly" in url:
            body: dict[str, object] = {"count": 1}
        elif "/query" not in url:
            body = {
                "maxRecordCount": 20000,
                "fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID"}],
            }
        else:
            body = {
                "features": [{"attributes": {"ZONE_NO": 1, "WATER_NO": "SYN-UTILITY"}}]
            }
        return Response(final_url=url, body=json.dumps(body).encode(), hops=())

    failure = fetch_entry(entry, transport, tmp_path, _clock, _sleep)
    assert failure is not None, f"utility field cached; requests={requests}"
    assert failure.check == "never_taken"
    assert list(tmp_path.iterdir()) == []


def test_declared_request_names_kept_fields_and_the_oid_from_the_answer(
    tmp_path: Path,
) -> None:
    """The object-id field is whatever type esriFieldTypeOID the layer names."""
    features = [_qars_feature()]
    transport = _LayerTransport(features, max_count=3, oid_name="SYN_OID")
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is None
    pages = [url for url in transport.urls if "outFields" in url]
    assert len(pages) == 1
    params = _params(pages[0])
    assert params["outFields"] == ",".join(_QARS_FIELDS)
    assert "*" not in params["outFields"]
    assert params["orderByFields"] == "SYN_OID"
    assert params["resultRecordCount"] == "3"
    assert params["outSR"] == "4326"
    for banned in (*_NEVER, "OBJECTID", "SYN_OID"):
        assert banned not in params["outFields"].split(",")
    stored = _stored(tmp_path)
    assert stored["layers"][0]["count"] == 1
    for feature in stored["layers"][0]["features"]:
        names = set(feature["attributes"])
        assert names.isdisjoint(_NEVER)
        assert "OBJECTID" not in names
        assert "SYN_OID" not in names


def test_smaller_stated_maximum_pages_until_the_total(tmp_path: Path) -> None:
    features = [_qars_feature(pin) for pin in (1001, 1002, 1003, 1004, 1005)]
    transport = _LayerTransport(features, max_count=2, oid_name="OBJECTID")
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is None
    pages = [_params(url) for url in transport.urls if "outFields" in url]
    assert [page["resultOffset"] for page in pages] == ["0", "2", "4"]
    assert {page["resultRecordCount"] for page in pages} == {"2"}
    stored = _stored(tmp_path)
    assert stored["layers"][0]["count"] == 5
    assert len(stored["layers"][0]["features"]) == 5


def test_short_total_fails(tmp_path: Path) -> None:
    transport = _LayerTransport([_qars_feature()], max_count=2, reported_count=4)
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "short_total"
    assert list(tmp_path.iterdir()) == []


def test_long_total_fails(tmp_path: Path) -> None:
    features = [_qars_feature(1001), _qars_feature(1002)]
    transport = _LayerTransport(features, max_count=20, reported_count=1)
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "long_total"
    assert list(tmp_path.iterdir()) == []


def test_missing_declared_field_fails(tmp_path: Path) -> None:
    feature = _qars_feature()
    del feature["attributes"]["STREET_NO"]
    transport = _LayerTransport([feature], max_count=20)
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "schema_missing"
    assert failure.expected == "STREET_NO"
    assert list(tmp_path.iterdir()) == []


def test_retyped_declared_field_fails(tmp_path: Path) -> None:
    feature = _qars_feature()
    feature["attributes"]["ZONE_NO"] = "7"
    transport = _LayerTransport([feature], max_count=20)
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "schema_retyped"
    assert list(tmp_path.iterdir()) == []


def test_extra_served_field_fails(tmp_path: Path) -> None:
    feature = _qars_feature()
    feature["attributes"]["SYN_EXTRA"] = "invented"
    transport = _LayerTransport([feature], max_count=20)
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "extra_field"
    assert failure.observed == "SYN_EXTRA"
    assert list(tmp_path.iterdir()) == []


def test_object_id_attribute_fails(tmp_path: Path) -> None:
    feature = _qars_feature()
    feature["attributes"]["SYN_OID"] = 4
    transport = _LayerTransport([feature], max_count=20, oid_name="SYN_OID")
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None, "object id attribute stored"
    assert failure.check == "object_id_field"
    assert list(tmp_path.iterdir()) == []


def test_emp_num_fails(tmp_path: Path) -> None:
    _assert_never_taken(tmp_path, "EMP_NUM", 9)


def test_surveyed_by_fails(tmp_path: Path) -> None:
    _assert_never_taken(tmp_path, "SURVEYED_BY", "SYN-EDITOR")


def test_token_demand_is_unavailable_and_loads_nothing(tmp_path: Path) -> None:
    transport = _LayerTransport([_qars_feature()], max_count=20, token_at="meta")
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "unavailable"
    assert list(tmp_path.iterdir()) == []
    assert not any("outFields" in url for url in transport.urls)


def test_token_code_without_the_word_loads_nothing(tmp_path: Path) -> None:
    transport = _LayerTransport(
        [_qars_feature()],
        max_count=20,
        token_at="meta",
        token_code=498,
        token_message="Access denied",
    )
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "unavailable"
    assert list(tmp_path.iterdir()) == []


def test_sign_in_message_without_a_token_code_loads_nothing(tmp_path: Path) -> None:
    transport = _LayerTransport(
        [_qars_feature()],
        max_count=20,
        token_at="meta",
        token_code=400,
        token_message="Please sign in",
    )
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "unavailable"
    assert list(tmp_path.iterdir()) == []


def test_zero_stated_maximum_fails_before_a_page(tmp_path: Path) -> None:
    transport = _LayerTransport([_qars_feature()], max_count=0)
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "schema_missing"
    assert not any("outFields" in url for url in transport.urls)
    assert list(tmp_path.iterdir()) == []


def test_boolean_is_not_an_integer_field(tmp_path: Path) -> None:
    feature = _qars_feature()
    feature["attributes"]["ZONE_NO"] = True
    transport = _LayerTransport([feature], max_count=20)
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "schema_retyped"
    assert list(tmp_path.iterdir()) == []


def test_undeclared_row_still_asks_for_every_field(tmp_path: Path) -> None:
    entry = next(
        item for item in load_registry() if item.source_id == "census_zone_sector"
    )
    transport = _LayerTransport([{"attributes": {}}], max_count=2000)
    failure = fetch_entry(entry, transport, tmp_path, _clock, _sleep)
    assert failure is None
    pages = [url for url in transport.urls if "outFields" in url]
    assert len(pages) == 1
    params = _params(pages[0])
    assert params["outFields"] == "*"
    assert "orderByFields" not in params
    assert params["resultRecordCount"] == "2000"


def test_geometry_outside_web_mercator_fails(tmp_path: Path) -> None:
    feature = _qars_feature()
    feature["geometry"] = {
        "x": 10.25,
        "y": 20.5,
        "spatialReference": {"wkid": 2932},
    }
    transport = _LayerTransport([feature], max_count=20)
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "spatial_reference"
    assert list(tmp_path.iterdir()) == []


def test_host_off_the_list_fails_before_a_request(tmp_path: Path) -> None:
    called = False

    def transport(url: str) -> Response:
        nonlocal called
        called = True
        raise AssertionError(url)

    entry = _entry("gis_address", "https://evil.example/Vector/QARS/MapServer")
    failure = fetch_entry(entry, transport, tmp_path, _clock, _sleep)
    assert failure is not None
    assert failure.check == "blocked_host"
    assert called is False
    assert list(tmp_path.iterdir()) == []


def test_review_file_lists_kept_fields_and_omits_absent_layers() -> None:
    from eii_custodian.publicdata.gis.fields import declarations

    found = declarations()
    address = found["gis_address"].layers[0]
    assert address.layer_name == "QARS"
    assert tuple(field.name for field in address.fields) == _QARS_FIELDS
    assert address.page_limit == 20000
    parcels = found["gis_parcels"].layers[0]
    assert tuple(field.name for field in parcels.fields) == (
        "PIN",
        "SHAPE.AREA",
        "STARTDATE",
        "ENDDATE",
        "SHAPE",
    )
    assert parcels.page_limit == 2000
    assert found["gis_landmarks"].layers[0].page_limit == 10000
    assert found["gis_poi_comm"].layers[0].page_limit == 1000
    catchment = found["gis_phcc"].layers[1]
    assert catchment.layer_id == 1
    assert "OBJECTID_1" not in {field.name for field in catchment.fields}
    for source_id, source in found.items():
        for layer in source.layers:
            names = {field.name for field in layer.fields}
            assert names.isdisjoint(_NEVER), source_id
            assert "OBJECTID" not in names
    for absent in ("gis_boundaries", "gis_imagery_history", "gis_locator"):
        assert absent not in found


def _assert_never_taken(tmp_path: Path, name: str, value: object) -> None:
    feature = _qars_feature()
    feature["attributes"][name] = value
    transport = _LayerTransport([feature], max_count=20)
    failure = fetch_entry(_entry("gis_address"), transport, tmp_path, _clock, _sleep)
    assert failure is not None, name
    assert failure.check == "never_taken"
    assert failure.observed == name
    assert list(tmp_path.iterdir()) == []


def _qars_feature(pin: int = 1001) -> dict[str, object]:
    return {
        "attributes": {
            "ZONE_NO": 7,
            "STREET_NO": 12,
            "BUILDING_NO": 3,
            "PIN": pin,
            "BUILDING_NO_SUBTYPE": 4,
            "SURVEYED_DATE": _SURVEY_MS,
        },
        "geometry": {
            "x": 10.25,
            "y": 20.5,
            "spatialReference": {"wkid": 4326},
        },
    }


class _LayerTransport:
    """Hand-made ArcGIS answers: layer document, count, then pages."""

    def __init__(
        self,
        features: list[dict[str, object]],
        max_count: int,
        oid_name: str = "OBJECTID",
        reported_count: int | None = None,
        token_at: str = "",
        token_code: int = 499,
        token_message: str = "Token Required",
    ) -> None:
        self.features = features
        self.max_count = max_count
        self.oid_name = oid_name
        self.reported_count = (
            len(features) if reported_count is None else reported_count
        )
        self.token_at = token_at
        self.token_code = token_code
        self.token_message = token_message
        self.urls: list[str] = []

    def __call__(self, url: str) -> Response:
        self.urls.append(url)
        if self.token_at == "meta" and "/query" not in url:
            body: object = {
                "error": {
                    "code": self.token_code,
                    "message": self.token_message,
                    "details": [],
                }
            }
        elif "returnCountOnly" in url:
            body = {"count": self.reported_count}
        elif "/query" not in url:
            body = {
                "maxRecordCount": self.max_count,
                "fields": [
                    {"name": "OBJECTID", "type": "esriFieldTypeInteger"},
                    {"name": self.oid_name, "type": "esriFieldTypeOID"},
                ],
            }
        else:
            params = _params(url)
            offset = int(params.get("resultOffset", "0"))
            size = int(params.get("resultRecordCount", "0"))
            body = {"features": self.features[offset : offset + size]}
        return Response(final_url=url, body=json.dumps(body).encode(), hops=())


def _entry(source_id: str, url: str = _GIS) -> Entry:
    base = next(entry for entry in load_registry() if entry.kind == "paged_layer")
    return replace(
        base,
        key=source_id,
        source_id=source_id,
        skip_reason="",
        layer=0,
        url=url,
        fetch_host=urlsplit(url).hostname or "",
        columns=(),
        terms_url="",
    )


def _params(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


def _stored(tmp_path: Path) -> dict[str, object]:
    indexes = sorted(tmp_path.glob("**/index/*.json"))
    snapshots = [read_snapshot(path.parent.parent, path.stem) for path in indexes]
    bodies = [snapshot.body for snapshot in snapshots]
    assert len(bodies) == 1
    for index, snapshot in zip(indexes, snapshots, strict=True):
        directory = index.parent.parent
        check = dict(snapshot.sidecar, identity=index.stem)
        check_bytes = (
            json.dumps(check, sort_keys=True, ensure_ascii=True) + "\n"
        ).encode()
        check_path = (
            directory / "checks" / (hashlib.sha256(check_bytes).hexdigest() + ".json")
        )
        body_alias = directory / snapshot.path.name
        receipt_alias = directory / snapshot.receipt_path.name
        assert {path for path in directory.rglob("*") if path.is_file()} == {
            snapshot.path,
            snapshot.receipt_path,
            index,
            check_path,
            body_alias,
            receipt_alias,
        }
        assert check_path.read_bytes() == check_bytes
        assert body_alias.samefile(snapshot.path)
        assert receipt_alias.samefile(snapshot.receipt_path)
        assert checked_times(directory) == (snapshot.sidecar["retrieved_utc"],)
    loaded = json.loads(bodies[0])
    assert isinstance(loaded, dict)
    return loaded


def _clock() -> str:
    return "2026-11-15T00:00:00Z"


def _sleep(_seconds: float) -> None:
    return None
