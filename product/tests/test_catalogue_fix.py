"""Fix-pass plants for catalogue foundations. Each expected refusal is written here."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

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
FACT_A = _FOUNDATIONS.FACT_A
FACT_B = _FOUNDATIONS.FACT_B
SHIPPED = _FOUNDATIONS.SHIPPED

_PROSE = "Open here now, revenue seven million"
_KEYCAP = "#\ufe0f\u20e3"


def _components() -> str:
    return (SHIPPED / "components.yaml").read_text(encoding="utf-8")


def _questions() -> str:
    return (SHIPPED / "questions.yaml").read_text(encoding="utf-8")


def _copy(tmp: Path, name: str, **files: str) -> Any:
    module = _api()
    folder = _FOUNDATIONS._copy(tmp, name, **files)
    return module, module.load_catalogue(folder)


def _words(en: str, ar: str | None = None) -> dict[str, str]:
    return {"en": en, "ar": ar if ar is not None else "المنطقة ظاهرة."}


def test_fix_a_sex_and_nationality_breakdown(tmp_path: Path) -> None:
    """Sex and nationality stay on the pack's subjects, and never beside another class."""
    refused = (
        (
            "company-sex",
            _claim(
                subject="register_company",
                slots=_slot(metric="employee_count", breakdown="sex"),
                **_words("The count is {reading}.", "العدد هو {reading}."),
            ),
            "claims[0].slots[0].breakdown",
        ),
        (
            "company-nationality",
            _claim(
                subject="register_company",
                slots=_slot(metric="employee_count", breakdown="nationality"),
                **_words("The count is {reading}.", "العدد هو {reading}."),
            ),
            "claims[0].slots[0].breakdown",
        ),
        (
            "area-talent-sex",
            _claim(slots=_slot(metric="talent_pool", breakdown="sex")),
            "claims[0].slots[0].breakdown",
        ),
        (
            "area-grid-nationality",
            _claim(slots=_slot(breakdown="nationality")),
            "claims[0].slots[0].breakdown",
        ),
        (
            "place-nationality",
            _claim(
                subject="place_public",
                slots=_slot(
                    metric="venue_busyness_index",
                    unit="relative_index",
                    geo="public",
                    breakdown="nationality",
                ),
                **_words("The reading is {reading}.", "القراءة هي {reading}."),
            ),
            "claims[0].slots[0].breakdown",
        ),
    )
    for name, claim, path in refused:
        module, result = _load(tmp_path, _claims(claim), name=name)
        assert result == module.Refusal("BREAKDOWN", path)
    module, grid = _load(
        tmp_path, _claims(_claim(slots=_slot(breakdown="sex"))), name="grid-sex"
    )
    assert grid.claims[0].slots[0].breakdown == "sex"
    for name, subject in (
        ("municipality-sex", "municipality"),
        ("national-sex", "national"),
        ("sector-sex", "sector"),
        ("municipality-nationality", "municipality"),
    ):
        breakdown = "nationality" if name.endswith("nationality") else "sex"
        _, loaded = _load(
            tmp_path,
            _claims(
                _claim(
                    subject=subject,
                    slots=_slot(geo="national", breakdown=breakdown),
                )
            ),
            name=name,
        )
        assert loaded.claims[0].slots[0].breakdown == breakdown
    sex = _slot(breakdown="sex")
    other_simulated = _slot(name="other", metric="talent_pool", provenance="simulated")
    other_synthetic = _slot(name="other", metric="talent_pool", provenance="synthetic")
    words = _words("See {reading} and {other}.", "انظر {reading} و {other}.")
    for name, other in (
        ("mixed-simulated", other_simulated),
        ("mixed-synthetic", other_synthetic),
    ):
        module, mixed = _load(
            tmp_path, _claims(_claim(slots=sex + other, **words)), name=name
        )
        assert mixed == module.Refusal(
            "BREAKDOWN_MIXED", "claims[0].slots[0].breakdown"
        )


def test_fix_b_estimate_share_score_and_rank(tmp_path: Path) -> None:
    """Estimate, scenario, share and rank slots stay on an area.

    DAT-145 and AI-42 allow a register company, in a list, its rank and fit
    facts in records the application renders. No such record template exists
    in this task, so rank on register_company is refused until that family is
    built.
    """
    plants = (
        (
            "place-estimate",
            "place_public",
            _slot(metric="estimate_middle", unit="qar", geo="public"),
            "SUBJECT_METRIC",
            "claims[0].slots[0].metric_key",
            "The reading is {reading}.",
            "القراءة هي {reading}.",
        ),
        (
            "fdi-share",
            "fdi_project",
            _slot(metric="catchment_share_outlet", unit="percent", geo="public"),
            "SUBJECT_METRIC",
            "claims[0].slots[0].metric_key",
            "The reading is {reading}.",
            "القراءة هي {reading}.",
        ),
        (
            "place-scenario",
            "place_public",
            _slot(metric="scenario_middle", unit="qar", geo="public"),
            "SUBJECT_METRIC",
            "claims[0].slots[0].metric_key",
            "The reading is {reading}.",
            "القراءة هي {reading}.",
        ),
        (
            "place-scenario-low",
            "place_public",
            _slot(metric="scenario_low", unit="qar", geo="public"),
            "SUBJECT_METRIC",
            "claims[0].slots[0].metric_key",
            "The reading is {reading}.",
            "القراءة هي {reading}.",
        ),
        (
            "place-scenario-high",
            "place_public",
            _slot(metric="scenario_high", unit="qar", geo="public"),
            "SUBJECT_METRIC",
            "claims[0].slots[0].metric_key",
            "The reading is {reading}.",
            "القراءة هي {reading}.",
        ),
        (
            "place-rank",
            "place_public",
            _slot(metric="forecast_value", unit="rank", geo="public"),
            "SUBJECT_UNIT",
            "claims[0].slots[0].unit",
            "The reading is {reading}.",
            "القراءة هي {reading}.",
        ),
        (
            "national-rank",
            "national",
            _slot(metric="forecast_value", unit="rank", geo="national"),
            "SUBJECT_UNIT",
            "claims[0].slots[0].unit",
            "The reading is {reading}.",
            "القراءة هي {reading}.",
        ),
        (
            "company-rank",
            "register_company",
            _slot(metric="forecast_value", unit="rank", geo="public"),
            "SUBJECT_UNIT",
            "claims[0].slots[0].unit",
            "The reading is {reading}.",
            "القراءة هي {reading}.",
        ),
    )
    for name, subject, slot, rule, path, en, ar in plants:
        module, result = _load(
            tmp_path,
            _claims(_claim(subject=subject, slots=slot, **_words(en, ar))),
            name=name,
        )
        assert result == module.Refusal(rule, path)
    module, area = _load(
        tmp_path,
        _claims(_claim(slots=_slot(metric="estimate_middle", unit="qar"))),
        name="area-estimate",
    )
    assert area.claims[0].slots[0].metric_key == "estimate_middle"


def test_fix_c_component_prop_kinds(tmp_path: Path) -> None:
    import dataclasses

    from eii_product.assistant.catalogue.schema import FieldSpec

    module = _api()
    shipped = module.load_catalogue(SHIPPED)

    def laid(kind: str, value: object, values: tuple[str, ...] = ()) -> Any:
        prop = FieldSpec("title", kind, values)
        component = dataclasses.replace(shipped.components[0], props=(prop,))
        catalogue = dataclasses.replace(shipped, components=(component,))
        brief = _brief(catalogue.version)
        brief["layout"] = [{"component": "foundation_note", "props": {"title": value}}]
        return module.check_brief(catalogue, brief, {})

    assert laid("enumeration", _PROSE, ("open_note",)) == module.Refusal(
        "PROP_VALUE", "layout[0].props.title"
    )
    assert laid("enumeration", 7.5, ("open_note",)) == module.Refusal(
        "PROP_VALUE", "layout[0].props.title"
    )
    assert laid("enumeration", 7, ("open_note",)) == module.Refusal(
        "PROP_VALUE", "layout[0].props.title"
    )
    assert laid("fact_id", _PROSE) == module.Refusal(
        "PROP_VALUE", "layout[0].props.title"
    )
    assert laid("enumeration", "open_note", ("open_note",)) is None
    fact = _fact(module)
    prop = FieldSpec("title", "fact_id")
    component = dataclasses.replace(shipped.components[0], props=(prop,))
    catalogue = dataclasses.replace(shipped, components=(component,))
    brief = _brief(catalogue.version)
    brief["layout"] = [
        {"component": "foundation_note", "props": {"title": fact.fact_id}}
    ]
    assert module.check_brief(catalogue, brief, {fact.fact_id: fact}) is None
    brief["layout"] = [{"component": "foundation_note", "props": {"title": FACT_B}}]
    assert module.check_brief(catalogue, brief, {fact.fact_id: fact}) == (
        module.Refusal("UNKNOWN_FACT", "layout[0].props.title")
    )
    body = _components().replace(
        "    props: []\n",
        "    props:\n      - name: title\n        kind: text\n",
        1,
    )
    module, refused = _copy(tmp_path, "prop-kind", **{"components.yaml": body})
    assert refused == module.Refusal("CATALOGUE_VALUE", "components[0].props[0].kind")
    accepted = _components().replace(
        "    props: []\n",
        "    props:\n      - name: shown\n        kind: fact_id\n",
        1,
    )
    module, loaded_prop = _copy(tmp_path, "prop-fact", **{"components.yaml": accepted})
    assert loaded_prop.components[0].props[0].kind == "fact_id"


def test_fix_d_strength_must_be_a_string(tmp_path: Path) -> None:
    module, loaded = _load(
        tmp_path,
        _claims(_claim(section="inferred", slots=_slot(), strengths="[indicative]")),
    )
    fact = _fact(module, evidence_status="inferred")
    for strength in ([], {}):
        brief = _brief(loaded.version)
        brief["inferred"] = [
            {
                "claim_key": "area_note",
                "slots": {"reading": fact.fact_id},
                "strength": strength,
            }
        ]
        assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == (
            module.Refusal("STRENGTH", "inferred[0].strength")
        )


def test_fix_h_fragment_kind_must_match() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    headline = _brief(loaded.version)
    headline["headline_key"] = "foundation_decision"
    assert module.check_brief(loaded, headline, {}) == module.Refusal(
        "FRAGMENT_KIND", "headline_key"
    )
    decision = _brief(loaded.version)
    decision["decision_template_key"] = "foundation_headline"
    assert module.check_brief(loaded, decision, {}) == module.Refusal(
        "FRAGMENT_KIND", "decision_template_key"
    )


def test_fix_j_register_company_item(tmp_path: Path) -> None:
    claim = _claim(
        key="company_note",
        subject="register_company",
        slots=_slot(metric="employee_count", provenance="synthetic"),
        **_words("The count is {reading}.", "العدد هو {reading}."),
    )
    module, loaded = _load(tmp_path, _claims(claim), name="company")
    fact = _fact(
        module,
        metric_key="employee_count",
        provenance="synthetic",
        lineage_ref="lin_staff",
    )
    brief = _brief(loaded.version)
    brief["observed"] = [
        {"claim_key": "company_note", "slots": {"reading": fact.fact_id}}
    ]
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "REGISTER_COMPANY_ITEM", "observed[0].claim_key"
    )
    inferred_claim = _claim(
        key="company_note",
        section="inferred",
        subject="register_company",
        slots=_slot(metric="employee_count", provenance="synthetic"),
        strengths="[indicative]",
        **_words("The count is {reading}.", "العدد هو {reading}."),
    )
    _, inferred = _load(tmp_path, _claims(inferred_claim), name="company-inferred")
    brief = _brief(inferred.version)
    brief["inferred"] = [
        {
            "claim_key": "company_note",
            "slots": {"reading": fact.fact_id},
            "strength": "indicative",
        }
    ]
    assert module.check_brief(inferred, brief, {fact.fact_id: fact}) == (
        module.Refusal("REGISTER_COMPANY_ITEM", "inferred[0].claim_key")
    )


def test_fix_k_slot_fact_reused_and_identical(tmp_path: Path) -> None:
    people = _slot(name="people")
    again = _slot(
        name="again",
        metric="night_lights_radiance",
        unit="radiance_nw_cm2_sr",
        period="calendar_month",
    )
    words = _words("See {people} and {again}.", "انظر {people} و {again}.")
    module, loaded = _load(
        tmp_path, _claims(_claim(slots=people + again, **words)), name="reused"
    )
    fact = _fact(module)
    brief = _brief(loaded.version)
    brief["observed"] = [
        {
            "claim_key": "area_note",
            "slots": {"people": fact.fact_id, "again": fact.fact_id},
        }
    ]
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "SLOT_FACT_REUSED", "observed[0].slots.again"
    )
    same = _slot(name="people").replace(
        "allowed_provenance: [public]",
        "allowed_provenance: [public, synthetic]",
    )
    flipped = _slot(name="again").replace(
        "allowed_provenance: [public]",
        "allowed_provenance: [synthetic, public]",
    )
    module, identical = _load(
        tmp_path,
        _claims(_claim(slots=same + flipped, **words)),
        name="identical",
    )
    assert identical == module.Refusal("SLOT_IDENTICAL", "claims[0].slots[1]")
    question = (
        "  - question_key: ask_pair\n"
        "    playbook: site_check\n"
        "    personas: [local]\n"
        "    slots:\n"
        + same
        + flipped
        + '    template_en: "See {people} and {again}."\n'
        + '    template_ar: "انظر {people} و {again}."\n'
    )
    module, asked = _copy(
        tmp_path, "q-identical", **{"questions.yaml": _questions() + question}
    )
    assert asked == module.Refusal("SLOT_IDENTICAL", "questions[3].slots[1]")


def test_fix_l_evidence_status_by_section(tmp_path: Path) -> None:
    """Observed binds observed facts. Inferred also binds an observed basis fact."""
    observed = _claim(key="seen", slots=_slot())
    inferred = _claim(
        key="drawn",
        section="inferred",
        slots=_slot(),
        strengths="[indicative]",
    )
    module, loaded = _load(tmp_path, _claims(observed, inferred))
    cases = (
        ("observed", "observed", "seen", None),
        (
            "observed",
            "inferred",
            "seen",
            module.Refusal("SLOT_EVIDENCE", "observed[0].slots.reading"),
        ),
        (
            "observed",
            "still_to_test",
            "seen",
            module.Refusal("SLOT_EVIDENCE", "observed[0].slots.reading"),
        ),
        ("inferred", "observed", "drawn", None),
        ("inferred", "inferred", "drawn", None),
        (
            "inferred",
            "still_to_test",
            "drawn",
            module.Refusal("SLOT_EVIDENCE", "inferred[0].slots.reading"),
        ),
    )
    for section, status, key, expected in cases:
        fact = _fact(module, evidence_status=status)
        brief = _brief(loaded.version)
        item: dict[str, object] = {
            "claim_key": key,
            "slots": {"reading": fact.fact_id},
        }
        if section == "inferred":
            item["strength"] = "indicative"
        brief[section] = [item]
        assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == expected
