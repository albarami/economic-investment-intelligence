"""Exact-host issuing-intermediate DER pins; system roots and hostname checks stay on.

The tender reader retains its existing PEM-byte convention. This adapter does not
change that convention or enable partial-chain trust. New pins require independent
security approval in reviewed configuration before they can reach the transport.
"""

from __future__ import annotations

import hashlib
import json
import ssl
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path

from .allowlist import approve, host_of
from .snapshots import utc
from .transport import Response


@dataclass(frozen=True)
class Pin:
    host: str
    sha256: str
    der: bytes = field(repr=False)
    approved: bool = False


class PinError(ValueError):
    """A closed diagnostic with no certificate or upstream error text."""


def validate_pin(host: str, pin: Pin) -> None:
    """Check binding before constructing a TLS context or opening a request."""
    if host != pin.host or not host or host != host.lower():
        raise PinError("certificate_host_mismatch")
    if not pin.der or hashlib.sha256(pin.der).hexdigest() != pin.sha256:
        raise PinError("certificate_chain_incomplete")
    if pin.approved is not True:
        raise PinError("certificate_review_pending")


def verified_context(
    host: str, pin: Pin, *, context: ssl.SSLContext | None = None
) -> ssl.SSLContext:
    """Add the pinned intermediate to the normal verifying system-root context."""
    validate_pin(host, pin)
    result = context if context is not None else ssl.create_default_context()
    if result.verify_mode != ssl.CERT_REQUIRED or not result.check_hostname:
        raise PinError("tls_verification_disabled")
    result.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
    try:
        result.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(pin.der))
    except (ValueError, ssl.SSLError):
        raise PinError("certificate_chain_incomplete") from None
    return result


_CURRENT: ContextVar[Pin | None] = ContextVar("page_intermediate_pin", default=None)
_BROWSER: ContextVar[bool] = ContextVar("page_browser_agent", default=False)


@contextmanager
def page_transport(pin: Pin | None) -> Iterator[None]:
    """Scope the browser user agent and optional exact-host pin to one fetch."""
    token = _CURRENT.set(pin)
    browser = _BROWSER.set(True)
    try:
        yield
    finally:
        _CURRENT.reset(token)
        _BROWSER.reset(browser)


def current_pin() -> Pin | None:
    return _CURRENT.get()


def browser_agent() -> bool:
    return _BROWSER.get()


@dataclass(frozen=True)
class Capture:
    body: bytes = field(repr=False)
    initial_url: str
    final_url: str
    hops: tuple[str, ...]
    tool: str
    captured_utc: str
    sha256: str
    pin: Pin
    tls_verified: bool
    access: str


def admit_capture(
    capture: Capture, expected_url: str
) -> tuple[Response, dict[str, object]]:
    """Validate lead capture evidence before returning bytes to the receipt seam."""
    if not capture.tool.strip() or capture.initial_url != expected_url:
        raise PinError("capture_evidence_missing")
    utc(capture.captured_utc)
    if capture.tls_verified is not True:
        raise PinError("tls_verification_disabled")
    if capture.access != "visitor":
        raise PinError("unavailable")
    if hashlib.sha256(capture.body).hexdigest() != capture.sha256:
        raise PinError("capture_hash_mismatch")
    for url in (capture.initial_url, *capture.hops, capture.final_url):
        if not approve(url).ok:
            raise PinError("blocked_host")
        verified_context(host_of(url), capture.pin)
    if capture.final_url != (capture.hops[-1] if capture.hops else capture.initial_url):
        raise PinError("capture_evidence_missing")
    evidence: dict[str, object] = {
        "initial_url": capture.initial_url,
        "final_url": capture.final_url,
        "redirect_urls": list(capture.hops),
        "tool": capture.tool,
        "captured_utc": capture.captured_utc,
        "sha256": capture.sha256,
        "intermediate_host": capture.pin.host,
        "intermediate_sha256": capture.pin.sha256,
        "tls_verified": True,
        "access": "visitor",
    }
    return Response(capture.final_url, capture.body, capture.hops), evidence


def intake_file(cache: Path, source: str, name: str) -> Path:
    """A relative, non-symlink file within this source's documented intake."""
    relative = Path(name)
    folder = cache / "intake" / source
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not name
        or Path(source).name != source
    ):
        raise PinError("intake_path_refused")
    path = folder / relative
    if not path.resolve().is_relative_to(
        folder.resolve()
    ) or not folder.resolve().is_relative_to(cache.resolve()):
        raise PinError("intake_path_refused")
    for part in (path, *path.parents):
        if part == cache:
            break
        if part.is_symlink():
            raise PinError("intake_path_refused")
    return path


def load_pin(cache: Path, source: str, config: object) -> Pin:
    """Load only the lead's hash-reviewed DER file; missing evidence stays closed."""
    if not isinstance(config, dict) or set(config) != {
        "host",
        "sha256",
        "file",
        "security_review",
    }:
        raise PinError("certificate_chain_incomplete")
    if any(not isinstance(value, str) for value in config.values()):
        raise PinError("certificate_chain_incomplete")
    path = intake_file(cache, source, config["file"])
    if config["security_review"] != "APPROVED":
        raise PinError("certificate_review_pending")
    try:
        der = path.read_bytes()
    except OSError:
        raise PinError("certificate_chain_incomplete") from None
    pin = Pin(config["host"], config["sha256"], der, True)
    validate_pin(pin.host, pin)
    return pin


def load_capture(cache: Path, source: str, pin: Pin) -> Capture | None:
    """Optional lead-operated browser capture; no browser package or automatic run."""
    path = intake_file(cache, source, "capture.json")
    if not path.exists():
        return None
    try:
        receipt = json.loads(path.read_bytes())
        expected = {
            "file",
            "initial_url",
            "final_url",
            "hops",
            "tool",
            "captured_utc",
            "sha256",
            "intermediate_host",
            "intermediate_sha256",
            "tls_verified",
            "access",
        }
        if not isinstance(receipt, dict) or set(receipt) != expected:
            raise PinError("capture_evidence_missing")
        text_keys = expected - {"hops", "tls_verified"}
        if any(not isinstance(receipt[key], str) for key in text_keys):
            raise PinError("capture_evidence_missing")
        if (
            not isinstance(receipt["hops"], list)
            or any(not isinstance(url, str) for url in receipt["hops"])
            or receipt["intermediate_host"] != pin.host
            or receipt["intermediate_sha256"] != pin.sha256
        ):
            raise PinError("capture_evidence_missing")
        body = intake_file(cache, source, receipt["file"]).read_bytes()
        return Capture(
            body,
            receipt["initial_url"],
            receipt["final_url"],
            tuple(receipt["hops"]),
            receipt["tool"],
            receipt["captured_utc"],
            receipt["sha256"],
            pin,
            receipt["tls_verified"],
            receipt["access"],
        )
    except (OSError, KeyError, json.JSONDecodeError):
        raise PinError("capture_evidence_missing") from None
