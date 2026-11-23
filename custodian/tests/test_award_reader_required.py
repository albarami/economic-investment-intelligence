"""S2-P66 round three: required proof fields survive the reader boundary."""

from datetime import date

import pytest
from custodian.tests.test_award_page_states import URL, page, parsed, reader
from custodian.tests.test_award_proof_formats import intake, proof, reason
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.fetch import awards
from eii_custodian.publicdata.fetch.award_checks import AwardError

REQUIRED = ("SYN company", "SYN registration", "SYN amount", "award_date")


def assert_missing_refuses(dec, body, record, field):
    assert field in record
    changed = dict(record)
    del changed[field]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(awards, "parse_body", lambda *_: [changed])
        with pytest.raises(AwardError, match=r"^schema_missing$"):
            reader(dec, body)(URL)


@pytest.mark.parametrize("field", REQUIRED)
def test_reader_refuses_each_missing_required_key(field):
    dec, body = page()
    record = parsed(dec, body)[0]
    assert reader(dec, body)(URL)[0]["award_date"] == record["award_date"]
    assert "proof_date_status" not in record
    assert_missing_refuses(dec, body, record, field)


@given(
    field=st.sampled_from(REQUIRED),
    awarded=st.dates(min_value=date(1900, 1, 1)),
    order=st.permutations(REQUIRED),
)
def test_one_key_deletions_always_refuse(field, awarded, order):
    dec, body = page(dates=(f"{awarded.day:02}/{awarded.month:02}/{awarded.year:04}",))
    record = parsed(dec, body)[0]
    ordered = {key: record[key] for key in (*order, *record)}
    assert_missing_refuses(dec, body, ordered, field)


@pytest.mark.parametrize("value", [0, False])
def test_reader_revalidates_projected_date(value, monkeypatch):
    dec, body = page()
    record = parsed(dec, body)[0]
    record["award_date"] = value
    monkeypatch.setattr(awards, "parse_body", lambda *_: [record])
    with pytest.raises(AwardError, match=r"^schema_missing$"):
        reader(dec, body)(URL)


@pytest.mark.parametrize("side", ["intake", "proof"])
@pytest.mark.parametrize(
    "field,expected",
    [
        ("Company Name", "matched_name_not_compared"),
        ("Commercial Registration Number", "proof_mismatch"),
        ("Approved Value", None),
    ],
)
def test_comparison_defaults_keep_closed_single_deletion_outcomes(
    side, field, expected
):
    left, right = intake(), proof()
    assert reason(left, right) == "matched"
    del (left if side == "intake" else right)[field]
    if expected is None:
        expected = "intake_value_absent" if side == "intake" else "proof_value_absent"
    assert reason(left, right) == expected
