"""National canonical building inventory, inside the shared public frame build.

Decision 0077 (proposed), design findings F1-F8. No transport, cache selection,
footprint repair, numeric mapping or invented building attribute lives here.
"""

from __future__ import annotations

import math
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from shapely import point_on_surface
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from eii_core.calc.building_heights import height_value

from .building_inputs import (
    BUILDING_MANIFEST,
    BUILDING_METHOD,
    BUILDING_PARTS,
    FRAME_BOUNDS,
    BuildingError,
    boundary_review,
    bounds_polygon,
    dump,
    fingerprint,
    invalidate_buildings,
    national_guard,
    pinned,
)
from .fetch.receipts import sha256_hex
from .fetch.registry import Entry
from .heights.model import HeightError, load_buildings
from .places import PlacesError
from .places.read import (
    SOURCE_RELEASE,
    building_source_rows,
    decode_wkb,
    geometry_bounds,
)


def _field_counts() -> dict[str, Any]:
    return {
        "mapping": "off",
        "reason": "recorded_field_unconfirmed",
        "present": 0,
        "usable": 0,
        "unusable": 0,
        "absent": 0,
        "source_value_present_unmapped": 0,
    }


def _count_field(counts: dict[str, Any], value: object, whole: bool) -> None:
    if value is None:
        counts["absent"] += 1
        return
    counts["present"] += 1
    counts["source_value_present_unmapped"] += 1
    usable = (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and height_value(Decimal(str(value))) is not None
    )
    if usable and whole and isinstance(value, int | float):
        usable = value == int(value)
    counts["usable" if usable else "unusable"] += 1


def _geometry(value: object) -> BaseGeometry | None:
    if isinstance(value, memoryview):
        value = value.tobytes()
    if not isinstance(value, bytes):
        return None
    try:
        geometry = decode_wkb(value)
    except PlacesError:
        return None
    if (
        geometry.geom_type not in {"Polygon", "MultiPolygon"}
        or geometry.is_empty
        or not geometry.is_valid
    ):
        return None
    west, south, east, north = geometry_bounds(geometry)
    if not all(math.isfinite(item) for item in (west, south, east, north)) or not (
        -180 <= west <= east <= 180 and -90 <= south <= north <= 90
    ):
        raise BuildingError("building_axis_range")
    return geometry


def _contributors(sources: object, counts: Counter[str]) -> None:
    found: set[str] = set()
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, dict) or source.get("property") not in ("", None):
                continue
            dataset = source.get("dataset")
            if isinstance(dataset, str) and dataset.strip():
                found.add(dataset)
    for dataset in found or {"unconfirmed"}:
        counts[dataset] += 1


def build_buildings(
    cache: Path,
    entries: Sequence[Entry],
    selections: Mapping[str, str],
    boundary: BaseGeometry,
) -> dict[str, object]:
    """Build all fixed parts, refusing partial inputs; publish manifest last."""
    invalidate_buildings(cache)
    parts = {key: pinned(cache, entries, selections, key) for key in BUILDING_PARTS}
    boundary_snapshot = pinned(cache, entries, selections, "bnd_hdx")
    complete, chain = national_guard(cache, entries, selections, boundary)
    chain.update(
        {key: fingerprint(snapshot, selections[key]) for key, snapshot in parts.items()}
    )
    chain["bnd_hdx"] = fingerprint(boundary_snapshot, selections["bnd_hdx"])
    features: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    seen: set[str] = set()
    counts: Counter[str] = Counter(
        {
            key: 0
            for key in (
                "read",
                "kept",
                "outside_frame_box",
                "inside_box_outside_boundary",
                "invalid_footprint",
                "underground",
            )
        }
    )
    fields = {name: _field_counts() for name in ("height", "num_floors")}
    fields_all_read = {name: _field_counts() for name in ("height", "num_floors")}
    contributors: Counter[str] = Counter()
    part_counts: dict[str, Any] = {}
    frame = bounds_polygon(FRAME_BOUNDS)
    for key, snapshot in parts.items():
        local: Counter[str] = Counter({name: 0 for name in counts})
        kept: list[str] = []
        any_in_frame = False
        any_swapped = False
        try:
            for row in building_source_rows(snapshot.path):
                counts["read"] += 1
                local["read"] += 1
                building_id = row["id"]
                if not isinstance(building_id, str) or not building_id.strip():
                    raise BuildingError("building_id")
                if building_id in seen:
                    raise BuildingError("building_duplicate")
                seen.add(building_id)
                _count_field(fields_all_read["height"], row["height"], False)
                _count_field(fields_all_read["num_floors"], row["num_floors"], True)
                underground = row["is_underground"]
                if underground is not None and not isinstance(underground, bool):
                    raise BuildingError("building_underground_flag")
                geometry = _geometry(row["geometry"])
                reason = ""
                if geometry is None:
                    reason = "invalid_footprint"
                elif underground is True:
                    reason = "underground"
                if reason:
                    excluded.append(
                        {"building_id": building_id, "part": key, "reason": reason}
                    )
                    counts[reason] += 1
                    local[reason] += 1
                    continue
                assert geometry is not None
                point = point_on_surface(geometry)
                inside = frame.covers(point)
                any_in_frame |= inside
                any_swapped |= frame.covers(Point(point.y, point.x))
                if not inside:
                    counts["outside_frame_box"] += 1
                    local["outside_frame_box"] += 1
                elif not boundary.covers(point):
                    counts["inside_box_outside_boundary"] += 1
                    local["inside_box_outside_boundary"] += 1
                else:
                    counts["kept"] += 1
                    _count_field(fields["height"], row["height"], False)
                    _count_field(fields["num_floors"], row["num_floors"], True)
                    local["kept"] += 1
                    kept.append(building_id)
                    _contributors(row["sources"], contributors)
                    features.append(
                        {
                            "type": "Feature",
                            "geometry": geometry.__geo_interface__,
                            "properties": {
                                "building_id": building_id,
                                "recorded_height_m": None,
                                "floor_count": None,
                                "footprint_source_id": "bldg_ovt",
                            },
                        }
                    )
        except PlacesError as error:
            raise BuildingError("building_" + error.reason, key) from None
        if not any_in_frame and any_swapped:
            raise BuildingError("building_axis_swapped", key)
        part_counts[key] = {
            "counts": dict(local),
            "kept_ids_sha256": sha256_hex(dump(sorted(kept))),
        }
    features.sort(key=lambda feature: feature["properties"]["building_id"])
    table_body = dump({"type": "FeatureCollection", "features": features})
    notices = {
        entry.key: entry.basis_note for entry in entries if entry.key in BUILDING_PARTS
    }
    block: dict[str, object] = {
        "method": BUILDING_METHOD,
        "source_release": SOURCE_RELEASE,
        "selection": "unrounded point_on_surface covered by national municipality union; full footprint",
        "frame_bounds": list(FRAME_BOUNDS),
        "boundary_bounds": list(geometry_bounds(boundary)),
        "national_completeness": complete,
        "source_chain": chain,
        "output_sha256": sha256_hex(table_body),
        "counts": dict(counts),
        "parts": part_counts,
        "optional_fields": fields,
        "optional_fields_all_read": fields_all_read,
        "excluded": sorted(excluded, key=lambda row: (row["part"], row["building_id"])),
        "boundary_review": boundary_review(
            cache, chain, counts["inside_box_outside_boundary"]
        ),
        "optional_field_scope": {
            "optional_fields": "kept table rows after spatial and footprint exclusions",
            "optional_fields_all_read": "all source rows before spatial and footprint exclusions",
        },
        "footprint_contributors": dict(sorted(contributors.items())),
        "footprint_contributor_rule": "record-level sources with absent or empty property; each dataset once per kept footprint",
        "attribution_notices": notices,
    }
    target = cache.parent / "assets/buildings"
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".buildings-", dir=target) as folder:
        staged = Path(folder) / "buildings.geojson"
        staged.write_bytes(table_body)
        try:
            load_buildings(staged)
        except HeightError as error:
            raise BuildingError("building_table_invalid", error.name) from None
        staged.replace(target / "buildings.geojson")
        marker = Path(folder) / BUILDING_MANIFEST
        marker.write_bytes(dump(block))
        marker.replace(target / BUILDING_MANIFEST)
    return block


__all__ = ["BuildingError", "build_buildings"]
