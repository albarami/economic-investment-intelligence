"""Small GIS declarations reach the remaining JSON and paging boundaries."""

from dataclasses import replace

import pytest
from custodian.tests import test_fetch_kinds_survivors as fixtures
from custodian.tests.test_publicdata_behaviour import _ok, _sleep

from eii_custodian.publicdata.fetch import kinds
from eii_custodian.publicdata.gis import fields

# Reuse the invented declaration and response builders from the first new file.
declared = fixtures.declared


@pytest.mark.parametrize(
    "esri_type,value,accepted",
    [
        ("esriFieldTypeInteger", None, True),
        ("esriFieldTypeString", "invented", True),
        ("esriFieldTypeString", 7, False),
        ("esriFieldTypeDouble", 2.5, True),
        ("esriFieldTypeDouble", 2, True),
        ("esriFieldTypeDouble", True, False),
        ("esriFieldTypeDouble", "invented", False),
        ("esriFieldTypeDate", 3, True),
    ],
)
def test_declared_json_kinds(declared, esri_type, value, accepted, monkeypatch):
    layer = replace(
        declared.layers[0],
        fields=(
            fields.FieldDecl("SYN_VALUE", esri_type),
            fields.FieldDecl("SYN_SHAPE", "esriFieldTypeGeometry"),
        ),
    )
    monkeypatch.setattr(
        fields, "_CACHE", {"invented": fields.SourceDecl("invented", (layer,))}
    )
    result = kinds.prepare(
        fixtures.entry(),
        fixtures.scripted(
            [fixtures.META_BODY, {"count": 1}, {"features": [fixtures.feature(value)]}],
            [],
        ),
        _sleep,
    )
    assert (result.failure is None) is accepted


def test_unknown_json_kind():
    # A loaded declaration never holds an unrecognised field type, so this
    # helper is called directly.
    assert kinds._json_kind_ok(7, "invented-kind") is False


@pytest.mark.parametrize("body", [b"not-json", b"[]", b"\xff"])
def test_malformed_gis_metadata_is_schema_failure(declared, body):
    calls = []

    def read(url):
        calls.append(url)
        assert len(calls) <= 2
        return _ok(fixtures.LAND, body if len(calls) == 1 else b'{"count": 1}')

    fixtures.failed(
        kinds.prepare(fixtures.entry(), read, _sleep),
        "schema_missing",
        "maxRecordCount",
        "missing",
    )
    assert calls == [fixtures.META, fixtures.COUNT]


@pytest.mark.parametrize("message", ["TOKEN needed", "no access token here"])
def test_token_text_without_token_code(declared, message):
    result = kinds.prepare(
        fixtures.entry(),
        fixtures.scripted([{"error": {"code": 400, "message": message}}], []),
        _sleep,
    )
    fixtures.failed(result, "unavailable", "no token", "token demand")


@pytest.mark.parametrize("name", ["", 7])
def test_oid_name_must_be_nonempty_text(declared, name):
    meta = {"maxRecordCount": 1, "fields": [{"type": "esriFieldTypeOID", "name": name}]}
    result = kinds.prepare(
        fixtures.entry(), fixtures.scripted([meta, {"count": 1}], []), _sleep
    )
    fixtures.failed(result, "schema_missing", "maxRecordCount", "missing")


def test_multiple_layer_total(declared, monkeypatch):
    second = replace(declared.layers[0], layer_id=4, layer_name="Invented second")
    monkeypatch.setattr(
        fields,
        "_CACHE",
        {"invented": fields.SourceDecl("invented", (*declared.layers, second))},
    )
    urls = []
    result = kinds.prepare(
        fixtures.entry(),
        fixtures.scripted(
            [
                fixtures.META_BODY,
                {"count": 1},
                {"features": [fixtures.feature()]},
                fixtures.META_BODY,
                {"count": 1},
                {"features": [fixtures.feature()]},
            ],
            urls,
        ),
        _sleep,
    )
    assert result.failure is None
    assert result.row_count == 2
    assert urls == [
        fixtures.META,
        fixtures.COUNT,
        fixtures.PAGE,
        "https://services.gisqatar.org.qa/inventedX/4?f=json",
        "https://services.gisqatar.org.qa/inventedX/4/query?where=1%3D1&returnCountOnly=true&f=json",
        "https://services.gisqatar.org.qa/inventedX/4/query?where=1%3D1&outFields=SYN_VALUE%2CSYN_SHAPE&orderByFields=SYN_OID&resultOffset=0&resultRecordCount=1&returnGeometry=true&outSR=4326&f=json",
    ]
