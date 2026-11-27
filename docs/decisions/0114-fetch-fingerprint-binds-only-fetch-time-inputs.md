# Decision 0114: Fetch fingerprints bind only fetch-time inputs

| | |
|---|---|
| Status | Accepted by the owner, 2026-11-27 ("Accept 0114 and 0115", relayed by the advisor in note owner-relayed-20261127-0822, ruling L-2288), on the different-maker review that stands on main `bc9bb749`: R60-REC.rv2 (Moonshot Kimi through Factory Droid, review mode, a maker other than the builder) APPROVED this record's text (blob `ea81e14c`) with no rejecting finding |
| Date | 2026-11-24 |
| Owner | The owner |
| Amends | Decision 0081 items 2 and 4; AGENTS.md and CLAUDE.md rule 44; document 13 command table; document 12 fetch-input test map; README resume description. |
| Purpose | Preserve reuse after proven post-loop input edits while keeping every possible fetch-time input bound. |
| Read first | Decision 0081 items 2 to 5; decision 0084 items 4 and 5; decision 0094's record shape; document 12, Fetch input partition; `fetch/fingerprint.py`, `fetch/build.py` and `fetch/resume.py` under `custodian/src/eii_custodian/publicdata/`. |

## Context

Decision 0081 item 2 binds every tracked publicdata file except the registry
bytes, whose constructed rows are bound per entry. That also binds files whose
readers execute only after the fetch loop or in separate tooling. Editing those
files invalidates otherwise reusable acquisitions. The production fetch-only
path returns before the later assembly stages; those stages still rerun.

A comment edit of `fingerprint.py` changes the machinery digest itself. This
change must therefore precede the acquisition whose later reuse it is intended
to preserve. The builder's before/after hashes are in PROGRESS.md, S2-FPR b1.
No acquisition timing or real-cache reuse is asserted here.

## Decision

1. **Closed three-way partition.** `INPUT_PARTITION` in `fetch/fingerprint.py`
   names every currently tracked file under `custodian/publicdata/`, once, with
   exactly one of the classifications below. The table is immutable in process.
   A newly tracked file absent from it defaults to shared fetch-pass; the
   completeness test also requires its explicit classification before acceptance.
   Publicdata symlinks, including the root, refuse proof before hashing publicdata content:
   resolved-path aliases cannot move a shared input into the excluded set.
   An untracked file or a missing tracked file still makes proof unavailable,
   even if that path would otherwise be excluded. Any doubt means refetch.
2. **Amendment of decision 0081 item 2.** Replace its whole-tree global data
   input with the canonical sorted path/hash list of shared fetch-pass files.
   Shared inputs enter every entry's fingerprint. Per-entry `sources.yaml`
   remains bound only through each constructed `Entry`, including every field;
   listing sibling rows retain their existing binding. Only proven post-loop-only
   files leave the data hash. No other fingerprint field, machinery seed,
   excluded function scope, intake proof, receipt proof or refusal is removed.
   Shared data hashes always read fresh bytes, including same-size edits within
   a filesystem timestamp tick; the code-module hash cache is unchanged. Unavailable proof still follows
   decision 0081 item 5: fetch without a reusable fingerprint, never silently
   reuse and never turn this into a new build gate. Dated note of 2026-11-25
   (OI-410): after S2-P78 the review S2-P78.rv1 counted 27 module files in
   the seeded path's loaded-module digest, which replaces the count of 20 in
   decision 0081 item 4.
3. **Fetch readers take precedence.** Shared includes the assessment's five
   fetch-shaping review groups: `gis_layer_fields.yaml`, `s2_t29_sources.yaml`,
   `fdi_crosswalks.yaml`, `additions_property_venues.yaml`, and the pair
   `busy_besttime_venues.csv` / `busy_besttime_requests.yaml`, all under `review/`.
   Generation setup, own-run confirmation and district-alias status inputs stay
   shared. The FDI crosswalk's `_mapping` can open arbitrary matching direct
   review CSV/YAML targets before checking their contents. Those potential
   targets stay shared too, even when today's table shape would be refused;
   `municipality_names.csv` is explicitly refused before open. No target-reader
   behavior is changed to obtain a smaller shared set.
4. **Completeness guard.** Instrument actual file opens during invented-fixture
   fetch execution. Exclude only the fingerprint's own measurement reads;
   every operational publicdata read must classify as per-entry or shared.
   The existing real fetch-reader audit uses the same classification and the
   new tests reuse its hook. A planted fetch-time read of a post-loop file must
   make the positive test fail. Tests separately cover Path, builtin and file
   descriptor opens, dynamic FDI target reads, unlisted tracked inputs, and each
   retained missing/untracked/outside-root refusal and the new symlink refusal
   by their exact reasons.
5. **Resume and recheck.** A post-loop edit preserves all completed-entry reuse;
   a shared edit changes every entry's data digest; a changed constructed registry
   row changes only its entry. Tests prove these three outcomes with interrupted
   journals and two completed entries. `closure_intact` rechecks the same shared
   partition during the run; post-loop assembly and its checks still rerun.

## Partition inventory

Paths below are relative to `custodian/publicdata/`. Counts are generated from
`INPUT_PARTITION`: per-entry: 1, shared fetch-pass: 44, post-loop-only: 13. Post-loop-only includes tooling-only inputs with
no fetch-time reader; it does not require that every run opens the file.

| File | Set |
|---|---|
| `atlas.yaml` | shared fetch-pass |
| `baci.yaml` | shared fetch-pass |
| `benchmarks.yaml` | shared fetch-pass |
| `gravity.yaml` | shared fetch-pass |
| `height_rules.yaml` | post-loop-only |
| `investment_pages.yaml` | shared fetch-pass |
| `review/activity_spine.csv` | shared fetch-pass |
| `review/activity_spine_audits.json` | post-loop-only |
| `review/activity_spine_refusals.json` | post-loop-only |
| `review/additions_industry.yaml` | shared fetch-pass |
| `review/additions_municipal.yaml` | shared fetch-pass |
| `review/additions_property_venues.yaml` | shared fetch-pass |
| `review/additions_splits.yaml` | shared fetch-pass |
| `review/arabic_tag.txt` | post-loop-only |
| `review/baskets.yaml` | shared fetch-pass |
| `review/busy_besttime_requests.yaml` | shared fetch-pass |
| `review/busy_besttime_venues.csv` | shared fetch-pass |
| `review/category_allowlist.csv` | shared fetch-pass |
| `review/country_aliases.csv` | shared fetch-pass |
| `review/country_iso3.csv` | shared fetch-pass |
| `review/district_crosswalk.csv` | shared fetch-pass |
| `review/district_layer_aliases.csv` | shared fetch-pass |
| `review/fdi_crosswalks.yaml` | shared fetch-pass |
| `review/flagship_candidates.yaml` | shared fetch-pass |
| `review/gis_imagery_views.yaml` | shared fetch-pass |
| `review/gis_layer_fields.yaml` | shared fetch-pass |
| `review/gis_snapshot.json` | post-loop-only |
| `review/greater_doha_municipalities.csv` | shared fetch-pass |
| `review/landmark_heights.yaml` | shared fetch-pass |
| `review/municipality_names.csv` | post-loop-only |
| `review/national_boundary_outside.json` | post-loop-only |
| `review/places_fsq_categories.csv` | shared fetch-pass |
| `review/places_fsq_policy.yaml` | shared fetch-pass |
| `review/places_ovt_attribution.csv` | shared fetch-pass |
| `review/places_ovt_categories.csv` | shared fetch-pass |
| `review/population_indicators.csv` | shared fetch-pass |
| `review/product_activity_occupation.v1.binding.json` | post-loop-only |
| `review/product_activity_occupation.v1.json` | post-loop-only |
| `review/product_activity_occupation.v1.schema.json` | post-loop-only |
| `review/property_use_map.csv` | shared fetch-pass |
| `review/reconciliation_oi03.md` | post-loop-only |
| `review/s2_t08_source_review.yaml` | shared fetch-pass |
| `review/s2_t09_generation_config.json` | shared fetch-pass |
| `review/s2_t09_source_checks.yaml` | shared fetch-pass |
| `review/s2_t13_confirmation.yaml` | shared fetch-pass |
| `review/s2_t17_forecast_series.md` | post-loop-only |
| `review/s2_t19_confirmation.yaml` | shared fetch-pass |
| `review/s2_t29_sources.yaml` | shared fetch-pass |
| `review/showcase_areas.yaml` | shared fetch-pass |
| `review/showcase_gazetteer.yaml` | shared fetch-pass |
| `review/trade_publisher_readings.yaml` | shared fetch-pass |
| `review/venue_busyness_crosswalk.csv` | shared fetch-pass |
| `review/venue_crosswalk.csv` | shared fetch-pass |
| `review/verified_places.csv` | shared fetch-pass |
| `review/zone_crosswalk.csv` | shared fetch-pass |
| `review/zones_without_districts.csv` | shared fetch-pass |
| `sources.yaml` | per-entry |
| `trade_reconciliation.yaml` | post-loop-only |

## Evidence and limits

The invented-fixture tests are `test_fetch_input_partition.py` and
`test_fixture_fetch_opens_only_declared_repo_files` in `test_fetch_fingerprint.py`.
The exact commands, seed, exits and planted guard removals are recorded in
PROGRESS.md, S2-FPR b1, and the builder's return. These are finite execution
coverage plus a conservative reader audit, not a proof about arbitrary future
Python code. A new fetch path must extend the audit fixtures. No network,
real cached source, private input or live acquisition is needed.

## Consequences

The excluded data files can change without re-keying entries. Many review files
remain shared because of the dynamic FDI reader; no time saving is promised.
Editing this machinery still invalidates existing fingerprints. Decision 0081's
runtime module checks and fail-closed refetch behavior remain in force.

## What would change it

A new fetch-time reader of an excluded file requires moving it to shared before
use. A narrower target-reader contract, separately approved and plant-tested,
could later justify excluding additional review files. Any stale reused input
is a reason to restore broader binding immediately.
