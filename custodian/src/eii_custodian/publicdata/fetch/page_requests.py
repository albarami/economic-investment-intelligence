"""Per-request exact URL frame, host-scoped pins, and closed school queries."""

from __future__ import annotations

import ssl
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from types import MappingProxyType
from urllib.parse import parse_qsl, urlsplit

from .allowlist import approve
from .certificate_pins import (
    Pin,
    PinError,
    offer_http11,
    validate_pin,
    verified_context,
)
from .page_schema import SCHOOL_FIELDS
from .transport import TransportFault

PIN_HOSTS = frozenset(
    {
        "eservices.qfc.qa",
        "www.qcb.gov.qa",
        "monaqasat.mof.gov.qa",
        "www.edu.gov.qa",
        "myschools.edu.gov.qa",
    }
)
_FRAME: ContextVar[tuple[str, ...] | None] = ContextVar(
    "reviewed_page_request_frame", default=None
)
_PINS: ContextVar[Mapping[str, Pin] | None] = ContextVar(
    "reviewed_page_host_pins", default=None
)


@contextmanager
def page_requests(urls: tuple[str, ...], pins: Mapping[str, Pin]) -> Iterator[None]:
    token = _FRAME.set(urls)
    pt = _PINS.set(pins)
    try:
        yield
    finally:
        _PINS.reset(pt)
        _FRAME.reset(token)


_POSTBACK: ContextVar[tuple[dict[str, str], str] | None] = ContextVar(
    "delivered_page_state", default=None
)


class PagePostback(str):
    """A public pager request; its string and repr contain no form state."""

    fields: Mapping[str, str]
    target: str
    argument: str

    def __new__(
        cls, url: str, fields: Mapping[str, str], target: str, argument: str = ""
    ) -> PagePostback:
        instance = super().__new__(cls, url)
        instance.fields = MappingProxyType(dict(fields))
        instance.target = target
        instance.argument = argument
        return instance

    def __repr__(self) -> str:
        return "PagePostback(redacted)"


@contextmanager
def delivered_state(fields: Mapping[str, str], target: str) -> Iterator[None]:
    token = _POSTBACK.set((dict(fields), target))
    try:
        yield
    finally:
        _POSTBACK.reset(token)


def active() -> bool:
    return _FRAME.get() is not None


def check_target(url: str) -> None:
    from ..fc_register.constants import STATE_FIELDS, TARGETS, URL

    if isinstance(url, PagePostback):
        delivered = _POSTBACK.get()
        if (
            not active()
            or str(url) != URL
            or url.target not in TARGETS
            or url.argument != ""
            or delivered is None
            or dict(url.fields) != delivered[0]
            or url.target != delivered[1]
            or set(url.fields) != set(STATE_FIELDS)
        ):
            raise TransportFault("schema_missing", "")
    if (
        active()
        and (urlsplit(url).hostname or "") == "eservices.qfc.qa"
        and str(url) != URL
    ):
        raise TransportFault("blocked_host", "")
    frame = _FRAME.get()
    if frame is not None and (url not in frame or not approve(url).ok):
        raise TransportFault("blocked_host", "")
    parts = urlsplit(url)
    if (parts.hostname or "") == "myschools.edu.gov.qa" and parts.path.endswith(
        "/PrivateSchoolsView/FeatureServer/0/query"
    ):
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        query = dict(pairs)
        if (
            len(pairs) != len(query)
            or query.get("where") != "1=1"
            or query.get("f") != "json"
        ):
            raise TransportFault("blocked_host", "")
        if query.get("returnCountOnly") == "true":
            if set(query) != {"where", "returnCountOnly", "f"}:
                raise TransportFault("blocked_host", "")
        else:
            if (
                set(query)
                != {
                    "where",
                    "outFields",
                    "orderByFields",
                    "returnGeometry",
                    "resultOffset",
                    "resultRecordCount",
                    "f",
                }
                or query["outFields"] != ",".join(SCHOOL_FIELDS)
                or query["orderByFields"] != "objectid"
                or query["returnGeometry"] != "true"
                or not query["resultOffset"].isascii()
                or not query["resultOffset"].isdigit()
                or not query["resultRecordCount"].isascii()
                or not query["resultRecordCount"].isdigit()
                or not 1 <= int(query["resultRecordCount"]) <= 1000
            ):
                raise TransportFault("blocked_host", "")


def page_context(host: str, supplied: ssl.SSLContext | None = None) -> ssl.SSLContext:
    if supplied is not None and (
        supplied.verify_mode != ssl.CERT_REQUIRED or not supplied.check_hostname
    ):
        raise PinError("tls_verification_disabled")
    pins = _PINS.get() or {}
    if host in PIN_HOSTS and host in pins:
        pin = pins[host]
        validate_pin(host, pin)
        return verified_context(host, pin)
    if host in PIN_HOSTS:
        raise PinError("certificate_chain_incomplete")
    # Never carry an augmented context onto a full-chain host.
    result = offer_http11(ssl.create_default_context())
    result.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
    return result
