"""Audit committed terms records without making unread terms a fetch gate."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from eii_custodian.publicdata.fetch.registry import (
    LICENCE_BASIS_PENDING,
    TERMS_WORDS_PENDING,
    RegistryError,
    load_registry,
    read_yaml,
    registry_path,
)


def _assert_terms_records(path: Path) -> None:
    # Reuse the loader's closed vocabulary and real-calendar-date checks.
    # Decision 0059 keeps incomplete readings loadable by the production reader.
    entries = load_registry(path)
    document = read_yaml(path)
    assert isinstance(document, dict)
    failures = []
    for row, entry in zip(document["sources"], entries, strict=True):
        basis = entry.licence_basis
        if basis == LICENCE_BASIS_PENDING:
            continue
        words = row.get("terms_words", "")
        if words == TERMS_WORDS_PENDING:
            # These are local-use/provider records, not claims of an open
            # dataset grant. Their unread terms remain usable (0059 item 1).
            if basis not in {"owner_decision", "provider_terms"}:
                failures.append((row["key"], "unread terms claim an open basis"))
            continue
        for field in ("terms_url", "terms_words", "terms_read_on"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                failures.append((row["key"], field))
        if row["terms_read_on"] == "pending":
            failures.append((row["key"], "terms_read_on"))
    assert not failures, failures


def test_committed_terms_records() -> None:
    _assert_terms_records(registry_path())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("terms_url", ""),
        ("terms_url", " \t "),
        ("terms_words", ""),
        ("terms_words", " \t "),
        ("terms_read_on", ""),
        ("terms_read_on", " \t "),
        ("terms_read_on", "2026-02-30"),
        ("terms_read_on", "pending"),
        ("licence_basis", "invented_basis"),
        ("terms_words", "terms to be read"),
    ],
)
def test_planted_incomplete_or_malformed_record_is_detected(
    tmp_path: Path, field: str, value: str
) -> None:
    document = read_yaml(registry_path())
    assert isinstance(document, dict)
    row = document["sources"][0]
    document = {"sources": [row]}
    row.update(
        licence_basis="dataset",
        terms_url="https://example.invalid/terms",
        terms_words="Invented terms for a synthetic guard plant.",
        terms_read_on="2026-11-19",
    )
    row[field] = value
    path = tmp_path / "planted.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises((AssertionError, RegistryError)):
        _assert_terms_records(path)


@pytest.mark.parametrize("basis", ["pending", ""])
def test_pending_basis_remains_loadable_and_auditable(
    tmp_path: Path, basis: str
) -> None:
    document = read_yaml(registry_path())
    assert isinstance(document, dict)
    row = document["sources"][0]
    document = {"sources": [row]}
    row.update(licence_basis=basis, terms_url="", terms_words="", terms_read_on="")
    path = tmp_path / "pending.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    _assert_terms_records(path)
    assert load_registry(path)[0].licence_basis == "pending"
