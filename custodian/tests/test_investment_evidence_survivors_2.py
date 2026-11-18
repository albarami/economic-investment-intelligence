"""Mutation survivors: closed milestone parsing and independent-evidence checks."""

from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.test_investment_evidence_survivors import (
    METHOD,
    PROJECT,
    PROJECT_IDENTITY,
    SOURCE,
    TERMS,
    UNKNOWN,
    URL,
    candidate,
    envelope,
    failure,
    milestone_body,
    milestone_row,
    project,
    shape,
)

import eii_custodian.publicdata.investment_evidence as evidence
from eii_custodian.publicdata.investment_contracts import (
    EvidenceAudit,
    EvidenceAuditEntry,
    ExpectedInput,
    FetchAttempt,
    ProjectEvidence,
    SourceAssertion,
    VerifiedArchive,
)


def wrong(value: Any) -> Any:
    """Pass a deliberately wrong JSON type without a suppression comment."""
    return value


def page_envelope(body: bytes) -> evidence.SourceEnvelope:
    return replace(envelope(), page_sha256=sha256(body).hexdigest())


def test_archive_validation_refusals_are_exact(tmp_path: Path) -> None:
    item = project(tmp_path)
    built = evidence.build_project_evidence((item,))
    assert isinstance(built, ProjectEvidence)
    archive = VerifiedArchive(PROJECT, PROJECT, "project", item.identity, item.snapshot)
    for planted, observed in [
        (replace(archive, kind="invented"), "unknown archive kind"),
        (replace(archive, source_id="invented_other"), "archive metadata differs"),
        (replace(archive, key="invented_other"), "archive metadata differs"),
    ]:
        assert evidence.audit_project_evidence(
            (), built, (), archives=(planted,)
        ) == failure(
            planted.source_id,
            "",
            "evidence_audit_incomplete",
            "every registration, revision and absence",
            observed,
        )
    row = candidate(tmp_path)
    milestone = VerifiedArchive(
        SOURCE, SOURCE, "milestone", row.snapshot_identity, row.snapshot, shape()
    )
    conflict = replace(
        milestone, milestone_shape=replace(shape(), shape_id="invented-other")
    )
    assert evidence.audit_project_evidence(
        (), ProjectEvidence(()), (), archives=(milestone, conflict)
    ) == failure(
        SOURCE,
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "conflicting archive selection",
    )
    assert evidence.audit_project_evidence(
        (),
        ProjectEvidence(()),
        (),
        archives=(replace(milestone, milestone_shape=None),),
    ) == failure(
        SOURCE,
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "milestone parser shape absent",
    )


def test_audit_project_snapshots_keep_selected_coverage(tmp_path: Path) -> None:
    item = project(tmp_path, coverage={"scope": "invented_selected_history"})
    archive = VerifiedArchive(PROJECT, PROJECT, "project", item.identity, item.snapshot)
    result = evidence._audit_project_snapshots((archive,), (item,))
    assert isinstance(result, tuple)
    assert result[0].coverage == {"scope": "invented_selected_history"}


def test_snapshotless_milestone_cannot_satisfy_audit(tmp_path: Path) -> None:
    row = replace(candidate(tmp_path), snapshot=None)
    built = ProjectEvidence(
        (),
        milestones=(
            evidence.MilestoneEvidence(
                row, None, "missing_evidence", "missing_artifact"
            ),
        ),
    )
    assert evidence.audit_project_evidence((), built, ()) == failure(
        "",
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "milestone projection differs",
    )


def test_archive_evidence_audit_writes_exact_document(tmp_path: Path) -> None:
    entry = EvidenceAuditEntry(
        PROJECT,
        PROJECT,
        "invented-café",
        "cd" * 32,
        "public",
        "observed_announcement",
        "retained_revision",
        "",
    )
    audit = EvidenceAudit((entry,))
    side = {
        name: "invented-remove"
        for name in (
            "sha256",
            "bytes",
            "identity",
            "extension",
            "path",
            "receipt",
            "receipt_sha256",
            "body_date",
        )
    }
    side.update(
        {
            "source_id": PROJECT,
            "key": PROJECT,
            "invented_keep": "kept",
            "retrieved_utc": "invented-old",
        }
    )
    archived = evidence.archive_evidence_audit(
        tmp_path / "cache", audit, sidecar=side, retrieved_utc="2026-11-16T08:00:00Z"
    )
    expected = {
        "schema_version": "project_evidence_audit.v1",
        "entries": [
            {
                "source_id": PROJECT,
                "key": PROJECT,
                "subject_id": "invented-café",
                "revision_identity": "cd" * 32,
                "provenance": "public",
                "evidence_status": "observed_announcement",
                "coverage": "retained_revision",
                "reason": "",
            }
        ],
    }
    assert (
        archived.body
        == (json.dumps(expected, sort_keys=True, ensure_ascii=True) + "\n").encode()
    )
    assert archived.sidecar["invented_keep"] == "kept"
    assert archived.sidecar["retrieved_utc"] == "2026-11-16T08:00:00Z"
    assert all(
        name not in archived.sidecar
        for name in (
            "identity",
            "body_date",
            "extension",
            "path",
            "receipt",
            "receipt_sha256",
        )
    )
    for key in ("", 3):
        with pytest.raises(ValueError, match=r"^evidence_audit_incomplete$"):
            evidence.archive_evidence_audit(
                tmp_path / "cache",
                audit,
                sidecar={"key": key},
                retrieved_utc="2026-11-16T08:00:00Z",
            )


def test_archive_fetch_attempts_is_exact(tmp_path: Path) -> None:
    item = project(tmp_path)
    registration = ExpectedInput(PROJECT, PROJECT, "project")
    success = FetchAttempt(PROJECT, PROJECT, "success", item.identity, "")
    sidecar = {PROJECT: item.snapshot.sidecar}
    result = evidence.archive_fetch_attempts(
        tmp_path / "cache",
        (registration,),
        (success,),
        sidecars=sidecar,
        retrieved_utc="2026-11-16T08:00:00Z",
    )
    assert result == EvidenceAudit(
        (
            EvidenceAuditEntry(
                PROJECT,
                PROJECT,
                "",
                item.identity,
                "public",
                "observed_announcement",
                "fetch_outcome",
                "",
            ),
        )
    )
    assert evidence.archive_fetch_attempts(
        tmp_path / "cache",
        (registration,),
        (success,),
        sidecars={},
        retrieved_utc="2026-11-16T08:00:00Z",
    ) == failure(
        PROJECT,
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "attempt lineage absent",
    )
    closure = replace(
        success, status="failed", snapshot_identity=None, closure_claimed=True
    )
    assert evidence.archive_fetch_attempts(
        tmp_path / "cache",
        (registration,),
        (closure,),
        sidecars=sidecar,
        retrieved_utc="2026-11-16T08:00:00Z",
    ) == failure(
        PROJECT,
        "",
        "closure_without_evidence",
        "no closure from failed or unattempted input",
        "failed",
    )
    for planted in (
        replace(success, status="invented"),
        replace(success, snapshot_identity="bad"),
        replace(success, snapshot_identity=wrong(3)),
    ):
        assert evidence.archive_fetch_attempts(
            tmp_path / "cache",
            (registration,),
            (planted,),
            sidecars=sidecar,
            retrieved_utc="2026-11-16T08:00:00Z",
        ) == failure(
            PROJECT,
            "",
            "evidence_audit_incomplete",
            "every registration, revision and absence",
            "invalid fetch outcome",
        )


def test_small_audit_projection_helpers_are_exact(tmp_path: Path) -> None:
    item = project(tmp_path)
    built = evidence.build_project_evidence((item,))
    assert isinstance(built, ProjectEvidence)
    revision = built.revisions[0]
    assert evidence._revision_entry(revision) == EvidenceAuditEntry(
        PROJECT,
        PROJECT,
        PROJECT_IDENTITY,
        item.identity,
        "public",
        "observed_announcement",
        "retained_revision",
        "",
    )
    registration = ExpectedInput(PROJECT, PROJECT, "project")
    missing = FetchAttempt(
        PROJECT, PROJECT, "unattempted", None, "snapshot_selection_missing"
    )
    assert evidence._attempt_entry(registration, missing) == EvidenceAuditEntry(
        PROJECT,
        PROJECT,
        "",
        "",
        "public",
        "missing_evidence",
        "fetch_outcome",
        "snapshot_selection_missing",
    )
    assert evidence._attempt_entry(registration, None) == EvidenceAuditEntry(
        PROJECT,
        PROJECT,
        "",
        "",
        "public",
        "unattempted",
        "fetch_outcome",
        "not_attempted_after_fail_fast",
    )
    failed = FetchAttempt(PROJECT, PROJECT, "failed", None, "invented_failure")
    assert evidence._attempt_entry(registration, failed) == EvidenceAuditEntry(
        PROJECT,
        PROJECT,
        "",
        "",
        "public",
        "failed",
        "fetch_outcome",
        "invented_failure",
    )
    assert evidence._row_observation({"announced": "2026-11"}) == SourceAssertion(
        "2026-11", "month", ""
    )
    assert evidence._row_observation({"announced": "2026-11-14T08:00:00Z"}) == UNKNOWN


@pytest.mark.parametrize(
    "changed", [{"confirmed": False}, {"shape_id": ""}, {"fields": frozenset()}]
)
def test_parser_requires_a_complete_confirmed_shape(changed: dict[str, object]) -> None:
    result = evidence.parse_milestone_page(
        milestone_body(), replace(shape(), **changed), envelope()
    )
    assert result == failure(
        SOURCE, URL, "unconfirmed", "confirmed shape", "unconfirmed"
    )


@pytest.mark.parametrize(
    ("field", "check", "expected"),
    [
        ("publisher", "missing_lineage", "publisher"),
        ("method", "missing_lineage", "method"),
    ],
)
def test_parser_lineage_refusals_are_exact(
    field: str, check: str, expected: str
) -> None:
    result = evidence.parse_milestone_page(
        milestone_body(), shape(), replace(envelope(), **{field: ""})
    )
    assert result == failure(SOURCE, URL, check, expected, "absent")


def test_parser_records_a_pending_terms_reading_without_refusing() -> None:
    """Ruling L-1001 (S2-T30): an empty terms field is a pending reading that
    fails nothing and is carried truthfully into every candidate's chain."""
    for field in ("terms_sha256", "terms_url"):
        result = evidence.parse_milestone_page(
            milestone_body(), shape(), replace(envelope(), **{field: ""})
        )
        assert not hasattr(result, "check")
        assert result
        assert all(candidate.source_chain[field] == "" for candidate in result)


@pytest.mark.parametrize(
    ("body", "check", "expected", "observed"),
    [
        (b"{", "shape_mismatch", "JSON milestones", "invalid"),
        (b"[]", "shape_mismatch", "milestones object", "invalid"),
        (b'{"other": []}', "shape_mismatch", "milestones object", "invalid"),
        (b'{"milestones": {}}', "shape_mismatch", "milestones array", "invalid"),
        (b'{"milestones": [1]}', "shape_mismatch", "milestone object", "invalid"),
    ],
)
def test_parser_structure_refusals_are_exact(
    body: bytes, check: str, expected: str, observed: str
) -> None:
    assert evidence.parse_milestone_page(body, shape(), page_envelope(body)) == failure(
        SOURCE, URL, check, expected, observed
    )


def test_parser_unknown_missing_and_invalid_fields_are_exact() -> None:
    extra = milestone_row()
    extra["unexpected"] = "invented"
    body = milestone_body([extra])
    result = evidence.parse_milestone_page(body, shape(), page_envelope(body))
    assert result == failure(
        SOURCE, URL, "unknown_field", "declared fields", "unexpected"
    )
    missing = milestone_row()
    del missing["status"]
    body = milestone_body([missing])
    result = evidence.parse_milestone_page(body, shape(), page_envelope(body))
    assert result == failure(SOURCE, URL, "shape_mismatch", "all fields", "missing")
    cases = [
        (
            "observation",
            {"value": 3, "precision": "day", "absence_reason": ""},
            "invalid_evidence_metadata",
            "observation",
        ),
        (
            "observation",
            {"value": "2026-11-13", "precision": "month", "absence_reason": ""},
            "invalid_evidence_metadata",
            "observation",
        ),
        ("status", "", "shape_mismatch", "source text"),
        ("milestone_id", 3, "shape_mismatch", "source text"),
        ("geography", None, "shape_mismatch", "source text"),
        ("independence", "invented", "shape_mismatch", "known independence claim"),
        ("project_source_id", 3, "shape_mismatch", "project source ID"),
        ("project_id", 3, "shape_mismatch", "project ID"),
    ]
    for field, value, check, expected in cases:
        row = milestone_row()
        row[field] = wrong(value)
        body = milestone_body([row])
        result = evidence.parse_milestone_page(body, shape(), page_envelope(body))
        assert result == failure(SOURCE, URL, check, expected, "invalid")


def test_parser_candidate_is_complete() -> None:
    body = milestone_body()
    digest = sha256(body).hexdigest()
    base = replace(envelope(), page_sha256=digest)
    result = evidence.parse_milestone_page(body, shape(), base)
    assert isinstance(result, tuple)
    stated = SourceAssertion("2026-11-13", "day", "")
    correction = SourceAssertion("false", "source_flag", "")
    source_chain = {
        "publisher": base.publisher,
        "page_url": URL,
        "licence_id": base.licence_id,
        "licence_basis": base.licence_basis,
        "decision_record": base.decision_record,
        "terms_sha256": base.terms_sha256,
        "retrieved_utc": base.retrieved_utc,
        "page_sha256": digest,
        "terms_url": TERMS,
        "method": METHOD,
        "method_version": "1",
    }
    expected = evidence.MilestoneCandidate(
        "invented_milestones:milestone:SYN-MILESTONE-independent",
        SOURCE,
        "SYN-MILESTONE-independent",
        PROJECT,
        "1001",
        "construction_started",
        digest,
        digest,
        "2026-11-15T08:00:00Z",
        "SYN-MILESTONE-SHAPE-v1",
        "Invented Bay",
        stated,
        stated,
        correction,
        "independent_report",
        source_chain,
        shape=shape(),
    )
    assert result == (expected,)


def test_read_assertion_requires_its_closed_typed_form() -> None:
    value = {"value": "2026", "precision": "year", "absence_reason": ""}
    assert evidence._read_assertion(value) == SourceAssertion("2026", "year", "")
    invalid = [
        None,
        [],
        {"value": "2026", "precision": "year"},
        {**value, "extra": "invented"},
        {**value, "value": 2026},
        {**value, "precision": 3},
        {**value, "absence_reason": None},
    ]
    for planted in invalid:
        assert evidence._read_assertion(wrong(planted)) is None
