"""Internal OI-03 evidence and a fail-closed display gate (PUB-74 to PUB-77)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from eii_core.calc.public_series import Group, weighted_mean

R1_SOURCES = frozenset({"sec_hr_ind", "sec_hr_goods", "sec_hr_serv", "sec_hr_size"})
R2_SOURCES = frozenset({"wage_occ", "wage_act"})


@dataclass(frozen=True)
class Resolution:
    """Committed decision and separately recorded delegated sign-off note."""

    record: Path
    sign_off: Path
    sources: frozenset[str]

    def approved(self) -> bool:
        """An unsigned or missing decision cannot unblock a source."""
        if not self.record.is_file() or not self.sign_off.is_file():
            return False
        note = json.loads(self.sign_off.read_text(encoding="utf-8"))
        return bool(
            note.get("approved") is True
            and note.get("reviewer_role") == "owner-delegated advisor"
            and note.get("record") == self.record.name
            and note.get("record_sha256")
            == hashlib.sha256(self.record.read_bytes()).hexdigest()
            and set(note.get("sources", [])) == self.sources
        )


def closure_status(resolution: Resolution) -> str:
    """Return the registry disposition; the caller must record OI-03 closure."""
    if not resolution.approved():
        return "open"
    return f"resolved:{resolution.record.stem}"


def emit_fact(
    fact: dict[str, object],
    lineage: Sequence[str],
    registry: Mapping[str, str],
    resolutions: Sequence[Resolution],
    affected: frozenset[str] = R1_SOURCES | R2_SOURCES,
) -> dict[str, object] | None:
    """All transitive source dependencies must be supplied, never just a leaf."""
    if not lineage:
        return None
    for source in lineage:
        state = registry.get(source, "open")
        if state == "open":
            return None
        if source in affected or state.startswith("resolved:"):
            if not any(
                source in item.sources
                and item.approved()
                and state == closure_status(item)
                for item in resolutions
            ):
                return None
    return fact


@dataclass(frozen=True)
class RestaurantObservation:
    """A copied value and all four PUB-75 scope axes; no inferred scope."""

    source: str
    field: str
    value: Decimal
    activities: str
    measure: str
    year: str
    establishments: str


def restaurant_evidence(
    observations: Sequence[RestaurantObservation],
    production: RestaurantObservation,
    target: Decimal,
    searched: frozenset[str],
) -> dict[str, object]:
    """Record every magnitude match and all scope comparisons, without editing it."""
    if searched != R1_SOURCES:
        raise ValueError("R1 needs all hotels-and-restaurants tables")
    matches = []
    for row in observations:
        if row.source not in searched:
            raise ValueError("unrecorded R1 source")
        if row.value == target:
            matches.append(
                {
                    "source": row.source,
                    "field": row.field,
                    "value": str(row.value),
                    "activities": (production.activities, row.activities),
                    "measure": (production.measure, row.measure),
                    "year": (production.year, row.year),
                    "establishments": (production.establishments, row.establishments),
                }
            )
    return {
        "item": "R1",
        "sources": sorted(searched),
        "matches": matches,
        "status": "open",
        "proposed_table": "sec_hr_ind",
        "revenue_display": False,
    }


def wage_evidence(
    tables: Mapping[str, Mapping[str, Mapping[str, Group]]],
    reported_years: Sequence[str],
) -> dict[str, object]:
    """Both unrounded means and totals for every shared year, even when unequal."""
    if set(tables) != R2_SOURCES:
        raise ValueError("wrong wage table identities")
    shared = sorted(tables["wage_occ"].keys() & tables["wage_act"].keys())
    if list(reported_years) != shared or not shared:
        raise ValueError("incomplete shared years")
    rows = []
    equal_means = []
    for year in shared:
        n_occ, m_occ = weighted_mean(tables["wage_occ"][year])
        n_act, m_act = weighted_mean(tables["wage_act"][year])
        equal_means.append(m_occ == m_act)
        rows.append(
            {
                "year": year,
                "wage_occ_workers": str(n_occ),
                "wage_act_workers": str(n_act),
                "wage_occ_mean": str(m_occ),
                "wage_act_mean": str(m_act),
                "equal_workers": n_occ == n_act,
            }
        )
    return {
        "item": "R2",
        "sources": sorted(R2_SOURCES),
        "years": rows,
        "status": (
            "open: worker totals differ"
            if not all(row["equal_workers"] for row in rows)
            else "reconciled: means equal, occupation table used"
            if all(equal_means)
            else "reconciled: tables differ, occupation table used"
        ),
    }
