# 0077 — Overture footprints as the national building table

| | |
|---|---|
| Status | Accepted, 2026-11-21; the owner's decision of 2026-11-21 05:32 |
| Date | 2026-11-20 |
| Decided by | The owner, 2026-11-21 05:32, on the lead's S2 gate question for item C-20 |
| Scope | S2-T20 national building producer; task-owned document under rule 33 and lead ruling L-1285 |

## Decision

1. The pinned Overture buildings release supplies the canonical building inventory,
   using the three concrete `bldg_ovt` parts of PUB-17. The national municipality
   union selects each unrounded point on surface; the full footprint is retained.
   Protomaps supplies the other basemap layers. Its buildings layer is hidden in
   every view drawing PUB-106 heights, preventing duplicate extrusion. IDs are
   scoped to the pinned release, with no cross-release continuity promise.
2. `./eii build-public` produces the building table and its companion manifest in
   its shared frame step before heights. This producer is not a separate script
   or command. Every required part must be registered, unskipped, explicitly
   pinned and verified through its receipt. STAC collection and item snapshots
   use reviewed `https_file` registry rows and the existing transport. Their
   licence fields follow the same release's `bldg_ovt` registry row
   exactly; `commit_allowed` remains false. Unknown
   item URLs remain unconfirmed, never guessed. An unregistered linked item or
   incomplete part set refuses national completeness. National boundary bounds
   must fit the PUB-17 frame box (proposed amendment: [decision 0089](0089-reviewed-outside-boundary-parts-and-the-required-building-part-set.md) admits
   reviewed wholly-outside boundary parts and states the required part set as a
   rule; owner acceptance owed). Counts distinguish outside-box rows from
   in-box rows outside the dated boundary; the latter await lead review for
   possible reclaimed land and a boundary amendment.
3. `height` and `num_floors` mapping is off. Both output slots remain null with
   reason `recorded_field_unconfirmed`; counts preserve absent, present, usable,
   unusable and present-unmapped source values. `optional_fields` counts kept
   table rows; `optional_fields_all_read` separately counts every source row
   before spatial and footprint exclusions. `optional_field_scope` names both
   populations. Activation requires the official
   schema reading, a committed closed list of recorded-origin datasets for each
   property, and live counts, as finding F4 requires. No estimate or default is
   recorded height. C47's whole-table numeric refusals remain unchanged; any
   future nulling of unusable mapped values needs another decision.
4. Invalid, empty, nonpolygonal or undecodable footprints are excluded and listed
   by source ID and part with `invalid_footprint`; they are never repaired.
   `is_underground=true` is excluded with reason `underground`. Unknown schema,
   CRS and malformed flags refuse. Only valid selected footprints enter the
   table and the rendered set. Nonzero exclusions require lead review. Every
   refresh rechecks all committed landmark building IDs; an absent binding
   refuses `landmark_building_absent`. The pending landmark marker clears only
   with the first cited entries bound to the pinned release.
5. The manifest preserves dataset and contributor notices, receipt and body
   hashes, boundary lineage, method version, per-part counts and sorted kept-ID
   hashes. Counts by record-level footprint dataset support the credits shown
   while buildings are drawn; unknown contributors require attribution review.
   Overture, ODbL and the contributing datasets' notices remain visible with the
   building layer under FE-139. No frontend implementation is claimed here.

## Amended anchors

- Document 04: `bldg_ovt` source title, source/use rows (Use and Release table),
  PUB-17 purpose and completeness check, PUB-106 inventory and stale B10 skip
  sentence, and PUB-110 attribution while buildings are drawn.
- Document 07: C47 Inputs, canonical footprints and counted unmapped fields.
- Document 10: section 6 Buildings and Buildings of all of Qatar rows,
  “Extruded buildings”, FE-143; section 7 Attribution and FE-139 contributor
  credits; section 14 asset-pipeline producer location, new Building table row
  and corrected Landmark heights row (cited recorded heights keyed by building ID).
- The source registry's matching titles and reviewed STAC rows; the heights and frame module documentation; TASKS.md S2-T20 delivery status.

## Evidence and remaining confirmation

The offline implementation uses invented Parquet fixtures only. The supplied
lead reading of the official building schema confirms optional positive `height`
in metres, positive whole `num_floors`, `is_underground`, Polygon/MultiPolygon
geometry and `sources` entries. Source:
<https://docs.overturemaps.org/schema/reference/buildings/building/>, read by the
lead 2026-11-20, schema v2.0.0. That reading supplies no recorded-origin allowlist.
Live schema/release metadata, all STAC item URLs, national boundary coverage,
exclusion review, counts and repeatability remain the lead's work. This proposed
record claims neither owner acceptance, independent build approval nor live
national coverage.

## Acceptance

The owner accepted this decision as written on 2026-11-21 at 05:32, in answer to the
S2 gate question on item C-20 (lead ruling L-1319). The acceptance adds nothing to the
decision. The live evidence named above (release metadata, STAC item addresses,
national coverage, exclusion review, counts and repeatability) is still owed before
gate item C-20 closes.
