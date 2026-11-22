"""Actual adapters over invented archives; never live-release evidence."""

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.test_source_completeness import entry

from eii_custodian.publicdata.assembly import AssemblyError
from eii_custodian.publicdata.assembly_adapters import Production
from eii_custodian.publicdata.fetch.registry import load_registry
from eii_custodian.publicdata.frame.build import FrameResult
from eii_custodian.publicdata.review.cache_fixture import write_cached


def context(tmp_path: Path, entries=()) -> Production:
    return Production(
        tuple(entries),
        tmp_path,
        Path("custodian/publicdata/review"),
        Path("."),
        lambda url: pytest.fail("network called"),
        lambda: "2026-11-18T00:00:00Z",
        lambda seconds: None,
        17,
        {},
    )


def test_selection_uses_reviewed_older_archive_and_refuses_substitution(
    tmp_path: Path,
) -> None:
    row = entry()
    old_path = write_cached(tmp_path, row, b'[{"amount":1}]')
    old = old_path.stem
    write_cached(tmp_path, row, b'[{"amount":2}]')
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({row.key: old}))
    build = context(tmp_path, (row,))
    build.reviewed_selections()
    assert build.selected == {row.key: old}
    assert build.raw(row) == [{"amount": 1}]
    old_path.write_bytes(b"[]")
    with pytest.raises((AssemblyError, ValueError)):
        build.raw(row)


def test_missing_pin_never_uses_fetched_hash_or_latest(tmp_path: Path) -> None:
    row = entry()
    write_cached(tmp_path, row, b"[]")
    (tmp_path / "snapshot_pins.json").unlink()
    build = context(tmp_path, (row,))
    with pytest.raises((AssemblyError, ValueError)):
        build.reviewed_selections()


@pytest.mark.parametrize("value, expected", [(25, "25.00"), (25.5, "25.50")])
def test_real_bank_credit_builder_and_null_unit_are_preserved(
    tmp_path: Path, value: int | float, expected: str
) -> None:
    row = replace(
        next(e for e in load_registry() if e.source_id == "bank_credit_act"),
        key="bank_credit_act",
    )
    digest = write_cached(
        tmp_path,
        row,
        json.dumps(
            [
                {
                    "year": "2026",
                    "economic_activity": "Invented activity",
                    "lnsht_lqtsdy": "نشاط تجريبي",
                    "value": value,
                }
            ]
        ).encode(),
    )
    build = context(tmp_path, (row,))
    build.selected = {row.key: digest.stem}
    build.frame_result = FrameResult({"grid_cell": []}, [], {}, {})
    build.gis_property_singles()
    rows = build.tables["pub_bank_credit"]
    assert rows[0]["value"] == Decimal(expected)
    assert rows[0]["value"].as_tuple().exponent == -2
    assert rows[0]["unit"] is None
    record = json.loads((tmp_path / "assembly/gis_property_singles.json").read_text())
    assert record["source_tables"] == {row.key: ["pub_bank_credit"]}


def test_bad_bank_column_is_real_builder_refusal(tmp_path: Path) -> None:
    row = replace(
        next(e for e in load_registry() if e.source_id == "bank_credit_act"),
        key="bank_credit_act",
    )
    digest = write_cached(tmp_path, row, b'[{"bad":1}]')
    build = context(tmp_path, (row,))
    build.selected = {row.key: digest.stem}
    build.frame_result = FrameResult({"grid_cell": []}, [], {}, {})
    with pytest.raises(Exception, match="unexpected_column"):
        build.gis_property_singles()
    assert not (tmp_path / "assembly/gis_property_singles.json").exists()


def test_real_frame_refuses_incomplete_inputs_instead_of_fixture_mode(
    tmp_path: Path,
) -> None:
    build = context(tmp_path)
    with pytest.raises(AssemblyError, match="assembly_frame_incomplete"):
        build.frame()


def test_real_height_seam_absence_is_named_and_not_a_table(tmp_path: Path) -> None:
    """A missing building table refuses (S2-P21 F3); it is never a NO_DATA record."""
    from eii_custodian.publicdata.heights.model import HeightError

    build = context(tmp_path)
    with pytest.raises(HeightError) as err:
        build.heights()
    assert err.value.name == "building_table_absent"
    assert not (tmp_path / "assembly/heights.json").exists()
    assert "pub_building_height" not in build.tables


def test_real_reconciliation_no_selection_is_named(tmp_path: Path, monkeypatch) -> None:
    from eii_custodian.publicdata import trade_reconciliation

    monkeypatch.setattr(trade_reconciliation, "load_selection", lambda: None)
    build = context(tmp_path)
    build.trade_reconciliation()
    assert (
        json.loads((tmp_path / "assembly/trade_reconciliation.json").read_text())[
            "state"
        ]
        == "NO_DATA"
    )


def test_adapter_map_matches_independent_inventory(tmp_path: Path) -> None:
    from eii_custodian.publicdata.assembly_inventory import validate_inventory

    build = context(tmp_path)
    validate_inventory(build.adapters())


def test_unknown_reviewed_key_is_refused(tmp_path: Path) -> None:
    row = entry()
    path = write_cached(tmp_path, row, b"[]")
    (tmp_path / "snapshot_pins.json").write_text(
        json.dumps({row.key: path.stem, "unregistered": "a" * 64})
    )
    with pytest.raises(AssemblyError, match="snapshot_selection_invalid"):
        context(tmp_path, (row,)).reviewed_selections()


def test_consistent_snapshot_of_other_source_is_refused(tmp_path: Path) -> None:
    row = entry()
    write_cached(tmp_path, replace(row, source_id="other_source"), b"[]")
    with pytest.raises(AssemblyError, match="assembly_lineage_missing"):
        context(tmp_path, (row,)).reviewed_selections()


def test_table_lineage_is_required_before_state_is_changed(tmp_path: Path) -> None:
    build = context(tmp_path)
    with pytest.raises(AssemblyError, match="assembly_lineage_missing"):
        build.table("pub_invented", [{"value": 1}], ("unreceipted",))
    assert build.tables == {}


def test_phase_output_records_versioned_method_and_actual_receipt_chain(
    tmp_path: Path,
) -> None:
    row = replace(
        next(e for e in load_registry() if e.source_id == "bank_credit_act"),
        key="bank_credit_act",
    )
    digest = write_cached(
        tmp_path,
        row,
        b'[{"year":"2026","economic_activity":"Invented","lnsht_lqtsdy":"SYN-activity","value":25}]',
    ).stem
    build = context(tmp_path, (row,))
    build.selected = {row.key: digest}
    build.frame_result = FrameResult({"grid_cell": []}, [], {})
    build.gis_property_singles()
    record = json.loads((tmp_path / "assembly/gis_property_singles.json").read_text())
    assert record["method"] == "public-assembly.gis_property_singles"
    assert record["method_version"] == "1"
    assert record["source_chain"][row.key]["sha256"] == digest
    assert record["source_chain"][row.key]["publisher"] == row.publisher
    assert record["source_chain"][row.key]["licence_basis"] == row.licence_basis
    assert record["source_chain"][row.key]["retrieved_utc"]


def test_gis_phase_does_not_claim_an_earlier_producers_table(tmp_path: Path) -> None:
    row = replace(
        next(e for e in load_registry() if e.source_id == "bank_credit_act"),
        key="bank_credit_act",
    )
    digest = write_cached(
        tmp_path,
        row,
        b'[{"year":"2026","economic_activity":"Invented","lnsht_lqtsdy":"SYN-activity","value":25}]',
    ).stem
    build = context(tmp_path, (row,))
    build.selected = {row.key: digest}
    build.reviewed_selections()
    build.table("pub_earlier", [], (row.key,))
    build.frame_result = FrameResult({"grid_cell": []}, [], {})
    build.gis_property_singles()
    record = json.loads((tmp_path / "assembly/gis_property_singles.json").read_text())
    assert set(record["tables"]) == {"pub_bank_credit"}


def test_overture_parent_pin_reads_its_declared_listing_archive(tmp_path: Path) -> None:
    from eii_custodian.publicdata.completeness import receipt_valid

    row = next(e for e in load_registry() if e.key == "places_ovt")
    stored = replace(row, key=row.key + "/listing", extension="json")
    identity = write_cached(tmp_path, stored, b'{"files":[]}').stem
    (tmp_path / "snapshot_pins.json").write_text(json.dumps({row.key: identity}))
    build = context(tmp_path, (row,))
    build.reviewed_selections()
    assert build.receipts[row.key]["key"] == stored.key
    assert build.receipts[row.key]["sha256"] == identity
    assert receipt_valid(row, build.receipts[row.key])


def test_listing_receipt_is_refused_for_an_invented_other_source() -> None:
    from custodian.tests.test_source_completeness import receipt

    from eii_custodian.publicdata.completeness import receipt_valid

    row = entry()
    assert receipt_valid(row, receipt(row)) is True
    stored = replace(row, key=row.key + "/listing", extension="json")
    assert receipt_valid(row, receipt(stored)) is False


def test_duplicate_table_is_refused_without_replacing_first_output(
    tmp_path: Path,
) -> None:
    from custodian.tests.test_source_completeness import receipt

    row = entry()
    state = context(tmp_path, (row,))
    state.receipts[row.key] = receipt(row)
    state.table("pub_invented", [{"value": 1}], (row.key,))
    with pytest.raises(AssemblyError, match="assembly_table_duplicate"):
        state.table("pub_invented", [{"value": 2}], (row.key,))
    assert state.tables["pub_invented"] == [{"value": 1}]
