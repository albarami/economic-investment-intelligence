"""The reviewed use mapping of PUB-107 for the two sales bulletins.

Property type and use are read from the Arabic label and the usage field only;
the English label is unreliable and is never read. Each committed row of
``custodian/publicdata/review/property_use_map.csv`` maps one
(source id, Arabic label, usage value) pair to a reviewed ``use_key`` and a
marker: ``land`` for land without a building, otherwise a published unit-type
key of ``prop_resi_units``. An unmapped label or usage fails the build.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from eii_custodian.publicdata.additions.common import (
    AdditionError,
    parse_period_value,
)
from eii_custodian.publicdata.frame.crosswalk import read_csv

LAND_MARKER = "land"
ANY_USAGE = "*"
UNIT_TYPES = frozenset({"residential_unit"})
SOURCE_IDS = frozenset({"prop_sales", "prop_resi_units"})
USE_MAP_COLUMNS = (
    "source_id",
    "arabic_label",
    "usage_value",
    "use_key",
    "marker",
    "reviewer",
    "reviewed_on",
)


@dataclass(frozen=True)
class UseMapping:
    """One reviewed row: a label and usage to a use key and a deal marker."""

    source_id: str
    arabic_label: str
    usage_value: str
    use_key: str
    marker: str
    reviewer: str
    reviewed_on: str

    @property
    def land(self) -> bool:
        return self.marker == LAND_MARKER

    @property
    def unit_type(self) -> str | None:
        return None if self.land else self.marker


def load_use_map(path: Path) -> tuple[UseMapping, ...]:
    """Read the committed mapping and refuse a row outside its contract."""
    rows = read_csv(path)
    seen: dict[tuple[str, str, str], UseMapping] = {}
    result: list[UseMapping] = []
    for row in rows:
        if set(row) != set(USE_MAP_COLUMNS):
            raise AdditionError("use_map_columns")
        fields = {name: row[name] for name in USE_MAP_COLUMNS}
        if any(
            not isinstance(value, str) or value.strip() == ""
            for value in fields.values()
        ):
            raise AdditionError("use_map_field_empty")
        if fields["source_id"] not in SOURCE_IDS:
            raise AdditionError("use_map_source")
        if fields["marker"] != LAND_MARKER and fields["marker"] not in UNIT_TYPES:
            raise AdditionError("unknown_unit_type")
        parse_period_value(fields["reviewed_on"], "date")
        mapping = UseMapping(**fields)
        pair = (mapping.source_id, mapping.arabic_label, mapping.usage_value)
        if pair in seen:
            raise AdditionError("use_map_conflict")
        seen[pair] = mapping
        result.append(mapping)
    return tuple(result)


def use_lookup(
    mappings: Iterable[UseMapping], source_id: str, arabic_label: str, usage: str
) -> UseMapping:
    """Return the one reviewed row for a bulletin, label and usage.

    The source id is part of the lookup key (J29(d)): a label reviewed for
    one bulletin never matches a row of the other.
    """
    if source_id not in SOURCE_IDS:
        raise AdditionError("use_map_source")
    scoped = [row for row in mappings if row.source_id == source_id]
    matches = [
        row
        for row in scoped
        if row.arabic_label == arabic_label
        and (row.usage_value == ANY_USAGE or row.usage_value == usage)
    ]
    if len(matches) > 1:
        raise AdditionError("use_map_ambiguous")
    if matches:
        return matches[0]
    if any(row.arabic_label == arabic_label for row in scoped):
        raise AdditionError("unmapped_usage")
    raise AdditionError("unmapped_label")
