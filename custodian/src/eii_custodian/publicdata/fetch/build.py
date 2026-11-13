"""Orchestrate one public build: registry order, receipts, then the stage."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from eii_custodian.publicdata.fetch.allowlist import approve
from eii_custodian.publicdata.fetch.kinds import prepare, read_recorded_terms
from eii_custodian.publicdata.fetch.receipts import (
    cache_directory,
    commit_citation,
    commit_pair,
    sha256_hex,
    sidecar_for,
)
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.report import (
    REASON_CHANGED,
    REASON_FORBID,
    citation_line,
    coverage_line,
    fail_line,
    owner_changed_line,
    owner_line,
    pass_line,
    skip_line,
    terms_changed_line,
)
from eii_custodian.publicdata.fetch.terms_text import FINGERPRINT_VISIBLE_TEXT
from eii_custodian.publicdata.fetch.transport import Transport
from eii_custodian.publicdata.stage import run_stage

CACHE_RELATIVE = "data/public_cache"
LOG_NAME = "build-log.json"
Sleeper = Callable[[float], None]
Clock = Callable[[], str]


@dataclass(frozen=True)
class FetchFailure:
    """One failed check. code 6 is an unavailable network; code 1 is any other check."""

    code: int
    source_id: str
    url: str
    check: str
    expected: str
    observed: str

    @property
    def detail(self) -> str:
        """Return the failure detail: source, URL, check, expected value and observed value."""
        return (
            f"{self.source_id} {self.url} {self.check} "
            f"expected={self.expected} observed={self.observed}"
        )


@dataclass(frozen=True)
class BuildOutcome:
    """Lines for the command, and the first failure when the build cannot succeed."""

    lines: tuple[str, ...]
    failure: FetchFailure | None


@dataclass(frozen=True)
class _Fetched:
    """Digest, host, retrieval time and terms hash of the receipt this run wrote."""

    digest: str
    fetch_host: str
    retrieved_utc: str
    terms_sha256: str


def utc_now() -> str:
    """Return the current UTC time as the retrieval timestamp."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_entry(
    entry: Entry,
    transport: Transport,
    cache: Path,
    clock: Clock,
    sleep: Sleeper,
) -> FetchFailure | None:
    """Fetch one row. An unlisted host is refused before the transport is called."""
    _fetched, failure = _fetch_row(entry, transport, cache, clock, sleep)
    return failure


def _fetch_row(
    entry: Entry,
    transport: Transport,
    cache: Path,
    clock: Clock,
    sleep: Sleeper,
) -> tuple[_Fetched | None, FetchFailure | None]:
    """Fetch one row and return the receipt values this run wrote."""
    if entry.url and not approve(entry.url).ok:
        return None, FetchFailure(
            1,
            entry.source_id,
            entry.url,
            "blocked_host",
            "allow-listed host",
            entry.url,
        )
    if entry.terms_url and not approve(entry.terms_url).ok:
        return None, FetchFailure(
            1,
            entry.source_id,
            entry.terms_url,
            "blocked_host",
            "allow-listed host",
            entry.terms_url,
        )
    try:
        prepared = prepare(entry, transport, sleep)
    except OSError:
        return None, FetchFailure(
            1, entry.source_id, entry.url, "write_failed", "stored file", "write failed"
        )
    if prepared.failure is not None:
        return None, FetchFailure(
            prepared.failure.code,
            entry.source_id,
            prepared.failure.url,
            prepared.failure.check,
            prepared.failure.expected,
            prepared.failure.observed,
        )
    digest = sha256_hex(prepared.body)
    retrieved = clock()
    sidecar = sidecar_for(
        entry,
        digest=digest,
        nbytes=len(prepared.body),
        fetch_url=prepared.fetch_url,
        fetch_host=prepared.fetch_host,
        retrieved_utc=retrieved,
        publisher=prepared.publisher,
        source_modified=prepared.source_modified,
        row_count=prepared.row_count,
        terms_sha256=prepared.terms_sha256,
        switched_off=False,
        portal_licence=prepared.portal_licence,
        portal_licence_url=prepared.portal_licence_url,
    )
    try:
        commit_pair(
            cache_directory(cache, entry.key),
            digest,
            entry.extension,
            prepared.body,
            sidecar,
        )
    except OSError:
        return None, FetchFailure(
            1,
            entry.source_id,
            prepared.fetch_url,
            "write_failed",
            "stored file",
            "write failed",
        )
    return (
        _Fetched(digest, prepared.fetch_host, retrieved, prepared.terms_sha256),
        None,
    )


def run_build(
    entries: tuple[Entry, ...] | list[Entry],
    transport: Transport,
    cache: Path,
    clock: Clock,
    sleep: Sleeper,
) -> BuildOutcome:
    """Fetch each row in order, then run the public_data stage."""
    lines: list[str] = []
    terms: list[dict[str, object]] = []
    previous = _previous_term_hashes(cache)
    failure: FetchFailure | None = None
    for entry in entries:
        if entry.terms_forbid:
            stopped = _switch_off_on_terms(entry, transport, sleep, clock, lines, terms)
            if stopped is not None:
                failure = stopped
                break
            continue
        if entry.terms_watch and entry.skip_reason:
            stopped = _watch_skipped_terms(
                entry, transport, sleep, clock, lines, terms, previous
            )
            if stopped is not None:
                failure = stopped
                break
            lines.append(skip_line(entry.key, entry.skip_reason))
            continue
        if entry.skip_reason:
            lines.append(skip_line(entry.key, entry.skip_reason))
            continue
        if entry.kind == "citation_only":
            _write_citation(entry, cache, clock())
            lines.append(citation_line(entry.key))
            continue
        fetched, result = _fetch_row(entry, transport, cache, clock, sleep)
        if result is not None:
            if result.check == "terms_forbid":
                lines.append(owner_line(entry.key, entry.terms_url))
                continue
            lines.append(
                fail_line(
                    entry.key,
                    result.url,
                    result.check,
                    result.expected,
                    result.observed,
                )
            )
            failure = result
            break
        assert fetched is not None
        if entry.terms_watch and fetched.terms_sha256:
            _record_watched_terms(
                entry,
                fetched.terms_sha256,
                fetched.retrieved_utc,
                previous,
                lines,
                terms,
            )
        lines.append(pass_line(entry.key, fetched.digest, fetched.fetch_host))
    if failure is None:
        stage = run_stage(cache)
        for figure_id in stage.missing:
            lines.append(coverage_line(figure_id))
        if stage.mismatch:
            failure = FetchFailure(
                1,
                stage.mismatch,
                "",
                "public_data",
                "section 10 anchor",
                stage.mismatch,
            )
            lines.append(
                fail_line(
                    stage.mismatch,
                    "",
                    "public_data",
                    "section 10 anchor",
                    stage.mismatch,
                )
            )
    _write_log(cache, lines, terms)
    return BuildOutcome(tuple(lines), failure)


def _switch_off_on_terms(
    entry: Entry,
    transport: Transport,
    sleep: Sleeper,
    clock: Clock,
    lines: list[str],
    terms: list[dict[str, object]],
) -> FetchFailure | None:
    """Read terms_url only. A recorded phrase, or its absence, switches the source off."""
    read = read_recorded_terms(entry, transport, sleep)
    if read.failure is not None:
        lines.append(
            fail_line(
                entry.key,
                read.failure.url,
                read.failure.check,
                read.failure.expected,
                read.failure.observed,
            )
        )
        return FetchFailure(
            read.failure.code,
            entry.source_id,
            read.failure.url,
            read.failure.check,
            read.failure.expected,
            read.failure.observed,
        )
    if read.phrase_present:
        lines.append(owner_line(entry.key, entry.terms_url))
        reason = REASON_FORBID
    else:
        lines.append(owner_changed_line(entry.key, entry.terms_url))
        reason = REASON_CHANGED
    terms.append(
        {
            "key": entry.key,
            "terms_url": entry.terms_url,
            "terms_sha256": read.sha256,
            "terms_fingerprint": FINGERPRINT_VISIBLE_TEXT,
            "retrieved_utc": clock(),
            "reason": reason,
            "switched_off": True,
        }
    )
    return None


def _watch_skipped_terms(
    entry: Entry,
    transport: Transport,
    sleep: Sleeper,
    clock: Clock,
    lines: list[str],
    terms: list[dict[str, object]],
    previous: dict[str, str],
) -> FetchFailure | None:
    """Read and hash the terms page of a watched row that this task does not fetch."""
    read = read_recorded_terms(entry, transport, sleep)
    if read.failure is not None:
        lines.append(
            fail_line(
                entry.key,
                read.failure.url,
                read.failure.check,
                read.failure.expected,
                read.failure.observed,
            )
        )
        return FetchFailure(
            read.failure.code,
            entry.source_id,
            read.failure.url,
            read.failure.check,
            read.failure.expected,
            read.failure.observed,
        )
    _record_watched_terms(entry, read.sha256, clock(), previous, lines, terms)
    return None


def _record_watched_terms(
    entry: Entry,
    digest: str,
    retrieved: str,
    previous: dict[str, str],
    lines: list[str],
    terms: list[dict[str, object]],
) -> None:
    """Record the visible-text fingerprint. A changed fingerprint of this kind is named."""
    terms.append(
        {
            "key": entry.key,
            "retrieved_utc": retrieved,
            "terms_sha256": digest,
            "terms_fingerprint": FINGERPRINT_VISIBLE_TEXT,
            "terms_url": entry.terms_url,
        }
    )
    prior = previous.get(entry.key)
    if prior is not None and prior != digest:
        lines.append(terms_changed_line(entry.key, entry.terms_url))


def _previous_term_hashes(cache: Path) -> dict[str, str]:
    """Return visible-text fingerprints from the previous build log.

    A row with no ``terms_fingerprint`` of ``visible_text`` was hashed from
    raw page bytes and is not compared.
    """
    path = cache / LOG_NAME
    if not path.is_file():
        return {}
    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    rows = loaded.get("terms")
    if not isinstance(rows, list):
        return {}
    found: dict[str, str] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        digest = item.get("terms_sha256")
        kind = item.get("terms_fingerprint")
        if (
            isinstance(key, str)
            and isinstance(digest, str)
            and digest
            and kind == FINGERPRINT_VISIBLE_TEXT
        ):
            found[key] = digest
    return found


def _write_citation(entry: Entry, cache: Path, retrieved: str) -> None:
    sidecar = sidecar_for(
        entry,
        digest="CITATION_ONLY",
        nbytes=0,
        fetch_url=entry.url,
        fetch_host="",
        retrieved_utc=retrieved,
        publisher=entry.publisher,
        source_modified="",
        row_count=None,
        terms_sha256="",
        switched_off=False,
    )
    commit_citation(cache_directory(cache, entry.key), sidecar)


def _write_log(cache: Path, lines: list[str], terms: list[dict[str, object]]) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"lines": lines, "terms": terms}, sort_keys=True) + "\n"
    partial = cache / ".build-log.json.partial"
    final = cache / LOG_NAME
    try:
        partial.write_text(payload, encoding="utf-8")
        os.replace(partial, final)
    except OSError:
        partial.unlink(missing_ok=True)
        raise
