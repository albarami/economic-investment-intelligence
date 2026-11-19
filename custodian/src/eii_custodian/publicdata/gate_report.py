"""Pure gate evidence gatherer; only the lead records acceptance or closure.

Task-specific producers validate their loaded confirmations before handing over
the named checks below. Joined forecast/height/additions adapters are Part B;
this module neither imports their unmerged code nor assumes their file shapes.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import PurePosixPath

from eii_custodian.publicdata.completeness import in_use
from eii_custodian.publicdata.confirm_s2_t13 import Confirmation, completion_evidence
from eii_custodian.publicdata.fetch.registry import Entry
from eii_custodian.publicdata.places_fsq.constants import RELEASE_KEY, RELEASE_POLICY
from eii_custodian.publicdata.places_fsq.errors import PlacesFsqError
from eii_custodian.publicdata.places_fsq.releases import validate_release

CONFIRMATION_TASKS = ("S2-T12", "S2-T13", "S2-T15", "S2-T17", "S2-T19", "S2-T20")
INVESTMENT_FLAGS = (
    "inventory_recorded",
    "field_coverage_recorded",
    "fixture_comparison_recorded",
    "live_page_compared",
)
CONFIRMATION_CHECKS = {
    "S2-T12": frozenset(
        key + ":" + flag
        for key in ("fdi_projects", "investqa_pages")
        for flag in INVESTMENT_FLAGS
    )
    | {"investqa_pages:arabic_evidence"},
    "S2-T13": frozenset({"completion_evidence"}),
    "S2-T15": frozenset({"release_matches"}),
    "S2-T17": frozenset({"series_validated", "record_present"}),
    "S2-T19": frozenset({"confirmed"}),
    "S2-T20": frozenset(
        {
            "storey_height_recorded",
            "fallback_errors_recorded",
            "asset_manifest_recorded",
            "rules_recorded",
        }
    ),
}


def coverage_geography(
    entries: Sequence[Entry],
    receipts: Mapping[str, Mapping[str, object]],
    share_columns: set[str] | frozenset[str],
) -> dict[str, str]:
    """PUB-82/MTH-39 order; caller passes the frame's existing share columns.

    A nonempty total/private column contract is required for a zone. District
    population cannot supply a private-employer share and never wins this order.
    Terms have no bearing on the geography selection.
    """
    used = {row.source_id: row for row in entries if in_use(row, receipts)}
    zone = used.get("census_zone_sector")
    if (
        zone is not None
        and share_columns
        and share_columns <= dict(zone.columns).keys()
    ):
        return {"geography": "ZONE", "row": zone.key, "reason": ""}
    municipality = used.get("pop_muni")
    if municipality is not None:
        return {
            "geography": "MUNICIPALITY",
            "row": municipality.key,
            "reason": "zone_row_absent"
            if zone is None
            else "zone_row_without_share_columns",
        }
    return {"geography": "NATIONAL", "row": "", "reason": "municipality_row_absent"}


def load_dispositions(raw: bytes) -> dict[str, object]:
    """Read the dispositions file; anything but a JSON object holds no entry.

    B14: bytes that are not UTF-8, text that is not JSON and JSON that is not
    an object all leave every disposition pending; no exception escapes.
    """
    try:
        loaded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _disposition_state(entry: object) -> str:
    """A recorded status is a text that is not empty once white space is removed."""
    if not isinstance(entry, Mapping):
        return "pending"
    status = entry.get("status")
    if not isinstance(status, str) or not status.strip():
        return "pending"
    return status


def oi03_line(
    *,
    entries: Sequence[Entry],
    decision: bytes,
    decision_name: str,
    signoff: Mapping[str, object],
    sources: frozenset[str],
    open_item_type: str,
    dispositions: Mapping[str, object],
) -> dict[str, object]:
    """Gather accepted decision, bound sign-off, registry rows and dispositions.

    Inputs are loaded evidence, never guessed from narrative words. Binding
    mirrors series.reconcile.Resolution's owner-delegated sign-off contract.
    The existing series producer's closed/reconciled dispositions are retained
    verbatim; an open or unknown disposition stays pending.
    """
    try:
        text = decision.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    match = re.search(r"^\| Status \| ([^|]+) \|$", text, re.M)
    status = match.group(1).strip() if match else "not recorded"
    binding = "resolved:" + PurePosixPath(decision_name).stem
    signed_sources = signoff.get("sources")
    bound = (
        signoff.get("approved") is True
        and signoff.get("reviewer_role") == "owner-delegated advisor"
        and signoff.get("record") == decision_name
        and signoff.get("record_sha256") == hashlib.sha256(decision).hexdigest()
        and isinstance(signed_sources, list)
        and all(isinstance(source, str) for source in signed_sources)
        and set(signed_sources) == sources
        and bool(sources)
    )
    open_rows = sorted(row.key for row in entries if row.reconciliation == "open")
    affected_rows = [row for row in entries if row.source_id in sources]
    resolved = {row.source_id for row in affected_rows} == sources and all(
        row.reconciliation == binding for row in affected_rows
    )
    states = {key: _disposition_state(dispositions.get(key)) for key in ("R1", "R2")}
    dispositions_resolved = states["R1"] == "closed: not published" and states[
        "R2"
    ] in (
        "reconciled: means equal, occupation table used",
        "reconciled: tables differ, occupation table used",
    )
    recorded = (
        (status == "Accepted" or status.startswith("Accepted,"))
        and bound
        and resolved
        and not open_rows
        and open_item_type == "CLOSED"
        and dispositions_resolved
    )
    return {
        "id": "OI-03",
        "state": "recorded" if recorded else "pending",
        "decision_status": status,
        "open_item_state": open_item_type,
        "open_rows": open_rows,
        "binding": binding if bound else "open",
        "dispositions": states,
    }


def display_allowed(
    lineage: Sequence[str],
    registry: Mapping[str, str],
    oi03: Mapping[str, object],
    affected: frozenset[str],
) -> bool:
    """Refuse facts with any open transitive dependency (PUB-74 through PUB-77).

    Assembly must provide the complete transitive lineage, not only a leaf.
    This gate is additional to the existing series emit_fact boundary.
    """
    if not lineage:
        return False
    for source in lineage:
        state = registry.get(source, "open")
        if state == "open":
            return False
        if source in affected or state.startswith("resolved:"):
            if (
                source not in affected
                or oi03.get("state") != "recorded"
                or state != oi03.get("binding")
            ):
                return False
    return True


@dataclass(frozen=True)
class ConfirmationEvidence:
    """Producer-validated checks and references, never a human-approval claim.

    References name the source-owner's confirmation/rules/manifest records;
    source_keys bind them to fetched receipts. Open-series entries survive
    gathering. Numerical height constants/errors remain in those references.
    """

    task: str
    source_keys: tuple[str, ...]
    references: tuple[str, ...]
    checks: Mapping[str, bool]
    open_entries: tuple[str, ...] = ()
    receipt_sha256: Mapping[str, str] = field(default_factory=dict)
    absence_reasons: Mapping[str, str] = field(default_factory=dict)


def confirmations(
    evidence: Sequence[ConfirmationEvidence],
    entries: Sequence[Entry],
    receipts: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    """List all six tasks; pending or mismatched inputs can never disappear."""
    if any(item.task not in CONFIRMATION_TASKS for item in evidence):
        raise ValueError("confirmation_task_unknown")
    if len({item.task for item in evidence}) != len(evidence):
        raise ValueError("confirmation_task_duplicate")
    by_task = {item.task: item for item in evidence}
    rows = {row.key: row for row in entries}
    result: list[dict[str, object]] = []
    for task in CONFIRMATION_TASKS:
        item = by_task.get(task)
        recorded = bool(
            item
            and item.source_keys
            and item.references
            and all(ref.strip() for ref in item.references)
            and set(item.checks) == CONFIRMATION_CHECKS[task]
            and all(check is True for check in item.checks.values())
            and all(
                key in rows
                and (
                    (
                        in_use(rows[key], receipts)
                        and item.receipt_sha256.get(key) == receipts[key].get("sha256")
                        and key not in item.absence_reasons
                    )
                    or (
                        bool(rows[key].skip_reason)
                        and item.absence_reasons.get(key) == rows[key].skip_reason
                        and key not in receipts
                    )
                )
                for key in item.source_keys
            )
        )
        result.append(
            {
                "task": task,
                "state": "recorded" if recorded else "pending",
                "reason": "" if recorded else "confirmation_pending",
                "references": list(item.references) if item else [],
                "open_entries": list(item.open_entries) if item else [],
                "absences": dict(item.absence_reasons) if item else {},
            }
        )
    return result


def tender_evidence(
    confirmation: Confirmation,
    row: Entry | None,
    receipt: Mapping[str, object] | None,
    reference: str,
) -> ConfirmationEvidence:
    """Reuse S2-T13's existing validation instead of duplicating its loader."""
    try:
        completion_evidence(confirmation, row, receipt)
    except ValueError:
        confirmed = False
    else:
        confirmed = True
    return ConfirmationEvidence(
        "S2-T13",
        (row.key,) if row else (),
        (reference,),
        {"completion_evidence": confirmed},
        receipt_sha256={row.key: str(receipt["sha256"])}
        if row and receipt and "sha256" in receipt
        else {},
        absence_reasons={row.key: row.skip_reason}
        if row and row.skip_reason and confirmed
        else {},
    )


def investment_evidence(
    document: Mapping[str, object], reference: str
) -> ConfirmationEvidence:
    """Read the existing investment_pages.yaml confirmation blocks (S2-T12)."""
    keys = ("fdi_projects", "investqa_pages")
    checks: dict[str, bool] = {}
    sources = document.get("sources")
    for key in keys:
        source = sources.get(key) if isinstance(sources, dict) else None
        block = source.get("confirmation") if isinstance(source, dict) else None
        for flag in INVESTMENT_FLAGS:
            checks[key + ":" + flag] = (
                isinstance(block, dict) and block.get(flag) is True
            )
    agency = sources.get("investqa_pages") if isinstance(sources, dict) else None
    checks["investqa_pages:arabic_evidence"] = _arabic_evidence(agency)
    return ConfirmationEvidence("S2-T12", keys, (reference,), checks)


def _arabic_evidence(agency: object) -> bool:
    """English confirmation never establishes an Arabic inventory or reading."""
    if not isinstance(agency, dict):
        return False
    confirmations = agency.get("language_confirmation")
    arabic = confirmations.get("ar") if isinstance(confirmations, dict) else None
    pages = agency.get("pages")
    if not isinstance(arabic, dict) or not isinstance(pages, list):
        return False
    try:
        if (
            not isinstance(arabic.get("read_on"), str)
            or date.fromisoformat(arabic["read_on"]).isoformat() != arabic["read_on"]
        ):
            return False
    except ValueError:
        return False
    kinds = {
        page.get("kind")
        for page in pages
        if isinstance(page, dict)
        and page.get("language") == "ar"
        and isinstance(page.get("kind"), str)
    }
    return (
        kinds >= {"sector", "opportunity", "incentive", "setup", "law"}
        and all(arabic.get(flag) is True for flag in INVESTMENT_FLAGS)
        and isinstance(arabic.get("reference"), str)
        and bool(arabic["reference"].strip())
    )


def fsq_evidence(
    registry_release: str,
    policy: Mapping[str, object],
    reference: str,
    receipt_release: str,
) -> ConfirmationEvidence:
    """Require one actual dated release in runtime evidence and its receipt."""
    try:
        validate_release(registry_release)
        validate_release(receipt_release)
    except PlacesFsqError:
        matches = False
    else:
        matches = (
            registry_release == receipt_release
            and policy.get("release") == RELEASE_POLICY
        )
    return ConfirmationEvidence(
        "S2-T15",
        (RELEASE_KEY,),
        (reference,),
        {"release_matches": matches},
    )


def terms_evidence(
    entries: Sequence[Entry], own_words_confirmed: frozenset[str] = frozenset()
) -> list[dict[str, str]]:
    """Preserve wording/dated markers; P6 never completes own-words review.

    The caller supplies separately confirmed keys from the source-owner review.
    Nothing here changes source admission or infers a live reading from text.
    """
    return [
        {
            "id": row.key,
            "terms_words": row.terms_words,
            "terms_read_on": row.terms_read_on,
            "licence_basis": row.licence_basis,
            "decision_record": row.decision_record,
            "own_words_state": "recorded"
            if row.key in own_words_confirmed
            else "pending",
        }
        for row in entries
    ]
