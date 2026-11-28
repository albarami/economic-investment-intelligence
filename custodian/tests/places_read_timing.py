"""Untraced fresh-process timing on the same P3/P4 invented files."""

import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

import pytest
from custodian.tests.test_places_read_memory import CHILD, fixture_files


@pytest.mark.parametrize("kind", ["place", "building"])
def test_untraced_timing(tmp_path, kind):
    paths = fixture_files(tmp_path, kind)
    child = CHILD.replace("tracemalloc.start()", "assert not tracemalloc.is_tracing()")
    child = child.replace(
        "dict(hash=",
        'dict(python=sys.version, duckdb=sys.modules["duckdb"].__version__, shapely=sys.modules["shapely"].__version__, hash=',
    )
    results = {}
    for origin in ("base", "new"):
        samples = []
        for index in range(5):
            report = tmp_path / f"syn-{origin}-{index}.json"
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    child,
                    kind,
                    origin,
                    str(tmp_path / "syn_base.py"),
                    str(report),
                    *map(str, paths),
                ],
                capture_output=True,
                text=True,
                check=True,
                env=os.environ.copy(),
            )
            samples.append(json.loads(report.read_text()))
        times = [sample["seconds"] for sample in samples]
        results[origin] = dict(
            samples=samples,
            median=statistics.median(times),
            minimum=min(times),
            maximum=max(times),
            spread=max(times) - min(times),
        )
    assert len({s["hash"] for r in results.values() for s in r["samples"]}) == 1
    output = Path(os.environ["SYN_TIMING_OUTPUT"])
    # Each parameter records its own complete table atomically in a separate file.
    output.with_name(output.stem + "-" + kind + output.suffix).write_text(
        json.dumps(results, indent=2)
    )
    print(kind, json.dumps(results), flush=True)
