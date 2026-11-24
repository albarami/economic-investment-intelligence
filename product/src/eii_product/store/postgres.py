"""PostgreSQL adapter. The driver is imported only by the live command, not here."""

from __future__ import annotations

import re
import threading
from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from eii_product.store.protocol import (
    EngineName,
    Param,
    QueryResult,
    StoreHealth,
    StoreRefusal,
    prepare_failed,
    require_identity,
)
from eii_product.store.registry import Inventory, bind, checked_result, require_query

_RELEASE_SCHEMA = re.compile(r"r_[0-9a-f]{16}\Z")
_CONTROL_SCHEMA = re.compile(r"ctl_[0-9a-f]{16}\Z")
_PLAIN_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_BEGIN = "BEGIN READ ONLY"
_SET_CONFIG = "SELECT set_config('search_path', %s, true)"
_COMMIT = "COMMIT"
_POSTGIS_SCHEMA_SQL = (
    "SELECT n.nspname FROM pg_catalog.pg_extension AS e "
    "JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace "
    "WHERE e.extname = 'postgis'"
)


class _Cursor(Protocol):
    description: Sequence[object] | None

    def execute(self, sql: str, params: object = None) -> object:
        """Run one statement."""

    def fetchone(self) -> tuple[object, ...] | None:
        """Return the current row."""

    def fetchall(self) -> list[tuple[object, ...]]:
        """Return every current row."""

    def close(self) -> None:
        """Close this cursor."""


@runtime_checkable
class PostgresConnection(Protocol):
    """A caller-owned connection. This adapter never opens one."""

    autocommit: bool

    def cursor(self) -> _Cursor:
        """Return a new cursor. Callers do not share cursors across threads."""

    def close(self) -> None:
        """Close the connection. The control command owns that call."""


def release_schema(identity: str) -> str:
    """Name a release schema `r_` plus the first 16 hex characters of the identity."""
    require_identity(identity)
    return "r_" + identity[:16]


def control_schema(identity: str) -> str:
    """Name a control schema. The name cannot match the release pattern."""
    require_identity(identity)
    name = "ctl_" + identity[:16]
    require_control_schema_name(name)
    return name


def require_control_schema_name(name: str) -> None:
    """Refuse a control schema whose spelling is a release schema."""
    if _RELEASE_SCHEMA.fullmatch(name):
        raise StoreRefusal("release identity invalid")
    if _CONTROL_SCHEMA.fullmatch(name) is None:
        raise StoreRefusal("release identity invalid")


def _require_connection(connection: object) -> PostgresConnection:
    """Refuse a connection that is not open in autocommit mode."""
    if (
        not isinstance(connection, PostgresConnection)
        or connection.autocommit is not True
    ):
        raise StoreRefusal("engine operation failed")
    return connection


class PostgresStore:
    """One connection, serialised. Each fetch opens and ends a read-only transaction."""

    engine: EngineName = "postgres"

    def __init__(self, connection: object, identity: str, inventory: Inventory) -> None:
        """Bind a trusted connection to the release schema of a verified identity."""
        self._connection = _require_connection(connection)
        self._inventory = inventory
        self._schema = release_schema(identity)
        self.release_id = identity
        self._lock = threading.Lock()
        self._postgis_schema = _read_postgis_schema(self._connection)

    @classmethod
    def for_control(
        cls, connection: object, identity: str, inventory: Inventory
    ) -> PostgresStore:
        """Open a control schema. Start-up and tests call this; tools do not."""
        store = cls.__new__(cls)
        connection = _require_connection(connection)
        store._connection = connection
        store._inventory = inventory
        store._schema = control_schema(identity)
        store.release_id = identity
        store._lock = threading.Lock()
        store._postgis_schema = _read_postgis_schema(store._connection)
        return store

    def fetch(self, query: object, params: Mapping[str, Param]) -> QueryResult:
        """Run one registered query inside a read-only transaction."""
        spec = require_query(self._inventory, query)
        sql, bound = bind(
            spec, params, self.engine, postgis_schema=self._postgis_schema
        )
        with self._lock:
            self._require_autocommit()
            columns, rows = self._execute(sql, bound, explain=False)
        return checked_result(spec, columns, rows)

    def plan(self, query: object, params: Mapping[str, Param]) -> None:
        """Plan one query inside the same read-only transaction as a fetch."""
        spec = require_query(self._inventory, query)
        sql, bound = bind(
            spec, params, self.engine, postgis_schema=self._postgis_schema
        )
        with self._lock:
            self._require_autocommit()
            try:
                self._execute("EXPLAIN " + sql, bound, explain=True)
            except StoreRefusal as refusal:
                if str(refusal) == "engine operation failed":
                    raise prepare_failed(spec.name, self.engine) from None
                raise

    def ping(self, timeout_s: float) -> StoreHealth:
        """Require the connection to answer. The statement time limit is not built."""
        del timeout_s
        with self._lock:
            self._require_autocommit()
            try:
                self._execute("SELECT 1", {}, explain=True)
            except StoreRefusal:
                raise StoreRefusal("STORE_UNAVAILABLE") from None
        return StoreHealth(ok=True)

    def close(self) -> None:
        """The caller owns the connection. This adapter does not close it."""
        return None

    def _require_autocommit(self) -> None:
        """Refuse a flipped connection. The caller holds the store lock."""
        if self._connection.autocommit is not True:
            raise StoreRefusal("engine operation failed")

    def _execute(
        self, sql: str, bound: Mapping[str, object], *, explain: bool
    ) -> tuple[tuple[str, ...], list[tuple[object, ...]]]:
        """Run one transaction. The caller holds the lock and has checked autocommit."""
        cursor = self._connection.cursor()
        columns: tuple[str, ...] = ()
        rows: list[tuple[object, ...]] = []
        try:
            cursor.execute(_BEGIN)
            cursor.execute(_SET_CONFIG, (self._schema,))
            configured = cursor.fetchone()
            if configured is None or configured[0] != self._schema:
                raise StoreRefusal("engine operation failed")
            cursor.execute(sql, dict(bound))
            if not explain:
                if cursor.description is None:
                    raise StoreRefusal("result description missing")
                columns = tuple(_column_name(column) for column in cursor.description)
                rows = cursor.fetchall()
            else:
                cursor.fetchall()
            cursor.execute(_COMMIT)
        except StoreRefusal:
            _rollback(cursor)
            raise
        except Exception:
            _rollback(cursor)
            raise StoreRefusal("engine operation failed") from None
        finally:
            cursor.close()
        return columns, rows


def _read_postgis_schema(connection: PostgresConnection) -> str:
    """Read the postgis extension's schema once. Refuse an absent or unsafe name."""
    cursor = connection.cursor()
    try:
        cursor.execute(_POSTGIS_SCHEMA_SQL)
        row = cursor.fetchone()
    except StoreRefusal:
        raise
    except Exception:
        raise StoreRefusal("engine operation failed") from None
    finally:
        cursor.close()
    if row is None or len(row) == 0:
        raise StoreRefusal("extension schema invalid")
    return _quote_identifier(row[0])


def _quote_identifier(name: object) -> str:
    """Quote a plain identifier. Any other name is refused."""
    if not isinstance(name, str) or _PLAIN_IDENTIFIER.fullmatch(name) is None:
        raise StoreRefusal("extension schema invalid")
    return '"' + name + '"'


def _column_name(column: object) -> str:
    if isinstance(column, tuple):
        raw: object = column[0]
    else:
        raw = getattr(column, "name", None)
    if not isinstance(raw, str):
        raise StoreRefusal("result columns invalid")
    return raw


def _rollback(cursor: _Cursor) -> None:
    try:
        cursor.execute("ROLLBACK")
    except Exception:
        return
