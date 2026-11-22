"""S2-P58: PUB-71 and PUB-72 are produced on the assembly path and compared.

Every count below is invented. PUB-71's stand-in expectations are
``INVENTED_PUB_71``; PUB-72's invented counts reproduce the committed open
anchors of ``stage.EXPECTED`` (section 10's worked example). PUB-73 has no
producer and stays not measured.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from custodian.tests.test_assembly_section10 import _passing_series
from custodian.tests.test_method_cache import _write_cached_source
from custodian.tests.test_production_adapters import context
from custodian.tests.test_public_data_stage import INVENTED_PUB_71

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame.layers import SCHEMAS
from eii_custodian.publicdata.series.section10 import produce
from eii_custodian.publicdata.stage import EXPECTED, run_stage

REGISTRY = load_registry()
ENTRIES = {entry.key: entry for entry in REGISTRY}
REFUSED = r"^assembly_regression_refused$"
INPUT_REFUSED = r"^assembly_section10_input_invalid$"
# zone: (private, all employed); zone 72 is unavailable (both null).
ZONES = {69: (61000, 100000), 70: (39000, 100000), 71: (23456, 34567), 72: None}
LICENCES = {("Al Daayen", "5610101"): 361, ("Doha", "5610101"): 4421}
RESIDENTS = {"Al Daayen": 111282, "Doha": 3108700}


def sector_payload(zones=ZONES) -> dict[str, object]:
    features = []
    for number, counts in zones.items():
        attrs: dict[str, object] = {
            field: "invented" if str in kinds else 0
            for field, kinds in SCHEMAS["census_zone_sector"].items()
        }
        private, total = counts if counts is not None else (None, None)
        attrs.update(ZONE_NO=number, Private=private, Total_Economic_active___15=total)
        features.append({"attributes": attrs, "geometry": {"rings": []}})
    return {"count": len(features), "features": features}


def active_rows(licences=LICENCES) -> list[dict[str, object]]:
    return [
        {
            "lbldy": name,
            "rmz_lnsht_ltjry": code,
            "lnsht_ltjry": "invented activity",
            "dd_lrkhs_lnsht": count,
        }
        for (name, code), count in licences.items()
    ]


def population_rows(residents=RESIDENTS, indicator="Population"):
    return [
        {
            "year": year,
            "municipality": name,
            "lbldy": name,
            "indicator": indicator,
            "lmw_shr": "invented",
            "count": count if year == "2025" else 7,
        }
        for name, count in residents.items()
        for year in ("2025", "2020")
    ]


def write_inputs(cache: Path, **changes: object) -> dict[str, str]:
    payloads = {
        "census_zone_sector": sector_payload(),
        "lic_active": active_rows(),
        "pop_muni": population_rows(),
        **changes,
    }
    return {
        key: _write_cached_source(cache, key, payload)  # type: ignore[arg-type]
        for key, payload in payloads.items()
        if payload is not None
    }


def local_record(cache: Path) -> None:
    record = cache / "local_expectations/PUB-71.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps(INVENTED_PUB_71), encoding="utf-8")


def production(cache: Path, **changes: object):
    build = context(cache, REGISTRY)
    build.selected = write_inputs(cache, **changes)
    local_record(cache)
    return build


def regression(cache: Path, figure: str) -> dict[str, object]:
    return json.loads((cache / f"series/regression/{figure}.json").read_text())


@pytest.mark.public_data
def test_section10_figures_produced_and_final_audit_passes(tmp_path: Path) -> None:
    """Red at the S2-P55 head: no producer, so both stayed in ``missing``."""
    build = production(tmp_path)
    assert build.section10() == ("PUB-71", "PUB-72")
    assert regression(tmp_path, "PUB-71")["values"] == INVENTED_PUB_71
    assert regression(tmp_path, "PUB-72")["values"] == EXPECTED["PUB-72"]
    for figure, keys in (
        ("PUB-71", ["census_zone_sector"]),
        ("PUB-72", ["lic_active", "pop_muni"]),
    ):
        chain = regression(tmp_path, figure)["source_chain"]
        assert [source["sha256"] for source in chain] == [
            build.selected[key] for key in keys
        ]
        assert [source["source_id"] for source in chain] == keys
    assert "assembly/final_audit.json" in build.final_audit()
    missing = build.audit["regressions"]["missing"]
    assert "PUB-71" not in missing and "PUB-72" not in missing
    assert "PUB-73" in missing  # no producer: not measured, gate pending
    assert build.audit["regressions"]["mismatch"] == ""


@pytest.mark.public_data
def test_series_stage_writes_section10_after_its_clear(tmp_path: Path) -> None:
    build = _passing_series(tmp_path)
    build.entries = (
        *build.entries,
        ENTRIES["census_zone_sector"],
        ENTRIES["pop_muni"],
    )
    pins = write_inputs(tmp_path, lic_active=None)
    build.selected.update(pins)
    local_record(tmp_path)
    stale = tmp_path / "series/regression/PUB-72.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("{}", encoding="utf-8")
    build.series_stage()
    record = json.loads((tmp_path / "assembly/series_stage.json").read_text())
    assert record["section10"] == ["PUB-71"]
    assert regression(tmp_path, "PUB-71")["values"] == INVENTED_PUB_71
    assert not stale.exists()  # cleared, and lic_active is not selected
    build.entries = REGISTRY
    build.final_audit()
    missing = build.audit["regressions"]["missing"]
    assert "PUB-71" not in missing and "PUB-62" not in missing
    assert "PUB-72" in missing


@pytest.mark.public_data
@pytest.mark.parametrize(
    ("figure", "change"),
    [
        (
            "PUB-71",
            {"census_zone_sector": sector_payload({**ZONES, 69: (62000, 100000)})},
        ),
        (
            "PUB-72",
            {"lic_active": active_rows({**LICENCES, ("Al Daayen", "5610101"): 400})},
        ),
        (
            "PUB-72",
            {"pop_muni": population_rows({**RESIDENTS, "Doha": 2000000})},
        ),
    ],
)
def test_planted_input_change_refuses_final_audit(
    tmp_path: Path, figure: str, change: dict[str, object]
) -> None:
    build = production(tmp_path, **change)
    build.section10()
    with pytest.raises(AssemblyError, match=REFUSED):
        build.final_audit()
    assert run_stage(tmp_path, evidence=True).mismatch == figure
    assert not (tmp_path / "assembly/final_audit.json").exists()


@pytest.mark.public_data
def test_pub71_without_its_local_record_refuses_final_audit(tmp_path: Path) -> None:
    build = production(tmp_path)
    (tmp_path / "local_expectations/PUB-71.json").unlink()
    build.section10()
    with pytest.raises(AssemblyError, match=REFUSED):
        build.final_audit()
    assert run_stage(tmp_path, evidence=True).unrecorded == "PUB-71"


@pytest.mark.public_data
@pytest.mark.parametrize(
    ("absent", "produced", "missing"),
    [
        ("census_zone_sector", ("PUB-72",), "PUB-71"),
        ("lic_active", ("PUB-71",), "PUB-72"),
        ("pop_muni", ("PUB-71",), "PUB-72"),
    ],
)
def test_missing_input_leaves_figure_not_measured(
    tmp_path: Path, absent: str, produced: tuple[str, ...], missing: str
) -> None:
    build = production(tmp_path)
    del build.selected[absent]
    assert build.section10() == produced
    assert not (tmp_path / f"series/regression/{missing}.json").exists()
    build.final_audit()
    assert missing in build.audit["regressions"]["missing"]


@pytest.mark.public_data
def test_skipped_input_leaves_figure_not_measured(tmp_path: Path) -> None:
    from dataclasses import replace

    build = production(tmp_path)
    build.entries = tuple(
        replace(entry, skip_reason="invented skip")
        if entry.key == "census_zone_sector"
        else entry
        for entry in REGISTRY
    )
    assert build.section10() == ("PUB-72",)


@pytest.mark.public_data
@pytest.mark.parametrize(
    "change",
    [
        {"census_zone_sector": sector_payload({**ZONES, 70: (39000, None)})},
        {"census_zone_sector": sector_payload({69: ZONES[69], 71: ZONES[71]})},
        {"pop_muni": population_rows(indicator="invented indicator")},
        {"pop_muni": population_rows({"Al Daayen": 111282})},
        {"lic_active": [{"lbldy": "Al Daayen"}]},
    ],
)
def test_parse_refusal_raises_the_closed_name(
    tmp_path: Path, change: dict[str, object]
) -> None:
    build = production(tmp_path, **change)
    with pytest.raises(AssemblyError, match=INPUT_REFUSED):
        build.section10()
    assert not list((tmp_path / "series/regression").glob("*.json"))


@pytest.mark.public_data
def test_duplicate_selected_source_raises_the_closed_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second selected row of one source is refused, never silently replaced.

    The twin reads the same verified snapshot, so no read refusal can stand in
    for the duplicate guard.
    """
    from dataclasses import replace

    from eii_custodian.publicdata.assembly_adapters import Production

    build = production(tmp_path)
    twin = replace(ENTRIES["census_zone_sector"], key="census_zone_sector_twin")
    build.entries = (*REGISTRY, twin)
    build.selected[twin.key] = build.selected["census_zone_sector"]
    real = Production.raw

    def raw(self, entry, **kwargs):
        if entry.key != twin.key:
            return real(self, entry, **kwargs)
        payload = real(self, ENTRIES["census_zone_sector"], **kwargs)
        self.receipts[twin.key] = self.receipts["census_zone_sector"]
        return payload

    monkeypatch.setattr(Production, "raw", raw)
    with pytest.raises(AssemblyError, match=INPUT_REFUSED):
        build.section10()
    assert not list((tmp_path / "series/regression").glob("*.json"))


def _inputs(cache: Path, **changes: object):
    build = production(cache, **changes)
    return {
        ENTRIES[key].source_id: (
            ENTRIES[key],
            build.raw(ENTRIES[key]),
            build.receipts[key],
        )
        for key in build.selected
    }


@pytest.mark.public_data
@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (
            {"census_zone_sector": sector_payload({**ZONES, 70: (39000, None)})},
            "null_pair",
        ),
        (
            {"census_zone_sector": sector_payload({69: ZONES[69], 71: ZONES[71]})},
            "zone_missing",
        ),
        (
            {"pop_muni": population_rows(indicator="invented indicator")},
            "population_indicator_unreviewed",
        ),
        ({"pop_muni": population_rows({"Al Daayen": 111282})}, "population_missing"),
        (
            {"lic_active": active_rows({("Doha", "5610101"): 4421})},
            "municipality_missing",
        ),
    ],
)
def test_producer_refusal_reasons(
    tmp_path: Path, change: dict[str, object], reason: str
) -> None:
    inputs = _inputs(tmp_path, **change)
    with pytest.raises(ValueError, match="^" + reason + "$"):
        produce(tmp_path, Path("custodian/publicdata/review"), inputs)


@pytest.mark.public_data
def test_incomplete_receipt_refuses_the_record(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    entry, payload, receipt = inputs["census_zone_sector"]
    inputs["census_zone_sector"] = (entry, payload, {**receipt, "licence_basis": " "})
    with pytest.raises(ValueError, match=r"^incomplete source_chain$"):
        produce(tmp_path, Path("custodian/publicdata/review"), inputs)
    assert not (tmp_path / "series/regression/PUB-71.json").exists()
