"""Licensed frame geometry and exact comparison with validation layers."""

from dataclasses import dataclass
from typing import Any

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from .checks import FrameError, safe_key


@dataclass(frozen=True)
class Boundary:
    key: str
    name_en: str
    name_ar: str
    municipality_code: str
    geometry: BaseGeometry


def index(boundaries: list[Boundary]) -> dict[str, BaseGeometry]:
    result = {}
    for row in boundaries:
        key = safe_key(row.key)
        if key in result:
            raise FrameError("duplicate boundary key")
        result[key] = row.geometry
    return result


def parse_boundaries(rows: list[dict[str, Any]], level: str) -> list[Boundary]:
    """Read contract-named GeoJSON properties; unknown source schemas refuse."""
    key = {
        "municipality": "municipality_code",
        "zone": "zone_code",
        "district": "district_key",
    }[level]
    fields = {key, "name_en", "name_ar", "municipality_code", "geometry"}
    result = []
    for row in rows:
        if set(row) != fields:
            raise FrameError(f"{level}: geometry columns differ from contract")
        if not row["name_en"] or not row["name_ar"]:
            raise FrameError(f"{level}: bilingual name missing")
        result.append(
            Boundary(
                safe_key(row[key]),
                row["name_en"],
                row["name_ar"],
                row["municipality_code"],
                shape(row["geometry"]),
            )
        )
    index(result)
    return result


def release_rows(
    boundaries: list[Boundary], level: str, source_id: str
) -> list[dict[str, Any]]:
    expected = "bnd_muni_2025" if level == "municipality" else "bnd_hdx"
    if source_id != expected:
        raise FrameError(f"{level}: release source must be {expected}")
    key = {
        "municipality": "municipality_code",
        "zone": "zone_code",
        "district": "district_key",
    }[level]
    result = []
    for item in boundaries:
        row = {
            key: item.key,
            "name_en": item.name_en,
            "name_ar": item.name_ar,
            "geometry": item.geometry,
            "source_id": source_id,
        }
        if level != "municipality":
            row["municipality_code"] = item.municipality_code
        result.append(row)
    return result


def disagreements(
    licensed: list[Boundary], comparison: list[Boundary], level: str
) -> list[str]:
    other = index(comparison)
    result = []
    for row in licensed:
        if row.key not in other:
            result.append(f"{level} {row.key}: missing comparison")
        elif not row.geometry.equals(other[row.key]):
            result.append(f"{level} {row.key}: polygon disagreement")
    return result
