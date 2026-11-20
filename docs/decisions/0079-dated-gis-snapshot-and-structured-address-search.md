# Decision 0079: Dated GIS imagery snapshot and offline structured-address search

| | |
|---|---|
| Status | Accepted, 2026-11-20 |
| Date | 2026-11-20 |
| Owner | The owner |
| Decided by | The owner, 2026-11-20, on the lead's reading of S2 gate item 9 (OI-311) |
| Amends | AGENTS.md and CLAUDE.md rules 13 and 44; document 02 ARC-13 and ARC-35; document 04 PUB-01 to PUB-04, PUB-07, PUB-105 and section 3.1; document 13 OPS-65; document 03 DAT-168 reader; documents 08 to 12 offline reader supplements; TASKS.md S2-T19, S2-T27, S3-T03 and S3-T16; document 14; decision 0064 items 24 and 30 for the national centre only |
| Purpose | Record the owner's snapshot-now decision and the two national-centre exceptions deferred until after go live |
| Read first | [decision 0064](0064-the-narrowing-rows-decided.md) items 24 and 30; document 04 PUB-105; document 13 OPS-65; OPEN_ITEMS.md OI-311 |

## Context and evidence

The owner answered the imagery-date/address-search question on 2026-11-20. The lead's
reading of that day reports eleven dated services, one Qatar National Grid tiling scheme,
512-pixel JPEG tiles, and a local address-points snapshot. This record does not turn the
lead's samples or cache observations into test constants. Tests use invented tiles and
points; no real download, capacity, completion or product integration is certified here.

The owner's words (typing preserved), recorded under OWNER_RULES 9:

> for number 2 i suggest with the enhancemnt after go live what do you think?

> let it run in the backgorund from now then but it shouldnt affect compelting s2 and s3. would this work?

The advisor agreed to snapshot now, and the two named national-centre run-time exceptions
after go live. Ruling L-1291 records the decision and confirms all six conditions below;
L-1296 makes explicit that the already-approved keyed imagery provider is a separate provider.
The earlier recommendation to put the national-centre exceptions in S2 is superseded.

## Decision

1. **Scope and scheduling.** S2-T51 implements the dated national GIS centre imagery snapshot
   through level 10, approximately 0.53 m, and offline structured zone/street/building search
   over the released cached address points. The dates are 1995-02, 2003-05, 2004-07, 2010-01,
   2012-08, 2017-04, 2019-12, 2021-09, 2022-04, 2024-10 and 2025-07. Implementation uses free
   seats behind S2 and S3 work; acquisition begins from the lead's own shell only after the
   task's normal review and different-maker approval, never from a worker or continuous integration.

2. **Closed acquisition contract.** `./eii build-public --gis-imagery-snapshot` runs alone,
   separately from the ordinary public build. Its exact service paths are registered in
   `custodian/publicdata/review/gis_snapshot.json`, under `gis_imagery_history`, with ordinary
   and nightly tile eligibility false. Metadata and tile starts share one sequential limiter,
   at most ten per second, retries included; every redirect is refused. The contract validates
   origin, CRS, decreasing declared resolutions, extent, JPEG and tile dimensions before
   activation, and binds metadata, national-land boundary, enumeration and member hashes.
   Enumeration intersects the whole reviewed national land polygon, including islands and
   coastal tiles, after projection to EPSG:2932. A level above 10 is refused before a request;
   level 11 is refused by name. Missing/error tiles remain gaps, never invented fill.

3. **Storage, safety and the six binding conditions.** Rule 13 is narrowed only for the
   dedicated lead-shell acquisition root and the explicitly selected immutable release input.
   `EII_GIS_SNAPSHOT_ROOT` must name a D: folder beside the existing data folder, outside the
   repository and separate from the ordinary public cache; no private folder name is recorded.
   Unset, wrong-drive, nested, traversal or symlink escapes refuse without fallback. Each bounded
   shard has dated hash-addressed bytes, a provenance/member receipt and a last-published identity
   index under document 04 section 3.1. Resume verifies enumeration, receipts, members and shards
   before skipping; changed bytes are new immutable objects, never an overwritten selection.

   The owner's six conditions are binding:

   - (i) No S2 or S3 gate, test, whole test or guided story waits for completion; the background
     snapshot is not a dependency of any task before go live. S2-T10's blanket dependency excludes it.
   - (ii) Its folder and process are its own, never the S2 live public build's folder or run;
     nice and ionice are required and fail closed, starts are capped at ten per second, progress
     is resumable, and one nonblocking global lock covers all dates; only the lead starts it.
   - (iii) Data stays on D:, in the sibling folder, with hashes and receipts per file or shard.
   - (iv) Before starting, the lead records capacity for remaining acquisition, staging and safety
     reserve, and measures free space on both `/` and `/mnt/d`; both are watched during the run.
     About 100 GB and about 2.5 days were estimates from the lead's samples, not guarantees.
     Only a disk or safety breach stops the run; there is no cost stop. The lead reports first-hour
     measured requests, elapsed time, throughput, bytes, failures and both free-space changes to
     the outbox, revises sizing from those measurements and retains resumable state on a stop.
   - (v) Registry, fetcher, receipts, planted checks and this record are one ordinary S2-T51 task
     with its own plan, build, review and different-maker confirmation, queued behind S2/S3 work;
     the background fetch starts after approval, not before.
   - (vi) No fixed model seat or core is held; acquisition uses network and disk.

4. **Release and product boundary.** A reviewed complete all-date manifest hash is selected
   explicitly, never through a latest pointer. Assembly verifies named hashes and binds only
   those immutable files read-only into the release sandbox; it never binds the acquisition root.
   Ordinary releases need no snapshot root. Product code reads only verified released artifacts
   through same-origin routes, with publisher/service/date/terms/basis credits while displayed;
   imagery stays a picture and supplies no number or evidence claim. A release without imagery
   remains usable with truthful missing coverage. These seams do not make the existing placeholder
   build-release command operational or certify its later integration.

5. **Offline structured address search.** `gis_address` continues through the existing
   `gis/layers.py::address_rows` parser to `pub_address_point` (DAT-168), dropping utility accounts,
   PIN and editing fields. The separate `POST /api/address-search/structured` route accepts exactly
   the published zone/street/building strings. The fixed `structured-address-v1` read and index
   apply in both stores, return at most five stable feature-key-ordered candidates, preserve
   subtypes and source lineage, and distinguish found, ambiguous, not-found and missing-source.
   There is no guessed match, person join, persisted query/result, model payload or provider
   fallback. Address numerals use Fact chips when displayed. Free text is refused by name with
   keys present or absent and the offline control set or unset. The existing keyed provider's
   BE-135/BE-136 routes and OPS-73, PUB-109, TST-248/TST-249 permissions are unchanged.

6. **Two deferred national-centre exceptions only.** S3-T29, trigger **after go live**, retains
   the value of national-centre levels 11 and 12 (0.265/0.132 m) and its
   `QARS_Custom_Locator` free-text matching, under the owner's quoted permission in the context
   above (OWNER_RULES 9). No adapter, enabling switch or product network path for either is
   installed now. Later review must establish API-only permissions, default-off/offline controls,
   attribution, non-storage and planted refusals on the terms of decision 0019 item 17. The keyed
   imagery provider already approved under decision 0023 item 7 is outside this deferral.

## Consequences and change triggers

OI-311's decision question is decided. The actual all-date snapshot fetch, disk observations,
first-hour report and eventual completeness remain pending the lead's approved run. Invented
fixtures do not tick acquisition acceptance. No before-go-live task or slice gate waits for it.
Any new host, date, level, storage/mount permission, real record, run-time locator permission or
change to the keyed provider requires its own reviewed amendment; nothing is silently enabled.

## Sources

- Owner-relayed note of 2026-11-20 21:30, items 1 to 4, supplied to S2-T51 as OWNER-DECISION.md;
  lead rulings L-1291 and L-1296, supplied as RULING.md and the approved plan's binding amendment.
- Lead's reading of S2 gate item 9, 2026-11-20, **Imagery**, **Sizes** and **Address search**,
  supplied as LEAD-READING.md; service names were already in the reviewed registry. Its sample
  size, cache count and sizing estimates are not regression fixtures or completion evidence.
- [decision 0023](0023-ten-additions-and-the-data-rule.md) items 3 and 7;
  [decision 0026](0026-public-sources-used-in-full-locally.md) item 2;
  [decision 0064](0064-the-narrowing-rows-decided.md) items 24 and 30;
  [decision 0019](0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 17.
