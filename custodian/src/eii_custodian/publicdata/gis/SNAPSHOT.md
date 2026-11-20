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
root lock spans all dates; a second process fails immediately. No seat/core is reserved.
Every request attempt, including metadata/retries, passes through one sequential pacer.
During longer waits the process checks disk and first-hour measurements every second; it
checks again immediately before each send.
Redirects never send a second request. Three retries use the existing back-off with a
longer Retry-After honored; failures preserve completed shards and exit nonzero.

Metadata activation checks QNG EPSG:2932, origin, extent, every declared level through the cap and
decreasing resolutions, approximately 0.53 m at level ten, 512-pixel JPEG. Each tile's JPEG frame header must also
declare those dimensions; the reader checks the header and hashes without decoding pixels. All dates must
have a compatible scheme. Old export scales are not tile levels. The boundary is projected
with the installed rasterio adapter and every intersecting tile is enumerated, including
coastal/island intersections. Actual metadata, coverage and disk sufficiency remain
unverified until the lead's live run. Missing/error/non-JPEG tiles stop with gaps; nothing
is filled. Upstream changes require review and a new namespace, never editing a receipt.

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

A completed shard is skipped only after its pointer, receipt, whole-body hash, member
hashes and expected keys verify. A partially staged shard is fetched again. Changed
metadata or boundary refuses the old enumeration. Changed bodies create new hash objects;
an existing selection is never overwritten. A level completion manifest is published only
after every enumerated shard verifies. The all-date manifest is published only after all
eleven dates and capped levels complete; fixtures are not evidence that this happened live.

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
and carries source receipts/credits. The existing build-release command stays a placeholder;
its eventual integration and UI display remain with the tasks that own those surfaces.

## Product readers

`api/gis_imagery.py` imports no custodian module and reads an explicitly named, hashed
release manifest and its objects only. It refuses a bad manifest, corrupt member/object,
unsafe path or level above ten, and shows missing-source/missing-coverage when appropriate.
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
