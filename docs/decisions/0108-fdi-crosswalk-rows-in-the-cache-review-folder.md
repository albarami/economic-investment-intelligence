# Decision 0108: FDI crosswalk rows in the cache review folder

| | |
|---|---|
| Status | Proposed, 2026-11-24 (task S2-P85); different-maker review and acceptance remain pending |
| Date | 2026-11-24 |
| Scope | TASKS.md S2-T39 acceptance criterion 3; document 03 section 7.3's `fdi_projects` row; `investment_crosswalk.load_crosswalk` |
| Amends | Nothing until accepted. Clarifies the crosswalk placement under [decision 0026](0026-public-sources-used-in-full-locally.md) item 5 and [decision 0034](0034-licence-questions-of-public-sources-are-answered-at-a-go-live.md) item 2 |
| Purpose | Keep source-issued project identifiers outside the public repository while retaining all three locally mapped columns |
| Read first | Decision 0026 item 5; decision 0034 item 2; TASKS.md S2-T39 acceptance criterion 3; AGENTS.md rules 5, 7, 19, 36 and 37 |

## Context

Decision 0026 item 5 bars every record, name and value of a source without an
open licence from the public repository. Decision 0034 item 2 keeps that rule
for new commits. The `fdi_projects` source uses the owner's decision as its
basis, and each crosswalk row carries its source-issued `project_id`.
S2-T39 acceptance criterion 3 nevertheless says the reviewed crosswalks are
committed. A populated crosswalk cannot follow both instructions.

The municipality-code target already lives in `CACHE/review/` and is read
through its pinned hash. The same placement can hold the crosswalk rows.

## Decision

1. Reviewed mapping rows live only in the uncommitted
   `CACHE/review/fdi_crosswalks.yaml`. `load_crosswalk(cache)` selects that
   file when present, validates it with `read_crosswalk` and records its
   SHA-256 and origin `cache`. Symlinks at the file, review directory or any
   ancestor refuse as `crosswalk_hash`, including dangling file links.
   An invalid cache file refuses rather than selecting the committed file.
   Non-municipality targets stay committed and are read from the committed
   review folder; only `municipality_codes.csv` is read from `CACHE/review/`.
2. The committed `custodian/publicdata/review/fdi_crosswalks.yaml` stays
   schema-only, with `mappings: []`. It is selected only when the cache file
   is absent, with origin `committed`; all three mapped slots stay null.
   A populated committed crosswalk refuses; a validated mapping row there
   uses the existing closed reason `crosswalk_schema`.
3. The review binding is the hash of the cache file recorded in PROGRESS.md
   by the lead's review. The loader's hash checks byte consistency during
   reading; computing it does not establish independent approval. Each row
   still requires the lead role, date and reference, source-issued ID,
   selected snapshot, content-derived project key and pinned target.
   Name-derived keys remain refused.
4. S2-T39 acceptance criterion 3 says the crosswalks are kept in the
   uncommitted cache review folder after the lead's review (decision 0108).
   Its box stays unticked until the real mapping review is complete (OI-182).

## Evidence and consequences

The S2-P85 row in PROGRESS.md records offline invented-file tests and planted
refusals. All three columns, `source_country_iso3`, `municipality_code` and
`place_key`, still fill locally from reviewed rows; no value is lost by
changing their storage location. Hosted CI uses invented files only. No
source record value or real mapping is added by this task, and no real
review hash or OI-182 closure is claimed.

## What would change this decision

A change to review approval, source identity, snapshot binding or target
validation needs its own reviewed change. This placement decision changes
none of those rules.
