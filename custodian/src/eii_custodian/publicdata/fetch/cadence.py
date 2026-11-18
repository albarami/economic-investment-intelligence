"""Closed recorded schedules and offline UTC anniversary calculations."""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eii_custodian.publicdata.fetch.registry import Entry

from eii_custodian.publicdata.fetch.snapshots import utc

VALUES = frozenset(
    {"daily", "weekly", "monthly", "quarterly", "annual", "as_published", "none"}
)


FAMILIES = {
    "investment_pages": "daily",
    "registers": "weekly",
    "overture_release": "monthly",
    "tender_notices": "daily",
    "event_pages": "daily",
    "award_reports": "weekly",
    "incentive_windows": "daily",
    "gis_layers": "weekly",
    "supplier_credentials": "weekly",
    "register_snapshots": "monthly",
    "statistical_series": "as_published",
}
RECORDED_FAMILIES = {
    "events_visit_qatar": "event_pages",
    "events_qncc": "event_pages",
    "suppliers_tawteen": "supplier_credentials",
    "monaqasat_classified": "supplier_credentials",
    "awards_owner_scrape": "award_reports",
    "fdi_projects": "investment_pages",
    "investqa_pages": "investment_pages",
    "lic_active": "registers",
    "lic_cancelled": "registers",
    "lic_issued": "registers",
    "places_ovt": "overture_release",
    "bldg_ovt": "overture_release",
}


@dataclass(frozen=True)
class Cadence:
    value: str
    reason: str
    evidence: str
    family: str = ""


def parse_cadence(value: object, *, source_id: str | None = None) -> Cadence:
    """No frequency is inferred from a source's observation period or title."""
    if not isinstance(value, dict):
        raise ValueError("cadence_missing")
    if set(value) - {"value", "reason", "evidence", "family"}:
        raise ValueError("cadence_unknown")
    name = value.get("value")
    family = value.get("family", "")
    if not isinstance(family, str) or ("family" in value and family not in FAMILIES):
        raise ValueError("cadence_family_unknown")
    if family and name != FAMILIES[family]:
        raise ValueError("cadence_family_mismatch")
    if source_id is not None and family != RECORDED_FAMILIES.get(source_id, ""):
        raise ValueError("cadence_family_assignment")
    if not isinstance(name, str) or name not in VALUES:
        raise ValueError("cadence_unknown")
    reason, evidence = value.get("reason", ""), value.get("evidence", "")
    if not isinstance(reason, str) or not isinstance(evidence, str):
        raise ValueError("cadence_unknown")
    if name == "none":
        if not reason.strip():
            raise ValueError("cadence_reason_missing")
    elif reason or not evidence.strip():
        raise ValueError("cadence_frequency_unconfirmed")
    return Cadence(name, reason, evidence, family)


@dataclass(frozen=True)
class Due:
    status: str
    reason: str
    checked_at: datetime | None
    due_at: datetime | None


def due_source(
    rule: Cadence, checks: Sequence[str], *, clock: Callable[[], datetime]
) -> Due:
    """Equal-byte checks reset the anniversary; the caller supplies verified events."""
    now = clock()
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("clock_invalid")
    checked = max((utc(stamp) for stamp in checks), default=None)
    if rule.value == "none":
        return Due("excluded", rule.reason, checked, None)
    if rule.value == "as_published":
        return Due("publication_check_required", "", checked, None)
    if checked is None:
        return Due("due", "never_fetched", None, None)
    if rule.value == "daily":
        due = checked + timedelta(days=1)
    elif rule.value == "weekly":
        due = checked + timedelta(weeks=1)
    else:
        months = {"monthly": 1, "quarterly": 3, "annual": 12}[rule.value]
        year, month = divmod(checked.year * 12 + checked.month - 1 + months, 12)
        month += 1
        due = checked.replace(
            year=year, month=month, day=min(checked.day, monthrange(year, month)[1])
        )
    return Due("due" if now >= due else "not_due", "", checked, due)


def due_sources(
    rules: Mapping[str, Cadence],
    checks: Mapping[str, Sequence[str]],
    *,
    clock: Callable[[], datetime],
) -> dict[str, Due]:
    """Return a stable offline listing, including explicit exclusion reasons."""
    now = clock()
    return {
        key: due_source(rule, checks.get(key, ()), clock=lambda: now)
        for key, rule in sorted(rules.items())
    }


def due_registry(
    entries: Sequence[Entry], cache: Path, *, clock: Callable[[], datetime]
) -> dict[str, Due]:
    """Offline listing from registry schedules and verified archive check events."""
    from eii_custodian.publicdata.fetch.snapshots import checked_times

    return due_sources(
        {entry.key: entry.refetch for entry in entries},
        {entry.key: checked_times(cache / entry.key) for entry in entries},
        clock=clock,
    )
