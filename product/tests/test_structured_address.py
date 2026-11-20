"""Offline structured search: invented released rows, no provider or persistence."""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi import FastAPI

from eii_product.api.address_search import (
    AddressIndex,
    AddressQuery,
    AddressRefusal,
    AddressRow,
    address_router,
    prepare_read,
)


@pytest.fixture(autouse=True)
def no_network():
    with patch(
        "socket.socket.connect", side_effect=AssertionError("network forbidden")
    ):
        yield


def row(key="fea-invented-a", subtype=None):
    return AddressRow(
        key,
        "71",
        "802",
        "9",
        subtype,
        Decimal("51.123456"),
        Decimal("25.123456"),
        "gis_address",
        "a" * 64,
        "2026-11-20",
        "owner_decision",
        "0026",
        "national GIS centre",
        "terms to be read",
    )


def test_exact_found_missing_and_ambiguous_never_silently_chosen():
    query = AddressQuery("71", "802", "9")
    assert AddressIndex(None).search(query).status == "missing-source"
    assert AddressIndex(()).search(query).status == "not-found"
    assert AddressIndex((row(),)).search(query).status == "found"
    found = AddressIndex((row("fea-invented-b", "2"), row())).search(query)
    assert found.status == "ambiguous"
    assert [r.feature_key for r in found.candidates] == [
        "fea-invented-a",
        "fea-invented-b",
    ]
    assert found.candidates[1].building_subtype == "2"
    assert (
        AddressIndex((row(),)).search(AddressQuery("071", "802", "9")).status
        == "not-found"
    )
    assert (
        AddressIndex(tuple(row(f"fea-invented-{i}") for i in range(7)))
        .search(query)
        .truncated
        is True
    )
    with pytest.raises(AddressRefusal, match="duplicate"):
        AddressIndex((row(), row()))


@pytest.mark.parametrize(
    "field",
    ["text", "pin", "utility_account", "person", "lang", "limit", "url", "model"],
)
def test_unknown_and_free_text_fields_refused_by_name(field):
    body = {"zone": "71", "street": "802", "building": "9", field: "invented"}
    with pytest.raises(
        AddressRefusal,
        match="free_text_refused" if field == "text" else "fields_refused",
    ):
        AddressQuery.parse(body)


@pytest.mark.parametrize(
    "value", [9, True, None, "", "9 road", " 9", "9\n", "1" * 8, "1" * 11]
)
def test_typed_fields_are_closed_published_strings(value):
    with pytest.raises(AddressRefusal, match="field_value"):
        AddressQuery.parse({"zone": "71", "street": "802", "building": value})


def test_two_fixed_store_reads_bind_only_typed_values():
    query = AddressQuery("71", "802", "9")
    for engine, placeholder in (("postgres", "%s"), ("embedded", "?")):
        sql, bound = prepare_read(engine, query)
        assert sql.count(placeholder) == 3
        assert bound == ("71", "802", "9")
        assert "pub_address_point" in sql and "ORDER BY feature_key" in sql
        assert "71" not in sql and "LIMIT 6" in sql
    with pytest.raises(AddressRefusal, match="engine"):
        prepare_read("unknown", query)


async def post(app, body):
    sent = []

    async def receive():
        return {
            "type": "http.request",
            "body": json.dumps(body).encode(),
            "more_body": False,
        }

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/address-search/structured",
        "raw_path": b"/api/address-search/structured",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json")],
        "server": ("test", 80),
        "client": ("test", 1),
    }
    await app(scope, receive, send)
    return sent[0]["status"], json.loads(sent[1]["body"])


def test_typed_api_with_keys_and_offline_controls_never_egresses(monkeypatch, tmp_path):
    app = FastAPI()
    app.include_router(address_router(AddressIndex((row(),))))
    for values in (
        {},
        {"ESRI_API_KEY": "invented-canary", "EII_OFFLINE": "0"},
        {"ESRI_API_KEY": "invented-canary", "EII_OFFLINE": "1"},
    ):
        for key in ("ESRI_API_KEY", "EII_OFFLINE"):
            monkeypatch.delenv(key, raising=False)
        for key, value in values.items():
            monkeypatch.setenv(key, value)
        status, body = asyncio.run(
            post(app, {"zone": "71", "street": "802", "building": "9"})
        )
        assert status == 200 and body["status"] == "found"
        assert body["candidates"][0]["source_id"] == "gis_address"
        status, body = asyncio.run(post(app, {"text": "invented query"}))
        assert status == 422 and body["detail"] == "free_text_refused"
    assert list(tmp_path.iterdir()) == []


def test_store_adapters_share_results_and_embedded_index_is_real():
    from dataclasses import asdict

    import duckdb

    from eii_product.api.address_search import INDEX_DDL, StoredAddressSearch

    data = (
        "fea-invented-a",
        "71",
        "802",
        "9",
        None,
        Decimal("51.123456"),
        Decimal("25.123456"),
    )
    # This double proves the PostgreSQL binding contract, not live PostgreSQL parity.
    seen = []

    def pg_read(sql, bound):
        seen.append((sql, bound))
        return [data]

    lineage = {
        key: value
        for key, value in asdict(row()).items()
        if key
        in {
            "source_id",
            "source_sha256",
            "retrieved_on",
            "licence_basis",
            "decision_record",
            "publisher",
            "terms_words",
        }
    }
    with duckdb.connect(":memory:") as connection:
        connection.execute("CREATE SCHEMA app")
        connection.execute(
            "CREATE TABLE app.pub_address_point (feature_key VARCHAR,zone_number VARCHAR,street_number VARCHAR,building_number VARCHAR,building_subtype VARCHAR,lon DECIMAL(9,6),lat DECIMAL(9,6))"
        )
        connection.execute(INDEX_DDL)
        connection.execute(
            "INSERT INTO app.pub_address_point VALUES (?,?,?,?,?,?,?)", data
        )

        def embedded_read(sql, bound):
            return connection.execute(sql, bound).fetchall()

        query = AddressQuery("71", "802", "9")
        pg = StoredAddressSearch("postgres", pg_read, lineage).search(query)
        embedded = StoredAddressSearch("embedded", embedded_read, lineage).search(query)
        assert pg == embedded == AddressIndex((row(),)).search(query)
        assert seen[0][1] == ("71", "802", "9")
        assert not any(
            word in seen[0][0].upper() for word in ("INSERT", "UPDATE", "DELETE")
        )
