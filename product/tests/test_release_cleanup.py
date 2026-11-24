"""A failed load leaves no staging schema or table after the connection closes."""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from eii_core.manifest import ColumnSpec
from eii_core.source_chain import SOURCE_KEYS
from eii_product.store.loader import PARTIAL_READER, READER_NAME, load_checked
from eii_product.store.release_check import RELEASE_MANIFEST_COLUMNS, CheckedRelease

IDENTITY = "ab" * 32
_QUOTED = re.compile(r'"([^"]+)"')
_FROM = re.compile(r'FROM "([^"]+)"\."([^"]+)"')


def test_lineage_tables_are_verified_like_every_table() -> None:
    """source_registry and fact_lineage take the same digest comparison."""
    from eii_product.store.loader import LoadRefusal, verify_staged

    checked = _checked(Path("."))
    rows = _memory_rows()
    verify_staged(rows, rows, checked)
    changed = copy.deepcopy(rows)
    registry = dict(changed["source_registry"][0])
    registry["publisher"] = "INVENTED-other"
    changed["source_registry"] = (registry,)
    with pytest.raises(LoadRefusal) as caught:
        verify_staged(rows, changed, checked)
    assert caught.value.reason == "store_verification_failed"


def test_abandoned_staging_is_committed_away(tmp_path: Path) -> None:
    """A failure after the staging commit leaves neither store with a stage."""
    _write_parquet(tmp_path)
    (tmp_path / READER_NAME).mkdir()
    stand = _Ledger()
    with pytest.raises(OSError):
        load_checked(stand, _checked(tmp_path))
    stand.close()
    assert stand.committed == {}
    drops = [
        index
        for index, sql in enumerate(stand.statements)
        if sql.startswith("DROP SCHEMA")
    ]
    commits = [index for index, sql in enumerate(stand.statements) if sql == "COMMIT"]
    assert drops
    assert commits
    assert commits[-1] > drops[-1]
    assert not (tmp_path / PARTIAL_READER).exists()
    created = [sql for sql in stand.statements if sql.startswith("CREATE TABLE")]
    for name in (
        "pub_census_national",
        "source_registry",
        "fact_lineage",
        "release_manifest",
    ):
        assert any(f'."{name}"' in sql or f'"{name}"' in sql for sql in created)


def _checked(folder: Path) -> CheckedRelease:
    tables = (
        ("pub_census_national", "public", _public_columns()),
        (
            "source_registry",
            "lineage",
            tuple(ColumnSpec(key, "string", False) for key in SOURCE_KEYS),
        ),
        ("fact_lineage", "lineage", _lineage_columns()),
    )
    entries = [
        {
            "file": f"tables/{name}.parquet",
            "grain": "invented",
            "name": name,
            "provenance_class": kind,
            "row_count": 1,
            "schema_sha256": "cd" * 32,
            "sha256": "ab" * 32,
        }
        for name, kind, _columns in tables
    ]
    document: dict[str, object] = {
        "artefacts": [],
        "build_id": "build-invented",
        "built_at": "2026-01-02T00:00:00Z",
        "code_version": "invented-code",
        "engine_versions": {
            "duckdb": "2.0.0",
            "postgis_target": "3.6",
            "python": "3.14",
        },
        "release_contract_version": "release.v1",
        "release_id": IDENTITY,
        "release_kind": "public_only",
        "rules_version_id": "invented-rules",
        "sources": [],
        "tables": entries,
    }
    return CheckedRelease(
        folder,
        document,
        {name: columns for name, _kind, columns in tables},
    )


def _public_columns() -> tuple[ColumnSpec, ...]:
    return (
        ColumnSpec("period", "string", False),
        ColumnSpec("indicator", "string", False),
        ColumnSpec("value", "int", False),
    )


def _lineage_columns() -> tuple[ColumnSpec, ...]:
    return (
        ColumnSpec("lineage_id", "string", False),
        ColumnSpec("source_id", "string", False),
        ColumnSpec("table_name", "string", False),
        ColumnSpec("transform", "string", False),
    )


def _memory_rows() -> dict[str, tuple[dict[str, object], ...]]:
    registry = {
        key: "INVENTED-publisher" if key == "publisher" else "src-invented"
        for key in SOURCE_KEYS
    }
    registry["sha256"] = "ab" * 32
    lineage = {
        "lineage_id": "lin_pub_census_national",
        "source_id": "src-invented",
        "table_name": "pub_census_national",
        "transform": "invented.module.hold@v1",
    }
    names = ("pub_census_national", "source_registry", "fact_lineage")
    manifest = tuple(
        {
            column.name: IDENTITY if column.name == "release_id" else name
            for column in RELEASE_MANIFEST_COLUMNS
        }
        for name in names
    )
    return {
        "fact_lineage": (lineage,),
        "pub_census_national": (
            {"indicator": "invented", "period": "2020", "value": 1},
        ),
        "release_manifest": manifest,
        "source_registry": (registry,),
    }


def _write_parquet(folder: Path) -> None:
    import duckdb

    table_dir = folder / "tables"
    table_dir.mkdir()
    registry_values = ", ".join(f"'{_cell(key)}' AS \"{key}\"" for key in SOURCE_KEYS)
    statements = {
        "pub_census_national": "SELECT '2020' AS period, 'invented' AS indicator, 1 AS value",
        "source_registry": f"SELECT {registry_values}",
        "fact_lineage": (
            "SELECT 'lin_pub_census_national' AS lineage_id, "
            "'src-invented' AS source_id, 'pub_census_national' AS table_name, "
            "'invented.module.hold@v1' AS transform"
        ),
    }
    connection = duckdb.connect()
    try:
        for name, select in statements.items():
            target = str(table_dir / f"{name}.parquet").replace("'", "''")
            connection.execute(f"COPY ({select}) TO '{target}' (FORMAT PARQUET)")
    finally:
        connection.close()


def _cell(key: str) -> str:
    if key == "publisher":
        return "INVENTED-publisher"
    if key == "sha256":
        return "ab" * 32
    if key == "retrieved_on":
        return "2026-01-02"
    if key == "source_id":
        return "src-invented"
    return f"INVENTED-{key}"


class _Ledger:
    """A PostgreSQL stand-in that keeps only committed schemas."""

    stand_in = True

    def __init__(self) -> None:
        self.committed: dict[str, dict[str, list[tuple[object, ...]]]] = {}
        self.working: dict[str, dict[str, list[tuple[object, ...]]]] = {}
        self.in_txn = False
        self.statements: list[str] = []

    def execute(self, sql: str, _params: object = None) -> list[tuple[object, ...]]:
        self.statements.append(sql)
        if "rolsuper" in sql:
            return [("eii_owner", False)]
        if "extnamespace" in sql:
            return [("ext_invented",)]
        if "extname" in sql and "pg_extension" in sql:
            return [("plpgsql",), ("postgis",)]
        if sql.startswith("SELECT nspname"):
            name = _params[0] if isinstance(_params, tuple) else ""
            return [(name,)] if name in self._visible() else []
        if sql == "BEGIN":
            self._begin()
            return []
        if sql == "COMMIT":
            self.committed = copy.deepcopy(self.working)
            self.in_txn = False
            return []
        if sql == "ROLLBACK":
            self.working = copy.deepcopy(self.committed)
            self.in_txn = False
            return []
        if sql.startswith("CREATE SCHEMA"):
            self._touch()
            self.working[_QUOTED.findall(sql)[0]] = {}
            return []
        if sql.startswith("DROP SCHEMA"):
            self._touch()
            self.working.pop(_QUOTED.findall(sql)[0], None)
            return []
        if sql.startswith("ALTER SCHEMA"):
            self._touch()
            left, right = _QUOTED.findall(sql)
            self.working[right] = self.working.pop(left, {})
            return []
        if sql.startswith("CREATE TABLE"):
            self._touch()
            schema, table = _QUOTED.findall(sql)[:2]
            self.working.setdefault(schema, {})[table] = []
            return []
        found = _FROM.search(sql)
        if found is not None:
            schema, table = found.groups()
            return list(self._visible().get(schema, {}).get(table, []))
        return []

    def copy_rows(self, sql: str, rows: list[tuple[object, ...]]) -> None:
        self.statements.append(sql)
        self._touch()
        schema, table = _QUOTED.findall(sql)[:2]
        self.working.setdefault(schema, {})[table] = [tuple(row) for row in rows]

    def close(self) -> None:
        """Drop an open transaction, as a server does when the session ends."""
        if self.in_txn:
            self.working = copy.deepcopy(self.committed)
            self.in_txn = False

    def _begin(self) -> None:
        if not self.in_txn:
            self.working = copy.deepcopy(self.committed)
            self.in_txn = True

    def _touch(self) -> None:
        if not self.in_txn:
            self._begin()

    def _visible(self) -> dict[str, dict[str, list[tuple[object, ...]]]]:
        return self.working if self.in_txn else self.committed
