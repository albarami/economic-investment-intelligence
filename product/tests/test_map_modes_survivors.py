"""Exact offline route contracts for the map-mode mutation pass."""

import json
from decimal import Decimal

import pytest
from fastapi import FastAPI
from product.tests.reason_contract import assert_error
from product.tests.test_map_modes import invoke, view_query
from product.tests.test_map_modes import provider as provider

from eii_product.api import map_modes
from eii_product.api.app import create_app
from eii_product.photoreal_tiles.limit import SPEND_CEILING_USD


def expected_meter(*, limit=None, warning=False):
    """Literal initial-journal contract of decision 0063 item 1."""
    return {
        "billable_requests": 0,
        "request_limit": int(SPEND_CEILING_USD * 1000 / Decimal("6"))
        if limit is None
        else limit,
        "spend_usd": "0",
        "warning": warning,
        "ceiling_usd": format(SPEND_CEILING_USD, "f"),
        "price_per_thousand_usd": "6",
        "method_version": "1",
        "default_price_retrieved_on": "2026-11-13",
    }


def assert_refusal(response, *, capped=False, reason="NOT_FOUND"):
    status, raw, headers = response
    if capped:
        assert status == 429
        assert_error(raw, "PROVIDER_CAP_REACHED", "cap_reached")
    else:
        assert status == 404
        assert_error(raw, "NOT_FOUND", reason)
    assert headers[b"cache-control"] == b"no-store"
    assert headers[b"content-type"] == b"application/json"


@pytest.mark.parametrize("configured", ["0", "-1"])
def test_zero_budget_refuses_exactly(tmp_path, provider, monkeypatch, configured):
    count, calls, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", configured)
    app = create_app(tmp_path, opener=opener, count_path=count)
    assert_refusal(invoke(app, "/api/photoreal/views", "POST"), capped=True)
    assert json.loads(invoke(app, "/api/map-modes")[1])["photoreal"] == {
        "available": False,
        "reason": "cap_reached",
        "meter": expected_meter(limit=0, warning=True),
    }
    assert count.read_text() == "ready:0\n"
    assert calls == []


@pytest.mark.parametrize(
    "setting,value",
    [
        ("EII_PHOTOREAL_LIMIT", "SYN-invalid"),
        ("EII_PHOTOREAL_PRICE_PER_THOUSAND", "SYN-invalid"),
        ("EII_PHOTOREAL_PRICE_PER_THOUSAND", "0"),
    ],
)
def test_invalid_configuration_reason(tmp_path, provider, monkeypatch, setting, value):
    count, calls, _, opener = provider
    monkeypatch.setenv(setting, value)
    app = create_app(tmp_path, opener=opener, count_path=count)
    assert json.loads(invoke(app, "/api/map-modes")[1])["photoreal"] == {
        "available": False,
        "reason": "count_unavailable",
        "meter": None,
    }
    assert_refusal(
        invoke(app, "/api/photoreal/views", "POST"), reason="count_unavailable"
    )
    assert calls == []


@pytest.mark.parametrize(
    "missing,unavailable",
    [
        ("ESRI_API_KEY", "satellite"),
        ("MAPTILE_API_KEY", "photoreal"),
        ("EII_IMAGERY_TILE_BASE", "satellite"),
        ("EII_PHOTOREAL_TILE_BASE", "photoreal"),
    ],
)
def test_modes_use_independent_settings(
    tmp_path, provider, monkeypatch, missing, unavailable
):
    count, calls, _, opener = provider
    monkeypatch.delenv(missing)
    app = create_app(tmp_path, opener=opener, count_path=count)
    modes = json.loads(invoke(app, "/api/map-modes")[1])
    expected = {
        "open": {"available": True, "reason": None},
        "satellite": {"available": True, "reason": None},
        "photoreal": {"available": True, "reason": None, "meter": expected_meter()},
    }
    expected[unavailable] = {
        "available": False,
        "reason": "no_key" if missing.endswith("KEY") else "no_address",
    }
    if unavailable == "photoreal":
        expected[unavailable]["meter"] = expected_meter()
    assert modes == expected
    assert calls == []


@pytest.mark.parametrize(
    "query", ["", "view=SYN-missing", "view=a&view=b", "view=a&extra=b"]
)
def test_malformed_view_refuses_exactly(tmp_path, provider, query):
    count, calls, _, opener = provider
    app = create_app(tmp_path, opener=opener, count_path=count)
    assert_refusal(invoke(app, "/api/photoreal/3dtiles/root.json", query=query))
    assert calls == []
    assert count.read_text() == "ready:0\n"


def test_damaged_counter_reason_and_body(tmp_path, provider):
    count, calls, _, opener = provider
    app = create_app(tmp_path, opener=opener, count_path=count)
    query = view_query(app)
    count.write_text("ready:0\npending:0\n")
    assert_refusal(
        invoke(app, "/api/photoreal/3dtiles/root.json", query=query),
        reason="count_unavailable",
    )
    assert json.loads(invoke(app, "/api/map-modes")[1])["photoreal"] == {
        "available": False,
        "reason": "count_unavailable",
        "meter": None,
    }
    assert calls == []


@pytest.mark.parametrize(
    "media_type",
    [
        "image/png",
        "image/jpeg",
        "application/json",
        "application/octet-stream",
        "model/gltf-binary",
        None,
    ],
)
def test_deliver_exact_media_type(provider, media_type):
    # Direct call: exchange_metadata normally supplies the provider's headers.
    # A provider can omit Content-Type, which must use the binary default.
    _, _, response, _ = provider
    headers = {"x-attribution": "SYN credit"}
    if media_type is not None:
        headers["content-type"] = media_type
    result = map_modes.deliver(
        (200, response.raw, headers), "SYN-unused", require_credit=True
    )
    assert result.status_code == 200
    assert result.body == b"SYN-tile"
    assert dict(result.headers) == {
        "cache-control": "no-store",
        "x-attribution": "SYN credit",
        "content-length": "8",
        "content-type": media_type
        if media_type is not None
        else "application/octet-stream",
    }


def test_schema_refusal_exact_body(provider):
    _, _, response, _ = provider
    result = map_modes.deliver(
        (200, response.raw, {"content-type": "text/html"}),
        "SYN-unused",
        require_credit=False,
    )
    assert result.status_code == 404
    assert_error(result.body, "NOT_FOUND", "response_unavailable")
    assert result.headers["cache-control"] == "no-store"


def test_project_limit_refusal_keeps_exact_count(tmp_path, provider, monkeypatch):
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", "600")
    count, calls, _, opener = provider
    app = create_app(tmp_path, opener=opener, count_path=count)
    query = view_query(app)
    status, raw, _ = invoke(app, "/api/photoreal/3dtiles/root.json", query=query)
    assert status == 200
    alias = json.loads(raw)["root"]["content"]["uri"]
    for _ in range(599):
        assert invoke(app, alias, query=query)[0] == 200
    before = count.read_bytes()
    assert_refusal(invoke(app, alias, query=query), capped=True)
    assert len(calls) == 600
    assert count.read_bytes() == before
    assert before.endswith(b"pending:599\nready:600\n")


def test_offline_reader_requires_literal_false(provider):
    count, calls, _, opener = provider
    app = FastAPI()
    app.include_router(
        map_modes.build_router(lambda: "SYN-unused", lambda: None, opener, count)
    )
    assert json.loads(invoke(app, "/api/map-modes")[1]) == {
        "open": {"available": True, "reason": None},
        "satellite": {"available": False, "reason": "offline"},
        "photoreal": {
            "available": False,
            "reason": "offline",
            "meter": expected_meter(),
        },
    }
    assert calls == []
