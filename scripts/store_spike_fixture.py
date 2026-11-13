"""Fixed Synthetic control fixture and isolated resources for S1-T05.

No release data, addresses, extensions or permanent PostgreSQL objects are used.
Temporary files follow tempfile's environment; the launcher supplies its scratch.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from preflight_database import DbTarget, parse_database_url
from store_spike_normalise import QueryResult, SpikeRefusal, normalise

if TYPE_CHECKING:
    import duckdb
    import psycopg

COLUMNS = ("unit_id", "label", "period", "count_value", "decimal_control")
type FixtureRow = tuple[str, str | None, date, int, Decimal | None]
LABELS = ("SYN-é", "SYN-tie", None, "SYN-أ", "SYN-tie", "SYN-e\u0301", "SYN-Z")
CONTROLS = (Decimal("1.2345645"), Decimal("-1.2345655"), None)
ROWS: tuple[FixtureRow, ...] = tuple(
    (
        f"SYN-unit-{letter}",
        label,
        date(2000, 1, 1),
        ordinal,
        CONTROLS[ordinal % len(CONTROLS)],
    )
    for ordinal, (letter, label) in enumerate(
        zip("abcdefg", LABELS, strict=True), start=1
    )
    for _ in range(2)
)
UNITS = tuple(dict.fromkeys(row[0] for row in ROWS))
FIXTURE_BYTES = json.dumps(
    {"name": "SYN-store-spike-v1", "columns": COLUMNS, "rows": ROWS},
    default=str,
    ensure_ascii=False,
    separators=(",", ":"),
    sort_keys=True,
).encode("utf-8")
FIXTURE_ID = hashlib.sha256(FIXTURE_BYTES).hexdigest()

DUCK_CREATE = """CREATE TABLE spike_control (
    unit_id TEXT NOT NULL, label TEXT, period DATE NOT NULL,
    count_value BIGINT NOT NULL, decimal_control DECIMAL(18, 7))"""
PG_CREATE = """CREATE TEMPORARY TABLE spike_control (
    unit_id TEXT COLLATE "C" NOT NULL, label TEXT COLLATE "C", period DATE NOT NULL,
    count_value BIGINT NOT NULL, decimal_control DECIMAL(18, 7)) ON COMMIT DROP"""
PG_INSERT = "INSERT INTO spike_control VALUES (%s, %s, %s, %s, %s)"
DUCK_INSERT = "INSERT INTO spike_control VALUES (?, ?, ?, ?, ?)"


def expected(units: list[str]) -> QueryResult:
    """Independent Python grouping and raw UTF-8 ordering before NFC conversion."""
    totals: dict[tuple[str, str | None, date, Decimal | None], int] = {}
    for unit, label, period, count, control in ROWS:
        if unit in units:
            key = (unit, label, period, control)
            totals[key] = totals.get(key, 0) + count
    ordered = sorted(
        totals,
        key=lambda key: (key[1] is None, (key[1] or "").encode("utf-8"), key[0]),
    )
    rows = tuple(
        tuple(normalise(value) for value in (unit, label, period, totals[key], control))
        for key in ordered
        for unit, label, period, control in (key,)
    )
    return QueryResult(FIXTURE_ID, COLUMNS, rows)


def database_target(environ: Mapping[str, str]) -> DbTarget:
    """Use only the environment and the preflight parser; never read a dotenv file."""
    raw = environ.get("EII_DATABASE_URL", "")
    if not raw:
        raise SpikeRefusal("database environment missing")
    target = parse_database_url(raw)
    if isinstance(target, str):
        raise SpikeRefusal("database configuration invalid")
    if target.host != "127.0.0.1":
        raise SpikeRefusal("database target is not project loopback")
    return target


@contextmanager
def duck_fixture(*, diverge: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
    """Close the writer before opening the read-only reader; always remove the file."""
    import duckdb

    with tempfile.TemporaryDirectory(prefix="store-spike-") as scratch:
        path = Path(scratch) / "control.duckdb"
        writer = duckdb.connect(str(path))
        try:
            writer.execute(DUCK_CREATE)
            writer.executemany(DUCK_INSERT, ROWS)
            if diverge:
                writer.execute(
                    "UPDATE spike_control SET count_value = count_value + 1 WHERE unit_id = ?",
                    [UNITS[0]],
                )
        finally:
            writer.close()
        reader = duckdb.connect(str(path), read_only=True)
        try:
            reader.execute("SET enable_external_access = false")
            reader.execute("SET lock_configuration = true")
            yield reader
        finally:
            reader.close()


@contextmanager
def postgres_fixture(
    environ: Mapping[str, str],
) -> Iterator[psycopg.Connection[tuple[object, ...]]]:
    """Temporary C-collated table, rolled back even on success; then close session."""
    target = database_target(environ)
    import psycopg

    connection: psycopg.Connection[tuple[object, ...]] = psycopg.connect(
        host=target.host,
        port=target.port,
        dbname=target.database,
        user=target.user,
        password=target.password,
        connect_timeout=5,
    )
    try:
        connection.execute("SET LOCAL search_path = pg_temp")
        connection.execute("SET LOCAL statement_timeout = '5s'")
        connection.execute(PG_CREATE)
        with connection.cursor() as cursor:
            cursor.executemany(PG_INSERT, ROWS)
        yield connection
    finally:
        try:
            connection.rollback()
        finally:
            connection.close()
