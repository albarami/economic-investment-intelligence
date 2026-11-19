"""PO-S2-87: caller equality cannot authenticate audit identity fields."""

from dataclasses import replace
from pathlib import Path

from custodian.tests.test_investment_evidence_survivors import (
    candidate,
    failure,
    project,
)

import eii_custodian.publicdata.investment_evidence as evidence
from eii_custodian.publicdata.investment_contracts import (
    MilestoneEvidence,
    ProjectEvidence,
)


class EqualHistory(tuple):
    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False


class EqualKey(str):
    __hash__ = str.__hash__

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False


def test_audit_refuses_lying_history_with_project_snapshot(tmp_path: Path) -> None:
    item = project(tmp_path)
    built = evidence.build_project_evidence((item,))
    assert isinstance(built, ProjectEvidence)
    forged = replace(
        built.revisions[0],
        source_id="fabricated_source",
        project_identity="fdi_projects:project:FABRICATED",
    )
    supplied = replace(built, revisions=EqualHistory((forged,)))
    result = evidence.audit_project_evidence((), supplied, (), snapshots=(item,))
    assert result == failure(
        "",
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "plain sequence",
    )


def test_audit_refuses_lying_source_id_with_project_snapshot(tmp_path: Path) -> None:
    item = project(tmp_path)
    built = evidence.build_project_evidence((item,))
    assert isinstance(built, ProjectEvidence)
    row = replace(candidate(tmp_path), source_id=EqualKey("fabricated_source"))
    supplied = replace(
        built, milestones=(MilestoneEvidence(row, None, "missing_evidence", ""),)
    )
    result = evidence.audit_project_evidence((), supplied, (), snapshots=(item,))
    assert result == failure(
        "",
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "plain key",
    )


def test_audit_refuses_lying_candidate_id_without_project_snapshot(
    tmp_path: Path,
) -> None:
    row = replace(candidate(tmp_path), candidate_id=EqualKey("FABRICATED-CANDIDATE"))
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
