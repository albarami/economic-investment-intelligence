"""L-212 M1-M5: closed zone measures and their cross-source proof.

Source attributes and meanings: lead's service-description note, 2026-11-14.
Only complete counts are summed; a missing count never becomes zero.
"""

from typing import Any

from eii_custodian.publicdata.fetch.registry import Entry

from .checks import FrameError
from .layers import COUNTS

SECTOR = "census_zone_sector"
OCCUPATION = "census_zone_occ"
HOUSEHOLDS = "census_zone_hh"
EMPLOYMENT_CHECK = f"{SECTOR} / {OCCUPATION}: employment cross-check"


def check_employment(layers: dict[str, list[dict[str, Any]]]) -> None:
    if SECTOR not in layers and OCCUPATION not in layers:
        return
    if SECTOR not in layers or OCCUPATION not in layers:
        raise FrameError(f"{EMPLOYMENT_CHECK}: required source unavailable")
    sector = {row["ZONE_NO"]: row for row in layers[SECTOR]}
    occupations = {row["ZONE_NO"]: row for row in layers[OCCUPATION]}
    if set(sector) != set(occupations):
        raise FrameError(f"{EMPLOYMENT_CHECK}: zone sets differ")
    for zone, row in sector.items():
        total = row["Total_Economic_active___15"]
        counts = [occupations[zone][field] for field in COUNTS[OCCUPATION][1:-1]]
        if total is None:
            if any(value is not None for value in counts):
                raise FrameError(f"{EMPLOYMENT_CHECK}: null coverage differs: {zone}")
        elif any(value is None for value in counts) or sum(counts) != total:
            raise FrameError(f"{EMPLOYMENT_CHECK}: counts differ: {zone}")


def zone_measures(
    layers: dict[str, list[dict[str, Any]]], entries: dict[str, Entry]
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    check_employment(layers)
    staged: dict[str, list[dict[str, Any]]] = {}
    report = []
    for source, rows in layers.items():
        excluded = COUNTS[source]
        if source == SECTOR:
            excluded = excluded[1:]
        for field in excluded:
            if source == HOUSEHOLDS:
                reason = (
                    "nationality split not declared"
                    if "nationality" not in entries[source].public_splits
                    else "Public nationality split requires a release split schema; not loaded"
                )
            else:
                reason = "not_applicable; " + (
                    "people aged above 15; not residents"
                    if field == "Pop_Aged__above__15"
                    else "unit not stated"
                    if source == "census_zone_lab"
                    else "sector breakdown; not an audit count"
                    if source == SECTOR
                    else "occupation breakdown; not an audit count"
                )
            report.append(f"{source}: not loaded: {field}; {reason}")
        if source not in {SECTOR, HOUSEHOLDS}:
            continue
        staged[source] = []
        for row in rows:
            values = (
                [row["Total_Economic_active___15"]]
                if source == SECTOR
                else [row["Qatari"], row["Non_Qatari"]]
            )
            if any(value is None for value in values):
                continue
            staged[source].append(
                {
                    "zone_code": str(row["ZONE_NO"]),
                    "period": "2020",
                    "indicator": "employees" if source == SECTOR else "households",
                    "value": sum(values),
                    "unit": "persons" if source == SECTOR else "households",
                }
            )
    return staged, report
