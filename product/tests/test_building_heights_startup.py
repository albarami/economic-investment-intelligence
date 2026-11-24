"""S3-T16 startup wiring: an invented release carrying the heights artefacts.

The release manifest lists ``artefacts/heights/`` (the three released files
and ``<sha256>.json``); every startup path mounts the checked release in
``create_app``, which reads the heights from that pin. Invented buildings
SYN-B-*, ``.invalid`` hosts and an invented database host only.
"""

from __future__ import annotations

import ast
import hashlib
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from product.tests.public_http_support import Client
from product.tests.test_building_heights_read import write_asset
from public_release_fixture import build_fixture
from routing_release_fixture import TILES, invented_extract
from test_live_public_release_load import _RecordingPostgres

from eii_product.api.building_heights import (
    RELEASE_FOLDER,
    HeightsRefusal,
    heights_from_release,
)
from eii_product.store.loader import _parquet_rows, run_load
from eii_product.store.release_check import check_release, manifest_rows
from operations.development import serve_embedded

ROOT = Path(__file__).resolve().parents[2]


def _refs(folder: Path) -> list[dict[str, str]]:
    return sorted(
        (
            {
                "path": RELEASE_FOLDER + path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in folder.iterdir()
        ),
        key=lambda ref: ref["path"],
    )


def _release(root: Path) -> tuple[Path, str, str]:
    """Build, copy in and load an invented release with the heights artefacts."""
    asset = root / "asset"
    pin = write_asset(asset)
    folder = root / "release"
    # The base's startup also mounts the release's one routing extract
    # (decision 0096 item 2), so the invented release carries it too.
    routing = invented_extract(folder / TILES)
    identity = build_fixture(folder, cards=True, artefacts=(routing, *_refs(asset)))
    shutil.copytree(asset, folder / RELEASE_FOLDER)
    checked = check_release(folder)
    rows = {
        entry["name"]: _parquet_rows(
            folder / entry["file"], checked.schemas[entry["name"]]
        )
        for entry in checked.document["tables"]  # type: ignore[union-attr]
    }
    rows["release_manifest"] = manifest_rows(checked.document)
    connection = _RecordingPostgres(rows, names=tuple(rows), columns=checked.schemas)
    code = run_load(
        folder,
        host="invented.invalid",
        port=1,
        database="INVENTED",
        connect=lambda **_kw: connection,
    )
    assert code == 0
    return folder, identity, pin


def test_embedded_startup_serves_the_released_heights(tmp_path: Path) -> None:
    folder, identity, pin = _release(tmp_path)
    home = tmp_path / "development"
    target = home / "releases" / identity
    target.parent.mkdir(parents=True)
    shutil.copytree(folder, target)
    served: list[dict[str, Any]] = []

    def server(app: Any, **_options: object) -> None:
        response = Client(app).get("/api/building-heights")
        assert response.status_code == 200
        served.append(response.json())

    serve_embedded(
        tmp_path,
        dict(
            EII_ENVIRONMENT="development",
            EII_RELEASE_DIR=str(target),
            EII_STATE_DIR=str(home / "state"),
        ),
        server=server,
    )
    assert [body["release_id"] for body in served] == [pin]
    assert len(served[0]["buildings"]) == 4
    assert {row["sourceId"] for row in served[0]["sources"]} >= {
        "bldg_ovt/invented-part-0",
        "landmark_heights/SYN-LM-0001",
    }


def _create_app_keywords(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "create_app"
    ]
    assert len(calls) == 1
    return {keyword.arg for keyword in calls[0].keywords if keyword.arg}


@pytest.mark.parametrize(
    "path", ["scripts/operations/serve.py", "scripts/operations/development.py"]
)
def test_every_startup_path_mounts_its_release_for_the_heights(path: str) -> None:
    # The installed entry cannot run here (it needs an installed application
    # and an activation log); it reaches the same mount as the embedded one.
    keywords = _create_app_keywords(ROOT / path)
    assert {"store", "release_dir"} <= keywords
    assert "heights" not in keywords


def _entries(tmp_path: Path) -> tuple[Path, list[dict[str, str]]]:
    asset = tmp_path / "release" / RELEASE_FOLDER
    write_asset(asset)
    return tmp_path / "release", _refs(asset)


def test_a_release_without_heights_entries_has_no_heights(tmp_path: Path) -> None:
    other = [{"path": "artefacts/routing/", "sha256": "a" * 64}]
    assert heights_from_release(tmp_path, other) is None
    assert heights_from_release(tmp_path, []) is None


def test_a_release_with_the_four_entries_reads_its_pin(tmp_path: Path) -> None:
    folder, refs = _entries(tmp_path)
    read = heights_from_release(folder, refs)
    assert read is not None
    pins = [r["sha256"] for r in refs if r["path"].endswith(r["sha256"] + ".json")]
    assert read.release_id == pins[0]


def _drop_table(refs: list[dict[str, str]]) -> None:
    refs[:] = [r for r in refs if not r["path"].endswith("buildings.geojson")]


def _extra_entry(refs: list[dict[str, str]]) -> None:
    refs.append({"path": RELEASE_FOLDER + "extra.json", "sha256": "b" * 64})


def _pin_not_name(refs: list[dict[str, str]]) -> None:
    for ref in refs:
        if ref["path"].endswith(ref["sha256"] + ".json"):
            ref["sha256"] = "c" * 64


def _second_manifest(refs: list[dict[str, str]]) -> None:
    refs.append({"path": RELEASE_FOLDER + "d" * 64 + ".json", "sha256": "d" * 64})


def _repeated_entry(refs: list[dict[str, str]]) -> None:
    # A second heights.json entry; the single pin alone does not refuse it.
    heights = next(r for r in refs if r["path"].endswith("/heights.json"))
    refs.append({**heights, "sha256": "e" * 64})


def _not_a_list(refs: list[dict[str, str]]) -> object:
    return {"artefacts": refs}


@pytest.mark.parametrize(
    "change",
    [_drop_table, _extra_entry, _pin_not_name, _second_manifest, _repeated_entry],
)
def test_one_changed_entry_refuses_the_release_heights(
    tmp_path: Path, change: Callable[[list[dict[str, str]]], None]
) -> None:
    folder, refs = _entries(tmp_path)
    change(refs)
    with pytest.raises(HeightsRefusal, match=r"^heights_release_artefacts$"):
        heights_from_release(folder, refs)


def test_artefacts_that_are_not_a_list_refuse(tmp_path: Path) -> None:
    folder, refs = _entries(tmp_path)
    with pytest.raises(HeightsRefusal, match=r"^heights_release_artefacts$"):
        heights_from_release(folder, _not_a_list(refs))


def test_a_changed_released_file_refuses_through_the_pin(tmp_path: Path) -> None:
    folder, refs = _entries(tmp_path)
    (folder / RELEASE_FOLDER / "manifest.buildings.json").write_bytes(b"{}\n")
    with pytest.raises(HeightsRefusal, match=r"^heights_file_integrity$"):
        heights_from_release(folder, refs)
