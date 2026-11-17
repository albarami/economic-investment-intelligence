"""Invented frame polygons; no fetched geometry or population values."""

import pytest
from custodian.tests.fixtures.frame.invented import invented_frame
from shapely.geometry import Point, box

import h3
from eii_custodian.publicdata.frame.checks import FrameError, check_cover, containing
from eii_custodian.publicdata.frame.grid import build_grid, check_ancestors


def test_exact_coverage():
    check_cover([box(0, 0, 1, 1), box(1, 0, 2, 1)], box(0, 0, 2, 1))


def test_gap_fails():
    with pytest.raises(FrameError, match="gap"):
        check_cover([box(0, 0, 1, 1)], box(0, 0, 2, 1))


def test_overlap_fails():
    with pytest.raises(FrameError, match="overlap"):
        check_cover([box(0, 0, 2, 1), box(1, 0, 2, 1)], box(0, 0, 2, 1))


@pytest.mark.parametrize("point", [Point(3, 3), Point(1, 0.5)])
def test_centre_requires_one_polygon(point):
    with pytest.raises(FrameError, match="exactly one"):
        containing(point, {"SYN-A": box(0, 0, 1, 1), "SYN-B": box(1, 0, 2, 1)})


def test_district_keys_and_resolution_parent_outline():
    municipalities, zones, districts = invented_frame()
    rows = build_grid(municipalities, zones, districts, {"SYN-A"})
    assert {row["district_key"] for row in rows} == {"SYN-D", "SYN-E"}
    assert {row["resolution"] for row in rows} == {9}
    assert all(row["in_greater_doha"] for row in rows)
    for row in rows:
        cell = h3.int_to_str(row["cell"])
        assert h3.get_resolution(h3.int_to_str(row["parent_r7"])) == 7
        assert h3.cell_to_parent(cell, 7) == h3.int_to_str(row["parent_r7"])
        lat, lon = h3.cell_to_latlng(cell)
        assert row["geometry"].contains(Point(lon, lat))
    rural = build_grid(municipalities, zones, districts, set())
    assert {row["resolution"] for row in rural} == {8}
    assert not any(row["in_greater_doha"] for row in rural)


def test_parent_and_child_fail():
    child = h3.latlng_to_cell(0, 0, 9)
    with pytest.raises(FrameError, match="ancestor"):
        check_ancestors([child, h3.cell_to_parent(child, 8)])


def test_unknown_greater_doha_fails():
    with pytest.raises(FrameError, match="Greater Doha"):
        build_grid(*invented_frame(), {"SYN-MISSING"})


def test_duplicate_district_key_fails():
    municipalities, zones, districts = invented_frame()
    with pytest.raises(FrameError, match="duplicate"):
        build_grid(municipalities, zones, districts + districts[:1], set())


def test_empty_district_key_fails():
    from dataclasses import replace

    municipalities, zones, districts = invented_frame()
    districts[0] = replace(districts[0], key="")
    with pytest.raises(FrameError, match="key"):
        build_grid(municipalities, zones, districts, set())


def test_tiny_district_without_centre_is_reported():
    from dataclasses import replace

    municipalities, zones, districts = invented_frame()
    tiny = box(0, 0, 0.00001, 0.00001)
    districts = [
        replace(districts[0], geometry=tiny),
        replace(districts[1], geometry=municipalities[0].geometry.difference(tiny)),
    ]
    report = []
    build_grid(municipalities, zones, districts, set(), report=report)
    assert "district: 1 no_cell_centre" in report


def test_district_crossing_zone_fails():
    from dataclasses import replace

    municipalities, zones, districts = invented_frame()
    zones = [
        replace(zones[0], geometry=box(0, 0, 0.04, 0.02)),
        replace(zones[0], key="SYN-Y", geometry=box(0, 0.02, 0.04, 0.04)),
    ]
    with pytest.raises(FrameError, match="containment"):
        build_grid(municipalities, zones, districts, set())


def test_invented_subset_uses_both_resolutions():
    from dataclasses import replace

    from shapely.affinity import translate

    municipalities, zones, districts = invented_frame()
    others = [
        replace(
            b,
            key=b.key + "-OTHER",
            municipality_code="SYN-A-OTHER",
            geometry=translate(b.geometry, xoff=1),
        )
        for b in municipalities + zones + districts
    ]
    rows = build_grid(
        municipalities + others[:1],
        zones + others[1:2],
        districts + others[2:],
        {"SYN-A"},
    )
    assert {
        (r["municipality_code"], r["resolution"], r["in_greater_doha"]) for r in rows
    } == {("SYN-A", 9, True), ("SYN-A-OTHER", 8, False)}


def test_duplicate_cell_fails():
    child = h3.latlng_to_cell(0, 0, 9)
    with pytest.raises(FrameError, match="duplicate cell"):
        check_ancestors([child, child])


def test_invalid_polygons_fail():
    from shapely.geometry import Polygon

    for invalid in (Polygon(), Point(0, 0), Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])):
        with pytest.raises(FrameError, match="invalid polygon"):
            check_cover([invalid], box(0, 0, 1, 1))


def test_wrong_municipality_join_fails():
    from dataclasses import replace

    municipalities, zones, districts = invented_frame()
    districts[0] = replace(districts[0], municipality_code="SYN-MISSING")
    with pytest.raises(FrameError, match="municipality containment"):
        build_grid(municipalities, zones, districts, set())


def test_multipolygon_is_a_valid_boundary():
    from shapely.geometry import MultiPolygon

    whole = MultiPolygon([box(0, 0, 1, 1), box(2, 0, 3, 1)])
    check_cover([whole], whole)


def test_licensed_archive_shape_and_planted_violations():
    import copy
    import io
    import json
    import zipfile

    from eii_custodian.publicdata.frame.raw import read_archive

    def archive(change=None):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as zipped:
            for level in (1, 2, 3):
                properties = {}
                for n in range(level + 1):
                    properties.update(
                        {
                            f"adm{n}_name": f"Invented {n}",
                            f"adm{n}_name1": "اسم تجريبي",
                            f"adm{n}_name2": None,
                            f"adm{n}_name3": None,
                            f"adm{n}_pcode": "SYN" + "042" * n,
                        }
                    )
                properties.update(
                    valid_on="2026-01-01",
                    valid_to=None,
                    area_sqkm=17,
                    version="invented",
                    lang="en",
                    lang1="ar",
                    lang2=None,
                    lang3=None,
                    center_lat=0.02,
                    center_lon=0.02,
                )
                if level >= 2:
                    properties["adm2_name"] = "Invented zone 42"
                document = {
                    "type": "FeatureCollection",
                    "name": "Invented",
                    "crs": {
                        "type": "name",
                        "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
                    },
                    "features": [
                        {
                            "type": "Feature",
                            "properties": properties,
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [
                                    [[0, 0], [0.04, 0], [0.04, 0.04], [0, 0.04], [0, 0]]
                                ],
                            },
                        }
                    ],
                }
                if change and level == 2:
                    document = copy.deepcopy(document)
                    if change(document) is False:
                        continue
                zipped.writestr(f"qat_admin{level}.geojson", json.dumps(document))
        return stream.getvalue()

    result = read_archive(archive())
    assert result["municipality"][0].key == "SYN042"
    assert result["zone"][0].key == "42"
    assert result["district"][0].key == "SYN042042042"
    assert result["zone"][0].municipality_code == "SYN042"
    assert result["zone"][0].geometry.area > 0
    for mutation, message in [
        (lambda d: False, "missing member"),
        (
            lambda d: d["crs"]["properties"].update(name="invented CRS"),
            "coordinate system",
        ),
        (lambda d: d["features"][0]["properties"].update(SYN_unknown=1), "properties"),
        (lambda d: d["features"][0]["properties"].pop("adm2_name"), "properties"),
        (lambda d: d["features"][0]["geometry"].update(type="Point"), "geometry type"),
        (lambda d: d["features"][0]["properties"].update(adm2_pcode="SYN-bad"), "code"),
        (
            lambda d: d["features"][0]["properties"].update(adm2_name="Invented 43"),
            "zone name",
        ),
    ]:
        with pytest.raises(FrameError, match=message):
            read_archive(archive(mutation))


def test_registry_pass_three_attribution_and_archive():
    from eii_custodian.publicdata.fetch.kinds import prepare
    from eii_custodian.publicdata.fetch.registry import load_registry
    from eii_custodian.publicdata.fetch.transport import Response

    entries = {e.source_id: e for e in load_registry()}
    hdx = entries["bnd_hdx"]
    assert hdx.extension == "zip"
    assert hdx.licence_id == "cc-by-igo"
    assert hdx.skip_reason == ""
    assert hdx.url == (
        "https://data.humdata.org/dataset/6a84f3b8-41cd-4769-a61f-6dbd5f61bd05/"
        "resource/1955adf8-4e4a-4a87-b3f0-0fbe6e761ca9/download/qat_admin_boundaries.geojson.zip"
    )
    assert hdx.licence_basis == "dataset"
    assert "district" in hdx.release_tables
    target = "https://s3.us-east-1.amazonaws.com/invented/archive.zip"
    result = prepare(
        hdx, lambda url: Response(target, b"invented bytes", (target,)), lambda n: None
    )
    assert result.failure is None
    assert result.body == b"invented bytes"
    target = "https://invented.invalid/archive.zip"
    result = prepare(
        hdx, lambda url: Response(target, b"invented bytes", (target,)), lambda n: None
    )
    assert result.failure.check == "blocked_host"
    for source in ("est_census", "zone_population", "census_hh_type_2020"):
        row = entries[source]
        assert row.publisher == "National Planning Council"
        assert row.licence_id == "CC-BY-4.0"
        assert row.licence_basis == "dataset"
        assert row.licence_url == "https://creativecommons.org/licenses/by/4.0/"
        assert row.skip_reason == ""
    assert entries["bnd_muni_2025"].skip_reason == ""
    assert dict(entries["bnd_muni_2025"].columns)["geo_shape"] == "geojson_geometry"


def test_archive_all_property_types_parent_codes_and_multipolygon():
    import copy
    import io
    import json
    import zipfile

    from custodian.tests.fixtures.frame.invented import invented_archive

    from eii_custodian.publicdata.frame.raw import parse_level

    with zipfile.ZipFile(io.BytesIO(invented_archive())) as archive:
        document = json.loads(archive.read("qat_admin3.geojson"))
    for field, value in document["features"][0]["properties"].items():
        bad = copy.deepcopy(document)
        bad["features"][0]["properties"][field] = (
            "unexpected" if value is None else None
        )
        with pytest.raises(FrameError, match="property"):
            parse_level(bad, 3)
    for n in (2, 3):
        bad = copy.deepcopy(document)
        bad["features"][0]["properties"][f"adm{n}_pcode"] = "SYN043" + "042" * (n - 1)
        with pytest.raises(FrameError, match="parent code"):
            parse_level(bad, 3)
    multi = copy.deepcopy(document)
    geometry = multi["features"][0]["geometry"]
    geometry["type"] = "MultiPolygon"
    geometry["coordinates"] = [geometry["coordinates"]]
    assert parse_level(multi, 3)[0].geometry.geom_type == "MultiPolygon"
