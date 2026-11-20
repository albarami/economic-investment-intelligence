"""S2-T19 open-data family release tables (decision 0064 item 29)."""

import json
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path

import pytest
from custodian.tests.repository_root import repository_root
from custodian.tests.test_production_adapters import context
from custodian.tests.test_s2_t19_registry import FAMILIES, _fixture_entry, _transport

from eii_custodian.publicdata.fetch.build import fetch_entry
from eii_custodian.publicdata.fetch.registry import COLLECTED_FAMILIES, load_registry
from eii_custodian.publicdata.frame.build import FrameResult
from eii_custodian.publicdata.review.cache_fixture import write_cached
from eii_custodian.publicdata.singles.families import (
    FamilyError,
    family_table_name,
    parse_family_rows,
)

REPO = repository_root(Path(__file__))


def test_each_family_registry_names_its_release_table():
    for entry in load_registry(REPO / "custodian/publicdata/sources.yaml"):
        if entry.source_id not in FAMILIES:
            continue
        assert entry.release_tables == (family_table_name(entry.source_id),)


def test_family_fetch_receipt_names_its_release_table(tmp_path):
    entry = replace(_fixture_entry(), release_tables=("pub_trade_ext",))
    records = [
        {"year": "2020-01-01", "value": 1},
        {"year": "2021-01-01", "value": 2},
    ]
    assert (
        fetch_entry(
            entry,
            _transport(entry, records),
            tmp_path,
            lambda: "2026-11-15T00:00:00Z",
            lambda _: None,
        )
        is None
    )
    receipt = json.loads(next(tmp_path.rglob("*.meta.json")).read_text())
    assert receipt["release_tables"] == ["pub_trade_ext"]


def test_undeclared_column_is_refused():
    entry = replace(
        _fixture_entry(),
        columns=(("year", "string"), ("value", "number")),
    )
    rows = [{"year": "2020-01-01", "value": 1, "invented": "shape"}]
    with pytest.raises(FamilyError, match="unexpected_column"):
        parse_family_rows(
            entry, rows, retrieved_utc="2026-11-15T00:00:00Z", sha256="a" * 64
        )


def test_declared_columns_reach_release_shape():
    entry = replace(
        _fixture_entry(),
        columns=(("year", "string"), ("value", "number")),
    )
    rows = [{"year": "2020-01-01", "value": 2.5}]
    cells = parse_family_rows(
        entry, rows, retrieved_utc="2026-11-15T00:00:00Z", sha256="b" * 64
    )
    assert len(cells) == 2
    assert {cell.field_name for cell in cells} == {"year", "value"}
    assert json.loads(next(c.field_value for c in cells if c.field_name == "year")) == (
        "2020-01-01"
    )
    assert (
        json.loads(next(c.field_value for c in cells if c.field_name == "value")) == 2.5
    )
    row = asdict(cells[0])
    assert row["source_key"] == entry.key
    assert row["sha256"] == "b" * 64


def test_family_assembly_accumulates_declared_cells(tmp_path):
    entry = next(
        e
        for e in load_registry(REPO / "custodian/publicdata/sources.yaml")
        if e.key == "trade_ext/imports-by-nature-of-items-and-year"
    )
    declared = {name for name, _kind in entry.columns}
    row = {
        name: ("2020-01-01" if kind == "string" else 1) for name, kind in entry.columns
    }
    digest = write_cached(tmp_path, entry, json.dumps([row]).encode())
    build = context(tmp_path, (entry,))
    build.selected = {entry.key: digest.stem}
    build.frame_result = FrameResult({"grid_cell": []}, [], {}, {})
    build.gis_property_singles()
    table = family_table_name(entry.source_id)
    assert len(build.tables[table]) == len(declared)
    assert {r["field_name"] for r in build.tables[table]} == declared


def test_family_table_contract_is_documented():
    doc = (REPO / "docs/03_DATA_CONTRACTS.md").read_text()
    for source_id in sorted(COLLECTED_FAMILIES):
        assert f"`{family_table_name(source_id)}`" in doc
    pack = (REPO / "docs/04_PUBLIC_DATA_PACK.md").read_text()
    section = pack.split("### 2.2 Coverage, use and traps", 1)[1]
    for source_id in sorted(COLLECTED_FAMILIES):
        row = next(
            line
            for line in section.splitlines()
            if line.startswith(f"| `{source_id}` |")
        )
        assert family_table_name(source_id) in row.split("|", 5)[4]


def test_decimal_measure_encodes_for_release():
    entry = replace(
        _fixture_entry(),
        columns=(("year", "string"), ("value", "number")),
    )
    rows = [{"year": "2020-01-01", "value": Decimal("12.340")}]
    cells = parse_family_rows(
        entry, rows, retrieved_utc="2026-11-15T00:00:00Z", sha256="c" * 64
    )
    encoded = next(c.field_value for c in cells if c.field_name == "value")
    assert encoded == "12.34"
    assert Decimal(encoded) == Decimal("12.34")


def test_text_measure_in_number_column_is_refused():
    entry = replace(
        _fixture_entry(),
        columns=(("year", "string"), ("value", "number")),
    )
    with pytest.raises(FamilyError, match="field_kind"):
        parse_family_rows(
            entry,
            [{"year": "2020-01-01", "value": "not-a-number"}],
            retrieved_utc="2026-11-15T00:00:00Z",
            sha256="d" * 64,
        )


def test_boolean_measure_in_number_column_is_refused():
    entry = replace(
        _fixture_entry(),
        columns=(("year", "string"), ("value", "number")),
    )
    with pytest.raises(FamilyError, match="field_kind"):
        parse_family_rows(
            entry,
            [{"year": "2020-01-01", "value": True}],
            retrieved_utc="2026-11-15T00:00:00Z",
            sha256="e" * 64,
        )


def test_family_assembly_refuses_duplicate_measure_key(tmp_path):
    entry = next(
        e
        for e in load_registry(REPO / "custodian/publicdata/sources.yaml")
        if e.key == "trade_ext/imports-by-nature-of-items-and-year"
    )
    number = next(name for name, kind in entry.columns if kind == "number")
    string_fields = {
        name: "2020-01-01" for name, kind in entry.columns if kind == "string"
    }
    inner = ",".join(
        [f'"{name}":"{string_fields[name]}"' for name in sorted(string_fields)]
        + [f'"{number}":1', f'"{number}":2']
    )
    body = ("[{" + inner + "}]").encode()
    digest = write_cached(tmp_path, entry, body)
    build = context(tmp_path, (entry,))
    build.selected = {entry.key: digest.stem}
    build.frame_result = FrameResult({"grid_cell": []}, [], {}, {})
    with pytest.raises(FamilyError, match="duplicate_member"):
        build.gis_property_singles()


def test_family_assembly_round_trips_decimal_measure(tmp_path):
    entry = next(
        e
        for e in load_registry(REPO / "custodian/publicdata/sources.yaml")
        if e.key == "trade_ext/imports-by-nature-of-items-and-year"
    )
    parts = []
    for name, kind in entry.columns:
        if kind == "string":
            parts.append(f'"{name}":"2020-01-01"')
        else:
            parts.append(f'"{name}":99.01')
    body = ("[{" + ",".join(parts) + "}]").encode()
    digest = write_cached(tmp_path, entry, body)
    build = context(tmp_path, (entry,))
    build.selected = {entry.key: digest.stem}
    build.frame_result = FrameResult({"grid_cell": []}, [], {}, {})
    build.gis_property_singles()
    table = family_table_name(entry.source_id)
    number = next(name for name, kind in entry.columns if kind == "number")
    encoded = next(
        r["field_value"] for r in build.tables[table] if r["field_name"] == number
    )
    assert encoded == "99.01"
    assert build.tables[table][0]["sha256"] == build.receipts[entry.key]["sha256"]
