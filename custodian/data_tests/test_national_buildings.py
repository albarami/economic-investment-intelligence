"""Lead-shell-only national inventory reconciliation; no fetch or network.

Run only through the documented custodian/data_tests command after a complete
public build and metadata/boundary review. Never selected by a gate or CI.
"""

import json

from shapely import point_on_surface
from shapely.geometry import box
from shapely.ops import unary_union

from eii_custodian.publicdata.building_inputs import (
    BUILDING_PARTS,
    FRAME_BOUNDS,
    dump,
    pinned,
    verify_building_manifest,
)
from eii_custodian.publicdata.buildings import build_buildings
from eii_custodian.publicdata.fetch.bounded import file_hash
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
from eii_custodian.publicdata.frame.raw import read_archive
from eii_custodian.publicdata.heights.model import load_buildings
from eii_custodian.publicdata.heights.step import build_heights
from eii_custodian.publicdata.places import PlacesError
from eii_custodian.publicdata.places.read import building_source_rows, decode_wkb

from .cache import CACHE


def test_selected_national_source_ids_table_ids_and_height_ids(capsys):
    entries = load_registry()
    selected = reviewed_selections(CACHE)
    output = CACHE.parent / "assets/buildings"
    table = output / "buildings.geojson"
    verify_building_manifest(CACHE, entries, selected, table)
    block = json.loads((output / "manifest.buildings.json").read_text())
    archive = read_archive(pinned(CACHE, entries, selected, "bnd_hdx").body)
    boundary = unary_union([item.geometry for item in archive["municipality"]])
    frame = box(*FRAME_BOUNDS)
    expected = set()
    exclusions = []
    for key in BUILDING_PARTS:
        part = pinned(CACHE, entries, selected, key)
        kept = []
        for row in building_source_rows(part.path):
            building_id = row["id"]
            try:
                footprint = decode_wkb(row["geometry"])
            except PlacesError:
                footprint = None
            if (
                footprint is None
                or footprint.geom_type not in {"Polygon", "MultiPolygon"}
                or footprint.is_empty
                or not footprint.is_valid
            ):
                exclusions.append(
                    {
                        "building_id": building_id,
                        "part": key,
                        "reason": "invalid_footprint",
                    }
                )
            elif row["is_underground"] is True:
                exclusions.append(
                    {"building_id": building_id, "part": key, "reason": "underground"}
                )
            else:
                point = point_on_surface(footprint)
                if frame.covers(point) and boundary.covers(point):
                    assert building_id not in expected, "national_inventory_duplicate"
                    expected.add(building_id)
                    kept.append(building_id)
        assert block["parts"][key]["counts"]["kept"] == len(kept), (
            "national_inventory_part_count"
        )
        assert block["parts"][key]["kept_ids_sha256"] == sha256_hex(
            dump(sorted(kept))
        ), "national_inventory_part_ids"
    assert block["excluded"] == sorted(
        exclusions, key=lambda row: (row["part"], row["building_id"])
    ), "national_inventory_exclusions"
    actual = {building.building_id for building in load_buildings(table)}
    assert actual == expected, "national_inventory_table_ids"
    height_output = CACHE.parent / "assets/heights"
    height_manifest = json.loads((height_output / "manifest.heights.json").read_text())
    attempts = tuple(
        item
        for credit in height_manifest["credits"].values()
        for item in credit["terms_attempts"]
    )
    heights = json.loads((height_output / "heights.json").read_text())
    assert len(heights) == len(actual), "national_inventory_height_count"
    assert {row["building_id"] for row in heights} == actual, (
        "national_inventory_height_ids"
    )
    paths = (
        table,
        output / "manifest.buildings.json",
        height_output / "heights.json",
        height_output / "manifest.heights.json",
    )
    before = [file_hash(path) for path in paths]
    build_buildings(CACHE, entries, selected, boundary)
    lines = []
    build_heights(
        CACHE,
        entries,
        table,
        height_output,
        lines,
        selections=selected,
        terms_attempts=attempts,
    )
    assert before == [file_hash(path) for path in paths], (
        "national_inventory_repeatability"
    )
    # Only public aggregate evidence is printed, never a building identifier.
    with capsys.disabled():
        print(
            json.dumps(
                {
                    "national_buildings": {
                        "counts": block["counts"],
                        "parts": block["parts"],
                        "optional_fields": block["optional_fields"],
                        "national_completeness": block["national_completeness"],
                        "boundary_review": block["boundary_review"],
                        "boundary_scope": block["boundary_scope"],
                        "hashes": before,
                        "fallback_errors": height_manifest["errors"],
                    }
                },
                sort_keys=True,
            )
        )
