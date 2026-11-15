"""Fetch one concrete Overture file through the existing transport seam."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from eii_custodian.publicdata.fetch.allowlist import approve, host_of
from eii_custodian.publicdata.fetch.receipts import (
    cache_directory,
    commit_pair,
    sha256_hex,
    sidecar_for,
)
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.transport import Response, Transport, TransportFault

FILE_KEYS = (
    "places_ovt/part-00014",
    "bldg_ovt/part-00288",
    "bldg_ovt/part-00384",
    "bldg_ovt/part-00385",
)
Clock = Callable[[], str]
Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class FileFailure:
    """A fetch check that stored no file."""

    code: int
    url: str
    check: str
    expected: str
    observed: str


@dataclass(frozen=True)
class FileFetch:
    """Digest and host of one whole file."""

    digest: str
    host: str


def is_place_file(entry: Entry) -> bool:
    """True for an appended concrete file that this task fetches."""
    return entry.key in FILE_KEYS and entry.skip_reason == ""


def fetch_place_file(
    entry: Entry,
    transport: Transport,
    cache: Path,
    clock: Clock,
    sleep: Sleeper,
) -> tuple[FileFetch | None, FileFailure | None]:
    """Fetch the whole file once. Size and ETag are the recorded registry values."""
    del sleep
    if _ranged(entry.url):
        return None, FileFailure(1, entry.url, "byte_range", "whole file", entry.url)
    decision = approve(entry.url)
    if not decision.ok:
        return None, FileFailure(
            1, entry.url, "blocked_host", "allow-listed host", entry.url
        )
    recorded, failure = _recorded(entry)
    if failure is not None or recorded is None:
        return None, failure
    try:
        response = transport(entry.url)
    except TransportFault as exc:
        return None, _fault(exc)
    for hop in (*response.hops, response.final_url):
        if not approve(hop).ok:
            return None, FileFailure(1, hop, "blocked_host", "allow-listed host", hop)
    size, etag = recorded
    if len(response.body) == 0:
        return None, FileFailure(1, response.final_url, "empty_body", str(size), "0")
    if len(response.body) != size:
        return None, FileFailure(
            1,
            response.final_url,
            "size_mismatch",
            str(size),
            str(len(response.body)),
        )
    observed, etag_check = _etag(response)
    if etag_check is not None:
        return None, FileFailure(1, response.final_url, etag_check, etag, observed)
    if observed != etag:
        return None, FileFailure(1, response.final_url, "etag_mismatch", etag, observed)
    digest = sha256_hex(response.body)
    sidecar = sidecar_for(
        entry,
        digest=digest,
        nbytes=len(response.body),
        fetch_url=response.final_url,
        fetch_host=host_of(response.final_url),
        retrieved_utc=clock(),
        publisher=entry.publisher,
        source_modified="",
        row_count=None,
        terms_sha256="",
        switched_off=False,
    )
    commit_pair(
        cache_directory(cache, entry.key),
        digest,
        entry.extension or "parquet",
        response.body,
        sidecar,
    )
    return FileFetch(digest, host_of(response.final_url)), None


def _ranged(url: str) -> bool:
    lowered = url.casefold()
    return "bytes=" in lowered or "range=" in lowered


_BYTES_PREFIX = "recorded_bytes: "
_ETAG_PREFIX = "recorded_etag: "


def _recorded(entry: Entry) -> tuple[tuple[int, str] | None, FileFailure | None]:
    sizes: list[str] = []
    etags: list[str] = []
    size_malformed = False
    etag_malformed = False
    for line in entry.basis_note.splitlines():
        if line.startswith("recorded_bytes:"):
            if line.startswith(_BYTES_PREFIX):
                sizes.append(line[len(_BYTES_PREFIX) :])
            else:
                size_malformed = True
        elif line.startswith("recorded_etag:"):
            if line.startswith(_ETAG_PREFIX):
                etags.append(line[len(_ETAG_PREFIX) :])
            else:
                etag_malformed = True
    if (
        size_malformed
        or len(sizes) != 1
        or not _positive_size(sizes[0] if sizes else "")
    ):
        observed = sizes[0] if len(sizes) == 1 else ""
        return None, FileFailure(1, entry.url, "recorded_size", "bytes", observed)
    if etag_malformed or len(etags) != 1 or not _etag_token(etags[0] if etags else ""):
        observed = etags[0] if len(etags) == 1 else ""
        return None, FileFailure(1, entry.url, "recorded_etag", "etag", observed)
    return (int(sizes[0]), etags[0]), None


def _positive_size(text: str) -> bool:
    return text.isdecimal() and int(text) > 0


def _etag_token(text: str) -> bool:
    if text == "" or text.startswith("W/") or '"' in text:
        return False
    return all(not char.isspace() for char in text)


def _etag(response: Response) -> tuple[str, str | None]:
    value = response.etag
    if not isinstance(value, str):
        return "", "etag_unobserved"
    if value.startswith("W/"):
        return value, "etag_weak"
    if len(value) < 2 or not value.startswith('"') or not value.endswith('"'):
        return value, "etag_form"
    return value[1:-1], None


def _fault(exc: TransportFault) -> FileFailure:
    if exc.kind == "blocked_host":
        return FileFailure(1, exc.url, "blocked_host", "allow-listed host", exc.url)
    if exc.kind == "unreachable":
        return FileFailure(6, exc.url, "unreachable", "reachable host", "unreachable")
    return FileFailure(1, exc.url, "http_status", "http success", "http status")
