"""Receipt identity against the writer, on invented rows only."""

import json
import re

import pytest
from custodian.tests.test_source_completeness import entry, receipt
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata import completeness as c

_LABEL = re.compile(r"\Adistinct labels (?:0|[1-9][0-9]*)\Z")
_RULE = "sit=row;form=published_label;field=period"


def _label_row():
    return entry(
        period_field=_RULE,
        period_first="2025",
        period_last="Q3-2025",
    )


def _label_receipt(row):
    evidence = receipt(row)
    evidence["period_first"] = None
    evidence["period_last"] = None
    evidence["coverage_note"] = "distinct labels 3"
    return evidence


def test_published_label_receipt_keeps_the_label_count_and_null_bounds():
    row = _label_row()
    assert c.receipt_disagreement(row, _label_receipt(row)) == ""
    assert c.receipt_valid(row, _label_receipt(row)) is True


def test_published_label_rejects_a_note_that_is_not_a_label_count():
    row = _label_row()
    evidence = _label_receipt(row)
    evidence["coverage_note"] = "distinct labels"
    assert c.receipt_disagreement(row, evidence) == "coverage_note"


@pytest.mark.parametrize(
    "note", ["", "distinct labels 03", "distinct labels 3 ", 3, None]
)
def test_published_label_rejects_one_bad_note(note):
    row = _label_row()
    evidence = _label_receipt(row)
    evidence["coverage_note"] = note
    assert c.receipt_disagreement(row, evidence) == "coverage_note"


def test_published_label_rejects_a_bound_taken_from_the_registry():
    row = _label_row()
    evidence = _label_receipt(row)
    evidence["period_first"] = "2025"
    assert c.receipt_disagreement(row, evidence) == "period_first"


def test_year_text_rejects_a_label_count_note():
    row = entry(
        period_field="sit=row;form=year_text;field=year",
        period_first="2020",
        period_last="2020",
    )
    evidence = receipt(row)
    evidence["coverage_note"] = "distinct labels 3"
    assert c.receipt_disagreement(row, evidence) == "coverage_note"


def test_publisher_case_fold_matches_the_fetch_rule():
    row = entry(publisher="Kahramaa")
    evidence = receipt(row)
    evidence["publisher"] = "KAHRAMAA"
    assert c.receipt_disagreement(row, evidence) == ""


def test_publisher_of_another_name_is_refused():
    row = entry(publisher="Kahramaa")
    evidence = receipt(row)
    evidence["publisher"] = "Other Authority"
    assert c.receipt_disagreement(row, evidence) == "publisher"


def test_blank_licence_identifier_is_refused():
    row = entry(licence_id=" ")
    evidence = receipt(row)
    assert c.receipt_disagreement(row, evidence) == "licence_id"


def test_file_descriptor_mismatch_is_refused():
    row = entry(
        source_id="worldpop_qat_agesex",
        cell_units="unconfirmed",
        doi_confirmed=False,
    )
    evidence = receipt(row)
    evidence["file"]["cell_units"] = "people_per_cell"
    evidence["file"]["doi_confirmed"] = True
    assert c.receipt_disagreement(row, evidence) == "file"


@given(st.text(max_size=200))
def test_label_note_accepts_only_the_writer_shape(note: str):
    row = _label_row()
    evidence = _label_receipt(row)
    evidence["coverage_note"] = note
    reason = c.receipt_disagreement(row, evidence)
    if _LABEL.fullmatch(note):
        assert reason == ""
    else:
        assert reason == "coverage_note"


def test_one_renamed_column_is_refused():
    row = entry(columns=(("years", "integer"), ("value", "number")))
    evidence = receipt(row)
    assert c.receipt_disagreement(row, evidence) == ""
    evidence["columns"][0]["name"] = "year"
    assert c.receipt_disagreement(row, evidence) == "columns"


def test_published_label_rejects_a_last_bound_taken_from_the_registry():
    row = _label_row()
    evidence = _label_receipt(row)
    evidence["period_last"] = "Q3-2025"
    assert c.receipt_disagreement(row, evidence) == "period_last"


@pytest.mark.parametrize("field", ["terms_words", "terms_read_on", "licence_basis"])
def test_terms_records_may_drift(field):
    row = entry()
    evidence = receipt(row)
    evidence[field] = "Invented later reading"
    assert c.receipt_disagreement(row, evidence) == ""


@pytest.mark.parametrize(
    "field",
    ["key", "source_id", "publisher", "title_en", "licence_id", "decision_record"],
)
def test_identity_fields_still_refuse_drift(field):
    row = entry()
    evidence = receipt(row)
    evidence[field] = "Invented other identity"
    assert c.receipt_disagreement(row, evidence) == field


def test_digest_shape_and_snapshot_reader_boundary():
    # test_snapshot_refusals.test_snapshot_refusal_site[read_body_hash] proves
    # the snapshot reader refuses a byte mismatch.
    row = entry()
    evidence = receipt(row)
    evidence["sha256"] = "c" * 64
    assert c.receipt_disagreement(row, evidence) == ""
    evidence["sha256"] = "invalid"
    assert c.receipt_disagreement(row, evidence) == "digest"


@pytest.mark.parametrize("field", ["period_first", "period_last"])
def test_observed_period_requires_independent_evidence(field):
    row = entry()
    evidence = receipt(row)
    evidence.update(period_first="2026-01-01", period_last="2026-01-03")
    bounds = ("2026-01-01", "2026-01-03")
    assert c.receipt_disagreement(row, evidence, observed_periods=bounds) == ""
    evidence[field] = "2026-01-02"
    assert c.receipt_disagreement(row, evidence, observed_periods=bounds) == field


@pytest.mark.parametrize("field", ["period_first", "period_last"])
def test_stated_period_remains_authoritative(field):
    row = entry(period_first="2026-01-01", period_last="2026-01-03")
    evidence = receipt(row)
    evidence[field] = "2026-01-02"
    assert (
        c.receipt_disagreement(
            row, evidence, observed_periods=("2026-01-02", "2026-01-02")
        )
        == field
    )


def test_observed_period_without_evidence_refuses_first_bound():
    row = entry()
    evidence = receipt(row)
    evidence.update(period_first="2026-01-01", period_last="2026-01-03")
    evidence["summary"] = {"date_first": "2026-01-01", "date_last": "2026-01-03"}
    assert c.receipt_disagreement(row, evidence) == "period_first"


def test_registry_has_no_empty_licence_on_non_skipped_rows():
    from eii_custodian.publicdata.fetch.registry import load_registry

    assert [
        row.key
        for row in load_registry()
        if not row.skip_reason and not row.licence_id.strip()
    ] == []


def test_check_prints_disagreeing_field():
    from custodian.tests.test_source_completeness import failures, inputs

    args = inputs()
    args["receipts"]["invented"]["title_en"] = "Invented changed title"
    assert failures(c.check(**args)) == [
        {
            "id": "invented",
            "state": "failed",
            "reason": "source_receipt_missing: field=title_en",
        }
    ]


def test_audit_periods_resolve_fsq_dated_manifest(tmp_path):
    from custodian.tests.test_production_adapters import context

    from eii_custodian.publicdata.assembly_reports import observed_periods
    from eii_custodian.publicdata.fetch.receipts import sha256_hex
    from eii_custodian.publicdata.fetch.snapshots import publish_snapshot

    row = entry("places_fsq", key="places_fsq/copy")
    state = context(tmp_path, (row,))
    snap = publish_snapshot(
        tmp_path / row.key / "2026-01-03" / "manifests",
        "json",
        b"{}",
        dict(receipt(row), sha256=sha256_hex(b"{}"), bytes=2),
    )
    state.selected[row.key] = snap.sha256
    state.receipts[row.key] = receipt(row)
    assert observed_periods(state) == {row.key: ("2026-01-03", "2026-01-03")}


def test_audit_periods_recompute_awards_from_saved_batch(tmp_path, monkeypatch):
    from custodian.tests.test_production_adapters import context

    from eii_custodian.publicdata.assembly_reports import observed_periods
    from eii_custodian.publicdata.fetch import page_records
    from eii_custodian.publicdata.fetch.receipts import sha256_hex

    row = entry("awards_owner_scrape")
    state = context(tmp_path, (row,))
    directory = tmp_path / "intake" / row.key
    directory.mkdir(parents=True)
    from custodian.tests.test_s2_t29_awards import profile

    body = b"syn_company,syn_reg,syn_value,syn_date,report_url\nSYN A,SYN-a,1,03/01/2026,https://example.org/a\nSYN B,SYN-b,2,01/01/2026,https://example.org/b\n"
    (directory / "syn.csv").write_bytes(body)
    (directory / "intake.json").write_text(
        json.dumps(
            {
                "file": "syn.csv",
                "sha256": sha256_hex(body),
                "seed": 17,
                "register_selections": {},
            }
        )
    )
    declaration = {"max_bytes": 4096, "profile": profile()}
    monkeypatch.setattr(page_records, "load_declaration", lambda _key: declaration)
    state.selected[row.key] = "a" * 64
    state.receipts[row.key] = dict(receipt(row), summary={"date_first": "2099-01-01"})
    assert observed_periods(state) == {row.key: ("2026-01-01", "2026-01-03")}


@given(st.text(max_size=200))
def test_any_recorded_terms_wording_preserves_identity(words):
    row = entry()
    evidence = receipt(row)
    evidence["terms_words"] = words
    assert c.receipt_disagreement(row, evidence) == ""


def test_check_uses_independent_period_evidence():
    from custodian.tests.test_source_completeness import failures, inputs

    args = inputs()
    args["receipts"]["invented"].update(
        period_first="2026-01-01", period_last="2026-01-03"
    )
    assert (
        failures(
            c.check(**args, observed_periods={"invented": ("2026-01-01", "2026-01-03")})
        )
        == []
    )
    assert failures(c.check(**args)) == [
        {
            "id": "invented",
            "state": "failed",
            "reason": "source_receipt_missing: field=period_first",
        }
    ]
