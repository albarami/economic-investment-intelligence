"""Live public release load. The lead runs it; tests call it with a stand-in."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from eii_product.store.postgres import release_schema

if TYPE_CHECKING:
    from preflight_database import DbTarget
from eii_core.manifest import ColumnSpec
from eii_core.reasons import reason
from eii_product.store.protocol import StoreHealth, StoreRefusal, require_identity
from eii_product.store.release_check import CheckedRelease

PROOF_PREFIX = "invented_r_"
PASS_LINE = "PASS public-release-load: both stores match"
PING_TIMEOUT_S = 1.0
INTEGER_TYPES = frozenset({"int", "cell"})
_TABLES_SQL = (
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = %s AND table_type = 'BASE TABLE'"
)
_EMBEDDED_TABLES_SQL = (
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'main' AND table_type = 'BASE TABLE'"
)


class _Stop(Exception):
    """A live-command refusal. Exit 1, or 3 when it is a detected divergence."""

    def __init__(self, reason: str, code: int = 1) -> None:
        self.reason = reason
        self.code = code
        super().__init__(reason)


class _ParserRefusal(Exception):
    """A refusal printed as the parser's own fixed reason."""


class _OpenStore(Protocol):
    """An adapter opened on a loaded store. It answers and carries an identity."""

    release_id: str

    def ping(self, timeout_s: float) -> StoreHealth:
        """Require the store to answer."""


def main(
    args: Sequence[str],
    environ: Mapping[str, str],
    *,
    connect: Callable[..., object] | None = None,
    before_check: Callable[[str, Path], None] | None = None,
) -> int:
    """Exit 0 on a full pass, 3 on a detected divergence, 2 on usage, 1 otherwise."""
    if list(args) not in ([], ["--diverge"]):
        print(
            "FAIL public-release-load: usage: live_public_release_load.py [--diverge]"
        )
        return 2
    try:
        evidence = _run(
            environ,
            diverge=list(args) == ["--diverge"],
            connect=connect,
            before_check=before_check,
        )
    except _Stop as error:
        print(f"FAIL public-release-load: {error.reason}")
        return error.code
    except _ParserRefusal as error:
        print(f"FAIL public-release-load: {reason(error)}")
        return 1
    except StoreRefusal as error:
        print(f"FAIL public-release-load: {reason(error)}")
        return 1
    except Exception as error:
        print("FAIL public-release-load: " + reason(error))
        return 1
    print(PASS_LINE)
    print(json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    return 0


def proof_database(release_id: str) -> str:
    """Name the proof database from the fixture release identity, in one place."""
    require_identity(release_id)
    return PROOF_PREFIX + release_id[:16]


def drop_names(release_id: str) -> tuple[str, str, str]:
    """The only names removal may drop: the proof database and the two schemas."""
    schema = release_schema(release_id)
    return (proof_database(release_id), schema, schema + "__loading")


def classify_divergence(baseline_ok: bool, detected: bool) -> int:
    """Exit 3 only when a passing baseline then sees the planted difference."""
    if baseline_ok and detected:
        return 3
    return 1


def require_same_identity(left: object, right: object, expected: object) -> None:
    """Both stores must hold the manifest's release identity."""
    if left != expected or right != expected:
        raise _Stop("store_verification_failed")


def require_parity(left: str, right: str, count: int, expected_count: int) -> None:
    """Counts and digests of one public table must agree."""
    if left != right or count != expected_count:
        raise _Stop("store_verification_failed")


def require_receipt(
    state: object, release_id: object, expected: str, artefact: bool
) -> None:
    """The receipt is complete, matches, and is not a manifest artefact."""
    if artefact or state != "complete" or release_id != expected:
        raise _Stop("receipt_not_complete")


def require_srids(srids: Sequence[object]) -> None:
    """Every loaded geometry must be SRID 4326."""
    for srid in srids:
        if srid != 4326:
            raise _Stop("store_verification_failed")


def require_unlisted_refused(code: int, reason: str) -> None:
    """An extra table is refused and the first load's schemas were already dropped."""
    if code == 0 or "unlisted_table" not in reason:
        raise _Stop("unlisted_table")


def load_arguments(host: str, port: int, database: str) -> dict[str, object]:
    """Arguments for the owner load. The URL's user and password are not here."""
    return {"database": database, "host": host, "port": port}


def _run(
    environ: Mapping[str, str],
    *,
    diverge: bool,
    connect: Callable[..., object] | None,
    before_check: Callable[[str, Path], None] | None,
) -> dict[str, object]:
    target = _target(environ)
    folder = Path(tempfile.mkdtemp(prefix="invented-release-"))
    created = False
    setup: object | None = None
    reader: object | None = None
    release_id = ""
    try:
        import public_release_fixture as fixture

        release_id = fixture.build_fixture(folder)
        database = proof_database(release_id)
        setup = _open(target, connect, target.database)
        if _exists(setup, "pg_database", "datname", database):
            raise _Stop("proof database exists")
        if not _exists(setup, "pg_roles", "rolname", "eii_owner"):
            raise _Stop("owner_role_unavailable")
        _statement(
            setup, f'CREATE DATABASE "{database}" TEMPLATE template0 OWNER eii_owner'
        )
        created = True
        proof = _open(target, connect, database)
        try:
            _statement(proof, "CREATE EXTENSION postgis")
        finally:
            _close(proof)
        from eii_product.store.loader import perform

        owner = _owner_connect()
        perform(
            folder,
            host=target.host,
            port=target.port,
            database=database,
            connect=owner,
        )
        reader = _open(target, connect, database)
        # Unlisted loading drops the schema, so the postgres side of a divergence
        # is the loader's read of that schema, taken while it is still loaded.
        staged: _Staged | None = None
        if diverge:
            staged = _staged_postgres(folder, release_id, reader)
        evidence = _loaded_checks(
            folder,
            release_id,
            reader,
            database,
            target.host,
            target.port,
            owner,
            before_check,
        )
        if diverge:
            _diverge(folder, release_id, staged, before_check)
        return evidence
    finally:
        if reader is not None:
            _close(reader)
        cleanup_failed = False
        if created and setup is not None and release_id != "":
            try:
                _remove(setup, release_id)
            except Exception:
                cleanup_failed = True
        if setup is not None:
            _close(setup)
        shutil.rmtree(folder, ignore_errors=True)
        if cleanup_failed:
            raise _Stop("proof database cleanup failed")


def _loaded_checks(
    folder: Path,
    release_id: str,
    connection: object,
    database: str,
    host: str,
    port: int,
    owner: Callable[..., object],
    before_check: Callable[[str, Path], None] | None,
) -> dict[str, object]:
    from eii_product.store.release_check import check_release

    checked = check_release(folder)
    schema = release_schema(release_id)
    postgis = _postgis_schema(connection)
    ran = 0
    _before(before_check, "manifest_only_load_both_stores", folder)
    manifest_only_load_both_stores(connection, checked, schema, folder)
    ran += 1
    _before(before_check, "public_tables_parity", folder)
    compared = public_tables_parity(connection, checked, schema, postgis, folder)
    ran += 1
    _before(before_check, "receipt_complete_not_artefact", folder)
    receipt_complete_not_artefact(folder, release_id)
    ran += 1
    _before(before_check, "same_release_identity", folder)
    same_release_identity(connection, checked, schema, postgis, folder, release_id)
    ran += 1
    _before(before_check, "loaded_geometry_has_srid_4326", folder)
    loaded_geometry_has_srid_4326(connection, checked, schema, postgis)
    ran += 1
    _before(before_check, "configured_preflight_passes", folder)
    configured_preflight_passes(folder)
    ran += 1
    _before(before_check, "unlisted_table_loads_nowhere", folder)
    unlisted_table_loads_nowhere(
        folder, release_id, connection, database, host, port, owner
    )
    ran += 1
    return {
        "checks_run": ran,
        "digests_identical": True,
        "tables_compared": compared,
        "tables_loaded": len(checked.schemas) + 1,
    }


def _before(
    before_check: Callable[[str, Path], None] | None, name: str, folder: Path
) -> None:
    if before_check is not None:
        before_check(name, folder)


def manifest_only_load_both_stores(
    connection: object, checked: CheckedRelease, schema: str, folder: Path
) -> None:
    """Each store holds the manifest tables and release_manifest, and no other."""
    expected = set(checked.schemas) | {"release_manifest"}
    if _postgres_tables(connection, schema) != expected:
        raise _Stop("manifest_tables_mismatch")
    if _embedded_tables(folder / "release.duckdb") != expected:
        raise _Stop("manifest_tables_mismatch")


def public_tables_parity(
    connection: object,
    checked: CheckedRelease,
    schema: str,
    postgis: str,
    folder: Path,
) -> int:
    """Public tables, every district column, and the null grid-cell key agree."""
    from eii_core.manifest import CATALOGUE, by_name
    from eii_product.store.loader import _read_embedded, _read_postgres

    embedded = _read_embedded(folder / "release.duckdb", checked)
    postgres = _read_postgres(connection, checked, schema, postgis)
    compared = 0
    for table in CATALOGUE:
        if table.manifest_class != "public":
            continue
        if table.name not in checked.schemas:
            raise _Stop("store_verification_failed")
        _same_table(table.name, embedded, postgres, checked, table.key)
        compared += 1
    for name in ("district", "grid_cell"):
        catalogue = by_name(name)
        key: Sequence[str] = () if catalogue is None else catalogue.key
        _same_table(name, embedded, postgres, checked, key)
        compared += 1
    _require_null_key(embedded.get("grid_cell", ()))
    _require_null_key(postgres.get("grid_cell", ()))
    return compared


def _same_table(
    name: str,
    embedded: Mapping[str, Sequence[Mapping[str, object]]],
    postgres: Mapping[str, Sequence[Mapping[str, object]]],
    checked: CheckedRelease,
    key: Sequence[str],
) -> None:
    from eii_product.store.release_check import digest_rows

    left = embedded.get(name)
    right = postgres.get(name)
    columns = checked.schemas[name]
    if left is None or right is None or len(left) != len(right):
        raise _Stop("store_verification_failed")
    if not _has_columns(left, columns) or not _has_columns(right, columns):
        raise _Stop("store_verification_failed")
    require_parity(
        digest_rows(left, columns, key),
        digest_rows(right, columns, key),
        len(left),
        len(right),
    )


def _has_columns(
    rows: Sequence[Mapping[str, object]], columns: Sequence[ColumnSpec]
) -> bool:
    names = {column.name for column in columns}
    return all(names <= set(row) for row in rows)


def _require_null_key(rows: Sequence[Mapping[str, object]]) -> None:
    if not any(row.get("district_key") is None for row in rows):
        raise _Stop("store_verification_failed")


def receipt_complete_not_artefact(folder: Path, release_id: str) -> None:
    """The receipt is complete, matches, and is not named as an artefact."""
    from eii_product.store.receipt import ReceiptRefusal, read_receipt

    document = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    artefacts: object = []
    if type(document) is dict:
        artefacts = document.get("artefacts", [])
    named = _receipt_named(artefacts)
    try:
        receipt = read_receipt(folder, release_id)
    except ReceiptRefusal as error:
        raise _Stop(reason(error)) from None
    require_receipt(receipt.get("state"), receipt.get("release_id"), release_id, named)


def _receipt_named(artefacts: object) -> bool:
    if type(artefacts) is not list:
        return False
    return any(
        type(item) is dict
        and Path(str(item.get("path", ""))).name == "load_receipt.json"
        for item in artefacts
    )


def same_release_identity(
    connection: object,
    checked: CheckedRelease,
    schema: str,
    postgis: str,
    folder: Path,
    release_id: str,
) -> None:
    """The manifest id is the id read from each store, and both adapters answer."""
    from eii_product.store.embedded import EmbeddedStore
    from eii_product.store.loader import _read_embedded, _read_postgres
    from eii_product.store.postgres import PostgresStore
    from eii_product.store.registry import load_inventory, packaged_sql_dir

    embedded = _read_embedded(folder / "release.duckdb", checked)
    postgres = _read_postgres(connection, checked, schema, postgis)
    require_same_identity(
        _one_release_id(embedded.get("release_manifest", ())),
        _one_release_id(postgres.get("release_manifest", ())),
        release_id,
    )
    # The adapters do not read the identity from the store. This half proves
    # only that both open and answer on the loaded stores under that identity.
    # The release_manifest read proves the identity.
    inventory = load_inventory(packaged_sql_dir())
    embedded_store = EmbeddedStore(folder / "release.duckdb", release_id, inventory)
    try:
        _require_adapter(embedded_store, release_id)
    finally:
        embedded_store.close()
    _require_adapter(PostgresStore(connection, release_id, inventory), release_id)


def _one_release_id(rows: Sequence[Mapping[str, object]]) -> object:
    found = {row.get("release_id") for row in rows}
    if len(found) != 1:
        return None
    return found.pop()


def _require_adapter(store: _OpenStore, release_id: str) -> None:
    health = store.ping(PING_TIMEOUT_S)
    if health.ok is not True or store.release_id != release_id:
        raise _Stop("store_verification_failed")


def loaded_geometry_has_srid_4326(
    connection: object, checked: CheckedRelease, schema: str, postgis: str
) -> None:
    """Every geometry of grid_cell and district in the loaded schema is 4326."""
    from eii_product.store.loader import _geometry_srids

    found = _geometry_srids(connection, checked, schema, postgis)
    for name in ("grid_cell", "district"):
        srids = found.get(name, ())
        if len(srids) == 0:
            raise _Stop("store_verification_failed")
        require_srids(srids)


def configured_preflight_passes(folder: Path) -> None:
    """The release, receipt and embedded-reader rows are PASS."""
    from preflight_rows import release_rows

    lines = release_rows({"EII_RELEASE_DIR": str(folder)})
    for name in ("release", "load-receipt", "embedded-reader"):
        if lines[name].severity != "PASS":
            raise _Stop("preflight_failed")


def unlisted_table_loads_nowhere(
    folder: Path,
    release_id: str,
    connection: object,
    database: str,
    host: str,
    port: int,
    owner: Callable[..., object],
) -> None:
    """An extra Parquet table is refused and leaves no schema, reader or receipt."""
    from eii_product.store.loader import PARTIAL_READER, READER_NAME, perform
    from eii_product.store.receipt import RECEIPT_NAME
    from eii_product.store.release_check import ReleaseRefusal

    copy_root = Path(tempfile.mkdtemp(prefix="invented-unlisted-"))
    try:
        copy_folder = copy_root / "release"
        shutil.copytree(folder, copy_folder)
        for name in (READER_NAME, PARTIAL_READER, RECEIPT_NAME):
            (copy_folder / name).unlink(missing_ok=True)
        tables = copy_folder / "tables"
        source = next(tables.glob("*.parquet"), None)
        if source is None:
            raise _Stop("unlisted_table")
        shutil.copyfile(source, tables / "invented_extra.parquet")
        _schema, staging = drop_names(release_id)[1:]
        for name in (staging, _schema):
            _statement(connection, f'DROP SCHEMA IF EXISTS "{name}" CASCADE')
        try:
            perform(
                copy_folder,
                host=host,
                port=port,
                database=database,
                connect=owner,
            )
        except ReleaseRefusal as refusal:
            require_unlisted_refused(refusal.exit_code, refusal.reason)
        else:
            raise _Stop("unlisted_table")
        for name in (READER_NAME, PARTIAL_READER, RECEIPT_NAME):
            if (copy_folder / name).exists():
                raise _Stop("unlisted_table")
        if _schema_named(connection, _schema) or _schema_named(connection, staging):
            raise _Stop("unlisted_table")
    finally:
        shutil.rmtree(copy_root, ignore_errors=True)


class _Staged:
    """Rows and geometry SRIDs read from the loaded PostgreSQL schema."""

    def __init__(
        self,
        rows: dict[str, tuple[Mapping[str, object], ...]],
        srids: dict[str, tuple[object, ...]],
    ) -> None:
        self.rows = rows
        self.srids = srids


def _staged_postgres(folder: Path, release_id: str, connection: object) -> _Staged:
    from eii_product.store.loader import _geometry_srids, _read_postgres
    from eii_product.store.release_check import check_release

    checked = check_release(folder)
    schema = release_schema(release_id)
    postgis = _postgis_schema(connection)
    return _Staged(
        _read_postgres(connection, checked, schema, postgis),
        _geometry_srids(connection, checked, schema, postgis),
    )


def _diverge(
    folder: Path,
    release_id: str,
    staged: _Staged | None,
    before_check: Callable[[str, Path], None] | None,
) -> None:
    """Change one manifest integer in a reader copy, then verify against PostgreSQL."""
    from eii_product.store.loader import LoadRefusal, _read_embedded, verify_staged
    from eii_product.store.release_check import check_release

    del release_id
    if staged is None:
        raise _Stop("divergence not detected")
    _before(before_check, "diverge", folder)
    checked = check_release(folder)
    chosen = _integer_target(checked)
    if chosen is None:
        raise _Stop("divergence not detected")
    table, column = chosen
    copy = folder / "release.duckdb.diverged"
    shutil.copyfile(folder / "release.duckdb", copy)
    try:
        changed = _change_one_integer(copy, table, column)
        refused = False
        if len(changed) == 1:
            try:
                verify_staged(
                    _read_embedded(copy, checked), staged.rows, checked, staged.srids
                )
            except LoadRefusal as refusal:
                refused = refusal.reason == "store_verification_failed"
        detected = len(changed) == 1 and refused
        if classify_divergence(True, detected) == 3:
            raise _Stop("store_verification_failed", 3)
        raise _Stop("divergence not detected")
    finally:
        copy.unlink(missing_ok=True)


def _integer_target(checked: CheckedRelease) -> tuple[str, str] | None:
    """The first public column whose manifest type is an integer."""
    from eii_core.manifest import CATALOGUE
    from eii_product.store.loader import LoadRefusal, require_plain_identifier

    for table in CATALOGUE:
        if table.manifest_class != "public":
            continue
        columns = checked.schemas.get(table.name)
        if columns is None:
            continue
        for column in columns:
            if column.logical_type not in INTEGER_TYPES:
                continue
            try:
                return (
                    require_plain_identifier(table.name),
                    require_plain_identifier(column.name),
                )
            except LoadRefusal:
                return None
    return None


def _change_one_integer(
    path: Path, table: str, column: str
) -> list[tuple[object, ...]]:
    import duckdb

    connection = duckdb.connect(str(path))
    try:
        statement = (
            f'UPDATE "{table}" SET "{column}" = "{column}" + 1 '
            f'WHERE rowid = (SELECT MIN(rowid) FROM "{table}" '
            f'WHERE "{column}" IS NOT NULL) RETURNING "{column}"'
        )
        return [tuple(row) for row in connection.execute(statement).fetchall()]
    finally:
        connection.close()


def _postgis_schema(connection: object) -> str:
    from eii_product.store.loader import (
        _POSTGIS_SCHEMA_SQL,
        _execute,
        require_plain_identifier,
    )

    return require_plain_identifier(_execute(connection, _POSTGIS_SCHEMA_SQL)[0][0])


def _postgres_tables(connection: object, schema: str) -> set[str]:
    from eii_product.store.loader import _execute

    rows = _execute(connection, _TABLES_SQL, (schema,))
    return {row[0] for row in rows if type(row[0]) is str}


def _embedded_tables(path: Path) -> set[str]:
    import duckdb

    connection = duckdb.connect(str(path), read_only=True)
    try:
        rows = connection.execute(_EMBEDDED_TABLES_SQL).fetchall()
    finally:
        connection.close()
    return {row[0] for row in rows if type(row[0]) is str}


def _schema_named(connection: object, name: str) -> bool:
    from eii_product.store.loader import _SCHEMA_EXISTS_SQL, _execute

    return len(_execute(connection, _SCHEMA_EXISTS_SQL, (name,))) > 0


def _target(environ: Mapping[str, str]) -> DbTarget:
    raw = environ.get("EII_DATABASE_URL", "")
    if raw == "":
        raise _ParserRefusal("database environment missing")
    scripts = str(Path(__file__).resolve().parents[1])
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from preflight_database import parse_database_url

    parsed = parse_database_url(raw)
    if not isinstance(parsed, str) and parsed.host != "127.0.0.1":
        raise _ParserRefusal("EII_DATABASE_URL host is not 127.0.0.1")
    if isinstance(parsed, str):
        raise _ParserRefusal(parsed)
    return parsed


def _open(
    target: DbTarget, connect: Callable[..., object] | None, database: str
) -> object:
    if connect is not None:
        return connect(target, database)
    import psycopg

    return psycopg.connect(
        host=target.host,
        port=target.port,
        user=target.user,
        password=target.password,
        dbname=database,
        autocommit=True,
    )


def _owner_connect() -> Callable[..., object]:
    def connect(host: str, port: int, dbname: str, user: str) -> object:
        import psycopg

        return psycopg.connect(host=host, port=port, dbname=dbname, user=user)

    return connect


def _exists(connection: object, catalogue: str, column: str, name: str) -> bool:
    rows = _query(
        connection,
        f"SELECT 1 FROM pg_catalog.{catalogue} WHERE {column} = %s",
        (name,),
    )
    return len(rows) > 0


def _statement(connection: object, sql: str) -> None:
    _query(connection, sql, None)


def _query(connection: object, sql: str, params: object) -> list[tuple[object, ...]]:
    execute = getattr(connection, "execute", None)
    if callable(execute) and getattr(connection, "stand_in", False):
        result = execute(sql, params)
        return [] if result is None else [tuple(row) for row in result]
    cursor_fn = getattr(connection, "cursor", None)
    if not callable(cursor_fn):
        message = "engine operation failed"
        raise _Stop(message)
    cursor = cursor_fn()
    try:
        cursor.execute(sql, params)
        description = getattr(cursor, "description", None)
        if description is None:
            return []
        return [tuple(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def _remove(connection: object, release_id: str) -> None:
    database, schema, staging = drop_names(release_id)
    for name in (staging, schema):
        _statement(connection, f'DROP SCHEMA IF EXISTS "{name}" CASCADE')
    _statement(connection, f'DROP DATABASE IF EXISTS "{database}"')


def _close(connection: object) -> None:
    close = getattr(connection, "close", None)
    if callable(close):
        close()


if __name__ == "__main__":
    import os

    sys.exit(main(sys.argv[1:], os.environ))
