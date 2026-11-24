"""`pub_accident_zone`: accident context on source zones (S3-T12, decision 0047).

Pure release-build code. The caller supplies the records of the verified year
exports, the lead-reviewed measure confirmation and exact zone crosswalk, the
zone codes of the release's `zone` table and the selected snapshot's receipt
date. Nothing is fetched or read here, no geometry is made, and no street,
time, person, vehicle or coordinate field crosses (rule 10). An unconfirmed
`total` counts nothing, a zone without an exact reviewed match carries no
count, and an absent row never becomes zero (DAT-07).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass
from datetime import date

COVERAGE_KEYS = ("counted", "measure_unconfirmed", "geography_missing")
# The caveat of the registered source's NO_DATA coverage row (document 03).
SOURCE_MISSING_CAVEAT = "accident_source_missing"
_REQUIRED = frozenset({"accident_year", "zone", "total"})
_YEAR = re.compile(r"([1-9][0-9]{3})(?:-([0-9]{2})(?:-([0-9]{2}))?)?")
_INT64 = 2**63 - 1


class AccidentRefusal(ValueError):
    """A closed reason; the build stops rather than emit a doubtful row."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class AccidentReview:
    """Lead-reviewed facts the source metadata does not prove.

    `measure_confirmed`: `total` counts accidents and rows are disjoint.
    `crosswalk`: source `zone` number to `zone.zone_code`, exact identity only.
    """

    measure_confirmed: bool
    crosswalk: Mapping[int, str]


def _count_field(value: object, reason: str) -> int:
    if type(value) is not int or value < 0:
        raise AccidentRefusal(reason)
    return value


def _year(value: object) -> str:
    match = _YEAR.fullmatch(value) if type(value) is str else None
    if match is None:
        raise AccidentRefusal("accident_year_invalid")
    year, month, day = match.groups()
    try:
        if day is not None:
            date(int(year), int(month), int(day))
        elif month is not None:
            date(int(year), int(month), 1)
    except ValueError:
        raise AccidentRefusal("accident_year_invalid") from None
    return year


def _crosswalk(review: AccidentReview, zone_codes: Set[str]) -> Mapping[int, str]:
    targets = list(review.crosswalk.values())
    if any(code not in zone_codes for code in targets):
        raise AccidentRefusal("accident_crosswalk_invalid")
    if len(set(targets)) != len(targets):
        # Two source zones on one boundary would merge counts (no allocation).
        raise AccidentRefusal("accident_geography_allocation")
    return review.crosswalk


def accident_zone_rows(
    records: Iterable[object],
    review: AccidentReview,
    zone_codes: Set[str],
    columns: Set[str],
    source_id: str,
    as_of: str,
) -> list[dict[str, object]]:
    """One row per source zone and year, in key order."""
    if not source_id:
        raise AccidentRefusal("accident_source_invalid")
    try:
        retrieved = date.fromisoformat(as_of)
    except (TypeError, ValueError):
        raise AccidentRefusal("accident_as_of_invalid") from None
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", as_of) is None:
        raise AccidentRefusal("accident_as_of_invalid")
    crosswalk = _crosswalk(review, zone_codes)
    sums: dict[tuple[int, str], int] = {}
    for record in records:
        if not isinstance(record, dict):
            raise AccidentRefusal("accident_record_invalid")
        if not _REQUIRED <= set(record):
            raise AccidentRefusal("accident_field_missing")
        if not set(record) <= columns:
            raise AccidentRefusal("accident_field_unknown")
        zone = _count_field(record["zone"], "accident_zone_invalid")
        key = (zone, _year(record["accident_year"]))
        total = sums.get(key, 0) + _count_field(
            record["total"], "accident_total_invalid"
        )
        if total > _INT64:
            raise AccidentRefusal("accident_count_overflow")
        sums[key] = total
    if not sums:
        raise AccidentRefusal("accident_records_empty")
    rows: list[dict[str, object]] = []
    for (zone, period), total in sorted(sums.items()):
        code = crosswalk.get(zone)
        state = (
            "measure_unconfirmed"
            if not review.measure_confirmed
            else "counted"
            if code is not None
            else "geography_missing"
        )
        rows.append(
            {
                "source_zone": str(zone),
                "period": period,
                "zone_code": code,
                "accident_count": total if state == "counted" else None,
                "coverage_key": state,
                "as_of": retrieved,
                "source_id": source_id,
            }
        )
    return rows
