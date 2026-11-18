"""Orchestrate one public build: registry order, receipts, then the stage."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict, cast

from eii_custodian.publicdata.additions.common import (
    ADDITION_FAMILIES as _ADDITION_FAMILIES,
)
from eii_custodian.publicdata.additions.common import AdditionError
from eii_custodian.publicdata.atlas.config import AtlasError
from eii_custodian.publicdata.atlas.config import Config as AtlasConfig
from eii_custodian.publicdata.atlas.config import load_config as load_atlas_config
from eii_custodian.publicdata.atlas.fetch import fetch_atlas
from eii_custodian.publicdata.baci.config import BaciError, Config, load_config
from eii_custodian.publicdata.baci.fetch import fetch_baci
from eii_custodian.publicdata.benchmarks.config import Policy as BenchmarkPolicy
from eii_custodian.publicdata.benchmarks.config import load_policies
from eii_custodian.publicdata.benchmarks.contracts import TABLES as BENCHMARK_TABLES
from eii_custodian.publicdata.benchmarks.fetch import fetch_benchmark, owner_obstacle
from eii_custodian.publicdata.fetch.allowlist import approve, host_of
from eii_custodian.publicdata.fetch.kinds import (
    TERMS_HOST_UNLISTED,
    prepare,
    read_terms_page,
)
from eii_custodian.publicdata.fetch.partitions import (
    PartitionError,
    bounded_partition_reader,
    load_partition_spans,
)
from eii_custodian.publicdata.fetch.receipts import (
    archive_auxiliary,
    cache_directory,
    commit_citation,
    commit_pair,
    sha256_hex,
    sidecar_for,
)
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.fetch.report import (
    TERMS_HOST_NOT_LISTED,
    citation_line,
    coverage_line,
    evidence_line,
    fail_line,
    pass_line,
    skip_line,
    terms_attempt_record,
    terms_changed_line,
    terms_host_line,
    terms_unread_line,
)
from eii_custodian.publicdata.fetch.terms_text import FINGERPRINT_VISIBLE_TEXT
from eii_custodian.publicdata.fetch.transport import (
    Opener,
    SlotReader,
    StreamTransport,
    Transport,
    TransportFault,
    public_address,
)
from eii_custodian.publicdata.gravity.config import Config as GravityConfig
from eii_custodian.publicdata.gravity.config import GravityError
from eii_custodian.publicdata.gravity.config import load_config as load_gravity_config
from eii_custodian.publicdata.gravity.fetch import fetch_gravity
from eii_custodian.publicdata.grids.fetch import GRID_SOURCES, prepare_grid
from eii_custodian.publicdata.investment_build import (
    INVESTMENT_SOURCES,
    publish_investment,
)
from eii_custodian.publicdata.investment_contracts import (
    EvidenceAuditEntry,
    EvidenceProjection,
    ExpectedInput,
    FetchAttempt,
    InvestmentFailure,
    MilestoneArchiveSelection,
    ProjectArchiveSelection,
)
from eii_custodian.publicdata.investment_evidence import (
    archive_fetch_attempts,
    build_cache_evidence,
)
from eii_custodian.publicdata.places.fetch import fetch_place_file, is_place_file
from eii_custodian.publicdata.places_fsq.fetch import fetch_release, is_release_entry
from eii_custodian.publicdata.stage import run_stage
from eii_custodian.publicdata.trade_reconciliation import (
    Selection,
    build_reconciliation,
    load_selection,
)

CACHE_RELATIVE = "data/public_cache"
LOG_NAME = "build-log.json"
Sleeper = Callable[[float], None]
Clock = Callable[[], str]
TOKEN_SOURCE = "ntl_blackmarble"


class _StreamOptions(TypedDict, total=False):
    large_stream: StreamTransport


def _stream_options(stream: StreamTransport | None) -> _StreamOptions:
    """Keep the existing callback signature when no stream was configured."""
    return {} if stream is None else {"large_stream": stream}


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
    manifests: dict[str, str] = field(default_factory=dict)
    investment_attempts: tuple[FetchAttempt, ...] = ()
    terms: tuple[dict[str, object], ...] = ()
    terms_attempts: tuple[dict[str, object], ...] = ()


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


def _comtrade_dispatch(
    entry: Entry,
    cache: Path,
    clock: Clock,
    sleep: Sleeper,
    opener: Opener | None,
    slots: SlotReader | None,
    lines: list[str],
) -> FetchFailure | None:
    """Dispatch one Comtrade row. A missing opener never opens a socket."""
    from eii_custodian.publicdata.comtrade.fetch import fetch_source

    if opener is None:
        failure = FetchFailure(
            1,
            entry.source_id,
            "https://invalid.example/refused",
            "transport_uninjected",
            "injected opener",
            "absent",
        )
        lines.append(
            fail_line(
                entry.key,
                failure.url,
                failure.check,
                failure.expected,
                failure.observed,
            )
        )
        return failure
    traded = fetch_source(entry, cache, clock, sleep, opener, slots)
    if traded.failure is not None:
        lines.append(
            fail_line(
                entry.key,
                traded.failure.safe_url,
                traded.failure.check,
                traded.failure.check,
                traded.failure.endpoint_id,
            )
        )
        return FetchFailure(
            1,
            entry.source_id,
            traded.failure.safe_url,
            traded.failure.check,
            traded.failure.check,
            traded.failure.endpoint_id,
        )
    lines.append(pass_line(entry.key, traded.digest, traded.host))
    return None


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
    *,
    large_stream: StreamTransport | None = None,
) -> FetchFailure | None:
    """Fetch one row. An unlisted host is refused before the transport is called."""
    _fetched, failure = _fetch_row(
        entry, transport, cache, clock, sleep, token, **_stream_options(large_stream)
    )
    return failure


def _fetch_row(
    entry: Entry,
    transport: Transport,
    cache: Path,
    clock: Clock,
    sleep: Sleeper,
    token: str = "",
    registry_entries: tuple[Entry, ...] | None = None,
    large_stream: StreamTransport | None = None,
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
    from .large import REQUIRED_KEYS, IntakeError, fetch_large

    if large_stream is not None and entry.key in REQUIRED_KEYS:
        try:
            found = fetch_large(entry, transport, large_stream, cache, clock, sleep)
        except IntakeError as exc:
            return None, FetchFailure(
                1,
                entry.source_id,
                entry.url,
                str(exc),
                "complete streamed input",
                "NO_DATA",
            )
        except TransportFault as exc:
            return None, FetchFailure(
                6 if exc.kind == "unreachable" else 1,
                entry.source_id,
                entry.url,
                exc.kind,
                "complete streamed input",
                "NO_DATA",
            )
        except (OSError, ValueError):
            return None, FetchFailure(
                1, entry.source_id, entry.url, "write_failed", "stored file", "NO_DATA"
            )
        return _Fetched(
            found.digest, found.fetch_host, found.retrieved_utc, "", ""
        ), None
    try:
        prepared = (
            prepare_grid(entry, transport, sleep, token)
            if entry.source_id in GRID_SOURCES
            else prepare(
                entry, transport, sleep, cache=cache, registry_entries=registry_entries
            )
        )
    except PartitionError as exc:
        return None, FetchFailure(
            1, entry.source_id, entry.url, str(exc), "reviewed byte span", "refused"
        )
    except (OSError, ValueError):
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
    # What is stored of a final address is scheme, host and path only (rule
    # 14): a storage host's signed redirect query never reaches a receipt,
    # whichever fetcher built the row. Hops are never stored at all.
    stored_url = (
        public_address(prepared.fetch_url)
        if entry.kind == "https_file"
        else prepared.fetch_url
    )
    stored_entry = entry
    if entry.key in {"places_ovt", "bldg_ovt"}:
        # Listing evidence must not replace the parent's cached Parquet rows.
        stored_entry = replace(entry, key=entry.key + "/listing", extension="json")
    sidecar = sidecar_for(
        stored_entry,
        digest=digest,
        nbytes=len(prepared.body),
        fetch_url=stored_url,
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
    if prepared.requests:
        sidecar["requests"] = list(prepared.requests)
    if entry.source_id in INVESTMENT_SOURCES:
        sidecar["terms_url"] = entry.terms_url
    try:
        commit_pair(
            cache_directory(cache, stored_entry.key),
            digest,
            stored_entry.extension,
            prepared.body,
            sidecar,
        )
        for response in prepared.auxiliary:
            archive_auxiliary(
                entry,
                cache / entry.key,
                "inputs",
                response.body,
                retrieved,
                response.final_url,
            )
    except (OSError, ValueError):
        return None, FetchFailure(
            1,
            entry.source_id,
            stored_url,
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
    stream_transport: StreamTransport | None = None,
    baci_config: Config | None = None,
    gravity_config: GravityConfig | None = None,
    atlas_config: AtlasConfig | None = None,
    gravity_stream: StreamTransport | None = None,
    atlas_stream: StreamTransport | None = None,
    opener: Opener | None = None,
    slots: SlotReader | None = None,
    *,
    token: str = "",
    key_name: str = "",
    additions_review: Path | None = None,
    additions_frame: Path | None = None,
    additions_output: Path | None = None,
    benchmark_policies: dict[str, BenchmarkPolicy] | None = None,
    benchmark_stream: StreamTransport | None = None,
    reconciliation_selection: Selection | None = None,
    environ: Mapping[str, str] | None = None,
    large_stream: StreamTransport | None = None,
    seed: int | None = None,
    _fetch_only: bool = False,
) -> BuildOutcome:
    """Run the production assembly when a seed is supplied; retain the fetch seam."""
    if seed is not None:
        from eii_custodian.publicdata.assembly import AssemblyError
        from eii_custodian.publicdata.assembly_adapters import Production

        if type(seed) is not int or seed < 0:
            raise AssemblyError("figure_seed_invalid")

        def fetch_only() -> BuildOutcome:
            return run_build(
                entries,
                transport,
                cache,
                clock,
                sleep,
                stream_transport=stream_transport,
                baci_config=baci_config,
                gravity_config=gravity_config,
                atlas_config=atlas_config,
                gravity_stream=gravity_stream,
                atlas_stream=atlas_stream,
                opener=opener,
                slots=slots,
                token=token,
                key_name=key_name,
                benchmark_policies=benchmark_policies,
                benchmark_stream=benchmark_stream,
                environ=environ,
                large_stream=large_stream,
                _fetch_only=True,
            )

        build = Production(
            tuple(entries),
            cache,
            _review_dir(),
            cache.parent.parent,
            transport,
            clock,
            sleep,
            seed,
            environ or {},
            fetcher=fetch_only,
            reconciliation_selection=reconciliation_selection,
        )
        try:
            build.run()
        except Exception as exc:
            # No exception text crosses the source/credential boundary. Preserve
            # an existing structured fetch failure and its network exit code.
            if build.fetched is not None and build.fetched.failure is not None:
                return cast(BuildOutcome, build.fetched)
            from eii_custodian.publicdata.series.frame import MunicipalityFrameRefused
            from eii_custodian.publicdata.series.parse import (
                SERIES_REFUSALS,
                SeriesRefused,
            )

            reason = "assembly_build_refused"
            if isinstance(exc, SeriesRefused) and exc.word in SERIES_REFUSALS:
                reason = exc.word
            elif (
                isinstance(exc, MunicipalityFrameRefused)
                and exc.reason in SERIES_REFUSALS
            ):
                reason = exc.reason
            if isinstance(exc, AssemblyError) and str(exc) in {
                "snapshot_selection_invalid",
                "assembly_gate_pending",
                "assembly_frame_incomplete",
                "assembly_places_incomplete",
                "assembly_membership_invalid",
                "assembly_regression_refused",
                "assembly_intake_invalid",
                "assembly_tender_pages_incomplete",
            }:
                reason = str(exc)
            assembly_failure = FetchFailure(
                1,
                "assembly",
                "",
                reason,
                "verified ordered outputs",
                "NO_DATA",
            )
            build.lines.append(
                fail_line(
                    "assembly",
                    "",
                    assembly_failure.check,
                    assembly_failure.expected,
                    assembly_failure.observed,
                )
            )
            _write_log(
                cache,
                build.lines,
                list(build.fetched.terms) if build.fetched else [],
                list(build.fetched.terms_attempts) if build.fetched else [],
            )
            return BuildOutcome(tuple(build.lines), assembly_failure)
        _write_log(
            cache,
            build.lines,
            list(build.fetched.terms) if build.fetched else [],
            list(build.fetched.terms_attempts) if build.fetched else [],
        )
        return BuildOutcome(tuple(build.lines), None)
    # One injected UTC clock sample governs every verification in this build.
    started = clock()
    if (
        re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", started)
        is None
    ):
        raise ValueError("invalid build-start UTC timestamp")
    try:
        build_date = datetime.strptime(started, "%Y-%m-%dT%H:%M:%SZ").date()
    except ValueError:
        raise ValueError("invalid build-start UTC timestamp") from None
    manifests: dict[str, str] = {}
    lines: list[str] = []
    pending: list[Entry] = []
    terms: list[dict[str, object]] = []
    terms_attempts: list[dict[str, object]] = []
    benchmark_obstacles: list[dict[str, object]] = []
    previous = _previous_term_hashes(cache)
    failure: FetchFailure | None = None
    selected: list[tuple[str, str]] = []
    fetched_entries: list[Entry] = []
    investment_attempts: list[FetchAttempt] = []
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
        if entry.source_id in BENCHMARK_TABLES:
            try:
                policies = (
                    benchmark_policies
                    if benchmark_policies is not None
                    else load_policies()
                )
                policy = policies[entry.source_id]
                if not policy.confirmed:
                    lines.append(
                        skip_line(entry.source_id, "benchmark_metadata_unconfirmed")
                    )
                    continue
                obstacle = owner_obstacle(policy)
                if obstacle is not None:
                    benchmark_obstacles.append(obstacle)
                benchmark_result = fetch_benchmark(
                    entry, policy, transport, benchmark_stream, cache, clock, sleep
                )
                manifests[entry.source_id] = benchmark_result.digest
                lines.append(
                    pass_line(entry.key, benchmark_result.digest, benchmark_result.host)
                )
            except (ValueError, KeyError, OSError, TypeError):
                lines.append(
                    fail_line(
                        entry.source_id,
                        "",
                        "benchmark_validation_failed",
                        "verified benchmark",
                        "NO_DATA",
                    )
                )
                failure = FetchFailure(
                    1,
                    entry.source_id,
                    "",
                    "benchmark_validation_failed",
                    "verified benchmark",
                    "NO_DATA",
                )
            continue
        if entry.source_id == "cepii_baci":
            try:
                config = baci_config if baci_config is not None else load_config()
                baci_result = fetch_baci(
                    entry, config, transport, stream_transport, cache, clock, sleep
                )
                manifests[entry.source_id] = baci_result.digest
                lines.append(pass_line(entry.key, baci_result.digest, baci_result.host))
                if baci_result.terms_sha256:
                    _record_terms(
                        entry,
                        baci_result.terms_sha256,
                        baci_result.retrieved_utc,
                        previous,
                        lines,
                        terms,
                    )
                else:
                    lines.append(
                        terms_unread_line(entry.key, baci_result.terms_unread, "")
                    )
            except BaciError as exc:
                reason = str(exc)
                if reason == "baci_metadata_unconfirmed":
                    lines.append(skip_line("cepii_baci", reason))
                    lines.append(
                        terms_unread_line("cepii_baci", "terms_to_be_read", "")
                    )
                    continue
                failure = FetchFailure(
                    6 if reason == "network_exhausted" else 1,
                    "cepii_baci",
                    "",
                    reason,
                    "validated source",
                    "NO_DATA",
                )
                lines.append(
                    fail_line("cepii_baci", "", reason, "validated source", "NO_DATA")
                )
                break
            continue
        if entry.source_id == "cepii_gravity":
            try:
                gravity_loaded = (
                    gravity_config
                    if gravity_config is not None
                    else load_gravity_config()
                )
                gravity_result = fetch_gravity(
                    entry,
                    gravity_loaded,
                    transport,
                    gravity_stream,
                    cache,
                    clock,
                    sleep,
                )
                manifests[entry.source_id] = gravity_result.digest
                lines.append(
                    pass_line(entry.key, gravity_result.digest, gravity_result.host)
                )
                if gravity_result.terms_sha256:
                    _record_terms(
                        entry,
                        gravity_result.terms_sha256,
                        gravity_result.retrieved_utc,
                        previous,
                        lines,
                        terms,
                    )
                else:
                    lines.append(
                        terms_unread_line(entry.key, gravity_result.terms_unread, "")
                    )
            except GravityError as exc:
                reason = str(exc)
                if reason == "gravity_metadata_unconfirmed":
                    lines.append(skip_line("cepii_gravity", reason))
                    lines.append(
                        terms_unread_line("cepii_gravity", "terms_to_be_read", "")
                    )
                    continue
                failure = FetchFailure(
                    6 if reason == "network_exhausted" else 1,
                    "cepii_gravity",
                    "",
                    reason,
                    "validated source",
                    "NO_DATA",
                )
                lines.append(
                    fail_line(
                        "cepii_gravity", "", reason, "validated source", "NO_DATA"
                    )
                )
                break
            continue
        if entry.source_id == "atlas_complexity":
            try:
                atlas_loaded = (
                    atlas_config if atlas_config is not None else load_atlas_config()
                )
                atlas_result = fetch_atlas(
                    entry, atlas_loaded, transport, atlas_stream, cache, clock, sleep
                )
                manifests[entry.source_id] = atlas_result.digest
                lines.append(
                    pass_line(entry.key, atlas_result.digest, atlas_result.host)
                )
                if atlas_result.terms_sha256:
                    _record_terms(
                        entry,
                        atlas_result.terms_sha256,
                        atlas_result.retrieved_utc,
                        previous,
                        lines,
                        terms,
                    )
                else:
                    lines.append(
                        terms_unread_line(entry.key, atlas_result.terms_unread, "")
                    )
            except AtlasError as exc:
                reason = str(exc)
                if reason == "atlas_metadata_unconfirmed":
                    lines.append(skip_line("atlas_complexity", reason))
                    lines.append(
                        terms_unread_line("atlas_complexity", "terms_to_be_read", "")
                    )
                    continue
                failure = FetchFailure(
                    6 if reason == "network_exhausted" else 1,
                    "atlas_complexity",
                    "",
                    reason,
                    "validated source",
                    "NO_DATA",
                )
                lines.append(
                    fail_line(
                        "atlas_complexity", "", reason, "validated source", "NO_DATA"
                    )
                )
                break
            continue
        if entry.kind == "besttime":
            pending.append(entry)
            continue
        if entry.skip_reason:
            if entry.source_id == "suppliers_tawteen":
                from .page_records import load_declaration, record_failure

                refusal = load_declaration(entry.source_id)
                if refusal.get("kind") != "refusal":
                    raise ValueError("schema_missing")
                record_failure(
                    cache,
                    entry,
                    refusal["shape"]["observed_utc"],
                    refusal["shape"]["reason"],
                )
            if entry.terms_url and entry.kind not in {"public_page", "awards_intake"}:
                _read_terms_apart(
                    entry,
                    transport,
                    sleep,
                    clock,
                    lines,
                    terms,
                    previous,
                    cache,
                    terms_attempts,
                )
            lines.append(skip_line(entry.key, entry.skip_reason))
            continue
        if entry.kind in {"public_page", "awards_intake"}:
            from .award_checks import AwardError
            from .awards import fetch_awards
            from .certificate_pins import PinError
            from .page_records import PageError, fetch_page
            from .snapshots import SnapshotError

            try:
                page = (
                    fetch_awards(entry, transport, cache, clock, sleep)
                    if entry.kind == "awards_intake"
                    else fetch_page(entry, transport, cache, clock, sleep)
                )
                manifests[entry.key] = page.sha256
                lines.append(pass_line(entry.key, page.sha256, entry.fetch_host))
            except (PageError, AwardError, PinError, SnapshotError) as exc:
                reason = str(exc)
                failure = FetchFailure(
                    1, entry.source_id, "", reason, "verified snapshot", "NO_DATA"
                )
                lines.append(
                    fail_line(entry.key, "", reason, "verified snapshot", "NO_DATA")
                )
                break
            except (OSError, ValueError, KeyError, TypeError):
                failure = FetchFailure(
                    1,
                    entry.source_id,
                    "",
                    "page_validation_failed",
                    "verified snapshot",
                    "NO_DATA",
                )
                lines.append(
                    fail_line(
                        entry.key, "", failure.check, "verified snapshot", "NO_DATA"
                    )
                )
                break
            continue
        if entry.kind == "citation_only":
            _write_citation(entry, cache, clock())
            lines.append(citation_line(entry.key))
            continue
        if entry.kind == "comtrade_api":
            traded_failure = _comtrade_dispatch(
                entry, cache, clock, sleep, opener, slots, lines
            )
            if traded_failure is not None:
                failure = traded_failure
                break
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
                entry, transport, cache, clock, sleep, **_stream_options(large_stream)
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
        row_transport = transport
        if entry.key == "accident":
            try:
                row_transport = bounded_partition_reader(
                    transport, load_partition_spans(), sleep
                )
            except PartitionError as exc:
                failure = FetchFailure(
                    1,
                    entry.source_id,
                    entry.url,
                    str(exc),
                    "reviewed byte span",
                    "NO_DATA",
                )
                lines.append(
                    fail_line(entry.key, "", str(exc), "reviewed byte span", "NO_DATA")
                )
                break
        fetched, result = _fetch_row(
            entry,
            row_transport,
            cache,
            clock,
            sleep,
            token,
            registry_entries=tuple(entries),
            **_stream_options(large_stream),
        )
        if result is not None:
            if entry.source_id in INVESTMENT_SOURCES:
                investment_attempts.append(
                    FetchAttempt(
                        entry.source_id, entry.key, "failed", None, "fetch_failed"
                    )
                )
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
            _note_fetched_terms(entry, fetched, lines, terms, previous, terms_attempts)
        elif entry.terms_url:
            _read_terms_apart(
                entry,
                transport,
                sleep,
                clock,
                lines,
                terms,
                previous,
                cache,
                terms_attempts,
            )
        if entry.source_id in _ADDITION_FAMILIES:
            selected.append((entry.key, fetched.digest))
            fetched_entries.append(entry)
        batch = publish_investment(
            entry, cache, fetched.digest, transport, sleep, clock
        )
        if batch is not None:
            investment_attempts.append(
                FetchAttempt(
                    entry.source_id,
                    entry.key,
                    "failed",
                    fetched.digest,
                    "publication_failed",
                )
            )
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
        if entry.source_id in INVESTMENT_SOURCES:
            investment_attempts.append(
                FetchAttempt(entry.source_id, entry.key, "success", fetched.digest, "")
            )
        lines.append(pass_line(entry.key, fetched.digest, fetched.fetch_host))
        counted = cache / entry.source_id / "empty_coordinates.txt"
        if counted.is_file():
            lines.append(counted.read_text(encoding="utf-8").strip())
    if _fetch_only:
        from eii_custodian.publicdata.busyness.security import assert_clean

        if failure is not None:
            _archive_investment_attempts(
                entries, investment_attempts, cache, clock, lines
            )
        assert_clean(environ if environ is not None else {}, lines)
        _write_log(cache, lines, terms, terms_attempts)
        return BuildOutcome(
            tuple(lines),
            failure,
            manifests,
            tuple(investment_attempts),
            tuple(terms),
            tuple(terms_attempts),
        )
    attempt_failure = _archive_investment_attempts(
        entries, investment_attempts, cache, clock, lines
    )
    if failure is None and attempt_failure is not None:
        failure = attempt_failure
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
        frame_when_ready(cache, entries, lines, build_date=build_date)
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
            failure = _heights(cache, entries, lines, terms_attempts)

    if benchmark_obstacles:
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "benchmark_owner_report.json").write_text(
            json.dumps(benchmark_obstacles, sort_keys=True), encoding="utf-8"
        )
    if failure is None:
        from eii_custodian.publicdata.comtrade.policy import SafeRefusal
        from eii_custodian.publicdata.fetch.decimals import DecimalRefusal

        try:
            selected_comparison = reconciliation_selection or load_selection()
            if selected_comparison is not None:
                from eii_custodian.publicdata.comtrade.policy import (
                    Policy as TradePolicy,
                )

                native_policy = next(
                    (
                        e.comtrade_policy
                        for e in entries
                        if isinstance(e.comtrade_policy, TradePolicy)
                    ),
                    None,
                )
                manifests["trade_reconciliation"] = build_reconciliation(
                    cache, selected_comparison, comtrade_policy=native_policy
                )
        except (
            ValueError,
            KeyError,
            OSError,
            TypeError,
            SafeRefusal,
            BaciError,
            DecimalRefusal,
        ):
            failure = FetchFailure(
                1,
                "trade_reconciliation",
                "",
                "comparison_invalid",
                "verified inputs",
                "NO_DATA",
            )
            lines.append(
                fail_line(
                    "trade_reconciliation",
                    "",
                    "comparison_invalid",
                    "verified inputs",
                    "NO_DATA",
                )
            )
    if failure is None:
        from eii_custodian.publicdata.busyness.build import (
            BuildInputError,
            build_busyness,
        )
        from eii_custodian.publicdata.busyness.parse import FORECAST_URL, QUERY_URL
        from eii_custodian.publicdata.busyness.review import ReviewError
        from eii_custodian.publicdata.busyness.security import assert_clean

        for entry in pending:
            detail = ""
            trusted = False
            try:
                digest = build_busyness(
                    entry,
                    transport,
                    cache,
                    clock,
                    environ if environ is not None else {},
                )
            except (ValueError, OSError) as exc:
                detail = str(exc)
                trusted = isinstance(exc, (BuildInputError, ReviewError))
            if detail:
                # Only static schema/variable tokens cross into the build log.
                tokens = (
                    "BESTTIME_API_KEY_PRIVATE",
                    "BESTTIME_API_KEY_PUBLIC",
                    "EII_BESTTIME_RUN_CREDIT_LIMIT",
                    "forecast_credits",
                    "query_credits",
                    "source_page",
                    "read_on",
                    "terms_words",
                )
                check = next(
                    (token for token in tokens if token in detail),
                    "busyness_build_failed",
                )
                if trusted:
                    try:
                        assert_clean(environ if environ is not None else {}, detail)
                        check = detail
                    except ValueError:
                        check = "secret_in_input"
                endpoint = QUERY_URL if QUERY_URL in detail else FORECAST_URL
                failure = FetchFailure(
                    1,
                    "busy_besttime",
                    endpoint,
                    check,
                    "valid build inputs and answer",
                    "refused",
                )
                lines.append(
                    fail_line(
                        entry.key, endpoint, check, failure.expected, failure.observed
                    )
                )
                break
            lines.append(pass_line(entry.key, digest, "besttime.app"))
    from eii_custodian.publicdata.busyness.security import assert_clean

    assert_clean(environ if environ is not None else {}, lines)
    _write_log(cache, lines, terms, terms_attempts)
    return BuildOutcome(tuple(lines), failure, manifests)


def _archive_investment_attempts(
    entries: tuple[Entry, ...] | list[Entry],
    attempts: list[FetchAttempt],
    cache: Path,
    clock: Clock,
    lines: list[str],
    *,
    audit_history: bool = False,
    audit_entries: list[EvidenceAuditEntry] | None = None,
    milestones: tuple[MilestoneArchiveSelection, ...] = (),
) -> FetchFailure | None:
    """Retain investment attempts without changing fetch fail-fast behaviour."""
    expected = tuple(
        ExpectedInput(entry.source_id, entry.key, "project")
        for entry in entries
        if entry.source_id in INVESTMENT_SOURCES
    )
    if not expected and not milestones:
        return None
    retrieved = clock()
    sidecars = {
        entry.key: sidecar_for(
            entry,
            digest="",
            nbytes=0,
            fetch_url=entry.url,
            fetch_host=entry.fetch_host,
            retrieved_utc=retrieved,
            publisher=entry.publisher,
            source_modified="",
            row_count=None,
            terms_sha256="",
        )
        for entry in entries
        if entry.source_id in INVESTMENT_SOURCES
    }
    try:
        project_registrations = tuple(
            registration
            for registration in expected
            if registration.source_id == "fdi_projects"
        )
        projection = None
        if project_registrations or milestones:
            selections = tuple(
                ProjectArchiveSelection(
                    registration.key, str(attempt.snapshot_identity), {}
                )
                for registration in project_registrations
                for attempt in attempts
                if attempt.source_id == registration.source_id
                and attempt.key == registration.key
                and attempt.status == "success"
                and isinstance(attempt.snapshot_identity, str)
            )
            if audit_history:
                # History is an audit input only. Release consumers still require
                # their explicit reviewed selection and never choose a latest file.
                selections = tuple(
                    ProjectArchiveSelection(registration.key, path.stem, {})
                    for registration in project_registrations
                    for path in sorted(
                        (cache / registration.key / "index").glob("*.json")
                    )
                )
            projection = build_cache_evidence(
                cache,
                projects=selections,
                milestones=milestones,
                expected=project_registrations
                + tuple(
                    ExpectedInput(item.envelope.source_id, item.key, "milestone")
                    for item in milestones
                ),
                attempts=tuple(attempts),
            )
        audited = (
            projection
            if isinstance(projection, InvestmentFailure)
            else archive_fetch_attempts(
                cache,
                expected,
                tuple(attempts),
                sidecars=sidecars,
                retrieved_utc=retrieved,
            )
        )
    except (OSError, ValueError):
        audited = InvestmentFailure(
            1,
            "investment_evidence",
            "",
            "evidence_audit_incomplete",
            "archived attempt evidence",
            "write or verification failed",
        )
    if isinstance(audited, InvestmentFailure):
        lines.append(
            fail_line(
                audited.source_id,
                audited.url,
                audited.check,
                audited.expected,
                audited.observed,
            )
        )
        return FetchFailure(
            1,
            audited.source_id,
            audited.url,
            audited.check,
            audited.expected,
            audited.observed,
        )
    if audit_entries is not None:
        if isinstance(projection, EvidenceProjection):
            audit_entries.extend(projection.audit.entries)
        audit_entries.extend(
            entry for entry in audited.entries if entry not in audit_entries
        )
    registry_keys = frozenset(registration.key for registration in expected)
    for entry in audited.entries:
        status = (
            "retained"
            if entry.evidence_status == "observed_announcement"
            else entry.evidence_status
        )
        lines.append(
            evidence_line(entry.key, status, entry.reason, registry_keys=registry_keys)
        )
    return None


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
    terms_attempts: list[dict[str, object]],
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
            terms_attempts=tuple(terms_attempts),
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
    attempts: list[dict[str, object]],
) -> None:
    """Record the fingerprint a terms_page row already read inside its fetch."""
    if not entry.terms_url:
        return
    if fetched.terms_unread == TERMS_HOST_UNLISTED:
        lines.append(
            terms_host_line(entry.key, host_of(entry.terms_url), entry.terms_url)
        )
        attempts.append(
            terms_attempt_record(entry, TERMS_HOST_NOT_LISTED, fetched.retrieved_utc)
        )
        return
    if fetched.terms_unread:
        lines.append(
            terms_unread_line(entry.key, fetched.terms_unread, entry.terms_url)
        )
        attempts.append(
            terms_attempt_record(entry, fetched.terms_unread, fetched.retrieved_utc)
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
    cache: Path,
    attempts: list[dict[str, object]],
) -> None:
    """Read a terms page that the row's own fetch does not read.

    An unread page keeps its advisory line and adds one attempt record with the
    attempt time and reason; the recorded reading date is never set from it.
    """
    if not approve(entry.terms_url).ok:
        lines.append(
            terms_host_line(entry.key, host_of(entry.terms_url), entry.terms_url)
        )
        attempts.append(terms_attempt_record(entry, TERMS_HOST_NOT_LISTED, clock()))
        return
    read = read_terms_page(entry, transport, sleep)
    if read.failure is not None:
        lines.append(terms_unread_line(entry.key, read.failure.check, entry.terms_url))
        attempts.append(terms_attempt_record(entry, read.failure.check, clock()))
        return
    retrieved = clock()
    archive_auxiliary(
        entry, cache / entry.key, "terms", read.body, retrieved, entry.terms_url
    )
    _record_terms(entry, read.sha256, retrieved, previous, lines, terms)


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


def _write_log(
    cache: Path,
    lines: list[str],
    terms: list[dict[str, object]],
    terms_attempts: list[dict[str, object]],
) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            {"lines": lines, "terms": terms, "terms_attempts": terms_attempts},
            sort_keys=True,
        )
        + "\n"
    )
    partial = cache / ".build-log.json.partial"
    final = cache / LOG_NAME
    try:
        partial.write_text(payload, encoding="utf-8")
        os.replace(partial, final)
    except OSError:
        partial.unlink(missing_ok=True)
        raise
