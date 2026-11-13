# 17 — Deployment hardening

| | |
|---|---|
| Status | Draft v0.2, created by decisions 0016 and 0017 and amended by decisions 0018 and 0019 on 2026-11-12, and by decisions 0022 and 0023 on 2026-11-13 |
| Date | 2026-11-13 |
| Owner | albarami |
| Purpose | List what a deployment on real records must add beyond the demonstrator, so that no version 1 capability is read as ready for real data. |
| Read first | [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md), [13_DEPLOYMENT_AND_OPERATIONS.md](13_DEPLOYMENT_AND_OPERATIONS.md), [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), [decision 0018](decisions/0018-priorities-and-amendments-to-decision-0015.md), [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md), [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) |

## In brief

- Nothing is built yet. Version 1 is a demonstrator on synthetic custodian-type labour and residence records attached to the real companies of the public registers ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)), simulated mobility and cited Public data. It reads no real custodian record, except the calibration table of the owner's note, read only by the world build, and no real mobility feed (AGENTS.md rules 3 and 4); the one live outside source at run time is the optional traffic provider, off by default ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 17).
- This document lists what a deployment on real records must add. Each item is a precondition of that deployment, not a version 1 feature. Nothing here says that the product exists, that it passes a gate or that version 1 meets any item.
- The version 1 controls are the floor. A deployment adds controls; it never relaxes one (AGENTS.md rule 12).
- Six areas: real footfall counts from a telecom feed; differencing across periods, the forecast of a real protected series included; firm-level release of real register fields; query auditing and rate limits for drawn areas; the sources, the traffic provider included, that stay on if the product is ever hosted publicly or for a commercial purpose; and the governance of real custodian data, where document 13 already covers several points.
- This proof of concept is strict in two places only (DHA-05). Section 8 holds the real-deployment items that the owner's note of 2026-11-12 moved here from [OPEN_ITEMS.md](../OPEN_ITEMS.md), and section 9 is the register of hardening points raised during the build.

## 1. Position

| ID | Requirement |
|---|---|
| DHA-01 | This document applies only to a deployment that reads real custodian records, a real mobility feed or real custodian figures about named firms. Version 1 does none of these (BRF-37, BRF-38): it shows the fields that the public business register and the financial centre's public register publish for each register company, which are Public, and the employee count of the synthetic labour and residence records attached to it; the one real custodian-type input, the calibration table of the owner's note, is a table of totals read only by the world build ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)). The optional traffic provider and the published relative busyness of named venues are neither a custodian record nor a mobility feed; section 6 covers their hosting. |
| DHA-02 | Each requirement that concerns a deployment is met, with its evidence recorded, before that deployment reads its first real record. No document, screen or presentation says that version 1 meets one. |
| DHA-03 | A deployment keeps every version 1 privacy invariant, security control, test, attack size and tolerance (AGENTS.md rule 12; TST-03). Where a requirement below and a version 1 rule differ, the stricter one applies. |
| DHA-04 | Each requirement below becomes work only through a decision record and the normal task, review and evidence workflow ([README.md](README.md), "Identifiers and change control"). |
| DHA-05 | Priority rule ([decision 0018](decisions/0018-priorities-and-amendments-to-decision-0015.md) items 1 to 4). This proof of concept is strict in two places only: nothing secret, real or private reaches the public repository, and numbers and claims stay right. |
| DHA-06 | Every other security requirement (the generator sandbox, the hooks, the commit guard, the CI rules, the repository settings, tamper resistance) is built in its simplest form that meets its acceptance criterion in [TASKS.md](../TASKS.md). |
| DHA-07 | Hardening beyond that criterion is never a verdict finding, in any review round. It is listed here with its origin (the review, plan or document that raised it) and is not built now. Section 9 is its register. |
| DHA-08 | At each plan's one refresh, above all S0-T06, S0-T07, S0-T11, S0-T12 and S0-T14, such hardening moves out of the plan into this document. |

## 2. Real footfall counts from a telecom feed

Version 1 simulates presence locally and contacts no telecom operator. Its estimated people present are released only at release-unit grain under the panel minimum, complementary suppression and rounding of document 06, and are worded "estimated people around this location" ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 7). The version 1 rule mirrors the thresholds an operator would apply; it is not a person-level privacy guarantee (document 06, section 9.2).

| ID | Requirement |
|---|---|
| DHA-10 | Real presence counts come only from a provider's aggregate feed and follow that provider's own disclosure rules: its contribution limits for each device across cells, hours, segments and origin-destination rows, its minimum panels, and its published methodology. Each release records which provider rules applied, in which version, and cites the methodology like any source (AGENTS.md rule 5). |
| DHA-11 | No device data enters the product: no device identifier, trajectory, single-device row, panel size or expansion factor. The custodian plane receives aggregates only, and only release-unit aggregates leave it (PRV-57, PRV-59). |
| DHA-12 | The version 1 panel minimum, complementary suppression and rounding (PRV-58) remain the floor; where the provider's rule is stricter, the provider's rule applies. |
| DHA-13 | A person-level protection claim for movement is made only where the provider supplies auditable cross-row contribution limits covering every cell, hour, situation, segment and origin-destination row, and only within what that audit shows (PRV-60). |
| DHA-14 | Until a decision record says otherwise, the wording stays "estimated people around this location", and no count is attributed to a named building or business as its footfall (AGENTS.md rule 24). |

## 3. Differencing across periods

Version 1 holds one protected window with monthly periods inside it. Each month passes the same disclosure controls, one treatment holds for every month, adjacent-month cohorts pass their tests, and cross-month differencing attacks must recover nothing (decision 0016 item 10; TST-205, TST-206, TST-220). Version 1 builds no second window and makes no consecutive-window claim (PRV-53, PRV-56). Real records arrive release after release, so a deployment needs more.

| ID | Requirement |
|---|---|
| DHA-20 | Release cadence: real releases follow a fixed cadence agreed with the data owner and stated with each release. A released period is never released again under another treatment (PRV-120). |
| DHA-21 | Rolling windows: before a second protected window is exported, the second-window rules of PRV-56 and the partition freeze of PRV-23 are built, two adjacent complete test windows are attacked inside the custodian plane, and the full attacker-view audit passes across both windows (document 06, section 17). |
| DHA-22 | Cohort tests: every change between consecutive periods, across months and across windows, is enumerated at origin and destination (joiners, leavers, movers, and contributors whose employer group, band or category changed), and each cohort passes every affected tier and atom test (PRV-56). |
| DHA-23 | Stable suppression: a cell withheld in one period stays unrecoverable from every later period, every multi-period total and every difference between releases. The mover attack and every cross-period typed predicate run before each new window is exported. |
| DHA-24 | Query auditing: the serving plane records which released figures each organisation and session read, by area, period and list, with no record-level data in the record (REV-18). A periodic review looks for sequences that combine periods, shapes or lists toward a withheld cell or a small population; a finding tightens the release rule, never the attack (decision 0016). Version 1 has no oversight seat: the question log is an internal record with no screen, and no seat, screen, export or API response shows the log or a roll-up of it (PRV-66, [decision 0023](decisions/0023-ten-additions-and-the-data-rule.md) item 15). |
| DHA-25 | Shared stayer draws: before any real-data pilot, the attacker-view audit models the draws that PRV-42 and PRV-43 share between stayer bills of nested or overlapping units and of different pairs of months, or the stayer index is released only where no two published stayer cohorts can share contributors (origin: pull request 6, review round 2, part 6, F2; document 06, section 17). |
| DHA-84 | Forecasting a real protected series: in version 1 the forecast of card C30 runs on the released monthly statistics of the synthetic custodian-type feeds, a fixed function of rows that are already released and labelled a projection from those months (PRV-54; [02_ARCHITECTURE.md](02_ARCHITECTURE.md) ARC-130, ARC-138; [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 6). A deployment on real records runs the cross-month attack suite (TST-205, TST-206, TST-220) on a forecast of a real protected series before it shows one. |

## 4. Firm-level release of real register fields

Version 1 shows register companies, the real companies of the public business register and of the financial centre's public register ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)); named synthetic firms are retired. A company's card shows every field the register publishes for it, person names excluded, which are Public, and its employee count from the synthetic labour and residence records attached to it; its wages and other labour and residence details appear only as released aggregates under the disclosure rules of document 06. Lists of prospects, partners and suppliers show register companies ordered by tested code over criteria the user can see and change, never by wages. Other real businesses appear only from public places data, public listings and the investment sources of [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) (decision 0016 item 13). A deployment that attaches real custodian records to the register companies would release real company-level figures, and needs this section first.

| ID | Requirement |
|---|---|
| DHA-30 | Releasing any field of real custodian records about a real, named firm, an employee count from real attached records included, needs a recorded legal basis for that field and that use, confirmed in writing by the data owner before the first such release. The fields that the public registers publish are Public facts and not such a release; their terms of use are recorded with their source ([04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md), [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)). The pack gives no legal advice (document 06, section 17). |
| DHA-31 | Every named list is reviewed before release, by a reviewer whose role is recorded, against the list rules and the linkage attack. The review record is kept with the release. A list that lets a reader infer a firm's wages, wage bill or any labour or residence detail beyond an employee count released under DHA-30, alone or with any released figure, is not released; without that basis a firm's headcount stays protected too. |
| DHA-32 | The version 1 list rules stay the floor ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)): the register-company list holds the employee count and no wage, wage-bill, pay-band or other labour or residence column; a company's wage on a card or in a list fails, and so does a released aggregate that isolates one company; every released aggregate keeps the minimum, dominance and complement rules with every employee count as attacker knowledge; the register-company linkage attack recovers nothing (TST-207, TST-222). |
| DHA-33 | No Synthetic, Simulated or apportioned figure, and no estimate, share or score, is attached to a real named firm (AGENTS.md rules 8 and 24; BRF-42; [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 8 and 9), except, in version 1, the employee count of a register company's attached records on its card ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) item 4); in a deployment, a company-level figure from real records follows DHA-30 to DHA-32. |

## 5. Drawn areas: query auditing and rate limits

In version 1 a drawn shape's protected figures snap to whole release units, two shapes that snap to the same units return identical protected figures, and attacks on drawn shapes and apportioning recover nothing (TST-25, TST-204, TST-221). A single-machine demonstrator with three seats needs nothing more; a served deployment does.

| ID | Requirement |
|---|---|
| DHA-40 | Every drawn-area request is logged with a hash of the shape, the release units it snapped to, the period and the requesting session, with no record-level data in the log (REV-18). |
| DHA-41 | Rate limits per session and per organisation cap how many drawn areas, periods and lists can be read in a stated time. The limits are set with the data owner, recorded with the release, and tested at the limit and at one request above it. |
| DHA-42 | An audit flags sequences of shapes whose snapped unit sets differ by one unit or by a withheld group, and shapes nudged repeatedly around one unit. A person reviews each flagged sequence. |
| DHA-43 | Snapping, stable treatment and closure stay the primary control (TST-20, TST-25). Auditing and rate limits are defence in depth, never a reason to relax a disclosure rule. |

## 6. Public and investment sources if hosted publicly

Version 1 runs locally as a personal internal project. The FDI projects dashboard and the investment agency's pages are used on the owner's decision of 2026-11-12 without a permission request, and the census map layers are used in this internal project (decision 0017 items 8 and 10). Every figure shows its source and retrieval date, and fetched data stays in the uncommitted `data/` folder. The relative busyness of named venues (`busy_gmaps`) is used on the owner's decision of 2026-11-12 for this personal internal project, although the publisher states no licence for reuse and its terms name automated reading ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 19); the traffic provider and the free weather interface (`weather_openmeteo`, non-commercial use) run within their free allowances.

| ID | Requirement |
|---|---|
| DHA-50 | Before the demonstrator or a deployment is hosted publicly, the owner decides which public and investment sources stay on and records that decision in a decision record (decision 0017). |
| DHA-51 | That decision reads each source's terms again for the public use: the FDI projects dashboard and the investment agency's pages; the census map layers, whose licence question for any wider use is open (DHA-70); and every other source under its recorded licence, the portal datasets under their CC BY 4.0 attribution included, and the sources of [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) under the terms recorded for them (DHA-85 to DHA-87). |
| DHA-52 | A source whose terms do not allow the public use is switched off before hosting, and the owner is told (decision 0017, "What would change this decision"). |
| DHA-53 | The decision also states whether official splits by sex or nationality (the WorldPop grids by age and sex, under their CC BY 4.0 attribution, included), and FDI projects that name real investing companies, are shown on a public host. |
| DHA-54 | On a public host each figure keeps its source and retrieval date, and fetched data stays out of the repository, as it does locally. |
| DHA-85 | Traffic provider. Before the demonstrator is hosted publicly or for a commercial purpose, the traffic provider stays off until the owner decides ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), "What would change this decision"). That decision settles the provider's developer terms for that use, which could not be read on 2026-11-12, among them its rule on storing responses (nothing is stored in version 1); the attribution "© TomTom" shown while a live layer is on; where the key is kept on a host (it stays in the API process and in no log, ledger or file); and whether the monthly free allowance (200,000 tile requests, 2,500 reachable-range requests) is enough or a paid arrangement is made. |
| DHA-86 | Relative busyness of named venues. The source `busy_gmaps` states no licence for reuse, and the publisher's terms name automated reading. It is used on the owner's decision of 2026-11-12 for this personal internal project (`licence_basis: owner_decision`, named under PUB-12), its values stay in the uncommitted public cache and in no repository or test fixture, and it is left out of the nightly live fetch. Before any public or commercial hosting it stays off until the owner decides; a source whose terms are read at a fetch to forbid the use made here is switched off and the owner is told. The label "Google Maps popular times" with its retrieval date stays on every figure. |
| DHA-87 | Weather history. The free Open-Meteo interface is for non-commercial use and its data is CC BY 4.0. The non-commercial basis ends with any public or commercial use, so before such hosting the source `weather_openmeteo` stays off until the owner decides, and the attribution the publisher asks for stays on the figures that rest on it. |

## 7. Governance of real custodian data

Document 13 already covers the deployment platform, the place of the build engine, the network binding and the identity and audit services. This section points to it and adds what a real-data deployment needs.

| ID | Requirement |
|---|---|
| DHA-60 | Platform: a custodian-approved environment with the same PostgreSQL major version and PostGIS line as version 1, in an in-country cloud region or on a custodian server. No deployment-fit statement is made until the custodian confirms its platform in writing ([13_DEPLOYMENT_AND_OPERATIONS.md](13_DEPLOYMENT_AND_OPERATIONS.md), OPS-51 and OPS-54; DHA-73). |
| DHA-61 | The build engine and the custodian plane run only inside the custodian environment, and only a release crosses to the serving store (OPS-52; AGENTS.md rule 11; [decision 0002](decisions/0002-three-planes-and-the-release-boundary.md)). |
| DHA-62 | The API binds beyond the loopback address only in a deployment that the custodian approves in writing (OPS-01). |
| DHA-63 | Identity and audit: single sign-on at the API and database audit logging (OPS-53) replace the version 1 seat picker, which shows query isolation after selection and is not identity or tenant authentication (BRF-24, PRV-117). |
| DHA-64 | Data owners set the real privacy thresholds (DHA-71). Real suppression rates are measured inside the custodian environment and reported in the survival report before any figure is shown (document 06, section 17). |
| DHA-65 | Each real adapter passes its contract's conformance suite unchanged before its feed is accepted (TST-30, TST-31). |
| DHA-66 | Whether and how real records may be linked is for the data owners, with the legal basis recorded. The pilot request states feed scope, custodians, purpose, period, operator, environment, legal basis, pass criteria and kill criteria before any real feed is used (OI-28). |
| DHA-67 | Every real release passes the attack suite, the attacker-view audit and the recorded human release review before it is frozen, as a synthetic release does (TST-120 to TST-126, TST-188, TST-194). |

## 8. Items moved from OPEN_ITEMS.md

On 2026-11-12 the owner's note moved these real-deployment items here ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 21; [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 10). Their earlier text stays in [OPEN_ITEMS.md](../OPEN_ITEMS.md), and version 1 keeps each documented default.

| ID | Requirement |
|---|---|
| DHA-70 | Census map-layer licence (origin: OI-04, closed for version 1). Before any use of the statistics authority's census map layers beyond this internal project, written licence terms for that use are recorded. Until then they are used only in the local release of this project, each figure with its source and retrieval date, and nothing fetched from them is committed. |
| DHA-71 | Real privacy thresholds (origin: OI-11). Before any real-data pilot, the data owners set and hold the real thresholds. Version 1 default: sets A and B are evaluated inside the custodian plane and set A is exported; no rule is tuned to make an area look finer. |
| DHA-72 | Independent human attack (origin: the pilot part of OI-24). Decide whether an independent human attacker session precedes a real-data pilot; the open item recommends that it does. The selection of public totals for the attacker-view audit stays in OPEN_ITEMS.md for slice S5. |
| DHA-73 | Deployment platform (origin: OI-26). The custodian confirms its database platform, approved region, data-residency terms and operating environment in writing. Version 1 makes no deployment-fit statement (DHA-60). |
| DHA-74 | Layout signals before a real-data pilot (origin: OI-36). Before any real-data pilot, either the disclosure-control failure branches are modelled, with predicates that separate what a rule publishes by design from what it leaks, or an attack runs against every released instance of each layout signal. Version 1 default: layout signals stay outside the acceptance model, the limit is stated, and the typed attack suite covers each kind of layout signal. |

## 9. Hardening register

Hardening points raised during the build that go beyond a task's acceptance criterion ([decision 0018](decisions/0018-priorities-and-amendments-to-decision-0015.md) items 3 and 4). Each entry names its origin. No deciding check is built now; entries that were built and later removed say so explicitly. A deployment on real records, or a decision record, turns an entry into work (DHA-04).

| ID | Requirement |
|---|---|
| DHA-80 | Host rule of built JavaScript (origin: the first review of task S0-T03, pull request 3, round 1, proposed item P1). The built-JavaScript host rule stops at a colon and does not look for a user part before an at-sign, so a URL whose user part names an allowed host can hide a third-party host. This is hardening against deliberate evasion. Before a deployment, the rule parses the URL, rejects any user part and compares the real host with the allow-list. Not built now. |
| DHA-81 | Exact AppArmor listing (origin: the plan of task S0-T11; the owner's notes of 2026-11-12). Requiring `aa-status --json` to parse in an exact format and list `bwrap` and `unpriv_bwrap` by exact name in enforce mode was built with task S0-T11 and removed as a deciding check in task S0-T15. The command's raw exit status, standard output and standard error are printed for the record; behaviour decides the hosted sandbox proof. |
| DHA-82 | Profile file pin by size and SHA-256 (origin: the plan of task S0-T11; the owner's notes of 2026-11-12). Requiring the distribution and installed `bwrap-userns-restrict` files to match a pinned size and SHA-256 was built with task S0-T11 and removed as a deciding check in task S0-T15. Both files' sizes and hashes are printed for the record without comparison; an existing file that differs is never replaced. The source must exist, installation and loading must succeed, and the probe after loading must pass. |
| DHA-83 | Stacked AppArmor label (origin: the plan of task S0-T11; the owner's notes of 2026-11-12). Requiring a program started by bubblewrap to read exactly `bwrap//&unpriv_bwrap (enforce)` was built with task S0-T11 and removed as a deciding check in task S0-T15. The label command's raw exit status, standard output and standard error are printed for the record, including failures or text that cannot be parsed; the namespace probe and prohibited-operation tests still decide the result. |
| DHA-88 | Neutral git environment for the secret scanner (origin: the plans of tasks S0-T06 and S0-T07). The staged scan and the history scan would run the secret scanner in a neutral git environment, so that git attributes and text-conversion drivers cannot hide a token, and would refuse a non-empty attributes file of the clone and a git too old to offer the needed setting. Not built now. |
| DHA-89 | Refusal of a scanner ignore file (origin: the plans of tasks S0-T06 and S0-T07). A `.gitleaksignore` file in the work tree or the index would be refused. Not built now. |
| DHA-90 | Closed child environment of the secret scanner (origin: the plans of tasks S0-T06 and S0-T07). Every `GITLEAKS_*` variable, and every git variable outside a closed list, would be removed from the scanner's child environment. Not built now. |
| DHA-91 | Second digest of the extracted scanner binary (origin: the plan of task S0-T06 (its first plan review)). A second pinned digest of the extracted scanner binary would be checked again at every use, together with its file type, link count and size, and the download would have size caps. Not built now. |
| DHA-92 | Further test inventories of the commit hooks (origin: the plan of task S0-T06 (its internal critique and its plan reviews)). The inventories would cover hostile repository settings for the guard and the scanner, every type of index entry, the corner cases of the `.env` grammar and of database addresses, a failure table of the four scripts, the corner cases of the installer and the dispatcher, tests of the stated limits, and a mutant list. Not built now. |
| DHA-93 | Proofs of the commit hooks beyond the recorded commands (origin: the plan of task S0-T06). The proofs would be a run with the network unshared, an independent probe of the scanners, and a scratch-copy run of the real tools through the hooks with a measurement of the commit time. Not built now. |
| DHA-94 | Cancellation of superseded workflow runs (origin: the plan of task S0-T07). A concurrency setting in the workflow files would cancel a superseded run. Not built now. |
| DHA-95 | YAML policy beyond the safe loader (origin: the plans of tasks S0-T07 and S0-T08 (part C)). For the workflow files and the Compose file, anchors, aliases, merge keys, explicit tags and duplicate keys would be refused. Not built now. |
| DHA-96 | Mutation inventories for the workflow rules and the Compose contract (origin: the plans of tasks S0-T07 and S0-T08 (part C)). Mutation inventories and self-mutation proofs for the workflow rules and the Compose contract, and grammar checks of hosted logs, would go beyond one planted violation a rule. Not built now. |
| DHA-97 | Process and environment protections of preflight's child runner (origin: the plan of task S0-T08 (part C)). Protections of the child runner would go beyond the bounded runner and the two exact sandbox argument lists. Not built now. |
| DHA-98 | A rendered proof of the Compose file (origin: the plan of task S0-T08 (part C)). The test suite would hold a proof of the Compose file as the runtime renders it, or another live service proof. Not built now. |
| DHA-99 | Required checks bound to the reporting application (origin: the plan of task S0-T14). Each required check of the base-branch ruleset would be bound to the application that reports it. Not built now. |
| DHA-100 | Ruleset refusals in a disposable repository (origin: the plan of task S0-T14). A rejected direct push, forced push, deletion, missing check, failing check and administrator bypass would each be exercised in a disposable repository. Not built now. |
| DHA-101 | Drift watch for the repository settings (origin: the plan of task S0-T14). Comparators, fixtures and self-tests for the settings calls, and a continuous watch for drift of the repository settings (rule-suite history and merge-state checks), would be kept. Not built now. |

## Open questions and assumptions

- ASSUMPTION: a deployment keeps the three planes and the release-only boundary ([decision 0002](decisions/0002-three-planes-and-the-release-boundary.md)) and one treatment per window ([decision 0007](decisions/0007-disclosure-control-by-pooling-and-stable-treatment.md), PRV-120).
- OPEN: which provider, if any, supplies a real mobility feed, and under which rules; no feed is used before a decision record approves it (DHA-10).
- OPEN: the release cadence and window length for real records, set with the data owner (DHA-20).
- OPEN: the rate-limit values, the audit review interval and the role that reviews flagged sequences, set with the data owner (DHA-41, DHA-42).
- OPEN: the legal basis for any firm-level release, including whether a firm named in a list is told and may object, decided with the data owner (DHA-30).
- OPEN: which sources stay on if the product is ever hosted publicly or for a commercial purpose (DHA-50 to DHA-53, DHA-85 to DHA-87).
- OPEN (decision 0022): whether a deployment that attaches real custodian records shows each register company's real employee count on its card, decided with the data owner under DHA-30.
- OPEN (decision 0022): whether the two public registers stay on if the product is ever hosted publicly or for a commercial purpose belongs to the decision of DHA-50; their terms are recorded when the register file is first read.
- The entries of section 9 stay unbuilt until a decision record or a real-records deployment makes them work.
- The items of section 8 stay open as real-deployment items; [OPEN_ITEMS.md](../OPEN_ITEMS.md) keeps their history.

## Sources

- [Decision 0018](decisions/0018-priorities-and-amendments-to-decision-0015.md), 2026-11-12: the priority rule and the register of section 9.
- [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), 2026-11-12: the provider, the relative-busyness source, the weather source and the forecast of a real protected series, whose real-deployment consequences DHA-84 to DHA-87 list.
- [Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) and [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), 2026-11-12: the version 1 scope and the public data additions whose real-deployment consequences this document lists.
- [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md), 2026-11-13: the register companies and the attached synthetic records that DHA-01 and section 4 now describe.
- [Decision 0002](decisions/0002-three-planes-and-the-release-boundary.md) and [decision 0007](decisions/0007-disclosure-control-by-pooling-and-stable-treatment.md): the release boundary and the stable treatment that a deployment keeps.
- [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) (sections 9 and 17), [13_DEPLOYMENT_AND_OPERATIONS.md](13_DEPLOYMENT_AND_OPERATIONS.md) (sections 2 and 11), [12_TESTING_AND_QUALITY.md](12_TESTING_AND_QUALITY.md) and [OPEN_ITEMS.md](../OPEN_ITEMS.md).
- No external source was used.
