"""Announced-project revisions, independent milestones and completeness evidence."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

import eii_custodian.publicdata.investment_contracts as evidence_contracts
import eii_custodian.publicdata.investment_evidence as evidence_module
from eii_custodian.publicdata.fetch.snapshots import (
    SnapshotError,
    publish_snapshot,
    read_snapshot,
    reviewed_selections,
)
from eii_custodian.publicdata.investment_contracts import (
    ProjectSnapshot,
    SourceAssertion,
    SourceEnvelope,
)
from eii_custodian.publicdata.investment_evidence import build_project_evidence


def test_revision_history_is_immutable(tmp_path: Path) -> None:
    """Changed announcements retain both snapshots and refuse historical replacement."""
    first = _project_snapshot(tmp_path, day="2026-11-14", capex="12.5", marker="first")
    second = _project_snapshot(
        tmp_path, day="2026-11-15", capex="14.5", marker="second"
    )
    result = build_project_evidence((first, second))
    assert not hasattr(result, "check")
    assert len(result.revisions) == 2
    assert {row.project_identity for row in result.revisions} == {
        "fdi_projects:project:1001"
    }
    assert [row.announced["capex"] for row in result.revisions] == ["12.5", "14.5"]
    assert (
        result.revisions[0].snapshot_identity != result.revisions[1].snapshot_identity
    )

    overwritten = build_project_evidence((first, first))
    assert getattr(overwritten, "check", "") == "revision_overwrite"


def test_snapshot_metadata_and_lineage(tmp_path: Path) -> None:
    """Revision metadata stays sourced, complete and distinct from fetch clocks."""
    first = _project_snapshot(tmp_path, day="2026-11-14", capex="12.5", marker="first")
    result = build_project_evidence((first,))
    assert not hasattr(result, "check")
    revision = result.revisions[0]
    assert revision.observation.value == "2024-06-15"
    assert revision.observation.precision == "day"
    assert revision.publication.value is None
    assert revision.publication.absence_reason == "not_stated_by_source"
    assert revision.retrieved_utc == "2026-11-14T08:00:00Z"
    assert revision.checksum == first.snapshot.sha256
    assert revision.schema == "fdi_projects.v1"
    assert revision.geography == "Invented Bay"
    assert revision.correction.value is None
    assert revision.correction.absence_reason == "not_stated_by_source"

    missing_terms = replace(
        first,
        rows=({**first.rows[0], "terms_sha256": ""},),
    )
    assert (
        getattr(build_project_evidence((missing_terms,)), "check", "")
        == "missing_terms"
    )
    missing_method = replace(
        first,
        rows=({**first.rows[0], "method": ""},),
    )
    assert (
        getattr(build_project_evidence((missing_method,)), "check", "")
        == "missing_lineage"
    )
    for planted in (
        replace(first, schema=""),
        replace(first, rows=({**first.rows[0], "location_text": ""},)),
        replace(first, observation=SourceAssertion(None, "", "")),
        replace(
            first,
            publication=SourceAssertion("2026-11-14T08:00:00Z", "fetch_recheck", ""),
        ),
        replace(first, correction=SourceAssertion(None, "", "")),
    ):
        assert (
            getattr(build_project_evidence((planted,)), "check", "")
            == "invalid_evidence_metadata"
        )


def test_project_identity_continuity(tmp_path: Path) -> None:
    """Only source-scoped published IDs link revisions; content keys never do."""
    first = _project_snapshot(tmp_path, day="2026-11-14", capex="12.5", marker="first")
    second = _project_snapshot(
        tmp_path, day="2026-11-15", capex="14.5", marker="second"
    )
    from custodian.tests.investment_fixtures import invented_record

    other = _project_snapshot(
        tmp_path,
        day="2026-11-16",
        capex="15.5",
        marker="third",
        records=(invented_record(project_id=1002, capex=("n", "15.5")),),
    )
    result = build_project_evidence((first, second, other))
    assert not hasattr(result, "check")
    assert len({row.project_identity for row in result.revisions}) == 2

    changed_id = replace(second, rows=({**second.rows[0], "project_id": 1002},))
    changed_id = replace(
        changed_id,
        rows=({**changed_id.rows[0], "project_key": first.rows[0]["project_key"]},),
    )
    refused = build_project_evidence((first, changed_id))
    assert getattr(refused, "check", "") == "invalid_evidence_metadata"

    ambiguous = _project_snapshot(
        tmp_path,
        day="2026-11-17",
        capex="16.5",
        marker="ambiguous",
        records=(
            invented_record(project_id=1001, capex=("n", "16.5")),
            invented_record(
                project_id=1001,
                investing_company_name="Invented Other Works",
                capex=("n", "16.5"),
            ),
        ),
    )
    assert (
        getattr(build_project_evidence((ambiguous,)), "check", "")
        == "project_identity_unresolved"
    )


def test_source_times_and_corrections(tmp_path: Path) -> None:
    """Unknown source assertions stay unknown; rechecks and invented places do not fill them."""
    first = _project_snapshot(tmp_path, day="2026-11-14", capex="12.5", marker="first")
    unknown = SourceAssertion(None, "", "not_stated_by_source")
    with_unknowns = replace(
        first,
        observation=unknown,
        publication=unknown,
        correction=unknown,
        snapshot=replace(
            first.snapshot,
            sidecar={**first.snapshot.sidecar, "source_modified": "2026-11-13"},
        ),
    )
    result = build_project_evidence((with_unknowns,))
    assert not hasattr(result, "check")
    revision = result.revisions[0]
    assert revision.observation.value == "2024-06-15"
    assert revision.publication.absence_reason == "not_stated_by_source"
    assert revision.correction.value is None
    assert revision.retrieved_utc == "2026-11-14T08:00:00Z"

    for planted in (
        replace(
            first,
            rows=({**first.rows[0], "location_text": "Invented Other Place"},),
        ),
        replace(first, observation=SourceAssertion("false", "source_flag", "")),
        replace(first, correction=SourceAssertion("2026-11-13", "day", "")),
    ):
        assert (
            getattr(build_project_evidence((planted,)), "check", "")
            == "invalid_evidence_metadata"
        )


def test_independent_milestone_requires_independent_evidence(tmp_path: Path) -> None:
    """Only archived, reviewed independent reporting validates a milestone."""
    parse_milestone_page = getattr(evidence_module, "parse_milestone_page", None)
    require_independent_milestone = getattr(
        evidence_module, "require_independent_milestone", None
    )
    assert callable(parse_milestone_page), "confirmed milestone parsing is absent"
    assert callable(require_independent_milestone), "milestone review is absent"
    from eii_custodian.publicdata.investment_contracts import (
        MilestoneShape,
        ReviewedMilestoneLink,
        SourceEnvelope,
    )

    shape = MilestoneShape(
        "invented-independent-milestones-v1",
        frozenset(
            {
                "milestone_id",
                "project_source_id",
                "project_id",
                "status",
                "observation",
                "publication",
                "correction",
                "geography",
                "independence",
            }
        ),
        True,
    )
    envelope = SourceEnvelope(
        source_id="invented_milestones",
        publisher="Invented independent publisher",
        page_url="https://milestones.invalid/invented-start",
        licence_id="invented-public-terms",
        licence_basis="owner_decision",
        decision_record="invented-review",
        terms_sha256="ab" * 32,
        terms_url="https://terms.invalid/terms",
        retrieved_utc="2026-11-15T08:00:00Z",
        page_sha256="",
        method="eii_custodian.publicdata.investment_evidence.parse_milestone_page",
        method_version="1",
    )
    project = _project_snapshot(
        tmp_path, day="2026-11-14", capex="12.5", marker="first"
    )
    candidate = _milestone_candidate(
        tmp_path,
        parse_milestone_page,
        shape,
        envelope,
        independence="independent_report",
    )
    link = ReviewedMilestoneLink(
        candidate_id=candidate.candidate_id,
        project_identity="fdi_projects:project:1001",
        independence="independent_report",
        reviewed=True,
        review_reference="invented-independent-review",
        crosswalk_sha256="",
    )
    result = build_project_evidence((project,), (candidate,), (link,))
    assert not hasattr(result, "check")
    assert result.milestones[0].evidence_status == "validated"
    assert result.milestones[0].project_identity == "fdi_projects:project:1001"

    for relation in ("publisher_announcement", "syndicated_copy"):
        copied = _milestone_candidate(
            tmp_path,
            parse_milestone_page,
            shape,
            envelope,
            independence=relation,
            marker=relation,
        )
        copied_link = replace(link, candidate_id=copied.candidate_id)
        refused = require_independent_milestone(
            copied, copied_link, frozenset({"fdi_projects:project:1001"})
        )
        assert getattr(refused, "check", "") == "milestone_not_independent"
        retained = build_project_evidence((project,), (copied,), (copied_link,))
        assert not hasattr(retained, "check")
        assert retained.milestones[0].evidence_status == "missing_evidence"
        assert retained.milestones[0].missing_reason == "milestone_not_independent"

    unreviewed = replace(link, reviewed=False)
    retained = build_project_evidence((project,), (candidate,), (unreviewed,))
    assert retained.milestones[0].evidence_status == "missing_evidence"
    assert retained.milestones[0].missing_reason == "project_identity_unresolved"
    retained = build_project_evidence((project,), (candidate,), ())
    assert retained.milestones[0].missing_reason == "project_identity_unresolved"

    unknown_shape = replace(shape, confirmed=False)
    refused = parse_milestone_page(_milestone_page(), unknown_shape, envelope)
    assert getattr(refused, "check", "") == "unconfirmed"
    unknown_field = _milestone_page(extra={"unexpected": "invented"})
    refused = parse_milestone_page(
        unknown_field, shape, replace(envelope, page_sha256="cd" * 32)
    )
    assert getattr(refused, "check", "") == "unknown_field"


def test_reviewed_crosswalk_and_milestone_lineage(tmp_path: Path) -> None:
    """Crosswalk links need receipts and ambiguous links never validate a milestone."""
    project = _project_snapshot(
        tmp_path, day="2026-11-14", capex="12.5", marker="first"
    )
    candidate, direct_link = _valid_milestone_parts(tmp_path)
    shape = evidence_contracts.MilestoneShape(
        "invented-independent-milestones-v1",
        frozenset(
            {
                "milestone_id",
                "project_source_id",
                "project_id",
                "status",
                "observation",
                "publication",
                "correction",
                "geography",
                "independence",
            }
        ),
        True,
    )
    envelope = SourceEnvelope(
        source_id="invented_milestones",
        publisher="Invented independent publisher",
        page_url="https://milestones.invalid/invented-start",
        licence_id="invented-public-terms",
        licence_basis="owner_decision",
        decision_record="invented-review",
        terms_sha256="ab" * 32,
        terms_url="https://terms.invalid/terms",
        retrieved_utc="2026-11-15T08:00:00Z",
        page_sha256="",
        method="eii_custodian.publicdata.investment_evidence.parse_milestone_page",
        method_version="1",
    )
    crosswalk_candidate = _milestone_candidate(
        tmp_path,
        evidence_module.parse_milestone_page,
        shape,
        envelope,
        independence="independent_report",
        marker="crosswalk",
        direct=False,
    )
    crosswalk_key = "review/milestone_crosswalk"
    archived = _archive_crosswalk(
        tmp_path,
        crosswalk_key,
        crosswalk_candidate.candidate_id,
        "fdi_projects:project:1001",
        direct_link.review_reference,
    )
    link = replace(
        direct_link,
        candidate_id=crosswalk_candidate.candidate_id,
        crosswalk_sha256=archived.sha256,
        crosswalk_key=crosswalk_key,
        crosswalk=archived,
    )
    identities = frozenset({"fdi_projects:project:1001"})
    validated = evidence_module.require_independent_milestone(
        crosswalk_candidate, link, identities
    )
    assert not hasattr(validated, "check")
    no_receipt = replace(link, crosswalk_sha256="")
    refused = evidence_module.require_independent_milestone(
        crosswalk_candidate, no_receipt, identities
    )
    assert getattr(refused, "check", "") == "project_identity_unresolved"

    missing_terms = replace(
        candidate,
        source_chain={**candidate.source_chain, "terms_sha256": ""},
    )
    refused = evidence_module.require_independent_milestone(
        missing_terms, direct_link, identities
    )
    assert getattr(refused, "check", "") == "missing_terms"
    synthetic = replace(
        candidate,
        source_chain={**candidate.source_chain, "provenance": "synthetic"},
    )
    refused = evidence_module.require_independent_milestone(
        synthetic, direct_link, identities
    )
    assert getattr(refused, "check", "") == "provenance"
    wrong_candidate = replace(direct_link, candidate_id="invented-other-candidate")
    refused = evidence_module.require_independent_milestone(
        candidate, wrong_candidate, identities
    )
    assert getattr(refused, "check", "") == "project_identity_unresolved"

    duplicated = build_project_evidence(
        (project,), (candidate,), (direct_link, direct_link)
    )
    assert duplicated.milestones[0].evidence_status == "missing_evidence"
    assert duplicated.milestones[0].missing_reason == "project_identity_unresolved"


def test_announcement_and_observation_are_separate(tmp_path: Path) -> None:
    """Announced estimates and milestone prose never become realised investment."""
    observed_type = getattr(evidence_contracts, "ObservedInvestment", None)
    assert observed_type is not None, "announcement/observation boundary is not typed"
    project = _project_snapshot(
        tmp_path, day="2026-11-14", capex="12.5", marker="first"
    )
    result = build_project_evidence((project,))
    assert result.revisions[0].announced == {
        "capex": "12.5",
        "jobs": "40",
        "stated_intent": "Invented café note",
    }
    assert result.observed_investment == ()

    candidate, link = _valid_milestone_parts(tmp_path)
    identities = frozenset({"fdi_projects:project:1001"})
    for planted in (
        replace(candidate, completion="2026-11-16"),
        replace(candidate, observed_investment="12.5"),
        replace(candidate, status="completed"),
    ):
        refused = evidence_module.require_independent_milestone(
            planted, link, identities
        )
        assert getattr(refused, "check", "") == "unsupported_milestone"
        retained = build_project_evidence((project,), (planted,), (link,))
        assert retained.milestones[0].evidence_status == "missing_evidence"
        assert retained.milestones[0].missing_reason == "unsupported_milestone"
        assert retained.observed_investment == ()

    announcement = observed_type(
        project_identity="fdi_projects:project:1001",
        amount="12.5",
        source_id="fdi_projects",
        evidence_kind="announcement",
        snapshot_identity=project.identity,
    )
    refused = build_project_evidence((project,), observed_investment=(announcement,))
    assert getattr(refused, "check", "") == "announcement_as_observed"


def test_audit_lists_every_revision_and_absence(tmp_path: Path) -> None:
    """The S2 audit enumerates history, absence and registry-only missing evidence."""
    audit_project_evidence = getattr(evidence_module, "audit_project_evidence", None)
    assert callable(audit_project_evidence), "exhaustive evidence audit is absent"
    first = _project_snapshot(tmp_path, day="2026-11-14", capex="12.5", marker="first")
    from custodian.tests.investment_fixtures import invented_record

    other_record = invented_record(
        project_id=1002,
        investing_company_name="Invented Reed Mill",
        project_address="Invented Cove",
    )
    missing = _project_snapshot(
        tmp_path,
        day="2026-11-15",
        capex="12.5",
        marker="absent",
        records=(other_record,),
    )
    returned = _project_snapshot(
        tmp_path,
        day="2026-11-16",
        capex="14.5",
        marker="returned",
        records=(
            invented_record(project_id=1001, capex=("n", "14.5")),
            other_record,
        ),
    )
    evidence = build_project_evidence((first, missing, returned))
    assert len(evidence.revisions) == 4
    assert len(evidence.absences) == 1
    assert evidence.absences[0].snapshot_identity == missing.identity

    expected = (
        evidence_contracts.ExpectedInput("fdi_projects", "fdi_projects", "project"),
    )
    attempts = (
        evidence_contracts.FetchAttempt(
            "fdi_projects", "fdi_projects", "success", returned.identity, ""
        ),
    )
    audited = audit_project_evidence(
        expected, evidence, attempts, snapshots=(first, missing, returned)
    )
    assert not hasattr(audited, "check")
    assert len(audited.entries) == 5
    assert [entry.coverage for entry in audited.entries] == [
        "retained_revision",
        "retained_revision",
        "absent_from_snapshot",
        "retained_revision",
        "retained_revision",
    ]
    assert {entry.provenance for entry in audited.entries} == {"public"}
    absence = next(
        entry for entry in audited.entries if entry.coverage == "absent_from_snapshot"
    )
    assert absence.evidence_status == "missing_evidence"
    assert absence.reason == "not_present_in_source_snapshot"

    omitted_revision = replace(evidence, revisions=evidence.revisions[:1])
    refused = audit_project_evidence(
        expected, omitted_revision, attempts, snapshots=(first, missing, returned)
    )
    assert getattr(refused, "check", "") == "evidence_audit_incomplete"
    omitted_absence = replace(evidence, absences=())
    refused = audit_project_evidence(
        expected, omitted_absence, attempts, snapshots=(first, missing, returned)
    )
    assert getattr(refused, "check", "") == "evidence_audit_incomplete"

    registry_only = (
        *expected,
        evidence_contracts.ExpectedInput(
            "invented_milestones", "invented_milestones", "milestone"
        ),
    )
    registry_attempts = (
        *attempts,
        evidence_contracts.FetchAttempt(
            "invented_milestones",
            "invented_milestones",
            "success",
            "ef" * 32,
            "citation_only",
        ),
    )
    refused = audit_project_evidence(
        registry_only, evidence, registry_attempts, snapshots=(first, missing, returned)
    )
    assert getattr(refused, "check", "") == "evidence_audit_incomplete"


def test_failed_fetch_is_never_closure(tmp_path: Path) -> None:
    """Failure and fail-fast non-attempts stay visible and never reset raw cadence."""
    audit_project_evidence = getattr(evidence_module, "audit_project_evidence", None)
    archive_evidence_audit = getattr(evidence_module, "archive_evidence_audit", None)
    assert callable(audit_project_evidence), "fetch outcome audit is absent"
    assert callable(archive_evidence_audit), "attempt evidence is not archived"
    first = _project_snapshot(tmp_path, day="2026-11-14", capex="12.5", marker="first")
    evidence = build_project_evidence((first,))
    expected = (
        evidence_contracts.ExpectedInput("fdi_projects", "fdi_projects", "project"),
        evidence_contracts.ExpectedInput(
            "invented_milestones", "invented_milestones", "milestone"
        ),
    )
    failed = evidence_contracts.FetchAttempt(
        "fdi_projects", "fdi_projects", "failed", None, "transport_failed"
    )
    audited = audit_project_evidence(expected, evidence, (failed,), snapshots=(first,))
    assert not hasattr(audited, "check")
    states = {(entry.key, entry.evidence_status) for entry in audited.entries}
    assert ("fdi_projects", "failed") in states
    assert ("invented_milestones", "unattempted") in states
    assert ("fdi_projects", "observed_announcement") in states

    closure = replace(failed, closure_claimed=True)
    refused = audit_project_evidence(expected, evidence, (closure,), snapshots=(first,))
    assert getattr(refused, "check", "") == "closure_without_evidence"

    from eii_custodian.publicdata.fetch.cadence import due_registry
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.snapshots import checked_times

    cache = tmp_path / "cache"
    entry = next(row for row in load_registry() if row.source_id == "fdi_projects")

    def clock() -> datetime:
        return datetime(2026, 11, 16, tzinfo=UTC)

    before_checks = checked_times(cache / entry.key)
    before_due = due_registry((entry,), cache, clock=clock)
    archived = archive_evidence_audit(
        cache,
        audited,
        sidecar=first.snapshot.sidecar,
        retrieved_utc="2026-11-16T08:00:00Z",
    )
    assert archived.path.parent.parent.name == "evidence"
    assert checked_times(cache / entry.key) == before_checks
    assert due_registry((entry,), cache, clock=clock) == before_due


def test_referenced_older_snapshot_and_tamper(tmp_path: Path) -> None:
    """A pin selects older bytes; absent or malformed pins never choose latest."""
    older = _project_snapshot(tmp_path, day="2026-11-14", capex="12.5", marker="older")
    newer = _project_snapshot(tmp_path, day="2026-11-15", capex="14.5", marker="newer")
    cache = tmp_path / "cache"
    (cache / "snapshot_pins.json").write_text(
        json.dumps({"fdi_projects": older.identity}), encoding="utf-8"
    )
    selected = reviewed_selections(cache)["fdi_projects"]
    verified = read_snapshot(cache / "fdi_projects", selected)
    assert verified.sha256 == older.snapshot.sha256
    assert verified.sha256 != newer.snapshot.sha256
    retained = build_project_evidence((older,))
    assert retained.revisions[0].announced["capex"] == "12.5"

    verified.path.write_bytes(b"invented substituted bytes")
    with pytest.raises(SnapshotError, match="snapshot_hash_mismatch"):
        read_snapshot(cache / "fdi_projects", selected)
    with pytest.raises(SnapshotError, match="snapshot_hash_mismatch"):
        build_project_evidence((older,))

    (cache / "snapshot_pins.json").write_text(
        json.dumps({"fdi_projects": "invalid-pin"}), encoding="utf-8"
    )
    with pytest.raises(SnapshotError, match="snapshot_selection_invalid"):
        reviewed_selections(cache)
    (cache / "snapshot_pins.json").unlink()
    assert reviewed_selections(cache) == {}
    expected = (
        evidence_contracts.ExpectedInput("fdi_projects", "fdi_projects", "project"),
    )
    absent_pin = evidence_contracts.FetchAttempt(
        "fdi_projects",
        "fdi_projects",
        "unattempted",
        None,
        "snapshot_selection_missing",
    )
    audited = evidence_module.audit_project_evidence(
        expected, build_project_evidence(()), (absent_pin,)
    )
    assert audited.entries[0].evidence_status == "missing_evidence"
    assert audited.entries[0].reason == "snapshot_selection_missing"


def test_evidence_public_only_and_safe_report(tmp_path: Path) -> None:
    """Public-only project slots and source-named reports reject record-bearing output."""
    from eii_custodian.publicdata.fetch import report

    evidence_line = getattr(report, "evidence_line", None)
    assert callable(evidence_line), "safe evidence report line is absent"
    project = _project_snapshot(
        tmp_path, day="2026-11-14", capex="12.5", marker="first"
    )
    synthetic = replace(project, rows=({**project.rows[0], "provenance": "synthetic"},))
    assert getattr(build_project_evidence((synthetic,)), "check", "") == "provenance"
    joined = replace(
        project, rows=({**project.rows[0], "join_key": "invented-protected-join"},)
    )
    assert getattr(build_project_evidence((joined,)), "check", "") == "prohibited_join"

    line = evidence_line(
        "fdi_projects", "missing_evidence", "snapshot_selection_missing"
    )
    assert line == (
        "EVIDENCE fdi_projects missing_evidence reason=snapshot_selection_missing"
    )
    assert "Invented Loom" not in line
    assert "12.5" not in line
    for unsafe in (
        "Invented Loom Works capex 12.5",
        "secret=value",
        "/invented/private/path",
    ):
        with pytest.raises(ValueError, match=r"^unsafe_report$"):
            evidence_line("fdi_projects", "failed", unsafe)


def _valid_milestone_parts(tmp_path: Path):
    shape = evidence_contracts.MilestoneShape(
        "invented-independent-milestones-v1",
        frozenset(
            {
                "milestone_id",
                "project_source_id",
                "project_id",
                "status",
                "observation",
                "publication",
                "correction",
                "geography",
                "independence",
            }
        ),
        True,
    )
    envelope = SourceEnvelope(
        source_id="invented_milestones",
        publisher="Invented independent publisher",
        page_url="https://milestones.invalid/invented-start",
        licence_id="invented-public-terms",
        licence_basis="owner_decision",
        decision_record="invented-review",
        terms_sha256="ab" * 32,
        terms_url="https://terms.invalid/terms",
        retrieved_utc="2026-11-15T08:00:00Z",
        page_sha256="",
        method="eii_custodian.publicdata.investment_evidence.parse_milestone_page",
        method_version="1",
    )
    candidate = _milestone_candidate(
        tmp_path,
        evidence_module.parse_milestone_page,
        shape,
        envelope,
        independence="independent_report",
    )
    link = evidence_contracts.ReviewedMilestoneLink(
        candidate_id=candidate.candidate_id,
        project_identity="fdi_projects:project:1001",
        independence="independent_report",
        reviewed=True,
        review_reference="invented-independent-review",
        crosswalk_sha256="",
    )
    return candidate, link


def _milestone_candidate(
    root: Path,
    parser: object,
    shape: object,
    envelope: SourceEnvelope,
    *,
    independence: str,
    marker: str = "independent",
    direct: bool = True,
):
    body = _milestone_page(independence=independence, marker=marker, direct=direct)
    import hashlib

    digest = hashlib.sha256(body).hexdigest()
    stamped = replace(envelope, page_sha256=digest)
    parsed = parser(body, shape, stamped)
    assert not hasattr(parsed, "check")
    candidate = parsed[0]
    directory = root / "cache" / "invented_milestones"
    sidecar = {
        "source_id": stamped.source_id,
        "key": stamped.source_id,
        "retrieved_utc": stamped.retrieved_utc,
        "publisher": stamped.publisher,
        "fetch_url": stamped.page_url,
        "licence_id": stamped.licence_id,
        "licence_basis": stamped.licence_basis,
        "decision_record": stamped.decision_record,
        "terms_sha256": stamped.terms_sha256,
        "terms_url": stamped.terms_url,
        "method": stamped.method,
        "method_version": stamped.method_version,
    }
    publish_snapshot(directory, "json", body, sidecar)
    return replace(candidate, snapshot=read_snapshot(directory, digest))


def _milestone_page(
    *,
    independence: str = "independent_report",
    marker: str = "independent",
    extra: dict | None = None,
    direct: bool = True,
) -> bytes:
    stated = {"value": "2026-11-13", "precision": "day", "absence_reason": ""}
    row = {
        "milestone_id": f"invented-{marker}",
        "project_source_id": "fdi_projects" if direct else None,
        "project_id": "1001" if direct else None,
        "status": "construction_started",
        "observation": stated,
        "publication": stated,
        "correction": {
            "value": "false",
            "precision": "source_flag",
            "absence_reason": "",
        },
        "geography": "Invented Bay",
        "independence": independence,
    }
    if extra:
        row.update(extra)
    return (json.dumps({"milestones": [row]}, sort_keys=True) + "\n").encode()


def _project_snapshot(
    root: Path,
    *,
    day: str,
    capex: str,
    marker: str,
    records: tuple[dict[str, object], ...] | None = None,
) -> ProjectSnapshot:
    from custodian.tests.investment_fixtures import invented_record

    del marker
    if records is None:
        records = (invented_record(project_id=1001, capex=("n", capex)),)
    identity = _archive_dashboard(root / "cache", day, records)
    snapshot = read_snapshot(root / "cache" / "fdi_projects", identity)
    parsed = evidence_module._parse_project_snapshot(snapshot, coverage={})
    assert not hasattr(parsed, "check")
    return parsed


def test_archive_adapter_retains_history_and_failed_refresh(tmp_path: Path) -> None:
    """F1: explicit archived pages produce the complete S2-T08 projection."""
    adapter = getattr(evidence_module, "build_cache_evidence", None)
    assert callable(adapter), "the cache-only evidence adapter is absent"
    from custodian.tests.investment_fixtures import invented_record

    first_records = (
        invented_record(project_id=1001, capex=("n", "12.5")),
        invented_record(
            project_id=1002,
            investing_company_name="Invented Reed Mill",
            project_address="Invented Cove",
        ),
    )
    second_records = (first_records[1],)
    third_records = (
        first_records[1],
        invented_record(project_id=1001, capex=("n", "14.5")),
    )
    cache = tmp_path / "cache"
    identities = tuple(
        _archive_dashboard(cache, day, records)
        for day, records in zip(
            ("2026-11-14", "2026-11-15", "2026-11-16"),
            (first_records, second_records, third_records),
            strict=True,
        )
    )
    selection_type = evidence_contracts.ProjectArchiveSelection
    selections = tuple(
        selection_type("fdi_projects", identity, {"scope": "invented_history"})
        for identity in identities
    )
    expected = (
        evidence_contracts.ExpectedInput("fdi_projects", "fdi_projects", "project"),
        evidence_contracts.ExpectedInput(
            "invented_milestones", "invented_milestones", "milestone"
        ),
    )
    attempts = (
        evidence_contracts.FetchAttempt(
            "fdi_projects", "fdi_projects", "failed", None, "fetch_failed"
        ),
    )
    projection = adapter(
        cache,
        projects=selections,
        milestones=(),
        expected=expected,
        attempts=attempts,
    )
    assert not hasattr(projection, "check")
    assert len(projection.evidence.revisions) == 5
    assert len(projection.evidence.absences) == 1
    assert projection.evidence.absences[0].project_identity.endswith(":1001")
    returned = [
        row
        for row in projection.evidence.revisions
        if row.snapshot_identity == identities[2] and row.project_id == "1001"
    ]
    assert len(returned) == 1
    assert returned[0].announced["capex"] == "14.5"
    states = {(row.key, row.evidence_status) for row in projection.audit.entries}
    assert ("fdi_projects", "failed") in states
    assert ("invented_milestones", "unattempted") in states
    assert len(projection.archives) == 3


def test_cache_adapter_retains_unresolved_milestone(tmp_path: Path) -> None:
    """F1: an unresolved reviewed candidate stays visible as missing evidence."""
    cache = tmp_path / "cache"
    project = _project_snapshot(
        tmp_path, day="2026-11-14", capex="12.5", marker="first"
    )
    shape = _milestone_shape()
    candidate = _milestone_candidate(
        tmp_path,
        evidence_module.parse_milestone_page,
        shape,
        _milestone_envelope(),
        independence="independent_report",
        marker="unresolved",
    )
    link = evidence_contracts.ReviewedMilestoneLink(
        candidate.candidate_id,
        "fdi_projects:project:1002",
        "independent_report",
        True,
        "review/independent_milestone",
        "",
    )
    projection = evidence_module.build_cache_evidence(
        cache,
        projects=(
            evidence_contracts.ProjectArchiveSelection(
                "fdi_projects", project.identity, {}
            ),
        ),
        milestones=(
            evidence_contracts.MilestoneArchiveSelection(
                "invented_milestones",
                candidate.snapshot_identity,
                shape,
                _milestone_envelope(),
                (link,),
                "",
            ),
        ),
        expected=(
            evidence_contracts.ExpectedInput("fdi_projects", "fdi_projects", "project"),
            evidence_contracts.ExpectedInput(
                "invented_milestones", "invented_milestones", "milestone"
            ),
        ),
        attempts=(
            evidence_contracts.FetchAttempt(
                "fdi_projects", "fdi_projects", "success", project.identity, ""
            ),
            evidence_contracts.FetchAttempt(
                "invented_milestones",
                "invented_milestones",
                "success",
                candidate.snapshot_identity,
                "",
            ),
        ),
    )
    assert not hasattr(projection, "check")
    assert projection.evidence.milestones[0].evidence_status == "missing_evidence"
    assert (
        projection.evidence.milestones[0].missing_reason
        == "project_identity_unresolved"
    )


def test_crosswalk_requires_its_verified_archive_and_exact_mapping(
    tmp_path: Path,
) -> None:
    """F2: a hash-shaped token is not a reviewed crosswalk receipt."""
    candidate, direct_link = _valid_milestone_parts(tmp_path)
    shape = candidate.shape if hasattr(candidate, "shape") else None
    if shape is None:
        shape = _milestone_shape()
    envelope = _milestone_envelope()
    crosswalk_candidate = _milestone_candidate(
        tmp_path,
        evidence_module.parse_milestone_page,
        shape,
        envelope,
        independence="independent_report",
        marker="crosswalk",
        direct=False,
    )
    fabricated = replace(
        direct_link,
        candidate_id=crosswalk_candidate.candidate_id,
        crosswalk_sha256="cd" * 32,
    )
    identities = frozenset({"fdi_projects:project:1001"})
    refused = evidence_module.require_independent_milestone(
        crosswalk_candidate, fabricated, identities
    )
    assert getattr(refused, "check", "") == "project_identity_unresolved"
    assert "crosswalk" in evidence_contracts.ReviewedMilestoneLink.__dataclass_fields__

    key = "review/milestone_crosswalk"
    archived = _archive_crosswalk(
        tmp_path,
        key,
        crosswalk_candidate.candidate_id,
        "fdi_projects:project:1001",
        direct_link.review_reference,
    )
    linked = replace(
        fabricated,
        crosswalk_sha256=archived.sha256,
        crosswalk_key=key,
        crosswalk=archived,
    )
    validated = evidence_module.require_independent_milestone(
        crosswalk_candidate, linked, identities
    )
    assert not hasattr(validated, "check")

    no_archive = replace(linked, crosswalk=None)
    refused = evidence_module.require_independent_milestone(
        crosswalk_candidate, no_archive, identities
    )
    assert getattr(refused, "check", "") == "project_identity_unresolved"

    missing_root = tmp_path / "missing-body"
    missing = _archive_crosswalk(
        missing_root,
        key,
        crosswalk_candidate.candidate_id,
        "fdi_projects:project:1001",
        direct_link.review_reference,
    )
    missing.path.unlink()
    refused = evidence_module.require_independent_milestone(
        crosswalk_candidate,
        replace(linked, crosswalk_sha256=missing.sha256, crosswalk=missing),
        identities,
    )
    assert getattr(refused, "check", "") == "project_identity_unresolved"

    tampered = _archive_crosswalk(
        tmp_path / "tampered",
        key,
        crosswalk_candidate.candidate_id,
        "fdi_projects:project:1001",
        direct_link.review_reference,
    )
    tampered.path.write_bytes(b"invented crosswalk substitution")
    refused = evidence_module.require_independent_milestone(
        crosswalk_candidate,
        replace(linked, crosswalk_sha256=tampered.sha256, crosswalk=tampered),
        identities,
    )
    assert getattr(refused, "check", "") == "project_identity_unresolved"

    wrong = _archive_crosswalk(
        tmp_path / "wrong-mapping",
        key,
        crosswalk_candidate.candidate_id,
        "fdi_projects:project:1002",
        direct_link.review_reference,
    )
    refused = evidence_module.require_independent_milestone(
        crosswalk_candidate,
        replace(linked, crosswalk_sha256=wrong.sha256, crosswalk=wrong),
        identities,
    )
    assert getattr(refused, "check", "") == "project_identity_unresolved"


def test_project_rows_and_assertions_must_match_archived_parser(
    tmp_path: Path,
) -> None:
    """F3: caller substitutions cannot change values beside unchanged bytes."""
    adapter = getattr(evidence_module, "build_cache_evidence", None)
    assert callable(adapter), "the archive-backed project parser is absent"
    from custodian.tests.investment_fixtures import invented_record

    cache = tmp_path / "cache"
    identity = _archive_dashboard(
        cache, "2026-11-14", (invented_record(project_id=1001),)
    )
    selection = evidence_contracts.ProjectArchiveSelection(
        "fdi_projects", identity, {"scope": "invented_substitution"}
    )
    projection = adapter(
        cache, projects=(selection,), milestones=(), expected=(), attempts=()
    )
    snapshot = projection.snapshots[0]
    row = snapshot.rows[0]
    for planted in (
        replace(snapshot, rows=({**row, "capex_value": "99.5"},)),
        replace(snapshot, rows=({**row, "announced": "2025-01-01"},)),
        replace(
            snapshot,
            correction=SourceAssertion("true", "source_flag", ""),
        ),
        replace(snapshot, rows=({**row, "terms_sha256": "cd" * 32},)),
    ):
        refused = build_project_evidence((planted,))
        assert getattr(refused, "check", "") == "invalid_evidence_metadata"


def test_milestone_assertions_and_lineage_must_match_archived_parser(
    tmp_path: Path,
) -> None:
    """F3: milestone dates, correction flags and terms are receipt-bound."""
    candidate, link = _valid_milestone_parts(tmp_path)
    identities = frozenset({"fdi_projects:project:1001"})
    for planted in (
        replace(
            candidate,
            observation=SourceAssertion("2026-11-14", "day", ""),
        ),
        replace(candidate, correction=SourceAssertion("true", "source_flag", "")),
        replace(
            candidate,
            source_chain={**candidate.source_chain, "terms_sha256": "cd" * 32},
        ),
    ):
        refused = evidence_module.require_independent_milestone(
            planted, link, identities
        )
        assert getattr(refused, "check", "") == "invalid_evidence_metadata"


def test_coordinated_project_sidecar_and_row_substitution_is_refused(
    tmp_path: Path,
) -> None:
    """F3 round 2: caller-held lineage cannot replace the verified receipt."""
    project = _project_snapshot(
        tmp_path, day="2026-11-14", capex="12.5", marker="receipt-substitution"
    )
    original_body = project.snapshot.path.read_bytes()
    substituted_terms = "cd" * 32
    planted = replace(
        project,
        snapshot=replace(
            project.snapshot,
            sidecar={**project.snapshot.sidecar, "terms_sha256": substituted_terms},
        ),
        rows=({**project.rows[0], "terms_sha256": substituted_terms},),
    )
    refused = build_project_evidence((planted,))
    assert getattr(refused, "check", "") == "invalid_evidence_metadata"
    assert project.snapshot.path.read_bytes() == original_body


def test_coordinated_milestone_sidecar_and_candidate_substitution_is_refused(
    tmp_path: Path,
) -> None:
    """F3 round 2: a candidate and its mutable sidecar cannot collude."""
    candidate, link = _valid_milestone_parts(tmp_path)
    original_body = candidate.snapshot.path.read_bytes()
    substituted_terms = "cd" * 32
    planted = replace(
        candidate,
        snapshot=replace(
            candidate.snapshot,
            sidecar={**candidate.snapshot.sidecar, "terms_sha256": substituted_terms},
        ),
        source_chain={**candidate.source_chain, "terms_sha256": substituted_terms},
    )
    refused = evidence_module.require_independent_milestone(
        planted, link, frozenset({"fdi_projects:project:1001"})
    )
    assert getattr(refused, "check", "") == "invalid_evidence_metadata"
    assert candidate.snapshot.path.read_bytes() == original_body


def test_project_receipt_tamper_is_refused_with_unchanged_body(
    tmp_path: Path,
) -> None:
    """F3 round 2: project validation rereads and authenticates the receipt."""
    project = _project_snapshot(
        tmp_path, day="2026-11-14", capex="12.5", marker="receipt-tamper"
    )
    original_body = project.snapshot.path.read_bytes()
    project.snapshot.receipt_path.write_bytes(
        (
            json.dumps(
                {**project.snapshot.sidecar, "terms_sha256": "cd" * 32},
                sort_keys=True,
            )
            + "\n"
        ).encode()
    )
    with pytest.raises(SnapshotError, match="snapshot_hash_mismatch"):
        build_project_evidence((project,))
    assert project.snapshot.path.read_bytes() == original_body


def test_milestone_receipt_tamper_is_refused_with_unchanged_body(
    tmp_path: Path,
) -> None:
    """F3 round 2: milestone validation rereads and authenticates the receipt."""
    candidate, link = _valid_milestone_parts(tmp_path)
    original_body = candidate.snapshot.path.read_bytes()
    candidate.snapshot.receipt_path.write_bytes(
        (
            json.dumps(
                {**candidate.snapshot.sidecar, "terms_sha256": "cd" * 32},
                sort_keys=True,
            )
            + "\n"
        ).encode()
    )
    with pytest.raises(SnapshotError, match="snapshot_hash_mismatch"):
        evidence_module.require_independent_milestone(
            candidate, link, frozenset({"fdi_projects:project:1001"})
        )
    assert candidate.snapshot.path.read_bytes() == original_body


def test_parser_snapshot_keeps_geography_per_project_row(tmp_path: Path) -> None:
    """F4: two locations and an unstated location survive independently."""
    adapter = getattr(evidence_module, "build_cache_evidence", None)
    assert callable(adapter), "the parser-made snapshot adapter is absent"
    from custodian.tests.investment_fixtures import invented_record

    records = (
        invented_record(project_id=1001, project_address="Invented Bay"),
        invented_record(project_id=1002, project_address="Invented Cove"),
        invented_record(project_id=1003, project_address=""),
    )
    cache = tmp_path / "cache"
    identity = _archive_dashboard(cache, "2026-11-14", records)
    coverage = {"scope": "invented_three_location_snapshot"}
    selection = evidence_contracts.ProjectArchiveSelection(
        "fdi_projects", identity, coverage
    )
    projection = adapter(
        cache, projects=(selection,), milestones=(), expected=(), attempts=()
    )
    assert projection.snapshots[0].coverage == coverage
    revisions = {row.project_id: row for row in projection.evidence.revisions}
    assert revisions["1001"].geography == "Invented Bay"
    assert revisions["1002"].geography == "Invented Cove"
    assert revisions["1003"].geography is None
    assert revisions["1003"].geography_absence_reason == "not_stated_by_source"


def test_registration_cannot_substitute_another_sources_archive(
    tmp_path: Path,
) -> None:
    """F5: source, key, kind and identity all bind a registration."""
    project = _project_snapshot(
        tmp_path, day="2026-11-14", capex="12.5", marker="first"
    )
    expected = (
        evidence_contracts.ExpectedInput("other_source", "fdi_projects", "project"),
    )
    attempts = (
        evidence_contracts.FetchAttempt(
            "other_source", "fdi_projects", "success", project.identity, ""
        ),
    )
    evidence = build_project_evidence((project,))
    refused = evidence_module.audit_project_evidence(
        expected, evidence, attempts, snapshots=(project,)
    )
    assert getattr(refused, "check", "") == "evidence_audit_incomplete"

    wrong_kind = evidence_module.audit_project_evidence(
        (
            evidence_contracts.ExpectedInput(
                "fdi_projects", "fdi_projects", "milestone"
            ),
        ),
        evidence,
        (
            evidence_contracts.FetchAttempt(
                "fdi_projects", "fdi_projects", "success", project.identity, ""
            ),
        ),
        snapshots=(project,),
    )
    assert getattr(wrong_kind, "check", "") == "evidence_audit_incomplete"

    candidate, link = _valid_milestone_parts(tmp_path)
    with_milestone = build_project_evidence((project,), (candidate,), (link,))
    milestone_expected = (
        evidence_contracts.ExpectedInput(
            "other_source", "invented_milestones", "milestone"
        ),
    )
    milestone_attempt = evidence_contracts.FetchAttempt(
        "other_source",
        "invented_milestones",
        "success",
        candidate.snapshot_identity,
        "",
    )
    refused = evidence_module.audit_project_evidence(
        milestone_expected,
        with_milestone,
        (milestone_attempt,),
        snapshots=(project,),
    )
    assert getattr(refused, "check", "") == "evidence_audit_incomplete"

    milestone_kind = evidence_module.audit_project_evidence(
        (
            evidence_contracts.ExpectedInput(
                "invented_milestones", "invented_milestones", "project"
            ),
        ),
        with_milestone,
        (
            evidence_contracts.FetchAttempt(
                "invented_milestones",
                "invented_milestones",
                "success",
                candidate.snapshot_identity,
                "",
            ),
        ),
        snapshots=(project,),
    )
    assert getattr(milestone_kind, "check", "") == "evidence_audit_incomplete"


def test_nonempty_archived_dashboard_rejects_omitted_rows(tmp_path: Path) -> None:
    """F8: empty supplied rows cannot erase a nonempty verified archive."""
    project = _project_snapshot(
        tmp_path, day="2026-11-14", capex="12.5", marker="omitted-row"
    )
    empty = replace(project, rows=())
    refused = evidence_module.audit_project_evidence(
        (evidence_contracts.ExpectedInput("fdi_projects", "fdi_projects", "project"),),
        evidence_contracts.ProjectEvidence(()),
        (
            evidence_contracts.FetchAttempt(
                "fdi_projects", "fdi_projects", "success", empty.identity, ""
            ),
        ),
        snapshots=(empty,),
    )
    assert getattr(refused, "check", "") == "evidence_audit_incomplete"


def test_empty_milestone_archive_satisfies_its_own_registration(
    tmp_path: Path,
) -> None:
    """F8: the milestone parser genuinely supports an empty archived page."""
    cache = tmp_path / "cache"
    shape = _milestone_shape()
    envelope = _milestone_envelope()
    body = b'{"milestones": []}\n'
    sidecar = {
        "source_id": envelope.source_id,
        "key": envelope.source_id,
        "retrieved_utc": envelope.retrieved_utc,
        "publisher": envelope.publisher,
        "fetch_url": envelope.page_url,
        "licence_id": envelope.licence_id,
        "licence_basis": envelope.licence_basis,
        "decision_record": envelope.decision_record,
        "terms_sha256": envelope.terms_sha256,
        "terms_url": envelope.terms_url,
        "method": envelope.method,
        "method_version": envelope.method_version,
    }
    archived = publish_snapshot(cache / envelope.source_id, "json", body, sidecar)
    projection = evidence_module.build_cache_evidence(
        cache,
        projects=(),
        milestones=(
            evidence_contracts.MilestoneArchiveSelection(
                envelope.source_id,
                archived.sha256,
                shape,
                envelope,
                (),
                "",
            ),
        ),
        expected=(
            evidence_contracts.ExpectedInput(
                envelope.source_id, envelope.source_id, "milestone"
            ),
        ),
        attempts=(
            evidence_contracts.FetchAttempt(
                envelope.source_id,
                envelope.source_id,
                "success",
                archived.sha256,
                "",
            ),
        ),
    )
    assert not hasattr(projection, "check")
    assert projection.evidence.milestones == ()
    assert projection.audit.entries == ()


def test_dashboard_parser_still_refuses_an_empty_project_batch(
    tmp_path: Path,
) -> None:
    """F8: empty milestone coverage does not relax the dashboard parser."""
    cache = tmp_path / "cache"
    identity = _archive_dashboard(cache, "2026-11-14", ())
    snapshot = read_snapshot(cache / "fdi_projects", identity)
    refused = evidence_module._parse_project_snapshot(snapshot, coverage={})
    assert getattr(refused, "check", "") == "schema_missing"


def test_standalone_audit_rereads_missing_and_tampered_archives(
    tmp_path: Path,
) -> None:
    """F8: registration matching alone never authenticates archive contents."""
    for plant in ("missing", "tampered"):
        project = _project_snapshot(
            tmp_path / plant,
            day="2026-11-14",
            capex="12.5",
            marker=plant,
        )
        archive = evidence_contracts.VerifiedArchive(
            "fdi_projects",
            "fdi_projects",
            "project",
            project.identity,
            project.snapshot,
        )
        arguments = {
            "expected": (
                evidence_contracts.ExpectedInput(
                    "fdi_projects", "fdi_projects", "project"
                ),
            ),
            "evidence": build_project_evidence((project,)),
            "attempts": (
                evidence_contracts.FetchAttempt(
                    "fdi_projects", "fdi_projects", "success", project.identity, ""
                ),
            ),
            "archives": (archive,),
        }
        intact = evidence_module.audit_project_evidence(**arguments)
        assert not hasattr(intact, "check")
        if plant == "missing":
            project.snapshot.path.unlink()
        else:
            project.snapshot.path.write_bytes(b"invented audit substitution")
        with pytest.raises(SnapshotError, match=r"snapshot_(missing|hash_mismatch)"):
            evidence_module.audit_project_evidence(**arguments)


def test_evidence_report_uses_only_registry_keys_and_closed_reasons() -> None:
    """F6: record text and identifier-shaped keys or reasons are refused."""
    from eii_custodian.publicdata.fetch.report import evidence_line

    for key in (
        "invented_loom_works",
        "fdi_projects_extra",
        "a" + "1" * 8,
        "a" + "1" * 11,
    ):
        with pytest.raises(ValueError, match=r"^unsafe_report$"):
            evidence_line(key, "failed", "fetch_failed")
    for reason in (
        "invented_loom_works",
        "unknown_reason",
        "a" + "1" * 8,
        "a" + "1" * 11,
    ):
        with pytest.raises(ValueError, match=r"^unsafe_report$"):
            evidence_line("fdi_projects", "failed", reason)


def test_report_digit_run_guard_is_reached_for_registered_keys() -> None:
    """F9: registry membership cannot short-circuit the key digit-run guard."""
    from eii_custodian.publicdata.fetch.report import evidence_line

    for digits in ("1" * 8, "1" * 11):
        key = "a" + digits
        with pytest.raises(ValueError, match=r"^unsafe_report$"):
            evidence_line(
                key,
                "failed",
                "fetch_failed",
                registry_keys=frozenset({key}),
            )


def test_report_digit_run_guard_is_reached_for_otherwise_closed_reasons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F9: the reason digit-run guard is exercised past vocabulary membership."""
    from eii_custodian.publicdata.fetch import report

    for digits in ("1" * 8, "1" * 11):
        reason = "a" + digits
        monkeypatch.setattr(
            report, "_EVIDENCE_REASONS", frozenset({*report._EVIDENCE_REASONS, reason})
        )
        with pytest.raises(ValueError, match=r"^unsafe_report$"):
            report.evidence_line(
                "fdi_projects",
                "failed",
                reason,
                registry_keys=frozenset({"fdi_projects"}),
            )


def test_crosswalk_rejects_mismatched_registry_key(tmp_path: Path) -> None:
    """F9: the archived crosswalk key must equal the reviewed link key."""
    candidate, link = _crosswalk_guard_case(tmp_path)
    refused = evidence_module.require_independent_milestone(
        candidate,
        replace(link, crosswalk_key="review/other_crosswalk"),
        frozenset({"fdi_projects:project:1001"}),
    )
    assert getattr(refused, "check", "") == "project_identity_unresolved"


def test_crosswalk_rejects_mismatched_receipt_review_reference(
    tmp_path: Path,
) -> None:
    """F9: the verified receipt must carry the link's review reference."""
    candidate, link = _crosswalk_guard_case(
        tmp_path, receipt_review_reference="invented-other-review"
    )
    refused = evidence_module.require_independent_milestone(
        candidate, link, frozenset({"fdi_projects:project:1001"})
    )
    assert getattr(refused, "check", "") == "project_identity_unresolved"


def test_crosswalk_rejects_mismatched_body_review_reference(
    tmp_path: Path,
) -> None:
    """F9: the verified body must carry the link's review reference."""
    candidate, link = _crosswalk_guard_case(
        tmp_path, body_review_reference="invented-other-review"
    )
    refused = evidence_module.require_independent_milestone(
        candidate, link, frozenset({"fdi_projects:project:1001"})
    )
    assert getattr(refused, "check", "") == "project_identity_unresolved"


def test_crosswalk_rejects_duplicate_candidate_mappings(tmp_path: Path) -> None:
    """F9: exactly one archived mapping may name a milestone candidate."""
    candidate, link = _crosswalk_guard_case(tmp_path, duplicate_mapping=True)
    refused = evidence_module.require_independent_milestone(
        candidate, link, frozenset({"fdi_projects:project:1001"})
    )
    assert getattr(refused, "check", "") == "project_identity_unresolved"


def test_crosswalk_rejects_an_actually_missing_receipt_file(tmp_path: Path) -> None:
    """F9: a supplied snapshot object cannot substitute for its receipt file."""
    candidate, link = _crosswalk_guard_case(tmp_path)
    link.crosswalk.receipt_path.unlink()
    refused = evidence_module.require_independent_milestone(
        candidate, link, frozenset({"fdi_projects:project:1001"})
    )
    assert getattr(refused, "check", "") == "project_identity_unresolved"


def _crosswalk_guard_case(
    root: Path,
    *,
    receipt_review_reference: str | None = None,
    body_review_reference: str | None = None,
    duplicate_mapping: bool = False,
):
    candidate, direct_link = _valid_milestone_parts(root)
    crosswalk_candidate = _milestone_candidate(
        root,
        evidence_module.parse_milestone_page,
        candidate.shape,
        _milestone_envelope(),
        independence="independent_report",
        marker="guard-crosswalk",
        direct=False,
    )
    key = "review/milestone_crosswalk"
    archived = _archive_crosswalk(
        root / "crosswalk-case",
        key,
        crosswalk_candidate.candidate_id,
        "fdi_projects:project:1001",
        direct_link.review_reference,
        receipt_review_reference=receipt_review_reference,
        body_review_reference=body_review_reference,
        duplicate_mapping=duplicate_mapping,
    )
    link = replace(
        direct_link,
        candidate_id=crosswalk_candidate.candidate_id,
        crosswalk_sha256=archived.sha256,
        crosswalk_key=key,
        crosswalk=archived,
    )
    return crosswalk_candidate, link


def test_assertion_precision_equals_parsed_granularity() -> None:
    """F7: every mismatched year/month/day declaration is refused."""
    values = {"year": "2026", "month": "2026-11", "day": "2026-11-14"}
    for actual, value in values.items():
        assertion = SourceAssertion(value, actual, "")
        assert evidence_module._valid_assertion(assertion)
        assert evidence_module._row_observation({"announced": value}) == assertion
        for declared in values.keys() - {actual}:
            assertion = SourceAssertion(value, declared, "")
            assert not evidence_module._valid_assertion(assertion)


def _archive_dashboard(
    cache: Path, day: str, records: tuple[dict[str, object], ...]
) -> str:
    from custodian.tests.investment_fixtures import dashboard_page

    body = dashboard_page(records)
    retrieved = f"{day}T08:00:00Z"
    sidecar = {
        "source_id": "fdi_projects",
        "key": "fdi_projects",
        "retrieved_utc": retrieved,
        "publisher": "Invented public publisher",
        "fetch_url": "https://dashboard.invalid/",
        "licence_id": "invented-public-terms",
        "licence_basis": "owner_decision",
        "decision_record": "invented-review",
        "terms_sha256": "ab" * 32,
        "terms_url": "https://terms.invalid/terms",
        "method": "eii_custodian.publicdata.investment_parse.parse_fdi",
        "method_version": "1",
    }
    archived = publish_snapshot(cache / "fdi_projects", "html", body, sidecar)
    return archived.sha256


def _archive_crosswalk(
    root: Path,
    key: str,
    candidate_id: str,
    project_identity: str,
    review_reference: str,
    *,
    receipt_review_reference: str | None = None,
    body_review_reference: str | None = None,
    duplicate_mapping: bool = False,
):
    mapping = {
        "candidate_id": candidate_id,
        "project_identity": project_identity,
        "independence": "independent_report",
    }
    mappings = [mapping, mapping] if duplicate_mapping else [mapping]
    body = (
        json.dumps(
            {
                "schema_version": "reviewed_milestone_crosswalk.v1",
                "review_reference": body_review_reference or review_reference,
                "mappings": mappings,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    sidecar = {
        "source_id": "independent_milestone_review",
        "key": key,
        "retrieved_utc": "2026-11-15T08:00:00Z",
        "review_reference": receipt_review_reference or review_reference,
    }
    directory = root / "cache" / key
    published = publish_snapshot(directory, "json", body, sidecar)
    return read_snapshot(directory, published.sha256)


def _milestone_shape():
    return evidence_contracts.MilestoneShape(
        "invented-independent-milestones-v1",
        frozenset(
            {
                "milestone_id",
                "project_source_id",
                "project_id",
                "status",
                "observation",
                "publication",
                "correction",
                "geography",
                "independence",
            }
        ),
        True,
    )


def _milestone_envelope() -> SourceEnvelope:
    return SourceEnvelope(
        source_id="invented_milestones",
        publisher="Invented independent publisher",
        page_url="https://milestones.invalid/invented-start",
        licence_id="invented-public-terms",
        licence_basis="owner_decision",
        decision_record="invented-review",
        terms_sha256="ab" * 32,
        terms_url="https://terms.invalid/terms",
        retrieved_utc="2026-11-15T08:00:00Z",
        page_sha256="",
        method="eii_custodian.publicdata.investment_evidence.parse_milestone_page",
        method_version="1",
    )
