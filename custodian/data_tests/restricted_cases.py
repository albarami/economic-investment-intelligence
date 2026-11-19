"""PYTEST_DONT_REWRITE — metadata only; never source names, rows or values.

Inventory anchors: S2-T22 task log, OI-195, OI-276 and document 04 section
2.2/PUB-71. C12's population source follows document 07, C12 "Research note".
Decision 0034 item 3's standing places are excluded.
"""

import re
from dataclasses import asdict, dataclass, fields

import yaml

from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame.layers import COUNTS
from eii_custodian.publicdata.stage import _LOCAL_FIELDS

from .cache import ROOT

HISTORICAL_REMOVALS = ("PROGRESS.md:S2-T22:What became of each finding:F2",)
VERSION = "S2-T35-v1"


@dataclass(frozen=True)
class Case:
    case_id: str
    record_anchor: str
    source_key: str
    source_ids: tuple[str, ...]
    selectors: tuple[str, ...]
    period: str
    geography: tuple[str, ...]
    units: str
    method: str
    version: str
    recipe: tuple[str, ...]
    status: str
    owner: str


CASES = (
    Case(
        "PUB-71",
        "docs/04_PUBLIC_DATA_PACK.md:PUB-71",
        "census_zone_sector",
        ("census_zone_sector", "census_zone_occ"),
        _LOCAL_FIELDS["PUB-71"],
        "2020",
        ("census_zone_sector",),
        "count_and_percent",
        "coverage_share",
        VERSION,
        ("layer_rows", "check_employment", "coverage_share", "rounded"),
        "ready",
        "S2-T35",
    ),
    Case(
        "C12-MTH-46",
        "docs/07_ECONOMIC_METHODS.md:MTH-46",
        "census_district_pop",
        ("census_district_pop",),
        ("POP2020",),
        "2020",
        ("census_district_pop",),
        "access_score",
        "reachable_access",
        VERSION,
        ("reachable_access",),
        "awaiting_routine",
        "S6-T13",
    ),
    Case(
        "H2",
        HISTORICAL_REMOVALS[0],
        "accident",
        ("accident",),
        ("accident_year", "accident_time", "total"),
        "unconfirmed",
        ("accident",),
        "count_and_share",
        "h2_hour_counts",
        VERSION,
        ("h2_hour_counts",),
        "awaiting_expectation",
        "S2-T35",
    ),
    *(
        Case(
            case_id,
            "OPEN_ITEMS.md:OI-276",
            "gis_boundaries",
            ("gis_boundaries",),
            (selector,),
            "unconfirmed",
            ("gis_boundaries",),
            "count",
            "boundary_finding_counts",
            VERSION,
            ("boundary_finding_counts",),
            "awaiting_expectation",
            "S2-T35",
        )
        for case_id, selector in (
            (
                "GIS-ZONES",
                "https://services.gisqatar.org.qa/server/rest/services/Vector/ZonesA/MapServer/0",
            ),
            (
                "GIS-MUNICIPALITIES",
                "https://services.gisqatar.org.qa/server/rest/services/Vector/MunicipalityA/MapServer/1",
            ),
            (
                "GIS-DISTRICTS",
                "https://services.gisqatar.org.qa/server/rest/services/Vector/DistrictsAr/MapServer/1",
            ),
        )
    ),
    *(
        Case(
            "COUNT-" + source,
            "docs/04_PUBLIC_DATA_PACK.md:2.2",
            source,
            (source,),
            (source,),
            "2020",
            (source,),
            "count",
            "layer_rows",
            VERSION,
            ("layer_rows", "row_count"),
            "ready",
            "S2-T35",
        )
        for source in (
            "census_zone_sector",
            "census_zone_occ",
            "census_zone_hh",
            "census_zone_lab",
            "census_district_pop",
            "bnd_zone_2020",
            "bnd_district_2020",
        )
    ),
)


def case_by_id(case_id):
    for case in CASES:
        if case.case_id == case_id:
            return case
    raise ValueError("unknown_case") from None


def outstanding():
    return {f"{case.case_id}:{case.status}" for case in CASES if case.status != "ready"}


def validate_inventory(cases, registry=None):
    """Closed metadata contract and L-1046's historical-removal predicate."""
    entries = load_registry() if registry is None else registry
    by_id = {entry.source_id: entry for entry in entries}
    identifiers = {entry.key for entry in entries}
    identifiers.update(name for entry in entries for name, _ in entry.columns)
    identifiers.update(COUNTS["census_district_pop"])
    identifiers.update(name for names in _LOCAL_FIELDS.values() for name in names)
    pointer = yaml.safe_load(
        (ROOT / "custodian/publicdata/review/s2_t29_sources.yaml").read_text()
    )["gis_confirmation"]
    identifiers.update(pointer["boundaries"])
    recipes = {
        "layer_rows",
        "check_employment",
        "coverage_share",
        "rounded",
        "reachable_access",
        "h2_hour_counts",
        "boundary_finding_counts",
        "row_count",
    }
    seen = set()
    keys = {field.name for field in fields(Case)}
    for case in cases:
        row = asdict(case) if isinstance(case, Case) else case
        if not isinstance(row, dict) or set(row) != keys:
            raise ValueError("inventory_shape") from None
        if row["status"] not in {"ready", "awaiting_routine", "awaiting_expectation"}:
            raise ValueError("inventory_status") from None
        if not row["owner"] or not re.fullmatch(r"S\d+-T\d+", row["owner"]):
            raise ValueError("inventory_owner") from None
        if row["case_id"] in seen or row["case_id"] not in {c.case_id for c in CASES}:
            raise ValueError("inventory_identity") from None
        seen.add(row["case_id"])
        if not row["source_ids"] or row["source_key"] not in row["source_ids"]:
            raise ValueError("inventory_source") from None
        for source in row["source_ids"]:
            if source not in by_id:
                raise ValueError("inventory_source") from None
            if (
                by_id[source].licence_basis == "dataset"
                and row["record_anchor"] not in HISTORICAL_REMOVALS
            ):
                raise ValueError("inventory_basis") from None
        for field in ("selectors", "geography"):
            if not row[field] or any(value not in identifiers for value in row[field]):
                raise ValueError("inventory_identifier") from None
        if not row["recipe"] or any(value not in recipes for value in row["recipe"]):
            raise ValueError("inventory_recipe") from None
        if row["version"] != VERSION or not row["record_anchor"] or not row["method"]:
            raise ValueError("inventory_metadata") from None
