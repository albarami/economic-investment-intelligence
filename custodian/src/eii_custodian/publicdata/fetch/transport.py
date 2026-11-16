"""Transport seam. Only this module constructs the real HTTPS opener."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from http.client import HTTPException, HTTPMessage
from typing import IO
from urllib.parse import urlsplit

from eii_custodian.publicdata.fetch.allowlist import approve

HTTP_TIMEOUT_S = 60.0
MAX_RETRIES = 3
ATTEMPT_LIMIT = MAX_RETRIES + 1
BACKOFF_S = (1.0, 2.0, 4.0)

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
            body = response.read()
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
