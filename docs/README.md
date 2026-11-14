# Documentation index

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016, 0017, 0018 and 0019 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| Date | 2026-11-13 |
| Owner | albarami |
| Purpose | Index the EII pack, its reading orders, statuses, identifiers and amendment process. |
| Read first | [README.md](../README.md), [AGENTS.md](../AGENTS.md) |

## In brief

- Read the project brief before any specialised document.
- Every numbered document is a draft. Documents 01 to 16 and the glossary were reviewed by models of other makers and corrected on 2026-11-11, then amended on 2026-11-12 by decisions 0016 and 0017, which also created document 17, by decision 0018, which also amended the applicable documents and document 17, and by decision 0019, which also amended the applicable documents and document 17; on 2026-11-13 decision 0022 amended documents 01 to 17 and the glossary, and decision 0023 amended rules 3, 8 and 10 of AGENTS.md, documents 01 to 17 and the glossary; [PROGRESS.md](../PROGRESS.md) lists the reviews, their verdicts and what is still unreviewed (open items OI-37 and OI-38). No document is approved for a slice gate yet.
- Version 1 now covers the whole initiative ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)): seven decision journeys, three services and four cases on one living map, with drawn areas, simulated footfall and traffic, and monthly periods. [Decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) makes the companies the real ones of the public business register, attaches synthetic labour and residence records to them, and retires the named synthetic firms of decision 0016. [Decision 0017](decisions/0017-public-data-additions-and-public-splits.md) adds 77 portal datasets, two investment sources and official splits by sex and nationality as Public facts. [17_DEPLOYMENT_HARDENING.md](17_DEPLOYMENT_HARDENING.md) lists what a deployment on real records must add. [Decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) replaces the ban on forecasts by forecasts, estimates and base rates computed by tested code, adds scenario tools, people present by pay band, an optional 3D view and six self-serve sources, and sets the citation of the pack by stable anchor, never by line number.
- The implementation plan is such a draft too; the task ledger is a draft queue whose tasks all start queued.
- Decision records 0001 to 0024 and 0027 are accepted (0025 and 0026 are numbered and arrive with their own pull requests); decision 0016 supersedes decision 0013 and amends decisions 0006 and 0007; decision 0022 amends parts of decisions 0001, 0016, 0017 and 0019; decision 0023 settles questions that decision 0022 left open and amends decisions 0003, 0011 and 0022 where they name the oversight seat or the ministry view. [Decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) adds ten capabilities, all free and self-serve except the photorealistic 3D mode, which the owner caps at USD 20 in total; sets the order of the site answer; limits synthetic records to the confirmed ministry sources (its data rule); and makes the product one for companies, designed for three personas, with no oversight seat and no ministry-only view. [Decision 0027](decisions/0027-hosted-web-checks-time-limit.md) allows the web checks of the whole test command 3,000 seconds on GitHub's hosted runner as a stopgap, with nothing else of the checks changed. Later amendments need new records, not silent edits.
- Requirement identifiers are defined once in requirement tables; task identifiers come from the plan and task ledger.
- [GLOSSARY.md](GLOSSARY.md) pins vocabulary. [OPEN_ITEMS.md](../OPEN_ITEMS.md) tracks what is undecided.

## Reading order by role

| Role | Read in this order |
|---|---|
| Owner | [01](01_PROJECT_BRIEF.md) → [14](14_IMPLEMENTATION_PLAN.md) → [OPEN_ITEMS.md](../OPEN_ITEMS.md) → relevant decision records → [16](16_DEMO_RUNBOOK.md) → [17](17_DEPLOYMENT_HARDENING.md) |
| Builder | [AGENTS.md](../AGENTS.md) → assigned task in [TASKS.md](../TASKS.md) and slice in [14](14_IMPLEMENTATION_PLAN.md) → [02](02_ARCHITECTURE.md) → task-specific documents → the reference notes of any library they name ([engines and the Claude API](REFERENCE_NOTES.md), [map libraries](../web/REFERENCE_NOTES.md)) → [12](12_TESTING_AND_QUALITY.md) |
| Reviewer | [15](15_REVIEWER_CHECKLIST.md) → task and full diff → [12](12_TESTING_AND_QUALITY.md) → [PROGRESS.md](../PROGRESS.md) → affected documents and decision records |
| Data custodian | [01](01_PROJECT_BRIEF.md) → [03](03_DATA_CONTRACTS.md) → [06](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) → [17](17_DEPLOYMENT_HARDENING.md) → [05](05_SYNTHETIC_WORLD_AND_SIMULATION.md) → [04](04_PUBLIC_DATA_PACK.md) → [16](16_DEMO_RUNBOOK.md) |
| Designer | [01](01_PROJECT_BRIEF.md) → [GLOSSARY.md](GLOSSARY.md) → [11](11_DESIGN_DIRECTION.md) → [10](10_FRONTEND.md) → [09](09_AI_ASSISTANT.md) → [16](16_DEMO_RUNBOOK.md) |

## Numbered documents

| Document | Purpose | Status on 2026-11-13 |
|---|---|---|
| [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md) | Audience, scope, version 1, journeys and prohibited claims | Draft v0.3, amended by decisions 0016, 0017, 0018 and 0019 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| [02_ARCHITECTURE.md](02_ARCHITECTURE.md) | Planes, trust boundaries, release, stores and stack | Draft v0.3, amended by decisions 0016, 0017, 0018, 0019 and 0020 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| [03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) | Feed, release, fact, graph and application contracts | Draft v0.3, amended by decisions 0016, 0017 and 0019 on 2026-11-12, and by decisions 0021, 0022 and 0023 on 2026-11-13 |
| [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md) | Public sources, licences, frame, spine and places | Draft v0.3, amended by decisions 0016, 0017 and 0019 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| [05_SYNTHETIC_WORLD_AND_SIMULATION.md](05_SYNTHETIC_WORLD_AND_SIMULATION.md) | Synthetic generation, simulation and sealed evaluation | Draft v0.3, amended by decisions 0016, 0017 and 0019 on 2026-11-12, and by decisions 0021, 0022 and 0023 on 2026-11-13 |
| [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) | Partitions, one selected export, one treatment per window, attacks, receipts and limits | Draft v0.3, amended by decisions 0016, 0017, 0018 and 0019 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13; the last ten corrections of 2026-11-11 still await review by another maker (OI-37) |
| [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) | Deterministic methods and worked public examples | Draft v0.3, amended by decisions 0016, 0017 and 0019 on 2026-11-12, and by decisions 0021, 0022 and 0023 on 2026-11-13 |
| [08_BACKEND.md](08_BACKEND.md) | Stores, loader, tools, playbooks, API and seats | Draft v0.3, amended by decisions 0016, 0017, 0018, 0019 and 0020 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| [09_AI_ASSISTANT.md](09_AI_ASSISTANT.md) | Governed composition, catalogues, fallback and evaluation | Draft v0.3, amended by decisions 0016, 0017, 0018 and 0019 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| [10_FRONTEND.md](10_FRONTEND.md) | Browser components, map, Fact chips and bilingual behaviour | Draft v0.3, amended by decisions 0016, 0017, 0018 and 0019 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 and decision 0024 on 2026-11-14 |
| [11_DESIGN_DIRECTION.md](11_DESIGN_DIRECTION.md) | Visual tokens, motion, storyboard and design audit | Draft v0.3, amended by decisions 0016, 0017, 0018 and 0019 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| [12_TESTING_AND_QUALITY.md](12_TESTING_AND_QUALITY.md) | Test map, gates, CI and evidence standard | Draft v0.3, amended by decisions 0016, 0017, 0018, 0019 and 0020 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 and decision 0024 on 2026-11-14; also amended on 2026-11-12 by [decision 0015](decisions/0015-review-rounds-and-the-scope-of-repository-checks.md), as amended by [decision 0018](decisions/0018-priorities-and-amendments-to-decision-0015.md) |
| [13_DEPLOYMENT_AND_OPERATIONS.md](13_DEPLOYMENT_AND_OPERATIONS.md) | Commands, stage operation, freeze and recovery | Draft v0.3, amended by decisions 0016, 0017, 0018, 0019 and 0020 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| [14_IMPLEMENTATION_PLAN.md](14_IMPLEMENTATION_PLAN.md) | Slices, dependencies, tasks and gates | Draft v0.3, amended by decisions 0016, 0017, 0018, 0019 and 0020 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13; also amended on 2026-11-12 by [decision 0015](decisions/0015-review-rounds-and-the-scope-of-repository-checks.md) |
| [15_REVIEWER_CHECKLIST.md](15_REVIEWER_CHECKLIST.md) | Independent checks and verdict format | Draft v0.3, amended by decisions 0016, 0017, 0018 and 0019 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 and decision 0024 on 2026-11-14; also amended on 2026-11-12 by [decision 0015](decisions/0015-review-rounds-and-the-scope-of-repository-checks.md), as amended by [decision 0018](decisions/0018-priorities-and-amendments-to-decision-0015.md) |
| [16_DEMO_RUNBOOK.md](16_DEMO_RUNBOOK.md) | Guided session, recoveries and closing request | Draft v0.3, amended by decisions 0016, 0017, 0018, 0019 and 0020 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| [17_DEPLOYMENT_HARDENING.md](17_DEPLOYMENT_HARDENING.md) | What a deployment on real records must add beyond the demonstrator | Draft v0.2, created by decisions 0016 and 0017 and amended by decisions 0018 and 0019 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| [GLOSSARY.md](GLOSSARY.md) | Shared technical and interface vocabulary | Draft v0.3, amended by decisions 0016, 0017 and 0019 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| [REFERENCE_NOTES.md](REFERENCE_NOTES.md) | Official pages read for DuckDB 2.0, PostgreSQL 18 and the Claude API, the idioms that changed, and the slice S1 confirmation fields | Draft written by task S0-T13 on 2026-11-12; not approved |
| [web/REFERENCE_NOTES.md](../web/REFERENCE_NOTES.md) | The same for MapLibre GL JS 6, deck.gl 9.4 and the deck.gl MapLibre module (FE-02), and the font weights and icon licence confirmations (DES-25, DES-45) | Draft written by task S0-T13 on 2026-11-12; not approved |
| [TASKS.md](../TASKS.md) | Task-level scope, acceptance criteria and evidence links | Draft task queue; all tasks start queued |
| [evals/](../evals/typed_decisions/README.md) | Current typed-decision cases, blind labels and initial qualification results | Recorded initial set; fresh human-labelled qualification remains open under OI-15 |

## Decision records

| Record | Decision | Status |
|---|---|---|
| [0001](decisions/0001-fully-synthetic-records-real-public-data.md) | Fully synthetic custodian-type records; cited real public data | Accepted, 2026-11-11; its consequences amended by decision 0022 on 2026-11-13 |
| [0002](decisions/0002-three-planes-and-the-release-boundary.md) | Three planes and the release-only boundary | Accepted, 2026-11-11 |
| [0003](decisions/0003-postgresql-postgis-in-version-1.md) | PostgreSQL with PostGIS in version 1 | Accepted, 2026-11-11; item 2 amended by decision 0023 on 2026-11-13, which removes the oversight seat |
| [0004](decisions/0004-duckdb-build-engine-and-embedded-standby.md) | DuckDB build engine and embedded standby | Accepted, 2026-11-11 |
| [0005](decisions/0005-economic-graph-as-tables-neo4j-deferred.md) | Graph as tables; graph server deferred | Accepted, 2026-11-11 |
| [0006](decisions/0006-fixed-grid-and-pin-based-areas.md) | Fixed grid and pin-based areas | Accepted, 2026-11-11; amended by decision 0016 on 2026-11-12 |
| [0007](decisions/0007-disclosure-control-by-pooling-and-stable-treatment.md) | Pooling and stable treatment | Accepted, 2026-11-11; amended by decision 0016 on 2026-11-12 |
| [0008](decisions/0008-assistant-never-types-a-number.md) | Application-rendered numbers, never model-typed numbers | Accepted, 2026-11-11 |
| [0009](decisions/0009-provenance-classes-and-evidence-status.md) | Separate provenance and evidence-status axes | Accepted, 2026-11-11 |
| [0010](decisions/0010-story-opens-on-public-evidence.md) | Public evidence opens the story | Accepted, 2026-11-11 |
| [0011](decisions/0011-store-selection-at-start-up.md) | Start-up store selection and no automatic failover | Accepted, 2026-11-11; item 4 amended by decision 0023 on 2026-11-13, which removes the oversight seat |
| [0012](decisions/0012-neutral-source-labels-and-no-product-comparisons.md) | Neutral labels and no named product comparisons | Accepted, 2026-11-11 |
| [0013](decisions/0013-one-deep-journey-before-breadth.md) | One deep journey before breadth | Accepted, 2026-11-11; superseded by decision 0016 on 2026-11-12 |
| [0014](decisions/0014-typed-decision-gateway.md) | Offline typed-decision gateway, default provider none | Accepted, 2026-11-11 (amendment 1 to the first pack) |
| [0015](decisions/0015-review-rounds-and-the-scope-of-repository-checks.md) | Review rounds after the first, proposed open items, the scope of the repository's checks, and building ahead | Accepted, 2026-11-12 (amendment 2 to the first pack) |
| [0016](decisions/0016-version-1-covers-the-whole-initiative.md) | Version 1 covers the whole initiative: seven journeys, three services and four cases, with drawn areas, simulated footfall and traffic, monthly periods and named synthetic firms | Accepted, 2026-11-12 (amendment 3 to the first pack); where it says that no revenue, demand or success forecast is given, amended by decision 0019 on 2026-11-12; items 12, 13 and 19 to 21 amended by decision 0022 on 2026-11-13 |
| [0017](decisions/0017-public-data-additions-and-public-splits.md) | Public data additions, public splits by sex and nationality, and investment sources | Accepted, 2026-11-12 (amendment 4 to the first pack); items 4 and 5 amended by decision 0019 on 2026-11-12; item 9 amended by decision 0022 on 2026-11-13 |
| [0018](decisions/0018-priorities-and-amendments-to-decision-0015.md) | Priorities of the proof of concept (strict in two places only, other hardening to document 17) and amendments to decision 0015 | Accepted, 2026-11-12 (amendment 5 to the first pack) |
| [0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) | Forecasts, estimates and base rates by tested code in place of the ban on forecasts; scenario tools; people present by pay band; an optional 3D view; six self-serve sources and two keys; rules 4, 10, 24 and 25 of AGENTS.md amended; the pack cited by stable anchor | Accepted, 2026-11-12 (amendment 6 to the first pack); item 1 amended by decision 0022 on 2026-11-13 |
| [0020](decisions/0020-freeze-bundle-check-and-project-database-port.md) | Freeze-bundle preflight and the database port of this project's Compose service | Accepted, 2026-11-12 (amendment 7 to the first pack) |
| [0021](decisions/0021-one-speed-for-a-link-and-an-hour.md) | One speed for a link and an hour: the speed floor, the hour mechanism of drive areas, turns at junctions and the version-1 traffic values | Accepted, 2026-11-13 (amendment 8 to the first pack) |
| [0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) | Real register companies with a synthetic labour and residence world attached and treated as real; named synthetic firms retired; the subject `register_company`; rules 3, 8, 10 and 24 of AGENTS.md amended | Accepted, 2026-11-13; its open questions on legal entities, groups, the address type and monthly openings and closures settled by decision 0023 on 2026-11-13; items 3, 4, 6 and 7 amended by decision 0023 on 2026-11-13 where they name the ministry view |
| [0023](decisions/0023-ten-additions-and-the-data-rule.md) | Ten additions (talent available near this site, Qatar in 3D with a clock, the national GIS centre's layers, voice, best three sites with "how sure", the financial centre's firms, satellite imagery with address search and a photorealistic 3D mode, property prices and bank credit, the decision question bank, and tenders, district cooling and ten open-data families); the site answer's order; the data rule that builds synthetic records only for the confirmed ministry sources; a product for companies, designed for three personas, without the oversight seat or a ministry-only view; rules 3, 8 and 10 of AGENTS.md amended; the owner's decisions of 2026-11-14 add the 30-minute cap (item 17), the talent ratio (item 1) and the movement splits (item 16) | Accepted, 2026-11-13 |
| [0024](decisions/0024-one-private-name-in-two-places.md) | One name of the private registry passes in two places (a source row of document 04 and the map attribution line), known to the repository by its digest in a configuration of at most one entry (TST-263); amends a consequence of decision 0012 | Accepted, 2026-11-14 |
| [0027](decisions/0027-hosted-web-checks-time-limit.md) | The web checks of the whole test command may run 3,000 seconds on GitHub's hosted runner, 1,800 seconds everywhere else; a stopgap until task S1-T15 makes the suite fast enough on slow runners; no test, assertion, bound or suite changes | Accepted, 2026-11-14 |

## Identifiers and change control

1. A requirement ID has its document prefix and a number. It is defined exactly once, as the bare first cell of a requirement-table row; other documents may reference it only after confirming that definition.
2. Value-stack capabilities are always written "capability M1" to "capability M8" and "capability S1" to "capability S11". Build slices are always written "slice S0" to "slice S11" to avoid confusing the two families. Decision 0016 adds journeys D1 to D7, services S1 to S3 and cases C1 to C4: write "service S1" and "case C1" wherever a slice, a capability or a method card of document 07 could be meant; the journeys need no family word.
3. Slice IDs and gates come from document 14. Task IDs, scope and acceptance criteria come from TASKS.md; do not guess either before those files are complete.
4. Decision-record numbers are four digits. A record explains context, decision, evidence, consequences and what would change it.
5. After approval, a material change is proposed and reviewed as an amendment recorded in a new decision record. Existing approved text is never silently edited to hide a changed decision.
6. Routine corrections that do not change a decision still go through the normal task, review and evidence workflow. [PROGRESS.md](../PROGRESS.md) records evidence; [OPEN_ITEMS.md](../OPEN_ITEMS.md) records unresolved questions.
7. "A lead ruling of 2026-11-11" means a ruling the lead gave on a reviewer's finding while this pack was reviewed. The rulings are a project record held by the owner and are not in this repository; every ruling that changed the design is written into the documents themselves, and into a decision record where it changed a decision.
8. Figures attributed to "design research", "architecture research", "methods research", "graph research", an "engineering judge" or a "feasibility review" and dated 2026-11-11 were measured once while the design was chosen, on third-party software with throwaway synthetic tables or public inputs, before any product code existed. They are not test results of this product, their raw outputs are not in this repository, and each is measured again at the slice that builds the part concerned.
9. The pack is cited by a stable anchor, never by line number: a requirement ID with its file, a section heading (with the table row or the numbered item where one is meant), a task ID, a rule number or the numbered item of a decision record. Every check that reads citations verifies that the anchor exists in the cited file (rule 33 of [AGENTS.md](../AGENTS.md); [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 26). In a decision record, write "item 5 of decision 0019", never a bare "D5", which names a journey.

## Open questions and assumptions

The implementation plan and TASKS.md are drafts, not claims that build work is complete. The initial typed-decision set does not establish human ground truth; OI-15 remains open. All other open questions are in [OPEN_ITEMS.md](../OPEN_ITEMS.md).

## Sources

The numbered documents and decision records linked above; no external source is restated by this index.
