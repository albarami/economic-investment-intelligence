"""Mutation-pass plants for the brief module's surviving refusal mutants.

Every expected refusal below is a hand-written literal; none is copied from
the module under test. The claims, facts and identifiers are invented ones.
"""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path

from eii_product.assistant.catalogue.schema import Alternative, FieldSpec

_SPEC = importlib.util.spec_from_file_location(
    "catalogue_foundations_helpers",
    Path(__file__).with_name("test_catalogue_foundations.py"),
)
assert _SPEC is not None and _SPEC.loader is not None
_FOUNDATIONS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FOUNDATIONS)

_api = _FOUNDATIONS._api
_brief = _FOUNDATIONS._brief
_claim = _FOUNDATIONS._claim
_claims = _FOUNDATIONS._claims
_fact = _FOUNDATIONS._fact
_load = _FOUNDATIONS._load
_slot = _FOUNDATIONS._slot
SHIPPED = _FOUNDATIONS.SHIPPED


def test_non_string_fragment_keys_refuse() -> None:
    """A headline or decision key that is not a string is refused whole."""
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    headline = _brief(loaded.version)
    headline["headline_key"] = 7
    assert module.check_brief(loaded, headline, {}) == module.Refusal(
        "UNKNOWN_FRAGMENT", "headline_key"
    )
    decision = _brief(loaded.version)
    decision["decision_template_key"] = 7
    assert module.check_brief(loaded, decision, {}) == module.Refusal(
        "UNKNOWN_FRAGMENT", "decision_template_key"
    )


def test_a_simulated_fact_on_a_place_claim_refuses_by_subject(
    tmp_path: Path,
) -> None:
    """The section passes the claim subject on, so the subject rule refuses.

    A place_public claim accepts only public facts, so a simulated fact is
    refused as SUBJECT_PROVENANCE, not as the slot's own SLOT_PROVENANCE.
    """
    module, loaded = _load(
        tmp_path,
        _claims(
            _claim(
                key="place_note",
                subject="place_public",
                slots=_slot(
                    name="busyness",
                    metric="price_deal_value",
                    unit="qar",
                    geo="public",
                ),
                en="The reading is {busyness}.",
                ar="القراءة هي {busyness}.",
            )
        ),
        name="place",
    )
    fact = _fact(
        module,
        metric_key="price_deal_value",
        unit="qar",
        geography_kind="public",
        provenance="simulated",
        lineage_ref="lin_busyness",
    )
    brief = _brief(loaded.version)
    brief["observed"] = [
        {"claim_key": "place_note", "slots": {"busyness": fact.fact_id}}
    ]
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "SUBJECT_PROVENANCE", "observed[0].slots.busyness"
    )


def test_layout_shows_props_for_a_non_string_property_key() -> None:
    """A layout props key that is not a string shows as 'props' in the path."""
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    brief = _brief(loaded.version)
    brief["layout"] = [{"component": "foundation_note", "props": {7: "note"}}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_PROPERTY", "layout[0].props.props"
    )


def test_stage_shows_props_for_a_non_string_property_key() -> None:
    """A stage props key that is not a string shows as 'props' in the path."""
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    brief = _brief(loaded.version)
    brief["stage"] = [{"component": "hour", "props": {7: "hour_am"}}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_PROPERTY", "stage[0].props.props"
    )


def test_a_prop_kind_the_loader_refuses_refuses_every_value() -> None:
    """A component prop kind the loader never loads refuses through check_brief.

    The loader refuses every prop kind outside enumeration, boolean and
    fact_id (entries.py, CATALOGUE_VALUE at props[i].kind), so only a
    directly constructed catalogue reaches this refusal.
    """
    module = _api()
    shipped = module.load_catalogue(SHIPPED)
    component = dataclasses.replace(
        shipped.components[0], props=(FieldSpec("title", "identifier"),)
    )
    catalogue = dataclasses.replace(shipped, components=(component,))
    brief = _brief(catalogue.version)
    brief["layout"] = [{"component": "foundation_note", "props": {"title": "note"}}]
    assert module.check_brief(catalogue, brief, {}) == module.Refusal(
        "PROP_VALUE", "layout[0].props.title"
    )


def test_a_stage_fact_id_that_is_not_one_refuses() -> None:
    """The highlight directive's fact_id prop takes only a well-formed id."""
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    brief = _brief(loaded.version)
    brief["stage"] = [{"component": "highlight", "props": {"fact_id": "nope"}}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "STAGE_VALUE", "stage[0].props.fact_id"
    )


def test_a_directive_field_kind_the_loader_refuses_refuses_every_value() -> None:
    """A directive field kind the loader never loads refuses through check_brief.

    The loader refuses every field kind outside DIRECTIVE_KINDS (directives.py,
    CATALOGUE_VALUE at fields[i].kind), so only a directly constructed
    catalogue reaches this refusal.
    """
    module = _api()
    shipped = module.load_catalogue(SHIPPED)
    spin = dataclasses.replace(
        shipped.directives[0],
        alternatives=(Alternative((FieldSpec("spin", "colour"),)),),
    )
    catalogue = dataclasses.replace(shipped, directives=(spin,))
    brief = _brief(catalogue.version)
    brief["stage"] = [{"component": "fly", "props": {"spin": "left"}}]
    assert module.check_brief(catalogue, brief, {}) == module.Refusal(
        "STAGE_VALUE", "stage[0].props.spin"
    )
