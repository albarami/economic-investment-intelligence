"""Whole publication objects, immutable evidence and refusal cleanup plants."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from custodian.tests.investment_fixtures import (
    DASHBOARD_URL,
    LANDING_URL,
    agency_bodies,
    dashboard_page,
    invented_record,
)
from custodian.tests.test_investment_build import (
    RETRIEVED,
    _agency_entry,
    _agency_transport_bodies,
    _batch,
    _fdi_entry,
    _run,
)
from custodian.tests.test_investment_build_survivors import (
    _envelope,
    _failure,
    _spec,
    _untyped,
)

import eii_custodian.publicdata.investment_build as build
from eii_custodian.publicdata.fetch.checks import AttemptFailure
from eii_custodian.publicdata.fetch.snapshots import SnapshotError, read_snapshot
from eii_custodian.publicdata.fetch.transport import Response


def test_dashboard_requires_its_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # _dashboard_spec always supplies DashboardShape; exercise the defensive seam.
    monkeypatch.setattr(
        build, "load_source_spec", lambda *a, **kw: replace(_spec(), dashboard=None)
    )
    result = build.publish_investment(
        _fdi_entry(),
        tmp_path,
        "SYN-digest",
        _untyped(None),
        _untyped(None),
        _untyped(None),
    )
    _failure(
        result,
        "1|fdi_projects|https://dashboard.invalid/|unconfirmed|dashboard|missing",
    )


def test_dashboard_publishes_exact_document_and_page_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = dashboard_page(
        (
            invented_record(),
            invented_record(project_id=1002, lat=("n", "0"), lng=("n", "0")),
        )
    )
    assert _run(tmp_path, monkeypatch, _fdi_entry(), {DASHBOARD_URL: body}) == 0
    _, manifest, table = _batch(tmp_path, "fdi_projects")
    assert set(table) == {
        "schema_version",
        "source_id",
        "caveat_keys",
        "caveat_text",
        "row_count",
        "empty_coordinate_count",
        "rows",
    }
    assert table["schema_version"] == "fdi_projects.v1"
    assert table["source_id"] == "fdi_projects"
    assert table["caveat_keys"] == ["fdi_estimates"]
    assert table["caveat_text"] == {
        "announced_estimates": "estimates of publicly announced projects",
        "incomplete_coverage": "does not capture all investment projects",
    }
    assert table["row_count"] == 2
    assert table["empty_coordinate_count"] == 1
    assert manifest["pages"] == [
        {
            "url": "https://dashboard.invalid/",
            "sha256": hashlib.sha256(body).hexdigest(),
            "retrieved_utc": "2026-11-14T08:00:00Z",
            "kind": "dashboard",
        }
    ]
    assert (
        tmp_path / "data/public_cache/fdi_projects/empty_coordinates.txt"
    ).read_text(encoding="utf-8") == "fdi_projects empty_coordinates=1\n"


def test_agency_publishes_exact_counts_and_each_kind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run(tmp_path, monkeypatch, _agency_entry(), _agency_transport_bodies()) == 0
    _, manifest, table = _batch(tmp_path, "investqa_pages")
    assert set(table) == {"schema_version", "source_id", "row_count", "rows"}
    assert table["schema_version"] == "pub_investqa_record.v1"
    assert table["source_id"] == "investqa_pages"
    assert table["row_count"] == 27
    assert len(table["rows"]) == 27
    bodies = {LANDING_URL: b"<html>Invented landing.</html>", **agency_bodies()}
    expected = []
    for kind, url in zip(
        ("landing", "sector", "opportunity", "incentive", "setup", "law"),
        bodies,
        strict=True,
    ):
        expected.append(
            {
                "kind": kind,
                "url": url,
                "sha256": hashlib.sha256(bodies[url]).hexdigest(),
                "retrieved_utc": "2026-11-14T08:00:00Z",
            }
        )
    for order, page in enumerate(expected[1:], 1):
        page.update(language="en", order=order)
    assert manifest["pages"] == expected
    for row in table["rows"]:
        assert row["retrieved_utc"] == "2026-11-14T08:00:00Z"
        assert row["page_url"] in bodies


def test_agency_missing_rule_names_the_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # _kind_rules supplies all families; this inconsistent injected spec tests defense.
    pages = tuple(
        build.PageSpec(kind, f"https://syn.invalid/{kind}", 1, 0)
        for kind in ("sector", "opportunity", "incentive", "setup", "law")
    )
    spec = replace(_spec(), source_id="investqa_pages", pages=pages)
    monkeypatch.setattr(build, "load_source_spec", lambda *a, **kw: spec)
    monkeypatch.setattr(
        build, "_receipt", lambda *a: ("SYN-terms", "2026-01-03T04:05:06Z")
    )
    monkeypatch.setattr(
        build,
        "_fetch_page",
        lambda *a: ("SYN-digest", "2026-01-03T04:05:06Z", b"SYN-page"),
    )
    result = build.publish_investment(
        _agency_entry(),
        tmp_path,
        "SYN-landing",
        _untyped(None),
        _untyped(None),
        _untyped(None),
    )
    _failure(
        result,
        "1|investqa_pages|https://syn.invalid/sector|missing_page|sector|missing",
    )


@pytest.mark.parametrize(
    "fault",
    [
        None,
        AttemptFailure(
            6, "https://syn.invalid/page", "SYN-read", "SYN-expect", "SYN-observe"
        ),
    ],
)
def test_fetch_failure_and_missing_response_are_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: AttemptFailure | None
) -> None:
    monkeypatch.setattr(build, "read_bounded", lambda *a: (None, fault))
    result = build._fetch_page(
        _fdi_entry(),
        tmp_path,
        "https://syn.invalid/page",
        _untyped(None),
        _untyped(None),
        _untyped(None),
        "SYN-terms",
    )
    if fault is None:
        _failure(
            result,
            "1|fdi_projects|https://syn.invalid/page|check_failed|readable page|missing",
        )
    else:
        _failure(
            result,
            "6|fdi_projects|https://syn.invalid/page|SYN-read|SYN-expect|SYN-observe",
        )
    assert list(tmp_path.iterdir()) == []


def test_fetch_receipt_and_original_retrieval_are_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = replace(_fdi_entry(), key="SYN-cache", publisher="SYN-publisher")
    body = dashboard_page()
    digest = hashlib.sha256(body).hexdigest()
    sleeps: list[float] = []

    def transport(url: str) -> Response:
        raise AssertionError("SYN-unexpected transport")

    sleeper = sleeps.append

    # Bound methods are fresh objects on access: keep and compare one supplied seam.
    def bounded(caller: object, sleep: object, url: str) -> tuple[Response, None]:
        assert caller is transport
        assert sleep is sleeper
        assert url == "https://syn.invalid/page"
        return Response(url, body, ()), None

    monkeypatch.setattr(build, "read_bounded", bounded)
    for clock_value in ("2026-01-03T04:05:06Z", "2026-01-04T04:05:06Z"):
        result = build._fetch_page(
            entry,
            tmp_path,
            "https://syn.invalid/page",
            transport,
            sleeper,
            lambda value=clock_value: value,
            "ab" * 32,
        )
        assert result == (digest, "2026-01-03T04:05:06Z", body)
    side = read_snapshot(tmp_path / "SYN-cache", digest).sidecar
    assert side["source_id"] == "fdi_projects"
    assert side["key"] == "SYN-cache"
    assert side["fetch_url"] == "https://syn.invalid/page"
    assert side["fetch_host"] == "dashboard.invalid"
    assert side["publisher"] == "SYN-publisher"
    assert side["source_modified"] is None
    assert side["terms_sha256"] == "ab" * 32


@pytest.mark.parametrize("cause", ["reader", "retrieved"])
def test_fetch_snapshot_refusal_is_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cause: str
) -> None:
    monkeypatch.setattr(
        build,
        "read_bounded",
        lambda *a: (Response("https://syn.invalid/page", b"SYN", ()), None),
    )
    monkeypatch.setattr(build, "commit_pair", lambda *a: None)

    def snapshot(*args: object) -> object:
        if cause == "reader":
            raise SnapshotError("SYN-invalid")
        # Real read_snapshot validates lineage first; reach this defensive check.
        return SimpleNamespace(sidecar={"retrieved_utc": 4}, body=b"SYN")

    monkeypatch.setattr(build, "read_snapshot", snapshot)
    result = build._fetch_page(
        _fdi_entry(),
        tmp_path,
        "https://syn.invalid/page",
        _untyped(None),
        _untyped(None),
        lambda: RETRIEVED,
        "ab" * 32,
    )
    _failure(
        result,
        "1|fdi_projects|https://syn.invalid/page|snapshot_invalid|verified snapshot|invalid",
    )


def test_commit_batch_manifest_pointer_and_archive_are_complete(tmp_path: Path) -> None:
    entry = replace(_fdi_entry(), publisher="SYN-publisher")
    envelope = _envelope()
    body = b"SYN-public-page"
    raw_digest = hashlib.sha256(body).hexdigest()
    source = tmp_path / "fdi_projects"
    source.mkdir()
    (source / f"{raw_digest}.html").write_bytes(body)
    pages = (
        {
            "url": "https://syn.invalid/page",
            "sha256": raw_digest,
            "retrieved_utc": "2026-01-03T04:05:06Z",
            "kind": "dashboard",
        },
    )
    assert (
        build._commit_batch(
            tmp_path,
            entry,
            _spec(),
            envelope,
            {"SYN-note": "café"},
            pages,
            "ef" * 32,
            "2026-01-04T04:05:06Z",
        )
        is None
    )
    table_bytes = b'{"SYN-note": "caf\\u00e9"}\n'
    table_digest = hashlib.sha256(table_bytes).hexdigest()
    pointer = json.loads((source / "loadable.json").read_bytes())
    manifest_digest = pointer["manifest_sha256"]
    assert pointer == {
        "source_id": "fdi_projects",
        "manifest_sha256": manifest_digest,
        "evidence_manifest_identity": manifest_digest,
        "release_selected": False,
    }
    manifest_bytes = (source / "manifests" / f"{manifest_digest}.json").read_bytes()
    assert hashlib.sha256(manifest_bytes).hexdigest() == manifest_digest
    assert json.loads(manifest_bytes) == {
        "schema_version": "source_snapshot.v1",
        "source_id": "fdi_projects",
        "snapshot_identity": "page_sha256",
        "release_selected": False,
        "live_page_compared": False,
        "currency_rule": "Mn USD",
        "location_precision": "location_text",
        "publisher": "SYN-publisher",
        "licence_id": "SYN-licence",
        "licence_basis": "owner_decision",
        "decision_record": "SYN-review",
        "terms_sha256": "ef" * 32,
        "terms_url": "https://syn.invalid/terms",
        "retrieved_utc": "2026-01-04T04:05:06Z",
        "parser_method": "SYN-parser",
        "parser_version": "SYN-version",
        "table_sha256": table_digest,
        "table_snapshot_identity": table_digest,
        "pages": list(pages),
    }
    assert (source / "staging" / f"{table_digest}.json").read_bytes() == table_bytes
    for identity, expected in (
        (table_digest, table_bytes),
        (manifest_digest, manifest_bytes),
    ):
        archived = read_snapshot(source / "evidence", identity)
        assert archived.body == expected
        assert archived.sidecar["parser_method"] == "SYN-parser"
        assert archived.sidecar["parser_version"] == "SYN-version"
        assert archived.sidecar["publisher"] == "SYN-publisher"
        assert archived.sidecar["retrieved_utc"] == "2026-01-04T04:05:06Z"
        assert archived.sidecar["terms_sha256"] == "ef" * 32
        assert archived.sidecar["fetch_url"] == "https://syn.invalid/page"
        assert archived.sidecar["fetch_host"] == "dashboard.invalid"
        assert archived.sidecar["source_modified"] is None


@pytest.mark.parametrize("fail_at", [1, 2])
def test_commit_archive_refusal_removes_candidate_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_at: int
) -> None:
    source = tmp_path / "fdi_projects"
    (source / "staging").mkdir(parents=True)
    (source / "manifests").mkdir()
    (source / "loadable.json").write_text(
        '{"manifest_sha256": "SYN-old"}', encoding="utf-8"
    )
    (source / "manifests/SYN-old.json").write_text(
        '{"table_sha256": "SYN-table"}', encoding="utf-8"
    )
    (source / "staging/SYN-table.json").write_bytes(b"SYN-retained")
    body = b"SYN-public-page"
    digest = hashlib.sha256(body).hexdigest()
    (source / f"{digest}.html").write_bytes(body)
    calls: list[object] = []

    def archive(*args: object) -> None:
        calls.append(args)
        if len(calls) == fail_at:
            raise SnapshotError("SYN-invalid")

    monkeypatch.setattr(build, "_archive_evidence", archive)
    result = build._commit_batch(
        tmp_path,
        _fdi_entry(),
        _spec(),
        _envelope(),
        {"SYN-candidate": True},
        (
            {
                "url": "https://syn.invalid/page",
                "sha256": digest,
                "retrieved_utc": "2026-01-03T04:05:06Z",
                "kind": "dashboard",
            },
        ),
        "ab" * 32,
        "2026-01-03T04:05:06Z",
    )
    if fail_at == 1:
        _failure(
            result,
            "1|fdi_projects|https://syn.invalid/page|snapshot_invalid|verified parsed evidence|invalid",
        )
    else:
        _failure(
            result,
            "1|fdi_projects|https://syn.invalid/page|snapshot_invalid|verified manifest evidence|invalid",
        )
    assert len(calls) == fail_at
    assert (source / "loadable.json").read_text(
        encoding="utf-8"
    ) == '{"manifest_sha256": "SYN-old"}'
    assert [p.name for p in (source / "staging").iterdir()] == ["SYN-table.json"]
    assert [p.name for p in (source / "manifests").iterdir()] == ["SYN-old.json"]
    assert (source / "staging/SYN-table.json").read_bytes() == b"SYN-retained"


def test_archive_evidence_keeps_explicit_identity(tmp_path: Path) -> None:
    # A malformed explicit identity is a path refusal, never an inferred identity.
    with pytest.raises(SnapshotError) as failure:
        build._archive_evidence(
            tmp_path,
            _fdi_entry(),
            _envelope(),
            "ef" * 32,
            "2026-01-04T04:05:06Z",
            "SYN-invalid-identity",
            b"SYN-body",
        )
    assert str(failure.value) == "snapshot_path_invalid"


def test_agency_forwards_transport_and_sleeper_through_public_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from custodian.tests.test_investment_build import _family_pages

    entry = _agency_entry()
    loaded = build.load_source_spec("investqa_pages", url=entry.url)
    assert isinstance(loaded, build.SourceSpec)
    spec = replace(
        loaded,
        pages=_family_pages(
            "https://agency.invalid/sectors/invented-textiles",
            "https://agency.invalid/incentives/invented-rent-ease",
        ),
    )
    body = b"SYN-landing"
    digest = hashlib.sha256(body).hexdigest()
    (tmp_path / "investqa_pages").mkdir()
    (tmp_path / "investqa_pages" / f"{digest}.html").write_bytes(body)
    monkeypatch.setattr(build, "load_source_spec", lambda *a, **kw: spec)
    monkeypatch.setattr(build, "_receipt", lambda *a: ("ab" * 32, RETRIEVED))
    bodies = agency_bodies()
    seen: list[str] = []

    def transport(url: str) -> Response:
        raise AssertionError("SYN-unexpected transport")

    def sleeper(seconds: float) -> None:
        raise AssertionError("SYN-unexpected wait")

    def bounded(caller: object, sleep: object, url: str) -> tuple[Response, None]:
        assert caller is transport
        assert sleep is sleeper
        seen.append(url)
        return Response(url, bodies[url], ()), None

    monkeypatch.setattr(build, "read_bounded", bounded)
    assert (
        build.publish_investment(
            entry, tmp_path, digest, transport, sleeper, lambda: RETRIEVED
        )
        is None
    )
    assert seen == [
        "https://agency.invalid/sectors/invented-textiles",
        "https://agency.invalid/opportunities/invented-loom",
        "https://agency.invalid/incentives/invented-rent-ease",
        "https://agency.invalid/setup/invented-steps",
        "https://agency.invalid/laws/invented-statute",
    ]


def test_agency_missing_families_refuses_before_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = replace(
        _spec(), pages=(build.PageSpec("sector", "https://syn.invalid/sector", 1, 0),)
    )
    monkeypatch.setattr(build, "load_source_spec", lambda *a, **kw: spec)
    result = build.publish_investment(
        _agency_entry(),
        tmp_path,
        "SYN-digest",
        _untyped(None),
        _untyped(None),
        _untyped(None),
    )
    _failure(
        result,
        "1|investqa_pages|https://agency.invalid/|missing_page|page family|opportunity,incentive,setup,law",
    )
