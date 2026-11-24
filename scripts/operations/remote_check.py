"""The checks of ``./eii remote-check``: presence and shape, never a number.

The command's own reader asks Health and the streamed answer of the HTTPS
origin of the owner's host; the pinned browser runner reports the other five
items in one closed result file. Every outcome is PASS or one closed reason.
The host is never part of a line.
"""

from __future__ import annotations

import codecs
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from operations import remote
from operations.common import Refusal

# The bounds of document 13, section 6: judgements for the lead to confirm.
CONNECT_SECONDS = 5.0
READ_SECONDS = 10.0
ITEM_SECONDS = 30.0
HEALTH_BYTES = 65_536
STREAM_BYTES = 1_048_576
BROWSER_SECONDS = 180.0
BROWSER_STEP_SECONDS = 15.0  # Held by the runner; pinned here against its file.
RESULT_BYTES = 65_536
CHUNK = 65_536  # bytes of one read.

RESULT_SCHEMA = "remote_check_browser.v1"
EVENTS_PATH = re.compile(r"/api/answers/[a-f0-9-]+/events\Z")
FRAME_ID = re.compile(r"[0-9]{1,9}\Z")
KINDS = frozenset(
    {
        "plan_step",
        "stage",
        "evidence",
        "receipt",
        "status",
        "narrative",
        "done",
        "error",
    }
)
PAGE_REASONS = (
    "page_no_response",
    "page_status_unexpected",
    "page_not_rendered",
    "page_language_mismatch",
    "page_direction_mismatch",
)
# The closed reasons of each browser item, as the runner's own module lists them.
ITEM_REASONS: Mapping[str, tuple[str, ...]] = {
    "start_page_en": PAGE_REASONS,
    "start_page_ar": PAGE_REASONS,
    "card": (
        "card_ui_unavailable",
        "card_selection_unresolved",
        "card_playbook_refused",
        "card_stream_refused",
        "card_tool_refused",
        "card_no_data",
        "card_lineage_unanswered",
        "card_lineage_mismatch",
        "card_missing",
        "card_fact_chip_missing",
        "card_fact_binding_mismatch",
    ),
    "map_style": (
        "map_unavailable",
        "release_unanswered",
        "style_source_mismatch",
        "style_glyphs_mismatch",
        "style_layers_missing",
    ),
    "tile": ("tile_no_range_response", "tile_status_unexpected", "tile_not_rendered"),
}
BROWSER_REASONS = (
    "browser_unavailable",
    "browser_timeout",
    "browser_failed",
    "browser_result_missing",
    "browser_result_invalid",
)
# The printed order: the command's Health, the browser's five, the stream.
LABELS: Mapping[str, str] = {
    "health": "health",
    "start_page_en": "start page (en)",
    "start_page_ar": "start page (ar)",
    "card": "card with fact chip",
    "map_style": "map style",
    "tile": "tile",
    "stream": "streamed answer",
}
NO_STATUS = "no HTTP status was received"
# Health reasons after which no response says whether tunnel or product failed.
UNDECIDED = frozenset(
    {"no_response", "tls_failed", "response_timeout", "status_unexpected"}
)
NOT_SERVING = frozenset({"entry_upstream_unavailable", "entry_route_unavailable"})
SENTENCES = (
    "every item passed",
    "the entry answered and public exposure is not authorised",
    "the entry answered and the product is not serving",
    "the entry answered and refused the check's request",
    "the tunnel or the product is down, and the responses cannot establish which",
    # No response is claimed here: nothing above established one (R3-F3).
    "the failed items above failed on content, or the browser could not run",
)
_INVALID: Any = object()


@dataclass(frozen=True)
class Limits:
    connect: float = CONNECT_SECONDS
    read: float = READ_SECONDS
    item: float = ITEM_SECONDS
    health: int = HEALTH_BYTES
    stream: int = STREAM_BYTES


@dataclass(frozen=True)
class Outcome:
    """One item: its HTTP status if one was received, and ``None`` or a reason."""

    status: int | None
    reason: str | None
    entry: bool = False  # The reason is the entry's own closed body.


Opener = Callable[[str, str, float], http.client.HTTPConnection]


def loaded(text: str | bytes) -> Any:
    """Strict JSON: a repeated key or a non-finite constant is not JSON."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        if len({key for key, _ in items}) != len(items):
            raise ValueError("repeated")
        return dict(items)

    def constant(_: str) -> Any:
        raise ValueError("constant")

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError):
        return _INVALID


def system_addresses(host: str) -> list[str]:
    found = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    return [str(entry[4][0]) for entry in found]


def resolved(host: str, resolve: Callable[[str], Sequence[str]]) -> str:
    """The address the command connects to: the first one its resolver gave."""
    try:
        addresses = [str(address) for address in resolve(host)]
        parsed = [ipaddress.ip_address(address) for address in addresses]
    except Exception:
        parsed = []
    if not parsed:
        raise Refusal("remote_host_unresolved", 2)
    if any(local(address) for address in parsed):
        # A mistaken setting: the check must leave through the tunnel.
        raise Refusal("remote_host_loopback", 2)
    return addresses[0]


def local(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # Both properties read through an IPv4-mapped address on the pinned Python.
    return bool(address.is_loopback or address.is_unspecified)


def verified_context() -> ssl.SSLContext:
    return ssl.create_default_context()


class Pinned(http.client.HTTPSConnection):
    """Connect to the checked address; the name serves the certificate check."""

    def __init__(self, address: str, host: str, timeout: float, tls: ssl.SSLContext):
        super().__init__(host, 443, timeout=timeout, context=tls)
        self.address, self.tls = address, tls

    def connect(self) -> None:
        raw = socket.create_connection((self.address, 443), self.timeout)
        self.sock = self.tls.wrap_socket(raw, server_hostname=self.host)


def default_opener(address: str, host: str, timeout: float) -> Pinned:
    tls = verified_context()
    if tls.verify_mode is not ssl.CERT_REQUIRED or not tls.check_hostname:
        raise Refusal("tls_failed")
    return Pinned(address, host, timeout, tls)


def bounded(sock: Any, seconds: float) -> None:
    try:
        sock.settimeout(seconds)
    except OSError:
        pass  # Already closed: the read that follows returns at once.


def chunks(
    response: http.client.HTTPResponse,
    sock: Any,
    limit: int,
    read: float,
    deadline: float,
) -> Iterator[bytes]:
    """The body, one read at a time, under the size, read and item bounds."""
    total = 0
    while not response.isclosed():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        bounded(sock, min(read, remaining))
        try:
            chunk = response.read1(CHUNK)
        except TimeoutError:
            raise
        except (OSError, http.client.HTTPException):
            return  # A cut body is decided by its content rule, never passed.
        if not chunk:
            return
        total += len(chunk)
        if total > limit:
            raise Refusal("response_too_large")
        yield chunk


def other_status(status: int, location: str | None, body: Callable[[], bytes]) -> str:
    """An answer that is not 200: the entry's own reason, or a refusal."""
    if 300 <= status < 400 and location is not None:
        raise Refusal("redirect_refused")
    reason = remote.entry_reason(status, body())
    if reason is None:
        raise Refusal("status_unexpected")
    return reason


def health_document(body: bytes) -> dict[str, Any]:
    """The closed Health document, or an empty mapping when it is not one."""
    from eii_product.api.health import Health

    document = loaded(body)
    try:
        return Health.model_validate(document).model_dump()
    except ValueError:
        return {}


def health_rule(body: bytes) -> None:
    document = health_document(body)
    if not document:
        raise Refusal("health_malformed")
    if document.get("status") != "ok":
        raise Refusal("health_not_ok")


def stream_head(kind: str | None, length: str | None, encoding: str | None) -> None:
    if (kind or "").split(";")[0].strip().lower() != "text/event-stream":
        raise Refusal("stream_type_invalid")
    if length is not None:
        raise Refusal("stream_length_fixed")
    if encoding is not None:
        raise Refusal("stream_encoded")


def frame_fields(block: str) -> tuple[str, str, Any] | None:
    """One frame's id, kind and data; ``None`` when it is not a closed frame."""
    lines = block.split("\n")
    found = {
        name: [line[len(name) + 2 :] for line in lines if line.startswith(name + ": ")]
        for name in ("id", "event", "data")
    }
    if sum(len(values) for values in found.values()) != len(lines):
        return None
    if len(found["event"]) != 1:
        return None
    if found["event"][0] not in KINDS:
        return None
    if len(found["id"]) != 1 or not FRAME_ID.match(found["id"][0]):
        return None
    data = loaded("\n".join(found["data"]))  # No data line is no JSON either.
    if data is _INVALID:
        return None
    # The web reader's own contract: only a narrative frame may be a non-object.
    if found["event"][0] != "narrative" and type(data) is not dict:
        return None
    return found["id"][0], found["event"][0], data


@dataclass
class Frames:
    """Frames decided as they arrive; nothing is kept but ids and the end."""

    seen: set[str] = field(default_factory=set)
    done: bool = False
    pending: str = ""
    decoder: Any = field(default_factory=codecs.getincrementaldecoder("utf-8"))

    def feed(self, chunk: bytes) -> None:
        try:
            self.pending += self.decoder.decode(chunk)
        except UnicodeDecodeError:
            raise Refusal("stream_frame_malformed") from None
        *complete, self.pending = self.pending.replace("\r\n", "\n").split("\n\n")
        for block in complete:
            if block.strip():
                self.frame(block)

    def frame(self, block: str) -> None:
        if self.done:
            raise Refusal("stream_order_invalid")
        fields = frame_fields(block)
        if fields is None:
            raise Refusal("stream_frame_malformed")
        if fields[0] in self.seen:
            raise Refusal("stream_order_invalid")
        if fields[1] == "error":
            raise Refusal("stream_error_event")
        self.seen.add(fields[0])
        self.done = fields[1] == "done"

    def end(self) -> None:
        if self.pending.strip() or self.decoder.getstate()[0]:
            raise Refusal("stream_truncated")
        if not self.done:
            raise Refusal("stream_truncated")


def item_shape(name: str, item: Any) -> bool:
    if type(item) is not dict or set(item) != {"status", "reason"}:
        return False
    status, reason = item["status"], item["reason"]
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        return False
    if reason is None:
        return status is not None
    return type(reason) is str and reason in ITEM_REASONS[name]


def result_shape(document: Any) -> bool:
    if type(document) is not dict or set(document) != {
        "schema",
        "items",
        "events_path",
    }:
        return False
    if document["schema"] != RESULT_SCHEMA:
        return False
    items, path = document["items"], document["events_path"]
    if type(items) is not dict or set(items) != set(ITEM_REASONS):
        return False
    if path is not None and (type(path) is not str or not EVENTS_PATH.match(path)):
        return False
    return all(item_shape(name, items[name]) for name in ITEM_REASONS)


def browser_result(raw: bytes) -> tuple[dict[str, Outcome], str | None]:
    """The five browser outcomes and the events address the page was given."""
    document = loaded(raw) if len(raw) <= RESULT_BYTES else _INVALID
    if not result_shape(document):
        raise Refusal("browser_result_invalid")
    outcomes = {
        name: Outcome(item["status"], item["reason"])
        for name, item in document["items"].items()
    }
    return outcomes, document["events_path"]


def browser_items(
    browse: Callable[[], bytes],
) -> tuple[dict[str, Outcome], str | None]:
    """A browser that could not report fails all five items with one reason."""
    try:
        return browser_result(browse())
    except Refusal as refusal:
        reason = (
            refusal.reason if refusal.reason in BROWSER_REASONS else "browser_failed"
        )
        return {name: Outcome(None, reason) for name in ITEM_REASONS}, None


def exchange(
    opener: Opener,
    address: str,
    host: str,
    path: str,
    limits: Limits,
    decide: Callable[[http.client.HTTPResponse, Callable[[int], Iterator[bytes]]], Any],
) -> Outcome:
    """One bounded GET on its own connection; no redirect is followed."""
    deadline = time.monotonic() + limits.item
    status: int | None = None
    connection: http.client.HTTPConnection | None = None
    try:
        connection = opener(address, host, limits.connect)
        connection.connect()
        sock = connection.sock
        bounded(sock, limits.read)
        connection.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
        connection.putheader("Host", host)
        connection.putheader("Accept-Encoding", "identity")
        connection.endheaders()
        response = connection.getresponse()
        status = response.status

        def body(limit: int) -> Iterator[bytes]:
            return chunks(response, sock, limit, limits.read, deadline)

        if status != 200:
            location = response.getheader("Location")
            entry = other_status(
                status, location, lambda: b"".join(body(limits.health))
            )
            return Outcome(status, entry, entry=True)
        decide(response, body)
        return Outcome(status, None)
    except Refusal as refusal:
        return Outcome(status, refusal.reason)
    except TimeoutError:
        return Outcome(status, "response_timeout")
    except ssl.SSLError:
        return Outcome(status, "tls_failed")
    except (OSError, http.client.HTTPException):
        return Outcome(None, "no_response")
    finally:
        if connection is not None:
            connection.close()


def check_health(opener: Opener, address: str, host: str, limits: Limits) -> Outcome:
    def decide(_: Any, body: Callable[[int], Iterator[bytes]]) -> None:
        health_rule(b"".join(body(limits.health)))

    return exchange(opener, address, host, "/health", limits, decide)


def check_stream(
    opener: Opener, address: str, host: str, path: str | None, limits: Limits
) -> Outcome:
    if path is None:
        # Withheld: the page was given no events address, so nothing is asked.
        return Outcome(None, "stream_answer_unavailable")

    def decide(response: Any, body: Callable[[int], Iterator[bytes]]) -> None:
        stream_head(
            response.getheader("Content-Type"),
            response.getheader("Content-Length"),
            response.getheader("Content-Encoding"),
        )
        frames = Frames()
        for chunk in body(limits.stream):
            frames.feed(chunk)
        frames.end()

    return exchange(opener, address, host, path, limits, decide)


def check(
    opener: Opener,
    address: str,
    host: str,
    browse: Callable[[], bytes],
    limits: Limits | None = None,
) -> dict[str, Outcome]:
    """Every item, in the printed order; nothing is skipped."""
    limits = limits or Limits()
    outcomes = {"health": check_health(opener, address, host, limits)}
    browser, path = browser_items(browse)
    outcomes.update(browser)
    outcomes["stream"] = check_stream(opener, address, host, path, limits)
    return outcomes


def closing(outcomes: Mapping[str, Outcome]) -> str:
    """One of six closed sentences, limited to what the responses establish."""
    entry = {outcome.reason for outcome in outcomes.values() if outcome.entry}
    if all(outcome.reason is None for outcome in outcomes.values()):
        return SENTENCES[0]
    if "remote_exposure_required" in entry:
        return SENTENCES[1]
    if entry & NOT_SERVING:
        return SENTENCES[2]
    if entry:
        return SENTENCES[3]
    if outcomes["health"].reason in UNDECIDED:
        return SENTENCES[4]
    return SENTENCES[5]


def lines(outcomes: Mapping[str, Outcome]) -> list[str]:
    """One PASS or FAIL line per item, then the closing line; never the host."""
    written = []
    for name, label in LABELS.items():
        outcome = outcomes[name]
        seen = NO_STATUS if outcome.status is None else f"HTTP {outcome.status}"
        if outcome.reason is None:
            written.append(f"PASS {label}: {seen}")
        else:
            written.append(f"FAIL {label}: {seen}: {outcome.reason}")
    return [*written, "remote-check: " + closing(outcomes)]
