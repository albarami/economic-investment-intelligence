"""Data-test wiring on invented files of the confirmed source format."""

import json
from pathlib import Path

import pytest
from custodian.data_tests.cache import cached

from eii_core.calc.facts import Measure
from eii_core.calc.public_methods import AnnualEnergy, zone_momentum
from eii_custodian.publicdata.fetch.receipts import commit_pair, sha256_hex, sidecar_for
from eii_custodian.publicdata.fetch.registry import load_registry


def fixture(cache):
    entry = next(row for row in load_registry() if row.key == "util_elec")
    body = json.dumps(
        [
            {"year": "2021", "zone_number": "invented", "value": 1000000},
            {"year": "2025", "zone_number": "invented", "value": 2000000},
            {"year": "2021", "zone_number": "invented_zero", "value": 0},
            {"year": "2025", "zone_number": "invented_zero", "value": 500},
        ]
    ).encode()
    digest = sha256_hex(body)
    receipt = sidecar_for(
        entry,
        digest=digest,
        nbytes=len(body),
        fetch_url=entry.url,
        fetch_host=entry.fetch_host,
        retrieved_utc="2026-11-14T00:00:00Z",
        publisher=entry.publisher,
        source_modified="",
        row_count=4,
        terms_sha256="",
        switched_off=False,
    )
    commit_pair(cache / entry.key, digest, "json", body, receipt)
    return digest


def test_method_cache_same_reader_and_real_receipt_chain(tmp_path):
    from decimal import Decimal as D

    from eii_core.calc.facts import NoData

    digest = fixture(tmp_path)
    rows, chain = cached(tmp_path, "util_elec", digest)

    def energy(row, national=False):
        zone = "national" if national else str(row["zone_number"])
        value = D(str(row["value"]))
        return AnnualEnergy(
            zone,
            int(row["year"]),
            value,
            True,
            Measure(
                value,
                "kwh",
                row["year"],
                "national" if national else f"zone:{zone}",
                "national" if national else "public",
                "public",
                (chain,),
            ),
        )

    result = zone_momentum(
        [energy(row) for row in rows], energy(rows[0], True), energy(rows[1], True)
    )
    assert result["zones"]["invented"]["ratio"].value == D("2.00")
    assert result["order_unrounded"] == ("invented",)
    for slot in ("ratio", "ranked_ratio", "relative"):
        assert result["zones"]["invented_zero"][slot] == NoData("no_denominator")
    assert "invented_zero" not in result["order_unrounded"]
    assert result["national_ratio"].sources == (chain,)
    assert chain.sha256 == digest
    assert chain.retrieved == "2026-11-14"


@pytest.mark.parametrize("plant", ["file", "receipt", "hash"])
def test_method_cache_named_failures(tmp_path, plant):
    digest = fixture(tmp_path)
    folder = tmp_path / "util_elec"
    if plant == "file":
        (folder / f"{digest}.json").unlink()
    elif plant == "receipt":
        (folder / f"{digest}.meta.json").unlink()
    else:
        (folder / f"{digest}.json").write_text("[]")
    expected = "receipt_hash_mismatch" if plant == "hash" else "public_cache_missing"
    with pytest.raises(ValueError, match=expected + ":util_elec"):
        cached(tmp_path, "util_elec", digest)


def test_method_data_tests_are_outside_whole_command_selection():
    from scripts.run_tests import SUITES

    selections = [
        arg for suite in SUITES if suite.kind == "pytest" for arg in suite.args
    ]
    assert "custodian/tests" in selections
    assert "custodian/data_tests" not in selections
    assert not any(
        Path("custodian/data_tests").is_relative_to(Path(arg)) for arg in selections
    )


def _write_cached_source(cache: Path, source_key: str, rows: list[dict]):
    entry = next(row for row in load_registry() if row.key == source_key)
    body = json.dumps(rows).encode()
    digest = sha256_hex(body)
    receipt = sidecar_for(
        entry,
        digest=digest,
        nbytes=len(body),
        fetch_url=entry.url,
        fetch_host=entry.fetch_host,
        retrieved_utc="2026-11-14T00:00:00Z",
        publisher=entry.publisher,
        source_modified="",
        row_count=len(rows),
        terms_sha256="",
        switched_off=False,
    )
    commit_pair(cache / entry.key, digest, entry.extension, body, receipt)
    return digest


@pytest.mark.parametrize(
    "plant", ["missing_pins_file", "missing_pin_key", "receipt_sha"]
)
def test_method_cache_pinned_named_failures(tmp_path, monkeypatch, plant):
    import custodian.data_tests.cache as cache_mod

    monkeypatch.setattr(cache_mod, "CACHE", tmp_path)
    digest = fixture(tmp_path)
    if plant == "missing_pin_key":
        (tmp_path / "method_pins.json").write_text("{}")
    elif plant == "receipt_sha":
        (tmp_path / "method_pins.json").write_text(json.dumps({"util_elec": digest}))
        receipt_path = tmp_path / "util_elec" / f"{digest}.meta.json"
        meta = json.loads(receipt_path.read_text())
        meta["sha256"] = "0" * 64
        receipt_path.write_text(json.dumps(meta))
    expected = (
        "receipt_hash_mismatch:util_elec"
        if plant == "receipt_sha"
        else "public_cache_missing:util_elec"
    )
    with pytest.raises(ValueError, match=expected):
        cache_mod.pinned("util_elec")


def test_method_cache_c2_municipal_and_missing_municipality_guard(
    tmp_path, monkeypatch
):
    from decimal import Decimal as D

    import custodian.data_tests.cache as cache_mod
    from custodian.data_tests.test_pinned_methods import c2_municipal_churn

    monkeypatch.setattr(cache_mod, "CACHE", tmp_path)
    active_digest = _write_cached_source(
        tmp_path,
        "lic_active",
        [
            {
                "lbldy": "بلدية تجريبية أولى",
                "rmz_lnsht_ltjry": "5610101",
                "lnsht_ltjry": "نشاط تجريبي",
                "dd_lrkhs_lnsht": 200,
            },
            {
                "lbldy": "بلدية تجريبية ثانية",
                "rmz_lnsht_ltjry": "5610101",
                "lnsht_ltjry": "نشاط تجريبي",
                "dd_lrkhs_lnsht": 100,
            },
        ],
    )
    cancelled_digest = _write_cached_source(
        tmp_path,
        "lic_cancelled",
        [
            {
                "sn_llg": None,
                "shhr_llg": None,
                "lbldy": "بلدية تجريبية أولى",
                "rmz_lnsht_ltjry": "5610101",
                "sm_lnsht_ltjry": "نشاط تجريبي",
                "dd_lrkhs_lmlg": 5,
            },
            {
                "sn_llg": "2024",
                "shhr_llg": 1,
                "lbldy": "بلدية تجريبية أولى",
                "rmz_lnsht_ltjry": "5610101",
                "sm_lnsht_ltjry": "نشاط تجريبي",
                "dd_lrkhs_lmlg": 20,
            },
            {
                "sn_llg": "2024",
                "shhr_llg": 9,
                "lbldy": "بلدية تجريبية أولى",
                "rmz_lnsht_ltjry": "5610101",
                "sm_lnsht_ltjry": "نشاط تجريبي",
                "dd_lrkhs_lmlg": 10,
            },
            {
                "sn_llg": "2023",
                "shhr_llg": 6,
                "lbldy": "بلدية تجريبية ثانية",
                "rmz_lnsht_ltjry": "5610101",
                "sm_lnsht_ltjry": "نشاط تجريبي",
                "dd_lrkhs_lmlg": 4,
            },
        ],
    )
    (tmp_path / "method_pins.json").write_text(
        json.dumps({"lic_active": active_digest, "lic_cancelled": cancelled_digest})
    )
    active_rows, active_chain = cache_mod.pinned("lic_active")
    cancelled_rows, cancelled_chain = cache_mod.pinned("lic_cancelled")
    stock, cancelled_2024, result = c2_municipal_churn(
        active_rows,
        active_chain,
        cancelled_rows,
        cancelled_chain,
        "بلدية تجريبية أولى",
        "invented_one",
    )
    assert stock == D(200)
    assert cancelled_2024 == D(30)
    assert result["active_count"].value == D(200)
    assert result["including_percent"].value == D("15.0")
    assert result["undated_count"].value == D(5)
    assert result["undated_count"].geography == "national"
    assert result["including_percent"].geography == "municipality:invented_one"
    with pytest.raises(ValueError, match="municipality_missing:lic_active:absent"):
        c2_municipal_churn(
            active_rows,
            active_chain,
            cancelled_rows,
            cancelled_chain,
            "بلدية غير موجودة",
            "absent",
        )
    with pytest.raises(ValueError, match="municipality_missing:lic_cancelled:absent"):
        c2_municipal_churn(
            active_rows,
            active_chain,
            [r for r in cancelled_rows if r["lbldy"] == "بلدية تجريبية أولى"],
            cancelled_chain,
            "بلدية تجريبية ثانية",
            "absent",
        )
