"""Receipt identity against the writer, on invented rows only."""

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
