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
    assert revision.observation.value == "2026-11-13"
    assert revision.publication.precision == "day"
    assert revision.retrieved_utc == "2026-11-14T08:00:00Z"
    assert revision.checksum == first.snapshot.sha256
    assert revision.schema == "fdi_projects.v1"
    assert revision.geography == "Invented Bay"
    assert revision.correction.value == "false"

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
        replace(first, geography=""),
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
    other = _project_snapshot(tmp_path, day="2026-11-16", capex="15.5", marker="third")
    other = replace(
        other,
        rows=({**other.rows[0], "project_id": 1002, "project_key": "fdi_" + "c" * 16},),
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
    assert getattr(refused, "check", "") == "project_identity_unresolved"

    ambiguous = replace(
        first,
        rows=(first.rows[0], {**first.rows[0], "project_key": "fdi_" + "d" * 16}),
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
    assert revision.observation.value is None
    assert revision.publication.absence_reason == "not_stated_by_source"
    assert revision.correction.value is None
    assert revision.retrieved_utc == "2026-11-14T08:00:00Z"

    for planted in (
        replace(first, geography="Invented Other Place"),
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
    link = replace(
        direct_link,
        candidate_id=crosswalk_candidate.candidate_id,
        crosswalk_sha256="cd" * 32,
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
        "stated_intent": "Invented announced intent",
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
    missing = _project_snapshot(
        tmp_path, day="2026-11-15", capex="12.5", marker="absent"
    )
    missing = replace(missing, rows=())
    returned = _project_snapshot(
        tmp_path, day="2026-11-16", capex="14.5", marker="returned"
    )
    evidence = build_project_evidence((first, missing, returned))
    assert len(evidence.revisions) == 2
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
    assert len(audited.entries) == 3
    assert [entry.coverage for entry in audited.entries] == [
        "retained_revision",
        "absent_from_snapshot",
        "retained_revision",
    ]
    assert {entry.provenance for entry in audited.entries} == {"public"}
    absence = audited.entries[1]
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
) -> ProjectSnapshot:
    body = f"invented project snapshot {marker}".encode()
    retrieved = f"{day}T08:00:00Z"
    directory = root / "cache" / "fdi_projects"
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
    published = publish_snapshot(directory, "json", body, sidecar)
    identity = published.sha256
    snapshot = read_snapshot(directory, identity)
    row = {
        "source_id": "fdi_projects",
        "project_id": 1001,
        "project_key": "fdi_" + ("a" if marker == "first" else "b") * 16,
        "capex_value": capex,
        "jobs": "40",
        "stated_intent": "Invented announced intent",
        "location_text": "Invented Bay",
        "provenance": "public",
        "publisher": sidecar["publisher"],
        "page_url": sidecar["fetch_url"],
        "licence_id": sidecar["licence_id"],
        "licence_basis": sidecar["licence_basis"],
        "decision_record": sidecar["decision_record"],
        "terms_sha256": sidecar["terms_sha256"],
        "retrieved_utc": retrieved,
        "page_sha256": identity,
        "method": sidecar["method"],
        "method_version": sidecar["method_version"],
    }
    stated = SourceAssertion("2026-11-13", "day", "")
    corrected = SourceAssertion("false", "source_flag", "")
    return ProjectSnapshot(
        identity=identity,
        snapshot=snapshot,
        rows=(row,),
        schema="fdi_projects.v1",
        geography="Invented Bay",
        observation=stated,
        publication=stated,
        correction=corrected,
    )
