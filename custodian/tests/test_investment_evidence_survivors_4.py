"""Mutation survivors: independent milestone and metadata authentication."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from custodian.tests.test_investment_evidence_survivors import (
    DASHBOARD_URL,
    PROJECT,
    PROJECT_IDENTITY,
    SOURCE,
    TERMS,
    URL,
    candidate,
    crosswalk,
    crosswalk_candidate,
    envelope,
    failure,
    link_for,
    milestone_body,
    milestone_row,
    project,
)

import eii_custodian.publicdata.investment_evidence as evidence
from eii_custodian.publicdata.fetch import registry as registry_module
from eii_custodian.publicdata.fetch.registry import RegistryError
from eii_custodian.publicdata.fetch.snapshots import publish_snapshot, read_snapshot
from eii_custodian.publicdata.investment_contracts import (
    MilestoneEvidence,
    SourceAssertion,
)


def test_require_milestone_artifact_lineage_and_public_boundary(tmp_path: Path) -> None:
    row = candidate(tmp_path)
    linked = link_for(row)
    identities = frozenset({PROJECT_IDENTITY})
    assert evidence.require_independent_milestone(
        replace(row, snapshot=None), linked, identities
    ) == failure(SOURCE, URL, "missing_artifact", "archived milestone", "missing")
    for field, check in (
        ("publisher", "missing_lineage"),
        ("method", "missing_lineage"),
    ):
        planted = replace(row, source_chain={**row.source_chain, field: ""})
        assert evidence.require_independent_milestone(
            planted, linked, identities
        ) == failure(SOURCE, URL, check, field, "absent")
    # Ruling L-1001 (S2-T30): a pending terms reading in the chain is recorded
    # truthfully and never refuses the milestone.
    pending = replace(
        row, source_chain={**row.source_chain, "terms_sha256": "", "terms_url": ""}
    )
    kept = evidence.require_independent_milestone(pending, linked, identities)
    assert not hasattr(kept, "check")
    assert kept.candidate.source_chain["terms_sha256"] == ""
    synthetic = replace(
        row, source_chain={**row.source_chain, "provenance": "synthetic"}
    )
    assert evidence.require_independent_milestone(
        synthetic, linked, identities
    ) == failure(SOURCE, URL, "provenance", "public", "not Public")
    joined = replace(
        row, source_chain={**row.source_chain, "join_key": "invented-join"}
    )
    assert evidence.require_independent_milestone(
        joined, linked, identities
    ) == failure(SOURCE, URL, "prohibited_join", "no join", "joined")


@pytest.mark.parametrize(
    "changed",
    [
        {"checksum": "cd" * 32},
        {"source_id": "invented_other"},
        {"retrieved_utc": "2026-11-16T08:00:00Z"},
    ],
)
def test_require_milestone_archive_identity_is_exact(
    tmp_path: Path, changed: dict[str, str]
) -> None:
    row = candidate(tmp_path)
    result = evidence.require_independent_milestone(
        replace(row, **changed), link_for(row), frozenset({PROJECT_IDENTITY})
    )
    assert result == failure(
        changed.get("source_id", SOURCE),
        URL,
        "invalid_evidence_metadata",
        "archived identity",
        "mismatch",
    )


def test_require_milestone_lineage_shape_and_parser_row_are_exact(
    tmp_path: Path,
) -> None:
    row = candidate(tmp_path)
    linked = link_for(row)
    identities = frozenset({PROJECT_IDENTITY})
    planted = replace(row, source_chain={**row.source_chain, "terms_sha256": "cd" * 32})
    assert evidence.require_independent_milestone(
        planted, linked, identities
    ) == failure(
        SOURCE, URL, "invalid_evidence_metadata", "receipt lineage", "mismatch"
    )
    for changed in (replace(row, shape=None), replace(row, schema="invented-other")):
        assert evidence.require_independent_milestone(
            changed, linked, identities
        ) == failure(
            SOURCE, URL, "invalid_evidence_metadata", "confirmed shape", "absent"
        )
    assert evidence.require_independent_milestone(
        replace(row, status="invented_changed"), linked, identities
    ) == failure(
        SOURCE, URL, "invalid_evidence_metadata", "archived parser row", "mismatch"
    )


def test_require_milestone_unknown_source_assertion_is_exact(tmp_path: Path) -> None:
    row_data = milestone_row()
    row_data["observation"] = {
        "value": None,
        "precision": "",
        "absence_reason": "not_stated_by_source",
    }
    row = candidate(tmp_path, body=milestone_body([row_data]))
    result = evidence.require_independent_milestone(
        row, link_for(row), frozenset({PROJECT_IDENTITY})
    )
    assert result == failure(
        SOURCE,
        URL,
        "invalid_evidence_metadata",
        "source-stated milestone metadata",
        "unknown",
    )


def test_require_milestone_review_and_independence_are_exact(tmp_path: Path) -> None:
    row = candidate(tmp_path)
    linked = link_for(row)
    identities = frozenset({PROJECT_IDENTITY})
    for changed in (
        None,
        replace(linked, reviewed=False),
        replace(linked, review_reference=""),
        replace(linked, candidate_id="invented-other"),
    ):
        assert evidence.require_independent_milestone(
            row, changed, identities
        ) == failure(
            SOURCE,
            URL,
            "project_identity_unresolved",
            "reviewed project link",
            "absent",
        )
    copied = candidate(
        tmp_path,
        body=milestone_body([milestone_row(independence="publisher_announcement")]),
    )
    assert evidence.require_independent_milestone(
        copied, link_for(copied), identities
    ) == failure(
        SOURCE, URL, "milestone_not_independent", "independent reporting", "copy"
    )
    assert evidence.require_independent_milestone(
        row, replace(linked, independence="publisher_announcement"), identities
    ) == failure(
        SOURCE, URL, "milestone_not_independent", "independent reporting", "copy"
    )


def test_direct_and_crosswalk_validation_results_are_exact(tmp_path: Path) -> None:
    row = candidate(tmp_path)
    linked = link_for(row)
    assert evidence.require_independent_milestone(
        row, linked, frozenset({PROJECT_IDENTITY})
    ) == MilestoneEvidence(row, PROJECT_IDENTITY, "validated", "")
    assert evidence.require_independent_milestone(
        row,
        replace(linked, project_identity="fdi_projects:project:1002"),
        frozenset({PROJECT_IDENTITY}),
    ) == failure(
        SOURCE,
        URL,
        "project_identity_unresolved",
        "source-ID/project-ID link or verified crosswalk",
        "mismatch",
    )
    assert evidence.require_independent_milestone(
        row, linked, frozenset({"fdi_projects:project:1002"})
    ) == failure(
        SOURCE, URL, "project_identity_unresolved", "retained project", "unmatched"
    )
    indirect, crosswalk_link = crosswalk_candidate(tmp_path / "indirect")
    assert evidence.require_independent_milestone(
        indirect, crosswalk_link, frozenset({PROJECT_IDENTITY})
    ) == MilestoneEvidence(indirect, PROJECT_IDENTITY, "validated", "")


def test_partial_direct_identity_cannot_replace_crosswalk(tmp_path: Path) -> None:
    row_data = milestone_row()
    row_data["project_id"] = None
    row = candidate(tmp_path, body=milestone_body([row_data]))
    partial_identity = "fdi_projects:project:None"
    linked = link_for(row, project_identity=partial_identity)
    result = evidence.require_independent_milestone(
        row, linked, frozenset({partial_identity})
    )
    assert result == failure(
        SOURCE,
        URL,
        "project_identity_unresolved",
        "source-ID/project-ID link or verified crosswalk",
        "mismatch",
    )


def test_crosswalk_document_shape_and_exact_mapping(tmp_path: Path) -> None:
    row = candidate(tmp_path, body=milestone_body([milestone_row(direct=False)]))
    base = link_for(row)
    valid_document = {
        "schema_version": "reviewed_milestone_crosswalk.v1",
        "review_reference": base.review_reference,
        "mappings": [
            {
                "candidate_id": row.candidate_id,
                "project_identity": PROJECT_IDENTITY,
                "independence": "independent_report",
            }
        ],
    }
    documents = [
        [],
        {"schema_version": "reviewed_milestone_crosswalk.v1"},
        {**valid_document, "schema_version": "invented-other"},
        {**valid_document, "review_reference": "invented-other"},
        {**valid_document, "mappings": {}},
        {**valid_document, "mappings": [1]},
        {**valid_document, "mappings": [{"candidate_id": row.candidate_id}]},
        {
            **valid_document,
            "mappings": [valid_document["mappings"][0], valid_document["mappings"][0]],
        },
    ]
    for document in documents:
        archived = crosswalk(tmp_path, row, base, document=document)
        linked = replace(
            base,
            crosswalk_sha256=archived.sha256,
            crosswalk_key="review/milestone_crosswalk",
            crosswalk=archived,
        )
        assert evidence._valid_crosswalk(row, linked) is False
    archived = crosswalk(tmp_path, row, base)
    linked = replace(
        base,
        crosswalk_sha256=archived.sha256,
        crosswalk_key="review/milestone_crosswalk",
        crosswalk=archived,
    )
    assert evidence._valid_crosswalk(row, linked) is True


def test_receipt_lineage_uses_only_receipt_and_supplied_defaults(
    tmp_path: Path,
) -> None:
    page = milestone_body()
    side = {
        "source_id": SOURCE,
        "key": SOURCE,
        "retrieved_utc": "2026-11-15T08:00:00Z",
        "publisher": "Invented independent publisher",
        "fetch_url": URL,
        "licence_id": "invented-public-terms",
        "licence_basis": "owner_decision",
        "decision_record": "invented-review",
        "terms_sha256": "ab" * 32,
        "terms_url": TERMS,
    }
    directory = tmp_path / "cache" / SOURCE
    archived = publish_snapshot(directory, "json", page, side)
    result = evidence._receipt_lineage(
        read_snapshot(directory, archived.sha256), "invented.method", "invented-version"
    )
    assert result == {
        "publisher": side["publisher"],
        "page_url": URL,
        "licence_id": side["licence_id"],
        "licence_basis": side["licence_basis"],
        "decision_record": side["decision_record"],
        "terms_sha256": side["terms_sha256"],
        "retrieved_utc": side["retrieved_utc"],
        "page_sha256": archived.sha256,
        "terms_url": TERMS,
        "method": "invented.method",
        "method_version": "invented-version",
    }


def test_registry_terms_url_requires_one_exact_registry_row(monkeypatch) -> None:
    entry = SimpleNamespace(
        source_id="invented_registry_source",
        key="invented_registry_key",
        publisher="Invented registry publisher",
        url="https://invented-registry.invalid/",
        licence_id="invented-registry-licence",
        licence_basis="owner_decision",
        decision_record="invented-registry-review",
        terms_url="https://invented-registry.invalid/terms",
    )
    side = {
        "source_id": entry.source_id,
        "key": entry.key,
        "publisher": entry.publisher,
        "fetch_url": entry.url,
        "licence_id": entry.licence_id,
        "licence_basis": entry.licence_basis,
        "decision_record": entry.decision_record,
    }
    monkeypatch.setattr(registry_module, "load_registry", lambda: (entry,))
    assert (
        evidence._registry_terms_url(side) == "https://invented-registry.invalid/terms"
    )
    for field in (
        "publisher",
        "fetch_url",
        "licence_id",
        "licence_basis",
        "decision_record",
        "key",
        "source_id",
    ):
        assert evidence._registry_terms_url({**side, field: "invented-other"}) == ""
    monkeypatch.setattr(registry_module, "load_registry", lambda: (entry, entry))
    assert evidence._registry_terms_url(side) == ""

    def broken():
        raise RegistryError("invented")

    monkeypatch.setattr(registry_module, "load_registry", broken)
    assert evidence._registry_terms_url(side) == ""


def test_metadata_sidecar_schema_and_assertion_refusals(tmp_path: Path) -> None:
    item = project(tmp_path)
    planted = replace(
        item,
        snapshot=replace(
            item.snapshot,
            sidecar={**item.snapshot.sidecar, "retrieved_utc": "2026-11-16T08:00:00Z"},
        ),
    )
    assert evidence.build_project_evidence((planted,)) == failure(
        PROJECT,
        DASHBOARD_URL,
        "invalid_evidence_metadata",
        "supplied receipt metadata",
        "differs from verified receipt",
    )
    assert evidence.build_project_evidence((replace(item, schema=""),)) == failure(
        PROJECT,
        DASHBOARD_URL,
        "invalid_evidence_metadata",
        "selected snapshot identity",
        "mismatch",
    )
    for field in ("observation", "publication", "correction"):
        planted = replace(item, **{field: SourceAssertion(None, "", "")})
        assert evidence.build_project_evidence((planted,)) == failure(
            PROJECT,
            DASHBOARD_URL,
            "invalid_evidence_metadata",
            "source assertion or explicit absence",
            "invalid",
        )


def test_metadata_lineage_and_row_refusals_are_exact(tmp_path: Path) -> None:
    item = project(tmp_path)
    fields = (
        "publisher",
        "page_url",
        "licence_id",
        "licence_basis",
        "decision_record",
        "retrieved_utc",
        "page_sha256",
        "method",
        "method_version",
    )
    for field in fields:
        planted = replace(item, rows=({**item.rows[0], field: ""},))
        assert evidence.build_project_evidence((planted,)) == failure(
            PROJECT, DASHBOARD_URL, "missing_lineage", field, "absent"
        )
    for field, value in (
        ("project_key", ""),
        ("project_id", ""),
        ("source_id", "invented_other"),
        ("terms_sha256", "cd" * 32),
        # Ruling L-1001: a cleared hash against a receipt that holds a reading
        # is a substituted record, not a pending one, and still fails.
        ("terms_sha256", ""),
    ):
        planted = replace(item, rows=({**item.rows[0], field: value},))
        assert evidence.build_project_evidence((planted,)) == failure(
            PROJECT,
            DASHBOARD_URL,
            "invalid_evidence_metadata",
            "matching source metadata",
            "mismatch",
        )
    synthetic = replace(item, rows=({**item.rows[0], "provenance": "synthetic"},))
    assert evidence.build_project_evidence((synthetic,)) == failure(
        PROJECT, DASHBOARD_URL, "provenance", "public", "not Public"
    )
    joined = replace(item, rows=({**item.rows[0], "join_key": "invented-join"},))
    assert evidence.build_project_evidence((joined,)) == failure(
        PROJECT, DASHBOARD_URL, "prohibited_join", "no join", "joined"
    )


def test_metadata_pending_terms_retain_the_revision_and_drift_still_refuses(
    tmp_path: Path, monkeypatch
) -> None:
    """Ruling L-1001 (S2-T30): a pending terms reading fails nothing and the
    archived parser output is still refused when it drifts."""
    monkeypatch.setattr(registry_module, "load_registry", lambda: ())
    pending = project(tmp_path, pending_terms=True)
    result = evidence.build_project_evidence((pending,))
    assert not hasattr(result, "check")
    assert len(result.revisions) == 1
    assert all(row["terms_sha256"] == "" for row in pending.rows)
    item = project(tmp_path / "held", day="2026-11-15")
    plants = (
        replace(item, rows=({**item.rows[0], "capex_value": "99.5"},)),
        replace(item, observation=SourceAssertion("2024", "year", "")),
    )
    for planted in plants:
        assert evidence.build_project_evidence((planted,)) == failure(
            PROJECT,
            DASHBOARD_URL,
            "invalid_evidence_metadata",
            "archived parser output",
            "mismatch",
        )


def test_valid_assertion_truth_table() -> None:
    cases = [
        (SourceAssertion(None, "", "not_stated_by_source"), False, True),
        (SourceAssertion(None, "day", "not_stated_by_source"), False, False),
        (SourceAssertion(None, "", ""), False, False),
        (SourceAssertion("2026", "year", "invented-reason"), False, False),
        (SourceAssertion("", "year", ""), False, False),
        (SourceAssertion("2026", "year", ""), False, True),
        (SourceAssertion("2026-11", "month", ""), False, True),
        (SourceAssertion("2026-11-16", "day", ""), False, True),
        (SourceAssertion("2026-11", "day", ""), False, False),
        (SourceAssertion("2026-02-30", "day", ""), False, False),
        (SourceAssertion("true", "source_flag", ""), True, True),
        (SourceAssertion("false", "source_flag", ""), True, True),
        (SourceAssertion("invented", "source_flag", ""), True, False),
        (SourceAssertion("true", "day", ""), True, False),
    ]
    for assertion, correction, expected in cases:
        assert evidence._valid_assertion(assertion, correction=correction) is expected


def test_candidate_parser_and_refusal_failures_are_complete(tmp_path: Path) -> None:
    assert evidence._parser_failure(
        envelope(), "invented_check", "invented_expected", "invented_observed"
    ) == failure(
        SOURCE, URL, "invented_check", "invented_expected", "invented_observed"
    )
    row = candidate(tmp_path)
    assert evidence._candidate_failure(
        row, "invented_check", "invented_expected", "invented_observed"
    ) == failure(
        SOURCE, URL, "invented_check", "invented_expected", "invented_observed"
    )
    row = replace(row, source_chain={**row.source_chain, "page_url": 3})
    assert evidence._candidate_failure(row, "check", "expected", "observed") == failure(
        SOURCE, "", "check", "expected", "observed"
    )
    item = project(tmp_path)
    item = replace(
        item,
        snapshot=replace(item.snapshot, sidecar={"source_id": 3, "fetch_url": 4}),
    )
    assert evidence._refusal(item, "check", "expected", "observed") == failure(
        "", "", "check", "expected", "observed"
    )


def test_unsupported_completion_or_investment_inference_is_refused(
    tmp_path: Path,
) -> None:
    row = candidate(tmp_path)
    for changed in (
        {"completion": "invented-completion"},
        {"observed_investment": "invented-investment"},
    ):
        planted = replace(row, **changed)
        assert evidence.require_independent_milestone(
            planted, link_for(row), frozenset({PROJECT_IDENTITY})
        ) == failure(
            SOURCE,
            URL,
            "unsupported_milestone",
            "reported milestone only",
            "completion or investment inference",
        )
