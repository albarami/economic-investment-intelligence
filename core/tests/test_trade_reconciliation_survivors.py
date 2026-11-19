"""Invented exact reconciliation cases for the lead's surviving mutants."""

from dataclasses import replace
from fractions import Fraction

import pytest

from eii_core.calc import trade_reconciliation as tr

from .test_trade_reconciliation import figure


def refusal(caught, expected):
    assert str(caught.value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (Fraction(-1, 25), "-0.04"),
        (Fraction(1, 10**400), "0." + "0" * 399 + "1"),
        (Fraction(1, 25), "0.04"),
    ],
)
def test_terminating_text(value, expected):
    assert tr._text(value) == expected


@pytest.mark.parametrize("kind", ["left_missing", "right_missing", "mismatch", "valid"])
def test_complete_comparison(kind):
    left, right = figure(), replace(figure(), input_id="invented-right", value="10.20")
    if kind == "left_missing":
        left = None
    elif kind == "right_missing":
        right = None
    elif kind == "mismatch":
        right = replace(right, currency="invented-other")
    result = tr.compare_trade_sources(left, right)
    assert result == tr.Comparison(
        left,
        right,
        "-2.05" if kind == "valid" else None,
        ()
        if kind == "valid"
        else ("currency",)
        if kind == "mismatch"
        else ("missing_side",),
    )


def months():
    return tuple(
        replace(
            figure(),
            input_id=f"invented-month-{m}",
            periods=(f"2020-{m:02}",),
            value="0.1",
        )
        for m in range(1, 13)
    )


@pytest.mark.parametrize(
    "kind", ["empty", "duplicate_id", "multiple_periods", "wrong_period"]
)
def test_annual_coverage_messages(kind):
    rows = list(months())
    if kind == "empty":
        rows = []
    elif kind == "duplicate_id":
        rows[-1] = replace(rows[-1], input_id=rows[0].input_id)
    elif kind == "multiple_periods":
        rows[-1] = replace(rows[-1], periods=("2020-12", "2021-01"))
    else:
        rows[-1] = replace(rows[-1], periods=("2021-01",))
    with pytest.raises(ValueError) as caught:
        tr.annual_trade_sum(tuple(rows), output_id="invented-annual")
    refusal(caught, "annual_coverage")


def test_annual_identity_and_order():
    result = tr.annual_trade_sum(tuple(reversed(months())), output_id="invented-annual")
    assert result.input_id == "invented-annual"
    assert result.value == "1.2"
    assert result.periods == ("2020",)
    assert result.lineage == (
        "invented-month-1",
        "invented-month-2",
        "invented-month-3",
        "invented-month-4",
        "invented-month-5",
        "invented-month-6",
        "invented-month-7",
        "invented-month-8",
        "invented-month-9",
        "invented-month-10",
        "invented-month-11",
        "invented-month-12",
    )


def test_all_pairs_absent_first_and_two_present():
    left = figure()
    right = replace(
        left,
        source_id="invented-second",
        role="mirror",
        input_id="invented-right",
        value="10.25",
    )
    result = tr.all_pairs(
        (left, right),
        (
            ("invented-absent", "reporter"),
            ("invented-source", "reporter"),
            ("invented-second", "mirror"),
        ),
        ("invented-partner",),
        (2020,),
        ("import",),
        ("invented-scope",),
    )
    assert result == (
        tr.PairResult(
            "invented-partner",
            2020,
            "import",
            "invented-scope",
            "invented-absent",
            "reporter",
            "invented-source",
            "reporter",
            None,
            "invented-left",
            None,
            ("missing_side",),
        ),
        tr.PairResult(
            "invented-partner",
            2020,
            "import",
            "invented-scope",
            "invented-absent",
            "reporter",
            "invented-second",
            "mirror",
            None,
            "invented-right",
            None,
            ("missing_side",),
        ),
        tr.PairResult(
            "invented-partner",
            2020,
            "import",
            "invented-scope",
            "invented-source",
            "reporter",
            "invented-second",
            "mirror",
            "invented-left",
            "invented-right",
            "-2",
            (),
        ),
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("partner", "invented-other"),
        ("year", 2021),
        ("flow", "export"),
        ("product_scope", "invented-other"),
        ("source_id", "invented-other"),
    ],
)
def test_unrelated_month_is_not_incomplete(field, value):
    row = replace(figure(), periods=("2020-01",), **{field: value})
    result = tr.all_pairs(
        (row,),
        (("invented-source", "reporter"), ("invented-second", "mirror")),
        ("invented-partner",),
        (2020,),
        ("import",),
        ("invented-scope",),
    )
    assert result[0].mismatch_codes == ("missing_side",)


def test_published_annual_does_not_stop_other_groups():
    rows = (replace(figure(), source_id="invented-annual"), *months())
    prepared = tr.comparison_figures(rows)
    assert prepared[:-1] == rows
    assert len(prepared) == 14
    assert prepared[-1].input_id == (
        "annual:invented-month-1:invented-month-2:invented-month-3:invented-month-4:"
        "invented-month-5:invented-month-6:invented-month-7:invented-month-8:"
        "invented-month-9:invented-month-10:invented-month-11:invented-month-12"
    )
    assert prepared[-1].value == "1.2"


def test_extra_month_with_distinct_id_is_refused():
    rows = (*months(), replace(months()[0], input_id="invented-extra"))
    with pytest.raises(ValueError) as caught:
        tr.annual_trade_sum(rows, output_id="invented-annual")
    refusal(caught, "annual_coverage")


def test_duplicate_annual_is_missing_without_calendar_claim():
    rows = (figure(), replace(figure(), input_id="invented-duplicate"))
    result = tr.all_pairs(
        rows,
        (("invented-source", "reporter"), ("invented-second", "mirror")),
        ("invented-partner",),
        (2020,),
        ("import",),
        ("invented-scope",),
    )
    assert result[0].mismatch_codes == ("missing_side", "duplicate_annual")
    assert "incomplete_calendar" not in result[0].mismatch_codes


def test_single_month_has_coverage_refusal():
    with pytest.raises(ValueError) as caught:
        tr.annual_trade_sum((months()[0],), output_id="invented-annual")
    refusal(caught, "annual_coverage")
