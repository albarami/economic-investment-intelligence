"""The committed tender review joins to a fresh, invented archive receipt."""

import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from custodian.tests.singles_entries import tender_entry
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_tenders import archive_pages, terms_body_hash
from eii_custodian.publicdata.confirm_s2_t13 import (
    completion_evidence,
    load_confirmation,
)
from eii_custodian.publicdata.fetch.snapshots import read_snapshot
from eii_custodian.publicdata.singles.tenders import (
    LIST_PATHS,
    ListReading,
    _write_pages,
)

REVIEW = (
    Path(__file__).resolve().parents[1] / "publicdata/review/s2_t13_confirmation.yaml"
)


def _fresh(tmp_path):
    entry = tender_entry()
    confirmation = load_confirmation(REVIEW)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    pairs = [(name, language) for name, _ in LIST_PATHS for language in ("en", "ar")]
    pages = [(name, language, 1, b"<html>SYN-page</html>") for name, language in pairs]
    readings = [
        ListReading(name, language, 1, 1, stamp, stamp) for name, language in pairs
    ]
    _write_pages(tmp_path / entry.key, pages, readings)
    identity = archive_pages(
        tmp_path, entry, stamp, terms_sha256=confirmation.tender.terms_sha256
    )
    receipt = read_snapshot(tmp_path / entry.key, identity).sidecar
    return confirmation, entry, receipt


def test_committed_review_accepts_fresh_archive(tmp_path):
    confirmation, entry, receipt = _fresh(tmp_path)
    assert receipt["retrieved_utc"] != confirmation.tender.retrieved_utc
    assert receipt["sha256"] != confirmation.tender.page_sha256
    assert completion_evidence(confirmation, entry, receipt) == confirmation


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("terms_sha256", "0" * 64),
        ("terms_sha256", None),
        ("fetch_url", "https://monaqasat.mof.gov.qa/other"),
        ("source_id", "another_source"),
        ("key", "another_source"),
        ("sha256", "bad"),
        ("retrieved_utc", "not-a-date"),
    ],
)
def test_receipt_substitutions_refused(tmp_path, field, value):
    confirmation, entry, receipt = _fresh(tmp_path)
    receipt[field] = value
    with pytest.raises(ValueError, match="do not confirm tender"):
        completion_evidence(confirmation, entry, receipt)


@pytest.mark.parametrize("value", ["", "a" * 63, "a" * 65, "G" * 64, "a" * 63 + "!"])
def test_sha_boundaries_refused(tmp_path, value):
    confirmation, entry, receipt = _fresh(tmp_path)
    receipt["sha256"] = value
    with pytest.raises(ValueError, match="do not confirm tender"):
        completion_evidence(confirmation, entry, receipt)


@pytest.mark.parametrize(
    "value", [None, "", "2026-11-21T00:00:00", "2026-11-21T03:00:00+03:00"]
)
def test_missing_or_non_utc_retrieval_refused(tmp_path, value):
    confirmation, entry, receipt = _fresh(tmp_path)
    receipt["retrieved_utc"] = value
    with pytest.raises(ValueError, match="do not confirm tender"):
        completion_evidence(confirmation, entry, receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("url", "https://other.invalid/tenders"),
        ("terms_url", "https://other.invalid/terms"),
        ("fetch_host", "other.invalid"),
        ("release_tables", ()),
        ("publisher", "other publisher"),
        ("licence_basis", "dataset"),
        ("decision_record", "other"),
        ("period_first", "different"),
        ("period_last", "different"),
        ("skip_reason", "unavailable"),
    ],
)
def test_registry_substitutions_refused(tmp_path, field, value):
    confirmation, entry, receipt = _fresh(tmp_path)
    with pytest.raises(ValueError, match="do not confirm tender"):
        completion_evidence(confirmation, replace(entry, **{field: value}), receipt)


@pytest.mark.parametrize("plant", ["missing", "duplicate", "other_url", "no_body_hash"])
def test_run_terms_record_must_be_unique_and_bound(tmp_path, plant):
    entry = tender_entry()
    row = {
        "key": entry.key,
        "terms_url": entry.terms_url,
        "terms_fingerprint": "visible_text",
        "terms_body_sha256": "a" * 64,
    }
    rows = [row]
    if plant == "missing":
        rows = []
    elif plant == "duplicate":
        rows.append(row.copy())
    elif plant == "other_url":
        row["terms_url"] = "https://other.invalid/terms"
    else:
        del row["terms_body_sha256"]
    with pytest.raises(AssemblyError, match="assembly_tender_terms_incomplete"):
        terms_body_hash(tmp_path, entry, rows)


def test_terms_read_carries_its_raw_body_hash(tmp_path, monkeypatch):
    from eii_custodian.publicdata.fetch import build
    from eii_custodian.publicdata.fetch.kinds import TermsPage
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    entry = tender_entry()
    body = b"<html>Invented terms</html>"
    monkeypatch.setattr(
        build,
        "read_terms_page",
        lambda *_: TermsPage(sha256_hex(b"Invented terms"), None, body),
    )
    terms = []
    build._read_terms_apart(
        entry,
        lambda *_: None,
        lambda *_: None,
        lambda: "2026-11-21T00:00:00Z",
        [],
        terms,
        {},
        tmp_path,
        [],
    )
    assert terms_body_hash(tmp_path, entry, terms) == sha256_hex(body)
    terms[0]["terms_sha256"] = "0" * 64
    with pytest.raises(AssemblyError, match="assembly_tender_terms_incomplete"):
        terms_body_hash(tmp_path, entry, terms)


@given(
    value=st.text().filter(lambda value: re.fullmatch(r"[0-9a-f]{64}", value) is None)
)
def test_every_malformed_sha_is_refused(value):
    from custodian.tests.test_s2_t13_confirmation import (
        receipt as invented_receipt,
    )
    from custodian.tests.test_s2_t13_confirmation import registry_record, tender

    t = tender()
    entry = registry_record(t)
    receipt = invented_receipt(t, entry)
    receipt["sha256"] = value
    from eii_custodian.publicdata.confirm_s2_t13 import tender_disposition

    assert not tender_disposition(t, entry, receipt).shown
