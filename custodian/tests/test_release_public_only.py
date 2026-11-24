"""The public_only writer, on invented rows, and each refusal."""

from __future__ import annotations

import hashlib
import json
import struct
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from eii_core.manifest import (
    CATALOGUE,
    ColumnSpec,
    by_name,
    canonical_json,
    release_hash,
    schema_hash,
)
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


def _scalars(**extra: object) -> dict[str, object]:
    fields: dict[str, object] = {
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
    fields.update(extra)
    return fields


def _row(indicator: str = "invented-indicator") -> dict[str, object]:
    return {
        "period": "2020",
        "indicator": indicator,
        "value": Decimal("1.2500"),
        "unit": "persons",
        "source_id": "src-invented",
    }


def _table(rows: tuple[dict[str, object], ...] | None = None) -> TableWrite:
    body = (_row(),) if rows is None else rows
    return TableWrite("pub_census_national", _COLUMNS, body)


def _sources() -> tuple[dict[str, str], ...]:
    return (_source_record(),)


def _source_record() -> dict[str, str]:
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


def _with_chain(tables: tuple[TableWrite, ...]) -> tuple[TableWrite, ...]:
    """Append the lineage tables a public_only release has to hold."""
    public = tuple(
        table.name
        for table in tables
        if (catalogue := by_name(table.name)) is not None
        and catalogue.manifest_class == "public"
    )
    registry = TableWrite(
        "source_registry",
        tuple(ColumnSpec(key, "string", False) for key in SOURCE_KEYS),
        (_source_record(),),
    )
    lineage_rows = tuple(
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
        lineage_rows,
    )
    return (*tables, registry, lineage)


def _write(folder: Path, table: TableWrite | None = None, **scalars: object) -> str:
    body = (_table(),) if table is None else (table,)
    return write_public_only(folder, _scalars(**scalars), _sources(), _with_chain(body))


def _point() -> bytes:
    return struct.pack("<BI2d", 1, 1, 1.0, 2.0)


def test_literal_canonical_bytes_and_sha256() -> None:
    """The same hand-written bytes and hashlib digests as the core literal test."""
    release_bytes = '{"release_kind":"public_only","tables":[]}'
    schema_bytes = '[{"logical_type":"string","name":"label","nullable":false}]'
    row_bytes = '[{"label":"invented"}]'
    release_sha = "c880f42f38270ff391c0078412f4d46a00fc1fbb66478d2ca7ff67048aada721"
    schema_sha = "84d0138670a68a839672e9ccc0b12e03c21e808e66d25acbf727a6539423523a"
    row_sha = "b2a3679905852fc98f9d8008ca43960a0ed76420253ead2008b0d0b4fa08e0e9"
    document = {
        "build_id": "build-a",
        "built_at": "2026-01-01T00:00:00Z",
        "release_id": "ab" * 32,
        "release_kind": "public_only",
        "tables": [],
    }
    assert release_hash(document) == release_sha
    assert (
        canonical_json(
            {
                key: value
                for key, value in document.items()
                if key not in {"release_id", "build_id", "built_at"}
            }
        )
        == release_bytes
    )
    columns = (ColumnSpec("label", "string", False),)
    assert schema_hash(columns) == schema_sha
    assert (
        canonical_json([{"logical_type": "string", "name": "label", "nullable": False}])
        == schema_bytes
    )
    from eii_product.store.release_check import digest_rows

    assert digest_rows(({"label": "invented"},), columns, ("label",)) == row_sha
    assert canonical_json([{"label": "invented"}]) == row_bytes


def test_written_manifest_verifies(tmp_path: Path) -> None:
    """Recorded hashes, counts and release_id match the written files."""
    folder = tmp_path / "release"
    release_id = _write(folder)
    document = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert document["release_id"] == release_id
    assert document["release_id"] == release_hash(document)
    assert document["release_kind"] == "public_only"
    entry = document["tables"][0]
    payload = (folder / "tables" / "pub_census_national.parquet").read_bytes()
    assert entry["sha256"] == hashlib.sha256(payload).hexdigest()
    assert entry["row_count"] == 1
    assert entry["schema_sha256"] == schema_hash(_COLUMNS)
    assert entry["provenance_class"] == "public"
    stored = _schema_text(folder / "tables" / "pub_census_national.parquet")
    assert hashlib.sha256(stored).hexdigest() == entry["schema_sha256"]
    assert stored.decode("utf-8") == canonical_json(
        [
            {
                "logical_type": column.logical_type,
                "name": column.name,
                "nullable": False,
            }
            for column in _COLUMNS
        ]
    )


def test_same_rows_same_release_id(tmp_path: Path) -> None:
    """Two writes of the same rows share one release id."""
    first = _write(tmp_path / "one")
    second = _write(tmp_path / "two")
    assert first == second


def test_one_changed_value_changes_release_id(tmp_path: Path) -> None:
    """One changed cell is a different release."""
    first = _write(tmp_path / "one")
    changed = TableWrite("pub_census_national", _COLUMNS, (_row("other-indicator"),))
    second = _write(tmp_path / "two", changed)
    assert first != second


def test_geometry_round_trip_needs_no_extension(tmp_path: Path) -> None:
    """WKB written as GEOMETRY is read back by hex(ST_AsWKB) without an extension."""
    columns = (
        ColumnSpec("district_key", "string", False),
        ColumnSpec("name_en", "string", False),
        ColumnSpec("name_ar", "string", False),
        ColumnSpec("municipality_code", "string", False),
        ColumnSpec("geometry", "geometry", False, "Geometry", 4326),
        ColumnSpec("source_id", "string", False),
    )
    row = {
        "district_key": "d1",
        "geometry": _point(),
        "municipality_code": "m1",
        "name_ar": "INVENTED-district-ar",
        "name_en": "INVENTED-district",
        "source_id": "src-invented",
    }
    folder = tmp_path / "geom"
    write_public_only(
        folder,
        _scalars(),
        _sources(),
        _with_chain((TableWrite("district", columns, (row,)),)),
    )
    import duckdb

    connection = duckdb.connect()
    try:
        literal = str(folder / "tables" / "district.parquet").replace("'", "''")
        found = connection.execute(
            f"SELECT hex(ST_AsWKB(geometry)) FROM read_parquet('{literal}')"
        ).fetchone()
    finally:
        connection.close()
    assert found is not None
    assert found[0] == _point().hex().upper()


def test_refuses_an_unknown_table(tmp_path: Path) -> None:
    """A table outside the catalogue leaves the destination empty."""
    _expect(tmp_path, TableWrite("not_a_table", _COLUMNS, (_row(),)), "unknown_table")


def test_refuses_release_manifest(tmp_path: Path) -> None:
    """release_manifest is not a release input."""
    _expect(
        tmp_path,
        TableWrite("release_manifest", _COLUMNS, (_row(),)),
        "unknown_table",
    )


def test_refuses_each_protected_and_simulated_table(tmp_path: Path) -> None:
    """Every protected and every simulated catalogue table is refused by name."""
    protected = [row.name for row in CATALOGUE if row.manifest_class == "protected"]
    simulated = [row.name for row in CATALOGUE if row.manifest_class == "simulated"]
    assert len(protected) == 7
    assert len(simulated) == 6
    for name in protected + simulated:
        folder = tmp_path / name
        table = TableWrite(
            name, (ColumnSpec("ignored", "string", True),), ({"ignored": None},)
        )
        _expect(folder, table, "forbidden_table_class")


def test_refuses_privacy_written_frame_and_control_tables(tmp_path: Path) -> None:
    """release_unit, unit_member and the Control tables are privacy-written."""
    names = [
        row.name
        for row in CATALOGUE
        if row.writer == "privacy"
        and row.manifest_class not in {"protected", "simulated"}
    ]
    assert names == [
        "release_unit",
        "unit_member",
        "rules_version",
        "suppression_reason",
        "survival_report",
    ]
    for name in names:
        _expect(
            tmp_path / name,
            TableWrite(
                name, (ColumnSpec("ignored", "string", True),), ({"ignored": None},)
            ),
            "privacy_written_table",
        )


def test_refuses_an_empty_table_list(tmp_path: Path) -> None:
    """No tables is not a release."""
    folder = tmp_path / "empty"
    with pytest.raises(WriterRefusal) as caught:
        write_public_only(folder, _scalars(), _sources(), ())
    assert caught.value.reason == "empty_table_list"
    assert not folder.exists() or list(folder.iterdir()) == []


def test_refuses_a_row_whose_columns_differ(tmp_path: Path) -> None:
    """An extra or missing column is refused."""
    row = _row()
    row["extra"] = "x"
    _expect(
        tmp_path,
        TableWrite("pub_census_national", _COLUMNS, (row,)),
        "column_mismatch",
    )


def test_refuses_a_null_in_a_required_column(tmp_path: Path) -> None:
    """A null in a column declared not nullable is refused."""
    row = _row()
    row["source_id"] = None
    _expect(
        tmp_path,
        TableWrite("pub_census_national", _COLUMNS, (row,)),
        "null_not_allowed",
    )


def test_refuses_a_geometry_srid_other_than_4326(tmp_path: Path) -> None:
    """A geometry column whose SRID is not 4326 is refused."""
    columns = (
        ColumnSpec("district_key", "string", False),
        ColumnSpec("name_en", "string", False),
        ColumnSpec("name_ar", "string", False),
        ColumnSpec("municipality_code", "string", False),
        ColumnSpec("geometry", "geometry", False, "Geometry", 0),
        ColumnSpec("source_id", "string", False),
    )
    row = {
        "district_key": "d1",
        "name_en": "INVENTED-district",
        "name_ar": "INVENTED-district-ar",
        "municipality_code": "m1",
        "geometry": _point(),
        "source_id": "src-invented",
    }
    _expect(tmp_path, TableWrite("district", columns, (row,)), "geometry_srid_invalid")


def test_refuses_a_forbidden_scalar(tmp_path: Path) -> None:
    """A protected-only field is refused and nothing is written."""
    folder = tmp_path / "forbidden"
    with pytest.raises(WriterRefusal) as caught:
        write_public_only(
            folder,
            _scalars(window_key="ab" * 32),
            _sources(),
            (_table(),),
        )
    assert caught.value.reason == "forbidden_manifest_field"
    assert not folder.exists() or list(folder.iterdir()) == []


def _expect(folder: Path, table: TableWrite, reason: str) -> None:
    target = (
        folder if folder.name != "test_refuses_an_unknown_table" else folder / "out"
    )
    if not target.exists():
        target.mkdir(parents=True)
    with pytest.raises(WriterRefusal) as caught:
        write_public_only(target, _scalars(), _sources(), (table,))
    assert caught.value.reason == reason
    assert list(target.iterdir()) == []


def _wrong_type(value: object) -> Any:
    """Hand a value through without a suppression comment."""
    return value


def test_refuses_engine_versions_missing_a_key(tmp_path: Path) -> None:
    """A map without python is refused before any release file is written."""
    engines = {"duckdb": "2.0.0", "postgis_target": "3.6"}
    _expect_engines(tmp_path / "missing", engines, "manifest_type_invalid")


def test_refuses_an_unknown_engine_key(tmp_path: Path) -> None:
    """An engine key outside duckdb, postgis_target and python is refused."""
    engines = {
        "duckdb": "2.0.0",
        "invented_engine": "1.0.0",
        "postgis_target": "3.6",
        "python": "3.14",
    }
    _expect_engines(tmp_path / "unknown", engines, "unknown_manifest_key")


def test_refuses_an_engine_key_in_another_case(tmp_path: Path) -> None:
    """DuckDB and PYTHON are not the engine keys."""
    plants = (
        {"DuckDB": "2.0.0", "postgis_target": "3.6", "python": "3.14"},
        {"duckdb": "2.0.0", "postgis_target": "3.6", "PYTHON": "3.14"},
    )
    for index, engines in enumerate(plants):
        _expect_engines(tmp_path / f"case-{index}", engines, "manifest_key_case")


def test_refuses_an_empty_engine_version(tmp_path: Path) -> None:
    """An empty version string is refused before any release file is written."""
    engines = {"duckdb": "2.0.0", "postgis_target": "3.6", "python": ""}
    _expect_engines(tmp_path / "empty", engines, "manifest_type_invalid")


def test_refuses_a_non_string_engine_version(tmp_path: Path) -> None:
    """A version that is not a string is refused before any release file is written."""
    engines: dict[str, object] = {
        "duckdb": "2.0.0",
        "postgis_target": "3.6",
        "python": _wrong_type(3),
    }
    _expect_engines(tmp_path / "type", engines, "manifest_type_invalid")


def _expect_engines(folder: Path, engines: object, reason: str) -> None:
    with pytest.raises(WriterRefusal) as caught:
        write_public_only(
            folder,
            _scalars(engine_versions=engines),
            _sources(),
            _with_chain((_table(),)),
        )
    assert caught.value.reason == reason
    assert not folder.exists() or list(folder.iterdir()) == []


def _schema_text(path: Path) -> bytes:
    import duckdb

    connection = duckdb.connect()
    try:
        rows = connection.execute(
            "SELECT value FROM parquet_kv_metadata(?) WHERE key = ?",
            [str(path), "eii_logical_schema"],
        ).fetchall()
    except Exception:
        literal = str(path).replace("'", "''")
        rows = connection.execute(
            f"SELECT value FROM parquet_kv_metadata('{literal}') WHERE key = 'eii_logical_schema'"
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) == 1
    value = rows[0][0]
    assert isinstance(value, bytes)
    return value
