"""What public-only make_area reads. Invented rows only."""

from __future__ import annotations

from pathlib import Path

import pytest
from product.tests.make_area_support import (
    MUNICIPALITIES,
    NO_CELL,
    ORIGIN,
    SHAPE_EMPTY,
    SHAPE_INSIDE,
    RecordingStore,
    allowed_tables,
    box_route,
    context,
    geometry_rows,
    write_database,
)

from eii_core.shapes import GEOMETRY_REFUSED, GeometryTextError
from eii_product.store.embedded import EmbeddedStore
from eii_product.store.lint import lint_inventory
from eii_product.store.protocol import StoreRefusal
from eii_product.store.registry import PACKAGED, load_inventory, packaged_sql_dir
from eii_product.tools.make_area import make_area, read_land


def _kinds() -> tuple[dict, ...]:
    pin = {
        "latitude": float(ORIGIN[0]),
        "longitude": float(ORIGIN[1]),
    }
    return (
        {**pin, "mode": "distance", "cutoff": 250},
        {**pin, "mode": "walk", "cutoff": 5},
        {**pin, "mode": "drive", "cutoff": 10},
        {"shape_id": SHAPE_INSIDE},
        {"shape_id": SHAPE_EMPTY},
        {
            "latitude": float(NO_CELL[0]),
            "longitude": float(NO_CELL[1]),
            "mode": "distance",
            "cutoff": 1000,
        },
        {
            "latitude": float(NO_CELL[0]),
            "longitude": float(NO_CELL[1]),
            "mode": "walk",
            "cutoff": 15,
        },
        {
            "latitude": float(NO_CELL[0]),
            "longitude": float(NO_CELL[1]),
            "mode": "drive",
            "cutoff": 15,
        },
    )


def test_public_only_reads_no_unit_protected_or_simulated_table() -> None:
    for request in _kinds():
        store = RecordingStore(PACKAGED, geometry_rows())
        make_area(store, request, context(PACKAGED, routing=box_route))
        allowed_tables(PACKAGED, store.calls)

    def variant(names: list[str], inventory) -> None:
        allowed_tables(inventory, names)

    folder = Path(packaged_sql_dir())
    assert variant([], PACKAGED) is None
    for table in ("release_unit", "syn_simulated"):
        with pytest.raises(AssertionError):
            _forbidden_fetch(folder, table)


def test_tool_cannot_pass_sql() -> None:
    store = RecordingStore(PACKAGED, geometry_rows())
    with pytest.raises(StoreRefusal, match="unknown query"):
        store.fetch("SELECT * FROM grid_cell", {})
    with pytest.raises(StoreRefusal, match="unknown query"):
        store.fetch("make_area_grid_cells", {})
    assert store.calls == []


def test_unknown_gazetteer_key_is_invalid_argument() -> None:
    store = RecordingStore(PACKAGED, geometry_rows())
    result = make_area(
        store,
        {"place_key": "SYN-missing", "mode": "walk", "cutoff": 5},
        context(PACKAGED, routing=box_route),
    )
    assert result.status == "INVALID_ARGUMENT"
    assert result.payload is None


def test_land_area_is_read_through_the_named_query_as_geometry_text(
    tmp_path: Path,
) -> None:
    path = tmp_path / "land.duckdb"
    write_database(path)
    store = EmbeddedStore(path, "ab" * 32, PACKAGED)
    try:
        polygons = read_land(store, PACKAGED)
    finally:
        store.close()
    assert len(polygons) == 8
    for row, polygon in zip(MUNICIPALITIES, polygons, strict=True):
        assert len(polygon) == len(row["rings"])
        for actual, expected in zip(polygon, row["rings"], strict=True):
            assert len(actual) == len(expected)
            for got, want in zip(actual, expected, strict=True):
                assert got[0] == want[0] or _same(got[0], want[0])
                assert got[1] == want[1] or _same(got[1], want[1])
    folder = tmp_path / "wrapped"
    _write_wrapped(folder)
    with pytest.raises(StoreRefusal, match="forbidden construct"):
        lint_inventory(load_inventory(folder))
    lower = RecordingStore(PACKAGED, geometry_rows())
    text = lower._rows["make_area_municipalities"][0][1]
    lower._rows["make_area_municipalities"] = (
        (MUNICIPALITIES[0]["code"], text.lower()),
    )
    with pytest.raises(GeometryTextError, match=GEOMETRY_REFUSED):
        read_land(lower, PACKAGED)


def _same(got, want) -> bool:
    from decimal import Decimal
    from fractions import Fraction

    return Fraction(got) == Fraction(Decimal(str(want))) or got == Fraction(
        Decimal(want)
    )


def _forbidden_fetch(source: Path, table: str) -> None:
    """The variant tool attempts the forbidden fetch. The helper refuses it."""
    inventory = _inventory_with(source, table)
    rows = geometry_rows()
    rows["bad_read"] = ()

    def variant(store, request, ctx):
        store.fetch(ctx.inventory.lookup("bad_read"), {})
        return make_area(store, request, ctx)

    store = RecordingStore(inventory, rows)
    variant(store, _kinds()[0], context(inventory, routing=box_route))
    allowed_tables(inventory, store.calls)


def _inventory_with(source: Path, table: str):
    import shutil
    import tempfile

    folder = Path(tempfile.mkdtemp())
    for path in source.iterdir():
        if path.is_file():
            shutil.copy(path, folder / path.name)
    name = "bad_read"
    (folder / f"{name}.sql").write_text(
        f"-- name: {name}\n-- params:\n-- returns: label text\n-- order: label\n"
        "SELECT t.label\n"
        f"FROM {table} AS t\n"
        "ORDER BY t.label ASC NULLS LAST\n",
        encoding="utf-8",
    )
    (folder / f"{name}.toml").write_text(
        f'[[tables]]\nname = "{table}"\nanchor = "invented"\n'
        'key = ["label"]\n\n[[tables.columns]]\nname = "label"\n'
        'type = "string"\nnullable = false\n',
        encoding="utf-8",
    )
    return load_inventory(folder)


def _write_wrapped(folder: Path) -> None:
    folder.mkdir()
    (folder / "__init__.py").write_text('"""invented"""\n', encoding="utf-8")
    (folder / "wrapped.sql").write_text(
        "-- name: wrapped\n-- params:\n"
        "-- returns: municipality_code text, geometry text\n"
        "-- order: municipality_code\n"
        "SELECT m.municipality_code, ST_AsText(m.geometry) AS geometry\n"
        "FROM municipality AS m\n"
        "ORDER BY m.municipality_code ASC NULLS LAST\n",
        encoding="utf-8",
    )
    (folder / "wrapped.toml").write_text(
        '[[tables]]\nname = "municipality"\nanchor = "invented"\n'
        'key = ["municipality_code"]\n\n[[tables.columns]]\n'
        'name = "municipality_code"\ntype = "string"\nnullable = false\n\n'
        '[[tables.columns]]\nname = "geometry"\ntype = "geometry"\nnullable = false\n',
        encoding="utf-8",
    )
