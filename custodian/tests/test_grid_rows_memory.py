"""Invented scale, record parity and writer bounds; no public cache reads."""

import gc
import json
import os
import resource
import subprocess
import sys
import time
import tracemalloc
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest
from custodian.tests.test_population_grid import spec
from custodian.tests.test_population_parity import _raster
from custodian.tests.test_population_parity import read_population as reference

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_io import (
    HeldRecord,
    record_encoder,
    write_record,
)
from eii_custodian.publicdata.grids import population as population_module
from eii_custodian.publicdata.grids.population import read_population


def _base_io(directory):
    return _base_module(directory, "assembly_io")


def _digest(value):
    digest = sha256()
    for chunk in record_encoder().iterencode(value):
        digest.update(chunk.encode("utf-8"))
    return digest.hexdigest()


@pytest.mark.parametrize("side", [1, 8, 32])
def test_record_parity_and_held(tmp_path, side):
    path = _raster(
        tmp_path / "qat_f_25_2025_SYN.tif", np.full((side, side), -0.0, dtype="float32")
    )
    expected = {
        "tables": {"pub_pop_agesex_grid": reference(tmp_path, path, spec())},
        "label": "SYN-العربية",
    }
    actual = {
        "tables": {"pub_pop_agesex_grid": read_population(tmp_path, path, spec())},
        "label": "SYN-العربية",
    }
    body = (record_encoder().encode(expected) + "\n").encode("utf-8")
    digest = write_record(tmp_path, "record.json", actual)["record.json"]
    assert (tmp_path / "record.json").read_bytes() == body
    assert digest == sha256(body).hexdigest()
    held = HeldRecord.capture(actual, digest)
    assert held.verify() == held.data
    changed = reference(tmp_path, path, spec())
    changed[0]["people"] = 1
    held.data["tables"]["pub_pop_agesex_grid"] = changed
    with pytest.raises(AssemblyError, match="assembly_draw_held_rows_changed"):
        held.verify()


def test_writer_reread_corruption(tmp_path, monkeypatch):
    import eii_custodian.publicdata.assembly_io as module

    original = module.file_hash

    def corrupt(path):
        path.write_bytes(b"corrupted")
        return original(path)

    monkeypatch.setattr(module, "file_hash", corrupt)
    with pytest.raises(AssemblyError, match="assembly_output_invalid"):
        write_record(tmp_path, "record.json", {"tables": {"SYN": [{"value": "SYN"}]}})
    assert not (tmp_path / "record.json").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == []


@pytest.mark.parametrize("mask", [0o022, 0o077])
def test_writer_file_mode_matches_base(tmp_path, mask):
    base_io = _base_io(tmp_path)
    previous = os.umask(mask)
    try:
        base_io.write_record(tmp_path, "base.json", {"tables": {"SYN": []}})
        write_record(tmp_path, "candidate.json", {"tables": {"SYN": []}})
    finally:
        os.umask(previous)
    assert (tmp_path / "candidate.json").stat().st_mode & 0o777 == (
        tmp_path / "base.json"
    ).stat().st_mode & 0o777


def _writer_peak(tmp_path, count, base=False):
    value = {"tables": {"SYN": [{"text": "SYN-" + "x" * 96}] * count}}
    base_io = _base_io(tmp_path)
    gc.collect()
    tracemalloc.start()
    if base:
        base_io.write_record(tmp_path, "base.json", value)
    else:
        write_record(tmp_path, "stream.json", value)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


def test_writer_extra_peak_bound(tmp_path):
    # Inputs are held before tracing. Eight times as many rows may add at most
    # 256 KiB of writer workspace; encode() must exceed that planted budget.
    small, large = 1024, 8192
    bound = 256 * 1024
    old_small, old_large = (_writer_peak(tmp_path, n, True) for n in (small, large))
    new_small, new_large = (_writer_peak(tmp_path, n) for n in (small, large))
    print(
        json.dumps(
            dict(
                old_small=old_small,
                old_large=old_large,
                new_small=new_small,
                new_large=new_large,
                bound=bound,
            )
        )
    )
    assert old_large - old_small > bound
    assert new_large - new_small < bound


def _measure(directory, option):
    rows = []
    parts = []
    base_io = _base_io(directory)
    if option == "C":
        base_io.record_encoder = record_encoder
    started = time.perf_counter()
    gc.collect()
    tracemalloc.start()
    for name, reviewed_spec in _files():
        path = directory / name
        file_rows = (reference if option == "A" else read_population)(
            directory, path, reviewed_spec
        )
        if isinstance(file_rows, list):
            rows.extend(file_rows)
        else:
            parts.append(file_rows)
    if parts:
        rows = population_module.PopulationTable(parts)
    retained, ingestion_peak = tracemalloc.get_traced_memory()
    ingestion_seconds = time.perf_counter() - started
    table_digest = _digest(rows)
    value = {"tables": {"pub_pop_agesex_grid": rows}}
    if option == "CE":
        digest = write_record(directory, option + ".json", value)[option + ".json"]
    else:
        digest = base_io.write_record(directory, option + ".json", value)[
            option + ".json"
        ]
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(
        json.dumps(
            dict(
                option=option,
                pixels=32 * 32,
                files=40,
                distinct_contents=True,
                peak=peak,
                retained=retained,
                ingestion_peak=ingestion_peak,
                ingestion_seconds=ingestion_seconds,
                ru_maxrss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                seconds=time.perf_counter() - started,
                table_sha256=table_digest,
                record_sha256=digest,
            )
        ),
        flush=True,
    )
    if peak > 16 * 1024 * 1024:
        raise SystemExit(3)


def _files():
    for index in range(40):
        reviewed_spec = replace(
            spec(), sex_code="f" if index % 2 == 0 else "m", age_code=str(index // 2)
        )
        yield (
            f"qat_{reviewed_spec.sex_code}_{reviewed_spec.age_code}_2025_SYN.tif",
            reviewed_spec,
        )


def test_scale_budget(tmp_path):
    # Fixed tracemalloc peak budget includes ingestion, retained rows, table
    # hashing and writing. The base path completes its evidence before the
    # budget verdict, so the failure still supplies an independently matched hash.
    budget = 16 * 1024 * 1024
    source_hashes = set()
    for index, (name, _reviewed_spec) in enumerate(_files()):
        path = _raster(
            tmp_path / name, np.full((32, 32), index + 1.23455, dtype="float32")
        )
        source_hashes.add(sha256(path.read_bytes()).hexdigest())
    assert len(source_hashes) == 40
    measurements = []
    for option in ("A", "C", "CE"):
        command = [
            sys.executable,
            "-c",
            "from pathlib import Path; from custodian.tests.test_grid_rows_memory import _measure; "
            '_measure(Path(__import__("sys").argv[1]), __import__("sys").argv[2])',
            str(tmp_path),
            option,
        ]
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            command,
            cwd=root,
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join([str(root / "custodian/src"), str(root)]),
            },
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode in (0, 3), result.stderr
        measurement = json.loads(result.stdout)
        measurement["exit"] = result.returncode
        measurements.append(measurement)
    print(json.dumps(dict(budget=budget, measurements=measurements)), flush=True)
    base, columns, streaming = measurements
    assert base["peak"] > budget
    assert base["exit"] == 3
    assert streaming["exit"] == 0
    assert streaming["peak"] < budget
    assert len({row["table_sha256"] for row in measurements}) == 1
    assert len({row["record_sha256"] for row in measurements}) == 1
    assert columns["retained"] < base["retained"]


def _base_module(directory, suffix):
    import importlib.util

    relative = suffix.replace(".", "/") + ".py"
    path = directory / (suffix.replace(".", "_") + ".py")
    path.write_bytes(
        subprocess.check_output(
            [
                "git",
                "show",
                "66c0ea750d7df8b54b20e8688a8768d52e21c0b1:"
                "custodian/src/eii_custodian/publicdata/" + relative,
            ]
        )
    )
    package, _, leaf = suffix.rpartition(".")
    name = (
        "eii_custodian.publicdata."
        + (package + "." if package else "")
        + "_base_"
        + leaf
    )
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _mixed_registry(prepared, tmp_path):
    from affine import Affine
    from custodian.tests.fixtures.grids.invented import store
    from custodian.tests.test_grids_build_mutation import _population

    entries = []
    hashes = set()
    for index, (sex, age) in enumerate(
        (("f", "25"), ("m", "25"), ("f", "30"), ("m", "30"))
    ):
        name = f"qat_{sex}_{age}_2025_SYN.tif"
        row = replace(
            _population(),
            key=f"worldpop_qat_agesex/2025/{sex}/{age}",
            sex=sex,
            age_code=age,
            url="https://data.worldpop.org/SYN/" + name,
        )
        path = _raster(
            tmp_path / name,
            np.array(
                [
                    [-0.0, index + 1.23445, -99999],
                    [index + 1.23455, 0.00005, index + 2],
                ],
                dtype="float32",
            ),
            transform=Affine(0.0008, 0.00002, 0, 0.00003, -0.0009, 1),
        )
        body = path.read_bytes()
        hashes.add(sha256(body).hexdigest())
        store(prepared.cache, row, body)
        entries.append(row)
    assert len(hashes) == 4
    # A missing-cache entry produces a nonempty coverage line on both paths.
    entries.append(
        replace(
            entries[0],
            key="worldpop_qat_agesex/2024/f/25",
            year="2024",
            cell_units="density",
        )
    )
    return (*prepared.entries, *entries)


def test_mixed_frame_handoff(tmp_path, monkeypatch):
    from custodian.tests.test_frame_live_survivors import _world
    from custodian.tests.test_grids_build_mutation import (
        test_grids_of_one_year_must_agree_by_name,
    )

    from eii_custodian.publicdata.fetch.snapshots import reviewed_selections
    from eii_custodian.publicdata.frame import live
    from eii_custodian.publicdata.frame.build import inspect_cache
    from eii_custodian.publicdata.grids import build

    prepared = _world(tmp_path)
    registry = _mixed_registry(prepared, tmp_path)
    base_build = _base_module(tmp_path, "grids.build")
    base_build.read_population = reference
    base_live = _base_module(tmp_path, "frame.live")
    base_live.build_grids = base_build.build_grids
    base_io = _base_io(tmp_path)
    results = []
    for label, module, writer in (
        ("base", base_live, base_io.write_record),
        ("new", live, write_record),
    ):
        selected = reviewed_selections(prepared.cache)
        inspected = inspect_cache(prepared.cache, registry, prepared.review, selected)
        frame = module.build_live_frame(
            prepared.cache, registry, prepared.review, None, inspected, selected
        )
        value = dict(tables=frame.tables, report=frame.report, sources=frame.sources)
        digest = writer(tmp_path, label + ".json", value)[label + ".json"]
        held = HeldRecord.capture(value, digest)
        assert held.verify() == held.data
        results.append((frame, digest))
    old, new = results
    assert old[1] == new[1]
    assert (tmp_path / "base.json").read_bytes() == (tmp_path / "new.json").read_bytes()
    assert old[0].report == new[0].report
    assert any("NO_CACHE" in line for line in new[0].report)
    assert old[0].sources == new[0].sources
    evidence = {}
    for name, rows in old[0].tables.items():
        actual = new[0].tables[name]
        assert len(rows) == len(actual)
        assert [tuple(row) for row in rows] == [tuple(row) for row in actual]
        assert list(rows) == list(actual)
        before = (record_encoder().encode(rows) + "\n").encode()
        after = (record_encoder().encode(actual) + "\n").encode()
        assert before == after
        evidence[name] = dict(
            rows=len(rows), sha256=sha256(before).hexdigest(), bytes=len(before)
        )
    print(
        json.dumps(dict(tables=evidence, coverage=new[0].report, record_sha256=new[1])),
        flush=True,
    )
    # Reuse the existing mismatch input and exact refusal assertion on both builds.
    for label, builder in (
        ("base", base_build.build_grids),
        ("new", build.build_grids),
    ):
        folder = tmp_path / (label + "-refusal")
        folder.mkdir()
        with monkeypatch.context() as patch:
            patch.setattr(
                "custodian.tests.test_grids_build_mutation.build_grids", builder
            )
            test_grids_of_one_year_must_agree_by_name(folder)
