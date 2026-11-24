"""Read-only DuckDB adapter. The driver is imported only while a store is open."""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
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


class _Cursor(Protocol):
    description: Sequence[Sequence[object]] | None

    def execute(self, sql: str, params: object = None) -> object:
        """Run one statement on this cursor."""

    def fetchall(self) -> list[tuple[object, ...]]:
        """Return every row of the current statement."""


@runtime_checkable
class _Connection(Protocol):
    def cursor(self) -> _Cursor:
        """Return a new cursor."""

    def execute(self, sql: str) -> object:
        """Run one setup statement."""

    def close(self) -> None:
        """Close the file."""


class EmbeddedStore:
    """One read-only DuckDB file. Each thread keeps its own cursor."""

    engine: EngineName = "embedded"

    def __init__(self, path: Path, identity: str, inventory: Inventory) -> None:
        """Open the file read-only, disable external access, then lock configuration."""
        require_identity(identity)
        self.release_id = identity
        self._inventory = inventory
        self._local = threading.local()
        self._connection: _Connection | None = None
        connection: _Connection | None = None
        try:
            import duckdb

            opened = duckdb.connect(str(path), read_only=True)
            if not isinstance(opened, _Connection):
                opened.close()
                raise StoreRefusal("STORE_UNAVAILABLE")
            connection = opened
            connection.execute("SET enable_external_access = false")
            connection.execute("SET lock_configuration = true")
        except StoreRefusal:
            _close(connection)
            raise
        except Exception:
            _close(connection)
            raise StoreRefusal("STORE_UNAVAILABLE") from None
        self._connection = connection

    def fetch(self, query: object, params: Mapping[str, Param]) -> QueryResult:
        """Run one registered query on this thread's cursor."""
        spec = require_query(self._inventory, query)
        sql, bound = bind(spec, params, self.engine)
        try:
            cursor = self._cursor()
            cursor.execute(sql, bound)
            if cursor.description is None:
                raise StoreRefusal("result description missing")
            columns = tuple(_column_name(column) for column in cursor.description)
            rows = cursor.fetchall()
        except StoreRefusal:
            raise
        except Exception:
            raise StoreRefusal("engine operation failed") from None
        return checked_result(spec, columns, rows)

    def plan(self, query: object, params: Mapping[str, Param]) -> None:
        """Ask DuckDB to plan the query. A binder error names the query and engine."""
        spec = require_query(self._inventory, query)
        sql, bound = bind(spec, params, self.engine)
        try:
            cursor = self._cursor()
            cursor.execute("EXPLAIN " + sql, bound)
            cursor.fetchall()
        except StoreRefusal as refusal:
            if str(refusal) == "engine operation failed":
                raise prepare_failed(spec.name, self.engine) from None
            raise
        except Exception:
            raise prepare_failed(spec.name, self.engine) from None

    def ping(self, timeout_s: float) -> StoreHealth:
        """Require a trivial read. The statement time limit is not built here."""
        del timeout_s
        try:
            self._cursor().execute("SELECT 1")
        except Exception:
            raise StoreRefusal("STORE_UNAVAILABLE") from None
        return StoreHealth(ok=True)

    def close(self) -> None:
        """Close the file this store opened."""
        _close(self._connection)
        self._connection = None

    def _cursor(self) -> _Cursor:
        if self._connection is None:
            raise StoreRefusal("STORE_UNAVAILABLE")
        cursor = getattr(self._local, "cursor", None)
        if cursor is None:
            cursor = self._connection.cursor()
            self._local.cursor = cursor
        return cursor


def _column_name(column: Sequence[object]) -> str:
    raw = column[0]
    if not isinstance(raw, str):
        raise StoreRefusal("result columns invalid")
    return raw


def _close(connection: _Connection | None) -> None:
    if connection is not None:
        connection.close()
