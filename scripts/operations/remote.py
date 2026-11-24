"""Pure admission, host, framing and cookie rules of the one entry (S3-T20).

Nothing here opens a socket. The 8088 socket is the tunnel's ingress, so no
request on it is local-privileged whatever Host it carries: whether it relays
at all is decided from durable state and the entry's own start (`admission`),
and every admitted request is rebuilt into one validated form (`rebuild`).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from operations.common import Refusal, encoded

HOST_NAME = "EII_REMOTE_HOST"
LOCAL_HOST = "localhost:8088"
BODY_LIMIT = 65_536  # bytes; equal to the API's largest accepted body.
READ_SECONDS = 10.0  # seconds per client read; a judgement, not a measurement.
GZIP_LIMIT = 4_194_304  # bytes of one upstream body the entry will compress.
PRESENTER_HEADER = "x-eii-presenter-token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
METHODS = SAFE_METHODS | {"POST"}
GZIP_TYPES = frozenset(
    {
        "text/html",
        "text/css",
        "text/plain",
        "text/javascript",
        "application/javascript",
        "application/json",
        "image/svg+xml",
    }
)
HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)
# Every closed reason the entry itself answers, with its HTTP status.
STATUS: Mapping[str, int] = {
    "entry_route_unavailable": 503,
    "entry_upstream_unavailable": 503,
    "remote_exposure_required": 503,
    "remote_host_missing": 503,
    "cookie_policy_refused": 502,
    "request_malformed": 400,
    "method_refused": 405,
    "request_read_timeout": 408,
    "host_header_invalid": 400,
    "host_refused": 403,
    "origin_header_invalid": 400,
    "origin_refused": 403,
    "target_form_refused": 400,
    "target_path_refused": 400,
    "header_syntax_refused": 400,
    "transfer_encoding_refused": 400,
    "content_length_invalid": 400,
    "request_body_refused": 400,
    "request_body_too_large": 413,
    "request_body_incomplete": 400,
    "presenter_remote_refused": 403,
}
ENTRY_REASONS = frozenset(STATUS)

_LABEL = "[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_NAME = re.compile("(?:" + _LABEL + r"\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_TOKEN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")
_VALUE = re.compile(r"[\t\x20-\x7e\x80-\xff]*\Z")
_DIGITS = re.compile(r"[0-9]{1,9}\Z")
_ESCAPE = re.compile(r"%(?:[0-9A-Fa-f]{2})?")
_QUERY = re.compile(r"[\x21\x24-\x7e]*\Z")
_SEGMENT_SAFE = "!$&'()*+,;=:@-._~"
_WEIGHT = re.compile(r"(?:1(?:\.0{0,3})?|0(?:\.[0-9]{0,3})?)\Z")


def remote_host(value: str) -> str:
    """One lower-case DNS name of two labels or more, and nothing else."""
    if value == "":
        raise Refusal("remote_host_missing")
    if (
        len(value) > 253
        or _NAME.fullmatch(value) is None
        or value.rsplit(".", 1)[1] == "localhost"
    ):
        raise Refusal("remote_host_invalid")
    return value


def take_host(environ: Mapping[str, str]) -> tuple[dict[str, str], str]:
    """Take the name out before the unchanged closed-list function refuses it."""
    rest = {key: value for key, value in environ.items() if key != HOST_NAME}
    return rest, environ.get(HOST_NAME, "")


def entry_environment(
    child: Mapping[str, str], exposure: object, raw_host: str
) -> dict[str, str]:
    """The entry child is the API child plus the host, on a public route only."""
    if exposure != "public_entry":
        return dict(child)
    return {**child, HOST_NAME: remote_host(raw_host)}


def entry_host(exposure: object, raw_host: str) -> str | None:
    """What this entry process holds: a public route without a host never starts."""
    if raw_host == "" and exposure != "public_entry":
        return None
    return remote_host(raw_host)


def bound(state: Path) -> bool:
    """P: the verified promotion log holds an authorised public request."""
    from operations.activation import entries

    return any(
        entry["request"]["exposure"] == "public_entry" for entry in entries(state)
    )


def admission(exposure: object, is_bound: bool, host_held: bool) -> None:
    """Decide relaying from E, P and H alone, before any caller input is read."""
    if exposure == "public_entry":
        if not host_held:
            raise Refusal("remote_host_missing")
        return
    if exposure != "loopback":
        raise Refusal("entry_route_unavailable")
    if is_bound:
        raise Refusal("remote_exposure_required")
    if host_held:
        raise Refusal("remote_exposure_required")


def expected_answer(exposure: object, is_bound: bool) -> str | None:
    """What an entry started by `up` must answer: None for relayed health."""
    try:
        admission(exposure, is_bound, exposure == "public_entry")
    except Refusal as refusal:
        return refusal.reason
    return None


def closed_body(reason: str) -> bytes:
    if reason not in ENTRY_REASONS:
        raise Refusal("entry_route_unavailable")
    return encoded({"error_code": reason, "status": "entry_refused"})


def entry_reason(status: int, body: bytes) -> str | None:
    """Recognise the entry's own body by exact bytes, list membership and status."""
    for reason, expected in STATUS.items():
        if status == expected and body == closed_body(reason):
            return reason
    return None


def header_rule(headers: Sequence[tuple[str, str]]) -> None:
    for name, value in headers:
        if _TOKEN.fullmatch(name) is None or _VALUE.fullmatch(value) is None:
            raise Refusal("header_syntax_refused")


def _values(headers: Sequence[tuple[str, str]], wanted: str) -> list[str]:
    return [value for name, value in headers if name.lower() == wanted]


def host_rule(values: Sequence[str], remote: str | None) -> str:
    if len(values) != 1:
        raise Refusal("host_header_invalid")
    admitted = {LOCAL_HOST}
    if remote is not None:
        admitted |= {remote, remote + ":443"}
    if values[0] not in admitted:
        raise Refusal("host_refused")
    return values[0]


def origin_of(host: str) -> str:
    if host == LOCAL_HOST:
        return "http://" + LOCAL_HOST
    return "https://" + host.removesuffix(":443")


def origin_rule(values: Sequence[str], method: str, host: str) -> None:
    if len(values) > 1:
        raise Refusal("origin_header_invalid")
    if not values:
        if method not in SAFE_METHODS:
            raise Refusal("origin_refused")
        return
    if values[0] != origin_of(host):
        raise Refusal("origin_refused")


def _decoded(segment: str) -> str:
    """Decode one segment once; an escape may not hide structure or control."""
    raw = bytearray()
    position = 0
    for match in _ESCAPE.finditer(segment):
        if len(match.group()) != 3:
            raise Refusal("target_path_refused")
        octet = int(match.group()[1:], 16)
        if octet in b"/\\.%":
            raise Refusal("target_path_refused")
        raw += segment[position : match.start()].encode("ascii")
        raw.append(octet)
        position = match.end()
    raw += segment[position:].encode("ascii")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Refusal("target_path_refused") from None
    if any(ord(char) < 0x20 or 0x7F <= ord(char) < 0xA0 for char in text):
        raise Refusal("target_path_refused")
    return text


def canonical_target(target: str) -> tuple[str, str]:
    """Return the decoded path decisions use and the entry's own re-encoding."""
    if not target.startswith("/"):
        raise Refusal("target_form_refused")
    path, mark, query = target.partition("?")
    if (
        not path.isascii()
        or any(ord(char) <= 0x20 or ord(char) == 0x7F for char in path)
        or "#" in path
        or "\\" in path
        or _QUERY.fullmatch(query) is None
    ):
        raise Refusal("target_path_refused")
    if path == "/":
        return "/", "/" + mark + query
    segments = [_decoded(segment) for segment in path[1:].split("/")]
    if any(segment in {"", ".", ".."} for segment in segments):
        raise Refusal("target_path_refused")
    forward = "/" + "/".join(quote(item, safe=_SEGMENT_SAFE) for item in segments)
    return "/" + "/".join(segments), forward + mark + query


def presenter_rule(path: str, headers: Sequence[tuple[str, str]]) -> None:
    """Presenter controls never cross this socket, for any Host or exposure."""
    if any(segment.casefold() == "presenter" for segment in path.split("/")) or any(
        name.lower() == PRESENTER_HEADER for name, _ in headers
    ):
        raise Refusal("presenter_remote_refused")


def body_length(method: str, headers: Sequence[tuple[str, str]]) -> int:
    if _values(headers, "transfer-encoding"):
        raise Refusal("transfer_encoding_refused")
    lengths = _values(headers, "content-length")
    if len(lengths) > 1 or (not lengths and method == "POST"):
        raise Refusal("content_length_invalid")
    if not lengths:
        return 0
    if _DIGITS.fullmatch(lengths[0]) is None:
        raise Refusal("content_length_invalid")
    length = int(lengths[0])
    if length and method != "POST":
        raise Refusal("request_body_refused")
    if length > BODY_LIMIT:
        raise Refusal("request_body_too_large")
    return length


def forward_headers(headers: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop hop-by-hop, client-nominated and forwarding headers; keep the rest."""
    nominated = {
        token.strip().lower()
        for value in _values(headers, "connection")
        for token in value.split(",")
    }
    dropped = HOP | nominated | {"forwarded", "content-length"}
    return [
        (name, value)
        for name, value in headers
        if name.lower() not in dropped and not name.lower().startswith("x-forwarded-")
    ]


@dataclass(frozen=True)
class Forward:
    """The one validated form of a request; only this is sent upstream."""

    method: str
    path: str
    target: str
    headers: tuple[tuple[str, str], ...]
    length: int


def rebuild(
    method: str, target: str, headers: Sequence[tuple[str, str]], remote: str | None
) -> Forward:
    if method not in METHODS:
        raise Refusal("method_refused")
    header_rule(headers)
    host = host_rule(_values(headers, "host"), remote)
    origin_rule(_values(headers, "origin"), method, host)
    path, forward = canonical_target(target)
    presenter_rule(path, headers)
    length = body_length(method, headers)
    return Forward(method, path, forward, tuple(forward_headers(headers)), length)


def _attributes(cookie: str) -> dict[str, str]:
    pairs = (part.strip().partition("=") for part in cookie.split(";")[1:])
    return {name.strip().lower(): value.strip().lower() for name, _, value in pairs}


def response_cookies(values: Sequence[str], public: bool) -> list[str]:
    """On a public route each cookie is Secure and carries a real SameSite."""
    if not public:
        return list(values)
    result = []
    for cookie in values:
        attributes = _attributes(cookie)
        if attributes.get("samesite") not in {"strict", "lax"}:
            raise Refusal("cookie_policy_refused")
        result.append(cookie if "secure" in attributes else cookie + "; Secure")
    return result


def relay_headers(
    headers: Sequence[tuple[str, str]], public: bool
) -> list[tuple[str, str]]:
    """Drop hop-by-hop fields and relay each Set-Cookie separately."""
    cookies = response_cookies(_values(headers, "set-cookie"), public)
    kept = [
        (name, value)
        for name, value in headers
        if name.lower() not in HOP | {"set-cookie"}
    ]
    return kept + [("Set-Cookie", cookie) for cookie in cookies]


def accepts_gzip(values: Sequence[str]) -> bool:
    for value in values:
        for part in value.split(","):
            coding, _, parameter = part.partition(";")
            if coding.strip().lower() != "gzip":
                continue
            name, _, weight = parameter.partition("=")
            if name.strip().lower() != "q":
                return parameter.strip() == ""
            weight = weight.strip()
            return _WEIGHT.fullmatch(weight) is not None and weight.strip("0.") != ""
    return False


def gzip_wanted(
    forward: Forward, status: int, response: Sequence[tuple[str, str]]
) -> bool:
    """Compress only a complete, listed, unencoded, bounded text answer."""
    lengths = _values(response, "content-length")
    kinds = _values(response, "content-type")
    return (
        forward.method == "GET"
        and status == 200
        and accepts_gzip(_values(forward.headers, "accept-encoding"))
        and not _values(forward.headers, "range")
        and not _values(response, "content-encoding")
        and not _values(response, "content-range")
        and len(kinds) == 1
        and kinds[0].split(";", 1)[0].strip().lower() in GZIP_TYPES
        and len(lengths) == 1
        and _DIGITS.fullmatch(lengths[0]) is not None
        and 0 < int(lengths[0]) <= GZIP_LIMIT
    )


def gzip_headers(
    headers: Sequence[tuple[str, str]], length: int
) -> list[tuple[str, str]]:
    """The compressed answer's own length, encoding and negotiation field."""
    varied = ", ".join([*_values(headers, "vary"), "Accept-Encoding"])
    kept = [
        (name, value)
        for name, value in headers
        if name.lower() not in {"content-length", "vary"}
    ]
    return [
        *kept,
        ("Content-Encoding", "gzip"),
        ("Content-Length", str(length)),
        ("Vary", varied),
    ]
