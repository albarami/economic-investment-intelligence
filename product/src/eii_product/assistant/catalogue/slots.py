"""Fact-to-slot match and the subject rules checked at load and at match."""

from __future__ import annotations

from collections.abc import Mapping

from eii_product.assistant.catalogue.schema import (
    BREAKDOWNS,
    ESTIMATE_SHARE_SCORE,
    EVIDENCE_STATUSES,
    FACT_ID,
    FACT_UNITS,
    GEOGRAPHY_KINDS,
    LINEAGE,
    METRIC_UNITS,
    MONEY_UNITS,
    PERIOD_PATTERNS,
    PROVENANCE_ALL,
    PUBLIC_BREAKDOWNS,
    SIMULATED_BREAKDOWNS,
    Catalogue,
    Refusal,
    ReturnedFact,
    Slot,
    join_path,
)

_SCENARIO_METRICS = frozenset({"scenario_low", "scenario_middle", "scenario_high"})
_TABULATED_SUBJECTS = frozenset({"municipality", "national", "sector"})
_GRID_SEX_METRIC = "population_grid_people"


def subject_refusal(
    subject: str,
    metric_key: str,
    unit: str,
    provenances: tuple[str, ...],
    *,
    metric_path: str,
    unit_path: str,
    provenance_path: str,
) -> Refusal | None:
    """Refuse a metric, unit or provenance the subject does not accept."""
    if metric_key == "employee_count" and subject != "register_company":
        return Refusal("SUBJECT_METRIC", metric_path)
    if subject != "area" and (
        metric_key in ESTIMATE_SHARE_SCORE or metric_key in _SCENARIO_METRICS
    ):
        return Refusal("SUBJECT_METRIC", metric_path)
    if subject == "register_company" and unit in MONEY_UNITS:
        return Refusal("SUBJECT_UNIT", unit_path)
    if subject == "area":
        return None
    if unit == "rank":
        return Refusal("SUBJECT_UNIT", unit_path)
    if "simulated" in provenances:
        return Refusal("SUBJECT_PROVENANCE", provenance_path)
    if "synthetic" in provenances:
        if subject == "register_company" and metric_key == "employee_count":
            return None
        if subject == "register_company":
            return Refusal("SUBJECT_METRIC", metric_path)
        return Refusal("SUBJECT_PROVENANCE", provenance_path)
    return None


def breakdown_refusal(
    subject: str,
    breakdown: str,
    provenances: tuple[str, ...],
    metric_key: str,
    path: str,
) -> Refusal | None:
    """Refuse a breakdown the subject, metric or provenance list does not allow."""
    if breakdown not in BREAKDOWNS:
        return Refusal("BREAKDOWN", path)
    if breakdown == "none":
        return None
    if breakdown in PUBLIC_BREAKDOWNS:
        if set(provenances) != {"public"}:
            return Refusal("BREAKDOWN", path)
        if subject in _TABULATED_SUBJECTS:
            return None
        if subject == "area" and breakdown == "sex" and metric_key == _GRID_SEX_METRIC:
            return None
        return Refusal("BREAKDOWN", path)
    if breakdown in SIMULATED_BREAKDOWNS and (
        subject != "area" or set(provenances) != {"simulated"}
    ):
        return Refusal("BREAKDOWN", path)
    return None


def mixed_breakdown_index(slots: tuple[Slot, ...]) -> int | None:
    """Index of a sex or nationality slot beside a synthetic or simulated slot."""
    split_at = [
        index for index, slot in enumerate(slots) if slot.breakdown in PUBLIC_BREAKDOWNS
    ]
    if not split_at:
        return None
    for index, slot in enumerate(slots):
        if index in split_at:
            continue
        provenances = set(slot.allowed_provenance)
        if "synthetic" in provenances or "simulated" in provenances:
            return split_at[0]
    return None


def match_slots(
    catalogue: Catalogue,
    claim_key: str,
    slots: Mapping[str, object],
    facts: Mapping[str, ReturnedFact],
    *,
    item_path: str = "",
) -> Refusal | None:
    """Match ordered claim slots to facts from this answer."""
    claim = catalogue.find_claim(claim_key)
    if claim is None:
        return Refusal("UNKNOWN_CLAIM", join_path(item_path, "claim_key"))
    return match_slot_list(
        claim.slots,
        slots,
        facts,
        subject=claim.subject,
        evidence=claim.section,
        item_path=item_path,
    )


def match_slot_list(
    defined: tuple[Slot, ...],
    slots: Mapping[str, object],
    facts: Mapping[str, ReturnedFact],
    *,
    subject: str | None,
    evidence: str | None,
    item_path: str,
) -> Refusal | None:
    """Match a slot list. A question passes no subject and no evidence section."""
    if not isinstance(slots, dict):
        return Refusal("BRIEF_TYPE", join_path(item_path, "slots"))
    defined_names = [slot.name for slot in defined]
    for name in defined_names:
        if name not in slots:
            return Refusal("SLOT_MISSING", join_path(item_path, f"slots.{name}"))
    for name in slots:
        if name not in defined_names:
            return Refusal("SLOT_EXTRA", join_path(item_path, f"slots.{name}"))
    seen_facts: set[str] = set()
    for name in defined_names:
        bound = slots[name]
        if isinstance(bound, str) and bound in seen_facts:
            return Refusal("SLOT_FACT_REUSED", join_path(item_path, f"slots.{name}"))
        if isinstance(bound, str):
            seen_facts.add(bound)
    by_name = {slot.name: slot for slot in defined}
    for name in defined_names:
        refusal = _match_one(
            by_name[name],
            slots[name],
            facts,
            subject=subject,
            evidence=evidence,
            path=join_path(item_path, f"slots.{name}"),
        )
        if refusal is not None:
            return refusal
    return None


def _match_one(
    slot: Slot,
    bound: object,
    facts: Mapping[str, ReturnedFact],
    *,
    subject: str | None,
    evidence: str | None,
    path: str,
) -> Refusal | None:
    if not isinstance(bound, str):
        return Refusal("UNKNOWN_FACT", path)
    fact = facts.get(bound)
    if fact is None:
        return Refusal("UNKNOWN_FACT", path)
    if not isinstance(fact, ReturnedFact):
        return Refusal("FACT_FIELD", path)
    refusal = returned_fact_refusal(fact, bound, path)
    if refusal is not None:
        return refusal
    if fact.metric_key != slot.metric_key:
        return Refusal("SLOT_METRIC", path)
    if fact.unit != slot.unit:
        return Refusal("SLOT_UNIT", path)
    if fact.geography_kind != slot.geography_role:
        return Refusal("SLOT_GEOGRAPHY", path)
    period = PERIOD_PATTERNS[slot.period_rule]
    if period.fullmatch(fact.period) is None:
        return Refusal("SLOT_PERIOD", path)
    if subject is not None:
        refusal = subject_refusal(
            subject,
            slot.metric_key,
            slot.unit,
            (fact.provenance,),
            metric_path=path,
            unit_path=path,
            provenance_path=path,
        )
        if refusal is not None:
            return refusal
        refusal = breakdown_refusal(
            subject, slot.breakdown, (fact.provenance,), slot.metric_key, path
        )
        if refusal is not None:
            return refusal
    if fact.breakdown != slot.breakdown:
        return Refusal("SLOT_BREAKDOWN", path)
    if fact.provenance not in slot.allowed_provenance:
        return Refusal("SLOT_PROVENANCE", path)
    if evidence == "observed" and fact.evidence_status != "observed":
        return Refusal("SLOT_EVIDENCE", path)
    if evidence == "inferred" and fact.evidence_status not in {"observed", "inferred"}:
        return Refusal("SLOT_EVIDENCE", path)
    return None


def returned_fact_refusal(fact: ReturnedFact, bound: str, path: str) -> Refusal | None:
    """Refuse a fact whose identifier, lineage, fields or suppression block use."""
    fact_id = fact.fact_id
    if (
        not isinstance(fact_id, str)
        or fact_id != bound
        or FACT_ID.fullmatch(fact_id) is None
    ):
        return Refusal("FACT_ID", f"{path}.fact_id")
    lineage_ref = fact.lineage_ref
    if not isinstance(lineage_ref, str) or LINEAGE.fullmatch(lineage_ref) is None:
        return Refusal("LINEAGE_REF", f"{path}.lineage_ref")
    field_refusal = _fact_fields(fact, path)
    if field_refusal is not None:
        return field_refusal
    if fact.provenance == "suppressed":
        return Refusal("SUPPRESSED_FACT", path)
    return None


def _fact_fields(fact: ReturnedFact, path: str) -> Refusal | None:
    if not isinstance(fact.unit, str) or fact.unit not in FACT_UNITS:
        return Refusal("FACT_FIELD", f"{path}.unit")
    if not isinstance(fact.provenance, str) or fact.provenance not in PROVENANCE_ALL:
        return Refusal("FACT_FIELD", f"{path}.provenance")
    if (
        not isinstance(fact.evidence_status, str)
        or fact.evidence_status not in EVIDENCE_STATUSES
    ):
        return Refusal("FACT_FIELD", f"{path}.evidence_status")
    if (
        not isinstance(fact.geography_kind, str)
        or fact.geography_kind not in GEOGRAPHY_KINDS
    ):
        return Refusal("FACT_FIELD", f"{path}.geography")
    if not isinstance(fact.metric_key, str) or fact.metric_key not in METRIC_UNITS:
        return Refusal("FACT_FIELD", f"{path}.metric_key")
    if not isinstance(fact.breakdown, str) or fact.breakdown not in BREAKDOWNS:
        return Refusal("FACT_FIELD", f"{path}.breakdown")
    if not isinstance(fact.period, str):
        return Refusal("FACT_FIELD", f"{path}.period")
    return None
