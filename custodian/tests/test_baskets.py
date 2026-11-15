"""Invented bilingual descriptions only: these are not reviewed real tariff lines."""

from copy import deepcopy

import pytest

from eii_custodian.publicdata.series.baskets import (
    historical_selection,
    reviewed_inputs,
    tariff_digits,
)


def invented_review():
    item = {
        "name": "invented pasta",
        "lines": [
            {
                "code": "19.02.11.10.00.01",
                "description_en": "invented pasta",
                "description_ar": "معكرونة تجريبية",
            }
        ],
        "inclusion_reason": "Invented dry pasta test",
        "excluded_lines": [
            {"code": "19.02.11.10.00.02", "reason": "invented instant noodles"}
        ],
        "supplier_isic": "4630",
        "reviewer_role": "fixture reviewer",
        "review_date": "2026-11-14",
        "source_sha256": "a" * 64,
    }
    return {
        "activities": [
            {"activity": activity, "inputs": [deepcopy(item)]}
            for activity in ("5610", "5630", "5510")
        ]
    }


def test_review_all_activities_and_required_fields() -> None:
    review = invented_review()
    assert len(reviewed_inputs(review, "5610")) == 1
    for field in (
        "inclusion_reason",
        "excluded_lines",
        "supplier_isic",
        "reviewer_role",
        "review_date",
        "source_sha256",
        "lines",
    ):
        planted = deepcopy(review)
        del planted["activities"][0]["inputs"][0][field]
        with pytest.raises(ValueError, match="incomplete review fields"):
            reviewed_inputs(planted, "5610")
    for field in ("reviewer_role", "review_date"):
        planted = deepcopy(review)
        planted["activities"][0]["inputs"][0][field] = ""
        with pytest.raises(ValueError, match="missing review metadata"):
            reviewed_inputs(planted, "5610")


def test_activity_and_input_limits() -> None:
    review = invented_review()
    review["activities"].pop()
    with pytest.raises(ValueError, match="wrong playbook activities"):
        reviewed_inputs(review, "5610")


@pytest.mark.parametrize(
    "field,value",
    [
        ("description_en", ""),
        ("description_ar", ""),
    ],
)
def test_bad_bilingual_pasta_review_refused(field: str, value: str) -> None:
    review = invented_review()
    review["activities"][0]["inputs"][0]["lines"][0][field] = value
    with pytest.raises(ValueError, match="review needs bilingual descriptions"):
        reviewed_inputs(review, "5610")


def test_input_limit_refused() -> None:
    review = invented_review()
    review["activities"][0]["inputs"] *= 9
    with pytest.raises(ValueError, match="basket exceeds eight inputs"):
        reviewed_inputs(review, "5610")


@pytest.mark.parametrize(
    "code", ["19.02", "19.02.11", "invalid", "1902" + "1110", "19..02.11.10"]
)
def test_coarse_or_undotted_line_refused(code: str) -> None:
    with pytest.raises(
        ValueError,
        match="coarse tariff line"
        if code in {"19.02", "19.02.11"}
        else "tariff code must be dotted",
    ):
        tariff_digits(code)


def test_historical_parent_selected_once_and_contamination_marked() -> None:
    rows = [
        {"tariff_code": "19.02.11.10", "value_qar": "75"},
        {"tariff_code": "19.02.99.99", "value_qar": "100"},
    ]
    selected = ["19.02.11.10.00.01", "19.02.11.10.00.03"]
    assert historical_selection(rows, selected, []) == [
        {"tariff_code": "19.02.11.10", "value_qar": "75", "rollup_note": ""}
    ]
    assert historical_selection(rows, selected, ["19.02.11.10.00.02"]) == [
        {
            "tariff_code": "19.02.11.10",
            "value_qar": "75",
            "rollup_note": "includes excluded lines",
        }
    ]


def test_selected_activity_keeps_its_own_basket() -> None:
    review = invented_review()
    for row in review["activities"]:
        row["inputs"][0]["name"] = "invented " + row["activity"]
    for activity in ("5610", "5630", "5510"):
        assert reviewed_inputs(review, activity)[0]["name"] == "invented " + activity


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("review_date", "2026-13-40", "month must be in 1..12"),
        ("source_sha256", "zz", "review source hash missing"),
        ("lines", [], "review lines missing"),
        (
            "excluded_lines",
            [{"code": "19.02.11.10.00.02", "reason": ""}],
            "review exclusion reason missing",
        ),
    ],
)
def test_review_named_refusals(field, value, reason):
    review = invented_review()
    review["activities"][0]["inputs"][0][field] = value
    with pytest.raises(ValueError, match=reason):
        reviewed_inputs(review, "5610")


def test_activities_must_be_a_list():
    with pytest.raises(ValueError, match="missing activities"):
        reviewed_inputs({"activities": "invented"}, "5610")
