# heights

The heights step of `./eii build-public` (task S2-T20, PUB-106, method card
C47, requirement MTH-125).

Every building of the basemap building table
(`data/assets/buildings/buildings.geojson`) receives a height in the order of
decision 0023 item A2:

Under decision 0077, that table is the pinned Overture inventory built
inside the shared public-frame composition. Before reading it, heights checks
its output hash, method version and source chain against the current run's
part and STAC pins and boundary snapshot, including their verified receipt
hashes. The height manifest's `source_chain` gives the building manifest's
relative path and hash. A missing table remains `building_table_absent`;
a missing manifest, stale pin, changed boundary or altered table refuses.
Overture height and floor mappings stay off, counted as
`recorded_field_unconfirmed`; they are not silently treated as absent source
values. The hierarchy below remains unchanged.

1. `recorded` — the building's own recorded height (`Public`, observed),
   including heights from the committed hand list
   (`custodian/publicdata/review/landmark_heights.yaml`), each with its cited
   public page, publisher and retrieval date in the asset manifest. The list
   is empty and `pending` until the basemap building ids are confirmed. A
   cited page must name a registry row with the same publisher and licence
   basis, and resolve through the snapshot verifier to cached page bytes whose
   receipt names that row's source and key, the cited URL, publisher, licence
   basis, retrieval day and page hash; any other case refuses with
   `landmark_heights_citation` and a named detail, and the step writes nothing;
2. `floor_count` — the floor count times the stated storey height;
3. `3dglobfp` — the open heights of 3D-GloBFP, `bldg_3dglobfp`
   (CC BY 4.0, credit "Che et al. 2024");
4. `wsf3d` — the WSF 3D 90 m cell mean, `bldg_wsf3d`;
5. `none` — no height; the row carries a reason, never the numeral 0.

Every fallback height is `Public`, inferred. Every output row keeps its
`height_source` so an estimate is never mistaken for a recorded value.

## Outputs

Written under `data/assets/heights/` (uncommitted):

- `heights.json` — one row per building: `building_id`, `height_m`,
  `height_source`, `footprint_source_id`, `reason`;
- `manifest.heights.json` — the deterministic manifest: input and output file
  hashes, retrieval metadata, licences and basis, terms, credits, the matching
  rules, the source order, the counts per source, the `none` reasons, the tied-height count, the error
  block of each fallback against the recorded heights, the storey-height
  assumption, the label `Heights are estimates.`, the `landmark_heights`
  citation block and the `gba_calibration` block (GlobalBuildingAtlas measured
  against recorded heights overall and for the declared class `all`, with `order_status`
  `pending_owner_decision` until OI-310). Both files are sorted and byte-stable:
  identical inputs give identical bytes (FE-98).

The error block of each fallback holds `count`, `mean_signed_error_m`
(fallback minus recorded), `mean_absolute_error_m` and
`median_absolute_error_m`; a fallback with no comparable recorded-height pairs
has count 0 and reason `no_pairs`. The same numbers are computed by
`eii_core.calc.building_heights` and shown behind "More evidence" (FE-52).

## Rules file

`custodian/publicdata/height_rules.yaml` holds the storey height as the quoted
text `"3.0"` with the label `ASSUMPTION` (the lead's stated assumption of
2026-11-14; the owner replaces it). It is parsed to `Decimal` — never a float —
and no Python file may repeat the literal. The same file declares the structure
each height source must match: `bldg_3dglobfp` is `shapefile_zip` with the
field `Height`; `bldg_gba` is `geoparquet` with the DOUBLE field `height`,
WKB Polygon geometry, the four-DOUBLE `bbox` struct and CRS84 (longitude then
latitude). Its declared nodata is `-999`; the publisher's meaning for that
value remains unconfirmed. There is no published class: every kept row gets
the single declared class `all` (`class_basis: none_published`), never a class
inferred from the source or region label. It remains calibration only, outside
the PUB-106 order pending OI-310. `bldg_wsf3d` is a `GTiff` band
`1` of the declared sample type `int16` with nodata `-32767` and scale
`"0.1"`, all in metres; the shapefile and raster use EPSG:4326; the reader refuses another driver or
another sample type by name (`structure_mismatch`); the value `to be confirmed`
marks a source whose structure is not yet confirmed and that source is absent
with reason `structure_unconfirmed`, never a failure.

## Sources

The height and calibration sources are the registry rows of
`custodian/publicdata/sources.yaml`: `bldg_3dglobfp/1636` and
`bldg_3dglobfp/1639`, the two tile files holding Qatar (CC BY 4.0, credit
"Che et al. 2024", from `ndownloader.figshare.com`); `bldg_wsf3d`, the
global file of `download.geoservice.dlr.de` (CC BY 4.0, credit "Copyright DLR
(year of production)"); and `bldg_gba/e050_n25_e055_n20` and
`bldg_gba/e050_n30_e055_n25`, the two GlobalBuildingAtlas GeoParquet mirror
tiles from `data.source.coop` (CC BY-NC 4.0 with a reported ODbL polygon
component, calibration only; exact component notice wording remains pending).
The original dataset citation is https://github.com/zhu-xlab/GlobalBuildingAtlas/
and the hosted conversion is https://source.coop/tge-labs/globalbuildingatlas-lod1.
Each GBA key uses the existing large-file fetch path: fixed chunks are hashed
and written to a staged file, never joined into a whole response body. Redirect
hosts stay checked against PUB-03; none is newly admitted. Both keys need their
own reviewed snapshot selection after the lead's first live fetch.

Only a verified local path enters DuckDB with GeoParquet conversion off and
no spatial extension. The schema is checked even for an empty building table.
Only rows with a source bbox intersecting the building table bounds are read;
`bounds is None` reads no rows. **Stated limit:** an incorrect source bbox can
omit an intersecting footprint; this path cannot check that bbox against WKB.
Rows with a NULL bbox struct or any NULL bbox child are counted as `bbox_null`
per file and in source and calibration totals, outside the in-bounds partition,
even when the building table has no bounds; their geometry is not read.
Rows are ordered by `file_row_number`. Heights are selected as VARCHAR and
parsed as Decimal; no Python float conversion or early rounding occurs.

Each bounded row is kept or counted exactly once, in this fixed precedence:
`geometry_null`, `geometry_empty`, `geometry_invalid`, `height_null`,
`height_nodata`, `height_non_finite`, `height_non_positive`. A malformed WKB or
a non-Polygon row withdraws the file; excluded polygons are never repaired.
Each file's `read_counts`, `sources.bldg_gba` totals and the calibration's
`read_counts` expose `rows_in_bounds`, `rows_kept` and all exclusion counters.
Core validates the complete row partition before summing it for the manifest.

Each 3D-GloBFP file is one flat zip of exactly five
members — `cpg`, `dbf`, `prj`, `shp`, `shx` — of one stem: the `cpg` text must
read `ISO-8859-1`, the `prj` well-known text must resolve to EPSG:4326 through
`to_epsg`, and the named `Height` field is read as the `dbf` record's own
fixed-width text and parsed to `Decimal`, never through a float. The WSF 3D
file's hash is computed in pieces, and only the window of cells over the
building table's bounds, grown one cell on each side, is read. No fetched byte
is committed (FE-95). A source absent from the cache is `not_fetched`; a
switched-off row is refused; a row the fetch reported is read and its hash,
receipt, terms and declared structure are checked before any row is parsed.

## Matching

3D-GloBFP candidate footprints are those holding the building's
`point_on_surface` (never the centroid) and overlapping its footprint; the
largest overlap wins, ties take the lowest file name then the lowest row
index, and a building whose winning overlap ties a different-height candidate
is counted in the manifest's `tied_height_buildings`. The spatial index over
all footprints of all files is built once per run. WSF 3D uses the cell
holding the same representative point, its stored value scaled by the
declared scale in `eii_core.calc.building_heights`; a no-data cell or a point
outside the raster gives no value, and several files each giving a usable
value at one point refuse the build (`wsf3d_overlap`).


GBA calibration reuses this spatial index as a deterministic bbox prefilter.
An exhaustive-fixture comparison proves the same winners, tie order and
counters. Core reports `recorded_buildings`, `matched`, `no_footprint`,
`unusable_height`, `recorded_height_unusable`, `tied_height` and `shared_footprint`.
The primary outcomes partition every building with a recorded height: no winner
gives `no_footprint`; an unusable winner height gives `unusable_height`; then an
unusable recorded height gives `recorded_height_unusable`; otherwise `matched`.
Core refuses an incomplete partition with `gba match accounting`; calibration
and the manifest carry these same counts. Absent recorded heights are skipped.
`no_footprint` means
no candidate covers the point; `largest_overlap` accepts zero-area candidates,
so there is no separate `no_overlap` outcome. `shared_footprint` counts distinct
(file, row) winners used by more than one recorded building, including a winner
whose height later rounds to no usable value. `matched` equals `overall.count`;
sub-precision recorded heights are omitted from error pairs as before. No pairs
gives `no_pairs`, with the declared `all` class and no invented metric.

The offline implementation uses the pinned DuckDB series and retreat series in
`pins.toml`; official readings are document 04's public-source chain and
`docs/REFERENCE_NOTES.md`, DuckDB P13 (Parquet), P14 (metadata), P15 / S33
(conversion setting) and P11 (ordering). Supplied footer research is dated
2026-11-22; no real tile is needed by a test. The live measured error, landmark
hand list and owner's order placement remain open (S2-T20, C-20, OI-310).
