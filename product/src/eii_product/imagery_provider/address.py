"""Address search against the imagery provider. The key is an argument.

The request is the form documented for findAddressCandidates. Only the label
and the point are returned. Every failure is an empty signal with no provider
text. The live function is built by the caller and opens a connection only
when it is called.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request

FIND_ADDRESS_CANDIDATES = (
    "https://geocode-api.arcgis.com/arcgis/rest/services/"
    "World/GeocodeServer/findAddressCandidates"
)
MAX_LOCATIONS = 5
REQUEST_TIMEOUT_S = 5
_LON_LIMIT = 180
_LAT_LIMIT = 90


class AddressFailure(Exception):
    """The provider did not yield a usable result. The message is fixed."""

    def __init__(self) -> None:
        super().__init__("NOT_FOUND")


@dataclass(frozen=True)
class AddressHit:
    """One label and one point. Nothing else from the provider is kept."""

    label: str
    longitude: float
    latitude: float


def live_transport(
    opener: Callable[..., object],
) -> Callable[[str, str, str], tuple[AddressHit, ...]]:
    """Return the live call. Constructing it opens nothing."""

    def send(text: str, lang: str, key: str) -> tuple[AddressHit, ...]:
        body = urlencode(
            {
                "SingleLine": text,
                "f": "json",
                "maxLocations": str(MAX_LOCATIONS),
                "langCode": lang,
                "token": key,
            }
        ).encode("utf-8")
        request = Request(FIND_ADDRESS_CANDIDATES, data=body, method="POST")
        request.add_header("content-type", "application/x-www-form-urlencoded")
        try:
            status, raw = _exchange(opener, request)
        except AddressFailure:
            raise
        except (OSError, URLError, TimeoutError, ValueError):
            raise AddressFailure from None
        if status != 200:
            raise AddressFailure
        try:
            payload = json.loads(raw)
        except ValueError:
            raise AddressFailure from None
        return parse_candidates(payload)

    return send


def parse_candidates(payload: object) -> tuple[AddressHit, ...]:
    """Keep address and location. Drop score, attributes and extent."""
    if not isinstance(payload, dict):
        raise AddressFailure
    candidates = payload.get("candidates")
    if type(candidates) is not list:
        raise AddressFailure
    hits: list[AddressHit] = []
    for item in candidates:
        hits.append(_hit(item))
        if len(hits) == MAX_LOCATIONS:
            break
    return tuple(hits)


def _hit(item: object) -> AddressHit:
    if not isinstance(item, dict):
        raise AddressFailure
    label = item.get("address")
    location = item.get("location")
    if type(label) is not str or label == "" or not isinstance(location, dict):
        raise AddressFailure
    longitude = _axis(location.get("x"), _LON_LIMIT)
    latitude = _axis(location.get("y"), _LAT_LIMIT)
    return AddressHit(label, longitude, latitude)


def _axis(value: object, limit: int) -> float:
    if type(value) is not int and type(value) is not float:
        raise AddressFailure
    number = float(value)
    if not math.isfinite(number) or number < -limit or number > limit:
        raise AddressFailure
    return number


def _exchange(opener: Callable[..., object], request: Request) -> tuple[int, bytes]:
    status, raw, _headers = exchange_metadata(opener, request)
    return status, raw


def _metadata(response: object) -> dict[str, str]:
    headers = getattr(response, "headers", None)
    items = getattr(headers, "items", None)
    if not callable(items):
        return {}
    return {str(name).lower(): str(value) for name, value in items()}


def exchange_metadata(
    opener: Callable[..., object],
    request: Request,
    *,
    on_status: Callable[[int], None] | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    """Report status before reading; a failed body must not erase billing evidence."""
    response = opener(request, timeout=REQUEST_TIMEOUT_S)
    enter = getattr(response, "__enter__", None)
    leave = getattr(response, "__exit__", None)
    if callable(enter) and callable(leave):
        body = enter()
        try:
            status = _status(body)
            if on_status is not None:
                on_status(status)
            return status, _read(body), _metadata(body)
        finally:
            leave(None, None, None)
    try:
        status = _status(response)
        if on_status is not None:
            on_status(status)
        return status, _read(response), _metadata(response)
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _status(response: object) -> int:
    status = getattr(response, "status", None)
    if type(status) is int:
        return status
    getcode = getattr(response, "getcode", None)
    if callable(getcode):
        code = getcode()
        if type(code) is int:
            return code
    raise AddressFailure


def _read(response: object) -> bytes:
    read = getattr(response, "read", None)
    if not callable(read):
        raise AddressFailure
    raw = read()
    if type(raw) is not bytes:
        raise AddressFailure
    return raw
