"""Administrative interior points and reviewed, source-given named pins."""

from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from shapely import point_on_surface

from .checks import FrameError, safe_key
from .geometry import Boundary
from .grid import ownership_index, point_cell


def make_row(
    key: str,
    kind: str,
    name_en: str,
    name_ar: str,
    aliases: str | None,
    lon: float,
    lat: float,
    source: str,
    stored: frozenset[int],
) -> dict[str, Any]:
    if not name_en or not name_ar:
        raise FrameError("gazetteer: missing bilingual name")
    stored_lon = Decimal(str(lon)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_EVEN
    )
    stored_lat = Decimal(str(lat)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_EVEN
    )
    cell = point_cell(float(stored_lon), float(stored_lat), stored)
    if cell is None and kind not in {"municipality", "zone", "district"}:
        raise FrameError("gazetteer: point has no unique base cell")
    return {
        "place_key": safe_key(key),
        "kind": kind,
        "name_en": name_en,
        "name_ar": name_ar,
        "aliases": aliases,
        "lon": stored_lon,
        "lat": stored_lat,
        "cell": cell,
        "showcase_verified": False,
        "source_id": source,
    }


def administrative_rows(
    municipalities: list[Boundary],
    zones: list[Boundary],
    districts: list[Boundary],
    grid: list[dict[str, Any]],
    report: list[str] | None = None,
) -> list[dict[str, Any]]:
    stored = ownership_index(grid)
    result = []
    for kind, boundaries in (
        ("municipality", municipalities),
        ("zone", zones),
        ("district", districts),
    ):
        for boundary in boundaries:
            point = point_on_surface(boundary.geometry)
            result.append(
                make_row(
                    f"{kind}:{boundary.key}",
                    kind,
                    boundary.name_en,
                    boundary.name_ar,
                    None,
                    point.x,
                    point.y,
                    "bnd_hdx",
                    stored,
                )
            )
    if report is not None:
        for kind in ("municipality", "zone", "district"):
            count = sum(row["kind"] == kind and row["cell"] is None for row in result)
            report.append(f"gazetteer {kind}: {count} point_without_base_cell")
    return result


def reviewed_points(
    specifications: list[dict[str, Any]],
    points: dict[tuple[str, str], dict[str, Any]],
    grid: list[dict[str, Any]],
    *,
    stored: frozenset[int] | None = None,
) -> list[dict[str, Any]]:
    if stored is None:
        stored = ownership_index(grid)
    result = []
    seen = set()
    for item in specifications:
        key = safe_key(item["place_key"])
        if key in seen:
            raise FrameError("gazetteer: duplicate place key")
        seen.add(key)
        if item["kind"] not in {"landmark", "building"}:
            raise FrameError("gazetteer: invalid reviewed kind")
        if item["arabic_review"] not in {"pending native review", "approved"}:
            raise FrameError("gazetteer: Arabic review status")
        source_key = (item["source_id"], item["record_key"])
        if source_key not in points:
            raise FrameError(f"gazetteer {key}: missing source point")
        point = points[source_key]
        result.append(
            make_row(
                key,
                item["kind"],
                item["name_en"],
                item["name_ar"],
                item["aliases"],
                point["lon"],
                point["lat"],
                item["source_id"],
                stored,
            )
        )
    return result


def validate_frame_tables(
    tables: dict[str, list[dict[str, Any]]], district_free: set[str]
) -> None:
    """L-255 nullable fields are conditional, never an unrestricted relaxation."""
    grid = tables["grid_cell"]
    for row in grid:
        if (row["district_key"] is None) != (row["zone_code"] in district_free):
            raise FrameError("grid_cell: district null condition")
    stored = ownership_index(grid)
    for row in tables["gazetteer"]:
        owner = point_cell(float(row["lon"]), float(row["lat"]), stored)
        if row["cell"] != owner or (
            owner is None and row["kind"] not in {"municipality", "zone", "district"}
        ):
            raise FrameError("gazetteer cell condition")
