"""Mutation survivors: revision, absence and exhaustive audit contracts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.investment_fixtures import invented_record
from custodian.tests.test_investment_evidence_survivors import (
    DASHBOARD_URL,
    PROJECT,
    PROJECT_IDENTITY,
    SOURCE,
    UNKNOWN,
    candidate,
    failure,
    link_for,
    milestone_body,
    milestone_row,
    project,
    shape,
)
from custodian.tests.test_investment_evidence_survivors_2 import wrong

import eii_custodian.publicdata.investment_evidence as evidence
from eii_custodian.publicdata.investment_contracts import (
    EvidenceAudit,
    EvidenceAuditEntry,
    ExpectedInput,
    FetchAttempt,
    ObservedInvestment,
    ProjectAbsence,
    ProjectEvidence,
    SourceAssertion,
    VerifiedArchive,
)


def test_revision_and_absence_projection_is_complete(tmp_path: Path) -> None:
    other = invented_record(
        project_id=1002, investing_company_name="Invented Reed Mill"
    )
    first = project(tmp_path, records=(invented_record(project_id=1001), other))
    second = project(tmp_path, records=(other,), day="2026-11-15")
    result = evidence.build_project_evidence((first, second))
    assert isinstance(result, ProjectEvidence)
    assert len(result.revisions) == 3
    revision = result.revisions[0]
    assert revision.project_identity == PROJECT_IDENTITY
    assert revision.source_id == PROJECT and revision.project_id == "1001"
    assert revision.snapshot_identity == first.identity
    assert revision.project_key == first.rows[0]["project_key"]
    assert revision.observation == SourceAssertion("2024-06-15", "day", "")
    assert revision.publication == UNKNOWN and revision.correction == UNKNOWN
    assert revision.retrieved_utc == "2026-11-14T08:00:00Z"
    assert (
        revision.checksum == first.snapshot.sha256
        and revision.schema == "fdi_projects.v1"
    )
    assert (
        revision.geography == "Invented Bay" and revision.geography_absence_reason == ""
    )
    assert revision.announced == {
        "capex": "12.5",
        "jobs": "40",
        "stated_intent": "Invented café note",
    }
    assert revision.source_chain == dict(first.rows[0])
    assert result.absences == (
        ProjectAbsence(
            PROJECT_IDENTITY, PROJECT, second.identity, "not_present_in_source_snapshot"
        ),
    )
    assert result.observed_investment == ()


def test_duplicate_snapshot_and_project_id_refusals_are_exact(tmp_path: Path) -> None:
    item = project(tmp_path)
    assert evidence.build_project_evidence((item, item)) == failure(
        PROJECT,
        DASHBOARD_URL,
        "revision_overwrite",
        "distinct archived snapshot",
        "duplicate snapshot identity",
    )
    ambiguous = project(
        tmp_path / "ambiguous",
        records=(
            invented_record(project_id=1001),
            invented_record(
                project_id=1001, investing_company_name="Invented Other Works"
            ),
        ),
    )
    assert evidence.build_project_evidence((ambiguous,)) == failure(
        PROJECT,
        DASHBOARD_URL,
        "project_identity_unresolved",
        "one project ID per snapshot",
        "ambiguous project ID",
    )


@pytest.mark.parametrize(
    ("source", "kind", "check"),
    [
        (PROJECT, "measured", "announcement_as_observed"),
        ("invented_observed", "measured", "closure_without_evidence"),
        ("invented_observed", "milestone", "announcement_as_observed"),
    ],
)
def test_observed_investment_boundary_is_exact(
    tmp_path: Path, source: str, kind: str, check: str
) -> None:
    item = project(tmp_path)
    observed = ObservedInvestment(PROJECT_IDENTITY, "12.5", source, kind, item.identity)
    assert evidence.build_project_evidence(
        (item,), observed_investment=(observed,)
    ) == failure(
        source, "", check, "separately archived observed-investment evidence", kind
    )


def test_audit_entries_cover_history_and_milestones_exactly(tmp_path: Path) -> None:
    other = invented_record(
        project_id=1002, investing_company_name="Invented Reed Mill"
    )
    first = project(tmp_path, records=(invented_record(project_id=1001), other))
    second = project(tmp_path, records=(other,), day="2026-11-15")
    valid = candidate(tmp_path)
    missing = candidate(
        tmp_path,
        body=milestone_body(
            [milestone_row(marker="copy", independence="publisher_announcement")]
        ),
    )
    built = evidence.build_project_evidence(
        (first, second), (valid, missing), (link_for(valid), link_for(missing))
    )
    assert isinstance(built, ProjectEvidence)
    result = evidence.audit_project_evidence((), built, (), snapshots=(first, second))
    expected_entries = [
        EvidenceAuditEntry(
            PROJECT,
            PROJECT,
            PROJECT_IDENTITY,
            first.identity,
            "public",
            "observed_announcement",
            "retained_revision",
            "",
        ),
        EvidenceAuditEntry(
            PROJECT,
            PROJECT,
            "fdi_projects:project:1002",
            first.identity,
            "public",
            "observed_announcement",
            "retained_revision",
            "",
        ),
        EvidenceAuditEntry(
            PROJECT,
            PROJECT,
            "fdi_projects:project:1002",
            second.identity,
            "public",
            "observed_announcement",
            "retained_revision",
            "",
        ),
        EvidenceAuditEntry(
            PROJECT,
            PROJECT,
            PROJECT_IDENTITY,
            second.identity,
            "public",
            "missing_evidence",
            "absent_from_snapshot",
            "not_present_in_source_snapshot",
        ),
        EvidenceAuditEntry(
            SOURCE,
            SOURCE,
            valid.candidate_id,
            valid.snapshot_identity,
            "public",
            "observed_independent_milestone",
            "independent_milestone",
            "",
        ),
        EvidenceAuditEntry(
            SOURCE,
            SOURCE,
            missing.candidate_id,
            missing.snapshot_identity,
            "public",
            "missing_evidence",
            "unvalidated_milestone",
            "milestone_not_independent",
        ),
    ]
    assert result == EvidenceAudit(tuple(expected_entries))


def test_audit_projection_refusals_are_exact(tmp_path: Path) -> None:
    item = project(tmp_path)
    built = evidence.build_project_evidence((item,))
    assert isinstance(built, ProjectEvidence)
    omitted = replace(built, revisions=())
    assert evidence.audit_project_evidence(
        (), omitted, (), snapshots=(item,)
    ) == failure(
        "",
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "revision or absence projection differs",
    )
    row = candidate(tmp_path)
    with_milestone = evidence.build_project_evidence((item,), (row,), (link_for(row),))
    assert isinstance(with_milestone, ProjectEvidence)
    without_milestone = replace(with_milestone, milestones=())
    milestone_archive = VerifiedArchive(
        SOURCE, SOURCE, "milestone", row.snapshot_identity, row.snapshot, shape()
    )
    assert evidence.audit_project_evidence(
        (), without_milestone, (), snapshots=(item,), archives=(milestone_archive,)
    ) == failure(
        "",
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "milestone projection differs",
    )
    changed = replace(
        with_milestone.milestones[0], candidate=replace(row, status="invented_changed")
    )
    assert evidence.audit_project_evidence(
        (), replace(with_milestone, milestones=(changed,)), (), snapshots=(item,)
    ) == failure(
        "",
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "milestone parser output differs",
    )


def test_audit_matches_candidates_by_snapshot_and_id(tmp_path: Path) -> None:
    item = project(tmp_path)
    first = candidate(
        tmp_path, body=milestone_body([milestone_row()]), day="2026-11-14"
    )
    second_body = milestone_body([{**milestone_row(), "geography": "Invented Cove"}])
    second = candidate(tmp_path, body=second_body, day="2026-11-15")
    built = evidence.build_project_evidence(
        (item,), (first, second), (link_for(first), link_for(second))
    )
    assert isinstance(built, ProjectEvidence)
    result = evidence.audit_project_evidence((), built, (), snapshots=(item,))
    assert isinstance(result, EvidenceAudit)
    assert len(result.entries) == 3


def test_audit_fetch_refusals_are_exact(tmp_path: Path) -> None:
    item = project(tmp_path)
    built = evidence.build_project_evidence((item,))
    assert isinstance(built, ProjectEvidence)
    registration = ExpectedInput(PROJECT, PROJECT, "project")
    success = FetchAttempt(PROJECT, PROJECT, "success", item.identity, "")
    cases = [
        ((success, success), PROJECT, "duplicate fetch attempt"),
        (
            (
                replace(
                    success,
                    status="failed",
                    snapshot_identity=None,
                    closure_claimed=True,
                ),
            ),
            PROJECT,
            "closure_without_evidence",
        ),
        ((replace(success, status="invented"),), PROJECT, "invalid fetch outcome"),
        (
            (replace(success, snapshot_identity=wrong(3)),),
            PROJECT,
            "invalid fetch outcome",
        ),
        (
            (replace(success, snapshot_identity="not-a-hash"),),
            PROJECT,
            "success has no archive hash",
        ),
    ]
    for attempts, source, observed in cases:
        expected_check = (
            "closure_without_evidence"
            if observed == "closure_without_evidence"
            else "evidence_audit_incomplete"
        )
        expected_text = (
            "no closure from failed or unattempted input"
            if expected_check == "closure_without_evidence"
            else "every registration, revision and absence"
        )
        result = evidence.audit_project_evidence(
            (registration,), built, attempts, snapshots=(item,)
        )
        observed_value = (
            "failed" if observed == "closure_without_evidence" else observed
        )
        assert result == failure(
            source, "", expected_check, expected_text, observed_value
        )
    assert evidence.audit_project_evidence(
        (registration,), ProjectEvidence(()), (success,)
    ) == failure(
        PROJECT,
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "registered input has no archived evidence",
    )
    wrong_kind = ExpectedInput(PROJECT, PROJECT, "invented_kind")
    assert evidence.audit_project_evidence(
        (wrong_kind,), built, (success,), snapshots=(item,)
    ) == failure(
        PROJECT,
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "unknown registration kind",
    )
