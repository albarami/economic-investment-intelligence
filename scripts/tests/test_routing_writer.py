"""Offline routing phase reuses the pinned builder, with invented PBF only."""

import json
from dataclasses import replace
from importlib import import_module
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from eii_custodian.publicdata.assembly import PHASES, AssemblyError
from eii_custodian.publicdata.assembly_adapters import Production
from eii_custodian.publicdata.assembly_inventory import INVENTORY
from eii_custodian.publicdata.fetch.bounded import file_hash
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.review.cache_fixture import write_cached
from eii_custodian.release.artefacts import RECORD

TILES = "artefacts/routing/tiles.tar"


def prepared(tmp_path: Path) -> tuple[Production, Path]:
    entry = replace(
        next(e for e in load_registry() if e.key == "roads_osm"),
        publisher="INVENTED-publisher",
        licence_id="INVENTED-licence",
        url="https://roads.invalid/extract.pbf",
    )
    # Reuse the invented source generator, not a downloaded PBF.
    from eii_product.areas_spike.extract import generate

    road = Path("product/tests/fixtures/areas_spike/road_network.json")
    path = write_cached(tmp_path, entry, generate(road, 1.0))
    build = import_module("custodian.tests.test_production_adapters").context(
        tmp_path, (entry,)
    )
    build.selected = {entry.key: path.stem}
    return build, path


def test_writer_builds_extract_and_roads_receipt_chain(tmp_path: Path) -> None:
    build, source = prepared(tmp_path)
    assert "routing" in PHASES
    assert "routing" in {item.name for item in INVENTORY}
    assert build.adapters()["routing"]() == {
        "assembly/routing.json": file_hash(tmp_path / "assembly/routing.json")
    }
    record = json.loads((tmp_path / "assembly/routing.json").read_bytes())
    reference = dict(path=TILES, sha256=file_hash(tmp_path / TILES))
    assert record["artefact"] == reference
    assert record["source_chain"]["roads_osm"]["sha256"] == source.stem
    assert record["source_chain"]["roads_osm"]["publisher"] == "INVENTED-publisher"
    assert record["source_chain"]["roads_osm"]["licence_id"] == "INVENTED-licence"
    assert record["engine_version"] == "3.9.1"
    assert json.loads((tmp_path / RECORD).read_bytes())["artefacts"] == [reference]
    assert build.files[TILES] == reference["sha256"]
    assert build.files[RECORD] == file_hash(tmp_path / RECORD)


@pytest.mark.parametrize("fault", ["no-pin", "wrong-source", "wrong-key", "build"])
def test_writer_refuses_its_specific_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from custodian.tests.snapshot_fixture import update_receipt

    from eii_custodian.publicdata.places.area_engine import PinnedEngine

    build, source = prepared(tmp_path)
    reason = "assembly_lineage_missing"
    if fault == "no-pin":
        build.selected.clear()
    elif fault in {"wrong-source", "wrong-key"}:
        update_receipt(
            tmp_path,
            "roads_osm",
            source.stem,
            {"source_id" if fault == "wrong-source" else "key": "INVENTED-other"},
        )
    else:
        reason = "assembly_routing_failed"
        monkeypatch.setattr(
            PinnedEngine,
            "write_extract",
            Mock(side_effect=RuntimeError("INVENTED-private-engine-text")),
        )
    with pytest.raises(AssemblyError, match="^" + reason + "$"):
        build.routing()
    assert not (tmp_path / TILES).exists()


def test_wheel_extract_failure_has_its_specific_reason_and_closes_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eii_custodian.publicdata.places.area_engine import PinnedEngine

    engine = PinnedEngine()
    engine._config = str(tmp_path / "config.json")
    storage = Mock()
    engine._storage = storage
    monkeypatch.setattr(engine, "prepare", lambda road: None)
    monkeypatch.setattr(
        "eii_custodian.publicdata.places.area_engine.subprocess.run",
        Mock(return_value=Mock(returncode=1)),
    )
    with pytest.raises(RuntimeError, match=r"^tile extract failed$"):
        engine.write_extract(b"INVENTED", tmp_path / "tiles.tar")
    storage.cleanup.assert_called_once()


def test_changed_osm_refuses_snapshot_hash(tmp_path: Path) -> None:
    build, source = prepared(tmp_path)
    source.write_bytes(b"INVENTED-corruption")
    with pytest.raises(ValueError, match=r"^snapshot_hash_mismatch$"):
        build.routing()


def candidate_inputs(tmp_path: Path) -> dict[str, Any]:
    from public_assembly_fixture import dump, inputs

    from eii_custodian.publicdata.fetch.snapshots import read_snapshot
    from eii_custodian.release import producer

    build, source = prepared(tmp_path)
    spec = inputs(tmp_path)
    build.routing()
    snapshot = read_snapshot(tmp_path / "roads_osm", source.stem)
    spec["sources"]["roads_osm"] = dict(
        format="sidecar",
        receipt=dict(
            path=snapshot.receipt_path.relative_to(tmp_path).as_posix(),
            sha256=file_hash(snapshot.receipt_path),
        ),
        body=dict(
            path=snapshot.path.relative_to(tmp_path).as_posix(), sha256=snapshot.sha256
        ),
    )
    spec["artefacts"] = json.loads((tmp_path / RECORD).read_bytes())["artefacts"]
    dump(tmp_path / producer.SPEC, spec)
    return spec


def test_routing_receipt_is_bound_into_prepared_release(tmp_path: Path) -> None:
    from eii_custodian.release import producer

    candidate_inputs(tmp_path)
    candidate = producer.prepare(tmp_path)
    assert "assembly/routing.json" in candidate["files"]
    assert any(s["source_id"] == "roads_osm" for s in candidate["sources"])
    from public_assembly_fixture import approve

    from eii_custodian.release.assembly import build
    from eii_product.api.area_context import routing_from_release
    from eii_product.store.release_check import check_release
    from eii_product.store.startup import verify_artefacts
    from eii_product.tools.routing import outline

    approve(tmp_path)
    producer.produce(tmp_path)
    release = tmp_path / "INVENTED-release"
    build(tmp_path, release)
    checked = check_release(release)
    verify_artefacts(checked)
    source = routing_from_release(checked)
    assert source.tile_folder is not None
    assert outline(source.tile_folder, "walk", 5, 0.0, 0.0)
    assert outline(source.tile_folder, "drive", 10, 0.0, 0.0)


@pytest.mark.parametrize(
    "fault",
    [
        "missing-record",
        "artefact",
        "source",
        "method",
        "version",
        "engine",
        "no-source",
    ],
)
def test_routing_chain_cannot_be_detached_from_release(
    tmp_path: Path, fault: str
) -> None:
    from public_assembly_fixture import dump

    from eii_custodian.release import producer

    spec = candidate_inputs(tmp_path)
    path = tmp_path / "assembly/routing.json"
    record = json.loads(path.read_bytes())
    if fault == "missing-record":
        path.unlink()
    elif fault == "no-source":
        del spec["sources"]["roads_osm"]
        dump(tmp_path / producer.SPEC, spec)
    else:
        if fault == "artefact":
            record["artefact"]["sha256"] = "00" * 32
        elif fault == "source":
            record["source_chain"]["roads_osm"]["sha256"] = "00" * 32
        else:
            record[
                {
                    "method": "method",
                    "version": "method_version",
                    "engine": "engine_version",
                }[fault]
            ] = "INVENTED-other"
        dump(path, record)
    with pytest.raises(ValueError, match=r"^producer_chain_incomplete$"):
        producer.prepare(tmp_path)


def test_every_routing_record_leaf_with_hostile_values(tmp_path: Path) -> None:
    import copy
    from collections.abc import Iterator

    from public_assembly_fixture import dump

    from eii_custodian.release import producer

    spec = candidate_inputs(tmp_path)
    path = tmp_path / "assembly/routing.json"
    original = json.loads(path.read_bytes())

    def leaves(
        value: dict[str, Any], prefix: tuple[str, ...] = ()
    ) -> Iterator[tuple[str, ...]]:
        for key, child in value.items():
            if isinstance(child, dict) and child:
                yield from leaves(child, (*prefix, key))
            else:
                yield (*prefix, key)

    hostile_values: tuple[object, ...] = ({"toString": None}, 7, None, [])
    leaf_paths = tuple(leaves(original))
    assert ("tables",) in leaf_paths
    for parts in leaf_paths:
        for hostile in hostile_values:
            changed = copy.deepcopy(original)
            parent = changed
            for part in parts[:-1]:
                parent = parent[part]
            parent[parts[-1]] = hostile
            dump(path, changed)
            try:
                candidate = producer.prepare(tmp_path)
            except ValueError as error:
                assert str(error) in {
                    "producer_chain_incomplete",
                    "producer_schema_refused",
                }
            else:
                # Unused descriptive fields never change the verified exported files.
                assert candidate["artefacts"] == spec["artefacts"]
                assert any(s["source_id"] == "roads_osm" for s in candidate["sources"])

    print(
        "hostile_leaf_coverage", len(leaf_paths), len(leaf_paths) * len(hostile_values)
    )


def test_writer_uses_only_local_ancillary_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    original = subprocess.run
    configurations = []

    def run(command: list[str], **kwargs: Any) -> Any:
        if "valhalla_build_tiles" in command:
            path = Path(command[command.index("-c") + 1])
            config = json.loads(path.read_bytes())
            for key in (
                "admin",
                "timezone",
                "landmarks",
                "traffic_extract",
                "transit_dir",
                "transit_feeds_dir",
            ):
                assert Path(config["mjolnir"][key]).is_relative_to(path.parent), key
            assert Path(config["additional_data"]["elevation"]).is_relative_to(
                path.parent
            )
            configurations.append(config)
        return original(command, **kwargs)

    monkeypatch.setattr(
        "eii_custodian.publicdata.places.area_engine.subprocess.run", run
    )
    build, _source = prepared(tmp_path)
    build.routing()
    assert len(configurations) == 1


def test_writer_refuses_uninstalled_engine_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build, _source = prepared(tmp_path)
    monkeypatch.setattr(
        "eii_custodian.publicdata.places.area_engine.version",
        lambda package: "INVENTED-uninstalled-version",
    )
    with pytest.raises(AssemblyError, match=r"^assembly_routing_failed$"):
        build.routing()
    assert not (tmp_path / TILES).exists()


def test_writer_refuses_missing_engine_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build, _source = prepared(tmp_path)

    def missing_version(package: str) -> str:
        raise PackageNotFoundError(package)

    monkeypatch.setattr(
        "eii_custodian.publicdata.places.area_engine.version", missing_version
    )
    with pytest.raises(AssemblyError, match=r"^assembly_routing_failed$"):
        build.routing()
    assert not (tmp_path / TILES).exists()
