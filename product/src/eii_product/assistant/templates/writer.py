"""Compose the playbook's default selection using the catalogue's fact slots."""

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from eii_product.assistant.catalogue.schema import Catalogue
from eii_product.assistant.playbooks.models import Bundle
from eii_product.assistant.playbooks.registry import Definition


@dataclass
class Draft:
    brief: dict[str, Any]
    playbook: str
    assumptions: list[str]
    caveat_keys: list[str]
    coverage_keys: list[str]
    still_to_test: list[str]
    not_measured: list[str]

    def wire(self) -> dict[str, Any]:
        return {
            **self.brief,
            "assumptions": self.assumptions,
            "caveat_keys": self.caveat_keys,
            "coverage_keys": self.coverage_keys,
            "still_to_test": self.still_to_test,
            "not_measured": self.not_measured,
        }


def cap_strength(requested: str, classes: Sequence[str]) -> str:
    """AI-31: cap by the least-real input, independently of evidence status."""
    if "simulated" in classes:
        return "illustrative"
    if "synthetic" in classes and requested == "strong":
        return "indicative"
    return requested


def compose(bundle: Bundle, definition: Definition, catalogue: Catalogue) -> Draft:
    observed: list[dict[str, Any]] = []
    inferred: list[dict[str, Any]] = []
    caveats = list(definition.caveat_keys)
    coverage: list[str] = []
    assumptions = list(bundle.inputs)
    for evidence in bundle.facts.values():
        caveats.extend(evidence.fact.caveat_keys)
        coverage.extend(evidence.fact.coverage_keys)
        if (
            evidence.fact.evidence_status == "inferred"
            or "user_input" in evidence.fact.input_classes
        ):
            assumptions.append(evidence.fact.fact_id)
    for selection in definition.claims:
        claim = catalogue.find_claim(selection.claim_key)
        if claim is None:
            raise ValueError("unknown_claim")
        bound = [bundle.facts[identity].fact for identity in selection.slots.values()]
        statuses = {fact.evidence_status for fact in bound}
        item: dict[str, Any] = {"claim_key": claim.key, "slots": dict(selection.slots)}
        if statuses == {"observed"}:
            observed.append(item)
        elif statuses == {"inferred"}:
            item["strength"] = cap_strength(
                selection.strength,
                [value for fact in bound for value in fact.input_classes],
            )
            inferred.append(item)
        else:
            raise ValueError("evidence_status_mismatch")
        caveats.extend(claim.required_caveat_keys)
    brief = dict(
        catalogue_version=catalogue.version,
        headline_key=definition.headline_key,
        decision_template_key=definition.decision_template_key,
        observed=observed,
        inferred=inferred,
        still_to_test=[],
        not_measured=[],
        next_questions=[
            {"question_key": key, "slots": {}} for key in definition.questions
        ],
        layout=deepcopy(definition.layout),
        stage=[
            {
                "component": value["directive"],
                "props": {k: v for k, v in value.items() if k != "directive"},
            }
            for value in bundle.stage
        ],
    )
    return Draft(
        brief,
        bundle.playbook,
        list(dict.fromkeys(assumptions)),
        list(dict.fromkeys(caveats)),
        list(dict.fromkeys(coverage)),
        list(definition.still_to_test),
        list(definition.not_measured),
    )
