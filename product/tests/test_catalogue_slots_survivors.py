"""Mutation-pass plants for the slots module's surviving path and subject mutants.

Every expected refusal below is a hand-written literal; none is copied from
the module under test. The claims, facts and identifiers are invented ones.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from eii_product.assistant.catalogue.slots import match_slot_list

_SPEC = importlib.util.spec_from_file_location(
    "catalogue_foundations_helpers",
    Path(__file__).with_name("test_catalogue_foundations.py"),
)
assert _SPEC is not None and _SPEC.loader is not None
_FOUNDATIONS = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FOUNDATIONS)

_api = _FOUNDATIONS._api
_claim = _FOUNDATIONS._claim
_claims = _FOUNDATIONS._claims
_fact = _FOUNDATIONS._fact
_load = _FOUNDATIONS._load
_slot = _FOUNDATIONS._slot
FACT_A = _FOUNDATIONS.FACT_A


def _mistyped(value: object) -> Any:
    """Hand a deliberately mistyped slots value to the typed parameter."""
    return value


def test_match_slots_keeps_the_item_path_on_an_unknown_claim(tmp_path: Path) -> None:
    """An unknown claim refuses at the item path the caller passed in."""
    module, loaded = _load(tmp_path, _claims(_claim(slots=_slot())), name="paths")
    refused = module.match_slots(
        loaded, "missing_claim", {}, {}, item_path="observed[7]"
    )
    assert refused == module.Refusal("UNKNOWN_CLAIM", "observed[7].claim_key")


def test_match_slots_keeps_the_claim_section_evidence(tmp_path: Path) -> None:
    """The claim's own section decides which evidence statuses may bind."""
    module, loaded = _load(tmp_path, _claims(_claim(slots=_slot())), name="section")
    fact = _fact(module, evidence_status="inferred")
    refused = module.match_slots(
        loaded,
        "area_note",
        {"reading": fact.fact_id},
        {fact.fact_id: fact},
        item_path="observed[7]",
    )
    assert refused == module.Refusal("SLOT_EVIDENCE", "observed[7].slots.reading")


def test_match_slot_list_keeps_the_item_path(tmp_path: Path) -> None:
    """Every slot refusal carries the item path the caller passed in."""
    module, loaded = _load(tmp_path, _claims(_claim(slots=_slot())), name="list")
    defined = loaded.claims[0].slots
    refused = match_slot_list(
        defined, _mistyped([]), {}, subject=None, evidence=None, item_path="brief[2]"
    )
    assert refused == module.Refusal("BRIEF_TYPE", "brief[2].slots")
    refused = match_slot_list(
        defined, {}, {}, subject=None, evidence=None, item_path="brief[2]"
    )
    assert refused == module.Refusal("SLOT_MISSING", "brief[2].slots.reading")
    refused = match_slot_list(
        defined,
        {"reading": FACT_A, "spare": FACT_A},
        {},
        subject=None,
        evidence=None,
        item_path="brief[2]",
    )
    assert refused == module.Refusal("SLOT_EXTRA", "brief[2].slots.spare")


def test_match_slot_list_refuses_a_rank_unit_by_subject(tmp_path: Path) -> None:
    """The rank unit stays on the area subject; place_public refuses it."""
    module, loaded = _load(
        tmp_path,
        _claims(_claim(slots=_slot(metric="forecast_value", unit="rank"))),
        name="rank",
    )
    fact = _fact(module, metric_key="forecast_value", unit="rank")
    refused = match_slot_list(
        loaded.claims[0].slots,
        {"reading": fact.fact_id},
        {fact.fact_id: fact},
        subject="place_public",
        evidence=None,
        item_path="brief[2]",
    )
    assert refused == module.Refusal("SUBJECT_UNIT", "brief[2].slots.reading")


def test_match_slot_list_refuses_an_estimate_metric_by_subject(tmp_path: Path) -> None:
    """Estimate metrics stay on the area subject; place_public refuses them."""
    module, loaded = _load(
        tmp_path,
        _claims(_claim(slots=_slot(metric="estimate_middle", unit="qar"))),
        name="estimate",
    )
    fact = _fact(module, metric_key="estimate_middle", unit="qar")
    refused = match_slot_list(
        loaded.claims[0].slots,
        {"reading": fact.fact_id},
        {fact.fact_id: fact},
        subject="place_public",
        evidence=None,
        item_path="brief[2]",
    )
    assert refused == module.Refusal("SUBJECT_METRIC", "brief[2].slots.reading")
