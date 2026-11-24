"""Shared invented fixture for make_area tests.

``product.tests`` is importable because pytest puts the repository root on the
path, which is how ``product.tests.test_areas_spike`` is already imported.
``--import-mode=importlib`` does not put the test directory itself on the path,
so a bare sibling import would fail.
"""

from __future__ import annotations

import struct
from decimal import Decimal
from pathlib import Path

import h3
from eii_core.shapes import exact_point
from eii_product.store.protocol import QueryResult, StoreHealth, StoreRefusal
from eii_product.store.registry import Inventory, require_query
from eii_product.tools.make_area import (
    QUERY_NAMES,
    MakeAreaContext,
    RegisteredShape,
    ShapeMiss,
)

RELEASE_ID = "ab" * 32
SHAPE_INSIDE = "cd" * 32
SHAPE_EMPTY = "ef" * 32
SHAPE_CROSS = "12" * 32
SHAPE_OUT = "34" * 32
SHAPE_OTHER = "56" * 32
EDGES = (
    Decimal("-0.09375"),
    Decimal("-0.03125"),
    Decimal("0.03125"),
    Decimal("0.09375"),
)
NO_CELL = (Decimal("0.015625"), Decimal("0.015625"))
ORIGIN = (Decimal("0"), Decimal("0"))
OUTSIDE = (Decimal("1"), Decimal("1"))


def _square(lat0: Decimal, lon0: Decimal, lat1: Decimal, lon1: Decimal) -> tuple:
    return (
        (lat0, lon0),
        (lat0, lon1),
        (lat1, lon1),
        (lat1, lon0),
        (lat0, lon0),
    )


def _municipalities() -> tuple[dict[str, object], ...]:
    rows = []
    index = 0
    for row in range(3):
        for column in range(3):
            if (column, row) == (2, 2):
                continue
            lat0, lat1 = EDGES[row], EDGES[row + 1]
            lon0, lon1 = EDGES[column], EDGES[column + 1]
            outer = _square(lat0, lon0, lat1, lon1)
            holes: tuple = ()
            kind = "polygon"
            code = f"SYN-M{index}"
            if code == "SYN-M6":
                mid_lat = (lat0 + lat1) / 2
                mid_lon = (lon0 + lon1) / 2
                span = (lat1 - lat0) / 8
                holes = (
                    _square(
                        mid_lat - span,
                        mid_lon - span,
                        mid_lat + span,
                        mid_lon + span,
                    ),
                )
            if code == "SYN-M0":
                kind = "multipolygon"
            rows.append({"code": code, "kind": kind, "rings": (outer, *holes)})
            index += 1
    return tuple(rows)


MUNICIPALITIES = _municipalities()


def _cell(latitude: Decimal, longitude: Decimal, resolution: int) -> int:
    return h3.str_to_int(
        h3.latlng_to_cell(float(latitude), float(longitude), resolution)
    )


def _frame() -> tuple[tuple[int, int], ...]:
    origin = _cell(ORIGIN[0], ORIGIN[1], 9)
    excluded = _cell(NO_CELL[0], NO_CELL[1], 9)
    parent = h3.str_to_int(h3.cell_to_parent(h3.int_to_str(origin), 8))
    chosen: dict[int, int] = {}
    for text in h3.grid_disk(h3.int_to_str(origin), 2):
        cell = h3.str_to_int(text)
        if cell != excluded:
            chosen[cell] = 9
    corner = _cell(EDGES[0] + Decimal("0.01"), EDGES[0] + Decimal("0.01"), 9)
    corner_parent = h3.str_to_int(h3.cell_to_parent(h3.int_to_str(corner), 8))
    if corner_parent != parent:
        for text in h3.cell_to_children(h3.int_to_str(corner_parent), 9):
            chosen.pop(h3.str_to_int(text), None)
        chosen[corner_parent] = 8
    return tuple(sorted(chosen.items()))


FRAME = _frame()


def _edge_pin() -> tuple[Decimal, Decimal]:
    from eii_core.shapes import reduce_six

    cell = _cell(ORIGIN[0], ORIGIN[1], 9)
    centre = h3.cell_to_latlng(h3.int_to_str(cell))
    vertex = h3.cell_to_boundary(h3.int_to_str(cell))[0]
    latitude = reduce_six(centre[0] * 0.08 + vertex[0] * 0.92)
    longitude = reduce_six(centre[1] * 0.08 + vertex[1] * 0.92)
    return latitude, longitude


EDGE_PIN = _edge_pin()


def _tiny(latitude: Decimal, longitude: Decimal, span: Decimal) -> tuple:
    return _square(latitude, longitude, latitude + span, longitude + span)


EMPTY_RING = _tiny(Decimal("0.0078125"), Decimal("0.0078125"), Decimal("0.0000001"))
CROSS_RING = _square(Decimal("0"), Decimal("0"), Decimal("0.02"), Decimal("0.02"))
INSIDE_RING = _square(
    Decimal("-0.01"), Decimal("-0.01"), Decimal("0.005"), Decimal("0.005")
)
OUT_RING = _square(Decimal("0.5"), Decimal("0.5"), Decimal("0.6"), Decimal("0.6"))


class MapShapes:
    """Test stand-in for the shape lookup port."""

    def __init__(self) -> None:
        self._rings = {
            SHAPE_INSIDE: INSIDE_RING,
            SHAPE_EMPTY: EMPTY_RING,
            SHAPE_CROSS: CROSS_RING,
            SHAPE_OUT: OUT_RING,
        }
        self._not_yours = {SHAPE_OTHER}

    def find(self, shape_id: str) -> RegisteredShape | ShapeMiss:
        if shape_id in self._not_yours:
            return ShapeMiss("not_yours")
        ring = self._rings.get(shape_id)
        if ring is None:
            return ShapeMiss("unknown")
        return RegisteredShape(tuple((lat, lon) for lat, lon in ring))


class RecordingStore:
    """Invented store. It records query names and serves the fixture rows."""

    engine = "embedded"

    def __init__(self, inventory: Inventory, rows: dict[str, tuple]) -> None:
        self.release_id = RELEASE_ID
        self.inventory = inventory
        self.calls: list[str] = []
        self._rows = rows

    def fetch(self, query: object, params: object) -> QueryResult:
        spec = require_query(self.inventory, query)
        self.calls.append(spec.name)
        rows = self._rows[spec.name]
        if spec.name == "make_area_gazetteer_point":
            key = params["place_key"]
            rows = tuple(row for row in rows if row[0] == key)
        return QueryResult(tuple(item.name for item in spec.returns), rows)

    def ping(self, timeout_s: float) -> StoreHealth:
        del timeout_s
        return StoreHealth(ok=True)

    def close(self) -> None:
        return None


class StandInStore(RecordingStore):
    """Second engine. It is not a PostgresStore and it accepts only a QueryName."""

    engine = "postgres"

    def fetch(self, query: object, params: object) -> QueryResult:
        if type(query) is str:
            raise StoreRefusal("unknown query")
        return super().fetch(query, params)


def geometry_rows() -> dict[str, tuple]:
    places = (
        ("SYN-pin", ORIGIN[1], ORIGIN[0]),
        ("SYN-edge", EDGE_PIN[1], EDGE_PIN[0]),
        ("SYN-nocell", NO_CELL[1], NO_CELL[0]),
        ("SYN-out", OUTSIDE[1], OUTSIDE[0]),
    )
    grid = tuple((cell, resolution) for cell, resolution in FRAME)
    municipalities = tuple((row["code"], _geometry_hex(row)) for row in MUNICIPALITIES)
    return {
        "make_area_grid_cells": grid,
        "make_area_municipalities": municipalities,
        "make_area_gazetteer_point": places,
    }


def box_route(mode: str, minutes: int, latitude, longitude):
    """A tiny ring around the pin. It does not contain a neighbouring cell centre."""
    del mode, minutes
    span = Decimal("0.00001")
    return (
        (latitude, longitude),
        (latitude, longitude + span),
        (latitude + span, longitude + span),
        (latitude + span, longitude),
        (latitude, longitude),
    )


def context(
    inventory: Inventory, store_rows: dict[str, tuple] | None = None, **overrides
):
    del store_rows
    body = {
        "release_id": RELEASE_ID,
        "release_mode": "public_only",
        "playbook_key": None,
        "inventory": inventory,
        "shapes": MapShapes(),
        "tile_folder": None,
        "routing": None,
        "hour_keys": frozenset({"hour_09", "hour_12"}),
        "day_keys": frozenset({"weekday", "friday"}),
    }
    body.update(overrides)
    return MakeAreaContext(**body)


def write_database(path: Path) -> None:
    """Build an invented DuckDB file. The geometry column is filled as WKT."""
    import duckdb

    connection = duckdb.connect(str(path))
    connection.execute(
        "CREATE TABLE grid_cell (cell BIGINT NOT NULL, resolution BIGINT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE municipality "
        "(municipality_code VARCHAR NOT NULL, geometry GEOMETRY)"
    )
    connection.execute(
        "CREATE TABLE gazetteer "
        "(place_key VARCHAR NOT NULL, lon DECIMAL(9,6) NOT NULL, lat DECIMAL(9,6) NOT NULL)"
    )
    connection.executemany("INSERT INTO grid_cell VALUES (?, ?)", list(FRAME))
    for row in MUNICIPALITIES:
        connection.execute(
            "INSERT INTO municipality VALUES (?, ?::GEOMETRY)",
            [row["code"], _wkt(row)],
        )
    for code, lon, lat in geometry_rows()["make_area_gazetteer_point"]:
        connection.execute(
            "INSERT INTO gazetteer VALUES (?, ?, ?)",
            [code, str(lon), str(lat)],
        )
    connection.close()


def _wkt(row: dict[str, object]) -> str:
    rings = row["rings"]
    if row["kind"] == "multipolygon":
        return "MULTIPOLYGON((" + _ring_text(rings[0]) + "))"
    body = ",".join(_ring_text(ring) for ring in rings)
    return f"POLYGON({body})"


def _ring_text(ring) -> str:
    return "(" + ", ".join(f"{lon} {lat}" for lat, lon in ring) + ")"


def _geometry_hex(row: dict[str, object]) -> str:
    rings = row["rings"]
    if row["kind"] == "multipolygon":
        blob = (
            struct.pack("<BI", 1, 6)
            + struct.pack("<I", 1)
            + _polygon_bytes((rings[0],))
        )
    else:
        blob = _polygon_bytes(rings)
    return blob.hex().upper()


def _polygon_bytes(rings) -> bytes:
    body = struct.pack("<BI", 1, 3) + struct.pack("<I", len(rings))
    for ring in rings:
        body += struct.pack("<I", len(ring))
        for lat, lon in ring:
            body += struct.pack("<d", float(lon)) + struct.pack("<d", float(lat))
    return body


def allowed_tables(inventory: Inventory, names: list[str]) -> None:
    """The contracts of the fetched names name only the three public tables."""
    allowed = {"grid_cell", "municipality", "gazetteer"}
    for name in names:
        spec = inventory.get(name)
        assert spec is not None
        for table in spec.tables:
            assert table.name in allowed


__all__ = [
    "CROSS_RING",
    "EDGE_PIN",
    "EMPTY_RING",
    "FRAME",
    "INSIDE_RING",
    "MUNICIPALITIES",
    "NO_CELL",
    "ORIGIN",
    "OUTSIDE",
    "QUERY_NAMES",
    "RELEASE_ID",
    "SHAPE_CROSS",
    "SHAPE_EMPTY",
    "SHAPE_INSIDE",
    "SHAPE_OTHER",
    "SHAPE_OUT",
    "MapShapes",
    "RecordingStore",
    "StandInStore",
    "allowed_tables",
    "context",
    "exact_point",
    "geometry_rows",
    "write_database",
]
