"""Validate claim, component, fragment and question entries."""

from __future__ import annotations

from eii_product.assistant.catalogue.scan import check_rendered
from eii_product.assistant.catalogue.schema import (
    BREAKDOWNS,
    CLAIM_FIELDS,
    COMPONENT_FIELDS,
    DECISION_FIELDS,
    FACT_UNITS,
    GEOGRAPHY_KINDS,
    HEADLINE_FIELDS,
    KEY,
    METRIC_UNITS,
    PERIOD_PATTERNS,
    PLAYBOOKS,
    PROVENANCE_ALLOWED,
    QUESTION_FIELDS,
    SECTIONS,
    SLOT_FIELDS,
    STRENGTHS,
    SUBJECTS,
    Claim,
    Component,
    FieldSpec,
    Fragment,
    Question,
    Refusal,
    Slot,
)
from eii_product.assistant.catalogue.slots import (
    breakdown_refusal,
    mixed_breakdown_index,
    subject_refusal,
)


def _claims(value: object) -> tuple[Claim, ...] | Refusal:
    rows = _rows(value, "claims")
    if isinstance(rows, Refusal):
        return rows
    claims: list[Claim] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        path = f"claims[{index}]"
        refusal = _exact(row, CLAIM_FIELDS, path)
        if refusal is not None:
            return refusal
        key = _key(row, "claim_key", path)
        if isinstance(key, Refusal):
            return key
        if key in seen:
            return Refusal("DUPLICATE_KEY", f"{path}.claim_key")
        seen.add(key)
        claim = _claim(row, path, key)
        if isinstance(claim, Refusal):
            return claim
        claims.append(claim)
    return tuple(claims)


def _claim(row: dict[str, object], path: str, key: str) -> Claim | Refusal:
    section = _member(row["section"], SECTIONS, f"{path}.section")
    if isinstance(section, Refusal):
        return section
    subject = _text(row["subject"], f"{path}.subject")
    if isinstance(subject, Refusal):
        return subject
    if subject == "synthetic_firm":
        return Refusal("RETIRED_SUBJECT", f"{path}.subject")
    if subject not in SUBJECTS:
        return Refusal("UNKNOWN_SUBJECT", f"{path}.subject")
    slots = _slots(row["slots"], f"{path}.slots", subject)
    if isinstance(slots, Refusal):
        return slots
    caveats = _keys(row["required_caveat_keys"], f"{path}.required_caveat_keys")
    if isinstance(caveats, Refusal):
        return caveats
    companions = _keys(row["required_companions"], f"{path}.required_companions")
    if isinstance(companions, Refusal):
        return companions
    strengths = _members(
        row["strengths_allowed"], STRENGTHS, f"{path}.strengths_allowed"
    )
    if isinstance(strengths, Refusal):
        return strengths
    fields = _rendered(
        row, path, ("template_en", "template_ar"), tuple(slot.name for slot in slots)
    )
    if isinstance(fields, Refusal):
        return fields
    return Claim(key, section, subject, slots, caveats, companions, strengths, fields)


def _components(value: object) -> tuple[Component, ...] | Refusal:
    rows = _rows(value, "components")
    if isinstance(rows, Refusal):
        return rows
    components: list[Component] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        path = f"components[{index}]"
        refusal = _exact(row, COMPONENT_FIELDS, path)
        if refusal is not None:
            return refusal
        key = _key(row, "component_key", path)
        if isinstance(key, Refusal):
            return key
        if key in seen:
            return Refusal("DUPLICATE_KEY", f"{path}.component_key")
        seen.add(key)
        maximum = row["max_count"]
        if type(maximum) is not int or maximum < 1:
            return Refusal("CATALOGUE_VALUE", f"{path}.max_count")
        props = _component_props(row["props"], f"{path}.props")
        if isinstance(props, Refusal):
            return props
        components.append(Component(key, maximum, props))
    return tuple(components)


def _fragments(value: object) -> tuple[Fragment, ...] | Refusal:
    rows = _rows(value, "fragments")
    if isinstance(rows, Refusal):
        return rows
    fragments: list[Fragment] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        path = f"fragments[{index}]"
        kind = row.get("kind")
        rendered_names: tuple[str, ...]
        if kind == "headline":
            fragment_kind = "headline"
            rendered_names = HEADLINE_FIELDS
        elif kind == "decision":
            fragment_kind = "decision"
            rendered_names = DECISION_FIELDS
        else:
            return Refusal("FRAGMENT_KIND", f"{path}.kind")
        allowed = frozenset({"fragment_key", "kind", *rendered_names})
        refusal = _exact(row, allowed, path)
        if refusal is not None:
            return refusal
        key = _key(row, "fragment_key", path)
        if isinstance(key, Refusal):
            return key
        if key in seen:
            return Refusal("DUPLICATE_KEY", f"{path}.fragment_key")
        seen.add(key)
        fields = _rendered(row, path, rendered_names, ())
        if isinstance(fields, Refusal):
            return fields
        fragments.append(Fragment(key, fragment_kind, fields))
    return tuple(fragments)


def _questions(value: object) -> tuple[Question, ...] | Refusal:
    rows = _rows(value, "questions")
    if isinstance(rows, Refusal):
        return rows
    questions: list[Question] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        path = f"questions[{index}]"
        refusal = _exact(row, QUESTION_FIELDS, path)
        if refusal is not None:
            return refusal
        key = _key(row, "question_key", path)
        if isinstance(key, Refusal):
            return key
        if key in seen:
            return Refusal("DUPLICATE_KEY", f"{path}.question_key")
        seen.add(key)
        playbook = _text(row["playbook"], f"{path}.playbook")
        if isinstance(playbook, Refusal):
            return playbook
        if playbook not in PLAYBOOKS:
            return Refusal("UNKNOWN_PLAYBOOK", f"{path}.playbook")
        personas = _personas(row["personas"], f"{path}.personas")
        if isinstance(personas, Refusal):
            return personas
        slots = _slots(row["slots"], f"{path}.slots", None)
        if isinstance(slots, Refusal):
            return slots
        fields = _rendered(
            row,
            path,
            ("template_en", "template_ar"),
            tuple(slot.name for slot in slots),
        )
        if isinstance(fields, Refusal):
            return fields
        questions.append(Question(key, playbook, personas, slots, fields))
    return tuple(questions)


def _slots(value: object, path: str, subject: str | None) -> tuple[Slot, ...] | Refusal:
    if not isinstance(value, list):
        return Refusal("NOT_MAPPING", path)
    slots: list[Slot] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        slot_path = f"{path}[{index}]"
        row = _string_key_mapping(item, slot_path)
        if isinstance(row, Refusal):
            return row
        refusal = _exact(row, SLOT_FIELDS, slot_path)
        if refusal is not None:
            return refusal
        slot = _slot(row, slot_path, subject)
        if isinstance(slot, Refusal):
            return slot
        if slot.name in seen:
            return Refusal("DUPLICATE_KEY", f"{slot_path}.name")
        seen.add(slot.name)
        for earlier in slots:
            if _same_slot(earlier, slot):
                return Refusal("SLOT_IDENTICAL", slot_path)
            if _overlapping_slot(earlier, slot):
                return Refusal("SLOT_OVERLAP", slot_path)
        slots.append(slot)
    mixed = mixed_breakdown_index(tuple(slots))
    if mixed is not None:
        return Refusal("BREAKDOWN_MIXED", f"{path}[{mixed}].breakdown")
    return tuple(slots)


def _slot(row: dict[str, object], path: str, subject: str | None) -> Slot | Refusal:
    name = _key(row, "name", path)
    if isinstance(name, Refusal):
        return name
    metric = _key(row, "metric_key", path)
    if isinstance(metric, Refusal):
        return metric
    unit = _text(row["unit"], f"{path}.unit")
    if isinstance(unit, Refusal):
        return unit
    geography = _text(row["geography_role"], f"{path}.geography_role")
    if isinstance(geography, Refusal):
        return geography
    period = _text(row["period_rule"], f"{path}.period_rule")
    if isinstance(period, Refusal):
        return period
    breakdown = _text(row["breakdown"], f"{path}.breakdown")
    if isinstance(breakdown, Refusal):
        return breakdown
    provenances = _provenances(row["allowed_provenance"], f"{path}.allowed_provenance")
    if isinstance(provenances, Refusal):
        return provenances
    if metric not in METRIC_UNITS:
        return Refusal("UNKNOWN_METRIC", f"{path}.metric_key")
    if unit not in FACT_UNITS:
        return Refusal("UNKNOWN_UNIT", f"{path}.unit")
    if unit not in METRIC_UNITS[metric]:
        return Refusal("SLOT_UNIT", f"{path}.unit")
    if geography not in GEOGRAPHY_KINDS:
        return Refusal("UNKNOWN_GEOGRAPHY_ROLE", f"{path}.geography_role")
    if period not in PERIOD_PATTERNS:
        return Refusal("UNKNOWN_PERIOD_RULE", f"{path}.period_rule")
    if breakdown not in BREAKDOWNS:
        return Refusal("BREAKDOWN", f"{path}.breakdown")
    if subject is None:
        if metric == "employee_count":
            return Refusal("QUESTION_METRIC", f"{path}.metric_key")
        if breakdown != "none":
            return Refusal("BREAKDOWN", f"{path}.breakdown")
    else:
        refusal = breakdown_refusal(
            subject, breakdown, provenances, metric, f"{path}.breakdown"
        )
        if refusal is not None:
            return refusal
        refusal = subject_refusal(
            subject,
            metric,
            unit,
            provenances,
            metric_path=f"{path}.metric_key",
            unit_path=f"{path}.unit",
            provenance_path=f"{path}.allowed_provenance",
        )
        if refusal is not None:
            return refusal
    return Slot(name, metric, unit, geography, period, provenances, breakdown)


def _rendered(
    row: dict[str, object],
    path: str,
    names: tuple[str, ...],
    slot_names: tuple[str, ...],
) -> tuple[tuple[str, str], ...] | Refusal:
    fields: list[tuple[str, str]] = []
    for name in names:
        text = row[name]
        if not isinstance(text, str):
            return Refusal("MISSING_PROPERTY", f"{path}.{name}")
        refusal = check_rendered(
            text,
            slot_names,
            f"{path}.{name}",
            require_slots=name in {"template_en", "template_ar"},
        )
        if refusal is not None:
            return refusal
        fields.append((name, text))
    return tuple(fields)


def _personas(value: object, path: str) -> tuple[str, ...] | Refusal:
    if not isinstance(value, list) or not value:
        return Refusal("EMPTY_PERSONAS", path)
    personas: list[str] = []
    for item in value:
        if not isinstance(item, str) or item not in {
            "international",
            "local",
            "start_up",
        }:
            return Refusal("UNKNOWN_PERSONA", path)
        personas.append(item)
    return tuple(personas)


def _provenances(value: object, path: str) -> tuple[str, ...] | Refusal:
    if not isinstance(value, list) or not value:
        return Refusal("PROVENANCE_LIST", path)
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or item not in PROVENANCE_ALLOWED:
            return Refusal("PROVENANCE_LIST", path)
        items.append(item)
    return tuple(dict.fromkeys(items))


def _rows(value: object, path: str) -> list[dict[str, object]] | Refusal:
    if not isinstance(value, list):
        return Refusal("NOT_MAPPING", path)
    rows: list[dict[str, object]] = []
    for index, item in enumerate(value):
        row = _string_key_mapping(item, f"{path}[{index}]")
        if isinstance(row, Refusal):
            return row
        rows.append(row)
    return rows


def _exact(row: dict[str, object], fields: frozenset[str], path: str) -> Refusal | None:
    unknown = [key for key in row if key not in fields]
    if unknown:
        return Refusal("UNKNOWN_PROPERTY", f"{path}.{unknown[0]}")
    missing = [key for key in sorted(fields) if key not in row]
    if missing:
        return Refusal("MISSING_PROPERTY", f"{path}.{missing[0]}")
    return None


def _key(row: dict[str, object], name: str, path: str) -> str | Refusal:
    value = _text(row[name], f"{path}.{name}")
    if isinstance(value, Refusal):
        return value
    if KEY.fullmatch(value) is None:
        return Refusal("KEY_SHAPE", f"{path}.{name}")
    return value


def _same_binding(left: Slot, right: Slot) -> bool:
    return (
        left.metric_key == right.metric_key
        and left.unit == right.unit
        and left.geography_role == right.geography_role
        and left.period_rule == right.period_rule
        and left.breakdown == right.breakdown
    )


def _same_slot(left: Slot, right: Slot) -> bool:
    provenances = set(left.allowed_provenance) == set(right.allowed_provenance)
    return _same_binding(left, right) and provenances


def _overlapping_slot(left: Slot, right: Slot) -> bool:
    shared = set(left.allowed_provenance) & set(right.allowed_provenance)
    return _same_binding(left, right) and bool(shared)


def _component_props(value: object, path: str) -> tuple[FieldSpec, ...] | Refusal:
    if not isinstance(value, list):
        return Refusal("CATALOGUE_VALUE", path)
    props: list[FieldSpec] = []
    for index, item in enumerate(value):
        row_path = f"{path}[{index}]"
        row = _string_key_mapping(item, row_path)
        if isinstance(row, Refusal):
            return row
        prop = _component_prop(row, row_path)
        if isinstance(prop, Refusal):
            return prop
        props.append(prop)
    return tuple(props)


def _component_prop(row: dict[str, object], path: str) -> FieldSpec | Refusal:
    kind = row.get("kind")
    name = row.get("name")
    if not isinstance(kind, str) or kind not in {"enumeration", "boolean", "fact_id"}:
        return Refusal("CATALOGUE_VALUE", f"{path}.kind")
    if not isinstance(name, str) or KEY.fullmatch(name) is None:
        return Refusal("CATALOGUE_VALUE", f"{path}.name")
    allowed = {"name", "kind"}
    if kind == "enumeration":
        allowed.add("values")
    unknown = [key for key in row if key not in allowed]
    if unknown:
        return Refusal("UNKNOWN_PROPERTY", f"{path}.{unknown[0]}")
    if kind != "enumeration":
        return FieldSpec(name, kind)
    if "values" not in row:
        return Refusal("MISSING_PROPERTY", f"{path}.values")
    parsed = _plain_strings(row["values"], f"{path}.values")
    if isinstance(parsed, Refusal):
        return parsed
    if not parsed:
        return Refusal("CATALOGUE_VALUE", f"{path}.values")
    shaped = _key_values(parsed, f"{path}.values")
    if isinstance(shaped, Refusal):
        return shaped
    return FieldSpec(name, kind, shaped)


def _key_values(values: tuple[str, ...], path: str) -> tuple[str, ...] | Refusal:
    for index, item in enumerate(values):
        if KEY.fullmatch(item) is None:
            return Refusal("KEY_SHAPE", f"{path}[{index}]")
    return values


def _keys(value: object, path: str) -> tuple[str, ...] | Refusal:
    if not isinstance(value, list):
        return Refusal("CATALOGUE_VALUE", path)
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or KEY.fullmatch(item) is None:
            return Refusal("KEY_SHAPE", f"{path}[{index}]")
        items.append(item)
    return tuple(items)


def _members(
    value: object, allowed: frozenset[str], path: str
) -> tuple[str, ...] | Refusal:
    if not isinstance(value, list):
        return Refusal("CATALOGUE_VALUE", path)
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or item not in allowed:
            return Refusal("CATALOGUE_VALUE", f"{path}[{index}]")
        items.append(item)
    return tuple(items)


def _member(value: object, allowed: frozenset[str], path: str) -> str | Refusal:
    if not isinstance(value, str) or value not in allowed:
        return Refusal("CATALOGUE_VALUE", path)
    return value


def _text(value: object, path: str) -> str | Refusal:
    if not isinstance(value, str) or value == "":
        return Refusal("MISSING_PROPERTY", path)
    return value


def _plain_strings(value: object, path: str) -> tuple[str, ...] | Refusal:
    if not isinstance(value, list):
        return Refusal("CATALOGUE_VALUE", path)
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or item == "":
            return Refusal("CATALOGUE_VALUE", f"{path}[{index}]")
        items.append(item)
    return tuple(items)


def _count(value: object, path: str) -> int | Refusal:
    if type(value) is not int or value < 1:
        return Refusal("CATALOGUE_VALUE", path)
    return value


def _string_key_mapping(value: object, path: str) -> dict[str, object] | Refusal:
    if not isinstance(value, dict):
        return Refusal("NOT_MAPPING", path)
    narrowed: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return Refusal("NOT_MAPPING", path)
        narrowed[key] = item
    return narrowed
