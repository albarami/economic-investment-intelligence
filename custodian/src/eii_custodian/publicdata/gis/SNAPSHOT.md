# National-centre imagery snapshot and offline address seams — S2-T51

Authority: decision 0079 items 1 to 6; document 04 PUB-105 and section 3.1; document 13
OPS-65. This is separate from the keyed imagery provider. No national-centre finer-level
or free-text locator adapter exists. Tests never fetch real tiles, read real address points,
read the ordinary public cache, or read the external drive.

## Lead-shell acquisition, after task approval only

The only activating form is `./eii build-public --gis-imagery-snapshot`, alone, from the
lead's shell after different-maker task approval. It never runs with an ordinary public
build, test, gate, story or CI run. Ordinary builds never enter its acquisition code.

Set `EII_GIS_SNAPSHOT_ROOT` to the separately chosen D: folder beside the existing data
folder; no private path is recorded here. The command accepts one direct child of the
WSL D: mount, refuses the existing data folder, nesting, traversal, symbolic links and an
unset root, and never falls back to the repository cache. Only this configured root is
read/written. Tests inject temporary roots and invented filesystem facts.

Before launch the lead stages `national-land.geojson` (the explicitly reviewed Public
national-land Polygon/MultiPolygon in EPSG:4326, including islands), its
`national-land.meta.json` Public-chain receipt, and a `job.json` with exactly these fields:

- `boundary_sha256`: SHA-256 of those exact source bytes.
- `remaining_bytes`: the recorded total acquisition estimate, revised from measurements;
  the lead's initial estimate was about 100 GB, not a verified bound.
- `staging_bytes`: at least three GiB for staging/metadata and bounded shards.
- `reserve_bytes`: at least five GiB free on the data drive after remaining acquisition/staging.
- `system_reserve_bytes`: at least two GiB free on the system filesystem.

The boundary receipt has exactly string fields `source_id`, `key`, `publisher`, `fetch_url`,
`licence_basis`, `licence_id`, `decision_record`, `terms_words`, `terms_read_on`, `retrieved_utc`,
`sha256`, `method_version` and `upstream_sha256`. It names the reviewed boundary-producing
method/version and original Public input hash, publisher, source URL, basis/licence and dates;
its own hash equals the exact boundary bytes. The URL must be an admitted Public source URL
with no credential. The original boundary and receipt are retained as immutable snapshots and
carried through selection/assembly with the projected boundary, so the clip does not lose its
source chain. A missing or mismatching boundary receipt refuses activation.

These are operational safety floors, not sample-derived source facts. The lead records
actual capacity on both filesystems and the chosen reserves before launch. The process
sets nice to nineteen and ionice to idle and refuses if either fails. One nonblocking
machine-global abstract Unix socket lock spans the entire run, followed by the root's
nonblocking filesystem lock. A second run, including one configured with a different
folder, refuses as `run_locked`. No seat/core is reserved.
Every request attempt, including metadata/retries, passes through one sequential pacer.
During longer waits the process checks disk and first-hour measurements every second; it
checks again immediately before each send.
Redirects never send a second request. Three retries use the existing back-off with a
longer Retry-After honored. Persistent tile failures become recorded gaps; metadata,
redirect or safety refusals preserve completed shards and exit nonzero. Disk exhaustion
and quota errors report `disk_safety_stop`, and I/O faults report `io_error`, including
faults wrapped by immutable publication; a job-body fault is never labelled a lock fault.

Only tile HTTP 404/410 and invalid successful tile bodies (empty, non-JPEG or wrong
dimensions) on the first attempt become recorded gaps. A missing or invalid tile after
earlier retries stops resumably with its actual status, reason and attempt count; no
unfinished shard tar, receipt, index or selection pointer is published. Resume requests
the same key afresh. Under L-1303's recorded-gap treatment, a fresh first-attempt 404 on
resume is a persistent recorded gap, even when the previous run saw 503 then 404; an
intact tile on resume is retained normally. Attempts are never rewritten to one.
Exhausted retries on HTTP 429/500/502/503/504 or an
unreachable transport stop with `request_failed`, publishing no unfinished shard; resume
requests that tile key again. Other unsuccessful statuses also stop rather than become
gaps. A wholly out-of-extent tile is a gap with `outside_extent`, no HTTP status and zero
attempts, and is never requested. Tests use a unique abstract lock name per test; the
production name remains machine-global and is explicitly passed by the supervisor.

Metadata activation checks QNG EPSG:2932, origin, extent, every declared level through the cap and
decreasing resolutions, approximately 0.53 m at level ten, 512-pixel JPEG. Each tile's JPEG frame header must also
declare those dimensions; the bounded reader then forces a full pixel read with the pinned
rasterio/GDAL JPEG driver. Missing SOS, missing quantization or invalid scan structure is
`tile_format_or_gap`, never a present member. The same decoder runs during shard verification. All dates must
have a compatible scheme. Old export scales are not tile levels. The boundary is projected
with the installed rasterio adapter and every intersecting tile is enumerated, including
coastal/island intersections. Actual metadata, coverage and disk sufficiency remain
unverified until the lead's live run. Missing or invalid tiles remain explicit gaps;
nothing is filled. A date's smaller service extent does not clip country enumeration or
refuse the date: the uncovered land geometry is retained, and wholly uncovered tiles are
recorded without requests. Upstream changes require review and a new namespace, never
editing a receipt.

The disk watch runs before each request and shard. It reserves remaining estimated bytes,
staging and the safety margins; only this acquisition's existing tar objects and transferred
bytes reduce its remaining estimate. Other drive consumers cannot lower its threshold.
Disk or safety breaches stop resumably; there is no cost stop. Standard output emits
measured first-hour request count, elapsed seconds, bytes, failures, request and byte rates,
and measured changes in both filesystems. The lead copies those observations to the outbox
and revises sizing; the command does not send messages. A final measurement is emitted on
success or refusal.

## Immutable objects, resume and selection

Per date and capped level, `enumeration.json` fixes source-boundary, metadata, projected
boundary and enumeration identities and sorted tile keys. Shards contain at most five
hundred twelve JPEG members. Their body, receipt and index reuse `fetch/snapshots.py`:
`shards/<shard>/<UTC-day>/<body-sha>.tar`, the immutable identity receipt beside it, and
`index/<identity>.json` published last. The receipt binds publisher, service, imagery date,
terms/basis, UTC retrieval, byte size, generator version and every member hash/key.
It also lists gaps by tile key, fixed reason, HTTP status (when available), attempts and
UTC retrieval. Members and gaps must cover exactly the enumerated keys, without overlap
or duplicates. An all-gap shard is valid. Resume verifies recorded gaps and never requests
them again; changing that selection requires the lead's explicit review.

`snapshot_receipt.py` owns the closed Public-chain schema used for metadata, projected
boundary, original boundary, shard, level completion and all-date receipts. Every stored
receipt has source/key, publisher, URL, licence basis/licence and decision record, terms
words/read date, UTC retrieval, generator version, SHA-256, byte count, kind and imagery
date; each kind has a closed set of additional fields. Unread terms retain the explicit
pending record under decision 0059. The projected boundary preserves its original
publisher, URL and licence chain and binds the original boundary hash and projection
method. Resume and release selection validate the same schema and refuse incomplete or
foreign lineage, even when the envelope hashes agree. A shared boundary-chain check holds
source id/key, publisher, URL, licence basis/id and decision record against the original;
resume also holds upstream hash and method version. Retrieval time and terms readings are
not chain identity. As a result, `pin_boundary` refuses a changed source chain under an
unchanged boundary identity; review requires a new namespace. The shared shard-lineage
check compares metadata, boundary and enumeration hashes and shard number with the
verified enumeration at both resume and selection. Gap reasons also bind status and
attempt count: request failures require HTTP 404/410 and one attempt; successful-body
refusals require HTTP 200 and one attempt, otherwise `gap_reason_integrity`.
The same gap eligibility validator runs before immutable shard publication as well as
at resume and release selection. Invalid supplied gaps leave only resumable staging
cleanup, never a published shard or pointer; existing consumer checks are unchanged.

A completed shard is skipped only after its pointer, receipt, whole-body hash, member
hashes and expected keys verify. A partially staged shard is fetched again. Changed
metadata or boundary refuses the old enumeration. Changed bodies create new hash objects;
an existing selection is never overwritten. A level completion manifest is published only
after every enumerated shard verifies. The all-date manifest is published only after all
eleven dates and capped levels complete; fixtures are not evidence that this happened live.
Completion means every key is accounted for, including recorded gaps. Level and all-date
manifests carry the gap keys/count and uncovered geometry. Assembly carries that coverage
to the release, including releases whose selected tiles are all gaps; the product credit
route reports it as missing coverage.

Release review writes `release-selection.json` with exactly `manifest_sha256`, selecting
the reviewed all-date manifest's hash explicitly. `snapshot_release.reviewed_inputs`
verifies all dates/levels and named hashes, never latest. `scripts/gis_snapshot_input.select`
is the opt-in seam for the future release command; with imagery false it reads no root.
Only the selected immutable files bind read-only by descriptor into `/imagery/`; the
mutable tree is never mounted. Selection refuses above ten thousand named files or an
insufficient process descriptor limit, before opening sources; there is no broad-mount
fallback. Shard capacity bounds the normal argument/descriptor count, and mount validation
uses ordered path components and grouped roles to avoid quadratic work. Actual live counts
remain unmeasured. Hashes are rechecked through opened descriptors; the
independent mount judge rejects writable/overbroad mounts. Acquisition writes one tile at a time into staging; validation reads bounded tile
members without loading whole shards into memory. The assembly seam streams one
shard at a time into release staging, copies objects without aliasing acquisition files,
and carries source receipts/credits. The selected all-date manifest and its receipt enter
the same hash/copy/rehash path exactly once, including all-gap releases. The existing build-release command stays a placeholder;
its eventual integration and UI display remain with the tasks that own those surfaces.

## Product readers

`api/gis_imagery.py` imports no custodian module and reads an explicitly named, hashed
release manifest and its objects only. It refuses a bad manifest, corrupt member/object,
unsafe path or level above ten, and shows missing-source/missing-coverage when appropriate.
The whole-shard hash is cached for the reader's process lifetime by content identity and
opened-file device, inode, size and modification/change timestamps. A changed file is
hashed again, and the requested member hash is checked on every request.
The identity comparison after hashing uses those same fields and excludes access time,
which a normal first read may update on a relatime filesystem.
The same-origin tile route supplies a picture only. The credit route supplies publisher,
service, retrieval date, imagery date, terms and basis for the UI's always-visible credit;
it supplies no numerical evidence. A release without imagery stays usable.

`api/address_search.py` supplies an immutable released-row index plus fixed read adapters
for PostgreSQL and embedded storage (`structured-address-v1`). Both exact reads bind zone,
street and building strings and order by feature key, fetching at most six rows to signal
truncation and returning at most five candidates. The composite index DDL is shared by
both stores. Duplicate triples remain ambiguous, subtype strings stay as published, and
leading zeroes are not normalized away. Null source coverage differs from an empty table.
The route `/api/address-search/structured` accepts exactly those three fields, refuses free
text by name, and ignores keys/offline settings because it has no transport. The table/index
is persisted Public data; requests/results are not persisted or passed to a model. Selected
release lineage accompanies candidates. Address numerals must use Fact chips when the UI
integrates this route. The keyed provider's `/api/address-search` stays separate and unchanged.

## Offline evidence and limits

The new invented tests are `custodian/tests/test_gis_snapshot.py`,
`product/tests/test_structured_address.py`, `product/tests/test_released_imagery.py` and
`scripts/tests/test_gis_snapshot_binding.py`. Their network sentinels refuse socket connects;
all filesystem fixtures use temporary paths. The real public-data regression command is
not run here. The lead's live capacity, metadata, first-hour measurements, complete fetch,
real PostgreSQL parity, release-command integration and visible frontend integration are
separate evidence; none is established by these fixtures.

## Official interface reading for this task

No dependency or pin changes. The implementation reuses installed rasterio 1.5.2 and
shapely 2.2.0. Their bundled official docstrings for `rasterio.warp.transform_geom`,
`shapely.geometry.box` and `shapely.geometry.mapping` were read offline on 2026-11-20;
no documentation site or source host was contacted. API reference identities:
`https://rasterio.readthedocs.io/en/stable/api/rasterio.warp.html#rasterio.warp.transform_geom`,
`https://shapely.readthedocs.io/en/stable/reference/shapely.box.html` and
`https://shapely.readthedocs.io/en/stable/manual.html#shapely.geometry.mapping`.
These are reference identifiers, not claims of an online reading. The local reading confirms
GeoJSON input/output and source/target CRS parameters; exact installed pins stay unchanged.
The installed official `BaseGeometry.difference` docstring was also read offline for the
uncovered-land operation in fix round f1; it returns the difference of the geometries.

The fix-round-three offline interface reading covers the installed rasterio 1.5.2 official
`MemoryFile`, `MemoryFile.open` and `DatasetReader.read` docstrings and `RasterioIOError`:
immutable initial bytes, driver selection and an explicit full pixel read. Reference
identities are `https://rasterio.readthedocs.io/en/stable/topics/memory-files.html` and
`https://rasterio.readthedocs.io/en/stable/api/rasterio.io.html`. These identifiers record
an offline reading on 2026-11-20, not a documentation-host request. No pin changed.


## Fix-round-four mixed-retry correction

PO-S2-T51-F3-01 is corrected by the pre-publication eligibility check and producer stop
above. Permanent invented plants cover 503 then 404, 410, empty 200 and invalid 200,
each followed by a fresh one-attempt 404 gap or intact tile on the same key. They require
the true two-attempt failure, no tar/receipt/index/pointer, cleaned staging and successful
resume; a subsequent resume skips the verified selection. Direct archive plants refuse
ineligible status/attempt combinations before publication and then successfully write
the same shard. Isolated tracked-file archives demonstrate red on the preceding code
and red when either added call-site guard is removed alone, then restored green.
Evidence is appended in PROGRESS.md, **S2-T51 f4 mixed-retry publication correction**.
No live archive was read or changed; different-maker review and acquisition approval
remain pending.
