"""S1-T05 one-query spike, not the production registry or store selector.

Offline test_store_spike proves binding, normalisation, comparison, refusals and
real DuckDB behaviour. Only tests/live_store_spike.py proves both real engines;
a missing PostgreSQL service is a failure, never a skip or one-store fallback.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from store_spike_fixture import COLUMNS, FIXTURE_ID
from store_spike_normalise import QueryResult, SpikeRefusal, normalise

if TYPE_CHECKING:
    import duckdb
    import psycopg

QUERY_NAME = "spike_unit_totals"
SQL_PATH = Path(__file__).with_suffix(".sql")
PLACEHOLDER = re.compile(r"(?<![\w:]):([a-z_][a-z0-9_]*)(?!\w)")
type Engine = Literal["postgres", "embedded"]


def translate(sql: str, engine: Engine) -> str:
    """Whole-token translation of the fixed file, never interpolation of values."""
    if engine == "postgres":
        return PLACEHOLDER.sub(lambda m: f"%({m[1]})s", sql)
    if engine == "embedded":
        return PLACEHOLDER.sub(lambda m: f"${m[1]}", sql)
    raise SpikeRefusal("unknown engine")


def prepare(
    query: str, params: Mapping[str, object], engine: Engine
) -> tuple[str, dict[str, list[str]]]:
    """Accept the sole named query and precisely its typed list parameter."""
    if query != QUERY_NAME:
        raise SpikeRefusal("unknown query")
    if set(params) != {"units"}:
        raise SpikeRefusal("parameter names invalid")
    units = params["units"]
    if not isinstance(units, list) or not all(isinstance(unit, str) for unit in units):
        raise SpikeRefusal("parameter types invalid")
    return translate(SQL_PATH.read_text(encoding="utf-8"), engine), {
        "units": list(units)
    }


def query_hash() -> str:
    return hashlib.sha256(SQL_PATH.read_bytes()).hexdigest()


def result(columns: tuple[str, ...], rows: Sequence[Sequence[object]]) -> QueryResult:
    if columns != COLUMNS:
        raise SpikeRefusal("result columns invalid")
    if any(len(row) != len(COLUMNS) for row in rows):
        raise SpikeRefusal("result width invalid")
    return QueryResult(
        FIXTURE_ID,
        columns,
        tuple(tuple(normalise(value) for value in row) for row in rows),
    )


@dataclass
class DuckStore:
    connection: duckdb.DuckDBPyConnection

    def fetch(self, query: str, params: Mapping[str, object]) -> QueryResult:
        sql, bound = prepare(query, params, "embedded")
        cursor = self.connection.execute(sql, bound)
        if cursor.description is None:
            raise SpikeRefusal("result description missing")
        return result(
            tuple(column[0] for column in cursor.description), cursor.fetchall()
        )


@dataclass
class PostgresStore:
    connection: psycopg.Connection[tuple[object, ...]]

    def fetch(self, query: str, params: Mapping[str, object]) -> QueryResult:
        sql, bound = prepare(query, params, "postgres")
        with self.connection.cursor() as cursor:
            cursor.execute(sql, bound)
            if cursor.description is None:
                raise SpikeRefusal("result description missing")
            return result(
                tuple(column.name for column in cursor.description), cursor.fetchall()
            )
