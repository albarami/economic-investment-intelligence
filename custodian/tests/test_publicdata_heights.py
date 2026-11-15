"""S2-T20: the heights step end to end, its contract, rules, readers and fetch.

Every fixture is hand-made: invented buildings SYN-B-*, invented files and a
tiny invented raster, written only into temporary folders (FE-95). The worked
fixture is card C42's worked example; its error block is the card's.
"""

from __future__ import annotations

import ast
import inspect
import json
import zipfile
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

from eii_core.calc.building_heights import (
    choose_height,
    floor_height,
    height_counts,
    height_value,
    metres,
)
from eii_custodian.publicdata import heights as heights_package
from eii_custodian.publicdata.fetch.allowlist import ALLOWED_HOSTS, approve
from eii_custodian.publicdata.fetch.build import run_build
from eii_custodian.publicdata.fetch.kinds import Prepared, prepare
from eii_custodian.publicdata.fetch.receipts import sha256_hex
from eii_custodian.publicdata.fetch.registry import Entry, load_registry
from eii_custodian.publicdata.fetch.transport import Response
from eii_custodian.publicdata.heights.manifest import (
    ESTIMATE_LABEL,
    check_row,
)
from eii_custodian.publicdata.heights.match import (
    globfp_candidates,
    globfp_height,
    globfp_index,
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
from eii_custodian.publicdata.heights.read import (
    WsfGrid,
    read_sources,
    sha256_path,
)
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
    globfp_row = invented.entry("bldg_3dglobfp", extension="zip")
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
    assert block["tied_height_buildings"] == 0
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


def test_the_real_doc04_credit_is_the_real_manifest_credit(tmp_path: Path) -> None:
    """R2/F6: document 04's credit, the rules file and the manifest tie.

    The template is read from document 04's own attribution row, never
    restated here, and the manifest is built with the committed rules file
    and the fixtures' invented retrieval date, so a wrong real
    `credit_3dglobfp` template cannot pass.
    """
    pack = (REPO / "docs" / "04_PUBLIC_DATA_PACK.md").read_text(encoding="utf-8")
    template = ""
    for line in pack.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) > 3 and cells[1] == "CC BY 4.0" and cells[2] == "`bldg_3dglobfp`":
            quoted = cells[3]
            assert quoted.startswith('"')
            assert quoted.endswith('"')
            template = quoted[1:-1]
    assert template == load_rules(RULES_PATH).credit_3dglobfp
    for entry in _heights_entries(load_registry()):
        assert entry.licence_id == "CC-BY-4.0"
        assert entry.licence_basis == "dataset"
    globfp_row = invented.entry("bldg_3dglobfp", extension="zip")
    cache = tmp_path / "cache"
    invented.store(
        cache,
        globfp_row,
        invented.globfp_zip([(invented.square(0.05, 0.05, 0.6), "7")]),
    )
    buildings = tmp_path / "buildings.geojson"
    buildings.write_bytes(
        invented.buildings_bytes(
            [invented.building_feature("SYN-B-0001", invented.square(0.1, 0.1, 0.5))]
        )
    )
    out_dir = tmp_path / "out"
    build_heights(cache, (globfp_row,), buildings, out_dir, [], RULES_PATH)
    credit = _manifest(out_dir)["credits"]["bldg_3dglobfp"]["credit"]
    assert credit == template.replace("{date}", "2026-11-14")


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
    assert globfp["url"].startswith(f"https://{invented.ALLOWED_HOST}/")
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


def test_the_committed_rules_read_both_sources_not_fetched(
    tmp_path: Path,
) -> None:
    """The committed structures are confirmed; unfetched rows are absent."""
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
    assert rows["SYN-B-0001"]["reason"] == "not_fetched"
    assert rows["SYN-B-0002"]["height_m"] == "30.00"
    block = _manifest(out_dir)
    assert block["sources"]["bldg_3dglobfp"]["reason"] == "not_fetched"
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


def test_the_committed_rules_file_loads_with_the_declared_structures() -> None:
    """The committed file parses; the declared values name the real forms."""
    rules = load_rules(RULES_PATH)
    assert rules.storey_height == Decimal("3.0")
    assert rules.label == "ASSUMPTION"
    globfp = rules.structures["bldg_3dglobfp"]
    assert globfp.format == "shapefile_zip"
    assert globfp.field == "Height"
    assert globfp.unit == "m"
    assert globfp.crs == "EPSG:4326"
    wsf = rules.structures["bldg_wsf3d"]
    assert wsf.format == "GTiff"
    assert wsf.band == "1"
    assert wsf.unit == "m"
    assert wsf.nodata == "-32767"
    assert wsf.scale == "0.1"
    assert wsf.crs == "EPSG:4326"
    assert wsf.dtype == "int16"


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
    index = globfp_index(files)
    assert globfp_candidates(point, building, index) == []
    assert globfp_height(point, building, index) is None


def test_the_larger_overlap_wins_and_residual_ties_are_broken() -> None:
    """Largest overlap wins; ties take the lowest file, then the lowest row."""
    building = _polygon(invented.square(0, 0, 1))
    point = representative_point(building)
    whole = _polygon(invented.square(-0.5, -0.5, 2))
    part = _polygon(invented.square(0.5, 0.5, 1))
    files = (("one", ((part, Decimal(8)), (whole, Decimal(9)))),)
    assert globfp_height(point, building, globfp_index(files)) == Decimal(9)
    across = (
        ("b", ((whole, Decimal(8)),)),
        ("a", ((whole, Decimal(9)),)),
    )
    assert globfp_height(point, building, globfp_index(across)) == Decimal(9)
    same_file = (("a", ((whole, Decimal(8)), (whole, Decimal(9)))),)
    assert globfp_height(point, building, globfp_index(same_file)) == Decimal(8)


def _grid(values, width, height, nodata=Decimal("-99999"), scale=Decimal("1")):
    from rasterio.transform import from_origin

    return WsfGrid(
        transform=from_origin(0, 1, 1, 1),
        data=np.array(values, dtype="float32").reshape(height, width),
        nodata=nodata,
        width=width,
        height=height,
        scale=scale,
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


def _sources(tmp_path: Path, entries, rules=None, bodies=(), bounds=None):
    """Run read_sources over stored fixtures."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    cache = tmp_path / "cache"
    for entry, body in bodies:
        invented.store(cache, entry, body)
    return read_sources(
        cache,
        entries,
        load_rules(rules or invented.rules_file(tmp_path / "rules.yaml")),
        bounds=bounds,
    )


def test_read_refusals_and_absent_reasons(tmp_path: Path) -> None:
    """B6: hash and receipt defects refuse; skip and not_fetched are absent."""
    row = invented.entry("bldg_3dglobfp", extension="zip")
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
    row = invented.entry("bldg_3dglobfp", extension="zip")
    body = invented.globfp_zip([(invented.square(0, 0, 1), "7")])
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
    globfp_row = invented.entry("bldg_3dglobfp", extension="zip")
    missing_field = invented.globfp_zip(
        [(invented.square(0, 0, 1), "7")], field="other_name"
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
    row = invented.entry("bldg_3dglobfp", extension="zip")
    body = invented.globfp_zip([(invented.square(0, 0, 1), "7")])
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


def _heights_entries(loaded: tuple[Entry, ...]) -> list[Entry]:
    return [
        entry for entry in loaded if entry.source_id in {"bldg_3dglobfp", "bldg_wsf3d"}
    ]


def test_committed_rows_load_with_their_basis_and_no_credit() -> None:
    """Criterion 4: the three rows load with their licences and no credit."""
    entries = _heights_entries(load_registry())
    assert [entry.key for entry in entries] == [
        "bldg_3dglobfp/1636",
        "bldg_3dglobfp/1639",
        "bldg_wsf3d",
    ]
    for entry in entries:
        assert entry.source_id in {"bldg_3dglobfp", "bldg_wsf3d"}
        assert entry.licence_id == "CC-BY-4.0"
        assert entry.licence_basis == "dataset"
        assert entry.decision_record == ""
        assert "credit" not in vars(entry)
        assert entry.kind == "https_file"
        assert entry.commit_allowed is False
        assert entry.nightly_live_fetch is False
        assert entry.skip_reason == ""
        assert entry.row_count_min is None
        assert entry.row_count_max is None
        assert entry.terms_watch is False
    globfp = entries[0]
    assert globfp.fetch_host == "ndownloader.figshare.com"
    assert globfp.extension == "zip"
    wsf = entries[2]
    assert wsf.fetch_host == "download.geoservice.dlr.de"
    assert wsf.extension == "tif"
    pack = (REPO / "docs" / "04_PUBLIC_DATA_PACK.md").read_text()
    assert '"Che et al. 2024"' in pack
    document = yaml.safe_load(
        (REPO / "custodian" / "publicdata" / "sources.yaml").read_text()
    )
    rows = [
        row
        for row in document["sources"]
        if row["source_id"] in {"bldg_3dglobfp", "bldg_wsf3d"}
    ]
    assert all("credit" not in row for row in rows)


def test_committed_rows_carry_no_row_count_bounds(tmp_path: Path) -> None:
    """R9(a): the count check reads JSON only; a planted bound fails."""
    entries = _heights_entries(load_registry())
    assert all(
        entry.row_count_min is None and entry.row_count_max is None for entry in entries
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
        )
    )


def _admit_invented_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """Admit the fixtures' invented host for this test only (F7).

    The host is reserved and invented (`syn-heights.invalid`); no test
    widens the committed allow-list, and the off-list host of the refusal
    plants is still refused in this module.
    """
    monkeypatch.setattr(
        "eii_custodian.publicdata.fetch.allowlist.ALLOWED_HOSTS",
        ALLOWED_HOSTS | {invented.ALLOWED_HOST},
    )


def test_non_commercial_terms_never_block_the_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Criterion 5: a non-commercial row loads, fetches and gives its height."""
    _admit_invented_host(monkeypatch)
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
    wsf = invented.wsf_bytes(tmp_path / "w.tif", [[420]], 1, 1)

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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B9: each row is fetched and stored; bytes stay in the cache (FE-95)."""
    _admit_invented_host(monkeypatch)
    rows = [
        invented.entry("bldg_3dglobfp", extension="zip"),
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


def test_a_signed_redirect_query_reaches_no_receipt_manifest_log_or_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F1/rule 14: a signed storage redirect stores scheme, host and path only.

    The invented redirect answers with an address whose query carries signed
    parameters; no query and no word of it reaches the receipt, the manifest,
    the build log or an error text, and the hops never appear anywhere.
    """
    _admit_invented_host(monkeypatch)
    row = invented.entry("bldg_3dglobfp", extension="zip")
    signature_words = ("X-Amz", "SYN-INVENTED-SIGNATURE", "SYN-INVENTED-KEY")
    signed_final = (
        f"https://{invented.ALLOWED_HOST}/SYN/signed-tile.zip"
        "?X-Amz-Algorithm=SYN-INVENTED&X-Amz-Signature=SYN-INVENTED-SIGNATURE"
        "&X-Amz-Credential=SYN-INVENTED-KEY"
    )
    signed_hop = (
        f"https://{invented.ALLOWED_HOST}/SYN/hop?X-Amz-Signature=SYN-INVENTED-HOP"
    )
    globfp = invented.globfp_zip([(invented.square(0.05, 0.05, 0.6), "7")])

    def transport(url: str) -> Response:
        assert url == row.url
        return Response(final_url=signed_final, body=globfp, hops=(signed_hop,))

    cache = tmp_path / "data" / "public_cache"
    buildings = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    buildings.parent.mkdir(parents=True, exist_ok=True)
    buildings.write_bytes(
        invented.buildings_bytes(
            [invented.building_feature("SYN-B-0001", invented.square(0.1, 0.1, 0.5))]
        )
    )
    outcome = run_build((row,), transport, cache, _clock, _sleep)
    assert outcome.failure is None
    receipt_path = next((cache / row.key).glob("*.meta.json"))
    receipt_text = receipt_path.read_text()
    receipt = json.loads(receipt_text)
    public_final = f"https://{invented.ALLOWED_HOST}/SYN/signed-tile.zip"
    assert receipt["fetch_url"] == public_final
    manifest_text = (
        tmp_path / "data" / "assets" / "heights" / "manifest.heights.json"
    ).read_text()
    manifest = json.loads(manifest_text)
    record = next(
        found for found in manifest["files"] if found["key"] == "bldg_3dglobfp"
    )
    assert record["url"] == public_final
    for text in (receipt_text, manifest_text):
        for word in signature_words:
            assert word not in text
        assert "?" not in text
    for line in outcome.lines:
        for word in signature_words:
            assert word not in line
        assert "SYN/signed-tile.zip?" not in line
    log_text = (cache / "build-log.json").read_text()
    for word in signature_words:
        assert word not in log_text

    # The error text of a refused row carries the public form only.
    refused = replace(
        row,
        key="bldg_3dglobfp/two",
        slug="two",
        row_count_min=1,
    )

    def refused_transport(url: str) -> Response:
        assert url == refused.url
        return Response(final_url=signed_final, body=b"not json, invented", hops=())

    refused_outcome = run_build(
        (refused,), refused_transport, tmp_path / "second" / "cache", _clock, _sleep
    )
    assert refused_outcome.failure is not None
    assert refused_outcome.failure.url == public_final
    fail_line = next(line for line in refused_outcome.lines if line.startswith("FAIL"))
    assert public_final in fail_line
    for word in signature_words:
        assert word not in fail_line
    assert "?" not in fail_line


_SIGNED_QUERY_WORDS = ("X-Amz", "SYN-INVENTED-SIGNATURE", "SYN-INVENTED-KEY")


def _signed_final_url() -> str:
    """A final address whose query carries invented signed credentials."""
    return (
        f"https://{invented.ALLOWED_HOST}/SYN/signed-tile.zip"
        "?X-Amz-Algorithm=SYN-INVENTED&X-Amz-Signature=SYN-INVENTED-SIGNATURE"
        "&X-Amz-Credential=SYN-INVENTED-KEY"
    )


def _public_final_url() -> str:
    """The public form of the signed final address: scheme, host and path."""
    return f"https://{invented.ALLOWED_HOST}/SYN/signed-tile.zip"


def test_the_file_kind_returns_no_query_of_a_signed_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P1(a)/rule 14: the file kind itself returns the public form only.

    The transport answers a file row with a final address whose query holds
    invented signed credentials; the address `_file` returns holds scheme,
    host and path only, whichever later line guards the stored receipt.
    """
    _admit_invented_host(monkeypatch)
    row = invented.entry("bldg_3dglobfp", extension="zip")

    def transport(url: str) -> Response:
        assert url == row.url
        return Response(final_url=_signed_final_url(), body=b"invented body", hops=())

    prepared = prepare(row, transport, _sleep)
    assert prepared.failure is None
    assert prepared.fetch_url == _public_final_url()
    assert "?" not in prepared.fetch_url
    for word in _SIGNED_QUERY_WORDS:
        assert word not in prepared.fetch_url


def test_fetch_row_stores_no_query_whatever_address_the_fetcher_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P1(b)/rule 14: the stored address of a file row is the public form.

    A stand-in fetcher hands `_fetch_row` a prepared result whose address
    still carries an invented signed query; the receipt, the manifest line
    and the log line hold no query, whichever earlier line guards the
    fetched address.
    """
    _admit_invented_host(monkeypatch)
    row = invented.entry("bldg_3dglobfp", extension="zip")
    globfp = invented.globfp_zip([(invented.square(0.05, 0.05, 0.6), "7")])

    def stand_in(_entry: Entry, _transport: object, _sleep: object) -> Prepared:
        """The stand-in fetcher: a prepared result with a signed address."""
        return Prepared(
            body=globfp,
            fetch_url=_signed_final_url(),
            fetch_host=invented.ALLOWED_HOST,
            publisher="SYN-publisher",
            source_modified="",
            row_count=None,
            terms_sha256="",
            failure=None,
        )

    monkeypatch.setattr(
        "eii_custodian.publicdata.fetch.build.prepare",
        stand_in,
    )

    def no_transport(url: str) -> Response:
        raise AssertionError("the stand-in fetcher must answer this row")

    cache = tmp_path / "data" / "public_cache"
    buildings = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    buildings.parent.mkdir(parents=True, exist_ok=True)
    buildings.write_bytes(
        invented.buildings_bytes(
            [invented.building_feature("SYN-B-0001", invented.square(0.1, 0.1, 0.5))]
        )
    )
    outcome = run_build((row,), no_transport, cache, _clock, _sleep)
    assert outcome.failure is None
    receipt_path = next((cache / row.key).glob("*.meta.json"))
    receipt_text = receipt_path.read_text()
    receipt = json.loads(receipt_text)
    assert receipt["fetch_url"] == _public_final_url()
    assert "?" not in receipt_text
    manifest_text = (
        tmp_path / "data" / "assets" / "heights" / "manifest.heights.json"
    ).read_text()
    manifest = json.loads(manifest_text)
    record = next(
        found for found in manifest["files"] if found["key"] == "bldg_3dglobfp"
    )
    assert record["url"] == _public_final_url()
    assert "?" not in manifest_text
    log_text = (cache / "build-log.json").read_text()
    for text in (receipt_text, manifest_text, log_text):
        for word in _SIGNED_QUERY_WORDS:
            assert word not in text
        assert "SYN/signed-tile.zip?" not in text


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
    globfp_row = invented.entry("bldg_3dglobfp", extension="zip")
    globfp = invented.globfp_zip(
        [
            (invented.square(0.05, 0.05, 0.6), "1.01"),
            (invented.square(1.05, 0.05, 0.6), "1.01"),
            (invented.square(2.05, 0.05, 0.6), "1.02"),
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
        cache, wsf_row, invented.wsf_bytes(tmp_path / "w.tif", [[0, 50]], 2, 1)
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


def test_a_nan_wsf_cell_is_no_value_not_a_crash() -> None:
    """V1/F2: a non-finite cell of a directly built grid is no value, counted.

    The source file's stored type is declared and enforced (F2), so a
    non-finite cell can no longer arrive through the reader; the value rule
    itself is exercised on a directly built invented grid, as the fix says.
    """
    grid = _grid([[float("nan")]], 1, 1)
    value = wsf_value(grid, Point(0.5, 0.5))
    assert value is not None
    assert not value.is_finite()
    assert height_value(value) is None
    choice = choose_height(
        {
            "recorded": None,
            "floor_count": None,
            "3dglobfp": None,
            "wsf3d": value,
        }
    )
    assert choice.source == "none"
    assert choice.reason == "order_exhausted"
    assert choice.dropped == ("wsf3d",)
    counts = height_counts([choice], [[]])
    assert counts.no_value_reasons == {"wsf3d_value_not_positive": 1}


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
    _admit_invented_host(monkeypatch)
    row = invented.entry("bldg_wsf3d", extension="tif")
    rules = invented.rules_file(tmp_path / "rules.yaml")
    cache = tmp_path / "data" / "public_cache"
    invented.store(cache, row, b"this is not a raster, invented")
    with pytest.raises(HeightError) as err:
        read_sources(cache, (row,), load_rules(rules), bounds=None)
    assert err.value.name == "structure_mismatch"

    buildings = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    buildings.parent.mkdir(parents=True, exist_ok=True)
    buildings.write_bytes(
        invented.buildings_bytes(
            [invented.building_feature("SYN-B-0001", invented.square(0, 0, 1), 30, 8)]
        )
    )

    def transport(url: str) -> Response:
        return Response(final_url=url, body=b"this is not a raster, invented", hops=())

    outcome = run_build((row,), transport, cache, _clock, _sleep)
    assert outcome.failure is not None
    assert outcome.failure.check == "structure_mismatch"
    assert any("FAIL heights" in line for line in outcome.lines)


def test_a_receipt_that_is_not_json_is_a_named_refusal(tmp_path: Path) -> None:
    """V2: a receipt that is not JSON is refused as cache_receipt."""
    row = invented.entry("bldg_3dglobfp", extension="zip")
    cache = tmp_path / "cache"
    invented.store(cache, row, invented.globfp_zip([(invented.square(0, 0, 1), "7")]))
    meta = next((cache / row.key).glob("*.meta.json"))
    meta.write_text("this is not json {")
    with pytest.raises(HeightError) as err:
        read_sources(
            cache,
            (row,),
            load_rules(invented.rules_file(tmp_path / "r.yaml")),
            bounds=None,
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


def test_a_programming_error_inside_the_shape_reader_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F3/V2: a KeyError in the pinned shape reader is never a data refusal.

    Only the parse failures a malformed shape file or index provably raises
    are refused as `structure_mismatch`; a programming error of the reader
    leaves the step unchanged.
    """
    body = invented.globfp_zip([(invented.square(0, 0, 1), "7")])

    def stand_in(*_args, **_kwargs):
        raise KeyError("invented programming error")

    monkeypatch.setattr("shapefile.Reader", stand_in)
    row = invented.entry("bldg_3dglobfp", extension="zip")
    with pytest.raises(KeyError):
        _sources(tmp_path, (row,), None, ((row, body),))


def test_a_programming_error_inside_the_geometry_conversion_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F3/V2: a KeyError in the geometry conversion is never a data refusal.

    Only a record whose rings no converter can read is refused as
    `structure_mismatch`; a programming error of the conversion leaves the
    step unchanged.
    """
    body = invented.globfp_zip([(invented.square(0, 0, 1), "7")])

    def stand_in(*_args, **_kwargs):
        raise KeyError("invented programming error")

    monkeypatch.setattr("shapely.geometry.shape", stand_in)
    row = invented.entry("bldg_3dglobfp", extension="zip")
    with pytest.raises(KeyError):
        _sources(tmp_path, (row,), None, ((row, body),))


def test_every_registry_row_of_a_source_is_named_in_the_manifest(
    tmp_path: Path,
) -> None:
    """V3: a cached row and an uncached row are each named; state is partial."""
    globfp_row = invented.entry("bldg_3dglobfp", extension="zip")
    missing = replace(globfp_row, key="bldg_3dglobfp/two", slug="two")
    cache = tmp_path / "data" / "public_cache"
    invented.store(
        cache,
        globfp_row,
        invented.globfp_zip([(invented.square(0.05, 0.05, 0.6), "7")]),
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
            mutated(lambda d: d["sources"]["bldg_wsf3d"].pop("scale")),
            "rules_missing_key",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_wsf3d"].update(scale="")),
            "rules_scale",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_wsf3d"].update(scale=1)),
            "rules_scale",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_3dglobfp"].update(scale="0.1")),
            "rules_field_or_band",
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
        (
            # The storey block's own unknown-key plant.
            mutated(lambda d: d["storey_height_m"].update(invented=1)),
            "rules_unknown_key",
        ),
        (
            # The storey block's own missing-key plant.
            mutated(lambda d: d["storey_height_m"].pop("label")),
            "rules_missing_key",
        ),
        (
            # The required structure keys' own plant: a source without a
            # required key of the declared form.
            mutated(lambda d: d["sources"]["bldg_wsf3d"].pop("unit")),
            "rules_missing_key",
        ),
        (
            # The band form's own dtype plants (F2): a band source declares
            # its stored type, and the field form carries none.
            mutated(lambda d: d["sources"]["bldg_wsf3d"].pop("dtype")),
            "rules_missing_key",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_wsf3d"].update(dtype="")),
            "rules_dtype",
        ),
        (
            mutated(lambda d: d["sources"]["bldg_3dglobfp"].update(dtype="int16")),
            "rules_field_or_band",
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
            # The features-not-a-list shape guard's own plant.
            json.dumps({"type": "FeatureCollection", "features": {}}).encode(),
            "building_table",
        ),
        (
            # The non-dict feature shape guard's own plant.
            json.dumps({"type": "FeatureCollection", "features": [7]}).encode(),
            "building_table",
        ),
        (
            # The non-dict properties shape guard's own plant.
            _raw_building_table("7"),
            "missing_property",
        ),
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


def test_an_unreadable_building_table_is_a_named_refusal(tmp_path: Path) -> None:
    """V9/F4: the table's read failure has its own plant, refused by name."""
    with pytest.raises(HeightError) as err:
        load_buildings(tmp_path)  # a directory, so the read itself fails
    assert err.value.name == "building_table"


def test_cache_refusals_are_planted_and_named_in_full(tmp_path: Path) -> None:
    """V9/V6: receipt, hash and path checks carry their closed reasons."""
    row = invented.entry("bldg_3dglobfp", extension="zip")
    body = invented.globfp_zip([(invented.square(0, 0, 1), "7")])
    rules = invented.rules_file(tmp_path / "rules.yaml")

    def run(cache: Path, entry: Entry = row) -> None:
        read_sources(cache, (entry,), load_rules(rules), bounds=None)

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

    # The receipt-shape guard's own plant (F4): valid JSON that is not an
    # object is refused as a receipt, not read as one.
    cache = tmp_path / "nondict" / "cache"
    invented.store(cache, row, body)
    meta = next((cache / row.key).glob("*.meta.json"))
    meta.write_text('["valid json", "not an object"]')
    with pytest.raises(HeightError) as err:
        run(cache)
    assert err.value.name == "cache_receipt"

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
    globfp_row = invented.entry("bldg_3dglobfp", extension="zip")
    wsf_row = invented.entry("bldg_wsf3d", extension="tif")
    rules = invented.rules_file(tmp_path / "rules.yaml")

    def run(index: str, entry: Entry, body: bytes, rules_path: Path = rules) -> None:
        cache = tmp_path / index / "cache"
        invented.store(cache, entry, body)
        read_sources(cache, (entry,), load_rules(rules_path), bounds=None)

    ring = invented.square(0, 0, 1)
    projected_wkt = (
        b'PROJCS["WGS_1984_Web_Mercator_Auxiliary_Sphere",'
        b'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
        b'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
        b'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
        b'PROJECTION["Mercator_Auxiliary_Sphere"],'
        b'PARAMETER["False_Easting",0.0],PARAMETER["False_Northing",0.0],'
        b'PARAMETER["Central_Meridian",0.0],PARAMETER["Standard_Parallel_1",0.0],'
        b'PARAMETER["Auxiliary_Sphere_Type",0.0],UNIT["Meter",1.0]]'
    )
    other_datum_wkt = (
        b'GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",'
        b'SPHEROID["GRS_1980",6378137.0,298.257222101]],'
        b'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
    )

    def members(**changes) -> dict:
        bodies = invented.shapefile_members([[invented.cw(ring)]], [["1", "7", ""]])
        bodies.update(changes)
        return bodies

    def zipped(
        bodies: dict, stem: str = "syn.tile.01", extra: dict | None = None
    ) -> bytes:
        out = {f"{stem}.{ext}": body for ext, body in bodies.items()}
        out.update(extra or {})
        return invented.zip_members(out)

    offset, size = invented.dbf_field_offset(members()["dbf"], "Height")

    def dbf_change(row: int, at: int, text: bytes) -> bytes:
        return invented.dbf_patch(members()["dbf"], row, at, text)

    def dbf_set(at: int, value: int) -> bytes:
        """Patch one byte of the invented table (planted header forms, F4)."""
        raw = bytearray(members()["dbf"])
        raw[at] = value
        return bytes(raw)

    def count_change(count: int) -> bytes:
        raw = bytearray(members()["dbf"])
        raw[4:8] = count.to_bytes(4, "little")
        return bytes(raw)

    def one_record_dbf() -> dict:
        """A dbf whose header count matches its one record, beside two shapes.

        The record-count check's own plant: the table is self-consistent, so
        only the `.shp` row count differs from the `.dbf` records.
        """
        bodies = invented.shapefile_members(
            [[invented.cw(ring)], [invented.cw(invented.square(5, 5, 1))]],
            [["1", "7", ""], ["2", "9", ""]],
        )
        raw = bytearray(bodies["dbf"])
        raw[4:8] = (1).to_bytes(4, "little")
        header_len = int.from_bytes(raw[8:10], "little")
        record_len = int.from_bytes(raw[10:12], "little")
        bodies["dbf"] = bytes(raw[: header_len + record_len])
        return bodies

    # A bow-tie ring that crosses itself, the `is_valid` check's own plant.
    self_crossing = [[0, 0], [2, 2], [2, 0], [0, 2], [0, 0]]

    globfp_cases: list[tuple[str, bytes, str]] = [
        ("notzip", b"this is not a zip {", "structure_mismatch"),
        (
            "fourmembers",
            zipped({k: v for k, v in members().items() if k != "cpg"}),
            "structure_mismatch",
        ),
        (
            "sixmembers",
            zipped(members(), extra={"six.txt": b"x"}),
            "structure_mismatch",
        ),
        (
            "nested",
            zipped(members(), extra={"folder/syn.tile.01.cpg": b"x"}),
            "structure_mismatch",
        ),
        (
            # The folder check's own plant: five members, one stem, one
            # folder, so only the folder clause refuses this body.
            "folder",
            invented.shapefile_zip(
                [[invented.cw(ring)]], [["1", "7", ""]], stem="folder/syn.tile.01"
            ),
            "structure_mismatch",
        ),
        (
            # The compression-method check's own plant: five flat members of
            # one stem, every one compressed with a method never published.
            "bzip2",
            invented.zip_members(
                {f"syn.tile.01.{ext}": body for ext, body in members().items()},
                compression=zipfile.ZIP_BZIP2,
            ),
            "structure_mismatch",
        ),
        (
            "twostems",
            zipped(
                {k: v for k, v in members().items() if k != "prj"},
                extra={"other.prj": invented.WGS84_PRJ},
            ),
            "structure_mismatch",
        ),
        (
            "missingdbf",
            zipped({k: v for k, v in members().items() if k != "dbf"}),
            "structure_mismatch",
        ),
        (
            "badcpg",
            zipped(members(cpg=b"UTF-8")),
            "structure_mismatch",
        ),
        (
            "encrypted",
            invented.zip_flag_patch(zipped(members()), 1),
            "structure_mismatch",
        ),
        (
            # The extraction-failure check's own plant (F4): the declared
            # sizes all stand, so every earlier check passes and only the
            # member's own read fails on the corrupted stream.
            "extractfail",
            invented.zip_stream_corrupt(zipped(members()), "syn.tile.01.prj"),
            "structure_mismatch",
        ),
        (
            # The member-count clause's own plant (F4): six flat members of
            # one stem, two of them the same `.dbf` name.
            "duplicatedb",
            invented.zip_members_duplicated(
                {f"syn.tile.01.{ext}": body for ext, body in members().items()},
                "syn.tile.01.dbf",
            ),
            "structure_mismatch",
        ),
        (
            # The member-set clause's own plant (F4): five members of one
            # stem, one `.dbf` name twice and no `.cpg`, so only the member
            # set itself differs from the published form.
            "duplicateset",
            invented.zip_members_duplicated(
                {f"syn.tile.01.{ext}": body for ext, body in members().items()},
                "syn.tile.01.dbf",
                drop="cpg",
            ),
            "structure_mismatch",
        ),
        (
            "badprj",
            zipped(members(prj=b"not a wkt at all")),
            "reference_system",
        ),
        (
            "projectedprj",
            zipped(members(prj=projected_wkt)),
            "reference_system",
        ),
        (
            "otherdatum",
            zipped(members(prj=other_datum_wkt)),
            "reference_system",
        ),
        (
            "missingfield",
            invented.globfp_zip([(ring, "7")], field="other_name"),
            "structure_mismatch",
        ),
        (
            "fieldwrongtype",
            invented.shapefile_zip(
                [[invented.cw(ring)]],
                [["1", "7", ""]],
                [["FID", "N", 18, 0], ["Height", "C", 24, 0], ["FID_1", "N", 24, 15]],
            ),
            "structure_mismatch",
        ),
        (
            "deletedrow",
            zipped(members(dbf=dbf_change(0, 0, b"*"))),
            "structure_mismatch",
        ),
        (
            "truncateddbf",
            zipped(members(dbf=members()["dbf"][:-5])),
            "structure_mismatch",
        ),
        (
            # A table cut inside its own header: the declared header is
            # longer than the bytes, so the length must be checked before
            # the terminator byte is read.
            "cutinsideheader",
            zipped(members(dbf=members()["dbf"][:100])),
            "structure_mismatch",
        ),
        (
            # The minimum-length clause's own plant (F4): a table shorter
            # than its own header arithmetic.
            "shortdbf",
            zipped(members(dbf=b"cut inside the invented header")),
            "structure_mismatch",
        ),
        (
            # The version clause's own plant (F4): a version byte the
            # published form never writes.
            "versionbyte",
            zipped(members(dbf=dbf_set(0, 0x30))),
            "structure_mismatch",
        ),
        (
            # The descriptor-decoding branch's own plant (F4): a field
            # descriptor whose name holds a byte no ASCII table writes.
            "descriptor",
            zipped(members(dbf=dbf_set(32 + 2, 0xC3))),
            "structure_mismatch",
        ),
        (
            # The record-layout offset check's own plant (F4): the first
            # field's declared size is one byte short of the record length,
            # so the field sizes no longer sum to the record layout.
            "offsetlayout",
            zipped(members(dbf=dbf_set(32 + 16, 17))),
            "structure_mismatch",
        ),
        (
            # The record-count line's own plant: the header count matches
            # the one dbf record, but the shapefile holds two shapes.
            "shapemismatch",
            zipped(one_record_dbf()),
            "structure_mismatch",
        ),
        (
            "countmismatch",
            zipped(members(dbf=count_change(5))),
            "structure_mismatch",
        ),
        (
            "nullshape",
            invented.shapefile_zip(
                [None],
                [["1", "7", ""]],
            ),
            "structure_mismatch",
        ),
        (
            "pointshape",
            invented.shapefile_zip(
                [[1, 1]],
                [["1", "7", ""]],
                shape_type=__import__("shapefile").POINT,
            ),
            "structure_mismatch",
        ),
        (
            # The validity check's own plant: a polygon that crosses itself.
            "selfcrossing",
            invented.shapefile_zip([[self_crossing]], [["1", "7", ""]]),
            "structure_mismatch",
        ),
        (
            "negheight",
            invented.globfp_zip([(ring, "-3")]),
            "height_value",
        ),
        (
            "zeroheight",
            invented.globfp_zip([(ring, "0")]),
            "height_value",
        ),
        (
            "textheight",
            zipped(members(dbf=dbf_change(0, offset, b"x" * size))),
            "height_value",
        ),
        (
            "blankheight",
            zipped(members(dbf=dbf_change(0, offset, b" " * size))),
            "height_value",
        ),
        (
            "nanheight",
            zipped(members(dbf=dbf_change(0, offset, b"NaN".rjust(size)))),
            "height_value",
        ),
        (
            "starheight",
            zipped(members(dbf=dbf_change(0, offset, b"*" * size))),
            "height_value",
        ),
        (
            "exponentheight",
            zipped(members(dbf=dbf_change(0, offset, b"1e2".rjust(size)))),
            "height_value",
        ),
        (
            "underscoreheight",
            zipped(members(dbf=dbf_change(0, offset, b"1_0".rjust(size)))),
            "height_value",
        ),
        (
            "signedheight",
            zipped(members(dbf=dbf_change(0, offset, b"+7".rjust(size)))),
            "height_value",
        ),
        (
            # The record-text decoding branch's own plant (F4): a record
            # whose height text holds a byte no ASCII table writes.
            "nonascii",
            zipped(members(dbf=dbf_change(0, offset, b"\xc3\xa9".rjust(size)))),
            "height_value",
        ),
        (
            # The shape-reader catch's own plants (F3/F4): a cut index, and
            # a record whose point count no published file writes. The cut
            # is past the eight-byte header word but short of the first
            # index record, so pyshp's index unpack raises struct.error.
            "truncshx",
            zipped(members(shx=members()["shx"][:20])),
            "structure_mismatch",
        ),
        (
            "emptypoints",
            zipped(members(shp=invented.shp_record_numpoints(members()["shp"], 0))),
            "structure_mismatch",
        ),
        (
            # The geometry-conversion catch's own plants (F3/F4): a
            # one-point ring and a two-point ring, both refused by name.
            "onepoint",
            zipped(members(shp=invented.shp_record_numpoints(members()["shp"], 1))),
            "structure_mismatch",
        ),
        (
            "shortring",
            zipped(members(shp=invented.shp_record_numpoints(members()["shp"], 2))),
            "structure_mismatch",
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
        dtype="int16",
        transform=from_origin(0, 1, 1, 1),
        nodata=-32767,
    ) as target:
        target.write(np.zeros((1, 1), dtype="int16"), 1)
    # The driver check's own plant (F2): an invented ASCII grid, a driver
    # the declared structure does not name.
    other_driver = tmp_path / "ascii.tif"
    with rasterio.open(
        other_driver,
        "w",
        driver="AAIGrid",
        width=1,
        height=1,
        count=1,
        dtype="int16",
        transform=from_origin(0, 1, 1, 1),
        nodata=-32767,
    ) as target:
        target.write(np.zeros((1, 1), dtype="int16"), 1)
    wsf_cases: list[tuple[str, bytes, str, Path]] = [
        (
            "driver",
            other_driver.read_bytes(),
            "structure_mismatch",
            rules,
        ),
        (
            # The band-type check's own plants (F2): a float type and an
            # unsigned byte type, both stored by real drivers but neither
            # the type the source publishes.
            "floatdtype",
            invented.wsf_bytes(tmp_path / "f32.tif", [[5]], 1, 1, dtype="float32"),
            "structure_mismatch",
            rules,
        ),
        (
            "uint8dtype",
            invented.wsf_bytes(
                tmp_path / "u8.tif", [[5]], 1, 1, dtype="uint8", nodata=0
            ),
            "structure_mismatch",
            rules,
        ),
        (
            "nodata",
            invented.wsf_bytes(tmp_path / "n.tif", [[5]], 1, 1, nodata=-1),
            "structure_mismatch",
            rules,
        ),
        ("dtype", bad_dtype.read_bytes(), "structure_mismatch", rules),
        ("nocrs", no_crs.read_bytes(), "reference_system", rules),
        (
            "scale",
            invented.wsf_bytes(tmp_path / "s.tif", [[5]], 1, 1, scale=0.2),
            "structure_mismatch",
            rules,
        ),
        (
            "offset",
            invented.wsf_bytes(tmp_path / "o.tif", [[5]], 1, 1, offset=0.5),
            "structure_mismatch",
            rules,
        ),
        (
            "unitmissing",
            invented.wsf_bytes(tmp_path / "u.tif", [[5]], 1, 1, unit_tag=None),
            "structure_mismatch",
            rules,
        ),
        (
            "unitwrong",
            invented.wsf_bytes(tmp_path / "uw.tif", [[5]], 1, 1, unit_tag="ft"),
            "structure_mismatch",
            rules,
        ),
        (
            # The raster-type check's own plant: an invented raster tagged
            # "Point" where the declared structure says PixelIsArea.
            "areapoint",
            invented.wsf_bytes(tmp_path / "ap.tif", [[5]], 1, 1, area_or_point="Point"),
            "structure_mismatch",
            rules,
        ),
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
        (
            "declaredscale",
            invented.wsf_bytes(tmp_path / "ds.tif", [[5]], 1, 1),
            "structure_mismatch",
            invented.rules_file(tmp_path / "rds.yaml", wsf_scale="0.2"),
        ),
    ]
    for index, body, reason, rules_path in wsf_cases:
        with pytest.raises(HeightError) as err:
            run(f"w-{index}", wsf_row, body, rules_path)
        assert err.value.name == reason, index


def test_the_zip_member_total_bound_is_a_named_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A zip whose members declare more than the bound is refused."""
    import eii_custodian.publicdata.heights.read as read_module

    monkeypatch.setattr(read_module, "_ZIP_MEMBER_TOTAL_MAX", 10)
    row = invented.entry("bldg_3dglobfp", extension="zip")
    cache = tmp_path / "cache"
    invented.store(cache, row, invented.globfp_zip([(invented.square(0, 0, 1), "7")]))
    with pytest.raises(HeightError, match="structure_mismatch"):
        read_sources(
            cache,
            (row,),
            load_rules(invented.rules_file(tmp_path / "r.yaml")),
            bounds=None,
        )


def test_bounds_is_a_required_argument_of_the_raster_read() -> None:
    """P4: a caller that forgets the table's bounds cannot read a source."""
    parameter = inspect.signature(read_sources).parameters["bounds"]
    assert parameter.default is inspect.Parameter.empty


def test_the_published_height_text_arrives_digit_for_digit(tmp_path: Path) -> None:
    """An 18-digit height text parses as the Decimal the publisher wrote."""
    bodies = invented.shapefile_members(
        [[invented.cw(invented.square(0, 0, 1))]], [["1", "7", ""]]
    )
    offset, size = invented.dbf_field_offset(bodies["dbf"], "Height")
    bodies["dbf"] = invented.dbf_patch(
        bodies["dbf"], 0, offset, b"123.456789012345678".rjust(size)
    )
    row = invented.entry("bldg_3dglobfp", extension="zip")
    results = _sources(
        tmp_path,
        (row,),
        None,
        (
            (
                row,
                invented.zip_members(
                    {f"syn.tile.01.{k}": v for k, v in bodies.items()}
                ),
            ),
        ),
    )
    files = results["bldg_3dglobfp"].globfp
    ((_geometry, height),) = files[0][1]
    assert height == Decimal("123.456789012345678")


def test_a_footprint_with_a_hole_reads_its_height(tmp_path: Path) -> None:
    """A ring inside the outer ring is a hole, not a second footprint."""
    outer = invented.cw(invented.square(0, 0, 10))
    hole = invented.square(2, 2, 4)
    bodies = invented.shapefile_members([[outer, hole]], [["1", "9", ""]])
    row = invented.entry("bldg_3dglobfp", extension="zip")
    results = _sources(
        tmp_path,
        (row,),
        None,
        (
            (
                row,
                invented.zip_members(
                    {f"syn.tile.01.{k}": v for k, v in bodies.items()}
                ),
            ),
        ),
    )
    ((geometry, height),) = results["bldg_3dglobfp"].globfp[0][1]
    assert height == Decimal("9")
    assert not geometry.covers(Point(4, 4))
    assert geometry.covers(Point(1, 1))
    building = _polygon(invented.square(2.5, 2.5, 3))
    point = representative_point(building)
    assert (
        globfp_height(point, building, globfp_index(results["bldg_3dglobfp"].globfp))
        is None
    )


def test_two_tiles_read_together_and_keep_their_row_indices(tmp_path: Path) -> None:
    """Two rows of one source read side by side, each named by its key."""
    low = invented.entry("bldg_3dglobfp", extension="zip")
    high = replace(
        invented.entry("bldg_3dglobfp", extension="zip"),
        key="bldg_3dglobfp/high",
        slug="high",
    )
    same = invented.square(0, 0, 1)
    results = _sources(
        tmp_path,
        (low, high),
        None,
        (
            (low, invented.globfp_zip([(same, "7")])),
            (high, invented.globfp_zip([(same, "9")])),
        ),
    )
    files = results["bldg_3dglobfp"].globfp
    assert [name for name, _rows in files] == [low.key, high.key]
    building = _polygon(invented.square(0.1, 0.1, 0.5))
    point = representative_point(building)
    assert globfp_height(point, building, globfp_index(files)) == Decimal("7")


def test_the_footprint_index_is_built_once_for_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H3: seven buildings, one tile: the index constructor runs once."""
    import shapely.strtree

    constructions: list[int] = []
    real = shapely.strtree.STRtree

    class CountingTree(real):
        def __init__(self, geometries):
            constructions.append(len(geometries))
            super().__init__(geometries)

    monkeypatch.setattr("shapely.strtree.STRtree", CountingTree)
    _card_setup(tmp_path)
    assert constructions == [5]


def test_tied_footprints_with_two_heights_count_one(tmp_path: Path) -> None:
    """H4: two identical footprints, two heights: one building counts one."""
    buildings = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    buildings.parent.mkdir(parents=True, exist_ok=True)
    buildings.write_bytes(
        invented.buildings_bytes(
            [invented.building_feature("SYN-B-0001", invented.square(0.1, 0.1, 0.5))]
        )
    )
    row = invented.entry("bldg_3dglobfp", extension="zip")
    cache = tmp_path / "data" / "public_cache"
    same = invented.square(0.05, 0.05, 0.6)
    invented.store(cache, row, invented.globfp_zip([(same, "7.5"), (same, "9.5")]))
    out_dir = tmp_path / "data" / "assets" / "heights"
    build_heights(
        cache,
        (row,),
        buildings,
        out_dir,
        [],
        invented.rules_file(tmp_path / "rules.yaml"),
    )
    table_row = _rows(out_dir)[0]
    assert table_row["height_m"] == "7.50"
    assert table_row["height_source"] == "3dglobfp"
    assert _manifest(out_dir)["tied_height_buildings"] == 1


def test_tied_footprints_with_the_same_height_count_none(tmp_path: Path) -> None:
    """H4: two identical footprints of one height are not a different-height tie."""
    buildings = tmp_path / "data" / "assets" / "buildings" / "buildings.geojson"
    buildings.parent.mkdir(parents=True, exist_ok=True)
    buildings.write_bytes(
        invented.buildings_bytes(
            [invented.building_feature("SYN-B-0001", invented.square(0.1, 0.1, 0.5))]
        )
    )
    row = invented.entry("bldg_3dglobfp", extension="zip")
    cache = tmp_path / "data" / "public_cache"
    same = invented.square(0.05, 0.05, 0.6)
    invented.store(cache, row, invented.globfp_zip([(same, "7.5"), (same, "7.5")]))
    out_dir = tmp_path / "data" / "assets" / "heights"
    build_heights(
        cache,
        (row,),
        buildings,
        out_dir,
        [],
        invented.rules_file(tmp_path / "rules.yaml"),
    )
    assert _rows(out_dir)[0]["height_m"] == "7.50"
    assert _manifest(out_dir)["tied_height_buildings"] == 0


def test_only_the_window_over_the_building_table_is_read(tmp_path: Path) -> None:
    """H5c/P3: the exact worked window, floored, ceiled, grown one cell, clipped.

    Worked by hand (MTH-123): the invented raster spans x in [0, 8) and y in
    (0, 4] at one unit a cell, so bounds (3.6, 1.2, 3.9, 1.8) give fractional
    cells 3.6 to 3.9 across and 2.2 to 2.8 down. Floored at the start, ceiled
    at the end and grown one cell on each side, they give columns 2 to 5 and
    rows 1 to 4: offset (2, 1), width 3, height 3.
    """
    row = invented.entry("bldg_wsf3d", extension="tif")
    body = invented.wsf_bytes(
        tmp_path / "w.tif",
        [
            [10, 20, 30, 40, 50, 60, 70, 80],
            [110, 120, 130, 140, 150, 160, 170, 180],
            [210, 220, 230, 240, 250, 260, 270, 280],
            [310, 320, 330, 340, 350, 360, 370, 380],
        ],
        8,
        4,
        west=0.0,
        north=4.0,
    )
    results = _sources(
        tmp_path, (row,), None, ((row, body),), bounds=(3.6, 1.2, 3.9, 1.8)
    )
    grid = results["bldg_wsf3d"].wsf[0][1]
    assert grid.transform.c == 2.0
    assert grid.transform.f == 3.0
    assert grid.width == 3
    assert grid.height == 3
    assert grid.data.tolist() == [
        [130, 140, 150],
        [230, 240, 250],
        [330, 340, 350],
    ]
    assert 380 not in grid.data.tolist()[0]
    # The point sits in the grid's own cell (1, 1) — raster cell 240, so
    # 240 tenths of a metre is 24 metres after the declared scale.
    assert wsf_value(grid, Point(3.75, 1.75)) == Decimal("24")


def test_a_building_in_the_windows_corner_cell_gets_its_own_cell(
    tmp_path: Path,
) -> None:
    """H5c: a building in the window's corner cell reads that cell's value."""
    row = invented.entry("bldg_wsf3d", extension="tif")
    body = invented.wsf_bytes(
        tmp_path / "w.tif", [[100, 200, 300, 400, 500, 600]], 6, 1
    )
    results = _sources(
        tmp_path, (row,), None, ((row, body),), bounds=(3.1, 0.0, 3.6, 1.0)
    )
    grid = results["bldg_wsf3d"].wsf[0][1]
    assert wsf_value(grid, Point(3.35, 0.5)) == Decimal("40")


def test_a_window_spanning_the_raster_is_refused(tmp_path: Path) -> None:
    """H5c: a window over the bound is raster_window, before any read."""
    path = tmp_path / "wide.tif"
    side = 8192
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=side,
        height=side,
        count=1,
        dtype="int16",
        crs="EPSG:4326",
        transform=from_origin(0, float(side), 1, 1),
        nodata=-32767,
        compress="lzw",
    ) as target:
        target.scales = (0.1,)
        target.update_tags(unit="m")
    row = invented.entry("bldg_wsf3d", extension="tif")
    with pytest.raises(HeightError, match="raster_window"):
        _sources(
            tmp_path / "a",
            (row,),
            None,
            ((row, path.read_bytes()),),
        )
    results = _sources(
        tmp_path / "b",
        (row,),
        None,
        ((row, path.read_bytes()),),
        bounds=(3.0, 0.0, 4.0, 1.0),
    )
    grid = results["bldg_wsf3d"].wsf[0][1]
    assert grid.width < side


def test_a_building_table_wholly_outside_the_raster_reads_nothing(
    tmp_path: Path,
) -> None:
    """H5c: a table outside the raster gives an empty grid, not a refusal."""
    row = invented.entry("bldg_wsf3d", extension="tif")
    body = invented.wsf_bytes(tmp_path / "w.tif", [[50, 60]], 2, 1)
    results = _sources(
        tmp_path, (row,), None, ((row, body),), bounds=(50.0, 50.0, 60.0, 60.0)
    )
    grid = results["bldg_wsf3d"].wsf[0][1]
    assert grid.width == 0
    assert wsf_value(grid, Point(55, 55)) is None


def test_the_piecewise_digest_equals_the_one_shot_digest(tmp_path: Path) -> None:
    """H5d: a body larger than one piece hashes piecewise to the same digest."""
    import eii_custodian.publicdata.heights.read as read_module

    size = read_module._HASH_PIECE_BYTES + 123
    body = (bytes(range(256)) * (size // 256 + 1))[:size]
    path = tmp_path / "big.bin"
    path.write_bytes(body)
    assert sha256_path(path) == sha256_hex(body)


def test_the_height_hosts_join_the_allow_list() -> None:
    """PUB-03: the three height hosts are listed; another name is refused."""
    assert "ndownloader.figshare.com" in ALLOWED_HOSTS
    assert "44c1cec316ec56bca76dfd65d2882b20.r2.cloudflarestorage.com" in ALLOWED_HOSTS
    assert "download.geoservice.dlr.de" in ALLOWED_HOSTS
    assert approve("https://ndownloader.figshare.com/ndownloader/files/1").ok
    assert not approve(
        "https://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.r2.cloudflarestorage.com/x"
    ).ok


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
