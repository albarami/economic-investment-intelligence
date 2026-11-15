"""Transport seam. Only this module constructs the real HTTPS opener."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPMessage
from typing import IO
from urllib.parse import urlsplit, urlunsplit

from eii_custodian.publicdata.fetch.allowlist import approve, host_of

HTTP_TIMEOUT_S = 60.0
MAX_RETRIES = 3
ATTEMPT_LIMIT = MAX_RETRIES + 1
BACKOFF_S = (1.0, 2.0, 4.0)

Transport = Callable[[str], "Response"]
Sleeper = Callable[[float], None]
AUTHORIZATION_HOSTS = frozenset({"ladsweb.modaps.eosdis.nasa.gov"})
SIGN_IN_HOST = "urs.earthdata.nasa.gov"
GRANULE_SUFFIX = ".h5"


def public_address(url: str) -> str:
    """Return scheme, host and path. A query string is never part of an error."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def authorization_header(url: str, token: str) -> dict[str, str]:
    """Return the bearer header for an archive granule only, and nothing otherwise."""
    if not token or host_of(url) not in AUTHORIZATION_HOSTS:
        return {}
    if not urlsplit(url).path.endswith(GRANULE_SUFFIX):
        return {}
    return {"Authorization": f"Bearer {token}"}


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
        self.url = public_address(url)
        super().__init__(f"{kind} {self.url}")


def open_https(url: str, token: str = "") -> Response:
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
            if host_of(newurl) == SIGN_IN_HOST:
                raise TransportFault("credential_missing_or_not_accepted", newurl)
            if not approve(newurl).ok:
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

    opener = urllib.request.build_opener(_Guard)
    request = urllib.request.Request(
        url, method="GET", headers=authorization_header(url, token)
    )
    try:
        with opener.open(request, timeout=HTTP_TIMEOUT_S) as response:
            body = response.read()
            final = str(response.geturl())
            etag = response.headers.get("ETag")
    except TransportFault:
        raise
    except urllib.error.HTTPError:
        raise TransportFault("http", url) from None
    except urllib.error.URLError:
        raise TransportFault("unreachable", url) from None
    except OSError:
        raise TransportFault("unreachable", url) from None
    return Response(final_url=final, body=body, hops=tuple(hops), etag=etag)
