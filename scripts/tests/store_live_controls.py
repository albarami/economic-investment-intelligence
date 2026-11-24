"""Invented control rows shared by the store tests and the live command."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from eii_product.store.normalise import normalise
from eii_product.store.protocol import QueryResult

FIXTURE_DIR = (
    Path(__file__).resolve().parents[2] / "product" / "tests" / "fixtures" / "store"
)
COLUMNS = ("unit_id", "label", "period", "count_value", "amount")
ROWS: tuple[tuple[str, str | None, date, int, Decimal | None], ...] = (
    ("SYN-a", "SYN-alpha", date(2000, 1, 1), 2, Decimal("1.25")),
    ("SYN-b", "SYN-e\u0301", date(2000, 1, 2), 4, Decimal("2.5")),
    ("SYN-c", None, date(2000, 1, 3), 6, None),
)
FIXTURE_BYTES = json.dumps(
    {"columns": COLUMNS, "name": "SYN-control-rows", "rows": ROWS},
    default=str,
    ensure_ascii=False,
    separators=(",", ":"),
    sort_keys=True,
).encode("utf-8")
FIXTURE_ID = hashlib.sha256(FIXTURE_BYTES).hexdigest()
DUCK_CREATE = """CREATE TABLE control_rows (
    unit_id VARCHAR NOT NULL,
    label VARCHAR,
    period DATE NOT NULL,
    count_value BIGINT NOT NULL,
    amount DECIMAL(18, 6))"""
DUCK_INSERT = "INSERT INTO control_rows VALUES (?, ?, ?, ?, ?)"
# ISO WKB, little-endian, no SRID. A point is the byte 0x01, then uint32 type 1,
# then two IEEE-754 little-endian doubles.
# 0.125 is 0x3FC0000000000000, stored 000000000000C03F.
# 0.25 is 0x3FD0000000000000, stored 000000000000D03F.
# 0.5 is 0x3FE0000000000000, stored 000000000000E03F.
POINT_A = "0101000000000000000000C03F000000000000D03F"
POINT_B = "0101000000000000000000E03F000000000000E03F"
GEOM_WKT = (
    ("SYN-g0", "POINT(0.125 0.25)"),
    ("SYN-g1", "POINT(0.5 0.5)"),
    ("SYN-g2", None),
)
DUCK_GEOM_CREATE = """CREATE TABLE control_shape (
    shape_id VARCHAR NOT NULL,
    shape GEOMETRY)"""
# DuckDB accepts a statement that begins with FROM (measured on this machine).
# PostgreSQL 18's SELECT page is
# https://www.postgresql.org/docs/18/sql-select.html
# Its synopsis starts with an optional WITH and then SELECT; FROM is a clause of
# SELECT, and that synopsis has no statement that starts with FROM. The page was
# not re-fetched in this pass, so that sentence is not a quotation. The live run
# is the proof that PostgreSQL's prepare rejects this statement.
SPLIT_SQL = """-- name: engine_split
-- params:
-- returns: pair_count text
-- order: pair_count
FROM control_rows SELECT unit_id AS pair_count
"""
SPLIT_TOML = """[[tables]]
name = "control_rows"
anchor = "invented control table"
key = ["pair_count"]

[[tables.columns]]
name = "unit_id"
type = "string"
nullable = false

[[tables.columns]]
name = "label"
type = "string"
nullable = true

[[tables.columns]]
name = "pair_count"
type = "int"
nullable = false
"""


def units() -> list[str]:
    """Every invented unit, in header order."""
    return [row[0] for row in ROWS]


def expected(selected: list[str]) -> QueryResult:
    """Rows a correct read returns, in the query's order, after normalisation."""
    chosen = [row for row in ROWS if row[0] in selected]
    chosen.sort(key=lambda row: row[0])
    return QueryResult(
        COLUMNS,
        tuple(tuple(normalise(value) for value in row) for row in chosen),
    )
