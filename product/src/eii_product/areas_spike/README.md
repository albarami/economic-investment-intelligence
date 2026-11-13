# Synthetic area spike

Task S1-T03 exercises fixture-only area conversion under ARC-88, BE-82,
PRV-10 and SYN-53. This is not the production `make_area` implementation.

The road network, speed factors and frame in `product/tests/fixtures/areas_spike/`
are invented and describe no named place. The package's `extract.generate` function
encodes the synthetic roads into an OSM PBF extract; no downloaded geography,
database or external routing request is used.

## Routing mechanism and limits

The primary engine is pyvalhalla at the exact root engine-group pin.
For each distinct hour factor, the generator multiplies the fixture edge drive
speeds by that factor. The bundled `valhalla_build_tiles` command builds tiles
in a standard-library temporary directory, then exits. A cached in-process Actor
uses those tiles. Equal factors reuse the same tiles. Walk uses unscaled tiles
and the fixture walking speed, so the hour table does not change its polygon.
The empty network is refused before the builder runs.

The returned outline is the engine's own polygon ring, with longitude/latitude
converted to the spike's latitude/longitude convention. It is not replaced by a
convex hull or by snapped-cell geometry. The engine gives a single road a polygon.
Named invented road points inside and outside the fixture cutoff test visible
reach, independently of the retired graph's travel-time attributes.

This spike does not prove routing on a real road network, use of the manifest's
release graph, or performance and memory use with many tile sets. The cached
Actors and temporary tiles last for the process; clearing the cache permits fresh
builds. SYN-53's slice decision record remains the lead's work.

## Shapes and snapping

A drawn polygon keeps its starting vertex, removes repeated closing vertices,
and becomes a closed counterclockwise ring. A radius retains an analytical
circle centred on the requested point. Its protected-cell selection uses
the pin cell's centre, as BE-82 requires.

H3 `h3shape_to_cells` uses centre containment. The spike applies it at each
frame resolution and intersects its result with the frame. Returned cells
are whole frame cells, sorted, without compaction into parent outlines.
An empty snap raises an error. The mixed frame has a finer invented core
and a coarser surround. Production catchment resolution and release-unit
snapping remain the later area-tool task's work under BE-84.

## Verification and environment

Install the root engine group before running the product tests. Shapely is a
direct engine-group dependency used only for independent polygon assertions in
tests; it brings NumPy through the lock. OSMnx and NetworkX are not installed.
The member manifest remains unchanged. H3 ships no typing files in the installed
distribution, so `product/src/h3.pyi` supplies the minimal used signatures.
pyvalhalla and DuckDB ship their own types; neither has a local replacement stub.
The pyvalhalla distribution lacks a `py.typed` marker, so mypy explicitly follows
that package's imports to analyze its shipped types without suppressing errors.

Run `uv run --locked python -m pytest product/tests -v -p no:cacheprovider`.
The no-server test finishes tile preparation before blocking socket constructors,
connections and subprocess creation during all walk and drive routing calls.
The recorded `expected_outputs.json` was recorded once from the primary engine
in this round, explicitly replacing the retreat output under the lead's ruling.
It is a regression fixture, not external ground truth. The determinism test
clears the Actor cache between fresh computations and compares both with it.

## Reference provenance

Earlier-round documentation readings dated 2026-11-13 recorded these official
pages. This round's network allowance covers only lock and sync, so these pages
were not fetched again; installed binding docstrings and distribution typing
metadata were inspected locally on the same date.

- [Valhalla Python bindings](https://valhalla.github.io/valhalla/bindings/python/)
- [Valhalla isochrone API](https://valhalla.github.io/valhalla/api/isochrone/)
- [H3 API reference](https://uber.github.io/h3-py/api_verbose.html)

The local Actor docstring describes configuration files and in-process actions;
the H3 docstring states centre containment and no guaranteed output order.
