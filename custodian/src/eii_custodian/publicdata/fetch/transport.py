"""Transport seam. Only this module constructs the real HTTPS opener."""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http.client import HTTPMessage
from typing import IO
from urllib.parse import urlencode

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
    body: bytes = field(repr=False)
    hops: tuple[str, ...]
    etag: str | None = None
    body_sha256: str = ""


class TransportFault(Exception):
    """A transport failure. kind is unreachable, http or blocked_host."""

    def __init__(self, kind: str, url: str) -> None:
        self.kind = kind
        self.url = url
        super().__init__(kind)


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


def open_https(url: str) -> Response:
    """Open one HTTPS URL with the standard library. Redirects are checked first."""
    decision = approve(url)
    if not decision.ok:
        raise TransportFault("blocked_host", url)
    keyed = isinstance(url, KeyedRequest)
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
            if keyed:
                # No redirected send can become a second chargeable request.
                raise TransportFault("blocked_host", str(url))
            hops.append(newurl)
            if not approve(newurl).ok:
                raise TransportFault("blocked_host", newurl)
            return urllib.request.HTTPRedirectHandler.redirect_request(
                self, req, fp, code, msg, headers, newurl
            )

    opener = urllib.request.build_opener(_Guard)
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
    request = urllib.request.Request(address, method=method)
    fault: str | None = None
    try:
        with opener.open(request, timeout=HTTP_TIMEOUT_S) as response:
            body = response.read()
            final = str(response.geturl())
            etag = response.headers.get("ETag")
    except TransportFault:
        if not keyed:
            raise
        fault = "blocked_host"
    except urllib.error.HTTPError as exc:
        if not keyed:
            raise TransportFault("http", url) from exc
        fault = "http"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        if not keyed:
            raise TransportFault("unreachable", url) from exc
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
        final_url=final, body=body, hops=tuple(hops), etag=etag, body_sha256=digest
    )
