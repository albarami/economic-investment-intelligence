"""Catalogue foundations: closed files, refusals, slot match and the numeral scan."""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path
from typing import Any

FILES = ("claims.yaml", "components.yaml", "fragments.yaml", "questions.yaml")
SHIPPED = (
    Path(__file__).resolve().parents[1] / "src/eii_product/assistant/catalogue/assets"
)
FACT_A = "f_" + ("a1b2c3d4" * 4)
FACT_B = "f_" + ("b2c3d4e5" * 4)
NUMERAL_CATEGORIES = frozenset({"Nd", "Nl", "No"})


def _api() -> Any:
    from eii_product.assistant import catalogue

    return catalogue


def _rendered(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if (
                isinstance(key, str)
                and key.endswith(("_en", "_ar"))
                and isinstance(item, str)
            ):
                found.append(item)
            else:
                found.extend(_rendered(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_rendered(item))
    return found


def _copy(tmp: Path, name: str = "cat", **replacements: str) -> Path:
    folder = tmp / name
    folder.mkdir()
    for file_name in FILES:
        text = replacements.get(file_name)
        if text is None:
            text = (SHIPPED / file_name).read_text(encoding="utf-8")
        (folder / file_name).write_text(text, encoding="utf-8")
    return folder


def _slot(
    name: str = "reading",
    metric: str = "price_deal_count",
    unit: str = "count",
    geo: str = "area_shape",
    period: str = "calendar_year",
    provenance: str = "public",
    breakdown: str = "none",
) -> str:
    # Generic slot guards use ordinary metrics; C36-C38 have display-only rules
    # exercised by test_public_context rather than serving as generic fixtures.
    return (
        f"      - name: {name}\n"
        f"        metric_key: {metric}\n"
        f"        unit: {unit}\n"
        f"        geography_role: {geo}\n"
        f"        period_rule: {period}\n"
        f"        allowed_provenance: [{provenance}]\n"
        f"        breakdown: {breakdown}\n"
    )


def _claim(
    key: str = "area_note",
    subject: str = "area",
    section: str = "observed",
    slots: str = "",
    en: str | None = None,
    ar: str | None = None,
    extra: str = "",
    strengths: str = "[]",
    caveats: str = "[]",
) -> str:
    if slots:
        en = "See {reading}." if en is None else en
        ar = "انظر {reading}." if ar is None else ar
        slot_line = "    slots:\n" + slots
    else:
        en = "The area is shown." if en is None else en
        ar = "المنطقة ظاهرة." if ar is None else ar
        slot_line = "    slots: []\n"
    extra_line = f"    {extra}\n" if extra else ""
    return (
        f"  - claim_key: {key}\n"
        f"    section: {section}\n"
        f"    subject: {subject}\n"
        f"{slot_line}"
        f"    required_caveat_keys: {caveats}\n"
        "    required_companions: []\n"
        f"    strengths_allowed: {strengths}\n"
        f'    template_en: "{en}"\n'
        f'    template_ar: "{ar}"\n'
        f"{extra_line}"
    )


def _claims(*items: str) -> str:
    if not items:
        return "version: 1\nclaims: []\n"
    return "version: 1\nclaims:\n" + "".join(items)


def _load(tmp: Path, claims: str, name: str = "cat") -> Any:
    module = _api()
    result = module.load_catalogue(_copy(tmp, name, **{"claims.yaml": claims}))
    return module, result


def _fact(module: Any, **overrides: object) -> Any:
    values: dict[str, object] = {
        "fact_id": FACT_A,
        "metric_key": "price_deal_count",
        "unit": "count",
        "period": "2024",
        "geography_kind": "area_shape",
        "provenance": "public",
        "evidence_status": "observed",
        "lineage_ref": "lin_grid_people",
    }
    values.update(overrides)
    return module.ReturnedFact(**values)


def _brief(version: str) -> dict[str, object]:
    return {
        "catalogue_version": version,
        "headline_key": "foundation_headline",
        "decision_template_key": "foundation_decision",
        "observed": [],
        "inferred": [],
        "still_to_test": [],
        "not_measured": [],
        "next_questions": [
            {"question_key": "foundation_ask_shape", "slots": {}},
            {"question_key": "foundation_ask_walk", "slots": {}},
            {"question_key": "foundation_ask_context", "slots": {}},
        ],
        "layout": [{"component": "foundation_note", "props": {}}],
        "stage": [{"component": "hour", "props": {"hour_key": "hour_am"}}],
    }


def _swap(brief: dict[str, object], left: str, right: str) -> dict[str, object]:
    items = list(brief.items())
    positions = {key: index for index, (key, _) in enumerate(items)}
    first, second = positions[left], positions[right]
    items[first], items[second] = items[second], items[first]
    return dict(items)


def test_template_scan_rejects_a_numeral() -> None:
    import yaml

    from eii_product.assistant.catalogue.scan import find_numeral

    planted = {
        "7": "Nd",
        "\u0663": "Nd",
        "\u06f4": "Nd",
        "\u216b": "Nl",
        "\u00b2": "No",
        "\u00bd": "No",
    }
    for character, category in planted.items():
        assert unicodedata.category(character) == category
        assert find_numeral("lead " + character) == character
    for code_point in range(sys.maxunicode + 1):
        character = chr(code_point)
        if unicodedata.category(character) in NUMERAL_CATEGORIES:
            assert find_numeral(character) == character
    names = {path.name for path in SHIPPED.glob("*.yaml")}
    assert names == set(FILES)
    rendered: list[str] = []
    for path in sorted(SHIPPED.glob("*.yaml")):
        rendered.extend(_rendered(yaml.safe_load(path.read_text(encoding="utf-8"))))
    assert rendered
    for text in rendered:
        assert find_numeral(text) is None


def test_pyyaml_safe_load_keeps_the_last_equal_key() -> None:
    import yaml

    loaded = yaml.safe_load("alpha: 1\nalpha: 2\n")
    assert loaded == {"alpha": 2}


def test_four_catalogue_files_load() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    assert tuple(item.key for item in loaded.claims) == (
        "night_lights",
        "venue_busyness",
        "population_age_sex",
    )
    assert tuple(item.key for item in loaded.components) == (
        "foundation_note",
        "night_lights",
        "venue_busyness",
        "population_age_sex",
    )
    assert loaded.components[0].max_count == 1
    assert loaded.components[0].props == ()
    assert tuple(item.key for item in loaded.fragments) == (
        "foundation_headline",
        "foundation_decision",
        "night_lights",
        "venue_busyness",
        "population_age_sex",
        "night_lights_not_activity",
        "relative_busyness_not_people",
        "grid_cells_summed",
        "context_no_data",
        "context_no_forecast",
        "context_retrieved",
        "context_updated",
        "context_update_not_stated",
        "context_source",
        "context_level_answer",
        "context_level_comparison",
        "context_level_evidence",
        "context_compare_night_lights",
        "context_compare_venue_busyness",
        "context_compare_population_age_sex",
        "context_withheld_reason",
        "context_all_ages",
        "context_age_band",
        "context_female",
        "context_male",
        "context_none",
        "context_monday",
        "context_tuesday",
        "context_wednesday",
        "context_thursday",
        "context_friday",
        "context_saturday",
        "context_sunday",
        "opening_electricity_unavailable",
    )
    headline = loaded.fragments[0].fields
    decision = loaded.fragments[1].fields
    assert headline == (
        ("template_en", "What the area shows"),
        ("template_ar", "ما تظهره المنطقة"),
    )
    assert decision == (
        ("lead_en", "The figures are the ones the tools returned."),
        ("lead_ar", "الأرقام هي التي أعادتها الأدوات"),
        ("cheapest_test_en", "Read the source chain of each figure."),
        ("cheapest_test_ar", "اقرأ سلسلة المصدر لكل قيمة"),
    )
    assert tuple(item.key for item in loaded.questions) == (
        "foundation_ask_shape",
        "foundation_ask_walk",
        "foundation_ask_context",
    )
    assert loaded.questions[0].playbook == "site_check"
    assert loaded.questions[0].personas == ("local",)
    assert loaded.questions[0].fields[0] == (
        "template_en",
        "What does the area you drew show?",
    )
    assert loaded.questions[1].fields[0] == (
        "template_en",
        "What does a walk area from this pin show?",
    )
    assert loaded.questions[2].fields[0] == (
        "template_en",
        "What public context does this area have?",
    )
    assert tuple(item.name for item in loaded.directives) == (
        "fly",
        "layer",
        "highlight",
        "rings",
        "dial",
        "hour",
        "day",
        "month",
        "split",
        "set_scenario_inputs",
    )
    assert loaded.version == module.catalogue_version(SHIPPED)
    for name in FILES:
        assert (module.catalogue_directory() / name).read_bytes() == (
            SHIPPED / name
        ).read_bytes()
    assert module.check_brief(loaded, _brief(loaded.version), {}) is None


def test_unknown_keys_and_properties_fail(tmp_path: Path) -> None:
    module = _api()
    shipped = module.load_catalogue(SHIPPED)
    probes = (
        (
            {"observed": [{"claim_key": "missing_claim", "slots": {}}]},
            "UNKNOWN_CLAIM",
            "observed[0].claim_key",
        ),
        ({"headline_key": "missing_fragment"}, "UNKNOWN_FRAGMENT", "headline_key"),
        (
            {"decision_template_key": "missing_fragment"},
            "UNKNOWN_FRAGMENT",
            "decision_template_key",
        ),
        (
            {"layout": [{"component": "missing_component", "props": {}}]},
            "UNKNOWN_COMPONENT",
            "layout[0].component",
        ),
        (
            {
                "next_questions": [
                    {"question_key": "missing_question", "slots": {}},
                    {"question_key": "foundation_ask_walk", "slots": {}},
                    {"question_key": "foundation_ask_context", "slots": {}},
                ]
            },
            "UNKNOWN_QUESTION",
            "next_questions[0].question_key",
        ),
    )
    for changes, rule, path in probes:
        brief = _brief(shipped.version)
        brief.update(changes)
        assert module.check_brief(shipped, brief, {}) == module.Refusal(rule, path)
    property_files = {
        "claims.yaml": _claims(_claim(extra="extra_field: no")),
        "components.yaml": (SHIPPED / "components.yaml")
        .read_text(encoding="utf-8")
        .replace("    max_count: 1\n", "    max_count: 1\n    extra_field: no\n", 1),
        "fragments.yaml": (SHIPPED / "fragments.yaml")
        .read_text(encoding="utf-8")
        .replace(
            "    kind: headline\n", "    kind: headline\n    extra_field: no\n", 1
        ),
        "questions.yaml": (SHIPPED / "questions.yaml")
        .read_text(encoding="utf-8")
        .replace(
            "    playbook: site_check\n",
            "    playbook: site_check\n    extra_field: no\n",
            1,
        ),
    }
    paths = {
        "claims.yaml": "claims[0].extra_field",
        "components.yaml": "components[0].extra_field",
        "fragments.yaml": "fragments[0].extra_field",
        "questions.yaml": "questions[0].extra_field",
    }
    for file_name, body in property_files.items():
        folder = _copy(tmp_path, file_name, **{file_name: body})
        assert module.load_catalogue(folder) == module.Refusal(
            "UNKNOWN_PROPERTY", paths[file_name]
        )


def test_swapped_fact_slots_fail(tmp_path: Path) -> None:
    slots = _slot(name="people") + _slot(
        name="radiance",
        metric="price_deal_value",
        unit="qar",
        period="calendar_month",
    )
    claim = _claim(
        key="area_pair",
        slots=slots,
        en="People {people} and radiance {radiance}.",
        ar="الناس {people} والإشراق {radiance}.",
    )
    module, loaded = _load(tmp_path, _claims(claim))
    people = _fact(module)
    radiance = _fact(
        module,
        fact_id=FACT_B,
        metric_key="price_deal_value",
        unit="qar",
        period="2024-06",
        lineage_ref="lin_night_radiance",
    )
    facts = {people.fact_id: people, radiance.fact_id: radiance}
    paired = {"people": people.fact_id, "radiance": radiance.fact_id}
    assert module.match_slots(loaded, "area_pair", paired, facts) is None
    swapped = {"people": radiance.fact_id, "radiance": people.fact_id}
    assert module.match_slots(loaded, "area_pair", swapped, facts) == module.Refusal(
        "SLOT_METRIC", "slots.people"
    )


def test_geography_role_mismatch(tmp_path: Path) -> None:
    module, loaded = _load(tmp_path, _claims(_claim(slots=_slot())))
    fact = _fact(module, geography_kind="national")
    assert module.match_slots(
        loaded, "area_note", {"reading": fact.fact_id}, {fact.fact_id: fact}
    ) == (module.Refusal("SLOT_GEOGRAPHY", "slots.reading"))


def test_month_slot_rejects_a_year(tmp_path: Path) -> None:
    module, loaded = _load(
        tmp_path, _claims(_claim(slots=_slot(period="calendar_month")))
    )
    fact = _fact(module, period="2024")
    refused = module.match_slots(
        loaded, "area_note", {"reading": fact.fact_id}, {fact.fact_id: fact}
    )
    assert refused == module.Refusal("SLOT_PERIOD", "slots.reading")
    accepted = _fact(module, period="2024-06")
    assert (
        module.match_slots(
            loaded,
            "area_note",
            {"reading": accepted.fact_id},
            {accepted.fact_id: accepted},
        )
        is None
    )


def test_window_slot_rejects_one_month(tmp_path: Path) -> None:
    module, loaded = _load(
        tmp_path, _claims(_claim(slots=_slot(period="month_window")))
    )
    one_month = _fact(module, period="2024-06")
    assert module.match_slots(
        loaded,
        "area_note",
        {"reading": one_month.fact_id},
        {one_month.fact_id: one_month},
    ) == module.Refusal("SLOT_PERIOD", "slots.reading")
    window = _fact(module, period="2024-01/2024-06")
    assert (
        module.match_slots(
            loaded, "area_note", {"reading": window.fact_id}, {window.fact_id: window}
        )
        is None
    )


def test_unknown_period_rule(tmp_path: Path) -> None:
    module, result = _load(
        tmp_path, _claims(_claim(slots=_slot(period="release_period")))
    )
    assert result == module.Refusal(
        "UNKNOWN_PERIOD_RULE", "claims[0].slots[0].period_rule"
    )


def test_second_foundation_note() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    brief = _brief(loaded.version)
    brief["layout"] = [
        {"component": "foundation_note", "props": {}},
        {"component": "foundation_note", "props": {}},
    ]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "MAX_COUNT", "layout[1]"
    )


def test_missing_or_malformed_lineage_ref(tmp_path: Path) -> None:
    module, loaded = _load(tmp_path, _claims(_claim(slots=_slot())))
    missing = _fact(module, lineage_ref=None)
    malformed = _fact(module, lineage_ref="missing")
    for fact in (missing, malformed):
        assert module.match_slots(
            loaded, "area_note", {"reading": fact.fact_id}, {fact.fact_id: fact}
        ) == module.Refusal("LINEAGE_REF", "slots.reading.lineage_ref")


def test_brief_parts_out_of_order() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    brief = _swap(_brief(loaded.version), "still_to_test", "not_measured")
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "BRIEF_ORDER", "brief"
    )


def test_next_question_count() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    questions = _brief(loaded.version)["next_questions"]
    assert isinstance(questions, list)
    for count in (2, 4):
        brief = _brief(loaded.version)
        brief["next_questions"] = (
            list(questions)[:2] if count == 2 else [*questions, questions[0]]
        )
        assert module.check_brief(loaded, brief, {}) == module.Refusal(
            "QUESTION_COUNT", "next_questions"
        )


def test_unknown_directive() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    brief = _brief(loaded.version)
    brief["stage"] = [{"component": "spin", "props": {}}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_DIRECTIVE", "stage[0].component"
    )


def test_numeric_extra_stage_property() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    brief = _brief(loaded.version)
    brief["stage"] = [
        {"component": "hour", "props": {"hour_key": "hour_am", "count": 3}}
    ]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_PROPERTY", "stage[0].props.count"
    )
    brief["stage"] = [{"component": "hour", "props": {"hour_key": 3}}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "STAGE_VALUE", "stage[0].props.hour_key"
    )


def test_three_ring_ids() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    for count in (1, 2):
        brief = _brief(loaded.version)
        brief["stage"] = [
            {
                "component": "rings",
                "props": {
                    "area_ids": [
                        "ma1/" + "ab" * 8 + "/walk/5/none/25.000000/51.000000",
                        "ma1/" + "ab" * 8 + "/drive/5/none/25.000000/51.000000",
                    ][:count]
                },
            }
        ]
        assert module.check_brief(loaded, brief, {}) is None
    brief = _brief(loaded.version)
    brief["stage"] = [
        {
            "component": "rings",
            "props": {
                "area_ids": [
                    "ma1/" + "ab" * 8 + "/walk/5/none/25.000000/51.000000",
                    "ma1/" + "ab" * 8 + "/drive/5/none/25.000000/51.000000",
                    "ma1/" + "ab" * 8 + "/distance/5/none/25.000000/51.000000",
                ]
            },
        }
    ]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "STAGE_VALUE", "stage[0].props.area_ids"
    )


def test_split_is_two_ids_or_off() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    paired = _brief(loaded.version)
    paired["stage"] = [
        {
            "component": "split",
            "props": {
                "area_ids": [
                    "ma1/" + "ab" * 8 + "/walk/5/none/25.000000/51.000000",
                    "ma1/" + "ab" * 8 + "/drive/5/none/25.000000/51.000000",
                ]
            },
        }
    ]
    assert module.check_brief(loaded, paired, {}) is None
    off = _brief(loaded.version)
    off["stage"] = [{"component": "split", "props": {"off": True}}]
    assert module.check_brief(loaded, off, {}) is None
    one = _brief(loaded.version)
    one["stage"] = [
        {
            "component": "split",
            "props": {
                "area_ids": ["ma1/" + "ab" * 8 + "/walk/5/none/25.000000/51.000000"]
            },
        }
    ]
    assert module.check_brief(loaded, one, {}) == module.Refusal(
        "STAGE_VALUE", "stage[0].props.area_ids"
    )


def test_observed_claim_rejects_an_inferred_fact(tmp_path: Path) -> None:
    module, loaded = _load(tmp_path, _claims(_claim(slots=_slot())))
    fact = _fact(module, evidence_status="inferred")
    brief = _brief(loaded.version)
    brief["observed"] = [{"claim_key": "area_note", "slots": {"reading": fact.fact_id}}]
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) == module.Refusal(
        "SLOT_EVIDENCE", "observed[0].slots.reading"
    )


def test_place_public_simulated_slot_without_a_place_name(tmp_path: Path) -> None:
    slot = _slot(
        name="busyness",
        metric="price_deal_value",
        unit="qar",
        geo="public",
        provenance="simulated",
    )
    module, refused = _load(
        tmp_path,
        _claims(
            _claim(
                key="place_note",
                subject="place_public",
                slots=slot,
                en="The reading is {busyness}.",
                ar="القراءة هي {busyness}.",
            )
        ),
        name="load",
    )
    assert refused == module.Refusal(
        "SUBJECT_PROVENANCE", "claims[0].slots[0].allowed_provenance"
    )
    _, loaded = _load(
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
        name="match",
    )
    fact = _fact(
        module,
        metric_key="price_deal_value",
        unit="qar",
        geography_kind="public",
        provenance="simulated",
        lineage_ref="lin_busyness",
    )
    assert module.match_slots(
        loaded, "place_note", {"busyness": fact.fact_id}, {fact.fact_id: fact}
    ) == (module.Refusal("SUBJECT_PROVENANCE", "slots.busyness"))


def test_fdi_project_rejects_a_simulated_slot(tmp_path: Path) -> None:
    module, result = _load(
        tmp_path,
        _claims(
            _claim(
                key="project_note",
                subject="fdi_project",
                slots=_slot(metric="firms_per_tower", provenance="simulated"),
                en="The reading is {reading}.",
                ar="القراءة هي {reading}.",
            )
        ),
    )
    assert result == module.Refusal(
        "SUBJECT_PROVENANCE", "claims[0].slots[0].allowed_provenance"
    )


def test_synthetic_firm_subject_is_refused(tmp_path: Path) -> None:
    module, result = _load(
        tmp_path, _claims(_claim(subject="synthetic_firm", slots=_slot()))
    )
    assert result == module.Refusal("RETIRED_SUBJECT", "claims[0].subject")


def test_register_company_money_unit(tmp_path: Path) -> None:
    module, result = _load(
        tmp_path,
        _claims(
            _claim(
                subject="register_company",
                slots=_slot(metric="price_deal_value", unit="qar", geo="public"),
            )
        ),
    )
    assert result == module.Refusal("SUBJECT_UNIT", "claims[0].slots[0].unit")


def test_register_company_refuses_simulated(tmp_path: Path) -> None:
    module, refused = _load(
        tmp_path,
        _claims(
            _claim(subject="register_company", slots=_slot(provenance="simulated"))
        ),
        name="load",
    )
    assert refused == module.Refusal(
        "SUBJECT_PROVENANCE", "claims[0].slots[0].allowed_provenance"
    )
    _, loaded = _load(
        tmp_path,
        _claims(
            _claim(
                key="company_note",
                subject="register_company",
                slots=_slot(metric="employee_count", provenance="synthetic"),
                en="The count is {reading}.",
                ar="العدد هو {reading}.",
            )
        ),
        name="match",
    )
    fact = _fact(
        module,
        metric_key="employee_count",
        provenance="simulated",
        lineage_ref="lin_staff",
    )
    assert module.match_slots(
        loaded, "company_note", {"reading": fact.fact_id}, {fact.fact_id: fact}
    ) == (module.Refusal("SUBJECT_PROVENANCE", "slots.reading"))


def test_register_company_refuses_an_estimate_metric(tmp_path: Path) -> None:
    module, result = _load(
        tmp_path,
        _claims(
            _claim(
                subject="register_company",
                slots=_slot(metric="estimate_low", unit="qar", geo="public"),
            )
        ),
    )
    assert result == module.Refusal("SUBJECT_METRIC", "claims[0].slots[0].metric_key")


def test_register_company_refuses_another_synthetic_metric(tmp_path: Path) -> None:
    module, result = _load(
        tmp_path,
        _claims(
            _claim(
                subject="register_company",
                slots=_slot(metric="talent_pool", provenance="synthetic"),
            )
        ),
    )
    assert result == module.Refusal("SUBJECT_METRIC", "claims[0].slots[0].metric_key")


def test_employee_count_on_an_area_claim(tmp_path: Path) -> None:
    module, refused = _load(
        tmp_path,
        _claims(_claim(slots=_slot(metric="employee_count", provenance="synthetic"))),
        name="area",
    )
    assert refused == module.Refusal("SUBJECT_METRIC", "claims[0].slots[0].metric_key")
    _, loaded = _load(
        tmp_path,
        _claims(
            _claim(
                key="company_note",
                subject="register_company",
                slots=_slot(metric="employee_count", provenance="synthetic"),
                en="The count is {reading}.",
                ar="العدد هو {reading}.",
            )
        ),
        name="company",
    )
    fact = _fact(
        module,
        metric_key="employee_count",
        provenance="synthetic",
        lineage_ref="lin_staff",
    )
    assert (
        module.match_slots(
            loaded, "company_note", {"reading": fact.fact_id}, {fact.fact_id: fact}
        )
        is None
    )


def test_synthetic_provenance_on_a_municipality(tmp_path: Path) -> None:
    module, result = _load(
        tmp_path,
        _claims(_claim(subject="municipality", slots=_slot(provenance="synthetic"))),
    )
    assert result == module.Refusal(
        "SUBJECT_PROVENANCE", "claims[0].slots[0].allowed_provenance"
    )


def test_question_with_no_persona(tmp_path: Path) -> None:
    module = _api()
    text = (SHIPPED / "questions.yaml").read_text(encoding="utf-8")
    empty = _copy(
        tmp_path,
        "empty",
        **{"questions.yaml": text.replace("personas: [local]", "personas: []", 1)},
    )
    assert module.load_catalogue(empty) == module.Refusal(
        "EMPTY_PERSONAS", "questions[0].personas"
    )
    unknown = _copy(
        tmp_path,
        "unknown",
        **{
            "questions.yaml": text.replace(
                "personas: [local]", "personas: [official]", 1
            )
        },
    )
    assert module.load_catalogue(unknown) == module.Refusal(
        "UNKNOWN_PERSONA", "questions[0].personas"
    )


def test_loader_uses_safe_load_and_never_yaml_load() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "eii_product"
        / "assistant"
        / "catalogue"
        / "load.py"
    ).read_text(encoding="utf-8")
    assert "yaml.safe_load(" in source
    assert "yaml.load(" not in source


def test_catalogue_package_does_not_import_the_gateway() -> None:
    import importlib
    import sys

    root = Path(__file__).resolve().parents[1] / "src" / "eii_product" / "assistant"
    files = list(root.rglob("*.py"))
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "eii_gateway" not in text
        assert "eii_custodian" not in text
    importlib.import_module("eii_product.assistant.catalogue")

    assert "eii_gateway" not in sys.modules


def test_duplicate_mapping_key_is_refused(tmp_path: Path) -> None:
    module = _api()
    folder = _copy(tmp_path, **{"claims.yaml": "version: 1\nversion: 2\nclaims: []\n"})
    assert module.load_catalogue(folder) == module.Refusal(
        "DUPLICATE_KEY", "claims.yaml.version"
    )


def test_duplicate_entry_key_is_refused(tmp_path: Path) -> None:
    module, result = _load(tmp_path, _claims(_claim(), _claim()))
    assert result == module.Refusal("DUPLICATE_KEY", "claims[1].claim_key")


def test_suppressed_provenance_is_refused_at_load(tmp_path: Path) -> None:
    module, result = _load(
        tmp_path, _claims(_claim(slots=_slot(provenance="suppressed")))
    )
    assert result == module.Refusal(
        "PROVENANCE_LIST", "claims[0].slots[0].allowed_provenance"
    )


def test_suppressed_fact_is_refused_at_match(tmp_path: Path) -> None:
    module, loaded = _load(tmp_path, _claims(_claim(slots=_slot())))
    fact = _fact(module, provenance="suppressed")
    assert module.match_slots(
        loaded, "area_note", {"reading": fact.fact_id}, {fact.fact_id: fact}
    ) == (module.Refusal("SUPPRESSED_FACT", "slots.reading"))


def test_slot_unit_must_be_the_metric_unit(tmp_path: Path) -> None:
    module, wrong = _load(
        tmp_path, _claims(_claim(slots=_slot(unit="percent"))), name="wrong"
    )
    assert wrong == module.Refusal("SLOT_UNIT", "claims[0].slots[0].unit")
    _, unknown = _load(
        tmp_path, _claims(_claim(slots=_slot(unit="widget"))), name="unknown"
    )
    assert unknown == module.Refusal("UNKNOWN_UNIT", "claims[0].slots[0].unit")


def test_breakdown_sex_requires_public(tmp_path: Path) -> None:
    module, refused = _load(
        tmp_path,
        _claims(
            _claim(
                subject="national",
                slots=_slot(geo="national", breakdown="sex", provenance="synthetic"),
            )
        ),
        name="bad",
    )
    assert refused == module.Refusal("BREAKDOWN", "claims[0].slots[0].breakdown")
    _, loaded = _load(
        tmp_path,
        _claims(
            _claim(subject="national", slots=_slot(geo="national", breakdown="sex"))
        ),
        name="good",
    )
    assert loaded.claims[0].slots[0].breakdown == "sex"


def test_breakdown_age_band_requires_simulated_area(tmp_path: Path) -> None:
    module, refused = _load(
        tmp_path,
        _claims(
            _claim(
                subject="municipality",
                slots=_slot(breakdown="age_band", provenance="simulated"),
            )
        ),
        name="place",
    )
    assert refused == module.Refusal("BREAKDOWN", "claims[0].slots[0].breakdown")
    _, loaded = _load(
        tmp_path,
        _claims(
            _claim(
                slots=_slot(
                    metric="present_by_pay_band",
                    breakdown="age_band",
                    provenance="simulated",
                )
            )
        ),
        name="area",
    )
    assert loaded.claims[0].slots[0].breakdown == "age_band"


def test_undeclared_placeholder(tmp_path: Path) -> None:
    module, result = _load(
        tmp_path,
        _claims(_claim(slots=_slot(), en="See {other}.", ar="انظر {reading}.")),
    )
    assert result == module.Refusal("TEMPLATE_SLOT", "claims[0].template_en")


def test_slot_missing_in_arabic(tmp_path: Path) -> None:
    module, result = _load(
        tmp_path,
        _claims(_claim(slots=_slot(), en="See {reading}.", ar="المنطقة ظاهرة.")),
    )
    assert result == module.Refusal("TEMPLATE_SLOT", "claims[0].template_ar")


def test_stray_brace(tmp_path: Path) -> None:
    module, result = _load(
        tmp_path,
        _claims(
            _claim(slots=_slot(), en="See {reading} then {.", ar="انظر {reading}.")
        ),
    )
    assert result == module.Refusal("TEMPLATE_BRACE", "claims[0].template_en")


def test_one_changed_byte_changes_catalogue_version(tmp_path: Path) -> None:
    module = _api()
    folder = _copy(tmp_path)
    original = module.catalogue_version(folder)
    for name in FILES:
        path = folder / name
        raw = path.read_bytes()
        mutated = bytearray(raw)
        mutated[0] ^= 1
        path.write_bytes(bytes(mutated))
        assert module.catalogue_version(folder) != original
        path.write_bytes(raw)
        assert module.catalogue_version(folder) == original


def test_brief_rejects_another_catalogue_version() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    brief = _brief("a" * 64)
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "CATALOGUE_VERSION", "catalogue_version"
    )


def test_application_owned_field_is_an_unknown_property() -> None:
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    brief = _brief(loaded.version)
    brief["writer"] = "model"
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_PROPERTY", "writer"
    )


def test_still_to_test_rejects_prose() -> None:
    """The application selects these lists; a model brief must leave them empty.

    Document 09, section "5. The brief": the application selects still_to_test
    and not_measured and never accepts those choices from the model. The former
    passing case ["coverage_gap"] is refused, and so is any other non-empty list.
    """
    module = _api()
    loaded = module.load_catalogue(SHIPPED)
    assert module.check_brief(loaded, _brief(loaded.version), {}) is None
    brief = _brief(loaded.version)
    brief["still_to_test"] = ["coverage_gap"]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "APPLICATION_SELECTED", "still_to_test"
    )
    brief = _brief(loaded.version)
    brief["not_measured"] = ["outside_release"]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "APPLICATION_SELECTED", "not_measured"
    )
    brief = _brief(loaded.version)
    brief["still_to_test"] = ["not a key"]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "APPLICATION_SELECTED", "still_to_test"
    )


def test_question_slots_must_match(tmp_path: Path) -> None:
    module = _api()
    extra = (
        "  - question_key: foundation_ask_count\n"
        "    playbook: site_check\n"
        "    personas: [local]\n"
        "    slots:\n"
        + _slot(name="people")
        + '    template_en: "See {people}."\n'
        + '    template_ar: "انظر {people}."\n'
    )
    text = (SHIPPED / "questions.yaml").read_text(encoding="utf-8") + extra
    loaded = module.load_catalogue(_copy(tmp_path, **{"questions.yaml": text}))
    fact = _fact(module)
    other = _fact(
        module,
        fact_id=FACT_B,
        metric_key="price_deal_value",
        unit="qar",
        period="2024-06",
        lineage_ref="lin_night_radiance",
    )
    brief = _brief(loaded.version)
    brief["next_questions"] = [
        {"question_key": "foundation_ask_count", "slots": {"people": other.fact_id}},
        {"question_key": "foundation_ask_walk", "slots": {}},
        {"question_key": "foundation_ask_context", "slots": {}},
    ]
    assert module.check_brief(
        loaded, brief, {other.fact_id: other, fact.fact_id: fact}
    ) == (module.Refusal("SLOT_METRIC", "next_questions[0].slots.people"))
    brief["next_questions"][0] = {
        "question_key": "foundation_ask_count",
        "slots": {"people": fact.fact_id},
    }
    assert module.check_brief(loaded, brief, {fact.fact_id: fact}) is None


def test_unknown_playbook_is_refused(tmp_path: Path) -> None:
    module = _api()
    text = (SHIPPED / "questions.yaml").read_text(encoding="utf-8")
    folder = _copy(
        tmp_path,
        **{
            "questions.yaml": text.replace(
                "playbook: site_check", "playbook: other_book", 1
            )
        },
    )
    assert module.load_catalogue(folder) == module.Refusal(
        "UNKNOWN_PLAYBOOK", "questions[0].playbook"
    )


def test_malformed_fact_id(tmp_path: Path) -> None:
    module, loaded = _load(tmp_path, _claims(_claim(slots=_slot())))
    fact = _fact(module, fact_id="f_short")
    assert module.match_slots(
        loaded, "area_note", {"reading": fact.fact_id}, {fact.fact_id: fact}
    ) == (module.Refusal("FACT_ID", "slots.reading.fact_id"))
    stored = _fact(module, fact_id=FACT_B)
    assert module.match_slots(
        loaded, "area_note", {"reading": FACT_A}, {FACT_A: stored}
    ) == (module.Refusal("FACT_ID", "slots.reading.fact_id"))


def _shipped(tmp: Path, name: str = "shipped") -> Any:
    module = _api()
    loaded = module.load_catalogue(_copy(tmp, name))
    return module, loaded


def _replace(text: str, old: str, new: str) -> str:
    assert old in text
    return text.replace(old, new, 1)


def test_closed_records_stay_frozen() -> None:
    import dataclasses

    from eii_product.assistant.catalogue import schema

    slot = schema.Slot(
        "reading",
        "price_deal_count",
        "count",
        "area_shape",
        "calendar_year",
        ("public",),
        "none",
    )
    claim = schema.Claim("area_note", "observed", "area", (slot,), (), (), (), ())
    records = (
        schema.Refusal("RULE", "path"),
        slot,
        claim,
        schema.Component("foundation_note", 1, ()),
        schema.Fragment("foundation_headline", "headline", ()),
        schema.Question("foundation_ask_shape", "site_check", ("local",), (), ()),
        schema.FieldSpec("hour_key", "identifier"),
        schema.Alternative((schema.FieldSpec("hour_key", "identifier"),)),
        schema.Directive("hour", ()),
        schema.Catalogue("a" * 64, (claim,), (), (), (), ()),
        schema.ReturnedFact(
            FACT_A,
            "price_deal_count",
            "count",
            "2024",
            "area_shape",
            "public",
            "observed",
            "lin_grid_people",
        ),
    )
    for record in records:
        field = next(iter(dataclasses.fields(record))).name
        try:
            setattr(record, field, "changed")
        except dataclasses.FrozenInstanceError:
            continue
        raise AssertionError(type(record).__name__)


def test_brief_shape_and_strength(tmp_path: Path) -> None:
    module, loaded = _shipped(tmp_path)
    brief = _brief(loaded.version)
    assert module.check_brief(loaded, [], {}) == module.Refusal("NOT_MAPPING", "brief")
    brief["observed"] = "no"
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "BRIEF_TYPE", "observed"
    )
    brief["observed"] = ["no"]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "BRIEF_TYPE", "observed[0]"
    )
    brief["still_to_test"] = "no"
    brief["observed"] = []
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "BRIEF_TYPE", "still_to_test"
    )
    brief["still_to_test"] = []
    brief["next_questions"] = "no"
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "BRIEF_TYPE", "next_questions"
    )
    brief["next_questions"] = ["no", "no", "no"]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "BRIEF_TYPE", "next_questions[0]"
    )
    brief = _brief(loaded.version)
    brief["next_questions"][0] = {"question_key": 1, "slots": {}}
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_QUESTION", "next_questions[0].question_key"
    )
    brief = _brief(loaded.version)
    brief["layout"] = "no"
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "BRIEF_TYPE", "layout"
    )
    brief["layout"] = ["no"]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "BRIEF_TYPE", "layout[0]"
    )
    brief["layout"] = [{"component": 1, "props": {}}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_COMPONENT", "layout[0].component"
    )
    brief["layout"] = [{"component": "foundation_note", "props": "no"}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "BRIEF_TYPE", "layout[0].props"
    )
    brief["layout"] = [{"component": "foundation_note", "props": {"extra": True}}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_PROPERTY", "layout[0].props.extra"
    )
    brief = _brief(loaded.version)
    brief["stage"] = "no"
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "BRIEF_TYPE", "stage"
    )
    brief["stage"] = ["no"]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "BRIEF_TYPE", "stage[0]"
    )
    brief["stage"] = [{"component": 1, "props": {}}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_DIRECTIVE", "stage[0].component"
    )
    brief["stage"] = [{"component": "hour", "props": []}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "STAGE_VALUE", "stage[0].props"
    )
    import dataclasses

    questions = (
        dataclasses.replace(loaded.questions[0], playbook="other_book"),
        *loaded.questions[1:],
    )
    altered = dataclasses.replace(loaded, questions=questions)
    assert module.check_brief(altered, _brief(loaded.version), {}) == module.Refusal(
        "QUESTION_PLAYBOOK", "next_questions[0].question_key"
    )

    module, inferred = _load(
        tmp_path,
        _claims(_claim(section="inferred", slots=_slot(), strengths="[indicative]")),
        name="inferred",
    )
    fact = _fact(module, evidence_status="inferred")
    accepted = _brief(inferred.version)
    accepted["inferred"] = [
        {
            "claim_key": "area_note",
            "slots": {"reading": fact.fact_id},
            "strength": "indicative",
        }
    ]
    assert module.check_brief(inferred, accepted, {fact.fact_id: fact}) is None
    accepted["inferred"][0]["strength"] = "strong"
    assert module.check_brief(inferred, accepted, {fact.fact_id: fact}) == (
        module.Refusal("STRENGTH", "inferred[0].strength")
    )
    module, observed = _load(
        tmp_path,
        _claims(_claim(slots=_slot())),
        name="observed",
    )
    misplaced = _brief(observed.version)
    misplaced["inferred"] = [
        {
            "claim_key": "area_note",
            "slots": {"reading": fact.fact_id},
            "strength": "indicative",
        }
    ]
    assert module.check_brief(observed, misplaced, {fact.fact_id: fact}) == (
        module.Refusal("CLAIM_SECTION", "inferred[0].claim_key")
    )
    typed = _brief(observed.version)
    typed["observed"] = [
        {"claim_key": 1, "slots": {"reading": fact.fact_id}},
    ]
    assert module.check_brief(observed, typed, {fact.fact_id: fact}) == (
        module.Refusal("UNKNOWN_CLAIM", "observed[0].claim_key")
    )
    typed["observed"] = [{"claim_key": "area_note", "slots": []}]
    assert module.check_brief(observed, typed, {fact.fact_id: fact}) == (
        module.Refusal("BRIEF_TYPE", "observed[0].slots")
    )


def test_stage_values_match_the_directive(tmp_path: Path) -> None:
    module, loaded = _shipped(tmp_path, "stage")

    def stage(component: str, props: dict[str, object]) -> dict[str, object]:
        brief = _brief(loaded.version)
        brief["stage"] = [{"component": component, "props": props}]
        return brief

    assert (
        module.check_brief(
            loaded,
            stage("fly", {"target": {"area_id": "area_north"}, "zoom": "city"}),
            {},
        )
        is None
    )
    assert (
        module.check_brief(
            loaded, stage("fly", {"target": {"lat": 25, "lon": 51}, "zoom": "city"}), {}
        )
        is None
    )
    assert module.check_brief(
        loaded, stage("fly", {"target": [], "zoom": "city"}), {}
    ) == module.Refusal("STAGE_VALUE", "stage[0].props.target")
    assert module.check_brief(
        loaded, stage("fly", {"target": {"note": "area_north"}, "zoom": "city"}), {}
    ) == module.Refusal("UNKNOWN_PROPERTY", "stage[0].props.target.note")
    assert module.check_brief(
        loaded,
        stage("fly", {"target": {"lat": float("inf"), "lon": 51}, "zoom": "city"}),
        {},
    ) == module.Refusal("STAGE_VALUE", "stage[0].props.target")
    assert module.check_brief(
        loaded, stage("fly", {"target": {"area_id": 3}, "zoom": "city"}), {}
    ) == module.Refusal("STAGE_VALUE", "stage[0].props.target.area_id")
    assert module.check_brief(
        loaded,
        stage("fly", {"target": {"area_id": "area_north"}, "zoom": "village"}),
        {},
    ) == module.Refusal("STAGE_VALUE", "stage[0].props.zoom")
    assert (
        module.check_brief(
            loaded,
            stage("dial", {"situation": "weekday_lunch", "summer": True}),
            {},
        )
        is None
    )
    assert module.check_brief(
        loaded, stage("dial", {"situation": "brunch", "summer": True}), {}
    ) == module.Refusal("STAGE_VALUE", "stage[0].props.situation")
    assert module.check_brief(
        loaded, stage("dial", {"situation": "weekday_lunch", "summer": "yes"}), {}
    ) == module.Refusal("STAGE_VALUE", "stage[0].props.summer")
    assert module.check_brief(loaded, stage("split", {"off": False}), {}) == (
        module.Refusal("STAGE_VALUE", "stage[0].props.off")
    )
    assert (
        module.check_brief(loaded, stage("highlight", {"place_keys": ["unit_a"]}), {})
        is None
    )
    assert module.check_brief(
        loaded, stage("highlight", {"place_keys": ["1bad"]}), {}
    ) == module.Refusal("STAGE_VALUE", "stage[0].props.place_keys")
    assert module.check_brief(
        loaded, stage("rings", {"area_ids": [1]}), {}
    ) == module.Refusal("STAGE_VALUE", "stage[0].props.area_ids")
    assert module.check_brief(loaded, stage("hour", {"hour_key": ""}), {}) == (
        module.Refusal("STAGE_VALUE", "stage[0].props.hour_key")
    )
    assert (
        module.check_brief(
            loaded,
            stage("set_scenario_inputs", {"open": True, "focus": "rent"}),
            {},
        )
        is None
    )


def test_fact_binding_and_template_edges(tmp_path: Path) -> None:
    from eii_product.assistant.catalogue.scan import check_rendered
    from eii_product.assistant.catalogue.slots import breakdown_refusal

    module, loaded = _load(tmp_path, _claims(_claim(slots=_slot())))
    fact = _fact(module)
    facts = {fact.fact_id: fact}
    assert module.match_slots(loaded, "missing_claim", {}, {}) == module.Refusal(
        "UNKNOWN_CLAIM", "claim_key"
    )
    assert module.match_slots(loaded, "area_note", [], facts) == module.Refusal(
        "BRIEF_TYPE", "slots"
    )
    assert module.match_slots(loaded, "area_note", {}, facts) == module.Refusal(
        "SLOT_MISSING", "slots.reading"
    )
    assert module.match_slots(
        loaded, "area_note", {"reading": fact.fact_id, "other": fact.fact_id}, facts
    ) == module.Refusal("SLOT_EXTRA", "slots.other")
    assert module.match_slots(loaded, "area_note", {"reading": 1}, facts) == (
        module.Refusal("UNKNOWN_FACT", "slots.reading")
    )
    assert module.match_slots(loaded, "area_note", {"reading": fact.fact_id}, {}) == (
        module.Refusal("UNKNOWN_FACT", "slots.reading")
    )
    assert module.match_slots(
        loaded, "area_note", {"reading": fact.fact_id}, {fact.fact_id: "no"}
    ) == module.Refusal("FACT_FIELD", "slots.reading")
    wrong_unit = _fact(module, unit="percent")
    assert module.match_slots(
        loaded, "area_note", {"reading": fact.fact_id}, {fact.fact_id: wrong_unit}
    ) == module.Refusal("SLOT_UNIT", "slots.reading")
    for field, value, path in (
        ("unit", "widget", "slots.reading.unit"),
        ("provenance", "guessed", "slots.reading.provenance"),
        ("evidence_status", "maybe", "slots.reading.evidence_status"),
        ("geography_kind", "ward", "slots.reading.geography"),
        ("metric_key", "not_a_metric", "slots.reading.metric_key"),
        ("period", 2024, "slots.reading.period"),
    ):
        bad = _fact(module, **{field: value})
        assert module.match_slots(
            loaded, "area_note", {"reading": fact.fact_id}, {fact.fact_id: bad}
        ) == module.Refusal("FACT_FIELD", path)
    synthetic = _fact(module, provenance="synthetic")
    assert module.match_slots(
        loaded, "area_note", {"reading": fact.fact_id}, {fact.fact_id: synthetic}
    ) == module.Refusal("SLOT_PROVENANCE", "slots.reading")
    _, sex = _load(
        tmp_path,
        _claims(
            _claim(
                key="population_age_sex",
                slots=_slot(metric="population_grid_people", breakdown="sex"),
                caveats="[grid_cells_summed]",
            )
        ),
        name="sex",
    )
    assert module.match_slots(
        sex,
        "population_age_sex",
        {"reading": fact.fact_id},
        {
            fact.fact_id: _fact(
                module, metric_key="population_grid_people", provenance="synthetic"
            )
        },
    ) == module.Refusal("BREAKDOWN", "slots.reading")
    assert breakdown_refusal(
        "area",
        "widget",
        ("public",),
        "price_deal_count",
        "claims[0].slots[0].breakdown",
    ) == module.Refusal("BREAKDOWN", "claims[0].slots[0].breakdown")
    assert check_rendered("", (), "claims[0].template_en", require_slots=False) == (
        module.Refusal("MISSING_PROPERTY", "claims[0].template_en")
    )
    number: object = 1
    assert check_rendered(
        number, (), "claims[0].template_en", require_slots=False
    ) == module.Refusal("MISSING_PROPERTY", "claims[0].template_en")
    assert check_rendered(
        "See }.", (), "claims[0].template_en", require_slots=False
    ) == module.Refusal("TEMPLATE_BRACE", "claims[0].template_en")
    assert check_rendered(
        "The area is 7.", (), "claims[0].template_en", require_slots=False
    ) == module.Refusal("TEMPLATE_NUMERAL", "claims[0].template_en")


def test_loader_closed_field_refusals(tmp_path: Path) -> None:
    module = _api()
    claims = (SHIPPED / "claims.yaml").read_text(encoding="utf-8")
    components = (SHIPPED / "components.yaml").read_text(encoding="utf-8")
    fragments = (SHIPPED / "fragments.yaml").read_text(encoding="utf-8")
    questions = (SHIPPED / "questions.yaml").read_text(encoding="utf-8")

    def expect(name: str, refusal: Any, **files: str) -> None:
        loaded = module.load_catalogue(_copy(tmp_path, name, **files))
        assert loaded == refusal

    expect("empty", module.Refusal("NOT_MAPPING", "claims.yaml"), **{"claims.yaml": ""})
    expect(
        "version",
        module.Refusal("FILE_VERSION", "claims.yaml.version"),
        **{"claims.yaml": "version: 2\nclaims: []\n"},
    )
    expect(
        "version-bool",
        module.Refusal("FILE_VERSION", "claims.yaml.version"),
        **{"claims.yaml": "version: true\nclaims: []\n"},
    )
    expect(
        "missing",
        module.Refusal("MISSING_PROPERTY", "claims.yaml.claims"),
        **{"claims.yaml": "version: 1\n"},
    )
    expect(
        "unknown",
        module.Refusal("UNKNOWN_KEY", "claims.yaml.extra"),
        **{"claims.yaml": "version: 1\nclaims: []\nextra: 1\n"},
    )
    expect(
        "subject",
        module.Refusal("UNKNOWN_SUBJECT", "claims[0].subject"),
        **{"claims.yaml": _claims(_claim(subject="borough"))},
    )
    expect(
        "section",
        module.Refusal("CATALOGUE_VALUE", "claims[0].section"),
        **{"claims.yaml": _claims(_claim(section="other"))},
    )
    expect(
        "metric",
        module.Refusal("UNKNOWN_METRIC", "claims[0].slots[0].metric_key"),
        **{"claims.yaml": _claims(_claim(slots=_slot(metric="not_a_metric")))},
    )
    expect(
        "geography",
        module.Refusal("UNKNOWN_GEOGRAPHY_ROLE", "claims[0].slots[0].geography_role"),
        **{"claims.yaml": _claims(_claim(slots=_slot(geo="ward")))},
    )
    expect(
        "breakdown",
        module.Refusal("BREAKDOWN", "claims[0].slots[0].breakdown"),
        **{"claims.yaml": _claims(_claim(slots=_slot(breakdown="widget")))},
    )
    expect(
        "provenance",
        module.Refusal("PROVENANCE_LIST", "claims[0].slots[0].allowed_provenance"),
        **{"claims.yaml": _claims(_claim(slots=_slot(provenance="")))},
    )
    slot = _slot().replace("allowed_provenance: [public]", "allowed_provenance: public")
    expect(
        "provenance-shape",
        module.Refusal("PROVENANCE_LIST", "claims[0].slots[0].allowed_provenance"),
        **{"claims.yaml": _claims(_claim(slots=slot))},
    )
    expect(
        "numeral",
        module.Refusal("TEMPLATE_NUMERAL", "claims[0].template_en"),
        **{"claims.yaml": _claims(_claim(en="The area is 7.", ar="المنطقة ظاهرة."))},
    )
    expect(
        "empty-words",
        module.Refusal("MISSING_PROPERTY", "claims[0].template_en"),
        **{"claims.yaml": _claims(_claim(en="", ar="المنطقة ظاهرة."))},
    )
    expect(
        "brace",
        module.Refusal("TEMPLATE_BRACE", "claims[0].template_en"),
        **{"claims.yaml": _claims(_claim(en="See }.", ar="المنطقة ظاهرة."))},
    )
    expect(
        "claims-shape",
        module.Refusal("NOT_MAPPING", "claims"),
        **{"claims.yaml": "version: 1\nclaims: 1\n"},
    )
    expect(
        "max-count",
        module.Refusal("CATALOGUE_VALUE", "components[0].max_count"),
        **{"components.yaml": _replace(components, "max_count: 1", "max_count: 0")},
    )
    expect(
        "max-count-bool",
        module.Refusal("CATALOGUE_VALUE", "components[0].max_count"),
        **{"components.yaml": _replace(components, "max_count: 1", "max_count: true")},
    )
    note = "  - component_key: foundation_note\n    max_count: 1\n    props: []\n"
    expect(
        "duplicate-component",
        module.Refusal("DUPLICATE_KEY", "components[1].component_key"),
        **{"components.yaml": _replace(components, note, note + note)},
    )
    expect(
        "props-shape",
        module.Refusal("CATALOGUE_VALUE", "components[0].props"),
        **{"components.yaml": _replace(components, "props: []", "props: note")},
    )
    headline = (
        "  - fragment_key: foundation_headline\n"
        "    kind: headline\n"
        '    template_en: "What the area shows"\n'
        '    template_ar: "ما تظهره المنطقة"\n'
    )
    expect(
        "fragment-kind",
        module.Refusal("FRAGMENT_KIND", "fragments[0].kind"),
        **{"fragments.yaml": _replace(fragments, "kind: headline", "kind: other")},
    )
    expect(
        "duplicate-fragment",
        module.Refusal("DUPLICATE_KEY", "fragments[1].fragment_key"),
        **{"fragments.yaml": _replace(fragments, headline, headline + headline)},
    )
    expect(
        "duplicate-question",
        module.Refusal("DUPLICATE_KEY", "questions[1].question_key"),
        **{
            "questions.yaml": questions.replace(
                "  - question_key: foundation_ask_walk\n",
                "  - question_key: foundation_ask_shape\n",
                1,
            )
        },
    )
    question_slot = (
        "    slots:\n"
        "      - name: reading\n"
        "        metric_key: price_deal_count\n"
        "        unit: count\n"
        "        geography_role: area_shape\n"
        "        period_rule: calendar_year\n"
        "        allowed_provenance: [public]\n"
        "        breakdown: sex\n"
    )
    expect(
        "question-breakdown",
        module.Refusal("BREAKDOWN", "questions[0].slots[0].breakdown"),
        **{"questions.yaml": _replace(questions, "    slots: []\n", question_slot)},
    )
    fly = (
        "  fly:\n"
        "    fields:\n"
        "      - name: target\n"
        "        kind: target\n"
        "      - name: zoom\n"
        "        kind: enumeration\n"
        "        values: [country, city, district, street]\n"
    )
    expect(
        "directives-shape",
        module.Refusal("NOT_MAPPING", "stage_directives.fly"),
        **{"components.yaml": _replace(components, fly, "  fly: []\n")},
    )
    expect(
        "directive-property",
        module.Refusal("UNKNOWN_PROPERTY", "stage_directives.fly.other"),
        **{"components.yaml": _replace(components, fly, "  fly:\n    other: 1\n")},
    )
    hour = "  hour:\n    fields:\n      - name: hour_key\n        kind: identifier\n"
    expect(
        "directive-kind",
        module.Refusal("CATALOGUE_VALUE", "stage_directives.hour.fields[0].kind"),
        **{
            "components.yaml": _replace(
                components, hour, hour.replace("kind: identifier", "kind: widget")
            )
        },
    )
    expect(
        "directive-target",
        module.Refusal("CATALOGUE_VALUE", "stage_directives.hour.fields[0].kind"),
        **{
            "components.yaml": _replace(
                components, hour, hour.replace("kind: identifier", "kind: target")
            )
        },
    )
    expect(
        "field-name",
        module.Refusal("CATALOGUE_VALUE", "stage_directives.hour.fields[0].name"),
        **{
            "components.yaml": _replace(
                components, hour, hour.replace("name: hour_key", 'name: "Hour"')
            )
        },
    )
    expect(
        "field-property",
        module.Refusal("UNKNOWN_PROPERTY", "stage_directives.hour.fields[0].note"),
        **{
            "components.yaml": _replace(
                components,
                hour,
                hour.replace(
                    "kind: identifier\n", "kind: identifier\n        note: 1\n"
                ),
            )
        },
    )
    rings = (
        "  rings:\n"
        "    fields:\n"
        "      - name: area_ids\n"
        "        kind: area_ids\n"
        "        minimum: 1\n"
        "        maximum: 2\n"
    )
    expect(
        "maximum",
        module.Refusal("CATALOGUE_VALUE", "stage_directives.rings.fields[0].maximum"),
        **{
            "components.yaml": _replace(
                components,
                rings,
                rings.replace("minimum: 1", "minimum: 2").replace(
                    "maximum: 2", "maximum: 1"
                ),
            )
        },
    )
    expect(
        "const",
        module.Refusal(
            "CATALOGUE_VALUE", "stage_directives.split.one_of[1].fields[0].const"
        ),
        **{"components.yaml": _replace(components, "const: true", 'const: "yes"')},
    )
    expect(
        "directive-name",
        module.Refusal("UNKNOWN_KEY", "components.yaml.stage_directives.Fly"),
        **{"components.yaml": _replace(components, "  fly:\n", "  Fly:\n")},
    )
    assert claims.startswith("version: 1\n")


def test_malformed_values_are_refused(tmp_path: Path) -> None:
    module = _api()
    components = (SHIPPED / "components.yaml").read_text(encoding="utf-8")
    fragments = (SHIPPED / "fragments.yaml").read_text(encoding="utf-8")
    questions = (SHIPPED / "questions.yaml").read_text(encoding="utf-8")

    def expect(name: str, refusal: Any, **files: str) -> None:
        assert module.load_catalogue(_copy(tmp_path, name, **files)) == refusal

    expect(
        "subject-type",
        module.Refusal("MISSING_PROPERTY", "claims[0].subject"),
        **{"claims.yaml": _claims(_claim()).replace("subject: area", "subject: 1", 1)},
    )
    expect(
        "key-shape",
        module.Refusal("KEY_SHAPE", "claims[0].claim_key"),
        **{"claims.yaml": _claims(_claim(key="A"))},
    )
    expect(
        "empty-unit",
        module.Refusal("MISSING_PROPERTY", "claims[0].slots[0].unit"),
        **{
            "claims.yaml": _claims(
                _claim(slots=_slot().replace("unit: count", 'unit: ""'))
            )
        },
    )
    expect(
        "caveat-shape",
        module.Refusal("KEY_SHAPE", "claims[0].required_caveat_keys[0]"),
        **{"claims.yaml": _claims(_claim(caveats="[A]"))},
    )
    expect(
        "companion-shape",
        module.Refusal("KEY_SHAPE", "claims[0].required_companions[0]"),
        **{
            "claims.yaml": _claims(_claim()).replace(
                "required_companions: []", "required_companions: [A]", 1
            )
        },
    )
    expect(
        "strength-word",
        module.Refusal("CATALOGUE_VALUE", "claims[0].strengths_allowed[0]"),
        **{"claims.yaml": _claims(_claim(strengths="[other]"))},
    )
    expect(
        "strength-type",
        module.Refusal("CATALOGUE_VALUE", "claims[0].strengths_allowed[0]"),
        **{"claims.yaml": _claims(_claim(strengths="[1]"))},
    )
    _, loaded = _load(
        tmp_path, _claims(_claim(strengths="[strong]")), name="strength-ok"
    )
    assert loaded.claims[0].strengths_allowed == ("strong",)
    expect(
        "slots-type",
        module.Refusal("NOT_MAPPING", "claims[0].slots"),
        **{"claims.yaml": _claims(_claim()).replace("slots: []", "slots: 1", 1)},
    )
    expect(
        "slot-row",
        module.Refusal("NOT_MAPPING", "claims[0].slots[0]"),
        **{"claims.yaml": _claims(_claim()).replace("slots: []", "slots: [1]", 1)},
    )
    expect(
        "claim-row",
        module.Refusal("NOT_MAPPING", "claims[0]"),
        **{"claims.yaml": "version: 1\nclaims: [1]\n"},
    )
    expect(
        "empty-name",
        module.Refusal("MISSING_PROPERTY", "claims[0].slots[0].name"),
        **{
            "claims.yaml": _claims(
                _claim(slots=_slot().replace("name: reading", 'name: ""'))
            )
        },
    )
    expect(
        "empty-metric",
        module.Refusal("MISSING_PROPERTY", "claims[0].slots[0].metric_key"),
        **{
            "claims.yaml": _claims(
                _claim(
                    slots=_slot().replace(
                        "metric_key: price_deal_count", 'metric_key: ""'
                    )
                )
            )
        },
    )
    expect(
        "empty-geography",
        module.Refusal("MISSING_PROPERTY", "claims[0].slots[0].geography_role"),
        **{
            "claims.yaml": _claims(
                _claim(
                    slots=_slot().replace(
                        "geography_role: area_shape", 'geography_role: ""'
                    )
                )
            )
        },
    )
    expect(
        "empty-period",
        module.Refusal("MISSING_PROPERTY", "claims[0].slots[0].period_rule"),
        **{
            "claims.yaml": _claims(
                _claim(
                    slots=_slot().replace(
                        "period_rule: calendar_year", 'period_rule: ""'
                    )
                )
            )
        },
    )
    expect(
        "empty-breakdown",
        module.Refusal("MISSING_PROPERTY", "claims[0].slots[0].breakdown"),
        **{
            "claims.yaml": _claims(
                _claim(slots=_slot().replace("breakdown: none", 'breakdown: ""'))
            )
        },
    )
    expect(
        "strengths-shape",
        module.Refusal("CATALOGUE_VALUE", "claims[0].strengths_allowed"),
        **{
            "claims.yaml": _claims(_claim()).replace(
                "strengths_allowed: []", "strengths_allowed: 1", 1
            )
        },
    )
    bare = _slot().replace("        unit: count\n", "")
    expect(
        "slot-field",
        module.Refusal("MISSING_PROPERTY", "claims[0].slots[0].unit"),
        **{"claims.yaml": _claims(_claim(slots=bare))},
    )
    expect(
        "int-key",
        module.Refusal("NOT_MAPPING", "claims[0]"),
        **{"claims.yaml": "version: 1\nclaims:\n  - 1: no\n"},
    )
    doubled = _slot() + _slot()
    expect(
        "duplicate-slot",
        module.Refusal("DUPLICATE_KEY", "claims[0].slots[1].name"),
        **{
            "claims.yaml": _claims(
                _claim(slots=doubled, en="See {reading}.", ar="انظر {reading}.")
            )
        },
    )
    expect(
        "template-type",
        module.Refusal("MISSING_PROPERTY", "claims[0].template_en"),
        **{
            "claims.yaml": _claims(_claim()).replace(
                'template_en: "The area is shown."', "template_en: 1", 1
            )
        },
    )
    omitted = _claims(_claim()).replace(
        '    template_en: "The area is shown."\n', "", 1
    )
    expect(
        "template-missing",
        module.Refusal("MISSING_PROPERTY", "claims[0].template_en"),
        **{"claims.yaml": omitted},
    )
    expect(
        "components-type",
        module.Refusal("NOT_MAPPING", "components"),
        **{"components.yaml": "version: 1\ncomponents: 1\nstage_directives: {}\n"},
    )
    expect(
        "component-version",
        module.Refusal("FILE_VERSION", "components.yaml.version"),
        **{"components.yaml": components.replace("version: 1", "version: 2", 1)},
    )
    expect(
        "component-key",
        module.Refusal("KEY_SHAPE", "components[0].component_key"),
        **{
            "components.yaml": components.replace(
                "component_key: foundation_note", "component_key: A", 1
            )
        },
    )
    expect(
        "fragments-type",
        module.Refusal("NOT_MAPPING", "fragments"),
        **{"fragments.yaml": "version: 1\nfragments: 1\n"},
    )
    expect(
        "fragment-key",
        module.Refusal("KEY_SHAPE", "fragments[0].fragment_key"),
        **{
            "fragments.yaml": fragments.replace(
                "fragment_key: foundation_headline", "fragment_key: A", 1
            )
        },
    )
    expect(
        "fragment-numeral",
        module.Refusal("TEMPLATE_NUMERAL", "fragments[0].template_en"),
        **{
            "fragments.yaml": fragments.replace(
                "What the area shows", "What the area shows 7", 1
            )
        },
    )
    expect(
        "questions-type",
        module.Refusal("NOT_MAPPING", "questions"),
        **{"questions.yaml": "version: 1\nquestions: 1\n"},
    )
    expect(
        "question-key",
        module.Refusal("KEY_SHAPE", "questions[0].question_key"),
        **{
            "questions.yaml": questions.replace(
                "question_key: foundation_ask_shape", "question_key: A", 1
            )
        },
    )
    expect(
        "playbook-type",
        module.Refusal("MISSING_PROPERTY", "questions[0].playbook"),
        **{
            "questions.yaml": questions.replace(
                "playbook: site_check", "playbook: 1", 1
            )
        },
    )
    expect(
        "question-numeral",
        module.Refusal("TEMPLATE_NUMERAL", "questions[0].template_en"),
        **{
            "questions.yaml": questions.replace(
                "What does the area you drew show?",
                "What does the area you drew show 7?",
                1,
            )
        },
    )
    nested = "version: 1\nclaims:\n  - claim_key: area_note\n    claim_key: area_note\n"
    expect(
        "nested-duplicate",
        module.Refusal("DUPLICATE_KEY", "claims.yaml.claims[0].claim_key"),
        **{"claims.yaml": nested},
    )
    expect(
        "complex-key",
        module.Refusal("NOT_MAPPING", "claims.yaml"),
        **{"claims.yaml": "? [a]\n: 1\nversion: 1\nclaims: []\n"},
    )
    fly = (
        "  fly:\n"
        "    fields:\n"
        "      - name: target\n"
        "        kind: target\n"
        "      - name: zoom\n"
        "        kind: enumeration\n"
        "        values: [country, city, district, street]\n"
    )
    expect(
        "nested-directive",
        module.Refusal("DUPLICATE_KEY", "components.yaml.stage_directives.fly.fields"),
        **{
            "components.yaml": components.replace(
                fly, "  fly:\n    fields: []\n    fields: []\n", 1
            )
        },
    )
    head, _marker, _rest = components.partition("stage_directives:\n")
    expect(
        "directives-list",
        module.Refusal("NOT_MAPPING", "components.yaml.stage_directives"),
        **{"components.yaml": head + "stage_directives: []\n"},
    )
    highlight = (
        "  highlight:\n"
        "    one_of:\n"
        "      - fields:\n"
        "          - name: fact_id\n"
        "            kind: fact_id\n"
        "      - fields:\n"
        "          - name: place_keys\n"
        "            kind: identifier_list\n"
        "            minimum: 1\n"
        "      - fields:\n"
        "          - name: unit_ids\n"
        "            kind: identifier_list\n"
        "            minimum: 1\n"
    )
    expect(
        "empty-alternative",
        module.Refusal("CATALOGUE_VALUE", "stage_directives.highlight.one_of"),
        **{
            "components.yaml": components.replace(
                highlight, "  highlight:\n    one_of: []\n", 1
            )
        },
    )
    hour = "  hour:\n    fields:\n      - name: hour_key\n        kind: identifier\n"
    expect(
        "empty-fields",
        module.Refusal("CATALOGUE_VALUE", "stage_directives.hour.fields"),
        **{"components.yaml": components.replace(hour, "  hour:\n    fields: []\n", 1)},
    )
    expect(
        "field-row",
        module.Refusal("NOT_MAPPING", "stage_directives.hour.fields[0]"),
        **{
            "components.yaml": components.replace(hour, "  hour:\n    fields: [1]\n", 1)
        },
    )
    situation = (
        "      - name: situation\n"
        "        kind: enumeration\n"
        "        values: [weekday_lunch, weekday_evening, friday_evening, ramadan_iftar]\n"
    )
    expect(
        "missing-values",
        module.Refusal("MISSING_PROPERTY", "stage_directives.dial.fields[0].values"),
        **{
            "components.yaml": components.replace(
                situation, "      - name: situation\n        kind: enumeration\n", 1
            )
        },
    )
    expect(
        "empty-values",
        module.Refusal("CATALOGUE_VALUE", "stage_directives.dial.fields[0].values"),
        **{
            "components.yaml": components.replace(
                situation,
                situation.replace(
                    "values: [weekday_lunch, weekday_evening, friday_evening, ramadan_iftar]",
                    "values: []",
                ),
                1,
            )
        },
    )
    expect(
        "values-shape",
        module.Refusal("CATALOGUE_VALUE", "stage_directives.dial.fields[0].values"),
        **{
            "components.yaml": components.replace(
                situation,
                situation.replace(
                    "values: [weekday_lunch, weekday_evening, friday_evening, ramadan_iftar]",
                    "values: weekday_lunch",
                ),
                1,
            )
        },
    )
    expect(
        "blank-value",
        module.Refusal("CATALOGUE_VALUE", "stage_directives.dial.fields[0].values[0]"),
        **{
            "components.yaml": components.replace(
                situation,
                situation.replace(
                    "values: [weekday_lunch, weekday_evening, friday_evening, ramadan_iftar]",
                    'values: [""]',
                ),
                1,
            )
        },
    )
    rings = "        minimum: 1\n        maximum: 2\n"
    expect(
        "minimum",
        module.Refusal("CATALOGUE_VALUE", "stage_directives.rings.fields[0].minimum"),
        **{
            "components.yaml": components.replace(
                rings, "        minimum: 0\n        maximum: 2\n", 1
            )
        },
    )
    expect(
        "maximum-zero",
        module.Refusal("CATALOGUE_VALUE", "stage_directives.rings.fields[0].maximum"),
        **{
            "components.yaml": components.replace(
                rings, "        minimum: 1\n        maximum: 0\n", 1
            )
        },
    )
    split_alt = (
        "      - fields:\n"
        '          - name: "off"\n'
        "            kind: boolean\n"
        "            const: true\n"
    )
    expect(
        "alternative-row",
        module.Refusal("NOT_MAPPING", "stage_directives.split.one_of[1]"),
        **{"components.yaml": components.replace(split_alt, "      - 1\n", 1)},
    )
    expect(
        "alternative-property",
        module.Refusal("UNKNOWN_PROPERTY", "stage_directives.split.one_of[1]"),
        **{"components.yaml": components.replace(split_alt, "      - note: 1\n", 1)},
    )

    module, loaded = _shipped(tmp_path, "edges")
    fact = _fact(module)
    brief = _brief(loaded.version)
    brief["observed"] = [{"claim_key": "missing_claim", "note": True}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_PROPERTY", "observed[0].note"
    )
    brief = _brief(loaded.version)
    brief["observed"] = [{"claim_key": "missing_claim"}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "MISSING_PROPERTY", "observed[0].slots"
    )
    brief = _brief(loaded.version)
    brief["next_questions"][0] = {
        "question_key": "foundation_ask_shape",
        "slots": {},
        "note": True,
    }
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_PROPERTY", "next_questions[0].note"
    )
    brief = _brief(loaded.version)
    brief["layout"] = [{"component": "foundation_note", "props": {}, "note": True}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_PROPERTY", "layout[0].note"
    )
    brief = _brief(loaded.version)
    brief["stage"] = [
        {"component": "hour", "props": {"hour_key": "hour_am"}, "note": True}
    ]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_PROPERTY", "stage[0].note"
    )
    brief = _brief(loaded.version)
    brief["stage"] = [
        {"component": "split", "props": {"area_ids": ["area_a", "area_b"], "off": True}}
    ]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "STAGE_VALUE", "stage[0].props"
    )
    brief = _brief(loaded.version)
    brief["stage"] = [{"component": "rings", "props": {"area_ids": "area_a"}}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "STAGE_VALUE", "stage[0].props.area_ids"
    )
    brief = _brief(loaded.version)
    brief["stage"] = [
        {"component": "fly", "props": {"target": {1: "area_north"}, "zoom": "city"}}
    ]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "STAGE_VALUE", "stage[0].props.target"
    )
    brief = _brief(loaded.version)
    brief["stage"] = [{"component": "fly", "props": {"target": {}, "zoom": "city"}}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "STAGE_VALUE", "stage[0].props.target"
    )
    brief = _brief(loaded.version)
    brief["stage"] = [
        {
            "component": "fly",
            "props": {
                "target": {"area_id": "area_north", "place_key": "pin_a"},
                "zoom": "city",
            },
        }
    ]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "STAGE_VALUE", "stage[0].props.target"
    )
    brief = _brief(loaded.version)
    brief["stage"] = [
        {
            "component": "fly",
            "props": {"target": {"lat": 25.5, "lon": 51.5}, "zoom": "city"},
        }
    ]
    assert module.check_brief(loaded, brief, {}) is None
    brief = _brief(loaded.version)
    brief["stage"] = [
        {
            "component": "fly",
            "props": {"target": {"lat": "north", "lon": 51}, "zoom": "city"},
        }
    ]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "STAGE_VALUE", "stage[0].props.target"
    )
    brief = _brief(loaded.version)
    brief["observed"] = [{"claim_key": "missing_claim", "slots": {}, 1: "x"}]
    assert module.check_brief(loaded, brief, {}) == module.Refusal(
        "UNKNOWN_PROPERTY", "observed[0].field"
    )
    ask = (
        "  - question_key: foundation_ask_count\n"
        "    playbook: site_check\n"
        "    personas: [local]\n"
        "    slots:\n"
        "      - name: people\n"
        "        metric_key: price_deal_count\n"
        "        unit: count\n"
        "        geography_role: area_shape\n"
        "        period_rule: calendar_year\n"
        "        allowed_provenance: [public]\n"
        "        breakdown: none\n"
        '    template_en: "See {people}."\n'
        '    template_ar: "انظر {people}."\n'
    )
    folder = _copy(tmp_path, "qslots", **{"questions.yaml": questions + ask})
    asked = module.load_catalogue(folder)
    brief = _brief(asked.version)
    brief["next_questions"] = [
        {"question_key": "foundation_ask_count", "slots": {"other": fact.fact_id}},
        {"question_key": "foundation_ask_walk", "slots": {}},
        {"question_key": "foundation_ask_context", "slots": {}},
    ]
    assert module.check_brief(asked, brief, {fact.fact_id: fact}) == module.Refusal(
        "QUESTION_SLOTS", "next_questions[0].slots"
    )
    noted_components = components.replace(
        "props: []",
        "props:\n      - name: note\n        kind: boolean",
        1,
    )
    folder = _copy(tmp_path, "props", **{"components.yaml": noted_components})
    with_props = module.load_catalogue(folder)
    brief = _brief(with_props.version)
    assert module.check_brief(with_props, brief, {}) == module.Refusal(
        "MISSING_PROPERTY", "layout[0].props"
    )
    brief["layout"] = [{"component": "foundation_note", "props": {"note": True}}]
    assert module.check_brief(with_props, brief, {}) is None
