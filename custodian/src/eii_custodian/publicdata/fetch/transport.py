"""Transport seam. Only this module constructs the real HTTPS opener."""

from __future__ import annotations

import hashlib
import json
import re
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from http.client import HTTPException, HTTPMessage, HTTPResponse, HTTPSConnection
from typing import IO, Protocol
from urllib.parse import unquote, urlencode, urlsplit, urlunsplit

from eii_custodian.publicdata.fetch.allowlist import approve, host_of

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
    Other callers retain the general intake ceiling.
    """
    token = _METADATA_LIMIT.set(max_bytes)
    try:
        yield
    finally:
        _METADATA_LIMIT.reset(token)


Transport = Callable[[str], "Response"]
Sleeper = Callable[[float], None]
AUTHORIZATION_HOSTS = frozenset({"ladsweb.modaps.eosdis.nasa.gov"})
SIGN_IN_HOST = "urs.earthdata.nasa.gov"
GRANULE_SUFFIX = ".h5"


def public_address(url: str) -> str:
    """Return scheme, host and path. A query string is never part of an error."""
    parts = urlsplit(url)
    netloc = parts.netloc
    if parts.username is not None or parts.password is not None:
        # Userinfo never reaches an error: rebuild the netloc from host and port.
        host = parts.hostname or ""
        netloc = f"[{host}]" if ":" in host else host
        try:
            port = parts.port
        except ValueError:
            port = None
        if port is not None:
            netloc = f"{netloc}:{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def authorization_header(url: str, token: str) -> dict[str, str]:
    """Return the bearer header for an archive granule only, and nothing otherwise."""
    if not token or host_of(url) not in AUTHORIZATION_HOSTS:
        return {}
    if not urlsplit(url).path.endswith(GRANULE_SUFFIX):
        return {}
    return {"Authorization": f"Bearer {token}"}


# Expose the read-error type without requiring callers to import networking modules.
TransportReadError = HTTPException


@dataclass(frozen=True)
class Response:
    """One completed response. hops are redirect targets, in order."""

    final_url: str
    body: bytes = field(repr=False)
    hops: tuple[str, ...]
    etag: str | None = None
    body_sha256: str = ""
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    evidence: Mapping[str, object] = field(default_factory=dict)


class TransportFault(Exception):
    """A transport failure. kind is unreachable, http or blocked_host."""

    def __init__(self, kind: str, url: str, status: int | None = None) -> None:
        self.status = status if type(status) is int and 100 <= status <= 599 else None
        self.kind = kind
        self.url = public_address(url)
        super().__init__(f"{kind} {self.url}")


# The owner ruling of 2026-11-18 retains the general ceiling; required large
# sources use the file-stream intake. Lower source caps keep their own refusal.
INTAKE_CEILING_BYTES = 300 * 1024 * 1024
INTAKE_CEILING_STATUS = "bounded intake with required-source streams"
READ_CHUNK_BYTES = 65536


class BodyTooLarge(TransportFault):
    """A body above the intake ceiling: declared by its header, or read past it.

    observed is ``declared N`` or ``more than C``; no full size or hash of a
    refused body is claimed.
    """

    def __init__(self, url: str, ceiling: int, observed: str) -> None:
        super().__init__("body_bytes", url)
        self.ceiling = ceiling
        self.observed = observed


@dataclass(frozen=True)
class StreamResponse:
    """Metadata and bounded chunks; consumed only inside its open context."""

    final_url: str
    hops: tuple[str, ...]
    declared_length: int | None
    chunks: Iterator[bytes]
    etag: str | None = None


StreamTransport = Callable[[str], AbstractContextManager[StreamResponse]]


class KeyedRequest(str):
    """A key-free endpoint; credentials are resolved by the transport at send time."""

    method: str
    parameters: Mapping[str, str]
    environ: Mapping[str, str]

    def __new__(
        cls,
        url: str,
        method: str,
        parameters: Mapping[str, str],
        environ: Mapping[str, str],
    ) -> KeyedRequest:
        instance = super().__new__(cls, url)
        instance.method = method
        instance.parameters = parameters
        instance.environ = environ
        return instance


def _request_allowed(url: str) -> bool:
    """Dynamic admission exists only inside the company-web exact URL frame."""
    from ..company_web.scope import active, allowed

    return allowed(url) if active() else approve(url).ok


def _reviewed_allowed(url: str) -> bool:
    from ..company_web.scope import active, allowed

    return allowed(url) if active() else _stream_allowed(url)


def open_https(
    url: str,
    token: str = "",
    headers: Mapping[str, str] | None = None,
    ssl_context: ssl.SSLContext | None = None,
    *,
    reviewed_urls: tuple[str, ...] | None = None,
    legacy_chain_sha256: str | None = None,
) -> Response:
    """Open one HTTPS URL with the standard library. Redirects are checked first."""
    from ..company_web.scope import active as company_active
    from .certificate_pins import PinError, browser_agent, current_pin, verified_context
    from .page_requests import (
        PIN_HOSTS,
        PagePostback,
        active,
        check_target,
        page_context,
    )

    check_target(url)
    if company_active() and (
        token or headers or isinstance(url, (KeyedRequest, PagePostback))
    ):
        raise TransportFault("blocked_host", "")
    supplied_partial_chain = ssl_context is not None and bool(
        ssl_context.verify_flags & ssl.VERIFY_X509_PARTIAL_CHAIN
    )
    page_scoped = active()
    pin = current_pin()
    if page_scoped:
        if token or (
            headers
            and any(
                name.casefold()
                in {"authorization", "cookie", "__requestverificationtoken"}
                for name in headers
            )
        ):
            raise TransportFault("blocked_host", "")
        ssl_context = page_context(host_of(url), ssl_context)
    elif pin is not None:
        ssl_context = verified_context(host_of(url), pin, context=ssl_context)
    if not _request_allowed(url) or (
        reviewed_urls is not None
        and (url not in reviewed_urls or not _reviewed_allowed(url))
    ):
        raise TransportFault("blocked_host", url)
    if ssl_context is not None and (
        ssl_context.verify_mode != ssl.CERT_REQUIRED or not ssl_context.check_hostname
    ):
        raise TransportFault("unreachable", url)
    if supplied_partial_chain:
        raise PinError("certificate_chain_incomplete")
    # L-921: only the tender adapter supplies the chain hash already checked by
    # chain_context. A context alone or an unchecked pin shape cannot bridge the
    # unscoped page-host refusal. Disabled verification keeps its precedence.
    if not page_scoped and pin is None and host_of(url) in PIN_HOSTS:
        if (
            ssl_context is None
            or re.fullmatch(r"[0-9a-fA-F]{64}", legacy_chain_sha256 or "") is None
        ):
            raise PinError("certificate_chain_incomplete")
    keyed = isinstance(url, KeyedRequest)
    hops: list[str] = []
    guard = _redirect_guard(
        hops,
        token,
        strict=reviewed_urls is not None,
        reviewed_urls=reviewed_urls,
        keyed_url=str(url) if keyed else None,
        postback=isinstance(url, PagePostback),
    )
    if page_scoped:

        class _PageHTTPS(urllib.request.HTTPSHandler):
            def https_open(self, req: urllib.request.Request) -> HTTPResponse:
                check_target(req.full_url)
                return self.do_open(
                    HTTPSConnection, req, context=page_context(host_of(req.full_url))
                )

        opener = urllib.request.build_opener(guard, _PageHTTPS())
    elif ssl_context is None:
        opener = urllib.request.build_opener(guard)
    else:
        opener = urllib.request.build_opener(
            guard, urllib.request.HTTPSHandler(context=ssl_context)
        )
    request_headers = dict(headers) if headers else {}
    request_headers.setdefault("User-Agent", "EII-Public-Citation-Client/1.0")
    if browser_agent():
        request_headers["User-Agent"] = "Mozilla/5.0"
    request_headers.update(authorization_header(url, token))
    address = str(url)
    method = "GET"
    if isinstance(url, KeyedRequest):
        from eii_custodian.publicdata.busyness.parse import FORECAST_URL, QUERY_URL

        specs = {
            FORECAST_URL: ("POST", "api_key_private", "BESTTIME_API_KEY_PRIVATE"),
            QUERY_URL: ("GET", "api_key_public", "BESTTIME_API_KEY_PUBLIC"),
        }
        if str(url) not in specs:
            raise TransportFault("blocked_host", FORECAST_URL)
        method, parameter, variable = specs[str(url)]
        if url.method != method or not url.environ.get(variable, "").strip():
            raise TransportFault("credentials", str(url))
        address += "?" + urlencode({**url.parameters, parameter: url.environ[variable]})
    data = None
    if isinstance(url, PagePostback):
        method = "POST"
        data = urlencode(
            {**url.fields, "__EVENTTARGET": url.target, "__EVENTARGUMENT": url.argument}
        ).encode()
    request = urllib.request.Request(
        address, data=data, method=method, headers=request_headers
    )
    fault: str | None = None
    try:
        with opener.open(request, timeout=HTTP_TIMEOUT_S) as response:
            body = _bounded_body(response, str(url))
            final = str(response.geturl())
            if (company_active() and not _request_allowed(final)) or (
                reviewed_urls is not None
                and (final not in reviewed_urls or not _reviewed_allowed(final))
            ):
                raise TransportFault("blocked_host", "")
            etag = response.headers.get("ETag")
            public_headers = {
                name: response.headers[name]
                for name in ("x-wp-total", "x-wp-totalpages", "Content-Type")
                if response.headers.get(name) is not None
            }
    except PinError:
        raise
    except TransportFault:
        if not keyed:
            raise
        fault = "blocked_host"
    except urllib.error.HTTPError as exc:
        if not keyed:
            raise TransportFault(
                "http", url, exc.code if page_scoped else None
            ) from None
        fault = "http"
    except ssl.SSLError:
        if page_scoped:
            raise PinError("certificate_chain_incomplete") from None
        if not keyed:
            raise TransportFault("unreachable", url) from None
        fault = "unreachable"
    except urllib.error.URLError as exc:
        if page_scoped and isinstance(exc.reason, ssl.SSLError):
            raise PinError("certificate_chain_incomplete") from None
        if not keyed:
            raise TransportFault("unreachable", url) from None
        fault = "unreachable"
    except (OSError, ValueError, TransportReadError):
        if not keyed:
            raise TransportFault("unreachable", url) from None
        fault = "unreachable"
    if fault is not None:
        raise TransportFault(fault, str(url)) from None
    digest = hashlib.sha256(body).hexdigest()
    if keyed:
        from eii_custodian.publicdata.busyness.parse import _clean

        try:
            body = json.dumps(_clean(json.loads(body))).encode()
        except (ValueError, UnicodeError):
            body = b"null"
        final, hops, etag = str(url), [], None
    return Response(
        final_url=final,
        body=body,
        hops=tuple(hops),
        etag=etag,
        body_sha256=digest,
        headers=public_headers,
    )


def _bounded_body(response: HTTPResponse, url: str) -> bytes:
    """Read fixed chunks, refusing the general cap and preserving lower caps."""
    limit = _METADATA_LIMIT.get()
    scoped = limit is not None and limit <= INTAKE_CEILING_BYTES
    ceiling = limit if scoped and limit is not None else INTAKE_CEILING_BYTES
    if scoped and ceiling + 1 <= READ_CHUNK_BYTES:
        return response.read(ceiling + 1)
    declared = response.headers.get("Content-Length")
    if (
        not scoped
        and isinstance(declared, str)
        and declared.isascii()
        and declared.isdigit()
        and int(declared) > ceiling
    ):
        raise BodyTooLarge(url, ceiling, f"declared {int(declared)}")
    chunks: list[bytes] = []
    count = 0
    while count <= ceiling:
        chunk = response.read(min(READ_CHUNK_BYTES, ceiling + 1 - count))
        if not chunk:
            break
        count += len(chunk)
        if count > ceiling and not scoped:
            raise BodyTooLarge(url, ceiling, f"more than {ceiling}")
        chunks.append(chunk)
    return b"".join(chunks)


def _redirect_guard(
    hops: list[str],
    token: str = "",
    strict: bool = False,
    reviewed_urls: tuple[str, ...] | None = None,
    *,
    keyed_url: str | None = None,
    postback: bool = False,
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
            if postback:
                raise TransportFault("blocked_host", "")
            if keyed_url is not None:
                # No redirected send can become a second chargeable request.
                raise TransportFault("blocked_host", keyed_url)
            from .certificate_pins import PinError, current_pin, validate_pin
            from .page_requests import PIN_HOSTS, active, check_target, page_context

            check_target(newurl)
            if active():
                page_context(host_of(newurl))
            pin = current_pin()
            if pin is not None:
                validate_pin(host_of(newurl), pin)
            elif not active() and host_of(newurl) in PIN_HOSTS:
                raise PinError("certificate_chain_incomplete")
            hops.append(newurl)
            if host_of(newurl) == SIGN_IN_HOST:
                raise TransportFault("credential_missing_or_not_accepted", newurl)
            if (
                not _request_allowed(newurl)
                or (strict and not _reviewed_allowed(newurl))
                or (reviewed_urls is not None and newurl not in reviewed_urls)
            ):
                raise TransportFault("blocked_host", newurl)
            redirected = urllib.request.HTTPRedirectHandler.redirect_request(
                self, req, fp, code, msg, headers, newurl
            )
            if redirected is not None:
                for fields in (redirected.headers, redirected.unredirected_hdrs):
                    for name in tuple(fields):
                        if name.lower() == "authorization":
                            del fields[name]
                for name, value in authorization_header(newurl, token).items():
                    redirected.add_header(name, value)
            return redirected

    return _Guard


@contextmanager
def open_https_stream(
    url: str, *, reviewed_urls: tuple[str, ...] | None = None
) -> Iterator[StreamResponse]:
    """Open a bounded-chunk stream; the context always closes the response."""
    from ..company_web.scope import active as company_active
    from .certificate_pins import PinError
    from .page_requests import PIN_HOSTS

    if company_active():
        raise TransportFault("blocked_host", "")
    if host_of(url) in PIN_HOSTS:
        raise PinError("certificate_chain_incomplete")
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
                final,
                tuple(hops),
                None if length is None else int(length),
                chunks(),
                response.headers.get("ETag"),
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
    from .certificate_pins import PinError
    from .page_requests import PIN_HOSTS

    if host_of(request.url) in PIN_HOSTS:
        raise PinError("certificate_chain_incomplete")

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
            body = _bounded_body(response, request.url)
    except BodyTooLarge:
        raise OpenerFault("body_bytes") from None
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
    secret = header_value or ""
    if not direction_ok(policy, descriptor):
        raise refusal(policy, descriptor, "mirror_direction", secret) from None
    family = descriptor.endpoint_family.casefold()
    forbidden = family in FORBIDDEN_FAMILIES or any(
        token in family for token in FORBIDDEN_FAMILIES
    )
    if forbidden:
        raise refusal(policy, descriptor, "forbidden_endpoint", secret) from None
    if not url_approved(policy, descriptor):
        raise refusal(policy, descriptor, "blocked_host", secret) from None
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
        raise refusal(policy, descriptor, "provider_error", secret) from None
    except (OSError, ValueError, UnicodeError):
        raise refusal(policy, descriptor, "provider_error", secret) from None
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
    header = header_value or ""
    if any(token in lowered for token in FORBIDDEN_FAMILIES):
        raise refusal(policy, descriptor, "forbidden_endpoint", header) from None
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
        raise refusal(policy, descriptor, "redirect_host", header) from None
    if redirect_host not in allowed:
        raise refusal(policy, descriptor, "redirect_host", header) from None
    if header_value and redirect_host != request_host:
        raise refusal(policy, descriptor, "cross_origin_credential", header) from None


def open_gis_snapshot(url: str) -> Response:
    """One bounded attempt, no redirects; the snapshot runner paces every send."""
    from eii_custodian.publicdata.gis.snapshot_policy import check_url

    check_url(url)

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(
            self,
            req: urllib.request.Request,
            fp: IO[bytes],
            code: int,
            msg: str,
            headers: HTTPMessage,
            newurl: str,
        ) -> urllib.request.Request | None:
            raise TransportFault("redirect", "")

    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, method="GET")
    try:
        with (
            metadata_limit(4 * 1024 * 1024),
            opener.open(request, timeout=HTTP_TIMEOUT_S) as response,
        ):
            body = _bounded_body(response, url)
            return Response(
                str(response.geturl()),
                body,
                (),
                headers={"Content-Type": response.headers.get("Content-Type", "")},
            )
    except urllib.error.HTTPError as error:
        return Response(
            url,
            b"",
            (),
            headers={"Retry-After": error.headers.get("Retry-After", "")},
            evidence={"http_status": error.code},
        )
    except TransportFault:
        raise
    except (OSError, urllib.error.URLError, HTTPException):
        raise TransportFault("unreachable", "") from None
