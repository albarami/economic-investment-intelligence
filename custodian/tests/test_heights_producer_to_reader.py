"""S3-T16: the S2-T20 heights producer's own output read by the product.

The heights step runs on the card's invented fixture (SYN-B-*, ``.invalid``
hosts, invented receipts in a temporary cache), with one invented landmark
citation. Its outputs are bound by an invented ``heights`` phase record,
placed as release artefacts by ``stage_heights`` through ``place_artefact`` and read through the
product's startup function, so every field the reader requires is the one
the producer writes. No real cache or file is read.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from custodian.tests.test_publicdata_heights import _card_setup
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from eii_custodian.publicdata.heights import step
from eii_custodian.publicdata.heights.landmarks import (
    LANDMARK_FIXTURE_PATH,
    LandmarkRecord,
    load_landmark_heights,
)
from eii_custodian.release import heights_artefacts
from eii_custodian.release.heights_artefacts import stage_heights
from eii_product.api.building_heights import HeightsRefusal, heights_from_release

LANDMARK_BUILDING = "SYN-B-0004"


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _dump(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True) + "\n").encode()


@pytest.fixture
def produced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run the producer with one landmark; return the data root."""
    row = replace(
        load_landmark_heights(LANDMARK_FIXTURE_PATH)[0], building_id=LANDMARK_BUILDING
    )
    # The base's step reads one landmark record (rows, readiness and bytes).
    record = LandmarkRecord((row,), "", LANDMARK_FIXTURE_PATH.read_bytes())
    monkeypatch.setattr(step, "load_landmark_record", lambda _path: record)
    # The page receipt check is the producer's own; it has its own tests.
    monkeypatch.setattr(step, "verify_landmark_receipts", lambda _cache, _rows: None)
    _card_setup(tmp_path)
    data = tmp_path / "data"
    _record(data)
    return data


def _record(data: Path) -> None:
    """The invented ``heights`` phase record binding the four files."""
    files = {
        name: _sha((data / "assets/heights" / name).read_bytes())
        for name in ("heights.json", "manifest.heights.json")
    }
    building = {
        name: _sha((data / name).read_bytes())
        for name in (
            "assets/buildings/buildings.geojson",
            "assets/buildings/manifest.buildings.json",
        )
    }
    record = data / "public_cache/assembly/heights.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_bytes(
        _dump({"state": "built", "files": files, "building_files": building})
    )


def _read(data: Path) -> dict[str, Any]:
    cache = data / "public_cache"
    read = heights_from_release(cache, stage_heights(cache))
    assert read is not None
    return read.read()


def test_the_producers_output_reads_whole_with_every_chain(produced: Path) -> None:
    body = _read(produced)
    sources = {row["sourceId"]: row for row in body["sources"]}
    fetched = [key for key in sources if key.startswith("bldg_3dglobfp")]
    assert fetched and all(sources[key]["publisher"] for key in fetched)
    inventory = json.loads(
        (produced / "assets/buildings/manifest.buildings.json").read_bytes()
    )["source_chain"]
    assert set(inventory) <= set(sources)
    landmark = sources["landmark_heights/SYN-LM-0001"]
    assert landmark["publisher"] == "Fixture Heights Publisher"
    assert landmark["datasetOrPage"] == "https://syn-heights.invalid/SYN/landmark-page"
    assert body["lineage"]["sourceIds"] == sorted(sources)
    assert len(body["buildings"]) == 7
    assert body["facts"]


def _heights_manifest(data: Path, change: Callable[[dict[str, Any]], None]) -> None:
    path = data / "assets/heights/manifest.heights.json"
    manifest = json.loads(path.read_bytes())
    change(manifest)
    path.write_bytes(_dump(manifest))


def _inventory(data: Path, change: Callable[[dict[str, Any]], None]) -> None:
    """Change the inventory manifest and carry its new hash into the heights one."""
    path = data / "assets/buildings/manifest.buildings.json"
    inventory = json.loads(path.read_bytes())
    change(inventory)
    path.write_bytes(_dump(inventory))

    def relink(manifest: dict[str, Any]) -> None:
        for record in manifest["files"]:
            if record["key"] == "building_table":
                record["source_chain"]["sha256"] = _sha(path.read_bytes())

    _heights_manifest(data, relink)


def _no_fetched_publisher(data: Path) -> None:
    def change(manifest: dict[str, Any]) -> None:
        for record in manifest["files"]:
            if record["key"].startswith("bldg_"):
                del record["publisher"]

    _heights_manifest(data, change)


def _no_inventory_publisher(data: Path) -> None:
    def change(inventory: dict[str, Any]) -> None:
        del next(iter(inventory["source_chain"].values()))["publisher"]

    _inventory(data, change)


def _no_landmark_publisher(data: Path) -> None:
    def change(manifest: dict[str, Any]) -> None:
        del manifest["landmark_heights"][0]["citation"]["publisher"]

    _heights_manifest(data, change)


def _no_building_link(data: Path) -> None:
    def change(manifest: dict[str, Any]) -> None:
        for record in manifest["files"]:
            if record["key"] == "building_table":
                del record["source_chain"]

    _heights_manifest(data, change)


@pytest.mark.parametrize(
    "plant",
    [
        _no_fetched_publisher,
        _no_inventory_publisher,
        _no_landmark_publisher,
        _no_building_link,
    ],
)
def test_a_missing_link_of_the_producers_output_refuses(
    produced: Path, plant: Callable[[Path], None]
) -> None:
    plant(produced)
    _record(produced)
    with pytest.raises(HeightsRefusal, match=r"^heights_lineage$"):
        _read(produced)


def test_no_heights_record_stages_nothing(tmp_path: Path) -> None:
    (tmp_path / "public_cache").mkdir()
    assert stage_heights(tmp_path / "public_cache") == []


def test_a_record_not_built_refuses_staging(produced: Path) -> None:
    record = produced / "public_cache/assembly/heights.json"
    value = json.loads(record.read_bytes())
    record.write_bytes(_dump({**value, "state": "NO_DATA"}))
    with pytest.raises(ValueError, match=r"^assembly_heights_incomplete$"):
        stage_heights(produced / "public_cache")


def test_a_file_changed_after_its_record_refuses_staging(produced: Path) -> None:
    path = produced / "assets/heights/heights.json"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match=r"^assembly_heights_incomplete$"):
        stage_heights(produced / "public_cache")
    # Checked before any copy: nothing is placed.
    assert not (produced / "public_cache/artefacts").exists()


def test_a_missing_recorded_source_file_refuses_staging(produced: Path) -> None:
    # The first recorded file in name order, so a missed read cannot fall
    # through onto the previous file's bytes and the hash check.
    (produced / "assets/buildings/buildings.geojson").unlink()
    with pytest.raises(ValueError, match=r"^assembly_heights_incomplete$"):
        stage_heights(produced / "public_cache")


def test_a_symlinked_recorded_source_file_refuses_staging(produced: Path) -> None:
    """The pinned no-follow read refuses a symlink; staging names its own reason."""
    path = produced / "assets/heights/heights.json"
    moved = produced / "INVENTED-heights.json"
    path.rename(moved)
    path.symlink_to(moved)
    with pytest.raises(ValueError, match=r"^assembly_heights_incomplete$"):
        stage_heights(produced / "public_cache")
    assert not (produced / "public_cache/artefacts").exists()


def test_a_refused_placement_refuses_staging(
    produced: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_args: object) -> dict[str, str]:
        raise ValueError("artefact_not_regular")

    monkeypatch.setattr(heights_artefacts, "place_artefact", refuse)
    with pytest.raises(ValueError, match=r"^assembly_heights_incomplete$"):
        stage_heights(produced / "public_cache")


def test_bytes_changed_between_check_and_copy_refuse_staging(
    produced: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The writer's own hash of the copied bytes must still be the record's."""
    place = heights_artefacts.place_artefact

    def changed(cache: Path, relative: str, source: Path) -> dict[str, str]:
        source.write_bytes(source.read_bytes() + b" ")
        return place(cache, relative, source)

    monkeypatch.setattr(heights_artefacts, "place_artefact", changed)
    with pytest.raises(ValueError, match=r"^assembly_heights_incomplete$"):
        stage_heights(produced / "public_cache")


@pytest.mark.parametrize(
    ("field", "change"),
    [
        ("files", lambda files: {**files, "INVENTED.json": "0" * 64}),
        ("files", lambda files: {"heights.json": files["heights.json"]}),
        ("files", lambda files: sorted(files)),
        ("building_files", lambda files: {**files, "INVENTED.json": "0" * 64}),
        ("building_files", lambda files: dict(list(files.items())[:1])),
        ("building_files", lambda files: None),
    ],
    ids=[
        "extra-file",
        "missing-file",
        "files-not-object",
        "extra-building-file",
        "missing-building-file",
        "building-files-null",
    ],
)
def test_a_record_with_another_file_set_refuses_staging(
    produced: Path, field: str, change: Callable[[Any], Any]
) -> None:
    record = produced / "public_cache/assembly/heights.json"
    value = json.loads(record.read_bytes())
    record.write_bytes(_dump({**value, field: change(value[field])}))
    with pytest.raises(ValueError, match=r"^assembly_heights_incomplete$"):
        stage_heights(produced / "public_cache")


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    names=st.sets(
        st.sampled_from(["heights.json", "manifest.heights.json", "INVENTED.json"])
    )
)
def test_any_other_heights_file_set_refuses_staging(
    produced: Path, names: set[str]
) -> None:
    """Every file-name set but exactly the two heights files refuses."""
    _record(produced)  # the fixture is shared by every example
    record = produced / "public_cache/assembly/heights.json"
    value = json.loads(record.read_bytes())
    files = {name: value["files"].get(name, "0" * 64) for name in names}
    record.write_bytes(_dump({**value, "files": files}))
    if names == {"heights.json", "manifest.heights.json"}:
        assert len(stage_heights(produced / "public_cache")) == 4
    else:
        with pytest.raises(ValueError, match=r"^assembly_heights_incomplete$"):
            stage_heights(produced / "public_cache")
