"""Fixed centre-based grid and resolution-seven ancestry (SYN-10, DAT-73)."""

from typing import Any

from shapely.geometry import Point, shape
from shapely.ops import unary_union

import h3

from .checks import FrameError, check_cover, containing
from .geometry import Boundary, index


def check_ancestors(cells: list[str]) -> None:
    stored = set(cells)
    if len(stored) != len(cells):
        raise FrameError("duplicate cell")
    for cell in cells:
        for resolution in range(h3.get_resolution(cell)):
            if h3.cell_to_parent(cell, resolution) in stored:
                raise FrameError("stored ancestor and child")


def build_grid(
    municipalities: list[Boundary],
    zones: list[Boundary],
    districts: list[Boundary],
    greater_doha: set[str],
    district_free: set[str] | None = None,
    report: list[str] | None = None,
) -> list[dict[str, Any]]:
    """The reviewed municipality keys alone choose the resolution."""
    muni, zone, district = index(municipalities), index(zones), index(districts)
    if not greater_doha <= muni.keys():
        raise FrameError("Greater Doha: unknown municipality")
    frame = unary_union(list(muni.values()))
    district_free = district_free or set()
    for polygons in (muni, zone):
        check_cover(list(polygons.values()), frame)
    for child, parents in [(z, muni) for z in zones] + [(d, zone) for d in districts]:
        owners = [
            key for key, polygon in parents.items() if polygon.covers(child.geometry)
        ]
        if len(owners) != 1:
            raise FrameError("boundary containment: requires one parent")
    for boundary in zones + districts:
        if boundary.municipality_code not in muni or not muni[
            boundary.municipality_code
        ].covers(boundary.geometry):
            raise FrameError("municipality containment disagrees with key")
    check_districts(zone, district, district_free)
    fine = set(h3.geo_to_cells(frame.__geo_interface__, 9))
    split = {
        h3.cell_to_parent(cell, 8)
        for cell in fine
        if containing(Point(*reversed(h3.cell_to_latlng(cell))), muni) in greater_doha
    }
    selected = {cell for cell in fine if h3.cell_to_parent(cell, 8) in split} | (
        set(h3.geo_to_cells(frame.__geo_interface__, 8)) - split
    )
    cells = sorted(selected)
    check_ancestors(cells)
    check_atoms(cells)
    result = []
    for cell in cells:
        lat, lon = h3.cell_to_latlng(cell)
        centre = Point(lon, lat)
        municipality = containing(centre, muni)
        resolution = h3.get_resolution(cell)
        in_doha = municipality in greater_doha
        if in_doha and resolution != 9:
            raise FrameError("Greater Doha cell must have resolution 9")
        if resolution == 9 and not in_doha and h3.cell_to_parent(cell, 8) not in split:
            raise FrameError("outside Greater Doha cell has no Greater Doha sibling")
        zone_key = containing(centre, zone)
        result.append(
            {
                "cell": h3.str_to_int(cell),
                "resolution": resolution,
                "parent_r7": h3.str_to_int(h3.cell_to_parent(cell, 7)),
                "in_greater_doha": in_doha,
                "zone_code": zone_key,
                "district_key": None
                if zone_key in district_free
                else containing(centre, district),
                "municipality_code": municipality,
                "geometry": shape(h3.cells_to_geo(atoms(cell))),
            }
        )
    covered_zones = {row["zone_code"] for row in result}
    for boundary in zones:
        if boundary.key not in covered_zones:
            raise FrameError(f"zone_code {boundary.key}: no cell centre")
    if report is not None:
        report.append(
            f"grid_cell: {sum(r['district_key'] is None for r in result)} zone_without_district"
        )
        covered_districts = {row["district_key"] for row in result}
        report.append(
            f"district: {sum(d.key not in covered_districts for d in districts)} no_cell_centre"
        )
    return result


def atoms(cell: str) -> list[str]:
    """Resolution-nine ownership units, also used to trace the stored outline."""
    if h3.get_resolution(cell) == 9:
        return [cell]
    return h3.cell_to_children(cell, 9)


def check_atoms(cells: list[str]) -> None:
    owned: set[str] = set()
    for cell in cells:
        for atom in atoms(cell):
            if atom in owned:
                raise FrameError("resolution-9 cell owned twice")
            owned.add(atom)


def ownership_index(grid: list[dict[str, Any]]) -> frozenset[int]:
    """Prepare the stored-cell membership once for a batch of point lookups."""
    return frozenset(row["cell"] for row in grid)


def point_cell(lon: float, lat: float, stored: frozenset[int]) -> int | None:
    """Use the point's fine index and its logical parent; never relocate."""
    fine = h3.latlng_to_cell(lat, lon, 9)
    candidates = (h3.str_to_int(fine), h3.str_to_int(h3.cell_to_parent(fine, 8)))
    found = [cell for cell in candidates if cell in stored]
    if len(found) > 1:
        raise FrameError("gazetteer: point has no unique base cell")
    return found[0] if found else None


def check_districts(
    zones: dict[str, Any], districts: dict[str, Any], district_free: set[str]
) -> None:
    if not district_free <= zones.keys():
        raise FrameError("unknown district-free zone")
    # Validate overlap and validity independently of the allowed whole-zone gaps.
    check_cover(list(districts.values()), unary_union(list(districts.values())))
    for key, zone in zones.items():
        members = [polygon for polygon in districts.values() if zone.covers(polygon)]
        if members:
            if key in district_free:
                raise FrameError("listed zone has a district")
            if not unary_union(members).equals(zone):
                raise FrameError("partial district coverage")
        elif key not in district_free:
            raise FrameError("unlisted district-free zone")
