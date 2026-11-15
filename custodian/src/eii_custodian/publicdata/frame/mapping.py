"""Confirmed cache shapes from the lead's field-only inventory, 2026-11-14.

Nested ArcGIS names are confirmed by the lead's L-202 structure note.
POP_MAPPING records the population field mapping; municipality requires the reviewed
name crosswalk. Indicators load only through the reviewed indicator mapping.
Neither a translation nor a spelling correspondence is inferred from cached values.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .census import UNITS
from .checks import FrameError

POP_MAPPING = {
    "year": ("pub_population_municipality", "period"),
    "municipality": ("pub_population_municipality", "municipality_code"),
    "indicator": ("pub_population_municipality", "indicator"),
    "count": ("pub_population_municipality", "value"),
}
POP_FIELDS = {
    "year": str,
    "municipality": str,
    "lbldy": str,
    "indicator": str,
    "lmw_shr": str,
    "count": int,
}
UTILITY_FIELDS = {"year": str, "zone_number": str, "value": int}
GEOB_FIELDS = dict.fromkeys(
    (
        "boundaryID",
        "boundaryName",
        "boundaryISO",
        "boundaryYearRepresented",
        "boundaryType",
        "boundaryCanonical",
        "boundarySource",
        "boundaryLicense",
        "licenseDetail",
        "licenseSource",
        "boundarySourceURL",
        "sourceDataUpdateDate",
        "buildDate",
        "Continent",
        "UNSDG-region",
        "UNSDG-subregion",
        "worldBankIncomeGroup",
        "admUnitCount",
        "meanVertices",
        "minVertices",
        "maxVertices",
        "meanPerimeterLengthKM",
        "minPerimeterLengthKM",
        "maxPerimeterLengthKM",
        "meanAreaSqKM",
        "minAreaSqKM",
        "maxAreaSqKM",
        "staticDownloadLink",
        "gjDownloadURL",
        "tjDownloadURL",
        "imagePreview",
        "simplifiedGeometryGeoJSON",
    ),
    str,
)
LAYER_MISSING = {
    "bnd_zone_2020": "zone_code, geometry encoding and coordinate reference system",
    "bnd_district_2020": "district_key, geometry encoding and coordinate reference system",
    "census_zone_hh": "zone_code, period, indicator, value, unit",
    "census_zone_occ": "zone_code, period, indicator, value, unit",
    "census_zone_lab": "zone_code, period, indicator, value, unit",
    "census_zone_sector": "zone_code, period, indicator, value, unit",
    "census_district_pop": "district_key, period, indicator, value, unit",
}
CONFIRMED_SOURCES = frozenset(
    {"pop_muni", "est_census", "util_elec", "util_water", "bnd_geob", *LAYER_MISSING}
)


@dataclass(frozen=True)
class Inspection:
    rows: list[dict[str, Any]]
    inventory: dict[str, tuple[str, ...]]
    reason: str


def fields(row: Any, expected: Mapping[str, type], source: str) -> None:
    if not isinstance(row, dict):
        raise FrameError(f"{source}: expected object")
    missing, unknown = expected.keys() - row.keys(), row.keys() - expected.keys()
    if missing or unknown:
        raise FrameError(
            f"{source}: missing fields {sorted(missing)}; unknown fields {sorted(unknown)}"
        )
    for name, kind in expected.items():
        if type(row[name]) is not kind:
            raise FrameError(f"{source}: field {name} must be {kind.__name__}")


def inspect_source(
    source: str, payload: Any, indicators: dict[str, str] | None = None
) -> Inspection:
    if source == "est_census":
        from .establishments import establishment_rows

        return Inspection(establishment_rows(payload), {}, "")
    if source in LAYER_MISSING:
        from .layers import layer_rows

        rows = layer_rows(source, payload)
        inventory = {
            field: tuple(sorted({str(row[field]) for row in rows}))
            for field in {field for row in rows for field in row}
        }
        return Inspection(
            rows,
            inventory,
            "map_geometry_not_used: coordinate system absent from cache",
        )
    schemas: dict[str, Mapping[str, type]] = {
        "pop_muni": POP_FIELDS,
        "util_elec": UTILITY_FIELDS,
        "util_water": UTILITY_FIELDS,
        "bnd_geob": GEOB_FIELDS,
    }
    if source not in schemas:
        raise FrameError(f"{source}: no confirmed cache shape")
    if not isinstance(payload, list):
        raise FrameError(f"{source}: expected list")
    for row in payload:
        fields(row, schemas[source], source)
    if source == "bnd_geob":
        return Inspection(
            [],
            {},
            "metadata_only: missing zone tokens and geometry; download links are not geometry",
        )
    if source in {"util_elec", "util_water"}:
        return Inspection(
            [],
            {"zone_number": tuple(sorted({r["zone_number"] for r in payload}))},
            "inventory_only: utility figures belong to S2-T03",
        )
    inventory = {
        field: tuple(sorted({r[field] for r in payload}))
        for field in ("municipality", "lbldy", "indicator", "lmw_shr")
    }
    indicators = indicators if indicators is not None else {}
    unknown = set(inventory["indicator"]) - indicators.keys()
    if unknown:
        return Inspection(
            [], inventory, "unreviewed_indicator: " + ", ".join(sorted(unknown))
        )
    rows = []
    omitted = [r for r in payload if not indicators[r["indicator"]]]
    for record in payload:
        if not indicators[record["indicator"]]:
            continue
        row = {column: record[field] for field, (_, column) in POP_MAPPING.items()}
        row["municipality_name"] = row.pop("municipality_code")
        row["indicator"] = indicators[record["indicator"]]
        row["unit"] = UNITS[row["indicator"]]
        rows.append(row)
    reason = ""
    if omitted:
        reason = f"pop_muni: {len(omitted)} rows not loaded: " + ", ".join(
            sorted({r["indicator"] for r in omitted})
        )
    return Inspection(rows, inventory, reason)
