"""P3/P4 behaviour: fixture-only Python allocation budgets, no real-run fit claim."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
from custodian.tests.fixtures.places.invented import (
    building_row,
    place_row,
    write_buildings,
    write_places,
)
from custodian.tests.test_places_read_parity import BASE, base_module
from shapely.geometry import box

CHILD = r"""
import hashlib, importlib.util, json, resource, sys, time, tracemalloc
from pathlib import Path
from shapely.geometry import box
from eii_custodian.publicdata.places import read
from custodian.tests.fixtures.places.invented import receipt_for
kind, origin, base_path, report_path, *files = sys.argv[1:]
if origin == "base":
    spec = importlib.util.spec_from_file_location("syn_memory_base", base_path)
    read = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = read
    spec.loader.exec_module(read)
paths = [Path(p) for p in files]
receipts = [receipt_for(p) for p in paths]
tracemalloc.start()
start = time.perf_counter()
h = hashlib.sha256()
if kind == "place":
    reader = getattr(read, "iter_place_file", read.read_place_file)
    import inspect
    options = {"outside": []} if "outside" in inspect.signature(reader).parameters else {}
    for row in reader(paths[0], "ar", (51.,25.,52.,26.), **options):
        if 51 <= row.lon <= 52 and 25 <= row.lat <= 26:
            h.update(repr(row).encode())
else:
    rows, recorded, outside = read.load_boundary_buildings(paths, receipts, box(51,25,52,26))
    for row in rows:
        h.update(repr(row).encode())
    h.update(str(outside).encode())
Path(report_path).write_text(json.dumps(dict(hash=h.hexdigest(), peak=tracemalloc.get_traced_memory()[1], rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, seconds=time.perf_counter()-start)))
"""


def expand(path, count):
    import duckdb

    expanded = path.with_name("syn-expanded-" + path.name)
    connection = duckdb.connect()
    try:
        connection.execute(
            "COPY (SELECT 'SYN-' || i::VARCHAR AS id, p.* EXCLUDE(id) "
            "FROM read_parquet(?) p CROSS JOIN range(?) r(i) WHERE (p.id = 'SYN-IN') = (i % 100 = 0)) TO ? "
            "(FORMAT PARQUET, KV_METADATA {schema_versions: ?})",
            [str(path), count, str(expanded), '{"overture-schema-pyspark":"2.0.0"}'],
        )
    finally:
        connection.close()
    expanded.replace(path)


@pytest.mark.parametrize(
    "kind,budget", [("place", 32_000_000), ("building", 55_000_000)]
)
def test_fixture_memory_bound(tmp_path, kind, budget):
    """Behaviour: 200k rows for places, two 100k-row building files; base must exceed."""
    paths = fixture_files(tmp_path, kind)
    results = {}
    for origin in ("base", "new"):
        report_path = tmp_path / f"syn-measure-{origin}.json"
        subprocess.run(
            [
                sys.executable,
                "-c",
                CHILD,
                kind,
                origin,
                str(tmp_path / "syn_base.py"),
                str(report_path),
                *map(str, paths),
            ],
            capture_output=True,
            text=True,
            check=True,
            env=os.environ.copy(),
        )
        results[origin] = json.loads(report_path.read_text())
    print(
        json.dumps(
            {
                "kind": kind,
                "rows": 200_000,
                "budget": budget,
                "base_commit": BASE,
                **results,
            }
        ),
        flush=True,
    )
    assert results["base"]["hash"] == results["new"]["hash"]
    assert results["base"]["peak"] > budget
    assert results["new"]["peak"] < budget


def fixture_files(tmp_path, kind):
    """Reuse the identical invented P3/P4 inputs for timing and memory."""
    base_module(tmp_path)
    paths = []
    for part in range(1 if kind == "place" else 2):
        path = tmp_path / f"syn-{part}.parquet"
        if kind == "place":
            write_places(
                path, [place_row(lon=10, lat=20), place_row(place_id="SYN-IN")]
            )
        else:
            ring = tuple(box(10 + part, 20, 10.01 + part, 20.01).exterior.coords)
            write_buildings(
                path,
                [
                    building_row("SYN-B", ring),
                    building_row(
                        "SYN-IN", tuple(box(51.4, 25.4, 51.5, 25.5).exterior.coords)
                    ),
                ],
            )
        expand(path, 200_000 if kind == "place" else 100_000)
        paths.append(path)
    # File-specific IDs keep the across-file duplicate check active.
    if kind == "building":
        import duckdb

        path = paths[1]
        renamed = tmp_path / "syn-renamed.parquet"
        connection = duckdb.connect()
        try:
            connection.execute(
                "COPY (SELECT 'SYN-SECOND-' || id AS id, geometry FROM read_parquet(?)) "
                "TO ? (FORMAT PARQUET, KV_METADATA {schema_versions: ?})",
                [str(path), str(renamed), '{"overture-schema-pyspark":"2.0.0"}'],
            )
        finally:
            connection.close()
        renamed.replace(path)
    return paths
