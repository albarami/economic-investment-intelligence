"""Regressions for catalogue review L-1097 findings one and two."""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path
from typing import Any

import pytest

from eii_product.assistant.catalogue.schema import Claim, Slot

_SPEC = importlib.util.spec_from_file_location(
    "catalogue_foundations_helpers",
    Path(__file__).with_name("test_catalogue_foundations.py"),
)
assert _SPEC is not None and _SPEC.loader is not None
_FOUNDATIONS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FOUNDATIONS)


def _load(tmp: Path, subject: str, **slot: str) -> tuple[Any, Any]:
    return _FOUNDATIONS._load(
        tmp,
        _FOUNDATIONS._claims(
            _FOUNDATIONS._claim(subject=subject, slots=_FOUNDATIONS._slot(**slot))
        ),
    )


def _match(subject: str, **overrides: str) -> Any:
    """Bypass loading to prove the matching guard independently."""
    module = _FOUNDATIONS._api()
    catalogue = module.load_catalogue(_FOUNDATIONS.SHIPPED)
    fact = _FOUNDATIONS._fact(module, geography_kind="public", **overrides)
    slot = Slot(
        "reading",
        fact.metric_key,
        fact.unit,
        fact.geography_kind,
        "calendar_year",
        (fact.provenance,),
        "none",
    )
    claim = Claim("subject_note", "observed", subject, (slot,), (), (), (), ())
    catalogue = dataclasses.replace(catalogue, claims=(claim,))
    return module.match_slots(
        catalogue, claim.key, {"reading": fact.fact_id}, {fact.fact_id: fact}
    )


def test_district_public_loads_and_matches(tmp_path: Path) -> None:
    module, loaded = _load(tmp_path, "district", geo="public")
    assert isinstance(loaded, module.Catalogue)
    fact = _FOUNDATIONS._fact(module, geography_kind="public")
    assert (
        module.match_slots(
            loaded, "area_note", {"reading": fact.fact_id}, {fact.fact_id: fact}
        )
        is None
    )


@pytest.mark.parametrize("provenance", ["synthetic", "simulated"])
def test_district_non_public_refuses_at_load(tmp_path: Path, provenance: str) -> None:
    module, loaded = _load(tmp_path, "district", geo="public", provenance=provenance)
    assert loaded == module.Refusal(
        "SUBJECT_PROVENANCE", "claims[0].slots[0].allowed_provenance"
    )


@pytest.mark.parametrize("provenance", ["synthetic", "simulated"])
def test_district_non_public_refuses_at_match(provenance: str) -> None:
    module = _FOUNDATIONS._api()
    assert _match("district", provenance=provenance) == module.Refusal(
        "SUBJECT_PROVENANCE", "slots.reading"
    )


@pytest.mark.parametrize(
    "geography", ["area_shape", "release_units", "user_scenario", "national"]
)
def test_district_only_publisher_geography_load(tmp_path: Path, geography: str) -> None:
    module, loaded = _load(tmp_path, "district", geo=geography)
    assert loaded == module.Refusal(
        "SUBJECT_GEOGRAPHY", "claims[0].slots[0].geography_role"
    )


@pytest.mark.parametrize(
    "geography", ["area_shape", "release_units", "user_scenario", "national"]
)
def test_district_only_publisher_geography_match(geography: str) -> None:
    module = _FOUNDATIONS._api()
    catalogue = module.load_catalogue(_FOUNDATIONS.SHIPPED)
    fact = _FOUNDATIONS._fact(module, geography_kind=geography)
    slot = Slot(
        "reading",
        fact.metric_key,
        fact.unit,
        geography,
        "calendar_year",
        ("public",),
        "none",
    )
    claim = Claim("subject_note", "observed", "district", (slot,), (), (), (), ())
    catalogue = dataclasses.replace(catalogue, claims=(claim,))
    assert module.match_slots(
        catalogue, claim.key, {"reading": fact.fact_id}, {fact.fact_id: fact}
    ) == module.Refusal("SUBJECT_GEOGRAPHY", "slots.reading")


@pytest.mark.parametrize("metric", ["population_grid_people", "firms_per_tower"])
def test_company_unrelated_public_metric_load(tmp_path: Path, metric: str) -> None:
    module, loaded = _load(tmp_path, "register_company", metric=metric, geo="public")
    assert loaded == module.Refusal("SUBJECT_METRIC", "claims[0].slots[0].metric_key")


@pytest.mark.parametrize("metric", ["population_grid_people", "firms_per_tower"])
def test_company_unrelated_public_metric_match(metric: str) -> None:
    module = _FOUNDATIONS._api()
    assert _match("register_company", metric_key=metric) == module.Refusal(
        "SUBJECT_METRIC", "slots.reading"
    )


@pytest.mark.parametrize(
    ("metric", "unit", "provenance"),
    [
        ("establishment_nationality", "published_text", "public"),
        ("employee_count", "count", "synthetic"),
    ],
)
def test_company_supported_card_and_count(
    tmp_path: Path, metric: str, unit: str, provenance: str
) -> None:
    module, loaded = _load(
        tmp_path,
        "register_company",
        metric=metric,
        unit=unit,
        provenance=provenance,
        geo="public",
    )
    assert isinstance(loaded, module.Catalogue)
    fact = _FOUNDATIONS._fact(
        module,
        metric_key=metric,
        unit=unit,
        provenance=provenance,
        geography_kind="public",
    )
    assert (
        module.match_slots(
            loaded, "area_note", {"reading": fact.fact_id}, {fact.fact_id: fact}
        )
        is None
    )


def test_company_public_card_field_refuses_synthetic(tmp_path: Path) -> None:
    module, loaded = _load(
        tmp_path,
        "register_company",
        metric="establishment_nationality",
        unit="published_text",
        provenance="synthetic",
        geo="public",
    )
    assert loaded == module.Refusal("SUBJECT_METRIC", "claims[0].slots[0].metric_key")
    assert _match(
        "register_company",
        metric_key="establishment_nationality",
        unit="published_text",
        provenance="synthetic",
    ) == module.Refusal("SUBJECT_METRIC", "slots.reading")


def test_company_card_field_cannot_enter_area_or_question(tmp_path: Path) -> None:
    module, loaded = _load(
        tmp_path,
        "area",
        metric="establishment_nationality",
        unit="published_text",
    )
    assert loaded == module.Refusal("SUBJECT_METRIC", "claims[0].slots[0].metric_key")
    question = (
        "version: 1\nquestions:\n  - question_key: ask_card\n"
        "    playbook: site_check\n    personas: [local]\n    slots:\n"
        + _FOUNDATIONS._slot(metric="establishment_nationality", unit="published_text")
        + '    template_en: "See {reading}."\n'
        + '    template_ar: "انظر {reading}."\n'
    )
    folder = _FOUNDATIONS._copy(tmp_path, "question", **{"questions.yaml": question})
    assert module.load_catalogue(folder) == module.Refusal(
        "QUESTION_METRIC", "questions[0].slots[0].metric_key"
    )


@pytest.mark.parametrize("surface", ["question", "layout", "highlight"])
def test_company_card_field_cannot_enter_brief(surface: str) -> None:
    from eii_product.assistant.catalogue.schema import FieldSpec

    module = _FOUNDATIONS._api()
    catalogue = module.load_catalogue(_FOUNDATIONS.SHIPPED)
    fact = _FOUNDATIONS._fact(
        module, metric_key="establishment_nationality", unit="published_text"
    )
    brief = _FOUNDATIONS._brief(catalogue.version)
    if surface == "question":
        slot = Slot(
            "reading",
            fact.metric_key,
            fact.unit,
            "area_shape",
            "calendar_year",
            ("public",),
            "none",
        )
        question = dataclasses.replace(catalogue.questions[0], slots=(slot,))
        catalogue = dataclasses.replace(
            catalogue, questions=(question, *catalogue.questions[1:])
        )
        brief["next_questions"][0] = {
            "question_key": question.key,
            "slots": {"reading": fact.fact_id},
        }
        path = "next_questions[0].slots.reading"
    elif surface == "layout":
        component = dataclasses.replace(
            catalogue.components[0], props=(FieldSpec("title", "fact_id"),)
        )
        catalogue = dataclasses.replace(catalogue, components=(component,))
        brief["layout"] = [
            {"component": component.key, "props": {"title": fact.fact_id}}
        ]
        path = "layout[0].props.title"
    else:
        brief["stage"] = [
            {"component": "highlight", "props": {"fact_id": fact.fact_id}}
        ]
        path = "stage[0].props.fact_id"
    assert module.check_brief(catalogue, brief, {fact.fact_id: fact}) == module.Refusal(
        "REGISTER_COMPANY_FACT", path
    )
