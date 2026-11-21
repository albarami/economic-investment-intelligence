"""Intercepted public POSTs: delivered state, headers, redirects, pins and bounds."""

import io
from http.client import HTTPMessage
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs

import pytest
from custodian.tests.test_fc_register import page
from custodian.tests.test_fc_register_capture import pin

from eii_custodian.publicdata.fc_register.constants import SHAPE, TARGETS, URL
from eii_custodian.publicdata.fc_register.parse import project
from eii_custodian.publicdata.fetch import page_requests as requests
from eii_custodian.publicdata.fetch import transport
from eii_custodian.publicdata.fetch.certificate_pins import PinError


class Body(io.BytesIO):
    def __init__(self, body):
        super().__init__(body)
        self.headers = {}

    def geturl(self):
        return URL


def test_actual_post_is_bounded_and_contains_only_delivered_fields():
    fields = project(page(1), SHAPE).fields
    p = pin()
    sent = []

    def send(request, **kwargs):
        sent.append(request)
        assert request.method == "POST" and request.full_url == URL
        assert parse_qs(request.data.decode(), keep_blank_values=True) == {
            **{k: [v] for k, v in fields.items()},
            "__EVENTTARGET": [TARGETS[0]],
            "__EVENTARGUMENT": [""],
        }
        return Body(b"SYN-response")

    with (
        requests.page_requests((URL,), {p.host: p}),
        requests.delivered_state(fields, TARGETS[0]),
        transport.metadata_limit(3),
        patch("urllib.request.build_opener", return_value=SimpleNamespace(open=send)),
    ):
        response = transport.open_https(requests.PagePostback(URL, fields, TARGETS[0]))
    assert response.body == b"SYN-" and len(sent) == 1


@pytest.mark.parametrize(
    "header", ["Authorization", "Cookie", "__RequestVerificationToken"]
)
def test_post_header_refusals_precede_opener(header):
    fields = project(page(1), SHAPE).fields
    p = pin()
    with (
        requests.page_requests((URL,), {p.host: p}),
        requests.delivered_state(fields, TARGETS[0]),
        patch(
            "urllib.request.build_opener",
            return_value=SimpleNamespace(open=lambda *a, **k: Body(b"SYN-response")),
        ) as build,
    ):
        with pytest.raises(transport.TransportFault, match="blocked_host"):
            transport.open_https(
                requests.PagePostback(URL, fields, TARGETS[0]),
                headers={header: "SYN-secret"},
            )
        build.assert_not_called()


def test_post_token_and_missing_pin_refuse_before_send():
    fields = project(page(1), SHAPE).fields
    with (
        requests.page_requests((URL,), {}),
        requests.delivered_state(fields, TARGETS[0]),
        patch(
            "urllib.request.build_opener",
            return_value=SimpleNamespace(open=lambda *a, **k: Body(b"SYN-response")),
        ) as build,
    ):
        with pytest.raises(transport.TransportFault, match="blocked_host"):
            transport.open_https(
                requests.PagePostback(URL, fields, TARGETS[0]), token="SYN-secret"
            )
        with pytest.raises(PinError, match="certificate_chain_incomplete"):
            transport.open_https(requests.PagePostback(URL, fields, TARGETS[0]))
        build.assert_not_called()


@pytest.mark.parametrize(
    "target", [URL, "https://example.invalid/SYN", "https://eservices.qfc.qa/View/SYN"]
)
def test_post_redirect_never_sends_a_second_request(target):
    from urllib.request import Request

    guard = transport._redirect_guard([], postback=True)()
    p = pin()
    with (
        requests.page_requests((URL,), {p.host: p}),
        pytest.raises(transport.TransportFault, match="blocked_host"),
    ):
        guard.redirect_request(
            Request(URL, data=b"SYN-state"), None, 302, "SYN", HTTPMessage(), target
        )


@pytest.mark.parametrize("status", [403, 429, 503, 404])
def test_http_status_retained_without_upstream_diagnostics(status):
    fields = project(page(1), SHAPE).fields
    p = pin()

    def send(*args, **kwargs):
        raise HTTPError(URL, status, "SYN-secret-upstream", {}, None)

    with (
        requests.page_requests((URL,), {p.host: p}),
        requests.delivered_state(fields, TARGETS[0]),
        patch("urllib.request.build_opener", return_value=SimpleNamespace(open=send)),
    ):
        with pytest.raises(transport.TransportFault) as caught:
            transport.open_https(requests.PagePostback(URL, fields, TARGETS[0]))
    assert caught.value.status == status
    assert "SYN-secret" not in str(caught.value)


@pytest.mark.parametrize("wrapped", [False, True])
def test_tls_errors_are_terminal_never_connection_recovery(wrapped):
    import ssl
    from urllib.error import URLError

    fields = project(page(1), SHAPE).fields
    p = pin()
    fault = ssl.SSLCertVerificationError("SYN-upstream-secret")
    if wrapped:
        fault = URLError(fault)
    with (
        requests.page_requests((URL,), {p.host: p}),
        requests.delivered_state(fields, TARGETS[0]),
        patch(
            "urllib.request.build_opener",
            return_value=SimpleNamespace(
                open=lambda *a, **k: (_ for _ in ()).throw(fault)
            ),
        ),
    ):
        with pytest.raises((PinError, transport.TransportFault)) as caught:
            transport.open_https(requests.PagePostback(URL, fields, TARGETS[0]))
    assert isinstance(caught.value, PinError)
    assert str(caught.value) == "certificate_chain_incomplete"
    assert "SYN-upstream-secret" not in str(caught.value)
