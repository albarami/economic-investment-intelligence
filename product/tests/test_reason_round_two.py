"""Round-two regression plants: exact closed reasons at real refusal boundaries."""

import json
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from hypothesis import given
from hypothesis import strategies as st
from product.tests.reason_contract import assert_error
from product.tests.test_map_modes import Response, invoke, view_query
from product.tests.test_map_modes import provider as provider
from product.tests.test_reason_part_b import playbook_failure, sector_failure

from eii_core.reason_codes import CODES
from eii_core.reasons import reason
from eii_product.api import map_modes, results
from eii_product.imagery_provider.address import AddressFailure
from eii_product.photoreal_tiles import proxy
from eii_product.photoreal_tiles.limit import BillableFailure
from eii_product.photoreal_tiles.native import NativeFailure, NativeViews
from eii_product.store.protocol import StoreRefusal
from eii_product.tools.make_area import ArgumentError


def map_app(provider, *, key_reader=None):
    count, _, _, opener = provider
    app = FastAPI()
    app.include_router(
        map_modes.build_router(
            key_reader or (lambda: "SYN-unused"), lambda: False, opener, count
        )
    )
    return app


@pytest.mark.parametrize("satellite", [False, True])
@pytest.mark.parametrize("code", ["cap_reached", "source_missing"])
def test_provider_header_cannot_choose_error(
    provider, monkeypatch, capsys, satellite, code
):
    key = "SYN-key-echo"
    count, _, response, opener = provider
    monkeypatch.setattr(map_modes, "read_maptile_api_key", lambda: key)
    response.raw = key.encode()
    response.headers["X-EII-Error-Code"] = code
    app = map_app((count, [], response, opener), key_reader=lambda: key)
    # The proxy must strip the header even when a downstream cap check also refuses it.
    with patch.object(
        map_modes, "safe_response", wraps=map_modes.safe_response
    ) as safe:
        if satellite:
            with patch.object(map_modes, "satellite_credit", return_value="SYN-credit"):
                result = invoke(app, "/api/imagery/tiles/0/0/0")
        else:
            result = invoke(
                app, "/api/photoreal/3dtiles/root.json", query=view_query(app)
            )
    assert result[0] == 404
    assert_error(result[1], "NOT_FOUND", "response_unavailable")
    assert all("x-eii-error-code" not in call.args[1] for call in safe.call_args_list)
    log = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert log[-1]["error_code"] == "response_unavailable"
    assert key not in result[1].decode()
    assert all(key not in json.dumps(line) for line in log)


@given(code=st.one_of(st.sampled_from(sorted(CODES)), st.text()))
def test_provider_header_is_never_a_diagnostic(code):
    result = proxy.fetch_tile(
        lambda *args, **kwargs: Response(
            headers={"X-EII-Error-Code": code, "Content-Type": "image/png"}
        ),
        "https://tiles.invalid",
        "tile/0/0/0",
        "SYN-key",
        satellite=True,
    )
    assert result == (200, b"SYN-tile", {"content-type": "image/png"})


@pytest.mark.parametrize("path", ["-1/0/0", "31/0/0", "1/2/0", "1/0/2"])
def test_coordinate_refusal_keeps_default(provider, path):
    status, raw, _ = invoke(map_app(provider), "/api/imagery/tiles/" + path)
    assert status == 404
    assert_error(raw, "NOT_FOUND", "NOT_FOUND")


@pytest.mark.parametrize("site", ["satellite", "photoreal"])
def test_key_disappearing_after_availability(provider, monkeypatch, site):
    reader = Mock(side_effect=["SYN-unused", None])
    if site == "satellite":
        app = map_app(provider, key_reader=reader)
        result = invoke(app, "/api/imagery/tiles/0/0/0")
    else:
        monkeypatch.setattr(map_modes, "read_maptile_api_key", reader)
        app = map_app(provider)
        with patch.object(NativeViews, "contains", return_value=True):
            result = invoke(
                app, "/api/photoreal/3dtiles/root.json", query="view=SYN-view"
            )
    assert result[0] == 404
    assert_error(result[1], "NOT_FOUND", "no_key")


@pytest.mark.parametrize("credit", ["", "SYN-\ncredit", "SYN-écredit"])
def test_credit_refusal_is_specific(provider, credit):
    app = map_app(provider)
    with patch.object(map_modes, "satellite_credit", return_value=credit):
        status, raw, _ = invoke(app, "/api/imagery/tiles/0/0/0")
    assert status == 404
    assert_error(raw, "NOT_FOUND", "attribution_unavailable")


def test_playbook_packaging_failure_is_internal(tmp_path):
    assert (
        playbook_failure("D37", tmp_path, FileNotFoundError("SYN-missing"), 500)
        == "operation_os_error"
    )


@pytest.mark.parametrize(
    "site,fault,expected",
    [
        ("target", NativeFailure(), "native-view-unavailable"),
        ("satellite_credit", TimeoutError("SYN-private"), "operation_timeout"),
        ("fetch_tile", AddressFailure(), "NOT_FOUND"),
    ],
)
def test_map_inner_refusal_routes(provider, site, fault, expected):
    app = map_app(provider)
    with patch.object(map_modes, "refuse", wraps=map_modes.refuse) as refused:
        _map_inner_refusal(app, site, fault, expected)
    refused.assert_called_once_with(expected)


def _map_inner_refusal(app, site, fault, expected):
    if site == "target":
        query = view_query(app)
        with patch.object(NativeViews, "target", side_effect=fault):
            status, raw, _ = invoke(
                app, "/api/photoreal/3dtiles/root.json", query=query
            )
    else:
        with patch.object(map_modes, "satellite_credit", return_value="SYN-credit"):
            with patch.object(map_modes, site, side_effect=fault):
                status, raw, _ = invoke(app, "/api/imagery/tiles/0/0/0")
    assert status == 404
    assert_error(raw, "NOT_FOUND", expected)


@pytest.mark.parametrize(
    "fault,status,code",
    [
        (ArgumentError("INVALID_ARGUMENT"), 422, "INVALID_ARGUMENT"),
        (StoreRefusal("STORE_UNAVAILABLE"), 503, "STORE_UNAVAILABLE"),
    ],
)
def test_class_placeholder_keeps_default(fault, status, code):
    response = results.error_response(fault)
    assert response.status_code == status
    assert_error(response.body, code, code.lower())


@pytest.mark.parametrize(
    "column", ["unit", "activity", "geography", "topic", "scenario", "cursor"]
)
def test_missing_release_column_is_not_an_input_field(column):
    assert sector_failure("D44", KeyError(column)) == "input_key_missing"


@pytest.mark.parametrize(
    "headers,expected",
    [
        ({}, "response_unavailable"),
        ({"x-eii-error-code": "SYN-private"}, "response_unavailable"),
        ({"x-eii-error-code": "cap_reached"}, "response_unavailable"),
        ({"x-eii-error-code": "operation_timeout"}, "operation_timeout"),
    ],
)
def test_transport_reason_cannot_claim_budget_cap(headers, expected):
    response = map_modes.deliver((503, b"", headers), "SYN-key", require_credit=False)
    assert response.status_code == 404
    assert_error(response.body, "NOT_FOUND", expected)


@pytest.mark.parametrize("kind", ["satellite", "photoreal"])
@pytest.mark.parametrize(
    "leaf", ["status", "raw", "Content-Type", "X-Attribution", "X-EII-Error-Code"]
)
@pytest.mark.parametrize("hostile", [{"toString": None}, 7, None, []])
def test_every_provider_leaf_is_closed_or_rendered(kind, leaf, hostile):
    response = Response(
        headers={
            "Content-Type": "image/png" if kind == "satellite" else "model/gltf-binary",
            "X-Attribution": "SYN-credit",
            "X-EII-Error-Code": "cap_reached",
        }
    )
    if leaf in {"status", "raw"}:
        setattr(response, leaf, hostile)
    else:
        response.headers[leaf] = hostile
    try:
        result = proxy.fetch_tile(
            lambda *args, **kwargs: response,
            "https://tiles.invalid",
            "tile/0/0/0",
            "SYN-key",
            satellite=kind == "satellite",
        )
    except (AddressFailure, BillableFailure) as error:
        assert kind == "photoreal" and leaf in {"status", "raw"}
        assert reason(error) == "NOT_FOUND"
        return
    rendered = map_modes.deliver(result, "SYN-key", require_credit=True)
    if rendered.status_code == 200:
        assert rendered.body == b"SYN-tile"
        assert "x-eii-error-code" not in result[2]
    else:
        expected = (
            "NOT_FOUND"
            if leaf == "raw" or (leaf == "status" and hostile != 7)
            else "response_unavailable"
        )
        assert rendered.status_code == 404
        assert_error(rendered.body, "NOT_FOUND", expected)


@pytest.mark.parametrize("credit", [None, "", "SYN-\ncredit", "SYN-écredit"])
def test_deliver_credit_refusal(credit):
    headers = {"content-type": "image/png"}
    if credit is not None:
        headers["x-attribution"] = credit
    result = map_modes.deliver(
        (200, b"SYN-tile", headers), "SYN-key", require_credit=True
    )
    assert result.status_code == 404
    assert_error(result.body, "NOT_FOUND", "attribution_unavailable")
