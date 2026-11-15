"""Crosswalks only assign explicitly reviewed keys."""

from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.test_frame_coverage import invented_frame

from eii_custodian.publicdata.frame.checks import FrameError, safe_key
from eii_custodian.publicdata.frame.crosswalk import (
    check_zones,
    district_keys,
    municipality_key,
    read_csv,
)
from eii_custodian.publicdata.frame.geometry import disagreements

REVIEW = repository_root(Path(__file__)) / "custodian/publicdata/review"


def test_committed_zone_exceptions():
    rows = read_csv(REVIEW / "zone_crosswalk.csv")
    by_key = {row["zone_code"]: row for row in rows}
    assert by_key["10"]["status"] == "no_polygon"
    assert by_key["11"]["status"] == "no_polygon"
    assert by_key["18-19"]["status"] == "merged"
    check_zones(rows, {"util_elec": {"10", "11"}, "bnd_geob": {"18-19"}})


def test_crosswalk_unknown_zone_and_status_fail():
    rows = read_csv(REVIEW / "zone_crosswalk.csv")
    with pytest.raises(FrameError, match="unlisted zone"):
        check_zones(rows, {"bnd_hdx": {"SYN-Z"}})
    rows[0]["status"] = "guessed"
    with pytest.raises(FrameError, match="status"):
        check_zones(rows, {})


def test_municipality_spelling_pairs():
    rows = read_csv(REVIEW / "municipality_names.csv")
    for a, b in [
        ("Al Sheehaniya", "Al Shahaniya"),
        ("Umm Slal", "Umm Salal"),
        ("Al Khor", "Al Thakhira"),
    ]:
        assert municipality_key(a, rows) == municipality_key(b, rows)
    with pytest.raises(FrameError, match="unmapped municipality"):
        municipality_key("SYN-Unknown", rows)


def test_district_unmatched_is_listed_never_guessed():
    rows = [{"name": "Invented mapped", "district_keys": "SYN-D"}]
    assert district_keys("Invented mapped", rows, {"SYN-D"}) == (("SYN-D",), None)
    assert district_keys("Invented unmatched", rows, {"SYN-D"}) == (
        (),
        "unmatched district: Invented unmatched",
    )
    with pytest.raises(FrameError, match="unknown district"):
        district_keys("Invented mapped", rows, {"SYN-E"})


@pytest.mark.parametrize("size", [8, 11])
def test_bare_digit_run_fails(size):
    with pytest.raises(FrameError, match="digit run"):
        safe_key("1" * size)


def test_polygon_equality_and_disagreements():
    from dataclasses import replace

    from shapely.geometry import box

    _, zones, _ = invented_frame()
    zones = [replace(zones[0], key="69")]
    assert disagreements(zones, zones, "zone") == []
    assert disagreements(zones, [], "zone") == ["zone 69: missing comparison"]
    changed = [replace(zones[0], geometry=box(0, 0, 0.01, 0.01))]
    assert disagreements(zones, changed, "zone") == ["zone 69: polygon disagreement"]


def test_duplicate_district_mapping_fails():
    rows = [{"name": "Invented mapped", "district_keys": "SYN-D"}] * 2
    with pytest.raises(FrameError, match="duplicate district mapping"):
        district_keys("Invented mapped", rows, {"SYN-D"})


def test_valid_keys_and_explicit_district_split():
    assert safe_key("SYN-A") == "SYN-A"
    rows = [{"name": "Invented mapped", "district_keys": "SYN-D;SYN-E"}]
    assert district_keys("Invented mapped", rows, {"SYN-D", "SYN-E"}) == (
        ("SYN-D", "SYN-E"),
        None,
    )


def test_boundary_names_required():
    from shapely.geometry import box, mapping

    from eii_custodian.publicdata.frame.geometry import parse_boundaries

    row = {
        "municipality_code": "SYN-A",
        "name_en": "Invented",
        "name_ar": "اسم تجريبي",
        "geometry": mapping(box(0, 0, 1, 1)),
    }
    for field in ("name_en", "name_ar"):
        with pytest.raises(FrameError, match="bilingual name"):
            parse_boundaries([{**row, field: ""}], "municipality")


@pytest.mark.parametrize(
    "status", ["matched", "absent_in_source", "merged", "no_polygon"]
)
def test_all_closed_zone_statuses(status):
    check_zones(
        [{"zone_code": "SYN-Z", "bnd_hdx": "SYN-Z", "status": status}],
        {"bnd_hdx": {"SYN-Z"}},
    )


def test_geometry_release_columns_match_contract():
    from eii_custodian.publicdata.frame.geometry import release_rows

    municipalities, zones, districts = invented_frame()
    for level, boundaries, key, source in (
        ("municipality", municipalities, "municipality_code", "bnd_muni_2025"),
        ("zone", zones, "zone_code", "bnd_hdx"),
        ("district", districts, "district_key", "bnd_hdx"),
    ):
        rows = release_rows(boundaries, level, source)
        expected = {key, "name_en", "name_ar", "geometry", "source_id"}
        if level != "municipality":
            expected.add("municipality_code")
        assert len(rows) == len(boundaries)
        for row, boundary in zip(rows, boundaries, strict=True):
            assert set(row) == expected
            assert row[key] == boundary.key
            assert row["name_en"] == boundary.name_en
            assert row["name_ar"] == boundary.name_ar
            assert row["geometry"].equals(boundary.geometry)
            assert row["source_id"] == source
            assert row["municipality_code"] == boundary.municipality_code


def test_live_shape_key_joins_and_violations():
    from dataclasses import replace

    from custodian.tests.fixtures.frame.invented import invented_layer

    from eii_custodian.publicdata.frame.joins import join_districts, join_municipalities
    from eii_custodian.publicdata.frame.layers import layer_rows

    municipalities, zones, districts = invented_frame()
    municipalities = [
        replace(municipalities[0], key="SYN042", municipality_code="SYN042")
    ]
    zones = [replace(zones[0], key="42", municipality_code="SYN042")]
    districts = [
        replace(
            districts[0],
            key="SYN042042009",
            municipality_code="SYN042",
            name_en="Invented district",
        )
    ]
    zone_rows = layer_rows("bnd_zone_2020", invented_layer("bnd_zone_2020"))
    mapping, review = join_municipalities(municipalities, zones, zone_rows)
    assert mapping == {"SYN042": "9"}
    assert review[0]["municipality_code"] == "9"
    assert review[0]["hdx_code"] == "SYN042"
    assert review[0]["layer_name_en"] == "Different invented spelling"
    for rows, match in [
        ([], "zone_sets"),
        (zone_rows * 2, "duplicate_zone"),
        ([{**zone_rows[0], "ZONE_NO": 43}], "zone_sets"),
    ]:
        with pytest.raises(FrameError, match=match):
            join_municipalities(municipalities, zones, rows)
    more_zones = [*zones, replace(zones[0], key="43")]
    with pytest.raises(FrameError, match="municipality_consistency"):
        join_municipalities(
            municipalities,
            more_zones,
            [*zone_rows, {**zone_rows[0], "ZONE_NO": 43, "MUNICIPAL_CODE": "0"}],
        )
    with pytest.raises(FrameError, match="municipality_bijection"):
        join_municipalities(
            [*municipalities, replace(municipalities[0], key="SYN043")],
            [*zones, replace(zones[0], key="43", municipality_code="SYN043")],
            [*zone_rows, {**zone_rows[0], "ZONE_NO": 43}],
        )
    district_rows = layer_rows("bnd_district_2020", invented_layer("bnd_district_2020"))
    census = layer_rows("census_district_pop", invented_layer("census_district_pop"))
    joined, report = join_districts(districts, district_rows, census, [])
    assert joined == {(42, 73): "SYN042042009"}
    assert report == []
    with pytest.raises(FrameError, match="district_census_pair"):
        join_districts(districts, district_rows, [{**census[0], "ZONENO": 43}], [])
    with pytest.raises(FrameError, match="district_key_equality"):
        join_districts(districts, [{**district_rows[0], "DIST_KEY": 74}], census, [])
    with pytest.raises(FrameError, match="district_pair_unique"):
        join_districts(districts * 2, district_rows, census, [])
    with pytest.raises(FrameError, match="district_pair_unique"):
        join_districts(districts, district_rows * 2, census, [])
    changed = [{**district_rows[0], "ENAME": "Invented unmatched"}]
    joined, report = join_districts(districts, changed, census, [])
    assert joined == {}
    assert len(report) == 2
    assert all("district_name_pair_unmatched" in line for line in report)
    aliases = [
        {
            "zone_code": "42",
            "layer_name": "Invented unmatched",
            "hdx_name": "Invented district",
        }
    ]
    assert join_districts(districts, changed, census, aliases) == (
        {(42, 73): "SYN042042009"},
        [],
    )
    with pytest.raises(FrameError, match="district_alias"):
        join_districts(districts, changed, census, aliases * 2)


def test_census_zone_membership_is_checked_before_measure_loading():
    from eii_custodian.publicdata.frame.joins import check_census_zones

    rows = [{"ZONE_NO": 42, "MUNICIPAL_CODE": "9"}]
    check_census_zones("census_zone_sector", rows, {"42": "9"})
    for changed in (
        {"ZONE_NO": 43, "MUNICIPAL_CODE": "9"},
        {"ZONE_NO": 42, "MUNICIPAL_CODE": "0"},
    ):
        with pytest.raises(FrameError, match="census_zone_key"):
            check_census_zones("census_zone_sector", [changed], {"42": "9"})
    with pytest.raises(FrameError, match="duplicate_zone"):
        check_census_zones("census_zone_sector", rows * 2, {"42": "9"})


@pytest.fixture
def municipal_review(tmp_path):
    review = tmp_path / "review"
    review.mkdir()
    arabic = "اسم تجريبي"
    (review / "municipality_names.csv").write_text(
        "name,municipality_code\n  Invented\u00a0  North  ,SYN-A\n"
        f"Only-Hyphen,SYN-A\nInvented-North,SYN-A\n{arabic},SYN-A\nOther invented,SYN-B\n",
        encoding="utf-8",
    )
    return review


def test_r5_whitespace_only_lookup_and_aliases(municipal_review):
    from eii_custodian.publicdata.frame.crosswalk import load_municipality_names

    rows = load_municipality_names(municipal_review, {"SYN-A", "SYN-B"})
    for name in ("Invented North", "  Invented\t\u00a0North\n", "Invented-North"):
        assert municipality_key(name, rows) == "SYN-A"
    for name in (
        "invented North",
        "InventedNorth",
        "Invented",
        "اسم تجريبى",
        "Only Hyphen",
    ):
        with pytest.raises(FrameError, match="unmapped municipality") as error:
            municipality_key(name, rows)
        assert name not in str(error.value)


@pytest.mark.parametrize("plant", ["conflict", "unknown_key", "same_key"])
def test_r5_crosswalk_load_validation(municipal_review, plant):
    from eii_custodian.publicdata.frame.crosswalk import load_municipality_names

    extra = {
        "conflict": "Invented North,SYN-B\n",
        "unknown_key": "Unused invented,SYN-C\n",
        "same_key": "Invented North,SYN-A\n",
    }[plant]
    with (municipal_review / "municipality_names.csv").open("a") as handle:
        handle.write(extra)
    if plant == "same_key":
        assert (
            municipality_key(
                "Invented North",
                load_municipality_names(municipal_review, {"SYN-A", "SYN-B"}),
            )
            == "SYN-A"
        )
    else:
        with pytest.raises(FrameError, match="municipality_names: " + plant):
            load_municipality_names(municipal_review, {"SYN-A", "SYN-B"})


@pytest.mark.parametrize(
    "fields",
    [("municipality", "lbldy"), ("municipality_name", "sm_lbldy"), ("municipality",)],
)
def test_r5_shared_bilingual_lookup(municipal_review, fields):
    from eii_custodian.publicdata.frame.crosswalk import (
        load_municipality_names,
        municipality_keys,
    )

    rows = load_municipality_names(municipal_review, {"SYN-A", "SYN-B"})
    record = dict(zip(fields, ("Invented North", "اسم تجريبي"), strict=False))
    assert municipality_keys("SYN-table", [record], fields, rows, None) == ["SYN-A"]
    if len(fields) == 2:
        record[fields[1]] = "Other invented"
        with pytest.raises(
            FrameError, match="SYN-table: municipality name disagreement"
        ):
            municipality_keys("SYN-table", [record], fields, rows, None)


@pytest.mark.parametrize("output", [True, False])
def test_r5_unmapped_spellings_only_in_report(
    municipal_review, tmp_path, capsys, caplog, output
):
    import json

    from eii_custodian.publicdata.frame.crosswalk import (
        load_municipality_names,
        municipality_keys,
    )

    rows = load_municipality_names(municipal_review, {"SYN-A", "SYN-B"})
    report = tmp_path / "build_report.json" if output else None
    records = [
        {"municipality": "Unmapped invented", "lbldy": "اسم مجهول"},
        {"municipality": "Unmapped invented", "lbldy": "مجهول آخر"},
    ]
    with pytest.raises(FrameError) as error:
        municipality_keys("pop_muni", records, ("municipality", "lbldy"), rows, report)
    assert (
        str(error.value)
        == "pop_muni: municipality: 1 unmapped spellings; pop_muni: lbldy: 2 unmapped spellings"
    )
    assert capsys.readouterr() == ("", "")
    assert caplog.text == ""
    if report:
        assert json.loads(report.read_text()) == {
            "pop_muni": {
                "municipality": ["Unmapped invented"],
                "lbldy": ["اسم مجهول", "مجهول آخر"],
            }
        }
