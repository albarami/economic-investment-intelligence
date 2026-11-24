"""Walk and free-flow drive on the spike's invented road extract."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from eii_product.areas_spike.engine import scaled_actor
from eii_product.tools.routing import RoutingTilesUnavailable, outline

ROAD = json.loads(
    (
        Path(__file__).parent / "fixtures" / "areas_spike" / "road_network.json"
    ).read_text(encoding="utf-8")
)


def _tiles() -> Path:
    _actor, temporary = scaled_actor(json.dumps(ROAD, sort_keys=True), 1.0)
    folder = Path(temporary.name)
    assert (folder / "config.json").is_file()
    return folder


def test_importing_tools_loads_no_engine() -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    def loads(code: str) -> None:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr

    loads(
        "import eii_product.tools.routing, sys\nassert 'valhalla' not in sys.modules\n"
    )
    with pytest.raises(AssertionError):
        loads("import valhalla, sys\nassert 'valhalla' not in sys.modules\n")


def test_walk_and_drive_on_invented_tiles() -> None:
    folder = _tiles()
    walk = outline(folder, "walk", 5, 0.0, 0.0)
    drive = outline(folder, "drive", 10, 0.0, 0.0)
    assert len(walk) >= 4
    assert len(drive) >= 4
    assert walk == outline(folder, "walk", 5, 0.0, 0.0)


def test_routing_opens_no_server_or_subprocess() -> None:
    folder = _tiles()

    def route() -> None:
        outline(folder, "walk", 5, 0.0, 0.0)

    with (
        patch.object(socket, "socket", side_effect=AssertionError("socket")),
        patch.object(
            socket, "create_connection", side_effect=AssertionError("connection")
        ),
        patch.object(subprocess, "Popen", side_effect=AssertionError("process")),
    ):
        route()

        def opens() -> None:
            socket.socket()

        with pytest.raises(AssertionError, match="socket"):
            opens()


def _names_no_path(error: BaseException, folder: Path) -> None:
    parts = (str(error), str(error.__cause__), str(error.__context__))
    text = " ".join(parts)
    assert folder.name not in text
    assert str(folder) not in text
    assert error.__cause__ is None
    assert error.__context__ is None


def test_unreadable_configuration_names_no_path() -> None:
    folder = _tiles()
    config = folder / "config.json"
    config.chmod(0)
    try:
        with pytest.raises(
            RoutingTilesUnavailable, match="operation_os_error"
        ) as caught:
            outline(folder, "walk", 5, 0.0, 0.0)
        _names_no_path(caught.value, folder)
    finally:
        config.chmod(0o644)


def test_unreadable_tile_folder_names_no_path() -> None:
    folder = _tiles()
    tile_root = next(path for path in folder.iterdir() if path.is_dir())
    tile_root.chmod(0)
    try:
        with pytest.raises(
            RoutingTilesUnavailable, match="routing tiles unavailable"
        ) as caught:
            outline(folder, "walk", 5, 0.0, 0.0)
        _names_no_path(caught.value, folder)
    finally:
        tile_root.chmod(0o755)


def test_missing_tile_folder_names_no_path(tmp_path: Path) -> None:
    missing = tmp_path / "absent-tiles"
    with pytest.raises(
        RoutingTilesUnavailable, match="routing tiles unavailable"
    ) as caught:
        outline(missing, "walk", 5, 0.0, 0.0)
    assert "absent-tiles" not in str(caught.value)
    assert str(tmp_path) not in str(caught.value)
