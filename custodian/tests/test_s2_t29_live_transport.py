"""Planted exact-host, request-frame and TLS-context isolation violations."""

import hashlib
import ssl
from http.client import HTTPMessage
from unittest.mock import patch
from urllib.request import Request

import pytest

from eii_custodian.publicdata.fetch.certificate_pins import Pin
from eii_custodian.publicdata.fetch.transport import open_https

PIN_HOSTS = [
    "www.qcb.gov.qa",
    "monaqasat.mof.gov.qa",
    "www.edu.gov.qa",
    "myschools.edu.gov.qa",
]


@pytest.mark.parametrize("host", PIN_HOSTS)
@pytest.mark.parametrize("plant", ["hash", "host", "approval", "missing", "tls"])
@pytest.mark.parametrize("role", ["initial", "redirect", "terms"])
def test_v2_pin_refuses_before_send(host, plant, role):
    from contextlib import nullcontext

    from eii_custodian.publicdata.fetch.certificate_pins import PinError
    from eii_custodian.publicdata.fetch.page_requests import page_requests
    from eii_custodian.publicdata.fetch.transport import _redirect_guard

    raw = b"SYN-intermediate"
    pin = Pin(host, hashlib.sha256(raw).hexdigest(), raw, True)
    if plant == "hash":
        pin = Pin(host, "SYN-wrong", raw, True)
    if plant == "host":
        pin = Pin("www.data.gov.qa", pin.sha256, raw, True)
    if plant == "approval":
        pin = Pin(host, pin.sha256, raw, False)
    url = "https://" + host + ("/SYN-terms" if role == "terms" else "/SYN-path")
    initial = "https://www.data.gov.qa/SYN-initial"
    context = ssl.create_default_context()
    if plant == "tls":
        context.check_hostname = False
    reason = {
        "hash": "certificate_chain_incomplete",
        "host": "certificate_host_mismatch",
        "approval": "certificate_review_pending",
        "missing": "certificate_chain_incomplete",
        "tls": "tls_verification_disabled",
    }[plant]
    # Redirects construct their own context; plant disabled verification there too.
    context_factory = (
        patch(
            "eii_custodian.publicdata.fetch.certificate_pins.ssl.create_default_context",
            return_value=context,
        )
        if plant == "tls"
        else nullcontext()
    )
    with (
        context_factory,
        patch("urllib.request.build_opener") as opener,
        patch("urllib.request.HTTPRedirectHandler.redirect_request") as redirect_base,
    ):
        with pytest.raises(PinError, match="^" + reason + "$"):
            with page_requests(
                (initial, url), {} if plant == "missing" else {host: pin}
            ):
                if role == "redirect":
                    _redirect_guard([])().redirect_request(
                        Request(initial), None, 302, "SYN", HTTPMessage(), url
                    )
                else:
                    open_https(url, ssl_context=context)
        assert opener.call_count == 0
        assert redirect_base.call_count == 0


def test_v2_unreviewed_redirect_zero_target_sends():
    from eii_custodian.publicdata.fetch.page_requests import page_requests
    from eii_custodian.publicdata.fetch.transport import TransportFault, _redirect_guard

    url = "https://www.data.gov.qa/SYN-initial"
    with page_requests((url,), {}):
        with pytest.raises(TransportFault, match="blocked_host"):
            _redirect_guard([])().redirect_request(
                Request(url),
                None,
                302,
                "SYN",
                HTTPMessage(),
                "https://www.data.gov.qa/SYN-unreviewed",
            )


def test_v2_full_chain_context_isolation():
    from eii_custodian.publicdata.fetch.page_requests import page_context, page_requests

    raw = b"SYN-intermediate"
    host = PIN_HOSTS[0]
    pin = Pin(host, hashlib.sha256(raw).hexdigest(), raw, True)
    with patch(
        "eii_custodian.publicdata.fetch.page_requests.verified_context"
    ) as verify:
        pinned = ssl.create_default_context()
        verify.return_value = pinned
        with page_requests(
            ("https://" + host + "/SYN", "https://visitqatar.com/SYN"), {host: pin}
        ):
            assert page_context(host) is pinned
            other = page_context("visitqatar.com")
            assert (
                other is not pinned
                and other.verify_mode == ssl.CERT_REQUIRED
                and other.check_hostname
            )
            assert verify.call_count == 1


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": "SYN credential"},
        {"Cookie": "SYN cookie"},
        {"__RequestVerificationToken": "SYN token"},
    ],
)
def test_page_credential_injection_refused_before_opener(headers):
    from eii_custodian.publicdata.fetch.page_requests import page_requests
    from eii_custodian.publicdata.fetch.transport import TransportFault

    url = "https://www.data.gov.qa/SYN-initial"
    with page_requests((url,), {}), patch("urllib.request.build_opener") as opener:
        with pytest.raises(TransportFault, match="blocked_host"):
            open_https(url, headers=headers)
        assert opener.call_count == 0
