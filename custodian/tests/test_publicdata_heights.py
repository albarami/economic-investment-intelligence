"""S2-T20: the heights step end to end, its contract, rules, readers and fetch.

Every fixture is hand-made: invented buildings SYN-B-*, invented files and a
tiny invented raster, written only into temporary folders (FE-95). The worked
fixture is card C42's worked example; its error block is the card's.
"""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
import rasterio
import yaml
from custodian.tests.fixtures.heights import invented
from custodian.tests.repository_root import repository_root
from rasterio.transform import from_origin
from shapely.geometry import Point, Polygon

from eii_core.calc.building_heights import floor_height, metres
from eii_custodian.publicdata import heights as heights_package
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.heights import step
from eii_custodian.publicdata.heights.manifest import (
    ESTIMATE_LABEL,
    check_row,
)
from eii_custodian.publicdata.heights.match import (
    globfp_candidates,
    globfp_height,
    representative_point,
    wsf3d_height,
    wsf_value,
)
from eii_custodian.publicdata.heights.model import (
    RULES_PATH,
    HeightError,
    float_calls,
    load_buildings,
    load_rules,
    storey_literals,
)
from eii_custodian.publicdata.heights.read import WsfGrid, read_sources
from eii_custodian.publicdata.heights.step import build_heights

REPO = repository_root(Path(__file__))
PACKAGE = Path(heights_package.__file__).resolve().parent
CALC = Path(floor_height.__code__.co_filename).resolve()


def _clock() -> str:
    return "2026-11-14T00:00:00Z"


def _sleep(_seconds: float) -> None:
    return None


def _rows(out_dir: Path) -> list[dict]:
    return json.loads((out_dir / "heights.json").read_text())


def _manifest(out_dir: Path) -> dict:
    return json.loads((out_dir / "manifest.heights.json").read_text())


def _card_setup(tmp_path):
    """The card's fixture: seven buildings, one 3D-GloBFP file, one raster."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    buildings, globfp, wsf = invented.card_fixture(tmp_path)
    globfp_row = invented.entry("bldg_3dglobfp", extension="geojson")
    wsf_row = invented.entry("bldg_wsf3d", extension="tif")
    cache = tmp_path / "data" / "public_cache"
    invented.store(cache, globfp_row, globfp)
    invented.store(cache, wsf_row, wsf)
    path = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buildings)
    out_dir = tmp_path / "data" / "assets" / "heights"
    lines: list[str] = []
    build_heights(
        cache,
        (globfp_row, wsf_row),
        path,
        out_dir,
        lines,
        invented.rules_file(tmp_path / "rules.yaml"),
    )
    return out_dir, lines


def test_the_card_fixture_end_to_end(tmp_path: Path) -> None:
    """Criterion 1 and 3: the rows and the error block equal the card's."""
    out_dir, lines = _card_setup(tmp_path)
    rows = {row["building_id"]: row for row in _rows(out_dir)}
    assert rows["SYN-B-0001"]["height_m"] == "30.00"
    assert rows["SYN-B-0001"]["height_source"] == "recorded"
    assert rows["SYN-B-0004"]["height_m"] == "20.00"
    assert rows["SYN-B-0004"]["height_source"] == "floor_count"
    assert rows["SYN-B-0005"]["height_m"] == "6.00"
    assert rows["SYN-B-0005"]["height_source"] == "wsf3d"
    assert rows["SYN-B-0007"]["height_m"] == "7.00"
    assert rows["SYN-B-0007"]["height_source"] == "3dglobfp"
    none_row = rows["SYN-B-0006"]
    assert none_row["height_source"] == "none"
    assert none_row["height_m"] is None
    assert none_row["reason"] == "order_exhausted"
    for row in rows.values():
        if row["height_source"] != "none":
            assert row["reason"] == ""
    block = _manifest(out_dir)
    assert block["card"] == "C42"
    assert block["method"] == "MTH-123"
    assert block["estimate_label"] == ESTIMATE_LABEL
    assert block["counts"] == {
        "recorded": 3,
        "floor_count": 1,
        "3dglobfp": 1,
        "wsf3d": 1,
        "none": 1,
    }
    assert block["none_reasons"] == {"order_exhausted": 1}
    assert block["errors"]["floor_count"] == {
        "count": 2,
        "mean_signed_error_m": "1.00",
        "mean_absolute_error_m": "1.00",
        "median_absolute_error_m": "1.00",
        "reason": "",
    }
    assert block["errors"]["3dglobfp"] == {
        "count": 3,
        "mean_signed_error_m": "-3.00",
        "mean_absolute_error_m": "5.00",
        "median_absolute_error_m": "6.00",
        "reason": "",
    }
    assert block["errors"]["wsf3d"] == {
        "count": 2,
        "mean_signed_error_m": "-10.00",
        "mean_absolute_error_m": "10.00",
        "median_absolute_error_m": "10.00",
        "reason": "",
    }
    assert block["storey_height_m"]["value"] == "4"
    assert block["storey_height_m"]["label"] == "ASSUMPTION"
    assert block["sources"]["bldg_3dglobfp"]["state"] == "read"
    assert any("PASS heights" in line for line in lines)


def test_the_3dglobfp_credit_fills_the_receipt_date(tmp_path: Path) -> None:
    """Criterion 4: the credit equals doc 04's text with the retrieval date."""
    out_dir, _lines = _card_setup(tmp_path)
    credits = _manifest(out_dir)["credits"]
    assert credits["bldg_3dglobfp"]["credit"] == (
        "Invented credit line, retrieved 2026-11-14."
    )
    assert credits["bldg_wsf3d"]["terms_words"] == ("invented terms words for a test")
    assert credits["bldg_wsf3d"]["terms_read_on"] == "2026-11-14"


def test_two_runs_give_identical_file_hashes(tmp_path: Path) -> None:
    """FE-98: identical inputs give byte-identical files."""
    first, _ = _card_setup(tmp_path / "one")
    second, _ = _card_setup(tmp_path / "two")
    for name in ("heights.json", "manifest.heights.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_the_manifest_files_list_carries_hashes_and_receipt_terms(
    tmp_path: Path,
) -> None:
    """FE-96: every file read or written names its hash and provenance."""
    out_dir, _ = _card_setup(tmp_path)
    files = {record["key"]: record for record in _manifest(out_dir)["files"]}
    assert files["building_table"]["role"] == "read"
    assert files["heights"]["role"] == "written"
    globfp = files["bldg_3dglobfp"]
    assert len(globfp["sha256"]) == 64
    assert globfp["url"].startswith("https://data.worldpop.org/")
    assert globfp["retrieved_utc"] == "2026-11-14T00:00:00Z"
    assert globfp["licence_id"] == "CC-BY-4.0"
    assert globfp["terms_words"] == "invented terms words for a test"
    assert globfp["terms_read_on"] == "2026-11-14"


def test_an_absent_building_table_is_a_skip_line_not_a_failure(
    tmp_path: Path,
) -> None:
    """B10: the absent table adds one SKIP line and changes no exit code."""
    lines: list[str] = []
    build_heights(
        tmp_path / "cache",
        (),
        tmp_path / "data" / "assets" / "buildings" / "buildings.geojson",
        tmp_path / "out",
        lines,
    )
    assert lines == ["SKIP heights building_table_absent"]
    assert not (tmp_path / "out").exists()


def test_the_committed_rules_leave_both_sources_structure_unconfirmed(
    tmp_path: Path,
) -> None:
    """Without a structure note both sources are absent, never a failure."""
    out_dir = tmp_path / "out"
    buildings_path = tmp_path / "buildings.geojson"
    buildings_path.write_bytes(
        invented.buildings_bytes(
            [
                invented.building_feature(
                    "SYN-B-0001", invented.square(0, 0, 1), None, None
                ),
                invented.building_feature(
                    "SYN-B-0002", invented.square(2, 0, 1), 30, 8
                ),
            ]
        )
    )
    lines: list[str] = []
    build_heights(
        tmp_path / "cache",
        (),
        buildings_path,
        out_dir,
        lines,
        RULES_PATH,
    )
    rows = {row["building_id"]: row for row in _rows(out_dir)}
    assert rows["SYN-B-0001"]["height_source"] == "none"
    assert rows["SYN-B-0001"]["reason"] == "structure_unconfirmed"
    assert rows["SYN-B-0002"]["height_m"] == "30.00"
    block = _manifest(out_dir)
    assert block["sources"]["bldg_3dglobfp"]["reason"] == "structure_unconfirmed"
    assert block["sources"]["bldg_wsf3d"]["state"] == "absent"
    assert block["storey_height_m"]["value"] == "3.0"
    assert block["credits"]["bldg_3dglobfp"]["credit"] == ""


def test_the_floor_count_product_reads_the_committed_constant(
    tmp_path: Path,
) -> None:
    """Criterion 2: the storey constant is read by name from its own file."""
    rules = load_rules(RULES_PATH)
    buildings_path = tmp_path / "buildings.geojson"
    buildings_path.write_bytes(
        invented.buildings_bytes(
            [invented.building_feature("SYN-B-0001", invented.square(0, 0, 1), None, 5)]
        )
    )
    out_dir = tmp_path / "out"
    lines: list[str] = []
    build_heights(tmp_path / "cache", (), buildings_path, out_dir, lines, RULES_PATH)
    row = _rows(out_dir)[0]
    expected = floor_height(Decimal(5), rules.storey_height)
    assert rules.storey_height == Decimal("3.0")
    assert row["height_m"] == str(expected) == "15.00"
    assert row["height_source"] == "floor_count"


def test_no_python_file_repeats_the_storey_literal(tmp_path: Path) -> None:
    """B4: the constant lives once; a planted literal is caught by the scan."""
    constant = load_rules(RULES_PATH).storey_height
    for path in [*sorted(PACKAGE.glob("*.py")), CALC]:
        assert storey_literals(path, constant) == (), path
    planted = tmp_path / "planted.py"
    planted.write_text("x = 3.0\ny = 4.0\n", encoding="utf-8")
    assert storey_literals(planted, constant) == (1,)


def test_rules_reader_refusals(tmp_path: Path) -> None:
    """B4: unknown key, missing key, wrong label and bad values are refused."""
    document = invented.rules_document()
    document["invented_key"] = 1
    with pytest.raises(HeightError, match="rules_unknown_key"):
        load_rules(invented.write_rules(tmp_path / "a.yaml", document))
    document = invented.rules_document()
    del document["order"]
    with pytest.raises(HeightError, match="rules_missing_key"):
        load_rules(invented.write_rules(tmp_path / "b.yaml", document))
    document = invented.rules_document()
    document["storey_height_m"]["label"] = "GUESS"
    with pytest.raises(HeightError, match="rules_label"):
        load_rules(invented.write_rules(tmp_path / "c.yaml", document))
    for value in ("0", "-1", "NaN", "Infinity", 4.0, True):
        document = invented.rules_document()
        document["storey_height_m"]["value"] = value
        with pytest.raises(HeightError):
            load_rules(invented.write_rules(tmp_path / "d.yaml", document))
    document = invented.rules_document()
    document["sources"]["bldg_3dglobfp"]["invented"] = 1
    with pytest.raises(HeightError, match="rules_unknown_key"):
        load_rules(invented.write_rules(tmp_path / "e.yaml", document))


def test_the_committed_rules_file_loads_and_marks_every_value() -> None:
    """The committed file parses; every declared value is the marker."""
    rules = load_rules(RULES_PATH)
    assert rules.storey_height == Decimal("3.0")
    assert rules.label == "ASSUMPTION"
    for structure in rules.structures.values():
        assert all(
            value == "to be confirmed"
            for value in (
                structure.format,
                structure.unit,
                structure.nodata,
                structure.crs,
            )
        )


def test_input_contract_refusals(tmp_path: Path) -> None:
    """B3: repeated id, extra property, missing property and bad values."""
    base = invented.building_feature("SYN-B-0001", invented.square(0, 0, 1), 30, 8)
    cases = {}
    repeated = [base, dict(base)]
    cases["repeated_id"] = repeated
    extra = invented.building_feature(
        "SYN-B-0001",
        invented.square(0, 0, 1),
        30,
        8,
        extra={"SYN_figure": 7.5},
    )
    cases["extra_property"] = [extra]
    missing = invented.building_feature("SYN-B-0001", invented.square(0, 0, 1), 30, 8)
    del missing["properties"]["floor_count"]
    cases["missing_property"] = [missing]
    cases["bad_floor_count"] = [
        invented.building_feature("SYN-B-0001", invented.square(0, 0, 1), 30, -2)
    ]
    cases[r"bad_floor_count.*"] = [
        invented.building_feature("SYN-B-0001", invented.square(0, 0, 1), 30, 8.5)
    ]
    cases["bad_recorded_height_m"] = [
        invented.building_feature("SYN-B-0001", invented.square(0, 0, 1), "30", 8)
    ]
    cases["bad_footprint"] = [
        invented.building_feature(
            "SYN-B-0001",
            invented.square(0, 0, 1),
            30,
            8,
            geometry={"type": "Point", "coordinates": [0, 0]},
        )
    ]
    for name, features in cases.items():
        path = tmp_path / f"{name}.geojson"
        path.write_bytes(invented.buildings_bytes(features))
        with pytest.raises(HeightError, match=name):
            load_buildings(path)


def test_a_table_that_is_not_a_feature_collection_is_refused(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.geojson"
    path.write_bytes(json.dumps({"type": "Feature"}).encode())
    with pytest.raises(HeightError, match="building_table"):
        load_buildings(path)


def test_the_writer_refuses_extra_columns_and_bad_sources() -> None:
    """B7's writer plant: a column beyond the closed set and a bad source."""
    row = {
        "building_id": "SYN-B-0001",
        "height_m": 30,
        "height_source": "recorded",
        "footprint_source_id": "SYN-FOOT",
        "reason": "",
    }
    check_row(dict(row))
    with pytest.raises(HeightError, match="output_columns"):
        check_row({**row, "planted_column": 1})
    with pytest.raises(HeightError, match="output_columns"):
        check_row({key: row[key] for key in row if key != "reason"})
    with pytest.raises(HeightError, match="output_source"):
        check_row({**row, "height_source": "invented_source"})
    with pytest.raises(HeightError, match="output_none"):
        check_row(
            {
                "building_id": "SYN-B-0001",
                "height_m": 0,
                "height_source": "none",
                "footprint_source_id": "SYN-FOOT",
                "reason": "order_exhausted",
            }
        )


def _polygon(ring: list) -> Polygon:
    return Polygon(ring)


def test_a_concave_footprint_uses_an_interior_point() -> None:
    """The representative point is inside where the centroid is not."""
    ring = [
        [0, 0],
        [4, 0],
        [4, 1],
        [0.5, 1],
        [0.5, 3],
        [4, 3],
        [4, 4],
        [0, 4],
        [0, 0],
    ]
    geometry = _polygon(ring)
    assert not geometry.covers(geometry.centroid)
    point = representative_point(geometry)
    assert geometry.covers(point)


def test_a_footprint_not_holding_the_point_gives_no_candidate() -> None:
    """A 3D-GloBFP footprint away from the point is never a candidate."""
    building = _polygon(invented.square(0, 0, 1))
    point = representative_point(building)
    away = _polygon(invented.square(5, 5, 1))
    files = (("f", ((away, Decimal(9)),)),)
    assert globfp_candidates(point, building, files) == []
    assert globfp_height(point, building, files) is None


def test_the_larger_overlap_wins_and_residual_ties_are_broken() -> None:
    """Largest overlap wins; ties take the lowest file, then the lowest row."""
    building = _polygon(invented.square(0, 0, 1))
    point = representative_point(building)
    whole = _polygon(invented.square(-0.5, -0.5, 2))
    part = _polygon(invented.square(0.5, 0.5, 1))
    files = (("one", ((part, Decimal(8)), (whole, Decimal(9)))),)
    assert globfp_height(point, building, files) == Decimal(9)
    across = (
        ("b", ((whole, Decimal(8)),)),
        ("a", ((whole, Decimal(9)),)),
    )
    assert globfp_height(point, building, across) == Decimal(9)
    same_file = (("a", ((whole, Decimal(8)), (whole, Decimal(9)))),)
    assert globfp_height(point, building, same_file) == Decimal(8)


def _grid(values, width, height, nodata=Decimal("-99999")):
    from rasterio.transform import from_origin

    return WsfGrid(
        transform=from_origin(0, 1, 1, 1),
        data=np.array(values, dtype="float32").reshape(height, width),
        nodata=nodata,
        width=width,
        height=height,
    )


def test_a_no_data_cell_and_a_point_outside_give_no_value() -> None:
    """A no-data cell or a point outside the raster produces no value."""
    grid = _grid([[18, -99999]], 2, 1)
    assert wsf_value(grid, Point(0.5, 0.5)) == Decimal(18)
    assert wsf_value(grid, Point(1.5, 0.5)) is None
    assert wsf_value(grid, Point(5, 5)) is None
    assert wsf_value(grid, Point(-1, 0.5)) is None
    assert wsf_value(grid, Point(2.0, 0.5)) is None
    assert wsf_value(grid, Point(0.5, 0.0)) is None


def test_two_wsf_files_giving_values_at_one_point_are_refused() -> None:
    """V11: two files that both give a value at the point refuse, never choose."""
    low = _grid([[7]], 1, 1)
    high = _grid([[9]], 1, 1)
    files = (("b", high), ("a", low))
    with pytest.raises(HeightError, match="wsf3d_overlap"):
        wsf3d_height(Point(0.5, 0.5), files)
    nodata = _grid([[-99999]], 1, 1)
    assert wsf3d_height(Point(0.5, 0.5), (("a", nodata), ("b", low))) == Decimal(7)
    zero = _grid([[0]], 1, 1)
    assert wsf3d_height(Point(0.5, 0.5), (("a", zero), ("b", low))) == Decimal(7)


def _sources(tmp_path: Path, entries, rules=None, bodies=()):
    """Run read_sources over stored fixtures."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    cache = tmp_path / "cache"
    for entry, body in bodies:
        invented.store(cache, entry, body)
    return read_sources(
        cache,
        entries,
        load_rules(rules or invented.rules_file(tmp_path / "rules.yaml")),
    )


def test_read_refusals_and_absent_reasons(tmp_path: Path) -> None:
    """B6: hash and receipt defects refuse; skip and not_fetched are absent."""
    row = invented.entry("bldg_3dglobfp", extension="geojson")
    skipped = replace(
        row, key="bldg_3dglobfp/two", slug="two", skip_reason="direct_url_unconfirmed"
    )
    results = _sources(tmp_path / "one", (skipped,))
    assert results["bldg_3dglobfp"].state == "absent"
    assert results["bldg_3dglobfp"].reason == "direct_url_unconfirmed"
    results = _sources(tmp_path / "two", (row,))
    assert results["bldg_3dglobfp"].state == "absent"
    assert results["bldg_3dglobfp"].reason == "not_fetched"
    changed = tmp_path / "three"
    row = invented.entry("bldg_3dglobfp", extension="geojson")
    body = invented.globfp_bytes([(invented.square(0, 0, 1), 7)])
    digest = invented.store(changed / "cache", row, body)
    target = changed / "cache" / "bldg_3dglobfp" / f"{digest}.{row.extension}"
    target.write_bytes(b"planted other bytes")
    with pytest.raises(HeightError, match="content_hash_mismatch"):
        _sources(changed, (row,))
    switched = tmp_path / "four"
    digest = invented.store(switched / "cache", row, body)
    receipt_path = next((switched / "cache" / "bldg_3dglobfp").glob("*.meta.json"))
    receipt = json.loads(receipt_path.read_text())
    receipt["switched_off"] = True
    receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n")
    with pytest.raises(HeightError, match="switched_off"):
        _sources(switched, (row,))


def test_read_declared_and_file_structure_refusals(tmp_path: Path) -> None:
    """R9(g): declared unit and crs, and files that differ, are refused."""
    row = invented.entry("bldg_wsf3d", extension="tif")
    body = invented.wsf_bytes(tmp_path / "w.tif", [[5]], 1, 1)
    rules = invented.rules_file(tmp_path / "feet.yaml", wsf_unit="ft")
    with pytest.raises(HeightError, match="declared_unit"):
        _sources(tmp_path / "a", (row,), rules, ((row, body),))
    rules = invented.rules_file(tmp_path / "crs.yaml", wsf_crs="EPSG:3857")
    with pytest.raises(HeightError, match="declared_reference_system"):
        _sources(tmp_path / "b", (row,), rules, ((row, body),))
    wrong_crs = invented.wsf_bytes(tmp_path / "w2.tif", [[5]], 1, 1, epsg=3857)
    with pytest.raises(HeightError, match="reference_system"):
        _sources(
            tmp_path / "c",
            (row,),
            invented.rules_file(tmp_path / "ok.yaml"),
            ((row, wrong_crs),),
        )
    two_band = tmp_path / "w3.tif"
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    with rasterio.open(
        two_band,
        "w",
        driver="GTiff",
        width=1,
        height=1,
        count=2,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0, 1, 1, 1),
        nodata=-99999,
    ) as target:
        target.write(np.zeros((2, 1, 1), dtype="float32"))
    with pytest.raises(HeightError, match="structure_mismatch"):
        _sources(
            tmp_path / "d",
            (row,),
            invented.rules_file(tmp_path / "ok2.yaml"),
            ((row, two_band.read_bytes()),),
        )
    globfp_row = invented.entry("bldg_3dglobfp", extension="geojson")
    missing_field = invented.globfp_bytes(
        [(invented.square(0, 0, 1), 7)], field="other_name"
    )
    with pytest.raises(HeightError, match="structure_mismatch"):
        _sources(
            tmp_path / "e",
            (globfp_row,),
            invented.rules_file(tmp_path / "ok3.yaml"),
            ((globfp_row, missing_field),),
        )


def test_a_marker_structure_is_absent_without_failure(tmp_path: Path) -> None:
    """`to be confirmed` gives `structure_unconfirmed`, no failure."""
    document = invented.rules_document()
    document["sources"]["bldg_3dglobfp"]["format"] = "to be confirmed"
    row = invented.entry("bldg_3dglobfp", extension="geojson")
    body = invented.globfp_bytes([(invented.square(0, 0, 1), 7)])
    results = _sources(
        tmp_path,
        (row,),
        invented.write_rules(tmp_path / "r.yaml", document),
        ((row, body),),
    )
    assert results["bldg_3dglobfp"].state == "absent"
    assert results["bldg_3dglobfp"].reason == "structure_unconfirmed"
    assert results["bldg_wsf3d"].reason == "not_fetched"


def test_another_declared_format_is_absent_not_refused(tmp_path: Path) -> None:
    """A declared format we cannot read is structure_unconfirmed, not a FAIL."""
    row = invented.entry("bldg_3dglobfp", extension="zip")
    results = _sources(
        tmp_path,
        (row,),
        invented.rules_file(tmp_path / "r.yaml", globfp_format="shp"),
    )
    assert results["bldg_3dglobfp"].state == "absent"
    assert results["bldg_3dglobfp"].reason == "structure_unconfirmed"


def _heights_entries(loaded: tuple[Entry, ...]) -> dict[str, Entry]:
    return {
        entry.source_id: entry
        for entry in loaded
        if entry.source_id in {"bldg_3dglobfp", "bldg_wsf3d"}
    }


def test_committed_rows_load_with_their_basis_and_no_credit() -> None:
    """Criterion 4: the two rows load; 3D-GloBFP has its licence, no credit."""
    entries = _heights_entries(load_registry())
    globfp = entries["bldg_3dglobfp"]
    assert globfp.licence_id == "CC-BY-4.0"
    assert globfp.licence_basis == "dataset"
    assert globfp.decision_record == ""
    assert "credit" not in vars(globfp)
    wsf = entries["bldg_wsf3d"]
    assert wsf.licence_basis == "owner_decision"
    assert wsf.decision_record == "0026"
    assert wsf.licence_id == "unconfirmed"
    for entry in entries.values():
        assert entry.kind == "https_file"
        assert entry.commit_allowed is False
        assert entry.nightly_live_fetch is False
        assert entry.skip_reason == "direct_url_unconfirmed"
        assert entry.row_count_min is None
        assert entry.row_count_max is None
    pack = (REPO / "docs" / "04_PUBLIC_DATA_PACK.md").read_text()
    assert '"Che et al. 2024"' in pack
    document = yaml.safe_load(
        (REPO / "custodian" / "publicdata" / "sources.yaml").read_text()
    )
    rows = {
        row["source_id"]: row
        for row in document["sources"]
        if row["source_id"] in {"bldg_3dglobfp", "bldg_wsf3d"}
    }
    assert "credit" not in rows["bldg_3dglobfp"]
    assert "credit" not in rows["bldg_wsf3d"]


def test_committed_rows_carry_no_row_count_bounds(tmp_path: Path) -> None:
    """R9(a): the count check reads JSON only; a planted bound fails."""
    entries = _heights_entries(load_registry())
    assert all(
        entry.row_count_min is None and entry.row_count_max is None
        for entry in entries.values()
    )
    document = yaml.safe_load(
        (REPO / "custodian" / "publicdata" / "sources.yaml").read_text()
    )
    for row in document["sources"]:
        if row["source_id"] == "bldg_3dglobfp":
            row["row_count_min"] = 1
    assert not all(
        entry.row_count_min is None and entry.row_count_max is None
        for entry in _heights_entries(
            load_registry(invented.write_rules(tmp_path / "r.yaml", document))
        ).values()
    )


def test_non_commercial_terms_never_block_the_source(tmp_path: Path) -> None:
    """Criterion 5: a non-commercial row loads, fetches and gives its height."""
    document = yaml.safe_load(
        (REPO / "custodian" / "publicdata" / "sources.yaml").read_text()
    )
    for row in document["sources"]:
        if row["source_id"] == "bldg_wsf3d":
            row["licence_id"] = "CC-BY-NC-4.0"
            row["licence_basis"] = "owner_decision"
            row["decision_record"] = "0026"
            row["terms_words"] = "invented non-commercial words for a test"
            row["skip_reason"] = ""
            row["fetch_host"] = invented.ALLOWED_HOST
            row["url"] = f"https://{invented.ALLOWED_HOST}/SYN/wsf3d.tif"
            row["extension"] = "tif"
    loaded = load_registry(invented.write_rules(tmp_path / "r.yaml", document))
    row = next(entry for entry in loaded if entry.source_id == "bldg_wsf3d")
    assert row.licence_id == "CC-BY-NC-4.0"
    wsf = invented.wsf_bytes(tmp_path / "w.tif", [[42]], 1, 1)

    def transport(url: str) -> Response:
        assert url == row.url
        return Response(final_url=url, body=wsf, hops=())

    cache = tmp_path / "data" / "public_cache"
    outcome = run_build((row,), transport, cache, _clock, _sleep)
    assert outcome.failure is None
    receipt_path = next((cache / "bldg_wsf3d").glob("*.meta.json"))
    receipt = json.loads(receipt_path.read_text())
    assert receipt["switched_off"] is False
    assert receipt["terms_words"] == "invented non-commercial words for a test"
    buildings_path = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    buildings_path.parent.mkdir(parents=True, exist_ok=True)
    buildings_path.write_bytes(
        invented.buildings_bytes(
            [invented.building_feature("SYN-B-0001", invented.square(0, 0, 1))]
        )
    )
    out_dir = tmp_path / "data" / "assets" / "heights"
    build_heights(
        cache,
        (row,),
        buildings_path,
        out_dir,
        [],
        invented.rules_file(tmp_path / "rules.yaml"),
    )
    rows = _rows(out_dir)
    assert rows[0]["height_m"] == "42.00"
    assert rows[0]["height_source"] == "wsf3d"


def test_both_rows_fetch_through_run_build_on_an_allowed_host(
    tmp_path: Path,
) -> None:
    """B9: each row is fetched and stored; bytes stay in the cache (FE-95)."""
    rows = [
        invented.entry("bldg_3dglobfp", extension="geojson"),
        invented.entry("bldg_wsf3d", extension="tif"),
    ]
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        return Response(final_url=url, body=b"invented-bytes", hops=())

    cache = tmp_path / "data" / "public_cache"
    outcome = run_build(tuple(rows), transport, cache, _clock, _sleep)
    assert outcome.failure is None
    assert seen == [entry.url for entry in rows]
    assert "SKIP heights building_table_absent" in outcome.lines
    for entry in rows:
        digest = sha256_hex(b"invented-bytes")
        stored_body = cache / entry.key / f"{digest}.{entry.extension}"
        assert stored_body.read_bytes() == b"invented-bytes"
        receipt_path = cache / entry.key / f"{digest}.meta.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["switched_off"] is False


def test_an_off_list_host_is_refused_before_the_transport(
    tmp_path: Path,
) -> None:
    """PUB-03: an unlisted host is refused before any byte is asked for."""
    row = replace(
        invented.entry("bldg_3dglobfp"),
        fetch_host=invented.BLOCKED_HOST,
        url=f"https://{invented.BLOCKED_HOST}/SYN/x.bin",
    )
    seen: list[str] = []

    def transport(url: str) -> Response:
        seen.append(url)
        return Response(final_url=url, body=b"planted", hops=())

    outcome = run_build((row,), transport, tmp_path / "cache", _clock, _sleep)
    assert seen == []
    assert outcome.failure is not None
    assert outcome.failure.check == "blocked_host"


def test_run_build_skips_heights_on_an_absent_table(tmp_path: Path) -> None:
    """B10: the absent table gives one SKIP line and no failure."""
    cache = tmp_path / "data" / "public_cache"

    def transport(url: str) -> Response:
        raise AssertionError(url)

    outcome = run_build((), transport, cache, _clock, _sleep)
    assert outcome.failure is None
    assert outcome.lines.count("SKIP heights building_table_absent") == 1


def test_build_public_returns_0_and_prints_the_skip_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """B10: `./eii build-public` stays green while the table is absent."""
    import commands.build_public as build_public

    def transport(url: str) -> Response:
        raise AssertionError(url)

    monkeypatch.setattr(build_public, "load_registry", lambda: ())
    monkeypatch.setattr(build_public, "utc_now", lambda: _clock())
    code = build_public.run(tmp_path, {}, (), transport=transport, sleep=_sleep)
    assert code == 0
    assert "SKIP heights building_table_absent" in capsys.readouterr().out


def test_an_fe50_table_fails_the_build_and_writes_no_heights(
    tmp_path: Path,
) -> None:
    """R4: the extra numeric property is refused; no heights file exists."""
    cache = tmp_path / "data" / "public_cache"
    buildings = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    buildings.parent.mkdir(parents=True, exist_ok=True)
    buildings.write_bytes(
        invented.buildings_bytes(
            [
                invented.building_feature(
                    "SYN-B-0001",
                    invented.square(0, 0, 1),
                    30,
                    8,
                    extra={"SYN_figure": 7.5},
                )
            ]
        )
    )

    def transport(url: str) -> Response:
        raise AssertionError(url)

    outcome = run_build((), transport, cache, _clock, _sleep)
    assert outcome.failure is not None
    assert any("FAIL heights" in line for line in outcome.lines)
    assert not (tmp_path / "data" / "assets" / "heights").exists()


def test_a_written_row_reads_back_as_the_same_decimal(tmp_path: Path) -> None:
    """The file's own text parses back to exactly the rounded Decimal."""
    buildings_path = tmp_path / "buildings.geojson"
    buildings_path.write_bytes(
        invented.buildings_bytes(
            [
                invented.building_feature(
                    "SYN-B-0001", invented.square(0, 0, 1), 30.127, None
                )
            ]
        )
    )
    out_dir = tmp_path / "out"
    build_heights(tmp_path / "cache", (), buildings_path, out_dir, [], RULES_PATH)
    row = _rows(out_dir)[0]
    assert row["height_m"] == "30.13"
    assert Decimal(row["height_m"]) == metres(Decimal("30.127"))


def test_a_long_expansion_statistic_is_written_at_the_stated_decimals(
    tmp_path: Path,
) -> None:
    """0.04/3 has a long expansion; the manifest writes the rounded text."""
    features = [
        invented.building_feature(
            f"SYN-B-000{i + 1}", invented.square(i + 0.1, 0.1, 0.5), 1, None
        )
        for i in range(3)
    ]
    buildings_path = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    buildings_path.parent.mkdir(parents=True, exist_ok=True)
    buildings_path.write_bytes(invented.buildings_bytes(features))
    globfp_row = invented.entry("bldg_3dglobfp", extension="geojson")
    globfp = invented.globfp_bytes(
        [
            (invented.square(0.05, 0.05, 0.6), 1.01),
            (invented.square(1.05, 0.05, 0.6), 1.01),
            (invented.square(2.05, 0.05, 0.6), 1.02),
        ]
    )
    cache = tmp_path / "data" / "public_cache"
    invented.store(cache, globfp_row, globfp)
    out_dir = tmp_path / "data" / "assets" / "heights"
    build_heights(
        cache,
        (globfp_row,),
        buildings_path,
        out_dir,
        [],
        invented.rules_file(tmp_path / "rules.yaml"),
    )
    block = _manifest(out_dir)["errors"]["3dglobfp"]
    assert block["count"] == 3
    assert block["mean_signed_error_m"] == "0.01"
    assert block["mean_absolute_error_m"] == "0.01"


def test_a_non_positive_wsf_cell_is_counted_and_never_a_crash(
    tmp_path: Path,
) -> None:
    """V1: raster [[0, 5]] — the recorded 30 wins and each 0 cell is counted."""
    buildings = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    buildings.parent.mkdir(parents=True, exist_ok=True)
    buildings.write_bytes(
        invented.buildings_bytes(
            [
                invented.building_feature(
                    "SYN-B-0001", invented.square(0.1, 0.1, 0.5), 30, None
                ),
                invented.building_feature(
                    "SYN-B-0002", invented.square(0.6, 0.7, 0.3), None, None
                ),
                invented.building_feature(
                    "SYN-B-0003", invented.square(1.1, 0.1, 0.5), None, None
                ),
            ]
        )
    )
    wsf_row = invented.entry("bldg_wsf3d", extension="tif")
    cache = tmp_path / "data" / "public_cache"
    invented.store(
        cache, wsf_row, invented.wsf_bytes(tmp_path / "w.tif", [[0, 5]], 2, 1)
    )
    out_dir = tmp_path / "data" / "assets" / "heights"
    lines: list[str] = []
    build_heights(
        cache,
        (wsf_row,),
        buildings,
        out_dir,
        lines,
        invented.rules_file(tmp_path / "rules.yaml"),
    )
    rows = {row["building_id"]: row for row in _rows(out_dir)}
    assert rows["SYN-B-0001"]["height_m"] == "30.00"
    assert rows["SYN-B-0001"]["height_source"] == "recorded"
    assert rows["SYN-B-0002"]["height_source"] == "none"
    assert rows["SYN-B-0003"]["height_m"] == "5.00"
    assert rows["SYN-B-0003"]["height_source"] == "wsf3d"
    block = _manifest(out_dir)
    assert block["no_value_reasons"] == {"wsf3d_value_not_positive": 2}
    assert block["none_reasons"] == {"not_fetched": 1}


def test_a_nan_wsf_cell_is_no_value_not_a_crash(tmp_path: Path) -> None:
    """V1: a NaN cell gives no value and is counted, never a crash."""
    buildings = tmp_path / "buildings.geojson"
    buildings.write_bytes(
        invented.buildings_bytes(
            [
                invented.building_feature(
                    "SYN-B-0001", invented.square(0.1, 0.1, 0.5), None, None
                )
            ]
        )
    )
    wsf_row = invented.entry("bldg_wsf3d", extension="tif")
    cache = tmp_path / "cache"
    invented.store(
        cache,
        wsf_row,
        invented.wsf_bytes(tmp_path / "w.tif", [[float("nan")]], 1, 1),
    )
    out_dir = tmp_path / "out"
    build_heights(
        cache,
        (wsf_row,),
        buildings,
        out_dir,
        [],
        invented.rules_file(tmp_path / "rules.yaml"),
    )
    row = _rows(out_dir)[0]
    assert row["height_source"] == "none"
    assert _manifest(out_dir)["no_value_reasons"] == {"wsf3d_value_not_positive": 1}


def test_the_pass_line_names_fallback_buildings(tmp_path: Path) -> None:
    """V10: the PASS line counts buildings whose source is a fallback."""
    _out_dir, lines = _card_setup(tmp_path)
    (line,) = [line for line in lines if line.startswith("PASS heights")]
    assert "fallback_buildings=3" in line
    assert "sources=" not in line


def test_no_float_call_converts_a_figure_in_the_heights_package(
    tmp_path: Path,
) -> None:
    """Rules 16-17: a planted float( on a figure is caught by the AST scan."""
    for path in [*sorted(PACKAGE.glob("*.py")), CALC]:
        assert float_calls(path) == (), path
    planted = tmp_path / "planted.py"
    planted.write_text("height = float('1.5')\n", encoding="utf-8")
    assert float_calls(planted) == (1,)


def test_the_heights_package_has_no_numeric_storey_literal() -> None:
    """Re-scan with the AST itself: the constant is never re-declared."""
    constant = load_rules(RULES_PATH).storey_height
    for path in [*sorted(PACKAGE.glob("*.py")), CALC]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, (int, float))
                and not isinstance(node.value, bool)
            ):
                assert Decimal(str(node.value)) != constant, (
                    path,
                    node.lineno,
                )


def _raw_building_table(properties_json: str) -> bytes:
    """A building table with literal JSON properties (for 1e60, dup keys)."""
    ring = json.dumps([invented.square(0, 0, 1)])
    return (
        '{"type": "FeatureCollection", "features": [{"type": "Feature",'
        ' "geometry": {"type": "Polygon", "coordinates": ' + ring + "},"
        ' "properties": ' + properties_json + "}]}"
    ).encode()


def test_a_repeated_key_in_the_building_table_is_refused(tmp_path: Path) -> None:
    """V6: an object holding a key twice is refused, naming the key, never the value."""
    path = tmp_path / "dup.geojson"
    path.write_bytes(
        _raw_building_table(
            '{"building_id": "SYN-B-0001", "recorded_height_m": 30,'
            ' "recorded_height_m": null, "floor_count": 8,'
            ' "footprint_source_id": "SYN-FOOT"}'
        )
    )
    with pytest.raises(HeightError) as err:
        load_buildings(path)
    assert err.value.name == "building_table"
    assert err.value.detail == "recorded_height_m"


def test_a_recorded_height_too_large_for_the_context_is_refused(
    tmp_path: Path,
) -> None:
    """V2: a recorded 1e60 cannot round at the stated places; named refusal."""
    path = tmp_path / "huge.geojson"
    path.write_bytes(
        _raw_building_table(
            '{"building_id": "SYN-B-0001", "recorded_height_m": 1e60,'
            ' "floor_count": null, "footprint_source_id": "SYN-FOOT"}'
        )
    )
    with pytest.raises(HeightError) as err:
        load_buildings(path)
    assert err.value.name == "bad_recorded_height_m"


def test_a_recorded_height_that_rounds_to_zero_is_refused(tmp_path: Path) -> None:
    """V7: a recorded 0.004 is refused as a zero is, with the zero's reason."""
    path = tmp_path / "zero.geojson"
    path.write_bytes(
        _raw_building_table(
            '{"building_id": "SYN-B-0001", "recorded_height_m": 0.004,'
            ' "floor_count": 8, "footprint_source_id": "SYN-FOOT"}'
        )
    )
    with pytest.raises(HeightError) as err:
        load_buildings(path)
    assert err.value.name == "bad_recorded_height_m"


def test_a_floor_product_too_large_for_the_context_is_refused(
    tmp_path: Path,
) -> None:
    """V2: a valid floor count times a valid storey can still overflow."""
    rules = invented.rules_file(tmp_path / "r.yaml", storey="4E+47")
    path = tmp_path / "buildings.geojson"
    path.write_bytes(
        _raw_building_table(
            '{"building_id": "SYN-B-0001", "recorded_height_m": null,'
            ' "floor_count": 4e47, "footprint_source_id": "SYN-FOOT"}'
        )
    )
    with pytest.raises(HeightError) as err:
        build_heights(tmp_path / "cache", (), path, tmp_path / "out", [], rules)
    assert err.value.name == "bad_floor_count"


def test_a_rules_file_that_is_not_yaml_is_a_named_refusal(tmp_path: Path) -> None:
    """V2: a rules file that is not YAML is refused as rules_root."""
    path = tmp_path / "rules.yaml"
    path.write_text("][")
    with pytest.raises(HeightError) as err:
        load_rules(path)
    assert err.value.name == "rules_root"


def test_a_wsf_body_that_is_not_a_raster_is_a_named_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V2: a WSF body rasterio cannot open is structure_mismatch, with FAIL."""
    row = invented.entry("bldg_wsf3d", extension="tif")
    rules = invented.rules_file(tmp_path / "rules.yaml")
    cache = tmp_path / "data" / "public_cache"
    invented.store(cache, row, b"this is not a raster, invented")
    with pytest.raises(HeightError) as err:
        read_sources(cache, (row,), load_rules(rules))
    assert err.value.name == "structure_mismatch"

    buildings = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    buildings.parent.mkdir(parents=True, exist_ok=True)
    buildings.write_bytes(
        invented.buildings_bytes(
            [invented.building_feature("SYN-B-0001", invented.square(0, 0, 1), 30, 8)]
        )
    )
    # The committed rules still mark the live structures unconfirmed, so the
    # step's FAIL line is driven through this confirmed-structure rules file.
    real_build_heights = step.build_heights

    def with_confirmed_rules(*args, **kwargs):
        return real_build_heights(*args, rules_path=rules, **kwargs)

    monkeypatch.setattr(
        "eii_custodian.publicdata.heights.step.build_heights",
        with_confirmed_rules,
    )

    def transport(url: str) -> Response:
        return Response(final_url=url, body=b"this is not a raster, invented", hops=())

    outcome = run_build((row,), transport, cache, _clock, _sleep)
    assert outcome.failure is not None
    assert outcome.failure.check == "structure_mismatch"
    assert any("FAIL heights" in line for line in outcome.lines)


def test_a_receipt_that_is_not_json_is_a_named_refusal(tmp_path: Path) -> None:
    """V2: a receipt that is not JSON is refused as cache_receipt."""
    row = invented.entry("bldg_3dglobfp", extension="geojson")
    cache = tmp_path / "cache"
    invented.store(cache, row, invented.globfp_bytes([(invented.square(0, 0, 1), 7)]))
    meta = next((cache / row.key).glob("*.meta.json"))
    meta.write_text("this is not json {")
    with pytest.raises(HeightError) as err:
        read_sources(
            cache, (row,), load_rules(invented.rules_file(tmp_path / "r.yaml"))
        )
    assert err.value.name == "cache_receipt"


def test_an_exception_the_step_does_not_own_still_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V2: no blanket catch — a KeyError inside a stand-in reader escapes."""
    buildings = tmp_path / "buildings.geojson"
    buildings.write_bytes(
        invented.buildings_bytes(
            [invented.building_feature("SYN-B-0001", invented.square(0, 0, 1), 30, 8)]
        )
    )

    def stand_in(_path):
        raise KeyError("invented programming error")

    monkeypatch.setattr(
        "eii_custodian.publicdata.heights.step.load_buildings", stand_in
    )
    with pytest.raises(KeyError):
        build_heights(tmp_path / "cache", (), buildings, tmp_path / "out", [])


def test_every_registry_row_of_a_source_is_named_in_the_manifest(
    tmp_path: Path,
) -> None:
    """V3: a cached row and an uncached row are each named; state is partial."""
    globfp_row = invented.entry("bldg_3dglobfp", extension="geojson")
    missing = replace(globfp_row, key="bldg_3dglobfp/two", slug="two")
    cache = tmp_path / "data" / "public_cache"
    invented.store(
        cache,
        globfp_row,
        invented.globfp_bytes([(invented.square(0.05, 0.05, 0.6), 7)]),
    )
    buildings = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    buildings.parent.mkdir(parents=True, exist_ok=True)
    buildings.write_bytes(
        invented.buildings_bytes(
            [invented.building_feature("SYN-B-0001", invented.square(0.1, 0.1, 0.5))]
        )
    )
    out_dir = tmp_path / "data" / "assets" / "heights"
    build_heights(
        cache,
        (globfp_row, missing),
        buildings,
        out_dir,
        [],
        invented.rules_file(tmp_path / "rules.yaml"),
    )
    source = _manifest(out_dir)["sources"]["bldg_3dglobfp"]
    assert source["state"] == "partial"
    assert source["reason"] == "not_fetched"
    assert source["rows"] == [
        {"key": "bldg_3dglobfp", "reason": "", "state": "read"},
        {"key": "bldg_3dglobfp/two", "reason": "not_fetched", "state": "not_fetched"},
    ]
    assert _rows(out_dir)[0]["height_m"] == "7.00"
    assert _rows(out_dir)[0]["height_source"] == "3dglobfp"


def test_a_skip_removes_the_outputs_of_an_earlier_run(tmp_path: Path) -> None:
    """V4: after a good run, a later SKIP leaves no heights file behind."""
    out_dir, _ = _card_setup(tmp_path)
    assert (out_dir / "heights.json").is_file()
    assert (out_dir / "manifest.heights.json").is_file()
    lines: list[str] = []
    build_heights(
        tmp_path / "cache",
        (),
        tmp_path / "absent.geojson",
        out_dir,
        lines,
    )
    assert lines == ["SKIP heights building_table_absent"]
    assert not (out_dir / "heights.json").exists()
    assert not (out_dir / "manifest.heights.json").exists()


def test_a_refusal_removes_the_outputs_of_an_earlier_run(tmp_path: Path) -> None:
    """V4: after a good run, a refused table leaves no heights file behind."""
    out_dir, _ = _card_setup(tmp_path)
    buildings = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    buildings.write_bytes(
        invented.buildings_bytes(
            [
                invented.building_feature(
                    "SYN-B-0001",
                    invented.square(0, 0, 1),
                    30,
                    8,
                    extra={"SYN_figure": 7.5},
                )
            ]
        )
    )
    with pytest.raises(HeightError):
        build_heights(tmp_path / "cache", (), buildings, out_dir, [])
    assert not (out_dir / "heights.json").exists()
    assert not (out_dir / "manifest.heights.json").exists()


def test_a_blank_footprint_source_id_is_refused(tmp_path: Path) -> None:
    """V8: an empty or blank footprint_source_id refuses the row."""
    for blank in ("", "   "):
        path = tmp_path / f"blank{len(blank)}.geojson"
        path.write_bytes(
            invented.buildings_bytes(
                [
                    invented.building_feature(
                        "SYN-B-0001",
                        invented.square(0, 0, 1),
                        30,
                        8,
                        source=blank,
                    )
                ]
            )
        )
        with pytest.raises(HeightError) as err:
            load_buildings(path)
        assert err.value.name == "footprint_source_id"


def test_the_manifest_names_the_tables_source_chain_not_a_licence(
    tmp_path: Path,
) -> None:
    """V8: the table record points at the asset pipeline's manifest entry."""
    out_dir, _ = _card_setup(tmp_path)
    record = {f["key"]: f for f in _manifest(out_dir)["files"]}["building_table"]
    assert record["source_chain"] == (
        "the asset pipeline's own manifest entry of the same key and sha256"
    )
    for field in ("licence_id", "licence_basis", "url", "terms_words"):
        assert field not in record


def test_rules_refusals_are_planted_and_named_in_full(tmp_path: Path) -> None:
    """V9: every rules check is planted with its closed reason in full."""

    def mutated(change) -> dict:
        document = invented.rules_document()
        change(document)
        return document

    cases: list[tuple[dict, str]] = [
        (mutated(lambda d: d.update(storey_height_m=5)), "rules_storey"),
        (
            mutated(lambda d: d["storey_height_m"].update(value="not a number")),
            "rules_storey_value",
        ),
        (
            mutated(lambda d: d["storey_height_m"].update(value="1E+60")),
            "rules_storey_value",
        ),
        (
            mutated(lambda d: d["storey_height_m"].update(value="0.004")),
            "rules_storey_value",
        ),
        (mutated(lambda d: d.update(sources=["x"])), "rules_sources"),
        (
            mutated(lambda d: d["sources"].update(bldg_wsf3d="x")),
            "rules_source",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_3dglobfp"].update(band="1")),
            "rules_field_or_band",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_wsf3d"].pop("band")),
            "rules_field_or_band",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_wsf3d"].update(nodata=5)),
            "rules_nodata",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_3dglobfp"].update(format="")),
            "rules_format",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_3dglobfp"].update(field="")),
            "rules_field",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_wsf3d"].update(band="")),
            "rules_band",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_3dglobfp"].update(unit="")),
            "rules_unit",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_3dglobfp"].update(crs="")),
            "rules_crs",
        ),
        (
            mutated(lambda d: d["storey_height_m"].update(basis="")),
            "rules_basis",
        ),
        (mutated(lambda d: d.update(order="")), "rules_order"),
        (
            mutated(lambda d: d.update(match_3dglobfp="")),
            "rules_match_3dglobfp",
        ),
        (mutated(lambda d: d.update(match_wsf3d="")), "rules_match_wsf3d"),
        (
            mutated(lambda d: d.update(credit_3dglobfp="")),
            "rules_credit_3dglobfp",
        ),
    ]
    for index, (document, reason) in enumerate(cases):
        path = invented.write_rules(tmp_path / f"case{index}.yaml", document)
        with pytest.raises(HeightError) as err:
            load_rules(path)
        assert err.value.name == reason, index
    path = invented.write_rules(tmp_path / "list.yaml", ["not", "a", "dict"])
    with pytest.raises(HeightError) as err:
        load_rules(path)
    assert err.value.name == "rules_root"


def test_building_table_refusals_are_planted_and_named_in_full(
    tmp_path: Path,
) -> None:
    """V9: the table loader's refusals are planted with closed reasons."""
    cases: list[tuple[bytes, str]] = [
        (b"this is not json at all {", "building_table"),
        (
            _raw_building_table(
                '{"building_id": "", "recorded_height_m": 30,'
                ' "floor_count": 8, "footprint_source_id": "SYN-FOOT"}'
            ),
            "building_id",
        ),
        (
            _raw_building_table(
                '{"building_id": "SYN-B-0001", "recorded_height_m": 30,'
                ' "floor_count": 8, "footprint_source_id": 7}'
            ),
            "footprint_source_id",
        ),
        (
            invented.buildings_bytes(
                [
                    invented.building_feature(
                        "SYN-B-0001",
                        invented.square(0, 0, 1),
                        30,
                        8,
                        geometry={"type": "Polygon", "coordinates": []},
                    )
                ]
            ),
            "bad_footprint",
        ),
        (
            invented.buildings_bytes(
                [
                    invented.building_feature(
                        "SYN-B-0001",
                        invented.square(0, 0, 1),
                        30,
                        8,
                        geometry={
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]],
                        },
                    )
                ]
            ),
            "bad_footprint",
        ),
    ]
    for index, (body, reason) in enumerate(cases):
        path = tmp_path / f"case{index}.geojson"
        path.write_bytes(body)
        with pytest.raises(HeightError) as err:
            load_buildings(path)
        assert err.value.name == reason, index


def test_cache_refusals_are_planted_and_named_in_full(tmp_path: Path) -> None:
    """V9/V6: receipt, hash and path checks carry their closed reasons."""
    row = invented.entry("bldg_3dglobfp", extension="geojson")
    body = invented.globfp_bytes([(invented.square(0, 0, 1), 7)])
    rules = invented.rules_file(tmp_path / "rules.yaml")

    def run(cache: Path, entry: Entry = row) -> None:
        read_sources(cache, (entry,), load_rules(rules))

    cache = tmp_path / "two" / "cache"
    invented.store(cache, row, body)
    invented.store(cache, row, body + b" invented")
    with pytest.raises(HeightError) as err:
        run(cache)
    assert err.value.name == "cache_receipt"

    cache = tmp_path / "dup" / "cache"
    invented.store(cache, row, body)
    meta = next((cache / row.key).glob("*.meta.json"))
    meta.write_text('{"source_id": "a", "source_id": "b"}')
    with pytest.raises(HeightError) as err:
        run(cache)
    assert err.value.name == "cache_receipt"
    assert err.value.detail == "source_id"

    for change, reason in (
        ({"source_id": "other"}, "cache_receipt_mismatch"),
        ({"publisher": ""}, "cache_receipt_missing"),
        ({"sha256": "abc"}, "malformed_hash"),
    ):
        cache = tmp_path / reason / "cache"
        invented.store(cache, row, body)
        meta = next((cache / row.key).glob("*.meta.json"))
        receipt = json.loads(meta.read_text())
        receipt.update(change)
        meta.write_text(json.dumps(receipt, sort_keys=True) + "\n")
        with pytest.raises(HeightError) as err:
            run(cache)
        assert err.value.name == reason

    outside = invented.entry(
        "bldg_wsf3d", key="bldg_wsf3d/../../outside", extension="tif"
    )
    cache = tmp_path / "escape" / "cache"
    invented.store(
        cache, outside, invented.wsf_bytes(tmp_path / "esc.tif", [[5]], 1, 1)
    )
    with pytest.raises(HeightError) as err:
        run(cache, outside)
    assert err.value.name == "cache_path"


def test_source_structure_refusals_are_planted_and_named_in_full(
    tmp_path: Path,
) -> None:
    """V9/V2: each structure branch of both readers carries its reason."""
    globfp_row = invented.entry("bldg_3dglobfp", extension="geojson")
    wsf_row = invented.entry("bldg_wsf3d", extension="tif")
    rules = invented.rules_file(tmp_path / "rules.yaml")

    def run(index: str, entry: Entry, body: bytes, rules_path: Path = rules) -> None:
        cache = tmp_path / index / "cache"
        invented.store(cache, entry, body)
        read_sources(cache, (entry,), load_rules(rules_path))

    def globfp(features: list, **extra) -> bytes:
        return json.dumps(
            {"type": "FeatureCollection", "features": features, **extra}
        ).encode()

    feature = {"type": "Feature", "properties": {"syn_height_m": 7}}
    globfp_cases: list[tuple[str, bytes, str]] = [
        ("notjson", b"this is not json {", "structure_mismatch"),
        ("notfc", b'{"type": "Feature"}', "structure_mismatch"),
        (
            "featdict",
            b'{"type": "FeatureCollection", "features": {}}',
            "structure_mismatch",
        ),
        (
            "featnum",
            b'{"type": "FeatureCollection", "features": [5]}',
            "structure_mismatch",
        ),
        (
            "proptext",
            globfp([{**feature, "properties": "x"}]),
            "structure_mismatch",
        ),
        (
            "geopoint",
            globfp(
                [
                    {
                        **feature,
                        "geometry": {"type": "Point", "coordinates": [0, 0]},
                    }
                ]
            ),
            "structure_mismatch",
        ),
        (
            "geobad",
            globfp(
                [
                    {
                        **feature,
                        "geometry": {"type": "Polygon", "coordinates": "x"},
                    }
                ]
            ),
            "structure_mismatch",
        ),
        (
            "geoempty",
            globfp(
                [
                    {
                        **feature,
                        "geometry": {"type": "Polygon", "coordinates": []},
                    }
                ]
            ),
            "structure_mismatch",
        ),
        (
            "dupkey",
            b'{"type": "FeatureCollection", "type": "FeatureCollection",'
            b' "features": []}',
            "structure_mismatch",
        ),
        (
            "crs3857",
            globfp([], crs={"properties": {"name": "EPSG:3857"}}),
            "reference_system",
        ),
        (
            "negheight",
            invented.globfp_bytes([(invented.square(0, 0, 1), -3)]),
            "height_value",
        ),
        (
            "textheight",
            invented.globfp_bytes([(invented.square(0, 0, 1), "x")]),
            "height_value",
        ),
    ]
    for index, body, reason in globfp_cases:
        with pytest.raises(HeightError) as err:
            run(f"g-{index}", globfp_row, body)
        assert err.value.name == reason, index

    bad_dtype = tmp_path / "d.tif"
    with rasterio.open(
        bad_dtype,
        "w",
        driver="GTiff",
        width=1,
        height=1,
        count=1,
        dtype="int8",
        crs="EPSG:4326",
        transform=from_origin(0, 1, 1, 1),
        nodata=-1,
    ) as target:
        target.write(np.zeros((1, 1), dtype="int8"), 1)
    no_crs = tmp_path / "c.tif"
    with rasterio.open(
        no_crs,
        "w",
        driver="GTiff",
        width=1,
        height=1,
        count=1,
        dtype="float32",
        transform=from_origin(0, 1, 1, 1),
        nodata=-99999,
    ) as target:
        target.write(np.zeros((1, 1), dtype="float32"), 1)
    wsf_cases: list[tuple[str, bytes, str, Path]] = [
        (
            "nodata",
            invented.wsf_bytes(tmp_path / "n.tif", [[5]], 1, 1, nodata=-1),
            "structure_mismatch",
            rules,
        ),
        ("dtype", bad_dtype.read_bytes(), "structure_mismatch", rules),
        ("nocrs", no_crs.read_bytes(), "reference_system", rules),
        (
            "band",
            invented.wsf_bytes(tmp_path / "b.tif", [[5]], 1, 1),
            "structure_mismatch",
            invented.rules_file(tmp_path / "rb.yaml", wsf_band="x"),
        ),
        (
            "declarednodata",
            invented.wsf_bytes(tmp_path / "dn.tif", [[5]], 1, 1),
            "structure_mismatch",
            invented.rules_file(tmp_path / "rdn.yaml", wsf_nodata="x"),
        ),
    ]
    for index, body, reason, rules_path in wsf_cases:
        with pytest.raises(HeightError) as err:
            run(f"w-{index}", wsf_row, body, rules_path)
        assert err.value.name == reason, index


def test_the_writer_refusal_output_row_is_planted() -> None:
    """V9: a sourced row with no height or with a reason is refused."""
    row = {
        "building_id": "SYN-B-0001",
        "height_m": None,
        "height_source": "recorded",
        "footprint_source_id": "SYN-FOOT",
        "reason": "",
    }
    with pytest.raises(HeightError) as err:
        check_row(dict(row))
    assert err.value.name == "output_row"
    row["height_m"], row["reason"] = "30.00", "order_exhausted"
    with pytest.raises(HeightError) as err:
        check_row(dict(row))
    assert err.value.name == "output_row"
