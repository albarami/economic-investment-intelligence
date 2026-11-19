"""Duplicate annual figures carry their own mismatch cause."""

from dataclasses import replace

from eii_core.calc.trade_reconciliation import all_pairs

from .test_trade_reconciliation import figure


def _pairs(rows):
    return all_pairs(
        rows,
        (("invented-source", "reporter"), ("invented-second", "mirror")),
        ("invented-partner",),
        (2020,),
        ("import",),
        ("invented-scope",),
    )


def test_duplicate_annual_beside_a_present_side_is_not_a_missing_side():
    duplicate = (
        figure(),
        replace(figure(), input_id="invented-duplicate"),
    )
    other = replace(
        figure(),
        source_id="invented-second",
        role="mirror",
        input_id="invented-right",
        value="10.25",
    )
    result = _pairs((*duplicate, other))
    assert result[0].gap is None
    assert result[0].left_input_id is None
    assert result[0].mismatch_codes == ("duplicate_annual",)


def test_duplicate_annual_keeps_a_genuinely_absent_side():
    rows = (figure(), replace(figure(), input_id="invented-duplicate"))
    result = _pairs(rows)
    assert result[0].mismatch_codes == ("missing_side", "duplicate_annual")
    assert "incomplete_calendar" not in result[0].mismatch_codes
