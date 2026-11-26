"""Design cooling capacity unpivoted onto the municipality name map.

``culture`` stays text. The other sector columns stay integers. Geometry columns
stay out of the release row. The indicator is capacity.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.crosswalk import municipality_key

_SECTORS = (
    "other",
    "industrial",
    "real_estate_development",
    "sport",
    "culture",
    "health",
    "transport",
    "education",
    "hotels",
    "commercial",
    "district_cooling_service_supply",
)
_TEXT_SECTOR = "culture"
_FIELDS = (
    "year",
    "project_status",
    "municipality",
    *_SECTORS,
    "lbldy",
    "hl_lmshry",
    "geo_point",
    "geo_shape",
)
_DIGITS = re.compile(r"\A[0-9]+\Z")
_INDICATOR = "capacity"
_UNIT = "TR"


class CoolingError(Exception):
    """The capacity table is not the published shape. Nothing is returned."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class CoolingRow:
    """One pub_district_cooling row on the source's own geography."""

    municipality_code: str
    sector_key: str
    period: str
    indicator: str
    value: Decimal
    unit: str


def parse_dcool(
    rows: Sequence[Mapping[str, object]],
    names: Sequence[Mapping[str, str]],
) -> tuple[CoolingRow, ...]:
    """Unpivot sector columns through the reviewed municipality names."""
    built: list[CoolingRow] = []
    seen: set[tuple[str, str, str]] = set()
    name_rows = [dict(row) for row in names]
    for row in rows:
        if any("consumption" in key for key in row):
            raise CoolingError("consumption")
        if set(row) != set(_FIELDS):
            raise CoolingError("unexpected_column")
        year = row["year"]
        municipality = row["municipality"]
        if not isinstance(year, str) or year.strip() == "":
            raise CoolingError("year")
        if not isinstance(municipality, str):
            raise CoolingError("unmapped_municipality")
        try:
            code = municipality_key(municipality, name_rows)
        except FrameError as exc:
            raise CoolingError("unmapped_municipality") from exc
        for sector in _SECTORS:
            if row[sector] is None:
                # R1: the portal leaves a sector cell empty when it publishes
                # no capacity; an empty cell is no row, never a zero.
                continue
            value = _sector_value(sector, row[sector])
            key = (code, sector, year.strip())
            if key in seen:
                raise CoolingError("duplicate_key")
            seen.add(key)
            built.append(
                CoolingRow(
                    municipality_code=code,
                    sector_key=sector,
                    period=year.strip(),
                    indicator=_INDICATOR,
                    value=value,
                    unit=_UNIT,
                )
            )
    return tuple(built)


def _sector_value(sector: str, raw: object) -> Decimal:
    if sector == _TEXT_SECTOR:
        if isinstance(raw, bool) or isinstance(raw, int) or not isinstance(raw, str):
            raise CoolingError("culture_type")
        if _DIGITS.fullmatch(raw.strip()) is None:
            raise CoolingError("culture_type")
        return Decimal(raw.strip())
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise CoolingError("sector_type")
    return Decimal(raw)
