"""Brief order, question count, layout and stage checks."""

from __future__ import annotations

from collections.abc import Mapping

from eii_product.assistant.catalogue.schema import (
    BRIEF_ORDER,
    FACT_ID,
    IDENTIFIER,
    PLAYBOOKS,
    STRENGTHS,
    Alternative,
    Catalogue,
    Directive,
    FieldSpec,
    Refusal,
    ReturnedFact,
)
from eii_product.assistant.catalogue.slots import (
    match_slot_list,
    returned_fact_refusal,
)

_OBSERVED_FIELDS = frozenset({"claim_key", "slots"})
_INFERRED_FIELDS = frozenset({"claim_key", "slots", "strength"})
_QUESTION_FIELDS = frozenset({"question_key", "slots"})
_COMPONENT_FIELDS = frozenset({"component", "props"})
_TARGET_SHAPES = (
    frozenset({"area_id"}),
    frozenset({"place_key"}),
    frozenset({"zone_code"}),
    frozenset({"lat", "lon"}),
)
_TARGET_KEYS = frozenset({"area_id", "place_key", "zone_code", "lat", "lon"})


def check_brief(
    catalogue: Catalogue,
    brief: Mapping[str, object],
    facts: Mapping[str, ReturnedFact],
) -> Refusal | None:
    """Accept a model brief only when every part matches the catalogue."""
    if not isinstance(brief, dict):
        return Refusal("NOT_MAPPING", "brief")
    keys = tuple(brief)
    for key in keys:
        if not isinstance(key, str) or key not in BRIEF_ORDER:
            return Refusal("UNKNOWN_PROPERTY", str(key))
    if keys != BRIEF_ORDER:
        return Refusal("BRIEF_ORDER", "brief")
    if brief["catalogue_version"] != catalogue.version:
        return Refusal("CATALOGUE_VERSION", "catalogue_version")
    for name, path, kind in (
        ("headline_key", "headline_key", "headline"),
        ("decision_template_key", "decision_template_key", "decision"),
    ):
        refusal = _fragment(catalogue, brief[name], path, kind)
        if refusal is not None:
            return refusal
    for section in ("observed", "inferred"):
        refusal = _section(catalogue, brief[section], section, facts)
        if refusal is not None:
            return refusal
    for name in ("still_to_test", "not_measured"):
        refusal = _key_list(brief[name], name)
        if refusal is not None:
            return refusal
    refusal = _questions(catalogue, brief["next_questions"], facts)
    if refusal is not None:
        return refusal
    refusal = _layout(catalogue, brief["layout"], facts)
    if refusal is not None:
        return refusal
    return _stage(catalogue, brief["stage"], facts)


def _fragment(
    catalogue: Catalogue, value: object, path: str, kind: str
) -> Refusal | None:
    if not isinstance(value, str):
        return Refusal("UNKNOWN_FRAGMENT", path)
    fragment = catalogue.find_fragment(value)
    if fragment is None:
        return Refusal("UNKNOWN_FRAGMENT", path)
    if fragment.kind != kind:
        return Refusal("FRAGMENT_KIND", path)
    return None


def _section(
    catalogue: Catalogue,
    items: object,
    section: str,
    facts: Mapping[str, ReturnedFact],
) -> Refusal | None:
    if not isinstance(items, list):
        return Refusal("BRIEF_TYPE", section)
    required = _OBSERVED_FIELDS if section == "observed" else _INFERRED_FIELDS
    for index, item in enumerate(items):
        path = f"{section}[{index}]"
        if not isinstance(item, dict):
            return Refusal("BRIEF_TYPE", path)
        refusal = _exact_keys(item, required, path)
        if refusal is not None:
            return refusal
        claim_key = item["claim_key"]
        if not isinstance(claim_key, str):
            return Refusal("UNKNOWN_CLAIM", f"{path}.claim_key")
        claim = catalogue.find_claim(claim_key)
        if claim is None:
            return Refusal("UNKNOWN_CLAIM", f"{path}.claim_key")
        if claim.section != section:
            return Refusal("CLAIM_SECTION", f"{path}.claim_key")
        if claim.subject == "register_company":
            return Refusal("REGISTER_COMPANY_ITEM", f"{path}.claim_key")
        if section == "inferred":
            strength = item["strength"]
            if (
                not isinstance(strength, str)
                or strength not in STRENGTHS
                or strength not in claim.strengths_allowed
            ):
                return Refusal("STRENGTH", f"{path}.strength")
        slots = item["slots"]
        if not isinstance(slots, dict):
            return Refusal("BRIEF_TYPE", f"{path}.slots")
        refusal = match_slot_list(
            claim.slots,
            slots,
            facts,
            subject=claim.subject,
            evidence=claim.section,
            item_path=path,
        )
        if refusal is not None:
            return refusal
    return None


def _key_list(value: object, path: str) -> Refusal | None:
    if not isinstance(value, list):
        return Refusal("BRIEF_TYPE", path)
    if len(value) != 0:
        return Refusal("APPLICATION_SELECTED", path)
    return None


def _questions(
    catalogue: Catalogue,
    items: object,
    facts: Mapping[str, ReturnedFact],
) -> Refusal | None:
    if not isinstance(items, list):
        return Refusal("BRIEF_TYPE", "next_questions")
    if len(items) != 3:
        return Refusal("QUESTION_COUNT", "next_questions")
    seen: set[str] = set()
    for index, item in enumerate(items):
        path = f"next_questions[{index}]"
        if not isinstance(item, dict):
            return Refusal("BRIEF_TYPE", path)
        refusal = _exact_keys(item, _QUESTION_FIELDS, path)
        if refusal is not None:
            return refusal
        question_key = item["question_key"]
        if not isinstance(question_key, str):
            return Refusal("UNKNOWN_QUESTION", f"{path}.question_key")
        if question_key in seen:
            return Refusal("QUESTION_DUPLICATE", f"{path}.question_key")
        seen.add(question_key)
        question = catalogue.find_question(question_key)
        if question is None:
            return Refusal("UNKNOWN_QUESTION", f"{path}.question_key")
        if question.playbook not in PLAYBOOKS:
            return Refusal("QUESTION_PLAYBOOK", f"{path}.question_key")
        slots = item["slots"]
        names = {slot.name for slot in question.slots}
        if not isinstance(slots, dict) or set(slots) != names:
            return Refusal("QUESTION_SLOTS", f"{path}.slots")
        for slot in question.slots:
            bound = slots[slot.name]
            if isinstance(bound, str):
                fact = facts.get(bound)
                if (
                    isinstance(fact, ReturnedFact)
                    and fact.metric_key == "employee_count"
                ):
                    return Refusal("REGISTER_COMPANY_FACT", f"{path}.slots.{slot.name}")
        refusal = match_slot_list(
            question.slots,
            slots,
            facts,
            subject=None,
            evidence=None,
            item_path=path,
        )
        if refusal is not None:
            return refusal
    return None


def _layout(
    catalogue: Catalogue,
    items: object,
    facts: Mapping[str, ReturnedFact],
) -> Refusal | None:
    if not isinstance(items, list):
        return Refusal("BRIEF_TYPE", "layout")
    counts: dict[str, int] = {}
    for index, item in enumerate(items):
        path = f"layout[{index}]"
        if not isinstance(item, dict):
            return Refusal("BRIEF_TYPE", path)
        refusal = _exact_keys(item, _COMPONENT_FIELDS, path)
        if refusal is not None:
            return refusal
        name = item["component"]
        if not isinstance(name, str):
            return Refusal("UNKNOWN_COMPONENT", f"{path}.component")
        component = catalogue.find_component(name)
        if component is None:
            return Refusal("UNKNOWN_COMPONENT", f"{path}.component")
        counts[name] = counts.get(name, 0) + 1
        if counts[name] > component.max_count:
            return Refusal("MAX_COUNT", path)
        props = item["props"]
        if not isinstance(props, dict):
            return Refusal("BRIEF_TYPE", f"{path}.props")
        allowed = {prop.name: prop for prop in component.props}
        for key in props:
            if not isinstance(key, str) or key not in allowed:
                shown = key if isinstance(key, str) else "props"
                return Refusal("UNKNOWN_PROPERTY", f"{path}.props.{shown}")
        if set(props) != set(allowed):
            return Refusal("MISSING_PROPERTY", f"{path}.props")
        for name, field in allowed.items():
            refusal = _prop_value(props[name], field, f"{path}.props.{name}", facts)
            if refusal is not None:
                return refusal
    return None


def _stage(
    catalogue: Catalogue,
    items: object,
    facts: Mapping[str, ReturnedFact],
) -> Refusal | None:
    if not isinstance(items, list):
        return Refusal("BRIEF_TYPE", "stage")
    for index, item in enumerate(items):
        path = f"stage[{index}]"
        if not isinstance(item, dict):
            return Refusal("BRIEF_TYPE", path)
        refusal = _exact_keys(item, _COMPONENT_FIELDS, path)
        if refusal is not None:
            return refusal
        name = item["component"]
        if not isinstance(name, str):
            return Refusal("UNKNOWN_DIRECTIVE", f"{path}.component")
        directive = catalogue.find_directive(name)
        if directive is None:
            return Refusal("UNKNOWN_DIRECTIVE", f"{path}.component")
        props = item["props"]
        if not isinstance(props, dict):
            return Refusal("STAGE_VALUE", f"{path}.props")
        refusal = _directive_props(directive, props, f"{path}.props", facts)
        if refusal is not None:
            return refusal
    return None


def _directive_props(
    directive: Directive,
    props: dict[object, object],
    path: str,
    facts: Mapping[str, ReturnedFact],
) -> Refusal | None:
    allowed: set[str] = set()
    for alternative in directive.alternatives:
        for field in alternative.fields:
            allowed.add(field.name)
    for key in props:
        if not isinstance(key, str) or key not in allowed:
            shown = key if isinstance(key, str) else "props"
            return Refusal("UNKNOWN_PROPERTY", f"{path}.{shown}")
    names = {key for key in props if isinstance(key, str)}
    exact = [
        alternative
        for alternative in directive.alternatives
        if {field.name for field in alternative.fields} == names
    ]
    if not exact:
        return Refusal("STAGE_VALUE", path)
    first: Refusal | None = None
    for alternative in exact:
        refusal = _alternative(props, alternative, path, facts)
        if refusal is None:
            return None
        if first is None:
            first = refusal
    return first


def _alternative(
    props: dict[object, object],
    alternative: Alternative,
    path: str,
    facts: Mapping[str, ReturnedFact],
) -> Refusal | None:
    for field in alternative.fields:
        refusal = _field_value(props[field.name], field, f"{path}.{field.name}", facts)
        if refusal is not None:
            return refusal
    return None


def _prop_value(
    value: object,
    field: FieldSpec,
    path: str,
    facts: Mapping[str, ReturnedFact],
) -> Refusal | None:
    if field.kind == "enumeration":
        if isinstance(value, str) and value in field.values:
            return None
        return Refusal("PROP_VALUE", path)
    if field.kind == "boolean":
        if type(value) is bool:
            return None
        return Refusal("PROP_VALUE", path)
    if field.kind == "fact_id":
        found = _lookup_returned_fact(value, path, facts, "PROP_VALUE")
        if isinstance(found, Refusal):
            return found
        bound, fact = found
        refusal = returned_fact_refusal(fact, bound, path)
        if refusal is not None:
            return refusal
        return _company_fact(fact, path)
    return Refusal("PROP_VALUE", path)


def _lookup_returned_fact(
    value: object,
    path: str,
    facts: Mapping[str, ReturnedFact],
    malformed: str,
) -> tuple[str, ReturnedFact] | Refusal:
    if not isinstance(value, str) or FACT_ID.fullmatch(value) is None:
        return Refusal(malformed, path)
    fact = facts.get(value)
    if not isinstance(fact, ReturnedFact):
        return Refusal("UNKNOWN_FACT", path)
    return value, fact


def _company_fact(fact: ReturnedFact, path: str) -> Refusal | None:
    if fact.metric_key == "employee_count":
        return Refusal("REGISTER_COMPANY_FACT", path)
    return None


def _field_value(
    value: object,
    field: FieldSpec,
    path: str,
    facts: Mapping[str, ReturnedFact],
) -> Refusal | None:
    if field.kind == "identifier":
        if isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None:
            return None
        return Refusal("STAGE_VALUE", path)
    if field.kind == "enumeration":
        if isinstance(value, str) and value in field.values:
            return None
        return Refusal("STAGE_VALUE", path)
    if field.kind == "boolean":
        if type(value) is not bool:
            return Refusal("STAGE_VALUE", path)
        if field.const is not None and value is not field.const:
            return Refusal("STAGE_VALUE", path)
        return None
    if field.kind in {"identifier_list", "area_ids"}:
        return _identifiers(value, field.minimum, field.maximum, path)
    if field.kind == "fact_id":
        found = _lookup_returned_fact(value, path, facts, "STAGE_VALUE")
        if isinstance(found, Refusal):
            return found
        bound, fact = found
        refusal = returned_fact_refusal(fact, bound, path)
        if refusal is not None:
            return refusal
        return _company_fact(fact, path)
    if field.kind == "target":
        return _target(value, path)
    return Refusal("STAGE_VALUE", path)


def _identifiers(
    value: object,
    minimum: int | None,
    maximum: int | None,
    path: str,
) -> Refusal | None:
    if not isinstance(value, list):
        return Refusal("STAGE_VALUE", path)
    if minimum is not None and len(value) < minimum:
        return Refusal("STAGE_VALUE", path)
    if maximum is not None and len(value) > maximum:
        return Refusal("STAGE_VALUE", path)
    for item in value:
        if not isinstance(item, str) or IDENTIFIER.fullmatch(item) is None:
            return Refusal("STAGE_VALUE", path)
    return None


def _target(value: object, path: str) -> Refusal | None:
    if not isinstance(value, dict):
        return Refusal("STAGE_VALUE", path)
    keys = frozenset(key for key in value if isinstance(key, str))
    if len(keys) != len(value):
        return Refusal("STAGE_VALUE", path)
    if keys not in _TARGET_SHAPES:
        extra = [
            key for key in value if isinstance(key, str) and key not in _TARGET_KEYS
        ]
        if extra:
            return Refusal("UNKNOWN_PROPERTY", f"{path}.{extra[0]}")
        return Refusal("STAGE_VALUE", path)
    if keys == frozenset({"lat", "lon"}):
        lat = value["lat"]
        lon = value["lon"]
        if not _coordinate(lat) or not _coordinate(lon):
            return Refusal("STAGE_VALUE", path)
        if lat < -90 or lat > 90:
            return Refusal("COORDINATE_RANGE", f"{path}.lat")
        if lon < -180 or lon > 180:
            return Refusal("COORDINATE_RANGE", f"{path}.lon")
        return None
    name = next(iter(keys))
    ident = value[name]
    if isinstance(ident, str) and IDENTIFIER.fullmatch(ident) is not None:
        return None
    return Refusal("STAGE_VALUE", f"{path}.{name}")


def _coordinate(value: object) -> bool:
    if type(value) not in {int, float}:
        return False
    if isinstance(value, float):
        return value == value and value not in {float("inf"), float("-inf")}
    return True


def _exact_keys(
    row: dict[object, object], required: frozenset[str], path: str
) -> Refusal | None:
    unknown = [key for key in row if key not in required]
    if unknown:
        shown = unknown[0] if isinstance(unknown[0], str) else "field"
        return Refusal("UNKNOWN_PROPERTY", f"{path}.{shown}")
    if set(row) != required:
        missing = sorted(required - {key for key in row if isinstance(key, str)})
        return Refusal("MISSING_PROPERTY", f"{path}.{missing[0]}")
    return None
