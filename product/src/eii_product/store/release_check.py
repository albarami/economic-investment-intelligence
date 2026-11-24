"""Checks and the table digest. Nothing here opens a store."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from eii_core.manifest import ColumnSpec, canonical_json, release_hash
from eii_product.store.normalise import hold_geometry, normalise

EXIT_CODES: dict[str, int] = {
    "absolute_path": 4,
    "digest_mismatch": 4,
    "duplicate_key": 4,
    "duplicate_table": 4,
    "empty_table_list": 4,
    "forbidden_manifest_field": 4,
    "forbidden_table_class": 4,
    "manifest_key_case": 4,
    "manifest_type_invalid": 4,
    "path_outside_release": 4,
    "path_traversal": 4,
    "privacy_written_table": 4,
    "receipt_listed_as_artefact": 4,
    "release_incomplete": 4,
    "release_kind_unsupported": 1,
    "release_missing": 4,
    "source_link_incomplete": 4,
    "source_link_mismatch": 4,
    "source_link_missing": 4,
    "source_link_unknown": 4,
    "symbolic_link": 4,
    "table_class_invalid": 4,
    "unknown_manifest_key": 4,
    "unknown_table": 4,
    "unlisted_table": 4,
}
_SCHEMA_KEY = "eii_logical_schema"
RELEASE_MANIFEST_KEY = ("table_name",)
RELEASE_MANIFEST_COLUMNS = (
    ColumnSpec("release_id", "string", False),
    ColumnSpec("table_name", "string", False),
    ColumnSpec("provenance_class", "string", False),
    ColumnSpec("file", "string", False),
    ColumnSpec("sha256", "string", False),
    ColumnSpec("row_count", "int", False),
    ColumnSpec("schema_sha256", "string", False),
    ColumnSpec("release_kind", "string", False),
    ColumnSpec("release_contract_version", "string", False),
    ColumnSpec("build_id", "string", False),
    ColumnSpec("built_at", "string", False),
    ColumnSpec("code_version", "string", False),
    ColumnSpec("rules_version_id", "string", False),
    ColumnSpec("engine_versions", "string", False),
    ColumnSpec("fc_register_sha256", "string", True),
)


class _Fetched(Protocol):
    def fetchone(self) -> tuple[object, ...] | None: ...

    def fetchall(self) -> Sequence[tuple[object, ...]]: ...


class _Connection(Protocol):
    """One read connection shared by every file of a single release check."""

    def execute(self, query: str) -> _Fetched: ...

    def close(self) -> None: ...


class ReleaseRefusal(Exception):
    """A fixed reason found before either store is touched."""

    def __init__(self, reason: str, detail: str = "") -> None:
        """Refuse a reason outside the checker's closed list."""
        if reason not in EXIT_CODES:
            message = "refusal reason invalid"
            raise ValueError(message)
        self.reason = reason
        self.exit_code = EXIT_CODES[reason]
        self.detail = detail
        super().__init__(reason)


@dataclass(frozen=True)
class CheckedRelease:
    """A release folder whose manifest matches its files."""

    folder: Path
    document: dict[str, object]
    schemas: dict[str, tuple[ColumnSpec, ...]]


def check_release(folder: Path) -> CheckedRelease:
    """Recompute every hash from the files. Trust no manifest number."""
    manifest_path = folder / "manifest.json"
    if not folder.is_dir() or not manifest_path.is_file():
        raise ReleaseRefusal("release_missing")
    try:
        document = _loads(manifest_path.read_text(encoding="utf-8"))
    except ReleaseRefusal:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ReleaseRefusal("release_missing") from None
    if type(document) is not dict:
        raise ReleaseRefusal("release_missing")
    from eii_product.store import release_shape

    release_shape.refuse_document(document)
    tables = document["tables"]
    if type(tables) is not list:
        raise ReleaseRefusal("empty_table_list")
    listed = {
        entry["name"]
        for entry in tables
        if type(entry) is dict and type(entry.get("name")) is str
    }
    _refuse_unlisted(folder, listed)
    schemas: dict[str, tuple[ColumnSpec, ...]] = {}
    import duckdb

    connection = duckdb.connect()
    try:
        for entry in tables:
            if type(entry) is not dict:
                raise ReleaseRefusal("digest_mismatch")
            name = entry.get("name")
            if type(name) is not str:
                raise ReleaseRefusal("unknown_table")
            listed.add(name)
            schemas[name] = _check_table(folder, entry, name, connection)
        release_shape.require_source_chain(
            folder, document, schemas, connection=connection
        )
        _require_hash(release_hash(document), str(document.get("release_id", "")))
        return CheckedRelease(folder, document, schemas)
    finally:
        connection.close()


def refuse_document(document: Mapping[str, object]) -> None:
    """Apply the manifest rules that do not read a file."""
    from eii_product.store import release_shape

    release_shape.refuse_document(document)


def require_count(found: int, recorded: int) -> None:
    """Refuse a row count that is not the counted number."""
    if found != recorded:
        raise ReleaseRefusal("digest_mismatch")


def require_hash(found: str, recorded: str) -> None:
    """Refuse a hash that differs by any character."""
    _require_hash(found, recorded)


def digest_rows(
    rows: Sequence[Mapping[str, object]],
    columns: Sequence[ColumnSpec],
    key: Sequence[str],
) -> str:
    """SHA-256 of key-ordered rows. Geometry, bool and time are handled here."""
    prepared: list[dict[str, object]] = []
    for row in rows:
        prepared.append(
            {
                column.name: digest_value(row.get(column.name), column)
                for column in columns
            }
        )
    prepared.sort(key=lambda item: tuple(_sort_token(item[name]) for name in key))
    return hashlib.sha256(canonical_json(prepared).encode("utf-8")).hexdigest()


def digest_value(value: object, column: ColumnSpec) -> object:
    """One digest scalar. A time stamp keeps its time. Geometry is exact text."""
    if value is None:
        return None
    if column.logical_type == "geometry":
        text = value.hex().upper() if type(value) is bytes else value
        held = hold_geometry(text)
        return "" if held is None else held
    if column.logical_type == "bool" or type(value) is bool:
        if type(value) is not bool:
            raise ReleaseRefusal("digest_mismatch")
        return value
    if column.logical_type == "timestamp" or type(value) is datetime:
        if type(value) is not datetime:
            raise ReleaseRefusal("digest_mismatch")
        return value.isoformat()
    normalised = normalise(value)
    if type(normalised) is Decimal:
        return format(normalised, "f")
    if type(normalised) is date:
        return normalised.isoformat()
    return normalised


def manifest_rows(document: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    """One release_manifest row per verified table. engine_versions is canonical text.

    ``fc_register_sha256`` repeats the hash the release lists for the register
    file, or is null when the release lists none (L-1509).
    """
    engines = canonical_json(document["engine_versions"])
    fc_register = _listed_sha256(document, "fc_register")
    rows: list[dict[str, object]] = []
    tables = document["tables"]
    if type(tables) is not list:
        return ()
    for entry in tables:
        if type(entry) is not dict:
            continue
        rows.append(
            {
                "build_id": document["build_id"],
                "built_at": document["built_at"],
                "code_version": document["code_version"],
                "engine_versions": engines,
                "fc_register_sha256": fc_register,
                "file": entry["file"],
                "provenance_class": entry["provenance_class"],
                "release_contract_version": document["release_contract_version"],
                "release_id": document["release_id"],
                "release_kind": document["release_kind"],
                "row_count": entry["row_count"],
                "rules_version_id": document["rules_version_id"],
                "schema_sha256": entry["schema_sha256"],
                "sha256": entry["sha256"],
                "table_name": entry["name"],
            }
        )
    return tuple(rows)


def _listed_sha256(document: Mapping[str, object], name: str) -> object:
    listed = document.get("listed_inputs", [])
    if type(listed) is not list:
        return None
    for item in listed:
        if type(item) is dict and item.get("name") == name:
            return item.get("sha256")
    return None


def _loads(payload: str) -> object:
    """Decode one JSON document. A repeated key at any depth is refused."""

    def pairs(items: list[tuple[object, object]]) -> dict[str, object]:
        found: dict[str, object] = {}
        for key, value in items:
            if type(key) is not str or key in found:
                raise ReleaseRefusal("duplicate_key")
            found[key] = value
        return found

    return json.loads(payload, object_pairs_hook=pairs)


def _check_table(
    folder: Path, entry: Mapping[str, object], name: str, connection: _Connection
) -> tuple[ColumnSpec, ...]:
    from eii_product.store import release_shape

    path = release_shape.table_path(folder, entry.get("file"), name)
    _require_hash(_sha256(path.read_bytes()), str(entry.get("sha256", "")))
    require_count(_parquet_count(path, connection), _as_int(entry.get("row_count")))
    schema_bytes = _schema_bytes(path, connection)
    if schema_bytes is None:
        raise ReleaseRefusal("digest_mismatch")
    _require_hash(_sha256(schema_bytes), str(entry.get("schema_sha256", "")))
    return _parse_schema(schema_bytes)


def _refuse_unlisted(folder: Path, listed: set[str]) -> None:
    table_dir = folder / "tables"
    if not table_dir.is_dir():
        raise ReleaseRefusal("release_incomplete")
    for path in sorted(table_dir.glob("*.parquet")):
        if path.stem not in listed:
            raise ReleaseRefusal("unlisted_table", path.stem)


def _require_hash(found: str, recorded: str) -> None:
    if found != recorded:
        raise ReleaseRefusal("digest_mismatch")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _as_int(value: object) -> int:
    if type(value) is not int:
        raise ReleaseRefusal("digest_mismatch")
    return value


def _parquet_count(path: Path, connection: _Connection) -> int:
    row = connection.execute(
        f"SELECT count(*) FROM read_parquet({_literal(path)})"
    ).fetchone()
    if row is None or type(row[0]) is bool or not isinstance(row[0], int):
        raise ReleaseRefusal("digest_mismatch")
    return int(row[0])


def _schema_bytes(path: Path, connection: _Connection) -> bytes | None:
    rows = connection.execute(
        "SELECT value FROM parquet_kv_metadata("
        f"{_literal(path)}) WHERE key = '{_SCHEMA_KEY}'"
    ).fetchall()
    if len(rows) != 1:
        return None
    value = rows[0][0]
    if type(value) is str:
        return value.encode("utf-8")
    if type(value) is not bytes:
        return None
    return value


def _parse_schema(payload: bytes) -> tuple[ColumnSpec, ...]:
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise ReleaseRefusal("digest_mismatch") from None
    if type(parsed) is not list:
        raise ReleaseRefusal("digest_mismatch")
    columns: list[ColumnSpec] = []
    for item in parsed:
        if type(item) is not dict:
            raise ReleaseRefusal("digest_mismatch")
        name = item.get("name")
        logical = item.get("logical_type")
        nullable = item.get("nullable")
        if (
            type(name) is not str
            or type(logical) is not str
            or type(nullable) is not bool
        ):
            raise ReleaseRefusal("digest_mismatch")
        if logical == "geometry":
            geometry_type = item.get("geometry_type")
            srid = item.get("srid")
            if type(geometry_type) is not str or type(srid) is not int:
                raise ReleaseRefusal("digest_mismatch")
            columns.append(ColumnSpec(name, logical, nullable, geometry_type, srid))
        else:
            columns.append(ColumnSpec(name, logical, nullable))
    return tuple(columns)


def _literal(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _sort_token(value: object) -> tuple[int, str, str]:
    if value is None:
        return (0, "", "")
    return (1, type(value).__name__, str(value))
