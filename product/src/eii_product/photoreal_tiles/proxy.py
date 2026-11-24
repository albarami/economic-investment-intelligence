"""Closed tile paths and a redirect-refusing opener; keys stay on the server."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from eii_core.reasons import reason
from eii_product.imagery_provider.address import AddressFailure, exchange_metadata
from eii_product.photoreal_tiles.limit import BillableFailure
from eii_product.photoreal_tiles.native import Target

_TILE = re.compile(r"3dtiles/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.(?:json|glb|b3dm)")


def closed_path(path: str) -> bool:
    return _TILE.fullmatch(path) is not None


def valid_base(base: str) -> bool:
    try:
        parsed = urlsplit(base)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and all(part not in (".", "..") for part in parsed.path.split("/"))
            and re.fullmatch(r"/[A-Za-z0-9_/-]*|", parsed.path) is not None
        )
    except ValueError:
        return False


class RedirectRefused(AddressFailure):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        raise RedirectRefused


def tile_opener(request: Request, timeout: float) -> object:
    return build_opener(NoRedirect()).open(request, timeout=timeout)


def fetch_tile(
    opener: Callable[..., object],
    base: str,
    path: str,
    key: str,
    *,
    satellite: bool,
    native: Target | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    if not valid_base(base):
        raise AddressFailure
    parameter = "token" if satellite else "key"
    query = {parameter: key}
    url = base.rstrip("/") + "/" + path
    if native is not None:
        if satellite:
            raise AddressFailure
        origin = urlsplit(base)
        url = f"{origin.scheme}://{origin.netloc}{native.path}"
        if native.session is not None:
            query["session"] = native.session
    request = Request(url + "?" + urlencode(query))
    request.add_header("Cache-Control", "no-store")
    status: int | None = None

    def remember_status(value: int) -> None:
        nonlocal status
        status = value

    try:
        return exchange_metadata(opener, request, on_status=remember_status)
    except HTTPError as error:
        error.close()
        return error.code, b"", {}
    except Exception as error:
        if satellite:
            return 503, b"", {"x-eii-error-code": reason(error)}
        if status is not None and 200 <= status < 300:
            raise BillableFailure(reason(error)) from None
        if isinstance(error, RedirectRefused):
            return 503, b"", {"x-eii-error-code": reason(error)}
        # No trustworthy billable result: leave Budget.request's pending entry unresolved.
        raise AddressFailure(reason(error)) from None


def safe_response(raw: bytes, headers: dict[str, str], key: str) -> bool:
    """Refuse a provider echo, including escaped JSON forms of the key."""
    try:
        decoded = json.dumps(json.loads(raw), ensure_ascii=False)
    except (ValueError, UnicodeError):
        decoded = ""
    escaped = json.dumps(key)[1:-1].encode()
    return (
        key.encode() not in raw
        and escaped not in raw
        and key not in decoded
        and not any(key in value for value in headers.values())
    )


def satellite_credit(opener: Callable[..., object], base: str, key: str) -> str:
    """Service metadata copyrightText; fixture-tested, not live-verified."""
    request = Request(base.rstrip("/") + "?" + urlencode({"f": "json", "token": key}))
    request.add_header("Cache-Control", "no-store")
    try:
        status, raw, headers = exchange_metadata(opener, request)
        if status != 200 or not safe_response(raw, headers, key):
            return ""
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return ""
        credit = payload.get("copyrightText")
        if not isinstance(credit, str):
            return ""
        return credit
    except Exception as error:
        raise AddressFailure(reason(error)) from None
