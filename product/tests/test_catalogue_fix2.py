"""Second fix pass: breakdown binding, company facts, field types, shared checks."""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path
from typing import Any

from eii_product.assistant.catalogue.schema import FieldSpec, Slot

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
FACT_B = _FOUNDATIONS.FACT_B
SHIPPED = _FOUNDATIONS.SHIPPED


def _copy(tmp: Path, name: str, **files: str) -> tuple[Any, Any]:
    module = _api()
    folder = _FOUNDATIONS._copy(tmp, name, **files)
    return module, module.load_catalogue(folder)


def _words(en: str, ar: str) -> dict[str, str]:
    return {"en": en, "ar": ar}


def _reading(
    tmp: Path, name: str, **overrides: object
) -> tuple[Any, Any, dict[str, object], Any]:
    module, loaded = _load(tmp, _claims(_claim(slots=_slot())), name=name)
    fact = _fact(module, **overrides)
    brief = _brief(loaded.version)
    brief["observed"] = [{"claim_key": "area_note", "slots": {"reading": fact.fact_id}}]
    return module, fact, brief, loaded


def _staff(module: Any) -> Any:
    return _fact(
        module,
        metric_key="employee_count",
        provenance="synthetic",
        lineage_ref="lin_staff",
    )


def _fact_prop(catalogue: Any) -> Any:
    prop = FieldSpec("title", "fact_id")
    component = dataclasses.replace(catalogue.components[0], props=(prop,))
    return dataclasses.replace(catalogue, components=(component,))


def _layout(catalogue: Any, fact_id: str) -> dict[str, object]:
    brief = _brief(catalogue.version)
    brief["layout"] = [{"component": "foundation_note", "props": {"title": fact_id}}]
    return brief


def _highlight(catalogue: Any, fact_id: str) -> dict[str, object]:
    brief = _brief(catalogue.version)
    brief["stage"] = [{"component": "highlight", "props": {"fact_id": fact_id}}]
    return brief


def test_fix2_f1_exchanged_breakdowns_refuse(tmp_path: Path) -> None:
    """Two grid slots that differ only in breakdown bind one way."""
    whole = _slot(name="whole")
    split = _slot(name="split", breakdown="sex")
    words = _words("See {whole} and {split}.", "انظر {whole} و {split}.")
    module, loaded = _load(
        tmp_path, _claims(_claim(slots=whole + split, **words)), name="bound"
    )
    assert loaded.claims[0].slots[0].breakdown == "none"
    assert loaded.claims[0].slots[1].breakdown == "sex"
    plain = _fact(module, breakdown="none")
    parted = _fact(
        module, fact_id=FACT_B, breakdown="sex", lineage_ref="lin_grid_split"
    )
    facts = {plain.fact_id: plain, parted.fact_id: parted}
    brief = _brief(loaded.version)
    brief["observed"] = [
        {
            "claim_key": "area_note",
            "slots": {"whole": plain.fact_id, "split": parted.fact_id},
        }
    ]
    assert module.check_brief(loaded, brief, facts) is None
    brief["observed"] = [
        {
            "claim_key": "area_note",
            "slots": {"whole": parted.fact_id, "split": plain.fact_id},
        }
    ]
    assert module.check_brief(loaded, brief, facts) == module.Refusal(
        "SLOT_BREAKDOWN", "observed[0].slots.whole"
    )


def test_fix2_f1_overlapping_provenance_refuses_at_load(tmp_path: Path) -> None:
    """Slots that coincide except for an overlapping provenance set do not load."""
    whole = _slot(name="whole")
    wide = _slot(name="split").replace(
        "allowed_provenance: [public]",
        "allowed_provenance: [public, synthetic]",
    )
    words = _words("See {whole} and {split}.", "انظر {whole} و {split}.")
    module, claim = _load(
        tmp_path, _claims(_claim(slots=whole + wide, **words)), name="overlap"
    )
    assert claim == module.Refusal("SLOT_OVERLAP", "claims[0].slots[1]")
    question = (
        "version: 1\n"
        "questions:\n"
        "  - question_key: ask_pair\n"
        "    playbook: site_check\n"
        "    personas: [local]\n"
        "    slots:\n"
        + whole
        + wide
        + '    template_en: "See {whole} and {split}."\n'
        + '    template_ar: "انظر {whole} و {split}."\n'
    )
    module, asked = _copy(tmp_path, "q-overlap", **{"questions.yaml": question})
    assert asked == module.Refusal("SLOT_OVERLAP", "questions[0].slots[1]")


def test_fix2_f1_breakdown_outside_the_closed_list(tmp_path: Path) -> None:
    module, fact, brief, loaded = _reading(
        tmp_path, "breakdown-word", breakdown="widget"
    )
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "FACT_FIELD", "observed[0].slots.reading.breakdown"
    )


def test_fix2_f1_breakdown_must_be_a_string(tmp_path: Path) -> None:
    module, fact, brief, loaded = _reading(tmp_path, "breakdown-list", breakdown=[])
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "FACT_FIELD", "observed[0].slots.reading.breakdown"
    )


def test_fix2_f2_question_employee_count_refuses_at_load(tmp_path: Path) -> None:
    question = (
        "version: 1\n"
        "questions:\n"
        "  - question_key: ask_staff\n"
        "    playbook: site_check\n"
        "    personas: [local]\n"
        "    slots:\n"
        + _slot(metric="employee_count", provenance="synthetic")
        + '    template_en: "See {reading}."\n'
        + '    template_ar: "انظر {reading}."\n'
    )
    module, loaded = _copy(tmp_path, "q-staff", **{"questions.yaml": question})
    assert loaded == module.Refusal(
        "QUESTION_METRIC", "questions[0].slots[0].metric_key"
    )


def test_fix2_f2_question_refuses_a_company_fact() -> None:
    module = _api()
    shipped = module.load_catalogue(SHIPPED)
    slot = Slot(
        "reading",
        "employee_count",
        "count",
        "area_shape",
        "calendar_year",
        ("synthetic",),
        "none",
    )
    question = dataclasses.replace(shipped.questions[0], slots=(slot,))
    catalogue = dataclasses.replace(
        shipped,
        questions=(question, shipped.questions[1], shipped.questions[2]),
    )
    fact = _staff(module)
    brief = _brief(catalogue.version)
    brief["next_questions"] = [
        {"question_key": "foundation_ask_shape", "slots": {"reading": fact.fact_id}},
        {"question_key": "foundation_ask_walk", "slots": {}},
        {"question_key": "foundation_ask_context", "slots": {}},
    ]
    assert module.check_brief(catalogue, brief, {fact.fact_id: fact}) == (
        module.Refusal("REGISTER_COMPANY_FACT", "next_questions[0].slots.reading")
    )


def test_fix2_f2_layout_refuses_a_company_fact() -> None:
    module = _api()
    catalogue = _fact_prop(module.load_catalogue(SHIPPED))
    fact = _staff(module)
    assert module.check_brief(
        catalogue, _layout(catalogue, fact.fact_id), {fact.fact_id: fact}
    ) == module.Refusal("REGISTER_COMPANY_FACT", "layout[0].props.title")


def test_fix2_f2_highlight_refuses_a_company_fact() -> None:
    module = _api()
    catalogue = module.load_catalogue(SHIPPED)
    fact = _staff(module)
    assert module.check_brief(
        catalogue, _highlight(catalogue, fact.fact_id), {fact.fact_id: fact}
    ) == module.Refusal("REGISTER_COMPANY_FACT", "stage[0].props.fact_id")


def test_fix2_f3_numeric_lineage_ref(tmp_path: Path) -> None:
    module, fact, brief, loaded = _reading(tmp_path, "lineage-number", lineage_ref=7)
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "LINEAGE_REF", "observed[0].slots.reading.lineage_ref"
    )


def test_fix2_f3_unhashable_unit(tmp_path: Path) -> None:
    module, fact, brief, loaded = _reading(tmp_path, "unit-list", unit=[])
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "FACT_FIELD", "observed[0].slots.reading.unit"
    )


def test_fix2_f3_unhashable_provenance(tmp_path: Path) -> None:
    module, fact, brief, loaded = _reading(tmp_path, "provenance-list", provenance=[])
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "FACT_FIELD", "observed[0].slots.reading.provenance"
    )


def test_fix2_f3_unhashable_evidence_status(tmp_path: Path) -> None:
    module, fact, brief, loaded = _reading(
        tmp_path, "evidence-list", evidence_status=[]
    )
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "FACT_FIELD", "observed[0].slots.reading.evidence_status"
    )


def test_fix2_f3_unhashable_geography_kind(tmp_path: Path) -> None:
    module, fact, brief, loaded = _reading(
        tmp_path, "geography-list", geography_kind=[]
    )
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "FACT_FIELD", "observed[0].slots.reading.geography"
    )


def test_fix2_f3_unhashable_metric_key(tmp_path: Path) -> None:
    module, fact, brief, loaded = _reading(tmp_path, "metric-list", metric_key=[])
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "FACT_FIELD", "observed[0].slots.reading.metric_key"
    )


def test_fix2_f3_unhashable_period(tmp_path: Path) -> None:
    module, fact, brief, loaded = _reading(tmp_path, "period-list", period=[])
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "FACT_FIELD", "observed[0].slots.reading.period"
    )


def test_fix2_f4_layout_refuses_a_suppressed_fact() -> None:
    module = _api()
    catalogue = _fact_prop(module.load_catalogue(SHIPPED))
    fact = _fact(module, provenance="suppressed")
    assert module.check_brief(
        catalogue, _layout(catalogue, fact.fact_id), {fact.fact_id: fact}
    ) == module.Refusal("SUPPRESSED_FACT", "layout[0].props.title")


def test_fix2_f4_layout_refuses_a_missing_lineage() -> None:
    module = _api()
    catalogue = _fact_prop(module.load_catalogue(SHIPPED))
    fact = _fact(module, lineage_ref=None)
    assert module.check_brief(
        catalogue, _layout(catalogue, fact.fact_id), {fact.fact_id: fact}
    ) == module.Refusal("LINEAGE_REF", "layout[0].props.title.lineage_ref")


def test_fix2_f4_layout_accepts_a_valid_fact() -> None:
    module = _api()
    catalogue = _fact_prop(module.load_catalogue(SHIPPED))
    fact = _fact(module)
    assert (
        module.check_brief(
            catalogue, _layout(catalogue, fact.fact_id), {fact.fact_id: fact}
        )
        is None
    )


def test_fix2_f4_highlight_refuses_a_suppressed_fact() -> None:
    module = _api()
    catalogue = module.load_catalogue(SHIPPED)
    fact = _fact(module, provenance="suppressed")
    assert module.check_brief(
        catalogue, _highlight(catalogue, fact.fact_id), {fact.fact_id: fact}
    ) == module.Refusal("SUPPRESSED_FACT", "stage[0].props.fact_id")


def test_fix2_f4_highlight_refuses_a_missing_lineage() -> None:
    module = _api()
    catalogue = module.load_catalogue(SHIPPED)
    fact = _fact(module, lineage_ref=None)
    assert module.check_brief(
        catalogue, _highlight(catalogue, fact.fact_id), {fact.fact_id: fact}
    ) == module.Refusal("LINEAGE_REF", "stage[0].props.fact_id.lineage_ref")


def test_fix2_f4_highlight_accepts_a_valid_fact() -> None:
    module = _api()
    catalogue = module.load_catalogue(SHIPPED)
    fact = _fact(module)
    assert (
        module.check_brief(
            catalogue, _highlight(catalogue, fact.fact_id), {fact.fact_id: fact}
        )
        is None
    )


def test_fix2_f5_boolean_and_nan_coordinates() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)

    def fly(lat: object, lon: object) -> Any:
        brief = _brief(loaded.version)
        brief["stage"] = [
            {
                "component": "fly",
                "props": {"target": {"lat": lat, "lon": lon}, "zoom": "city"},
            }
        ]
        return module.check_brief(loaded, brief, {})

    assert fly(True, 0) == module.Refusal("STAGE_VALUE", "stage[0].props.target")
    assert fly(float("nan"), 0) == module.Refusal(
        "STAGE_VALUE", "stage[0].props.target"
    )
    assert fly(0, 0) is None


def test_fix2_f5_boolean_prop_refuses_a_number_and_a_string() -> None:
    module = _api()
    shipped = module.load_catalogue(SHIPPED)
    prop = FieldSpec("title", "boolean")
    component = dataclasses.replace(shipped.components[0], props=(prop,))
    catalogue = dataclasses.replace(shipped, components=(component,))

    def laid(value: object) -> Any:
        brief = _brief(catalogue.version)
        brief["layout"] = [{"component": "foundation_note", "props": {"title": value}}]
        return module.check_brief(catalogue, brief, {})

    assert laid(1) == module.Refusal("PROP_VALUE", "layout[0].props.title")
    assert laid("yes") == module.Refusal("PROP_VALUE", "layout[0].props.title")
    assert laid(True) is None
