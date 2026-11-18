"""Caller-level missing artifacts, batch terms and empty candidate stems."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.investment_fixtures import (
    DASHBOARD_URL,
    TERMS_BODY,
    dashboard_page,
)
from custodian.tests.test_investment_build import (
    _agency_entry,
    _agency_transport_bodies,
    _batch,
    _fdi_entry,
    _run,
)
from custodian.tests.test_investment_build_survivors import (
    _failure,
    _spec,
    _untyped,
)

import eii_custodian.publicdata.investment_build as build
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.investment_contracts import DashboardShape


@pytest.mark.parametrize("raw_present", [False, True])
def test_public_dashboard_missing_body_or_receipt_names_original_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw_present: bool
) -> None:
    shape = DashboardShape(
        "fdi-dashboard-v2",
        frozenset(build.COLUMN_FROM_PAGE),
        dict(build.COLUMN_FROM_PAGE),
        {},
        {},
        {},
    )
    monkeypatch.setattr(
        build, "load_source_spec", lambda *a, **kw: replace(_spec(), dashboard=shape)
    )
    digest = "SYN-missing"
    if raw_present:
        body = dashboard_page()
        digest = hashlib.sha256(body).hexdigest()
        (tmp_path / "fdi_projects").mkdir()
        (tmp_path / "fdi_projects" / f"{digest}.html").write_bytes(body)
    result = build.publish_investment(
        _fdi_entry(), tmp_path, digest, _untyped(None), _untyped(None), _untyped(None)
    )
    if raw_present:
        _failure(
            result,
            "1|fdi_projects|https://dashboard.invalid/|missing_artifact|sidecar|missing",
        )
    else:
        _failure(
            result,
            "1|fdi_projects|https://dashboard.invalid/|missing_artifact|SYN-missing|missing",
        )
    assert not (tmp_path / "fdi_projects/loadable.json").exists()


def test_public_agency_missing_receipt_names_original_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pages = tuple(
        build.PageSpec(kind, f"https://syn.invalid/{kind}", 1, 0)
        for kind in ("sector", "opportunity", "incentive", "setup", "law")
    )
    monkeypatch.setattr(
        build, "load_source_spec", lambda *a, **kw: replace(_spec(), pages=pages)
    )
    result = build.publish_investment(
        _agency_entry(),
        tmp_path,
        "SYN-missing",
        _untyped(None),
        _untyped(None),
        _untyped(None),
    )
    _failure(
        result,
        "1|investqa_pages|https://agency.invalid/|missing_artifact|sidecar|missing",
    )


@pytest.mark.parametrize("source", ["fdi_projects", "investqa_pages"])
def test_caller_publishes_terms_on_manifest_and_both_archived_objects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    entry = _fdi_entry() if source == "fdi_projects" else _agency_entry()
    bodies = (
        {DASHBOARD_URL: dashboard_page()}
        if source == "fdi_projects"
        else _agency_transport_bodies()
    )
    assert _run(tmp_path, monkeypatch, entry, bodies) == 0
    pointer, manifest, _ = _batch(tmp_path, source)
    expected_terms = hashlib.sha256(TERMS_BODY).hexdigest()
    assert manifest["terms_sha256"] == expected_terms
    for page in manifest["pages"]:
        raw = read_snapshot(tmp_path / "data/public_cache" / source, page["sha256"])
        assert raw.sidecar["terms_sha256"] == expected_terms
    evidence = tmp_path / "data/public_cache" / source / "evidence"
    for identity in (
        pointer["evidence_manifest_identity"],
        manifest["table_snapshot_identity"],
    ):
        assert (
            read_snapshot(evidence, identity).sidecar["terms_sha256"] == expected_terms
        )


def test_discard_candidate_never_unlinks_an_empty_stem_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Relative empty stems are possible Path inputs; keep this probe inside tmp_path.
    monkeypatch.chdir(tmp_path)
    build._discard_candidate(tmp_path / "SYN-cache", "SYN-source", Path(), Path())
    assert tmp_path.is_dir()
    assert list(tmp_path.iterdir()) == []
