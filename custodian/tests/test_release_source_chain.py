"""Build-time source chain. A refusal leaves the destination empty."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from eii_core.manifest import ColumnSpec, by_name
from eii_core.source_chain import SOURCE_KEYS
from eii_custodian.release.public_only import (
    TableWrite,
    WriterRefusal,
    write_public_only,
)

_COLUMNS = (
    ColumnSpec("period", "string", False),
    ColumnSpec("indicator", "string", False),
    ColumnSpec("value", "decimal(18,4)", False),
    ColumnSpec("unit", "string", False),
    ColumnSpec("source_id", "string", False),
)


def test_missing_registry_is_refused_before_writing(tmp_path: Path) -> None:
    """A public table without source_registry is not written."""
    with pytest.raises(WriterRefusal) as caught:
        write_public_only(tmp_path, _scalars(), (_source(),), (_table(),))
    assert caught.value.reason == "source_link_missing"
    assert list(tmp_path.iterdir()) == []


def test_incomplete_source_is_refused_before_writing(tmp_path: Path) -> None:
    """A source without its publisher is incomplete."""
    broken = _source()
    del broken["publisher"]
    _refuse(tmp_path, (broken,), _bundled((_table(),)), "source_link_incomplete")


def test_unknown_source_is_refused_before_writing(tmp_path: Path) -> None:
    """A manifest source that is not in the registry is unknown."""
    source = _source()
    source["source_id"] = "src-missing"
    _refuse(tmp_path, (source,), _bundled((_table(),)), "source_link_unknown")


def test_unknown_public_source_id_is_refused_before_writing(tmp_path: Path) -> None:
    """A Public row whose source_id is not registered is unknown."""
    row = _row()
    row["source_id"] = "src-missing"
    table = TableWrite("pub_census_national", _COLUMNS, (row,))
    _refuse(tmp_path, (_source(),), _bundled((table,)), "source_link_unknown")


def test_mismatched_publisher_is_refused_before_writing(tmp_path: Path) -> None:
    """A manifest publisher that differs from the registry is a mismatch."""
    source = _source()
    source["publisher"] = "INVENTED-other"
    _refuse(tmp_path, (source,), _bundled((_table(),)), "source_link_mismatch")


def test_lineage_without_method_version_is_incomplete(tmp_path: Path) -> None:
    """A fact_lineage transform without method@version is incomplete."""
    tables = _bundled((_table(),))
    lineage = tables[-1]
    row = dict(lineage.rows[0])
    row["transform"] = "invented-no-version"
    replaced = TableWrite(lineage.name, lineage.columns, (row,))
    _refuse(tmp_path, (_source(),), (*tables[:-1], replaced), "source_link_incomplete")


def test_public_table_without_a_lineage_row_is_missing(tmp_path: Path) -> None:
    """A Public table with no fact_lineage row is a missing link."""
    tables = _bundled((_table(),))
    lineage = tables[-1]
    empty = TableWrite(
        lineage.name,
        lineage.columns,
        (
            {
                "lineage_id": "lin_other",
                "source_id": "src-invented",
                "table_name": "district",
                "transform": "invented.module.hold@v1",
            },
        ),
    )
    _refuse(tmp_path, (_source(),), (*tables[:-1], empty), "source_link_missing")


def _refuse(
    folder: Path,
    sources: tuple[dict[str, str], ...],
    tables: tuple[TableWrite, ...],
    reason: str,
) -> None:
    with pytest.raises(WriterRefusal) as caught:
        write_public_only(folder, _scalars(), sources, tables)
    assert caught.value.reason == reason
    assert list(folder.iterdir()) == []


def _scalars() -> dict[str, object]:
    return {
        "build_id": "build-invented",
        "built_at": "2026-01-01T00:00:00Z",
        "code_version": "invented-code",
        "engine_versions": {
            "duckdb": "2.0.0",
            "postgis_target": "3.6",
            "python": "3.14",
        },
        "release_contract_version": "release.v1",
        "release_kind": "public_only",
        "rules_version_id": "invented-rules",
    }


def _row() -> dict[str, object]:
    return {
        "indicator": "invented-indicator",
        "period": "2020",
        "source_id": "src-invented",
        "unit": "persons",
        "value": Decimal("1.2500"),
    }


def _table() -> TableWrite:
    return TableWrite("pub_census_national", _COLUMNS, (_row(),))


def _source() -> dict[str, str]:
    return {
        "licence": "INVENTED-licence",
        "licence_basis": "INVENTED-basis",
        "publisher": "INVENTED-publisher",
        "retrieved_on": "2026-01-01",
        "sha256": "ab" * 32,
        "source_id": "src-invented",
        "title": "INVENTED-dataset",
        "url": "https://invented.invalid/page",
    }


def _bundled(tables: tuple[TableWrite, ...]) -> tuple[TableWrite, ...]:
    public = tuple(
        table.name
        for table in tables
        if (catalogue := by_name(table.name)) is not None
        and catalogue.manifest_class == "public"
    )
    registry = TableWrite(
        "source_registry",
        tuple(ColumnSpec(key, "string", False) for key in SOURCE_KEYS),
        (_source(),),
    )
    rows = tuple(
        {
            "lineage_id": f"lin_{name}",
            "source_id": "src-invented",
            "table_name": name,
            "transform": "invented.module.hold@v1",
        }
        for name in public
    )
    lineage = TableWrite(
        "fact_lineage",
        (
            ColumnSpec("lineage_id", "string", False),
            ColumnSpec("source_id", "string", False),
            ColumnSpec("table_name", "string", False),
            ColumnSpec("transform", "string", False),
        ),
        rows,
    )
    return (*tables, registry, lineage)
