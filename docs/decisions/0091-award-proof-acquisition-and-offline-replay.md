# Decision 0091: Award proof acquisition and offline replay

| | |
|---|---|
| Status | Proposed; S2-P46 task brief authorizes the offline implementation; lead review pending |
| Date | 2026-11-22 |
| Scope | PUB-04; document 03 **S2-T29 cached page and awards contracts**; decision 0088 item 5; decision 0081 reuse boundary |

## Context and evidence

The S2-P46 brief requires acquisition once per distinct proof link, survival of
shape refusals, offline comparison replay and a bounded pool. The existing source
stage discards a proof when parsing or publication refuses. Invented tests and
measured replay evidence are recorded under S2-P46 in PROGRESS.md. These establish
no real-cache completeness or live acquisition result.

## Proposed decision

1. A proof acquisition is the resume unit. Its identity binds the transport
   version, representation version, configured pins and byte ceiling, and exact
   requested URL. Parsing and comparison code, workbook contents, reader width
   and the build-run fingerprint are excluded. The enclosing build-run journal
   keeps decision 0081's full fingerprint: a changed checker re-executes the
   entry, whose link store reuses verified bytes and reruns every check.
2. Under the entry's cache folder, `proof_store/<acquisition-hash>/state.json`
   selects a random acquisition namespace. Inside it the existing PUB-04 dated
   body, immutable receipt, index and check layout applies unchanged. Each link
   receipt records requested URL, final URL, archived SHA-256 and byte size,
   retrieval UTC, upstream SHA-256, transport version and representation. Version
   two removes form secrets before storage. Bytes that the mandatory sanitizer
   cannot represent safely refuse as hard `proof_representation_refused`, without
   a raw-byte fallback or a completed acquisition receipt. Storage precedes source-shape parsing
   and is outside the source publication stage. No source bytes are committed.
3. Every reuse calls the existing snapshot reader and rehashes its receipt and
   bytes. Missing operational state, missing receipts, changed bytes or invalid
   receipt/index contents that the reader classifies `snapshot_index_invalid`
   invalidate only that link. A live run acquires it into a fresh namespace and
   atomically changes only operational state. Old archive objects, including
   damaged ones, are retained untouched. Path/symlink, trust, date and other
   archive refusals propagate immediately. No latest-file selection or immutable
   overwrite is introduced. An offline replay refuses `proof_store_missing`
   rather than fetching an absent or invalidated link.
4. The all-link checker records closed `refused` results for `schema_missing`,
   `snapshot_date_missing`, `unavailable` and `row_count`, continues, then refuses
   source publication with `award_proof_refused`. The immutable `proof_checks`
   receipt keeps the full URL-ordered results, counts, classes and reader fallback
   metadata, without company names, registration numbers or amounts. Publication
   and receipt gates continue to reject refused results. Unknown reasons and
   trust/archive refusals never become ordinary fetch failures.
5. The awards declaration sets `max_readers: 4`, with integer values one through
   four only. A pool submits at most that many links in each batch, copies the
   caller's Context separately for every worker, and the proof reader enters its
   own exact-URL, pin and byte-limit scopes. Results are ordered by URL. On a
   connection refusal, HTTP 429/503 (even if a retry succeeds), or exhausted
   transport failure, the rest of the run uses one reader. Already running reads
   may finish; no next parallel batch is submitted. The receipt records this
   permanent reduction. Retry bounds and trust checks are unchanged.
6. `uv run --locked python scripts/awards_proofs.py replay --cache data/public_cache`
   is a closed, strictly offline lead-shell shape/comparison check over the
   verified intake and stored proof bytes. `live` in place of `replay` runs the
   same check with acquisition of missing/invalid links, then staged publication.
   Both print the existing link-result structure; replay exits one for incomplete
   evidence and zero for complete evidence. Neither command reads a latest
   snapshot, calls the gateway, alters privacy rules or supplies release approval.

## Consequences and limits

A refusal or interruption retains completed acquisitions. The selected per-link
store is operational acquisition evidence, never release selection. Replay
recomputes shape and comparison results and cannot refresh the publication date
of stored proof bytes. The current proof transport version must be bumped when
its fetch/representation contract changes. No code hash of comparison is used as
an acquisition identity. Single-writer source publication remains required.
Independent different-maker review and real-cache replay remain lead-owned.
