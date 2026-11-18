"""Continuation proofs for archive selection, fail-fast order and receipt guards."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.test_investment_evidence_survivors import (
    PROJECT,
    PROJECT_IDENTITY,
    SOURCE,
    URL,
    candidate,
    crosswalk_candidate,
    failure,
    milestone_selection,
    project,
    shape,
)

import eii_custodian.publicdata.investment_evidence as evidence
from eii_custodian.publicdata.fetch.snapshots import (
    SnapshotError,
    publish_snapshot,
    read_snapshot,
)
from eii_custodian.publicdata.investment_contracts import (
    EvidenceAudit,
    EvidenceAuditEntry,
    ExpectedInput,
    FetchAttempt,
    InvestmentFailure,
    MilestoneEvidence,
    ProjectArchiveSelection,
    ProjectEvidence,
    SourceAssertion,
    VerifiedArchive,
)


def test_unavailable_selected_crosswalk_keeps_supplied_verified_link(tmp_path: Path):
    row, linked = crosswalk_candidate(tmp_path)
    item = project(tmp_path)
    selection = replace(
        milestone_selection(row, (linked,)), crosswalk_key="review/SYN-MISSING"
    )
    result = evidence.build_cache_evidence(
        tmp_path / "cache",
        projects=(ProjectArchiveSelection(PROJECT, item.identity, {}),),
        milestones=(selection,),
        expected=(),
        attempts=(),
    )
    assert not isinstance(result, InvestmentFailure)
    assert result.evidence.milestones == (
        MilestoneEvidence(row, PROJECT_IDENTITY, "validated", ""),
    )


def test_audit_archive_uses_reread_metadata(tmp_path: Path):
    item = project(tmp_path)
    supplied = replace(
        item.snapshot,
        sidecar={**item.snapshot.sidecar, "publisher": "SYN-SUBSTITUTED"},
    )
    archive = VerifiedArchive(PROJECT, PROJECT, "project", item.identity, supplied)
    assert evidence._audit_archives((), (archive,), ()) == (
        replace(archive, snapshot=item.snapshot),
    )


def test_audit_derives_milestone_archive_without_explicit_selection(tmp_path: Path):
    row = candidate(tmp_path)
    milestone = MilestoneEvidence(row, None, "missing_evidence", "unreviewed")
    result = evidence._audit_archives((), (), (milestone,))
    assert result == (
        VerifiedArchive(
            SOURCE, SOURCE, "milestone", row.snapshot_identity, row.snapshot, shape()
        ),
    )


def test_snapshotless_candidate_does_not_skip_following_archive(tmp_path: Path):
    row = candidate(tmp_path)
    missing = MilestoneEvidence(
        replace(row, snapshot=None), None, "missing_evidence", ""
    )
    present = MilestoneEvidence(row, None, "missing_evidence", "")
    result = evidence._audit_archives((), (), (missing, present))
    assert isinstance(result, tuple)
    assert len(result) == 1
    assert result[0].identity == row.snapshot_identity


def test_project_archive_after_milestone_is_still_parsed(tmp_path: Path):
    item = project(tmp_path)
    row = candidate(tmp_path)
    milestone = VerifiedArchive(
        SOURCE, SOURCE, "milestone", row.snapshot_identity, row.snapshot, shape()
    )
    archive = VerifiedArchive(PROJECT, PROJECT, "project", item.identity, item.snapshot)
    result = evidence._audit_project_snapshots((milestone, archive), ())
    assert isinstance(result, tuple)
    assert len(result) == 1
    assert result[0].rows[0]["project_id"] == 1001


def test_audit_candidates_keep_their_verified_snapshot(tmp_path: Path):
    row = candidate(tmp_path)
    archive = VerifiedArchive(
        SOURCE, SOURCE, "milestone", row.snapshot_identity, row.snapshot, shape()
    )
    assert evidence._audit_milestone_candidates((archive,)) == (row,)


@pytest.mark.parametrize("status", [None, "failed", "unattempted"])
def test_audit_attempts_continue_and_keep_full_states(
    tmp_path: Path, status: str | None
):
    item = project(tmp_path)
    built = evidence.build_project_evidence((item,))
    assert isinstance(built, ProjectEvidence)
    expected = (
        ExpectedInput(SOURCE, SOURCE, "milestone"),
        ExpectedInput(PROJECT, PROJECT, "project"),
    )
    attempts = (
        ()
        if status is None
        else (FetchAttempt(SOURCE, SOURCE, status, None, "SYN-FAILURE"),)
    )
    result = evidence.audit_project_evidence(
        expected, built, attempts, snapshots=(item,)
    )
    assert isinstance(result, EvidenceAudit)
    assert result.entries[1:] == (
        EvidenceAuditEntry(
            SOURCE,
            SOURCE,
            "",
            "",
            "public",
            status or "unattempted",
            "fetch_outcome",
            "not_attempted_after_fail_fast" if status is None else "SYN-FAILURE",
        ),
        EvidenceAuditEntry(
            PROJECT,
            PROJECT,
            "",
            "",
            "public",
            "unattempted",
            "fetch_outcome",
            "not_attempted_after_fail_fast",
        ),
    )


@pytest.mark.parametrize("status", [None, "failed", "unattempted"])
def test_archived_attempts_continue_after_every_non_success(
    tmp_path: Path, status: str | None
):
    item = project(tmp_path)
    expected = (
        ExpectedInput(SOURCE, SOURCE, "milestone"),
        ExpectedInput(PROJECT, PROJECT, "project"),
    )
    first = (
        ()
        if status is None
        else (FetchAttempt(SOURCE, SOURCE, status, None, "SYN-FAILURE"),)
    )
    result = evidence.archive_fetch_attempts(
        tmp_path / "cache",
        expected,
        (*first, FetchAttempt(PROJECT, PROJECT, "success", item.identity, "")),
        sidecars={
            PROJECT: item.snapshot.sidecar,
            SOURCE: {**item.snapshot.sidecar, "key": SOURCE, "source_id": SOURCE},
        },
        retrieved_utc="2026-11-16T08:00:00Z",
    )
    assert result == EvidenceAudit(
        (
            EvidenceAuditEntry(
                SOURCE,
                SOURCE,
                "",
                "",
                "public",
                status or "unattempted",
                "fetch_outcome",
                "not_attempted_after_fail_fast" if status is None else "SYN-FAILURE",
            ),
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


@pytest.mark.parametrize("archive", [False, True])
def test_success_with_closure_flag_is_still_backed_by_archive(
    tmp_path: Path, archive: bool
):
    item = project(tmp_path)
    registration = ExpectedInput(PROJECT, PROJECT, "project")
    attempt = FetchAttempt(PROJECT, PROJECT, "success", item.identity, "", True)
    if archive:
        result = evidence.archive_fetch_attempts(
            tmp_path / "cache",
            (registration,),
            (attempt,),
            sidecars={PROJECT: item.snapshot.sidecar},
            retrieved_utc="2026-11-16T08:00:00Z",
        )
        assert isinstance(result, EvidenceAudit)
        assert result.entries[0].evidence_status == "observed_announcement"
    else:
        built = evidence.build_project_evidence((item,))
        assert isinstance(built, ProjectEvidence)
        result = evidence.audit_project_evidence(
            (registration,), built, (attempt,), snapshots=(item,)
        )
        assert isinstance(result, EvidenceAudit)
        assert len(result.entries) == 1


@pytest.mark.parametrize("field", ["source_id", "key"])
def test_archive_fetch_registration_binds_each_receipt_field(
    tmp_path: Path, field: str
):
    item = project(tmp_path)
    directory = tmp_path / "SYN-OTHER" / PROJECT
    archived = publish_snapshot(
        directory,
        "html",
        item.snapshot.body,
        {**item.snapshot.sidecar, field: "SYN-OTHER"},
    )
    result = evidence.archive_fetch_attempts(
        directory.parent,
        (ExpectedInput(PROJECT, PROJECT, "project"),),
        (FetchAttempt(PROJECT, PROJECT, "success", archived.sha256, ""),),
        sidecars={PROJECT: item.snapshot.sidecar},
        retrieved_utc="2026-11-16T08:00:00Z",
    )
    assert result == failure(
        PROJECT,
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "archive registration metadata differs",
    )


def test_attempt_audit_body_is_verified_after_publication(tmp_path: Path, monkeypatch):
    item = project(tmp_path)
    original = evidence.archive_evidence_audit

    def tamper(*args, **kwargs):
        archived = original(*args, **kwargs)
        archived.path.write_bytes(b"SYN-CHANGED-AUDIT")
        return archived

    monkeypatch.setattr(evidence, "archive_evidence_audit", tamper)
    with pytest.raises(SnapshotError, match=r"^snapshot_hash_mismatch$"):
        evidence.archive_fetch_attempts(
            tmp_path / "cache",
            (ExpectedInput(PROJECT, PROJECT, "project"),),
            (),
            sidecars={PROJECT: item.snapshot.sidecar},
            retrieved_utc="2026-11-16T08:00:00Z",
        )


def test_milestone_receipt_defaults_supply_method_and_version(tmp_path: Path):
    row = candidate(tmp_path)
    directory = tmp_path / "SYN-DEFAULTS" / SOURCE
    side = {
        name: value
        for name, value in row.snapshot.sidecar.items()
        if name not in ("method", "method_version")
    }
    archived = publish_snapshot(directory, "json", row.snapshot.body, side)
    selected = replace(row, snapshot=read_snapshot(directory, archived.sha256))
    from custodian.tests.test_investment_evidence_survivors import link_for

    assert evidence.require_independent_milestone(
        selected, link_for(selected), frozenset({PROJECT_IDENTITY})
    ) == MilestoneEvidence(selected, PROJECT_IDENTITY, "validated", "")


def test_correction_flag_is_valid_metadata_but_not_a_dashboard_assertion(
    tmp_path: Path,
):
    item = project(tmp_path)
    planted = replace(item, correction=SourceAssertion("false", "source_flag", ""))
    from custodian.tests.test_investment_evidence_survivors import DASHBOARD_URL

    assert evidence.build_project_evidence((planted,)) == failure(
        PROJECT,
        DASHBOARD_URL,
        "invalid_evidence_metadata",
        "archived parser output",
        "mismatch",
    )


def test_unknown_assertion_precision_is_refused():
    assert (
        evidence._valid_assertion(SourceAssertion("2026", "SYN-UNKNOWN", "")) is False
    )


def test_empty_join_value_reaches_parser_identity_check(tmp_path: Path):
    row = candidate(tmp_path)
    from custodian.tests.test_investment_evidence_survivors import link_for

    planted = replace(row, source_chain={**row.source_chain, "join_key": ""})
    assert evidence.require_independent_milestone(
        planted, link_for(row), frozenset({PROJECT_IDENTITY})
    ) == failure(
        SOURCE, URL, "invalid_evidence_metadata", "archived parser row", "mismatch"
    )
