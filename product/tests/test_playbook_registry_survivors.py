"""Kills for the playbook registry: exact refusal text and the loaded record."""

from collections.abc import Callable
from dataclasses import replace

import pytest
from product.tests.test_public_playbook import catalogue

from eii_product.assistant.catalogue.schema import Question
from eii_product.assistant.playbooks.registry import load_playbook, validate_definition


def _assert_refusal(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(ValueError) as caught:
        call()
    assert str(caught.value) == expected


def test_site_check_definition_is_the_hand_written_record() -> None:
    definition = load_playbook("site_check", catalogue())
    again = validate_definition(definition.model_dump(), catalogue())
    assert again.name == "site_check"
    assert [(call.key, call.tool, dict(call.arguments)) for call in again.calls] == [
        ("resolve", "resolve", {"kind": "activity"}),
        ("near", "make_area", {"mode": "walk", "cutoff": 5}),
        ("wider", "make_area", {"mode": "drive", "cutoff": 10}),
        ("fly", "stage", {"directive": "fly", "zoom": "street"}),
        ("rings", "stage", {"directive": "rings"}),
        (
            "sector",
            "sector_facts",
            {"topic": "unit_economics", "geography": "national"},
        ),
        ("night", "night_lights", {}),
        ("population", "population_age_sex", {"split": "none"}),
    ]
    assert again.caveat_keys == []
    assert again.still_to_test == ["foundation_read_sources"]
    assert again.not_measured == []
    assert again.headline_key == "foundation_headline"
    assert again.decision_template_key == "foundation_decision"
    assert again.claims == []
    assert again.layout == [{"component": "foundation_note", "props": {}}]
    assert again.questions == [
        "foundation_ask_shape",
        "foundation_ask_walk",
        "foundation_ask_context",
    ]


def test_unknown_playbook_name_is_refused() -> None:
    _assert_refusal(lambda: load_playbook("invented", catalogue()), "NOT_FOUND")


def test_duplicate_call_key_is_refused() -> None:
    raw = load_playbook("site_check", catalogue()).model_dump()
    raw["calls"][1]["key"] = raw["calls"][0]["key"]
    _assert_refusal(lambda: validate_definition(raw, catalogue()), "duplicate_call")


def test_unknown_question_is_refused() -> None:
    raw = load_playbook("site_check", catalogue()).model_dump()
    raw["questions"] = ["invented"]
    _assert_refusal(lambda: validate_definition(raw, catalogue()), "unknown_question")


def test_question_of_another_playbook_is_refused() -> None:
    cat = catalogue()
    widened = replace(
        cat,
        questions=(*cat.questions, Question("invented_ask", "invented", (), (), ())),
    )
    raw = load_playbook("site_check", cat).model_dump()
    raw["questions"] = ["invented_ask"]
    _assert_refusal(lambda: validate_definition(raw, widened), "unknown_question")


def test_unknown_fragment_is_refused() -> None:
    raw = load_playbook("site_check", catalogue()).model_dump()
    raw["headline_key"] = "invented"
    _assert_refusal(lambda: validate_definition(raw, catalogue()), "unknown_fragment")


def test_unknown_claim_is_refused() -> None:
    raw = load_playbook("site_check", catalogue()).model_dump()
    raw["claims"] = [{"claim_key": "invented", "slots": {}}]
    _assert_refusal(lambda: validate_definition(raw, catalogue()), "unknown_claim")
