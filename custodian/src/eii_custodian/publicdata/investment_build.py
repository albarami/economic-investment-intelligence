"""Acquire investment pages, validate one batch, and publish it atomically.

A failed build leaves the earlier loadable snapshot byte-identical and is
not reported as a refresh of that snapshot. A changed raw file is stored
beside the old one.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from email.message import EmailMessage
from pathlib import Path

from eii_custodian.publicdata.fetch.kinds import read_bounded
from eii_custodian.publicdata.fetch.receipts import commit_pair, sha256_hex, sidecar_for
from eii_custodian.publicdata.fetch.registry import Entry, RegistryError, read_yaml
from eii_custodian.publicdata.fetch.snapshots import (
    SnapshotError,
    publish_snapshot,
    read_snapshot,
)
from eii_custodian.publicdata.fetch.transport import Transport
from eii_custodian.publicdata.investment_contracts import (
    AGENCY_KINDS,
    CAPEX_LABEL_WORDS,
    CAPEX_UNIT_USD,
    CAVEAT_KEY,
    CAVEAT_PHRASES,
    COLUMN_FROM_PAGE,
    FURTHER_FIELDS,
    LINEAGE_FIELDS,
    MEASURED_PERIOD_FIRST,
    MEASURED_PERIOD_LAST,
    MEASURED_ROW_MAX,
    MEASURED_ROW_MIN,
    PROVENANCE_PUBLIC,
    SCHEMA_AGENCY,
    SCHEMA_FDI,
    SCHEMA_MANIFEST,
    SHAPE_ID,
    TERMS_READING_FIELDS,
    Bounds,
    Confirmation,
    DashboardShape,
    InvestmentFailure,
    KindRule,
    SourceEnvelope,
)
from eii_custodian.publicdata.investment_crosswalk import load_crosswalk
from eii_custodian.publicdata.investment_parse import (
    agency_envelope,
    dashboard_envelope,
    field_coverage_failure,
    parse_agency,
    parse_fdi,
)
from eii_custodian.publicdata.investment_quotation import page_evidence

Sleeper = Callable[[float], None]
Clock = Callable[[], str]
INVESTMENT_SOURCES = frozenset({"fdi_projects", "investqa_pages"})
_PAGES = Path(__file__).resolve().parents[3] / "publicdata" / "investment_pages.yaml"


@dataclass(frozen=True)
class PageSpec:
    """One confirmed agency page."""

    kind: str
    url: str
    minimum_blocks: int
    minimum_paragraphs: int
    language: str = "en"


@dataclass(frozen=True)
class SourceSpec:
    """The reviewed shape, bounds and confirmation for one investment source."""

    source_id: str
    bounds: Bounds
    confirmation: Confirmation
    snapshot_identity: str
    currency_rule: str
    location_precision: str
    dashboard: DashboardShape | None
    pages: tuple[PageSpec, ...]
    parameter_units: Mapping[str, str]
    activity_keys: Mapping[str, str]
    furniture: frozenset[str]
    kind_rules: Mapping[str, KindRule]


def publish_investment(
    entry: Entry,
    cache: Path,
    digest: str,
    transport: Transport,
    sleep: Sleeper,
    clock: Clock,
) -> InvestmentFailure | None:
    """Parse one investment source after its fetch. Other sources are untouched."""
    if entry.source_id not in INVESTMENT_SOURCES:
        return None
    spec = load_source_spec(entry.source_id, url=entry.url)
    if isinstance(spec, InvestmentFailure):
        return _refuse(cache, entry.source_id, spec)
    if not spec.bounds.confirmed:
        return _refuse(
            cache,
            entry.source_id,
            InvestmentFailure(
                1,
                entry.source_id,
                entry.url,
                "unconfirmed",
                "confirmed specification",
                "unconfirmed",
            ),
        )
    try:
        if entry.source_id == "fdi_projects":
            failure = _publish_dashboard(entry, spec, cache, digest, clock)
        else:
            failure = _publish_agency(
                entry, spec, cache, digest, transport, sleep, clock
            )
    except OSError:
        _clear_partials(cache / entry.source_id)
        return _refuse(
            cache,
            entry.source_id,
            InvestmentFailure(
                1,
                entry.source_id,
                entry.url,
                "write_failed",
                "stored file",
                "write failed",
            ),
        )
    if failure is not None:
        return _refuse(cache, entry.source_id, failure)
    return None


def load_source_spec(source_id: str, *, url: str) -> SourceSpec | InvestmentFailure:
    """Load the reviewed page specification. An unknown key cannot publish."""
    if not _PAGES.is_file():
        return InvestmentFailure(
            1, source_id, url, "unconfirmed", "page specification", "missing"
        )
    try:
        loaded = read_yaml(_PAGES)
    except RegistryError:
        return InvestmentFailure(
            1, source_id, url, "unconfirmed", "page specification", "unreadable"
        )
    if not isinstance(loaded, dict):
        return InvestmentFailure(
            1, source_id, url, "unconfirmed", "page specification", "unreadable"
        )
    sources = loaded.get("sources")
    if not isinstance(sources, dict) or source_id not in sources:
        return InvestmentFailure(1, source_id, url, "unconfirmed", source_id, "missing")
    row = sources[source_id]
    if not isinstance(row, dict):
        return InvestmentFailure(
            1, source_id, url, "unconfirmed", source_id, "unreadable"
        )
    if loaded.get("schema_version") != "investment_pages.v2":
        return InvestmentFailure(
            1, source_id, url, "inventory_schema", "investment_pages.v2", "unsupported"
        )
    if source_id == "fdi_projects":
        return _dashboard_spec(row, url)
    return _agency_spec(row, url)


def validate_investment(
    rows: tuple[Mapping[str, object], ...],
    bounds: Bounds,
    confirmation: Confirmation,
    envelope: SourceEnvelope,
) -> tuple[dict[str, object], ...] | InvestmentFailure:
    """Accept one batch or refuse it. A refusal publishes nothing."""
    if not bounds.confirmed:
        return fail_of(
            envelope, "unconfirmed", "confirmed specification", "unconfirmed"
        )
    for name, flag in (
        ("confirmation_inventory", confirmation.inventory_recorded),
        ("confirmation_fields", confirmation.field_coverage_recorded),
        ("confirmation_fixture", confirmation.fixture_comparison_recorded),
    ):
        if not flag:
            return fail_of(envelope, name, "recorded", "missing")
    # Ruling L-1001: a missing terms reading is a pending record that fails
    # nothing; any other missing lineage element still refuses.
    missing = envelope.missing_refusal()
    if missing:
        return fail_of(envelope, "missing_lineage", missing, "absent")
    count = len(rows)
    span = f"{bounds.row_count_min}..{bounds.row_count_max}"
    if count < bounds.row_count_min or count > bounds.row_count_max:
        return fail_of(envelope, "row_count", span, str(count))
    period = _period_failure(rows, bounds, envelope)
    if period is not None:
        return period
    cleaned: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        checked = _row_failure(row, envelope)
        if isinstance(checked, InvestmentFailure):
            return checked
        identity = str(checked.get("project_key") or checked.get("record_key"))
        if identity in seen:
            return fail_of(envelope, "duplicate_key", "unique key", identity)
        seen.add(identity)
        cleaned.append(checked)
    parents = _parent_failure(cleaned, envelope)
    if parents is not None:
        return parents
    return tuple(cleaned)


def require_page_families(
    kinds: tuple[str, ...], envelope: SourceEnvelope
) -> InvestmentFailure | None:
    """Fail when a confirmed agency source omits a page family."""
    missing = [kind for kind in AGENCY_KINDS if kind not in kinds]
    if not missing:
        return None
    return fail_of(envelope, "missing_page", "page family", ",".join(missing))


def select_release(
    pointer: Mapping[str, object], *, reviewed: bool
) -> InvestmentFailure | None:
    """Refuse a release hash that has not been reviewed. This task never selects one."""
    source_id = pointer.get("source_id")
    name = source_id if isinstance(source_id, str) else ""
    if reviewed is not True:
        return InvestmentFailure(
            1, name, "", "unreviewed_release", "reviewed selection", "unreviewed"
        )
    return None


def audit_snapshot(cache: Path, source_id: str) -> InvestmentFailure | None:
    """Fail when a loadable manifest names a missing or hash-mismatched page."""
    pointer = _read_json(cache / source_id / "loadable.json")
    if not isinstance(pointer, dict):
        return InvestmentFailure(
            1, source_id, "", "missing_artifact", "loadable", "missing"
        )
    digest = pointer.get("manifest_sha256")
    if not isinstance(digest, str):
        return InvestmentFailure(
            1, source_id, "", "missing_artifact", "manifest", "missing"
        )
    manifest_path = cache / source_id / "manifests" / f"{digest}.json"
    try:
        manifest_body = manifest_path.read_bytes()
    except OSError:
        return InvestmentFailure(
            1, source_id, "", "missing_artifact", digest, "missing"
        )
    if sha256_hex(manifest_body) != digest:
        return InvestmentFailure(1, source_id, "", "hash_mismatch", digest, "mismatch")
    try:
        manifest: object = json.loads(manifest_body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return InvestmentFailure(
            1, source_id, "", "missing_artifact", digest, "missing"
        )
    if not isinstance(manifest, dict):
        return InvestmentFailure(
            1, source_id, "", "missing_artifact", digest, "missing"
        )
    return _audit_pages(cache, source_id, manifest)


def _audit_pages(
    cache: Path, source_id: str, manifest: Mapping[str, object]
) -> InvestmentFailure | None:
    """Fail when a candidate manifest names a missing or hash-mismatched page."""
    pages = manifest.get("pages")
    if not isinstance(pages, list):
        return InvestmentFailure(
            1, source_id, "", "missing_artifact", "pages", "missing"
        )
    if not pages:
        return InvestmentFailure(1, source_id, "", "missing_artifact", "pages", "empty")
    for page in pages:
        if not isinstance(page, dict):
            return InvestmentFailure(
                1, source_id, "", "hash_mismatch", "page", "unreadable"
            )
        page_hash = page.get("sha256")
        url = page.get("url")
        if not isinstance(page_hash, str) or not isinstance(url, str):
            return InvestmentFailure(
                1, source_id, "", "hash_mismatch", "page", "unreadable"
            )
        body = cache / source_id / f"{page_hash}.html"
        if not body.is_file():
            return InvestmentFailure(
                1, source_id, url, "missing_artifact", page_hash, "missing"
            )
        if sha256_hex(body.read_bytes()) != page_hash:
            return InvestmentFailure(
                1, source_id, url, "hash_mismatch", page_hash, "mismatch"
            )
    if source_id == "investqa_pages":
        for order, page in enumerate(pages[1:], 1):
            checked = page_evidence(cache / source_id, page, order)
            if isinstance(checked, InvestmentFailure):
                return checked
    return None


def fail_of(
    envelope: SourceEnvelope, check: str, expected: str, observed: str, *, code: int = 1
) -> InvestmentFailure:
    """Build a failure from an envelope."""
    return InvestmentFailure(
        code, envelope.source_id, envelope.page_url, check, expected, observed
    )


def _publish_dashboard(
    entry: Entry, spec: SourceSpec, cache: Path, digest: str, clock: Clock
) -> InvestmentFailure | None:
    del clock
    if spec.dashboard is None:
        return InvestmentFailure(
            1, entry.source_id, entry.url, "unconfirmed", "dashboard", "missing"
        )
    coverage = field_coverage_failure(spec.dashboard.fields)
    if coverage is not None:
        return coverage
    body = _cached_body(
        cache, entry.key, digest, entry.extension, entry.source_id, entry.url
    )
    if isinstance(body, InvestmentFailure):
        return body
    receipt = _receipt(cache, entry.key, digest, entry.source_id, entry.url)
    if isinstance(receipt, InvestmentFailure):
        return receipt
    terms, retrieved = receipt
    envelope = dashboard_envelope(
        _envelope(entry, entry.url, digest, terms, retrieved, method="")
    )
    parsed = parse_fdi(body, spec.dashboard, envelope)
    if isinstance(parsed, InvestmentFailure):
        return parsed
    rows, empty_coordinates = parsed
    validated = validate_investment(
        rows, _bounds(entry, spec), spec.confirmation, envelope
    )
    if isinstance(validated, InvestmentFailure):
        return validated
    document = {
        "schema_version": SCHEMA_FDI,
        "source_id": entry.source_id,
        "caveat_keys": [CAVEAT_KEY],
        "caveat_text": {key: phrase for key, phrase in CAVEAT_PHRASES},
        "row_count": len(validated),
        "empty_coordinate_count": empty_coordinates,
        "rows": list(validated),
    }
    pages = (
        {
            "url": entry.url,
            "sha256": digest,
            "retrieved_utc": retrieved,
            "kind": "dashboard",
        },
    )
    committed = _commit_batch(
        cache, entry, spec, envelope, document, pages, terms, retrieved
    )
    if committed is not None:
        return committed
    _atomic_write(
        cache / entry.source_id / "empty_coordinates.txt",
        f"{entry.source_id} empty_coordinates={empty_coordinates}\n",
    )
    return None


def _publish_agency(
    entry: Entry,
    spec: SourceSpec,
    cache: Path,
    digest: str,
    transport: Transport,
    sleep: Sleeper,
    clock: Clock,
) -> InvestmentFailure | None:
    missing_family = require_page_families(
        tuple(page.kind for page in spec.pages),
        _envelope(entry, entry.url, digest, "", "", method=""),
    )
    if missing_family is not None:
        return missing_family
    for language in {page.language for page in spec.pages}:
        missing = require_page_families(
            tuple(page.kind for page in spec.pages if page.language == language),
            _envelope(entry, entry.url, digest, "", "", method=""),
        )
        if missing is not None:
            return missing
    receipt = _receipt(cache, entry.key, digest, entry.source_id, entry.url)
    if isinstance(receipt, InvestmentFailure):
        return receipt
    terms, landing_retrieved = receipt
    pages: list[dict[str, object]] = [
        {
            "url": entry.url,
            "sha256": digest,
            "retrieved_utc": landing_retrieved,
            "kind": "landing",
        }
    ]
    rows: list[dict[str, object]] = []
    for order, page in enumerate(spec.pages, 1):
        fetched = _fetch_page(entry, cache, page.url, transport, sleep, clock, terms)
        if isinstance(fetched, InvestmentFailure):
            return fetched
        page_digest, retrieved, body = fetched
        pages.append(
            {
                "url": page.url,
                "sha256": page_digest,
                "retrieved_utc": retrieved,
                "kind": page.kind,
                "language": page.language,
                "order": order,
            }
        )
        envelope = agency_envelope(
            _envelope(entry, page.url, page_digest, terms, retrieved, method="")
        )
        rule = spec.kind_rules.get(page.kind)
        if rule is None:
            return fail_of(envelope, "missing_page", page.kind, "missing")
        parsed = parse_agency(
            body,
            rule=rule,
            furniture=spec.furniture,
            minimum_blocks=page.minimum_blocks,
            minimum_paragraphs=page.minimum_paragraphs,
            envelope=envelope,
            language=page.language,
        )
        if isinstance(parsed, InvestmentFailure):
            return parsed
        rows.extend(parsed)
    envelope = agency_envelope(
        _envelope(entry, entry.url, digest, terms, landing_retrieved, method="")
    )
    validated = validate_investment(
        tuple(rows), _bounds(entry, spec), spec.confirmation, envelope
    )
    if isinstance(validated, InvestmentFailure):
        return validated
    document = {
        "schema_version": SCHEMA_AGENCY,
        "source_id": entry.source_id,
        "row_count": len(validated),
        "rows": list(validated),
    }
    return _commit_batch(
        cache, entry, spec, envelope, document, tuple(pages), terms, landing_retrieved
    )


def header_charset(headers: Mapping[str, str]) -> str:
    """Read the charset parameter of ``Content-Type``, if any."""
    value = headers.get("Content-Type") or headers.get("content-type") or ""
    if not value:
        return ""
    message = EmailMessage()
    message["content-type"] = value
    charset = message.get_content_charset()
    return charset if isinstance(charset, str) else ""


def _fetch_page(
    entry: Entry,
    cache: Path,
    url: str,
    transport: Transport,
    sleep: Sleeper,
    clock: Clock,
    terms: str,
) -> tuple[str, str, bytes] | InvestmentFailure:
    response, failure = read_bounded(transport, sleep, url)
    if failure is not None or response is None:
        code = failure.code if failure is not None else 1
        check = failure.check if failure is not None else "check_failed"
        expected = failure.expected if failure is not None else "readable page"
        observed = failure.observed if failure is not None else "missing"
        return InvestmentFailure(code, entry.source_id, url, check, expected, observed)
    page_digest = sha256_hex(response.body)
    directory = cache / entry.key
    retrieved = clock()
    side = sidecar_for(
        entry,
        digest=page_digest,
        nbytes=len(response.body),
        fetch_url=url,
        fetch_host=entry.fetch_host,
        retrieved_utc=retrieved,
        publisher=entry.publisher,
        source_modified="",
        row_count=None,
        terms_sha256=terms,
    )
    charset = header_charset(response.headers)
    if charset:
        side["charset"] = charset
    try:
        commit_pair(directory, page_digest, entry.extension, response.body, side)
        snapshot = read_snapshot(directory, page_digest)
        archived_retrieved = snapshot.sidecar["retrieved_utc"]
        if not isinstance(archived_retrieved, str):
            raise SnapshotError("snapshot_index_invalid")
        return page_digest, archived_retrieved, snapshot.body
    except SnapshotError:
        return InvestmentFailure(
            1, entry.source_id, url, "snapshot_invalid", "verified snapshot", "invalid"
        )


def _commit_batch(
    cache: Path,
    entry: Entry,
    spec: SourceSpec,
    envelope: SourceEnvelope,
    document: Mapping[str, object],
    pages: tuple[Mapping[str, object], ...],
    terms: str,
    retrieved: str,
) -> InvestmentFailure | None:
    if entry.source_id == "investqa_pages":
        if len(pages) != len(spec.pages) + 1:
            return fail_of(envelope, "page_evidence", "complete inventory", "missing")
        for order, (page, expected) in enumerate(
            zip(pages[1:], spec.pages, strict=True), 1
        ):
            if (
                page.get("url") != expected.url
                or page.get("language") != expected.language
                or page.get("kind") != expected.kind
            ):
                return fail_of(
                    envelope, "page_evidence", "inventory agreement", "different"
                )
            checked = page_evidence(cache / entry.source_id, dict(page), order)
            if isinstance(checked, InvestmentFailure):
                return checked
    text = _dump(document)
    table_digest = sha256_hex(text.encode("utf-8"))
    table_path = cache / entry.source_id / "staging" / f"{table_digest}.json"
    _atomic_write(table_path, text)
    try:
        _archive_evidence(
            cache, entry, envelope, terms, retrieved, table_digest, text.encode()
        )
    except SnapshotError:
        _discard_candidate(cache, entry.source_id, table_path, table_path)
        return InvestmentFailure(
            1,
            entry.source_id,
            envelope.page_url,
            "snapshot_invalid",
            "verified parsed evidence",
            "invalid",
        )
    manifest = {
        "schema_version": SCHEMA_MANIFEST,
        "source_id": entry.source_id,
        "snapshot_identity": spec.snapshot_identity,
        "release_selected": False,
        "live_page_compared": spec.confirmation.live_page_compared,
        "currency_rule": spec.currency_rule,
        "location_precision": spec.location_precision,
        "publisher": envelope.publisher,
        "licence_id": envelope.licence_id,
        "licence_basis": envelope.licence_basis,
        "decision_record": envelope.decision_record,
        "terms_sha256": terms,
        "terms_url": envelope.terms_url,
        "retrieved_utc": retrieved,
        "parser_method": envelope.method,
        "parser_version": envelope.method_version,
        "table_sha256": table_digest,
        "table_snapshot_identity": table_digest,
        "pages": list(pages),
    }
    if entry.source_id == "investqa_pages":
        page_rows, refusals = selected_page_rows(
            cache / entry.key, [dict(page) for page in pages], spec.furniture
        )
        checked_pages = validate_page_rows(page_rows, page_rows)
        if isinstance(checked_pages, InvestmentFailure):
            return checked_pages
        page_body = _dump({"page_rows": page_rows, "page_refusals": refusals}).encode()
        page_digest = sha256_hex(page_body)
        try:
            _archive_evidence(
                cache, entry, envelope, terms, retrieved, page_digest, page_body
            )
        except SnapshotError:
            return fail_of(envelope, "page_evidence", "verified page table", "invalid")
        manifest["page_table_sha256"] = page_digest
        manifest["page_table_snapshot_identity"] = page_digest
    manifest_text = _dump(manifest)
    manifest_digest = sha256_hex(manifest_text.encode("utf-8"))
    manifest_path = cache / entry.source_id / "manifests" / f"{manifest_digest}.json"
    _atomic_write(manifest_path, manifest_text)
    audited = _audit_pages(cache, entry.source_id, manifest)
    if audited is not None:
        _discard_candidate(cache, entry.source_id, table_path, manifest_path)
        return audited
    try:
        _archive_evidence(
            cache,
            entry,
            envelope,
            terms,
            retrieved,
            manifest_digest,
            manifest_text.encode(),
        )
    except SnapshotError:
        _discard_candidate(cache, entry.source_id, table_path, manifest_path)
        return InvestmentFailure(
            1,
            entry.source_id,
            envelope.page_url,
            "snapshot_invalid",
            "verified manifest evidence",
            "invalid",
        )
    pointer = {
        "source_id": entry.source_id,
        "manifest_sha256": manifest_digest,
        "evidence_manifest_identity": manifest_digest,
        "release_selected": False,
    }
    _atomic_json(cache / entry.source_id / "loadable.json", pointer)
    return None


def _archive_evidence(
    cache: Path,
    entry: Entry,
    envelope: SourceEnvelope,
    terms: str,
    retrieved: str,
    identity: str,
    body: bytes,
) -> None:
    """Retain one parsed object and its immutable receipt below evidence/."""
    side = sidecar_for(
        entry,
        digest=identity,
        nbytes=len(body),
        fetch_url=envelope.page_url,
        fetch_host=entry.fetch_host,
        retrieved_utc=retrieved,
        publisher=envelope.publisher,
        source_modified="",
        row_count=None,
        terms_sha256=terms,
    )
    side["parser_method"] = envelope.method
    side["parser_version"] = envelope.method_version
    publish_snapshot(
        cache / entry.source_id / "evidence",
        "json",
        body,
        side,
        identity=identity,
    )


def _bounds(entry: Entry, spec: SourceSpec) -> Bounds:
    low = (
        entry.row_count_min
        if entry.row_count_min is not None
        else spec.bounds.row_count_min
    )
    high = (
        entry.row_count_max
        if entry.row_count_max is not None
        else spec.bounds.row_count_max
    )
    period_field = entry.period_field or spec.bounds.period_field
    period_last = entry.period_last or spec.bounds.period_last
    return Bounds(low, high, period_field, period_last, spec.bounds.confirmed)


def _envelope(
    entry: Entry, url: str, digest: str, terms: str, retrieved: str, method: str
) -> SourceEnvelope:
    del method
    return SourceEnvelope(
        source_id=entry.source_id,
        publisher=entry.publisher,
        page_url=url,
        licence_id=entry.licence_id,
        licence_basis=entry.licence_basis,
        decision_record=entry.decision_record,
        terms_sha256=terms,
        terms_url=entry.terms_url,
        retrieved_utc=retrieved,
        page_sha256=digest,
        method="",
        method_version="",
    )


def _cached_body(
    cache: Path, key: str, digest: str, extension: str, source_id: str, url: str
) -> bytes | InvestmentFailure:
    path = cache / key / f"{digest}.{extension}"
    if not path.is_file():
        return InvestmentFailure(
            1, source_id, url, "missing_artifact", digest, "missing"
        )
    body = path.read_bytes()
    if sha256_hex(body) != digest:
        return InvestmentFailure(1, source_id, url, "hash_mismatch", digest, "mismatch")
    return body


def _receipt(
    cache: Path, key: str, digest: str, source_id: str, url: str
) -> tuple[str, str] | InvestmentFailure:
    side = _read_json(cache / key / f"{digest}.meta.json")
    if not isinstance(side, dict):
        return InvestmentFailure(
            1, source_id, url, "missing_artifact", "sidecar", "missing"
        )
    terms = side.get("terms_sha256")
    retrieved = side.get("retrieved_utc")
    # Ruling L-1001: a missing or empty terms reading is a pending record and
    # never refuses; a non-string slot stays a malformed record.
    if terms is not None and not isinstance(terms, str):
        return InvestmentFailure(
            1, source_id, url, "missing_terms", "terms hash", "absent"
        )
    if not isinstance(retrieved, str) or retrieved == "":
        return InvestmentFailure(
            1, source_id, url, "missing_lineage", "retrieved_utc", "absent"
        )
    return terms if isinstance(terms, str) else "", retrieved


def _row_failure(
    row: Mapping[str, object], envelope: SourceEnvelope
) -> dict[str, object] | InvestmentFailure:
    for name in LINEAGE_FIELDS:
        value = row.get(name)
        if name in TERMS_READING_FIELDS:
            # Ruling L-1001: a pending terms reading (empty or absent) is a
            # record and never refuses a row; a non-string slot stays a
            # malformed record and keeps its refusal.
            if value is not None and not isinstance(value, str):
                return fail_of(envelope, "missing_terms", name, "absent")
            continue
        if not isinstance(value, str) or value == "":
            return fail_of(envelope, "missing_lineage", name, "absent")
    provenance = row.get("provenance")
    if provenance != PROVENANCE_PUBLIC:
        observed = provenance if isinstance(provenance, str) else "missing"
        return fail_of(envelope, "provenance", PROVENANCE_PUBLIC, observed)
    if row.get("join_key") not in ("", None):
        return fail_of(envelope, "prohibited_join", "no join", "joined")
    if "project_key" in row:
        keys = row.get("caveat_keys")
        if not isinstance(keys, list) or CAVEAT_KEY not in keys:
            return fail_of(envelope, "missing_caveat", CAVEAT_KEY, "absent")
    cleaned = dict(row)
    cleaned.pop("join_key", None)
    return cleaned


def _parent_failure(
    rows: list[dict[str, object]], envelope: SourceEnvelope
) -> InvestmentFailure | None:
    levels: dict[tuple[str, int], int] = {}
    for row in rows:
        ordinal = row.get("ordinal")
        level = row.get("level")
        if isinstance(ordinal, int) and isinstance(level, int):
            levels[(str(row.get("page_url")), ordinal)] = level
    for row in rows:
        parent = row.get("parent_ordinal")
        if parent is None:
            continue
        ordinal = row.get("ordinal")
        level = row.get("level")
        earlier = (
            levels.get((str(row.get("page_url")), parent))
            if isinstance(parent, int)
            else None
        )
        if (
            not isinstance(parent, int)
            or not isinstance(ordinal, int)
            or not isinstance(level, int)
            or earlier is None
            or parent >= ordinal
            or earlier >= level
        ):
            return fail_of(
                envelope, "invalid_parent", "earlier higher block", "unmatched"
            )
    return None


def _period_failure(
    rows: tuple[Mapping[str, object], ...], bounds: Bounds, envelope: SourceEnvelope
) -> InvestmentFailure | None:
    if bounds.period_last == "" or bounds.period_field == "":
        return None
    stated = [
        value
        for row in rows
        if isinstance((value := row.get(bounds.period_field)), str) and value != ""
    ]
    if bounds.period_field == "announced" and not stated:
        return fail_of(envelope, "period_last", bounds.period_last, "missing")
    if stated and max(stated) < bounds.period_last:
        return fail_of(envelope, "period_last", bounds.period_last, max(stated))
    return None


def _dashboard_spec(
    row: Mapping[str, object], url: str
) -> SourceSpec | InvestmentFailure:
    for name in ("country_iso3", "municipality_code", "place_key"):
        if row.get(name, {}) != {}:
            return InvestmentFailure(
                1,
                "fdi_projects",
                url,
                "name_derived_key",
                "identifier crosswalk",
                "legacy map",
            )
    crosswalk = load_crosswalk()
    if isinstance(crosswalk, InvestmentFailure):
        return replace(crosswalk, url=url)
    confirmation = _confirmation(row.get("confirmation"), "fdi_projects", url)
    if isinstance(confirmation, InvestmentFailure):
        return confirmation
    bounds = _spec_bounds(row, "fdi_projects", url)
    if isinstance(bounds, InvestmentFailure):
        return bounds
    if "cache_only" in row:
        return InvestmentFailure(
            1, "fdi_projects", url, "unconfirmed", "cache-only fields", "present"
        )
    mapping = row.get("mapping")
    if mapping != COLUMN_FROM_PAGE:
        return InvestmentFailure(
            1, "fdi_projects", url, "confirmation_fields", "mapped fields", "incomplete"
        )
    further = _string_list(row.get("further_fields"))
    if further is None or set(further) != set(FURTHER_FIELDS):
        return InvestmentFailure(
            1,
            "fdi_projects",
            url,
            "confirmation_fields",
            "further fields",
            "incomplete",
        )
    caveats = row.get("caveats")
    if caveats != {key: phrase for key, phrase in CAVEAT_PHRASES}:
        return InvestmentFailure(
            1, "fdi_projects", url, "missing_caveat", CAVEAT_KEY, "incomplete"
        )
    if row.get("capex_unit") != CAPEX_UNIT_USD:
        return InvestmentFailure(
            1, "fdi_projects", url, "capex_label", CAPEX_UNIT_USD, "missing"
        )
    if _string_list(row.get("capex_label_words")) != CAPEX_LABEL_WORDS:
        return InvestmentFailure(
            1, "fdi_projects", url, "capex_label", "Capex Mn USD", "missing"
        )
    if row.get("location_precision") != "location_text":
        return InvestmentFailure(
            1, "fdi_projects", url, "unconfirmed", "location_text", "missing"
        )
    if row.get("snapshot_identity") != "page_sha256":
        return InvestmentFailure(
            1, "fdi_projects", url, "unconfirmed", "page_sha256", "missing"
        )
    if row.get("shape_id") != SHAPE_ID:
        return InvestmentFailure(
            1, "fdi_projects", url, "shape_mismatch", SHAPE_ID, "missing"
        )
    if (
        bounds.row_count_min != MEASURED_ROW_MIN
        or bounds.row_count_max != MEASURED_ROW_MAX
        or bounds.period_last != MEASURED_PERIOD_LAST
        or row.get("period_first") != MEASURED_PERIOD_FIRST
    ):
        return InvestmentFailure(
            1, "fdi_projects", url, "unconfirmed", "measured bounds", "incomplete"
        )
    return SourceSpec(
        source_id="fdi_projects",
        bounds=bounds,
        confirmation=confirmation,
        snapshot_identity="page_sha256",
        currency_rule=CAPEX_UNIT_USD,
        location_precision="location_text",
        dashboard=DashboardShape(
            shape_id=SHAPE_ID,
            fields=frozenset(COLUMN_FROM_PAGE),
            column_from=dict(COLUMN_FROM_PAGE),
            country_iso3=_string_map(row.get("country_iso3")),
            municipality_code=_string_map(row.get("municipality_code")),
            place_key=_string_map(row.get("place_key")),
            crosswalk=crosswalk,
        ),
        pages=(),
        parameter_units={},
        activity_keys={},
        furniture=frozenset(),
        kind_rules={},
    )


def _agency_spec(row: Mapping[str, object], url: str) -> SourceSpec | InvestmentFailure:
    confirmation = _confirmation(row.get("confirmation"), "investqa_pages", url)
    if isinstance(confirmation, InvestmentFailure):
        return confirmation
    bounds = _spec_bounds(row, "investqa_pages", url)
    if isinstance(bounds, InvestmentFailure):
        return bounds
    if row.get("snapshot_identity") != "aggregate_manifest":
        return InvestmentFailure(
            1, "investqa_pages", url, "unconfirmed", "aggregate_manifest", "missing"
        )
    furniture = _string_list(row.get("furniture_classes"))
    if furniture is None:
        return InvestmentFailure(
            1, "investqa_pages", url, "unconfirmed", "furniture", "missing"
        )
    rules = _kind_rules(row.get("kind_rules"), url)
    if isinstance(rules, InvestmentFailure):
        return rules
    pages = _pages(row.get("pages"), url, rules)
    if isinstance(pages, InvestmentFailure):
        return pages
    return SourceSpec(
        source_id="investqa_pages",
        bounds=bounds,
        confirmation=confirmation,
        snapshot_identity="aggregate_manifest",
        currency_rule="",
        location_precision="",
        dashboard=None,
        pages=pages,
        parameter_units={},
        activity_keys={},
        furniture=frozenset(furniture),
        kind_rules=rules,
    )


def _pages(
    value: object, url: str, rules: Mapping[str, KindRule]
) -> tuple[PageSpec, ...] | InvestmentFailure:
    from urllib.parse import urlsplit

    if not isinstance(value, list) or not value:
        return InvestmentFailure(
            1, "investqa_pages", url, "missing_page", "page family", "missing"
        )
    found: list[PageSpec] = []
    for item in value:
        if not isinstance(item, dict):
            return InvestmentFailure(
                1, "investqa_pages", url, "missing_page", "page family", "unreadable"
            )
        kind = item.get("kind")
        page_url = item.get("url")
        if (
            not isinstance(kind, str)
            or not isinstance(page_url, str)
            or kind not in rules
        ):
            return InvestmentFailure(
                1, "investqa_pages", url, "missing_page", "page family", "unreadable"
            )
        rule = rules[kind]
        blocks = item.get("minimum_blocks", rule.minimum_blocks)
        paragraphs = item.get("minimum_paragraphs", rule.minimum_paragraphs)
        if (
            isinstance(blocks, bool)
            or isinstance(paragraphs, bool)
            or not isinstance(blocks, int)
            or not isinstance(paragraphs, int)
        ):
            return InvestmentFailure(
                1, "investqa_pages", url, "missing_page", "page family", "unreadable"
            )
        language = item.get("language")
        if not isinstance(language, str) or language not in {"en", "ar"}:
            return InvestmentFailure(
                1,
                "investqa_pages",
                url,
                "page_language",
                "en or ar",
                "missing or unknown",
            )
        try:
            segment = urlsplit(page_url).path.strip("/").split("/", 1)[0].casefold()
        except ValueError:
            return InvestmentFailure(
                1, "investqa_pages", url, "missing_page", "valid page URL", "unreadable"
            )
        if segment in {"en", "ar"} and segment != language:
            return InvestmentFailure(
                1, "investqa_pages", url, "page_language", language, segment
            )
        found.append(PageSpec(kind, page_url, blocks, paragraphs, language))
    return tuple(found)


def _kind_rules(value: object, url: str) -> dict[str, KindRule] | InvestmentFailure:
    if not isinstance(value, dict):
        return InvestmentFailure(
            1, "investqa_pages", url, "unconfirmed", "kind rules", "missing"
        )
    found: dict[str, KindRule] = {}
    for kind in AGENCY_KINDS:
        item = value.get(kind)
        parsed = _one_rule(item, url)
        if isinstance(parsed, InvestmentFailure):
            return parsed
        found[kind] = parsed
    return found


def _one_rule(item: object, url: str) -> KindRule | InvestmentFailure:
    if not isinstance(item, dict):
        return InvestmentFailure(
            1, "investqa_pages", url, "unconfirmed", "kind rules", "missing"
        )
    page_kind = item.get("page_kind")
    block_kind = item.get("block_kind", "")
    h3_under = item.get("h3_under_h4", "")
    leading = item.get("leading_level")
    minimum = item.get("minimum_blocks")
    paragraphs = item.get("minimum_paragraphs")
    levels = _level_kinds(item.get("level_kinds", {}))
    if (
        not isinstance(page_kind, str)
        or page_kind == ""
        or not isinstance(block_kind, str)
        or not isinstance(h3_under, str)
        or levels is None
        or isinstance(leading, bool)
        or isinstance(minimum, bool)
        or isinstance(paragraphs, bool)
        or not isinstance(leading, int)
        or not isinstance(minimum, int)
        or not isinstance(paragraphs, int)
    ):
        return InvestmentFailure(
            1, "investqa_pages", url, "unconfirmed", "kind rules", "unreadable"
        )
    return KindRule(
        page_kind, block_kind, levels, h3_under, leading, minimum, paragraphs
    )


def _level_kinds(value: object) -> dict[int, str] | None:
    if not isinstance(value, dict):
        return None
    found: dict[int, str] = {}
    for key, mapped in value.items():
        if (
            isinstance(key, bool)
            or not isinstance(key, int)
            or not isinstance(mapped, str)
        ):
            return None
        found[key] = mapped
    return found


def _confirmation(
    value: object, source_id: str, url: str
) -> Confirmation | InvestmentFailure:
    if not isinstance(value, dict):
        return InvestmentFailure(
            1, source_id, url, "confirmation_inventory", "recorded", "missing"
        )
    flags: dict[str, bool] = {}
    for name in (
        "inventory_recorded",
        "field_coverage_recorded",
        "fixture_comparison_recorded",
        "live_page_compared",
    ):
        flag = value.get(name)
        if not isinstance(flag, bool):
            return InvestmentFailure(
                1, source_id, url, "confirmation_inventory", name, "missing"
            )
        flags[name] = flag
    return Confirmation(
        inventory_recorded=flags["inventory_recorded"],
        field_coverage_recorded=flags["field_coverage_recorded"],
        fixture_comparison_recorded=flags["fixture_comparison_recorded"],
        live_page_compared=flags["live_page_compared"],
    )


def _spec_bounds(
    row: Mapping[str, object], source_id: str, url: str
) -> Bounds | InvestmentFailure:
    low = row.get("row_count_min")
    high = row.get("row_count_max")
    period_field = row.get("period_field")
    period_last = row.get("period_last")
    confirmed = row.get("confirmed")
    if (
        isinstance(low, bool)
        or isinstance(high, bool)
        or not isinstance(low, int)
        or not isinstance(high, int)
        or not isinstance(period_field, str)
        or not isinstance(period_last, str)
        or not isinstance(confirmed, bool)
    ):
        return InvestmentFailure(
            1, source_id, url, "unconfirmed", "bounds", "incomplete"
        )
    return Bounds(low, high, period_field, period_last, confirmed)


def _string_list(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return tuple(item for item in value if isinstance(item, str))


def _string_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, str)
    }


def _refuse(
    cache: Path, source_id: str, failure: InvestmentFailure
) -> InvestmentFailure:
    """Return the failure. The earlier snapshot is not removed or reported as refreshed."""
    del cache, source_id
    return failure


def _discard_candidate(
    cache: Path, source_id: str, table_path: Path, manifest_path: Path
) -> None:
    """Remove a candidate that was not published, and keep the files the pointer names."""
    keep_table = ""
    keep_manifest = ""
    pointer = _read_json(cache / source_id / "loadable.json")
    if isinstance(pointer, dict) and isinstance(pointer.get("manifest_sha256"), str):
        keep_manifest = pointer["manifest_sha256"]
        current = _read_json(cache / source_id / "manifests" / f"{keep_manifest}.json")
        if isinstance(current, dict) and isinstance(current.get("table_sha256"), str):
            keep_table = current["table_sha256"]
    if manifest_path.stem != keep_manifest:
        manifest_path.unlink(missing_ok=True)
    if table_path.stem != keep_table:
        table_path.unlink(missing_ok=True)


def _clear_partials(directory: Path) -> None:
    if not directory.exists():
        return
    for path in directory.rglob("*.partial"):
        path.unlink(missing_ok=True)


def _read_json(path: Path) -> object | None:
    if not path.is_file():
        return None
    try:
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded


def _dump(document: Mapping[str, object]) -> str:
    return json.dumps(document, sort_keys=True, ensure_ascii=True) + "\n"


def _atomic_json(path: Path, document: Mapping[str, object]) -> str:
    text = _dump(document)
    _atomic_write(path, text)
    return sha256_hex(text.encode("utf-8"))


def _atomic_bytes(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name("." + path.name + ".partial")
    partial.write_bytes(body)
    _replace(partial, path)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name("." + path.name + ".partial")
    partial.write_text(text, encoding="utf-8")
    _replace(partial, path)


def _replace(source: Path, destination: Path) -> None:
    os.replace(source, destination)


def validate_page_rows(
    rows: object,
    extracted: list[dict[str, object]],
) -> tuple[dict[str, object], ...] | InvestmentFailure:
    """Require closed rows and byte equality against fresh selected-byte extraction."""
    from .investment_agency import page_refusal
    from .investment_contracts import PAGE_COLUMNS, PAGE_EXTRACTOR

    if not isinstance(rows, list) or (extracted and not rows):
        return page_refusal("page_rows_missing")
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != PAGE_COLUMNS:
            return page_refusal("page_columns")
        if row.get("extractor") != PAGE_EXTRACTOR:
            return page_refusal("page_extractor_version")
        key = (str(row["page_key"]), str(row["page_language"]))
        if key in seen:
            return page_refusal("page_duplicate_key")
        seen.add(key)
        original = next(
            (item for item in extracted if item["page_url"] == row["page_url"]), None
        )
        if original is not None and row["page_language"] != original["page_language"]:
            return page_refusal("page_language")
        if original is None or row != original:
            return page_refusal("page_text_mismatch")
    if rows != extracted:
        return page_refusal("page_rows_missing")
    return tuple(dict(row) for row in rows)


def page_public_totals(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """PRV-115 row contributions; the release owner signs the complete inventory."""
    entries = []
    for row in rows:
        selectors = {name: row[name] for name in ("page_key", "page_language")}
        key = json.dumps(selectors, ensure_ascii=False, separators=(",", ":"))
        entries.append(
            {
                "public_total_id": "row:pub_investqa_page:" + key,
                "source_id": row["source_id"],
                "table_name": "pub_investqa_page",
                "selectors": selectors,
                "status": "not_applicable",
                "reason": "source_only",
            }
        )
    return entries


def selected_page_rows(
    directory: Path,
    pages: list[dict[str, object]],
    furniture: frozenset[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Re-read each explicitly selected immutable snapshot; no pointer fallback."""
    from .investment_agency import extract_page, page_refusal

    rows: list[dict[str, object]] = []
    refusals: list[dict[str, object]] = []
    for order, page in enumerate(pages[1:], 1):
        url = str(page.get("url", ""))
        digest = str(page.get("sha256", ""))
        key = str(page.get("page_key", urlsplit_path_key(url)))
        try:
            snapshot = read_snapshot(directory, digest)
            if (
                snapshot.sidecar.get("fetch_url") != url
                or snapshot.sidecar.get("retrieved_utc") != page.get("retrieved_utc")
                or snapshot.sidecar.get("source_id") != "investqa_pages"
                or page.get("order") != order
            ):
                extracted: dict[str, object] | InvestmentFailure = page_refusal(
                    "page_evidence", url
                )
            else:
                extracted = extract_page(
                    snapshot.body,
                    page_url=url,
                    page_language=str(page.get("language", "")),
                    sequence=None,
                    retrieved_on=str(page.get("retrieved_utc", ""))[:10],
                    page_sha256=snapshot.sha256,
                    manifest_sha256=digest,
                    charset=str(snapshot.sidecar.get("charset", "")),
                    furniture=furniture,
                )
        except (OSError, SnapshotError):
            extracted = page_refusal("page_hash_mismatch", url)
        if isinstance(extracted, InvestmentFailure):
            refusals.append({"page_key": key, **asdict(extracted)})
        else:
            rows.append(extracted)
    return rows, refusals


def urlsplit_path_key(url: str) -> str:
    """A report key from a page path, never its refused text."""
    import re
    from urllib.parse import urlsplit

    return re.sub(r"[^a-z0-9]+", "_", urlsplit(url).path.casefold()).strip("_")


def read_page_table(
    directory: Path, manifest: Mapping[str, object]
) -> dict[str, object] | InvestmentFailure:
    """Read the page table beside the unchanged v1 record-table document."""
    from .investment_agency import page_refusal

    identity = manifest.get("page_table_snapshot_identity")
    if not isinstance(identity, str):
        return page_refusal("page_rows_missing")
    try:
        snapshot = read_snapshot(directory, identity)
        if snapshot.sha256 != manifest.get("page_table_sha256"):
            return page_refusal("page_hash_mismatch")
        value = json.loads(snapshot.body)
        if not isinstance(value, dict) or set(value) != {"page_rows", "page_refusals"}:
            return page_refusal("page_rows_missing")
        return value
    except (OSError, SnapshotError, ValueError):
        return page_refusal("page_evidence")
