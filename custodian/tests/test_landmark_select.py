"""Invented candidates in the supplied research nesting; no live source values."""

from copy import deepcopy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from eii_custodian.publicdata.heights.landmark_select import select_landmarks


def citation_page(**changes):
    row = {
        "name_en": "SYN Example Tower",
        "area_or_street": "SYN Invented District",
        "height_m": "123.40",
        "unit_as_written": "m",
        "height_kind": "roof",
        "height_excerpt": "Roof: 123.40 m",
        "floors": "SYN not used",
        "floors_kind": "SYN not used",
        "completed": "2020",
        "page_url": "https://syn.example.invalid/a",
        "publisher": "SYN Publisher",
        "publisher_kind": "SYN invented reference",
        "retrieved_on": "2026-11-21",
        "terms_url": "https://syn.example.invalid/terms",
        "terms_words": "SYN invented terms",
        "additional_heights": [],
        "terms_checked_on": "2026-11-21",
        "independence_note": "SYN not independently corroborated",
    }
    row.update(changes)
    return row


def candidate(**changes):
    row = citation_page()
    row.update(
        {
            "landmark_id": "SYN-LM-A",
            "subject_kind": "completed_highrise_building",
            "status_as_written": "SYN completed",
            "row_role": "SYN primary",
            "disagrees": False,
            "agreement_basis": "SYN not compared",
            "comparison": "SYN not compared",
            "review_notes": [],
            "second_page": None,
        }
    )
    row.update(changes)
    return row


def test_research_subject_kind_is_admitted():
    row = candidate(subject_kind="completed_highrise_building")
    result = select_landmarks([row])
    assert result.outcomes == (("SYN-LM-A", "admitted"),)
    assert result.admitted[0].page is row


@pytest.mark.parametrize(
    "subject_kind",
    ["completed_highrise_building; under_review", "completed high-rise"],
)
def test_subject_kind_requires_the_exact_research_code(subject_kind):
    result = select_landmarks([candidate(subject_kind=subject_kind)])
    assert result.outcomes == (("SYN-LM-A", "not_building"),)
    assert not result.admitted


def test_one_page_is_enough_and_counts_are_closed():
    result = select_landmarks([candidate()])
    assert result.admitted[0].page["height_m"] == "123.40"
    assert result.by_kind == {"roof": 1, "architectural": 0}
    assert result.counts == {
        "admitted": 1,
        "not_building": 0,
        "kind_not_admitted": 0,
        "excerpt_mismatch": 0,
        "same_kind_disagreement": 0,
    }


@pytest.mark.parametrize("unit", ["m", "metre", "metres", "meter", "meters", "METRES"])
def test_literal_metric_units(unit):
    assert (
        len(
            select_landmarks(
                [candidate(unit_as_written=unit, height_excerpt=f"Roof: 123.40 {unit}")]
            ).admitted
        )
        == 1
    )


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"subject_kind": "sculpture"}, "not_building"),
        ({"completed": None}, "not_building"),
        ({"height_kind": "tip"}, "kind_not_admitted"),
        ({"height_qualifier": "approximate"}, "kind_not_admitted"),
        ({"unit_as_written": "ft"}, "excerpt_mismatch"),
        ({"height_excerpt": "Roof: 123.41 m"}, "excerpt_mismatch"),
        ({"height_excerpt": "Roof: 9123.40 m"}, "excerpt_mismatch"),
        ({"height_excerpt": "Roof: 123.40 miles"}, "excerpt_mismatch"),
        ({"height_m": "NaN"}, "excerpt_mismatch"),
        ({"height_excerpt": "Height: 123.40 m"}, "kind_not_admitted"),
        (
            {
                "second_page": citation_page(
                    height_m="123.4", height_excerpt="Roof: 123.4 m"
                )
            },
            "same_kind_disagreement",
        ),
        (
            {"additional_heights": [{"height_kind": "roof", "height_m": "124"}]},
            "same_kind_disagreement",
        ),
    ],
)
def test_each_refusal_changes_one_input(change, reason):
    result = select_landmarks([candidate(**change)])
    assert result.outcomes == (("SYN-LM-A", reason),)
    assert result.counts[reason] == 1
    assert not result.admitted


def test_cross_kind_is_not_conflict_and_comment_excerpt_is_allowed():
    row = candidate(
        second_page=citation_page(
            height_kind="architectural",
            height_m="130",
            height_excerpt="Architectural: 130 m",
        ),
        height_excerpt="SYN comment: Roof: 123.40 m",
    )
    assert len(select_landmarks([row]).admitted) == 1


def test_second_page_can_supply_the_admitted_kind():
    row = candidate(height_kind="tip")
    row["second_page"] = citation_page()
    assert select_landmarks([row]).admitted[0].page is row["second_page"]


def test_rule_order_and_empty():
    assert select_landmarks([]).admitted == ()
    result = select_landmarks([candidate(subject_kind="sculpture", height_kind="tip")])
    assert result.outcomes == (("SYN-LM-A", "not_building"),)


@given(
    st.integers(min_value=1, max_value=999999),
    st.sampled_from(["roof", "architectural"]),
)
def test_value_tokens_are_copied_and_precision_is_never_computed(n, kind):
    token = f"{n}.00"
    row = candidate(
        height_m=token, height_kind=kind, height_excerpt=f"{kind}: {token} m"
    )
    result = select_landmarks([row])
    assert result.admitted[0].page["height_m"] == token
    changed = deepcopy(row)
    changed["second_page"] = citation_page(
        height_kind=kind, height_m=str(n), height_excerpt=f"{kind}: {n} m"
    )
    assert select_landmarks([changed]).outcomes == (
        ("SYN-LM-A", "same_kind_disagreement"),
    )


def test_word_tokens_do_not_create_numeric_disagreement():
    row = candidate(
        second_page=citation_page(
            height_m="over one hundred", height_excerpt="Roof: over one hundred metres"
        )
    )
    assert select_landmarks([row]).outcomes == (("SYN-LM-A", "admitted"),)


def test_cross_page_additional_height_conflicts():
    row = candidate(
        second_page={
            "height_kind": "tip",
            "height_m": "150",
            "additional_heights": [{"height_kind": "roof", "height_m": "124"}],
        }
    )
    assert select_landmarks([row]).outcomes == (("SYN-LM-A", "same_kind_disagreement"),)


@given(
    st.from_regex(r"[0-9]+(?:\.[0-9]+)?", fullmatch=True),
    st.sampled_from(["m", "metre", "metres", "meter", "meters"]),
)
def test_entire_decimal_token_language_remains_literal(token, unit):
    row = candidate(
        height_m=token, unit_as_written=unit, height_excerpt=f"Roof: {token} {unit}"
    )
    assert select_landmarks([row]).admitted[0].page["height_m"] == token


@pytest.mark.parametrize(
    "field,value,excerpt",
    [
        ("height_m", "NaN", "Roof: 123.40 m; SYN invalid token: NaN m"),
        ("unit_as_written", "ft", "Roof: 123.40 m; SYN alternative: 123.40 ft"),
    ],
)
def test_numeric_and_unit_guards_cannot_hide_behind_excerpt_search(
    field, value, excerpt
):
    row = candidate(height_excerpt=excerpt)
    assert select_landmarks([row]).outcomes == (("SYN-LM-A", "admitted"),)
    row[field] = value
    assert select_landmarks([row]).outcomes == (("SYN-LM-A", "excerpt_mismatch"),)


def test_other_publisher_terms_do_not_hide_a_same_kind_conflict():
    other = citation_page(
        page_url="https://syn-other.example.invalid/b",
        publisher="SYN Other Publisher",
        terms_words="SYN restrictive terms",
        height_m="124",
        height_excerpt="Roof: 124 meters",
        unit_as_written="meters",
    )
    assert select_landmarks([candidate(second_page=other)]).outcomes == (
        ("SYN-LM-A", "same_kind_disagreement"),
    )
