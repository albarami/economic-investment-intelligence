# Decision 0096: release artefacts are single files under `artefacts/`

| | |
|---|---|
| Status | Accepted, 2026-11-23, by the owner (lead ruling L-1508); item 2's tile-extract form is still verified at S3-P05 under AGENTS.md rule 42, and acceptance does not replace that check |
| Date | 2026-11-23 |
| Owner | The owner |
| Decided by | The owner, 2026-11-23 ("i accept"), under the advisor's conditions recorded in lead ruling L-1508: every release artefact is one ordinary listed file with its hash, nothing unlisted is served, and map and routing sources keep their attribution |
| Amends | Decision 0061 item 12 (its routing-section sentence); document 02 section 4.2, the manifest example's `artefacts` line; document 03 section 9 **Mounted Public transport (S3-T24)**, the `basemap_url` paragraph's map-asset sentence; and aligns proposed decision 0088 item 1. Implemented by S3-P04 (`eii_custodian.release.artefacts`) |
| Purpose | Give every release artefact one writer and one shape, a single regular file under `artefacts/`, so the producer binds a computed hash and start-up accepts exactly the listed files |
| Read first | Document 02 ARC-42, ARC-43 and ARC-119; document 03 DAT-81 and section 9 **Mounted Public transport (S3-T24)**; document 13 **S3-T28 Public assembly producer**; AGENTS.md rules 7, 12, 42 and 46; decision 0054 |

## Context

ARC-119 and DAT-81 already admit only regular files under `artefacts/`: the
loader refuses a symlink and any non-regular file, and start-up
(`verify_artefacts`) refuses any release file the manifest does not list
(`startup_inventory_mismatch`). Three texts still describe something else.
Decision 0061 item 12 names a folder entry `artefacts/routing/`; the document 02
manifest example lists `{"path": "artefacts/routing/", ...}`; and document 03
says that map assets stay outside the release tables and release identity,
while a mounted release cannot hold an unlisted file. No writer placed an
artefact: the release spec's `artefacts` list carried a hash typed by hand.

## Decision

1. **Item (a): one regular file.** Every release artefact is one regular file
   whose manifest `path` is a normalised relative path under `artefacts/`
   (ARC-119). No folder artefact exists; ARC-43's folder digest is not used by
   any artefact this record admits. The custodian writer
   `place_artefact(cache, relative, source_file)` refuses any other path
   (`artefact_path_refused`) and a symlink, folder or other non-regular source
   (`artefact_not_regular`), copies the file atomically, and records
   `{path, sha256}` in the phase record `assembly/artefacts.json`, the
   producer's ninth phase. The release spec's `artefacts` list must equal that
   record: a differing hash refuses as `producer_hash_mismatch`, a missing,
   extra or repeated path as `producer_chain_incomplete`. The existing
   `producer_path_refused` and `startup_inventory_mismatch` refusals stay.
2. **Item (b): routing is one tile extract.** Routing is the one file
   `artefacts/routing/tiles.tar`, a Valhalla tile extract (the archive form that
   Valhalla's `mjolnir.tile_extract` setting names). This form is **not yet
   verified**: S3-P05 reads the current official Valhalla documentation for that
   setting under AGENTS.md rule 42 and decision 0054, names the pages read in its
   brief, and records the result. The owner accepted this record on 2026-11-23 with this
   check still owed (lead ruling L-1508). If the documentation does not support
   a single-file extract, a new decision record revises this item; no folder
   entry returns silently.
3. **Item (c): map assets are release artefacts.** The basemap is
   `artefacts/tiles/basemap.pmtiles` and each glyph range is
   `artefacts/fonts/<stack>/<range>.pbf`, each placed by `place_artefact` and
   listed in `manifest.artefacts`, so they enter release identity (ARC-44) and
   start-up's exact inventory. Document 03's sentence placing map assets outside
   release identity is replaced; `verify_artefacts` is not relaxed.
4. **Alignment of proposed decision 0088 item 1.** The building-heights asset
   of proposed decision 0088 item 1 is a release artefact under the same rule:
   one regular file under `artefacts/`, placed by `place_artefact`. Its file name
   stays that record's; this record changes only its prefix and writer.

## Text each amended document will carry

- **Decision 0061 item 12** (a proposed record, not edited here; this record
  supersedes the one sentence under the acceptance of 2026-11-23, L-1508):
  "The API process takes its
  routing only from a source given at start: the `artefacts/routing/tiles.tar`
  entry of the checked release (ARC-119, decision 0096), or an in-process
  routing callable in tests; never from a request, never over a network."
- **Document 02, manifest example**: the `artefacts` line reads
  `"artefacts": [{"path": "artefacts/routing/tiles.tar", "sha256": "<hex>"}]`,
  with a sentence citing accepted decision 0096 stating that every
  artefact is one regular file.
- **Document 03 section 9 Mounted Public transport (S3-T24), `basemap_url` paragraph**: a sentence citing accepted
  decision 0096: "Under decision 0096, accepted 2026-11-23, the basemap
  `artefacts/tiles/basemap.pmtiles` and the glyph ranges
  `artefacts/fonts/<stack>/<range>.pbf` are release artefacts listed in
  `manifest.artefacts` and inside release identity; the sentence placing map
  assets outside release identity no longer holds."

The owner accepted this record on 2026-11-23 (lead ruling L-1508): each
amended document now carries the sentence above as accepted text. Decision 0061
itself is not edited (AGENTS.md rule 46); this record's item 1 supersedes its
one routing-section sentence.

## Evidence and consequences

S3-P04 adds the writer, the ninth phase, the spec check and the draft's
`artefacts` list from the record, with invented tests only: path faults, source
faults, the record and spec refusals, one generator over relative paths, and a
producer, assembly and start-up run on invented single-file artefacts.
PROGRESS.md records the commands and exits. No real routing extract, basemap or
glyph is placed by this task: S3-P05 places routing and S3-P06 the map assets;
S3-P1b packs heights on this contract. No gate, privacy rule or refusal is
weakened.

## Open matters and change control

OPEN_ITEMS.md records the owner's acceptance of 2026-11-23 and that S3-P05
still verifies item 2. A material change needs a new record (AGENTS.md
rule 46).

## Sources

Document 02 ARC-42, ARC-43, ARC-44 and ARC-119; document 03 DAT-81 and section
9 **Mounted Public transport (S3-T24)**; document 13 **S3-T28 Public assembly producer**; decision 0054; decision 0061
item 12; lead ruling L-1507; plan S3-PFIX section S3-P04 (D-ART items (a), (b)
and (c)).
