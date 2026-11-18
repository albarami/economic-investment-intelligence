"""Investment boundary, row lineage, parent and period mutation plants."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from custodian.tests.test_investment_build import _fdi_entry
from custodian.tests.test_investment_build_survivors import (
    _envelope,
    _failure,
    _row,
    _spec,
)

import eii_custodian.publicdata.investment_build as build
from eii_custodian.publicdata.investment_contracts import Bounds


def test_bounds_uses_fallback_only_for_absent_entry_limits() -> None:
    entry = replace(
        _fdi_entry(),
        row_count_min=None,
        row_count_max=None,
        period_field="",
        period_last="",
    )
    assert build._bounds(entry, _spec()) == Bounds(1, 3, "announced", "2001", True)
    entry = replace(
        entry,
        row_count_min=0,
        row_count_max=0,
        period_field="SYN-period",
        period_last="2002",
    )
    assert build._bounds(entry, _spec()) == Bounds(0, 0, "SYN-period", "2002", True)


def test_envelope_keeps_lineage_and_leaves_parser_unset() -> None:
    entry = replace(
        _fdi_entry(),
        publisher="SYN-publisher",
        licence_id="SYN-licence",
        decision_record="SYN-review",
        terms_url="https://syn.invalid/terms",
    )
    actual = build._envelope(
        entry,
        "https://syn.invalid/page",
        "cd" * 32,
        "ab" * 32,
        "2026-01-03T04:05:06Z",
        "SYN-unused-method",
    )
    assert actual == replace(_envelope(), method="", method_version="")


def test_cached_body_missing_mismatched_and_verified(tmp_path: Path) -> None:
    _failure(
        build._cached_body(
            tmp_path,
            "SYN-cache",
            "SYN-missing",
            "html",
            "SYN-source",
            "https://syn.invalid/page",
        ),
        "1|SYN-source|https://syn.invalid/page|missing_artifact|SYN-missing|missing",
    )
    source = tmp_path / "SYN-cache"
    source.mkdir()
    (source / "SYN-bad.html").write_bytes(b"SYN-tampered")
    _failure(
        build._cached_body(
            tmp_path,
            "SYN-cache",
            "SYN-bad",
            "html",
            "SYN-source",
            "https://syn.invalid/page",
        ),
        "1|SYN-source|https://syn.invalid/page|hash_mismatch|SYN-bad|mismatch",
    )
    body = b"SYN-body"
    digest = hashlib.sha256(body).hexdigest()
    (source / f"{digest}.txt").write_bytes(body)
    assert (
        build._cached_body(
            tmp_path,
            "SYN-cache",
            digest,
            "txt",
            "SYN-source",
            "https://syn.invalid/page",
        )
        == b"SYN-body"
    )


@pytest.mark.parametrize(
    ("side", "expected"),
    [
        (
            None,
            "1|SYN-source|https://syn.invalid/page|missing_artifact|sidecar|missing",
        ),
        ([], "1|SYN-source|https://syn.invalid/page|missing_artifact|sidecar|missing"),
        ({}, "1|SYN-source|https://syn.invalid/page|missing_terms|terms hash|absent"),
        (
            {"terms_sha256": "", "retrieved_utc": "2026-01-03T04:05:06Z"},
            "1|SYN-source|https://syn.invalid/page|missing_terms|terms hash|absent",
        ),
        (
            {"terms_sha256": 3},
            "1|SYN-source|https://syn.invalid/page|missing_terms|terms hash|absent",
        ),
        (
            {"terms_sha256": "SYN-terms"},
            "1|SYN-source|https://syn.invalid/page|missing_lineage|retrieved_utc|absent",
        ),
        (
            {"terms_sha256": "SYN-terms", "retrieved_utc": ""},
            "1|SYN-source|https://syn.invalid/page|missing_lineage|retrieved_utc|absent",
        ),
        (
            {"terms_sha256": "SYN-terms", "retrieved_utc": 3},
            "1|SYN-source|https://syn.invalid/page|missing_lineage|retrieved_utc|absent",
        ),
    ],
)
def test_receipt_refuses_each_incomplete_slot(
    tmp_path: Path, side: object, expected: str
) -> None:
    source = tmp_path / "SYN-cache"
    source.mkdir()
    if side is not None:
        (source / "SYN-hash.meta.json").write_text(json.dumps(side), encoding="utf-8")
    _failure(
        build._receipt(
            tmp_path, "SYN-cache", "SYN-hash", "SYN-source", "https://syn.invalid/page"
        ),
        expected,
    )


def test_receipt_returns_the_selected_sidecar_values(tmp_path: Path) -> None:
    (tmp_path / "SYN-cache").mkdir()
    (tmp_path / "SYN-cache/SYN-hash.meta.json").write_text(
        '{"terms_sha256": "SYN-terms", "retrieved_utc": "2026-01-03T04:05:06Z"}',
        encoding="utf-8",
    )
    assert build._receipt(
        tmp_path, "SYN-cache", "SYN-hash", "SYN-source", "https://syn.invalid/page"
    ) == ("SYN-terms", "2026-01-03T04:05:06Z")


@pytest.mark.parametrize(
    "name",
    [
        "publisher",
        "page_url",
        "licence_id",
        "licence_basis",
        "decision_record",
        "terms_sha256",
        "retrieved_utc",
        "page_sha256",
    ],
)
@pytest.mark.parametrize("value", [None, "", 3])
def test_row_lineage_refuses_missing_slot(name: str, value: object) -> None:
    expected = {
        "publisher": "1|fdi_projects|https://syn.invalid/page|missing_lineage|publisher|absent",
        "page_url": "1|fdi_projects|https://syn.invalid/page|missing_lineage|page_url|absent",
        "licence_id": "1|fdi_projects|https://syn.invalid/page|missing_lineage|licence_id|absent",
        "licence_basis": "1|fdi_projects|https://syn.invalid/page|missing_lineage|licence_basis|absent",
        "decision_record": "1|fdi_projects|https://syn.invalid/page|missing_lineage|decision_record|absent",
        "terms_sha256": "1|fdi_projects|https://syn.invalid/page|missing_lineage|terms_sha256|absent",
        "retrieved_utc": "1|fdi_projects|https://syn.invalid/page|missing_lineage|retrieved_utc|absent",
        "page_sha256": "1|fdi_projects|https://syn.invalid/page|missing_lineage|page_sha256|absent",
    }
    _failure(
        build.validate_investment(
            (_row(**{name: value}),), _spec().bounds, _spec().confirmation, _envelope()
        ),
        expected[name],
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "1|fdi_projects|https://syn.invalid/page|provenance|public|missing"),
        (3, "1|fdi_projects|https://syn.invalid/page|provenance|public|missing"),
        (
            "synthetic",
            "1|fdi_projects|https://syn.invalid/page|provenance|public|synthetic",
        ),
        (
            "simulated",
            "1|fdi_projects|https://syn.invalid/page|provenance|public|simulated",
        ),
        ("PUBLIC", "1|fdi_projects|https://syn.invalid/page|provenance|public|PUBLIC"),
    ],
)
def test_row_provenance_names_the_exact_value(value: object, expected: str) -> None:
    _failure(
        build.validate_investment(
            (_row(provenance=value),), _spec().bounds, _spec().confirmation, _envelope()
        ),
        expected,
    )


@pytest.mark.parametrize("join", ["SYN-forbidden", 0, False, []])
def test_row_join_is_refused_even_when_falsey(join: object) -> None:
    _failure(
        build.validate_investment(
            (_row(join_key=join),), _spec().bounds, _spec().confirmation, _envelope()
        ),
        "1|fdi_projects|https://syn.invalid/page|prohibited_join|no join|joined",
    )


@pytest.mark.parametrize(
    "caveats", [None, [], ["SYN-other"], "fdi_estimates", ("fdi_estimates",)]
)
def test_project_caveat_is_a_required_list(caveats: object) -> None:
    row = _row(project_key="SYN-project-AA-0001", caveat_keys=caveats)
    _failure(
        build.validate_investment(
            (row,), _spec().bounds, _spec().confirmation, _envelope()
        ),
        "1|fdi_projects|https://syn.invalid/page|missing_caveat|fdi_estimates|absent",
    )


def test_row_cleaning_removes_only_join_key_and_never_mutates_input() -> None:
    for join in (None, ""):
        original = _row(join_key=join)
        expected = {key: value for key, value in original.items() if key != "join_key"}
        assert build.validate_investment(
            (original,), _spec().bounds, _spec().confirmation, _envelope()
        ) == (expected,)
        assert "join_key" in original
        assert original["join_key"] == join


@pytest.mark.parametrize(
    "changes",
    [
        {"parent_ordinal": "0"},
        {"parent_ordinal": []},
        {"ordinal": "1"},
        {"level": "3"},
        {"parent_ordinal": 4},
        {"parent_ordinal": 1},
        {"level": 2},
        {"page_url": "https://syn.invalid/other"},
    ],
)
def test_parent_relationship_rejects_each_invalid_component(
    changes: dict[str, object],
) -> None:
    rows = (
        _row(ordinal=0, level=2),
        _row(record_key="SYN-record-AA-0002", ordinal=1, level=3, parent_ordinal=0),
    )
    child = {**rows[1], **changes}
    _failure(
        build.validate_investment(
            (rows[0], child), _spec().bounds, _spec().confirmation, _envelope()
        ),
        "1|fdi_projects|https://syn.invalid/page|invalid_parent|earlier higher block|unmatched",
    )


def test_parent_accepts_zero_parent_and_continues_after_root() -> None:
    rows = (
        _row(ordinal=0, level=2),
        _row(record_key="SYN-record-AA-0002", ordinal=1, level=3, parent_ordinal=0),
    )
    result = build.validate_investment(
        rows, _spec().bounds, _spec().confirmation, _envelope()
    )
    assert isinstance(result, tuple)
    assert result[1]["parent_ordinal"] == 0
    malformed = (rows[0], {**rows[1], "parent_ordinal": 9})
    _failure(
        build.validate_investment(
            malformed, _spec().bounds, _spec().confirmation, _envelope()
        ),
        "1|fdi_projects|https://syn.invalid/page|invalid_parent|earlier higher block|unmatched",
    )


def test_parent_equal_ordinal_cannot_hide_behind_duplicate_level() -> None:
    rows = [
        _row(ordinal=1, level=3, parent_ordinal=1),
        _row(record_key="SYN-record-AA-0002", ordinal=1, level=2),
    ]
    _failure(
        build.validate_investment(
            tuple(rows), _spec().bounds, _spec().confirmation, _envelope()
        ),
        "1|fdi_projects|https://syn.invalid/page|invalid_parent|earlier higher block|unmatched",
    )


@pytest.mark.parametrize("value", [None, "", 2001])
def test_period_announced_requires_one_stated_string(value: object) -> None:
    _failure(
        build.validate_investment(
            (_row(announced=value),), _spec().bounds, _spec().confirmation, _envelope()
        ),
        "1|fdi_projects|https://syn.invalid/page|period_last|2001|missing",
    )


def test_period_latest_value_boundary_and_empty_field() -> None:
    spec = _spec()
    assert isinstance(
        build.validate_investment(
            (_row(),), spec.bounds, spec.confirmation, _envelope()
        ),
        tuple,
    )
    rows = (
        _row(announced="2000"),
        _row(record_key="SYN-record-AA-0002", announced="1999"),
    )
    _failure(
        build.validate_investment(rows, spec.bounds, spec.confirmation, _envelope()),
        "1|fdi_projects|https://syn.invalid/page|period_last|2001|2000",
    )
    # A blank configured field disables the period guard, even if that key exists.
    blank = _row(**{"": "1999"})
    assert isinstance(
        build.validate_investment(
            (blank,),
            replace(spec.bounds, period_field=""),
            spec.confirmation,
            _envelope(),
        ),
        tuple,
    )
    _failure(
        build._period_failure(
            ({"announced": "XXXX"},),
            Bounds(1, 3, "announced", "ZZZZ", True),
            _envelope(),
        ),
        "1|fdi_projects|https://syn.invalid/page|period_last|ZZZZ|XXXX",
    )


def test_parent_with_malformed_parent_level_is_refused() -> None:
    rows = (
        _row(ordinal=0, level="SYN-invalid-level"),
        _row(record_key="SYN-record-AA-0002", ordinal=1, level=3, parent_ordinal=0),
    )
    _failure(
        build.validate_investment(
            rows, _spec().bounds, _spec().confirmation, _envelope()
        ),
        "1|fdi_projects|https://syn.invalid/page|invalid_parent|earlier higher block|unmatched",
    )


def test_row_without_join_key_is_also_admitted() -> None:
    row = _row()
    del row["join_key"]
    assert build.validate_investment(
        (row,), _spec().bounds, _spec().confirmation, _envelope()
    ) == (row,)
