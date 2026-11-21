# Decision 0081: Per-entry fingerprints replace the checkout-HEAD gate of `./eii build-public --resume`

| | |
|---|---|
| Status | Proposed, 2026-11-21: built under the owner's S2-P39 approval and plan 3's independent design review, for different-maker confirmation |
| Date | 2026-11-21 |
| Owner | The owner |
| Decided by | The owner, recorded in `.overnight/IN/OWNER-CONDITION.md` (no loss of quality; any doubt means refetch); design independently approved by `.overnight/IN/DESIGN-REVIEW-3.md` (Anthropic Opus) with five records-only corrections applied |
| Amends | The `--resume` reuse rule recorded for S2-P37 in [document 13](../13_DEPLOYMENT_AND_OPERATIONS.md) command table, the [README](../../README.md) S2-P37 paragraph and `AGENTS.md`/`CLAUDE.md` rule 44; named by the task brief as an amendment of decision 0077's resume rule |
| Purpose | Let `./eii build-public --seed N --resume` reuse proven fetched bytes across unrelated code and data changes, with unchanged quality and an explicit refetch whenever proof is unavailable or uncertain |
| Read first | [PROGRESS.md](../../PROGRESS.md) S2-P37 and S2-P39; `.overnight/IN/PLAN.md`, `.overnight/IN/DESIGN-REVIEW-3.md`, `.overnight/IN/OWNER-CONDITION.md`; `custodian/src/eii_custodian/publicdata/fetch/fingerprint.py` and `fetch/resume.py` |

## Context and evidence

Under S2-P37 the durable journal `build-run.json` bound reuse to the seed and the
whole-checkout HEAD: any commit between the interrupted run and the resume made every
completed entry unproven and forced a full refetch. Replaying the last 40 commits that
touch `custodian/src`, `scripts/commands` or `custodian/publicdata` (at `ce4e7de3`)
shows most of them leave the fetch path of most entries untouched, so the HEAD gate
paid full refetches for changes that could not alter the bytes.

The owner condition for this task is unchanged quality: any input whose proof is
unavailable, malformed, unproven or simply different is fetched again, and reused
bytes keep their original publisher, retrieval time, hash and provenance.

## Decision

1. **Journal version 2.** `build-run.json` records `version: 2`. Each entry that
   completes through the ordinary fetched path stores a fingerprint beside the
   existing receipt and page-meta proofs. The recorded `head` stays in the journal
   for audit and for the version-1 refusal names below; it no longer gates reuse.
2. **Fingerprint contents.** The fingerprint of an entry binds: the canonical
   registry row, the named dispatch branch (including the explicit `grid` and
   `large` selections), the closed-encoded constructed `Entry`, the interpreter
   version, the `uv.lock` SHA-256, a hash of the computed code closure of the
   machinery and the branch, and one canonical hash of every git-tracked file
   under `custodian/publicdata/` (the global data input; `sources.yaml` rows stay
   bound per registry row and `tenders_pub.intermediate.pem` stays pinned by
   `chain_intermediate_sha256`). For `tenders_pub` the intake triple (award
   cutoff, cutoff reason, workbook SHA-256) is stored from the awarded-list
   receipts at fetch completion and recomputed through `intake_cutoff` on
   resume. Listing entries fold
   the canonical rows of every registry key under `entry.key + "/"`.
3. **Computed closure.** The machinery is the static import closure of the fetch
   loop seeds (`fetch/build.py`, `fetch/resume.py`, `commands.build_public`,
   `earthdata_key`) scanned by AST over module-level and function-level imports,
   relative imports, parent-package `__init__` modules and literal
   `importlib.import_module` targets, resolved by `importlib.util.find_spec`
   under the build's actual `sys.path`; bare script imports such as `cdse_key`
   join it. Only the named `build.py` scopes that run after the fetch loop or
   only for note-only rows are excluded; an unlisted scope is machinery by
   default, `.venv`, `.git` and `node_modules` are excluded code roots, and every
   dynamic form (`__import__`, `exec`, `eval`, `runpy`,
   `importlib.util.spec_from_file_location`, a non-literal `import_module`)
   refuses the fingerprint. In this checkout the machinery computes to **195
   modules** at build time (the review's static scan estimated 188 plus
   `cdse_key`; the difference is environment-dependent resolution, not scope).
   Every branch root of the dispatch map is already inside it, so the union
   measures the same 195; an added lazy import inside a kept scope invalidates
   every entry.
4. **Runtime guard.** At each recorded `fetched()` the loaded modules whose
   origin file lies under the runtime roots are compared with the union computed
   at run start; anything new and in-repository makes the item
   `resume_fingerprint_unproven` instead of silently binding it. Modules loaded
   before the run begins (for example the test runner's own imports) are the
   recorded baseline and do not trip the guard.
5. **Fail closed.** A missing or tampered fingerprint, an unresolvable first-party
   import, a dynamic import form, an unsupported `Entry` field type, an untracked
   file under `custodian/publicdata/`, a tracked input missing from the working
   tree, an unexpected loaded module or a changed intake triple each leave the
   entry without proof: it is refetched, or the item is marked
   `resume_fingerprint_unavailable` / `resume_fingerprint_unproven` and refetched
   on the next resume. A version-1 journal keeps its old refusal names:
   `resume_head_mismatch` when its recorded head differs, `resume_record_unproven`
   otherwise. Receipt and page-meta rehashing before reuse is unchanged, so
   provenance and every existing check are preserved.

## Measured and estimated gain

The honest corrected tally of DESIGN-REVIEW-3 Check 2 (dr3_hist.py, last 40
commits touching `custodian/src`, `scripts/commands` or `custodian/publicdata`,
at `ce4e7de3`):

| Commit class | Count of 40 | Reuse under this record |
|---|---|---|
| Registry-row-only changes (sources.yaml rows) | 4 | keep reuse except the changed rows; up to about 4 h 10 min of fetch time kept |
| No machinery module or data file touched (incl. docs/README-only `007b51af`) | 3 | keep all reuse |
| Rows/data files other than sources.yaml (`0ac6a0fc`, `8319086c`) | 2 | refetch all (global data input) |
| Machinery modules (incl. `732550b5` fetch/listing.py, awards, award_links, kinds' lazy dispatch, `run_build`'s kept-scope lazy imports) | 33 | refetch all |

About **7 of 40** past commits keep reuse, not the plan's earlier "about 10".
The `awards`/`award_links` figure is **0 s** — with the F2 dispatch refactor
dropped, both stay inside the machinery through `kinds.py`. **32** post-fetch
modules (assembly family of 12, `draw`, `gate_report`, the `heights` family,
`property` family of 5, `places_fsq.assemble`, `review.graph`,
`singles.families`, `method_card_validation`, `gis.layers`, `atlas.contracts`,
`gravity.contracts`) lie outside the machinery; `busyness.*` is inside it.

## Limits and consequences

- The gain is real but bounded: registry-row-only, records-only and
  post-fetch-only changes keep reuse; every machinery or review-file change
  refetches everything, exactly as before.
- The seed remains bound at run level; a different seed still refuses.
- Note-only rows (`note()` completions: grids, benchmark, BACI, Gravity, Atlas,
  besttime, skipped and register rows) carry no fingerprint and are simply
  re-executed on resume, as before.
- A later task may move `run_build`'s `busyness`/`building_inputs`/`series`/
  `places.integrate` lazy imports into named post-fetch scopes to shrink the
  machinery; it is recorded as an open item and is not built here.
- No live acquisition, network or real cache is used by the tests; every fixture
  is synthetic.

## What would change this decision

- A finding that a stale byte or stale check result can be reused despite the
  fingerprint, receipt and page-meta gates.
- A measured resume cost (scan, hashing and journal write) that exceeds the
  refetch it saves on the workloads that matter.
- The later machinery-shrinking task materially changing what the computed
  closure covers; it would amend the scope-exclusion list and the counts above.
