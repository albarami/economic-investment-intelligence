"""AI-14: five independent checks on the complete, buffered template draft."""

from typing import Any

from eii_product.assistant.catalogue.brief import check_brief
from eii_product.assistant.catalogue.schema import Catalogue
from eii_product.assistant.playbooks.models import Bundle
from eii_product.assistant.playbooks.registry import Definition
from eii_product.assistant.templates.writer import Draft, cap_strength

CHECKS = ("Sources", "Assumptions", "Nothing invented", "Scope", "Limits stated")


def referenced(value: Any) -> set[str]:
    """Fact bindings anywhere in a structured item, including component props."""
    if isinstance(value, str):
        return {value} if value.startswith("f_") else set()
    if isinstance(value, dict):
        return set().union(*(referenced(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(referenced(item) for item in value))
    return set()


def account(
    draft: Draft, bundle: Bundle, definition: Definition, catalogue: Catalogue
) -> dict[str, bool]:
    facts = {key: item.returned() for key, item in bundle.facts.items()}
    used = referenced(draft.brief)
    # Every evidence card is also displayed evidence, even with the empty foundation claims.
    used.update(
        identity for card in bundle.cards for identity in card.get("fact_ids", [])
    )
    sources = all(
        key in bundle.facts and bundle.facts[key].valid(bundle.release_id)
        for key in used
    )
    assumptions = set(bundle.inputs) <= set(draft.assumptions)
    scope = draft.playbook == bundle.playbook == definition.name
    caveats = set(definition.caveat_keys)
    coverage: set[str] = set()
    companions: set[str] = set()
    selected = {
        item.get("claim_key")
        for section in ("observed", "inferred")
        for item in draft.brief.get(section, [])
        if isinstance(item, dict)
    }
    selected.update(
        item.get("component")
        for item in draft.brief.get("layout", [])
        if isinstance(item, dict)
    )
    for identity in used:
        evidence = bundle.facts.get(identity)
        if evidence is None:
            continue
        fact = evidence.fact
        caveats.update(fact.caveat_keys)
        coverage.update(fact.coverage_keys)
        if fact.evidence_status == "inferred" or "user_input" in fact.input_classes:
            assumptions &= identity in draft.assumptions
        # This Public-only playbook cannot attach generated figures to named subjects.
        scope &= fact.provenance == "public" and fact.input_classes == ["public"]
    for section in ("observed", "inferred"):
        items = draft.brief.get(section, [])
        if not isinstance(items, list):
            scope = False
            continue
        for item in items:
            if not isinstance(item, dict):
                scope = False
                continue
            claim = catalogue.find_claim(item.get("claim_key", ""))
            if claim is None:
                continue
            caveats.update(claim.required_caveat_keys)
            companions.update(claim.required_companions)
            classes = []
            for identity in referenced(item):
                evidence = bundle.facts.get(identity)
                if evidence is not None:
                    assumptions &= evidence.fact.evidence_status == section
                    classes.extend(evidence.fact.input_classes)
                    if claim.subject != "area":
                        scope &= evidence.fact.provenance == "public"
            if section == "inferred":
                strength = item.get("strength", "")
                assumptions &= strength == cap_strength(strength, classes)
    for question in draft.brief.get("next_questions", []):
        if isinstance(question, dict):
            entry = catalogue.find_question(question.get("question_key", ""))
            scope &= entry is not None and entry.playbook == definition.name
    valid = check_brief(catalogue, draft.brief, facts) is None
    limits = (
        caveats == set(draft.caveat_keys)
        and coverage == set(draft.coverage_keys)
        and companions <= selected
        and draft.still_to_test == definition.still_to_test
        and draft.not_measured == definition.not_measured
    )
    return dict(zip(CHECKS, (sources, assumptions, valid, scope, limits), strict=True))
