"""L-255 regression fixtures: invented equatorial frame, no fetched data."""

import random
from dataclasses import replace

import pytest
from custodian.tests.fixtures.frame.invented import invented_frame
from custodian.tests.repository_root import repository_root
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

import h3
from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.gazetteer import make_row, point_cell
from eii_custodian.publicdata.frame.grid import build_grid, ownership_index


def edge_frame():
    template = invented_frame()[0][0]
    municipalities = [
        replace(template, key=key, municipality_code=key, geometry=geometry)
        for key, geometry in [
            ("SYN-A", box(0, 0, 0.02, 0.04)),
            ("SYN-B", box(0.02, 0, 0.04, 0.04)),
        ]
    ]
    return (
        municipalities,
        [replace(m, key=m.key + "-Z") for m in municipalities],
        [replace(m, key=m.key + "-D") for m in municipalities],
    )


def native(cell):
    return Polygon([(lon, lat) for lat, lon in h3.cell_to_boundary(cell)])


def test_split_selection_and_own_attributes():
    municipalities, zones, districts = edge_frame()
    rows = build_grid(municipalities, zones, districts, {"SYN-A"})
    stored = {h3.int_to_str(r["cell"]): r for r in rows}
    fine = h3.geo_to_cells(unary_union([m.geometry for m in municipalities]), 9)
    split = {
        h3.cell_to_parent(c, 8)
        for c in fine
        if municipalities[0].geometry.contains(Point(*reversed(h3.cell_to_latlng(c))))
    }
    outside_parents = {
        p
        for p in split
        if not unary_union([m.geometry for m in municipalities]).covers(
            Point(*reversed(h3.cell_to_latlng(p)))
        )
    }
    assert outside_parents
    siblings = []
    for cell in fine:
        parent = h3.cell_to_parent(cell, 8)
        if parent in split:
            assert cell in stored
            assert parent not in stored
            row = stored[cell]
            own = (
                "SYN-A"
                if municipalities[0].geometry.covers(
                    Point(*reversed(h3.cell_to_latlng(cell)))
                )
                else "SYN-B"
            )
            assert row["municipality_code"] == own
            assert row["zone_code"] == own + "-Z"
            assert row["district_key"] == own + "-D"
            assert row["in_greater_doha"] == (own == "SYN-A")
            if own == "SYN-B":
                siblings.append(cell)
    assert siblings
    assert any(r["resolution"] == 8 for r in rows)


def test_shape_and_point_ownership_agree():
    rows = build_grid(*edge_frame(), {"SYN-A"})
    shapes = [r["geometry"] for r in rows]
    for i, polygon in enumerate(shapes):
        assert all(polygon.intersection(other).area == 0 for other in shapes[:i])
    assert unary_union(shapes).area == pytest.approx(
        sum(p.area for p in shapes), rel=1e-14
    )
    rng = random.Random(255)
    for row in rows:
        polygon = row["geometry"]
        lo, bottom, hi, top = polygon.bounds
        for _ in range(10):
            point = Point(rng.uniform(lo, hi), rng.uniform(bottom, top))
            if polygon.contains(point):
                assert (
                    point_cell(point.x, point.y, ownership_index(rows)) == row["cell"]
                )
    # Construct both native-hexagon disagreement cases, not just random samples.
    coarse = [r for r in rows if r["resolution"] == 8]
    fine = [r for r in rows if r["resolution"] == 9]
    found = set()
    for large in coarse:
        for small in fine:
            p = native(h3.int_to_str(large["cell"])).intersection(small["geometry"])
            if p.area > 0:
                point = p.representative_point()
                assert (
                    point_cell(point.x, point.y, ownership_index(rows)) == small["cell"]
                )
                found.add("two")
            parent = h3.cell_to_parent(h3.int_to_str(small["cell"]), 8)
            p = (
                native(parent)
                .intersection(large["geometry"])
                .difference(native(h3.int_to_str(large["cell"])))
            )
            if p.area > 0:
                point = p.representative_point()
                assert (
                    point_cell(point.x, point.y, ownership_index(rows)) == large["cell"]
                )
                found.add("none")
    assert found == {"two", "none"}


def test_reviewed_district_free_zone_and_report():
    municipalities, zones, _ = invented_frame()
    report = []
    rows = build_grid(municipalities, zones, [], set(), {"SYN-Z"}, report)
    assert rows and all(r["district_key"] is None for r in rows)
    assert report == [
        f"grid_cell: {len(rows)} zone_without_district",
        "district: 0 no_cell_centre",
    ]


@pytest.mark.parametrize(
    "case, message",
    [
        ("unlisted", "unlisted district-free zone"),
        ("partial", "partial district coverage"),
        ("listed_with_district", "listed zone has a district"),
        ("unknown", "unknown district-free zone"),
    ],
)
def test_district_exception_refusals(case, message):
    municipalities, zones, districts = invented_frame()
    exceptions = set()
    if case == "unlisted":
        districts = []
    elif case == "partial":
        districts = districts[:1]
    elif case == "listed_with_district":
        exceptions = {"SYN-Z"}
    else:
        exceptions = {"SYN-UNKNOWN"}
    with pytest.raises(FrameError, match=message):
        build_grid(municipalities, zones, districts, set(), exceptions)


@pytest.mark.parametrize("kind", ["municipality", "zone", "district"])
def test_administrative_missing_cell_keeps_point(kind):
    row = make_row(
        "SYN-P",
        kind,
        "Invented",
        "تجريبي",
        None,
        0.012345,
        0.034567,
        "bnd_hdx",
        frozenset(),
    )
    assert row["cell"] is None
    assert float(row["lon"]) == 0.012345
    assert float(row["lat"]) == 0.034567


def test_nonadministrative_missing_cell_refuses():
    with pytest.raises(FrameError, match="no unique base cell"):
        make_row(
            "SYN-P",
            "landmark",
            "Invented",
            "تجريبي",
            None,
            0,
            0,
            "bnd_hdx",
            frozenset(),
        )


def test_reviewed_names_validate_all_four_source_names(tmp_path):
    from eii_custodian.publicdata.frame.crosswalk import (
        check_municipality_names,
        load_municipality_names,
    )

    records = [
        {
            "municipality_code": key,
            **{
                field: f"{key}-{field}"
                for field in ("name_en", "name_ar", "layer_name_en", "layer_name_ar")
            },
        }
        for key in ("SYN-A", "SYN-B")
    ]
    path = tmp_path / "municipality_names.csv"
    path.write_text(
        "name,municipality_code\n"
        + "".join(
            f"{value},{r['municipality_code']}\n"
            for r in records
            for field, value in r.items()
            if field != "municipality_code"
        )
    )
    names = load_municipality_names(tmp_path, {"SYN-A", "SYN-B"})
    check_municipality_names(records, names)
    for field in ("name_en", "name_ar", "layer_name_en", "layer_name_ar"):
        for replacement in ["SYN-unmapped", records[1][field]]:
            changed = [{**records[0], field: replacement}, records[1]]
            with pytest.raises(FrameError, match="municipality source spelling"):
                check_municipality_names(changed, names)
    swapped = [
        {
            **r,
            "municipality_code": "SYN-B"
            if r["municipality_code"] == "SYN-A"
            else "SYN-A",
        }
        for r in names
    ]
    with pytest.raises(FrameError, match="municipality source spelling"):
        check_municipality_names(records, swapped)


def test_doha_alias_and_duplicate_code(tmp_path):
    from eii_custodian.publicdata.frame.crosswalk import greater_doha_keys

    (tmp_path / "municipality_names.csv").write_text(
        "name,municipality_code\nInvented alias,SYN-A\nOther alias,SYN-A\n"
    )
    path = tmp_path / "greater_doha_municipalities.csv"
    path.write_text("name\nInvented alias\n")
    assert greater_doha_keys(tmp_path, {"SYN-A"}) == {"SYN-A"}
    path.write_text("name\nInvented alias\nOther alias\n")
    with pytest.raises(FrameError, match="duplicate municipality"):
        greater_doha_keys(tmp_path, {"SYN-A"})


def test_district_free_reason_closed(tmp_path):
    from eii_custodian.publicdata.frame.crosswalk import district_free_zones

    path = tmp_path / "zones_without_districts.csv"
    path.write_text("zone_code,reason\nSYN-Z,no_district_in_boundary_source\n")
    assert district_free_zones(tmp_path) == {"SYN-Z"}
    path.write_text("zone_code,reason\nSYN-Z,invented_reason\n")
    with pytest.raises(FrameError, match="district-free reason"):
        district_free_zones(tmp_path)


def test_proposed_review_outputs_and_summary(tmp_path):
    import csv

    from eii_custodian.publicdata.frame.crosswalk import propose_reviews

    review = tmp_path / "review"
    output = tmp_path / "output"
    review.mkdir()
    committed = (
        "zone_code,util_elec,bnd_geob,status\n10,10,,no_polygon\n18-19,,18-19,merged\n"
    )
    (review / "zone_crosswalk.csv").write_text(committed)
    inventory = {
        source: {field: ("42", "43", "99")}
        for source, field in [
            ("util_elec", "zone_number"),
            ("util_water", "zone_number"),
            ("census_zone_hh", "ZONE_NO"),
            ("bnd_zone_2020", "ZONE_NO"),
            ("bnd_district_2020", "KEY_NO"),
            ("census_district_pop", "ZONENO"),
        ]
    }
    inventory["pop_muni"] = {"indicator": ("Invented indicator",)}
    report = []
    propose_reviews(review, output, {"42", "43"}, inventory, report)
    with (output / "proposed_zone_crosswalk.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    for source in inventory.keys() - {"pop_muni"}:
        assert {r[source] for r in rows} >= {"42", "43", "99"}
        assert len([line for line in report if line.startswith(source + ":")]) == 1
    assert next(r for r in rows if r["zone_code"] == "99")["status"] == "unmatched"
    assert next(r for r in rows if r["zone_code"] == "10")["status"] == "no_polygon"
    assert next(r for r in rows if r["zone_code"] == "18-19")["bnd_geob"] == "18-19"
    assert (
        output / "proposed_population_indicators.csv"
    ).read_text() == "indicator,mapped_indicator\nInvented indicator,\n"
    before = (output / "proposed_zone_crosswalk.csv").read_bytes()
    (review / "proposed_zone_crosswalk.csv").write_text("malicious proposed mapping")
    propose_reviews(review, output, {"42", "43"}, inventory, [])
    assert (output / "proposed_zone_crosswalk.csv").read_bytes() == before
    assert (review / "zone_crosswalk.csv").read_text() == committed


def test_null_table_contract_checks():
    from eii_custodian.publicdata.frame.gazetteer import validate_frame_tables

    grid = build_grid(*invented_frame(), set())
    tables = {"grid_cell": grid, "gazetteer": []}
    validate_frame_tables(tables, set())
    original = grid[0]["district_key"]
    grid[0]["district_key"] = None
    with pytest.raises(FrameError, match="district null condition"):
        validate_frame_tables(tables, set())
    grid[0]["district_key"] = original
    with pytest.raises(FrameError, match="district null condition"):
        validate_frame_tables(tables, {"SYN-Z"})
    row = make_row(
        "SYN-P",
        "district",
        "Invented",
        "تجريبي",
        None,
        1.0123456789,
        1.0345678912,
        "bnd_hdx",
        ownership_index(grid),
    )
    assert str(row["lon"]) == "1.012346"
    assert str(row["lat"]) == "1.034568"
    tables["gazetteer"] = [row]
    validate_frame_tables(tables, set())
    row["kind"] = "building"
    with pytest.raises(FrameError, match="gazetteer cell condition"):
        validate_frame_tables(tables, set())
    row["kind"] = "district"
    row["cell"] = grid[0]["cell"]
    with pytest.raises(FrameError, match="gazetteer cell condition"):
        validate_frame_tables(tables, set())


def test_atom_duplicate_refuses():
    from eii_custodian.publicdata.frame.grid import check_atoms

    child = h3.latlng_to_cell(0, 0, 9)
    with pytest.raises(FrameError, match="owned twice"):
        check_atoms([h3.cell_to_parent(child, 8), child])


def test_no_cell_zone_still_refuses():
    municipalities, zones, _districts = invented_frame()
    tiny = box(0, 0, 0.00001, 0.00001)
    zones = [
        replace(zones[0], geometry=tiny),
        replace(
            zones[0], key="SYN-Z2", geometry=municipalities[0].geometry.difference(tiny)
        ),
    ]
    with pytest.raises(FrameError, match=r"zone_code.*no cell centre"):
        build_grid(municipalities, zones, [], set(), {"SYN-Z", "SYN-Z2"})


def test_proposed_keeps_unlisted_tokens_on_existing_review_row(tmp_path):
    import csv

    from eii_custodian.publicdata.frame.crosswalk import propose_reviews

    (tmp_path / "zone_crosswalk.csv").write_text(
        "zone_code,util_elec,status\n10,10,no_polygon\n"
    )
    inventory = {
        "util_elec": {"zone_number": ("10",)},
        "util_water": {"zone_number": ("10",)},
    }
    propose_reviews(tmp_path, tmp_path / "out", set(), inventory, [])
    with (tmp_path / "out" / "proposed_zone_crosswalk.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert any(r["util_water"] == "10" and r["status"] == "unmatched" for r in rows)
    assert any(r["util_elec"] == "10" and r["status"] == "no_polygon" for r in rows)


def test_frame_readme_documents_measured_limits():
    from pathlib import Path

    readme = (
        repository_root(Path(__file__))
        / "custodian/src/eii_custodian/publicdata/frame/README.md"
    ).read_text()
    for phrase in (
        "resolution-8 geometry is not a hexagon",
        "460",
        "473",
        "zone 99",
        "cells_to_geo",
        "point_without_base_cell",
    ):
        assert phrase in readme


def test_proposed_matches_zone_numbers_not_spelling(tmp_path):
    import csv

    from eii_custodian.publicdata.frame.crosswalk import propose_reviews

    (tmp_path / "zone_crosswalk.csv").write_text("zone_code,status\n")
    propose_reviews(
        tmp_path,
        tmp_path / "out",
        {"42"},
        {"util_water": {"zone_number": ("042",)}},
        [],
    )
    with (tmp_path / "out" / "proposed_zone_crosswalk.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [{"zone_code": "42", "util_water": "042", "status": "matched"}]


def test_proposed_output_even_when_geometry_unavailable(tmp_path):
    from eii_custodian.publicdata.frame.build import build_frame

    review = tmp_path / "review"
    review.mkdir()
    (review / "zone_crosswalk.csv").write_text("zone_code,status\n")
    output = tmp_path / "output"
    result = build_frame(tmp_path / "cache", (), review, output)
    assert (output / "proposed_zone_crosswalk.csv").exists()
    assert (output / "proposed_population_indicators.csv").exists()
    assert (
        "frame: required geometry unavailable; dependent tables not built"
        in result.report
    )


def test_administrative_null_report_counts_each_kind_once():
    from eii_custodian.publicdata.frame.gazetteer import administrative_rows

    report = []
    rows = administrative_rows(*invented_frame(), [], report)
    assert len(rows) == 4
    assert report == [
        "gazetteer municipality: 1 point_without_base_cell",
        "gazetteer zone: 1 point_without_base_cell",
        "gazetteer district: 2 point_without_base_cell",
    ]
