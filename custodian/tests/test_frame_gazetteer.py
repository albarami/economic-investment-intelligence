"""All named examples are invented; no coordinates for real named places."""

import pytest
from custodian.tests.test_frame_coverage import invented_frame

from eii_custodian.publicdata.frame.checks import FrameError
from eii_custodian.publicdata.frame.gazetteer import (
    administrative_rows,
    reviewed_points,
)
from eii_custodian.publicdata.frame.grid import build_grid, ownership_index
from eii_custodian.publicdata.frame.live import resolve_reviewed_specs


def test_administrative_names_and_interior_points():
    municipalities, zones, districts = invented_frame()
    grid = build_grid(municipalities, zones, districts, set())
    rows = administrative_rows(municipalities, zones, districts, grid)
    assert len(rows) == 4
    assert {row["source_id"] for row in rows} == {"bnd_hdx"}
    assert {row["kind"] for row in rows} == {"municipality", "zone", "district"}
    assert not any(row["showcase_verified"] for row in rows)
    assert all(row["cell"] in {r["cell"] for r in grid} for row in rows)


def test_showcases_and_candidates_resolve_from_source_points():
    grid = build_grid(*invented_frame(), set())
    import h3

    lat, lon = h3.cell_to_latlng(h3.int_to_str(grid[0]["cell"]))
    specs = [
        {
            "place_key": f"SYN-P-{i}",
            "kind": "landmark" if i < 4 else "building",
            "name_en": f"Invented place {i}",
            "name_ar": "اسم تجريبي",
            "aliases": None,
            "source_id": "places_ovt",
            "record_key": f"SYN-R-{i}",
            "arabic_review": "pending native review",
        }
        for i in range(11)
    ]
    points = {("places_ovt", f"SYN-R-{i}"): {"lon": lon, "lat": lat} for i in range(11)}
    rows = reviewed_points(specs, points, grid)
    assert len(rows) == 11
    assert sum(row["kind"] == "landmark" for row in rows) == 4
    assert sum(row["kind"] == "building" for row in rows) == 7
    del points[("places_ovt", "SYN-R-10")]
    with pytest.raises(FrameError, match="source point"):
        reviewed_points(specs, points, grid)


def test_null_source_stays_pending_and_a_filled_source_resolves():
    grid = build_grid(*invented_frame(), set())
    import h3

    lat, lon = h3.cell_to_latlng(h3.int_to_str(grid[0]["cell"]))
    report: list[str] = []
    assert (
        resolve_reviewed_specs(
            [{"place_key": "SYN-pending", "source_id": None, "record_key": None}],
            {},
            grid,
            report,
        )
        == []
    )
    assert report == ["gazetteer: source point pending S2-T06: SYN-pending"]
    filled: list[str] = []
    resolved = resolve_reviewed_specs(
        [
            {
                "place_key": "SYN-P",
                "kind": "landmark",
                "name_en": "SYN Invented",
                "name_ar": "اسم تجريبي",
                "aliases": None,
                "source_id": "places_ovt",
                "record_key": "SYN-R",
                "arabic_review": "pending native review",
            }
        ],
        {("places_ovt", "SYN-R"): {"lon": lon, "lat": lat}},
        grid,
        filled,
    )
    assert filled == []
    assert resolved[0]["source_id"] == "places_ovt"
    assert resolved[0]["place_key"] == "SYN-P"
    assert resolved[0]["name_en"] == "SYN Invented"
    pending: list[str] = []
    assert (
        resolve_reviewed_specs(
            [{"place_key": "SYN-EMPTY", "source_id": "", "record_key": "SYN-R"}],
            {},
            grid,
            pending,
        )
        == []
    )
    assert pending == ["gazetteer: source point pending S2-T06: SYN-EMPTY"]


def test_gazetteer_guard_violations():
    import h3
    from eii_custodian.publicdata.frame.gazetteer import make_row, point_cell

    grid = build_grid(*invented_frame(), set())
    lat, lon = h3.cell_to_latlng(h3.int_to_str(grid[0]["cell"]))
    spec = {
        "place_key": "SYN-P",
        "kind": "building",
        "name_en": "Invented",
        "name_ar": "اسم تجريبي",
        "aliases": None,
        "source_id": "places_ovt",
        "record_key": "SYN-R",
        "arabic_review": "pending native review",
    }
    points = {("places_ovt", "SYN-R"): {"lon": lon, "lat": lat}}
    with pytest.raises(FrameError, match="duplicate place key"):
        reviewed_points([spec, spec], points, grid)
    with pytest.raises(FrameError, match="invalid reviewed kind"):
        reviewed_points([{**spec, "kind": "invented-kind"}], points, grid)
    with pytest.raises(FrameError, match="Arabic review"):
        reviewed_points([{**spec, "arabic_review": "unmarked"}], points, grid)
    assert (
        len(reviewed_points([{**spec, "arabic_review": "approved"}], points, grid)) == 1
    )
    for en, ar in [("", "اسم تجريبي"), ("Invented", "")]:
        with pytest.raises(FrameError, match="bilingual name"):
            make_row(
                "SYN-P",
                "building",
                en,
                ar,
                None,
                lon,
                lat,
                "places_ovt",
                ownership_index(grid),
            )
    assert point_cell(lon, lat, frozenset()) is None
    with pytest.raises(FrameError, match="no unique base cell"):
        point_cell(
            lon,
            lat,
            frozenset(h3.str_to_int(h3.latlng_to_cell(lat, lon, r)) for r in (8, 9)),
        )
    rendered = make_row(
        "SYN-P",
        "building",
        "Invented",
        "اسم تجريبي",
        "Invented alias",
        lon,
        lat,
        "places_ovt",
        ownership_index(grid),
    )
    assert rendered["aliases"] == "Invented alias"
    assert set(rendered) == {
        "place_key",
        "kind",
        "name_en",
        "name_ar",
        "aliases",
        "lon",
        "lat",
        "cell",
        "showcase_verified",
        "source_id",
    }
