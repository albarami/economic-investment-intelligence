"""Invented workbook regressions for the S2-T29 quarterly continuity repair."""

import pytest
from custodian.tests.test_page_shapes_survivors_1 import (
    ANNUAL_ROW,
    BLANK_ROW,
    FOOTER_ROW,
    HEADER_ROW,
    Q1_ROW,
    run_workbook,
)
from custodian.tests.test_page_shapes_survivors_2 import move_row

from eii_custodian.publicdata.fetch.page_html import ShapeError


def quarter_transition(previous):
    return [
        HEADER_ROW,
        ANNUAL_ROW,
        BLANK_ROW,
        Q1_ROW.replace("<t>Q1</t>", f"<t>Q{previous}</t>"),
        move_row(Q1_ROW, 9, 10).replace("2031", "2032"),
        FOOTER_ROW,
    ]


def test_workbook_q1_to_next_year_q1_refused():
    with pytest.raises(ShapeError, match=r"^schema_missing$"):
        run_workbook(quarter_transition(1))


def test_workbook_q3_to_next_year_q1_refused():
    with pytest.raises(ShapeError, match=r"^schema_missing$"):
        run_workbook(quarter_transition(3))


def test_workbook_q2_to_next_year_q1_refused():
    with pytest.raises(ShapeError, match=r"^schema_missing$"):
        run_workbook(quarter_transition(2))


def test_workbook_q4_to_next_year_q1_exact_periods():
    assert [row["period"] for row in run_workbook(quarter_transition(4))] == [
        "2030",
        "2031-Q4",
        "2032-Q1",
    ]
