"""S3-T16 box 17. The count is Budget.request, called by the photoreal route.

Each provider forward on https://photoreal.invalid is one send. A later attempt
is another forward. A success status and a success whose body cannot be read
are the failures and successes the provider bills; an ordinary HTTP error is not.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qsl, urlsplit
from urllib.request import Request

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from product.tests.reason_contract import assert_error
from product.tests.test_map_modes import Response, invoke, seed_journal, view_query
from product.tests.test_map_modes import provider as provider

from eii_product.api.app import create_app
from eii_product.api.map_modes import deliver, meter_header
from eii_product.photoreal_tiles.limit import (
    SPEND_CEILING_USD,
    WARNING_FRACTION,
    BillableFailure,
    Budget,
    BudgetFailure,
    encode_spend_meter,
    journal_order_token,
)

HOST = "photoreal.invalid"
ROOT = {
    "asset": {"version": "1.1"},
    "geometricError": 0,
    "root": {
        "geometricError": 0,
        "boundingVolume": {"sphere": [0, 0, 0, 1]},
        "content": {"uri": "child.glb?session=SYN-session"},
    },
}


def warning_oracle(count: int, limit: int) -> bool:
    """80 percent as the integer comparison count/limit >= 4/5."""
    assert WARNING_FRACTION == Decimal("0.80")
    return count * 5 >= limit * 4


def spend_value(count: int, price_units: int) -> Decimal:
    """USD as micro-USD divided by one million.

    price_units is thousandths of one USD per thousand requests. The result
    is USD, never a request count.
    """
    return Decimal(count * price_units) / Decimal(1_000_000)


def plain_usd(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


class BrokenBody(Response):
    def read(self) -> bytes:
        raise OSError("SYN-body")


def query_shape(request: Request) -> tuple[str, tuple[str, ...]]:
    parsed = urlsplit(request.full_url)
    names = tuple(sorted(name for name, _value in parse_qsl(parsed.query)))
    return parsed.path, names


def test_each_success_is_one_forward_and_one_count(tmp_path, provider):
    count, calls, _, opener = provider
    budget = Budget(count)
    seen: list[str] = []

    def send() -> tuple[int, bytes, dict[str, str]]:
        seen.append("https://tiles.invalid/v1/3dtiles/root.json")
        return (200, b"SYN-tile", {})

    assert budget.request(3, send, lambda result: 200 <= result[0] < 300)[0] == 200
    assert seen == ["https://tiles.invalid/v1/3dtiles/root.json"]
    assert count.read_text() == "ready:0\npending:0\nready:1\n"
    app = create_app(tmp_path, opener=opener, count_path=count)
    status = invoke(app, "/api/photoreal/3dtiles/root.json", query=view_query(app))[0]
    assert status == 200
    assert len(calls) == 1
    assert count.read_text().endswith("ready:2\n")


def test_billed_body_failure_counts_once_and_the_retry_counts_again(tmp_path, provider):
    count, calls, _, _opener = provider
    mode = {"billed_failure": True}

    def opener(request: Request, timeout: float) -> Response:
        del timeout
        calls.append(request)
        assert urlsplit(request.full_url).hostname == HOST
        if mode["billed_failure"]:
            return BrokenBody(
                raw=json.dumps(ROOT).encode(),
                headers={"Content-Type": "application/json"},
            )
        return Response(
            raw=json.dumps(ROOT).encode(),
            headers={"Content-Type": "application/json"},
        )

    app = create_app(tmp_path, opener=opener, count_path=count)
    failed = invoke(app, "/api/photoreal/3dtiles/root.json", query=view_query(app))
    assert failed[0] == 404
    assert_error(failed[1], "NOT_FOUND", "operation_os_error")
    assert count.read_text() == "ready:0\npending:0\nready:1\n"
    assert len(calls) == 1
    mode["billed_failure"] = False
    retried = invoke(app, "/api/photoreal/3dtiles/root.json", query=view_query(app))
    assert retried[0] == 200
    assert len(calls) == 2
    assert count.read_text().endswith("ready:2\n")


def test_unbilled_http_error_is_forwarded_and_not_counted(tmp_path, provider):
    count, calls, response, opener = provider
    response.status = 500
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, raw, _headers = invoke(
        app, "/api/photoreal/3dtiles/root.json", query=view_query(app)
    )
    assert status == 404
    assert_error(raw, "NOT_FOUND", "response_unavailable")
    assert len(calls) == 1
    assert count.read_text() == "ready:0\npending:0\nready:0\n"


def test_direct_billed_failure_does_not_retry(provider):
    count, calls, _, _opener = provider
    budget = Budget(count)

    def send() -> tuple[int, bytes, dict[str, str]]:
        calls.append("https://tiles.invalid/once")
        raise BillableFailure

    with pytest.raises(BudgetFailure, match=r"^response_unavailable$"):
        budget.request(3, send, lambda result: True)
    assert calls == ["https://tiles.invalid/once"]
    assert count.read_text() == "ready:0\npending:0\nready:1\n"


def test_request_past_the_ceiling_never_reaches_the_stand_in(
    tmp_path, provider, monkeypatch
):
    count, calls, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", "1")
    seed_journal(count, 1)
    budget = Budget(count)
    with pytest.raises(BudgetFailure, match=r"^cap_reached$"):
        budget.request(1, lambda: calls.append("https://tiles.invalid/past"), bool)
    assert calls == []
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, raw, _headers = invoke(app, "/api/photoreal/views", "POST")
    assert status == 429
    assert_error(raw, "PROVIDER_CAP_REACHED", "cap_reached")
    modes = json.loads(invoke(app, "/api/map-modes")[1])
    assert modes["open"] == {"available": True, "reason": None}
    assert modes["photoreal"]["available"] is False
    assert modes["photoreal"]["reason"] == "cap_reached"
    assert modes["photoreal"]["meter"]["billable_requests"] == 1
    assert calls == []


def test_tile_query_is_unchanged_across_the_warning(tmp_path, provider, monkeypatch):
    count, calls, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", "10")
    shapes = []
    for total, warned in ((7, False), (8, True)):
        seed_journal(count, total)
        calls.clear()
        app = create_app(tmp_path, opener=opener, count_path=count)
        meter = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]["meter"]
        assert meter["warning"] is warned
        assert (
            invoke(app, "/api/photoreal/3dtiles/root.json", query=view_query(app))[0]
            == 200
        )
        shapes.append(query_shape(calls[-1]))
    assert shapes[0] == shapes[1]
    assert set(shapes[0][1]) <= {"key", "session"}
    assert "maximumScreenSpaceError" not in shapes[0][1]


def test_warning_stays_at_eighty_percent(tmp_path, provider, monkeypatch):
    count, _calls, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", "10")
    seed_journal(count, 8)
    unchanged = count.read_bytes()
    app = create_app(tmp_path, opener=opener, count_path=count)
    first = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]["meter"]
    second = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]["meter"]
    assert first["warning"] is True
    assert second == first
    assert first["ceiling_usd"] == format(SPEND_CEILING_USD, "f")
    assert count.read_bytes() == unchanged


def test_one_below_the_fraction_is_not_a_warning(tmp_path, provider, monkeypatch):
    count, _calls, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", "10")
    seed_journal(count, 7)
    app = create_app(tmp_path, opener=opener, count_path=count)
    meter = json.loads(invoke(app, "/api/map-modes")[1])["photoreal"]["meter"]
    assert meter["warning"] is False
    assert meter["billable_requests"] == 7


def test_successful_tiles_carry_the_server_meter_across_the_warning(
    tmp_path, provider, monkeypatch
):
    """The tile response carries Budget.meter. The provider query stays the same."""
    count, calls, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", "10")
    monkeypatch.setenv("EII_PHOTOREAL_PRICE_PER_THOUSAND", "7.125")
    seed_journal(count, 6)
    app = create_app(tmp_path, opener=opener, count_path=count)
    price = Decimal("7.125")
    shapes = []
    for expected, warned in ((7, False), (8, True)):
        status, raw, headers = invoke(
            app, "/api/photoreal/3dtiles/root.json", query=view_query(app)
        )
        assert status == 200
        assert raw != b'{"error":{"code":"NOT_FOUND"}}'
        meter = json.loads(headers[b"x-spend-meter"])
        assert meter == Budget(count).meter(10, price)
        assert meter["billable_requests"] == expected
        assert meter["warning"] is warned
        assert headers[b"x-spend-order"] == str(expected).encode()
        assert "SYN-" not in headers[b"x-spend-meter"].decode()
        assert b"SYN-" not in headers[b"x-spend-order"]
        shapes.append(query_shape(calls[-1]))
    assert shapes[0] == shapes[1]
    assert "maximumScreenSpaceError" not in shapes[0][1]


def test_unbilled_tile_has_no_spend_header(tmp_path, provider):
    count, calls, response, opener = provider
    response.status = 500
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, raw, headers = invoke(
        app, "/api/photoreal/3dtiles/root.json", query=view_query(app)
    )
    assert status == 404
    assert_error(raw, "NOT_FOUND", "response_unavailable")
    assert b"x-spend-meter" not in headers
    assert b"x-spend-order" not in headers
    assert len(calls) == 1
    assert count.read_text() == "ready:0\npending:0\nready:0\n"


def test_meter_failure_after_a_billed_tile_omits_the_header(
    tmp_path, provider, monkeypatch
):
    count, calls, _, opener = provider
    monkeypatch.setenv("EII_PHOTOREAL_LIMIT", "10")

    def unavailable(count, limit, price):
        del count, limit, price
        raise BudgetFailure("count_unavailable")

    monkeypatch.setattr("eii_product.api.map_modes.meter_for_count", unavailable)
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, raw, headers = invoke(
        app, "/api/photoreal/3dtiles/root.json", query=view_query(app)
    )
    assert status == 200
    assert raw != b'{"error":{"code":"NOT_FOUND"}}'
    assert b"x-spend-meter" not in headers
    assert b"x-spend-order" not in headers
    assert len(calls) == 1
    assert count.read_text().endswith("ready:1\n")


def test_satellite_tile_does_not_carry_a_provider_spend_header(tmp_path, provider):
    count, _calls, response, opener = provider
    response.headers["X-Spend-Meter"] = '{"billable_requests": 8}'
    app = create_app(tmp_path, opener=opener, count_path=count)
    status, raw, headers = invoke(app, "/api/imagery/tiles/0/0/0")
    assert status == 200
    assert raw == response.raw
    assert headers[b"x-attribution"] == b"SYN-credit"
    assert b"x-spend-meter" not in headers


@example(count=0, limit=10, price_units=6_000)
@example(count=1, limit=10, price_units=6_000)
@example(count=7, limit=10, price_units=6_000)
@example(count=8, limit=10, price_units=6_000)
@example(count=10, limit=10, price_units=6_000)
@example(count=0, limit=1, price_units=1)
@given(
    count=st.integers(min_value=0, max_value=40),
    limit=st.integers(min_value=1, max_value=40),
    price_units=st.integers(min_value=1, max_value=20_000),
)
def test_meter_matches_the_integer_oracle(
    count: int, limit: int, price_units: int
) -> None:
    with TemporaryDirectory() as directory:
        _meter_oracle(directory, count, limit, price_units)


def _meter_oracle(directory: str, count: int, limit: int, price_units: int) -> None:
    path = Path(directory) / "count"
    seed_journal(path, count)
    unchanged = path.read_bytes()
    price = Decimal(price_units) / Decimal(1000)
    meter = Budget(path).meter(limit, price)
    assert meter["billable_requests"] == count
    assert meter["request_limit"] == limit
    assert meter["warning"] is warning_oracle(count, limit)
    assert "e" not in meter["spend_usd"].lower()
    assert plain_usd(Decimal(meter["spend_usd"])) == plain_usd(
        spend_value(count, price_units)
    )
    assert meter["ceiling_usd"] == format(SPEND_CEILING_USD, "f")
    assert json.loads(encode_spend_meter(meter)) == meter
    assert path.read_bytes() == unchanged


def _header_names(response: object) -> set[str]:
    headers = getattr(response, "headers", None)
    if headers is None:
        raise AssertionError("response_without_headers")
    return {str(name).lower() for name in headers}


@example(status=200, leaked="")
@example(status=200, leaked='{"billable_requests":8}')
@example(status=500, leaked="not-json")
@example(status=404, leaked="")
@given(
    status=st.integers(min_value=100, max_value=599),
    leaked=st.text(
        alphabet="0123456789abcdefghijklmnopqrstuvwxyz{}[]:,. -",
        min_size=0,
        max_size=80,
    ),
)
def test_satellite_and_error_responses_omit_the_spend_header(
    status: int, leaked: str
) -> None:
    """A provider header is not a meter. An error does not gain one either."""
    headers = {
        "content-type": "image/png",
        "x-attribution": "SYN-credit",
        "x-spend-meter": leaked,
        "x-spend-order": "4",
    }
    meter = None if 200 <= status < 300 else '{"billable_requests":1}'
    response = deliver(
        (status, b"SYN-tile", headers),
        "SYN-key",
        require_credit=False,
        meter=meter,
    )
    assert "x-spend-meter" not in _header_names(response)
    assert "x-spend-order" not in _header_names(response)
    if 200 <= status < 300:
        assert response.status_code == status
        assert response.headers.get("x-attribution") == "SYN-credit"


def test_journal_order_token_refuses_a_negative_count() -> None:
    with pytest.raises(BudgetFailure, match=r"^count_unavailable$") as caught:
        journal_order_token(-1)
    assert str(caught.value) == "count_unavailable"


def test_meter_header_omits_both_when_the_step_was_not_captured() -> None:
    assert meter_header(lambda: (Decimal("6"), 10), None) is None


def test_an_order_token_without_a_meter_is_not_sent() -> None:
    response = deliver(
        (
            200,
            b"SYN-tile",
            {"content-type": "image/png", "x-attribution": "SYN-credit"},
        ),
        "SYN-key",
        require_credit=False,
        meter=None,
        order="8",
    )
    names = _header_names(response)
    assert names.isdisjoint({"x-spend-order", "x-spend-meter"})
    assert response.headers.get("x-attribution") == "SYN-credit"


def test_meter_header_uses_the_captured_step() -> None:
    issued = meter_header(lambda: (Decimal("7.125"), 10), 2)
    assert issued is not None
    assert issued["order"] == "2"
    assert json.loads(issued["meter"])["billable_requests"] == 2
    assert "warning" in json.loads(issued["meter"])


@example(count=0)
@example(count=1)
@example(count=9)
@example(count=10)
@example(count=99)
@example(count=100)
@given(count=st.integers(min_value=0, max_value=10_000))
def test_journal_order_token_is_the_canonical_decimal(count: int) -> None:
    token = journal_order_token(count)
    assert token == str(count)
    assert token == "0" or (not token.startswith("0") and token.isdecimal())
