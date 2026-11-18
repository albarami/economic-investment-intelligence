"""Exact survivor witnesses for archive linkage and audit diagnostics."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from custodian.tests.investment_fixtures import invented_record
from custodian.tests.test_investment_evidence_survivors import (
    PROJECT,
    PROJECT_IDENTITY,
    SOURCE,
    TERMS,
    candidate,
    crosswalk,
    failure,
    link_for,
    milestone_body,
    milestone_row,
    milestone_selection,
    project,
)

import eii_custodian.publicdata.investment_evidence as evidence
from eii_custodian.publicdata.fetch import registry as registry_module
from eii_custodian.publicdata.fetch.snapshots import publish_snapshot, read_snapshot
from eii_custodian.publicdata.investment_contracts import (
    EvidenceAudit,
    EvidenceAuditEntry,
    FetchAttempt,
    MilestoneEvidence,
    ProjectArchiveSelection,
    ProjectEvidence,
)


def test_cache_crosswalk_key_comes_from_archive_selection(tmp_path: Path) -> None:
    item = project(tmp_path)
    row = candidate(tmp_path, body=milestone_body([milestone_row(direct=False)]))
    link = link_for(row)
    archived = crosswalk(tmp_path, row, link)
    # The link has no prepopulated key or Snapshot: the selection supplies both.
    selected_link = replace(link, crosswalk_sha256=archived.sha256)
    selection = replace(
        milestone_selection(row, (selected_link,)),
        crosswalk_key="review/milestone_crosswalk",
    )
    result = evidence.build_cache_evidence(
        tmp_path / "cache",
        projects=(ProjectArchiveSelection(PROJECT, item.identity, {}),),
        milestones=(selection,),
        expected=(),
        attempts=(),
    )
    assert not isinstance(result, evidence.InvestmentFailure)
    assert result.evidence.milestones == (
        MilestoneEvidence(row, PROJECT_IDENTITY, "validated", ""),
    )
    assert result.audit.entries[-1] == EvidenceAuditEntry(
        SOURCE,
        SOURCE,
        row.candidate_id,
        row.snapshot_identity,
        "public",
        "observed_independent_milestone",
        "independent_milestone",
        "",
    )


@pytest.mark.parametrize(
    ("independence", "status", "reason"),
    [
        ("publisher_announcement", "missing_evidence", "project_identity_unresolved"),
        ("independent_report", "missing_evidence", "project_identity_unresolved"),
        ("independent_report", "missing_evidence", ""),
        ("publisher_announcement", "validated", ""),
        ("independent_report", "validated", ""),
    ],
)
def test_audit_preserves_reason_and_independence_states(
    tmp_path: Path, independence: str, status: str, reason: str
) -> None:
    row = candidate(
        tmp_path, body=milestone_body([milestone_row(independence=independence)])
    )
    supplied = ProjectEvidence((), (MilestoneEvidence(row, None, status, reason),), ())
    result = evidence.audit_project_evidence((), supplied, ())
    expected_reason = reason
    if independence == "publisher_announcement" and not reason:
        expected_reason = "milestone_not_independent"
    validated = independence == "independent_report" and status == "validated"
    assert result == EvidenceAudit(
        (
            EvidenceAuditEntry(
                SOURCE,
                SOURCE,
                row.candidate_id,
                row.snapshot_identity,
                "public",
                "observed_independent_milestone" if validated else "missing_evidence",
                "independent_milestone" if validated else "unvalidated_milestone",
                expected_reason,
            ),
        )
    )


def test_duplicate_attempt_refusal_preserves_source_before_writing(
    tmp_path: Path,
) -> None:
    failed = FetchAttempt(SOURCE, SOURCE, "failed", None, "SYN-FAILURE")
    unattempted = replace(failed, status="unattempted", reason="SYN-NOT-ATTEMPTED")
    result = evidence.archive_fetch_attempts(
        tmp_path,
        (),
        (failed, unattempted),
        sidecars={},
        retrieved_utc="2026-11-16T08:00:00Z",
    )
    assert result == failure(
        SOURCE,
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "duplicate fetch attempt",
    )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("terms_url", [None, "", 3])
def test_receipt_terms_fallback_uses_authenticated_registry_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, terms_url: object
) -> None:
    row = candidate(tmp_path)
    assert row.snapshot is not None
    side = dict(row.snapshot.sidecar)
    if terms_url is None:
        del side["terms_url"]
    else:
        side["terms_url"] = terms_url
    entry = SimpleNamespace(
        source_id=side["source_id"],
        key=side["key"],
        publisher=side["publisher"],
        url=side["fetch_url"],
        licence_id=side["licence_id"],
        licence_basis=side["licence_basis"],
        decision_record=side["decision_record"],
        terms_url=TERMS,
    )
    monkeypatch.setattr(registry_module, "load_registry", lambda: (entry,))
    directory = tmp_path / "fallback"
    archived = publish_snapshot(directory, "json", row.snapshot.body, side)
    selected = read_snapshot(directory, archived.sha256)
    result = evidence._receipt_lineage(selected, "SYN-METHOD", "SYN-VERSION")
    assert result == {**row.source_chain, "terms_url": TERMS}


def test_non_string_null_equal_location_keeps_absence(tmp_path: Path) -> None:
    class NullEqualLocation:
        def __eq__(self, other: object) -> bool:
            return other is None

    item = project(tmp_path, records=(invented_record(project_address=""),))
    assert item.rows[0]["location_text"] is None
    supplied = replace(
        item, rows=({**item.rows[0], "location_text": NullEqualLocation()},)
    )
    result = evidence.build_project_evidence((supplied,))
    assert isinstance(result, ProjectEvidence)
    assert result.revisions[0].geography is None
    assert result.revisions[0].geography_absence_reason == "not_stated_by_source"


@pytest.mark.parametrize(
    ("field", "missing_on"),
    [
        ("source_id", 3),
        ("project_id", 3),
        ("source_id", 4),
        ("project_id", 4),
        ("project_key", 3),
    ],
)
def test_unstable_caller_key_never_invents_identifier_text(
    tmp_path: Path,
    field: str,
    missing_on: int,
) -> None:
    class UnstableKey(str):
        __hash__ = str.__hash__

        def __new__(cls, value: str):
            instance = super().__new__(cls, value)
            instance.comparisons = 0
            return instance

        def __eq__(self, other: object) -> bool:
            self.comparisons += 1
            return self.comparisons != missing_on and str.__eq__(self, other)

    first = project(tmp_path)
    second = project(
        tmp_path,
        day="2026-11-15",
        records=(invented_record(project_id=1001, capex=("n", "13.5")),),
    )
    key = UnstableKey(field)
    row = {
        key if name == field else name: value for name, value in first.rows[0].items()
    }
    result = evidence.build_project_evidence((replace(first, rows=(row,)), second))
    control = evidence.build_project_evidence((first, second))
    # After archived-row equality, identity, geography and source chain come
    # from the authenticated parser rows. A caller key cannot empty them.
    assert isinstance(result, ProjectEvidence)
    assert isinstance(control, ProjectEvidence)
    assert [
        (
            revision.project_identity,
            revision.source_id,
            revision.project_id,
            revision.project_key,
            revision.geography,
            revision.source_chain,
        )
        for revision in result.revisions
    ] == [
        (
            revision.project_identity,
            revision.source_id,
            revision.project_id,
            revision.project_key,
            revision.geography,
            revision.source_chain,
        )
        for revision in control.revisions
    ]
    assert result.absences == control.absences


@pytest.mark.parametrize("kind", ["revision", "absence"])
def test_audit_fallback_never_rewrites_retained_entry_fields(
    tmp_path: Path, kind: str
) -> None:
    class EqualToEmpty(tuple):
        def __eq__(self, other: object) -> bool:
            return other == ()

        def __ne__(self, other: object) -> bool:
            return other != ()

    item = project(tmp_path)
    built = evidence.build_project_evidence((item,))
    assert isinstance(built, ProjectEvidence)
    if kind == "revision":
        supplied = replace(built, revisions=EqualToEmpty(built.revisions))
        expected = EvidenceAuditEntry(
            PROJECT,
            PROJECT,
            PROJECT_IDENTITY,
            item.identity,
            "public",
            "observed_announcement",
            "retained_revision",
            "",
        )
    else:
        absence = evidence.ProjectAbsence(
            PROJECT_IDENTITY, PROJECT, item.identity, "not_present_in_source_snapshot"
        )
        supplied = ProjectEvidence((), absences=EqualToEmpty((absence,)))
        expected = EvidenceAuditEntry(
            PROJECT,
            PROJECT,
            PROJECT_IDENTITY,
            item.identity,
            "public",
            "missing_evidence",
            "absent_from_snapshot",
            "not_present_in_source_snapshot",
        )
    result = evidence.audit_project_evidence((), supplied, ())
    # These tuple subclasses expose a separate boundary issue (PO-S2-87).
    # Preserve fields if returned; a future fix should refuse their projection.
    if isinstance(result, evidence.InvestmentFailure):
        assert result.check == "evidence_audit_incomplete"
        return
    assert result.entries == (expected,)


def test_audit_refuses_non_plain_str_key(tmp_path: Path) -> None:
    class SubKey(str):
        pass

    row = replace(candidate(tmp_path), source_id=SubKey(SOURCE))
    supplied = ProjectEvidence(
        (), (MilestoneEvidence(row, None, "missing_evidence", ""),), ()
    )
    result = evidence.audit_project_evidence((), supplied, ())
    assert result == failure(
        "",
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "plain key",
    )


def test_audit_refuses_non_plain_tuple_history(tmp_path: Path) -> None:
    class History(tuple):
        def __eq__(self, other: object) -> bool:
            return other == ()

        def __ne__(self, other: object) -> bool:
            return other != ()

    item = project(tmp_path)
    built = evidence.build_project_evidence((item,))
    assert isinstance(built, ProjectEvidence)
    supplied = replace(built, revisions=History(built.revisions))
    result = evidence.audit_project_evidence((), supplied, ())
    assert result == failure(
        "",
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "plain sequence",
    )


def test_audit_refuses_non_plain_tuple_absence(tmp_path: Path) -> None:
    class Absences(tuple):
        def __eq__(self, other: object) -> bool:
            return other == ()

        def __ne__(self, other: object) -> bool:
            return other != ()

    item = project(tmp_path)
    absence = evidence.ProjectAbsence(
        PROJECT_IDENTITY, PROJECT, item.identity, "not_present_in_source_snapshot"
    )
    supplied = ProjectEvidence((), absences=Absences((absence,)))
    result = evidence.audit_project_evidence((), supplied, ())
    assert result == failure(
        "",
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "plain sequence",
    )


def test_cache_keeps_conflicting_archive_selection_validation(tmp_path: Path) -> None:
    class ConflictingKey(str):
        __hash__ = str.__hash__
        comparisons = 0

        def __eq__(self, other: object) -> bool:
            self.comparisons += 1
            return self.comparisons != 3 and str.__eq__(self, other)

        def __ne__(self, other: object) -> bool:
            return not self.__eq__(other)

    item = project(tmp_path)
    result = evidence.build_cache_evidence(
        tmp_path / "cache",
        projects=(ProjectArchiveSelection(ConflictingKey(PROJECT), item.identity, {}),),
        milestones=(),
        expected=(),
        attempts=(),
    )
    assert result == failure(
        PROJECT,
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "conflicting archive selection",
    )
