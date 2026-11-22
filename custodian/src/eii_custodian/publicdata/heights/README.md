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
  against recorded heights overall and by class, with `order_status`
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
field `Height`; `bldg_gba` is `shapefile_zip` with its height and class fields
still `to be confirmed` on the registry row (calibration only, not in the
PUB-106 order pending OI-310), and fixtures carry `SYN_class` while the
production reader refuses another schema by name; `bldg_wsf3d` is a `GTiff` band
`1` of the declared sample type `int16` with nodata `-32767` and scale
`"0.1"`, both in metres and EPSG:4326; the reader refuses another driver or
another sample type by name (`structure_mismatch`); the value `to be confirmed`
marks a source whose structure is not yet confirmed and that source is absent
with reason `structure_unconfirmed`, never a failure.

## Sources

The height and calibration sources are the registry rows of
`custodian/publicdata/sources.yaml`: `bldg_3dglobfp/1636` and
`bldg_3dglobfp/1639`, the two tile files holding Qatar (CC BY 4.0, credit
"Che et al. 2024", from `ndownloader.figshare.com`); `bldg_wsf3d`, the
global file of `download.geoservice.dlr.de` (CC BY 4.0, credit "Copyright DLR
(year of production)"); and `bldg_gba`, the GlobalBuildingAtlas height tiles
from `data.source.coop` (CC BY-NC 4.0, terms recorded, calibration only). Each
3D-GloBFP or GBA file is one flat zip of exactly five
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

## Reviewed landmark cache record (S2-P53)

Under proposed decision 0093, the production list is one local, independently
reviewed `review/landmark_heights.yaml` beneath the public cache. The old
committed file remains only an empty format sample; it is used as pending
when the local record does not exist. No source row is copied into that sample.
Every publisher uses the same loader. Each entry requires `height_kind` from
`roof` or `architectural`; the manifest retains it and counts entries by kind.
The `gba_calibration` block records `landmark_count`, `by_kind` and `pending`.
An empty list with no pending string reports `landmark_list_empty`. Clearing
pending requires a nonempty list that passes loading and receipt verification.
This does not decide the GBA order or claim C-20.

The lead calls `landmark_select.select_landmarks` with the research document's
`landmarks` sequence. The candidate shape is the primary page plus optional
`second_page` and each page's `additional_heights`. The subject contract is
`subject_kind: completed_highrise_building` with a nonempty `completed` field,
as confirmed by the lead for S2-P53 round 2. The subject code must match exactly;
compound values with qualifiers and `completed high-rise` are not admitted.
Selection checks building status, the page's roof/architectural label, literal
metric token/excerpt agreement, then numeric-token conflicts of the same kind
across all pages and their additional heights. It accepts `m`, `metre`,
`metres`, `meter`, `meters` case-insensitively, without conversion. Word-valued
heights are not numeric disagreements; different precision tokens disagree.
One page suffices. Counts use the closed reasons `not_building`,
`kind_not_admitted`, `excerpt_mismatch`, `same_kind_disagreement`, plus
`admitted`. Licence admission is absent.

`landmark_tie.tie_landmarks` takes admitted candidates, reviewed national
landmark points in CRS84, and the canonical Overture building inventory.
Names and aliases match by exact equality after the existing award-name
normalizer. Aliases stay local. Footprints cover points, including boundaries.
The outcomes are `tied`, `no_point`, `several_points`, `point_in_no_building`,
`point_in_several_buildings`, `point_claimed_twice`, `building_claimed_twice`.
All claimants of a duplicate point or building are withheld. There is no manual
fallback. Output heights and excerpts come from the admitted page tokens;
the page hash and date come from its verified snapshot and receipt.
`write_landmark_heights` serializes the result to a temporary local YAML,
loads and verifies it, then atomically replaces the single cache record.
Independent review of that record remains lead-owned.

Citation acquisition reuses `public_page` and the version-two
`citation_snapshot` declaration: empty shape, columns and period fields,
no release tables, zero rows and `commit_allowed: false`. Each publisher has
one source ID and each page a distinct `source_id/page-key`; declarations
are keyed by that complete key. The normal fetch entry publishes a parsed
envelope and `inputs/input-0` snapshot using its existing receipt, archive,
byte bound, obstacle, exact-URL and host checks. The original `commit_refused`
guard remains intact. Ordinary HTTPS requests identify the generic client
without a contact detail. A citation excerpt must occur in the snapshot's
visible text after HTML unescaping and ASCII-whitespace collapse; non-breaking
spaces remain significant. An absent excerpt refuses
`landmark_heights_citation` / `excerpt_absent`; an unrelated height or kind
refuses `height_excerpt_mismatch`.

Malformed citation envelopes, including invalid UTF-8 and empty inputs, refuse
`landmark_heights_citation` / `page_snapshot`. Citation reads reuse the page
archive's constrained cache directory helper; absolute keys, parent traversal
and symlinked entry directories refuse with that same closed reason.

No live publisher/page metadata or host is installed by this offline task:
the brief forbids committing researched names, URLs and hosts. The lead must
resolve that constraint before the separate reviewed registry and PUB-03 host
admission. Invented acquisition tests establish the path, not live admission.

The cache loader retains the validated bytes, rows and pending status together
in an immutable `LandmarkRecord`. The height manifest hashes those same bytes;
it does not reread a mutable review file after using its heights. Duplicate
YAML keys are refused as `landmark_heights` / `duplicate_key` rather than
silently replacing a cited value.
