"""Mutation plants for investment publication; all inputs are invented and offline."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.test_investment_build import _fdi_entry

import eii_custodian.publicdata.investment_build as build
from eii_custodian.publicdata.investment_contracts import (
    Bounds,
    Confirmation,
    DashboardShape,
    InvestmentFailure,
    SourceEnvelope,
)


def test_atomic_bytes_creates_parents_and_replaces_exact_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The uncovered byte writer stages the complete body before replacement."""
    destination = tmp_path / "SYN-cache" / "nested" / "SYN-body.json"
    calls: list[tuple[Path, Path]] = []

    def replacing(source: Path, target: Path) -> None:
        assert source == destination.with_name(".SYN-body.json.partial")
        assert target == destination
        assert source.read_bytes() == b"SYN-byte-body\x00\xff"
        calls.append((source, target))
        source.replace(target)

    monkeypatch.setattr(build, "_replace", replacing)
    build._atomic_bytes(destination, b"SYN-byte-body\x00\xff")
    build._atomic_bytes(destination, b"SYN-byte-body\x00\xff")
    assert len(calls) == 2
    assert destination.read_bytes() == b"SYN-byte-body\x00\xff"
    assert sorted(path.name for path in destination.parent.iterdir()) == [
        "SYN-body.json"
    ]


def _untyped(value: object) -> Any:
    """Pass deliberately malformed boundary values without a suppression."""
    return value


def _failure(result: object, expected: str) -> None:
    """Compare the entire refusal, including every full text field, to a literal."""
    assert isinstance(result, InvestmentFailure)
    assert (
        "|".join(
            str(value)
            for value in (
                result.code,
                result.source_id,
                result.url,
                result.check,
                result.expected,
                result.observed,
            )
        )
        == expected
    )


def _envelope() -> SourceEnvelope:
    return SourceEnvelope(
        "fdi_projects",
        "SYN-publisher",
        "https://syn.invalid/page",
        "SYN-licence",
        "owner_decision",
        "SYN-review",
        "ab" * 32,
        "https://syn.invalid/terms",
        "2026-01-03T04:05:06Z",
        "cd" * 32,
        "SYN-parser",
        "SYN-version",
    )


def _spec() -> build.SourceSpec:
    return build.SourceSpec(
        "fdi_projects",
        Bounds(1, 3, "announced", "2001", True),
        Confirmation(True, True, True, False),
        "page_sha256",
        "Mn USD",
        "location_text",
        DashboardShape("fdi-dashboard-v2", frozenset(), {}, {}, {}, {}),
        (),
        {},
        {},
        frozenset(),
        {},
    )


def _row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "publisher": "SYN-publisher",
        "page_url": "https://syn.invalid/page",
        "licence_id": "SYN-licence",
        "licence_basis": "owner_decision",
        "decision_record": "SYN-review",
        "terms_sha256": "ab" * 32,
        "retrieved_utc": "2026-01-03T04:05:06Z",
        "page_sha256": "cd" * 32,
        "provenance": "public",
        "record_key": "SYN-record-AA-0001",
        "announced": "2001",
        "join_key": "",
    }
    row.update(changes)
    return row


def test_publish_refusals_preserve_source_and_all_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = _fdi_entry()
    failure = InvestmentFailure(
        6, "fdi_projects", entry.url, "SYN-read", "SYN-want", "SYN-got"
    )

    def loading(source_id: str, *, url: str) -> InvestmentFailure:
        assert source_id == "fdi_projects"
        assert url == "https://dashboard.invalid/"
        return failure

    monkeypatch.setattr(build, "load_source_spec", loading)
    args = (
        entry,
        tmp_path,
        "SYN-digest",
        _untyped(None),
        _untyped(None),
        _untyped(None),
    )
    assert build.publish_investment(*args) is failure
    monkeypatch.setattr(
        build,
        "load_source_spec",
        lambda *a, **kw: replace(_spec(), bounds=Bounds(1, 3, "", "", False)),
    )
    _failure(
        build.publish_investment(*args),
        "1|fdi_projects|https://dashboard.invalid/|unconfirmed|confirmed specification|unconfirmed",
    )
    monkeypatch.setattr(build, "load_source_spec", lambda *a, **kw: _spec())

    def interrupted(*args: object) -> None:
        partial = tmp_path / "fdi_projects" / "nested" / ".SYN.partial"
        partial.parent.mkdir(parents=True)
        partial.write_bytes(b"SYN")
        raise OSError("SYN-interrupted")

    monkeypatch.setattr(build, "_publish_dashboard", interrupted)
    _failure(
        build.publish_investment(*args),
        "1|fdi_projects|https://dashboard.invalid/|write_failed|stored file|write failed",
    )
    assert list(tmp_path.rglob("*.partial")) == []


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            None,
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|page specification|missing",
        ),
        (
            "[",
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|page specification|unreadable",
        ),
        (
            "[]",
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|page specification|unreadable",
        ),
        (
            '{"sources": []}',
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|fdi_projects|missing",
        ),
        (
            '{"sources": {}}',
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|fdi_projects|missing",
        ),
        (
            '{"sources": {"fdi_projects": []}}',
            "1|fdi_projects|https://syn.invalid/page|unconfirmed|fdi_projects|unreadable",
        ),
        (
            '{"schema_version": "investment_pages.v2", "sources": {"fdi_projects": {}}}',
            "1|fdi_projects|https://syn.invalid/page|confirmation_inventory|recorded|missing",
        ),
    ],
)
def test_spec_file_refusal_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str | None, expected: str
) -> None:
    path = tmp_path / "SYN-pages.yaml"
    if body is not None:
        path.write_text(body, encoding="utf-8")
    monkeypatch.setattr(build, "_PAGES", path)
    _failure(
        build.load_source_spec("fdi_projects", url="https://syn.invalid/page"), expected
    )


@pytest.mark.parametrize(
    ("confirmation", "expected"),
    [
        (
            Confirmation(False, True, True, True),
            "1|fdi_projects|https://syn.invalid/page|confirmation_inventory|recorded|missing",
        ),
        (
            Confirmation(True, False, True, True),
            "1|fdi_projects|https://syn.invalid/page|confirmation_fields|recorded|missing",
        ),
        (
            Confirmation(True, True, False, True),
            "1|fdi_projects|https://syn.invalid/page|confirmation_fixture|recorded|missing",
        ),
    ],
)
def test_validation_confirmation_messages(
    confirmation: Confirmation, expected: str
) -> None:
    _failure(
        build.validate_investment((_row(),), _spec().bounds, confirmation, _envelope()),
        expected,
    )


def test_validation_missing_envelope_and_exact_count_edges() -> None:
    spec = _spec()
    _failure(
        build.validate_investment(
            (_row(),),
            replace(spec.bounds, confirmed=False),
            spec.confirmation,
            _envelope(),
        ),
        "1|fdi_projects|https://syn.invalid/page|unconfirmed|confirmed specification|unconfirmed",
    )
    _failure(
        build.validate_investment(
            (_row(),), spec.bounds, spec.confirmation, replace(_envelope(), method="")
        ),
        "1|fdi_projects|https://syn.invalid/page|missing_lineage|method|absent",
    )
    for count in (1, 3):
        rows = tuple(_row(record_key=f"SYN-record-AA-{i:04d}") for i in range(count))
        result = build.validate_investment(
            rows, spec.bounds, spec.confirmation, _envelope()
        )
        assert isinstance(result, tuple)
        assert len(result) == count
        assert all("join_key" not in row for row in result)
    _failure(
        build.validate_investment((), spec.bounds, spec.confirmation, _envelope()),
        "1|fdi_projects|https://syn.invalid/page|row_count|1..3|0",
    )
    _failure(
        build.validate_investment(
            (_row(),) * 4, spec.bounds, spec.confirmation, _envelope()
        ),
        "1|fdi_projects|https://syn.invalid/page|row_count|1..3|4",
    )
    _failure(
        build.validate_investment(
            (_row(),) * 2, spec.bounds, spec.confirmation, _envelope()
        ),
        "1|fdi_projects|https://syn.invalid/page|duplicate_key|unique key|SYN-record-AA-0001",
    )


def test_page_families_report_all_missing_in_order() -> None:
    _failure(
        build.require_page_families(("sector",), _envelope()),
        "1|fdi_projects|https://syn.invalid/page|missing_page|page family|opportunity,incentive,setup,law",
    )
    assert (
        build.require_page_families(
            ("law", "setup", "incentive", "opportunity", "sector"), _envelope()
        )
        is None
    )


@pytest.mark.parametrize("source", [None, 3, [], "SYN-source"])
def test_release_selection_is_literal_true_only(source: object) -> None:
    for reviewed in (False, None, 1, "true"):
        result = build.select_release(
            {"source_id": source}, reviewed=_untyped(reviewed)
        )
        if source == "SYN-source":
            _failure(
                result, "1|SYN-source||unreviewed_release|reviewed selection|unreviewed"
            )
        else:
            _failure(result, "1|||unreviewed_release|reviewed selection|unreviewed")
    assert build.select_release({"source_id": source}, reviewed=True) is None


def test_audit_pointer_and_manifest_failures(tmp_path: Path) -> None:
    import hashlib

    source = tmp_path / "SYN-source"
    _failure(
        build.audit_snapshot(tmp_path, "SYN-source"),
        "1|SYN-source||missing_artifact|loadable|missing",
    )
    source.mkdir()
    pointer = source / "loadable.json"
    for body in ("[]", "{}", '{"manifest_sha256": 4}'):
        pointer.write_text(body, encoding="utf-8")
        expected = (
            "1|SYN-source||missing_artifact|loadable|missing"
            if body == "[]"
            else "1|SYN-source||missing_artifact|manifest|missing"
        )
        _failure(build.audit_snapshot(tmp_path, "SYN-source"), expected)
    pointer.write_text('{"manifest_sha256": "SYN-manifest"}', encoding="utf-8")
    _failure(
        build.audit_snapshot(tmp_path, "SYN-source"),
        "1|SYN-source||missing_artifact|SYN-manifest|missing",
    )
    (source / "manifests").mkdir()
    manifest_body = b'{"pages": [null]}'
    manifest_digest = hashlib.sha256(manifest_body).hexdigest()
    pointer.write_text(f'{{"manifest_sha256": "{manifest_digest}"}}', encoding="utf-8")
    manifest = source / "manifests" / f"{manifest_digest}.json"
    manifest.write_bytes(manifest_body)
    _failure(
        build.audit_snapshot(tmp_path, "SYN-source"),
        "1|SYN-source||hash_mismatch|page|unreadable",
    )


@pytest.mark.parametrize(
    ("pages", "expected"),
    [
        (None, "1|SYN-source||missing_artifact|pages|missing"),
        ({}, "1|SYN-source||missing_artifact|pages|missing"),
        ([None], "1|SYN-source||hash_mismatch|page|unreadable"),
        (
            [{"sha256": 4, "url": "https://syn.invalid/page"}],
            "1|SYN-source||hash_mismatch|page|unreadable",
        ),
        (
            [{"sha256": "SYN-hash", "url": 4}],
            "1|SYN-source||hash_mismatch|page|unreadable",
        ),
        (
            [{"sha256": "SYN-hash", "url": "https://syn.invalid/page"}],
            "1|SYN-source|https://syn.invalid/page|missing_artifact|SYN-hash|missing",
        ),
    ],
)
def test_audit_page_refusals(tmp_path: Path, pages: object, expected: str) -> None:
    # audit_snapshot only unwraps its manifest; direct cases isolate every bad slot.
    _failure(build._audit_pages(tmp_path, "SYN-source", {"pages": pages}), expected)


def test_audit_pages_compares_last_body(tmp_path: Path) -> None:
    import hashlib

    source = tmp_path / "SYN-source"
    source.mkdir()
    body = b"SYN-body"
    digest = hashlib.sha256(body).hexdigest()
    (source / f"{digest}.html").write_bytes(body)
    pages = [{"sha256": digest, "url": "https://syn.invalid/page"}]
    assert build._audit_pages(tmp_path, "SYN-source", {"pages": pages}) is None
    (source / "SYN-bad.html").write_bytes(b"SYN-substitution")
    pages.append({"sha256": "SYN-bad", "url": "https://syn.invalid/other"})
    _failure(
        build._audit_pages(tmp_path, "SYN-source", {"pages": pages}),
        "1|SYN-source|https://syn.invalid/other|hash_mismatch|SYN-bad|mismatch",
    )


def test_failure_factory_default_and_explicit_code() -> None:
    _failure(
        build.fail_of(_envelope(), "SYN-check", "SYN-expect", "SYN-observe"),
        "1|fdi_projects|https://syn.invalid/page|SYN-check|SYN-expect|SYN-observe",
    )
    _failure(
        build.fail_of(_envelope(), "SYN-check", "SYN-expect", "SYN-observe", code=6),
        "6|fdi_projects|https://syn.invalid/page|SYN-check|SYN-expect|SYN-observe",
    )
