"""Load one public release into PostgreSQL and the embedded reader."""

from __future__ import annotations

import os
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from eii_core.manifest import ColumnSpec, by_name
from eii_product.store.postgres import release_schema
from eii_product.store.receipt import write_receipt
from eii_product.store.release_check import (
    RELEASE_MANIFEST_COLUMNS,
    RELEASE_MANIFEST_KEY,
    CheckedRelease,
    ReleaseRefusal,
    check_release,
    digest_rows,
    manifest_rows,
)

_PLAIN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_POSTGIS_SCHEMA_SQL = (
    "SELECT n.nspname FROM pg_catalog.pg_extension AS e "
    "JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace "
    "WHERE e.extname = 'postgis'"
)
_ROLE_SQL = (
    "SELECT CURRENT_USER, r.rolsuper FROM pg_catalog.pg_roles AS r "
    "WHERE r.rolname = CURRENT_USER"
)
_EXTENSIONS_SQL = (
    "SELECT e.extname FROM pg_catalog.pg_extension AS e ORDER BY e.extname"
)
_SCHEMA_EXISTS_SQL = "SELECT nspname FROM pg_catalog.pg_namespace WHERE nspname = %s"
ALLOWED_EXTENSIONS = frozenset({"plpgsql", "postgis"})
PARTIAL_READER = "release.duckdb.partial"
READER_NAME = "release.duckdb"
_EXIT = {
    "engine_operation_failed": 1,
    "extension_not_allowed": 1,
    "extension_schema_invalid": 1,
    "owner_role_unavailable": 3,
    "postgres_not_answering": 3,
    "schema_exists": 1,
    "store_verification_failed": 4,
}


class PostgresNotAnswering(Exception):
    """The server did not answer. The message is never driver text."""


class OwnerConnectFailed(Exception):
    """The server answered and the owner role could not connect."""


class LoadRefusal(Exception):
    """A fixed loader reason and its ruled exit code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        """Refuse a reason outside the loader's closed list."""
        if reason not in _EXIT:
            message = "refusal reason invalid"
            raise ValueError(message)
        self.reason = reason
        self.exit_code = _EXIT[reason]
        self.detail = detail
        super().__init__(reason)


def owner_connect_kwargs(host: str, port: int, database: str) -> dict[str, object]:
    """Connection arguments for eii_owner. The password is never one of them."""
    return {"dbname": database, "host": host, "port": port, "user": "eii_owner"}


def run_load(
    folder: Path,
    *,
    host: str,
    port: int,
    database: str,
    connect: Callable[..., object],
) -> int:
    """Load or refuse. Print one FAIL line. Return the exit code."""
    try:
        perform(folder, host=host, port=port, database=database, connect=connect)
    except ReleaseRefusal as refusal:
        _report(refusal.reason, refusal.detail)
        return refusal.exit_code
    except LoadRefusal as refusal:
        _report(refusal.reason, refusal.detail)
        return refusal.exit_code
    return 0


def perform(
    folder: Path,
    *,
    host: str,
    port: int,
    database: str,
    connect: Callable[..., object],
) -> None:
    """Check the release, then load both stores. A failure leaves no receipt."""
    checked = check_release(folder)
    try:
        connection = connect(**owner_connect_kwargs(host, port, database))
    except Exception as exc:
        raise refusal_from_connect(exc) from None
    try:
        load_checked(connection, checked)
    finally:
        close = getattr(connection, "close", None)
        if close is not None:
            close()


def refusal_from_connect(exc: BaseException) -> LoadRefusal:
    """Map a connect failure onto a fixed reason. Driver text is dropped."""
    if type(exc) is PostgresNotAnswering:
        return LoadRefusal("postgres_not_answering")
    if type(exc) is OwnerConnectFailed:
        return LoadRefusal("owner_role_unavailable")
    return LoadRefusal("engine_operation_failed")


def require_owner(role: object, superuser: object) -> None:
    """The current role must be eii_owner and must not be a superuser."""
    if role != "eii_owner" or superuser is not False:
        raise LoadRefusal("owner_role_unavailable")


def require_extensions(names: Sequence[object]) -> None:
    """Refuse any extension other than PostGIS and plpgsql."""
    for name in names:
        if name not in ALLOWED_EXTENSIONS:
            raise LoadRefusal("extension_not_allowed")


def require_plain_identifier(name: object) -> str:
    """Refuse a schema name that is not a plain identifier, before any statement."""
    if type(name) is not str or _PLAIN.fullmatch(name) is None:
        raise LoadRefusal("extension_schema_invalid")
    return name


def refuse_existing_schema(exists: bool) -> None:
    """An existing final schema is left alone."""
    if exists:
        raise LoadRefusal("schema_exists")


def staging_schema(identity: str) -> str:
    """The loading schema is the release schema plus one suffix, formed once."""
    return release_schema(identity) + "__loading"


def verify_staged(
    embedded: Mapping[str, Sequence[Mapping[str, object]]],
    postgres: Mapping[str, Sequence[Mapping[str, object]]],
    checked: CheckedRelease,
    geometry_srids: Mapping[str, Sequence[object]] | None = None,
) -> None:
    """Counts, digests and the release identity must agree. SRID must be 4326."""
    document = checked.document
    tables = document["tables"]
    if type(tables) is not list:
        raise LoadRefusal("store_verification_failed")
    names = [entry["name"] for entry in tables if type(entry) is dict]
    counts = {
        entry["name"]: entry["row_count"] for entry in tables if type(entry) is dict
    }
    for name in (*names, "release_manifest"):
        left = embedded.get(name)
        right = postgres.get(name)
        if left is None or right is None or len(left) != len(right):
            raise LoadRefusal("store_verification_failed")
        if name == "release_manifest":
            columns: Sequence[ColumnSpec] = RELEASE_MANIFEST_COLUMNS
            key: Sequence[str] = RELEASE_MANIFEST_KEY
            expected = len(names)
        else:
            columns = checked.schemas[name]
            catalogue = by_name(name)
            key = () if catalogue is None else catalogue.key
            expected = counts[name]
        if len(left) != expected:
            raise LoadRefusal("store_verification_failed")
        if digest_rows(left, columns, key) != digest_rows(right, columns, key):
            raise LoadRefusal("store_verification_failed")
    identity = document["release_id"]
    for side in (embedded["release_manifest"], postgres["release_manifest"]):
        for row in side:
            if row.get("release_id") != identity:
                raise LoadRefusal("store_verification_failed")
    if geometry_srids is None:
        return
    for srids in geometry_srids.values():
        for srid in srids:
            if srid != 4326:
                raise LoadRefusal("store_verification_failed")


def geometry_alter(schema: str, postgis_schema: str, table: str, column: str) -> str:
    """Turn copied WKB into geometry(Geometry,4326) in the extension's schema."""
    require_plain_identifier(schema)
    require_plain_identifier(postgis_schema)
    require_plain_identifier(table)
    require_plain_identifier(column)
    return (
        f'ALTER TABLE "{schema}"."{table}" ALTER COLUMN "{column}" '
        f'TYPE geometry(Geometry,4326) USING "{postgis_schema}".ST_GeomFromWKB("{column}", 4326)'
    )


def build_reader(checked: CheckedRelease, target: Path) -> None:
    """Build the embedded reader from the release Parquet files."""
    _stage_embedded(checked, target)


def load_checked(connection: object, checked: CheckedRelease) -> None:
    """Stage, verify, rename, then write the receipt. Failure removes the stage."""
    role_row = _one(_execute(connection, _ROLE_SQL))
    require_owner(role_row[0], role_row[1])
    require_extensions([row[0] for row in _execute(connection, _EXTENSIONS_SQL)])
    postgis_schema = require_plain_identifier(
        _one(_execute(connection, _POSTGIS_SCHEMA_SQL))[0]
    )
    identity = str(checked.document["release_id"])
    final = release_schema(identity)
    staging = staging_schema(identity)
    refuse_existing_schema(_schema_present(connection, final))
    if _schema_present(connection, staging):
        _execute(connection, f'DROP SCHEMA "{staging}" CASCADE')
    partial = checked.folder / PARTIAL_READER
    renamed = False
    started = time.monotonic()
    try:
        _execute(connection, "BEGIN")
        _stage_postgres(connection, checked, staging, postgis_schema)
        embedded_rows = _stage_embedded(checked, partial)
        postgres_rows = _read_postgres(connection, checked, staging, postgis_schema)
        verify_staged(
            embedded_rows,
            postgres_rows,
            checked,
            _geometry_srids(connection, checked, staging, postgis_schema),
        )
        _execute(connection, f'ALTER SCHEMA "{staging}" RENAME TO "{final}"')
        _execute(connection, f'GRANT USAGE ON SCHEMA "{final}" TO eii_app')
        _execute(
            connection, f'GRANT SELECT ON ALL TABLES IN SCHEMA "{final}" TO eii_app'
        )
        _execute(connection, "COMMIT")
        renamed = True
        os.replace(partial, checked.folder / READER_NAME)
        elapsed = max(0, int((time.monotonic() - started) * 1000))
        write_receipt(
            checked.folder,
            identity,
            {name: rows for name, rows in postgres_rows.items()},
            {
                name: digest_rows(rows, _columns(checked, name), _key(name))
                for name, rows in postgres_rows.items()
            },
            {"embedded": elapsed, "postgres": elapsed},
        )
    except (LoadRefusal, ReleaseRefusal, KeyboardInterrupt, SystemExit):
        _abandon(
            connection,
            staging,
            final if renamed else None,
            partial,
            checked.folder / READER_NAME,
        )
        raise
    except BaseException:
        _abandon(
            connection,
            staging,
            final if renamed else None,
            partial,
            checked.folder / READER_NAME,
        )
        raise LoadRefusal("engine_operation_failed") from None


def _stage_postgres(
    connection: object,
    checked: CheckedRelease,
    staging: str,
    postgis_schema: str,
) -> dict[str, tuple[Mapping[str, object], ...]]:
    _execute(connection, f'CREATE SCHEMA "{staging}"')
    stored: dict[str, tuple[Mapping[str, object], ...]] = {}
    tables = checked.document["tables"]
    if type(tables) is not list:
        raise LoadRefusal("store_verification_failed")
    for entry in tables:
        if type(entry) is not dict:
            raise LoadRefusal("store_verification_failed")
        name = str(entry["name"])
        columns = checked.schemas[name]
        _execute(connection, _create_table(staging, name, columns))
        rows = _parquet_rows(checked.folder / str(entry["file"]), columns)
        _copy(connection, _copy_sql(staging, name, columns), rows, columns)
        for column in columns:
            if column.logical_type == "geometry":
                _execute(
                    connection,
                    geometry_alter(staging, postgis_schema, name, column.name),
                )
        stored[name] = rows
    manifest = manifest_rows(checked.document)
    _execute(
        connection, _create_table(staging, "release_manifest", RELEASE_MANIFEST_COLUMNS)
    )
    _copy(
        connection,
        _copy_sql(staging, "release_manifest", RELEASE_MANIFEST_COLUMNS),
        manifest,
        RELEASE_MANIFEST_COLUMNS,
    )
    stored["release_manifest"] = manifest
    return stored


def _stage_embedded(
    checked: CheckedRelease,
    partial: Path,
) -> dict[str, tuple[Mapping[str, object], ...]]:
    import duckdb

    if partial.exists():
        partial.unlink()
    connection = duckdb.connect(str(partial))
    try:
        tables = checked.document["tables"]
        if type(tables) is not list:
            raise LoadRefusal("store_verification_failed")
        for entry in tables:
            if type(entry) is not dict:
                raise LoadRefusal("store_verification_failed")
            name = str(entry["name"])
            source = checked.folder / str(entry["file"])
            connection.execute(
                f'CREATE TABLE "{name}" AS SELECT * FROM read_parquet({_sql_literal(source)})'
            )
        _create_manifest_table(connection)
        for row in manifest_rows(checked.document):
            connection.execute(
                "INSERT INTO release_manifest VALUES ("
                + ", ".join("?" for _ in row)
                + ")",
                [row[column.name] for column in RELEASE_MANIFEST_COLUMNS],
            )
    finally:
        connection.close()
    return _read_embedded(partial, checked)


def _read_embedded(
    path: Path,
    checked: CheckedRelease,
) -> dict[str, tuple[Mapping[str, object], ...]]:
    import duckdb

    connection = duckdb.connect(str(path), read_only=True)
    try:
        stored: dict[str, tuple[Mapping[str, object], ...]] = {}
        for name, columns in checked.schemas.items():
            stored[name] = _fetch(connection, name, columns, geometry_hex=True)
        stored["release_manifest"] = _fetch(
            connection, "release_manifest", RELEASE_MANIFEST_COLUMNS, geometry_hex=False
        )
        return stored
    finally:
        connection.close()


def _fetch(
    connection: object,
    table: str,
    columns: Sequence[ColumnSpec],
    *,
    geometry_hex: bool,
) -> tuple[Mapping[str, object], ...]:
    pieces: list[str] = []
    for column in columns:
        if geometry_hex and column.logical_type == "geometry":
            pieces.append(f'hex(ST_AsWKB("{column.name}")) AS "{column.name}"')
        else:
            pieces.append(f'"{column.name}"')
    rows = _duck_fetch(connection, f'SELECT {", ".join(pieces)} FROM "{table}"')
    return _as_dicts(rows, columns)


def _parquet_rows(
    path: Path, columns: Sequence[ColumnSpec]
) -> tuple[dict[str, object], ...]:
    import duckdb

    connection = duckdb.connect()
    try:
        pieces: list[str] = []
        for column in columns:
            if column.logical_type == "geometry":
                pieces.append(f'ST_AsWKB("{column.name}") AS "{column.name}"')
            else:
                pieces.append(f'"{column.name}"')
        fetched = connection.execute(
            f"SELECT {', '.join(pieces)} FROM read_parquet({_sql_literal(path)})"
        ).fetchall()
    finally:
        connection.close()
    return _as_dicts(fetched, columns)


def _read_postgres(
    connection: object,
    checked: CheckedRelease,
    staging: str,
    postgis_schema: str,
) -> dict[str, tuple[Mapping[str, object], ...]]:
    stored: dict[str, tuple[Mapping[str, object], ...]] = {}
    for name, columns in checked.schemas.items():
        stored[name] = _as_dicts(
            _execute(connection, _select_sql(staging, name, columns, postgis_schema)),
            columns,
        )
    stored["release_manifest"] = _as_dicts(
        _execute(
            connection,
            _select_sql(
                staging, "release_manifest", RELEASE_MANIFEST_COLUMNS, postgis_schema
            ),
        ),
        RELEASE_MANIFEST_COLUMNS,
    )
    return stored


def _select_sql(
    schema: str,
    table: str,
    columns: Sequence[ColumnSpec],
    postgis_schema: str,
) -> str:
    pieces: list[str] = []
    for column in columns:
        if column.logical_type == "geometry":
            pieces.append(
                f"upper(encode(\"{postgis_schema}\".ST_AsBinary(\"{column.name}\", 'NDR'), 'hex')) "
                f'AS "{column.name}"'
            )
        else:
            pieces.append(f'"{column.name}"')
    return f'SELECT {", ".join(pieces)} FROM "{schema}"."{table}"'


def _geometry_srids(
    connection: object,
    checked: CheckedRelease,
    staging: str,
    postgis_schema: str,
) -> dict[str, tuple[object, ...]]:
    found: dict[str, tuple[object, ...]] = {}
    for name, columns in checked.schemas.items():
        for column in columns:
            if column.logical_type != "geometry":
                continue
            rows = _execute(
                connection,
                f'SELECT "{postgis_schema}".ST_SRID("{column.name}") FROM "{staging}"."{name}"',
            )
            found[name] = tuple(row[0] for row in rows)
    return found


def _abandon(
    connection: object,
    staging: str,
    final: str | None,
    partial: Path,
    reader: Path,
) -> None:
    try:
        _execute(connection, "ROLLBACK")
    except Exception:
        pass
    for name in (staging, final):
        if name is None:
            continue
        try:
            _execute(connection, f'DROP SCHEMA IF EXISTS "{name}" CASCADE')
        except Exception:
            pass
    try:
        _execute(connection, "COMMIT")
    except Exception:
        pass
    partial.unlink(missing_ok=True)
    if final is not None:
        reader.unlink(missing_ok=True)


def _schema_present(connection: object, name: str) -> bool:
    return len(_execute(connection, _SCHEMA_EXISTS_SQL, (name,))) > 0


def _create_table(schema: str, table: str, columns: Sequence[ColumnSpec]) -> str:
    parts = [
        f'"{column.name}" {_pg_type(column)} {"NULL" if column.nullable else "NOT NULL"}'
        for column in columns
    ]
    return f'CREATE TABLE "{schema}"."{table}" ({", ".join(parts)})'


def _copy_sql(schema: str, table: str, columns: Sequence[ColumnSpec]) -> str:
    names = ", ".join(f'"{column.name}"' for column in columns)
    return f'COPY "{schema}"."{table}" ({names}) FROM STDIN'


def _pg_type(column: ColumnSpec) -> str:
    logical = column.logical_type
    if logical in {"string", "month"}:
        return "text"
    if logical in {"int", "cell"}:
        return "bigint"
    if logical.startswith("decimal(") and logical.endswith(")"):
        return "numeric" + logical[len("decimal") :]
    if logical == "bool":
        return "boolean"
    if logical == "date":
        return "date"
    if logical == "timestamp":
        return "timestamptz"
    if logical == "geometry":
        return "bytea"
    raise LoadRefusal("engine_operation_failed")


def _create_manifest_table(connection: object) -> None:
    parts = [
        f'"{column.name}" {_duck_type(column)}' for column in RELEASE_MANIFEST_COLUMNS
    ]
    _duck_fetch(connection, f"CREATE TABLE release_manifest ({', '.join(parts)})")


def _duck_type(column: ColumnSpec) -> str:
    if column.logical_type == "int":
        return "BIGINT"
    return "VARCHAR"


def _as_dicts(
    rows: Sequence[Sequence[object]],
    columns: Sequence[ColumnSpec],
) -> tuple[dict[str, object], ...]:
    return tuple(
        {column.name: row[index] for index, column in enumerate(columns)}
        for row in rows
    )


def _columns(checked: CheckedRelease, name: str) -> Sequence[ColumnSpec]:
    if name == "release_manifest":
        return RELEASE_MANIFEST_COLUMNS
    return checked.schemas[name]


def _key(name: str) -> Sequence[str]:
    if name == "release_manifest":
        return RELEASE_MANIFEST_KEY
    catalogue = by_name(name)
    if catalogue is None:
        return ()
    return catalogue.key


def _execute(
    connection: object, sql: str, params: object = None
) -> list[tuple[object, ...]]:
    if getattr(connection, "stand_in", False):
        execute = getattr(connection, "execute", None)
        if not callable(execute):
            raise LoadRefusal("engine_operation_failed")
        result = execute(sql, params)
        return [] if result is None else [tuple(row) for row in result]
    cursor_fn = getattr(connection, "cursor", None)
    if not callable(cursor_fn):
        raise LoadRefusal("engine_operation_failed")
    cursor = cursor_fn()
    try:
        cursor.execute(sql, params)
        description = getattr(cursor, "description", None)
        if description is None:
            return []
        fetched = cursor.fetchall()
        return [tuple(row) for row in fetched]
    finally:
        cursor.close()


def _copy(
    connection: object,
    sql: str,
    rows: Sequence[Mapping[str, object]],
    columns: Sequence[ColumnSpec],
) -> None:
    values = [tuple(row[column.name] for column in columns) for row in rows]
    if getattr(connection, "stand_in", False):
        copy_rows = getattr(connection, "copy_rows", None)
        if not callable(copy_rows):
            raise LoadRefusal("engine_operation_failed")
        copy_rows(sql, values)
        return
    cursor_fn = getattr(connection, "cursor", None)
    if not callable(cursor_fn):
        raise LoadRefusal("engine_operation_failed")
    cursor = cursor_fn()
    try:
        with cursor.copy(sql) as copy:
            for value in values:
                copy.write_row(value)
    finally:
        cursor.close()


def _duck_fetch(
    connection: object, sql: str, params: object = None
) -> list[tuple[object, ...]]:
    execute = getattr(connection, "execute", None)
    if not callable(execute):
        raise LoadRefusal("engine_operation_failed")
    result = execute(sql) if params is None else execute(sql, params)
    fetchall = getattr(result, "fetchall", None)
    if not callable(fetchall):
        return []
    fetched = fetchall()
    return [tuple(row) for row in fetched]


def _one(rows: Sequence[Sequence[object]]) -> tuple[object, ...]:
    if len(rows) != 1:
        raise LoadRefusal("engine_operation_failed")
    return tuple(rows[0])


def _sql_literal(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _report(reason: str, detail: str) -> None:
    line = reason if detail == "" else f"{reason} {detail}"
    sys.stderr.write(f"FAIL load-release: {line}\n")
