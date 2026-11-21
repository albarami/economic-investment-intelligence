"""Direct guards whose callers otherwise refuse earlier, and receipt races."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.investment_fixtures import invented_record
from custodian.tests.test_investment_evidence_survivors import (
    DASHBOARD_URL,
    METHOD,
    PROJECT,
    PROJECT_IDENTITY,
    SOURCE,
    TERMS,
    candidate,
    crosswalk_candidate,
    failure,
    link_for,
    project,
)

import eii_custodian.publicdata.investment_evidence as evidence
from eii_custodian.publicdata.fetch.snapshots import (
    SnapshotError,
    publish_snapshot,
)
from eii_custodian.publicdata.investment_contracts import (
    ObservedInvestment,
    ProjectEvidence,
)


def test_receipt_method_and_version_override_supplied_defaults(tmp_path: Path):
    row = candidate(tmp_path)
    result = evidence._receipt_lineage(
        row.snapshot, "SYN-OTHER-METHOD", "SYN-OTHER-VERSION"
    )
    assert result["method"] == METHOD
    assert result["method_version"] == "1"


@pytest.mark.parametrize("terms", ["", 3])
def test_receipt_terms_fallback_for_empty_and_wrong_type(
    tmp_path: Path, monkeypatch, terms: object
):
    row = candidate(tmp_path)
    directory = tmp_path / "SYN-TERMS" / SOURCE
    snapshot = publish_snapshot(
        directory,
        "json",
        row.snapshot.body,
        {**row.snapshot.sidecar, "terms_url": terms},
    )
    monkeypatch.setattr(evidence, "_registry_terms_url", lambda _: TERMS)
    result = evidence._receipt_lineage(snapshot, METHOD, "1")
    assert result["terms_url"] == TERMS


def test_crosswalk_receipt_filename_is_bound_even_with_matching_hash(tmp_path: Path):
    row, linked = crosswalk_candidate(tmp_path)
    supplied = replace(
        linked.crosswalk,
        receipt_path=linked.crosswalk.receipt_path.with_name("SYN-OTHER.meta.json"),
    )
    assert evidence._valid_crosswalk(row, replace(linked, crosswalk=supplied)) is False


@pytest.mark.parametrize("boundary", ["project", "milestone"])
def test_verified_body_is_checked_before_early_metadata_refusal(
    tmp_path: Path, monkeypatch, boundary: str
):
    # Simulate a file changing after the authenticated read but before use. The
    # malformed metadata makes the next refusal return without another body read.
    item = project(tmp_path) if boundary == "project" else candidate(tmp_path)
    original = evidence._reread_snapshot

    def changed_after_read(snapshot, identity):
        selected = original(snapshot, identity)
        selected.path.write_bytes(b"SYN-BODY-CHANGED-AFTER-READ")
        return selected

    monkeypatch.setattr(evidence, "_reread_snapshot", changed_after_read)
    with pytest.raises(SnapshotError, match=r"^snapshot_hash_mismatch$"):
        if boundary == "project":
            evidence._metadata_failure(replace(item, schema="SYN-INVALID"))
        else:
            evidence.require_independent_milestone(
                replace(item, source_chain={}), None, frozenset()
            )


def test_metadata_refuses_a_receipt_identity_distinct_from_content_hash(tmp_path: Path):
    item = project(tmp_path)
    directory = tmp_path / "SYN-IDENTITY" / PROJECT
    identity = "cd" * 32
    snapshot = publish_snapshot(
        directory,
        "html",
        item.snapshot.body,
        dict(item.snapshot.sidecar),
        identity=identity,
    )
    planted = replace(item, identity=identity, snapshot=snapshot)
    assert evidence._metadata_failure(planted) == failure(
        PROJECT,
        DASHBOARD_URL,
        "invalid_evidence_metadata",
        "selected snapshot identity",
        "mismatch",
    )


def test_content_key_collision_requires_stable_published_identity(
    tmp_path: Path, monkeypatch
):
    # A collision is supplied directly to the revision linker. An ordinary
    # caller's fabricated key would first fail _metadata_failure's parser check.
    first = project(tmp_path)
    second = project(
        tmp_path / "SYN-OTHER", records=(invented_record(project_id=1002),)
    )
    first = replace(first, rows=({**first.rows[0], "project_key": "SYN-COLLISION"},))
    second = replace(second, rows=({**second.rows[0], "project_key": "SYN-COLLISION"},))
    monkeypatch.setattr(
        evidence, "_metadata_failure", lambda item, *, cache=None: item.snapshot
    )
    assert evidence.build_project_evidence((first, second)) == failure(
        PROJECT,
        DASHBOARD_URL,
        "project_identity_unresolved",
        "stable source-scoped project ID",
        "changed project ID",
    )


@pytest.mark.parametrize("kind", ["announcement", "milestone", "measured"])
def test_observed_boundary_uses_kind_and_all_sources(tmp_path: Path, kind: str):
    item = project(tmp_path)
    row = candidate(tmp_path)
    sources = ("SYN-UNRELATED", PROJECT, SOURCE)
    for source in sources:
        observed = ObservedInvestment(
            PROJECT_IDENTITY, "12.5", source, kind, item.identity
        )
        result = evidence.build_project_evidence(
            (item,), (row,), (link_for(row),), observed_investment=(observed,)
        )
        check = (
            "closure_without_evidence"
            if source == "SYN-UNRELATED" and kind == "measured"
            else "announcement_as_observed"
        )
        assert result == failure(
            source, "", check, "separately archived observed-investment evidence", kind
        )


def test_missing_source_is_not_hidden_by_receipt_lineage(tmp_path: Path):
    item = project(tmp_path)
    result = evidence._refusal(item, "SYN-CHECK", "SYN-EXPECTED", "SYN-OBSERVED")
    assert result == failure(
        PROJECT, DASHBOARD_URL, "SYN-CHECK", "SYN-EXPECTED", "SYN-OBSERVED"
    )


def test_revision_linker_keeps_source_histories_separate(tmp_path: Path, monkeypatch):
    # Isolate the source-scoped linker: the current dashboard parser only accepts
    # fdi_projects, so another source otherwise refuses in _parse_project_snapshot.
    first = project(tmp_path)
    second = project(
        tmp_path / "SYN-SECOND", records=(invented_record(project_id=1002),)
    )
    second = replace(
        second,
        snapshot=replace(
            second.snapshot,
            sidecar={**second.snapshot.sidecar, "source_id": "SYN-SECOND"},
        ),
        rows=({**second.rows[0], "source_id": "SYN-SECOND"},),
    )
    monkeypatch.setattr(
        evidence, "_metadata_failure", lambda item, *, cache=None: item.snapshot
    )
    result = evidence.build_project_evidence((first, second))
    assert isinstance(result, ProjectEvidence)
    assert result.absences == ()
    assert [row.project_identity for row in result.revisions] == [
        "fdi_projects:project:1001",
        "SYN-SECOND:project:1002",
    ]
