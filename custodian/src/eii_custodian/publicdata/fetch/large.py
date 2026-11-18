"""Required large-source intake: fixed chunks, complete hashes, immutable files.

The owner ruling of 2026-11-18 requires retaining these inputs' value. Binary
files and the imports array stream to a staged file; only individual import
objects are decoded, under the existing general intake bound. Overture keeps
its recorded exact size and ETag. No incomplete body can become a snapshot.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TextIO

from eii_custodian.publicdata.additions.common import (
    AdditionError,
    observe_period_bounds,
    parse_period_rule,
)

from . import transport as transport_module
from .allowlist import approve, host_of
from .checks import count_value_failure, period_failure, schema_failure
from .kinds import _metadata_url, portal_metadata, read_bounded
from .receipts import sidecar_for
from .registry import Entry, undeclared_public_split
from .snapshots import publish_file
from .transport import Response, StreamTransport, Transport, public_address

REQUIRED_KEYS = (
    "cus_imp_2019",
    "trade_ext/qatar-imports-2014-2018",
    "places_ovt/part-00014",
    "bldg_ovt/part-00288",
    "bldg_ovt/part-00384",
    "bldg_ovt/part-00385",
    "bldg_wsf3d",
)
JSON_CHUNK_CHARS = 65536
# An object cannot occupy more than the former whole-export memory allowance.
JSON_ROW_CHARS = transport_module.INTAKE_CEILING_BYTES


class IntakeError(ValueError):
    """Closed failure name; never an upstream diagnostic or source value."""


@dataclass(frozen=True)
class Received:
    sha256: str
    nbytes: int
    final_url: str


@dataclass(frozen=True)
class Fetched:
    digest: str
    fetch_host: str
    retrieved_utc: str
    terms_sha256: str = ""
    terms_unread: str = ""
    # Ruling L-1025 item b (applying L-1001 and L-1016): the streamed path
    # records the same pending licence state as the ordinary path.
    licence_pending: str = ""
    licence_unstated: bool = False


def recorded_size(entry: Entry) -> int | None:
    """Reuse the places reader's reviewed exact-byte declaration."""
    if entry.key.startswith(("places_ovt/", "bldg_ovt/")):
        from ..places.fetch import _recorded

        record, failure = _recorded(entry)
        if failure is not None or record is None:
            raise IntakeError(failure.check if failure else "recorded_size")
        return record[0]
    return None


def recorded_etag(entry: Entry) -> str | None:
    """Return the quoted, reviewed ETag, never an inferred hash."""
    if entry.key.startswith(("places_ovt/", "bldg_ovt/")):
        from ..places.fetch import _recorded

        record, failure = _recorded(entry)
        if failure is not None or record is None:
            raise IntakeError(failure.check if failure else "recorded_etag")
        return '"' + record[1] + '"'
    return None


def receive(entry: Entry, stream: StreamTransport, output: IO[bytes]) -> Received:
    """Hash and write each fixed chunk; never concatenate the response body."""
    if entry.key not in REQUIRED_KEYS:
        raise IntakeError("stream_source")
    if not approve(entry.url).ok:
        raise IntakeError("blocked_host")
    size = recorded_size(entry)
    cap = transport_module._METADATA_LIMIT.get()
    with stream(entry.url) as response:
        for address in (*response.hops, response.final_url):
            if not approve(address).ok:
                raise IntakeError("blocked_host")
        length = response.declared_length
        if length is not None and (type(length) is not int or length < 0):
            raise IntakeError("declared_length")
        if size is not None and length is not None and length != size:
            raise IntakeError("size_mismatch")
        if cap is not None and length is not None and length > cap:
            raise IntakeError("body_bytes")
        if size is not None:
            from ..places.fetch import _etag

            seen, failure = _etag(Response(response.final_url, b"", (), response.etag))
            if failure is not None:
                raise IntakeError(failure)
            if '"' + seen + '"' != recorded_etag(entry):
                raise IntakeError("etag_mismatch")
        digest = hashlib.sha256()
        count = 0
        for chunk in response.chunks:
            if type(chunk) is not bytes or len(chunk) > 65536:
                raise IntakeError("stream_chunk")
            count += len(chunk)
            if size is not None and count > size:
                raise IntakeError("size_mismatch")
            if cap is not None and count > cap:
                raise IntakeError("body_bytes")
            if length is not None and count > length:
                raise IntakeError("length_mismatch")
            output.write(chunk)
            digest.update(chunk)
        if length is not None and count != length:
            raise IntakeError("length_mismatch")
        if size is not None and count != size:
            raise IntakeError("size_mismatch")
        if not count:
            raise IntakeError("empty_body")
        return Received(digest.hexdigest(), count, public_address(response.final_url))


def json_rows(source: TextIO) -> Iterator[dict[str, object]]:
    """Decode one array object at a time, with bounded retained text.

    JSON whitespace, separators and the trailing EOF are checked explicitly;
    raw_decode validates strings, escapes and nested values within each object.
    """
    buffer = ""
    eof = False
    decoder = json.JSONDecoder()

    def refill() -> None:
        nonlocal buffer, eof
        part = source.read(JSON_CHUNK_CHARS)
        eof = not part
        buffer += part

    def whitespace() -> None:
        nonlocal buffer
        while True:
            buffer = buffer.lstrip(" \t\r\n")
            if buffer or eof:
                return
            refill()

    whitespace()
    if not buffer.startswith("["):
        raise IntakeError("portal_json")
    buffer = buffer[1:]
    whitespace()
    if buffer.startswith("]"):
        buffer = buffer[1:]
    else:
        while True:
            whitespace()
            if not buffer.startswith("{"):
                raise IntakeError("portal_json")
            while True:
                try:
                    row, end = decoder.raw_decode(buffer)
                except ValueError:
                    if eof:
                        raise IntakeError("portal_json") from None
                    if len(buffer) > JSON_ROW_CHARS:
                        raise IntakeError("portal_row_bytes") from None
                    refill()
                else:
                    break
            if end > JSON_ROW_CHARS:
                raise IntakeError("portal_row_bytes")
            buffer = buffer[end:]
            yield row
            whitespace()
            if buffer.startswith("]"):
                buffer = buffer[1:]
                break
            if not buffer.startswith(","):
                raise IntakeError("portal_json")
            buffer = buffer[1:]
    whitespace()
    if buffer:
        raise IntakeError("portal_json")


@dataclass(frozen=True)
class RowSummary:
    count: int
    first: str = ""
    last: str = ""
    periods_observed: bool = False


def _check_imports(entry: Entry, staged: Path) -> RowSummary:
    """Keep schema, split, count and declared period gates one row at a time."""
    if entry.key == "cus_imp_2019" and (entry.period_field or entry.period_last):
        raise IntakeError("stream_contract_changed")
    rule = None
    if entry.key == "trade_ext/qatar-imports-2014-2018":
        try:
            rule = parse_period_rule(entry.period_field)
        except AdditionError as error:
            raise IntakeError(error.name) from None
        if rule.sit != "row" or rule.form != "date":
            raise IntakeError("stream_contract_changed")
    count = 0
    first, last = "", ""
    endpoints: list[object] = []
    with staged.open("r", encoding="utf-8") as source:
        try:
            for row in json_rows(source):
                failure = schema_failure(entry, [row], entry.url)
                if failure is not None:
                    raise IntakeError(failure.check)
                if undeclared_public_split(entry, list(row)):
                    raise IntakeError("public_split_undeclared")
                if rule is not None:
                    try:
                        low, high = observe_period_bounds([row], rule)
                    except AdditionError as error:
                        raise IntakeError(error.name) from None
                    if not endpoints:
                        endpoints = [row, row]
                        first, last = low, high
                    else:
                        if low < first:
                            endpoints[0], first = row, low
                        if high > last:
                            endpoints[1], last = row, high
                count += 1
        except UnicodeError:
            raise IntakeError("portal_json") from None
    failure = count_value_failure(entry, count, entry.url)
    if failure is None and not count:
        failure = schema_failure(entry, [], entry.url)
    if failure is not None:
        raise IntakeError(failure.check)
    failure = period_failure(entry, endpoints, entry.url)
    if failure is not None:
        raise IntakeError(failure.check)
    return RowSummary(count, first, last, rule is not None)


def fetch_large(
    entry: Entry,
    transport: Transport,
    stream: StreamTransport,
    cache: Path,
    clock: Callable[[], str],
    sleep: Callable[[float], None],
) -> Fetched:
    """Validate the complete download before publishing a dated file and receipt."""
    info = None
    if entry.kind == "portal_dataset":
        metadata, failure = read_bounded(transport, sleep, _metadata_url(entry.url))
        if failure is not None or metadata is None:
            raise IntakeError(failure.check if failure else "metadata_unreadable")
        info = portal_metadata(entry, metadata)
        if info.failure is not None:
            raise IntakeError(info.failure.check)
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".large-", dir=cache) as folder:
        staged = Path(folder) / "body"
        with staged.open("wb") as output:
            received = receive(entry, stream, output)
        summary = _check_imports(entry, staged) if info is not None else None
        retrieved = clock()
        sidecar = sidecar_for(
            entry,
            digest=received.sha256,
            nbytes=received.nbytes,
            fetch_url=received.final_url,
            fetch_host=host_of(received.final_url),
            retrieved_utc=retrieved,
            publisher=info.publisher if info is not None else entry.publisher,
            source_modified=info.source_modified if info is not None else "",
            row_count=summary.count if summary is not None else None,
            observed_periods=(
                (summary.first, summary.last)
                if summary is not None and summary.periods_observed
                else None
            ),
            terms_sha256="",
            portal_licence=info.portal_licence if info is not None else "",
            portal_licence_url=info.portal_licence_url if info is not None else "",
        )
        if info is not None and info.licence_unstated:
            # Ruling L-1025 item b (applying L-1016 and L-1001): the streamed
            # path records the same pending licence as the ordinary path, with
            # the date read in retrieved_utc, and fails nothing.
            sidecar["licence_review"] = "pending"
        publish_file(
            cache / entry.key, entry.extension, staged, sidecar, compatibility=True
        )
    return Fetched(
        received.sha256,
        host_of(received.final_url),
        retrieved,
        licence_pending=info.licence_pending if info is not None else "",
        licence_unstated=info.licence_unstated if info is not None else False,
    )
