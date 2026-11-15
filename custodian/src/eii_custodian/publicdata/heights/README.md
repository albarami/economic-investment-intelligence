# heights

The heights step of `./eii build-public` (task S2-T20, PUB-106, method card
C42, requirement MTH-123).

Every building of the basemap building table
(`data/assets/buildings/buildings.geojson`) receives a height in the order of
decision 0023 item A2:

1. `recorded` — the building's own recorded height (`Public`, observed);
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
  rules, the source order, the counts per source, the `none` reasons, the error
  block of each fallback against the recorded heights, the storey-height
  assumption, and the label `Heights are estimates.` Both files are sorted and
  byte-stable: identical inputs give identical bytes (FE-98).

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
each height source must match; the value `to be confirmed` marks a source
whose structure is not yet confirmed and that source is absent with reason
`structure_unconfirmed`, never a failure.

## Sources

The two height sources are the registry rows `bldg_3dglobfp` and `bldg_wsf3d`
of `custodian/publicdata/sources.yaml`. Until a direct URL is confirmed each
row holds `skip_reason: "direct_url_unconfirmed"`, no host joins the
allow-list, and no fetched byte is committed (FE-95). A source absent from the
cache is `not_fetched`; a switched-off row is refused; a row the fetch
reported is read and its hash, receipt, terms and declared structure are
checked before any row is parsed.

## Matching

3D-GloBFP candidate footprints are those holding the building's
`point_on_surface` (never the centroid) and overlapping its footprint; the
largest overlap wins, ties take the lowest file name then the lowest row
index. WSF 3D uses the 90 m cell holding the same representative point; a
no-data cell or a point outside the raster gives no value.
