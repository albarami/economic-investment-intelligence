"""The shared building-table helper is the non-heights build path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from custodian.tests.building_fixture import PARTS, bind_height_table, world
from custodian.tests.fixtures.atlas.invented import (
    configuration,
    entry,
    metadata,
    stream,
)
from custodian.tests.support.buildings import (
    building_table_path,
    ensure_minimal_building_table,
)
from custodian.tests.support.fetch_build import run_build

from eii_custodian.publicdata.atlas.config import Config
from eii_custodian.publicdata.fetch.build import _heights
from eii_custodian.publicdata.fetch.build import run_build as production_run_build


def test_run_build_leaves_unrelated_assets_in_non_pytest_named_dir(
    tmp_path: Path,
) -> None:
    """Unrelated assets survive when the cache sits in a non-temporary ``pytest-*`` folder."""
    workspace = tmp_path / "pytest-not-temporary"
    cache = workspace / "cache"
    cache.mkdir(parents=True)
    marker = workspace / "assets" / "unrelated-marker.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("keep", encoding="utf-8")

    outcome = run_build(
        [entry()],
        metadata,
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        atlas_stream=stream,
        atlas_config=Config.from_mapping(configuration()),
    )
    assert outcome.failure is None
    assert marker.is_file(), "cleanup deleted an unrelated asset"
    assert marker.read_text(encoding="utf-8") == "keep"


def test_minimal_building_table_satisfies_run_build(tmp_path: Path) -> None:
    """Without the helper's table the same build refuses ``building_table_absent``."""
    cache = tmp_path / "data" / "public_cache"
    cache.mkdir(parents=True)
    refused = production_run_build(
        [entry()],
        metadata,
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        atlas_stream=stream,
        atlas_config=Config.from_mapping(configuration()),
    )
    assert refused.failure is not None
    assert refused.failure.check == "building_table_absent"

    ensure_minimal_building_table(cache)
    path = building_table_path(cache.parent)
    assert path.is_file()
    entries = bind_height_table(cache, [entry()], path, write_manifest=False)
    assert _heights(cache, entries, [], []) is None
    path.unlink()
    with pytest.raises((FileNotFoundError, OSError)):
        path.read_bytes()
    refused_again = _heights(cache, entries, [], [])
    assert refused_again is not None
    assert refused_again.check == "building_table_absent"


@pytest.mark.parametrize("plant", ["missing_manifest", "altered_hash"])
def test_shared_helper_manifest_is_required_and_verified(
    tmp_path: Path, plant: str
) -> None:
    cache = tmp_path / "data/public_cache"
    path, _ = ensure_minimal_building_table(cache)
    entries = bind_height_table(cache, (), path, write_manifest=False)
    assert _heights(cache, entries, [], []) is None
    manifest = path.with_name("manifest.buildings.json")
    if plant == "missing_manifest":
        manifest.unlink()
        expected = "building_manifest_absent"
    else:
        block = json.loads(manifest.read_text())
        block["output_sha256"] = "0" * 64
        manifest.write_text(json.dumps(block))
        expected = "building_table_hash"
    refused = _heights(cache, entries, [], [])
    assert refused is not None
    assert refused.check == expected
    assert not (cache.parent / "assets/heights/heights.json").exists()


def test_missing_part_registration_still_refuses(tmp_path: Path) -> None:
    from eii_custodian.publicdata.building_inputs import BuildingError

    prepared = world(tmp_path)
    prepared.produce()
    prepared.entries = tuple(row for row in prepared.entries if row.key != PARTS[0])
    with pytest.raises(BuildingError) as refused:
        prepared.produce()
    assert refused.value.name == "building_part_unregistered"
    assert refused.value.detail == PARTS[0]


def test_run_build_verifies_the_shared_helper_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    from custodian.tests.support import fetch_build

    original = fetch_build.ensure_minimal_building_table

    def tampered(cache):
        path, created = original(cache)
        manifest = path.with_name("manifest.buildings.json")
        block = json.loads(manifest.read_text())
        block["output_sha256"] = "0" * 64
        manifest.write_text(json.dumps(block))
        return path, created

    monkeypatch.setattr(fetch_build, "ensure_minimal_building_table", tampered)
    cache = tmp_path / "data/public_cache"
    outcome = run_build(
        [entry()],
        metadata,
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        atlas_stream=stream,
        atlas_config=Config.from_mapping(configuration()),
    )
    assert outcome.failure is not None
    assert outcome.failure.check == "building_table_hash"
    assert not building_table_path(cache.parent).exists()
    assert not (cache.parent / "assets/heights/heights.json").exists()
    assert not list(cache.glob("bldg_ovt/**/*.meta.json"))
    assert not (cache / "snapshot_pins.json").exists()


def test_run_build_restores_fixture_pins_and_preserves_existing_receipts(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "data/public_cache"
    path, _ = ensure_minimal_building_table(cache)
    before = {file: file.read_bytes() for file in cache.rglob("*") if file.is_file()}
    outcome = run_build(
        [entry()],
        metadata,
        cache,
        lambda: "2026-11-16T00:00:00Z",
        lambda _: None,
        atlas_stream=stream,
        atlas_config=Config.from_mapping(configuration()),
    )
    assert outcome.failure is None
    assert not path.exists()
    assert all(file.read_bytes() == body for file, body in before.items())


def test_atlas_fixture_contains_its_height_outputs(tmp_path: Path) -> None:
    """The real Atlas fixture must keep both height files inside its own directory."""
    from custodian.tests.test_atlas_fetch import test_atlas_complete_archive

    from eii_custodian.publicdata.heights.model import (
        HEIGHTS_FILE,
        HEIGHTS_RELATIVE,
        MANIFEST_FILE,
    )

    fixture_root = tmp_path / "atlas-fixture"
    fixture_root.mkdir()
    test_atlas_complete_archive(fixture_root)
    for filename in (HEIGHTS_FILE, MANIFEST_FILE):
        outputs = list(tmp_path.rglob(filename))
        assert outputs, f"missing height output: {filename}"
        assert all(path.is_relative_to(fixture_root) for path in outputs), (
            "height output escaped its fixture tmp_path"
        )
        assert outputs == [fixture_root / "data" / HEIGHTS_RELATIVE / filename]
