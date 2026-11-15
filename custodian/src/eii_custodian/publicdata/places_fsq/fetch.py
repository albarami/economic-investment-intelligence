"""Fetch the pinned release through the existing transport seam.

One receipt is written for each file that the metadata selects. A summary
that names no file for the frame writes nothing and asks for no data file.
"""

from __future__ import annotations

import json
import os
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
from eii_custodian.publicdata.fetch.terms_text import terms_text_sha256
from eii_custodian.publicdata.fetch.transport import Response, Transport, TransportFault
from eii_custodian.publicdata.places_fsq.constants import (
    ATTRIBUTION,
    COPY_ROOT,
    COPYRIGHT_LINE,
    LICENCE_NAME,
    METHOD,
    PINNED_RELEASE,
    RELEASE_KEY,
)
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.select import (
    FRAME_BOX,
    coordinate_bounds,
    select_partitions,
)

Clock = Callable[[], str]
Sleeper = Callable[[float], None]
_SIGN_IN = ("sign in", "sign-in", "log in", "access token")


@dataclass(frozen=True)
class ReleaseFailure:
    """A fetch check that stored no complete manifest."""

    code: int
    url: str
    check: str
    expected: str
    observed: str


@dataclass(frozen=True)
class ReleaseFetch:
    """Manifest digest and host of a completed fetch."""

    digest: str
    host: str


def is_release_entry(entry: Entry) -> bool:
    """True for the appended release row and not for the skipped placeholder."""
    return entry.key == RELEASE_KEY and entry.skip_reason == ""


def fetch_release(
    entry: Entry,
    transport: Transport,
    cache: Path,
    clock: Clock,
    sleep: Sleeper,
) -> tuple[ReleaseFetch | None, ReleaseFailure | None]:
    """Fetch the metadata, the selected files and the licence text."""
    del sleep
    blocked = _blocked(entry)
    if blocked is not None:
        return None, blocked
    metadata, failure = _get(entry, transport, entry.url)
    if failure is not None or metadata is None:
        return None, failure
    refusal = _body_refusal(metadata.body, metadata.final_url, metadata=True)
    if refusal is not None:
        return None, refusal
    try:
        selected = select_partitions(metadata.body, PINNED_RELEASE, FRAME_BOX)
    except PlacesFsqError as exc:
        return None, ReleaseFailure(
            1, metadata.final_url, exc.reason, "files for the frame", "none"
        )
    terms_body = b""
    terms_url = entry.terms_url
    if terms_url:
        terms, failure = _get(entry, transport, terms_url)
        if failure is not None or terms is None:
            return None, failure
        refusal = _terms_refusal(terms.body, terms.final_url)
        if refusal is not None:
            return None, refusal
        terms_body = terms.body
        terms_url = terms.final_url
    stored: list[tuple[str, bytes, str]] = []
    for name in selected.files:
        url = _data_url(name)
        decision = approve(url)
        if not decision.ok:
            return None, ReleaseFailure(
                1, url, "blocked_host", "allow-listed host", url
            )
        response, failure = _get(entry, transport, url)
        if failure is not None or response is None:
            return None, failure
        refusal = _body_refusal(response.body, response.final_url, metadata=False)
        if refusal is not None:
            return None, refusal
        try:
            expected = coordinate_bounds(metadata.body, name)
            observed = coordinate_bounds(response.body)
            if observed != expected:
                raise PlacesFsqError("summary_stale")
        except PlacesFsqError as exc:
            return None, ReleaseFailure(
                1,
                response.final_url,
                exc.reason,
                "summary coordinate bounds",
                "file bounds differ or missing",
            )
        stored.append((name, response.body, response.final_url))
    retrieved = clock()
    digest = _store(
        entry,
        cache,
        metadata.body,
        stored,
        terms_body,
        terms_url,
        retrieved,
        host_of(metadata.final_url),
    )
    return ReleaseFetch(digest, host_of(metadata.final_url)), None


def _blocked(entry: Entry) -> ReleaseFailure | None:
    for url in (entry.url, entry.terms_url):
        if url and not approve(url).ok:
            return ReleaseFailure(1, url, "blocked_host", "allow-listed host", url)
    return None


def _get(
    entry: Entry, transport: Transport, url: str
) -> tuple[Response | None, ReleaseFailure | None]:
    del entry
    decision = approve(url)
    if not decision.ok:
        return None, ReleaseFailure(1, url, "blocked_host", "allow-listed host", url)
    try:
        response = transport(url)
    except TransportFault as exc:
        if exc.kind == "blocked_host":
            return None, ReleaseFailure(
                1, exc.url, "blocked_host", "allow-listed host", exc.url
            )
        if exc.kind == "unreachable":
            return None, ReleaseFailure(
                6, exc.url, "unreachable", "reachable host", "unreachable"
            )
        return None, ReleaseFailure(
            1, exc.url, "http_status", "http success", "http status"
        )
    for hop in (*response.hops, response.final_url):
        if not approve(hop).ok:
            return None, ReleaseFailure(
                1, hop, "blocked_host", "allow-listed host", hop
            )
    return response, None


def _body_refusal(body: bytes, url: str, *, metadata: bool) -> ReleaseFailure | None:
    if body.startswith(b"PAR1"):
        return None
    text = body[:4000].decode("utf-8", errors="replace").casefold()
    if any(mark in text for mark in _SIGN_IN):
        return ReleaseFailure(1, url, "sign_in_demand", "public file", "sign-in")
    check = "metadata_unreadable" if metadata else "not_parquet"
    return ReleaseFailure(1, url, check, "parquet", "other")


def _terms_refusal(body: bytes, url: str) -> ReleaseFailure | None:
    text = body.decode("utf-8", errors="replace")
    folded = text.casefold()
    if any(mark in folded for mark in _SIGN_IN):
        return ReleaseFailure(1, url, "sign_in_demand", "public file", "sign-in")
    if LICENCE_NAME not in text or COPYRIGHT_LINE not in text:
        return ReleaseFailure(
            1, url, "licence_mismatch", LICENCE_NAME, "licence text differs"
        )
    return None


def _data_url(file_path: str) -> str:
    name = file_path.rsplit("/", 1)[-1]
    return f"{COPY_ROOT}{PINNED_RELEASE}/places/{name}"


def _store(
    entry: Entry,
    cache: Path,
    metadata: bytes,
    files: list[tuple[str, bytes, str]],
    terms: bytes,
    terms_url: str,
    retrieved: str,
    host: str,
) -> str:
    directory = cache_directory(cache, entry.key)
    meta_digest = sha256_hex(metadata)
    file_rows: list[dict[str, object]] = []
    commit_pair(
        directory / "metadata",
        meta_digest,
        "parquet",
        metadata,
        _sidecar(entry, meta_digest, metadata, entry.url, host, retrieved, terms),
    )
    for name, body, url in files:
        digest = sha256_hex(body)
        commit_pair(
            directory / "files",
            digest,
            "parquet",
            body,
            _sidecar(entry, digest, body, url, host_of(url), retrieved, terms),
        )
        file_rows.append({"name": name, "sha256": digest, "bytes": len(body)})
    terms_digest = terms_text_sha256(terms) if terms else ""
    manifest = {
        "attribution": ATTRIBUTION,
        "files": file_rows,
        "metadata_sha256": meta_digest,
        "method": METHOD,
        "release": PINNED_RELEASE,
        "retrieved_utc": retrieved,
        "terms_sha256": terms_digest or None,
        "terms_url": terms_url or None,
    }
    payload = json.dumps(manifest, sort_keys=True).encode("utf-8")
    digest = sha256_hex(payload)
    final = directory / "manifest.json"
    partial = directory / ".manifest.json.partial"
    directory.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(payload)
    os.replace(partial, final)
    return digest


def _sidecar(
    entry: Entry,
    digest: str,
    body: bytes,
    url: str,
    host: str,
    retrieved: str,
    terms: bytes,
) -> dict[str, object]:
    return sidecar_for(
        entry,
        digest=digest,
        nbytes=len(body),
        fetch_url=url,
        fetch_host=host,
        retrieved_utc=retrieved,
        publisher=entry.publisher,
        source_modified=PINNED_RELEASE,
        row_count=None,
        terms_sha256=terms_text_sha256(terms) if terms else "",
        switched_off=False,
    )
