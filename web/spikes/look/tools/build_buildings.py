"""Build the look page's building tiles from an open-buildings file.

Heights: a measured ``height`` is kept; otherwise ``num_floors`` times
``STOREY_METRES``; otherwise an estimate from the footprint area, between
``ESTIMATE_LOW_METRES`` and ``ESTIMATE_HIGH_METRES``. The estimate is stated
in the page's README. Tiles are zooms 13 to 15, written as MBTiles with
Python's sqlite3 and then converted to PMTiles. The archive stays under
``data/`` and is never committed.

The script reads a GeoJSON fixture in tests and the Overture parquet when
run for the page. It prints the elapsed seconds, the tile count and the
archive size, and no row of either file.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
EXTENSIONS = ROOT / "data" / "engine_extensions"
PMTILES = ROOT / "data" / "tools" / "pmtiles" / "pmtiles"
DEFAULT_INPUT = (
    ROOT / "data" / "basemap" / "overture-buildings-qatar-2026-10-21.0.parquet"
)
DEFAULT_OUTPUT = (
    ROOT / "data" / "basemap" / "overture-buildings-qatar-2026-10-21.0.pmtiles"
)

STOREY_METRES = 3.2
ESTIMATE_LOW_METRES = 6.0
ESTIMATE_HIGH_METRES = 36.0
AREA_LOW_M2 = 80.0
AREA_HIGH_M2 = 4000.0
# Web Mercator world, metres (pi times the WGS 84 equatorial radius, and the
# whole circumference). Used only to name the tile a footprint meets.
EARTH_RADIUS_M = 6378137.0
ORIGIN_M = math.pi * EARTH_RADIUS_M
WORLD_M = 2 * ORIGIN_M
BASIS_MEASURED = 1
BASIS_FLOORS = 2
BASIS_FOOTPRINT = 3


def height_of(
    height: float | None, floors: float | None, area_m2: float
) -> tuple[float, int]:
    """Return ``(metres, basis)`` for one footprint.

    Args:
        height: Measured height in metres, or none.
        floors: Floor count, or none.
        area_m2: Footprint area in square metres.

    Returns:
        The height in metres and a basis code: 1 measured, 2 floors, 3 footprint.
    """
    if height is not None and height > 0:
        return (float(height), BASIS_MEASURED)
    if floors is not None and floors > 0:
        return (float(floors) * STOREY_METRES, BASIS_FLOORS)
    span = AREA_HIGH_M2 - AREA_LOW_M2
    if area_m2 <= AREA_LOW_M2:
        fraction = 0.0
    elif area_m2 >= AREA_HIGH_M2:
        fraction = 1.0
    else:
        fraction = (area_m2 - AREA_LOW_M2) / span
    metres = ESTIMATE_LOW_METRES + fraction * (
        ESTIMATE_HIGH_METRES - ESTIMATE_LOW_METRES
    )
    return (metres, BASIS_FOOTPRINT)


def _connect() -> Any:
    import duckdb

    return duckdb.connect(
        config={
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
            "extension_directories": [str(EXTENSIONS)],
        }
    )


def _polygon_wkt(coordinates: list[list[list[float]]]) -> str:
    rings = []
    for ring in coordinates:
        rings.append("(" + ", ".join(f"{x} {y}" for x, y in ring) + ")")
    return "POLYGON (" + ", ".join(rings) + ")"


def _load_geojson(con: Any, path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    con.execute(
        "CREATE TABLE raw (id VARCHAR, geom GEOMETRY, height DOUBLE, num_floors INTEGER)"
    )
    for index, feature in enumerate(document.get("features", [])):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Polygon":
            raise SystemExit(f"fixture feature {index} is not a polygon")
        properties = feature.get("properties") or {}
        con.execute(
            "INSERT INTO raw VALUES (?, ST_GeomFromText(?), ?, ?)",
            [
                str(properties.get("id", index)),
                _polygon_wkt(geometry["coordinates"]),
                properties.get("height"),
                properties.get("num_floors"),
            ],
        )


def _load_parquet(con: Any, path: Path) -> None:
    con.execute(
        """
        CREATE TABLE raw AS
        SELECT id, geometry AS geom, height, num_floors
        FROM read_parquet(?)
        """,
        [str(path)],
    )


def _prepare(con: Any) -> None:
    low = ESTIMATE_LOW_METRES
    high = ESTIMATE_HIGH_METRES
    span = AREA_HIGH_M2 - AREA_LOW_M2
    con.execute(
        f"""
        CREATE TABLE prepared AS
        SELECT
          id,
          ST_Transform(geom, 'EPSG:4326', 'EPSG:3857', always_xy := true) AS geom,
          CASE
            WHEN height IS NOT NULL AND height > 0 THEN height
            WHEN num_floors IS NOT NULL AND num_floors > 0 THEN num_floors * {STOREY_METRES}
            ELSE {low} + least(1.0, greatest(0.0,
              (ST_Area(ST_Transform(geom, 'EPSG:4326', 'EPSG:3857', always_xy := true))
                - {AREA_LOW_M2}) / {span})) * {high - low}
          END AS height,
          CASE
            WHEN height IS NOT NULL AND height > 0 THEN {BASIS_MEASURED}
            WHEN num_floors IS NOT NULL AND num_floors > 0 THEN {BASIS_FLOORS}
            ELSE {BASIS_FOOTPRINT}
          END AS height_basis
        FROM raw
        WHERE geom IS NOT NULL
        """
    )


def _tiles(con: Any, min_zoom: int, max_zoom: int) -> Any:
    return con.execute(
        f"""
        SELECT z, x, y, ST_AsMVT(feature, 'buildings', 4096, 'geom') AS mvt
        FROM (
          SELECT
            z, x, y,
            {{
              'geom': ST_AsMVTGeom(
                geom,
                ST_Extent(ST_TileEnvelope(z::INTEGER, x::INTEGER, y::INTEGER)),
                4096, 64, true
              ),
              'height': height,
              'height_basis': height_basis
            }} AS feature
          FROM (
            SELECT
              geom, height, height_basis, z,
              UNNEST(generate_series(x0, x1)) AS x,
              y0, y1
            FROM (
              SELECT
                geom, height, height_basis, z,
                floor((ST_XMin(geom) + {ORIGIN_M}) / {WORLD_M} * pow(2, z))::INTEGER AS x0,
                floor((ST_XMax(geom) + {ORIGIN_M}) / {WORLD_M} * pow(2, z))::INTEGER AS x1,
                floor(({ORIGIN_M} - ST_YMax(geom)) / {WORLD_M} * pow(2, z))::INTEGER AS y0,
                floor(({ORIGIN_M} - ST_YMin(geom)) / {WORLD_M} * pow(2, z))::INTEGER AS y1
              FROM prepared
              CROSS JOIN range({min_zoom}, {max_zoom + 1}) AS zoom(z)
            )
          )
          CROSS JOIN LATERAL generate_series(y0, y1) AS ys(y)
          WHERE x BETWEEN 0 AND pow(2, z) - 1
            AND y BETWEEN 0 AND pow(2, z) - 1
        ) src
        WHERE feature.geom IS NOT NULL
        GROUP BY z, x, y
        """
    )


def _write_mbtiles(con: Any, path: Path, min_zoom: int, max_zoom: int) -> int:
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(path)
    try:
        database.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
        database.execute(
            """
            CREATE TABLE tiles (
              zoom_level INTEGER,
              tile_column INTEGER,
              tile_row INTEGER,
              tile_data BLOB
            )
            """
        )
        database.executemany(
            "INSERT INTO metadata VALUES (?, ?)",
            [
                ("name", "overture-buildings"),
                ("format", "pbf"),
                ("type", "overlay"),
                ("minzoom", str(min_zoom)),
                ("maxzoom", str(max_zoom)),
                (
                    "json",
                    json.dumps(
                        {
                            "vector_layers": [
                                {
                                    "id": "buildings",
                                    "fields": {
                                        "height": "Number",
                                        "height_basis": "Number",
                                    },
                                }
                            ]
                        }
                    ),
                ),
            ],
        )
        cursor = _tiles(con, min_zoom, max_zoom)
        count = 0
        while True:
            batch = cursor.fetchmany(400)
            if not batch:
                break
            rows = []
            for zoom, column, row, blob in batch:
                if not blob:
                    continue
                tms = (1 << int(zoom)) - 1 - int(row)
                rows.append((int(zoom), int(column), tms, gzip.compress(bytes(blob))))
            database.executemany("INSERT INTO tiles VALUES (?, ?, ?, ?)", rows)
            count += len(rows)
        database.execute(
            """
            CREATE UNIQUE INDEX tile_index
            ON tiles (zoom_level, tile_column, tile_row)
            """
        )
        database.commit()
        return count
    finally:
        database.close()


def build(source: Path, output: Path, min_zoom: int, max_zoom: int) -> dict[str, int]:
    """Write the PMTiles archive and return its tile count and size.

    Args:
        source: A GeoJSON fixture or the Overture parquet.
        output: The PMTiles path, under ``data/``.
        min_zoom: Lowest zoom, inclusive.
        max_zoom: Highest zoom, inclusive.

    Returns:
        Tile count and archive size in bytes.
    """
    if "data" not in output.parts:
        raise SystemExit("the archive must stay under data/")
    started = time.perf_counter()
    con = _connect()
    con.execute("LOAD spatial")
    if source.suffix == ".parquet":
        _load_parquet(con, source)
    else:
        _load_geojson(con, source)
    _prepare(con)
    mbtiles = output.with_suffix(".mbtiles")
    count = _write_mbtiles(con, mbtiles, min_zoom, max_zoom)
    con.close()
    import subprocess

    completed = subprocess.run(
        [str(PMTILES), "convert", str(mbtiles), str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or "pmtiles convert failed")
    elapsed = round(time.perf_counter() - started, 1)
    size = output.stat().st_size
    print(f"tiles {count}")
    print(f"bytes {size}")
    print(f"seconds {elapsed}")
    return {"tiles": count, "bytes": size, "seconds": int(elapsed)}


def main(argv: list[str] | None = None) -> int:
    """Run the build from the command line.

    Args:
        argv: Arguments, or the process arguments when omitted.

    Returns:
        Exit status.
    """
    parser = argparse.ArgumentParser(
        description="Build building tiles for the look page"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-zoom", type=int, default=13)
    parser.add_argument("--max-zoom", type=int, default=15)
    args = parser.parse_args(argv)
    if not args.input.is_file():
        raise SystemExit(f"missing buildings file: {args.input}")
    build(args.input, args.output, args.min_zoom, args.max_zoom)
    return 0


if __name__ == "__main__":
    sys.exit(main())
