"""Mutation survivors: exact archive, revision and audit evidence contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.investment_fixtures import (
    DASHBOARD_URL,
    dashboard_page,
    invented_record,
)

import eii_custodian.publicdata.investment_build as investment_build
import eii_custodian.publicdata.investment_evidence as evidence
from eii_custodian.publicdata.fetch.snapshots import (
    Snapshot,
    SnapshotError,
    publish_snapshot,
    read_snapshot,
)
from eii_custodian.publicdata.investment_contracts import (
    InvestmentFailure,
    MilestoneArchiveSelection,
    MilestoneShape,
    ProjectArchiveSelection,
    ProjectSnapshot,
    ReviewedMilestoneLink,
    SourceAssertion,
    SourceEnvelope,
)

SOURCE = "invented_milestones"
PROJECT = "fdi_projects"
PROJECT_IDENTITY = "fdi_projects:project:1001"
URL = "https://milestones.invalid/invented"
TERMS = "https://terms.invalid/terms"
METHOD = "eii_custodian.publicdata.investment_evidence.parse_milestone_page"
UNKNOWN = SourceAssertion(None, "", "not_stated_by_source")
FIELDS = frozenset(
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
)


def failure(source: str, url: str, check: str, expected: str, observed: str):
    return InvestmentFailure(1, source, url, check, expected, observed)


def shape() -> MilestoneShape:
    return MilestoneShape("SYN-MILESTONE-SHAPE-v1", FIELDS, True)


def envelope() -> SourceEnvelope:
    return SourceEnvelope(
        SOURCE,
        "Invented independent publisher",
        URL,
        "invented-public-terms",
        "owner_decision",
        "invented-review",
        "ab" * 32,
        TERMS,
        "2026-11-15T08:00:00Z",
        hashlib.sha256(milestone_body()).hexdigest(),
        METHOD,
        "1",
    )


def milestone_row(
    *,
    marker: str = "independent",
    direct: bool = True,
    independence: str = "independent_report",
) -> dict[str, object]:
    stated = {"value": "2026-11-13", "precision": "day", "absence_reason": ""}
    return {
        "milestone_id": f"SYN-MILESTONE-{marker}",
        "project_source_id": PROJECT if direct else None,
        "project_id": "1001" if direct else None,
        "status": "construction_started",
        "observation": dict(stated),
        "publication": dict(stated),
        "correction": {
            "value": "false",
            "precision": "source_flag",
            "absence_reason": "",
        },
        "geography": "Invented Bay",
        "independence": independence,
    }


def milestone_body(rows: object | None = None) -> bytes:
    value = [milestone_row()] if rows is None else rows
    return (json.dumps({"milestones": value}, sort_keys=True) + "\n").encode()


def project(
    root: Path,
    *,
    records: tuple[dict[str, object], ...] | None = None,
    day: str = "2026-11-14",
    coverage: dict[str, object] | None = None,
    pending_terms: bool = False,
) -> ProjectSnapshot:
    rows = (invented_record(project_id=1001),) if records is None else records
    body = dashboard_page(rows)
    side = {
        "source_id": PROJECT,
        "key": PROJECT,
        "retrieved_utc": f"{day}T08:00:00Z",
        "publisher": "Invented public publisher",
        "fetch_url": DASHBOARD_URL,
        "licence_id": "invented-public-terms",
        "licence_basis": "owner_decision",
        "decision_record": "invented-review",
        "terms_sha256": "" if pending_terms else "ab" * 32,
        "terms_url": "" if pending_terms else TERMS,
        "method": "eii_custodian.publicdata.investment_parse.parse_fdi",
        "method_version": "1",
    }
    directory = root / "cache" / PROJECT
    archived = publish_snapshot(directory, "html", body, side)
    parsed = evidence._parse_project_snapshot(
        read_snapshot(directory, archived.sha256), coverage=coverage or {}
    )
    assert isinstance(parsed, ProjectSnapshot)
    return parsed


def candidate(
    root: Path,
    *,
    body: bytes | None = None,
    day: str = "2026-11-15",
):
    page = milestone_body() if body is None else body
    digest = hashlib.sha256(page).hexdigest()
    base = replace(envelope(), page_sha256=digest, retrieved_utc=f"{day}T08:00:00Z")
    parsed = evidence.parse_milestone_page(page, shape(), base)
    assert not isinstance(parsed, InvestmentFailure)
    side = {
        "source_id": SOURCE,
        "key": SOURCE,
        "retrieved_utc": base.retrieved_utc,
        "publisher": base.publisher,
        "fetch_url": base.page_url,
        "licence_id": base.licence_id,
        "licence_basis": base.licence_basis,
        "decision_record": base.decision_record,
        "terms_sha256": base.terms_sha256,
        "terms_url": base.terms_url,
        "method": base.method,
        "method_version": base.method_version,
    }
    directory = root / "cache" / SOURCE
    publish_snapshot(directory, "json", page, side)
    return replace(parsed[0], snapshot=read_snapshot(directory, digest))


def link_for(row, *, project_identity: str = PROJECT_IDENTITY) -> ReviewedMilestoneLink:
    return ReviewedMilestoneLink(
        row.candidate_id,
        project_identity,
        "independent_report",
        True,
        "SYN-REVIEW-INDEPENDENT",
        "",
    )


def milestone_selection(row, links=()) -> MilestoneArchiveSelection:
    return MilestoneArchiveSelection(
        SOURCE, row.snapshot_identity, shape(), envelope(), tuple(links), ""
    )


def crosswalk(
    root: Path,
    row,
    link: ReviewedMilestoneLink,
    *,
    document: object | None = None,
) -> Snapshot:
    key = "review/milestone_crosswalk"
    value = {
        "schema_version": "reviewed_milestone_crosswalk.v1",
        "review_reference": link.review_reference,
        "mappings": [
            {
                "candidate_id": row.candidate_id,
                "project_identity": link.project_identity,
                "independence": "independent_report",
            }
        ],
    }
    body = (
        json.dumps(value if document is None else document, sort_keys=True) + "\n"
    ).encode()
    side = {
        "source_id": "independent_milestone_review",
        "key": key,
        "retrieved_utc": "2026-11-15T08:00:00Z",
        "review_reference": link.review_reference,
    }
    directory = root / "cache" / key
    published = publish_snapshot(directory, "json", body, side)
    return read_snapshot(directory, published.sha256)


def crosswalk_candidate(root: Path):
    row = candidate(root, body=milestone_body([milestone_row(direct=False)]))
    link = link_for(row)
    archived = crosswalk(root, row, link)
    linked = replace(
        link,
        crosswalk_sha256=archived.sha256,
        crosswalk_key="review/milestone_crosswalk",
        crosswalk=archived,
    )
    return row, linked


def test_cache_raw_identity_mismatch_is_exact(tmp_path: Path, monkeypatch) -> None:
    item = project(tmp_path)
    monkeypatch.setattr(
        evidence,
        "read_snapshot",
        lambda *_args: replace(item.snapshot, sha256="cd" * 32),
    )
    result = evidence.build_cache_evidence(
        tmp_path,
        projects=(ProjectArchiveSelection(PROJECT, item.identity, {}),),
        milestones=(),
        expected=(),
        attempts=(),
    )
    assert result == failure(
        PROJECT,
        DASHBOARD_URL,
        "invalid_evidence_metadata",
        "raw snapshot identity",
        "mismatch",
    )


@pytest.mark.parametrize("changed", ["key", "source_id"])
def test_cache_milestone_registration_checks_each_binding(
    tmp_path: Path, changed: str
) -> None:
    row = candidate(tmp_path)
    side = {**row.snapshot.sidecar, changed: "invented_other"}
    directory = tmp_path / "other" / SOURCE
    archived = publish_snapshot(directory, "json", row.snapshot.body, side)
    selection = replace(milestone_selection(row), identity=archived.sha256)
    result = evidence.build_cache_evidence(
        directory.parent,
        projects=(),
        milestones=(selection,),
        expected=(),
        attempts=(),
    )
    assert result == failure(
        str(side["source_id"]),
        URL,
        "invalid_evidence_metadata",
        "milestone registration",
        "mismatch",
    )


def test_cache_missing_crosswalk_keeps_verified_link(tmp_path: Path) -> None:
    row = candidate(tmp_path, body=milestone_body([milestone_row(direct=False)]))
    base_link = link_for(row)
    archived = crosswalk(tmp_path, row, base_link)
    linked = replace(
        base_link,
        crosswalk_sha256=archived.sha256,
        crosswalk_key="review/milestone_crosswalk",
        crosswalk=None,
    )
    item = project(tmp_path)
    selection = replace(
        milestone_selection(row, (linked,)), crosswalk_key="review/milestone_crosswalk"
    )
    result = evidence.build_cache_evidence(
        tmp_path / "cache",
        projects=(ProjectArchiveSelection(PROJECT, item.identity, {}),),
        milestones=(selection,),
        expected=(),
        attempts=(),
    )
    assert not isinstance(result, InvestmentFailure)
    assert result.evidence.milestones[0].evidence_status == "validated"


def test_cache_reads_crosswalk_and_retains_following_links(tmp_path: Path) -> None:
    first, linked = crosswalk_candidate(tmp_path)
    second = candidate(tmp_path, body=milestone_body([milestone_row(marker="second")]))
    second_link = link_for(second)
    item = project(tmp_path)
    first_selection = replace(
        milestone_selection(first, (linked,)),
        crosswalk_key="review/milestone_crosswalk",
    )
    result = evidence.build_cache_evidence(
        tmp_path / "cache",
        projects=(ProjectArchiveSelection(PROJECT, item.identity, {}),),
        milestones=(first_selection, milestone_selection(second, (second_link,))),
        expected=(),
        attempts=(),
    )
    assert not isinstance(result, InvestmentFailure)
    assert [row.evidence_status for row in result.evidence.milestones] == [
        "validated",
        "validated",
    ]
    assert result.archives[-1].milestone_shape == shape()
    assert result.snapshots == (item,)
    assert [archive.identity for archive in result.archives] == [
        item.identity,
        first.snapshot_identity,
        second.snapshot_identity,
    ]


def test_cache_rejected_crosswalk_does_not_skip_later_direct_link(
    tmp_path: Path,
) -> None:
    first_row = milestone_row(direct=False)
    second_row = milestone_row(marker="second")
    body = milestone_body([first_row, second_row])
    first = candidate(tmp_path, body=body)
    item = project(tmp_path)
    missing = replace(
        link_for(first),
        crosswalk_sha256="cd" * 32,
        crosswalk_key="review/milestone_crosswalk",
        crosswalk=None,
    )
    direct = replace(
        link_for(first), candidate_id=f"{SOURCE}:milestone:SYN-MILESTONE-second"
    )
    selection = replace(
        milestone_selection(first, (missing, direct)),
        crosswalk_key="review/milestone_crosswalk",
    )
    result = evidence.build_cache_evidence(
        tmp_path / "cache",
        projects=(ProjectArchiveSelection(PROJECT, item.identity, {}),),
        milestones=(selection,),
        expected=(),
        attempts=(),
    )
    assert not isinstance(result, InvestmentFailure)
    assert [row.evidence_status for row in result.evidence.milestones] == [
        "missing_evidence",
        "validated",
    ]
    assert result.evidence.milestones[1].project_identity == PROJECT_IDENTITY


def test_project_archive_metadata_refusals_are_exact(tmp_path: Path) -> None:
    item = project(tmp_path)
    cases = (
        ({"source_id": "invented_other"}, "invented_other"),
        ({"key": ""}, PROJECT),
        ({"key": 3}, PROJECT),
        ({"fetch_url": ""}, PROJECT),
        ({"fetch_url": 3}, PROJECT),
    )
    for changed, source in cases:
        planted = replace(item.snapshot, sidecar={**item.snapshot.sidecar, **changed})
        result = evidence._parse_project_snapshot(planted, coverage={})
        changed_url = changed.get("fetch_url", DASHBOARD_URL)
        url = changed_url if isinstance(changed_url, str) else ""
        assert result == failure(
            source,
            url,
            "invalid_evidence_metadata",
            "project archive metadata",
            "mismatch",
        )


def test_project_archive_forwards_url_and_parser_version(
    tmp_path: Path, monkeypatch
) -> None:
    item = project(tmp_path)
    actual_load = investment_build.load_source_spec
    actual_parse = evidence.parse_fdi

    def loading(source_id: str, *, url: str):
        assert (source_id, url) == (PROJECT, DASHBOARD_URL)
        return actual_load(source_id, url=url)

    def parsing(body, dashboard, base):
        assert base.method == "eii_custodian.publicdata.investment_parse.parse_fdi"
        assert base.method_version == "1"
        return actual_parse(body, dashboard, base)

    monkeypatch.setattr(investment_build, "load_source_spec", loading)
    monkeypatch.setattr(evidence, "parse_fdi", parsing)
    result = evidence._parse_project_snapshot(item.snapshot, coverage={})
    assert isinstance(result, ProjectSnapshot)


def test_project_archive_missing_dashboard_shape_is_exact(
    tmp_path: Path, monkeypatch
) -> None:
    item = project(tmp_path)
    spec = investment_build.load_source_spec(PROJECT, url=DASHBOARD_URL)
    assert not isinstance(spec, InvestmentFailure)
    monkeypatch.setattr(
        investment_build,
        "load_source_spec",
        lambda *_args, **_kwargs: replace(spec, dashboard=None),
    )
    result = evidence._parse_project_snapshot(item.snapshot, coverage={})
    assert result == failure(
        PROJECT,
        DASHBOARD_URL,
        "invalid_evidence_metadata",
        "confirmed dashboard shape",
        "missing",
    )


def test_snapshot_envelope_normalises_and_stamps_dashboard(tmp_path: Path) -> None:
    item = project(tmp_path)
    side = {**item.snapshot.sidecar, "source_id": 7}
    result = evidence._snapshot_envelope(
        replace(item.snapshot, sidecar=side),
        "eii_custodian.publicdata.investment_parse.parse_fdi",
        "invented-version",
    )
    assert result.source_id == ""
    assert result.method == "eii_custodian.publicdata.investment_parse.parse_fdi"
    assert result.method_version == "1"


def test_snapshot_envelope_terms_fallback_gets_sidecar(
    tmp_path: Path, monkeypatch
) -> None:
    item = project(tmp_path)
    side = {**item.snapshot.sidecar, "terms_url": ""}
    monkeypatch.setattr(
        evidence, "_registry_terms_url", lambda value: TERMS if value is side else ""
    )
    result = evidence._snapshot_envelope(
        replace(item.snapshot, sidecar=side), METHOD, "1"
    )
    assert result.terms_url == TERMS


@pytest.mark.parametrize("changed", ["receipt_path", "path", "sha256"])
def test_reread_snapshot_checks_every_identity_part(
    tmp_path: Path, monkeypatch, changed: str
) -> None:
    item = project(tmp_path)
    replacement = tmp_path / "invented-other"
    value = "cd" * 32 if changed == "sha256" else replacement
    monkeypatch.setattr(
        evidence,
        "read_snapshot",
        lambda *_args: replace(item.snapshot, **{changed: value}),
    )
    with pytest.raises(SnapshotError, match=r"^snapshot_path_invalid$"):
        evidence._reread_snapshot(item.snapshot, item.identity)


def test_failure_builders_preserve_complete_diagnostics(tmp_path: Path) -> None:
    item = project(tmp_path)
    assert evidence._snapshot_failure(
        item.snapshot, "invented expected", "invented observed"
    ) == failure(
        PROJECT,
        DASHBOARD_URL,
        "invalid_evidence_metadata",
        "invented expected",
        "invented observed",
    )
    nonstring = replace(item.snapshot, sidecar={"source_id": 3, "fetch_url": 4})
    assert evidence._snapshot_failure(nonstring, "expected", "observed") == failure(
        "", "", "invalid_evidence_metadata", "expected", "observed"
    )
    assert evidence._refusal(item, "invented_check", "expected", "observed") == failure(
        PROJECT, DASHBOARD_URL, "invented_check", "expected", "observed"
    )
    assert evidence._audit_failure(PROJECT, "observed") == failure(
        PROJECT,
        "",
        "evidence_audit_incomplete",
        "every registration, revision and absence",
        "observed",
    )
