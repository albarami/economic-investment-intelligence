"""Cache-only announced-project revisions and their explicit evidence states."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

from eii_custodian.publicdata.fetch.snapshots import (
    Snapshot,
    publish_snapshot,
    read_snapshot,
)
from eii_custodian.publicdata.investment_contracts import (
    LINEAGE_FIELDS,
    PROVENANCE_PUBLIC,
    EvidenceAudit,
    EvidenceAuditEntry,
    ExpectedInput,
    FetchAttempt,
    InvestmentFailure,
    MilestoneCandidate,
    MilestoneEvidence,
    MilestoneShape,
    ObservedInvestment,
    ProjectAbsence,
    ProjectEvidence,
    ProjectRevision,
    ProjectSnapshot,
    ReviewedMilestoneLink,
    SourceAssertion,
    SourceEnvelope,
    parse_announced,
)

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
        metadata = _metadata_failure(item)
        if metadata is not None:
            return metadata
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
                    observation=item.observation,
                    publication=item.publication,
                    retrieved_utc=str(item.snapshot.sidecar.get("retrieved_utc", "")),
                    checksum=item.snapshot.sha256,
                    schema=item.schema,
                    geography=item.geography,
                    correction=item.correction,
                    announced={
                        "capex": row.get("capex_value"),
                        "jobs": row.get("jobs"),
                        "stated_intent": row.get("stated_intent"),
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
) -> EvidenceAudit | InvestmentFailure:
    """Project every retained row, absence and fetch outcome into the S2 audit."""
    attempt_by_key: dict[tuple[str, str], FetchAttempt] = {}
    for attempt in attempts:
        key = (attempt.source_id, attempt.key)
        if key in attempt_by_key:
            return _audit_failure(attempt.source_id, "duplicate fetch attempt")
        attempt_by_key[key] = attempt
    if snapshots:
        expected_revisions = {
            (
                item.identity,
                f"{row.get('source_id', '')}:project:{row.get('project_id', '')}",
            )
            for item in snapshots
            for row in item.rows
        }
        retained_revisions = {
            (row.snapshot_identity, row.project_identity) for row in evidence.revisions
        }
        expected_absences = _expected_absence_keys(snapshots)
        retained_absences = {
            (row.snapshot_identity, row.project_identity) for row in evidence.absences
        }
        if (
            expected_revisions != retained_revisions
            or expected_absences != retained_absences
        ):
            return _audit_failure("", "revision or absence projection differs")

    entries: list[EvidenceAuditEntry] = []
    ordered_snapshots = snapshots
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
    if not snapshots:
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
        validated = milestone.evidence_status == "validated"
        entries.append(
            EvidenceAuditEntry(
                candidate.source_id,
                candidate.source_id,
                candidate.candidate_id,
                candidate.snapshot_identity,
                PROVENANCE_PUBLIC,
                "observed_independent_milestone" if validated else "missing_evidence",
                "independent_milestone" if validated else "unvalidated_milestone",
                milestone.missing_reason,
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
        if registration.kind == "project":
            archived = any(
                row.snapshot_identity == identity for row in evidence.revisions
            ) or any(row.snapshot_identity == identity for row in evidence.absences)
        elif registration.kind == "milestone":
            archived = any(
                row.candidate.snapshot_identity == identity
                and row.candidate.snapshot is not None
                for row in evidence.milestones
            )
        else:
            return _audit_failure(registration.source_id, "unknown registration kind")
        if not archived:
            return _audit_failure(
                registration.source_id, "registered input has no archived evidence"
            )
    return EvidenceAudit(tuple(entries))


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
    by_key = {(attempt.source_id, attempt.key): attempt for attempt in attempts}
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
        read_snapshot(cache / registration.key, identity)
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


def _expected_absence_keys(
    snapshots: tuple[ProjectSnapshot, ...],
) -> set[tuple[str, str]]:
    expected: set[tuple[str, str]] = set()
    seen: dict[str, set[str]] = {}
    for item in snapshots:
        source = str(item.snapshot.sidecar.get("source_id", ""))
        current = {
            f"{row.get('source_id', '')}:project:{row.get('project_id', '')}"
            for row in item.rows
        }
        previous = seen.setdefault(source, set())
        expected.update((item.identity, identity) for identity in previous - current)
        previous.update(current)
    return expected


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
            )
        )
    return tuple(candidates)


def require_independent_milestone(
    candidate: MilestoneCandidate,
    link: ReviewedMilestoneLink | None,
    project_identities: frozenset[str],
) -> MilestoneEvidence | InvestmentFailure:
    """Validate only a reviewed explicit link to an archived independent page."""
    if candidate.snapshot is None:
        return _candidate_failure(
            candidate, "missing_artifact", "archived milestone", "missing"
        )
    _ = candidate.snapshot.body
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
        candidate.snapshot.receipt_path.name
        != f"{candidate.snapshot_identity}.meta.json"
        or candidate.snapshot.sha256 != candidate.checksum
        or candidate.snapshot.sidecar.get("source_id") != candidate.source_id
        or candidate.snapshot.sidecar.get("retrieved_utc") != candidate.retrieved_utc
    ):
        return _candidate_failure(
            candidate, "invalid_evidence_metadata", "archived identity", "mismatch"
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
    elif not _HASH.fullmatch(link.crosswalk_sha256):
        return _candidate_failure(
            candidate,
            "project_identity_unresolved",
            "reviewed crosswalk receipt",
            "absent",
        )
    if direct and link.project_identity != direct:
        return _candidate_failure(
            candidate,
            "project_identity_unresolved",
            "source-ID/project-ID link",
            "mismatch",
        )
    if link.project_identity not in project_identities:
        return _candidate_failure(
            candidate, "project_identity_unresolved", "retained project", "unmatched"
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
    return MilestoneEvidence(candidate, link.project_identity, "validated", "")


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


def _metadata_failure(item: ProjectSnapshot) -> InvestmentFailure | None:
    side = item.snapshot.sidecar
    _ = item.snapshot.body
    if item.snapshot.receipt_path.name != f"{item.identity}.meta.json":
        return _refusal(
            item, "invalid_evidence_metadata", "selected snapshot identity", "mismatch"
        )
    if not item.schema or not item.geography:
        return _refusal(
            item, "invalid_evidence_metadata", "schema and geography", "absent"
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
            or row.get("retrieved_utc") != side.get("retrieved_utc")
            or row.get("page_sha256") != item.snapshot.sha256
            or row.get("location_text") != item.geography
            or not row.get("project_key")
            or not row.get("project_id")
        ):
            return _refusal(
                item,
                "invalid_evidence_metadata",
                "matching source metadata",
                "mismatch",
            )
    return None


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
    return parse_announced(assertion.value) == assertion.value


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
