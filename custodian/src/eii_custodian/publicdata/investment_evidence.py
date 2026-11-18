"""Cache-only announced-project revisions and their explicit evidence states."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from eii_custodian.publicdata.fetch.snapshots import (
    Snapshot,
    SnapshotError,
    publish_snapshot,
    read_snapshot,
)
from eii_custodian.publicdata.investment_contracts import (
    FDI_METHOD,
    LINEAGE_FIELDS,
    PARSER_VERSION,
    PROVENANCE_PUBLIC,
    SCHEMA_FDI,
    EvidenceAudit,
    EvidenceAuditEntry,
    EvidenceProjection,
    ExpectedInput,
    FetchAttempt,
    InvestmentFailure,
    MilestoneArchiveSelection,
    MilestoneCandidate,
    MilestoneEvidence,
    MilestoneShape,
    ObservedInvestment,
    ProjectAbsence,
    ProjectArchiveSelection,
    ProjectEvidence,
    ProjectRevision,
    ProjectSnapshot,
    ReviewedMilestoneLink,
    SourceAssertion,
    SourceEnvelope,
    VerifiedArchive,
    parse_announced,
)
from eii_custodian.publicdata.investment_parse import dashboard_envelope, parse_fdi

_HASH = re.compile(r"[a-f0-9]{64}")
_INDEPENDENCE = frozenset(
    {"independent_report", "publisher_announcement", "syndicated_copy", "unreviewed"}
)
_MISSING_MILESTONE = frozenset(
    {
        "project_identity_unresolved",
        "milestone_not_independent",
        "invalid_evidence_metadata",
        "missing_artifact",
        "unsupported_milestone",
    }
)


_MILESTONE_METHOD = "eii_custodian.publicdata.investment_evidence.parse_milestone_page"
_UNKNOWN_ASSERTION = SourceAssertion(None, "", "not_stated_by_source")


def build_cache_evidence(
    cache: Path,
    *,
    projects: tuple[ProjectArchiveSelection, ...],
    milestones: tuple[MilestoneArchiveSelection, ...],
    expected: tuple[ExpectedInput, ...],
    attempts: tuple[FetchAttempt, ...],
) -> EvidenceProjection | InvestmentFailure:
    """Build the complete S2-T08 projection from explicit verified archives."""
    snapshots: list[ProjectSnapshot] = []
    archives: list[VerifiedArchive] = []
    for selection in projects:
        snapshot = read_snapshot(cache / selection.key, selection.identity)
        if selection.identity != snapshot.sha256:
            return _snapshot_failure(snapshot, "raw snapshot identity", "mismatch")
        item = _parse_project_snapshot(snapshot, coverage=selection.coverage)
        if isinstance(item, InvestmentFailure):
            return item
        snapshots.append(item)
        source_id = str(snapshot.sidecar.get("source_id", ""))
        archives.append(
            VerifiedArchive(
                source_id,
                selection.key,
                "project",
                selection.identity,
                snapshot,
            )
        )

    candidates: list[MilestoneCandidate] = []
    reviewed_links: list[ReviewedMilestoneLink] = []
    for milestone_selection in milestones:
        snapshot = read_snapshot(
            cache / milestone_selection.key, milestone_selection.identity
        )
        if (
            milestone_selection.identity != snapshot.sha256
            or snapshot.sidecar.get("key") != milestone_selection.key
            or snapshot.sidecar.get("source_id")
            != milestone_selection.envelope.source_id
        ):
            return _snapshot_failure(snapshot, "milestone registration", "mismatch")
        envelope = _snapshot_envelope(snapshot, _MILESTONE_METHOD, PARSER_VERSION)
        parsed = parse_milestone_page(
            snapshot.body, milestone_selection.shape, envelope
        )
        if isinstance(parsed, InvestmentFailure):
            return parsed
        candidates.extend(replace(row, snapshot=snapshot) for row in parsed)
        for link in milestone_selection.links:
            if link.crosswalk_sha256:
                try:
                    crosswalk = read_snapshot(
                        cache / milestone_selection.crosswalk_key,
                        link.crosswalk_sha256,
                    )
                except (OSError, SnapshotError):
                    reviewed_links.append(link)
                    continue
                link = replace(
                    link,
                    crosswalk_key=milestone_selection.crosswalk_key,
                    crosswalk=crosswalk,
                )
            reviewed_links.append(link)
        archives.append(
            VerifiedArchive(
                milestone_selection.envelope.source_id,
                milestone_selection.key,
                "milestone",
                milestone_selection.identity,
                snapshot,
                milestone_shape=milestone_selection.shape,
            )
        )

    evidence = build_project_evidence(
        tuple(snapshots), tuple(candidates), tuple(reviewed_links)
    )
    if isinstance(evidence, InvestmentFailure):
        return evidence
    audit = audit_project_evidence(
        expected,
        evidence,
        attempts,
        snapshots=tuple(snapshots),
        archives=tuple(archives),
    )
    if isinstance(audit, InvestmentFailure):
        return audit
    return EvidenceProjection(evidence, audit, tuple(snapshots), tuple(archives))


def _parse_project_snapshot(
    snapshot: Snapshot, *, coverage: Mapping[str, object]
) -> ProjectSnapshot | InvestmentFailure:
    """Parse one raw dashboard body; no caller-supplied row is evidence."""
    from eii_custodian.publicdata.investment_build import load_source_spec

    side = snapshot.sidecar
    source_id = side.get("source_id")
    key = side.get("key")
    url = side.get("fetch_url")
    if (
        source_id != "fdi_projects"
        or not isinstance(key, str)
        or not key
        or not isinstance(url, str)
        or not url
    ):
        return _snapshot_failure(snapshot, "project archive metadata", "mismatch")
    spec = load_source_spec(source_id, url=url)
    if isinstance(spec, InvestmentFailure):
        return spec
    if spec.dashboard is None:
        return _snapshot_failure(snapshot, "confirmed dashboard shape", "missing")
    envelope = _snapshot_envelope(snapshot, FDI_METHOD, PARSER_VERSION)
    parsed = parse_fdi(snapshot.body, spec.dashboard, envelope)
    if isinstance(parsed, InvestmentFailure):
        return parsed
    rows, _empty_coordinates = parsed
    return ProjectSnapshot(
        identity=snapshot.sha256,
        snapshot=snapshot,
        rows=rows,
        schema=SCHEMA_FDI,
        coverage=dict(coverage),
        observation=_UNKNOWN_ASSERTION,
        publication=_UNKNOWN_ASSERTION,
        correction=_UNKNOWN_ASSERTION,
    )


def _snapshot_envelope(snapshot: Snapshot, method: str, version: str) -> SourceEnvelope:
    """Build parser lineage from the verified receipt, never a supplied row."""
    side = snapshot.sidecar

    def text(name: str, alias: str = "") -> str:
        value = side.get(alias or name)
        return value if isinstance(value, str) else ""

    base = SourceEnvelope(
        source_id=text("source_id"),
        publisher=text("publisher"),
        page_url=text("fetch_url"),
        licence_id=text("licence_id"),
        licence_basis=text("licence_basis"),
        decision_record=text("decision_record"),
        terms_sha256=text("terms_sha256"),
        terms_url=text("terms_url") or _registry_terms_url(side),
        retrieved_utc=text("retrieved_utc"),
        page_sha256=snapshot.sha256,
        method=method,
        method_version=version,
    )
    return dashboard_envelope(base) if method == FDI_METHOD else base


def _reread_snapshot(snapshot: Snapshot, identity: str) -> Snapshot:
    """Authenticate the selected archive again; caller-held metadata is not proof."""
    selected = read_snapshot(snapshot.receipt_path.parent.parent, identity)
    if (
        selected.receipt_path != snapshot.receipt_path
        or selected.path != snapshot.path
        or selected.sha256 != snapshot.sha256
    ):
        raise SnapshotError("snapshot_path_invalid")
    return selected


def _snapshot_failure(
    snapshot: Snapshot, expected: str, observed: str
) -> InvestmentFailure:
    source = snapshot.sidecar.get("source_id")
    url = snapshot.sidecar.get("fetch_url")
    return InvestmentFailure(
        1,
        source if isinstance(source, str) else "",
        url if isinstance(url, str) else "",
        "invalid_evidence_metadata",
        expected,
        observed,
    )


def build_project_evidence(
    snapshots: tuple[ProjectSnapshot, ...],
    milestones: tuple[MilestoneCandidate, ...] = (),
    reviewed_links: tuple[ReviewedMilestoneLink, ...] = (),
    *,
    observed_investment: tuple[ObservedInvestment, ...] = (),
) -> ProjectEvidence | InvestmentFailure:
    """Link source-scoped project IDs across immutable, explicitly named snapshots."""
    seen_snapshots: set[str] = set()
    seen_revisions: set[tuple[str, str]] = set()
    identities_by_content: dict[str, str] = {}
    revisions: list[ProjectRevision] = []
    absences: list[ProjectAbsence] = []
    seen_by_source: dict[str, set[str]] = {}
    for item in snapshots:
        if item.identity in seen_snapshots:
            return _refusal(
                item,
                "revision_overwrite",
                "distinct archived snapshot",
                "duplicate snapshot identity",
            )
        seen_snapshots.add(item.identity)
        item = replace(item, rows=tuple(dict(row) for row in item.rows))
        metadata = _metadata_failure(item)
        if isinstance(metadata, InvestmentFailure):
            return metadata
        item = replace(item, snapshot=metadata)
        source_id = str(item.snapshot.sidecar.get("source_id", ""))
        current = {
            f"{row.get('source_id', '')}:project:{row.get('project_id', '')}"
            for row in item.rows
        }
        previous = seen_by_source.setdefault(source_id, set())
        for project_identity in sorted(previous - current):
            absences.append(
                ProjectAbsence(
                    project_identity,
                    source_id,
                    item.identity,
                    "not_present_in_source_snapshot",
                )
            )
        previous.update(current)
        for row in item.rows:
            source_id = str(row.get("source_id", ""))
            project_id = str(row.get("project_id", ""))
            identity = f"{source_id}:project:{project_id}"
            project_key = str(row.get("project_key", ""))
            location = row.get("location_text")
            geography = location if isinstance(location, str) else None
            revision_key = (item.identity, identity)
            if revision_key in seen_revisions:
                return _refusal(
                    item,
                    "project_identity_unresolved",
                    "one project ID per snapshot",
                    "ambiguous project ID",
                )
            seen_revisions.add(revision_key)
            previous_identity = identities_by_content.setdefault(project_key, identity)
            if previous_identity != identity:
                return _refusal(
                    item,
                    "project_identity_unresolved",
                    "stable source-scoped project ID",
                    "changed project ID",
                )
            revisions.append(
                ProjectRevision(
                    project_identity=identity,
                    source_id=source_id,
                    project_id=project_id,
                    snapshot_identity=item.identity,
                    project_key=project_key,
                    observation=_row_observation(row),
                    publication=_UNKNOWN_ASSERTION,
                    retrieved_utc=str(item.snapshot.sidecar.get("retrieved_utc", "")),
                    checksum=item.snapshot.sha256,
                    schema=item.schema,
                    geography=geography,
                    geography_absence_reason=(
                        "" if geography is not None else "not_stated_by_source"
                    ),
                    correction=_UNKNOWN_ASSERTION,
                    announced={
                        "capex": row.get("capex_value"),
                        "jobs": row.get("jobs"),
                        "stated_intent": row.get("description"),
                    },
                    source_chain=dict(row),
                )
            )
    retained = tuple(revisions)
    project_identities = frozenset(row.project_identity for row in retained)
    link_counts: dict[str, int] = {}
    for link in reviewed_links:
        link_counts[link.candidate_id] = link_counts.get(link.candidate_id, 0) + 1
    links = {
        link.candidate_id: link
        for link in reviewed_links
        if link_counts[link.candidate_id] == 1
    }
    milestone_rows: list[MilestoneEvidence] = []
    for candidate in milestones:
        checked = require_independent_milestone(
            candidate, links.get(candidate.candidate_id), project_identities
        )
        if isinstance(checked, InvestmentFailure):
            if checked.check not in _MISSING_MILESTONE:
                return checked
            milestone_rows.append(
                MilestoneEvidence(candidate, None, "missing_evidence", checked.check)
            )
        else:
            milestone_rows.append(checked)
    if observed_investment:
        announcement_sources = {row.source_id for row in retained} | {
            candidate.source_id for candidate in milestones
        }
        for observed in observed_investment:
            check = (
                "announcement_as_observed"
                if observed.evidence_kind in ("announcement", "milestone")
                or observed.source_id in announcement_sources
                else "closure_without_evidence"
            )
            return InvestmentFailure(
                1,
                observed.source_id,
                "",
                check,
                "separately archived observed-investment evidence",
                observed.evidence_kind,
            )
    return ProjectEvidence(retained, tuple(milestone_rows), (), tuple(absences))


def audit_project_evidence(
    expected: tuple[ExpectedInput, ...],
    evidence: ProjectEvidence,
    attempts: tuple[FetchAttempt, ...],
    *,
    snapshots: tuple[ProjectSnapshot, ...] = (),
    archives: tuple[VerifiedArchive, ...] = (),
) -> EvidenceAudit | InvestmentFailure:
    """Project every retained row, absence and fetch outcome into the S2 audit."""
    attempt_by_key: dict[tuple[str, str], FetchAttempt] = {}
    for attempt in attempts:
        key = (attempt.source_id, attempt.key)
        if key in attempt_by_key:
            return _audit_failure(attempt.source_id, "duplicate fetch attempt")
        attempt_by_key[key] = attempt
    verified_archives = _audit_archives(snapshots, archives, evidence.milestones)
    if isinstance(verified_archives, InvestmentFailure):
        return verified_archives
    canonical_snapshots = _audit_project_snapshots(verified_archives, snapshots)
    if isinstance(canonical_snapshots, InvestmentFailure):
        return canonical_snapshots
    canonical_projects = build_project_evidence(canonical_snapshots)
    if isinstance(canonical_projects, InvestmentFailure):
        return canonical_projects
    if (
        evidence.revisions != canonical_projects.revisions
        or evidence.absences != canonical_projects.absences
    ):
        return _audit_failure("", "revision or absence projection differs")
    canonical_candidates = _audit_milestone_candidates(verified_archives)
    if isinstance(canonical_candidates, InvestmentFailure):
        return canonical_candidates
    expected_milestones = sorted(
        (row.snapshot_identity, row.candidate_id) for row in canonical_candidates
    )
    retained_milestones = sorted(
        (row.candidate.snapshot_identity, row.candidate.candidate_id)
        for row in evidence.milestones
    )
    if expected_milestones != retained_milestones:
        return _audit_failure("", "milestone projection differs")
    for row in evidence.milestones:
        canonical = next(
            candidate
            for candidate in canonical_candidates
            if candidate.candidate_id == row.candidate.candidate_id
            and candidate.snapshot_identity == row.candidate.snapshot_identity
        )
        if replace(row.candidate, snapshot=None) != replace(canonical, snapshot=None):
            return _audit_failure("", "milestone parser output differs")

    entries: list[EvidenceAuditEntry] = []
    ordered_snapshots = canonical_snapshots
    for item in ordered_snapshots:
        for revision in evidence.revisions:
            if revision.snapshot_identity == item.identity:
                entries.append(_revision_entry(revision))
        for absence in evidence.absences:
            if absence.snapshot_identity == item.identity:
                entries.append(
                    EvidenceAuditEntry(
                        absence.source_id,
                        absence.source_id,
                        absence.project_identity,
                        absence.snapshot_identity,
                        PROVENANCE_PUBLIC,
                        "missing_evidence",
                        "absent_from_snapshot",
                        absence.reason,
                    )
                )
    if not ordered_snapshots:
        entries.extend(_revision_entry(revision) for revision in evidence.revisions)
        entries.extend(
            EvidenceAuditEntry(
                absence.source_id,
                absence.source_id,
                absence.project_identity,
                absence.snapshot_identity,
                PROVENANCE_PUBLIC,
                "missing_evidence",
                "absent_from_snapshot",
                absence.reason,
            )
            for absence in evidence.absences
        )
    for milestone in evidence.milestones:
        candidate = milestone.candidate
        validated = (
            milestone.evidence_status == "validated"
            and candidate.independence == "independent_report"
        )
        reason = milestone.missing_reason
        if (
            not validated
            and not reason
            and candidate.independence != "independent_report"
        ):
            reason = "milestone_not_independent"
        entries.append(
            EvidenceAuditEntry(
                candidate.source_id,
                candidate.source_id,
                candidate.candidate_id,
                candidate.snapshot_identity,
                PROVENANCE_PUBLIC,
                "observed_independent_milestone" if validated else "missing_evidence",
                "independent_milestone" if validated else "unvalidated_milestone",
                reason,
            )
        )

    for registration in expected:
        current_attempt = attempt_by_key.get((registration.source_id, registration.key))
        if current_attempt is None:
            entries.append(_attempt_entry(registration, None))
            continue
        if current_attempt.closure_claimed and current_attempt.status != "success":
            return InvestmentFailure(
                1,
                registration.source_id,
                "",
                "closure_without_evidence",
                "no closure from failed or unattempted input",
                current_attempt.status,
            )
        if current_attempt.status in ("failed", "unattempted"):
            entries.append(_attempt_entry(registration, current_attempt))
            continue
        if current_attempt.status != "success" or not isinstance(
            current_attempt.snapshot_identity, str
        ):
            return _audit_failure(registration.source_id, "invalid fetch outcome")
        identity = current_attempt.snapshot_identity
        if _HASH.fullmatch(identity) is None:
            return _audit_failure(registration.source_id, "success has no archive hash")
        if registration.kind not in ("project", "milestone"):
            return _audit_failure(registration.source_id, "unknown registration kind")
        archived = any(
            _archive_matches(registration, identity, archive)
            for archive in verified_archives
        )
        if not archived:
            return _audit_failure(
                registration.source_id, "registered input has no archived evidence"
            )
    return EvidenceAudit(tuple(entries))


def _audit_archives(
    snapshots: tuple[ProjectSnapshot, ...],
    archives: tuple[VerifiedArchive, ...],
    milestones: tuple[MilestoneEvidence, ...],
) -> tuple[VerifiedArchive, ...] | InvestmentFailure:
    """Reread every audit input and deduplicate only identical archive selections."""
    selected_archives: dict[tuple[str, str, str], VerifiedArchive] = {}

    def add(archive: VerifiedArchive) -> InvestmentFailure | None:
        if archive.kind not in ("project", "milestone"):
            return _audit_failure(archive.source_id, "unknown archive kind")
        selected = _reread_snapshot(archive.snapshot, archive.identity)
        if (
            selected.sidecar.get("source_id") != archive.source_id
            or selected.sidecar.get("key") != archive.key
        ):
            return _audit_failure(archive.source_id, "archive metadata differs")
        verified = replace(archive, snapshot=selected)
        selection = (archive.kind, archive.key, archive.identity)
        previous = selected_archives.get(selection)
        if previous is not None and previous != verified:
            return _audit_failure(archive.source_id, "conflicting archive selection")
        selected_archives[selection] = verified
        return None

    for archive in archives:
        failure = add(archive)
        if failure is not None:
            return failure
    for item in snapshots:
        selected = _reread_snapshot(item.snapshot, item.identity)
        failure = add(
            VerifiedArchive(
                str(selected.sidecar.get("source_id", "")),
                str(selected.sidecar.get("key", "")),
                "project",
                item.identity,
                selected,
            )
        )
        if failure is not None:
            return failure
    for row in milestones:
        candidate = row.candidate
        if candidate.snapshot is None:
            continue
        selected = _reread_snapshot(candidate.snapshot, candidate.snapshot_identity)
        failure = add(
            VerifiedArchive(
                candidate.source_id,
                str(selected.sidecar.get("key", "")),
                "milestone",
                candidate.snapshot_identity,
                selected,
                milestone_shape=candidate.shape,
            )
        )
        if failure is not None:
            return failure
    return tuple(selected_archives.values())


def _audit_project_snapshots(
    archives: tuple[VerifiedArchive, ...],
    supplied: tuple[ProjectSnapshot, ...],
) -> tuple[ProjectSnapshot, ...] | InvestmentFailure:
    """Derive expected revisions and absences from verified dashboard bytes."""
    coverage: dict[str, Mapping[str, object]] = {}
    for item in supplied:
        coverage.setdefault(item.identity, item.coverage)
    parsed_snapshots: list[ProjectSnapshot] = []
    for archive in archives:
        if archive.kind != "project":
            continue
        parsed = _parse_project_snapshot(
            archive.snapshot, coverage=coverage.get(archive.identity, {})
        )
        if isinstance(parsed, InvestmentFailure):
            return parsed
        parsed_snapshots.append(parsed)
    return tuple(parsed_snapshots)


def _audit_milestone_candidates(
    archives: tuple[VerifiedArchive, ...],
) -> tuple[MilestoneCandidate, ...] | InvestmentFailure:
    """Derive expected candidates, including a genuinely empty milestone page."""
    candidates: list[MilestoneCandidate] = []
    for archive in archives:
        if archive.kind != "milestone":
            continue
        if archive.milestone_shape is None:
            return _audit_failure(archive.source_id, "milestone parser shape absent")
        envelope = _snapshot_envelope(
            archive.snapshot, _MILESTONE_METHOD, PARSER_VERSION
        )
        parsed = parse_milestone_page(
            archive.snapshot.body, archive.milestone_shape, envelope
        )
        if isinstance(parsed, InvestmentFailure):
            return parsed
        candidates.extend(replace(row, snapshot=archive.snapshot) for row in parsed)
    return tuple(candidates)


def _archive_matches(
    registration: ExpectedInput, identity: str, archive: VerifiedArchive
) -> bool:
    snapshot = archive.snapshot
    return (
        archive.source_id == registration.source_id
        and archive.key == registration.key
        and archive.kind == registration.kind
        and archive.identity == identity
        and snapshot.sha256 == identity
        and snapshot.receipt_path.name == f"{identity}.meta.json"
        and snapshot.sidecar.get("source_id") == registration.source_id
        and snapshot.sidecar.get("key") == registration.key
    )


def archive_evidence_audit(
    cache: Path,
    audit: EvidenceAudit,
    *,
    sidecar: Mapping[str, object],
    retrieved_utc: str,
) -> Snapshot:
    """Archive audit attempts below evidence/, never as raw-source check events."""
    key = sidecar.get("key")
    if not isinstance(key, str) or not key:
        raise ValueError("evidence_audit_incomplete")
    document = {
        "schema_version": "project_evidence_audit.v1",
        "entries": [
            {
                "source_id": entry.source_id,
                "key": entry.key,
                "subject_id": entry.subject_id,
                "revision_identity": entry.revision_identity,
                "provenance": entry.provenance,
                "evidence_status": entry.evidence_status,
                "coverage": entry.coverage,
                "reason": entry.reason,
            }
            for entry in audit.entries
        ],
    }
    body = (json.dumps(document, sort_keys=True, ensure_ascii=True) + "\n").encode()
    side = dict(sidecar)
    for name in (
        "sha256",
        "bytes",
        "identity",
        "extension",
        "path",
        "receipt",
        "receipt_sha256",
        "body_date",
    ):
        side.pop(name, None)
    side["retrieved_utc"] = retrieved_utc
    return publish_snapshot(cache / key / "evidence", "json", body, side)


def archive_fetch_attempts(
    cache: Path,
    expected: tuple[ExpectedInput, ...],
    attempts: tuple[FetchAttempt, ...],
    *,
    sidecars: Mapping[str, Mapping[str, object]],
    retrieved_utc: str,
) -> EvidenceAudit | InvestmentFailure:
    """Verify successful raw archives and retain all fail-fast attempt outcomes."""
    by_key: dict[tuple[str, str], FetchAttempt] = {}
    for candidate_attempt in attempts:
        key = (candidate_attempt.source_id, candidate_attempt.key)
        if key in by_key:
            return _audit_failure(
                candidate_attempt.source_id, "duplicate fetch attempt"
            )
        by_key[key] = candidate_attempt
    entries: list[EvidenceAuditEntry] = []
    for registration in expected:
        attempt = by_key.get((registration.source_id, registration.key))
        if attempt is None:
            entries.append(_attempt_entry(registration, None))
            continue
        if attempt.closure_claimed and attempt.status != "success":
            return InvestmentFailure(
                1,
                registration.source_id,
                "",
                "closure_without_evidence",
                "no closure from failed or unattempted input",
                attempt.status,
            )
        if attempt.status in ("failed", "unattempted"):
            entries.append(_attempt_entry(registration, attempt))
            continue
        identity = attempt.snapshot_identity
        if (
            attempt.status != "success"
            or not isinstance(identity, str)
            or _HASH.fullmatch(identity) is None
        ):
            return _audit_failure(registration.source_id, "invalid fetch outcome")
        snapshot = read_snapshot(cache / registration.key, identity)
        if (
            snapshot.sha256 != identity
            or snapshot.sidecar.get("source_id") != registration.source_id
            or snapshot.sidecar.get("key") != registration.key
        ):
            return _audit_failure(
                registration.source_id, "archive registration metadata differs"
            )
        entries.append(
            EvidenceAuditEntry(
                registration.source_id,
                registration.key,
                "",
                identity,
                PROVENANCE_PUBLIC,
                "observed_announcement",
                "fetch_outcome",
                "",
            )
        )
    audit = EvidenceAudit(tuple(entries))
    for registration in expected:
        sidecar = sidecars.get(registration.key)
        if sidecar is None:
            return _audit_failure(registration.source_id, "attempt lineage absent")
        archived = archive_evidence_audit(
            cache / "audit",
            audit,
            sidecar=sidecar,
            retrieved_utc=retrieved_utc,
        )
        _ = archived.body
    return audit


def _row_observation(row: Mapping[str, object]) -> SourceAssertion:
    value = row.get("announced")
    if not isinstance(value, str) or parse_announced(value) != value:
        return _UNKNOWN_ASSERTION
    precision = {4: "year", 7: "month", 10: "day"}[len(value)]
    return SourceAssertion(value, precision, "")


def _revision_entry(revision: ProjectRevision) -> EvidenceAuditEntry:
    return EvidenceAuditEntry(
        revision.source_id,
        revision.source_id,
        revision.project_identity,
        revision.snapshot_identity,
        PROVENANCE_PUBLIC,
        "observed_announcement",
        "retained_revision",
        "",
    )


def _attempt_entry(
    registration: ExpectedInput, attempt: FetchAttempt | None
) -> EvidenceAuditEntry:
    status = "unattempted" if attempt is None else attempt.status
    reason = "not_attempted_after_fail_fast" if attempt is None else attempt.reason
    if reason == "snapshot_selection_missing":
        status = "missing_evidence"
    return EvidenceAuditEntry(
        registration.source_id,
        registration.key,
        "",
        "",
        PROVENANCE_PUBLIC,
        status,
        "fetch_outcome",
        reason,
    )


def _audit_failure(source_id: str, observed: str) -> InvestmentFailure:
    return InvestmentFailure(
        1,
        source_id,
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        observed,
    )


def parse_milestone_page(
    body: bytes, shape: MilestoneShape, envelope: SourceEnvelope
) -> tuple[MilestoneCandidate, ...] | InvestmentFailure:
    """Parse a confirmed closed shape into unvalidated, archived-page candidates."""
    if not shape.confirmed or not shape.shape_id or not shape.fields:
        return _parser_failure(
            envelope, "unconfirmed", "confirmed shape", "unconfirmed"
        )
    missing = envelope.missing()
    if missing:
        check = "missing_terms" if missing.startswith("terms") else "missing_lineage"
        return _parser_failure(envelope, check, missing, "absent")
    try:
        loaded: object = json.loads(body)
    except (UnicodeDecodeError, ValueError):
        return _parser_failure(envelope, "shape_mismatch", "JSON milestones", "invalid")
    if not isinstance(loaded, dict) or set(loaded) != {"milestones"}:
        return _parser_failure(
            envelope, "shape_mismatch", "milestones object", "invalid"
        )
    rows = loaded["milestones"]
    if not isinstance(rows, list):
        return _parser_failure(
            envelope, "shape_mismatch", "milestones array", "invalid"
        )
    candidates: list[MilestoneCandidate] = []
    for row in rows:
        if not isinstance(row, dict):
            return _parser_failure(
                envelope, "shape_mismatch", "milestone object", "invalid"
            )
        unknown = set(row) - shape.fields
        if unknown:
            return _parser_failure(
                envelope, "unknown_field", "declared fields", sorted(unknown)[0]
            )
        if set(row) != shape.fields:
            return _parser_failure(envelope, "shape_mismatch", "all fields", "missing")
        assertions: dict[str, SourceAssertion] = {}
        for name in ("observation", "publication", "correction"):
            assertion = _read_assertion(row[name])
            if assertion is None or not _valid_assertion(
                assertion, correction=name == "correction"
            ):
                return _parser_failure(
                    envelope, "invalid_evidence_metadata", name, "invalid"
                )
            assertions[name] = assertion
        strings = {
            name: row[name]
            for name in ("milestone_id", "status", "geography", "independence")
        }
        if any(not isinstance(value, str) or not value for value in strings.values()):
            return _parser_failure(envelope, "shape_mismatch", "source text", "invalid")
        if strings["independence"] not in _INDEPENDENCE:
            return _parser_failure(
                envelope, "shape_mismatch", "known independence claim", "invalid"
            )
        project_source = row["project_source_id"]
        published_id = row["project_id"]
        if project_source is not None and not isinstance(project_source, str):
            return _parser_failure(
                envelope, "shape_mismatch", "project source ID", "invalid"
            )
        if published_id is not None and not isinstance(published_id, str):
            return _parser_failure(envelope, "shape_mismatch", "project ID", "invalid")
        milestone_id = str(strings["milestone_id"])
        source_chain = {
            name: getattr(envelope, name)
            for name in (*LINEAGE_FIELDS, "terms_url", "method", "method_version")
        }
        candidates.append(
            MilestoneCandidate(
                candidate_id=f"{envelope.source_id}:milestone:{milestone_id}",
                source_id=envelope.source_id,
                milestone_id=milestone_id,
                project_source_id=project_source,
                published_project_id=published_id,
                status=str(strings["status"]),
                snapshot_identity=envelope.page_sha256,
                checksum=envelope.page_sha256,
                retrieved_utc=envelope.retrieved_utc,
                schema=shape.shape_id,
                geography=str(strings["geography"]),
                observation=assertions["observation"],
                publication=assertions["publication"],
                correction=assertions["correction"],
                independence=str(strings["independence"]),
                source_chain=source_chain,
                shape=shape,
            )
        )
    return tuple(candidates)


def require_independent_milestone(
    candidate: MilestoneCandidate,
    link: ReviewedMilestoneLink | None,
    project_identities: frozenset[str],
) -> MilestoneEvidence | InvestmentFailure:
    """Validate only parser-derived rows and reviewed archived link evidence."""
    if candidate.snapshot is None:
        return _candidate_failure(
            candidate, "missing_artifact", "archived milestone", "missing"
        )
    snapshot = _reread_snapshot(candidate.snapshot, candidate.snapshot_identity)
    _ = snapshot.body
    for name in (*LINEAGE_FIELDS, "terms_url", "method", "method_version"):
        value = candidate.source_chain.get(name)
        if not isinstance(value, str) or not value:
            check = "missing_terms" if name.startswith("terms") else "missing_lineage"
            return _candidate_failure(candidate, check, name, "absent")
    if candidate.source_chain.get("provenance", PROVENANCE_PUBLIC) != PROVENANCE_PUBLIC:
        return _candidate_failure(
            candidate, "provenance", PROVENANCE_PUBLIC, "not Public"
        )
    if candidate.source_chain.get("join_key") not in (None, ""):
        return _candidate_failure(candidate, "prohibited_join", "no join", "joined")
    if (
        snapshot.receipt_path.name != f"{candidate.snapshot_identity}.meta.json"
        or snapshot.sha256 != candidate.checksum
        or snapshot.sha256 != candidate.snapshot_identity
        or snapshot.sidecar.get("source_id") != candidate.source_id
        or snapshot.sidecar.get("retrieved_utc") != candidate.retrieved_utc
    ):
        return _candidate_failure(
            candidate, "invalid_evidence_metadata", "archived identity", "mismatch"
        )
    receipt_lineage = _receipt_lineage(snapshot, _MILESTONE_METHOD, PARSER_VERSION)
    if any(
        candidate.source_chain.get(name) != value
        for name, value in receipt_lineage.items()
    ):
        return _candidate_failure(
            candidate, "invalid_evidence_metadata", "receipt lineage", "mismatch"
        )
    if (
        candidate.status == "completed"
        or candidate.completion is not None
        or candidate.observed_investment is not None
    ):
        return _candidate_failure(
            candidate,
            "unsupported_milestone",
            "reported milestone only",
            "completion or investment inference",
        )
    if candidate.shape is None or candidate.shape.shape_id != candidate.schema:
        return _candidate_failure(
            candidate, "invalid_evidence_metadata", "confirmed shape", "absent"
        )
    envelope = _snapshot_envelope(snapshot, _MILESTONE_METHOD, PARSER_VERSION)
    parsed = parse_milestone_page(snapshot.body, candidate.shape, envelope)
    if isinstance(parsed, InvestmentFailure):
        return parsed
    matching = [row for row in parsed if row.candidate_id == candidate.candidate_id]
    if (
        len(matching) != 1
        or replace(candidate, snapshot=None, completion=None, observed_investment=None)
        != matching[0]
    ):
        return _candidate_failure(
            candidate, "invalid_evidence_metadata", "archived parser row", "mismatch"
        )
    if any(
        assertion.value is None
        or not _valid_assertion(assertion, correction=name == "correction")
        for name, assertion in (
            ("observation", candidate.observation),
            ("publication", candidate.publication),
            ("correction", candidate.correction),
        )
    ):
        return _candidate_failure(
            candidate,
            "invalid_evidence_metadata",
            "source-stated milestone metadata",
            "unknown",
        )
    if (
        link is None
        or link.candidate_id != candidate.candidate_id
        or not link.reviewed
        or not link.review_reference
    ):
        return _candidate_failure(
            candidate, "project_identity_unresolved", "reviewed project link", "absent"
        )
    if (
        candidate.independence != "independent_report"
        or link.independence != "independent_report"
    ):
        return _candidate_failure(
            candidate, "milestone_not_independent", "independent reporting", "copy"
        )
    direct = ""
    if candidate.project_source_id and candidate.published_project_id:
        direct = (
            f"{candidate.project_source_id}:project:{candidate.published_project_id}"
        )
    if direct:
        linked = link.project_identity == direct
    else:
        linked = _valid_crosswalk(candidate, link)
    if not linked:
        return _candidate_failure(
            candidate,
            "project_identity_unresolved",
            "source-ID/project-ID link or verified crosswalk",
            "mismatch",
        )
    if link.project_identity not in project_identities:
        return _candidate_failure(
            candidate, "project_identity_unresolved", "retained project", "unmatched"
        )
    return MilestoneEvidence(candidate, link.project_identity, "validated", "")


def _receipt_lineage(
    snapshot: Snapshot, method: str, version: str
) -> dict[str, object]:
    snapshot = _reread_snapshot(snapshot, snapshot.sha256)
    side = snapshot.sidecar
    terms_url = side.get("terms_url")
    if not isinstance(terms_url, str) or not terms_url:
        terms_url = _registry_terms_url(side)
    values = {
        "publisher": side.get("publisher"),
        "page_url": side.get("fetch_url"),
        "licence_id": side.get("licence_id"),
        "licence_basis": side.get("licence_basis"),
        "decision_record": side.get("decision_record"),
        "terms_sha256": side.get("terms_sha256"),
        "retrieved_utc": side.get("retrieved_utc"),
        "page_sha256": snapshot.sha256,
        "terms_url": terms_url,
        "method": side.get("method", method),
        "method_version": side.get("method_version", version),
    }
    return values


def _registry_terms_url(sidecar: Mapping[str, object]) -> str:
    """Resolve a missing receipt terms URL only from its exact registry row."""
    from eii_custodian.publicdata.fetch.registry import RegistryError, load_registry

    try:
        entries = tuple(
            entry
            for entry in load_registry()
            if entry.source_id == sidecar.get("source_id")
            and entry.key == sidecar.get("key")
        )
    except RegistryError:
        return ""
    if len(entries) != 1:
        return ""
    entry = entries[0]
    if any(
        sidecar.get(name) != value
        for name, value in (
            ("publisher", entry.publisher),
            ("fetch_url", entry.url),
            ("licence_id", entry.licence_id),
            ("licence_basis", entry.licence_basis),
            ("decision_record", entry.decision_record),
        )
    ):
        return ""
    return entry.terms_url


def _valid_crosswalk(
    candidate: MilestoneCandidate, link: ReviewedMilestoneLink
) -> bool:
    if (
        _HASH.fullmatch(link.crosswalk_sha256) is None
        or link.crosswalk is None
        or not link.crosswalk_key
    ):
        return False
    try:
        root = link.crosswalk.receipt_path.parent.parent
        snapshot = read_snapshot(root, link.crosswalk_sha256)
        if (
            snapshot.receipt_path != link.crosswalk.receipt_path
            or snapshot.sha256 != link.crosswalk_sha256
            or snapshot.sidecar.get("key") != link.crosswalk_key
            or snapshot.sidecar.get("review_reference") != link.review_reference
        ):
            return False
        loaded: object = json.loads(snapshot.body)
    except (OSError, SnapshotError, UnicodeDecodeError, ValueError):
        return False
    if not isinstance(loaded, dict) or set(loaded) != {
        "schema_version",
        "review_reference",
        "mappings",
    }:
        return False
    if (
        loaded["schema_version"] != "reviewed_milestone_crosswalk.v1"
        or loaded["review_reference"] != link.review_reference
        or not isinstance(loaded["mappings"], list)
    ):
        return False
    matches = []
    for row in loaded["mappings"]:
        if not isinstance(row, dict) or set(row) != {
            "candidate_id",
            "project_identity",
            "independence",
        }:
            return False
        if row["candidate_id"] == candidate.candidate_id:
            matches.append(row)
    return len(matches) == 1 and matches[0] == {
        "candidate_id": candidate.candidate_id,
        "project_identity": link.project_identity,
        "independence": "independent_report",
    }


def _read_assertion(value: object) -> SourceAssertion | None:
    if not isinstance(value, dict) or set(value) != {
        "value",
        "precision",
        "absence_reason",
    }:
        return None
    if value["value"] is not None and not isinstance(value["value"], str):
        return None
    if not isinstance(value["precision"], str) or not isinstance(
        value["absence_reason"], str
    ):
        return None
    return SourceAssertion(value["value"], value["precision"], value["absence_reason"])


def _parser_failure(
    envelope: SourceEnvelope, check: str, expected: str, observed: str
) -> InvestmentFailure:
    return InvestmentFailure(
        1, envelope.source_id, envelope.page_url, check, expected, observed
    )


def _candidate_failure(
    candidate: MilestoneCandidate, check: str, expected: str, observed: str
) -> InvestmentFailure:
    url = candidate.source_chain.get("page_url")
    return InvestmentFailure(
        1,
        candidate.source_id,
        url if isinstance(url, str) else "",
        check,
        expected,
        observed,
    )


def _metadata_failure(item: ProjectSnapshot) -> Snapshot | InvestmentFailure:
    """Return the verified snapshot, refusing conflicting receipt metadata."""
    snapshot = _reread_snapshot(item.snapshot, item.identity)
    side = snapshot.sidecar
    _ = snapshot.body
    if any(item.snapshot.sidecar.get(name) != value for name, value in side.items()):
        return _snapshot_failure(
            snapshot, "supplied receipt metadata", "differs from verified receipt"
        )
    if (
        snapshot.receipt_path.name != f"{item.identity}.meta.json"
        or snapshot.sha256 != item.identity
        or item.schema != SCHEMA_FDI
    ):
        return _refusal(
            item, "invalid_evidence_metadata", "selected snapshot identity", "mismatch"
        )
    for name, assertion in (
        ("observation", item.observation),
        ("publication", item.publication),
        ("correction", item.correction),
    ):
        if not _valid_assertion(assertion, correction=name == "correction"):
            return _refusal(
                item,
                "invalid_evidence_metadata",
                "source assertion or explicit absence",
                "invalid",
            )
    receipt_lineage = _receipt_lineage(snapshot, FDI_METHOD, PARSER_VERSION)
    for row in item.rows:
        for name in LINEAGE_FIELDS:
            value = row.get(name)
            if not isinstance(value, str) or not value:
                check = "missing_terms" if name == "terms_sha256" else "missing_lineage"
                return _refusal(item, check, name, "absent")
        for name in ("method", "method_version"):
            if not isinstance(row.get(name), str) or not row[name]:
                return _refusal(item, "missing_lineage", name, "absent")
        if not isinstance(side.get("terms_url"), str) or not side["terms_url"]:
            return _refusal(item, "missing_terms", "terms_url", "absent")
        if row.get("provenance") != PROVENANCE_PUBLIC:
            return _refusal(item, "provenance", PROVENANCE_PUBLIC, "not Public")
        if row.get("join_key") not in (None, ""):
            return _refusal(item, "prohibited_join", "no join", "joined")
        if (
            row.get("source_id") != side.get("source_id")
            or any(row.get(name) != value for name, value in receipt_lineage.items())
            or not row.get("project_key")
            or not row.get("project_id")
        ):
            return _refusal(
                item,
                "invalid_evidence_metadata",
                "matching source metadata",
                "mismatch",
            )
    canonical = _parse_project_snapshot(snapshot, coverage=item.coverage)
    if isinstance(canonical, InvestmentFailure):
        return canonical
    if (
        item.rows != canonical.rows
        or item.observation != _UNKNOWN_ASSERTION
        or item.publication != _UNKNOWN_ASSERTION
        or item.correction != _UNKNOWN_ASSERTION
        or item.coverage != canonical.coverage
    ):
        return _refusal(
            item, "invalid_evidence_metadata", "archived parser output", "mismatch"
        )
    return snapshot


def _valid_assertion(assertion: SourceAssertion, *, correction: bool = False) -> bool:
    if assertion.value is None:
        return assertion.precision == "" and bool(assertion.absence_reason)
    if assertion.absence_reason or not assertion.value:
        return False
    if correction:
        return assertion.precision == "source_flag" and assertion.value in (
            "true",
            "false",
        )
    if assertion.precision not in ("year", "month", "day"):
        return False
    if parse_announced(assertion.value) != assertion.value:
        return False
    granularity = {4: "year", 7: "month", 10: "day"}.get(len(assertion.value))
    return granularity == assertion.precision


def _refusal(
    item: ProjectSnapshot, check: str, expected: str, observed: str
) -> InvestmentFailure:
    source = item.snapshot.sidecar.get("source_id")
    url = item.snapshot.sidecar.get("fetch_url")
    return InvestmentFailure(
        1,
        source if isinstance(source, str) else "",
        url if isinstance(url, str) else "",
        check,
        expected,
        observed,
    )
