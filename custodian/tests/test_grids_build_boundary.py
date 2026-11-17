"""Grid-build encoding and cache-key bounds. Invented weather only."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from custodian.tests.fixtures.grids.invented import store, weather_point
from custodian.tests.repository_root import repository_root

import eii_custodian.publicdata.grids.build as grids_build
from eii_custodian.publicdata.grids.build import build_grids
from eii_custodian.publicdata.grids.contracts import GridError

_CHILD = """\
import sys
from pathlib import Path

from custodian.tests.fixtures.grids.invented import weather_point
from eii_custodian.publicdata.grids.build import build_grids

build_grids(Path(sys.argv[1]), (weather_point(),), {})
"""

_KEY_MESSAGE = "weather_openmeteo: key escapes the cache"
_WEATHER_KEY = "weather_openmeteo/2024-2025/point"


def _body() -> bytes:
    payload = {
        "latitude": 1.1,
        "longitude": 2.1,
        "timezone": "Asia/Qatar",
        "utc_offset_seconds": 10800,
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
        "hourly": {
            "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
            "temperature_2m": [20, 21],
        },
    }
    return json.dumps(payload).encode("utf-8")


def _weather_text(digest: str) -> str:
    written = {
        "source_id": "weather_openmeteo",
        "requested_coordinates": [1.0, 2.0],
        "provider_coordinates": [1.1, 2.1],
        "hourly": {
            "time": ["2023-12-31T21:00:00Z", "2023-12-31T22:00:00Z"],
            "temperature_2m": [20, 21],
        },
        "hourly_units": {"time": "UTC", "temperature_2m": "°C"},
        "timezone": "Asia/Qatar",
        "utc_offset_seconds": 10800,
        "attribution": (
            "Weather data by Open-Meteo.com — https://open-meteo.com/; "
            "https://creativecommons.org/licenses/by/4.0/; "
            "Generated using Copernicus Climate Change Service information 2022. "
            "Times converted to UTC."
        ),
        "licence_basis": "provider_terms",
        "release_tables": [],
        "source_key": _WEATHER_KEY,
        "source_sha256": digest,
        "variables": ["temperature_2m"],
    }
    return json.dumps(written, sort_keys=True, ensure_ascii=True) + "\n"


def _manifest_text(digest: str, nbytes: int) -> str:
    manifest = {
        "method": {
            "ntl_blackmarble": "C36",
            "worldpop_qat_agesex": "C38",
            "weather_openmeteo": "weather.v1",
        },
        "method_version": {
            "ntl_blackmarble": "MTH-109",
            "worldpop_qat_agesex": "MTH-111",
            "weather_openmeteo": "weather.v1",
        },
        "files": [
            {
                "key": _WEATHER_KEY,
                "source_id": "weather_openmeteo",
                "publisher": "SYN-publisher",
                "licence_id": "CC-BY-4.0",
                "licence_basis": "provider_terms",
                "retrieved_utc": "2026-11-14T00:00:00Z",
                "sha256": digest,
                "bytes": nbytes,
                "period": "2024-01-01T00:00",
                "period_first": "2024-01-01T00:00",
                "period_last": "2024-01-01T01:00",
                "tile": "",
                "sex": "",
                "age_code": "",
                "release": "",
                "year": "",
                "cell_units": "",
                "doi": "",
                "doi_confirmed": False,
                "variables": ["temperature_2m"],
                "method": "weather.v1",
                "method_version": "weather.v1",
            }
        ],
        "tables": {
            "pub_night_lights": 0,
            "pub_pop_agesex_grid": 0,
            "fact_lineage": 0,
            "source_registry": 1,
        },
    }
    return json.dumps(manifest, sort_keys=True, ensure_ascii=True) + "\n"


def _refuse(cache: Path, key: str) -> None:
    with pytest.raises(GridError) as caught:
        build_grids(cache, (weather_point(key),), {})
    assert str(caught.value) == _KEY_MESSAGE


def test_every_text_read_and_write_of_the_grid_build_names_its_encoding(
    tmp_path: Path,
) -> None:
    """Every text read and write of the grid build names its encoding, so the build never reads the locale."""
    body = _body()
    row = weather_point()
    store(tmp_path, row, body)
    # The mutation runner's stats pass sets MUTANT_UNDER_TEST to "stats". A child
    # then records the hit by reading setup.cfg with no encoding, and the warning
    # flag turns that into a failure. Call in-process for that pass so the hit is
    # recorded here; every other pass, including a real mutant, runs in the child.
    if os.environ.get("MUTANT_UNDER_TEST") == "stats":
        build_grids(tmp_path, (row,), {})
    else:
        source = Path(grids_build.__file__).resolve().parents[3]
        root = repository_root(Path(__file__))
        prior = os.environ.get("PYTHONPATH", "")
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(source), str(root), prior) if part
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-X",
                "warn_default_encoding",
                "-W",
                "error::EncodingWarning",
                "-c",
                _CHILD,
                str(tmp_path),
            ],
            check=False,
            capture_output=True,
            env=env,
            cwd=root,
        )
        detail = completed.stderr.decode().strip().splitlines()
        assert completed.returncode == 0, detail[-1] if detail else completed.returncode
    digest = hashlib.sha256(body).hexdigest()
    weather = tmp_path / "grids" / "weather_openmeteo.json"
    manifest = tmp_path / "grids" / "manifest.json"
    assert weather.read_bytes() == _weather_text(digest).encode("ascii")
    assert manifest.read_bytes() == _manifest_text(digest, len(body)).encode("ascii")


def test_grid_build_refuses_an_absolute_key(tmp_path: Path) -> None:
    """An absolute registry key is refused before the build reads or stores it."""
    key = str(tmp_path / "outside" / "weather_openmeteo" / "point")
    assert Path(key).is_absolute()
    _refuse(tmp_path / "cache", key)


def test_grid_build_refuses_a_leading_parent_key(tmp_path: Path) -> None:
    """A key whose first part is .. is refused before the build reads or stores it."""
    _refuse(tmp_path / "cache", "../x/point")


def test_grid_build_refuses_a_nested_parent_key(tmp_path: Path) -> None:
    """A key with a .. part after a name is refused before the build reads or stores it."""
    _refuse(tmp_path / "cache", "a/../../b")


def test_a_plain_relative_key_still_builds(tmp_path: Path) -> None:
    """A relative key with no .. part still builds both grid files."""
    body = _body()
    row = weather_point()
    store(tmp_path, row, body)
    result = build_grids(tmp_path, (row,), {})
    assert set(result.sources) == {_WEATHER_KEY}
    assert (tmp_path / "grids" / "weather_openmeteo.json").is_file()
    assert (tmp_path / "grids" / "manifest.json").is_file()
