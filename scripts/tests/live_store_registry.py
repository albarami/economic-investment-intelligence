"""Live control command. The lead runs it; tests call it with a stand-in connection."""

from __future__ import annotations

import json
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from store_live_controls import (
    DUCK_CREATE,
    DUCK_GEOM_CREATE,
    DUCK_INSERT,
    FIXTURE_DIR,
    FIXTURE_ID,
    GEOM_WKT,
    POINT_A,
    POINT_B,
    ROWS,
    SPLIT_SQL,
    SPLIT_TOML,
    expected,
    units,
)

from eii_product.store.embedded import EmbeddedStore
from eii_product.store.normalise import Fact, ToolResult, compare_queries
from eii_product.store.parity import (
    ParityCase,
    RunResult,
    ToolDescriptor,
    prepare_all,
    run_parity,
)
from eii_product.store.postgres import PostgresConnection, PostgresStore, control_schema
from eii_product.store.protocol import (
    NormalValue,
    QueryResult,
    ReleaseStore,
    StoreRefusal,
)
from eii_product.store.registry import Inventory, load_inventory

PASS_LINE = "PASS store-registry: both engines match"
EXISTS_SQL = "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s"
_ROUND = {"SYN-count": 0, "SYN-wkb": 0}


class _Divergence(Exception):
    """The baseline passed and the changed integer did not match."""


class _ParserRefusal(Exception):
    """A refusal that belongs to the database URL parser, printed as itself."""


def main(
    args: Sequence[str],
    environ: Mapping[str, str],
    *,
    connect: Callable[[object], object] | None = None,
    destination: Path | None = None,
) -> int:
    """Exit 0 on a full pass, 3 on a detected divergence, 2 on usage, 1 otherwise."""
    if list(args) not in ([], ["--diverge"]):
        print("FAIL store-registry: usage: live_store_registry.py [--diverge]")
        return 2
    try:
        _run(
            environ,
            diverge=list(args) == ["--diverge"],
            connect=connect,
            destination=destination,
        )
    except _Divergence as error:
        print(f"FAIL store-registry: {error}")
        return 3
    except _ParserRefusal as error:
        print(f"FAIL store-registry: {error}")
        return 1
    except StoreRefusal as error:
        print(f"FAIL store-registry: {error}")
        return 1
    except Exception:
        print("FAIL store-registry: engine operation failed")
        return 1
    return 0


def _run(
    environ: Mapping[str, str],
    *,
    diverge: bool,
    connect: Callable[[object], object] | None,
    destination: Path | None,
) -> None:
    target = _target(environ)
    schema = control_schema(FIXTURE_ID)
    connection = _open_postgres(target, connect)
    created_box = [False]
    failure: BaseException | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="syn-store-") as scratch:
            root = Path(scratch)
            duck_path = root / "control.duckdb"
            _build_duck(duck_path, changed=False)
            outcome: RunResult | None = None
            try:
                _setup_postgres(connection, schema, created_box)
                outcome = _prove(connection, duck_path, root, diverge)
            except BaseException as error:
                failure = error
            if created_box[0]:
                try:
                    _drop_schema(connection, schema)
                except StoreRefusal as error:
                    failure = error
            if failure is not None:
                raise failure
            if outcome is None:
                raise StoreRefusal("engine operation failed")
            report_path = (
                destination if destination is not None else root / "control-report.json"
            )
            from eii_product.store.parity import write_report

            write_report(
                report_path,
                results=outcome.results,
                traces=outcome.traces,
                scope="control",
                release_id=None,
                fixture_id=FIXTURE_ID,
                pairs=outcome.pairs,
            )
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            print(PASS_LINE)
            print(
                json.dumps(
                    {
                        "cases_run": payload["cases_run"],
                        "facts_compared": payload["facts_compared"],
                        "facts_identical": payload["facts_identical"],
                        "prepare_failed_engine": "postgres",
                    },
                    sort_keys=True,
                )
            )
    finally:
        _close(connection)


def _prove(
    connection: PostgresConnection,
    duck_path: Path,
    root: Path,
    diverge: bool,
) -> RunResult:
    inventory = load_inventory(FIXTURE_DIR)
    embedded = EmbeddedStore(duck_path, FIXTURE_ID, inventory)
    try:
        return _read(connection, embedded, inventory, duck_path, root, diverge)
    finally:
        embedded.close()


def _read(
    connection: PostgresConnection,
    embedded: EmbeddedStore,
    inventory: Inventory,
    duck_path: Path,
    root: Path,
    diverge: bool,
) -> RunResult:
    postgres = PostgresStore.for_control(connection, FIXTURE_ID, inventory)
    prepare_all(embedded, inventory)
    prepare_all(postgres, inventory)
    embedded.close()
    _one_engine_fails(duck_path, connection, root)
    reopened = EmbeddedStore(duck_path, FIXTURE_ID, inventory)
    try:
        outcome = run_parity(
            (postgres, reopened),
            (_tool(inventory),),
            (ParityCase("syn_control", (("units", units()),)),),
            inventory,
            unit_precision=_ROUND,
            round_fact=_round_fact,
        )
        _prove_write_refused(connection, postgres)
        _threads(postgres, reopened, inventory)
        if diverge:
            _diverge(connection, reopened, inventory, root)
        return outcome
    finally:
        reopened.close()


def _one_engine_fails(
    duck_path: Path, connection: PostgresConnection, root: Path
) -> None:
    folder = root / "split"
    folder.mkdir()
    (folder / "__init__.py").write_text(
        '"""Invented one-engine prepare probe."""\n', encoding="utf-8"
    )
    (folder / "engine_split.sql").write_text(SPLIT_SQL, encoding="utf-8")
    (folder / "engine_split.toml").write_text(SPLIT_TOML, encoding="utf-8")
    inventory = load_inventory(folder)
    failures: list[str] = []
    embedded = EmbeddedStore(duck_path, FIXTURE_ID, inventory)
    try:
        _record_prepare(embedded, inventory, failures)
    finally:
        embedded.close()
    postgres = PostgresStore.for_control(connection, FIXTURE_ID, inventory)
    _record_prepare(postgres, inventory, failures)
    _refuse_unexpected_prepare(failures)


def _refuse_unexpected_prepare(failures: list[str]) -> None:
    """The split probe fails on PostgreSQL alone. Any other list is printed, then refused."""
    if failures != ["postgres"]:
        print(",".join(failures))
        raise StoreRefusal("engine operation failed")


def _record_prepare(
    store: ReleaseStore, inventory: Inventory, failures: list[str]
) -> None:
    try:
        prepare_all(store, inventory)
    except StoreRefusal as error:
        if not str(error).startswith("prepare failed"):
            raise
        failures.append(store.engine)


def _diverge(
    connection: PostgresConnection,
    embedded: EmbeddedStore,
    inventory: Inventory,
    root: Path,
) -> None:
    member = inventory.lookup("control_rows")
    baseline = PostgresStore.for_control(connection, FIXTURE_ID, inventory).fetch(
        member, {"units": units()}
    )
    embedded.close()
    changed_path = root / "changed.duckdb"
    _build_duck(changed_path, changed=True)
    changed = EmbeddedStore(changed_path, FIXTURE_ID, inventory)
    try:
        compare_queries(
            FIXTURE_ID,
            baseline,
            FIXTURE_ID,
            changed.fetch(member, {"units": units()}),
        )
    except StoreRefusal as error:
        raise _Divergence(str(error)) from None
    else:
        raise StoreRefusal("engine operation failed")
    finally:
        changed.close()


def _threads(
    postgres: ReleaseStore, embedded: ReleaseStore, inventory: Inventory
) -> None:
    import threading

    member = inventory.lookup("control_rows")
    found: list[QueryResult] = []
    errors: list[BaseException] = []

    def read(store: ReleaseStore) -> None:
        try:
            found.append(store.fetch(member, {"units": units()}))
        except BaseException as error:
            errors.append(error)

    threads = [
        threading.Thread(target=read, args=(store,))
        for store in (postgres, postgres, embedded, embedded)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if errors or len(found) != 4:
        raise StoreRefusal("engine operation failed")
    wanted = expected(units())
    for result in found:
        compare_queries(FIXTURE_ID, wanted, FIXTURE_ID, result)


def _tool(inventory: Inventory) -> ToolDescriptor:
    member = inventory.lookup("control_rows")
    shape = inventory.lookup("control_shape")

    def run(store: ReleaseStore, params: Mapping[str, object]) -> ToolResult:
        del params
        full = store.fetch(member, {"units": units()})
        empty = store.fetch(member, {"units": []})
        if empty.rows:
            raise StoreRefusal("engine operation failed")
        geom = store.fetch(shape, {})
        total = 0
        for row in full.rows:
            value = row[3]
            if type(value) is not int:
                raise StoreRefusal("result types invalid")
            total += value
        facts = [Fact("total", "SYN-count", total)]
        for index, row in enumerate(geom.rows):
            facts.append(Fact(f"shape_{index}", "SYN-wkb", row[1]))
        return ToolResult(
            store.engine,
            "SYN-call",
            1,
            "syn_control",
            "ok",
            None,
            tuple(facts),
        )

    return ToolDescriptor(
        "syn_control", run, tuple(query.name for query in inventory.queries)
    )


def _prove_write_refused(connection: PostgresConnection, store: PostgresStore) -> None:
    """A write in the read-only transaction must fail. The adapter does not own this."""
    cursor = connection.cursor()
    try:
        cursor.execute("BEGIN READ ONLY")
        cursor.execute("SELECT set_config('search_path', %s, true)", (store._schema,))
        try:
            cursor.execute(
                "INSERT INTO control_rows VALUES (%s, %s, %s, %s, %s)",
                ("SYN-z", "SYN-z", "2000-01-01", 1, None),
            )
        except Exception as error:
            _rollback(cursor)
            if _engine_write_refusal(error):
                return
            raise StoreRefusal("engine operation failed") from None
        _rollback(cursor)
    finally:
        cursor.close()
    raise StoreRefusal("engine operation failed")


def _engine_write_refusal(error: BaseException) -> bool:
    """The engine's own read-only refusal, by its class or SQLSTATE 25006."""
    if type(error).__name__ == "ReadOnlySqlTransaction":
        return True
    return getattr(error, "sqlstate", None) == "25006"


def _rollback(cursor: object) -> None:
    execute = getattr(cursor, "execute", None)
    if not callable(execute):
        return
    try:
        execute("ROLLBACK")
    except Exception:
        return


def _setup_postgres(
    connection: PostgresConnection, schema: str, created_box: list[bool]
) -> None:
    """Create the control schema. The box records creation even when a later step fails."""
    cursor = connection.cursor()
    try:
        cursor.execute(EXISTS_SQL, (schema,))
        if cursor.fetchone() is not None:
            raise StoreRefusal("control schema exists")
        cursor.execute(f'CREATE SCHEMA "{schema}"')
        created_box[0] = True
        cursor.execute(
            f'''CREATE TABLE "{schema}".control_rows (
                unit_id TEXT COLLATE "C" NOT NULL,
                label TEXT COLLATE "C",
                period DATE NOT NULL,
                count_value BIGINT NOT NULL,
                amount NUMERIC(18, 6))'''
        )
        insert = f'INSERT INTO "{schema}".control_rows VALUES (%s, %s, %s, %s, %s)'
        for row in ROWS:
            cursor.execute(insert, row)
        cursor.execute(
            f'''CREATE TABLE "{schema}".control_shape (
                shape_id TEXT COLLATE "C" NOT NULL,
                shape geometry)'''
        )
        geom_insert = (
            f'INSERT INTO "{schema}".control_shape '
            "VALUES (%s, ST_GeomFromWKB(decode(%s, 'hex')))"
        )
        for shape_id, wkt in GEOM_WKT:
            if wkt is None:
                cursor.execute(
                    f'INSERT INTO "{schema}".control_shape VALUES (%s, NULL)',
                    (shape_id,),
                )
                continue
            text = POINT_A if shape_id == "SYN-g0" else POINT_B
            cursor.execute(geom_insert, (shape_id, text))
        cursor.execute("COMMIT")
    finally:
        cursor.close()


def _drop_schema(connection: PostgresConnection, schema: str) -> None:
    cursor = connection.cursor()
    try:
        try:
            cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
            cursor.execute("COMMIT")
        except StoreRefusal:
            raise
        except Exception:
            raise StoreRefusal("control schema cleanup failed") from None
    finally:
        cursor.close()


def _build_duck(path: Path, *, changed: bool) -> None:
    import duckdb

    connection = duckdb.connect(str(path))
    try:
        connection.execute(DUCK_CREATE)
        connection.executemany(DUCK_INSERT, ROWS)
        connection.execute(DUCK_GEOM_CREATE)
        for shape_id, wkt in GEOM_WKT:
            if wkt is None:
                connection.execute(
                    "INSERT INTO control_shape VALUES (?, NULL)", [shape_id]
                )
                continue
            connection.execute(
                "INSERT INTO control_shape VALUES (?, ?::GEOMETRY)",
                [shape_id, wkt],
            )
        if changed:
            connection.execute(
                "UPDATE control_rows SET count_value = count_value + 1 WHERE unit_id = ?",
                ["SYN-a"],
            )
    finally:
        connection.close()


def _open_postgres(
    target: object, connect: Callable[[object], object] | None
) -> PostgresConnection:
    from preflight_database import DbTarget

    if not isinstance(target, DbTarget):
        raise StoreRefusal("engine operation failed")
    try:
        if connect is not None:
            opened: object = connect(target)
        else:
            import psycopg

            opened = psycopg.connect(
                host=target.host,
                port=target.port,
                dbname=target.database,
                user=target.user,
                password=target.password,
                connect_timeout=5,
                autocommit=True,
            )
    except StoreRefusal:
        raise
    except Exception:
        raise StoreRefusal("engine operation failed") from None
    if not isinstance(opened, PostgresConnection):
        raise StoreRefusal("engine operation failed")
    return opened


def _target(environ: Mapping[str, str]) -> object:
    raw = environ.get("EII_DATABASE_URL", "")
    if raw == "":
        raise StoreRefusal("database environment missing")
    scripts = str(Path(__file__).resolve().parents[1])
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from preflight_database import parse_database_url

    parsed = parse_database_url(raw)
    if isinstance(parsed, str):
        raise _ParserRefusal(parsed)
    if parsed.host != "127.0.0.1":
        raise _ParserRefusal("EII_DATABASE_URL host is not 127.0.0.1")
    return parsed


def _close(connection: PostgresConnection) -> None:
    try:
        connection.close()
    except Exception:
        return


def _round_fact(value: NormalValue, places: int) -> NormalValue:
    del places
    return value


if __name__ == "__main__":
    import os

    raise SystemExit(main(sys.argv[1:], os.environ))
