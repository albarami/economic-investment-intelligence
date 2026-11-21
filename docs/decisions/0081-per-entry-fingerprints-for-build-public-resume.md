# Decision 0081: Per-entry fingerprints replace the checkout-HEAD gate of `./eii build-public --resume`

| | |
|---|---|
| Status | Proposed, 2026-11-21: built under the owner's S2-P39 approval and plan 3's independent design review, for different-maker confirmation |
| Date | 2026-11-21 |
| Owner | The owner |
| Decided by | The owner's S2-P39 approval of 2026-11-21 (no loss of quality; any doubt means refetch), recorded in [PROGRESS.md](../../PROGRESS.md) S2-P39; design independently approved by the plan-3 design review (Anthropic Opus) with five records-only corrections applied |
| Amends | The `--resume` reuse rule recorded for S2-P37 in [document 13](../13_DEPLOYMENT_AND_OPERATIONS.md) command table, the [README](../../README.md) S2-P37 paragraph and `AGENTS.md`/`CLAUDE.md` rule 44; named by the task brief as an amendment of decision 0077's resume rule |
| Purpose | Let `./eii build-public --seed N --resume` reuse proven fetched bytes across unrelated code and data changes, with unchanged quality and an explicit refetch whenever proof is unavailable or uncertain |
| Read first | [PROGRESS.md](../../PROGRESS.md) S2-P37 and S2-P39; `custodian/src/eii_custodian/publicdata/fetch/fingerprint.py` and `fetch/resume.py` |

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
2. **Fingerprint contents.** The fingerprint of an entry binds: the closed-encoded
   constructed `Entry`, which carries every field of its registry row, the named
   dispatch branch (including the explicit `grid` and `large` selections), the
   interpreter version, the `uv.lock` SHA-256, a hash of the computed code
   closure of the machinery and the branch, a loaded-module digest of every
   repository module under the runtime roots loaded before the run begins
   that lies outside that
   closure, the named `eii` shell launcher, and one canonical hash of every
   git-tracked file under `custodian/publicdata/` (the global data input;
   `sources.yaml` rows stay bound per registry row and
   `tenders_pub.intermediate.pem` stays pinned by `chain_intermediate_sha256`).
   For `tenders_pub` the intake triple (award
   cutoff, cutoff reason, workbook SHA-256) is stored from the awarded-list
   receipts at fetch completion and recomputed through `intake_cutoff` on
   resume. Listing entries fold
   the canonical rows of every registry key under `entry.key + "/"`.
   Stored and current fingerprints compare as canonical JSON text.
3. **Computed closure.** The machinery is the static import closure of the fetch
   loop seeds (`fetch/build.py`, `fetch/resume.py`, `commands.build_public`,
   `earthdata_key`) scanned by AST over module-level and function-level imports,
   relative imports, parent-package `__init__` modules and literal
   `importlib.import_module` targets, resolved by `importlib.util.find_spec`
   under the build's actual `sys.path`; bare script imports such as `cdse_key`
   join it. Of the named `build.py` scopes excluded from it, `_seeded_assembly`
   runs before the fetch loop and is bound through the loaded-module digest of
   item 4; the rest run only after the fetch loop or only for note-only rows,
   an unlisted scope is machinery by default, `.venv`, `.git` and
   `node_modules` are excluded code roots, and this closed set of dynamic
   forms refuses the fingerprint: any reference — call or not — to
   `__import__`, `exec`, `eval`, `compile`, `runpy`, `codeop`, `pkgutil`,
   `zipimport`, `pickle`, `shelve`, `importlib.machinery`, `importlib.reload`,
   `importlib._bootstrap`, `importlib.util.module_from_spec`,
   `importlib.util.spec_from_loader` or
   `importlib.util.spec_from_file_location`, `types.CodeType`,
   `types.FunctionType`, `types.LambdaType`, `code.interact`,
   `code.InteractiveConsole` and `code.InteractiveInterpreter`,
   `sys.meta_path` and `sys.path_hooks`, frame or module-object access
   through `sys._getframe`, `sys._current_frames` or `inspect.currentframe`,
   `inspect.stack`, `inspect.getouterframes`, `inspect.getinnerframes`,
   `inspect.getframeinfo`, `inspect.trace` and `inspect.getmodule` (the bare
   name `inspect` stays legal), `__builtins__`, the `__dict__` of `sys`,
   `importlib` or `builtins`, `os.sys`, any attribute named `load_module`,
   `exec_module`, `__getattr__` or `__getattribute__`,
   `operator.attrgetter` and `operator.methodcaller`,
   a `*` import from `sys`, `builtins`, `codeop`, `pickle`,
   `shelve`, `pkgutil`, `runpy`, `zipimport`, `importlib` or anything under
   it, a `getattr` on `importlib`, `builtins` or `sys`, a `getattr` anywhere
   with a literal attribute from the same loading and module-state set, a
   `vars()` on the same three roots, any `sys.modules` access (the one
   named exception is `fingerprint.py`'s own baseline read in
   `_qualifying_modules`), and any `importlib.import_module` reference that
   is not the direct callee of a call with a literal first argument. Stated
   limits: execution that leaves the process the scan and guard can see —
   `subprocess`, `os.system`, `ctypes` and the other FFI or process-spawning
   forms (`fingerprint.py` itself uses `subprocess` for `git ls-files`),
   deserializers that execute code other than `pickle` and `shelve` (for
   example `dill`), a `getattr` with a computed attribute name, and
   execution of a file that never enters `sys.modules` through a form this
   list does not name. In this checkout the machinery
   computes to **195 modules** at build time (the review's static scan
   estimated 188 plus
   `cdse_key`; the difference is environment-dependent resolution, not scope).
   Every branch root of the dispatch map is already inside it, so the union
   measures the same 195; an added lazy import inside a kept scope invalidates
   every entry.
4. **Runtime guard.** At each recorded `fetched()` the loaded modules whose
   origin file lies under the runtime roots — `custodian/src`, `core/src`,
   `product/src`, `gateway/src` and `scripts/` — are compared with the union
   computed at run start; anything new and in-repository makes the item
   `resume_fingerprint_unproven` instead of silently binding it. Modules
   loaded
   before the run begins — `scripts/commands/main.py`, the pre-fetch
   `_seeded_assembly` import chain and the test runner's own imports, for
   example — are the recorded baseline; they do not trip the guard, and each
   baseline file outside the computed closure is hashed at run start and folded
   into every record's loaded-module digest, so an edit to one refetches. In
   the production shape **20** module files are bound by that digest: the five
   launcher modules (`scripts/commands/main.py`, `database.py`,
   `placeholder.py`, `preflight_cmd.py`, `up_cmd.py`), the six assembly
   modules of `_seeded_assembly` and nine `scripts/` modules (`preflight.py`,
   `preflight_database.py`, `preflight_proc.py`, `preflight_rows.py`,
   `preflight_store.py`, `pack_anchors.py`, `versions_inputs.py`,
   `versions_record.py`, `versions_tools.py`) that `preflight_cmd.py`,
   `up_cmd.py` and `database.py` import at module level. The
   `eii` shell launcher, no Python module, is bound as a named hashed file of
   every record. Stated limit: a module whose file lies under the checkout
   but outside the runtime roots is bound by nothing — the baseline and the
   guard both stay inside the runtime roots, since widening them to the whole
   checkout makes the hash read stale or missing files under scratch folders
   and refuse the proof; the tracked test
   `test_production_shape_loads_no_checkout_module_outside_the_bound_set`
   proves the production process keeps every loaded module under the runtime
   roots (the unbound remainder is the review probe itself and the test
   harness).
5. **Fail closed.** A missing or tampered fingerprint, an unresolvable first-party
   import, a dynamic import form, an unsupported `Entry` field type, an untracked
   file under `custodian/publicdata/`, a tracked input missing from the working
   tree, an unexpected loaded module or a changed intake triple each leave the
   entry without proof: it is refetched, or the item is marked
   `resume_fingerprint_unavailable` / `resume_fingerprint_unproven` and refetched
   on the next resume. A proof that cannot be computed at all — the closure
   scan raising on any refused form, an unresolvable import or an unreadable
   module — never refuses the build, ordinary or resume: the run fetches with
   no fingerprints and every fetched item is marked
   `resume_fingerprint_unavailable` (lead ruling L-1379). A version-1 journal
   keeps its old refusal names:
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
dropped, both stay inside the machinery through `kinds.py`. **26** post-fetch
modules (assembly family of 6, `draw`, `gate_report`, the `heights` family,
`property` family of 5, `places_fsq.assemble`, `review.graph`,
`singles.families`, `method_card_validation`, `gis.layers`, `atlas.contracts`,
`gravity.contracts`) lie outside the machinery unbound; `busyness.*` is inside
it. Twenty modules — the six assembly modules `assembly.py`,
`assembly_adapters.py`,
`assembly_intake.py`, `assembly_inventory.py`, `assembly_io.py` and
`assembly_profile.py`, the five launcher modules of `scripts/commands/` and
the nine `scripts/` modules the command modules import — are loaded before
the run begins and bound by the loaded-module digest, so an edit to one
refetches everything.

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
- For the record, unchanged from version 1 and not regressions: reuse does not
  bind the wall clock (period forms, the weather grid), proxy variables of the
  environment, or the Earthdata token value.
- No live acquisition, network or real cache is used by the tests; every fixture
  is synthetic.

## What would change this decision

- A finding that a stale byte or stale check result can be reused despite the
  fingerprint, receipt and page-meta gates.
- A measured resume cost (scan, hashing and journal write) that exceeds the
  refetch it saves on the workloads that matter.
- The later machinery-shrinking task materially changing what the computed
  closure covers; it would amend the scope-exclusion list and the counts above.
