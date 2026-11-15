"""Orchestrate one public build: registry order, receipts, then the stage."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from eii_custodian.publicdata.additions.common import (
    ADDITION_FAMILIES as _ADDITION_FAMILIES,
)
from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.fetch.allowlist import approve, host_of
from eii_custodian.publicdata.fetch.kinds import (
    TERMS_HOST_UNLISTED,
    prepare,
    read_terms_page,
)
from eii_custodian.publicdata.fetch.receipts import (
    cache_directory,
    commit_citation,
    commit_pair,
    sha256_hex,
    sidecar_for,
)
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.report import (
    citation_line,
    coverage_line,
    fail_line,
    pass_line,
    skip_line,
    terms_changed_line,
    terms_host_line,
    terms_unread_line,
)
from eii_custodian.publicdata.fetch.terms_text import FINGERPRINT_VISIBLE_TEXT
from eii_custodian.publicdata.fetch.transport import Transport, public_address
from eii_custodian.publicdata.grids.fetch import GRID_SOURCES, prepare_grid
from eii_custodian.publicdata.investment_build import publish_investment
from eii_custodian.publicdata.places.fetch import fetch_place_file, is_place_file
from eii_custodian.publicdata.places_fsq.fetch import fetch_release, is_release_entry
from eii_custodian.publicdata.stage import run_stage

CACHE_RELATIVE = "data/public_cache"
LOG_NAME = "build-log.json"
Sleeper = Callable[[float], None]
Clock = Callable[[], str]
TOKEN_SOURCE = "ntl_blackmarble"


@dataclass(frozen=True)
class FetchFailure:
    """One failed check. code 6 is an unavailable network; code 1 is any other check."""

    code: int
    source_id: str
    url: str
    check: str
    expected: str
    observed: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "url", public_address(self.url))

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
    terms_unread: str


def _digest_pages(directory: Path) -> str:
    """Hash the stored page files. An empty body is not one of them."""
    chunks = [path.read_bytes() for path in sorted(directory.rglob("*.html"))]
    return sha256_hex(b"".join(chunks))


def utc_now() -> str:
    """Return the current UTC time as the retrieval timestamp."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_entry(
    entry: Entry,
    transport: Transport,
    cache: Path,
    clock: Clock,
    sleep: Sleeper,
    token: str = "",
) -> FetchFailure | None:
    """Fetch one row. An unlisted host is refused before the transport is called."""
    _fetched, failure = _fetch_row(entry, transport, cache, clock, sleep, token)
    return failure


def _fetch_row(
    entry: Entry,
    transport: Transport,
    cache: Path,
    clock: Clock,
    sleep: Sleeper,
    token: str = "",
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
    try:
        prepared = (
            prepare_grid(entry, transport, sleep, token)
            if entry.source_id in GRID_SOURCES
            else prepare(entry, transport, sleep, cache=cache)
        )
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
    if entry.kind == "paged_cards" and prepared.body == b"":
        return (
            _Fetched(
                _digest_pages(cache_directory(cache, entry.key)),
                prepared.fetch_host,
                clock(),
                prepared.terms_sha256,
                prepared.terms_unread,
            ),
            None,
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
        portal_licence=prepared.portal_licence,
        portal_licence_url=prepared.portal_licence_url,
        observed_periods=(
            (prepared.period_first, prepared.period_last)
            if prepared.periods_observed
            else None
        ),
        coverage_note=prepared.coverage_note,
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
        _Fetched(
            digest,
            prepared.fetch_host,
            retrieved,
            prepared.terms_sha256,
            prepared.terms_unread,
        ),
        None,
    )


def run_build(
    entries: tuple[Entry, ...] | list[Entry],
    transport: Transport,
    cache: Path,
    clock: Clock,
    sleep: Sleeper,
    token: str = "",
    key_name: str = "",
    *,
    additions_review: Path | None = None,
    additions_frame: Path | None = None,
    additions_output: Path | None = None,
) -> BuildOutcome:
    """Fetch each row in order, then run the public_data stage."""
    lines: list[str] = []
    terms: list[dict[str, object]] = []
    previous = _previous_term_hashes(cache)
    failure: FetchFailure | None = None
    selected: list[tuple[str, str]] = []
    fetched_entries: list[Entry] = []
    told_absent = False
    for entry in entries:
        if not token and _token_file(entry):
            if not told_absent:
                lines.append(
                    f"OMIT {TOKEN_SOURCE}: {key_name} absent; "
                    "night-lights layer left out"
                )
                told_absent = True
            continue
        if entry.skip_reason:
            if entry.terms_url:
                _read_terms_apart(
                    entry, transport, sleep, clock, lines, terms, previous
                )
            lines.append(skip_line(entry.key, entry.skip_reason))
            continue
        if entry.kind == "citation_only":
            _write_citation(entry, cache, clock())
            lines.append(citation_line(entry.key))
            continue
        if is_release_entry(entry):
            released, refused = fetch_release(entry, transport, cache, clock, sleep)
            if refused is not None:
                lines.append(
                    fail_line(
                        entry.key,
                        refused.url,
                        refused.check,
                        refused.expected,
                        refused.observed,
                    )
                )
                failure = FetchFailure(
                    refused.code,
                    entry.source_id,
                    refused.url,
                    refused.check,
                    refused.expected,
                    refused.observed,
                )
                break
            assert released is not None
            lines.append(pass_line(entry.key, released.digest, released.host))
            continue
        if is_place_file(entry):
            placed, place_failure = fetch_place_file(
                entry, transport, cache, clock, sleep
            )
            if place_failure is not None:
                lines.append(
                    fail_line(
                        entry.key,
                        place_failure.url,
                        place_failure.check,
                        place_failure.expected,
                        place_failure.observed,
                    )
                )
                failure = FetchFailure(
                    place_failure.code,
                    entry.source_id,
                    place_failure.url,
                    place_failure.check,
                    place_failure.expected,
                    place_failure.observed,
                )
                break
            assert placed is not None
            lines.append(pass_line(entry.key, placed.digest, placed.host))
            continue
        fetched, result = _fetch_row(entry, transport, cache, clock, sleep, token)
        if result is not None:
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
        if entry.kind == "terms_page":
            _note_fetched_terms(entry, fetched, lines, terms, previous)
        elif entry.terms_url:
            _read_terms_apart(entry, transport, sleep, clock, lines, terms, previous)
        if entry.source_id in _ADDITION_FAMILIES:
            selected.append((entry.key, fetched.digest))
            fetched_entries.append(entry)
        batch = publish_investment(
            entry, cache, fetched.digest, transport, sleep, clock
        )
        if batch is not None:
            lines.append(
                fail_line(
                    entry.key,
                    batch.url,
                    batch.check,
                    batch.expected,
                    batch.observed,
                )
            )
            failure = FetchFailure(
                batch.code,
                entry.source_id,
                batch.url,
                batch.check,
                batch.expected,
                batch.observed,
            )
            break
        lines.append(pass_line(entry.key, fetched.digest, fetched.fetch_host))
        counted = cache / entry.source_id / "empty_coordinates.txt"
        if counted.is_file():
            lines.append(counted.read_text(encoding="utf-8").strip())
    if failure is None and selected:
        failure = _publish_additions(
            tuple(fetched_entries),
            tuple(selected),
            cache,
            additions_review,
            additions_frame,
            additions_output,
            lines,
        )
    if failure is None:
        from eii_custodian.publicdata.places.integrate import (
            areas_before_stage,
            frame_when_ready,
        )

        areas_before_stage(cache, lines)
        frame_when_ready(cache, entries, lines)
        failure = run_stage(cache, build_entries=entries, build_lines=lines).failure
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
        elif stage.unrecorded:
            failure = FetchFailure(
                1,
                stage.unrecorded,
                "",
                "public_data",
                "local expectations record",
                "missing",
            )
            lines.append(
                fail_line(
                    stage.unrecorded,
                    "",
                    "public_data",
                    "local expectations record",
                    "missing",
                )
            )
        if failure is None:
            failure = _heights(cache, entries, lines)
    _write_log(cache, lines, terms)
    return BuildOutcome(tuple(lines), failure)


def _publish_additions(
    entries: tuple[Entry, ...],
    selected: tuple[tuple[str, str], ...],
    cache: Path,
    review: Path | None,
    frame: Path | None,
    output: Path | None,
    lines: list[str],
) -> FetchFailure | None:
    """Publish addition tables after the fetches. A parser failure leaves no tables."""
    from eii_custodian.publicdata.additions.build import build_additions

    review_dir = review if review is not None else _review_dir()
    frame_dir = frame if frame is not None else review_dir
    destination = output if output is not None else cache / "additions"
    try:
        build_additions(cache, entries, selected, review_dir, frame_dir, destination)
    except AdditionError as error:
        lines.append(
            fail_line("additions", "", error.name, "published tables", error.name)
        )
        return FetchFailure(
            1, "additions", "", error.name, "published tables", error.name
        )
    return None


def _review_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "publicdata" / "review"


def _token_file(entry: Entry) -> bool:
    """True for a per-month radiance file entry that needs the archive token."""
    return (
        entry.source_id == TOKEN_SOURCE and "/" in entry.key and not entry.skip_reason
    )


def _heights(
    cache: Path,
    entries: tuple[Entry, ...] | list[Entry],
    lines: list[str],
) -> FetchFailure | None:
    """Run the heights step after the stage; a missing table only skips (B10)."""
    from eii_custodian.publicdata.heights.step import (
        BUILDINGS_RELATIVE,
        HEIGHTS_RELATIVE,
        HeightError,
        build_heights,
    )

    root = cache.parent
    try:
        build_heights(
            cache,
            entries,
            root / BUILDINGS_RELATIVE,
            root / HEIGHTS_RELATIVE,
            lines,
        )
    except HeightError as error:
        lines.append(
            fail_line(
                "heights",
                "",
                error.name,
                "valid height inputs",
                error.name,
            )
        )
        return FetchFailure(
            1, "heights", "", error.name, "valid height inputs", error.name
        )
    return None


def _note_fetched_terms(
    entry: Entry,
    fetched: _Fetched,
    lines: list[str],
    terms: list[dict[str, object]],
    previous: dict[str, str],
) -> None:
    """Record the fingerprint a terms_page row already read inside its fetch."""
    if not entry.terms_url:
        return
    if fetched.terms_unread == TERMS_HOST_UNLISTED:
        lines.append(
            terms_host_line(entry.key, host_of(entry.terms_url), entry.terms_url)
        )
        return
    if fetched.terms_unread:
        lines.append(
            terms_unread_line(entry.key, fetched.terms_unread, entry.terms_url)
        )
        return
    if fetched.terms_sha256:
        _record_terms(
            entry,
            fetched.terms_sha256,
            fetched.retrieved_utc,
            previous,
            lines,
            terms,
        )


def _read_terms_apart(
    entry: Entry,
    transport: Transport,
    sleep: Sleeper,
    clock: Clock,
    lines: list[str],
    terms: list[dict[str, object]],
    previous: dict[str, str],
) -> None:
    """Read a terms page that the row's own fetch does not read."""
    if not approve(entry.terms_url).ok:
        lines.append(
            terms_host_line(entry.key, host_of(entry.terms_url), entry.terms_url)
        )
        return
    read = read_terms_page(entry, transport, sleep)
    if read.failure is not None:
        lines.append(terms_unread_line(entry.key, read.failure.check, entry.terms_url))
        return
    _record_terms(entry, read.sha256, clock(), previous, lines, terms)


def _record_terms(
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
            "terms_words": entry.terms_words,
            "terms_read_on": entry.terms_read_on,
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
