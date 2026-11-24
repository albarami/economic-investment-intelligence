# Building tiles for the look page

`build_buildings.py` reads an open-buildings file and writes a PMTiles archive under `data/basemap/`. The archive is derived from the footprints, stays under `data/`, and is never committed.

Heights, in metres, carried on each footprint as `height` with `height_basis` (1 measured, 2 floors, 3 footprint):

- a `height` above zero is kept
- otherwise `num_floors` times a storey of 3.2 metres
- otherwise an estimate from the footprint area: 6 metres at 80 square metres and below, 36 metres at 4,000 square metres and above, and a straight line between those areas

Zooms 13 to 15. MBTiles is written with Python's sqlite3, then `data/tools/pmtiles/pmtiles convert` writes the PMTiles archive. The page serves it at `/basemap/buildings.pmtiles` with HTTP range requests.

```
uv run --locked python web/spikes/look/tools/build_buildings.py
```

Tests use an invented GeoJSON fixture, never the real file: `web/spikes/look/tests/buildings.node-test.mjs` and `python -m unittest test_build_buildings.py` from this folder.
