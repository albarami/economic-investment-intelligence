"""Transport seam. Only this module constructs the real HTTPS opener."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPMessage
from typing import IO

from eii_custodian.publicdata.fetch.allowlist import approve

HTTP_TIMEOUT_S = 60.0
MAX_RETRIES = 3
ATTEMPT_LIMIT = MAX_RETRIES + 1
BACKOFF_S = (1.0, 2.0, 4.0)

Transport = Callable[[str], "Response"]
Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class Response:
    """One completed response. hops are redirect targets, in order."""

    final_url: str
    body: bytes
    hops: tuple[str, ...]


class TransportFault(Exception):
    """A retryable transport failure. kind is unreachable or http."""

    def __init__(self, kind: str, url: str) -> None:
        self.kind = kind
        self.url = url
        super().__init__(kind)


def open_https(url: str) -> Response:
    """Open one HTTPS URL with the standard library. Redirects are checked first."""
    decision = approve(url)
    if not decision.ok:
        raise TransportFault("blocked_host", url)
    hops: list[str] = []

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
            if not approve(newurl).ok:
                raise TransportFault("blocked_host", newurl)
            return urllib.request.HTTPRedirectHandler.redirect_request(
                self, req, fp, code, msg, headers, newurl
            )

    opener = urllib.request.build_opener(_Guard)
    request = urllib.request.Request(url, method="GET")
    try:
        with opener.open(request, timeout=HTTP_TIMEOUT_S) as response:
            body = response.read()
            final = str(response.geturl())
    except TransportFault:
        raise
    except urllib.error.HTTPError as exc:
        raise TransportFault("http", url) from exc
    except urllib.error.URLError as exc:
        raise TransportFault("unreachable", url) from exc
    return Response(final_url=final, body=body, hops=tuple(hops))
