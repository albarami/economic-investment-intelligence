"""S2-P77: every HTTPS context the fetch code builds offers ALPN ``http/1.1``.

A loopback TLS server with an invented self-signed certificate answers 403 to a
client hello without ALPN and 200 to one that offers ``http/1.1``. Only the
invented host ``page.invalid`` is used; its address is mapped to loopback in the
test, so no lookup or request leaves the machine.
"""

from __future__ import annotations

import hashlib
import socket
import ssl
import subprocess
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from custodian.tests.fixtures.invented_chain import intermediate_pem

from eii_custodian.publicdata.fetch import allowlist, kinds, transport
from eii_custodian.publicdata.fetch.certificate_pins import (
    Pin,
    page_transport,
    verified_context,
)
from eii_custodian.publicdata.fetch.page_requests import page_context, page_requests
from eii_custodian.publicdata.singles import tenders

HOST = "page.invalid"


@dataclass(frozen=True)
class Loopback:
    port: int
    cert_pem: bytes
    cert_file: Path
    offered: list[str | None]


@pytest.fixture(scope="module")
def certificate(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """An invented self-signed certificate for ``page.invalid`` and its key."""
    folder = tmp_path_factory.mktemp("SYN-alpn")
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "ec",
            "-pkeyopt",
            "ec_paramgen_curve:prime256v1",
            "-nodes",
            "-keyout",
            "server.key",
            "-out",
            "server.pem",
            "-days",
            "2",
            "-subj",
            "/CN=SYN page",
            "-addext",
            "subjectAltName=DNS:" + HOST,
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-addext",
            "keyUsage=critical,digitalSignature,keyCertSign",
            "-addext",
            "extendedKeyUsage=serverAuth",
        ],
        cwd=folder,
        check=True,
        capture_output=True,
    )
    return folder / "server.pem", folder / "server.key"


@pytest.fixture
def loopback(certificate: tuple[Path, Path]) -> Iterator[Loopback]:
    """403 when the client offered no ALPN, 200 when it offered ``http/1.1``."""
    cert_file, key_file = certificate
    offered: list[str | None] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            assert isinstance(self.connection, ssl.SSLSocket)
            selected = self.connection.selected_alpn_protocol()
            offered.append(selected)
            body = b"SYN page" if selected == "http/1.1" else b""
            self.send_response(200 if selected == "http/1.1" else 403)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert_file, key_file)
    server_context.set_alpn_protocols(["http/1.1"])
    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.socket = server_context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Loopback(
            server.server_address[1], cert_file.read_bytes(), cert_file, offered
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _status(context: ssl.SSLContext, server: Loopback) -> tuple[int, str | None]:
    """One GET over the context; the hostname check stays the context's own."""
    with socket.create_connection(("127.0.0.1", server.port), timeout=10) as raw:
        with context.wrap_socket(raw, server_hostname=HOST) as tls:
            tls.sendall(
                b"GET /SYN-page HTTP/1.1\r\nHost: page.invalid\r\n"
                b"Connection: close\r\n\r\n"
            )
            status_line = tls.makefile("rb").readline()
            return int(status_line.split()[1]), tls.selected_alpn_protocol()


def _assert_verifying(context: ssl.SSLContext) -> None:
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert not context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN


def _invented_pin(host: str) -> Pin:
    der = ssl.PEM_cert_to_DER_cert(intermediate_pem().decode("ascii"))
    return Pin(host, hashlib.sha256(der).hexdigest(), der, True)


def _trusting(context: ssl.SSLContext, server: Loopback) -> ssl.SSLContext:
    """Trust the loopback certificate in addition; nothing else is changed."""
    context.load_verify_locations(cadata=server.cert_pem.decode("ascii"))
    return context


def test_loopback_refuses_a_hello_without_alpn(loopback: Loopback) -> None:
    """The baseline: a verifying context that offers no ALPN gets 403."""
    bare = _trusting(ssl.create_default_context(), loopback)
    assert _status(bare, loopback) == (403, None)


def test_page_context_default_branch_offers_http11(loopback: Loopback) -> None:
    with page_requests((), {}):
        context = page_context(HOST)
    _assert_verifying(context)
    assert _status(_trusting(context, loopback), loopback) == (200, "http/1.1")


@pytest.mark.parametrize("host", ["www.qcb.gov.qa", "monaqasat.mof.gov.qa"])
def test_page_context_pinned_branch_offers_http11(
    loopback: Loopback, host: str
) -> None:
    pin = _invented_pin(host)
    with page_requests((), {host: pin}):
        context = page_context(host)
    _assert_verifying(context)
    assert pin.der in context.get_ca_certs(binary_form=True)
    assert _status(_trusting(context, loopback), loopback) == (200, "http/1.1")


def test_verified_context_offers_http11_and_keeps_tender_suite(
    loopback: Loopback,
) -> None:
    host = tenders.TENDER_HOST
    pin = _invented_pin(host)
    context = verified_context(host, pin)
    _assert_verifying(context)
    assert pin.der in context.get_ca_certs(binary_form=True)
    assert tenders._tls12_suites(context)[-1] == tenders.TENDER_SUITE
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2
    assert _status(_trusting(context, loopback), loopback) == (200, "http/1.1")


def test_verified_context_supplied_context_offers_http11(loopback: Loopback) -> None:
    supplied = ssl.create_default_context()
    context = verified_context(HOST, _invented_pin(HOST), context=supplied)
    assert context is supplied
    _assert_verifying(context)
    assert _status(_trusting(context, loopback), loopback) == (200, "http/1.1")


def test_tender_chain_context_offers_http11(loopback: Loopback, tmp_path: Path) -> None:
    chain = tmp_path / "SYN-intermediate.pem"
    chain.write_bytes(intermediate_pem())
    der = ssl.PEM_cert_to_DER_cert(intermediate_pem().decode("ascii"))
    context = tenders.chain_context(
        chain, hashlib.sha256(chain.read_bytes()).hexdigest()
    )
    _assert_verifying(context)
    assert der in context.get_ca_certs(binary_form=True)
    assert tenders._tls12_suites(context)[-1] == tenders.TENDER_SUITE
    assert _status(_trusting(context, loopback), loopback) == (200, "http/1.1")


def test_page_scoped_read_bounded_reaches_200(
    loopback: Loopback, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real page path: page_requests, page_transport and read_bounded."""
    url = f"https://{HOST}:{loopback.port}/SYN-page"
    original = socket.create_connection

    def to_loopback(address: tuple[str, int], *args: object, **kwargs: object):
        assert address == (HOST, loopback.port)
        return original(("127.0.0.1", loopback.port), *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(allowlist, "ALLOWED_HOSTS", frozenset({HOST}))
    monkeypatch.setattr(socket, "create_connection", to_loopback)
    # The existing trust seam of OpenSSL: the default verify paths name only the
    # invented certificate, so system roots are not consulted in this test.
    monkeypatch.setenv("SSL_CERT_FILE", str(loopback.cert_file))
    monkeypatch.setenv("SSL_CERT_DIR", str(loopback.cert_file.parent))
    with page_requests((url,), {}), page_transport(None, browser=True):
        response, failure = kinds.read_bounded(
            transport.open_https, lambda _seconds: None, url
        )
    assert failure is None
    assert response is not None
    assert response.status == 200
    assert response.body == b"SYN page"
    assert loopback.offered == ["http/1.1"]
