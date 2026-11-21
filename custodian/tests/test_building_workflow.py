"""Both public-build paths run the real inventory producer, with invented inputs."""

import json

import pytest
from custodian.tests.building_fixture import PARTS, table, world
from custodian.tests.test_production_adapters import context

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.frame.build import FrameResult


def prepared_frame(tmp_path, monkeypatch):
    prepared = world(tmp_path)
    review = prepared.cache.parent.parent / "custodian/publicdata/review"
    review.mkdir(parents=True)
    (review / "showcase_gazetteer.yaml").write_text("[]")
    municipality = {
        "municipality_code": "SYN-M",
        "name_en": "SYN municipality",
        "name_ar": "SYN",
        "geometry": prepared.boundary,
    }
    result = FrameResult(
        {
            "municipality": [municipality],
            "zone": [{"zone_code": "SYN-Z"}],
            "district": [{"district_key": "SYN-D"}],
            "grid_cell": [{"cell": 1}],
        },
        [],
        {key: {"sha256": "a" * 64} for key in ("bnd_hdx", "bnd_zone_2020")},
    )

    def frame(*_args, **kwargs):
        assert kwargs["selections"] is prepared.selected
        return result

    # Only the administrative assembler is supplied here; inventory production,
    # snapshot verification, publication, height reading and adapters are real.
    monkeypatch.setattr("eii_custodian.publicdata.frame.build.build_frame", frame)
    places = prepared.cache / "places_s2_t06"
    places.mkdir()
    for name in (
        "pub_place.jsonl",
        "pub_place_verification.jsonl",
        "place_points.json",
        "build_report.json",
        "flagship_check.json",
    ):
        (places / name).write_text("" if name.endswith("jsonl") else "{}")
    state = context(prepared.cache, prepared.entries)
    state.selected = prepared.selected
    state.review = review
    return prepared, state


@pytest.mark.parametrize("path", ["legacy", "assembly"])
def test_real_inventory_precedes_heights_and_binds_every_selected_id(
    tmp_path, monkeypatch, path
):
    from eii_custodian.publicdata import buildings
    from eii_custodian.publicdata.fetch.build import _heights
    from eii_custodian.publicdata.places.integrate import frame_when_ready

    prepared, state = prepared_frame(tmp_path, monkeypatch)
    calls = []
    actual = buildings.build_buildings

    def produce(*args, **kwargs):
        calls.append("inventory")
        assert not (prepared.output / "manifest.buildings.json").exists()
        return actual(*args, **kwargs)

    monkeypatch.setattr(buildings, "build_buildings", produce)
    if path == "legacy":
        frame_when_ready(
            prepared.cache, prepared.entries, state.lines, selections=prepared.selected
        )
        assert (
            _heights(
                prepared.cache,
                prepared.entries,
                state.lines,
                [],
                selections=prepared.selected,
            )
            is None
        )
    else:
        state.frame()
        assert set(state.data_files) == {
            "assets/buildings/buildings.geojson",
            "assets/buildings/manifest.buildings.json",
        }
        record = json.loads((prepared.cache / "assembly/frame.json").read_text())
        assert record["data_files"] == state.data_files
        state.heights()
        assert "building_files" in json.loads(
            (prepared.cache / "assembly/heights.json").read_text()
        )
    assert calls == ["inventory"]
    ids = {
        feature["properties"]["building_id"] for feature in table(prepared)["features"]
    }
    rows = json.loads((prepared.output.parent / "heights/heights.json").read_text())
    assert (
        ids == {"SYN-B-0", "SYN-B-1", "SYN-B-2"} == {row["building_id"] for row in rows}
    )
    assert all(
        row["height_source"] == "none" and row["height_m"] is None for row in rows
    )


@pytest.mark.parametrize("path", ["legacy", "assembly"])
def test_omitted_inventory_over_valid_old_artifacts_fails(tmp_path, monkeypatch, path):
    from eii_custodian.publicdata.fetch.build import _heights
    from eii_custodian.publicdata.places.integrate import frame_when_ready

    prepared, state = prepared_frame(tmp_path, monkeypatch)
    prepared.produce()
    monkeypatch.setattr(
        "eii_custodian.publicdata.buildings.build_buildings",
        lambda *_args, **_kwargs: None,
    )
    if path == "legacy":
        frame_when_ready(
            prepared.cache, prepared.entries, state.lines, selections=prepared.selected
        )
        failure = _heights(
            prepared.cache,
            prepared.entries,
            state.lines,
            [],
            selections=prepared.selected,
        )
        assert failure.check == "building_table_absent"
    else:
        with pytest.raises(AssemblyError, match="assembly_buildings_incomplete"):
            state.frame()
    assert not (prepared.output / "manifest.buildings.json").exists()
    assert not (prepared.output.parent / "heights/heights.json").exists()


@pytest.mark.parametrize("path", ["legacy", "assembly"])
@pytest.mark.parametrize("plant", ["missing_pin", "invalid_table"])
def test_named_inventory_failure_stops_both_callers(tmp_path, monkeypatch, path, plant):
    from eii_custodian.publicdata.buildings import BuildingError
    from eii_custodian.publicdata.heights.model import HeightError
    from eii_custodian.publicdata.places.integrate import frame_when_ready

    prepared, state = prepared_frame(tmp_path, monkeypatch)
    if plant == "missing_pin":
        del prepared.selected[PARTS[0]]
        name = "building_part_unpinned"
    else:
        name = "building_table_invalid"

        def invalid(_path):
            raise HeightError("bad_footprint")

        monkeypatch.setattr(
            "eii_custodian.publicdata.buildings.load_buildings", invalid
        )
    with pytest.raises(BuildingError, match=name):
        if path == "legacy":
            frame_when_ready(
                prepared.cache,
                prepared.entries,
                state.lines,
                selections=prepared.selected,
            )
        else:
            state.frame()
    assert f"FAIL buildings check={name}" in state.lines


def test_frame_refuses_missing_places_after_inventory(tmp_path, monkeypatch):
    prepared, state = prepared_frame(tmp_path, monkeypatch)
    (prepared.cache / "places_s2_t06/place_points.json").unlink()
    with pytest.raises(AssemblyError, match="assembly_places_incomplete"):
        state.frame()
    assert state.frame_result.tables["grid_cell"]
    assert not (prepared.cache / "assembly/frame.json").exists()


def test_assembly_build_outcome_preserves_missing_inventory_refusal(
    tmp_path, monkeypatch
):
    from eii_custodian.publicdata.assembly_adapters import Production
    from eii_custodian.publicdata.fetch.build import run_build

    def refused(_state):
        raise AssemblyError("assembly_buildings_incomplete")

    monkeypatch.setattr(Production, "run", refused)
    outcome = run_build(
        (),
        lambda _url: pytest.fail("network called"),
        tmp_path / "cache",
        lambda: "2026-11-20T00:00:00Z",
        lambda _delay: None,
        seed=17,
    )
    assert outcome.failure.check == "assembly_buildings_incomplete"


def test_legacy_build_outcome_preserves_inventory_refusal(tmp_path, monkeypatch):
    from eii_custodian.publicdata.buildings import BuildingError
    from eii_custodian.publicdata.fetch.build import run_build

    def refused(_cache, _entries, lines, **_kwargs):
        lines.append("FAIL buildings check=building_part_unpinned")
        raise BuildingError("building_part_unpinned")

    monkeypatch.setattr(
        "eii_custodian.publicdata.places.integrate.frame_when_ready", refused
    )
    outcome = run_build(
        (),
        lambda _url: pytest.fail("network called"),
        tmp_path / "cache",
        lambda: "2026-11-20T00:00:00Z",
        lambda _delay: None,
    )
    assert outcome.failure.check == "building_part_unpinned"
    assert "FAIL buildings check=building_part_unpinned" in outcome.lines
    assert not any("heights" in line for line in outcome.lines)


def test_assembly_build_outcome_preserves_inventory_refusal(tmp_path, monkeypatch):
    from eii_custodian.publicdata.assembly_adapters import Production
    from eii_custodian.publicdata.buildings import BuildingError
    from eii_custodian.publicdata.fetch.build import run_build

    def refused(state):
        state.lines.append("FAIL buildings check=building_part_unpinned")
        raise BuildingError("building_part_unpinned")

    monkeypatch.setattr(Production, "run", refused)
    outcome = run_build(
        (),
        lambda _url: pytest.fail("network called"),
        tmp_path / "cache",
        lambda: "2026-11-20T00:00:00Z",
        lambda _delay: None,
        seed=17,
    )
    assert outcome.failure.check == "building_part_unpinned"
    assert "FAIL buildings check=building_part_unpinned" in outcome.lines
