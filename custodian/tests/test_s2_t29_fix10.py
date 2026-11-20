"""Fix-ten security plants: invented certificates and intercepted sends only."""

import hashlib
import json
import ssl
import subprocess
from dataclasses import replace
from http.client import HTTPMessage, HTTPSConnection
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import HTTPSHandler

import pytest
from custodian.tests.fixtures.invented_chain import intermediate_pem
from custodian.tests.test_s2_t29_live_shapes import STAMP, embedded, entry

from eii_custodian.publicdata.fetch import certificate_pins as certificates
from eii_custodian.publicdata.fetch import page_acquire, page_requests, transport
from eii_custodian.publicdata.singles import tenders

HOST = "www.edu.gov.qa"
URL = "https://" + HOST + "/SYN-page"
OTHER = "https://www.data.gov.qa/SYN-other"


@pytest.fixture(scope="module")
def invented_certs(tmp_path_factory):
    """Generate a disposable root, intermediate and leaf, never a host certificate."""
    folder = tmp_path_factory.mktemp("SYN-certificates")

    def run(*args):
        subprocess.run(["openssl", *args], cwd=folder, check=True, capture_output=True)

    run(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-nodes",
        "-keyout",
        "root.key",
        "-out",
        "root.pem",
        "-days",
        "2",
        "-subj",
        "/CN=SYN root",
        "-addext",
        "basicConstraints=critical,CA:TRUE",
    )
    result = {}
    for name, ca in (("intermediate", "TRUE"), ("leaf", "FALSE")):
        run(
            "req",
            "-new",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            name + ".key",
            "-out",
            name + ".csr",
            "-subj",
            "/CN=SYN " + name,
        )
        (folder / "extensions.cnf").write_text(
            "basicConstraints=critical,CA:" + ca + "\n"
            "keyUsage=critical,"
            + ("keyCertSign,cRLSign" if ca == "TRUE" else "digitalSignature")
            + "\n"
        )
        run(
            "x509",
            "-req",
            "-in",
            name + ".csr",
            "-CA",
            "root.pem",
            "-CAkey",
            "root.key",
            "-set_serial",
            "2" if ca == "TRUE" else "3",
            "-out",
            name + ".pem",
            "-days",
            "2",
            "-extfile",
            "extensions.cnf",
        )
    for name in ("root", "intermediate", "leaf"):
        run("x509", "-in", name + ".pem", "-outform", "DER", "-out", name + ".der")
        result[name] = (folder / (name + ".der")).read_bytes()
    return result


def make_pin(der, host=HOST):
    return certificates.Pin(host, hashlib.sha256(der).hexdigest(), der, True)


def config_file(tmp_path, der, host=HOST, source="SYN-source"):
    folder = tmp_path / "intake" / source
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SYN.der").write_bytes(der)
    return {
        "host": host,
        "sha256": hashlib.sha256(der).hexdigest(),
        "file": "SYN.der",
        "security_review": "APPROVED",
    }


@pytest.mark.parametrize("host", sorted(page_requests.PIN_HOSTS))
@pytest.mark.parametrize("opener", ["stream", "attempt"])
def test_f1_all_unscoped_openers_refuse(host, opener):
    url = "https://" + host + "/SYN-unscoped"
    with patch("urllib.request.build_opener") as build:
        with pytest.raises(
            certificates.PinError, match=r"^certificate_chain_incomplete$"
        ):
            if opener == "stream":
                with transport.open_https_stream(url, reviewed_urls=(url,)):
                    pytest.fail("unscoped stream opened")
            else:
                transport.open_attempt(
                    transport.PreparedRequest(url, "X-SYN", "SYN", "SYN")
                )
        build.assert_not_called()


def test_f2_tender_requires_root_chain(tmp_path, monkeypatch):
    class Context:
        verify_mode = ssl.CERT_REQUIRED
        check_hostname = True
        verify_flags = ssl.VERIFY_X509_PARTIAL_CHAIN
        # The suite list a real context holds (LIVE-S2.r5 added the host's suite).
        minimum_version = ssl.TLSVersion.TLSv1_2
        security_level = 2
        suites = ("ECDHE-RSA-AES128-GCM-SHA256",)

        def get_ciphers(self):
            return [{"name": n, "protocol": "TLSv1.2"} for n in self.suites]

        def set_ciphers(self, spec):
            self.suites = tuple(n for n in spec.split(":") if not n.startswith("@"))

        def load_verify_locations(self, *, cadata):
            # S2-T08 part B, mismatch 7: trust is added from the inspected
            # bytes, never from the path, and the file is an invented
            # intermediate because a text stand-in is now refused.
            assert cadata == ssl.PEM_cert_to_DER_cert(chain.read_text())

    chain = tmp_path / "SYN.pem"
    chain.write_bytes(intermediate_pem())
    context = Context()
    monkeypatch.setattr(tenders.ssl, "create_default_context", lambda: context)
    assert (
        tenders.chain_context(chain, hashlib.sha256(chain.read_bytes()).hexdigest())
        is context
    )
    assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN


@pytest.mark.parametrize("scoped", [False, True, "pin"])
def test_f2_supplied_partial_chain_refuses(scoped, invented_certs):
    context = ssl.create_default_context()
    context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    with (
        page_requests.page_requests((OTHER,), {})
        if scoped is True
        else certificates.page_transport(
            make_pin(invented_certs["intermediate"], "www.data.gov.qa")
            if scoped == "pin"
            else None
        ),
        patch("urllib.request.build_opener") as build,
    ):
        response = build.return_value.open.return_value.__enter__.return_value
        response.read.return_value = b"SYN body"
        response.geturl.return_value = OTHER
        response.headers = {}
        with pytest.raises(
            certificates.PinError, match=r"^certificate_chain_incomplete$"
        ):
            transport.open_https(OTHER, ssl_context=context)
        build.assert_not_called()


def test_f3_load_pin_rejects_other_host(tmp_path, invented_certs):
    config = config_file(tmp_path, invented_certs["intermediate"], "www.data.gov.qa")
    with pytest.raises(certificates.PinError, match=r"^certificate_host_mismatch$"):
        certificates.load_pin(tmp_path, "SYN-source", config)


def test_f3_page_context_ignores_non_pin_host(invented_certs):
    pin = make_pin(invented_certs["intermediate"], "www.data.gov.qa")
    with (
        page_requests.page_requests((OTHER,), {pin.host: pin}),
        patch.object(
            page_requests, "verified_context", wraps=certificates.verified_context
        ) as verify,
    ):
        context = page_requests.page_context(pin.host)
        verify.assert_not_called()
        assert pin.der not in context.get_ca_certs(binary_form=True)
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN


def test_f3_fetch_pin_must_belong_to_reviewed_host(tmp_path, invented_certs):
    dec, body, _ = embedded()
    config = config_file(
        tmp_path, invented_certs["intermediate"], source=entry(dec).source_id
    )
    dec["pins"] = [config]
    calls = []

    def send(url):
        calls.append(url)
        return transport.Response(url, body, ())

    with pytest.raises(certificates.PinError, match=r"^certificate_host_mismatch$"):
        page_acquire.fetch(
            entry(dec), dec, send, tmp_path, lambda: STAMP, lambda _: None
        )
    assert calls == []


@pytest.mark.parametrize("kind", ["leaf", "root", "two", "trailing", "invalid"])
def test_f3_load_pin_requires_one_nonselfsigned_ca(tmp_path, invented_certs, kind):
    der = {
        "leaf": invented_certs["leaf"],
        "root": invented_certs["root"],
        "two": invented_certs["intermediate"] + invented_certs["root"],
        "trailing": invented_certs["intermediate"] + b"SYN trailing bytes",
        "invalid": b"SYN not a certificate",
    }[kind]
    config = config_file(tmp_path, der)
    with pytest.raises(certificates.PinError, match=r"^certificate_chain_incomplete$"):
        certificates.load_pin(tmp_path, "SYN-source", config)


def test_f3_load_pin_valid_intermediate(tmp_path, invented_certs):
    der = invented_certs["intermediate"]
    config = config_file(tmp_path, der)
    assert certificates.load_pin(tmp_path, "SYN-source", config) == make_pin(der)


@pytest.mark.parametrize("host", sorted(page_requests.PIN_HOSTS))
@pytest.mark.parametrize("reverse", [False, True])
def test_f4_handler_selects_context_each_redirect(host, reverse, invented_certs):
    pin = make_pin(invented_certs["intermediate"], host)
    pinned_url = (
        "https://"
        + host
        + (
            "/qfcpublicregister/publicregister.aspx"
            if host == "eservices.qfc.qa"
            else "/SYN-pin"
        )
    )
    initial, target = (OTHER, pinned_url) if reverse else (pinned_url, OTHER)
    sent = []

    class Body:
        def __init__(self):
            self.headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit=None):
            body = b"SYN body" if not getattr(self, "done", False) else b""
            self.done = True
            return body

        def geturl(self):
            return target

    def do_open(handler, connection, request, *, context):
        assert connection is HTTPSConnection
        expected_pin = request.host == host
        assert (pin.der in context.get_ca_certs(binary_form=True)) == expected_pin
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN
        sent.append((request.full_url, context))
        return Body()

    def build(guard, handler):
        def open_request(request, *, timeout):
            handler.https_open(request)
            redirected = guard().redirect_request(
                request, None, 302, "SYN", HTTPMessage(), target
            )
            assert redirected is not None
            return handler.https_open(redirected)

        return SimpleNamespace(open=open_request)

    with (
        page_requests.page_requests((initial, target), {host: pin}),
        patch.object(HTTPSHandler, "do_open", do_open),
        patch("urllib.request.build_opener", build),
    ):
        assert transport.open_https(initial).body == b"SYN body"
    assert [u for u, _ in sent] == [initial, target]
    assert sent[0][1] is not sent[1][1]


def capture_receipt(tmp_path, pin):
    folder = tmp_path / "intake" / "SYN-source"
    folder.mkdir(parents=True)
    body = b"SYN capture"
    (folder / "SYN.html").write_bytes(body)
    record = {
        "file": "SYN.html",
        "initial_url": URL,
        "final_url": URL,
        "hops": [],
        "tool": "SYN browser",
        "captured_utc": STAMP,
        "sha256": hashlib.sha256(body).hexdigest(),
        "intermediate_host": pin.host,
        "intermediate_sha256": pin.sha256,
        "tls_verified": True,
        "access": "visitor",
    }
    return folder / "capture.json", record


@pytest.mark.parametrize("plant", ["host", "digest"])
def test_f4_load_capture_binds_configured_pin(tmp_path, invented_certs, plant):
    pin = make_pin(invented_certs["intermediate"])
    path, record = capture_receipt(tmp_path, pin)
    record["intermediate_host" if plant == "host" else "intermediate_sha256"] = (
        "SYN wrong"
    )
    path.write_text(json.dumps(record))
    with pytest.raises(certificates.PinError, match=r"^capture_evidence_missing$"):
        certificates.load_capture(tmp_path, "SYN-source", pin)


def test_f4_load_capture_valid_and_absent(tmp_path, invented_certs):
    pin = make_pin(invented_certs["intermediate"])
    assert certificates.load_capture(tmp_path, "SYN-source", pin) is None
    path, record = capture_receipt(tmp_path, pin)
    path.write_text(json.dumps(record))
    capture = certificates.load_capture(tmp_path, "SYN-source", pin)
    response, evidence = certificates.admit_capture(capture, URL)
    assert (
        response.body == b"SYN capture"
        and evidence["intermediate_sha256"] == pin.sha256
    )


@pytest.mark.parametrize("part", ["file", "source", "intake"])
def test_f4_intake_links_refuse(tmp_path, part):
    intake = tmp_path / "intake"
    source = intake / "SYN-source"
    source.mkdir(parents=True)
    file = source / "SYN.der"
    file.write_bytes(b"SYN")
    original = {"file": file, "source": source, "intake": intake}[part]
    moved = original.with_name("SYN-real-" + part)
    original.rename(moved)
    original.symlink_to(moved, target_is_directory=part != "file")
    with pytest.raises(certificates.PinError, match=r"^intake_path_refused$"):
        certificates.intake_file(tmp_path, "SYN-source", "SYN.der")


@pytest.mark.parametrize("plant", ["missing", "wrong"])
def test_f4_actual_terms_role_refuses(tmp_path, invented_certs, plant):
    dec, body, _ = embedded()
    dec["reviewed_urls"].append(URL)
    row = replace(entry(dec), terms_url=URL)
    if plant == "wrong":
        config = config_file(
            tmp_path, invented_certs["intermediate"], source=row.source_id
        )
        dec["pins"] = [config]
    calls = []
    checked_hosts = []
    original = page_acquire.page_context

    def terms_context(host):
        checked_hosts.append(host)
        if plant == "wrong":
            with page_requests.page_requests(
                (URL,),
                {
                    HOST: replace(
                        make_pin(invented_certs["intermediate"]), sha256="0" * 64
                    )
                },
            ):
                return original(host)
        return original(host)

    def send(url):
        calls.append(url)
        assert url == dec["url"]
        assert page_requests.active()
        return transport.Response(url, body, ())

    with patch.object(page_acquire, "page_context", terms_context):
        with pytest.raises(
            certificates.PinError, match=r"^certificate_chain_incomplete$"
        ):
            page_acquire.fetch(row, dec, send, tmp_path, lambda: STAMP, lambda _: None)
    assert calls == [dec["url"]]
    assert checked_hosts == [HOST]
    assert not (tmp_path / row.key / "index").exists()


@pytest.mark.parametrize("boundary", ["certificate", "page"])
def test_f4_verify_mode_alone_refuses(invented_certs, boundary):
    # Real SSLContext prevents CERT_NONE + check_hostname; this narrow stand-in
    # isolates verify_mode so the other operand cannot satisfy the refusal.
    class Context:
        verify_mode = ssl.CERT_NONE
        check_hostname = True
        verify_flags = 0

        def load_verify_locations(self, **kwargs):
            pytest.fail("disabled verification reached certificate loading")

    with pytest.raises(certificates.PinError, match=r"^tls_verification_disabled$"):
        if boundary == "certificate":
            certificates.verified_context(
                HOST, make_pin(invented_certs["intermediate"]), context=Context()
            )
        else:
            page_requests.page_context("www.data.gov.qa", Context())


def test_f4_capture_wrong_pin_digest(invented_certs):
    pin = replace(make_pin(invented_certs["intermediate"]), sha256="0" * 64)
    body = b"SYN capture"
    value = certificates.Capture(
        body,
        URL,
        URL,
        (),
        "SYN browser",
        STAMP,
        hashlib.sha256(body).hexdigest(),
        pin,
        True,
        "visitor",
    )
    assert value.pin.der
    with pytest.raises(certificates.PinError, match=r"^certificate_chain_incomplete$"):
        certificates.admit_capture(value, URL)
