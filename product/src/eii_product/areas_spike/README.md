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

## Directional traffic spike, round one

Task S1-T11 adds `traffic.py`, which consumes the recorded C25 traffic rows,
the road fixture named by their digest and the byte-identical parameter-method
snapshot named by their digest. It imports no custodian code. The reader refuses
incomplete headers, unexpected row fields, mismatched digests and unknown
traffic_hourly keys (day type, hour and summer). Each directed link becomes its own one-way extract way with
its road class and hourly speed. Existing extract calls retain their original
bytes and the earlier area tests and fixtures are unchanged.

The existing engine cache accepts the road document containing each edge's
speed; equal whole-speed vectors therefore share a tile set. Hourly drive areas
carry Simulated and observed; free-flow areas carry Public and observed. Walk
always uses the unscaled graph. The outline is the engine polygon and protected
selection still uses the existing whole-cell snap function.

The parameter snapshots supply whole free-flow speeds and the configured floor.
Both planes refuse fractional speeds, speeds above the named engine maximum,
a fractional floor, a floor below the named engine minimum, and class speeds
below the floor. The custodian rounds the rule speed half-up before flooring,
timing and releasing its ratio. The product reconstructs the same whole speed
and refuses a noncanonical ratio or a speed below the snapshot floor, naming
the file and link. It never raises a released speed itself.

The fixtures use the routing graph's measured metre lengths: worked coordinates
move to preserve the method-card lengths; hourly coordinates stay fixed. Unit
loading in the method uses great-circle distance and lower-node-id ties, with
L-74 R8's fallback sphere because the engine's constant was not identified.
Every whole speed of each parameter class has a ratio round-trip proof.

A screen takes link speeds from `Traffic.link_speed`, link times from
`Traffic.link_minutes`, route times and their breakdown from `Traffic.route`,
and areas from `Traffic.area` only. Routes accept day type and summer, identify
links from the decoded engine shape, and return exact link minutes plus one
junction-seconds line. The total is the exact sum of those parts. L-83 R5 treats
residuals within one printed millisecond per link as zero, rounds larger positive
residuals half-up to milliseconds, and refuses larger negative disagreements.
Only `Traffic.route_for_measurement` exposes the raw engine answer.
Drive-time outlines include turn costs at junctions and are drawn from an
engine grid; measured entry-time deviations are recorded in the task return.

Hours are JSON integers; lookups retain day type, hour and summer. Drive requests
the hour's whole-speed document and walk requests the free-flow document. Shape
matching is fixture-only: straight links and one directed edge per node pair;
real release graphs need their own edge-identity treatment in S5-T09.

L-84 compares exact link sums across the planes and pins junction costs separately.
Day-route residuals after itemised junction seconds must remain within one printed
millisecond per link. The outline test retains its turn-shift check and applies
the absolute bound of forty seconds fixed by L-85. Both recorded rows files match
fresh assignment bytes; the task return records the single regeneration.
Package-local mutation runs exclude cross-plane tests; equivalent survivors
require exact entries in the committed explanation ledger.
The return carries the measurements and checks;
independent review remains with the lead and round two supplies the road page.

Routes return `link_ids`, `link_minutes`, `junction_seconds`, `minutes`, a latitude/longitude `line`, `provenance`, `evidence_status` and `caveat`; areas return `exact`, `cells`, `provenance`, `evidence_status` and `caveat`, with `traffic_simulated` on hourly drives and no caveat at free flow or on walks.
A single-link route refuses a positive discrepancy above its printed resolution because it crosses no junction.
Run local mutation checks with `uv run --locked --group mutation python scripts/mutation.py product/src/eii_product/areas_spike/traffic.py`.
