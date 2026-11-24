"""AI-18 definition data, checked against the existing closed catalogues."""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict

from eii_product.assistant.catalogue.schema import Catalogue


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Call(Closed):
    key: str
    tool: Literal[
        "resolve",
        "make_area",
        "stage",
        "sector_facts",
        "night_lights",
        "population_age_sex",
    ]
    arguments: dict[str, Any]


class Selection(Closed):
    claim_key: str
    slots: dict[str, str]
    strength: Literal["strong", "indicative", "illustrative"] = "strong"


class Definition(Closed):
    name: Literal["site_check"]
    calls: list[Call]
    caveat_keys: list[str]
    still_to_test: list[str]
    not_measured: list[str]
    headline_key: str
    decision_template_key: str
    claims: list[Selection]
    layout: list[dict[str, Any]]
    questions: list[str]


def validate_definition(raw: object, catalogue: Catalogue) -> Definition:
    result = Definition.model_validate(raw)
    if len({call.key for call in result.calls}) != len(result.calls):
        raise ValueError("duplicate_call")
    for key in result.questions:
        question = catalogue.find_question(key)
        if question is None or question.playbook != result.name:
            raise ValueError("unknown_question")
    for key in (result.headline_key, result.decision_template_key):
        if catalogue.find_fragment(key) is None:
            raise ValueError("unknown_fragment")
    for selection in result.claims:
        if catalogue.find_claim(selection.claim_key) is None:
            raise ValueError("unknown_claim")
    return result


def load_playbook(name: str, catalogue: Catalogue) -> Definition:
    if name != "site_check":
        raise ValueError("NOT_FOUND")
    path = Path(__file__).resolve().parents[4] / "assistant/playbooks/site_check.yaml"
    return validate_definition(
        yaml.safe_load(path.read_text(encoding="utf-8")), catalogue
    )
