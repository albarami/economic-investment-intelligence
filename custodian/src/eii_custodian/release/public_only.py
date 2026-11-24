"""Write one public_only release through DuckDB. The driver is imported inside."""

from __future__ import annotations

import hashlib
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from eii_core.manifest import (
    FORBIDDEN_PUBLIC_ONLY,
    ColumnSpec,
    by_name,
    canonical_json,
    engine_versions_reason,
    listed_inputs_reason,
    release_hash,
    schema_document,
    schema_hash,
    written_by_privacy,
)
from eii_core.source_chain import ChainTable, SourceChainRefusal, require_public_chain

_REASONS = frozenset(
    {
        "column_mismatch",
        "duplicate_key",
        "empty_table_list",
        "forbidden_manifest_field",
        "forbidden_table_class",
        "geometry_srid_invalid",
        "manifest_key_case",
        "manifest_type_invalid",
        "null_not_allowed",
        "privacy_written_table",
        "release_kind_unsupported",
        "source_link_incomplete",
        "source_link_mismatch",
        "source_link_missing",
        "source_link_unknown",
        "unknown_manifest_key",
        "unknown_table",
    }
)
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_SRID = 4326
_EWKB_FLAG = 0x20000000
_SCHEMA_KEY = "eii_logical_schema"


class WriterRefusal(Exception):
    """A fixed reason. The destination is left without a release."""

    def __init__(self, reason: str) -> None:
        """Refuse a reason outside the writer's closed list."""
        if reason not in _REASONS:
            message = "refusal reason invalid"
            raise ValueError(message)
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class TableWrite:
    """One table to write: its declared columns and its invented rows."""

    name: str
    columns: tuple[ColumnSpec, ...]
    rows: tuple[Mapping[str, object], ...]


def write_public_only(
    destination: Path,
    scalars: Mapping[str, object],
    sources: Sequence[Mapping[str, object]],
    tables: Sequence[TableWrite],
    *,
    artefacts: Sequence[Mapping[str, object]] = (),
    listed_inputs: Sequence[Mapping[str, object]] = (),
) -> str:
    """Write Parquet tables and a canonical manifest. Return the release id.

    ``listed_inputs`` names a file read outside the release with its hash; the
    field is written only when an entry is listed (L-1509).
    """
    _refuse_scalars(scalars)
    if listed_inputs:
        listed = listed_inputs_reason(list(listed_inputs))
        if listed is not None:
            raise WriterRefusal(listed)
    if len(tables) == 0:
        raise WriterRefusal("empty_table_list")
    for table in tables:
        _refuse_table(table)
    _refuse_chain(sources, tables)
    destination.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        table_dir = destination / "tables"
        table_dir.mkdir()
        created.append(table_dir)
        entries: list[dict[str, object]] = []
        for table in tables:
            path = table_dir / f"{table.name}.parquet"
            schema_text = canonical_json(schema_document(table.columns))
            _write_parquet(path, table, schema_text)
            catalogue = by_name(table.name)
            if catalogue is None:
                raise WriterRefusal("unknown_table")
            entries.append(
                {
                    "file": f"tables/{table.name}.parquet",
                    "grain": catalogue.grain,
                    "name": table.name,
                    "provenance_class": catalogue.manifest_class,
                    "row_count": len(table.rows),
                    "schema_sha256": schema_hash(table.columns),
                    "sha256": _file_sha256(path),
                }
            )
        document: dict[str, object] = {
            "artefacts": list(artefacts),
            "build_id": scalars["build_id"],
            "built_at": scalars["built_at"],
            "code_version": scalars["code_version"],
            "engine_versions": scalars["engine_versions"],
            "release_contract_version": scalars["release_contract_version"],
            "release_kind": "public_only",
            "rules_version_id": scalars["rules_version_id"],
            "sources": list(sources),
            "tables": entries,
        }
        if listed_inputs:
            document["listed_inputs"] = list(listed_inputs)
        document["release_id"] = release_hash(document)
        manifest_path = destination / "manifest.json"
        manifest_path.write_bytes(canonical_json(document).encode("utf-8"))
        created.append(manifest_path)
    except WriterRefusal:
        _remove(created)
        raise
    except Exception:
        _remove(created)
        raise
    release_id = document["release_id"]
    if type(release_id) is not str:
        raise WriterRefusal("unknown_table")
    return release_id


def _refuse_scalars(scalars: Mapping[str, object]) -> None:
    for key in scalars:
        if key in FORBIDDEN_PUBLIC_ONLY:
            raise WriterRefusal("forbidden_manifest_field")
    kind = scalars.get("release_kind", "public_only")
    if kind != "public_only":
        raise WriterRefusal("release_kind_unsupported")
    required = (
        "build_id",
        "built_at",
        "code_version",
        "engine_versions",
        "release_contract_version",
        "rules_version_id",
    )
    for key in required:
        if key not in scalars:
            raise WriterRefusal("column_mismatch")
    reason = engine_versions_reason(scalars.get("engine_versions"))
    if reason is not None:
        raise WriterRefusal(reason)


def _refuse_chain(
    sources: Sequence[Mapping[str, object]],
    tables: Sequence[TableWrite],
) -> None:
    """The source chain is refused before any release file is written."""
    try:
        require_public_chain(
            sources,
            tuple(ChainTable(table.name, table.rows) for table in tables),
        )
    except SourceChainRefusal as fault:
        raise WriterRefusal(fault.reason) from None


def _refuse_table(table: TableWrite) -> None:
    catalogue = by_name(table.name)
    if catalogue is None:
        raise WriterRefusal("unknown_table")
    if catalogue.manifest_class in {"protected", "simulated"}:
        raise WriterRefusal("forbidden_table_class")
    if written_by_privacy(catalogue):
        raise WriterRefusal("privacy_written_table")
    expected = [column.name for column in table.columns]
    if len(expected) != len(set(expected)):
        raise WriterRefusal("column_mismatch")
    for column in table.columns:
        if column.logical_type == "geometry" and (
            column.srid != _SRID or not column.geometry_type
        ):
            raise WriterRefusal("geometry_srid_invalid")
    for row in table.rows:
        if set(row) != set(expected):
            raise WriterRefusal("column_mismatch")
        for column in table.columns:
            value = row[column.name]
            if value is None and not column.nullable:
                raise WriterRefusal("null_not_allowed")
            if column.logical_type == "geometry" and value is not None:
                if type(value) is not bytes or _embedded_srid(value) not in {
                    None,
                    _SRID,
                }:
                    raise WriterRefusal("geometry_srid_invalid")


def _embedded_srid(value: bytes) -> int | None:
    if len(value) < 9:
        return None
    order = value[0]
    if order == 1:
        kind = int.from_bytes(value[1:5], "little")
        if kind & _EWKB_FLAG:
            return int.from_bytes(value[5:9], "little")
        return None
    if order == 0:
        kind = int.from_bytes(value[1:5], "big")
        if kind & _EWKB_FLAG:
            return int.from_bytes(value[5:9], "big")
    return None


def _write_parquet(path: Path, table: TableWrite, schema_text: str) -> None:
    import duckdb

    connection = duckdb.connect()
    try:
        quoted = _quote(table.name)
        definitions = ", ".join(
            f"{_quote(column.name)} {_duck_type(column)}" for column in table.columns
        )
        connection.execute(f"CREATE TABLE {quoted} ({definitions})")
        if table.rows:
            holders = ", ".join(
                "CAST(? AS GEOMETRY)" if column.logical_type == "geometry" else "?"
                for column in table.columns
            )
            insert = f"INSERT INTO {quoted} VALUES ({holders})"
            for row in table.rows:
                connection.execute(
                    insert,
                    [row[column.name] for column in table.columns],
                )
        statement = (
            f"COPY {quoted} TO {_sql_literal(str(path))} "
            f"(FORMAT PARQUET, KV_METADATA {{{_SCHEMA_KEY}: {_sql_literal(schema_text)}}})"
        )
        connection.execute(statement)
    finally:
        connection.close()


def _duck_type(column: ColumnSpec) -> str:
    logical = column.logical_type
    if logical in {"string", "month"}:
        return "VARCHAR"
    if logical in {"int", "cell"}:
        return "BIGINT"
    if logical.startswith("decimal("):
        return logical.upper()
    if logical == "bool":
        return "BOOLEAN"
    if logical == "date":
        return "DATE"
    if logical == "timestamp":
        return "TIMESTAMPTZ"
    if logical == "geometry":
        return "GEOMETRY"
    raise WriterRefusal("column_mismatch")


def _quote(name: str) -> str:
    if _IDENT.fullmatch(name) is None:
        raise WriterRefusal("unknown_table")
    return '"' + name + '"'


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _remove(created: list[Path]) -> None:
    for path in reversed(created):
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
