"""Unaltered census values, source-specific tables and closed count units."""

from decimal import Decimal, InvalidOperation
from typing import Any

from eii_custodian.publicdata.fetch.registry import Entry

from .checks import FrameError, safe_key

UNITS = {
    "residents": "persons",
    "households": "households",
    "establishments": "establishments",
    "employees": "persons",
}
# UNITS is the closed audit-count list of PUB-84 and DAT-128. A table-specific
# Public count below is loaded on its source's own geography but is no audit
# selector until a contract revision adds it (decision 0064 item 15, OI-170).
TABLE_UNITS = {("pub_population_municipality", "employed"): "persons"}
GEOGRAPHY = {
    "pub_population_municipality": "municipality_code",
    "pub_census_national": None,
    "pub_census_zone": "zone_code",
    "pub_census_district": "district_key",
}
SOURCES = {
    "pop_muni": "pub_population_municipality",
    "est_census": "pub_census_national",
    "census_2020_workbook": "pub_census_national",
    "census_zone_sector": "pub_census_zone",
    "census_zone_occ": "pub_census_zone",
    "census_zone_hh": "pub_census_zone",
    "census_zone_lab": "pub_census_zone",
    "census_district_pop": "pub_census_district",
}
# C8 is employed residents; est_census remains the separate establishment input.
C8_SOURCES = {"national": "census_2020_workbook", "zone": "census_zone_sector"}
BASE_FIELDS = {"period", "indicator", "value", "unit"}


def unit_for(table: str, indicator: str) -> str | None:
    """The closed unit of an indicator in a table, or None when it is not admitted."""
    if indicator in UNITS:
        return UNITS[indicator]
    return TABLE_UNITS.get((table, indicator))


def census_rows(
    entry: Entry, records: list[dict[str, Any]], retrieved: str, table: str
) -> tuple[list[dict[str, Any]], list[str]]:
    if (
        entry.skip_reason
        or table not in entry.release_tables
        or SOURCES.get(entry.source_id) != table
    ):
        raise FrameError(f"{entry.source_id}: invalid release source for {table}")
    if not retrieved:
        raise FrameError(f"{entry.source_id}: missing retrieval date")
    geography = GEOGRAPHY[table]
    fields = BASE_FIELDS | ({geography} if geography else set())
    rows = []
    ignored = set()
    for record in records:
        if not fields <= record.keys():
            raise FrameError(f"{entry.source_id}: missing census columns")
        extras = record.keys() - fields
        for field in extras:
            if table != "pub_census_zone" or type(record[field]) not in {
                int,
                float,
                Decimal,
            }:
                raise FrameError(f"{entry.source_id}: unexpected census column {field}")
            ignored.add(f"{entry.source_id}: not loaded: {field}")
        unit = unit_for(table, record["indicator"])
        if unit is None or unit != record["unit"]:
            raise FrameError(f"{entry.source_id}: invalid indicator/unit")
        if table == "pub_census_zone" and record["period"] != "2020":
            raise FrameError(f"{entry.source_id}: zone census period")
        try:
            value = Decimal(str(record["value"]))
        except InvalidOperation as exc:
            raise FrameError(f"{entry.source_id}: census value") from exc
        if not value.is_finite():
            raise FrameError(f"{entry.source_id}: census value")
        row = {key: record[key] for key in fields}
        if geography:
            safe_key(row[geography])
        row.update(value=value, source_id=entry.source_id)
        rows.append(row)
    return rows, sorted(ignored)


def validate_tables(
    tables: dict[str, list[dict[str, Any]]], known: dict[str, set[str]]
) -> None:
    for table, geography in GEOGRAPHY.items():
        if table not in tables:
            raise FrameError(f"{table}: missing table")
        fields = BASE_FIELDS | {"source_id"} | ({geography} if geography else set())
        seen = set()
        for row in tables[table]:
            if set(row) != fields:
                raise FrameError(f"{table}: census columns")
            key = (
                row[geography] if geography else None,
                row["period"],
                row["indicator"],
            )
            if key in seen:
                raise FrameError(f"{table}: duplicate census key")
            seen.add(key)
            if geography and row[geography] not in known[geography]:
                raise FrameError(f"{table}: unknown geography key")
