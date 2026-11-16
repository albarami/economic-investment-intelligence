"""Transport seam. Only this module constructs the real HTTPS opener."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from http.client import HTTPException, HTTPMessage
from typing import IO, Protocol
from urllib.parse import unquote, urlsplit

from eii_custodian.publicdata.fetch.allowlist import approve

HTTP_TIMEOUT_S = 60.0
MAX_RETRIES = 3
ATTEMPT_LIMIT = MAX_RETRIES + 1
BACKOFF_S = (1.0, 2.0, 4.0)

_METADATA_LIMIT: ContextVar[int | None] = ContextVar(
    "metadata_byte_limit", default=None
)


@contextmanager
def metadata_limit(max_bytes: int) -> Iterator[None]:
    """Bound HTTPS reads through existing one-argument transport wrappers.

    The scope is local to this call context and reset even after a refusal.
    Other callers retain the unbounded interface.
    """
    token = _METADATA_LIMIT.set(max_bytes)
    try:
        yield
    finally:
        _METADATA_LIMIT.reset(token)


Transport = Callable[[str], "Response"]
Sleeper = Callable[[float], None]
# Expose the read-error type without requiring callers to import networking modules.
TransportReadError = HTTPException


@dataclass(frozen=True)
class Response:
    """One completed response. hops are redirect targets, in order."""

    final_url: str
    body: bytes
    hops: tuple[str, ...]
    etag: str | None = None


class TransportFault(Exception):
    """A transport failure. kind is unreachable, http or blocked_host."""

    def __init__(self, kind: str, url: str) -> None:
        self.kind = kind
        self.url = url
        super().__init__(kind)


@dataclass(frozen=True)
class StreamResponse:
    """Metadata and bounded chunks; consumed only inside its open context."""

    final_url: str
    hops: tuple[str, ...]
    declared_length: int | None
    chunks: Iterator[bytes]


StreamTransport = Callable[[str], AbstractContextManager[StreamResponse]]


def open_https(url: str, *, reviewed_urls: tuple[str, ...] | None = None) -> Response:
    """Open one HTTPS URL with the standard library. Redirects are checked first."""
    decision = approve(url)
    if not decision.ok or (
        reviewed_urls is not None
        and (url not in reviewed_urls or not _stream_allowed(url))
    ):
        raise TransportFault("blocked_host", url)
    hops: list[str] = []
    opener = urllib.request.build_opener(
        _redirect_guard(
            hops, strict=reviewed_urls is not None, reviewed_urls=reviewed_urls
        )
    )
    request = urllib.request.Request(url, method="GET")
    try:
        with opener.open(request, timeout=HTTP_TIMEOUT_S) as response:
            limit = _METADATA_LIMIT.get()
            body = response.read() if limit is None else response.read(limit + 1)
            final = str(response.geturl())
            if reviewed_urls is not None and (
                final not in reviewed_urls or not _stream_allowed(final)
            ):
                raise TransportFault("blocked_host", "")
            etag = response.headers.get("ETag")
    except TransportFault:
        raise
    except urllib.error.HTTPError as exc:
        raise TransportFault("http", url) from exc
    except urllib.error.URLError as exc:
        raise TransportFault("unreachable", url) from exc
    return Response(final_url=final, body=body, hops=tuple(hops), etag=etag)


def _redirect_guard(
    hops: list[str], strict: bool = False, reviewed_urls: tuple[str, ...] | None = None
) -> type[urllib.request.HTTPRedirectHandler]:

    class _Guard(urllib.request.HTTPRedirectHandler):
        def redirect_request(
            self,
            req: urllib.request.Request,
            fp: IO[bytes],
            code: int,
            msg: str,
            headers: HTTPMessage,
            newurl: str,
        ) -> urllib.request.Request | None:
            hops.append(newurl)
            if (
                not approve(newurl).ok
                or (strict and not _stream_allowed(newurl))
                or (reviewed_urls is not None and newurl not in reviewed_urls)
            ):
                raise TransportFault("blocked_host", newurl)
            return urllib.request.HTTPRedirectHandler.redirect_request(
                self, req, fp, code, msg, headers, newurl
            )

    return _Guard


@contextmanager
def open_https_stream(
    url: str, *, reviewed_urls: tuple[str, ...] | None = None
) -> Iterator[StreamResponse]:
    """Open a bounded-chunk stream; the context always closes the response."""
    if not _stream_allowed(url) or (
        reviewed_urls is not None and url not in reviewed_urls
    ):
        raise TransportFault("blocked_host", "")
    hops: list[str] = []
    opener = urllib.request.build_opener(
        _redirect_guard(hops, strict=True, reviewed_urls=reviewed_urls)
    )
    request = urllib.request.Request(url, method="GET")
    try:
        with opener.open(request, timeout=HTTP_TIMEOUT_S) as response:
            final = str(response.geturl())
            if not _stream_allowed(final) or (
                reviewed_urls is not None and final not in reviewed_urls
            ):
                raise TransportFault("blocked_host", "")
            length = response.headers.get("Content-Length")
            if length is not None and not length.isascii():
                raise TransportFault("http", "")
            if length is not None and not length.isdigit():
                raise TransportFault("http", "")

            def chunks() -> Iterator[bytes]:
                while chunk := response.read(65536):
                    yield chunk

            yield StreamResponse(
                final, tuple(hops), None if length is None else int(length), chunks()
            )
    except TransportFault:
        raise
    except urllib.error.HTTPError:
        raise TransportFault("http", "") from None
    except (urllib.error.URLError, OSError, HTTPException):
        raise TransportFault("unreachable", "") from None


def _stream_allowed(url: str) -> bool:
    try:
        parts = urlsplit(url)
        return (
            approve(url).ok
            and parts.username is None
            and parts.password is None
            and not parts.query
            and not parts.fragment
            and parts.port in (None, 443)
            and not any(ord(char) <= 32 for char in url)
        )
    except ValueError:
        return False


def open_attempt(request: PreparedRequest) -> AttemptResult:
    """Open one checked HTTPS request. Redirects are not followed."""

    class _Stop(urllib.request.HTTPRedirectHandler):
        def redirect_request(
            self,
            req: urllib.request.Request,
            fp: IO[bytes],
            code: int,
            msg: str,
            headers: HTTPMessage,
            newurl: str,
        ) -> urllib.request.Request | None:
            del req, fp, code, msg, headers, newurl
            raise OpenerFault("redirect")

    decision = approve(request.url)
    if not decision.ok:
        raise OpenerFault("blocked_host")
    call = urllib.request.Request(request.url, method="GET")
    if request.header_name and request.header_value:
        call.add_header(request.header_name, request.header_value)
    opener = urllib.request.build_opener(_Stop)
    try:
        with opener.open(call, timeout=HTTP_TIMEOUT_S) as response:
            body = response.read()
    except OpenerFault:
        raise
    except urllib.error.HTTPError:
        raise OpenerFault("http") from None
    except urllib.error.URLError:
        raise OpenerFault("unreachable") from None
    return AttemptResult("ok", body)


@dataclass(frozen=True)
class SlotSecrets:
    """Header values for the two slots. The text form never includes them."""

    primary: str
    secondary: str

    def __repr__(self) -> str:
        return "SlotSecrets(redacted)"

    def for_slot(self, slot: str) -> str:
        """Return one slot's header value. An unknown slot is empty."""
        return self.read_slot(slot)

    def read_slot(self, slot: str) -> str:
        """Return one slot's header value. An unknown slot is empty."""
        if slot == "primary":
            return self.primary
        if slot == "secondary":
            return self.secondary
        return ""


@dataclass(frozen=True)
class PreparedRequest:
    """What the opener receives after the address has been checked."""

    url: str
    header_name: str
    header_value: str
    endpoint_id: str

    def __repr__(self) -> str:
        return "PreparedRequest(redacted)"


@dataclass(frozen=True)
class AttemptResult:
    """A classified opener result. Error text is not a failure message."""

    category: str
    body: bytes
    location: str = ""
    error_text: str = ""
    header_echo: str = ""

    def __repr__(self) -> str:
        return f"AttemptResult(category={self.category!r})"


class SlotReader(Protocol):
    """Reads one slot variable when a permitted request is about to be sent."""

    def read_slot(self, slot: str) -> str:
        """Return the header value for the named slot."""


class OpenerFault(Exception):
    """An opener failure whose text must not be copied into a receipt or a message."""


Opener = Callable[[PreparedRequest], AttemptResult]
HEADER_NAME = "Ocp-Apim-Subscription-Key"


def perform(
    policy: object,
    descriptor: object,
    header_value: str | None,
    opener: Opener,
) -> AttemptResult:
    """Check the descriptor, then call the opener. A redirect is not followed."""
    from eii_custodian.publicdata.comtrade.policy import (
        FORBIDDEN_FAMILIES,
        Descriptor,
        Policy,
        direction_ok,
        refusal,
        refusal_hiding,
        url_approved,
    )

    if not isinstance(policy, Policy) or not isinstance(descriptor, Descriptor):
        raise OpenerFault("descriptor")
    if not direction_ok(policy, descriptor):
        raise refusal(policy, descriptor, "mirror_direction") from None
    family = descriptor.endpoint_family.casefold()
    forbidden = family in FORBIDDEN_FAMILIES or any(
        token in family for token in FORBIDDEN_FAMILIES
    )
    if forbidden:
        raise refusal(policy, descriptor, "forbidden_endpoint") from None
    if not url_approved(policy, descriptor):
        raise refusal(policy, descriptor, "blocked_host") from None
    url = _checked_url(policy, descriptor)
    if header_value and _url_has_secret(url, header_value):
        raise refusal_hiding(policy, descriptor, "query_key", header_value) from None
    request = PreparedRequest(
        url=url,
        header_name=HEADER_NAME if header_value else "",
        header_value=header_value or "",
        endpoint_id=descriptor.endpoint_id(),
    )
    try:
        result = opener(request)
    except OpenerFault:
        raise refusal(policy, descriptor, "provider_error") from None
    except (OSError, ValueError, UnicodeError):
        raise refusal(policy, descriptor, "provider_error") from None
    if result.location:
        _refuse_redirect(policy, descriptor, result.location, header_value)
    return result


def _url_has_secret(url: str, secret: str) -> bool:
    from eii_custodian.publicdata.fetch.allowlist import secret_in_url

    if secret_in_url(url, secret):
        return True
    return secret in unquote(url)


def _checked_url(policy: object, descriptor: object) -> str:
    from eii_custodian.publicdata.comtrade.policy import Descriptor, Policy, safe_url

    if not isinstance(policy, Policy) or not isinstance(descriptor, Descriptor):
        raise OpenerFault("descriptor")
    return safe_url(policy, descriptor)


def _refuse_redirect(
    policy: object, descriptor: object, location: str, header_value: str | None
) -> None:
    from urllib.parse import parse_qsl, urlsplit

    from eii_custodian.publicdata.comtrade.policy import (
        FORBIDDEN_FAMILIES,
        Descriptor,
        Policy,
        refusal,
    )
    from eii_custodian.publicdata.fetch.allowlist import CREDENTIAL_QUERY_NAMES

    if not isinstance(policy, Policy) or not isinstance(descriptor, Descriptor):
        raise OpenerFault("descriptor")
    lowered = location.casefold()
    if any(token in lowered for token in FORBIDDEN_FAMILIES):
        raise refusal(policy, descriptor, "forbidden_endpoint") from None
    parts = urlsplit(location)
    template = policy.template(descriptor.api_class, descriptor.endpoint_family)
    request_host = template.host if template is not None else ""
    redirect_host = (parts.hostname or "").casefold()
    names = {
        name.casefold()
        for name, _value in parse_qsl(parts.query, keep_blank_values=True)
    }
    secret = bool(parts.username or parts.password or parts.fragment)
    keyed_query = bool(names & CREDENTIAL_QUERY_NAMES)
    allowed = frozenset(item.casefold() for item in policy.allowed_redirect_hosts)
    allowed = allowed | {request_host}
    if parts.scheme.casefold() != "https" or secret or keyed_query:
        raise refusal(policy, descriptor, "redirect_host") from None
    if redirect_host not in allowed:
        raise refusal(policy, descriptor, "redirect_host") from None
    if header_value and redirect_host != request_host:
        raise refusal(policy, descriptor, "cross_origin_credential") from None
