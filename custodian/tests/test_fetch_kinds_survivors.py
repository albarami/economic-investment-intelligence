"""Invented GIS answers exercise complete fetch contracts and refusal records."""

import json
from dataclasses import replace
from typing import Any

import pytest
from custodian.tests.test_publicdata_behaviour import _entry, _ok, _sleep

from eii_custodian.publicdata.fetch import kinds
from eii_custodian.publicdata.fetch.checks import AttemptFailure
from eii_custodian.publicdata.fetch.registry import RegistryError
from eii_custodian.publicdata.fetch.transport import Response, TransportFault
from eii_custodian.publicdata.gis import fields

BASE = "https://services.gisqatar.org.qa/inventedX/"
META = "https://services.gisqatar.org.qa/inventedX/3?f=json"
COUNT = "https://services.gisqatar.org.qa/inventedX/3/query?where=1%3D1&returnCountOnly=true&f=json"
PAGE = "https://services.gisqatar.org.qa/inventedX/3/query?where=1%3D1&outFields=SYN_VALUE%2CSYN_SHAPE&orderByFields=SYN_OID&resultOffset=0&resultRecordCount=1&returnGeometry=true&outSR=4326&f=json"
LAND = "https://services.gisqatar.org.qa/invented-final"
META_BODY = {
    "maxRecordCount": 1,
    "fields": [{"name": "SYN_OID", "type": "esriFieldTypeOID"}],
}


def wrong(value: object) -> Any:
    """Deliberately malformed seam input, without type suppression."""
    return value


def message(error: BaseException, expected: str) -> None:
    """Compare a complete refusal message with the caller's literal."""
    assert str(error) == expected


@pytest.fixture
def declared(monkeypatch: pytest.MonkeyPatch) -> fields.SourceDecl:
    layer = fields.LayerDecl(
        "/inventedX/",
        3,
        "Invented layer",
        "point",
        1,
        (
            fields.FieldDecl("SYN_VALUE", "esriFieldTypeInteger"),
            fields.FieldDecl("SYN_SHAPE", "esriFieldTypeGeometry"),
        ),
    )
    source = fields.SourceDecl("invented", (layer,))
    monkeypatch.setattr(fields, "_CACHE", {"invented": source})
    return source


def entry():
    return replace(
        _entry(), source_id="invented", kind="paged_layer", url=BASE, layer=3
    )


def feature(value: object = 7) -> dict[str, object]:
    return {
        "attributes": {"SYN_VALUE": value},
        "geometry": {"spatialReference": {"wkid": 4326}},
    }


def scripted(bodies: list[object], urls: list[str]):
    def read(url: str) -> Response:
        urls.append(url)
        assert len(urls) <= len(bodies), "unexpected request"
        body = bodies[len(urls) - 1]
        if isinstance(body, TransportFault):
            raise body
        return _ok(LAND, json.dumps(body).encode())

    return read


def failed(actual: kinds.Prepared, check: str, expected: str, observed: str) -> None:
    assert actual == kinds.Prepared(
        b"",
        LAND,
        "",
        "Planted publisher",
        "",
        None,
        "",
        AttemptFailure(1, LAND, check, expected, observed),
    )


@pytest.mark.parametrize(
    "bodies,check,expected,observed",
    [
        ([META_BODY, {}], "short_total", "count", "unreadable"),
        ([{}, {"count": 1}], "schema_missing", "maxRecordCount", "missing"),
        (
            [{"maxRecordCount": 1, "fields": []}, {"count": 1}],
            "schema_missing",
            "maxRecordCount",
            "missing",
        ),
        ([META_BODY, {"count": 1}, {}], "short_total", "features", "unreadable"),
        ([META_BODY, {"count": 1}, {"features": []}], "short_total", "1", "0"),
        (
            [META_BODY, {"count": 1}, {"features": [feature(), feature()]}],
            "long_total",
            "1",
            "2",
        ),
        ([{"error": {"code": 498}}], "unavailable", "no token", "token demand"),
        (
            [META_BODY, {"error": {"code": 499}}],
            "unavailable",
            "no token",
            "token demand",
        ),
        (
            [META_BODY, {"count": 1}, {"error": {"message": "SIGNIN"}}],
            "unavailable",
            "no token",
            "token demand",
        ),
    ],
)
def test_declared_failures(declared, bodies, check, expected, observed):
    urls: list[str] = []
    failed(
        kinds.prepare(entry(), scripted(bodies, urls), _sleep),
        check,
        expected,
        observed,
    )
    assert urls == [META, COUNT, PAGE][: len(bodies)]


@pytest.mark.parametrize("stage", [0, 1, 2])
def test_declared_transport_failure(declared, stage):
    bodies = [META_BODY, {"count": 1}, {"features": [feature()]}][:stage]
    bodies.append(TransportFault("blocked_host", LAND))
    urls: list[str] = []
    failed(
        kinds.prepare(entry(), scripted(bodies, urls), _sleep),
        "blocked_host",
        "allow-listed host",
        LAND,
    )
    assert urls == [META, COUNT, PAGE][: stage + 1]


@pytest.mark.parametrize("count", [0, 1])
def test_declared_success(declared, count):
    bodies = [META_BODY, {"count": count}]
    if count:
        bodies.append({"features": [feature()]})
    urls: list[str] = []
    actual = kinds.prepare(entry(), scripted(bodies, urls), _sleep)
    assert urls == ([META, COUNT, PAGE] if count else [META, COUNT])
    rows = (
        b'[{"attributes": {"SYN_VALUE": 7}, "geometry": {"spatialReference": {"wkid": 4326}}}]'
        if count
        else b"[]"
    )
    body = (
        b'{"layers": [{"count": '
        + (b"1" if count else b"0")
        + b', "features": '
        + rows
        + b', "geometry": "point", "layer_id": 3, "layer_name": "Invented layer", "service_path": "/inventedX/"}]}'
    )
    assert actual == kinds.Prepared(
        body, LAND, "services.gisqatar.org.qa", "Planted publisher", "", count, "", None
    )


def test_declared_invalid_source():
    # Public prepare obtains a SourceDecl from declaration_for; only this helper
    # accepts an arbitrary object, before the explicit isinstance refusal.
    with pytest.raises(RegistryError) as error:
        kinds._paged_declared(entry(), lambda url: _ok(url, b""), object())
    message(error.value, "gis declaration")


def test_declared_empty_source():
    result = kinds._paged_declared(
        entry(), lambda url: pytest.fail(url), fields.SourceDecl("invented", ())
    )
    assert result == kinds.Prepared(
        b'{"layers": []}',
        BASE,
        "services.gisqatar.org.qa",
        "Planted publisher",
        "",
        0,
        "",
        None,
    )


@pytest.mark.parametrize("stage", [0, 1, 2])
def test_declared_absent_response(declared, stage, monkeypatch):
    original = kinds._call
    calls = 0

    def call(row, url, reader):
        nonlocal calls
        calls += 1
        if calls == stage + 1:
            return None, None
        return original(row, url, reader)

    monkeypatch.setattr(kinds, "_call", call)
    result = kinds.prepare(entry(), scripted([META_BODY, {"count": 1}], []), _sleep)
    assert result == kinds.Prepared(
        b"",
        BASE,
        "",
        "Planted publisher",
        "",
        None,
        "",
        AttemptFailure(1, BASE, "check_failed", "passed check", "check failed"),
    )


@pytest.mark.parametrize(
    "bodies,expected,observed",
    [
        ([{}], "count", "unreadable"),
        ([{"count": 1}, {}], "features", "unreadable"),
        ([{"count": 2}, {"features": ["invented"]}], "2", "1"),
        ([{"count": 1}, {"features": []}], "1", "0"),
    ],
)
def test_undeclared_failures(bodies, expected, observed):
    urls: list[str] = []
    result = kinds.prepare(entry(), scripted(bodies, urls), _sleep)
    failed(result, "short_total", expected, observed)
    assert urls[0] == COUNT
    if len(urls) == 2:
        assert (
            urls[1]
            == "https://services.gisqatar.org.qa/inventedX/3/query?where=1%3D1&outFields=%2A&resultOffset=0&resultRecordCount=2000&f=json"
        )


@pytest.mark.parametrize("stage", [0, 1])
def test_undeclared_transport_failure(stage):
    bodies = [*[{"count": 1}][:stage], TransportFault("blocked_host", LAND)]
    failed(
        kinds.prepare(entry(), scripted(bodies, []), _sleep),
        "blocked_host",
        "allow-listed host",
        LAND,
    )


@pytest.mark.parametrize("count", [0, 1])
def test_undeclared_success(count):
    bodies = [{"count": count}]
    if count:
        bodies.append({"features": [{"z": 2, "a": 1}]})
    urls: list[str] = []
    result = kinds.prepare(entry(), scripted(bodies, urls), _sleep)
    body = (
        b'{"count": 1, "features": [{"a": 1, "z": 2}]}'
        if count
        else b'{"count": 0, "features": []}'
    )
    assert result == kinds.Prepared(
        body, LAND, "services.gisqatar.org.qa", "Planted publisher", "", count, "", None
    )
    assert len(urls) == (2 if count else 1)


def test_undeclared_three_pages():
    urls: list[str] = []
    bodies = [
        {"count": 4001},
        {"features": [1] * 2000},
        {"features": [2] * 2000},
        {"features": [3]},
    ]
    result = kinds.prepare(entry(), scripted(bodies, urls), _sleep)
    assert result.failure is None
    assert json.loads(result.body) == {
        "count": 4001,
        "features": [1] * 2000 + [2] * 2000 + [3],
    }
    assert urls == [COUNT] + [
        "https://services.gisqatar.org.qa/inventedX/3/query?where=1%3D1&outFields=%2A&resultOffset="
        + offset
        + "&resultRecordCount=2000&f=json"
        for offset in ("0", "2000", "4000")
    ]


def test_undeclared_requires_layer():
    with pytest.raises(RegistryError) as error:
        kinds.prepare(
            replace(entry(), layer=None), lambda url: pytest.fail(url), _sleep
        )
    message(error.value, "paged_layer requires layer")


@pytest.mark.parametrize(
    "row,check,expected,observed",
    [
        ({}, "schema_missing", "attributes", "missing"),
        ({"attributes": []}, "schema_missing", "attributes", "missing"),
        ({"attributes": {"EMP_NUM": 1}}, "never_taken", "absent", "EMP_NUM"),
        ({"attributes": {"SYN_OID": 1}}, "object_id_field", "absent", "SYN_OID"),
        ({"attributes": {"SYN_EXTRA": 1}}, "extra_field", "declared", "SYN_EXTRA"),
        ({"attributes": {}}, "schema_missing", "SYN_VALUE", "missing"),
        (feature(True), "schema_retyped", "SYN_VALUE:integer", "boolean"),
        (feature(2.5), "schema_retyped", "SYN_VALUE:integer", "number"),
        (feature("invented"), "schema_retyped", "SYN_VALUE:integer", "string"),
        (feature([]), "schema_retyped", "SYN_VALUE:integer", "other"),
        ({"attributes": {"SYN_VALUE": 7}}, "schema_missing", "SYN_SHAPE", "missing"),
        (
            {"attributes": {"SYN_VALUE": 7}, "geometry": {}},
            "spatial_reference",
            "4326",
            "other",
        ),
    ],
)
def test_declared_feature_failures(declared, row, check, expected, observed):
    result = kinds.prepare(
        entry(), scripted([META_BODY, {"count": 1}, {"features": [row]}], []), _sleep
    )
    failed(result, check, expected, observed)


def test_invalid_layer_declaration():
    # prepare obtains typed LayerDecl objects from SourceDecl; its field loader
    # rejects invalid layers before this helper can receive them.
    assert kinds._declared_features(object(), [], "SYN_OID", LAND) == AttemptFailure(
        1, LAND, "schema_missing", "layer", "missing"
    )


def test_integer_seen_in_string_slot(declared, monkeypatch):
    layer = replace(
        declared.layers[0],
        fields=(
            fields.FieldDecl("SYN_VALUE", "esriFieldTypeString"),
            fields.FieldDecl("SYN_SHAPE", "esriFieldTypeGeometry"),
        ),
    )
    monkeypatch.setattr(
        fields, "_CACHE", {"invented": fields.SourceDecl("invented", (layer,))}
    )
    failed(
        kinds.prepare(
            entry(),
            scripted([META_BODY, {"count": 1}, {"features": [feature()]}], []),
            _sleep,
        ),
        "schema_retyped",
        "SYN_VALUE:string",
        "integer",
    )
