"""Invented transport checks: no real opener or external request is used."""

from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request

import pytest
from product.tests.test_map_modes import Response
from product.tests.test_map_modes import provider as provider

from eii_product.photoreal_tiles import proxy


@pytest.mark.parametrize(
    "base",
    [
        "http://fixture.invalid/",
        "https://[SYN-invalid/",
        "https:///SYN-path",
        "https://fixture.invalid/./",
        "https://fixture.invalid/../",
    ],
)
def test_bad_base_is_refused(base):
    assert proxy.valid_base(base) is False


@pytest.mark.parametrize("satellite,parameter", [(False, "key"), (True, "token")])
def test_fetch_exact_request_and_response(provider, satellite, parameter):
    _, calls, _, opener = provider
    assert proxy.fetch_tile(
        opener,
        "https://fixture.invalid/SYN-X///",
        "3dtiles/root.json",
        "SYN-unused",
        satellite=satellite,
    ) == (
        200,
        b"SYN-tile",
        {"content-type": "image/png", "x-attribution": "SYN-credit"},
    )
    assert len(calls) == 1
    assert (
        calls[0].full_url
        == "https://fixture.invalid/SYN-X/3dtiles/root.json?"
        + parameter
        + "=SYN-unused"
    )
    assert calls[0].header_items() == [("Cache-control", "no-store")]
    assert calls[0].get_method() == "GET"


def test_satellite_metadata_request_exactly(provider):
    _, calls, _, opener = provider
    assert (
        proxy.satellite_credit(opener, "https://fixture.invalid/SYN-X///", "SYN-unused")
        == "SYN-credit"
    )
    assert len(calls) == 1
    assert calls[0].full_url == "https://fixture.invalid/SYN-X?f=json&token=SYN-unused"
    assert calls[0].header_items() == [("Cache-control", "no-store")]
    assert calls[0].get_method() == "GET"


def test_http_error_has_empty_body_and_closes():
    body = BytesIO(b"SYN-private-error")
    error = HTTPError("https://fixture.invalid/", 418, "SYN-error", {}, body)

    def opener(request, timeout):
        raise error

    assert proxy.fetch_tile(
        opener,
        "https://fixture.invalid/",
        "3dtiles/root.json",
        "SYN-unused",
        satellite=False,
    ) == (418, b"", {})
    assert body.closed


@pytest.mark.parametrize("satellite", [False, True])
def test_transport_error_has_closed_result(satellite):
    def opener(request, timeout):
        raise OSError("SYN-transport")

    def fetch():
        return proxy.fetch_tile(
            opener,
            "https://fixture.invalid/",
            "3dtiles/root.json",
            "SYN-unused",
            satellite=satellite,
        )

    if satellite:
        assert fetch() == (503, b"", {})
    else:
        # An unknown billable outcome must leave the journal pending.
        with pytest.raises(proxy.AddressFailure, match=r"^NOT_FOUND$"):
            fetch()


def test_tile_opener_passes_request_timeout_and_redirect_guard(monkeypatch):
    # Patch the constructor before calling the production wrapper: no network.
    response = Response()
    transport = Mock()
    transport.open.return_value = response
    constructor = Mock(return_value=transport)
    monkeypatch.setattr(proxy, "build_opener", constructor)
    request = Request("https://fixture.invalid/SYN-tile")
    assert proxy.tile_opener(request, 2.5) is response
    constructor.assert_called_once()
    args, kwargs = constructor.call_args
    assert len(args) == 1
    assert type(args[0]) is proxy.NoRedirect
    assert kwargs == {}
    transport.open.assert_called_once_with(request, timeout=2.5)


@pytest.mark.parametrize(
    "raw,marker,expected",
    [
        (b"SYN-binary", "XXXX", True),
        (b"SYN-ull", "SYN-unused", True),
        (b"SYN-used", "XSYN-used", True),
        (b"SYN-used", "SYN-usedX", True),
        (b"\\u00e9", "\u00e9", False),
        (b'{"echo":"\\u00E9"}', "\u00e9", False),
    ],
)
def test_safe_response_escape_boundaries(raw, marker, expected):
    assert proxy.safe_response(raw, {}, marker) is expected
