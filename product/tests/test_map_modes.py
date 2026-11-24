"""Offline invented provider responses; all counters use pytest temporary paths."""

from __future__ import annotations

import asyncio
import json
import uuid
from decimal import Decimal
from urllib.parse import unquote

import pytest

from eii_product.api.app import create_app
from eii_product.photoreal_tiles.limit import SPEND_CEILING_USD


def invoke(app, path, method="GET", query=""):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(
        app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": unquote(path),
                "raw_path": path.encode(),
                "query_string": query.encode(),
                "headers": [],
                "client": ("fixture.invalid", 0),
                "server": ("fixture.invalid", 80),
            },
            receive,
            send,
        )
    )
    start = next(row for row in sent if row["type"] == "http.response.start")
    raw = b"".join(row.get("body", b"") for row in sent)
    return start["status"], raw, dict(start["headers"])


class Response:
    def __init__(self, status=200, raw=b"SYN-tile", headers=None):
        self.status = status
        self.raw = raw
        self.headers = headers or {
            "Content-Type": "image/png",
            "X-Attribution": "SYN-credit",
        }

    def read(self):
        return self.raw

    def close(self):
        pass


@pytest.fixture
def provider(tmp_path, monkeypatch):
    monkeypatch.setenv("MAPTILE_API_KEY", "SYN-" + uuid.uuid4().hex)
    monkeypatch.setenv("ESRI_API_KEY", "SYN-" + uuid.uuid4().hex)
    monkeypatch.setenv("EII_PHOTOREAL_TILE_BASE", "https://photoreal.invalid/")
    monkeypatch.setenv("EII_IMAGERY_TILE_BASE", "https://imagery.invalid/")
    count = tmp_path / "count"
    count.write_text("ready:0\n")
    calls = []
    response = Response()

    def opener(request, timeout):
        calls.append(request)
        if "f=json" in request.full_url:
            return Response(
                raw=json.dumps(
                    {"copyrightText": response.headers.get("X-Attribution", "")}
                ).encode(),
                headers={"Content-Type": "application/json"},
            )
        if "/v1/3dtiles/root.json?" in request.full_url and response.raw == b"SYN-tile":
            return Response(
                status=response.status,
                raw=json.dumps(
                    {
                        "asset": {"version": "1.1"},
                        "geometricError": 0,
                        "root": {
                            "geometricError": 0,
                            "boundingVolume": {"sphere": [0, 0, 0, 1]},
                            "content": {"uri": "child.glb?session=SYN-session"},
                        },
                    }
                ).encode(),
                headers={**response.headers, "Content-Type": "application/json"},
            )
        if "/v1/3dtiles/child.glb?" in request.full_url:
            return Response(
                status=response.status,
                raw=b"SYN-tile",
                headers={"Content-Type": "model/gltf-binary"},
            )
        return response

    return count, calls, response, opener


@pytest.mark.parametrize(
    "path",
    [
        "https://foreign.invalid/tile.glb",
        "//foreign.invalid/tile.glb",
        "../tile.glb",
        "a/../tile.glb",
        "a%2f..%2ftile.glb",
        "root.json?key=plant",
        "root.json%3fkey=plant",
        "root.json#plant",
    ],
)
def test_photoreal_tile_path_is_closed(tmp_path, provider, path):
    count, calls, _, opener = provider
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, raw, _ = invoke(app, "/api/photoreal/views", "POST")
    assert status == 200
    view = json.loads(raw)["view_id"]
    assert invoke(app, "/api/photoreal/" + path, query="view=" + view)[0] == 404
    assert calls == []


def test_off_host_redirect_is_refused(tmp_path, provider):
    count, calls, response, opener = provider
    response.status = 302
    response.headers["Location"] = "https://foreign.invalid/tile.glb"
    app = create_app(tmp_path, opener=opener, count_path=count)
    _, raw, _ = invoke(app, "/api/photoreal/views", "POST")
    view = json.loads(raw)["view_id"]
    assert (
        invoke(app, "/api/photoreal/3dtiles/root.json", query="view=" + view)[0] == 404
    )
    assert len(calls) == 1
    assert count.read_text().endswith("ready:0\n")


def view_query(app):
    status, raw, _ = invoke(app, "/api/photoreal/views", "POST")
    assert status == 200
    return "view=" + json.loads(raw)["view_id"]


def test_modes_are_closed_and_keyless_requests_never_send(tmp_path, monkeypatch):
    calls = []
    monkeypatch.delenv("ESRI_API_KEY", raising=False)
    monkeypatch.delenv("MAPTILE_API_KEY", raising=False)
    app = create_app(tmp_path, opener=lambda *a, **k: calls.append(a))
    status, raw, headers = invoke(app, "/api/map-modes")
    assert status == 200
    assert json.loads(raw) == {
        "open": {"available": True, "reason": None},
        "satellite": {"available": False, "reason": "no_key"},
        "photoreal": {"available": False, "reason": "no_key", "meter": None},
    }
    assert headers[b"cache-control"] == b"no-store"
    assert invoke(app, "/api/imagery/tiles/0/0/0")[0] == 404
    assert invoke(app, "/api/photoreal/views", "POST")[0] == 404
    assert invoke(app, "/api/photoreal/3dtiles/root.json", query="view=plant")[0] == 404
    assert calls == []


def test_offline_and_missing_address_disable_modes(tmp_path, provider, monkeypatch):
    count, calls, _, opener = provider
    app = create_app(
        tmp_path, opener=opener, count_path=count, offline_reader=lambda: True
    )
    modes = json.loads(invoke(app, "/api/map-modes")[1])
    assert modes["satellite"]["reason"] == "offline"
    assert modes["photoreal"]["reason"] == "offline"
    assert invoke(app, "/api/imagery/tiles/0/0/0")[0] == 404
    assert invoke(app, "/api/photoreal/views", "POST")[0] == 404
    monkeypatch.delenv("EII_IMAGERY_TILE_BASE")
    monkeypatch.delenv("EII_PHOTOREAL_TILE_BASE")
    app = create_app(tmp_path, opener=opener, count_path=count)
    modes = json.loads(invoke(app, "/api/map-modes")[1])
    assert modes["satellite"]["reason"] == "no_address"
    assert modes["photoreal"]["reason"] == "no_address"
    assert calls == []


def test_satellite_tiles_are_ephemeral_and_credit_is_response_metadata(
    tmp_path, provider
):
    count, calls, response, opener = provider
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, raw, headers = invoke(app, "/api/imagery/tiles/0/0/0")
    assert status == 200 and raw == response.raw
    assert headers[b"cache-control"] == b"no-store"
    assert headers[b"x-attribution"] == b"SYN-credit"
    assert len(calls) == 2
    assert not any(
        response.raw in p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    )
    plant = tmp_path / "stored-tile"
    plant.write_bytes(response.raw)
    assert any(
        response.raw in p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    )
    plant.unlink()
    for path in ("-1/0/0", "1/2/0", "1/0/2", "999/0/0"):
        assert invoke(app, "/api/imagery/tiles/" + path)[0] == 404
    assert len(calls) == 2


@pytest.mark.parametrize("status", [200, 204, 299, 300, 302, 400, 503])
def test_counts_every_provider_success_including_root(tmp_path, provider, status):
    count, _, response, opener = provider
    response.status = status
    app = create_app(tmp_path, opener=opener, count_path=count)
    query = view_query(app)
    returned, _, _ = invoke(app, "/api/photoreal/3dtiles/root.json", query=query)
    assert returned == (status if 200 <= status < 300 else 404)
    assert count.read_text().endswith(
        "ready:1\n" if 200 <= status < 300 else "ready:0\n"
    )


@pytest.mark.parametrize("where", ["body", "header"])
def test_echoed_key_never_leaves_route(tmp_path, provider, monkeypatch, caplog, where):
    import os

    count, _, response, opener = provider
    secret = os.environ["MAPTILE_API_KEY"]
    if where == "body":
        response.raw = secret.encode()
    else:
        response.headers["X-Attribution"] = secret
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, raw, headers = invoke(
        app, "/api/photoreal/3dtiles/root.json", query=view_query(app)
    )
    assert status == 404
    assert secret not in raw.decode() + str(headers) + caplog.text
    assert count.read_text().endswith("ready:1\n")


def test_limit_price_and_serialized_concurrency(tmp_path, provider, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from decimal import Decimal

    from eii_product.photoreal_tiles.limit import SPEND_CEILING_USD, billable_limit

    assert billable_limit(Decimal("6")) == int(SPEND_CEILING_USD * 1000 / 6)
    assert billable_limit(Decimal("12")) == int(SPEND_CEILING_USD * 1000 / 12)
    count, calls, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", "1")
    app = create_app(tmp_path, opener=opener, count_path=count)
    queries = [view_query(app), view_query(app)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda q: invoke(app, "/api/photoreal/3dtiles/root.json", query=q)[0],
                queries,
            )
        )
    assert sorted(results) == [200, 429]
    assert len(calls) == 1
    assert json.loads(invoke(app, "/api/map-modes")[1])["photoreal"] == {
        "available": False,
        "reason": "cap_reached",
        "meter": {
            "billable_requests": 1,
            "request_limit": 1,
            "spend_usd": "0.006",
            "warning": True,
            "ceiling_usd": format(SPEND_CEILING_USD, "f"),
            "price_per_thousand_usd": "6",
            "method_version": "1",
            "default_price_retrieved_on": "2026-11-13",
        },
    }
    restarted = create_app(tmp_path, opener=opener, count_path=count)
    assert invoke(restarted, "/api/photoreal/views", "POST")[0] == 429


@pytest.mark.parametrize(
    "damage",
    ["missing", "malformed", "pending", "lowered", "restart-lowered", "restart-jumped"],
)
def test_counter_damage_fails_closed(tmp_path, provider, damage, monkeypatch):
    from eii_product.photoreal_tiles.limit import Budget, BudgetFailure

    count, calls, _, opener = provider
    if damage.startswith("restart-"):
        journal = (
            "ready:0\npending:0\nready:1\npending:1\nready:0\n"
            if damage == "restart-lowered"
            else "ready:0\npending:0\nready:2\n"
        )
        count.write_text(journal)
        # A fresh reader has no in-process prefix history to catch this damage.
        budget = Budget(count)
        with pytest.raises(BudgetFailure, match="count_unavailable"):
            budget.count()
        with pytest.raises(BudgetFailure, match="count_unavailable"):
            budget.request(3333, lambda: calls.append("SYN-send"), bool)
        app = create_app(tmp_path, opener=opener, count_path=count)
        state = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]
        assert state == {
            "available": False,
            "reason": "count_unavailable",
            "meter": None,
        }
        assert invoke(app, "/api/photoreal/views", "POST")[0] == 404
        assert calls == []
        assert count.read_text() == journal
        return
    app = create_app(tmp_path, opener=opener, count_path=count)
    query = view_query(app)
    status, raw, _ = invoke(app, "/api/photoreal/3dtiles/root.json", query=query)
    assert status == 200
    alias = json.loads(raw)["root"]["content"]["uri"]
    # A prior availability result must not replace the transaction's journal check.
    monkeypatch.setattr(Budget, "available", lambda self, maximum: None)
    if damage == "missing":
        count.unlink()
    elif damage == "malformed":
        count.write_text("plant\n")
    elif damage == "pending":
        with count.open("a") as f:
            f.write("pending:1\n")
    else:
        count.write_text("ready:0\n")
    assert invoke(app, alias, query=query)[0] == 404
    assert len(calls) == 1


def test_view_above_six_hundred_and_restart_forgets_view(tmp_path, provider):
    count, calls, _, opener = provider
    app = create_app(tmp_path, opener=opener, count_path=count)
    query = view_query(app)
    status, raw, _ = invoke(app, "/api/photoreal/3dtiles/root.json", query=query)
    assert status == 200
    alias = json.loads(raw)["root"]["content"]["uri"]
    for _ in range(601):
        assert invoke(app, alias, query=query)[0] == 200
    assert len(calls) == 602
    assert count.read_text().endswith("ready:602\n")
    restarted = create_app(tmp_path, opener=opener, count_path=count)
    assert invoke(restarted, "/api/photoreal/3dtiles/root.json", query=query)[0] == 404


def test_named_spend_ceiling_controls_the_billable_limit(monkeypatch):
    from eii_product.photoreal_tiles import limit

    assert limit.billable_limit(Decimal("5")) == 3333
    original = limit.billable_limit(Decimal("10"))
    # Plant a different ceiling: a literal in billable_limit must fail this test.
    monkeypatch.setattr(limit, "SPEND_CEILING_USD", Decimal("1"), raising=False)
    assert limit.billable_limit(Decimal("10")) == 100
    assert limit.billable_limit(Decimal("10")) < original


def test_meter_price_below_floor_keeps_request_limit(tmp_path, provider, monkeypatch):
    count, calls, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_PRICE_PER_THOUSAND", "5")
    monkeypatch.delenv("EII_PHOTOREAL_LIMIT", raising=False)
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, raw, headers = invoke(app, "/api/map-modes")
    assert status == 200 and headers[b"cache-control"] == b"no-store"
    meter = json.loads(raw)["photoreal"]["meter"]
    assert meter["request_limit"] == 3333
    assert meter["price_per_thousand_usd"] == "5"
    assert count.read_text() == "ready:0\n"
    assert calls == []


def seed_journal(count, total):
    count.write_text(
        "ready:0\n" + "".join(f"pending:{n}\nready:{n + 1}\n" for n in range(total))
    )


@pytest.mark.parametrize("total,warned", [(7, False), (8, True), (9, True)])
def test_meter_warning_below_at_and_above_fraction(
    tmp_path, provider, monkeypatch, total, warned
):
    count, calls, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", "10")
    monkeypatch.setenv("EII_PHOTOREAL_PRICE_PER_THOUSAND", "7.125")
    seed_journal(count, total)
    before = count.read_bytes()
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, raw, headers = invoke(app, "/api/map-modes")
    assert status == 200
    state = json.loads(raw)["photoreal"]
    assert state["available"] is True
    assert state["meter"] == {
        "billable_requests": total,
        "request_limit": 10,
        "spend_usd": str(Decimal(total) * Decimal("7.125") / 1000),
        "warning": warned,
        "ceiling_usd": format(SPEND_CEILING_USD, "f"),
        "price_per_thousand_usd": "7.125",
        "method_version": "1",
        "default_price_retrieved_on": "2026-11-13",
    }
    assert headers[b"cache-control"] == b"no-store"
    assert count.read_bytes() == before
    assert calls == []


def test_warning_fraction_is_one_named_default(tmp_path, provider, monkeypatch):
    from eii_product.photoreal_tiles import limit

    count, _, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", "10")
    seed_journal(count, 5)
    app = create_app(tmp_path, opener=opener, count_path=count)
    monkeypatch.setattr(limit, "WARNING_FRACTION", Decimal("0.50"), raising=False)
    assert (
        json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]["meter"]["warning"]
        is True
    )


def test_meter_keeps_small_decimal_money_in_plain_notation(
    tmp_path, provider, monkeypatch
):
    count, calls, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_PRICE_PER_THOUSAND", "0.000001")
    seed_journal(count, 1)
    app = create_app(tmp_path, opener=opener, count_path=count)
    meter = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]["meter"]
    assert meter["spend_usd"] == "0.000000001"
    assert calls == []


def test_meter_updates_on_requests_and_survives_restart(tmp_path, provider):
    count, calls, _, opener = provider
    app = create_app(tmp_path, opener=opener, count_path=count)
    initial = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]["meter"]
    assert initial["billable_requests"] == 0
    query = view_query(app)
    assert invoke(app, "/api/photoreal/3dtiles/root.json", query=query)[0] == 200
    updated = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]["meter"]
    assert updated["billable_requests"] == 1
    assert updated["spend_usd"] == "0.006"
    restarted = create_app(tmp_path, opener=opener, count_path=count)
    assert (
        json.loads(invoke(restarted, "/api/map-modes")[1])["photoreal"]["meter"]
        == updated
    )
    assert len(calls) == 1


@pytest.mark.parametrize("configured", ["2", "99999"])
def test_meter_setting_can_only_lower_named_ceiling(
    tmp_path, provider, monkeypatch, configured
):
    from eii_product.photoreal_tiles.limit import SPEND_CEILING_USD

    count, _, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", configured)
    monkeypatch.setenv("EII_PHOTOREAL_PRICE_PER_THOUSAND", "12")
    app = create_app(tmp_path, opener=opener, count_path=count)
    meter = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]["meter"]
    assert meter["request_limit"] == min(
        int(configured), int(SPEND_CEILING_USD * 1000 / Decimal("12"))
    )


def test_meter_at_cap_keeps_total_and_refuses_without_sending(
    tmp_path, provider, monkeypatch
):
    count, calls, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", "1")
    app = create_app(tmp_path, opener=opener, count_path=count)
    query = view_query(app)
    status, raw, _ = invoke(app, "/api/photoreal/3dtiles/root.json", query=query)
    assert status == 200
    alias = json.loads(raw)["root"]["content"]["uri"]
    before = count.read_bytes()
    state = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]
    assert state["reason"] == "cap_reached"
    assert state["meter"] == {
        "billable_requests": 1,
        "request_limit": 1,
        "spend_usd": "0.006",
        "warning": True,
        "ceiling_usd": format(SPEND_CEILING_USD, "f"),
        "price_per_thousand_usd": "6",
        "method_version": "1",
        "default_price_retrieved_on": "2026-11-13",
    }
    assert invoke(app, alias, query=query)[0] == 429
    assert count.read_bytes() == before
    assert len(calls) == 1


@pytest.mark.parametrize("journal", [None, "broken\n", "ready:0\npending:0\n"])
def test_meter_never_invents_a_total_for_unavailable_count(tmp_path, provider, journal):
    count, calls, _, opener = provider
    if journal is None:
        count.unlink()
    else:
        count.write_text(journal)
    app = create_app(tmp_path, opener=opener, count_path=count)
    state = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]
    assert state == {
        "available": False,
        "reason": "count_unavailable",
        "meter": None,
    }
    assert invoke(app, "/api/photoreal/views", "POST")[0] == 404
    assert calls == []


def test_actual_redirect_handler_refuses_without_following():
    from urllib.request import Request

    from eii_product.imagery_provider.address import AddressFailure
    from eii_product.photoreal_tiles.proxy import NoRedirect

    with pytest.raises(AddressFailure):
        NoRedirect().redirect_request(
            Request("https://fixture.invalid/"),
            None,
            302,
            "redirect",
            {},
            "https://foreign.invalid/",
        )


def test_escaped_key_is_refused(tmp_path, provider):
    import os

    count, _, response, opener = provider
    secret = os.environ["MAPTILE_API_KEY"]
    response.raw = (
        '{"echo":"' + "".join("\\u" + format(ord(c), "04x") for c in secret) + '"}'
    ).encode()
    response.headers["Content-Type"] = "application/json"
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, _, _ = invoke(
        app, "/api/photoreal/3dtiles/root.json", query=view_query(app)
    )
    assert status == 404
    assert count.read_text().endswith("ready:1\n")


def test_configured_tile_base_can_hold_the_providers_service_path(
    tmp_path, provider, monkeypatch
):
    count, calls, _, opener = provider
    monkeypatch.setenv(
        "EII_IMAGERY_TILE_BASE", "https://imagery.invalid/SYN-service/MapServer"
    )
    app = create_app(tmp_path, opener=opener, count_path=count)
    assert invoke(app, "/api/imagery/tiles/0/0/0")[0] == 200
    assert calls[1].full_url.startswith(
        "https://imagery.invalid/SYN-service/MapServer/tile/0/0/0?"
    )


def test_map_settings_are_empty_and_pinned():
    import ast

    from product.tests.sector_fixture import repository_path

    tree = ast.parse(repository_path("scripts/check_tree.py", __file__).read_text())
    names = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "ENV_EXAMPLE_NAMES"
            for target in node.targets
        )
    )
    env_example_names = ast.literal_eval(names)

    example = repository_path(".env.example", __file__).read_text()
    for name in (
        "EII_IMAGERY_TILE_BASE",
        "EII_PHOTOREAL_TILE_BASE",
        "EII_PHOTOREAL_LIMIT",
        "EII_PHOTOREAL_PRICE_PER_THOUSAND",
    ):
        assert name in env_example_names
        assert name + "=\n" in example


def test_missing_attribution_refuses_the_picture(tmp_path, provider):
    count, _, response, opener = provider
    response.headers.pop("X-Attribution")
    app = create_app(tmp_path, opener=opener, count_path=count)
    assert invoke(app, "/api/imagery/tiles/0/0/0")[0] == 404
    # Native tileset metadata has no header attribution contract (N3 C5).
    # Missing GLB copyright is refused by the qualified client loader.
    assert (
        invoke(app, "/api/photoreal/3dtiles/root.json", query=view_query(app))[0] == 200
    )
    assert count.read_text().endswith("ready:1\n")


def test_native_satellite_credit_comes_from_service_metadata(tmp_path, provider):
    count, calls, _, _ = provider

    def opener(request, timeout):
        calls.append(request)
        if "/tile/" not in request.full_url:
            return Response(
                raw=b'{"copyrightText":"SYN-native-credit"}',
                headers={"Content-Type": "application/json"},
            )
        return Response(
            headers={"Content-Type": "image/png", "X-Attribution": "SYN-false-credit"}
        )

    app = create_app(tmp_path, opener=opener, count_path=count)
    status, _, headers = invoke(app, "/api/imagery/tiles/0/0/0")
    assert status == 200
    assert headers[b"x-attribution"] == b"SYN-native-credit"
    assert len(calls) == 2
    assert "f=json" in calls[0].full_url


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b'{"copyrightText":0}',
        b'{"copyrightText":true}',
        b'{"copyrightText":["SYN-credit"]}',
        b'{"copyrightText":""}',
        b"[]",
        b"broken",
    ],
)
def test_invalid_native_credit_never_requests_a_tile(tmp_path, provider, raw):
    count, calls, _, _ = provider

    def opener(request, timeout):
        calls.append(request)
        return Response(raw=raw, headers={"Content-Type": "application/json"})

    app = create_app(tmp_path, opener=opener, count_path=count)
    assert invoke(app, "/api/imagery/tiles/0/0/0")[0] == 404
    assert len(calls) == 1
    assert bool("/tile/" not in calls[0].full_url)


@pytest.mark.parametrize("failure", ["unreadable", "write", "crash"])
def test_counter_io_failure_refuses_without_forgetting(
    tmp_path, provider, monkeypatch, failure
):
    from pathlib import Path

    from eii_product.photoreal_tiles.limit import Budget, BudgetFailure

    count, _, _, _ = provider
    budget = Budget(count)
    budget.request(3, lambda: True, bool)
    before = count.read_bytes()
    calls = []
    original = Path.open

    def fail_open(path, *args, **kwargs):
        if path == count:
            raise PermissionError
        return original(path, *args, **kwargs)

    def send():
        calls.append(True)
        if failure == "crash":
            raise RuntimeError("SYN-interrupted")
        return True

    if failure == "unreadable":
        monkeypatch.setattr(Path, "open", fail_open)
    elif failure == "write":
        monkeypatch.setattr(
            budget, "_append", lambda *args: (_ for _ in ()).throw(OSError())
        )
    with pytest.raises(BudgetFailure, match="count_unavailable"):
        budget.request(3, send, bool)
    monkeypatch.undo()
    if failure == "crash":
        assert calls == [True]
        with pytest.raises(BudgetFailure, match="count_unavailable"):
            Budget(count).available(3)
    else:
        assert calls == []
        assert count.read_bytes() == before


def test_new_application_and_release_roots_preserve_the_journal(tmp_path, provider):
    from eii_product.photoreal_tiles.limit import Budget, BudgetFailure

    count, calls, _, opener = provider
    Budget(count).request(1, lambda: True, bool)
    before = count.read_bytes()
    for root in (
        tmp_path,
        tmp_path / "SYN-new-release",
        tmp_path / "SYN-restored-release",
    ):
        app = create_app(root, opener=opener, count_path=count)
        modes = json.loads(invoke(app, "/api/map-modes")[1])
        assert modes["photoreal"]["available"] is True
        assert count.read_bytes() == before
        with pytest.raises(BudgetFailure, match="cap_reached"):
            Budget(count).available(1)
    assert calls == []


def test_satellite_does_not_hide_an_echoed_header_before_validation(tmp_path, provider):
    import os

    count, calls, _, _ = provider

    def opener(request, timeout):
        calls.append(request)
        if "f=json" in request.full_url:
            return Response(
                raw=b'{"copyrightText":"SYN-credit"}',
                headers={"Content-Type": "application/json"},
            )
        return Response(
            headers={
                "Content-Type": "image/png",
                "X-Attribution": os.environ["ESRI_API_KEY"],
            }
        )

    app = create_app(tmp_path, opener=opener, count_path=count)
    assert invoke(app, "/api/imagery/tiles/0/0/0")[0] == 404


@pytest.mark.parametrize("variant", ["redirect", "echo", "transport"])
def test_native_metadata_failure_refuses_without_tile(tmp_path, provider, variant):
    import os

    count, calls, _, _ = provider

    def opener(request, timeout):
        calls.append(request)
        if variant == "transport":
            raise OSError("SYN-unavailable")
        return Response(
            status=302 if variant == "redirect" else 200,
            raw=json.dumps(
                {
                    "copyrightText": os.environ["ESRI_API_KEY"]
                    if variant == "echo"
                    else "SYN-credit"
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
        )

    app = create_app(tmp_path, opener=opener, count_path=count)
    assert invoke(app, "/api/imagery/tiles/0/0/0")[0] == 404
    assert len(calls) == 1


def test_photoreal_without_credit_header_delivers_tile(tmp_path, provider):
    count, calls, response, opener = provider
    response.headers.pop("X-Attribution")
    app = create_app(tmp_path, opener=opener, count_path=count)
    query = view_query(app)
    status, raw, headers = invoke(app, "/api/photoreal/3dtiles/root.json", query=query)
    assert status == 200
    root = json.loads(raw)
    assert headers[b"cache-control"] == b"no-store"
    assert b"x-attribution" not in headers
    assert len(calls) == 1
    assert count.read_text().endswith("ready:1\n")
    alias = root["root"]["content"]["uri"]
    assert "?" not in alias
    status, raw, headers = invoke(app, alias, query=query)
    assert status == 200
    assert raw == b"SYN-tile"
    assert headers[b"cache-control"] == b"no-store"
    assert b"x-attribution" not in headers
    assert len(calls) == 2
    assert count.read_text().endswith("ready:2\n")


@pytest.mark.parametrize(
    "credit", ["SYN-credit", "SYN-\ncredit", "SYN-\tcredit", "SYN-\u00e9credit"]
)
def test_optional_photoreal_credit_is_validated(tmp_path, provider, credit):
    count, _, response, opener = provider
    response.headers["X-Attribution"] = credit
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, _, headers = invoke(
        app, "/api/photoreal/3dtiles/root.json", query=view_query(app)
    )
    assert status == (200 if credit == "SYN-credit" else 404)
    assert headers[b"cache-control"] == b"no-store"
    if status == 200:
        assert headers[b"x-attribution"] == b"SYN-credit"
    else:
        assert b"x-attribution" not in headers


def test_meter_operational_provenance_is_server_bound(tmp_path, provider):
    count, calls, _, opener = provider
    app = create_app(tmp_path, opener=opener, count_path=count)
    meter = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]["meter"]
    assert meter["method_version"] == "1"
    assert meter["ceiling_usd"] == format(SPEND_CEILING_USD, "f")
    assert meter["price_per_thousand_usd"] == "6"
    assert meter["default_price_retrieved_on"] == "2026-11-13"
    assert calls == []
