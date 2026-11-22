"""S2-P55: every section 10 figure is compared once during the assembly.

The series stage refuses only on a figure it owns (its ``required``) or on a
mismatch. PUB-71, PUB-72 and PUB-73 have no assembly producer; the final audit
compares every produced section 10 record with the same ``run_stage`` and
refuses a mismatch or a produced figure without its expectations record. Every
value below is invented, except the committed open anchors read from
``stage.EXPECTED``; no expected figure of PUB-71 is committed.
"""

from __future__ import annotations

import itertools
import json
import tempfile
from pathlib import Path

import pytest
from custodian.tests.test_production_adapters import context
from custodian.tests.test_public_data_stage import INVENTED_PUB_71
from custodian.tests.test_public_series import series_cache

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.stage import EXPECTED

UNOWNED = ("PUB-71", "PUB-72", "PUB-73")
# absent: no producer wrote it; match/mismatch: a produced record; unrecorded:
# a produced PUB-71 whose uncommitted expectations record is absent.
STATES = ("absent", "match", "mismatch", "unrecorded")
REGISTRY = load_registry()


def _utility_rows(zone_69_2021: int) -> list[dict[str, object]]:
    """Invented zone 70 rows; zone 69 uses PUB-62's committed open anchors."""
    return [
        {"year": "2021", "zone_number": "69", "value": zone_69_2021},
        {
            "year": "2025",
            "zone_number": "69",
            "value": int(EXPECTED["PUB-62"]["zone_69_2025"]),
        },
        {"year": "2021", "zone_number": "70", "value": 2000000000},
        {"year": "2025", "zone_number": "70", "value": 1819749060},
    ]


def _series(tmp_path: Path, rows: list[dict[str, object]]):
    row, digest = series_cache(tmp_path, "util_elec", rows)
    build = context(tmp_path, (row,))
    build.selected = {row.key: digest}
    return build


def _audited(build):
    """The final audit reads the whole registry; the series fixture holds one row."""
    build.entries = REGISTRY
    return build


def _passing_series(tmp_path: Path):
    return _series(tmp_path, _utility_rows(int(EXPECTED["PUB-62"]["zone_69_2021"])))


def _envelope(values: dict[str, str]) -> dict[str, object]:
    chain = {
        key: "SYN-" + key
        for key in (
            "source_id",
            "publisher",
            "slug",
            "licence_id",
            "licence_basis",
            "retrieved_utc",
            "fetch_url",
        )
    }
    return {
        "method": "SYN-method",
        "method_version": "1",
        "source_chain": [{**chain, "sha256": "a" * 64}],
        "release_tables": ["SYN_table"],
        "field_mapping": {"SYN": "SYN"},
        "values": values,
    }


def _plant(cache: Path, figure_id: str, state: str) -> None:
    """Write one produced record as a later producer would, or nothing."""
    if state == "absent":
        return
    expected = INVENTED_PUB_71 if figure_id == "PUB-71" else EXPECTED[figure_id]
    values = dict(expected)
    if state == "mismatch":
        first = next(iter(values))
        values[first] = "1" if values[first] != "1" else "2"
    if figure_id == "PUB-71" and state != "unrecorded":
        record = cache / "local_expectations/PUB-71.json"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(INVENTED_PUB_71), encoding="utf-8")
    path = cache / "series/regression" / f"{figure_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_envelope(values)), encoding="utf-8")


@pytest.mark.public_data
def test_series_stage_passes_on_owned_figures_and_final_audit_compares_rest(
    tmp_path: Path,
) -> None:
    """Red at e7edf546: PUB-71..73 have no producer, so the stage refused."""
    build = _passing_series(tmp_path)
    output = build.series_stage()
    assert "assembly/series_stage.json" in output
    record = json.loads((tmp_path / "assembly/series_stage.json").read_text())
    assert record["mismatch"] == ""
    assert record["required"] == ["PUB-62"]
    assert record["checks"]["PUB-62"] == EXPECTED["PUB-62"]
    # Not owned or not selected: still reported as not measured, never a pass.
    assert set(UNOWNED) <= set(record["missing"])
    assert "PUB-62" not in record["missing"]
    audit = _audited(build).final_audit()
    assert "assembly/final_audit.json" in audit
    assert set(UNOWNED) <= set(build.audit["regressions"]["missing"])


@pytest.mark.public_data
def test_owned_figure_mismatch_refuses_series_stage(tmp_path: Path) -> None:
    build = _series(tmp_path, _utility_rows(7))
    with pytest.raises(AssemblyError, match=r"^assembly_regression_refused$"):
        build.series_stage()
    record = json.loads((tmp_path / "assembly/series_stage.json").read_text())
    assert record["mismatch"] == "PUB-62"
    assert "PUB-62" in record["checks"]


@pytest.mark.public_data
def test_owned_figure_missing_refuses_series_stage(tmp_path: Path) -> None:
    rows = _utility_rows(int(EXPECTED["PUB-62"]["zone_69_2021"]))
    build = _series(tmp_path, [*rows, dict(rows[0])])  # duplicate period: blocked
    with pytest.raises(AssemblyError, match=r"^assembly_regression_refused$"):
        build.series_stage()
    record = json.loads((tmp_path / "assembly/series_stage.json").read_text())
    assert record["mismatch"] == "PUB-62"
    assert "PUB-62" in record["missing"]
    assert record["checks"] == {}


@pytest.mark.public_data
@pytest.mark.parametrize("figure_id", UNOWNED)
def test_unowned_figure_mismatch_refuses_final_audit(
    tmp_path: Path, figure_id: str
) -> None:
    build = _passing_series(tmp_path)
    build.series_stage()
    _plant(tmp_path, figure_id, "mismatch")
    with pytest.raises(AssemblyError, match=r"^assembly_regression_refused$"):
        _audited(build).final_audit()
    assert not (tmp_path / "assembly/final_audit.json").exists()


@pytest.mark.public_data
def test_unowned_figure_without_record_refuses_final_audit(tmp_path: Path) -> None:
    build = _passing_series(tmp_path)
    build.series_stage()
    _plant(tmp_path, "PUB-71", "unrecorded")
    with pytest.raises(AssemblyError, match=r"^assembly_regression_refused$"):
        _audited(build).final_audit()
    assert not (tmp_path / "assembly/final_audit.json").exists()


@pytest.mark.public_data
def test_owned_figure_changed_after_series_refuses_final_audit(
    tmp_path: Path,
) -> None:
    build = _passing_series(tmp_path)
    build.series_stage()
    _plant(tmp_path, "PUB-62", "mismatch")
    with pytest.raises(AssemblyError, match=r"^assembly_regression_refused$"):
        _audited(build).final_audit()


@pytest.mark.public_data
@pytest.mark.parametrize(
    "states", list(itertools.product(STATES, STATES[:3], STATES[:3]))
)
def test_final_audit_refuses_exactly_a_mismatch_or_an_unrecorded_figure(
    states: tuple[str, str, str],
) -> None:
    """Whole domain of the unowned figures, enumerated exhaustively (36 cases):
    PUB-72 and PUB-73 have committed anchors, so only PUB-71 can be produced
    without its expectations record. Each case runs a full final audit, so
    the domain is enumerated rather than sampled under a per-example timer."""
    plan = dict(zip(UNOWNED, states, strict=True))
    with tempfile.TemporaryDirectory() as folder:
        cache = Path(folder)
        build = context(cache, REGISTRY)
        for figure_id, state in plan.items():
            _plant(cache, figure_id, state)
        if {"mismatch", "unrecorded"} & set(states):
            with pytest.raises(AssemblyError, match=r"^assembly_regression_refused$"):
                build.final_audit()
            assert not (cache / "assembly/final_audit.json").exists()
        else:
            assert "assembly/final_audit.json" in build.final_audit()
