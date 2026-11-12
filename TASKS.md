# EII build task queue

This is the ordered queue consumed by the build run.
Each task is a few focused units of work with a visible or executable result.
Tasks in slice S0 through slice S3 are deliberately fine-grained and each should fit one short agent assignment.
Tasks in slice S4 through slice S11 are coarser and are refined at the preceding slice gate.

## Queue rules

- One task uses one branch and one pull request.
- Feature work is never committed directly to the base branch.
- The lead permits GitHub pushes strictly one at a time.
- The builder and first reviewer must come from different makers.
- Every task brief starts with the stated builder persona and reviewer persona.
- A task is done only when it is built, verified, reviewed, merged and green in CI.
- A reviewer returns only `APPROVED` or `REJECTED`; a rejection includes exact fixes. After round 1 only the kinds of finding of REV-39 reject; other valid points are proposed open items ([decision 0015](docs/decisions/0015-review-rounds-and-the-scope-of-repository-checks.md)).
- Acceptance evidence records the command or check, result, full commit hash and review verdict.
- Files outside the task's scope are read-only.
- Parallel tasks must have disjoint writable scopes; otherwise the lead serializes them.
- A task may be built ahead in a worktree on the pushed head of one base task that is still in review, in a fix round or in CI, when the lead's checks are green on that head and its open findings do not change what the new task builds on; one level only. It is not pushed and gets no pull request before its base is merged and it is rebased onto `main`; then every check is rerun.
- Each slice ends with a follow-up task before its gate that closes every proposed open item of the slice's reviews (REV-41); it is the last task of each slice below.
- All tasks start with status `queued`.
- Requirement references below are to IDs defined in the numbered documentation pack; this file defines no requirement IDs.

## Difficulty and personas

`routine` guides the lead towards a fast or mid-tier model.
`hard` guides the lead towards a strong model, with the top model reserved for expensive-to-get-wrong work.

Persona abbreviations used below:

- Platform: senior platform engineer / principal platform and supply-chain reviewer.
- Data: senior data engineer / principal data quality and provenance reviewer.
- Simulation: senior simulation engineer / principal statistical simulation reviewer.
- Privacy: senior disclosure-control engineer / principal privacy and adversarial reviewer.
- Backend: senior backend and database engineer / principal backend security reviewer.
- Methods: senior applied economist and calculation engineer / principal economic-methods reviewer.
- Frontend: senior bilingual product engineer / principal design, accessibility and data-visualisation reviewer.
- AI: senior AI systems engineer / principal AI safety and evaluation reviewer.
- Operations: senior demonstration producer / principal operational-readiness reviewer.

## slice S0 — Foundation

slice S0 begins with the environment, repository structure and dependencies.

### S0-T01 — Repository scaffolding and tool configuration
- Goal: Create the pinned repository layout and root configuration without implementing product behaviour.
- Acceptance criteria: [x] every pinned top-level folder exists; [x] ignores exclude generated data and secrets; [x] the tree check passes.
- Scope: root configuration, `contracts/`, `core/`, `custodian/`, `product/`, `web/`, `evals/`, `gateway/`, `infra/`, `scripts/`, `data/`.
- Depends: none.
- Requirements: ARC-01, PLN-22, TST-163.
- Delivery: routine; personas Platform; status done (pull request 1, merged 2026-11-12).
### S0-T02 — Python workspace and three packages
- Goal: Create one `uv` workspace containing `eii_core`, `eii_custodian` and `eii_product`.
- Acceptance criteria: [x] Python resolves all three packages; [x] each package imports in a clean environment; [x] workspace metadata names no forbidden dependency edge.
- Scope: root Python workspace files, `core/`, `custodian/`, `product/`.
- Depends: S0-T01.
- Requirements: ARC-01, BE-01, TST-60.
- Delivery: routine; personas Platform; status done (pull request 4, merged 2026-11-12).
### S0-T03 — Web application skeleton
- Goal: Create the React, TypeScript and Vite application shell with no feature UI.
- Acceptance criteria: [x] development build starts; [x] production build succeeds; [x] no run-time asset uses a third-party host.
- Scope: `web/`, web package and TypeScript configuration.
- Depends: S0-T01.
- Requirements: FE-01, FE-05, FE-07, DES-24.
- Delivery: routine; personas Frontend; status done (pull request 3, merged 2026-11-12).
### S0-T04 — Lint, format and type checks
- Goal: Make Python and web linting, formatting and type checks reproducible.
- Acceptance criteria: [x] each check has one documented command; [x] planted violations fail; [x] clean scaffolding passes.
- Scope: lint, formatter and type-checker configuration; check scripts only.
- Depends: S0-T02, S0-T03.
- Requirements: PLN-07, TST-161, TST-162, FE-11.
- Delivery: routine; personas Platform; status done (pull request 5, merged 2026-11-12).
### S0-T05 — Test runners
- Goal: Make `./eii test` run every network-free Python and web pull-request suite.
- Acceptance criteria: [x] suite counts are printed; [x] a failing fixture makes the command non-zero; [x] clean suites exit zero.
- Scope: test configuration, test bootstrap files, `scripts/` test runner.
- Depends: S0-T02, S0-T03.
- Requirements: TST-15, TST-01, PLN-14, FE-95.
- Delivery: routine; personas Platform; status done (pull request 7, merged 2026-11-12).
### S0-T06 — Pre-commit hooks
- Goal: Run formatting, lint, documentation, secret and identifier checks before commits.
- Acceptance criteria: [ ] hooks install from repository configuration; [ ] generated forbidden tokens are caught; [ ] a commit guard refuses any staged value equal to a non-empty local secret without printing the value; [ ] clean staged files pass.
- Scope: pre-commit configuration and scanner test fixtures.
- Depends: S0-T04, S0-T05.
- Requirements: TST-141, TST-144, PLN-05.
- Delivery: routine; personas Platform; status queued.
### S0-T07 — Continuous integration
- Goal: Build CI for tests, documentation checks, secret scanning, identifier-pattern scanning and the hosted-runner sandbox proof.
- Acceptance criteria: [ ] all check classes run on pull requests; [ ] the sandbox test runs on the hosted runner and is never skipped; [ ] planted failures block CI; [ ] the foundation commit is green.
- Scope: CI workflow files and CI-only setup scripts.
- Depends: S0-T04, S0-T05, S0-T06.
- Requirements: TST-61, TST-62, TST-140, TST-141, TST-150.
- Delivery: routine; personas Platform; status queued.
### S0-T08 — Compose and store preflight
- Goal: Add the portable database service and probes that select a store without starting or stopping it.
- Acceptance criteria: [ ] Compose defines the pinned database and PostGIS line; [ ] probes time out as specified; [ ] absent PostgreSQL selects embedded with a warning; [ ] with `EII_RELEASE_DIR` unset, foundation preflight exits zero, reports `WARN not_configured` for release, load-receipt, embedded-reader and recorded-replay checks, and keeps every other check's normal severity; [ ] `up` still refuses without a configured complete release.
- Scope: `infra/compose.yaml`, preflight probe modules and probe tests.
- Depends: S0-T01, S0-T02.
- Requirements: OPS-06, OPS-09, OPS-17, BE-87.
- Delivery: hard; personas Platform; status in review (pull request 10, round 3, part A; part B after the open documentation pull request merges; part C after S0-T07, S0-T11 and S0-T12 merge).
### S0-T09 — `./eii` command skeleton and database commands
- Goal: Create every pinned command entry point, including `db-up` and `db-down`, with safe placeholder dispatch.
- Acceptance criteria: [ ] usage lists every pinned command; [ ] `preflight` only probes; [ ] `db-up` and `db-down` alone start and stop the database; [ ] `up` never starts it.
- Scope: root `eii` launcher and `scripts/commands/`.
- Depends: S0-T08.
- Requirements: OPS-26, OPS-27, OPS-28, ARC-96.
- Delivery: hard; personas Platform; status queued.
### S0-T10 — Import-boundary test
- Goal: Enforce the three-plane imports before feature code exists.
- Acceptance criteria: [ ] direct, local and dynamic forbidden imports fail; [ ] package metadata edges are checked; [ ] clean packages pass.
- Scope: boundary test module and planted fixtures only.
- Depends: S0-T02.
- Requirements: ARC-06, BE-01, TST-60.
- Delivery: hard; personas Backend; status in review (pull request 8, round 2; part B after pull requests 6 and 7 merge).
### S0-T11 — Generator sandbox test
- Goal: Prove locally and on the hosted CI runner that the `build-world` and `build-release` sandbox profiles cannot read outside their allowed mounts or open the network.
- Acceptance criteria: [ ] both prohibited operations fail under both profiles locally and on the hosted runner; [ ] the read tooth succeeds outside; [ ] CI never skips the test; [ ] a runner restriction on unprivileged user namespaces is handled by a per-binary bubblewrap AppArmor profile or fails the job; [ ] engine extensions are fetched before sandbox entry into a project-local folder mounted read-only and load with the network off.
- Scope: sandbox launcher, hosted-runner namespace setup, project-local engine-extension folder, sentinel generator and sandbox tests.
- Depends: S0-T02, S0-T05.
- Requirements: ARC-09, ARC-10, ARC-14, SYN-01, TST-61, TST-62.
- Delivery: hard; personas Platform; status queued.
### S0-T12 — Version and retreat pins
- Goal: Pin supported toolchains and libraries with written retreat pins where the design requires them.
- Acceptance criteria: [ ] lock files resolve; [ ] exact and retreat pins are labelled; [ ] unsupported version drift fails a check.
- Scope: lock files, version files and dependency constraints.
- Depends: S0-T02, S0-T03.
- Requirements: FE-03, TST-153, PLN-15, TST-43, BE-13.
- Delivery: hard; personas Platform; status in review (pull request 9, round 2; part B after the open documentation pull requests merge).
### S0-T13 — New-library reference notes
- Goal: Give agents verified official-reference notes for libraries newer than most model training data.
- Acceptance criteria: [ ] each named newer library has an official-documentation pointer; [ ] no API behaviour is asserted from memory; [ ] slice S1 confirmation fields exist.
- Scope: dependency reference notes under `docs/` assigned to this task only.
- Depends: S0-T12.
- Requirements: FE-02, PLN-10, PLN-18, TST-01.
- Delivery: routine; personas Platform; status queued.
### S0-T14 — GitHub repository settings
- Goal: Enable secret scanning, push protection and branch protection under OI-13.
- Acceptance criteria: [ ] each setting is queried after change; [ ] evidence records the result; [ ] no repository file or git setting is changed by the task.
- Scope: GitHub repository settings only; repository files are read-only.
- Depends: S0-T07.
- Requirements: TST-141, PLN-06, PLN-12.
- Delivery: routine; personas Platform; status queued.
### S0-T15 — Review follow-up for slice S0
- Goal: Close every proposed open item that the reviews of slice S0 entered in `OPEN_ITEMS.md`, before the slice S0 gate.
- Acceptance criteria: [ ] each item of the slice is closed by a fix or by one line saying why it is not valid or is out of scope under REV-42; [ ] the reviewer checks every closure; [ ] no item is deferred out of this task; [ ] no item of the slice is left open.
- Scope: the files the closures change, and `OPEN_ITEMS.md`.
- Depends: every other task of slice S0.
- Requirements: REV-41, TST-168.
- Delivery: routine; personas as the items require; status queued.

## slice S1 — Technical spike

### S1-T01 — Arabic glyph and label-order spike
- Goal: Prove self-hosted Arabic glyphs render with hexagons below labels.
- Acceptance criteria: [ ] Arabic labels render from local assets; [ ] hexagons do not cover labels; [ ] visual evidence is recorded.
- Scope: `web/spikes/glyphs/`, local font and glyph spike assets.
- Depends: S0-T03, S0-T12.
- Requirements: FE-46, FE-56, FE-57, DES-24, DES-10.
- Delivery: hard; personas Frontend; status queued.
### S1-T02 — Map load and frame-rate spike
- Goal: Measure the pinned hexagon and particle load in a native host browser.
- Acceptance criteria: [ ] 110,000 hexagons render; [ ] 50,000 particles render; [ ] the trace records 60 frames per second on the build machine.
- Scope: `web/spikes/performance/` and performance scripts.
- Depends: S1-T01.
- Requirements: TST-132, FE-88, PLN-07.
- Delivery: hard; personas Frontend; status queued.
### S1-T03 — Isochrone-to-grid spike
- Goal: Convert one in-process routing isochrone into whole snapped grid cells.
- Acceptance criteria: [ ] routing has no server; [ ] output contains only frame cells; [ ] a deterministic fixture passes.
- Scope: routing spike under `product/` and its fixtures.
- Depends: S0-T02.
- Requirements: ARC-88, BE-82, PRV-10.
- Delivery: hard; personas Backend; status queued.
### S1-T04 — Tile range-request spike
- Goal: Serve one local tile artefact with correct byte-range behaviour.
- Acceptance criteria: [ ] full request succeeds; [ ] valid ranges return expected bytes; [ ] invalid ranges fail safely.
- Scope: tile spike API, fixture and tests only.
- Depends: S0-T03, S0-T05.
- Requirements: OPS-30, FE-56, FE-58, TST-167.
- Delivery: routine; personas Backend; status queued.
### S1-T05 — First two-store parity query
- Goal: Run one portable named query against PostgreSQL and DuckDB with identical normalised output.
- Acceptance criteria: [ ] both adapters answer; [ ] rounding is explicit; [ ] a deliberate divergence fails parity.
- Scope: store spike adapters, one SQL file and parity fixture.
- Depends: S0-T08, S0-T12.
- Requirements: BE-26, TST-40, PLN-19.
- Delivery: hard; personas Backend; status queued.
### S1-T06 — Sandbox enforcement spike
- Goal: Confirm the production sandbox boundary on the build machine without a fallback.
- Acceptance criteria: [ ] sentinel read and network attempts fail; [ ] mount list matches policy; [ ] any enforcement failure blocks the task.
- Scope: sandbox implementation and slice S1 enforcement evidence.
- Depends: S0-T11.
- Requirements: ARC-09, SYN-01, TST-61.
- Delivery: hard; personas Platform; status queued.
### S1-T07 — Offline typed-decision gateway
- Goal: Build the provider-neutral gateway contract, `none`, recorded and configured providers, decision records, data policy and import boundary.
- Acceptance criteria: [ ] default `none` opens no network; [ ] forbidden data classes are blocked; [ ] records use the closed schema; [ ] serving packages cannot import the gateway.
- Scope: `gateway/`, gateway-only tooling under `scripts/`, gateway contract tests.
- Depends: S0-T02, S0-T10.
- Requirements: DAT-126, BE-102, AI-98, PLN-20.
- Delivery: hard; personas AI; status queued.
### S1-T08 — Typed-decision requalification and pin ruling
- Goal: Re-run `evals/typed_decisions/` in both fixed option orders, compare the stated intervals and confirm exact and retreat pins.
- Acceptance criteria: [ ] the full set runs; [ ] the admitted measurement is reproduced within its stated intervals; [ ] every choice case runs in both hash-derived option orders and is accepted only when both agree; [ ] results and route identity are recorded; [ ] drift triggers requalification; [ ] any accepted alternative has a decision record.
- Scope: `evals/typed_decisions/`, slice S1 spike report and dependency pin decision.
- Depends: S1-T02, S1-T03, S1-T04, S1-T05, S1-T06, S1-T07.
- Requirements: FE-03, TST-155, AI-98, TST-167, PLN-15.
- Delivery: hard; personas AI; status queued.
### S1-T09 — Exported set and index scales
- Goal: Fix `export_parameter_set` = `A`, `presence_scale` and `flow_scale` in the rules configuration before the first world build.
- Acceptance criteria: [ ] `export_parameter_set` is `A` unless open item OI-35 is closed with another value by the owner or a data owner; [ ] `presence_scale` and `flow_scale` are positive and recorded in the slice S1 gate evidence; [ ] the name `presence_base` is not used; [ ] a missing or non-positive scale fails the configuration check.
- Scope: rules configuration and the slice S1 gate check.
- Depends: S1-T08.
- Requirements: PRV-05, PRV-59, PRV-120.
- Delivery: hard; personas Privacy; status queued.
### S1-T10 — Review follow-up for slice S1
- Goal: Close every proposed open item that the reviews of slice S1 entered in `OPEN_ITEMS.md`, before the slice S1 gate.
- Acceptance criteria: [ ] each item of the slice is closed by a fix or by one line saying why it is not valid or is out of scope under REV-42; [ ] the reviewer checks every closure; [ ] no item is deferred out of this task; [ ] no item of the slice is left open.
- Scope: the files the closures change, and `OPEN_ITEMS.md`.
- Depends: every other task of slice S1.
- Requirements: REV-41, TST-168.
- Delivery: routine; personas as the items require; status queued.

**slice S1 gate.** Arabic labels render with self-hosted glyphs; hexagons remain under labels; 110,000 hexagons and 50,000 particles render at 60 frames per second; an isochrone is turned into grid cells; tiles are served with range requests; PostgreSQL and DuckDB answer one parity query; and the sandbox works. Each item passes its named test. A technical alternative is accepted only if it keeps the same user-visible capability, passes the same assertion and is recorded as a decision. No fallback is permitted for sandbox enforcement, store parity or any security check. The rules configuration fixes `export_parameter_set` (default `A`), `presence_scale` and `flow_scale` before any world is built.

## slice S2 — Public pack, frame, spine, places

### S2-T01 — Public fetchers and source receipts
- Goal: Register every Public input required by any pack document, fetch only allow-listed licensed sources and store complete provenance receipts.
- Acceptance criteria: [ ] only `build-public` opens source connections; [ ] every required Public input is present in the registry, including citation-only metadata; [ ] every fetched file has URL, publisher, licence, retrieval date and hash; [ ] a source with no stated licence is validation-only and contributes no value, derived share, title or geometry to a release.
- Scope: `custodian/publicdata/fetch/`, source registry and fetch tests.
- Depends: S1-T08.
- Requirements: PUB-01, PUB-19, TST-50.
- Delivery: hard; personas Data; status queued.
### S2-T02 — Frame and gazetteer
- Goal: Build zones, districts, fixed grid cells, release-unit geometry inputs, bilingual gazetteer records and the municipality-population, national-census and district-census Public tables.
- Acceptance criteria: [ ] crosswalk checks pass; [ ] district keys are present; [ ] `pub_population_municipality`, `pub_census_national` and `pub_census_district` validate; [ ] every showcase area and candidate flagship is resolvable.
- Scope: public frame builders, gazetteer builder and frame tests.
- Depends: S2-T01.
- Requirements: PUB-24, PUB-30, SYN-10.
- Delivery: hard; personas Data; status queued.
### S2-T03 — Public series, customs and reconciliations
- Goal: Build the pinned Public series and customs inputs, reconcile both section 9 conflicts, and close OI-03.
- Acceptance criteria: [ ] section 9 regressions pass; [ ] restaurant scopes and wage-table names are reconciled; [ ] basket lines are reviewed; [ ] OI-03 has recorded closure evidence; [ ] an unresolved reconciliation emits no fact.
- Scope: public series builders, customs review files and reconciliation tests.
- Depends: S2-T01.
- Requirements: PUB-41, PUB-62, PUB-74, MTH-30.
- Delivery: hard; personas Data; status queued.
### S2-T04 — Activity spine and graph tables
- Goal: Build the reviewed activity spine, not-mappable bucket, graph tables and human review queue.
- Acceptance criteria: [ ] largest 200 codes, all food-service codes and all playbook codes are reviewed; [ ] every admitted mapping has human sign-off; [ ] the remainder is flagged; [ ] graph edges obey the Public-or-lineage rule.
- Scope: activity review files, spine builder, `graph_node`, `graph_edge` tests.
- Depends: S2-T01.
- Requirements: PUB-33, ARC-83, DAT-100.
- Delivery: hard; personas Data; status queued.
### S2-T05 — `spine_match` review triage
- Goal: Use the offline gateway only to order and pre-fill the activity human-review queue.
- Acceptance criteria: [ ] provider `none` leaves a valid deterministic queue; [ ] no mapping is adopted without sign-off; [ ] decision records stay under eval artefacts.
- Scope: `scripts/` spine triage and `evals/typed_decisions/runs/`.
- Depends: S2-T04, S1-T07.
- Requirements: AI-98, DAT-126, TST-155.
- Delivery: hard; personas Data; status queued.
### S2-T06 — Showcase places and flagship selection
- Goal: Build `pub_place_verification`, verify places in the four showcase areas and select a flagship building only from the recorded data check.
- Acceptance criteria: [ ] every `pub_place` row carries `source_provider`, `licence` and `confidence`; [ ] `pub_place_verification` is keyed to `pub_place` and stores check date, reviewer role, verification link and status; [ ] verification statuses are stored; [ ] the recorded candidate data check determines the flagship; [ ] all flagship checks pass; [ ] incomplete-listing caveat remains attached.
- Scope: place and place-verification builders, four review files, recorded flagship data check and decision fixture.
- Depends: S2-T01, S2-T02.
- Requirements: PUB-47, PUB-57, PUB-78.
- Delivery: hard; personas Data; status queued.
### S2-T07 — Calculation layer and method regressions
- Goal: Implement deterministic Public calculations in `eii_core.calc` with method-card regression tests.
- Acceptance criteria: [ ] no calculation reads files or databases; [ ] each implemented worked example has arithmetic and data tests; [ ] comparisons return facts rather than prose.
- Scope: `core/eii_core/calc/`, calculation tests and method-card test fixtures.
- Depends: S2-T03.
- Requirements: MTH-01, MTH-03, DAT-90.
- Delivery: hard; personas Methods; status queued.
### S2-T08 — Public pack assembly and source review
- Goal: Assemble the Public pack and close the slice S2 evidence bundle.
- Acceptance criteria: [ ] source completeness passes for every Public input required by the pack; [ ] validation-only sources contribute nothing to the release; [ ] the coverage bar uses and names the finest licensed geography available; [ ] OI-03 is closed; [ ] a different-maker reviewer checks twenty random figures; [ ] every regression and licence check passes.
- Scope: public build orchestration, slice S2 reports and review evidence.
- Depends: S2-T02, S2-T03, S2-T05, S2-T06, S2-T07.
- Requirements: REV-34, TST-50, PLN-07.
- Delivery: hard; personas Data; status queued.
### S2-T09 — Method-card pins from the public build
- Goal: After the reviewer has checked them against the source, write the values listed by MTH-03 into the method cards. Invent no value.
- Acceptance criteria: [ ] `./eii build-public` produces the unpinned inputs listed by MTH-03, including the riyal medians of the property-price method card; [ ] the reviewer checks each against its source before it is written; [ ] only checked values are written into the method cards; [ ] a value the source check cannot pin stays unpinned and is recorded in OPEN_ITEMS.md.
- Scope: method cards in `docs/07_ECONOMIC_METHODS.md` and the recorded source-check evidence.
- Depends: S2-T08.
- Requirements: MTH-03.
- Delivery: hard; personas Methods; status queued.
### S2-T10 — Review follow-up for slice S2
- Goal: Close every proposed open item that the reviews of slice S2 entered in `OPEN_ITEMS.md`, before the slice S2 gate.
- Acceptance criteria: [ ] each item of the slice is closed by a fix or by one line saying why it is not valid or is out of scope under REV-42; [ ] the reviewer checks every closure; [ ] no item is deferred out of this task; [ ] no item of the slice is left open.
- Scope: the files the closures change, and `OPEN_ITEMS.md`.
- Depends: every other task of slice S2.
- Requirements: REV-41, TST-168.
- Delivery: routine; personas as the items require; status queued.

**slice S2 gate.** Every stored Public figure has URL, licence, retrieval date and hash; the reviewer checks twenty random figures against their sources; every section 9 public regression example passes; regression values that the method cards could not pin are produced, checked against the source and written into the cards; and no file without a stated licence is committed.

## slice S3 — Public-only flagship answer

### S3-T01 — Store interface and portable query registry
- Goal: Implement named portable SQL and normalized results for the first Public tools.
- Acceptance criteria: [ ] tools cannot supply SQL; [ ] each registered tool has parity; [ ] the portability lint rejects forbidden SQL.
- Scope: `product/eii_product/store/`, named SQL and store tests.
- Depends: S2-T08.
- Requirements: BE-07, BE-26, TST-40.
- Delivery: hard; personas Backend; status queued.
### S3-T02 — Public release load in two stores
- Goal: Build, load and verify a `release_kind: public_only` release in PostgreSQL and the embedded reader.
- Acceptance criteria: [ ] the manifest contains no Protected or Simulated table and omits `window_key`, `protected_sha256`, `parameter_set`, `world_seed`, `scenario_sha256` and `contracts`; [ ] manifest-only loading succeeds in both stores; [ ] the loader-written `load_receipt.json` is not a manifest artefact and has `state: complete` and the matching manifest `release_id`; [ ] an extra table loads nowhere; [ ] both stores expose the same release identity; [ ] configured preflight passes; [ ] freeze and export-register entry are refused for this release kind.
- Scope: loader modules, Public release fixture and loader tests.
- Depends: S3-T01.
- Requirements: BE-44, BE-46, DAT-70, DAT-84, TST-63.
- Delivery: hard; personas Backend; status queued.
### S3-T03 — `resolve`
- Goal: Resolve Public places and activities with typed candidates and statuses.
- Acceptance criteria: [ ] bilingual fixtures resolve deterministically; [ ] unmapped codes stay visible; [ ] every returned numeral is a fact value.
- Scope: `product/eii_product/tools/resolve.py` and tests.
- Depends: S3-T01, S2-T04, S2-T06.
- Requirements: ARC-71, BE-49, DAT-90.
- Delivery: routine; personas Backend; status queued.
### S3-T04 — `make_area`
- Goal: Build snapped distance, walk and drive areas, including the staffing-only drive option and a Public-only path.
- Acceptance criteria: [ ] only closed cut-offs are accepted; [ ] Public-only mode uses the fixed base-cell frame and reads no privacy-derived release unit, protected table or simulated table; [ ] units are whole and deterministic; [ ] the snap report is technical metadata, not a Synthetic fact.
- Scope: `product/eii_product/tools/make_area.py`, routing adapter and tests.
- Depends: S3-T01, S1-T03, S2-T02.
- Requirements: ARC-88, BE-82, BE-105, PRV-10.
- Delivery: hard; personas Backend; status queued.
### S3-T05 — `scan_places`
- Goal: Return verified Public places with network distances and incompleteness caveats.
- Acceptance criteria: [ ] only Public places appear; [ ] distance facts have source chains; [ ] no synthetic property is attached to a real place.
- Scope: `product/eii_product/tools/scan_places.py` and tests.
- Depends: S3-T01, S3-T04, S2-T06.
- Requirements: BE-49, PUB-47, AI-42.
- Delivery: routine; personas Backend; status queued.
### S3-T06 — `sector_facts`
- Goal: Expose Public calculation facts through the store without recalculation by the assistant.
- Acceptance criteria: [ ] outputs come from `eii_core.calc`; [ ] worked examples still pass; [ ] every output validates as a fact.
- Scope: `product/eii_product/tools/sector_facts.py` and tests.
- Depends: S3-T01, S2-T07.
- Requirements: MTH-01, MTH-03, BE-49.
- Delivery: hard; personas Methods; status queued.
### S3-T07 — Catalogue foundations
- Goal: Create the four closed, versioned catalogues with strict schemas.
- Acceptance criteria: [ ] `claims.yaml`, `components.yaml`, `fragments.yaml` and `questions.yaml` exist under `product/assistant/catalogue/`; [ ] unknown claim, component, fragment and question keys and unknown properties fail; [ ] swapped valid fact slots fail; [ ] template scan rejects numerals.
- Scope: `product/assistant/catalogue/` and catalogue validation tests for all four files.
- Depends: S2-T07.
- Requirements: AI-28, AI-36, AI-37, AI-42, AI-45, AI-46, AI-88.
- Delivery: hard; personas AI; status queued.
### S3-T08 — Public playbook, API and template stream
- Goal: Serve evidence before a catalogue-rendered Public brief with no model call. The brief is buffered until the accounting gate has passed.
- Acceptance criteria: [ ] template output is deterministic; [ ] evidence cards may appear before the brief; [ ] the structured brief is buffered until the accounting gate passes; [ ] invalid components are not rendered.
- Scope: Public playbook, API streaming modules and tests.
- Depends: S3-T03, S3-T04, S3-T05, S3-T06, S3-T07.
- Requirements: BE-60, BE-65, AI-18.
- Delivery: hard; personas Backend; status queued.
### S3-T09 — Stage, Brief, Fact chip and source chain
- Goal: Build the core answer UI and refuse to render a fact without complete sanad.
- Acceptance criteria: [ ] only Fact chips render numerals; [ ] every chip opens its source chain; [ ] incomplete lineage refuses rendering; [ ] four provenance marks do not rely on colour.
- Scope: core Stage and Brief components, Fact chip, evidence drawer and tests.
- Depends: S0-T03, S3-T07.
- Requirements: FE-39, DES-71, DES-95, DAT-105.
- Delivery: hard; personas Frontend; status queued.
### S3-T10 — Bilingual Public opening and gate
- Goal: Deliver the English and Arabic Public-only flagship opening and complete its design audit.
- Acceptance criteria: [ ] end-to-end uses Public facts only; [ ] no model call occurs; [ ] parity and numeral lint pass; [ ] audit has no Blocker or Major finding.
- Scope: opening scene, bilingual strings, end-to-end and visual tests, design-audit evidence.
- Depends: S3-T02, S3-T08, S3-T09.
- Requirements: DES-06, DES-10, TST-80, TST-90, TST-100.
- Delivery: hard; personas Frontend; status queued.
### S3-T11 — Review follow-up for slice S3
- Goal: Close every proposed open item that the reviews of slice S3 entered in `OPEN_ITEMS.md`, before the slice S3 gate.
- Acceptance criteria: [ ] each item of the slice is closed by a fix or by one line saying why it is not valid or is out of scope under REV-42; [ ] the reviewer checks every closure; [ ] no item is deferred out of this task; [ ] no item of the slice is left open.
- Scope: the files the closures change, and `OPEN_ITEMS.md`.
- Depends: every other task of slice S3.
- Requirements: REV-41, TST-168.
- Delivery: routine; personas as the items require; status queued.

## slice S4 — Synthetic world and presence cube

These coarse tasks are refined at the slice S3 gate without weakening their criteria.

### S4-T01 — Contracts and conformance
- Goal: Implement unchanged conformance suites for all source contracts and the release contract.
- Acceptance criteria: [ ] every planted defect fails for the intended reason; [ ] only `SYN-E-`, `SYN-L-`, `SYN-G-`, `SYN-P-` and `SYN-F-` identifier forms are accepted for their pinned record types; [ ] headers and periods are required; [ ] coverage omissions never become zero.
- Scope: `contracts/`, conformance modules and fixtures.
- Depends: S3-T10.
- Requirements: DAT-09, DAT-12, TST-30.
- Delivery: hard; personas Data; status queued.
### S4-T02 — Register and employment world
- Goal: Generate the synthetic register and employment world only from public cache inputs.
- Acceptance criteria: [ ] establishment, legal-entity, employer-group and person identifiers use their pinned forms; [ ] no synthetic establishment carries a public place or gazetteer key, name or coordinates; [ ] names have zero real collisions; [ ] geography comes from the slice S2 frame; [ ] sandbox proof passes.
- Scope: `custodian/worldgen/register/`, `custodian/worldgen/employment/` and tests.
- Depends: S4-T01, S2-T02.
- Requirements: SYN-01, SYN-10, SYN-15.
- Delivery: hard; personas Simulation; status queued.
### S4-T03 — Wages, residence and linkage
- Goal: Generate monthly wages and residence, then deduplicate and link without ambiguous legal-entity joins.
- Acceptance criteria: [ ] the full month window conforms; [ ] every salary-file identifier uses `SYN-F-`; [ ] ambiguous registrations fail; [ ] no forbidden person attribute exists.
- Scope: wage and residence generators, `custodian/linkage/` and tests.
- Depends: S4-T02.
- Requirements: DAT-01, SYN-25, TST-30.
- Delivery: hard; personas Simulation; status queued.
### S4-T04 — Presence cube and mobility feeds
- Goal: Generate simulated situations, speed factors and aggregate feed tables without trajectories.
- Acceptance criteria: [ ] planted feed defects are counted; [ ] `presence_index` uses the fixed pre-committed `presence_scale`, and flow uses `flow_scale` (PRV-59); neither imposes a sum over protected rows; [ ] the name `presence_base` is not used; [ ] no person, device or trajectory enters the release input.
- Scope: `custodian/mobility/`, presence fixtures and tests.
- Depends: S4-T01, S2-T02.
- Requirements: SYN-46, SYN-51, PRV-57, PRV-59.
- Delivery: hard; personas Simulation; status queued.
### S4-T05 — Sealed reproducible world
- Goal: Seal the scenario and prove calibration, fidelity, collision safety and byte-identical rebuilding.
- Acceptance criteria: [ ] every calibration value is anchored or assumed; [ ] tolerances predate the run; [ ] hold-out H4 is reported only as a plausibility comparison and does not count as a hold-out; [ ] two clean builds match byte for byte; [ ] scenario hash is recorded.
- Scope: scenario, calibration manifest, fidelity report and reproducibility harness.
- Depends: S4-T03, S4-T04.
- Requirements: SYN-06, SYN-36, SYN-60, SYN-63.
- Delivery: hard; personas Simulation; status queued.
### S4-T06 — Review follow-up for slice S4
- Goal: Close every proposed open item that the reviews of slice S4 entered in `OPEN_ITEMS.md`, before the slice S4 gate.
- Acceptance criteria: [ ] each item of the slice is closed by a fix or by one line saying why it is not valid or is out of scope under REV-42; [ ] the reviewer checks every closure; [ ] no item is deferred out of this task; [ ] no item of the slice is left open.
- Scope: the files the closures change, and `OPEN_ITEMS.md`.
- Depends: every other task of slice S4.
- Requirements: REV-41, TST-168.
- Delivery: routine; personas as the items require; status queued.

## slice S5 — Privacy engine and release

These coarse tasks are refined at the slice S4 gate without weakening their criteria.

**Entry condition.** OI-37 is closed: a maker other than the one that last edited the privacy document has reviewed the lead's last ten corrections to it (made on 2026-11-11 after the second confirmation review), and the review is recorded in `PROGRESS.md`. slice S5 does not start before that evidence exists.

### S5-T01 — Partition family and rule sets
- Goal: Evaluate both proposed parameter sets on the one-window, parent-linked partition model.
- Acceptance criteria: [ ] OI-37 is closed by a different-maker review of the lead's last ten corrections to it (made on 2026-11-11 after the second confirmation review) and the review is recorded in `PROGRESS.md` before work starts; [ ] roots are resolution-7 parents intersected with municipalities; [ ] a whole-cell unit is one base cell or a union of whole base cells inside one root; [ ] the two cross-root municipality exceptions are the remainder (the union of the failed roots of one municipality) and the terminal `ha_home` unit (the union of every residence unit and remainder of one municipality); [ ] one parent-linked partition family exists per contributor universe and independent merges never cross; [ ] `home_area_share` belongs to that family and no row is published when either municipality-side complement is below the active count minimum; [ ] all-or-nothing siblings hold; [ ] remainders follow policy; [ ] version 1 builds no second window, mover canary or cross-period test.
- Scope: `custodian/privacy/partition/`, rules files and property tests.
- Depends: S4-T05.
- Requirements: PRV-10, PRV-24, TST-20.
- Delivery: hard; personas Privacy; status queued.
### S5-T02 — Stable treated leaf atoms
- Goal: Treat only mutually exclusive leaf atoms and derive every within-family total as the exact sum of that family's treated leaves. No cross-family equality is required.
- Acceptance criteria: [ ] cell keys are computed over distinct contributors; [ ] `other` is a treated leaf where pooling occurred; [ ] every stored total inside one additive family is the exact sum of that family's treated leaves, and no equality is asserted across families; [ ] the minimum-group, largest-group and top-two tests apply to every band and category atom; [ ] removing any one employer group leaves every published atom at or above the active count minimum; [ ] controlled rounding preserves exact within-family margins and a negative residual withholds the split; [ ] the pinned row-dropping order, fixed test order and reason-code mapping are implemented exactly; [ ] the privacy worked example reproduces its pinned result; [ ] identical inputs repeat exactly; [ ] keys never cross the release boundary.
- Scope: privacy treatment modules and primitive release builders.
- Depends: S5-T01.
- Requirements: PRV-24, PRV-29, PRV-35, PRV-42, PRV-44, PRV-45, PRV-46, PRV-110, TST-24, TST-26.
- Delivery: hard; personas Privacy; status queued.
### S5-T03 — Closure and adversarial audits
- Goal: Run exhaustive structural closure checks and the one attacker-view acceptance model, plus the typed attack suite, under both parameter sets. The audit is evidence under a stated attacker and is not called a proof.
- Acceptance criteria: [ ] exhaustive checks cover every unit, every pair of protected partitions and every area `make_area` can produce after pin reduction; [ ] at least 10,000 seeded fuzz pairs pass per release and per parameter set as regression evidence; [ ] the one acceptance model fixes every published leaf to its untreated aggregate, and no released-value interval is used for acceptance; [ ] every signed knowledge fixture is compared with sealed truth before optimisation, and any disagreement fails the build; [ ] published-means-passed constraints are present for every published leaf; [ ] targets the model cannot tell apart form one target class and are audited once; [ ] a time budget is set from a measured run at the start of slice S5 and recorded as a rule, a run over budget fails the build, and the model is not relaxed to meet it; [ ] `artefacts/attacker_view_audit.json` and `artefacts/attacker_view_public_totals.json` are the audit configuration and the public-total inventory; [ ] the audit fails when an applicable public total is unconfigured, and it covers `home_area_share` residuals; [ ] every person's feasible pay interval spans at least two released bands and every employer's headcount and wage-bill residuals exceed the declared bounds; [ ] PRV-121 allows only exact presolve, and one fixture world solved in both the full form and the reduced form gives identical statuses and identical minimum and maximum for every target class; [ ] the model does not represent what the layout tells about a failed population, and the typed attack suite holds one attack for each layout signal (a merged band, a category pooled into `other`, merged siblings, a withheld remainder and a released reason code); [ ] every canary and threat outcome has a typed recovery predicate; [ ] controls off recover every predicate and controls on recover none, for each parameter set; [ ] no mover or consecutive-window predicate is in the version 1 gate and no person-level movement-protection claim is made; [ ] reviewer attacks become permanent; [ ] no sentence in the audit report calls the result a proof.
- Scope: privacy audits, attack suite and signed reports.
- Depends: S5-T02.
- Requirements: PRV-49, PRV-67, PRV-73, PRV-76, PRV-112, PRV-113, PRV-116, PRV-121, TST-120.
- Delivery: hard; personas Privacy; status queued.
### S5-T04 — Manifest and sanad gate
- Goal: Select exactly one parameter set for export, build its canonical manifest and fail release construction when any fact lacks a complete source chain.
- Acceptance criteria: [ ] both parameter sets have completed their custodian-plane audits before selection; [ ] exactly one selected set's protected tables enter the manifest; [ ] missing lineage blocks the build; [ ] unsafe paths are rejected.
- Scope: release builder, manifest assembly and lineage validation tests.
- Depends: S5-T02, S5-T03.
- Requirements: DAT-80, DAT-105, DAT-132, PRV-01.
- Delivery: hard; personas Data; status queued.
### S5-T05 — Two-store load receipt
- Goal: Stage and verify both stores before writing `load_receipt.json` with `state: complete`.
- Acceptance criteria: [ ] unlisted tables and the unselected parameter set load nowhere; [ ] parity covers every exported release table; [ ] both stores verify the same release; [ ] the receipt has `state: complete` and the matching manifest `release_id` plus the protected-window fields; [ ] incomplete, missing or wrong-release receipt makes preflight and API refuse service.
- Scope: loader, store verification, load receipt and refusal tests.
- Depends: S5-T04, S5-T07, S3-T01.
- Requirements: BE-44, TST-63, DAT-80.
- Delivery: hard; personas Backend; status queued.
### S5-T06 — Survival and privacy receipts
- Goal: Publish a survival report for both parameter sets and release-safe privacy and audit receipts without protected inputs.
- Acceptance criteria: [ ] survival counts reconcile for both parameter sets; [ ] the exported set is identified only after both results exist; [ ] the flagship pin and default cut-offs are confirmed only after the report exists; [ ] no privacy rule is tuned to make an area look finer; [ ] every answer receipt names rules and checks; [ ] no receipt exposes a contributor or hidden key.
- Scope: release receipt builders, receipt schemas and tests.
- Depends: S5-T03, S5-T05.
- Requirements: MTH-53, PRV-80, PRV-83, PRV-87, PRV-90.
- Delivery: hard; personas Privacy; status queued.
### S5-T07 — Manifest window fields
- Goal: Add `window_key` and `protected_sha256` to `manifest.json`, then compute and verify the release identity.
- Acceptance criteria: [ ] `window_key` is the SHA-256 of canonical JSON containing the protected `period` and exactly four `{name, sha256}` entries, ordered by `name` as `business_register.v1`, `employment.v1`, `residence.v1` and `wages.v1`, whose `sha256` values are the corresponding manifest `feed_sha256` values, and nothing else (PRV-120); [ ] `protected_sha256` is the manifest value defined for the protected tables; [ ] both fields are present on the selected export's manifest; [ ] after adding both scalars, the full 64-character `release_id` under DAT-80 reproduces with every table and artefact digest included; [ ] two identical builds produce the same id.
- Scope: manifest window fields, release-identity builder and hash tests.
- Depends: S5-T04.
- Requirements: PRV-120.
- Delivery: hard; personas Privacy; status queued.
### S5-T08 — Review follow-up for slice S5
- Goal: Close every proposed open item that the reviews of slice S5 entered in `OPEN_ITEMS.md`, before the slice S5 gate.
- Acceptance criteria: [ ] each item of the slice is closed by a fix or by one line saying why it is not valid or is out of scope under REV-42; [ ] the reviewer checks every closure; [ ] no item is deferred out of this task; [ ] no item of the slice is left open.
- Scope: the files the closures change, and `OPEN_ITEMS.md`.
- Depends: every other task of slice S5.
- Requirements: REV-41, TST-168.
- Delivery: routine; personas as the items require; status queued.

**slice S5 gate.** Closure is proved by exhaustive structural checks, and a fuzz run of at least 10,000 area pairs per release and per parameter set passes; the attacker-view audit passes with every applicable public total configured; with controls off every typed predicate is recovered, and with controls on none is, for each parameter set; exactly one protected table set leaves the custodian plane; the loader rejects any table not in the manifest; and the release hash is reproducible.

## slice S6 — The joined door

These coarse tasks are refined at the slice S5 gate without weakening their criteria.

### S6-T01 — `area_evidence`
- Goal: Return joined-door evidence from release facts only with parity on both stores.
- Acceptance criteria: [ ] every status is tested; [ ] every numeral is a fact value; [ ] every release table used has parity; [ ] no privacy rule runs at request time.
- Scope: `area_evidence` tool, named SQL and parity tests.
- Depends: S5-T05.
- Requirements: BE-49, PRV-83, TST-40, TST-70.
- Delivery: hard; personas Backend; status queued.
### S6-T02 — Joined-door cards
- Goal: Build worker and resident pay cards, the licensed-versus-operating strip, housing split, coverage and reading guidance.
- Acceptance criteria: [ ] cards remain separate; [ ] resident housing always shows `family_housing`, `labour_accommodation`, `institution` and `unknown`, an explicit `other` row when pooling occurred, beside the not-measured count; [ ] the count and the shares beside it come from one additive family (FE-100, PRV-30); [ ] the not-measured count is a separate population; [ ] the aggregate strip stays separate from named places; [ ] coverage and not-measured states render; [ ] facts without sanad refuse.
- Scope: joined-door web components and component tests.
- Depends: S6-T01, S3-T09.
- Requirements: MTH-39, DES-92, DES-82, FE-21, FE-100.
- Delivery: hard; personas Frontend; status queued.
### S6-T03 — Dial, snap and suppressed states
- Goal: Build the four-situation dial, summer switch, snap animation and explanatory blanks.
- Acceptance criteria: [ ] presence is a Simulated index only and is not anchored hour by hour to a Public series; [ ] Public monthly context series remain separate Public cards; [ ] snap is deterministic; [ ] suppressed is never shown as zero; [ ] both languages pass visuals.
- Scope: dial, snap report, presence layer and blank-state components.
- Depends: S6-T01, S4-T04.
- Requirements: SYN-51, DES-99, DES-103, DES-07.
- Delivery: hard; personas Frontend; status queued.
### S6-T04 — Catalogues, template writer and accounting gate
- Goal: Complete catalogue-owned answers and audit sources, assumptions, invention, scope and limits before display.
- Acceptance criteria: [ ] every sentence is a catalogue claim; [ ] every component validates; [ ] all five checks pass or deterministic fallback runs; [ ] every answer receipt records the result under "Checked before display".
- Scope: assistant catalogues, template writer, accounting gate and mutation tests.
- Depends: S3-T07, S6-T01.
- Requirements: AI-14, AI-18, AI-28, AI-42, BE-107, DAT-105, DAT-135.
- Delivery: hard; personas AI; status queued.
### S6-T05 — Joined-door gate
- Goal: Prove no-model behaviour, complete source chains, performance and bilingual layouts end to end.
- Acceptance criteria: [ ] the flagship path works with no model call; [ ] every number resolves to a fact with a complete source chain; [ ] every receipt carries the accounting-gate result; [ ] local p95 is under 1.5 seconds; [ ] wall, laptop and tablet visuals pass in both languages.
- Scope: slice S6 end-to-end, performance and visual tests; gate evidence.
- Depends: S6-T02, S6-T03, S6-T04.
- Requirements: TST-90, TST-101, TST-130, PLN-07.
- Delivery: hard; personas Frontend; status queued.
### S6-T06 — Review follow-up for slice S6
- Goal: Close every proposed open item that the reviews of slice S6 entered in `OPEN_ITEMS.md`, before the slice S6 gate.
- Acceptance criteria: [ ] each item of the slice is closed by a fix or by one line saying why it is not valid or is out of scope under REV-42; [ ] the reviewer checks every closure; [ ] no item is deferred out of this task; [ ] no item of the slice is left open.
- Scope: the files the closures change, and `OPEN_ITEMS.md`.
- Depends: every other task of slice S6.
- Requirements: REV-41, TST-168.
- Delivery: routine; personas as the items require; status queued.

**slice S6 gate.** The flagship question is answered end to end with no model call; every number resolves to a fact with a complete source chain; every receipt carries the accounting-gate result; the evidence bundle is under 1.5 seconds at the 95th percentile locally; and visual tests pass at wall, laptop and tablet sizes in English and Arabic.

## slice S7 — Costs, suppliers, staffing

These coarse tasks are refined at the slice S6 gate without weakening their criteria.

### S7-T01 — Unit economics and break-even
- Goal: Build deterministic unit economics, six-input break-even and the optional target-surplus scenario without forecasting success.
- Acceptance criteria: [ ] the six inputs are monthly rent, seats, average bill, opening days defaulted to 30, optional expected covers per day and optional monthly staff cost; [ ] every output comes from `eii_core.calc`; [ ] invalid input fails safely; [ ] results are Inferred and tagged as user inputs; [ ] the zero-surplus regression uses `m = 0.313` and returns QAR 127,796 a month, 36 covers a day and 0.6 seat turns, with QAR 56,340 maximum rent and QAR 85.20 minimum bill at 50 expected covers; [ ] the `U = 0.197` target-surplus regression returns `m - U = 0.116`, QAR 344,827.59 a month, 96 covers a day and 1.6 seat turns, with QAR 20,880 maximum rent and QAR 229.89 minimum bill at 50 expected covers; [ ] the target case is labelled "to earn the sector's 2022 surplus share" and is never called break-even.
- Scope: C4 calculation, tool facts, break-even component and tests.
- Depends: S6-T05.
- Requirements: MTH-25, MTH-26, DES-110, MTH-03.
- Delivery: hard; personas Methods; status queued.
### S7-T02 — Supplier lens
- Goal: Build reviewed input baskets, origin paths, calculated import unit value (QAR per kg), concentration and wholesale depth.
- Acceptance criteria: [ ] only reviewed basket lines appear; [ ] every path is Public; [ ] the label is "calculated import unit value (QAR per kg)"; [ ] the valuation basis is shown as the source states it or as "not stated by the source"; [ ] flagship worked examples and source chains pass.
- Scope: supplier calculations, `supplier_lens`, supplier components and tests.
- Depends: S2-T03, S6-T05.
- Requirements: MTH-30, MTH-32, PUB-41, DAT-100.
- Delivery: hard; personas Methods; status queued.
### S7-T03 — Staffing and pay
- Goal: Build protected staffing pay bands beside Public benchmarks and the statutory minimum.
- Acceptance criteria: [ ] staffing-only drive option works; [ ] protected and Public facts remain distinct; [ ] the card lists occupation groups `0` to `9` and `unmapped`, and an explicit `other` row when pooling occurred; [ ] the not-measured count is not shown as an occupation group; [ ] statutory source and coverage are visible; [ ] worked example passes.
- Scope: C10 calculation, `pay_benchmark`, staffing components and tests.
- Depends: S6-T05.
- Requirements: AI-20, MTH-03, MTH-42, MTH-39, AI-42, FE-99.
- Delivery: hard; personas Methods; status queued.
### S7-T04 — Public context cards
- Goal: Build the property-sale method card, national pay decomposition, churn, zone momentum and neighbours evidence.
- Acceptance criteria: [ ] the property-sale card never shows sale price per square metre without its deal count; [ ] each method reproduces its worked example; [ ] OI-03 blocks unresolved facts; [ ] neighbours are Public and carry coverage caveats.
- Scope: property-sale method card, C1, C2, C3, C6 and C9 methods, components and tests.
- Depends: S2-T07, S6-T05.
- Requirements: PUB-14, FE-25, MTH-15, MTH-18, MTH-21, MTH-34, MTH-41.
- Delivery: hard; personas Methods; status queued.
### S7-T05 — Two-door comparison and provenance gate
- Goal: Build snapped shared-reach comparison and audit every slice S7 card.
- Acceptance criteria: [ ] overlap uses release-unit sets; [ ] each method reproduces its public worked example; [ ] no regression value is left unpinned; [ ] each card passes the provenance audit.
- Scope: C7, `compare_areas`, comparison UI and slice S7 audit.
- Depends: S7-T01, S7-T02, S7-T03, S7-T04.
- Requirements: MTH-37, MTH-03, TST-50.
- Delivery: hard; personas Methods; status queued.
### S7-T06 — Review follow-up for slice S7
- Goal: Close every proposed open item that the reviews of slice S7 entered in `OPEN_ITEMS.md`, before the slice S7 gate.
- Acceptance criteria: [ ] each item of the slice is closed by a fix or by one line saying why it is not valid or is out of scope under REV-42; [ ] the reviewer checks every closure; [ ] no item is deferred out of this task; [ ] no item of the slice is left open.
- Scope: the files the closures change, and `OPEN_ITEMS.md`.
- Depends: every other task of slice S7.
- Requirements: REV-41, TST-168.
- Delivery: routine; personas as the items require; status queued.

**slice S7 gate.** Each method reproduces its public worked example; no regression value is left unpinned; and each card passes the provenance audit.

## slice S8 — Assistant

These coarse tasks are refined at the slice S7 gate without weakening their criteria.

### S8-T01 — Deterministic router and playbooks
- Goal: Route to exactly three declarative playbooks before any provider call.
- Acceptance criteria: [ ] bilingual prepared questions route deterministically; [ ] closed values constrain user numbers; [ ] each playbook runs without a model.
- Scope: deterministic router, three playbooks and unit tests.
- Depends: S7-T05.
- Requirements: AI-07, AI-18, AI-23, AI-01.
- Delivery: hard; personas AI; status queued.
### S8-T02 — Main provider loop and egress controls
- Goal: Add the current main provider behind the fixed nine-tool contract with bounded egress.
- Acceptance criteria: [ ] exact tool list is asserted; [ ] no SQL, code or web tool exists; [ ] blocked egress falls back; [ ] current official API references support every call.
- Scope: main provider adapter, tool loop, egress records and tests.
- Depends: S8-T01.
- Requirements: AI-24, AI-55, AI-77, ARC-71.
- Delivery: hard; personas AI; status queued.
### S8-T03 — Structured brief validator
- Goal: Validate claim keys, slots, components, subjects and accounting receipts before streaming, with the build-time template scan.
- Acceptance criteria: [ ] the claim, component, fragment and question catalogues are closed and versioned; [ ] unknown catalogue keys, unknown properties and swapped slots fail; [ ] real-place non-Public facts fail; [ ] the build-time scan rejects numerals, number words, real place names in `area` templates and go or no-go wording; [ ] one repair is allowed; [ ] second failure uses template output.
- Scope: `claims.yaml`, `components.yaml`, `fragments.yaml`, `questions.yaml`, structured brief models, validators, build-time template scan, repair path and mutation tests.
- Depends: S8-T01, S3-T07, S6-T04.
- Requirements: AI-28, AI-37, AI-42, AI-48, AI-49, AI-88.
- Delivery: hard; personas AI; status queued.
### S8-T04 — Offline typed-decision evaluation classes
- Goal: Run `router_miss_finder`, `brief_second_reader` and shadow `question_route` only on permitted offline inputs.
- Acceptance criteria: [ ] visitor text is blocked; [ ] second reader only raises review; [ ] confirmed misses become deterministic tests; [ ] provider `none` leaves all gates valid.
- Scope: offline eval tooling and typed-decision run artefacts.
- Depends: S1-T07, S8-T01, S8-T03.
- Requirements: AI-98, DAT-126, TST-155, PLN-20.
- Delivery: hard; personas AI; status queued.
### S8-T05 — Evaluation harness and gate
- Goal: Prove routing, structured briefs, declines and injection resistance with code graders.
- Acceptance criteria: [ ] prepared questions pass five of five; [ ] must-decline passes at 100%; [ ] 500 distinct structured briefs returned by the model validate against the catalogues before repair or fallback; [ ] every fallback is counted and reported; [ ] injection successes are zero.
- Scope: golden, decline, structured-brief and injection evals; slice S8 report.
- Depends: S8-T02, S8-T03, S8-T04.
- Requirements: AI-90, TST-110, TST-114, TST-155.
- Delivery: hard; personas AI; status queued.
### S8-T06 — Memo, replay and offline completeness
- Goal: Make template, replay and recorded-provider modes deterministic and complete without network access.
- Acceptance criteria: [ ] memo key includes release, prompt and catalogue versions; [ ] replay tampering fails; [ ] no-key mode makes no outbound call; [ ] the full slice S8 gate passes offline.
- Scope: memo store, replay adapter, recorded provider and offline tests.
- Depends: S8-T03, S8-T05.
- Requirements: AI-63, AI-69, AI-71, AI-95, OPS-37, TST-127.
- Delivery: hard; personas AI; status queued.
### S8-T07 — Review follow-up for slice S8
- Goal: Close every proposed open item that the reviews of slice S8 entered in `OPEN_ITEMS.md`, before the slice S8 gate.
- Acceptance criteria: [ ] each item of the slice is closed by a fix or by one line saying why it is not valid or is out of scope under REV-42; [ ] the reviewer checks every closure; [ ] no item is deferred out of this task; [ ] no item of the slice is left open.
- Scope: the files the closures change, and `OPEN_ITEMS.md`.
- Depends: every other task of slice S8.
- Requirements: REV-41, TST-168.
- Delivery: routine; personas as the items require; status queued.

## slice S9 — Seats and oversight

These coarse tasks are refined at the slice S8 gate without weakening their criteria.

### S9-T01 — Application DDL, roles and row-level security
- Goal: Apply the canonical application schema with forced row-level security and fixed read functions.
- Acceptance criteria: [ ] application owns no object; [ ] direct base reads fail; [ ] company and oversight read functions have fixed, separate return types; [ ] oversight returns no organisation identity, question text or brief text; [ ] Company B receives no Company A brief; [ ] bypass attempts fail.
- Scope: `infra/postgres/`, application repository functions and database tests.
- Depends: S8-T06, S5-T05.
- Requirements: DAT-110, BE-31, BE-36, BE-38, TST-64.
- Delivery: hard; personas Backend; status queued.
### S9-T02 — Signed seat cookie and presenter token
- Goal: Bind each window to one seat and restrict presenter controls without claiming authentication.
- Acceptance criteria: [ ] API reads only signed `eii_seat`; [ ] request seat fields are rejected; [ ] `X-EII-Presenter-Token` is required; [ ] company windows without the per-session presenter token receive 403; [ ] the stage window's presenter console succeeds with its valid token.
- Scope: seat middleware, presenter middleware and browser tests.
- Depends: S9-T01.
- Requirements: BE-70, BE-89, OPS-56, PLN-19, TST-191.
- Delivery: hard; personas Backend; status queued.
### S9-T03 — Live and fallback ledger
- Goal: Stream ledger rows live and replay the durable SQLite fallback without duplicates.
- Acceptance criteria: [ ] every question creates a row; [ ] no-key rows have no egress link; [ ] fallback survives restart; [ ] replay is idempotent.
- Scope: ledger repositories, server-sent events, SQLite fallback and tests.
- Depends: S9-T01, S9-T02.
- Requirements: TST-145, OPS-17, OPS-37.
- Delivery: hard; personas Backend; status queued.
### S9-T04 — Oversight screen
- Goal: Show redacted live demand and minimum-protected roll-ups with a clear paused state.
- Acceptance criteria: [ ] rows arrive without reload; [ ] company identity and text are absent; [ ] the distinct-organisation minimum is 2 as demonstration configuration, not a disclosure threshold; [ ] the minimum is enforced at one organisation and shown at two; [ ] embedded mode shows paused.
- Scope: oversight API projection, oversight web route and tests.
- Depends: S9-T03.
- Requirements: DES-126, TST-145, TST-146, DAT-110.
- Delivery: hard; personas Frontend; status queued.
### S9-T05 — GIS mirror and seat gate
- Goal: Prove read-only GIS access and complete the database isolation gate.
- Acceptance criteria: [ ] standard GIS opens release layers; [ ] writes and creates fail; [ ] seat and role tests pass against real PostgreSQL; [ ] evidence is recorded.
- Scope: reviewer role, GIS connection fixture and slice S9 integration tests.
- Depends: S9-T01, S9-T04.
- Requirements: TST-64, TST-65, REV-33.
- Delivery: hard; personas Backend; status queued.
### S9-T06 — Review follow-up for slice S9
- Goal: Close every proposed open item that the reviews of slice S9 entered in `OPEN_ITEMS.md`, before the slice S9 gate.
- Acceptance criteria: [ ] each item of the slice is closed by a fix or by one line saying why it is not valid or is out of scope under REV-42; [ ] the reviewer checks every closure; [ ] no item is deferred out of this task; [ ] no item of the slice is left open.
- Scope: the files the closures change, and `OPEN_ITEMS.md`.
- Depends: every other task of slice S9.
- Requirements: REV-41, TST-168.
- Delivery: routine; personas as the items require; status queued.

## slice S10 — Proof and story

These coarse tasks are refined at the slice S9 gate without weakening their criteria.

### S10-T01 — Signed attack replay
- Goal: Revalidate prepared attack recordings at start-up, serve the complement step through `POST /api/proof/scene` (PRV-119) and refuse tampered evidence. This task cites that route and does not restate its schema.
- Acceptance criteria: [ ] the complement step calls `POST /api/proof/scene` (PRV-119), where one manifest-listed fixture id selects two prepared requests that differ by one published merged unit of at least two base cells, and no figure exists for any member base cell alone; [ ] the endpoint returns their pre-validated unit sets; [ ] production tools still accept only pin-based areas; [ ] the scene separately shows the typed phrase declined by the application; [ ] the injection step rejects invalid structured output, rejects its one prepared invalid repair, falls back to the playbook and logs from signed fixture identity; [ ] the unprotected comparison is a labelled replay of signed build-time results and names any canary only by its scenario label; [ ] tools reproduce every prepared fact; [ ] changed fact, release, prompt or brief fails; [ ] no controls-off path exists at run time.
- Scope: `POST /api/proof/scene`, typed-phrase decline fixture, signed injection fixture, labelled unprotected replay, replay validator, signed attack fixtures and negative tests.
- Depends: S9-T05.
- Requirements: PRV-105, PRV-119, TST-127, PRV-109.
- Delivery: hard; personas Privacy; status queued.
### S10-T02 — Proof room and Trust centre
- Goal: Show source chains, rules, receipts and the activity-spine lineage line without gateway scores.
- Acceptance criteria: [ ] sealed reveal uses only signed build-time evidence; [ ] every proof starts from released evidence; [ ] the Trust centre shows the sentence of FE-101; [ ] gateway line states machine-assisted order and human sign-off; [ ] prepared “other AI” answer is present; [ ] no live gateway call occurs.
- Scope: Proof room, Trust centre, lineage component and prepared runbook answer.
- Depends: S10-T01, S8-T04.
- Requirements: DES-95, DES-121, DES-164, FE-101, AI-98, PLN-20.
- Delivery: hard; personas Frontend; status queued.
### S10-T03 — Guided story and presenter controls
- Goal: Build record, replay and the eight-scene guided story with protected presenter actions.
- Acceptance criteria: [ ] every scene is directly reachable; [ ] Next, Back, Language, Offline, embedded switch and Reset work; [ ] controls require presenter token; [ ] replay is deterministic.
- Scope: story state, presenter console, recordings and story tests.
- Depends: S10-T01, S9-T02.
- Requirements: DES-113, RUN-03, OPS-56.
- Delivery: hard; personas Operations; status queued.
### S10-T04 — Native Arabic sign-off
- Goal: Obtain native review for every sentence template and every other prepared Arabic string, and block unsigned strings.
- Acceptance criteria: [ ] every sentence template has native Arabic sign-off; [ ] the signed catalogue is complete; [ ] Western digits and RTL rules pass; [ ] unsigned prepared text fails the gate.
- Scope: Arabic string catalogue, sign-off record and bilingual visual tests.
- Depends: S10-T02, S10-T03.
- Requirements: DES-10, TST-90, PLN-19.
- Delivery: hard; personas Frontend; status queued.
### S10-T05 — Bilingual briefing pack
- Goal: Produce a printable bilingual pack whose every figure opens a complete source chain.
- Acceptance criteria: [ ] only Fact chips render figures; [ ] every pack fact traces; [ ] standing honesty notice remains; [ ] both languages pass the pack audit.
- Scope: pack renderer, print styles and pack audit tests.
- Depends: S10-T04, S7-T05.
- Requirements: TST-100, TST-103, DES-78.
- Delivery: hard; personas Frontend; status queued.
### S10-T06 — Review follow-up for slice S10
- Goal: Close every proposed open item that the reviews of slice S10 entered in `OPEN_ITEMS.md`, before the slice S10 gate.
- Acceptance criteria: [ ] each item of the slice is closed by a fix or by one line saying why it is not valid or is out of scope under REV-42; [ ] the reviewer checks every closure; [ ] no item is deferred out of this task; [ ] no item of the slice is left open.
- Scope: the files the closures change, and `OPEN_ITEMS.md`.
- Depends: every other task of slice S10.
- Requirements: REV-41, TST-168.
- Delivery: routine; personas as the items require; status queued.

## slice S11 — Hardening and hand-over

These coarse tasks are refined at the slice S10 gate without weakening their criteria.

### S11-T01 — Command and freeze hardening
- Goal: Harden preflight, database, start, stop and both no-flag `./eii freeze` runs for the stage machine.
- Acceptance criteria: [ ] preflight reports every check; [ ] only `db-up` starts the database; [ ] wrong release receipt refuses start; [ ] the first freeze run requires current green evidence and a recorded human review of the release (role, date, and that the survival report and the signed attack report were read); [ ] no review record, no freeze; [ ] the first run writes the data bundle, checksum list and pending `freeze.json` and appends the register line; [ ] the second no-flag run starts from a base-branch commit containing that line, builds and verifies the application archive, writes its checksum beside the bundle and marks `freeze.json` complete; [ ] for a frozen release only, the installer and `./eii up` exit 7 unless the installed application's register contains the line and `freeze.json` says `complete`; [ ] a build release with no `freeze.json` is not checked.
- Scope: command implementations, health checks, freeze builder and operational tests.
- Depends: S10-T05.
- Requirements: DAT-133, OPS-06, OPS-27, OPS-32, PLN-20, RUN-12, RUN-13.
- Delivery: hard; personas Platform; status queued.
### S11-T02 — Runbook, limits and pilot request
- Goal: Finalise operator steps, recovery paths, honest limits and the filled pilot request.
- Acceptance criteria: [ ] every command has an expected result; [ ] the prepared gateway answer is in the runbook; [ ] the limits page carries the sentence of RUN-14; [ ] prohibited claims are explicit; [ ] pass and kill criteria are checkable; [ ] no unresolved fact is presented.
- Scope: `docs/16_DEMO_RUNBOOK.md`, limits page and pilot-request artefact.
- Depends: S11-T01.
- Requirements: RUN-01, RUN-07, RUN-14, BRF-36.
- Delivery: hard; personas Operations; status queued.
### S11-T03 — Three rehearsals
- Goal: Run three full human rehearsals, including database-stopped and offline conditions.
- Acceptance criteria: [ ] normal-store rehearsal passes; [ ] the rehearsal with PostgreSQL stopped passes; [ ] the offline rehearsal passes; [ ] every recovery result is recorded.
- Scope: rehearsal execution and evidence records; product files read-only unless a defect creates a new task.
- Depends: S11-T01, S11-T02.
- Requirements: RUN-07, RUN-08, TST-180.
- Delivery: hard; personas Operations; status queued.
### S11-T04 — Final independent reviews
- Goal: Complete task, slice, security, design and operational-readiness reviews on the frozen candidate.
- Acceptance criteria: [ ] all slice S11 gate evidence is checked; [ ] every finding has an exact fix; [ ] final verdict is `APPROVED`, or counts as approved under REV-40; [ ] merged commit remains green.
- Scope: review reports and evidence only.
- Depends: S11-T03.
- Requirements: REV-06, REV-30, REV-33, TST-160.
- Delivery: hard; personas Operations; status queued.
### S11-T05 — Owner decision and hand-over
- Goal: Present the frozen evidence and record the owner's go or no-go without adding new scope.
- Acceptance criteria: [ ] frozen versions and hashes are listed; [ ] open items and limits are visible; [ ] decision is recorded; [ ] hand-over bundle matches the approved commit.
- Scope: hand-over record and frozen bundle verification.
- Depends: S11-T04.
- Requirements: PLN-14, PLN-21, TST-150.
- Delivery: routine; personas Operations; status queued.
### S11-T06 — Export register
- Goal: Append one export-register line on the first `./eii freeze` run, enforce the two uniqueness rules, and complete the frozen bundle on the second no-flag run.
- Acceptance criteria: [ ] the first freeze run appends `window_key`, `protected_sha256`, `world_seed`, `rules_version_id`, `parameter_set`, `release_id` and `code_version`, in that order, as one line of `infra/export_register.jsonl`; [ ] continuous integration checks the register file alone, allows one `protected_sha256` per `window_key` and one `window_key` per `world_seed`, and fails if an existing line is changed or removed; [ ] a planted changed line, a planted deleted line, a second `protected_sha256` for one `window_key` and a second `window_key` for one `world_seed` all fail; [ ] a register conflict refuses freeze, and any post-freeze change to rules version, exported set, treatment code or world generator requires a new `world_seed` and a new build before another freeze (PRV-120); [ ] the second no-flag run from the base-branch commit containing the line builds and verifies the application archive, writes its checksum beside the bundle and marks `freeze.json` complete; [ ] a frozen bundle is refused at install or start with exit 7 when its line is missing from the installed application's register or `freeze.json` is incomplete, and the remedy is to finish the two-run freeze rather than change the seed; [ ] no signed receipt file is created.
- Scope: both freeze runs, `freeze.json`, the application archive and checksum, `infra/export_register.jsonl`, the frozen-bundle stage-machine checks and the continuous-integration register check.
- Depends: S11-T01, S5-T07.
- Requirements: PRV-120, RUN-13.
- Delivery: hard; personas Platform; status queued.
### S11-T07 — Review follow-up for slice S11
- Goal: Close every proposed open item that the reviews of slice S11 entered in `OPEN_ITEMS.md`, before the slice S11 gate.
- Acceptance criteria: [ ] each item of the slice is closed by a fix or by one line saying why it is not valid or is out of scope under REV-42; [ ] the reviewer checks every closure; [ ] no item is deferred out of this task; [ ] no item of the slice is left open.
- Scope: the files the closures change, and `OPEN_ITEMS.md`.
- Depends: every other task of slice S11.
- Requirements: REV-41, TST-168.
- Delivery: routine; personas as the items require; status queued.

**slice S11 gate.** Three rehearsals are complete, including one with PostgreSQL stopped and one offline; versions are frozen; the freeze carries a recorded human review of the release and passes the export-register check; the independent reviewer returns `APPROVED`; and the owner records go or no-go.
