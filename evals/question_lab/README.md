# S3 conversation lab

Authority: TASKS.md **S3-T21**, decisions **0044 items 1–8** and **0049 items 1–6**. The implementation plan and the binding design-review findings F1–F3 are in the task's overnight handoff. This directory is evaluation tooling, never a product import or a gateway class.

Run from the repository root:

```sh
./eii question-lab run --n 100 --seed 17
```

`N` counts **distinct question identities**, each executed in English and Arabic. The current manifest supplies exactly 100 identities and 200 language executions: 30 flagship, 30 map, 20 chip and 20 typed-refusal scenarios. Each has a different invented pin; the four selection modes use four expected anchor cells and four expected values, as fixed in the manifest. Screenshots, repetitions, warmups and another seed never add identities. Larger requests fail capacity rather than repeat questions. The closed parser requires `run`, one `--n` and one `--seed`, ASCII non-negative integer arguments of at most six digits, and `N` at least 100. Case order is ascending SHA-256 of `question-lab.v1:<seed>:<identity>`, independent of manifest order.

Question text is an invented scenario description. It is never passed to a nonexistent free-text router. The actual S3 path runs the existing invented release through its real loader, embedded store, typed routes, accounting gate, template SSE, card reader and source projection. Map cases also check the bilingual gazetteer against independently specified place keys and outlines. Expected values, ma1 identities, source fields and Fact identities are derived from the fixed fixture specification, not from the answer. The fixture's recording second store is **not live store-parity evidence**.

## Evidence and fail-closed operation

After validating git identity, the ledger, output path and budget shape, an invocation creates an exclusive `runs/run-<opaque-id>/manifest.json` before constructing the app. It records the full base commit, provider `none`, seed, input and budget hashes, runtime and scope. Dirty code and changed inputs prevent qualification. The runner strips inherited provider credentials and records even caught socket/provider attempts. Its Python guard covers connect, connect_ex, datagram and vectored-datagram sends and name resolution; it is a fixture guard, not a substitute for the generator's OS sandbox. No database service or external source is contacted.

The packet contains planned and actual coverage with empty cells, complete bilingual-result accounting, JSONL and CSV per-question results, actual API event traces, timing status, qualification failures, and a linked author gallery. JSONL retains each judgement's scope: an API accuracy pass is partial, never a complete UI judgement. The 100 author-visible scenarios are not held-out cases; the separately authored evaluator supplement remains unprovisioned and contributes no count.

Keep these inputs in version control: `cases.v1.json`, `budgets.v1.json`, `guards.v1.json`, the code, `gallery_index.v1.json` and the append-only `ledger.jsonl`. Entire per-run packets, traces and PNGs under `runs/` are git-ignored. Each ledger row binds its predecessor bytes and the packet hashes. Existing committed prefixes cannot be changed or deleted. Failed packets remain recorded after a code correction; a new run never replaces one.

At this head **qualification exits 1**. The command deliberately reports missing prerequisites and external evidence rather than inventing a success. The following are waiting:

- S3-T10's dated opening chip and mounted firms chain, as stated in document 14 **S3-T10 opening implementation and evidence boundary**.
- Ratified, committed budgets and named native stage and phone devices, before measurement. The proposal file has `ratification: waiting` and both device identities null. No duration is measured by the functional API runner.
- An independent evaluator identity and author-inaccessible sealed volume. `seal()` probes a dedicated canary, not a held-out prompt; missing files do not prove denied reads. Readable and copied-canary plants fail. No separate identity has been provisioned or proved here.
- Installed local browser assets and approved CI pixel baselines. There is no download, retry, skip or baseline-refresh path. Missing or unapproved baselines fail. Native Arabic approval, another maker's exact-head review and the owner's beauty review remain external gates.
- Full browser observations, applied camera/pin/land evidence, interruption/clarification episodes and complete value checks. Unsupported pay/lookup/footfall text routes are uncovered under S8-T03. Ranking explanations belong to S6-T11 and speech to S8-T10.

## Capture and parity companions

`web/playwright.question-lab.config.ts` reuses the S3 opening fixture and `openingReport`. It discovers 4,800 question/size/language/theme cases, with answer, comparison, evidence and drawer captures per case. The twelve sizes are the eight decision 0049 sizes, both phone rotations, and retained TST-90 sizes. No breakpoint is added. Refusal screens unsupported by the current UI fail explicitly; the adapter never renders its own answer. Snapshot updates are disabled; baselines require the separate CI manifest. Software-rendered captures are functional/pixel evidence only.

The browser companion starts only after its local-asset, prior-budget and CI-baseline prerequisites. Its subprocess has provider `none`, an environment allowlist, one worker, zero retries and unchanged per-test limits. The full browser execution has not passed in this workspace. Discovery is not execution evidence. The author gallery refuses sealed captures and external/escaping links; its curated index is waiting until real captures exist. Remote access remains S3-T20's task.

The card oracle compares exact locale catalogue slots, paired Fact identities, semantic states, depth, caveats and Western numeric strings/separators. Localized calendar month words are checked by locale text/formatter contracts, while numeric runs retain their separators. Component plants replace an Arabic caveat with English, insert uncatalogued text, alter a Fact chip, add a raw numeral and add unknown candidate properties. The production `answerAccepted` boundary now rejects extra top-level properties, including from structurally typed callers; application-owned templates and Fact chips still render the screen.

## Timing and negative proofs

The proposed limits are in `budgets.v1.json`, from the task plan **Page 4** and document 12 **TST-130–133**. The first map-action p95 is strictly below 500 ms; evidence and complete-brief targets remain 2 s and 6 s. Strictness, worst limits, frame intervals, layout shift, interaction counts, 200 measured requests and 20 warmups are retained. Locks require identical committed bytes; history rejects a later loosening. Nonfinite/Boolean limits and samples fail. There is no override.

`timing.py` grades raw native-trace fixtures and reports nearest-rank p50, p95 and worst by device, locale and temperature. It preserves warmup failures and rejects software rendering, missing/duplicate samples, bad or null device identities, unratified budgets, malformed trace groups or sample lists, altered locks, missing accounting, late warmups and exceeded budgets. Fixture inputs are not device evidence and a JSON assertion cannot authenticate prior locking or human approval. Actual native capture and evidence ingestion remain waiting.

`guards.v1.json` maps the guards to their planted violation, intended diagnostic and executable test. Root Python tests, the rendered-card tests and the Node baseline/path tests run in the existing suite discovery. The real red/green commands and remaining checks are recorded in the return report and PROGRESS; no slice gate or independent approval is claimed.
