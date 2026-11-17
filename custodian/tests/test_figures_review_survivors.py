"""Closed review schemas and exact refusals; only invented source stand-ins."""

from typing import Any

import pytest
from custodian.tests.test_figures_review import figure

from eii_custodian.publicdata.figures_review import compare, validate_record


def malformed(value: Any) -> Any:
    return value


def assert_message(error, expected):
    assert str(error.value) == expected


def test_reviewer_identity_refusal_is_exact():
    with pytest.raises(ValueError) as error:
        compare([figure()], {})
    assert_message(error, "reviewer_ids_mismatch")


@pytest.mark.parametrize("kind", ["invented", "DRAW", "VERDICT", "XXverdictXX"])
def test_record_kind_refusal_is_exact_even_without_rows(kind):
    with pytest.raises(ValueError) as error:
        validate_record([], kind)
    assert_message(error, "review_record_kind_invalid")


@pytest.mark.parametrize("value", ["", " ", None, 3])
def test_record_values_must_be_nonblank_text(value):
    row = {"figure_id": "invented", "url": "https://example.org", "result": "match"}
    row["figure_id"] = malformed(value)
    with pytest.raises(ValueError) as error:
        validate_record([row], "verdict")
    assert_message(error, "committed_source_value")


@pytest.mark.parametrize("result", ["invented", "MATCH", "XXmatchXX", "NO MATCH"])
def test_verdict_result_refusal_is_exact(result):
    with pytest.raises(ValueError) as error:
        validate_record(
            [{"figure_id": "invented", "url": "https://example.org", "result": result}],
            "verdict",
        )
    assert_message(error, "review_result_invalid")
