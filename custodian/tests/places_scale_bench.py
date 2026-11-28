"""Invented matched-scale cache; separate preparation and fresh-process reads.

Run as ``python -m custodian.tests.places_scale_bench make|run ...``.
The measured path is _cache_points plus area_requests (no road engine inputs),
followed by stage._source_points. No tracer is imported when tracing is off.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from custodian.tests.fixtures.places.invented import point_wkb, polygon_wkb
from custodian.tests.test_places_partb_survivors_c import _receipt, _row
from custodian.tests.test_places_points_parity import bind_points
from custodian.tests.test_places_read_parity import base_module
from custodian.tests.test_places_registry_areas import _candidate

from eii_custodian.publicdata.places import integrate, stage
from eii_custodian.publicdata.places.area_requests import area_requests


def digest(path: Path) -> str:
    """Hash files without materialising their contents."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _projection(place: bool) -> tuple[str, bytes]:
    """Invented source shapes with the lead-supplied projected text widths."""
    if place:
        # Names and source text widths include DuckDB's struct punctuation.
        columns = """?, 0.8::DOUBLE AS confidence,
            {'primary': repeat('s', 31),
             'common': NULL::MAP(VARCHAR,VARCHAR),
             'rules': []::STRUCT(variant VARCHAR)[]} AS names,
            list_transform(range(2), lambda j: {
                'property': CASE WHEN j=0 THEN '' ELSE 'name' END,
                'dataset': repeat('s', 87), 'license': 'SYN',
                'record_id': 'SYN', 'update_time': 'SYN',
                'confidence': 0.8, 'between': NULL::VARCHAR,
                'provider': 'SYN', 'resource': 'SYN', 'version': 'SYN'
            }) AS sources,
            'syn-category-' || lpad((i % 267)::VARCHAR,4,'0') AS basic_category"""
        geometry = point_wkb(51.5, 25.3)
    else:
        columns = "?"
        geometry = polygon_wkb(
            (
                (51.5, 25.3),
                (51.502, 25.3),
                (51.502, 25.302),
                (51.5, 25.302),
                (51.5, 25.3),
            )
        )
    return columns, geometry


def make(args: argparse.Namespace) -> None:
    """Reuse the candidate cache and receipt layout with bulk invented rows."""
    import duckdb

    args.out.mkdir(parents=True, exist_ok=False)
    with pytest.MonkeyPatch.context() as patch:
        cache, review = _candidate(args.out, patch, "bldg_ovt/part-00384")
    (review / "arabic_tag.txt").write_text("ar\n")
    keys = ["places_ovt/part-00014"] + [
        f"bldg_ovt/part-{384 + index:05d}" for index in range(args.building_files)
    ]
    con = duckdb.connect()
    con.execute("SET threads=2")
    con.execute("SET memory_limit='1GB'")
    files = []
    for index, key in enumerate(keys):
        path = cache / key / "syn.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        place = index == 0
        count = (
            args.places
            if place
            else (
                args.buildings // args.building_files
                + (index <= args.buildings % args.building_files)
            )
        )
        identity = "'SYN-' || md5(? || ':' || i::VARCHAR)"
        params = [f"{args.seed}:{key}"]
        columns, geometry = _projection(place)
        if not place:
            identity = "CASE WHEN i=0 AND ? THEN 'SYN-B-A' ELSE " + identity + " END"
            params.insert(0, index == 1)
        con.execute(
            f"COPY (SELECT {identity} AS id, {columns.replace('?,', '? AS geometry,', 1) if place else '? AS geometry'} FROM range(?) t(i)) TO ? (FORMAT PARQUET, KV_METADATA {{schema_versions: ?}})",
            [
                *params,
                geometry,
                count,
                str(path),
                '{"overture-schema-pyspark":"2.0.0"}',
            ],
        )
        stats = con.execute(
            "SELECT count(*), count(DISTINCT id), avg(length(id)) FROM read_parquet(?)",
            [str(path)],
        ).fetchone()
        assert stats is not None and stats[0] == stats[1] == count
        if place:
            widths = con.execute(
                "SELECT avg(length(names::VARCHAR)), avg(length(sources::VARCHAR)), "
                "avg(length(basic_category)), count(DISTINCT basic_category) "
                "FROM read_parquet(?)",
                [str(path)],
            ).fetchone()
        _receipt(path)
        files.append({"key": key, "rows": count, "sha256": digest(path)})
    con.close()
    manifest = {
        "seed": args.seed,
        "places": args.places,
        "buildings": args.buildings,
        "building_files": args.building_files,
        "files": files,
        "place_text_widths": widths,
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest), flush=True)


def status() -> dict[str, int]:
    """Each process reads only its own status; values returned in bytes."""
    fields = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        name, _, rest = line.partition(":")
        if name in {"VmRSS", "VmHWM"}:
            fields[name] = int(rest.split()[0]) * 1024
    return fields


def point_hash(points: dict) -> str:
    """Preserve dictionary insertion order and coordinates in the digest."""
    result = hashlib.sha256()
    for item in points.items():
        result.update(repr(item).encode())
        result.update(b"\n")
    return result.hexdigest()


def run(args: argparse.Namespace) -> None:
    """Measure one case in this fresh process, with optional profiler cost."""
    if args.tracemalloc == "off":
        assert "tracemalloc" not in sys.modules
    manifest = json.loads((args.cache / "manifest.json").read_text())
    cache, review = args.cache / "cache", args.cache / "review"
    entries = tuple(
        _row(item["key"], item["key"].split("/")[0]) for item in manifest["files"]
    )
    for item in manifest["files"]:
        assert digest(cache / item["key"] / "syn.parquet") == item["sha256"]
    config = SimpleNamespace(
        places_path=cache / manifest["files"][0]["key"] / "syn.parquet",
        arabic_tag="ar",
        buildings_paths=tuple(
            cache / item["key"] / "syn.parquet" for item in manifest["files"][1:]
        ),
    )
    with pytest.MonkeyPatch.context() as patch:
        if args.reader == "base":
            bind_points(patch, base_module(args.cache))
        patch.setattr(integrate, "load_registry", lambda: entries)
        baseline = status()["VmRSS"]
        if args.tracemalloc == "on":
            import tracemalloc

            tracemalloc.start()
        started = time.monotonic()
        report = {
            "reader": args.reader,
            "tracemalloc": args.tracemalloc,
            "scale": {
                key: manifest[key]
                for key in ("seed", "places", "buildings", "building_files")
            },
            "vmrss_before_bytes": baseline,
            "path": "_cache_points + area_requests; stage._source_points",
        }
        try:
            points = integrate._cache_points(cache, review)
            requests = repr(area_requests(review, points))
            first = point_hash(points)
            size = len(points)
            del points
            points = stage._source_points(config)
            second = point_hash(points)
            assert first == second
            report.update(
                dict_size=size,
                output_hash=first,
                requests_hash=hashlib.sha256(requests.encode()).hexdigest(),
                exit=0,
            )
        except Exception as exc:
            report.update(exit=1, refusal=f"{type(exc).__name__}: {exc}")
        report["wall_seconds"] = time.monotonic() - started
        report["vmhwm_bytes"] = status()["VmHWM"]
        if args.tracemalloc == "on":
            report["traced_current_bytes"], report["traced_peak_bytes"] = (
                tracemalloc.get_traced_memory()
            )
            report["tracemalloc_memory_bytes"] = tracemalloc.get_tracemalloc_memory()
        print(json.dumps(report), flush=True)
        if report["exit"]:
            raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("make")
    prepare.add_argument("--out", type=Path, required=True)
    prepare.add_argument("--seed", type=int, required=True)
    prepare.add_argument("--places", type=int, default=5_570_469)
    prepare.add_argument("--buildings", type=int, default=19_576_948)
    prepare.add_argument("--building-files", type=int, default=4)
    measure = commands.add_parser("run")
    measure.add_argument("--cache", type=Path, required=True)
    measure.add_argument("--reader", choices=("base", "new"), required=True)
    measure.add_argument("--tracemalloc", choices=("off", "on"), required=True)
    args = parser.parse_args()
    (make if args.command == "make" else run)(args)


if __name__ == "__main__":
    main()
