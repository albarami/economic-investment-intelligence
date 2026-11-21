# Places pipeline (S2-T06)

This package reads local Overture Parquet and builds `pub_place`. It does not
route. An area arrives only through `AreaProvider`: a reviewed point, a mode
(`walk` or `drive`) and a cut-off (5 or 10 minutes) return one polygon with its
method version, graph hash, inputs hash and engine version, or a typed error.
A result flagged `stand_in` is not passing evidence for a flagship decision.

`record_level_source` is the one function that selects the source entry whose
`property` is empty. The licence comes from the attribution table keyed on that
entry's `dataset` token. `sources[].license` is ignored.

Outside a showcase area a place is shown at confidence 0.7000 or above. Inside,
only the latest status `verified_open` is shown. With no area provider every
place is treated as outside and the report says `showcase_areas_pending`.

Every result carries the caveat "Open listings are incomplete". The census
figure is an input that carries its lineage from `est_census`. When that input
is absent the report says `census_comparison_pending` and the caveat holds no
figure. The Arabic line is pending native review.

The places stage runs after the fetch and after the frame's boundary, grid and zones exist, and before the gazetteer resolves its pending entries. A filled gazetteer spec without the places output `places_s2_t06/place_points.json` stays a named frame error. The area producer runs in that same public build after the road file's receipt and before the stage, and only when the manifest is absent or does not agree with that receipt and the requests. A polygon may contain a hole; the hole is outside the area.

The review files read by the stage are `showcase_areas.yaml`, `showcase_gazetteer.yaml`, `flagship_candidates.yaml`, `flagship.yaml`, `places_ovt_attribution.csv`, `places_ovt_categories.csv`, `verified_places.csv` and `arabic_tag.txt`. The lead writes `arabic_tag.txt` after reading the structure of the live places file: one line, the key of the Arabic name in the source's name map. The stage does not run without that file. The build log then reads `stage places arabic_tag_missing`.

The hashes bind an area to its inputs and to the manifest the check saw. The rebuild check is the lead's own call, not part of `./eii build-public`. With the engine group installed, from the repository root: `uv run --locked python -c "from pathlib import Path; from eii_custodian.publicdata.places.area_files import open_pinned_engine, verify_areas; from eii_custodian.publicdata.places_fsq.select import FRAME_BOX; verify_areas(open_pinned_engine(), cache=Path('data/public_cache'), frame_box=(FRAME_BOX.west, FRAME_BOX.south, FRAME_BOX.east, FRAME_BOX.north))"`.

The four concrete files are registry rows under the S2-T06 block. Each file's
receipt is checked before the file is read. Tests use invented Parquet and a
stand-in transport. They do not fetch those files.

Release listings compare only registered `part-NNNNN` child keys against their
recorded whole-file size and ETag. Only JSON children named exactly
`stac-collection` or `stac-part-NNNNN` skip those comparisons; every other
non-part child refuses before any listing request. STAC metadata children keep
their separate HTTPS fetch, receipts and building-completeness checks. The places
stage selects only Parquet entries from either Overture family, so a verified
STAC JSON snapshot cannot enter a place or building reader.
Assembly retains those metadata receipts in its source chain and credits a
gazetteer output only to entries that declare that release table.

The public build samples its injected UTC clock at build start, validates the
UTC timestamp and forwards that date through the frame to `StageConfig` and the
verification loader. Receipt retrieval timestamps continue to sample their own
clock; crossing midnight does not change the build date. Direct callers supply
an explicit date when loading verifications. A header-only `verified_places.csv`
with that date is an empty verification set and writes an empty verification
output. Without the date it still refuses with `bad_check_date`. Empty bytes,
a wrong header, malformed or future dates, duplicate place/date pairs, orphan
places, unknown statuses and refused sources keep their existing refusals;
showcase and flagship checks and pending coverage are unchanged.
