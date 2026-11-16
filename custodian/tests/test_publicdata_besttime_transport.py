"""Offline method and secret boundary tests with an invented environment."""

import io
import json
import traceback
import urllib.error
from typing import ClassVar
from unittest.mock import patch

import pytest

from eii_custodian.publicdata.busyness.parse import FORECAST_URL, QUERY_URL
from eii_custodian.publicdata.fetch.transport import (
    KeyedRequest,
    TransportFault,
    open_https,
)


def request(url=FORECAST_URL):
    return KeyedRequest(
        url,
        "POST" if url == FORECAST_URL else "GET",
        {"venue_name": "Invented cafe"},
        {
            "BESTTIME_API_KEY_PRIVATE": "SYN-invented-private",
            "BESTTIME_API_KEY_PUBLIC": "SYN-invented-public",
        },
    )


@pytest.mark.parametrize(
    "url,method,key",
    [(FORECAST_URL, "POST", "api_key_private"), (QUERY_URL, "GET", "api_key_public")],
)
def test_besttime_transport_method_and_key_in_memory(url, method, key):
    value = request(url)
    assert "SYN-invented" not in repr(value)
    assert str(value) == url

    class Answer(io.BytesIO):
        headers: ClassVar = {"ETag": "SYN-invented-private"}

        def geturl(self):
            return url

    def send(req, timeout):
        assert req.method == method
        assert key + "=" in req.full_url
        return Answer(
            json.dumps(
                {
                    "request_url": req.full_url,
                    "nested": {"arbitrary_api_key": "SYN-invented-private"},
                    "status": "Error",
                    "venue_info": {},
                }
            ).encode()
        )

    with patch("urllib.request.build_opener") as opener:
        opener.return_value.open.side_effect = send
        response = open_https(value)
    assert response.etag is None
    assert "request_url" not in response.body.decode()
    assert "api_key" not in response.body.decode()
    assert "SYN-invented" not in repr(response)


def test_besttime_transport_exception_has_no_secret_chain():
    value = request()
    with patch("urllib.request.build_opener") as opener:
        opener.return_value.open.side_effect = urllib.error.URLError(
            "SYN-invented-private"
        )
        with pytest.raises(TransportFault) as caught:
            open_https(value)
    rendered = "".join(traceback.format_exception(caught.value))
    assert "SYN-invented-private" not in rendered
    assert caught.value.__context__ is None
    assert caught.value.url == FORECAST_URL


def test_besttime_transport_redirect_refused_before_following():
    value = request()

    def make(handler):
        class Opener:
            def open(self, req, timeout):
                handler().redirect_request(
                    req, io.BytesIO(), 302, "", {}, "https://evil.example/path"
                )

        return Opener()

    with patch("urllib.request.build_opener", side_effect=make):
        with pytest.raises(TransportFault, match="blocked_host"):
            open_https(value)


def test_besttime_original_body_hash_survives_secret_projection():
    import hashlib

    value = request()
    raw = json.dumps(
        {"status": "Error", "venue_info": {}, "request_url": "discard"}
    ).encode()

    class Answer(io.BytesIO):
        headers: ClassVar = {}

        def geturl(self):
            return str(value)

    with patch("urllib.request.build_opener") as opener:
        opener.return_value.open.return_value = Answer(raw)
        response = open_https(value)
    assert response.body_sha256 == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    "url,method,env",
    [
        (FORECAST_URL, "GET", {"BESTTIME_API_KEY_PRIVATE": "SYN-key"}),
        (FORECAST_URL, "POST", {}),
        (FORECAST_URL + "/unknown", "POST", {}),
    ],
)
def test_besttime_transport_refuses_wrong_endpoint_method_or_missing_key(
    url, method, env
):
    with patch("urllib.request.build_opener") as opener:
        with pytest.raises(TransportFault):
            open_https(KeyedRequest(url, method, {}, env))
        opener.return_value.open.assert_not_called()


def test_besttime_allowed_host_redirect_is_still_second_send():
    def make(handler):
        class Opener:
            def open(self, req, timeout):
                result = handler().redirect_request(
                    req, io.BytesIO(), 302, "", {}, QUERY_URL
                )
                pytest.fail("redirect would be sent: " + str(result is not None))

        return Opener()

    with patch("urllib.request.build_opener", side_effect=make):
        with pytest.raises(TransportFault):
            open_https(request())


@pytest.mark.parametrize("kind", ["http", "network"])
@pytest.mark.parametrize("keyed", [True, False])
def test_besttime_transport_fault_branches(kind, keyed):
    value = request() if keyed else "https://besttime.app/terms"
    fault = (
        urllib.error.HTTPError(str(value), 403, "SYN-invented-private", {}, None)
        if kind == "http"
        else urllib.error.URLError("SYN-invented-private")
    )
    with patch("urllib.request.build_opener") as opener:
        opener.return_value.open.side_effect = fault
        with pytest.raises(TransportFault) as caught:
            open_https(value)
    assert caught.value.kind == ("http" if kind == "http" else "unreachable")
    if keyed:
        assert caught.value.__context__ is None
        assert "SYN-invented-private" not in "".join(
            traceback.format_exception(caught.value)
        )
    else:
        assert caught.value.__cause__ is fault


def test_besttime_malformed_body_retains_no_secret():
    class Answer(io.BytesIO):
        headers: ClassVar = {}

        def geturl(self):
            return FORECAST_URL

    with patch("urllib.request.build_opener") as opener:
        opener.return_value.open.return_value = Answer(b"not json SYN-invented-private")
        result = open_https(request())
    assert result.body == b"null"
