"""Unfiltered caller retention, measured in a fresh child on invented files."""

import json
import os
import subprocess
import sys

import pytest

CHILD = r"""
import json, sys, tracemalloc
from pathlib import Path
import pytest
from custodian.tests.test_places_registry_areas import _candidate
from custodian.tests.test_places_read_memory import expand
from custodian.tests.test_places_partb_survivors_c import _receipt, _row
from custodian.tests.fixtures.places.invented import place_row, write_places
from eii_custodian.publicdata.places import integrate
root, kind, report = map(Path, sys.argv[1:])
with pytest.MonkeyPatch.context() as patch:
    cache, review = _candidate(root, patch, "bldg_ovt/part-00384")
    if str(kind) == "place":
        path = cache / "places_ovt/part-00014/syn.parquet"
        path.parent.mkdir(parents=True)
        write_places(path, [place_row(place_id="SYN-IN"), place_row()])
        entries = (_row("places_ovt/part-00014", "places_ovt"), _row("bldg_ovt/part-00384", "bldg_ovt"))
        patch.setattr(integrate, "load_registry", lambda: entries)
        (review / "arabic_tag.txt").write_text("ar")
    else:
        path = cache / "bldg_ovt/part-00384/syn.parquet"
        # expand expects one SYN-IN row and one other row.
        import duckdb
        renamed = path.with_name("renamed.parquet")
        con = duckdb.connect()
        con.execute("COPY (SELECT 'SYN-IN' AS id, geometry FROM read_parquet(?) UNION ALL SELECT id, geometry FROM read_parquet(?)) TO ? (FORMAT PARQUET, KV_METADATA {schema_versions: ?})", [str(path), str(path), str(renamed), '{"overture-schema-pyspark":"2.0.0"}'])
        con.close()
        renamed.replace(path)
    expand(path, 300_000)
    _receipt(path)
    tracemalloc.start()
    points = integrate._cache_points(cache, review)
    current, peak = tracemalloc.get_traced_memory()
    Path(report).write_text(json.dumps(dict(size=len(points), current=current, peak=peak)))
"""


@pytest.mark.parametrize("kind", ["place", "building"])
def test_unfiltered_cache_points_peak(tmp_path, kind):
    report = tmp_path / "measurement.json"
    result = subprocess.run(
        [sys.executable, "-c", CHILD, str(tmp_path), kind, str(report)],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stderr
    measured = json.loads(report.read_text())
    assert measured["size"] >= 300_000
    print(kind, measured, flush=True)
    assert measured["peak"] < 160_000_000


def test_unfiltered_stage_points_peak(tmp_path):
    report = tmp_path / "measurement.json"
    target = "points = integrate._cache_points(cache, review)"
    assert CHILD.count(target) == 1
    child = CHILD.replace(
        target,
        "from types import SimpleNamespace\n"
        "    from eii_custodian.publicdata.places import stage\n"
        "    points = stage._source_points(SimpleNamespace("
        "places_path=path, arabic_tag='ar', buildings_paths=()))",
    )
    result = subprocess.run(
        [sys.executable, "-c", child, str(tmp_path), "place", str(report)],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stderr
    measured = json.loads(report.read_text())
    assert measured["size"] >= 300_000
    print("stage", measured, flush=True)
    assert measured["peak"] < 160_000_000
