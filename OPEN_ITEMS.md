# Open items

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016, 0017, 0018 and 0019 on 2026-11-12 and by decision 0023 on 2026-11-13, and by decision 0026 on 2026-11-14 (see PROGRESS.md) |
| Date | 2026-11-14 |
| Owner | albarami |
| Purpose | Track every unresolved owner decision, assumption, pending correction and technical unknown without implying closure. |
| Read first | [docs/README.md](docs/README.md), [PROGRESS.md](PROGRESS.md) |

## In brief

- OPEN means a decision, source or proof is still needed.
- ASSUMPTION means work may use the stated default, but the named owner must confirm or replace it.
- PENDING means review or correction work has not yet supplied evidence.
- CLOSED means the item is settled by the decision it names; its earlier text is kept.
- MOVED means a real-deployment item now listed in [docs/17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md); its earlier text is kept.
- The recommendation is the safe default, not a new decision. A material change needs a decision record.
- Items OI-01 to OI-18 carry the master decisions; OI-19 to OI-38 come from the written pack and its review.
- OI-36 to OI-38 record what the review of 2026-11-11 left open: an objection of two reviewers that was not accepted for version 1, and two sets of last corrections that another maker has not yet read.
- OI-35 records which parameter set is exported. A lead ruling of 2026-11-11 sets the default to A; the owner or a data owner may overrule it before the slice S1 gate.
- OI-39 onwards are raised during the build.
- OI-96 (closed by the owner's answer of 2026-11-12) and the items after it record the points of [decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md): the age of the places copy, the Public source for the survival base rate, the Public source of each forecast series without a table, the provider's rule on storing responses, the sources that are off under a public or commercial hosting, the size of the public-total inventory with the two gridded Public tables, the subject of a district series and the build without the night-lights key.
- OI-132 to OI-148 record the open points of [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md). The owner's pending questions are whether road traffic is part of the movement source, the gaps N1, N3, N4, N6 and N7 of the decision question bank (hiring and leaving flows, rents, an events calendar, supplier certifications and school capacity), who keeps the monthly register snapshots (OI-141), and whether a commute line from a whole home municipality to the site's snapped catchment meets the district-pair case (OI-147, with card C39's form as the default). The owner's attribution note for the imagery provider is received (ruling L-151 records the note and its permitted locations); OI-132 remains for the documentation guard's exception, which task S1-T14 builds. The owner's answer of 2026-11-14 settles the talent ratio (OI-140) and the movement splits (OI-134, item 16). OI-148 confirms the age bands against the operator's format when its data arrives, and is not an owner question. The others are the register file's fields still to confirm (OI-142), the look's task S3-T15 (OI-143), the recovery tracker and the Qatarization planner (OI-144), and two assumptions: the age profile of people living here (OI-145) and prices per square foot (OI-146). The decision also updates OI-08 (items 12 and 15), OI-27 (item 15, a product for companies), OI-97 (item 12), OI-98 (items 8 and 12) and OI-102 (items 6 and 8).

## OI-01 — Main model key (supplied for go-live; not used during the build)

- ID: OI-01
- TYPE: OPEN
- NEEDED: At go-live only: the owner's decision to switch the live adapter on, with any spend caps set then. During the build the key is not used.
- WHY: Live-model evaluation and operation cannot be claimed until the owner enables the supplied go-live key and sets the cost limits.
- DONE SO FAR: The template writer and recorded provider are used throughout the build; no build, CI or slice gate calls a keyed model service, and live-model runs (prepared recordings refreshed live, model-returned briefs, a full live run) form a go-live gate enabled by an owner decision after this item is closed.
- OPTIONS: **Recommendation:** keep the template writer and the recorded provider for the whole build; the live adapter and its evaluation gates wait for the owner's go-live decision.
- NEEDED BY: go-live (not before; the build runs in template mode).
- UPDATE: 2026-11-12, by the owner's note of that day, recorded in [decision 0018](docs/decisions/0018-priorities-and-amendments-to-decision-0015.md): key supplied for go-live; not used during the build. The assistant stays in template mode during the build. `TOMTOM_API_KEY` and `EARTHDATA_API_KEY` lie outside the keys of that item and may be used by the build within their free allowances ([decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 16); neither is printed, logged or committed, and no test, gate, command or the guided story needs either.

## OI-02 — Demonstration date

- ID: OI-02
- TYPE: OPEN
- NEEDED: The owner to set the demonstration date and confirm the venue display conditions.
- WHY: Freeze timing, rehearsals, theme and room scale depend on them.
- DONE SO FAR: No date-driven freeze is scheduled; a venue check is specified.
- OPTIONS: **Recommendation:** set them only when known, then rehearse on the actual display. Do not invent a deadline.
- NEEDED BY: slice S11 freeze and [16_DEMO_RUNBOOK.md](docs/16_DEMO_RUNBOOK.md).

## OI-03 — Conflicting restaurant and wage figures

- ID: OI-03
- TYPE: OPEN
- NEEDED: Reconcile the two restaurant totals and the two wage-table means by dataset, field, measure, activity scope and year; record owner sign-off.
- WHY: Conflicting public figures must not be displayed as though they were the same measure.
- DONE SO FAR: The candidate sources and reconciliation steps are documented; affected display cards stay blocked. The site demand and revenue estimate and the revenue range of the user's outlet ([decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 8 and 10) read the survey figures and stay off screen while this item is open.
- OPTIONS: **Recommendation:** follow the documented reconciliation and default to the named production-value and occupation tables only after sign-off. Otherwise leave the figures hidden.
- NEEDED BY: slice S2 reconciliation; slice S7 methods and affected story scenes.
- UPDATE: 2026-11-14, by [decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md): Restaurant production value is not a field of the present datasets and is neither derived nor shown. It is no longer a default or a reconciliation candidate. Reconciliation R1 is closed on that basis in the reconciliation record of task S2-T03, which is not merged yet. The wage-table reconciliation remains. Card C4 keeps shares of output computed from published figures only (item 12).
- UPDATE: 2026-11-15, by the ledger of merge train A (task S2-T03): the two reconciliations are computed and recorded. R1 is recorded as "closed: not published": the production value is not a field of the four datasets and is neither derived nor shown. R2 is recorded as "reconciled: tables differ, occupation table used", with the other mean shown in the source chain. These status words are written by code as dispositions of evidence; they are not closure of this item and they release nothing. The closure mechanism and its tests are built: a missing record or an absent sign-off cannot close the item or release an affected fact, and every affected display fact stays blocked. The reconciliation record `docs/decisions/0025-reconciliation-of-restaurant-and-wage-figures.md` is proposed, not accepted. Still needed: the advisor's signed note under the owner's delegation, bound to the hash of that record and to the complete affected source set; then the registry entries move to resolved and the lead records the closure. OI-171 and OI-172 wait for the same sign-off.


## OI-04 — Census map-layer licence

- ID: OI-04
- TYPE: CLOSED for version 1 (was OPEN)
- NEEDED: Written licence confirmation for the statistics authority's census map layers and associated boundary use.
- WHY: Redistribution and display rights are not stated.
- DONE SO FAR: A source with no stated licence is validation-only until its terms are recorded. No value, derived share, title or geometry from it enters a release. The coverage bar uses the finest licensed geography available (zone, otherwise municipality, otherwise national) and names it.
- OPTIONS: **Recommendation:** obtain and record written confirmation; until then keep the source validation-only and use the finest separately licensed geography for coverage and boundary geometry.
- NEEDED BY: slice S2 public frame and coverage data.
- CLOSED: 2026-11-12, by the owner's note of that day, recorded in [decision 0017](docs/decisions/0017-public-data-additions-and-public-splits.md): the census map layers of the statistics authority's public map service are used in this internal project. The written licence question for any use beyond it is a real-deployment item in [docs/17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md), section "Items moved from OPEN_ITEMS.md".
- UPDATE: 2026-11-14, by [decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md): The earlier validation-only restriction no longer holds in version 1. Census map layers follow the same rule as every public source: visitor-readable sources are used and shown in full, with the publisher's terms recorded in its own words with the date read and the basis of use in document 04. Nothing from a source not under an open licence is committed. The frame's geometry still comes from the licensed boundary source and the census map layers are joined by keys. Document 17 keeps the one list of permissions or licences needed before real use; nothing on it holds back version 1 (items 1 to 5 and 9).


## OI-05 — Product and Arabic names

- ID: OI-05
- TYPE: OPEN
- NEEDED: Owner clearance of the product name and its Arabic name.
- WHY: The working title is not an approved public identity.
- DONE SO FAR: “Economic & Investment Intelligence (EII)” is the working title; no Arabic name is proposed here.
- OPTIONS: **Recommendation:** keep the working title until clearance, then record the approved names.
- NEEDED BY: slice S3 shell; slice S10 Arabic sign-off and pack.

## OI-06 — Source labels on screen

- ID: OI-06
- TYPE: OPEN
- NEEDED: Owner choice between neutral record-type labels and named custodians, plus the configuration mechanism.
- WHY: Labels must not imply supply or endorsement by a custodian.
- DONE SO FAR: Neutral record-type names are the default.
- OPTIONS: **Recommendation:** retain neutral labels. Named custodians require explicit owner approval and one configuration value, not code or contract renames.
- NEEDED BY: slice S3 interface; slice S10 reviewed strings.

## OI-07 — Fictional prospect list

- ID: OI-07
- TYPE: CLOSED (was OPEN)
- NEEDED: Owner decision on whether later item L8 may include a clearly fictional list of firms.
- WHY: A synthetic prospect list can read as a real recommendation and reopens the firm channel.
- DONE SO FAR: No prospect list is in version 1; firm and owner networks are dropped. On 2026-11-13, [decision 0022](docs/decisions/0022-real-register-companies-with-a-synthetic-world.md) replaced named synthetic firms by register companies, the real companies of the public business register: lists of prospects, partners and suppliers show register companies with their card fields and employee counts, ordered by tested code over criteria the user can see and change; networks of firms or owners stay dropped.
- OPTIONS: **Recommendation:** keep it excluded. Any later list needs an owner-approved decision and a fresh privacy and wording review.
- NEEDED BY: After slice S11, backlog item L8.
- CLOSED: 2026-11-12, by the owner's decisions of that day, recorded in [decision 0016](docs/decisions/0016-version-1-covers-the-whole-initiative.md) (item 12): named synthetic firms are allowed in version 1 as prospects, partners and suppliers, always marked Synthetic, with names that never resemble real ones; networks of firms or owners stay dropped.

## OI-08 — Oversight labels and organisation minimum

- ID: OI-08
- TYPE: OPEN
- NEEDED: Confirm the distinct-organisation minimum for a roll-up of the internal question log made for the evaluation, which shows no company identity and only groups of at least that minimum ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-66). The live-row label and the demand-aggregate use left with the oversight seat (item 15).
- WHY: Oversight must show demand without exposing company identity or small-group behaviour.
- DONE SO FAR: Live rows default to “this session”, seeded history to Synthetic, and no company identity is shown. The minimum is two for the two-company demonstration; this is demonstration configuration, not a disclosure threshold.
- OPTIONS: **Recommendation:** keep the labels and the demonstration minimum of two; any other value needs an owner decision and must not be presented as a privacy rule.
- NEEDED BY: before the first roll-up of the question log made for the evaluation.
- UPDATE: 2026-11-13, by [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 12: the ledger starts empty and holds only questions asked, so no seeded history exists and its Synthetic label falls away (S9-T03).
- UPDATE: 2026-11-13, by [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 15: the product is for companies only. The oversight seat leaves version 1 with its screen and roll-ups (S9-T04), its read functions (S9-T01) and its badge, and the ledger stays only as the internal question log, with no screen. So no screen shows the live-row label or a demand aggregate, and the read function this item was to align leaves with the seat; the company read functions and their separation tests stay. The distinct-organisation minimum stays open for one use: a roll-up of the question log made for the evaluation shows no company identity and only groups of at least that minimum ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md) PRV-66). It is now needed before the first such roll-up.
- UPDATE: 2026-11-14: NEEDED and NEEDED BY are narrowed to that remaining use. The oversight screen, its live-row label and its demand aggregates stay withdrawn by item 15. Nothing earlier in this item is deleted.

## OI-09 — Native Arabic reviewer

- ID: OI-09
- TYPE: OPEN
- NEEDED: A named native Arabic reviewer for every prepared string and the human-labelled language sets.
- WHY: Automated judges do not approve Arabic, and unreviewed strings cannot be presented.
- DONE SO FAR: The owner is the fallback reviewer; all Arabic proposals remain pending native review.
- OPTIONS: **Recommendation:** appoint an independent native reviewer; otherwise the owner must perform and record the full review.
- NEEDED BY: slice S3 labels, slice S8 lexicons, slice S10 final gate; OI-15.

## OI-10 — PostgreSQL on the build machine

- ID: OI-10
- TYPE: OPEN
- NEEDED: Choose and prove a native Ubuntu service or Docker Desktop with working WSL integration.
- WHY: Start-up, stage recovery and local database tests need one reliable path.
- DONE SO FAR: Preflight probes the database named by `EII_DATABASE_URL` and selects the embedded store with a warning when PostgreSQL does not answer (task S0-T08). `infra/compose.yaml` defines this project's Compose service under project `eii-poc` on `127.0.0.1:55440`; the lead ran the live probe tests against it. The native-option setup script is not built in version 1. The later slice that loads a release owns its continuous-integration database service.
- OPTIONS: **Recommendation:** prefer the native service on stage after the owner's one-time setup; retain Compose for CI and portable deployment.
- NEEDED BY: slices S0 and S1; slice S11 rehearsals.

## OI-11 — Privacy thresholds

- ID: OI-11
- TYPE: MOVED (was OPEN)
- NEEDED: Data owners to set real privacy thresholds before any real-data pilot.
- WHY: Sets A and B are proposals measured only on synthetic data, not approved production rules.
- DONE SO FAR: Both parameter sets, stable treatment and attack requirements are specified. Both are evaluated inside the custodian plane, but exactly one selected set's protected tables are exported in a release. A lead ruling of 2026-11-11 accepts the rewritten privacy document as the disclosure-control reference. A lead ruling of 2026-11-11 sets the demonstrator default `export_parameter_set` to `A` (open item OI-35). A lead ruling of 2026-11-11 defines `window_key` as the SHA-256 of canonical JSON holding the protected `period` and the four name-ordered `{name, sha256}` pairs for `business_register.v1`, `employment.v1`, `residence.v1` and `wages.v1`, using each feed's manifest `feed_sha256`; nothing else enters it. Continuous integration checks the register alone and allows one `protected_sha256` per `window_key` and one `window_key` per `world_seed`; for a frozen release, the installed application's register is the allow-list and `freeze.json` must say complete. No signed receipt file is added. A lead ruling of 2026-11-11 limits exact sums to one additive family. Real thresholds remain for data owners, so this item stays open.
- OPTIONS: **Recommendation:** retain both for custodian-plane evaluation and export only the selected set for the demonstrator; custodians supply and hold real values for a pilot. Never tune a rule to make an area look finer.
- NEEDED BY: slice S5; any real-data pilot.
- MOVED: 2026-11-12, by the owner's note of that day: a real-deployment item, now in [docs/17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md), section "Items moved from OPEN_ITEMS.md". Version 1 keeps the documented default: sets A and B evaluated inside the custodian plane, set A exported.

## OI-12 — Graph server

- ID: OI-12
- TYPE: OPEN
- NEEDED: Owner confirmation that the graph server remains deferred, unless new evidence justifies L5.
- WHY: Version 1 needs graph content, not another serving engine.
- DONE SO FAR: Node and edge tables are the contract; L5 is deferred.
- OPTIONS: **Recommendation:** defer until a lawful relationship feed needs paths deeper than four steps. The owner may overrule by decision record.
- NEEDED BY: After slice S11, backlog item L5; no version 1 blocker.

## OI-13 — Repository protections

- ID: OI-13
- TYPE: CLOSED (was OPEN)
- NEEDED: Enable secret scanning, push protection and branch protection under the owner's standing permission.
- WHY: Public-repository safety needs platform controls as well as local scans.
- DONE SO FAR: The requirement is assigned to slice S0; local documentation and identifier checks exist.
- OPTIONS: **Recommendation:** enable all three and record the settings evidence; do not weaken them to make CI pass.
- NEEDED BY: slice S0.
- CLOSED: 2026-11-13, by task S0-T14: secret scanning and push protection are enabled, and the ruleset `main-protection` protects the base branch (pull requests only, the six checks of S0-T07 required on an up-to-date head, no bypass, no deletion, no forced push). Each setting was read back after its change; the calls and the service's answers are the entries of S0-T14 in [PROGRESS.md](PROGRESS.md). One default of the service outside the owner's table is recorded as OI-114.

## OI-14 — Approved typed-decision route

- ID: OI-14
- TYPE: OPEN
- NEEDED: An approved provider route before any run-time gateway use or real question.
- WHY: The current independent route stores submitted text and is not cleared for visitor text.
- DONE SO FAR: Default is no run-time use; only cleared offline data classes are allowed.
- OPTIONS: **Recommendation:** remain offline with provider `none`. Consider an official route with a data agreement, a local model, or the main vendor's small model through the same contract only by a new decision record.
- NEEDED BY: Any proposed run-time use after version 1.

## OI-15 — Human-labelled qualification sets

- ID: OI-15
- TYPE: OPEN
- NEEDED: Named people to label fresh qualification data and re-derive thresholds for each decision class.
- WHY: Existing labels and the strongest baseline come from one model family and are not human ground truth.
- DONE SO FAR: The initial set, blind labels, results and caveats are preserved; the default is 200 owner/native-reviewer-labelled cases before external claims.
- OPTIONS: **Recommendation:** use the owner or native reviewer with independent spot-checking; make no external accuracy claim before this is complete.
- NEEDED BY: slice S1 requalification; `string_parity` admission; any changed model, rubric, language or route.

## OI-16 — Activity-mapping sign-off

- ID: OI-16
- TYPE: OPEN
- NEEDED: Name who signs activity mappings and decide whether confident long-tail matches may be batch-signed.
- WHY: No mapping may enter a release on model output alone.
- DONE SO FAR: Default is individual review by the owner's delegate; the proposed batch audit is 30 random rows per batch with zero errors.
- OPTIONS: **Recommendation:** review every code individually. Allow batches only by owner-approved audit rule with named sign-off.
- NEEDED BY: slice S2 activity spine.
- UPDATE: 2026-11-15, by the ledger of merge train B5 (task S2-T04): the review files, the queue and the guards are built and approved; no person is named and no mapping is admitted. On the real public cache the spine holds 4,901 codes, 243 of them in the mandatory queue. The review itself is OI-203. Still needed: the name of the person who signs and the answer on batches.

## OI-17 — Gateway measurement panel

- ID: OI-17
- TYPE: OPEN
- NEEDED: Owner decision on whether a measurement panel ever appears in the Proof room.
- WHY: Scores could be mistaken for calibrated confidence or product evidence.
- DONE SO FAR: Default is no panel; only the activity-spine lineage line is shown.
- OPTIONS: **Recommendation:** keep no panel and show only the lineage line with human sign-off.
- NEEDED BY: slice S10 Proof room.

## OI-18 — Gateway token cap and key rotation

- ID: OI-18
- TYPE: CLOSED (was OPEN)
- NEEDED: Owner confirmation of the project token cap and a key rotation date, and of whether the gateway's provider key may be used during the build: the owner's note of 2026-11-12 keeps the API keys of the uncommitted `.env` file for go-live and does not name this key ([decision 0018](docs/decisions/0018-priorities-and-amendments-to-decision-0015.md) item 12).
- WHY: Offline provider use still needs a hard cost limit and credential hygiene.
- DONE SO FAR: Default cap is 5 million tokens in total; no agent may purchase, upgrade or renew.
- OPTIONS: **Recommendation:** confirm or tighten the default and record rotation before provider use; agents never change the subscription. No keyed provider run is made before the owner answers.
- NEEDED BY: slice S1 gateway qualification and every later provider run.
- CLOSED: 2026-11-13, by the owner's standing answer of that day: the gateway's provider key may be used for any run the plan calls for, on public or synthetic inputs only, from the lead's own shell and never through a worker tool, a test or CI; the caps are 5 million tokens for one run and 20 million for the build, and what each run used is logged; the key is rotated before go-live and at once if it is ever exposed; no agent purchases, upgrades or renews. The keyed requalification of 2026-11-13 made 340 calls and used 147,969 tokens ([evals/typed_decisions/README.md](evals/typed_decisions/README.md), section "Keyed run of 2026-11-13"). The rule that nothing a user types live goes to the provider stays as [decision 0014](docs/decisions/0014-typed-decision-gateway.md) has it; OI-15 stays open.

## OI-19 — Independent documentation review and corrections

- ID: OI-19
- TYPE: PENDING
- NEEDED: The two confirmations that remain after the review of 2026-11-11 (OI-37 and OI-38), and the continuous-integration run of the first commit recorded in [PROGRESS.md](PROGRESS.md).
- WHY: Some parallel drafts predate the current gateway placement, release identity, no-prose rule, calculation layer, activity-code distribution, staffing cut-off, command list, sandbox prohibition on fallback, identifier formats, customs precision, reliability vocabulary and interface test matrix.
- DONE SO FAR: Models of other makers reviewed every document on 2026-11-11; every first verdict was REJECTED and the findings were corrected, as [PROGRESS.md](PROGRESS.md) records with counts and makers. A final read-through by two makers returned 23 more findings, all applied. The documentation check passes. The continuous-integration run of the first commit is recorded in [PROGRESS.md](PROGRESS.md) since 2026-11-11.
- OPTIONS: **Recommendation:** close OI-38 at the slice S0 gate review and OI-37 before slice S5; do not copy a statement into code without reading the corrected document.
- NEEDED BY: Before the first build task and public hand-off.

## OI-20 — Playbook activity list

- ID: OI-20
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of the activities behind the three playbooks and their public cost tables and customs baskets.
- WHY: The master design names the restaurant flagship and other playbook activities without enumerating them.
- DONE SO FAR: The public-data draft assumes ISIC 5610 restaurants, 5630 beverage serving and 5510 short-term accommodation because one survey family covers them.
- OPTIONS: **Recommendation:** adopt those three for version 1 unless the owner records another list and equivalent verified public sources.
- NEEDED BY: slice S2 baskets; slice S7 costs and suppliers.

## OI-21 — Public-source metadata and method settings

- ID: OI-21
- TYPE: OPEN
- NEEDED: Verify Arabic ISIC title availability, the population year behind licence rates, customs valuation basis, the exact HTTPS Overture endpoint, all bulk months, the unrecorded co-location settings and any hotel guest series.
- WHY: These details affect labels, regression tests, calculations and whether parameters are anchored or assumed.
- DONE SO FAR: The registry marks each unknown; no value has been guessed in this file. A lead ruling of 2026-11-11 adds to the slice S2 gate that regression values the method cards could not pin are produced, checked against the source and written into the cards, and adds to the slice S7 gate that no regression value is left unpinned. The values themselves stay open until that check.
- OPTIONS: **Recommendation:** verify and cite each in slices S2 and S7, or mark it not measured and retain the stated fallback.
- NEEDED BY: slice S2 public pack; slice S4 mobility calibration; slice S7 methods.

## OI-22 — Technical spike and asset proofs

- ID: OI-22
- TYPE: OPEN
- NEEDED: Prove exact dependency pins and retreats, sandbox mounts and extension paths, speed-factor routing, text parity, map textures and watermark, Arabic glyphs, tabular figures, pixel-ratio cap, and remaining asset licences.
- WHY: These are uncertain joints, not established implementation facts.
- DONE SO FAR: Candidate mechanisms and named spike tests are documented. Task S1-T03 proved speed-factor routing on a synthetic road extract: the routing engine in process, one set of tiles for each distinct hourly factor, the drive area changing with the hour (OI-120). Task S1-T01 proved the Arabic glyph route and the label order on a synthetic page: five invented names drawn from local font files through the style's font faces, one hexagon under the first label layer. The other proofs named above are not proved by that spike.
- OPTIONS: **Recommendation:** test each at slices S0 and S1 and record decisions. No fallback is permitted for sandbox enforcement, store parity or security checks.
- NEEDED BY: slices S0 and S1 before dependent interface and release work.

## OI-23 — Synthetic-world validation inputs

- ID: OI-23
- TYPE: OPEN
- NEEDED: Decide whether transport-survey parameters may be used with consent, nominate the two long-term resident reviewers, confirm the hotel series, and align pay eligibility and window averaging across documents.
- WHY: Calibration, hold-outs and conformance must use one reviewed rule set rather than convenience choices.
- DONE SO FAR: Defaults are no restricted survey figures, owner nominations before slice S4, assumed hotel occupancy until sourced, and documented draft eligibility rules.
- OPTIONS: **Recommendation:** keep conservative defaults until evidence and reviewers exist; reconcile differences by decision record before the full world build.
- NEEDED BY: slice S4 world and validation scorecard.
- UPDATE: 2026-11-14, by [decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md): the consent question is replaced: transport-survey summaries readable as a visitor are used in version 1 whatever their reuse terms, their terms recorded in the publisher's own words with the date read in document 04 and any permission needed for real use listed in document 17; what stays open is the mapping of published parameters to the manifest entries (document 05, Q1).


## OI-24 — Privacy-audit scope

- ID: OI-24
- TYPE: OPEN
- NEEDED: Select and version the enumerated public totals used by the attacker-view audit and decide whether an independent human attacker session precedes a real-data pilot.
- WHY: Automated properties need realistic external attack coverage and correctly scoped public complements.
- DONE SO FAR: A lead ruling of 2026-11-11 decides the acceptance model: one model, every published leaf fixed to its untreated aggregate, knowledge fixtures checked against sealed truth before use, published-means-passed constraints, one solve per target class, and a time budget set from a measured run at the start of slice S5. What the layout tells about a failed population is not in that model; the typed attack suite holds one attack per layout signal. The audit is evidence under a stated attacker, not a proof. A lead ruling of 2026-11-11 pins `artefacts/attacker_view_public_totals.json` (PRV-115), and the audit configuration is `artefacts/attacker_view_audit.json`. A lead ruling of 2026-11-11 closes the count indicators that may be enabled: `residents` (`persons`), `households` (`households`), `establishments` (`establishments`) and `employees` (`persons`). A lead ruling of 2026-11-11 requires the inventory to equal the source registry plus every Public-table row. Which of those rows a release marks enabled is still selected at slice S5. Cross-month differencing and adjacent-month cohort attacks are version-1 work inside the one protected window; complement fixtures and mover attacks across two windows are deployment hardening in docs/17 section 3. Whether an independent human attacker session precedes a real-data pilot is still open.
- OPTIONS: **Recommendation:** derive the list from the reviewed public registry in slice S5 and require an independent human attack before any real-data pilot.
- NEEDED BY: slice S5; real-data pilot gate.
- MOVED PART: 2026-11-12, by the owner's note of that day: whether an independent human attacker session precedes a real-data pilot is a real-deployment item, now in [docs/17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md), section "Items moved from OPEN_ITEMS.md". The selection of the public totals for the attacker-view audit stays here, for slice S5.

## OI-25 — Interface and test-matrix alignment

- ID: OI-25
- TYPE: ASSUMPTION
- NEEDED: Align visual-test viewports, Plan rail placement, requested-area styling, pack language and layout, light-theme coverage, metadata numeral handling and moving-dash proofs.
- WHY: The design, front-end and testing drafts do not yet describe every one of these in the same way.
- DONE SO FAR: Design direction supplies proposed defaults and flags the conflicts; no interface exists to test.
- OPTIONS: **Recommendation:** let design direction own appearance, front end own implementation, and testing pin one matrix; never weaken the Fact chip or Arabic review rules.
- NEEDED BY: slice S1 spike; slice S3 visual gates; slice S10 pack and story.

## OI-26 — Later deployment platform

- ID: OI-26
- TYPE: MOVED (was OPEN)
- NEEDED: The custodian to confirm its database platform, approved region, data-residency terms and operating environment.
- WHY: Public provider offerings do not prove what a custodian runs or permits.
- DONE SO FAR: Available managed offerings were researched; no fit is claimed.
- OPTIONS: **Recommendation:** make no deployment-fit statement until written custodian confirmation; keep the build plane inside that environment.
- NEEDED BY: Later deployment only, not the local version 1 demonstrator.
- MOVED: 2026-11-12, by the owner's note of that day: a real-deployment item, now in [docs/17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md), section "Items moved from OPEN_ITEMS.md". Version 1 makes no deployment-fit statement, the documented default.

## OI-27 — Company-seat notice and decision scope

- ID: OI-27
- TYPE: CLOSED (was ASSUMPTION)
- NEEDED: Owner approval of the company-seat recording notice and confirmation that cross-country entry comparison and serving the region stay outside the current backlog.
- WHY: The project brief classifies these points without a master owner decision.
- DONE SO FAR: Draft wording discloses aggregate oversight recording; those two wider decisions are currently outside version 1 and the ordered backlog.
- OPTIONS: **Recommendation:** keep the disclosure and limited scope unless the owner adds work by decision record.
- NEEDED BY: slice S3 company interface; backlog review after slice S11.
- CLOSED: 2026-11-12, by the owner's decisions of that day, recorded in [decision 0016](docs/decisions/0016-version-1-covers-the-whole-initiative.md): serving the region (journey D7) is in version 1; a cross-country entry comparison stays out of version 1. The company-seat recording notice keeps its draft wording, the documented default.
- UPDATE: 2026-11-13, by [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 15: the oversight seat and its roll-up leave version 1, so the notice no longer discloses oversight recording. The company seat states that its questions are recorded in the internal question log, which no screen shows ([01_PROJECT_BRIEF.md](docs/01_PROJECT_BRIEF.md), section "Open questions and assumptions", ASSUMPTION 4).

## OI-28 — Pilot request and lawful real-data path

- ID: OI-28
- TYPE: OPEN
- NEEDED: The owner to complete feed scope, custodians, purpose, period, operator, environment, legal basis, pass criteria and kill criteria with named judges.
- WHY: The demonstration ends with a specific request, and no real feed may be used before that path is approved.
- DONE SO FAR: Only a template exists; all fields require owner completion.
- OPTIONS: **Recommendation:** complete and sign the request before the session; until then no real custodian data and no pilot are implied.
- NEEDED BY: slice S11 runbook preparation and any subsequent pilot.

## OI-29 — Flagship building and selection thresholds

- ID: OI-29
- TYPE: ASSUMPTION
- NEEDED: Verify the candidate buildings and have the owner choose one that passes the documented public-place and area checks.
- WHY: The flagship must be supported by real public places data, not selected for appearance alone.
- DONE SO FAR: Candidate checks are specified; the proposed minimums are eight verified restaurants within a five-minute walk and two verified Italian restaurants within a ten-minute walk. Final confirmation of the flagship pin and default cut-offs waits for the slice S5 survival report.
- OPTIONS: **Recommendation:** apply those minimums and let the owner choose among passing candidates; if none passes, add candidates or change selection thresholds only by decision record. Never tune a privacy rule to make the flagship area look finer.
- NEEDED BY: slice S2 candidate selection; slice S5 final pin and default cut-off confirmation.

## OI-30 — Live-model operating choices

- ID: OI-30
- TYPE: OPEN
- NEEDED: After measurement, the owner to decide fast mode and whether any separately evaluated server-side fallback model may be enabled.
- WHY: These choices affect latency, cost and which provider content can enter an answer; neither is justified before evidence exists.
- DONE SO FAR: Fast mode is off and server-side fallback is disabled; refusal and failure select the template writer. A lead ruling of 2026-11-11 replaces the earlier first-text target: evidence on screen within 2 s; the checked brief within 6 s when no live model is called (template writer or recorded provider), and within 20 s when a live model composes it. The brief is buffered until the accounting gate has passed. Fast mode remains an owner decision, so this item stays open.
- OPTIONS: **Recommendation:** keep both off. Reconsider only after cost, latency and the full evaluation harness support the exact proposed model and settings.
- NEEDED BY: go-live, after OI-01 is closed by the owner's decision (decision 0018 item 12); during the build, slice S8 included, only the template writer and the recorded provider run; any later provider change.

## OI-31 — Sealed-scenario writer and key holder

- ID: OI-31
- TYPE: OPEN
- NEEDED: The owner to name the independent reviewer who writes each sealed scenario and confirm that the owner holds the decryption key.
- WHY: The builder must not see the planted truths before the build, and the reveal needs a controlled key holder.
- DONE SO FAR: The default assigns scenario writing to an independent reviewer from a different maker and encryption to the owner's public key; no individual assignment or key-custody evidence is recorded.
- OPTIONS: **Recommendation:** have that reviewer write the scenarios for W0, W1 and W2; the owner holds the key and decrypts only to the documented temporary in-memory path, while the builder never sees plaintext.
- NEEDED BY: slice S4 scenario commitments and build; slice S10 sealed reveal.

## OI-32 — Residents for simulated-day face validity

- ID: OI-32
- TYPE: OPEN
- NEEDED: The owner to nominate the two long-term residents who review the four dial situations for face validity.
- WHY: The H5 review needs two people with relevant lived experience; a model or the builder cannot substitute for them.
- DONE SO FAR: The default is owner nomination before slice S4; the review, comments and resulting changes have not been recorded.
- OPTIONS: **Recommendation:** nominate both reviewers before the scorecard run and record their comments and changes without putting personal identities in the public pack. Their review supports face validity, not a claim that the simulation is validated.
- NEEDED BY: slice S4 world validation scorecard.

## OI-33 — Numeric scenario entry on the presenter console

- ID: OI-33
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that the presenter console may carry numeric scenario entry.
- WHY: The wall has no keyboard, and scenario values must be visibly typed user inputs rather than model-originated numbers.
- DONE SO FAR: Default is yes. The presenter console carries Scenario inputs for the break-even method, and the server calculates from those typed values. [Decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 9 and 10 extend the closed list of typed scenario inputs for the catchment-share scenario (card C34) and the revenue range of the user's outlet (card C35): the attractiveness that the user sets for the user's outlet against the competitors as a group or by competitor category, the capture rate, and the editable assumptions of the two cards, beside the average bill that the break-even calculator already takes. The cards fix each input, its range and its default (S7-T14, S7-T15).
- OPTIONS: **Recommendation:** permit numeric entry only in the presenter's Scenario inputs control, limited to the typed scenario inputs of the closed list: the six documented break-even method inputs and the inputs that cards C34 and C35 add; keep the browser and model from calculating or inventing values.
- NEEDED BY: slice S7 break-even method and scenario cards (S7-T14, S7-T15); slice S10 presenter controls and guided story.

## OI-34 — Scope of typed-decision authorisation

- ID: OI-34
- TYPE: OPEN
- NEEDED: The owner to confirm the recorded scope of the current typed-decision authorisation and to approve any later change explicitly.
- WHY: Route approval, permitted data classes, decision classes and permitted effects are separate boundaries; none may be inferred from another.
- DONE SO FAR: The current route is limited to offline use with `public`, `synthetic`, scanned `project_text` and `team_question` inputs, the five closed decision classes and their documented human-review effects. Run-time use remains disabled.
- OPTIONS: **Recommendation:** confirm exactly that closed scope and keep provider `none` as the default. Any new data class, decision class, route, run-time use or effect needs a new owner decision and, where material, a decision record.
- NEEDED BY: slice S1 gateway qualification and every later provider run; any proposed run-time use remains subject to OI-14.

## OI-35 — Exported privacy parameter set

- ID: OI-35
- TYPE: OPEN
- NEEDED: The owner or a data owner to confirm which parameter set is exported.
- WHY: Differently ruled layouts of one window can be differenced, and each export multiplies the routes an auditor must check, so exactly one set may leave the build machine (PRV-120). A lead ruling of 2026-11-11 sets the default. A lead ruling of 2026-11-11 does not reopen the choice of set.
- DONE SO FAR: A lead ruling of 2026-11-11 sets the default `export_parameter_set` to `A`, fixed in the rules configuration at the slice S1 gate, before any world is built; version 1 uses rounded estimated presence counts and flows without `presence_scale` or `flow_scale` (PRV-59, decision 0016). A lead ruling of 2026-11-11 writes that fix into the slice S1 gate. A lead ruling of 2026-11-11 defines `window_key` as the SHA-256 of canonical JSON holding the protected `period` and the four name-ordered `{name, sha256}` pairs for `business_register.v1`, `employment.v1`, `residence.v1` and `wages.v1`, using each feed's manifest `feed_sha256`; nothing else enters it. The register shipped inside an installed application is the allow-list for a frozen release, and `freeze.json` must say complete. The owner or a data owner may overrule the default set.
- OPTIONS: **Recommendation:** export set A unless the owner or a data owner records another choice before the slice S1 gate. Do not export a second treatment of the same window.
- NEEDED BY: the slice S1 gate, before the first world build.
- UPDATE: 2026-11-14: the rules configuration of task S1-T09 records the default exported set A; the owner or a data owner may still overrule it before the slice S1 gate.

## OI-36 — Layout signals outside the audit acceptance model

- ID: OI-36
- TYPE: MOVED (was OPEN)
- NEEDED: Before any real-data pilot, either model the disclosure-control failure branches, with predicates that separate what a rule publishes by design from what it leaks, or run an attack against every released instance of each layout signal.
- WHY: Layout signals are outside the acceptance model of the audit. Two independent reviewers object that one typed attack per kind of signal can miss a disclosure at another instance.
- DONE SO FAR: A lead ruling of 2026-11-11 keeps layout signals outside the acceptance model for version 1 (section 17 of the privacy document). The limit is stated, and the typed attack suite covers at least one merged band, category pooled into `other`, merged sibling set, withheld remainder and released reason code.
- OPTIONS: **Recommendation:** retain that ruling for the synthetic demonstration and state the limit. Before a real-data pilot, choose and complete one of the two needed routes; do not call the current audit a general proof.
- NEEDED BY: Before any real-data pilot.
- MOVED: 2026-11-12, by the owner's note of that day: a real-deployment item, now in [docs/17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md), section "Items moved from OPEN_ITEMS.md". Version 1 keeps the documented default: layout signals stay outside the acceptance model, the limit is stated and the typed attack suite covers each kind of layout signal.

## OI-37 — Independent review of the last privacy corrections

- ID: OI-37
- TYPE: PENDING
- NEEDED: A maker other than the one that last edited [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md) to review the lead's last ten corrections (made on 2026-11-11 after the second confirmation review) and record the review in [PROGRESS.md](PROGRESS.md).
- WHY: The privacy document was reviewed four times by three makers, but its last ten corrections have not been reviewed by another maker.
- DONE SO FAR: The lead applied the ten corrections. No independent review of that final correction set is recorded.
- OPTIONS: **Recommendation:** do not start slice S5 until the different-maker review is complete and recorded.
- NEEDED BY: Before slice S5 starts.

## OI-38 — Confirmation of the corrections made after the final read-through

- ID: OI-38
- TYPE: PENDING
- NEEDED: A maker other than the one that applied them to confirm that the 23 findings of the final read-through of 2026-11-11 are resolved in the pack, and to record the verdict in [PROGRESS.md](PROGRESS.md).
- WHY: Two makers read the whole pack and both returned REJECTED with local defects. The corrections were applied the same day and have not been read by another maker.
- DONE SO FAR: All 23 findings were applied; the lead changed one remedy that could not be built (the run-time outbound scanner holds no canary value; the comparison with canary pay values is a test). The documentation check passes.
- OPTIONS: **Recommendation:** make this confirmation part of the independent review of the slice S0 gate; the reviewer reads the corrected passages, not the whole pack again.
- NEEDED BY: slice S0 gate review.

## OI-39 — Shape of the Python workspace

- ID: OI-39
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm or replace two assumptions: the shape of the Python workspace, and the two dependency edges `eii-custodian -> eii-core` and `eii-product -> eii-core`, declared before any shared code exists.
- WHY: The pack pins Python 3.14 managed with `uv` as one workspace of `core`, `custodian` and `product` (docs/02_ARCHITECTURE.md, section "Technology stack", row "Python and packaging", and section "Repository layout, commands and configuration") but does not say how that Python request is written in the workspace metadata and in `.python-version`. The documents read for this task (docs/02_ARCHITECTURE.md sections 7 and 8, docs/08_BACKEND.md section 2, docs/12_TESTING_AND_QUALITY.md TST-60) do not describe the workspace root, the package version or where the metadata tests live. The pack requires code shared by the two Python planes to live only in `core/` (ARC-01, docs/02_ARCHITECTURE.md) and forbids every other edge (ARC-06, docs/02_ARCHITECTURE.md; BE-01 to BE-03, docs/08_BACKEND.md); this permits, but does not require, the two edges to `eii-core` before any shared code exists.
- DONE SO FAR: A non-package root `eii-workspace` (`[tool.uv] package = false`, no dependencies, no build system) with the three members `core`, `custodian` and `product`; `gateway/` is not a member. Each member uses the `src` layout (docs/08_BACKEND.md, section "Package layout and the import boundary", itself an assumption), version `0.0.0` and `requires-python = ">=3.14"`; `.python-version` holds `3.14`. `eii-custodian` and `eii-product` each declare `dependencies = ["eii-core"]` with `eii-core = { workspace = true }` in `[tool.uv.sources]`; `eii-core` declares no dependency. No sub-module exists yet. The guard and its tests are three standard-library files under `scripts/tests/` (`workspace_guard.py`, `workspace_fields.py` and `test_workspace_metadata.py`) and the clean-environment tests a fourth. The two edges, and the absence of every other edge between the three packages, are proved by `uv run --locked python -m unittest discover -s scripts/tests -p 'test_*.py' -v` (test `test_real_workspace_passes`, rules `workspace-source`, `dependency-edge` and `lock`) and by `uv lock --check`.
- OPTIONS: **Recommendation:** keep; a version scheme is decided when the first release is built, and per-package tests move to pytest in a later task. Alternatives: declare no dependency until the first import of `eii_core` exists (the two `[tool.uv.sources]` tables and the guard's two expected lock edges are then removed in that change); make `gateway/` a fourth member; or use a root without a `[project]` table.
- NEEDED BY: slice S0 gate.

## OI-40 — uv version and build-backend bound

- ID: OI-40
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm, and an exact `uv` pin at task S0-T12.
- WHY: The pack says `uv` is pinned at slice S0 but gives no number (docs/02_ARCHITECTURE.md, section "Technology stack", row "Python and packaging"), and the preflight row for locked dependencies requires that nothing is downloaded (docs/13_DEPLOYMENT_AND_OPERATIONS.md, section "Prerequisites and how each is checked", row "Locked dependencies").
- DONE SO FAR: The build machine has uv 0.11.31. All three members declare `requires = ["uv_build>=0.11.31,<0.12"]`. Tests in scripts/tests/test_clean_environment.py check the lock and install the members with an empty cache and --offline, without a download. uv is pinned by task S0-T12: `required-version` in the root `pyproject.toml`, recorded in `pins.toml` (OI-54). That task re-checked the table and the child environment named below: the pin is 0.11.31, the version they were written for, and `scripts/check_versions.py` reads `required-version` from the file because uv ignores it under `UV_NO_CONFIG=1`. The metadata guard's table of dependency-bearing fields and the child environment of the clean-environment tests were written for uv 0.11.31; that child environment sets `UV_NO_CONFIG=1`, which also makes uv ignore settings written in a `pyproject.toml` `[tool.uv]` table, so a task that adds such a setting revisits it. The uv documentation on configuration files names a project-level `uv.toml`, which takes precedence over the `[tool.uv]` table of a `pyproject.toml` in the same folder; the metadata guard does not read such a file, the clean-environment tests switch it off with `UV_NO_CONFIG=1`, and task S0-T12 (version pins) is the place to forbid or scan it.
- OPTIONS: **Recommendation:** task S0-T12 pins uv to the version on the build machine, keeps the bound in step with it, and re-checks the table of dependency-bearing fields and the child environment whenever the pin changes. Alternative: raise the bound together with an upgrade of uv on the build machine, once the owner approves that upgrade.
- NEEDED BY: task S0-T12; confirmed at slice S1.

## OI-41 — Conventions of the web skeleton

- ID: OI-41
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of eleven conventions of `web/`, each one a choice the pack permits and does not require: (1) the empty folders of the section 3.1 layout are kept by empty `.gitkeep` files; (2) `web/scripts/` holds the checks beside the pinned layout; (3) files owned by other tasks are not created and, until their task creates them, are named as deferred by the layout check; (4) the shell is English, with `lang="en" dir="ltr"` on the root element, an empty `main` element, a `data:,` icon and only the working title as text; (5) the development server binds `127.0.0.1` with a strict port through the flags of the `dev` script, keeping Vite's default port, and `engines.node` is the range `>=22.12.0 <23`; (6) the scan rules: the scan of the built JavaScript allows four named hosts, and the host scan and the import-boundary check handle closed lists of forms, each with a stated "not handled" part; (7) the TypeScript compiler options in `tsconfig.json` (strict family flags, `ES2022`, `bundler` resolution, `react-jsx`, `types` empty, no emit) and the `build` script `tsc --noEmit && vite build`; (8) the checks are dependency-free Node scripts run as `check:*` and `test:checks`, tested with Node's built-in runner in `*.node-test.mjs` files; (9) the package metadata (`name` `eii-web`, `private`, version `0.0.0`, licence `UNLICENSED`) and the absence of an `.npmrc`; (10) the import-boundary check reads `src/`, `tests/`, `eslint-rules/` and `vite.config.ts`, which is wider than FE-07, whose words name `web/src` only, and does not read `scripts/`, and the layout check fails a second Vite configuration file name beside `vite.config.ts`; (11) code files under `web/` aim at no more than 500 lines, a house target that the pack does not state, so the larger check scripts and test files were split by theme into several files; by [decision 0018](docs/decisions/0018-priorities-and-amendments-to-decision-0015.md) item 14 the limit is a target, never a gate: a file a little over is fine and a size check only warns.
- WHY: The pack fixes the layout and the file names of `web/` (docs/10_FRONTEND.md, section "Folders"), Node 22 with npm (docs/02_ARCHITECTURE.md, section "Technology stack", row "Front end", and section "Repository layout, commands and configuration"), React 19.3.1 and Vite 8.3.x (docs/10_FRONTEND.md, section "Stack and pins"), the built front end served at `/` and `/assets/*` (docs/08_BACKEND.md, section "Endpoints"), no third-party host (FE-05, DES-24), the import-boundary check (FE-07 (docs/10_FRONTEND.md): it fails if `web/src` imports from outside `web/`) and the document language and direction set at the root (DES-143). It does not say how an empty folder is kept, does not list `scripts/` in the layout, gives no compiler options, no script names, no package metadata and no limit on the length of a code file, and names Vitest for front-end tests with tools pinned at slice S0 (docs/10_FRONTEND.md, section "Testing"; TST-14, docs/12_TESTING_AND_QUALITY.md). The product name is not cleared (OI-05) and language switching is slice S3 (FE-61). Node is given as "22 (22.12 or later ...)", a range, while FE-01 asks for exact versions of dependencies. React ships namespace and message URLs that are not requests.
- DONE SO FAR: 21 empty marker files (14 under `src/`, 6 under `tests/`, 1 `eslint-rules/`), proved by `npm run check:layout`. `eslint.config.js` and `REFERENCE_NOTES.md` were moved into the required list by tasks S0-T04 and S0-T13. The allowed hosts for built JavaScript are `www.w3.org`, `react.dev`, `reactjs.org` and `github.com`, taken from the contents of the React packages, applied to built JavaScript only; a host outside the list found in a real build is reported to the lead and never added by the builder. The compiler options are observed by `npm run build`. The shell files and the `dev` flags are proved by `npm run test:checks` and `npm run check:dev`; the `engines` key is required to be present and its value is not judged. On 2026-11-11 the owner decided that the lead assigns each slice S0 requirement that no task owned to the nearest task and records it; the lead then assigned the import-boundary check of FE-07 to S0-T03, FE-11 to S0-T04, and the confirmation of font weights and of the icon licence (DES-25, DES-45) to S0-T13. The exact Node patch and version files are S0-T12; the test runner choice for the front end is S0-T05.
- OPTIONS: **Recommendation:** keep these readings; the end-to-end test that blocks other origins (ARC-36) and the server Content Security Policy are the later guards. Alternative: a one-line `README.md` in each marker folder; a scanner that parses the built JavaScript; moving the check tests to Vitest when S0-T05 lands; reading `web/src` only in the import-boundary check.
- NEEDED BY: slice S0 gate.

## OI-42 — Web dependency versions taken from the registry

- ID: OI-42
- TYPE: ASSUMPTION
- NEEDED: Confirmation of the web pins at the slice S1 spike, and a decision on TypeScript 7 then. Owner confirmation that no `@types/node` is added.
- WHY: The pack pins React and React DOM at 19.3.1 and Vite at 8.3.x with 8.3.8 as the latest (docs/10_FRONTEND.md, section "Stack and pins"), and says `typescript` is "pinned at slice S0 (not covered by the research)" (docs/10_FRONTEND.md, section "Stack and pins", row "`typescript`"), so it gives no TypeScript number. It names neither the Vite React plugin nor the React type packages. FE-01 asks for exact versions.
- DONE SO FAR: `react` 19.3.1, `react-dom` 19.3.1 and `vite` 8.3.8 are pack pins to confirm at slice S1. ASSUMPTION, taken from the registry on 2026-11-11 with the commands recorded in the research notes of the task: `@vitejs/plugin-react` 6.3.0, `@types/react` 19.3.0, `@types/react-dom` 19.3.0 and `typescript` 6.0.3. TypeScript is held at 6.0.3, not 7.0.2, because the lint rules of S0-T04 need `typescript-eslint` 8.72.2, which declares the peer range `>=4.8.4 <6.1.0`, and TypeScript 7.0 ships no compiler API; 6.0.3 is the newest release inside that range. No required peer of the set is unmet. `@types/node` is not added because the shell uses no Node API and the registry has no such package for Node 22.22.3. No retreat pin is recorded for the front end.
- OPTIONS: **Recommendation:** keep, and re-evaluate TypeScript 7 at slice S1. Alternative: pin TypeScript 7.0.2 once a typescript-eslint release supports it.
- NEEDED BY: slice S1 spike.

## OI-43 — Fonts are not bundled in the skeleton

- ID: OI-43
- TYPE: ASSUMPTION
- NEEDED: Confirmation that the web skeleton bundles no font, and the choice of the font package for IBM Plex Sans and IBM Plex Sans Arabic.
- WHY: The pack fixes IBM Plex Sans and IBM Plex Sans Arabic, self-hosted as WOFF2 from pinned npm packages (docs/10_FRONTEND.md, section "Bilingual and right-to-left rules"), with the pin at slice S0 (docs/10_FRONTEND.md, section "Stack and pins", row "IBM Plex Sans, IBM Plex Sans Arabic"), and DES-24 requires the font files and licence text to be served by the application and no font fetched from a third-party host. FE-97 (licence text with every bundled font) is slice S3 and the tabular-figures check is slice S1. The pack does not name the npm package and does not say which task adds the files. The shell has no styled text.
- DONE SO FAR: The skeleton adds no font, no font declaration and no font package, and its host scan fails a URL with a scheme and two separators and a protocol-relative URL with a dotted host, so the scan fails the listed URL forms in the files it reads (see `web/README.md`). On 2026-11-11 the owner decided that the lead assigns each slice S0 requirement that no task owned to the nearest task and records it; the lead then assigned the import-boundary check of FE-07 to S0-T03, FE-11 to S0-T04, and the confirmation of font weights and of the icon licence (DES-25, DES-45) to S0-T13. Vendoring the font files with the licence text stays with slice S3 (FE-97). Registry facts for four candidate packages (`@fontsource/ibm-plex-sans` and `@fontsource/ibm-plex-sans-arabic` 5.3.0, `@ibm/plex-sans` and `@ibm/plex-sans-arabic` 1.1.0, all OFL-1.1) are in the research notes of the task. Task S1-T01 installs the two IBM Plex packages and two Noto packages, each at 5.3.0, and its spike page serves weight 400 of each with the four licence texts; the application shell still bundles no font (OI-118).
- OPTIONS: **Recommendation:** vendor at slice S3 with FE-97 after the S0-T13 confirmation. Alternative: add the font packages to the S0-T12 pins now.
- NEEDED BY: S0-T13 (confirmations); slice S3 (vendoring).

## OI-44 — Python lint, format and type-check tools

- ID: OI-44
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of the Python lint, format and type-check tools and settings.
- WHY: The pack requires lint, format and type checks (docs/12_TESTING_AND_QUALITY.md, section "The CI pipeline", row "Static"; docs/14_IMPLEMENTATION_PLAN.md, section "slice S0 — Foundation") but names no Python tool, rule set, strictness level or version.
- DONE SO FAR: `ruff` 0.17.4 (lint and format) and `mypy` 2.4.1 (strict mode) are declared with exact versions in the `dev` dependency group of the root `pyproject.toml`, which `uv run` installs by default, and are locked in `uv.lock`; the versions are the registry releases of 2026-11-05 and 2026-10-28, read on 2026-11-11. Ruff rule families: `E4`, `E7`, `F`, `B`, `I`, `UP`, `RUF` (explicit, because the official pages describe the default set inconsistently); `fix = false`; ruff's `target-version` is `py312` because the documentation workflow runs `scripts/check_docs.py` on Python 3.12 and the formatter would otherwise write syntax that Python 3.12 rejects, while mypy checks against the Python 3.14 the pack pins; Markdown files are excluded from the formatter, as the ruff page recommends. The checks cover `scripts/`, `core/src`, `custodian/src` and `product/src`; `evals/` and `gateway/` hold no Python file yet. No suppression comment, per-file ignore or weaker setting was added to make the code pass; the files that needed an annotation or a formatting change are listed in the pull request. Three places in the clean-environment tests of S0-T02 were adjusted: the shared sync command (one constant, used by its class set-up and its hostile-surroundings test) gained `--no-dev`, because the dev group cannot be downloaded offline; the stale-lock test prepares a lock without registry packages, because a lock with registry packages cannot be re-resolved offline; and the hostile-surroundings test's per-variable runs use a workspace copy whose root dependency-groups table is removed and whose lock is regenerated offline, because without that step offline sync tries to satisfy the dev group from the cache and the per-variable sub-test fails for that reason instead of the variable under test. Each of the three commands has planted violations in the three `scripts/tests/test_pychecks_*.py` test files. The suppression comments that S0-T02 left (one `noqa: E402`, five `type: ignore`; proposed item PO-S0-02 below) are judged by the new checks: a comment that ruff or mypy reports as unused is removed, one that the tool shows to be used stays, and the pull request lists the result. House style (a ruling of the lead, an ASSUMPTION, not stated by the pack): files aim at 500 lines or fewer, every function signature is annotated, public non-test functions are documented in the Google style, and no bare `except` is used. Mypy in strict mode enforces the annotations. File length and the other house-style points are targets, not gates: they never fail a commit, a test or a check, and no tool configured by this task enforces a file-length limit or docstrings. The pack states neither.
- OPTIONS: **Recommendation:** keep. Alternatives: `basedpyright` in strict mode instead of `mypy`; a wider ruff rule set later (for example the numeric-literal lint of SYN-02 in the generator slice).
- NEEDED BY: slice S0 gate.

## OI-45 — Web lint, format and type-check tools and the scope of FE-11

- ID: OI-45
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of the web lint, format and type-check tools, of the lint scope, and of the way FE-11 is enforced.
- WHY: The pack names ESLint, a flat configuration `eslint.config.js` and a folder `eslint-rules/` (docs/10_FRONTEND.md, section "Folders") and a custom rule in slice S3 (FE-39, docs/10_FRONTEND.md), and FE-11 (docs/10_FRONTEND.md) asks for a lint rule that forbids `fetch` and `EventSource` elsewhere than `src/api/`, and names no exception for tests or tool scripts. It names no formatter, no type-check command, no ESLint version and no rule preset.
- DONE SO FAR: The owner decided on 2026-11-11 that the lead assigns each slice S0 requirement that no task owned to the nearest task; the lead assigned FE-11 to S0-T04. `eslint` 10.14.0, `@eslint/js` 10.0.1, `typescript-eslint` 8.72.2 (untyped `recommended` preset), `eslint-plugin-react-hooks` 7.1.1, `globals` 17.14.0 and `prettier` 3.9.10 (check only) are exact development dependencies, taken from the registry on 2026-11-11; Prettier 3.10.0 was the latest release but was published on that day, so the previous release is pinned. FE-11 uses the built-in rule `no-restricted-globals` (no custom rule). ASSUMPTION put to the owner: the rule applies to every file ESLint lints under `web/` (the eight extensions `js`, `mjs`, `cjs`, `jsx`, `ts`, `mts`, `cts`, `tsx`; tests, `scripts/` and configuration files included) with the single exception `src/api/**`, because the pack states the requirement without an exception; the tested forms are listed in `web/scripts/tests/lint-fe11.node-test.mjs`. ESLint skips every other file type silently, so the list of extensions is part of the configuration. ESLint also reads `web/scripts/` (the check scripts of S0-T03 and their tests, with the JavaScript rule set), except the generated folders `dist/` and `node_modules/`; no rule is switched off for any folder, and one may be switched off only by the lead's decision, written in `eslint.config.js` with its reason and recorded here; Prettier reads everything except `dist/`, `package-lock.json` and Markdown. The write-mode commands `uv run --locked ruff format .` and `npm run format` are in rule 44. ESLint 10.14.0 needs Node `^22.13.0`, while `engines.node` of `web/package.json` allows `>=22.12.0 <23`; the exact Node pin is S0-T12. The numerals rule and the local `eii` rules are slice S3 and are not loaded yet.
- OPTIONS: **Recommendation:** keep. Alternative: typed linting after a second `tsconfig` covers tests and configuration files.
- NEEDED BY: slice S0 gate.

## OI-46 — Test tools, seeds and conventions of the test runner

- ID: OI-46
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of the test tools and of twelve conventions of `./eii test`, each a choice the pack permits and does not require: (1) the tools `pytest` 9.2.0, `hypothesis` 6.170.15 and `vitest` 5.1.0 at exact versions; (2) six suites, named `python-guards`, `python-core`, `python-custodian`, `python-product`, `web-checks`, `web-unit`, listed in one table in `scripts/run_tests.py`; (3) counts read from JUnit XML elements, from a small counting reporter for Node's runner and from the assertion results of Vitest's JSON file; (4) the default pytest selection `-m "not nightly"`, so that `postgres`, `live_model` and `sandbox` tests are selected; (5) a run fails when a suite reports no test, when any skipped or TODO test that the tool reports lacks a reason containing OI-01 or OI-10, when a pytest expected failure (`xfail`, which the JUnit file holds as a skipped item) lacks one, and when a tool's exit status disagrees with its counts; two Vitest forms are not exposed by its JSON reporter and so escape this rule, an `it.fails` or `test.fails` test whose body fails as expected (written as passed, with no marker) and a `describe.todo` without a body (omitted), and are left to review and lint, as is an unmarked OI-10 skip; (6) one seed per run, ten decimal digits from 1000000000 to 4294967295 (so that it never forms an exactly-eight or exactly-eleven digit run, which the identifier scan rejects), printed first, passed to pytest as `--hypothesis-seed`, to Python children as `PYTHONHASHSEED` and to Vitest as `--sequence.seed` with test shuffling on; a Hypothesis test with its own `derandomize=True` is the same in every run and is not changed by the seed (observed with 6.170.15); (7) every suite runs with `EII_DECISION_PROVIDER=none` and an allow-list environment from which any variable named `ANTHROPIC_API_KEY`, `JEV_PRO_API_KEY` or ending in `_KEY`, `_TOKEN` or `_SECRET` is absent, and no database variable is passed in this task (a task that gives `postgres` tests a database adds its names to the allow-list); (8) one Hypothesis profile `eii` restating the default example count (100) and deadline (200 ms), with no example database, and Hypothesis's own storage folder moved to a temporary folder; (9) pytest `strict = true`, `--import-mode=importlib` and `scripts/tests` on the pytest path, so that test modules which import a support module or a base test module of the same folder by name collect as they do under unittest; (10) the first version of `./eii test` runs neither a parity suite nor the preflight groups, and never exits 3; (11) a Vitest unit test needs no DOM library; (12) the limits of the runner, each chosen and not measured (the builder reports the real durations): time-outs of 3600 seconds for the guard suite, 1800 for the Node suite and 600 for each other suite; a minimum of one test for each suite; an output block of the last 200 lines with test names cut at 120 characters; no pytest cache and no bytecode written by children; result files written through each tool's own output option (`--junit-xml`, the counting reporter's destination, Vitest's `--outputFile.json`); a Python test that uses subtests counts once; a Node file that registers no test and a skipped Node `describe` each count as one skipped item; a Vitest file that fails without a failed test counts as one failed test; a module-level pytest skip counts as a skipped item and can never carry a standing reason; child output is decoded as UTF-8 with replacement; a time-out kills the child's process group, and an interrupt (Ctrl-C, KeyboardInterrupt) during a suite kills the child's process group, prints `FAIL interrupted` and makes `./eii test` exit 1; SIGTERM installs no handler, so the runner stops as the operating system stops it.
- WHY: The pack requires `./eii test` to run every pull-request-level suite that needs no network, print passed, failed and skipped counts per suite and exit non-zero on any failure or error (TST-15, docs/12_TESTING_AND_QUALITY.md), seeded randomness with the seed printed (TST-07), only two standing skips (TST-06), the markers `postgres`, `sandbox`, `nightly` and `live_model` (TST-16, itself an assumption), pytest for the packages (TST-10) and Vitest for the front end (TST-14), and says that pytest, Hypothesis, Vitest and Playwright are "Pinned at slice S0" with no retreat pin and no version number (docs/02_ARCHITECTURE.md, section "Technology stack", row "Tests") and that Hypothesis tests run in pull-request CI with a fixed seed passed as `--hypothesis-seed` (TST-27). It does not give the versions, the default marker selection, suite names, how counts are read, the form of a seed or how Vitest receives one. docs/13_DEPLOYMENT_AND_OPERATIONS.md, section "The `./eii` commands", row "`./eii test`", says `./eii test` includes parity on both engines and runs the preflight groups Tools and PostgreSQL, and its exit-code table, row "3", gives exit status 3 for a PostgreSQL that does not answer; the slice S0 gate (docs/14_IMPLEMENTATION_PLAN.md, section "slice S0 — Foundation") asks only that `./eii test` exits zero.
- DONE SO FAR: `scripts/run_tests.py` with two helper modules, `conftest.py`, the `[tool.pytest]` table, `web/vitest.config.ts`, `web/scripts/count-reporter.mjs`, one package test per Python package and one Vitest test; the versions are the registry releases of 2026-10-27, 2026-11-06 and 2026-11-02, read on 2026-11-12, and the tools were run in a scratch project before the plan was finished. A secret in a variable with another name than the covered ones (the two names and three suffixes) is kept out only by the allow-list. A skip reason cannot be tied to a marker, so OI-10 on an unmarked test is accepted by the rule and left to the reviewer; Vitest's JSON gives no reason, so any skipped or TODO Vitest test that it reports fails; the two forms that it does not report (a failing `it.fails` or `test.fails` test, written as passed, and a `describe.todo` without a body, omitted) pass silently and are left to review and lint. `evals/` holds no test yet and `gateway/` no code; each later suite (boundary, parity, conformance, API, harness) adds a row to the table when it exists. The fixed seed that TST-27 asks of pull-request CI is passed by S0-T07 as `./eii test --seed N`.
- OPTIONS: **Recommendation:** keep. Alternatives: select `-m "not nightly and not postgres and not live_model"` and run those markers in separate suites; read Node counts from the TAP trailer (documented as unstable) instead of the reporter; allow a longer seed form.
- NEEDED BY: slice S0 gate.

## OI-47 — The `eii` launcher is created with one command

- ID: OI-47
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that task S0-T05 creates the root launcher `eii` with the single command `test`, and that task S0-T09 later adds the other eleven commands and replaces the usage text.
- WHY: TASKS.md gives task S0-T09 the scope "root `eii` launcher and `scripts/commands/`" and the goal to create every pinned command entry point, while the goal of task S0-T05 is that `./eii test` runs the suites and its scope is test configuration, test bootstrap files and the `scripts/` test runner. The pack does not say which task creates the launcher first. docs/13_DEPLOYMENT_AND_OPERATIONS.md, section "The `./eii` commands", row "`./eii test`" and rows "1" and "2" of its exit-code table, give the command and the exit codes 1 and 2 that the launcher uses.
- DONE SO FAR: `eii` is a short POSIX shell script. Any word other than `test`, or none, prints one line and exits 2; a missing `uv` prints one `FAIL` line and exits 1; otherwise it runs the runner through `uv run --locked` and passes the runner's exit status on. Its behaviour is tested by `scripts/tests/test_launcher.py`, whose tests name no word that a later task pins as a command and pin the usage text only by its prefix `eii: usage error:`, so that adding the other eleven commands does not require editing them. Task S0-T09 owns the usage text for all twelve commands and the test that lists them. S0-T09 has added the twelve usage forms and the dispatch, and `scripts/tests/test_commands.py` checks those forms against the architecture table.
- OPTIONS: **Recommendation:** keep. Alternative: leave the launcher entirely to S0-T09 and run the runner as `uv run --locked python -I scripts/run_tests.py` until then.
- NEEDED BY: slice S0 gate.

## OI-48 — Component and browser test tools are not installed in slice S0

- ID: OI-48
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that task S0-T05 installs only the tools that an existing test uses, and that Playwright with Chromium, axe-core, React Testing Library and a DOM environment for Vitest are installed and pinned with the first test that needs them.
- WHY: The pack names Vitest with React Testing Library, Playwright with Chromium and axe-core as test tools "pinned at slice S0" (docs/10_FRONTEND.md, section "Testing" and section "Open questions and assumptions", item 8; docs/02_ARCHITECTURE.md, section "Technology stack", row "Tests", for Playwright), gives the unit, component, visual, end-to-end and audit suites to slice S3 (FE-92, docs/10_FRONTEND.md) and requires `./eii test` to run suites that need no network (TST-15, docs/12_TESTING_AND_QUALITY.md). TASKS.md gives pins to task S0-T12. Playwright needs a browser downloaded by its own install command, which uses the network; the pack does not say how that is reconciled with TST-15.
- DONE SO FAR: Only `vitest` is installed (OI-46). Registry versions read on 2026-11-12 for the later decision: `@playwright/test` 1.65.0, `@axe-core/playwright` 4.14.0, `@testing-library/react` 16.3.3, `@testing-library/dom` 10.4.2, `jsdom` 31.0.0 (Node `^22.22.2` or later), `happy-dom` 21.0.4. The one unit test renders `App` with `react-dom/server`, which needs none of them. Task S1-T01 installs `@playwright/test` 1.65.0 for the glyph spike and fetches its headless shell by `npm run spike:glyphs:install-browser` into `data/tools/playwright/`; `./eii test` downloads nothing and fails by name where the browser is missing. The accessibility package, the component-test library and a DOM environment are still not installed.
- OPTIONS: **Recommendation:** keep; the first component test (slice S3) installs a DOM environment and Testing Library at exact versions, and the first end-to-end test installs Playwright and fetches its browser in a separate, documented, network step before `./eii test`. Alternative: install and pin all four now, unused.
- NEEDED BY: slice S0 gate (the pin record of S0-T12) and slice S3.

## OI-50 — Home and runner of the import-boundary test

- ID: OI-50
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that the import-boundary test is a set of standard-library `unittest`-style modules under `scripts/tests/`, run by the unittest command of rule 44 and collected by the suite `python-guards` of `./eii test`, and that it may be split into several modules around a 500-line target that the pack does not state.
- WHY: The pack requires the test from slice S0 and says it runs in `./eii test` and in continuous integration (BE-04, docs/08_BACKEND.md). It lists `pytest` as the tool of the Boundary test class (docs/12_TESTING_AND_QUALITY.md, section "Test map by plane", row "Boundary") and names no file or folder for the boundary test; TASKS.md, task S0-T10, says only "boundary test module". The `./eii test` command and its suite `python-guards`, which runs pytest over `scripts/tests`, are the work of task S0-T05 (TASKS.md), which had merged before this item was entered.
- DONE SO FAR: The boundary test is a set of modules under `scripts/tests/`: four support modules `scripts/tests/import_boundary_*.py`, whose names do not match the discovery pattern `test_*.py`, and five test modules `scripts/tests/test_import_boundary_*.py`, which do. It is split around a target of about 500 lines per code file, which is house style and never a failure; the pack states no such limit, so this is an ASSUMPTION put to the owner. The test modules are `unittest.TestCase` classes and import no `pytest`; the suite `python-guards` collects them through the pytest configuration of S0-T05, and the unittest command of rule 44 runs them too. Proved by `test_tables_have_their_sizes` and `test_real_tree_static_passes` in `scripts/tests/test_import_boundary_real.py`, by the whole suite command of rule 44 and by `./eii test`.
- OPTIONS: **Recommendation:** keep. Alternatives: write the tests as plain `pytest` functions with fixtures, which would no longer run under the unittest command of rule 44; or join the nine files into one module if the owner prefers one module to a split made for a target the pack does not state.
- NEEDED BY: the owner, before the S0 gate.

## OI-51 — Dynamic imports that the boundary test cannot resolve

- ID: OI-51
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that a call of `importlib.import_module` or `__import__` whose target cannot be resolved statically from literal arguments is reported as a note and does not fail the boundary test, and that the forms listed under DONE SO FAR are not judged.
- WHY: The pack requires failure for "string arguments to `importlib.import_module`" (TST-60, docs/12_TESTING_AND_QUALITY.md; BE-04, docs/08_BACKEND.md) and for "a module name passed as a string" (ARC-06, docs/02_ARCHITECTURE.md). It says nothing about a name built at run time, and it does not enumerate the other ways a module can be loaded.
- DONE SO FAR: A call whose name is an absolute string literal fails when it names a forbidden module: for `import_module` also when `*args` or `**kwargs` follow the name; for `__import__` when the level is the literal integer 0, or is absent with no `*args` or `**kwargs` in the call. A call prints a `NOTE dynamic-import` line and never fails when the name is not a string literal (concatenation, f-string, variable, `*args`, `**kwargs`, no argument); when a relative name has no literal, non-empty package that `importlib.util.resolve_name` accepts; when `__import__` is given a name that starts with a dot; and when its level is not the literal integer 0 or cannot be read because `*args` or `**kwargs` could carry it. The direct and alias forms of `importlib.import_module`, `importlib.__import__` and `builtins.__import__` are judged. Not judged at all: a judged function reached by any other route (an assignment alias, `getattr`, an attribute of another module such as `pkgutil.importlib.import_module`, a `sys.modules` lookup, `importlib._bootstrap._gcd_import`, a lookup in `builtins.__dict__`, an alias of a module `__init__`); `exec`, `eval`, `compile`, `pkgutil.resolve_name` and assignment to `sys.modules`; loading code by file path (`importlib.util.spec_from_file_location`, `runpy`), `ctypes` and a Python subprocess; functions of other libraries that take a module name; function references such as `map(importlib.import_module, ...)`; a sourceless `.pyc` or an extension module, in a folder with or without `__init__.py` (the `.py` files of a folder without `__init__.py` are parsed); `.pyi` stubs; an environment name split across two literals. The fresh-interpreter test sees only what loads or requests a forbidden module while the packages are imported, and only the modules that `pkgutil.walk_packages` yields and what those import; a form inside a function that does not run at import time is seen by neither guard. `test_not_judged_forms_in_the_child` asserts the result for ten planted forms: `exec`, an assignment to `sys.modules`, `importlib.util.find_spec` (reported as an attempted import), `map(importlib.import_module, ...)` and a sourceless `.pyc` directly in a package are reported; `importlib.util.spec_from_file_location`, `runpy`, `ctypes`, a Python subprocess and a sourceless `.pyc` in a folder without `__init__.py` are reported by neither guard and are left to code review. The sandbox of task S0-T11 does not judge imports; it limits what generator code can read or open. For the other forms no committed test asserts what the fresh-interpreter test reports. Proved by `test_non_literal_dynamic_is_a_note`, `test_declared_not_judged_forms_pass`, `test_not_judged_forms_in_the_child` and `test_every_edge_every_mechanism` in `scripts/tests/test_import_boundary_forms.py`, and `test_fresh_every_edge_import_time` in `scripts/tests/test_import_boundary_fresh.py`.
- OPTIONS: **Recommendation:** keep, because a later slice may need a dynamic import inside its own package and failing it now would force the guard to be loosened. Alternative: fail every such call and allow named exceptions in a reviewed list.
- NEEDED BY: slice S0 gate.

## OI-52 — Environment names, the gateway edge and package metadata

- ID: OI-52
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm three narrow readings of the gateway rules in the boundary test, and to assign the vault requirements the boundary test leaves.
- WHY: The pack says nothing under `core/`, `custodian/` or `product/` imports `eii_gateway` or reads `EII_DECISION_PROVIDER` or `JEV_PRO_API_KEY` (ARC-81, docs/02_ARCHITECTURE.md; BE-102, docs/08_BACKEND.md; REV-38, docs/15_REVIEWER_CHECKLIST.md). It does not say how "reads" is tested. The folder `gateway/` holds a note only (task S0-T01), so no package named `eii_gateway` exists yet. TST-60 asks for package metadata tests of "forbidden dependency" (TST-60, docs/12_TESTING_AND_QUALITY.md) without naming the gateway. BE-05 (docs/08_BACKEND.md), SYN-68 (docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md) and PRV-02 (docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md) name the import-boundary test or the vault path, and no task of TASKS.md names them.
- DONE SO FAR: (1) Only the three package trees `core/src/eii_core`, `custodian/src/eii_custodian` and `product/src/eii_product` are read; other files under `core/`, `custodian/` and `product/` are not. The two names must not occur at all in any file of those trees, matched as exact, case-sensitive text in the bytes of every file except the `.pyc` files directly inside a folder named `__pycache__`; this is stricter than "reads" because comments, strings and longer names that contain a name also fail, while a name split into two literals or written with an escape is not caught. (2) The gateway edge is judged by the module name `eii_gateway`, in the same three trees. (3) A dependency on the gateway in a `pyproject.toml` is not judged: the metadata guard of S0-T02 judges the three plane names only. (4) The vault clauses of BE-05, SYN-68 and PRV-02 are not tested, including the path segment `vault` in module names. Proved by `test_environment_names` in `scripts/tests/test_import_boundary_files.py`, `test_every_edge_every_mechanism` in `scripts/tests/test_import_boundary_forms.py`, `test_fresh_every_edge_import_time` in `scripts/tests/test_import_boundary_fresh.py` and `test_metadata_guard_is_wired` in `scripts/tests/test_import_boundary_real.py`.
- OPTIONS: **Recommendation:** keep; the gateway slice revisits the layout of `gateway/` and the metadata table. Alternatives: judge only reads of the process environment (a closed table of forms, weaker); add the gateway name to the metadata guard (a change to its reviewed table, re-checked by S0-T12). For point 4 the owner names the task that takes BE-05, SYN-68 and PRV-02.
- NEEDED BY: slice S0 gate.

## OI-53 — What the fresh-interpreter test judges

- ID: OI-53
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm the scope and strictness of the fresh-interpreter test and of reading the working tree.
- WHY: The pack says to import `eii_product` in a fresh interpreter and fail if any `eii_custodian` module is loaded (ARC-06, docs/02_ARCHITECTURE.md) and that fresh-interpreter tests assert no forbidden module is loaded (TST-60, docs/12_TESTING_AND_QUALITY.md). ARC-06 names one fresh-interpreter case, importing `eii_product` and failing on any `eii_custodian` module; TST-60 says only "no forbidden module is loaded". Neither names the other packages, interpreter options or a way to find the packages. AGENTS.md rule 13 keeps "every folder that git ignores or does not track" off-limits for tests and allows only documented repository, cache and temporary paths.
- DONE SO FAR: Each of the three packages is imported in its own isolated child interpreter (`-I -S -B`, an environment built from an empty dictionary, the three working-tree source folders first on the path), together with every package and module under it that `pkgutil.walk_packages` yields and any module a walked module imports. It fails when a forbidden package (for `eii_product`: `eii_custodian` and `eii_gateway`) is loaded or only requested, or when any import fails. This is wider than the words of ARC-06. A symbolic link under a source tree, or in a folder above it, also fails. The child's path gets, after the source folders, the global package folders of the running interpreter (`site.getsitepackages()`), never the user folder, and a module that reads an environment variable when it is imported fails the test. The static guard reads every file under the three source trees as it is in the working tree, tracked or not, and the fresh-interpreter test imports (executes) the packages and modules it finds there, tracked or not; whether rule 13 allows this is put to the owner. Proved by the tests in `scripts/tests/test_import_boundary_fresh.py` and `scripts/tests/test_import_boundary_surroundings.py` whose names start `test_fresh_`, and by `test_symbolic_links_fail` in `scripts/tests/test_import_boundary_files.py`.
- OPTIONS: **Recommendation:** keep. Alternatives: test `eii_product` against `eii_custodian` only, as worded, and widen later; judge only the files that git lists (tracked, or untracked and not ignored) for the real tree.
- NEEDED BY: slice S0 gate.

## OI-54 — Pin record, version files and pins that no document gives

- ID: OI-54
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of the pin record, of the toolchain pins and of the versions taken from the registries; the slice S1 confirmation of every pin and retreat pin (S1-T08), which also writes the spike result.
- WHY: The pack pins Python 3.14 managed by `uv`, Node 22 (22.12 or later), React 19.3.1, Vite 8.3.x with 8.3.8, MapLibre GL JS 6.17.0, deck.gl 9.4.1, `pmtiles` 4.5.0, `@protomaps/basemaps` 5.7.2, `h3` and `h3-js` 4.5.0, `apache-arrow` 21.2.0, `pyvalhalla` 3.9.1, FastAPI 0.162.x, DuckDB 2.0.x, PostgreSQL 18 and PostGIS 3.6, and writes retreat pins for DuckDB, MapLibre, deck.gl and routing (docs/02_ARCHITECTURE.md, section "Technology stack"; docs/10_FRONTEND.md, section "Stack and pins"). It says exact pins are confirmed at the slice S1 spike (docs/02_ARCHITECTURE.md, section "Technology stack"; docs/10_FRONTEND.md, section "Stack and pins", and FE-03; rule 42) and also that they are "pinned in slice S0 and confirmed at the spike" (docs/13_DEPLOYMENT_AND_OPERATIONS.md, section "Prerequisites and how each is checked"). It gives no number for `uv`, npm, TypeScript, pytest, Hypothesis, Vitest, Playwright, axe-core, React Testing Library, the Plex font packages, the OpenAPI generator, the SQL parser, the Anthropic SDK, psycopg, NumPy, SciPy or NetworkX, and names lock files and `web/package.json` as places where pins are recorded (docs/02_ARCHITECTURE.md, section "Technology stack"; docs/10_FRONTEND.md, section "Stack and pins") but no single record of every pin with its retreat pin and label, and no format for the version list of the freeze bundle (docs/13_DEPLOYMENT_AND_OPERATIONS.md, section "Building, loading and freezing a release", row "Version list of every pinned package"). FE-03 (docs/10_FRONTEND.md) asks for the retreat pin and the spike result that chose between them before slice S3 starts. PLN-15 (docs/14_IMPLEMENTATION_PLAN.md) asks for a re-estimate after the slice S1 spike.
- DONE SO FAR: `pins.toml` at the repository root records 57 components (4 toolchains, 15 Python, 32 npm, 6 external names): 27 values taken from the pack and labelled "pack, confirm at slice S1", 30 labelled ASSUMPTION with their source (the registry or the build machine, read on 2026-11-12, or the task that chose them). A retreat pin is written only where the pack names one, with one exception: for bubblewrap the pack names as its retreat "An equivalent mount-namespace and network-namespace sandbox enforcing the same mounts and passing the same sentinel tests, recorded as a decision; otherwise the build fails" (docs/02_ARCHITECTURE.md, section "Technology stack", row "Sandbox"), and the record says "none recorded" for it because rule 12 of AGENTS.md says "No fallback is allowed for sandbox enforcement" (AGENTS.md rule 12 and the lead's ruling that bubblewrap is the only sandbox, put to the owner here); every other row for which the pack names no retreat pin says "none recorded". Libraries the product will use later are recorded and not installed. `.nvmrc` holds `22`, the root `pyproject.toml` gains `required-version = "==0.11.31"`, and `uv run --locked python scripts/check_versions.py` fails when a dependency named in a judged place of a manifest, a locked version of a recorded component, a version file, a version field, or the running Python, `uv`, Node or npm differs from the record, or when a manifest, lock or version file outside its closed set is among the files that git tracks or would track (the places it does not judge are in the docstring of `scripts/check_versions.py`), with a planted test for each of its seventeen rules. ASSUMPTIONS put to the owner: the file, its format and its place; `uv` at the exact version of the build machine, 0.11.31 (the newest release found on 2026-11-12 is 0.13.7; moving to it needs the three `uv_build` bounds of S0-T02, one in each member, changed in the same step); npm as the series 10.9.x that Node 22.22 bundles; the Node floor stays at the pack's 22.12.0 although the installed ESLint 10.14.0 declares `^22.13.0`, so Node 22.12 passes this check and is outside the engines that ESLint 10.14.0 declares (`^22.13.0`, read from the registry on 2026-11-12; a scratch run of ESLint 10.14.0 alone under Node 22.12.0 printed its findings and exited 1 for a finding and 0 for a clean file, and whether `npm run lint` fails there was not run); Node 22 reaches the end of its life on 2027-04-30 (the Node release schedule); the versions the pack does not give, taken from the registries; the label and `state` words; `psycopg` is LGPL-3.0-only by its registry entry, noted for the owner's licence review. A library for which the pack names no number and this task chose none (`uvicorn`, `pydantic`, `shapely`, `pyarrow`, `jsonschema`, `go-pmtiles`) has no row; a manifest that names one fails rule `manifest-unrecorded` until a task adds its row. DuckDB 2.0.x is recorded and not installed here; S0-T11, built after this task, adds it to a manifest and changes its row to installed. The check does not read which registry a lock names (the index URL of `uv.lock`, the `resolved` and `integrity` fields of the npm lock), so a changed index setting would pass; a `uv.toml`, an `.npmrc`, an `npm-shrinkwrap.json` or any manifest outside the closed set fails when git lists it. `required-version` is ignored by `uv` when `UV_NO_CONFIG=1` is set, as in the clean-environment tests of S0-T02, so the check reads the file itself. The documentation workflow still uses Python 3.12 (`.github/workflows/docs.yml`); TST-153 asks CI to use Python 3.14 managed by `uv` and Node 22, and S0-T07 writes the workflow that must install the pinned `uv`, read `.python-version` and `.nvmrc`, and run the check. This task cannot close FE-03 or PLN-15: FE-03 is a requirement labelled slice S1 (docs/10_FRONTEND.md), whose spike result only S1-T08 can write, and this task provides a retreat value for every row and the place `spike_result`, left as "not yet run"; PLN-15 is an effort re-estimate rule for after the slice S1 spike (docs/14_IMPLEMENTATION_PLAN.md), and this task changes no effort figure. Node is pinned as the series 22.x with the floor 22.12.0 (the pack's own series); the exact Node pin that OI-45 leaves to this task is therefore this series, and the floor question is the option below. Rule `unscanned` takes its candidate files from `git ls-files -z --cached --others --exclude-standard`, run in the repository root with the user's and the system's git configuration switched off, that is the files git tracks and the untracked files that no `.gitignore` file or `.git/info/exclude` line of the repository ignores; a file that git ignores and does not track is never listed or judged (AGENTS.md rule 13), no folder is walked, and the check needs `git` on the path and the root to be the top of a work tree.
- OPTIONS: **Recommendation:** keep the record and the `uv` pin as they are. Option for the Node floor: raise it to 22.13.0, the lower bound that the installed ESLint 10.14.0 declares, by exactly two edits: the `floor` field of the `node` row of `pins.toml` becomes `22.13.0`, and `engines.node` of `web/package.json` becomes `>=22.13.0 <23`; nothing else changes, because the check derives the expected string from the row. Alternatives: keep the pack's floor 22.12.0; pin `uv` 0.13.7 and change the three `uv_build` bounds in the same step.
- NEEDED BY: the Node floor and `uv` choices before S0-T07 writes the workflow; the rest at the slice S1 spike (S1-T08).

## OI-55 — SQL parser for the portability lint

- ID: OI-55
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of `sqlglot` 30.31.0 as the parser of the portability lint, or another choice.
- WHY: TST-43 (docs/12_TESTING_AND_QUALITY.md) says the parser is "chosen in slice S0"; BE-13 (docs/08_BACKEND.md) says "parser chosen at slice S0; a tokeniser over the allow-list is the fallback"; no parser is named. The lint must read queries for PostgreSQL 18 and DuckDB 2.0 that use the neutral placeholder `:name` and must reject extension functions and forbidden constructs (docs/08_BACKEND.md, section "The portable SQL subset").
- DONE SO FAR: Registry facts and runs of 2026-11-12 on Python 3.14.6. `sqlglot` 30.31.0 (MIT, pure Python, no run-time dependency) parsed PostgreSQL-with-PostGIS and DuckDB samples to a syntax tree with the placeholder, kept function names, ignored function names in comments and strings, and flagged `WITH RECURSIVE` and several statements; it is lenient across dialects (it accepted `QUALIFY` when reading as PostgreSQL), so the allow-list has to be applied to the tree and each query parsed under both dialects. `sqlparse` 0.6.1 (BSD) is a tokeniser that accepts invalid SQL. `pglast` 8.7 reads PostgreSQL only, is GPL-3.0-or-later and needs the placeholder rewritten. `sqloxide` 0.61.1 (MIT, compiled) is also lenient. DuckDB's own serialiser reads one engine and SELECT statements only. `sqlglot` is recorded in `pins.toml` as an ASSUMPTION, state recorded, first use S3-T01; it is not installed. The owner decided the method on 2026-11-11 and the lead assigned the requirement to this task.
- OPTIONS: **Recommendation:** `sqlglot`, exactly pinned, each query parsed under both dialects and both required to succeed. Alternatives: `pglast` with DuckDB's parser (authoritative for each engine; a GPL licence and a rewrite of the placeholder); the pack's fallback, a tokeniser over the allow-list (no dependency, no syntax tree).
- NEEDED BY: slice S3 (S3-T01).

## OI-56 — Generator of TypeScript types from the OpenAPI schema

- ID: OI-56
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of `@hey-api/openapi-ts` 0.99.0, or another choice, and of the Node floor it implies.
- WHY: docs/10_FRONTEND.md, section "Folders", says types for API payloads are generated from the FastAPI OpenAPI schema into `src/api/generated/`, that CI fails when the file differs from a fresh generation, and that "the generator is chosen and pinned at slice S0" (docs/10_FRONTEND.md, section "Open questions and assumptions", item 1); no generator is named.
- DONE SO FAR: Run on 2026-11-12 with TypeScript 6.0.3 on a schema produced by FastAPI 0.162.4 (an enum, a literal, an optional number, a list with a default, a nested model). `@hey-api/openapi-ts` 0.99.0 installs beside TypeScript 6.0.3 with no extra manifest key, writes types only with the `@hey-api/typescript` plugin, gives the same output twice, has no suppression comment and passes `tsc` in strict mode; it declares Node 22.18 or later (above the pack's 22.12), is below version 1, and its output holds a `ClientOptions` type whose template text contains the input file name. `openapi-typescript` 7.13.0 declares the peer `typescript ^5.x`, so beside TypeScript 6.0.3 it installs only with a root `overrides` entry (which the FE-01 check of S0-T03 reads, so the value must be the exact `6.0.3`), and its newest 7.x release is dated 2026-02-11; its output is otherwise clean. `swagger-typescript-api` 13.14.0 writes `eslint-disable` and `@ts-nocheck` lines at the top of its output, which the rules of S0-T04 (no suppression comment) forbid. `@hey-api/openapi-ts` is recorded as an ASSUMPTION, state recorded; it is not installed. Whichever generator is adopted, its output must pass `npm run lint` and `npm run format:check` of S0-T04 or the owner approves how it is excluded. The owner decided the method on 2026-11-11 and the lead assigned the requirement to this task.
- OPTIONS: **Recommendation:** `@hey-api/openapi-ts` 0.99.0, with the types plugin only, and raise the Node floor together with the decision in OI-54 (22.18.0 would cover this generator). Alternative: `openapi-typescript` 7.13.0 with the exact override.
- NEEDED BY: slice S3 (the API slice).

## OI-57 — Package family for the IBM Plex interface fonts

- ID: OI-57
- TYPE: ASSUMPTION
- NEEDED: Owner choice between the Fontsource packages and the IBM-published packages for IBM Plex Sans and IBM Plex Sans Arabic.
- WHY: docs/10_FRONTEND.md, section "Stack and pins", row "IBM Plex Sans, IBM Plex Sans Arabic", says the fonts are "pinned at slice S0" and docs/10_FRONTEND.md, section "Bilingual and right-to-left rules", says they are self-hosted as WOFF2 from "the pinned npm packages"; no package name or version is given. docs/10_FRONTEND.md, section "The basemap", says telemetry of any kind is absent from the page at run time.
- DONE SO FAR: Registry facts of 2026-11-11 and 2026-11-12. `@fontsource/ibm-plex-sans` and `@fontsource/ibm-plex-sans-arabic` 5.3.0 (OFL-1.1, a repackaging, no dependency, no install script, WOFF2 and WOFF files) are recorded as ASSUMPTION rows, state recorded; they are not installed. `@ibm/plex-sans` and `@ibm/plex-sans-arabic` 1.1.0 (OFL-1.1, from the typeface's own repository) depend on IBM's telemetry package and run a `postinstall` script that starts a collector at install time; its README gives an environment variable as the opt-out. That is an install-time matter, not the run-time page that docs/10_FRONTEND.md, section "The basemap", describes, and the pack does not address it. Vendoring the files with the licence text is slice S3 (FE-97, OI-43); the weight confirmation is S0-T13.
- OPTIONS: **Recommendation:** the Fontsource packages. Alternative: the IBM packages installed with install scripts switched off and the opt-out variable set, which the pack does not mention.
- NEEDED BY: slice S3 (FE-97).

## OI-60 — Home of the sandbox code and group of the engine dependency

- ID: OI-60
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that the sandbox launcher, its proofs, the extension fetch and the hosted-runner steps are modules of `scripts/`, with the two programs that run inside the sandbox in `scripts/sandbox_inside/`, and that DuckDB 2.0.0 is installed through a root dependency group named `engine` and not as a dependency of a package.
- WHY: The pack names no folder for the launcher: `custodian/` lists six sub-folders and none is a sandbox, and `scripts/` is "developer commands" (docs/02_ARCHITECTURE.md, section "Repository layout, commands and configuration"). The pack names DuckDB 2.0.x as the build engine (decision 0004, item 1 of its section "Decision"; docs/02_ARCHITECTURE.md, section "Technology stack", row "Build engine and embedded reader") and gives its dependency no home in slice S0: it names no manifest, group or package for it, and slice S1 confirms the pins. A run-time dependency of a package would make the offline clean-environment test of task S0-T02 need a download, because that test installs the packages with an empty cache and the network off.
- DONE SO FAR: The launcher is `scripts/sandbox_launch.py` with the tables in `scripts/sandbox_profiles.py`; the proofs are in `scripts/sandbox_check.py`; the probe and the loader are `scripts/sandbox_inside/sentinel_probe.py` and `extension_check.py`; the environment is made by `uv sync --managed-python --all-packages --locked --group engine`. Nothing is added under `core/`, `custodian/` or `product/`. A plain `uv sync --locked` removes the engine again, and `uv run --locked` keeps it; the sandbox tests then fail with the command to run. Proved by `test_run_starts_bubblewrap_with_nothing_inherited` and `test_current_venv_refuses_outside_an_environment` in `scripts/tests/test_sandbox_argv.py`, `test_real_extension_folder_is_populated` in `scripts/tests/test_sandbox_records.py` and the job in `.github/workflows/sandbox.yml`.
- OPTIONS: **Recommendation:** keep. Alternatives: make `duckdb==2.0.0` a dependency of `eii-custodian` and change the workspace-install test to use a populated cache (this weakens its assertion that nothing is downloaded); put the probe and the loader under `custodian/` (this changes the package skeletons and the scope of the import-boundary test).
- NEEDED BY: slice S0 gate.

## OI-61 — Mount list, staging folder, scratch space and budget of the sandbox profiles

- ID: OI-61
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm the closed mount list of the two profiles, the release staging folder, the in-memory scratch folder, the budget of a sandbox run, that every mount is made from a descriptor that the launcher opened and checked (this needs a bubblewrap with the options `--ro-bind-fd` and `--bind-fd`: release 0.10.0 or later, or a distribution package that carries them), that the sandbox tests may read the host process table (two tests scan `/proc` for a marker) and mount the system library folders and the uv interpreter folder read-only (AGENTS.md rule 13 names only repository, cache and temporary paths), and the threat model of the launcher with its two limits: it defends against code inside the sandbox, against a symbolic link in any part of a checked path, an object of the wrong kind, an entry beyond the four extension files in their platform folder, a second name of the scenario file or of an extension file, and an extension binary that differs from its pinned SHA-256, when present at the start, and against a rename or a link put in the place of a checked path after the check; it does not defend (1) against a process outside the sandbox that has write permission on a mounted object (a process of the same user, or root) and changes that object's content while a build runs, nor (2) against root, the kernel or bubblewrap themselves.
- WHY: SYN-01 names categories of mounts (docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md) and ARC-10 is flagged ASSUMPTION (docs/02_ARCHITECTURE.md). The pack gives no system library, interpreter location, `/tmp`, `/proc`, `/dev`, environment variable or bubblewrap option beyond "network unshared" (docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md, section "Rule zero and the sandbox", says to read the manual), no name for the folder of the new release folders (a release folder is named by a hash of its content: decision 0002, item 3 of its section "Decision"), and no value or place for the "separately recorded budgets" of sandbox tests (OPS-09, docs/13_DEPLOYMENT_AND_OPERATIONS.md). The pack confines the code that runs inside the sandbox ("`./eii build-world` runs every generator and the mobility simulator inside a bubblewrap sandbox with no network", ARC-09 in docs/02_ARCHITECTURE.md; SYN-01) and names no adversary outside it; it relies on bubblewrap and so on the kernel's namespaces (ARC-09 and ARC-12, docs/02_ARCHITECTURE.md).
- DONE SO FAR: The list is the golden command line in `scripts/tests/sandbox_golden.py`. The checkout is not mounted whole: only `core/src`, `custodian/src` and `scripts/sandbox_inside` are, so `data/` (other vaults and releases) and `.env` are not readable, which ARC-09 ("the only data input is `data/public_cache/`") needs; `product/src` is not mounted. The writable host paths are the vault folder and, for `build-release`, `data/releases/.staging/<build_id>`, which the release command moves after the sandbox ends. `/tmp` is an in-memory folder of unbounded size, `/proc` and `/etc` are not mounted, every namespace is unshared, the environment holds five names. A sandbox run has a timeout of 120 s; the measured duration of the sandbox tests is written in the notes of the ledger entry that runs them. `--disable-userns` and `--size` are not used. `build-world` always receives the scenario file and `build-release` never does; the tests and checks give `build-world` a fixture scenario file made in a temporary folder. The launcher opens each mount source once without following a symbolic link in its last part, checks it on the open descriptor (its kind, and the path the kernel gives for it, which must equal the given path) and hands bubblewrap the descriptor (`--ro-bind-fd`, `--bind-fd`), so a folder renamed into the place of a source, or a symbolic link put there, between the check and the start is not mounted; bubblewrap closes each descriptor after its mount, so the sandboxed command sees none: the launcher keeps every other descriptor out by construction (it passes bubblewrap exactly the mount descriptors), and the probe, which tries every descriptor number from 3 to 1023 inside the sandbox, prints `fds none` in `test_hostile_surroundings_do_not_reach_the_sandbox` and `test_swapped_source_is_not_mounted`. The two options are in bubblewrap 0.11.1 and in the Ubuntu 24.04 package 0.9.0-1ubuntu0.3, not in the Ubuntu 24.04 release build 0.9.0-1build1; a path bind is not used as a fallback. The scenario file must have exactly one name. The engine-extension folder is an in-memory mount of its own: the launcher opens its version folder, its platform folder and its four files relative to the folder's descriptor without following a symbolic link in any of them, requires each file to be a regular file with one name and each binary to have its pinned size and SHA-256, read through its own descriptor, and binds each file read-only from that descriptor into it; the mount is then made read-only, so the engine sees exactly these four files and nothing can be added, removed or renamed in it inside the sandbox, wherever the folder lies (`write_extensions` in `test_filesystem_modes_in_both_profiles` and the plant in `test_planted_leaks_are_seen`); a platform folder that holds anything besides the four files, or lacks one of them, is refused before bubblewrap starts; an empty extension folder binds nothing, and a file replaced after the check is not the file that is loaded. The launcher does not protect against a process outside the sandbox that has write permission on a mounted object (a process of the same user, or root) and changes that object's content while a build runs: binding by descriptor fixes which object is mounted, not its bytes; the extension binaries stay signed and DuckDB checks the signature on every load. Nor does it protect against root, the kernel or bubblewrap themselves. When a mount destination lies under `/tmp`, the folders above it are made on the in-memory scratch mount and stay writable inside the sandbox; they belong to that one sandbox run and nothing of them reaches the host. Refusing such a layout is hardening beyond the acceptance criterion (document 17, DHA-07) and is not built. The tests read the host `/proc` process list only to look for their own marker (`test_timeout_kills_the_process_group`, `test_die_with_parent`) and write nothing outside temporary folders; the probe's write attempts into the environment and interpreter folders delete their file at once. Proved by `test_golden_command_line_build_world`, `test_golden_command_line_build_release`, `test_mount_destinations_are_the_closed_list`, `test_scenario_and_staging_belong_to_one_profile` and `test_open_sources_cases` in `scripts/tests/test_sandbox_argv.py`, `test_extension_tree_cases`, `test_launcher_binds_the_checked_files` and `test_every_source_descriptor_names_its_object_after_a_swap` in `scripts/tests/test_sandbox_extensions.py`, `test_swapped_source_is_not_mounted`, `test_hostile_surroundings_do_not_reach_the_sandbox`, `test_filesystem_modes_in_both_profiles` and `test_environment_names_and_values` in `scripts/tests/test_sandbox_mounts.py`, `test_repository_secrets_are_not_mounted` and `test_scenario_and_staging_mounts` in `scripts/tests/test_sandbox_sentinel.py`, and `test_extension_files_are_the_checked_objects` in `scripts/tests/test_sandbox_loading.py`. Task S1-T06 confirmed on the build machine, by `uv run --locked python scripts/sandbox_check.py check-enforcement`: the closed mount list of both profiles against an independent policy (descriptor binds; the scenario only in `build-world`; one writable staging folder only in `build-release`), the sentinel file unreadable and local network attempts failing inside both profiles, and the offline extension load. The system-library and interpreter mounts against rule 13, the timeout and the budgets, the limits of the threat model and the two tests that read the host process table stay for the owner.
- OPTIONS: **Recommendation:** keep; slice S1 task S1-T06 confirms the production boundary and slice S4 adds folders by editing the table and the golden list together. Alternatives: mount the checkout whole (this exposes `data/` and `.env`); mount `data/releases/` whole (existing releases become writable); add `/proc`; bound `/tmp` with `--size` after a measured need.
- NEEDED BY: slice S0 gate; slice S1 (S1-T06).

## OI-62 — Engine-extension folder, fetch hosts and pinned file hashes

- ID: OI-62
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm (1) that `data/engine_extensions/` is the provisional project-local folder of the DuckDB extensions and a documented cache path for tests; (2) that the fetch of the two extensions from `extensions.duckdb.org` and `community-extensions.duckdb.org` over HTTP is not a fetch of a "source host" in the sense of PUB-01 and PUB-03; (3) that the size and SHA-256 of each extension binary are pinned in `scripts/extension_tree.py` and enforced after every fetch and by `verify`: an enforced pin fails the fetch when the extension repository publishes a new build for the same engine version, and a person then reviews the new file and updates the pin; the alternative is to record the hashes and rely on the engine's signature check alone.
- WHY: ARC-14 and decision 0004 (section "Open questions and assumptions") fix the folder as project-local and "the exact path is fixed at slice S1" (ARC-14, docs/02_ARCHITECTURE.md). PUB-01 and PUB-03 (docs/04_PUBLIC_DATA_PACK.md) speak of source hosts, none of them an extension host, and no pack text names the command that fetches extensions. AGENTS.md rule 13 lets tests use only documented repository, cache and temporary paths.
- DONE SO FAR: `scripts/engine_extensions.py fetch` installs `spatial` (core repository, licence MIT) and `h3` (community repository, licence Apache-2.0) into the folder, checks the files against the pinned table (values taken from two repeatable fetches on 2026-11-12), and writes `EXTENSIONS.json` with the engine version, platform, file names, sizes and SHA-256 read through the descriptors of the checked files. The table and the check are in `scripts/extension_tree.py`: every part of the folder is opened without following a symbolic link, every file must be a regular file with one name, and the platform folder holds nothing but the four files. The folder is not mounted into the sandbox as a whole: each checked file is bound read-only from its descriptor, so the files lie at their paths inside the sandbox's read-only mounts and nothing else of the folder is visible. DuckDB's signature check stays on, and the `.info` file of each extension must be present (without it the community extension fails the check). The default extension folder in the home folder of a build machine may already hold the same files, so every load test runs inside the sandbox, where the home folder is not mounted. The folder is under the ignored `data/`; `docs/02_ARCHITECTURE.md`, section "Repository layout, commands and configuration", lists three children of `data/` and is not edited here; slice S1 edits it when the path is confirmed. Proved by `test_pinned_table_is_well_formed`, `test_fetch_configuration_and_statements`, `test_fetch_record_and_output`, `test_fetch_and_main_failures` and `test_real_extension_folder_is_populated` in `scripts/tests/test_sandbox_records.py`, by `test_extension_tree_cases` and `test_launcher_binds_the_checked_files` in `scripts/tests/test_sandbox_extensions.py`, and by `test_load_offline_read_only_in_both_profiles`, `test_signature_check_stays_on`, `test_empty_folder_and_read_only_install`, `test_automatic_loading_is_off` and `test_extension_files_are_the_checked_objects` in `scripts/tests/test_sandbox_loading.py`. Task S1-T06 confirmed that the folder is present, that `verify` passes and that the offline load inside the enforcement proof passes; the fetch hosts and the pin policy stay open for task S1-T08.
- OPTIONS: **Recommendation:** keep. Alternatives: a folder outside `data/` (needs an ignore pattern and a probe line in the tree check of task S0-T01); let `./eii build-public` fetch the extensions (needs a reviewed change of the host list); record the sizes and hashes without enforcing them and rely on the signature check of DuckDB alone (the fetch then never fails on a new build, and a new signed build is loaded without a review of its bytes).
- NEEDED BY: slice S1 (S1-T06 and S1-T08).

## OI-63 — The hosted-runner job and the AppArmor profile

- ID: OI-63
- TYPE: ASSUMPTION
- NEEDED: The owner confirmed in the notes of 2026-11-12 that the hosted sandbox proof decides by behaviour: with the restriction set to 1 and the first probe failing, the job installs and loads the per-binary distribution profile and requires the same probe to pass; the sandbox tests require both prohibited operations to fail under both profiles and are never skipped (TASKS.md, task S0-T11). A passing first probe installs nothing. The exact listing, profile size and SHA-256 pin, and stacked label are printed records only, registered in docs/17_DEPLOYMENT_HARDENING.md, section "Hardening register". The hosted evidence of the behaviour proof is the sandbox workflow on the pull request head of task S0-T15, recorded in PROGRESS.md.
- WHY: TST-62 requires the sandbox test in CI, never skipped, with a per-binary AppArmor profile preferred over a system-wide switch (docs/12_TESTING_AND_QUALITY.md). The scope of task S0-T11 names "hosted-runner namespace setup" and the criteria of S0-T07 name "the hosted-runner sandbox proof" (TASKS.md, tasks S0-T11 and S0-T07); both cite TST-61 and TST-62. The pack says only "GitHub Actions on an Ubuntu runner" (docs/13_DEPLOYMENT_AND_OPERATIONS.md, section "Environments", row "Continuous integration") and that workflow file names "are chosen in slice S0 and listed" in document 13 (docs/12_TESTING_AND_QUALITY.md, section "The CI pipeline"). The owner decided the method on 2026-11-11 and the lead assigned the requirement to this task; task S0-T07 lists the further files.
- DONE SO FAR: The job installs a pinned `uv` and a uv-managed Python 3.14, syncs the locked environment, installs `bubblewrap` and `apparmor-profiles`, prints the runner facts, runs `ci_sandbox.py install-profile`, fetches the extensions and runs `ci_sandbox.py prove`, which requires each of the 19 sandbox test cases named in `scripts/ci_junit.py` exactly once and passed and no other test case, and fails when one is missing, repeated, failed or skipped, when another case appears, or when the test run wrote to standard error. Task S0-T15 implements the owner's notes of 2026-11-12: `install-profile` reads the restriction without writing it and prints the first probe result. Exact success returns without installing anything, including when the restriction reads 1. Otherwise, when the restriction reads 1, the source profile must exist; its size and SHA-256 are printed without comparison. The profile is installed only when the target is absent; an existing file that differs is never replaced. The target size and SHA-256 are printed and `apparmor_parser -r` loads it. Installation, loading and the probe after loading still require exit 0, empty standard error and exactly the expected standard output; failure fails the job. After the probe passes, `aa-status --json` and the label read each print their raw exit status, standard output and standard error; neither the status nor the content decides the result. When the restriction is absent or not 1, a failing first probe fails the job. No kernel setting is written. The obsolete pin, listing and label judges and their test module are removed. The workflow and the 19-case proof are unchanged. Stub-runner evidence is in `scripts/tests/test_sandbox_userns.py` (call order, missing source, parser and probe failures, record-only commands, early return and no system-wide switch) and `scripts/tests/test_sandbox_output.py` (exact command judging); `scripts/tests/test_sandbox_prove.py` retains the case-identity proof. The README names none of the three demoted checks and is unchanged. Hosted evidence for this follow-up remains with the lead. Historical note: the initial S0-T11 entry said no hosted run had yet been made; the following correction is retained as history, not evidence for S0-T15. Correction after the hosted runs of 2026-11-12, which replaces the statement above that nothing was run on a hosted runner: three runs were made. The first failed in the status judge, because `aa-status --json` prints one JSON object whose closing brace stands on a second line; the judge now reads the whole output as one JSON document. The second passed that step and 18 of the 19 test cases; the one failure was the extension-folder defect recorded in OI-61. The third, on the commit that seals the extension folder, is green: https://github.com/albarami/economic-investment-intelligence/actions/runs/43249261738 . Its log shows Ubuntu 24.04.5 LTS with kernel 7.0.0-1017-azure; the restriction setting reads 1 and AppArmor is enabled; the packages are `bubblewrap` 0.9.0-1ubuntu0.3 and `apparmor-profiles` 4.0.1really4.0.1-0ubuntu0.24.04.9; before the profile is installed the probe exits 1 with "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted"; the listing names `bwrap` and `unpriv_bwrap` in enforce mode; the label read is `bwrap//&unpriv_bwrap (enforce)`; the probe then passes; the two extensions are fetched with their pinned sizes and hashes; and the 19 test cases pass.
- OPTIONS: **Recommendation:** keep; task S0-T07 lists the further workflow files in document 13, may move the job and never drops it. Alternatives: put the sandbox step into the workflow of S0-T07 and build that task first (this pull request is built before the CI task by the lead's order of work); leave document 13 unchanged and let task S0-T07 list both files (the sentence of docs/12_TESTING_AND_QUALITY.md, section "The CI pipeline", would then not be true of this pull request, and REV-17 asks that every affected document be updated).
- NEEDED BY: before task S0-T07 is planned; slice S0 gate.

## OI-64 — The sandbox tests are part of `./eii test` and are never skipped

- ID: OI-64
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that the sandbox tests are collected by the default test run, fail instead of skipping when bubblewrap, the `engine` group or the fetched extensions are missing, and are named one by one in a closed list that the hosted proof requires exactly.
- WHY: TST-15 says `./eii test` runs every pull-request suite that needs no network and TST-16 asks for a `sandbox` marker (docs/12_TESTING_AND_QUALITY.md); the architecture table gives `./eii test` the sandbox column "sentinel test only" (docs/02_ARCHITECTURE.md, section "Repository layout, commands and configuration", row `./eii test`) while the operations table lists "Tools, PostgreSQL" (docs/13_DEPLOYMENT_AND_OPERATIONS.md, section "The `./eii` commands", row `./eii test`); the S0 gate needs the sandbox tests passing with their teeth (docs/12_TESTING_AND_QUALITY.md, section "Slice gates and the evidence that proves them", row "slice S0 Foundation"); TST-06 allows only two standing skips. The extension fetch needs the network once, so the tests cannot fetch.
- DONE SO FAR: The three modules of the marker `sandbox` are in `scripts/tests/`, inside the suite `python-guards` and the unittest command. A missing prerequisite fails with a message that names the command. The list `REQUIRED` in `scripts/ci_junit.py` names each test of those modules, and `test_required_cases_match_the_marker_modules` compares it with the test methods the modules hold; the hosted proof requires each named test exactly once and passed and no other. `test_real_extension_folder_is_populated` is not marked, so it also runs in `python-guards`, in the unittest command and in any CI job that runs the guard suite or `./eii test`: such a job must sync with `--group engine` and run `uv run --locked python scripts/engine_extensions.py fetch` first, or the test fails and names the command; task S0-T07 plans for it. Proved by `test_required_cases_match_the_marker_modules` and `test_case_judgement` in `scripts/tests/test_sandbox_prove.py`, `test_real_extension_folder_is_populated` and `test_load_offline_read_only_in_both_profiles`.
- OPTIONS: **Recommendation:** keep. Alternatives: an opt-in marker run only in CI (leaves the local run without the proof, against TST-61); a skip with a reason (not allowed by TST-06).
- NEEDED BY: slice S0 gate.

## OI-80 — Placeholder exit and the failure line

- ID: OI-80
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that a command whose body is not built exits 1 and never 0, and that a failure prints `FAIL <command>: <detail>` followed by `eii: exit <code>: <meaning>` using the meaning text in the operations document.
- WHY: OPS-26 requires one code from that table and the meaning on failure. The pack has no code for work that is not built, and it does not give the print format. A code outside 0 to 7 is an internal fault and becomes exit 1.
- DONE SO FAR: Placeholders, including `down`, exit 1. `build-public` names S2-T01, `load-release` names S3-T02, and `freeze` names S11-T01 and S11-T06. The serving body of `up`, and the bodies of `down`, `build-world` and `build-release`, say `not_built (not built yet)` and name no task. `./eii test` keeps the usage line it already prints. On success, `db-down` prints `PASS db-down: database service stopped`, parallel to the success line stated for `db-up`. Two exit-1 paths delivered by S0-T05 print no meaning line and keep their own lines: the launcher when `uv` is not found, and `./eii test` when a suite fails.
- OPTIONS: **Recommendation:** keep. Alternative: exit 0 for `down` when no API is running, and print no success line for `db-down`.
- NEEDED BY: the owner, before the slice S0 gate.

## OI-81 — Database commands are Compose only, use stop, and use fixed time limits

- ID: OI-81
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that `db-up` and `db-down` use Compose only, that `db-down` runs `stop` so the volume stays, and that the outer limits are 90 seconds for `db-up` and 60 seconds for `db-down`.
- WHY: The operations document offers a native service as well as Compose, and it says `db-down` stops the database and never removes volumes. It is silent on the stop verb and on an outer limit beyond the 60 second Compose wait. A native start needs privileges, and the setup script is not in this tree.
- DONE SO FAR: Both commands refuse when `docker` is not on PATH. `db-down` runs `stop db`. The wait flag is `--wait-timeout 60`. The process limit is 90 seconds for `db-up` and 60 seconds for `db-down`.
- OPTIONS: **Recommendation:** keep. Alternatives: add the native service path, or stop with `compose down` without removing volumes.
- NEEDED BY: the owner, before a task builds a native database start.

## OI-82 — No preflight rows inside the database commands, and no product port ban

- ID: OI-82
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of two readings: `db-up` and `db-down` check that `docker` is on PATH and that `EII_DATABASE_URL` yields a loopback port, and they do not run the preflight rows; the command code has no ban on a port the operations document names.
- WHY: The command table lists "Tools, database" and "Tools" as the checks those two commands run. The same document names a pack port. The build machine forbids three ports for tests and for the lead; that ban is not written as a product rule.
- DONE SO FAR: Neither command calls preflight. An unset or invalid `EII_DATABASE_URL` exits 1 and names the variable. There is no default port and no port ban in the command code. The two command-table rows were not edited.
- OPTIONS: **Recommendation:** keep. Alternative: run the preflight rows before starting, and refuse the pack port in code.
- NEEDED BY: the owner, before the slice S0 gate.

## OI-83 — The Compose secret file is not created by the database commands

- ID: OI-83
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that `db-up` and `db-down` never create or print the Compose secret file, and that they refuse when it is not a regular file.
- WHY: The pack names `data/compose/postgres_superuser_password` and does not say which command writes it.
- DONE SO FAR: Both commands require a regular file at that relative path. The failure line names the path. The commands do not create the file and do not print its contents. `db-down` uses the same check because loading the project can read file secrets.
- OPTIONS: **Recommendation:** keep; the file is created outside these commands, with owner-only permissions. Alternative: generate a value into the uncommitted data folder.
- NEEDED BY: the owner, before the first live `db-up`.

## OI-84 — No task is named for four command bodies

- ID: OI-84
- TYPE: OPEN
- NEEDED: The owner to name the tasks that build the serving body of `up`, the body of `down`, `build-world` and `build-release`, or to confirm that none is named yet.
- WHY: A placeholder may name a task only where TASKS.md says that the task builds that command's body. S2-T01, S3-T02, S11-T01 and S11-T06 are named for `build-public`, `load-release` and `freeze`. No task is named for the other four bodies.
- DONE SO FAR: Those four lines say `not_built (not built yet)` and name no task. The other placeholders name only the tasks listed above.
- OPTIONS: **Recommendation:** the owner names the tasks, or records that they stay unnamed. Alternative: infer task ids from neighbouring tasks, which was refused.
- NEEDED BY: the owner, before those four bodies are built.

## OI-85 — A check for the reference notes, and the files it changes

- ID: OI-85
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that task S0-T13 adds a check of the reference notes (`scripts/check_reference_notes.py` with `scripts/reference_notes_parse.py`, `scripts/reference_notes_report.py`, `scripts/reference_notes_assigned.py` and `scripts/reference_notes_tables.py`, and a support module and four test files under `scripts/tests/`), one command in rule 44 of AGENTS.md and CLAUDE.md, and edits to files of earlier tasks (the layout check of `web/` and its test, README.md, the documents index and the information table).
- WHY: `TASKS.md, task S0-T13` gives the scope of S0-T13 as "dependency reference notes under `docs/` assigned to this task only", while FE-02 (docs/10_FRONTEND.md) puts one notes file under `web/` (and docs/10_FRONTEND.md, section "Folders", lists it). The acceptance criteria are to be shown by a command (TST-01, TST-04 in docs/12_TESTING_AND_QUALITY.md), the layout check of `web/` named the web notes file as deferred to this task, and `docs/12_TESTING_AND_QUALITY.md TST-163` requires documents that a change makes untrue to be updated in the same pull request. `TASKS.md, section "Queue rules"` says files outside a task's scope are read-only. The owner decided on 2026-11-11 that the lead assigns each slice S0 requirement that no task owned to the nearest task; the lead assigned DES-25 and DES-45 to S0-T13. The scope sentence names notes for libraries, so the section of `web/REFERENCE_NOTES.md` that holds those two confirmations is outside it in the same way as the check.
- DONE SO FAR: The check judges the form of the two notes files: sections, kinds, sources, allowed addresses, dates, quotation shape, the words "not verified" on pack statements, the confirmation tables, the coverage tables, the `pins.toml` rows and the pack anchors that the notes cite (it verifies that each anchor exists in the cited file and does not check what the anchored text says). It runs inside the test suite, so `./eii test` and continuous integration run it and no workflow file changes. The check also judges the section "Confirmations assigned to this task" of the web notes (its opening sentence, its four tables, the font rows and the icon rows). The layout check now requires `web/REFERENCE_NOTES.md` and no longer has a deferred list. The notes quote differences that the documentation of DuckDB and of PostgreSQL states for the same operation (the order of null values, integer division), because the pack relies on them for its parity query (docs/08_BACKEND.md, section "The portable SQL subset", rows "`/` and `%`" and "`ORDER BY` without explicit `NULLS FIRST` or `NULLS LAST`"); they are quoted from each page and make no comparison of quality, and decision 0012, item 5 of its section "Decision", allows software components to be named in engineering documents. Proved by `test_clean_fixture_passes`, `test_real_notes_pass` and the other tests of `scripts/tests/test_reference_notes_form.py`, `scripts/tests/test_reference_notes_rows.py`, `scripts/tests/test_reference_notes_real.py` and `scripts/tests/test_reference_notes_assigned.py`, and by `npm run check:layout` in `web/`.
- OPTIONS: **Recommendation:** keep. Alternatives: notes only, with no check (the acceptance criteria would then rest on a reviewer's reading); or a check in the documentation check `scripts/check_docs.py` (a change to a file that other tasks edit).
- NEEDED BY: slice S0 gate.

## OI-86 — Which libraries the notes cover

- ID: OI-86
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that the notes cover exactly MapLibre GL JS 6, deck.gl 9.4 with its MapLibre module, DuckDB 2.0, PostgreSQL 18 and the Claude API, or to name others.
- WHY: AGENTS.md rule 42 names these five and says "especially"; docs/02_ARCHITECTURE.md, section "Technology stack", names the same five. Other places call further items newer than most model training data or give them a read-first entry: PostGIS 3.6 and GeoParquet (docs/03_DATA_CONTRACTS.md, section "Logical types"), FastAPI's server-sent-event support (docs/08_BACKEND.md, section "Scope"), psycopg parameter passing (docs/02_ARCHITECTURE.md, section "Technology stack", row "PostgreSQL driver"), `pmtiles` and `@protomaps/basemaps` (docs/02_ARCHITECTURE.md, section "Technology stack", row "Basemap").
- DONE SO FAR: Six sections in two files: MapLibre GL JS 6, deck.gl 9.4 and the deck.gl MapLibre module in `web/REFERENCE_NOTES.md`; DuckDB 2.0, PostgreSQL 18 and the Claude API in `docs/REFERENCE_NOTES.md`. The closed list is in `scripts/reference_notes_tables.py`; adding a library is a change to that table, the notes and the tests of `scripts/tests/test_reference_notes_form.py` and `scripts/tests/test_reference_notes_rows.py` (`test_tables_have_their_sizes` fails until the sizes are updated). The font packages and the icon package are not libraries of this list; their confirmations are OI-89.
- OPTIONS: **Recommendation:** keep the five and add PostGIS 3.6 to the PostgreSQL section at slice S1, when the image is pinned. Alternatives: add every item listed under WHY now; or keep the five and read the others in their slice.
- NEEDED BY: slice S1 gate.

## OI-87 — Pack statements that the pages and runs did not support

- ID: OI-87
- TYPE: OPEN
- NEEDED: The owner (or the lead, through a decision record where a statement is amended) to decide how each statement below is corrected or confirmed.
- WHY: The notes were written from official pages read on 2026-11-12 and from runs with the packages. (1) docs/10_FRONTEND.md, section "Layouts, presenter mode and big-screen rules", and FE-71 (docs/10_FRONTEND.md) apply the pixel-ratio cap to deck.gl through `useDevicePixels` set to a number; the page of `MapLibreOverlay` says "useDevicePixels and device are ignored in interleaved mode because MapLibre owns the shared canvas", and the pack uses interleaved mode (FE-04 (docs/10_FRONTEND.md)); the MapLibre side (`pixelRatio`, `maxCanvasSize`) is supported by the MapOptions page. (2) docs/10_FRONTEND.md, section "Stack and pins", row "WebGPU in deck.gl", gives as a reason against WebGPU that it "cannot interleave with the basemap (deck.gl 9.4 notes)"; the What's New page says WebGPU is experimental and not recommended for production and does not say the second half, while the WebGPU developer-guide page (page P4 of the deck.gl section of the web notes) lists base map interleaving as not supported; the statement is supported, but the source the pack names is not the page that says it. (3) docs/09_AI_ASSISTANT.md says a zero-output pre-warm "is rejected together with streaming or structured output" (AI-57 (docs/09_AI_ASSISTANT.md)), that eager input streaming is "the reference's recommended setting" (docs/09_AI_ASSISTANT.md, section "Model settings", row "Tool definitions"), that earlier turns must be "byte-identical" (AI-48 (docs/09_AI_ASSISTANT.md)) and that the reference "recommends" server-side refusal fallbacks "by default" (AI-60 (docs/09_AI_ASSISTANT.md)); no page read says so. The row "Stop reasons" of the same section lists five stop reasons; the stop-reason page lists seven, adding `stop_sequence` and `model_context_window_exceeded`. The section "Model settings" of docs/09_AI_ASSISTANT.md says that every statement in it was checked against the Claude API reference bundled with the tool; the section "Sources" names the same bundled reference as its source. (4) docs/02_ARCHITECTURE.md, section "Technology stack", row "Build engine and embedded reader", and docs/decisions/0004-duckdb-build-engine-and-embedded-standby.md, section "Evidence", say `postgres_execute` takes one statement per call; the function page names one query argument and states no limit, and no PostgreSQL server was available. (5) PUB-17 (docs/04_PUBLIC_DATA_PACK.md) and docs/03_DATA_CONTRACTS.md, section "Logical types", say DuckDB 2.x needs `SET geometry_always_xy=true`; the spatial extension overview page (page P12 of the DuckDB section) does not mention it. (6) docs/decisions/0006-fixed-grid-and-pin-based-areas.md, section "Evidence", and docs/10_FRONTEND.md, section "Performance budgets", give 60 frames per second up to about one million items from the deck.gl performance guide; the page ties that figure to 2015 hardware with dual graphics cards and says frame rates fall to the low double digits near ten million items, and the pack itself calls its figures targets to be measured (docs/10_FRONTEND.md, section "Performance budgets").
- DONE SO FAR: In `docs/REFERENCE_NOTES.md` and `web/REFERENCE_NOTES.md` each point is a row: a READ row where a page supports a part, and a PACK row marked "not verified" where nothing does. No pack document was edited. Proved by the rows named in those files (statement S9 of the module section; S3, S4 and S10 of the deck.gl section; S24 and S25 of the DuckDB section; S23 to S27 of the Claude API section) and by `test_real_notes_pass`.
- OPTIONS: **Recommendation:** slice S1 settles (1), (4), (5) and (6) in its spikes and re-reads (2) and (3) before the assistant is built; amend the pack by a decision record (AGENTS.md rule 46) where a reading is changed. Alternative: amend the pack documents now.
- NEEDED BY: slice S1 gate.

## OI-88 — What the notes and their check prove

- ID: OI-88
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm five limits of the reference notes.
- WHY: `docs/12_TESTING_AND_QUALITY.md TST-01` allows a statement only with evidence; the pages change and a test may not use the network (AGENTS.md rule 27 and TST-08).
- DONE SO FAR: (a) `scripts/check_reference_notes.py` judges form only. It does not fetch pages; that a quotation is on its page and supports its row clause by clause, and that a command of a Runs table still prints its output, were checked once on 2026-11-12 by a second reader of another maker with scripts that are not committed, and are not checked in continuous integration. The coverage table of each file is a list, made by hand when the notes were written, of the statements of the pack about its libraries; the check requires each anchor it cites to exist in the cited file and its row references to be real, does not check what the anchored text says, and cannot show that the list is complete. (b) No browser, PostgreSQL server or request to the Claude API was used, so the notes carry no OBSERVED row about rendering, a server or the API. (c) The only value of a slice S1 confirmation field is `not yet confirmed`; the first S1 task that confirms a field widens the vocabulary in its own change. (d) The notes carry no pin and no retreat pin; `pins.toml` does. (e) The notes quote short phrases (3 to 40 words) of the pages with their addresses and dates; no page is copied. Proved by `test_clean_fixture_passes`, `test_addresses` and `test_dates` in `scripts/tests/test_reference_notes_form.py`, and by `test_confirmation`, `test_quotes` and `test_coverage` in `scripts/tests/test_reference_notes_rows.py`. A browser run now exists: the glyph spike of task S1-T01 measured the font route, the worker address, the interleaved overlay and the order of the hexagon layer; the measurements are in its task log, the confirmation fields of the notes stay as they are until task S1-T08 fills them, and the check still judges form only.
- OPTIONS: **Recommendation:** keep, and let slice S1 re-read the pages it relies on and update the dates. Alternative: a scheduled job that fetches the pages and compares the quotations (needs the network and a place to run it).
- NEEDED BY: slice S1 gate.

## OI-89 — What the font and icon confirmations leave open

- ID: OI-89
- TYPE: OPEN
- NEEDED: The owner or the lead to name the slice that pins the icon package and vendors the icon files with their licence text, and the files that are served for the two typefaces.
- WHY: The owner decided on 2026-11-11 that the lead assigns each slice S0 requirement that no task owned to the nearest task; the lead assigned DES-25 and DES-45 to S0-T13. DES-25 (docs/11_DESIGN_DIRECTION.md) says the availability of the weights Regular 400, Medium 500 and SemiBold 600 is "to be confirmed in the font files at slice S0"; DES-45 (docs/11_DESIGN_DIRECTION.md) says "the icons package licence is to be confirmed at slice S0" and that the icons are "vendored locally, with the licence recorded in the repository". The pack names no slice that vendors the icons; FE-97 (docs/10_FRONTEND.md) puts the font licence text in slice S3. The icon package is not a row of `pins.toml` and the notes pin nothing.
- DONE SO FAR: The section "Confirmations assigned to this task" of `web/REFERENCE_NOTES.md` records, from runs of 2026-11-12, that the two Fontsource packages (version 5.3.0 each, the version `pins.toml` pins) hold the files of the normal style at the weights 400, 500 and 600, as woff2 and woff files, in six subsets for IBM Plex Sans and four for IBM Plex Sans Arabic, and that the package `@carbon/icons` 11.92.0 names the licence Apache-2.0 in its metadata and holds a licence file that begins with the words of the Apache License, Version 2.0, as the licence file of the repository does (page read the same day); no weight is missing and the licence is the one the pack assumes. Nothing was looked at about glyph coverage, font features (the tabular figures that docs/10_FRONTEND.md, section "Bilingual and right-to-left rules", asks to check at slice S1) or the icons themselves (grid and stroke). Proved by the rules `weights` and `icon-licence`, by `test_font_weights`, `test_icon_licence` and `test_real_notes_pass`, and by the second reader's comparison of each font row with its package. The registry metadata of the package @carbon/icons 11.92.0 lists an install script that runs a telemetry command (read on 2026-11-12 with a registry query in a scratch folder); the slice that adds the package decides how it is installed and vendored. The glyph spike of task S1-T01 serves weight 400 only, of the two Plex and the two Noto packages; the other weights, tabular figures, glyph coverage beyond its five names and the icon package are not settled by it.
- OPTIONS: **Recommendation:** pin the icon package and vendor its files with the licence text in the first slice that uses an icon, and re-run the confirmation there. Alternative: add the icon package to `pins.toml` now.
- NEEDED BY: the first slice that serves a font file or an icon (slice S3 for fonts, FE-97).

## OI-90 — Hook framework, scanner version and the set of hooks

- ID: OI-90
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of the hook framework, the scanner version, the eleven hooks and when each runs, and that no commit-message hook is added.
- WHY: The pack requires gitleaks "as a pre-commit hook" (TST-141 in docs/12_TESTING_AND_QUALITY.md) and a commit guard that refuses a staged local secret value without printing it (TASKS.md, task S0-T06; docs/14_IMPLEMENTATION_PLAN.md, section "slice S0 — Foundation"); it names no hook framework, no gitleaks version and no configuration file, and states Conventional Commits as a convention only (PLN-05 in docs/14_IMPLEMENTATION_PLAN.md; AGENTS.md rule 33).
- DONE SO FAR: The `pre-commit` framework 4.7.0 (PyPI, 2026-11-12, MIT) is pinned in the root `dev` group, with `.pre-commit-config.yaml` holding eleven local hooks and `.gitleaks.toml` holding the default rules with no allow-list of its own (the scanner's built-in path list is inherited, see OI-93); gitleaks 8.30.1 (GitHub release, 2026-03-21, MIT) is recorded in `pins.toml`. Five hooks run on every commit and six run when a staged path matches (Python files or any `pyproject.toml`; files under `web/`), including the type checks; the move of the type checks to the manual stage is one configuration change. A hook whose program is missing fails with a message that names the install command. The first `uv run --locked` in a clone builds the environment and needs the network once; every later commit needs none. The scope line of the task ("pre-commit configuration and scanner test fixtures") is read as including the four small scripts and their tests that the guard, the scanner wrapper, the installer and the dispatcher need, and one statement of `scripts/check_docs.py` (OI-93). No commit-message hook is added: the pack gives no type list, no scope list and no rule for the merge messages that git writes, and a commit-message hook refuses those messages (observed).
- OPTIONS: **Recommendation:** keep. Alternatives: the framework's own gitleaks hook pinned by a commit hash (it fetched the latest Go toolchain and cached 329 MB when tried, so it is not immutable); type checks at the manual stage; a commit-message hook with a closed grammar (type list an assumption) and an explicit rule for merge messages.
- NEEDED BY: slice S0 gate.

## OI-91 — Installing the hooks beside existing local hooks

- ID: OI-91
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of the installer's default, which refuses and writes nothing wherever a hook or a `pre-commit.legacy` file already exists, and a decision on how the repository's hooks live beside hooks that are already in a clone's hooks folder.
- WHY: The framework moves an existing hook to `pre-commit.legacy` and runs it first, replaces an existing `pre-commit.legacy` without a message, runs a `pre-commit.legacy` that it finds without a `pre-commit` hook beside it, deletes the old hook under `-f`, refuses when `core.hooksPath` is set, and installs into the main clone's hooks folder even when run in a linked work tree (all observed on 2026-11-12 in scratch repositories). The pack asks for a hook and names no install procedure. The clone on the build machine already has local hook files named `pre-commit` and `pre-push` (their names were listed; nothing was read, written or run).
- DONE SO FAR: This task never installs a hook in the repository or in a work tree of it; every test installs in a scratch repository and compares the real hooks folder and git configuration before and after. `scripts/hooks_install.py` refuses in each of the cases above, and when its folder is not the top of its own checkout, and writes nothing; its refusal message points to README.md, section "Commit hooks".
- OPTIONS: **Recommendation:** keep the refusal as the default. Where a clone already has a hook, the developer copies the hooks folder aside and then either moves the old hook's commands into `.pre-commit-config.yaml` as one more local hook with a test, or runs `pre-commit install` by hand and accepts migration mode (the existing hook runs first; `pre-commit uninstall` restores it). Alternative: rely on continuous integration only (does not meet TST-141 in docs/12_TESTING_AND_QUALITY.md, "pre-commit hook").
- NEEDED BY: before the first developer installs the hooks; slice S0 gate.

## OI-92 — Commit guard: secret list, reading `.env`, minimum length

- ID: OI-92
- TYPE: CLOSED (was ASSUMPTION)
- NEEDED: Owner confirmation of the closed list of guarded values, that the guard may read the uncommitted `.env`, and the minimum length of 12 characters with refusal below it.
- WHY: The pack marks `ANTHROPIC_API_KEY`, `JEV_PRO_API_KEY`, `TOMTOM_API_KEY` and `EARTHDATA_API_KEY` as keys that are never printed and `EII_DATABASE_URL` as holding the application role's password (docs/13_DEPLOYMENT_AND_OPERATIONS.md, section "Environments", rows `ANTHROPIC_API_KEY`, `EII_DATABASE_URL`, `JEV_PRO_API_KEY`, `TOMTOM_API_KEY` and `EARTHDATA_API_KEY`; OPS-07, OPS-14 and OPS-71 in the same file), says running code reads secrets from the process environment and that "setup scripts may read the uncommitted `.env`" (OPS-08 in the same file), and gives no list for a guard, no minimum length and no rule for a short value.
- DONE SO FAR: The guard judges the five names, four keys and the database URL (for the URL, the password, raw and percent-decoded), from `.env` (read without a byte order mark, with quotes and a trailing comment; a line it cannot read is refused) and the environment, over the content and the path of every staged file, and prints the variable name and, only when it holds no value, the path. A value below 12 characters (for the URL, the password as written or percent-decoded), a database URL that is not a PostgreSQL URL with a host and, when a port is written, a numeric one, and with no at-sign after the host part and no `password` or `passfile` parameter in its query string, or a double-quoted `.env` value that holds a backslash, makes it refuse, because a silent pass would let a one-character value, an unreadable URL or a misread line switch the guard off. A staged submodule entry has no content of its own; its path is judged. The guard reads git's index from the top of the repository. A shorter minimum would refuse ordinary commits, because words such as `postgres` and `secret` occur in many tracked files; 12 is longer than those words and shorter than any real key. The generated database password should be at least 24 characters (set in slice S1, not here). Not covered, by design: the reviewer password (no variable name in the pack), the owner credential (a libpq password file outside the repository), values split over lines, reversed or encoded, `.env.local`. Closed on 2026-11-13 by the owner's decision of that day: approved as proposed.
- OPTIONS: **Recommendation:** keep. Alternatives: a minimum of 8 (more collisions with words); judging short values by exact line match; also reading `.env.local`; a pre-push repeat of the guard.
- NEEDED BY: slice S0 gate.

## OI-93 — Which scanner owns which rule, and what none of them judges

- ID: OI-93
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that `scripts/check_docs.py` is the one owner of the identifier-number, path, address and secret-shape rules in the hooks, of the one-statement change to it, and of the listed limits.
- WHY: The pack places identifier-shaped numbers inside `scripts/check_docs.py` (TST-140 in docs/12_TESTING_AND_QUALITY.md; DAT-15 in docs/03_DATA_CONTRACTS.md) and lists it with gitleaks as the secret and identifier scanner run "pre-commit and every pull request" (docs/12_TESTING_AND_QUALITY.md, section "Test map by plane", row "Secret and identifier scan"); it does not say whether the hook runs it for the whole tree or for staged files, and it leaves real-name collisions to the world build (TST-143 in docs/12_TESTING_AND_QUALITY.md), SYN forms and canary markers to the release build and run time, and the forbidden-name registry to a file outside the repository that the script loads when present (docs/decisions/0012-neutral-source-labels-and-no-product-comparisons.md).
- DONE SO FAR: The hook runs the script unchanged except that a secret-shaped token is reported as `(matched text not shown)` instead of its first six characters (AGENTS.md rule 14). No rule is copied. Limits, stated and not closed: the script reads the work tree, not the index (the framework stashes ordinary unstaged edits; with the index flags assume-unchanged or skip-worktree it does not); it reads only a closed list of suffixes (so `.lock` files, `.cjs` files, files without a suffix and binaries are not judged); an eight- or eleven-digit run with a hyphen, colon, slash, comma, underscore, hash or dot-and-digit beside it, and runs of other lengths, are not flagged; it scans untracked files that git does not ignore, so a scratch file can fail a commit; a missing `EII_FORBIDDEN_PATTERNS_FILE` is ignored without a message; gitleaks skips binary files, does not flag a database URL and, because `.gitleaks.toml` extends the default configuration, inherits that configuration's global path list (images, fonts, documents and binaries, Go files, vendored and package folders, lock files, script libraries, Python trees and any path containing `gitleaks.toml`) and its global regex and stop-word lists, so a token-shaped value in such a path is not found, and a git attribute that marks a path binary hides that path from it; the guard still judges configured values in every path, and refusing those paths was not chosen because it would block an honest commit of an image or a lock file.
- OPTIONS: **Recommendation:** keep; a later task may widen the script (suffix list, neighbours, a staged-content mode). Alternatives: a second identifier scanner over staged blobs (a second owner of one rule); make the registry file mandatory.
- NEEDED BY: slice S0 gate.

## OI-94 — The scanner binary, its supply chain and the backstop

- ID: OI-94
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of how the pinned scanner is obtained and of what stands behind the hooks.
- WHY: The pack requires gitleaks in a pre-commit hook and in continuous integration over the full history, and requires secret scanning and push protection to be enabled (TST-141 in docs/12_TESTING_AND_QUALITY.md; OI-13); it names no install method, platform or cache path.
- DONE SO FAR: `scripts/hooks_gitleaks.py fetch` downloads the Linux x86-64 release archive of the version in `pins.toml` from GitHub (the release page and its asset host), checks the SHA-256 of the archive against a value written in the script, and installs the binary into `data/tools/gitleaks/<version>/` (uncommitted; a cache path in the sense of AGENTS.md rule 13). The release has no signature, only a checksum list from the same page, so the digest is pinned in the repository. Other platforms are refused. Every later run checks that the binary reports the pinned version and needs no network. The hook tests need the binary and are never skipped: until the one-time download has run, `./eii test` and the unittest command fail and name the command to run, so every continuous-integration job that runs `./eii test`, the suite `python-guards` or the unittest command must run `uv run --locked python scripts/hooks_gitleaks.py fetch` before the suite (TASKS.md, task S0-T07). Not closed, by design, because they go beyond the acceptance criteria (docs/decisions/0018-priorities-and-amendments-to-decision-0015.md, items 2 to 4): git attributes and textconv drivers that hide a staged token from the scanner, a `.gitleaksignore` file, `GITLEAKS_` environment variables, a second digest for the binary itself; they are entered in docs/17_DEPLOYMENT_HARDENING.md, section "Hardening register", by the follow-up task of the slice (TASKS.md, task S0-T15). The full-history scan belongs to S0-T07, push protection and secret scanning to S0-T14, and a clone where nobody ran the installer, or a commit made while skipping the hooks, is not judged by the hooks; the framework's store can hold the unstaged diff of tracked files as patch files.
- OPTIONS: **Recommendation:** keep. Alternatives: the framework's gitleaks hook (a Go toolchain and a 329 MB cache at first use); a package-manager install (a global install, not wanted); more platforms (each needs its own pinned digest).
- NEEDED BY: slice S0 gate.

## OI-95 — Required CI check names and workflow split

- ID: OI-95
- TYPE: CLOSED (was ASSUMPTION)
- NEEDED: Owner confirmation that the six required check names are `check-docs`, `static-checks`, `tests`, `secret-scan`, `planted-failures` and `sandbox proof`, split across `docs.yml`, `ci.yml` and `sandbox.yml`.
- WHY: The pack fixes the stages but not every workflow file name or required-check label.
- DONE SO FAR: Task S0-T07 uses the six names above. The repository-settings task may require exactly these names without changing their commands.
- OPTIONS: **Recommendation:** keep the names stable.
- NEEDED BY: S0-T14 and the slice S0 gate.
- CLOSED: 2026-11-13, by the owner's answer of 2026-11-12 on the repository settings (recorded in the task log of S0-T14 in [PROGRESS.md](PROGRESS.md)): the six names are the required checks of the ruleset `main-protection`, as task S0-T07 delivers them in `docs.yml`, `ci.yml` and `sandbox.yml`.

## OI-96 — Age of the places copy of decision 0019

- ID: OI-96
- TYPE: CLOSED (was ASSUMPTION)
- NEEDED: The owner to confirm that the newest release of the public copy of the places dataset, dated 2025-01-10, is the one used, or to supply a newer one.
- WHY: The places source `places_fsq` is fetched inside `./eii build-public` from the public copy on Source Cooperative (`https://data.source.coop/fused/fsq-os-places/`, host `data.source.coop`), which is read without an account; only the files that cover Qatar are fetched. Read on 2026-11-12, its README states the Apache License, Version 2.0 and the publisher's copyright line, and its listing holds three dated releases, the newest dated 2025-01-10, with no update rhythm stated. A newer release comes from the publisher's portal, which needs an account, and is the owner's choice ([decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 21).
- DONE SO FAR: The source `places_fsq` and its table `pub_place_fsq` are listed in [04_PUBLIC_DATA_PACK.md](docs/04_PUBLIC_DATA_PACK.md). Task S2-T15 builds the fetcher, the registry row that records the release used, the reviewed category mapping and the extended real-name collision checks; the places are shown with the date of that release. No variable is added for this source. The files that cover Qatar are assumed to be found through the dataset's own metadata file, which the task that builds the fetcher confirms.
- OPTIONS: **Recommendation:** use the release dated 2025-01-10 and show its date; a newer release is the owner's choice. Alternative: leave the source out and keep the other registered places data.
- NEEDED BY: slice S2 gate (S2-T15, PLN-25); not a blocker.
- CLOSED: 2026-11-12, by the owner's answer of that day, recorded in [decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 21: the copy dated 2025-01-10 is used for version 1 as it is and is shown with its date; where a place of the copy disagrees with OpenStreetMap or Overture, which are current, the newer source wins; no account is opened and no newer release is fetched for now.

## OI-97 — Public source for the survival base rate

- ID: OI-97
- TYPE: OPEN
- NEEDED: A Public table that links a licence cancellation to the issue of the same licence, or the owner's decision to leave the survival base rate out.
- WHY: The Public licence tables do not link a cancellation to its issue, so no survival base rate can be computed from them; card C31 returns `NO_DATA` with the reason `no_denominator` for it. The closure and entry base rates are flows over the published active stock of the same activity and geography, labelled approximate, each with its two counts and period ([decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 7).
- DONE SO FAR: Task S6-T15 builds the base rates of card C31 and promises no survival figure. No survival figure is computed from the Synthetic births and closures.
- OPTIONS: **Recommendation:** keep the survival base rate at `NO_DATA` until a Public source carries the link; invent no value. Alternative: leave the survival base rate out of the product.
- NEEDED BY: any proposal to show a survival base rate; not a version 1 blocker.
- UPDATE: 2026-11-13, by [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 12: the Synthetic births and closures are withdrawn. The openings and closures of register companies are Public counts from the register's own dates and monthly snapshots ([03_DATA_CONTRACTS.md](docs/03_DATA_CONTRACTS.md) DAT-164), and no rate, net change or survival figure is computed from them ([07_ECONOMIC_METHODS.md](docs/07_ECONOMIC_METHODS.md) MTH-85), so they do not close this item.

## OI-98 — Public source of each forecast series without a table

- ID: OI-98
- TYPE: OPEN
- NEEDED: For each series of the closed list of card C30 for which the public data pack holds no source table, the Public source (publisher, dataset or page, licence, retrieval date), or the owner's decision to leave the series out.
- WHY: A series is forecast only when the public data pack holds its source table, and a named series without one is listed as open ([decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 2). The list is licence issues and cancellations by activity and by the source's own area, property prices by district, hotel demand and room rates, consumer and producer prices, imports by product, announced investment by sector and the construction pipeline by municipality. Several series are short, and their forecasts return `NO_DATA` until the backtest minimum is met.
- DONE SO FAR: Task S2-T17 records, for each series, the source table that the pack holds or that it holds none; a series without a table is not forecast. The hotel series is also the open point of OI-21 and OI-23.
- OPTIONS: **Recommendation:** record each missing source at the slice S2 gate or keep the series open and unforecast; invent no value and add no source without its licence.
- NEEDED BY: slice S2 gate (S2-T17, PLN-25); slice S6 (S6-T14).
- UPDATE: 2026-11-13, by [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) items 8 and 12: the list gains the quarterly median price per square foot of method card C41 by district and use, a series of its own beside the property prices of card C14, whose table `pub_property_quarter` comes from the sales bulletins fetched in S2-T19 ([03_DATA_CONTRACTS.md](docs/03_DATA_CONTRACTS.md) DAT-167), so it is not a series without a table. The establishments of an area by month are now a Public count of register companies, not a released synthetic series; whether their forecast joins the list is fixed with the list at the slice that builds card C30 ([02_ARCHITECTURE.md](docs/02_ARCHITECTURE.md) ARC-138).
- UPDATE: 2026-11-14, by [decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md): The earlier licence condition is replaced: any source readable as a visitor under item 2 may be used, with the publisher's terms recorded in its own words with the date read and the basis of use in document 04. A source with no open licence covering the use uses `owner_decision`, the owner's decision for a personal, local project. Invent no value; a missing table or insufficient backtest still prevents a forecast (items 1 to 3).
- UPDATE: 2026-11-14, by decision 0026 item 3 and ruling L-221: `provider_terms` stays for a provider's interface used under that provider's own terms (PUB-95 and PUB-97); `owner_decision` applies to every other source with no open licence covering the use.


## OI-99 — The traffic provider's rule on storing responses

- ID: OI-99
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that nothing of a traffic-provider response is stored, and to read the provider's developer terms before any use that stores a response.
- WHY: The provider's developer terms page could not be read on 2026-11-12, so its rule on storing responses is not verified ([decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 17). The free allowance read that day is monthly (200,000 tile requests; 2,500 reachable-range requests).
- DONE SO FAR: Nothing of a response is written to disk, to the release, to the ledger or to a log; the run-time lineage keeps the request, the retrieval time and the response hash; no response is committed and every test uses hand-made fixtures. The provider is off by default, and no test, gate, command or the guided story needs it or its key (S6-T19).
- OPTIONS: **Recommendation:** keep storing nothing; read the developer terms when the owner has an account that can open them, and record the result here.
- NEEDED BY: any use of the provider that stores a response, and any public or commercial hosting.

## OI-100 — Sources that stay off under a public or commercial hosting

- ID: OI-100
- TYPE: OPEN
- NEEDED: Before the demonstrator is hosted publicly or for a commercial purpose, the owner to decide whether the traffic provider, the relative-busyness source `busy_gmaps` and the free weather interface `weather_openmeteo` may stay on.
- WHY: The provider's terms for that use are unread (OI-99), the relative-busyness source states no licence and its publisher's terms name automated reading, and the free weather interface is for non-commercial use ([decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), "What would change this decision").
- DONE SO FAR: Version 1 runs locally as a personal internal project; the three sources are used on the owner's decision of 2026-11-12 or within their free terms, and what a public or commercial hosting would have to settle for each is listed in the section "Public and investment sources if hosted publicly" of [17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md). The three sources stay off until the owner decides.
- OPTIONS: **Recommendation:** keep the three sources off under any public or commercial hosting until the owner records another choice in a decision record; a source whose terms, read at a fetch, forbid the use made here is switched off and the owner is told, except `busy_gmaps`, which the owner decided to use.
- NEEDED BY: any public or commercial hosting; not a version 1 blocker.
- UPDATE: 2026-11-14, by [decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md): The earlier local switch-off rule and the `busy_gmaps` exception are replaced: no source is switched off or limited in version 1 because of its terms. The publisher's actual terms, including those of `busy_gmaps`, are recorded in its own words with the date read in document 04; the earlier summary is not a finding that no terms exist. Document 17 keeps one list for every source whose terms require permission or a licence before real use, with the publisher's words and date read, filled as terms are read. Real use means access outside the owner's organisation, publication of a page showing source records or commercial use. Nothing on the list holds back version 1. The existing going-live rule for the three sources stays and points to that list (items 1 to 4).


## OI-101 — Size of the public-total inventory with the two gridded Public tables

- ID: OI-101
- TYPE: OPEN
- NEEDED: For the slice that builds the privacy engine, the size of the public-total inventory of PRV-115 once the rows of `pub_night_lights` and `pub_pop_agesex_grid` are in it, and whether that size is workable.
- WHY: The inventory holds one entry for every Public source, one for every row of every Public table and one for every complete category split ([06_PRIVACY_AND_DISCLOSURE_CONTROL.md](docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md), PRV-115). [Decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 20 and 22 add two gridded Public tables, `pub_night_lights` (by frame cell and month) and `pub_pop_agesex_grid` (by grid cell, age band and sex), whose rows join the inventory.
- DONE SO FAR: PRV-115 states how the rows of both tables are reviewed: the rows of `pub_night_lights` are `different_measure`, and the rows of `pub_pop_agesex_grid` are reviewed for applicability like population rows. No count of entries is stated.
- OPTIONS: **Recommendation:** the slice that builds the privacy engine (slice S5) counts the entries and records the size; the rule of PRV-115 is not weakened to shrink it.
- NEEDED BY: slice S5 (privacy engine).

## OI-102 — Subject of a Public series by district

- ID: OI-102
- TYPE: OPEN
- NEEDED: The subject of a forecast of a Public series on district geography (property prices by district), fixed at slice S2.
- WHY: The closed subject list of [09_AI_ASSISTANT.md](docs/09_AI_ASSISTANT.md) has no official district, and the series is on the source's own geography ([decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 2 and 5).
- DONE SO FAR: Documents 03, 08 and 09 carry the same OPEN line.
- OPTIONS: **Recommendation:** fix the subject at slice S2 together with documents 03, 08 and 09, without adding an attribute to a real place.
- NEEDED BY: slice S2 gate (S2-T17); slice S6 (S6-T14).
- UPDATE: 2026-11-13, by [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) items 6 and 8: the property price measures of method card C41 (the price per square foot by district, use and quarter, and its forecast) and the count of the financial centre's firms in a district where its register gives no building ([09_AI_ASSISTANT.md](docs/09_AI_ASSISTANT.md) AI-137) take the same subject once it is fixed, as the open questions of document 09 record; this also bears on S6-T10.

## OI-103 — Public build without the night-lights key

- ID: OI-103
- TYPE: OPEN
- NEEDED: For the task that builds the night-lights fetcher, whether absence of `EARTHDATA_API_KEY` produces a warning that names the key and the layer left out, or a silent omission of the night-lights layer.
- WHY: The night-lights source `ntl_blackmarble` is fetched with the Earthdata token inside `./eii build-public` ([decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) items 16 and 20). No test, gate, command or the guided story needs the key. `./eii build-public` must continue successfully without the night-lights layer when the key is absent, and exit 6 stays for an unavailable network only.
- DONE SO FAR: Preflight reports the key as `present` or `absent` and never prints it.
- OPTIONS: **Recommendation:** a warning line that names the key and the layer left out. The alternative is a silent omission of the layer. In both cases `build-public` continues successfully. Exit 6 stays for an unavailable network.
- NEEDED BY: the task that builds the night-lights fetcher (S2-T14).

## OI-104 — Full-history scanner count evidence

- ID: OI-104
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that a clean full-history scan must print one positive scanned-commit count within the git-derived bounds, with no scanner error line.
- WHY: The scanner can exit zero for an invalid revision or outside a repository.
- DONE SO FAR: `scripts/ci_history_scan.py` judges status, error lines, finding text and the count.
- OPTIONS: **Recommendation:** keep.
- NEEDED BY: the slice S0 gate.

## OI-105 — Planted-failure CI scope

- ID: OI-105
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that one planted case per CI guard listed by S0-T07 is sufficient at the foundation gate.
- WHY: Existing checks have their own detailed teeth; this job proves that the CI wiring blocks one violation of each listed guard.
- DONE SO FAR: The closed table has twelve cases and no mutant inventory.
- OPTIONS: **Recommendation:** keep the closed table and add a case only when CI adds a new guard.
- NEEDED BY: every later task that adds a CI guard.

## OI-106 — Complete test job repeats hosted sandbox setup

- ID: OI-106
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that the `tests` job repeats the hosted namespace setup because `./eii test` includes unskipped sandbox tests, while `sandbox proof` remains a separate required check.
- WHY: Removing sandbox tests from `./eii test` or skipping them would break TST-15 and TST-62.
- DONE SO FAR: Both jobs use the same existing setup commands; `sandbox.yml` is unchanged.
- OPTIONS: **Recommendation:** keep until the suite structure changes by an approved task.
- NEEDED BY: the slice S0 gate.

## OI-107 — Scanner git-attribute exposure

- ID: OI-107
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that S0-T07's full-history scan has the same git-attribute exposure as the S0-T06 staged scan.
- WHY: Neutralising local and repository git attributes is hardening beyond the two tasks' acceptance criteria.
- DONE SO FAR: The plan records the limit and sends the hardening item to the later deployment-hardening register through S0-T15.
- OPTIONS: **Recommendation:** keep the simple scan for the proof of concept.
- NEEDED BY: S0-T15 and any real-record deployment.

## OI-108 — Known ledger lines in the full-history scan

- ID: OI-108
- TYPE: CLOSED (was ASSUMPTION)
- NEEDED: Owner confirmation that the history scan leaves out findings on ledger lines it knows by exact content.
- WHY: the recorded command of S0-T05 in PROGRESS.md plants two dummy values, the scanner's general rule reports them, the history of the base branch is never rewritten and TST-141 requires the scan over the full history, which the foundation commit must pass.
- DONE SO FAR: `scripts/ci_history_scan.py` holds a closed `KNOWN_LINES` table with one entry keyed by file, rule and SHA-256 of the line text; the judge reads a temporary JSON report, leaves out only findings that match that line at the reported commit, prints counts when all findings are known and fails on every other finding; four tests plant the violations named in the task brief; no ignore file and no allow-list in the scanner's configuration; tests that plant a shaped token build the value at run time so a new ledger line would be judged like any other. Closed on 2026-11-13 by the owner's decision of that day: approved as proposed.
- OPTIONS: **Recommendation:** keep. Alternatives: an ignore file with commit fingerprints (the commit hook would honour it too, and it does not hold in a scratch copy); an allow-list in the scanner's configuration (the hook configuration of S0-T06 keeps none); scanning only the commits of the pull request (weaker than TST-141).
- NEEDED BY: slice S0 gate.

## OI-110 — Placement, row set and output readings of preflight

- ID: OI-110
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm or replace the placement and output readings of task S0-T08.
- WHY: `docs/08_BACKEND.md` section "Configuration and preflight" names the product preflight responsibility; `docs/13_DEPLOYMENT_AND_OPERATIONS.md` OPS-06 names the full table and line form; `TASKS.md S0-T08` scopes the probe modules and tests. The current product package has no API or configuration module.
- DONE SO FAR: The current implementation is `scripts/preflight.py` and its sibling modules. It prints `<PASS|WARN|FAIL> <check>: <reason>` and then `store: <postgres|embedded|none>`. Empty `EII_RELEASE_DIR` is unset; the four foundation rows are `WARN not_configured`. With a release path set, the release, receipt and embedded-reader rows fail as not built and replay warns as not built. An absent model key passes as absent. `./eii up` returns exit 4 when the release path is unset and invokes preflight with Docker probing disabled, so its PostgreSQL warning says `Docker not probed`. The offline lock row runs the locked `uv` and npm checks. The seventeen-row tuple also runs the Python and Node/npm pin checks from S0-T12 and the DuckDB-extension and bubblewrap checks from S0-T11, whose normal FAIL severity is unchanged in foundation mode, and the optional `traffic-provider-key` and `night-lights-key` rows: both report key presence as `present` or `absent`, the traffic row also reports `EII_TRAFFIC_PROVIDER` (default `simulated`, allowed `simulated` or `tomtom`) and fails an unknown setting with a fixed reason that never echoes its value, and neither row prints a key or contacts a provider or source host.
- OPTIONS: **Recommendation:** keep the current placement through slice S0 and move product-plane responsibility only in the slice that builds the API and configuration module. Keep `Docker not probed` for `./eii up`. Alternative: move the same complete row set with its tests when that product module is built.
- NEEDED BY: slice S0 gate.

## OI-111 — PostgreSQL client programs before the driver pin

- ID: OI-111
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that preflight continues to use the PostgreSQL client programs until slice S1 decides the driver pin.
- WHY: `docs/13_DEPLOYMENT_AND_OPERATIONS.md` section "Prerequisites and how each is checked" names `pg_isready` and a version query; `docs/02_ARCHITECTURE.md` section "Technology stack", row "PostgreSQL driver", leaves the driver to slice S1.
- DONE SO FAR: Preflight runs `pg_isready` and then one `psql` query. The password reaches only the `psql` child environment. A missing `pg_isready` or no answer selects embedded with a warning; an answering server whose checks cannot be completed is a failure, never a fallback. The S0-T08 task log records all four live tests against this project's service. Task S1-T05 installs the driver `psycopg` 3.3.8 through the root dependency group `engine` for the store spike; preflight still uses the client programs, and task S1-T08 confirms the driver's pin.
- OPTIONS: **Recommendation:** keep the client programs through slice S0 and decide together with the driver pin at slice S1. Alternative: a separately scoped dependency and licence change adds the driver earlier.
- NEEDED BY: slice S1 gate.

## OI-112 — Choices in the Compose file and database commands

- ID: OI-112
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm or replace the Compose choices not fixed by `docs/13_DEPLOYMENT_AND_OPERATIONS.md` section "Compose service definition (in words)".
- WHY: That section fixes six service elements but does not specify the interpolation name, project-name enforcement, secret-file creator or first-image installation path. `TASKS.md S0-T09` owns the database commands.
- DONE SO FAR: The required interpolation name `EII_COMPOSE_DB_PORT` carries the host port from `EII_DATABASE_URL` through a generated temporary file and is not read by the product. The Compose file names project `eii-poc`; `./eii db-up` and `./eii db-down` also pass `-p eii-poc`. A test refuses `infra/.env`. Both commands require `data/compose/postgres_superuser_password` to be a regular file, never create it and never print its contents. The image uses `pull_policy: never`, so it must already be present. The file does not set `POSTGRES_DB`.
- OPTIONS: **Recommendation:** keep these choices; the owner creates the uncommitted secret file and arranges the pinned image before the first start. Alternative: a later operations decision defines another installation path without weakening the digest pin.
- NEEDED BY: slice S1 gate.

## OI-113 — A dependency alert on a development-only package of the web lock file

- ID: OI-113
- TYPE: OPEN
- NEEDED: The owner to say whether the lock file is raised before the slice S0 gate or with the next change of the web dependencies.
- WHY: GitHub reports one open alert of medium severity for the package `minimatch` in `web/package-lock.json` (a possible denial of service through a pattern; fixed in its version 11.0.1). The package is a transitive dependency of the lint tools, in development scope only: it runs on the build machine and in CI and is never served.
- DONE SO FAR: Nothing is changed. A lock file changes only inside a task that owns it, and `npm install --package-lock-only` runs only after a change to `web/package.json` (rule 44 of [AGENTS.md](AGENTS.md)). Tasks S1-T01 and S1-T02 changed the web dependencies (2026-11-13), and the lock file was read again: the package is at 10.2.6 and is needed only by the lint tool and its TypeScript parser, which accept the 10 series only, so no change of the lock file within their ranges reaches the fixed release 11.0.1. The alert stays open; task S1-T08 looks at it again when it confirms the pins.
- OPTIONS: **Recommendation:** raise it in the follow-up task of the slice if a fixed version resolves without a change of the pinned lint tools; otherwise with the first task that changes the web dependencies. Alternative: leave it until slice S1 confirms the web pins.
- NEEDED BY: slice S1 gate; not a blocker.

## OI-114 — A default of the service in the ruleset that the owner's table did not name

- ID: OI-114
- TYPE: ASSUMPTION
- NEEDED: The owner to note it, and to decide it again if a non-zero number of approving reviews is ever required.
- WHY: The ruleset `main-protection` of the base branch was created from the owner-approved body (task S0-T14). The service returns one further parameter of its pull-request rule that the body did not send, `require_extra_approval_for_unattributed_changes`, with the value true. GitHub's documentation (the REST reference of repository rules and the page on the available rules for rulesets, read on 2026-11-13) says: "When Copilot opens a pull request without a human collaborator, require one more approving review if a non-zero approval count is required"; the setting is enabled by default and has no effect if the ruleset requires zero approvals.
- DONE SO FAR: The ruleset requires zero approving reviews, so the parameter changes nothing; it is recorded with the ruleset's answer in [PROGRESS.md](PROGRESS.md). No call was made to change it: the task changes nothing outside the owner's table.
- OPTIONS: **Recommendation:** leave it. Alternative: a later owner-approved settings task sets it to false.
- NEEDED BY: any change of the required number of approving reviews; not a blocker.

## OI-115 — The browser half of FE-56 is carried by the map spikes

- ID: OI-115
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that the browser-level test of FE-56 is carried by the tasks that render a map and is checked at the slice S1 gate.
- WHY: FE-56 spans the server and the browser: with the network disabled except for the local server every layer renders, and an end-to-end test blocks every non-same-origin request. Task S1-T04 serves one tile artefact and renders no map; the browser tool is installed by task S1-T01 (OI-48).
- DONE SO FAR: Task S1-T04 proves the server's half over HTTP on the loopback interface: `test_the_api_app_serves_the_tile_and_the_status` in `product/tests/test_tiles_range.py` finds no cross-origin permission header, no redirect and no absolute address in a tile response, and the same check fails against an application built in the test with a wildcard cross-origin header.
- OPTIONS: **Recommendation:** the slice S1 gate checks the browser half on the pages of tasks S1-T01 and S1-T02; the run with the live traffic provider on waits for the task that builds the provider's adapter (S6-T19). Alternative: a decision record narrows FE-56 for slice S1.
- NEEDED BY: slice S1 gate.

## OI-116 — The server packages of the API are installed through the root development group

- ID: OI-116
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that `fastapi` and `uvicorn` stay in the root dependency group `dev` until task S3-T08 builds the API and declares them in the product manifest, and to confirm `uvicorn` as the server program that runs the FastAPI process.
- WHY: `eii_product.api` imports FastAPI, and the product manifest declares `eii_core` only: the clean-environment guard of task S0-T02 installs the three packages offline from an empty cache, so a member manifest cannot gain a third-party dependency in this slice (OI-60). The technology stack of `docs/02_ARCHITECTURE.md` names FastAPI and no server program, and the tests of the spike need one to speak HTTP to a real process.
- DONE SO FAR: Both packages are pinned exactly in the root group `dev` and recorded in `pins.toml`: `fastapi` in the series the pack names, `uvicorn` with the label ASSUMPTION at the release that was current on 2026-11-13. `import eii_product` stays free of FastAPI; only `eii_product.api` imports it. The rows `pmtiles` and `@protomaps/basemaps` of `pins.toml` name S1-T04 as their first use; this task installs neither, because it serves a synthetic byte artefact and renders no map.
- OPTIONS: **Recommendation:** keep both packages in the root group through slice S1; task S3-T08 declares them in `product/pyproject.toml` together with the change of the clean-environment guard; task S1-T08 confirms the two pins and corrects the first use of the two map rows. Alternative: a decision record names another server program.
- NEEDED BY: slice S1 pin confirmation (S1-T08); task S3-T08.
- UPDATE: 2026-11-14, by task S1-T10 (PO-S1-06): the same kind of gap holds for `pyvalhalla` and `h3`, which the areas spike of the product imports. Task S3-T04 declares both in `product/pyproject.toml` together with the change of the clean-environment guard; until then both stay in the root group `engine` under OI-60. This adds no answer to the NEEDED above. The earlier text is kept.

## OI-117 — A refused gateway request leaves no decision record, and run records are not committed by default

- ID: OI-117
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm two readings of the record contract that the gateway of task S1-T07 implements, or to replace either.
- WHY: Item 6 of [decision 0014](docs/decisions/0014-typed-decision-gateway.md) says that every call writes a decision record, and its item 8 says that the gateway code refuses every input class but the four cleared ones. The closed record schema of `docs/03_DATA_CONTRACTS.md` (section 12.1, DAT-126) admits only those four classes in `input_class`, so a refused class cannot be written without a false label, and a hash of refused text would itself be a trace of it. The same schema lists the outcome `BLOCKED_BY_DATA_POLICY`. The pack does not say whether the records of an offline run are committed.
- DONE SO FAR: The lead ruled on 2026-11-13 that a refused request is not a call. The gateway raises `DataPolicyBlocked` with the text `BLOCKED_BY_DATA_POLICY` before a provider is constructed and before anything is stored: for a declared input class outside the four, and for a cleared class that the decision class does not accept (`question_route` and `router_miss_finder` take team questions only, `string_parity` project text only). No record holds that outcome in version 1; every admitted call writes one record. Files under `evals/typed_decisions/runs/` are ignored by git, so the output of a run is committed only by a deliberate act; the tests write under temporary folders.
- OPTIONS: **Recommendation:** keep both readings. Alternative for the first: a request in a cleared class that its decision class does not accept writes a record with the outcome `BLOCKED_BY_DATA_POLICY`, with a rule that such a record is never replayed from the memo. Alternative for the second: the records of named runs are committed as evidence.
- NEEDED BY: slice S1 gate; the requalification of task S1-T08.

## OI-118 — The map label fonts of the glyph spike and where its browser lives

- ID: OI-118
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm the two packages that carry the map label fonts, `@fontsource/noto-sans` and `@fontsource/noto-sans-arabic` at 5.3.0, with no written retreat; and that the browser of the tests is the headless shell of the pinned browser tool, fetched once into the uncommitted folder `data/tools/playwright/`.
- WHY: The pack names the faces of the basemap labels (`docs/10_FRONTEND.md`, section "The basemap") and names neither a package for them nor a retreat. It names the browser tool for end-to-end tests (`docs/10_FRONTEND.md`, section "Testing") and no place for its browser. A browser kept inside the installed package folder is deleted by every `npm ci`.
- DONE SO FAR: Both font packages are pinned exactly in `web/package.json` and recorded in `pins.toml` with the label ASSUMPTION; the registry's record, read on 2026-11-13, shows 5.3.0 published on 2026-07-19. `npm run spike:glyphs:install-browser` fetches the headless shell, with the media library the tool attaches to it, into `data/tools/playwright/`; it installs system libraries only in the CI environment and changes nothing outside the repository on any other machine. A missing browser fails the tests and names the command.
- OPTIONS: **Recommendation:** keep both. Alternatives: other font packages or a written retreat, by a decision record; the full browser build beside the shell.
- NEEDED BY: slice S1 pin confirmation (S1-T08); slice S3, the first product screen with a map.

## OI-119 — The pixel comparison runs in the hosted job only

- ID: OI-119
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm the reading of TST-91 and TST-92 that the glyph spike implements.
- WHY: TST-91 says that screenshot baselines are committed and generated only in the CI environment, because rendering varies with host, browser and hardware, and TST-92 that a baseline change is a commit of its own. The pack does not say whether `./eii test` on the build machine compares pixels.
- DONE SO FAR: The three screenshot tests run their structural, request and font assertions everywhere, inside `./eii test` too. Pixels are compared only by the hosted job `tests`, in a step of its own, against the baselines under `web/spikes/glyphs/tests/baselines/`. The same job first makes the three captures with the suite's own capture and uploads them; the lead commits them as baselines in a commit of their own. A missing or differing baseline fails the hosted step and names the file. The owner's native reading of the five Arabic names and the three images is recorded in `web/spikes/glyphs/evidence/visual-review.md`, which says pending until then.
- OPTIONS: **Recommendation:** keep. Alternative: compare pixels on the build machine too, with a second set of baselines made there.
- NEEDED BY: slice S1 gate (FE-46, FE-57).
- UPDATE: 2026-11-14, by task S1-T10 (item I8): the five place identifiers and English names of the glyph spike are renamed (alif, ba, jim, dal and ha); the five Arabic strings are unchanged. Every machine-read review mark stays `pending native review`, because the evidence judge accepts a name's approval only together with the review of its image; the spike's README states the owner's approval of the five Arabic strings of 2026-11-13 (FE-57) in prose. The English baseline image is recaptured by the hosted job of pull request 46 and committed in a commit of its own. The review of the three images is still open. The earlier text is kept.

## OI-120 — The hour mechanism of drive areas and two choices of the routing spike

- ID: OI-120
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm the mechanism that the routing spike chose for SYN-53, which the lead writes into a decision record at the slice S1 gate; and two smaller choices: `shapely` as a dependency of the spike's tests only, and the type check following the routing engine's own type files.
- WHY: SYN-53 leaves the choice to slice S1 ("time-dependent edge speeds in the routing engine, or per-edge scaling of edge times"). ARC-88 names pyvalhalla as the engine that routes in process; the technology stack names another library only as a retreat "chosen in writing at slice S1 only if needed". The pack names no geometry library for tests, and the routing package ships type files without the marker that makes a type checker read them.
- DONE SO FAR: Task S1-T03 routes in process with pyvalhalla 3.9.1 on a synthetic road extract that its own generator writes; the retreat was not needed and is not installed. Routing tiles are built by the builder program that the package ships (about a quarter of a second for the fixture). The hour of day is handled by per-edge scaling: one set of tiles for each distinct hourly speed factor, built from the same extract with every way's speed multiplied by the factor; equal factors share one set. Measured on the fixture: the drive area changes with the factor, equal factors give equal areas, the walk area does not change. Predicted speeds inside the engine were tried first and are not used: with a departure time the engine answered without a timezone database, but two hours with the same factor gave different outlines, and the cause is not confirmed. `shapely` 2.2.0 (the registry's current release on 2026-11-13) is installed through the root dependency group `engine` and imported only by the spike's tests, for geometric assertions that do not come from the engine. The type check reads the engine's shipped type files through one setting for that package; no error is suppressed. Task S1-T11 carried the mechanism from one factor for all links to a speed for each link: one routing graph for each distinct set of whole link speeds, six for the 24 hours of its fixture day, with equal sets giving equal areas at every pair of hours. [Decision 0021](docs/decisions/0021-one-speed-for-a-link-and-an-hour.md) records the mechanism with the owner's rule of 2026-11-13 on one speed for a link and an hour.
- OPTIONS: **Recommendation:** keep all three; a release has one routing graph for each distinct set of whole link speeds among its hours, day types and summer settings, and one for each situation (decision 0021). Alternatives: predicted speeds inside the engine, once the difference for equal factors is understood and a timezone database is part of the build; a pure-Python containment test instead of `shapely`.
- NEEDED BY: slice S1 gate (the decision record of SYN-53); task S1-T11.

## OI-121 — The pixel-ratio cap of the map canvas in the performance spike

- ID: OI-121
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm or replace the cap of the map canvas at 1 device pixel for each CSS pixel on the wall canvas of 1920 by 1080.
- WHY: FE-71 and DES-139 leave the value of the pixel-ratio cap to the frame-rate spike. The gate of task S1-T02 is measured at one cap; searching for a cap that passes would change the measurement.
- DONE SO FAR: The page sets the cap to 1 through the map's own pixel ratio, labels it ASSUMPTION, records it on every trace and does not search it; text stays at the display's own pixel ratio. In the browser tests the drawing buffer is 1920 by 1080 at a device pixel ratio of 2. The reference notes say that the cap reaches the overlay through another property; in the interleaved mode this project uses, the map owns the canvas and the map's pixel ratio is what the buffer followed (measured; task S1-T08 corrects the notes).
- OPTIONS: **Recommendation:** keep the cap at 1 until a native trace of task S1-T12 passes or fails with it; if it fails, FE-89 and the retreat pins decide what is tried, and the sizes are never reduced.
- NEEDED BY: task S1-T12 (the native trace); slice S1 pin confirmation (S1-T08).
- UPDATE: 2026-11-15, by S1-T12 (pull request https://github.com/albarami/economic-investment-intelligence/pull/55 ): the native traces were taken with the cap at 1, on a display with a device pixel ratio of 1.125; each trace records the cap, its label ASSUMPTION and a drawing buffer of 1920 by 1080. With this cap the gate's load of 110,000 hexagons and 50,000 particles passed its named test (share of frame intervals under 16.7 ms 0.9611 against the minimum of 0.95). The condition of the recommendation is met on the passing side: the cap stays at 1, no other cap was tried, and neither FE-89 nor a retreat pin is called on. The two road sets were recorded at the same cap with shares of 0.8961 and 0.9017; no bound applies to them. The traces say nothing about a display with a higher pixel ratio. The item stays an assumption: the owner confirms or replaces the value.

## OI-122 — The native frame-rate traces are a task of their own and wait for one action of the owner

- ID: OI-122
- TYPE: CLOSED (was ASSUMPTION)
- NEEDED: The owner to take the trace (the steps are in `web/spikes/performance/README.md`). The re-plan that makes the two native traces task S1-T12 was accepted by the owner on 2026-11-13, as a stated assumption of the proof of concept.
- WHY: TST-132 asks that the frame-rate check is measured in a browser that runs natively on the host of the build machine, because a browser inside WSL can fall back to software rendering. The build agents do not start programs of the host. The third criterion of S1-T02 and the fifth of S1-T11 therefore need a person, and they would hold both spikes unmerged while everything else of them is built, tested and reviewed.
- DONE SO FAR: A re-plan of 2026-11-13, made with the pull request of S1-T02: the two criteria moved word for word to the new task S1-T12, which depends on S1-T02 and S1-T11; S1-T08 depends on S1-T12 as well, so the pins that the frame rate decides (FE-89) are not confirmed before the traces exist. The slice S1 gate is unchanged: it still needs the frame-rate statement. The page records the trace by itself; the evidence command passes only on a committed native trace of the gate profile with a hardware renderer and at least 95% of frames under 16.7 ms, and it fails with `missing-native-trace` until then. No placeholder trace exists and nothing is claimed. Changed by a further re-plan of 2026-11-13, entered with the pull request of S1-T13 (the owner's note that he reaches the workstation only through Remote Desktop until Sunday 15 November, which holds Windows to 30 frames a second): S1-T12 waits for the owner at the console; S1-T08 and S1-T10 no longer depend on it; the pin fields that the frame rate decides (FE-89) stay open in S1-T08 and close with the addendum of the slice S1 gate, whose record names the native trace as its one open item. The serve command's server could not store the owner's first trace; task S1-T13 fixed it.
- OPTIONS: **Recommendation:** keep the re-plan; the owner runs `npm --prefix web run spike:performance:serve` from the repository root, opens the printed address in Chrome or Edge on Windows and leaves the page open until it shows a path; the lead then commits the trace with its capture record. Alternative: the owner allows the build to start the host browser itself with a temporary profile.
- NEEDED BY: the addendum of the slice S1 gate (through S1-T12), and before any slice S3 task that depends on map performance is reviewed.
- CLOSED: 2026-11-15, by S1-T12 (pull request https://github.com/albarami/economic-investment-intelligence/pull/55 ): the owner took the three traces at the console on 2026-11-15, in Chrome running natively on the host of the build machine, on the page of main `a8a99dd94c30e3c5e3522d18f90c0edc14646f3e`, which is cross-origin isolated since task S1-T18. The three traces and their capture records are committed under `web/spikes/performance/evidence/`. The evidence command passes on the original layer set (1,800 frames; share of frame intervals under 16.7 ms 0.9611 against the minimum of 0.95) and records the two road sets (shares 0.8961 and 0.9017, both under 0.95; the command sets no minimum for a road set, and no pass is claimed for one). The first traces of the same day, taken on the coarse clock before S1-T18, are not committed and are not evidence. The addendum of the slice S1 gate stands in PROGRESS.md with the ledger of S1-T12; the gate's verdict waits for one reviewer's confirmation of it. The pin fields that the frame rate decides are answered in that addendum; their rows in `pins.toml` and `web/REFERENCE_NOTES.md` are not changed by it.

## OI-123 — The version-1 parameters of the traffic assignment, fixed at slice S1 with their sources

- ID: OI-123
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm the values below, or to name other values with their sources, before slice S5 builds traffic; and to confirm the rules that [decision 0021](docs/decisions/0021-one-speed-for-a-link-and-an-hour.md) adds to his speed floor as the lead's own: the method's whole speed for a link and an hour (item 2); one length, the routing graph's whole metres (item 4); the loading distance on a sphere and the tie rules (item 5); the printed resolution, the rounding and the refusals of a route (item 6); and the whole speed of a link in a dial situation (item 8), which changes the situation fixture of MTH-90. The speed floor and the itemised turns at junctions are the owner's decisions and need no confirmation. After the first traffic build a change needs a new method version (MTH-04, MTH-89).
- WHY: Card C25 of `docs/07_ECONOMIC_METHODS.md` and MTH-89 ask that α, β, the free-flow speeds, the capacities and the number and edges of the volume bands are fixed at slice S1, with their sources, before any traffic is built, and never tuned to a published figure. The card named no value. The routing engine stores a link's speed as a whole number of km/h and drops a fraction, so without a whole speed made by the method a user would see two speeds or two times for one link and hour, which the owner's rule of 2026-11-13 forbids.
- DONE SO FAR: Task S1-T11 fixed the values in the parameter file of the assignment spike, each with its source, the date it was read (2026-11-13) and its status. α 0.15 and β 4: the standard values of the volume-delay form of the Bureau of Public Roads (1964), as an open textbook of network analysis states them (Boyles, Lownes and Unnikrishnan, Transportation Network Analysis, Volume I, section 1.5.1). Free-flow speed by road class, in kilometres per hour: motorway 105, trunk 90, primary 75, secondary 60, tertiary 50, residential 35: the routing engine's own default for a road without a posted speed (the table `default_speed` of the file `lua/graph.lua` in the engine's source repository, and measured on the installed engine), so that free-flow drive times and the assignment agree. Capacity by road class, in vehicle trips per hour for one direction: motorway 4000, trunk 2000, primary 1500, secondary 1000, tertiary 600, residential 600: the default lanes in each direction times the default capacity per lane of the OpenStreetMap network reader of the open-source transport simulation MATSim (ASSUMPTION: a published default table, not measured for Qatar; one capacity for each class, because a road link of the data contract has no lane count). Volume bands: four, with the edges 0.85, 0.95 and 1.00, from Table 3-2 of chapter 3 of the Traffic Signal Timing Manual of the Federal Highway Administration (ASSUMPTION: thresholds published for signalised intersections, applied to road links as display bands). The speed floor is 10 kilometres per hour, by the owner's decision of 2026-11-13. The method makes one whole speed for a link and an hour, the larger of the floor and the rule's speed rounded half-up, times each link by its length over that speed, and releases the ratio of that speed to the free-flow speed rounded half-up to three decimals; the product reads the whole speed back exactly from the released ratio (tested for every whole speed from the floor to each class speed) and refuses a file of rows whose ratio gives back less than the floor or is not the rounded ratio of a whole speed. On the spike's fixture day two link-hours are at the floor by the rule, and four released rows give a whole speed of 10. A dial situation's link takes the speed of its length over the mean of its hourly times, rounded half-up to a whole km/h, so MTH-90's situation fixture becomes 53 km/h and 600/53 minutes. The spike routed between nodes only: how the end links of a route from a point inside a link are timed (an area's pin, a gateway) is left to the slice S3 task that shows such routes, in writing. The engine's turn costs at junctions are kept: a route shows its link times and one line for the turns, and a drive-time area's legend says once that it includes them; the differences between the engine and the method that the spike measured are pinned in tests and stated on card C25 as limits (decision 0021 item 9). Four rules of the spike's own, for task S5-T09 to keep or to change in writing: β is a positive whole number, because the assignment is computed in exact arithmetic; an hour is a whole number from 0 to 23, and text, decimal and boolean values are refused; identifiers are ordered as text by code point, so `SYN-N-0-10` comes before `SYN-N-0-9`, and the real graph needs its own fixed identifier order; trips between two different units that load at the same node stay off the network, like trips within one unit. The spike finds the links of an engine route from the vertices of the route's shape, which holds on its straight synthetic links only; the real graph needs the engine's edge identifiers. By the owner's decision of 2026-11-13, a link's capacity will be the capacity of one lane of its class times the link's lanes in one direction, read from the road extract (a link without a lanes tag taking its class's median); the amendment of decision 0021, card C25 and the road_link contract enters with task S5-T09, before any traffic is built; the values above stand until then.
- OPTIONS: **Recommendation:** confirm the values and the rules as fixed; decision 0021 records them. Alternatives: the owner or a transport authority supplies free-flow speeds and capacities for Qatar's road classes, with their source, before slice S5; for a situation, the exact mean time instead of the whole speed, with a mark on the screen wherever the engine's time is shown beside it.
- NEEDED BY: the slice S1 gate; task S5-T09.

## OI-125 — One random failure of the performance page's smoke orbit

- ID: OI-125
- TYPE: OPEN
- NEEDED: The cause of one failure of the browser test of the performance page's smoke orbit, or a record that it did not recur over a stated number of runs.
- WHY: AGENTS.md rule 39: a random failure is recorded, and a green re-run alone does not close it.
- DONE SO FAR: During task S1-T13 (2026-11-13), the builder's browser run of the smoke orbit, before its page change, failed once on the existing assertion that the map's bearing at the end of the orbit differs from its bearing at the start: both were 0. The same test passed on the immediate re-run and in every later full run of that task, including the lead's runs at the work commit. No code was changed because of it. A smoke orbit lasts 400 milliseconds in a headless browser that draws in software; a camera that has not yet moved by the end of so short an orbit would give exactly this result.
- OPTIONS: **Recommendation:** count the failures of this assertion over the next ten local runs of the spike's tests and record the count here; if it recurs, make the smoke orbit wait for the first camera movement before it ends, never loosen the assertion.
- NEEDED BY: the slice S1 gate.

## OI-126 — Two dependency alerts on runtime packages that the map layers of the performance spike bring in

- ID: OI-126
- TYPE: OPEN
- NEEDED: A decision, in task S1-T08's confirmation of the web pins, on each of two alerts: raise the package through the lock file, or keep the alert open with its reason recorded.
- WHY: GitHub opened two alerts on main on 2026-11-13, when pull request 34 (task S1-T02) merged: `image-size` 0.7.4, severity high (its parser of one icon format can loop without end on a crafted file; versions from 0.6.3 to 2.0.2 are affected, fixed in 2.0.3), and `fflate` 0.7.4, severity medium (its unzip function can loop without end on a malformed archive; versions from 0.7.0 below 0.7.5 are affected, fixed in 0.7.5). Both are transitive dependencies of `@deck.gl/geo-layers` 9.4.1 in `web/package-lock.json`, in runtime scope: `fflate` through `@loaders.gl/3d-tiles` and `@loaders.gl/compression` 4.5.4, which asks for exactly 0.7.4; `image-size` through `@luma.gl/gltf`, `@loaders.gl/textures` 4.4.5 and `texture-compressor` 1.0.2, which accepts the 0.7 series only. The spike uses the hexagon layer of that package; it loads no tile set, model, compressed texture or archive.
- DONE SO FAR: Nothing is changed; a lock file changes only inside a task that owns it (rule 44 of [AGENTS.md](AGENTS.md)). Neither fixed release lies inside the range its parent asks for, so raising either needs an override in `web/package.json`. The built page of the application shell was searched for both packages and holds neither; the spike's own built page was not searched. On 2026-11-14 task S1-T08 built the performance spike's page with the spike's own build helper and searched its four files for `fflate`, `image-size` and one message string of each parser; none matched (a search of minified text, not proof that no parser code is present). It added the exact override of `fflate` 0.7.5 in `web/package.json`; the lock file changed only that package's version, address and integrity value; the spike's Node and browser tests, the glyph tests, lint, the type check, the production build and the host checks passed with it, so the override is kept and the `fflate` alert is answered. No override of `image-size` was made: its fixed release is a new major version outside the series its parent accepts, and the spike loads no texture image; that alert stays open until the loaders are upgraded or replaced and tested.
- OPTIONS: **Recommendation:** in task S1-T08, search the spike's built page for both parsers; raise `fflate` to 0.7.5 by an override if the spike's tests stay green with it; keep the `image-size` alert open with its reason (no page loads a texture image; its fixed release is a new major version that its parent does not accept) unless a test shows the override harmless. Alternative: leave both until the map layers of slice S3 choose their loaders.
- NEEDED BY: slice S1 gate; not a blocker.

## OI-132 — The satellite imagery provider's attribution in committed text

- ID: OI-132
- TYPE: PENDING (was OPEN (owner))
- NEEDED: The owner's attribution note for the imagery provider whose key is `ESRI_API_KEY`: how the provider may be named in committed text and on screen, and the wording of its credit.
- WHY: [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item A7 adds a satellite mode that shows the provider's satellite imagery with the attribution its imagery style carries, and AGENTS.md rules 5 and 15 ask for every source to be cited and for no existing product to be named in comparison. Until the note is in force, committed text names the provider only "the imagery provider" or by its setting.
- DONE SO FAR: Document 04 records, under its source registry, that the provider's row is added when the note is in force; document 13 holds the setting (OPS-73); documents 10 and 11 show the satellite credits only inside the collapsed map credits while that mode is on.
- OPTIONS: **Recommendation:** keep the provider unnamed in committed text; take the credit at run time from the provider's imagery style and show it only inside the collapsed map credits while the satellite mode is on; add the registry row of document 04 when the owner's note is in force.
- NEEDED BY: task S3-T16 (the satellite mode).
- UPDATE: 2026-11-14. The owner's attribution note is received. Ruling L-151 records that note and its permitted locations; the owner question is no longer awaited. What remains is the documentation guard's exception. The D0023 entry of PROGRESS.md names task S1-T14 as the work that builds that exception and adds the provider's name in its two allowed places. The earlier text is kept.

## OI-133 — Whether road traffic is part of the movement source

- ID: OI-133
- TYPE: OPEN (owner)
- NEEDED: The owner's confirmation that the road traffic of method card C25 (the hourly link volumes, speed ratios and drive times by hour) is kept as part of the movement source.
- WHY: [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 12 builds synthetic records only for the confirmed sources; it keeps the road traffic of card C25 as part of the movement source and asks the owner to confirm. The lead's audit gave three options: derive traffic from the movement sources by the same assignment (it needs the open rule that turns trips into vehicle trips, document 05 Q7, and keeps capacities and delay parameters as assumptions); the optional live traffic provider of decision 0019 (it stores nothing and can fill no hourly table, ranking or travel time by hour); or keep the assignment as a method test only and show Public drive times at free flow, leaving out hour-varying drive times, the traffic animation and hourly access scores.
- DONE SO FAR: The decision keeps the first option until the owner answers. The S1-T11 spike assigns a synthetic flow fixture and is unaffected.
- OPTIONS: **Recommendation:** keep traffic as part of the movement source, derived from the released hourly flows, with the trips-to-vehicles rule stated as an assumption; if the owner declines, fall back to free-flow drive times and drop the hour-varying parts.
- NEEDED BY: the slice S4 gate (S4-T08); it bears on S5-T09, S6-T07, S6-T08, S6-T13, S6-T20, S7-T11 and S10-T03.

## OI-134 — The attributes of the movement records: age, nationality and gender

- ID: OI-134
- TYPE: CLOSED (was OPEN)
- NEEDED: Which of age, nationality and gender the confirmed movement sources (the mobile operator's presence data and the national crowd-management system's data) hold, at the grain the pack plans.
- WHY: Under [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 12, synthetic records follow the real formats and an attribute the confirmed source does not plausibly hold is not generated. AGENTS.md rule 10 bars any sex or gender attribute on synthetic or protected records, and nationality enters only in the two forms of decision 0022.
- DONE SO FAR: No movement contract of document 03 carries any of the three. The lead's audit found no sex or gender attribute planned inside a confirmed source; a real-data adapter must drop such a column before the vault, and the conformance schema test already refuses one.
- OPTIONS: **Recommendation:** generate none of the three on movement records. Gender stays barred whatever the source holds. Age or nationality on movement records would need the owner's confirmation that the source holds them and, for nationality, a new decision record amending rule 10.
- NEEDED BY: the slice S4 contracts (S4-T01, S4-T04).
- UPDATE: 2026-11-14, by the owner's words and his advisor's decision under his delegation, recorded in [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 16: movement aggregates carry age band, gender and nationality group as one-way splits. The bar on sex or gender still holds for the worker, residence and company records and for anything derived from them; movement aggregates are the one exception. The age bands are confirmed against the operator's format when its data arrives (OI-148), which is not an owner question.
- CLOSED: 2026-11-14, by decision 0023 item 16. The earlier text is kept.

## OI-135 — Hiring and leaving flows (the decision question bank's gap N1)

- ID: OI-135
- TYPE: OPEN (owner)
- NEEDED: The owner's word on whether hiring and leaving flows are built, and how, in the session on the design of value extraction.
- WHY: [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) items A9 and A10 record them as a gap of the question bank and as an analysis that waits for that session; no machine-learning work is added beyond the plan's tested forecasts, estimates and ranking.
- DONE SO FAR: Not built. The questions of the bank that need them are recorded as gaps (AI-129).
- OPTIONS: **Recommendation:** leave them out of version 1 until the owner's session decides; any later build is an analysis of the attached employment records released under document 06.
- NEEDED BY: the owner's session on value extraction.

## OI-136 — Rents (the decision question bank's gap N3)

- ID: OI-136
- TYPE: OPEN (owner)
- NEEDED: The owner's word on a source of rents, or a confirmation that rents stay the user's own input.
- WHY: No open rent source exists (document 04 section 12). [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 12 forbids synthetic rents or tenancies; the 2026 guide land prices and the recorded sale prices are prices and are never relabelled as rents.
- DONE SO FAR: Break-even and the "how sure" runs of S6-T21 take only the user's own rent, or the guide and recorded prices labelled as prices.
- OPTIONS: **Recommendation:** keep the user's rent as the only rent in version 1.
- NEEDED BY: before any rent figure is offered.

## OI-137 — An events calendar (the decision question bank's gap N4)

- ID: OI-137
- TYPE: OPEN (owner)
- NEEDED: The owner's word on a public source of an events calendar.
- WHY: [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item A9 records it as a gap that waits for the owner's word and is not built now.
- DONE SO FAR: The simulation keeps its three event days of document 05; no calendar of named events is shown.
- OPTIONS: **Recommendation:** leave it out until a public source is named and registered in document 04.
- NEEDED BY: before any question of the bank that needs it is answered.

## OI-138 — Supplier certifications (the decision question bank's gap N6)

- ID: OI-138
- TYPE: OPEN (owner)
- NEEDED: The owner's word on a public source of supplier certifications.
- WHY: [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item A9 records it as a gap that waits for the owner's word and is not built now; no synthetic data stands in for it (item 12).
- DONE SO FAR: The partner and supplier finder shows no certification; the structured qualification route stays as document 09 states it.
- OPTIONS: **Recommendation:** leave it out until a public source is named and registered in document 04.
- NEEDED BY: before any question of the bank that needs it is answered.

## OI-139 — School capacity (the decision question bank's gap N7)

- ID: OI-139
- TYPE: OPEN (owner)
- NEEDED: The owner's word on a public source of school capacity.
- WHY: [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 12 forbids synthetic school capacity, and item A9 records it as a gap that waits for the owner's word.
- DONE SO FAR: Only the published students by municipality (`students_muni`) are shown, as Public facts with source and year.
- OPTIONS: **Recommendation:** leave it out until a public source is named and registered in document 04.
- NEEDED BY: before any question of the bank that needs it is answered.

## OI-140 — Whether the competition-adjusted ratio of talent available near this site may be computed

- ID: OI-140
- TYPE: CLOSED (was OPEN)
- NEEDED: The owner's answer: may the competition-adjusted ratio of the two-step floating catchment (PySAL `access`, BSD-3), the talent pool within reach over the competing demand within reach, be computed from the two released tables as an exception to PRV-30 and PRV-18 of [06_PRIVACY_AND_DISCLOSURE_CONTROL.md](docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md)?
- WHY: [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 1 first planned method card C39 with that ratio. The review of the decision's sweep found that the ratio divides one protected family by another, which PRV-30 does not allow, and reads the competing jobs on work units chosen by travel time instead of by the snap, which PRV-18 does not allow. AGENTS.md rule 12 forbids weakening a privacy invariant on the lead's authority, so the lead's ruling L-160 of 2026-11-14 recast card C39 and left the exception to the owner.
- DONE SO FAR: Card C39 shows two released figures side by side within 15, 30 and 45 minutes' drive: the talent pool (residents by occupation and pay band within reach) and the competing demand (jobs of the same occupations within reach). Each catchment snaps to whole release units, and PRV-18 and PRV-30 stay as they are. PRV-127 is a guard that refuses any ratio of the two figures; a planted ratio, a planted read on units chosen by travel time and a planted figure on an unsnapped outline each fail.
- OPTIONS: **Recommendation:** keep the two figures side by side, with no ratio. If the owner wants the ratio, a new decision record must amend PRV-30 and PRV-18. It must also say how the work units of the competing demand are chosen, because the release's unit-to-unit travel times hold `px_base` unit pairs only ([03_DATA_CONTRACTS.md](docs/03_DATA_CONTRACTS.md) DAT-153), and keep the rule that no choice of units depends on a protected value (PRV-19).
- NEEDED BY: task S6-T20; not a blocker, because the side-by-side form needs no exception.
- UPDATE: 2026-11-14, by the owner's answer of that day, recorded in [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 1: yes. Card C39 keeps its two released figures side by side within 10, 20 and 30 minutes' drive and adds a third, qualified people within reach per competing job within reach, the quotient of those two released figures for the same occupation group and the same cut-off, shown to one decimal. It is computed only from the two released tables. It is the only exception to PRV-30 and PRV-18. PRV-127 refuses any other ratio of two protected families and any ratio computed before release. The two-step floating catchment is not used. Where an input is withheld the reason key is `ratio_input_withheld`; where no competing job is within reach the reason key is `no_competing_jobs`.
- CLOSED: 2026-11-14, by the owner's answer, recorded in decision 0023 item 1. The earlier text is kept.

## OI-141 — Who keeps the monthly register snapshots

- ID: OI-141
- TYPE: OPEN (owner)
- NEEDED: The owner to name who keeps a snapshot of each register file each month, from 2026-11, beside that file outside the repository.
- WHY: [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) items 12 and 13 count the openings and closures of register companies from the register's own dates and from its monthly snapshots, and the "what changed this month" card of item 13 reads the snapshots too. The snapshot route needs two kept snapshots: while the snapshot of a month or of the month before it is not kept, that route gives `NO_DATA` with the reason key `snapshot_not_kept` ([03_DATA_CONTRACTS.md](docs/03_DATA_CONTRACTS.md) DAT-164).
- DONE SO FAR: Documents 02, 03 and 13 record that the snapshots lie beside each register file outside the repository and are found through the same settings, `EII_REGISTER_FILE` and `EII_FC_REGISTER_FILE`, so no setting is added. The naming that tells the months apart is still to be fixed, without printing a path or committing a file name. Until two snapshots are kept, the openings and closures rest on the register's own dates alone.
- OPTIONS: **Recommendation:** the owner keeps them, or names who does, since he holds the register files outside the repository: once a month, a copy of each file beside it, under the naming that the first task reading them fixes. A month that is missed stays `NO_DATA` on the snapshot route and is never filled in.
- NEEDED BY: 2026-11, the first month to be kept; then S5-T10 and S7-T10, which read the snapshot route, and the "what changed this month" card of item 13 if its task is named.

## OI-142 — The register file's fields for groups, the address type and the dates

- ID: OI-142
- TYPE: OPEN
- NEEDED: At the first read of each register file, confirmation of the fields that show the main-and-branch structure, the registered-address type, and the registration and cancellation dates.
- WHY: Under [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 12, the employer groups of the dominance rules are the main-and-branch structure that the register shows, the address type is taken from the register files, and openings and closures come from the register's own dates. Where a file does not show a field, the decision's fallback applies: each registration is its own legal entity and group, the address type is absent, and a company with no date is counted in no month ([03_DATA_CONTRACTS.md](docs/03_DATA_CONTRACTS.md) DAT-164). [Decision 0022](docs/decisions/0022-real-register-companies-with-a-synthetic-world.md) left the same fields open.
- DONE SO FAR: Documents 03 and 05 state each rule and its fallback, and document 06 states the employer group (PRV-07); the dominance rules and their planted tests run on these groups unchanged. Tests and continuous integration use the invented stand-in register.
- OPTIONS: **Recommendation:** confirm the fields when the file is first read, without committing the file, a field value or a path, and record only which fields exist.
- NEEDED BY: task S4-T02 (the register and employment world), whose amendment applies these rules.

## OI-143 — The look's task S3-T15 is not in TASKS.md

- ID: OI-143
- TYPE: OPEN
- NEEDED: The lead to enter the look's task S3-T15 in [TASKS.md](TASKS.md), or to record that S3-T16 keeps the map-mode switch.
- WHY: [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 7 names the look's mode-switch task S3-T15, which is not in TASKS.md.
- DONE SO FAR: Until S3-T15 enters, S3-T16 carries the map-mode switch and the modes of item 7, satellite and photorealistic 3D, as the open questions of [14_IMPLEMENTATION_PLAN.md](docs/14_IMPLEMENTATION_PLAN.md) and OPS-74 of [13_DEPLOYMENT_AND_OPERATIONS.md](docs/13_DEPLOYMENT_AND_OPERATIONS.md) record.
- OPTIONS: **Recommendation:** keep the switch and the two modes in S3-T16; if S3-T15 enters TASKS.md first, move them there by a one-line amendment that cites decision 0023 item 7.
- NEEDED BY: the start of S3-T16.

## OI-144 — The recovery tracker and the Qatarization planner have no task yet

- ID: OI-144
- TYPE: OPEN (owner)
- NEEDED: For the recovery tracker, what it is, the journey that carries it and the task that builds it, from the owner's records. For the Qatarization planner, the task that builds it in journey D5.
- WHY: [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 15 keeps both for companies. It describes the Qatarization planner as a company tool of journey D5 under the cases of item 1: which roles Qataris hold in the private sector, at what pay, and where the talent is by district. It names the recovery tracker only. Neither has a task in TASKS.md, and the recovery tracker has no passage in the pack.
- DONE SO FAR: Documents 01, 09, 10 and 14 record the gap in their open questions. The cases of item 1 already bind the planner's figures: group statistics only, through the release rules, with Qatari and non-Qatari splits only where the cell passes (BRF-96, AI-133, FE-150).
- OPTIONS: **Recommendation:** build neither until its passage and task are recorded. The planner then follows the cases of item 1 and the release rules of document 06. The recovery tracker's passage is written from the owner's description, through a decision record if it adds scope to version 1 (AGENTS.md rule 46).
- NEEDED BY: for the planner, before the journey D5 tasks of slice S7 (S7-T03, S7-T08) are planned; for the recovery tracker, before any work on it.

## OI-145 — The age profile of people living here as its own Public component

- ID: OI-145
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that the age profile of people living here is shown as its own Public component after the two blocks of the site answer, not inside the people-living-here block.
- WHY: [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 11, the owner's expectation of 2026-11-13, puts the age profile in the people-living-here block. No synthetic or protected record may carry age ([05_SYNTHETIC_WORLD_AND_SIMULATION.md](docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md) SYN-13), so that block, built from protected records, cannot hold it.
- DONE SO FAR: The decision record and documents 01, 08 and 09 record the assumption: the age profile is the Public population by age over the area of the living block (method card C38), shown as its own component after the two blocks and never in one component, calculation or chart with a protected or Simulated figure (BRF-108, AI-131, FE-146). A planted age profile inside either block fails a component test (FE-146).
- OPTIONS: **Recommendation:** keep it as its own Public component. Inside the block it would share a component with protected figures, which [decision 0019](docs/decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 22 forbids for the population grid, and a protected age split would need an age attribute that SYN-13 forbids.
- NEEDED BY: tasks S6-T02 and S8-T01, which set the site answer's order.

## OI-146 — Prices per square foot beside the median per square metre

- ID: OI-146
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that the property price measures of [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 8 are stated per square foot, as he asked, while the median sale price per square metre of method card C14 stays as it is.
- WHY: Item 8 asks for the price per square foot by district, use and quarter, and card C14 already shows the median per square metre. The decision record keeps both and relates them only by the exact conversion of one foot to 0.3048 metres.
- DONE SO FAR: Card C41 states its measures per square foot and converts areas by that exact conversion (MTH-116). Its quarterly series is a series of its own, never joined to the series of card C14 (card C30).
- OPTIONS: **Recommendation:** keep both, each labelled with its unit. Alternative: the owner chooses one unit for every price on screen, by a decision record.
- NEEDED BY: task S6-T10, which builds the property price measures.

## OI-147 — Whether a commute line from a home municipality to the site's snapped catchment meets the district-pair case

- ID: OI-147
- TYPE: OPEN (owner)
- NEEDED: The owner's confirmation.
- WHY: `home_area_share` is released only per `ha_work_count` work unit and `ha_home` municipality (PRV-40), and a district-pair table would need a new rules version and re-audit (PRV-34). Card C39 already draws each line from one whole home municipality of `ha_home` to the site's catchment snapped on `ha_work_count`, an exact sum of published `home_area_share` rows ([decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 1).
- DONE SO FAR: Version 1 meets the case "commute lines only as totals between district pairs that pass the minimums" by that form: each end is an area, the home end is never finer than a municipality, and every total passes the minimums. The quoted case and its planted violation stay as written.
- OPTIONS: **Recommendation:** keep card C39's form, which is the default. Otherwise the work end is snapped from the district outline on `ha_work_count`. The home end stays a whole municipality in either case.
- NEEDED BY: S6-T20, not a blocker. Until the owner answers, no line is drawn in any other form.

## OI-148 — The age bands against the operator's format, for when its data arrives

- ID: OI-148
- TYPE: OPEN
- NEEDED: Confirm the age bands of movement aggregates against the operator's format when its data arrives. This is not a question for the owner.
- WHY: [Decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md) item 16 sets `age_band` to `15-24`, `25-34`, `35-44`, `45-54`, `55-64` and `65+`, chosen so that a public source's five-year age groups sum into them exactly. The band edges are held in one configuration value, so they can be remapped without changing the generator or the screens.
- DONE SO FAR: The bands are the closed list of item 16; visitors under 15 are counted in the age split's `other` value.
- OPTIONS: **Recommendation:** keep the bands until the operator's data arrives, then remap the one configuration value if the format differs.
- NEEDED BY: when the operator's data arrives; not a blocker for version 1.

## OI-149 — The reproduced measurement of the typed-decision set beside the admitted one

- ID: OI-149
- TYPE: OPEN
- NEEDED: The owner's reading of the reproduced measurement beside the admitted one, without retuning a threshold and without treating this set as fresh human ground truth.
- WHY: A successful reproduction on this set does not remove the recorded protocol differences and provides no fresh human labels (OI-15; [decision 0014](docs/decisions/0014-typed-decision-gateway.md), Evidence and item 6).
- DONE SO FAR: The admitted aggregate `results_2026-11-11.json` records 248 correct of 260 with its stated interval [92.1, 97.3]. The keyed aggregate of task S1-T08, `results_2026-11-13T04-19-15-163796.json`, records 250 correct first answers of 260, a rate computed by code of 96.15384615384616%, inside that admitted interval, with its own Wilson interval [93.1, 97.9]; every one of its 340 replies names the pinned model. Its gateway outcomes are 176 DECIDED and 84 BELOW_THRESHOLD, and two decided cases are wrong (A-M-048 and A-M-049). Four protocol differences are recorded in the aggregate: the option orders are hash-derived, the activity labels are sent with the `isic-` prefix, the admitted run was made before the gateway existed, and the adapter cuts the yes/no label at a weight of 0.5. Task S1-T08 changed no threshold, no pin and neither aggregate.
- OPTIONS: **Recommendation:** keep the reproduction as evidence for this model version, and settle its reading with the fresh human qualification of OI-15; change no threshold and no pin on this comparison alone.
- NEEDED BY: the fresh human qualification of OI-15; not a blocker of the slice S1 gate.

## OI-150 — The feed minimum of the conformance suite under parameter set B

- ID: OI-150
- TYPE: CLOSED (was OPEN)
- NEEDED: The owner's or a data owner's decision on which text holds under parameter set B: the conformance test that rejects a count-table row below the minimum of the active parameter set, or the feed rule of 20 panel devices with set B's 30 applied only by the privacy engine.
- WHY: TST-32 ([12](docs/12_TESTING_AND_QUALITY.md)) asks the conformance suite to reject a row of `presence_hourly` or `od_hourly` below the minimum panel devices of the active parameter set. DAT-60 ([03](docs/03_DATA_CONTRACTS.md)) and SYN-57 ([05](docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md)) fix the feed minimum at 20 and leave set B's 30 to the privacy engine. Under set B the two differ for rows of 20 to 29 panel devices, and the kept cell of the split feed tables (decision 0023 item 16) follows the count table.
- DONE SO FAR: Found by the lead's re-read of the sweep of [decision 0023](docs/decisions/0023-ten-additions-and-the-data-rule.md). Nothing is changed: lowering the test's bar would weaken a privacy test, which no agent does on its own authority (AGENTS rule 12). The exported set is A (task S1-T09), under which both texts say 20, so nothing differs today.
- OPTIONS: **Default until decided:** the stricter text stands (TST-32 as written). Option A: keep TST-32 and state in DAT-60 and SYN-57 that under set B the simulator omits rows below 30. Option B: set the conformance minimum to the feed rule of 20 and leave 30 to the release, tested by TST-203.
- NEEDED BY: before parameter set B is ever evaluated on a feed (slice S5); not a blocker of slices S2 to S4.
- UPDATE: 2026-11-14, by [decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md): CLOSED, decided: Option A. TST-32 stands as written. DAT-60 and SYN-57 say that the simulator omits rows of the count tables `presence_hourly` and `od_hourly` under the minimum panel devices of the active parameter set, 20 under set A and 30 under set B, before conformance. Nothing else about the two sets changes (item 11).


## OI-151 — Greater Doha as five whole municipalities

- ID: OI-151
- TYPE: ASSUMPTION
- NEEDED: The owner's confirmation or replacement of the lead's assumption that Greater Doha is, for version 1, five whole municipalities, named in the frame's review file of task S2-T02.
- WHY: The frame's resolution boundary (resolution 9 inside Greater Doha, 8 elsewhere) and every use of the name on a screen or a card depend on it. [Decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md) item 10 keeps the assumption for version 1 and rules that the definition is shown wherever the name appears.
- DONE SO FAR: The advisor decided under the owner's delegation on 2026-11-14 that the five-municipality reading stays for version 1 and that this item stays open as a record point. The review file is built by task S2-T02; until that task merges, the pack refers to "the five municipalities of the frame's review file" and lists no names.
- OPTIONS: **Default until decided:** five whole municipalities. Otherwise the owner names another set of whole municipalities or a drawn boundary, and the frame is rebuilt.
- NEEDED BY: the slice S2 gate (the frame), and before any screen shows the name (slice S3).
- UPDATE: 2026-11-15, by [decision 0030](docs/decisions/0030-frame-grid-by-index-ownership-and-two-nullable-keys.md) (proposed, for the owner's confirmation): the line WHY above gives the earlier resolution rule. Under items 1 and 5 of decision 0030, a resolution-8 parent is split when the centre of at least one of its resolution-9 children lies in a Greater Doha municipality, and a cell's resolution is read from the cell, never from `in_greater_doha` or its municipality: the frame holds 598 resolution-9 cells outside Greater Doha and no resolution-8 cell inside it. The Greater Doha set still decides which parents are split, so a change of the set needs a new build of the frame and, after a freeze, a new world seed (the record's Consequences). The assumption itself is unchanged (item 14).

## OI-157 — The caveat key `national_average` on card C33 after the survey benchmark left it

- ID: OI-157
- TYPE: OPEN
- NEEDED: Decide whether card C33 (site demand and revenue estimate) keeps the caveat key `national_average`.
- WHY: [Decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md) item 12 withdraws the survey's output per establishment, which was the only survey figure card C33 showed. The card's list of caveats in [07](docs/07_ECONOMIC_METHODS.md) still names `national_average`, which described that figure. A caveat with no figure behind it says something the card no longer shows.
- DONE SO FAR: Found by the lead's sweep of decision 0026. Left as it stands: the key is part of the card's closed list and of the tests that read it, and the card stays off screen while OI-03 is open.
- OPTIONS: **Recommendation:** remove the key from card C33 when task S6-T17 is planned, with its test rows. Otherwise keep it and name the figure it covers.
- NEEDED BY: the plan of task S6-T17 (slice S6).

## OI-155 — Forms that render as a listed name without being its text

- ID: OI-155
- TYPE: CLOSED (was PROPOSED (hardening: document 17))
- NEEDED: A decision whether the documentation check should also refuse forms that a reader sees as a listed name but that are not its text: tags inside the name, a link on half of it, further invisible characters, further escape forms.
- WHY: The break pass of task S1-T14 showed four such forms passing everywhere. The private list's plain patterns do not catch them either, with or without the place-scoped exception, so the exception weakens nothing here; refusing them is a defence against deliberate evasion beyond the task's criteria ([decision 0018](docs/decisions/0018-priorities-and-amendments-to-decision-0015.md)).
- DONE SO FAR: Recorded with the four demonstrated forms in the task's evidence. Nothing built.
- OPTIONS: **Recommendation:** move to [17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md) with the slice's follow-up task; build only if the repository ever takes contributions from outside the run.
- NEEDED BY: the follow-up task of slice S1 (S1-T10), which places it.
- CLOSED: 2026-11-14, by S1-T10: placed in section 9 of [17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md) as DHA-131, with the four forms, with its origin. Nothing built. The earlier text is kept.

## OI-156 — An unreadable folder and a failing file listing narrow the documentation check silently

- ID: OI-156
- TYPE: CLOSED (was PROPOSED (hardening: document 17))
- NEEDED: A decision whether the documentation check should fail when a folder cannot be read or when git cannot list the files, instead of scanning less.
- WHY: The break pass of task S1-T14 showed that a folder without read permission is skipped without a line, and that a failing git listing falls back, without notice, to the walk that leaves out build folders. Both are older than that task and concern the whole check, not its exception; neither occurs on the hosted checks.
- DONE SO FAR: Recorded with both demonstrations in the task's evidence. Nothing built.
- OPTIONS: **Recommendation:** move to [17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md) with the slice's follow-up task.
- NEEDED BY: the follow-up task of slice S1 (S1-T10), which places it.
- CLOSED: 2026-11-14, by S1-T10: placed in section 9 of [17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md) as DHA-132, with its origin. Nothing built. The earlier text is kept.

## OI-158 — The hosted time limit of the web checks goes back to 1,800 seconds

- ID: OI-158
- TYPE: OPEN
- NEEDED: Remove the hosted value of 3,000 s from `scripts/run_tests.py`, so that the limit of the suite `web-checks` is 1,800 s everywhere again, once task S1-T15 has made the suite fast enough on slow hosted runners.
- WHY: [Decision 0027](docs/decisions/0027-hosted-web-checks-time-limit.md) allows the hosted value only as a stopgap. A wider limit finds a hanging run later.
- DONE SO FAR: Task S1-T16 raises the limit on GitHub's hosted runner only, by the owner's decision of 2026-11-14. Task S1-T15 is in review with both parts (pull request 43): on four processors of the build machine the spike's browser run fell from 1,993 s to 1,294 s (one valid timing). Its criterion on the suite's time (under 1,200 s on four processors, measured twice) is not met; by the re-plan of 2026-11-14 recorded in `PROGRESS.md` under S1-T15 it is moved, unticked and word for word, to task S2-T10, and no further pass is made before the slice S1 gate. What is left of it is part of this item: a further shortening of the browser run that removes or weakens no test, and the second valid timing run.
- OPTIONS: **Default:** the pull request that completes S1-T15, or the one after it, removes the hosted value when three hosted runs in a row have finished the suite inside 1,800 s. The three runs are counted from the head of pull request 43: that head's run, the main branch's run after its merge, and the next pull request's run. Otherwise the owner decides to keep a hosted value.
- NEEDED BY: the slice S1 gate records the state of this item; the work is done in task S2-T10, before the slice S2 gate.
- UPDATE: 2026-11-14, by the gate-fix task S1-T17 after the first review of the slice S1 gate: the condition of the default is met. The three hosted runs it counts each finished the suite `web-checks` inside 1,800 s: the head of pull request 43 (731 s; 843 passed, 0 failed, 0 skipped), the main branch after its merge (912 s; 843 passed, 0 failed, 0 skipped) and the head of pull request 46 (937 s; 849 passed, 0 failed, 0 skipped); the main branch after the merge of pull request 46 took 938 s. The removal of the hosted value is now an acceptance criterion of task S2-T10, with the runner's files in its scope. It is a separate thing from that task's criterion on the suite's time on four processors (under 1,200 s, measured twice), which is not met. This item stays open until the removal is merged.

## OI-159 — The pin-ruling guard refuses the record once S1-T08 is marked done

- ID: OI-159
- TYPE: CLOSED (was OPEN)
- NEEDED: Correct the guard `scripts/tests/test_pin_rulings.py` so that a pin that is not installed is refused only when its not-installed ruling names a completed task, not when the retreat ruling's own attribution ("retreat ruling S1-T08") does; add the planted cases of both; then set the status line of S1-T08 in `TASKS.md` to done.
- WHY: The guard requires the words "retreat ruling S1-T08: none exists: " in the note of a pin without a retreat and refuses a not-installed pin whose note names a completed task. With S1-T08 marked done, the pin `@mapbox/mapbox-gl-rtl-text` fails both ways. The lead's whole test on the ledger head of pull request 45 found it (seed 2026111447: 2216 passed, 1 failed).
- DONE SO FAR: The status line of S1-T08 is back at "in review" although pull request 39 is merged, so that the guard passes; the cause is recorded in `PROGRESS.md` under task S1-T16. Nothing of the guard is changed (task S1-T16 changes no test, decision record 0027).
- OPTIONS: **Default:** the review follow-up of slice S1 (task S1-T10) corrects the guard test-first and sets the status line.
- NEEDED BY: the slice S1 gate, which reads the status lines of the slice's tasks.
- CLOSED: 2026-11-14, by S1-T10: the guard refuses a pin that is not installed only when its not-installed ruling names a completed task; the attribution of a retreat ruling does not count. Proved by `test_d_completed_task` (a not-installed ruling naming a completed task still fails) and `test_pending_task_with_completed_retreat_ruling_remains_valid` in `scripts/tests/test_pin_rulings.py`; the status line of S1-T08 in TASKS.md is done. The earlier text is kept.

## OI-160 — One time-out of the full street load on readiness, in a run under load

- ID: OI-160
- TYPE: CLOSED (was OPEN)
- NEEDED: Show that the readiness bound of 170 s in the browser test "roads full street load draws every link and carries the Simulated mark" (`web/spikes/performance/tests/performance.spec.ts`) has a real margin on the runners that run it, or find why it was exceeded once.
- WHY: In the builder's first measurement of part B of task S1-T15, taken while the build machine was loaded by other runs, that test timed out once on readiness at its bound and passed in the next run. A green re-run alone does not close a random failure (AGENTS rule 39).
- DONE SO FAR: No bound was changed. The test passed in every run of the lead since: the two timing runs of the browser suite on four processors (the test took 3.5 minutes in the run under load and 2.3 minutes on reserved processors; 54 tests passed in each) and the browser run of the ledger of part B (54 passed).
- OPTIONS: **Default:** the three hosted runs counted for S1-T15 (the head of pull request 43, the main branch after its merge, the next pull request) are the evidence: the item is closed when the test passed in all three, with the time of the suite `web-checks` in each recorded; a time-out in one of them keeps the item open and its cause is found before any bound moves.
- NEEDED BY: the slice S1 gate records the state of this item.
- CLOSED: 2026-11-14, by the gate-fix task S1-T17, on the item's own default: the test passed in the three hosted runs counted for S1-T15, and the time of the suite `web-checks` in each is recorded: the head of pull request 43 (731 s; 843 passed, 0 failed, 0 skipped), the main branch after its merge (912 s; 843 passed, 0 failed, 0 skipped) and the head of pull request 46 (937 s; 849 passed, 0 failed, 0 skipped). The main branch after the merge of pull request 46 passed too (938 s). No time-out was seen in any of them and no bound was changed. The hosted logs give no time for the one test alone, and the default does not ask for one; the first review of the slice S1 gate found that the gate record had kept the item open for that reason.

## OI-161 — Two dependency alerts on a development-only package that the mutation tester brings in

- ID: OI-161
- TYPE: OPEN
- NEEDED: An override in `web/package.json` that raises the package `qs` to a fixed release, with the lock file made again by `npm install --package-lock-only` and the web checks green; or the alerts kept open with their reason recorded.
- WHY: GitHub's dependency alerts on main name the package `qs` twice (alerts 4 and 7), severity medium, in `web/package-lock.json`. The lock file holds one copy, `qs` 6.15.1, in development scope only: `typed-rest-client` 2.3.1 asks for exactly that version, and `typed-rest-client` comes in through the pinned mutation tester `@stryker-mutator/core` 10.1.1. It runs on the build machine and in CI and is never served. Fixed releases exist; none can lie inside the exact version its parent asks for, so raising it needs an override.
- DONE SO FAR: Nothing is changed. The lead read the alerts in GitHub's answer to a push on 2026-11-14; they are new since 2026-11-13. A lock file changes only inside a task that owns it, and `npm install --package-lock-only` runs only after a change to `web/package.json` (rule 44 of [AGENTS.md](AGENTS.md)). Task S1-T10 read the structure of the lock file for this entry: one copy of `qs`, one package that asks for it, no override of it.
- OPTIONS: **Recommendation:** add the override at the next change of `web/package.json`, if the web checks and the tests of the web mutation runner stay green with it; otherwise keep the alerts open with that reason. Alternative: leave them until the pin of the mutation tester is next raised.
- NEEDED BY: the next change of `web/package.json` or the slice S3 gate, whichever is first; not a blocker.

## OI-162 — The task that builds the register-company table, card and map points

- ID: OI-162
- TYPE: OPEN
- NEEDED: The slice and task that build the Public table `pub_register_company`, the company card and the map's establishment points of the register, beside the real business points of S2-T06 and S3-T12 (the OPEN line of [decision 0022](docs/decisions/0022-real-register-companies-with-a-synthetic-world.md) in [14_IMPLEMENTATION_PLAN.md](docs/14_IMPLEMENTATION_PLAN.md)).
- WHY: The review of pull request 37 (point P1) found that the OPEN lines decision 0022 added to the pack name no task that owns them. The follow-up task of slice S1 (S1-T10, item I12) gave an owner where the plan has one; for this line its builders found no task of TASKS.md that names the three, and the follow-up adds no task.
- DONE SO FAR: The OPEN line stays in document 14 as it is. No owner is invented. Nothing built.
- OPTIONS: **Default:** the lead names the owning task in a re-plan, recorded in TASKS.md, before the first task that builds a register-company table, card or map layer starts; the owner is asked only if the allocation needs a new task.
- NEEDED BY: the slice S2 gate (the public pack and its places).

## OI-163 — One browser test of the performance spike lost its page during readiness, once

- ID: OI-163
- TYPE: OPEN
- NEEDED: The cause of one failure of the browser test "the smoke orbit draws both layers and records a trace" (`web/spikes/performance/tests/performance.spec.ts`), which ended during readiness with the browser's message `page.evaluate: Target page, context or browser has been closed`.
- WHY: A random failure is recorded, and a green re-run alone does not close it (AGENTS rule 39; TST-168). The failure was seen once, on 2026-11-14, in a standalone run of the spike's browser tests on processors 0 to 3 of the build machine (53 passed, 1 failed), inside the measuring job for OI-158. That job kept no change to the repository, and its record does not hold the browser's own log of the failure.
- DONE SO FAR: Recorded here by the slice S1 gate record. The same test passed in the job's later runs of the whole suite `web-checks`, in the lead's runs of the gate at the slice's final commit and in the hosted `tests` check of that commit. The cause is not found. No test, wait, bound or retry was changed.
- OPTIONS: **Default:** task S2-T10, which holds the criterion on the suite's time (OI-158), repeats the standalone browser run on four processors with the browser's log and the page's console kept on a failure of readiness, and records either the cause or the number of runs without the failure; no retry is added to the test and no bound moves before the cause is known.
- NEEDED BY: the slice S2 gate (task S2-T10).
- UPDATE: 2026-11-14, by the second round of the slice S1 gate record: a likely cause is found, and the item stays open. By the browser tool's own report the failing run started at 17:18:31, and the test failed about one second into it. In that second, four campaigns of the mutation tester, started by a builder's job at 17:17:19, were running in the shared process-number space of the build machine, and three of them recorded time-outs that fired. The tester sends its time-out signal to a process number that may by then belong to another process (OI-168), and a browser process that is stopped in that way gives this message. No record says which process ended, so the cause is not proved. The default stands, now with no campaign in the shared space: the repeated standalone run of task S2-T10 either shows the failure again or counts the runs without it.

## OI-165 — The optional 3D view stands in the slice S1 row of document 12's gate table

- ID: OI-165
- TYPE: CLOSED (was ASSUMPTION)
- NEEDED: One place for the gate item of the optional 3D view of decision 0019 item 14. The row "slice S1 Technical spike" of [12_TESTING_AND_QUALITY.md](docs/12_TESTING_AND_QUALITY.md) section 5 says "the optional 3D view of decision 0019 item 14 passes its named test" and names as its evidence "TST-242 for the 3D view, with its frame-rate numbers reported". [14_IMPLEMENTATION_PLAN.md](docs/14_IMPLEMENTATION_PLAN.md) puts the view in slice S6: PLN-28, the row of section 6 that names tasks S6-T18 and S6-T19, and the task list and the gate text of section "14. slice S6 — The flagship location choice". The gate text of slice S1 in document 14 (section "9. slice S1 — Technical spike") has fourteen statements and none names the view. The row "slice S6 The joined door" of document 12 does not name it.
- WHY: Found while the slice S1 gate record was prepared. REV-33 makes every item of the document 12 row an item of the gate review. No task of slice S1 builds the view (TASKS.md), so the clause cannot pass at this gate, and the gate record claims nothing about the view. The clause entered the slice S1 row with the documents change of decision 0019.
- DONE SO FAR: The lead's reading, recorded in the slice S1 gate record: PLN-28 says that the work of decision 0019 lands where section 6 of document 14 puts it, so the clause belongs to the slice S6 row and is not a gate item of slice S1. No document is changed by the gate record.
- OPTIONS: **Default:** a documents change with its own review moves the clause and its evidence clause from the slice S1 row to the slice S6 row of document 12, before the addendum that closes the slice S1 gate. The owner says so if the slice S1 gate is to hold a spike of the 3D view instead; the gate then stays open for it.
- NEEDED BY: the addendum of the slice S1 gate (task S1-T12).
- CLOSED: 2026-11-14, by the second round of the slice S1 gate record, on the item's default: the gate-fix task S1-T17 (pull request 48), a documents change with its own independent review, moved the clause and its evidence clause from the slice S1 row to the slice S6 row of document 12 (section 5), in the same words, with the owner's approval of the correction (quoted in the task log of S1-T17 in PROGRESS.md). The first review of the gate held that the question could not stand as an assumption while the gate was reviewed; the gate record's second round reads both rows at the slice's final commit. Nothing about the view itself is claimed: it is built and tested in slice S6.

## OI-168 — The mutation tester's time-out can stop a process that is not its own

- ID: OI-168
- TYPE: OPEN
- NEEDED: A way to run `scripts/mutation.py` that cannot stop a process outside its own campaign.
- WHY: The pinned mutation tester (mutmut, the dependency group `mutation`) records a deadline and a process number for every mutant run and cancels no entry when a run ends. When a deadline passes, it sends the signal SIGXCPU to that number (its module `mutmut/workers/timeout.py`, whose own comment says that entries of ended processes stay until they reach the top). On a machine that reuses process numbers quickly, the number can by then belong to another process of the same user, which ends with "CPU time limit exceeded" (exit code 152). On 2026-11-14 a run of the guard-test discovery on the build machine ended that way within a minute, while a builder's campaign ran in the same process-number space; the same command at the same commit passed once no such campaign ran. The highest process number of the build machine is 99999. A random failure and its cause are recorded (AGENTS rule 39).
- DONE SO FAR: The lead read the tester's module in full and found no limit on processor time in any shell, script or test of the repository. The campaign was stopped, and since then every campaign on the build machine is started in a process-number space of its own, with the sandbox tool the repository already uses, where it can reach only its own processes. Nothing in the repository is changed. The stopped run was not a run of the slice S1 gate. The lead's run records were read for the three random failures recorded earlier: OI-163 falls in a second in which four such campaigns were running (the update in that item); OI-125 and OI-160 do not fall on a campaign. The web mutation runner uses another tool, which was not examined.
- OPTIONS: **Default:** `scripts/mutation.py` starts the tester in a process-number space of its own and refuses to run where it cannot, with a planted case; no fallback to the shared space. Alternative: raise the pin once the tester cancels its entries, and keep the separate space until then.
- NEEDED BY: task S2-T10; until then no campaign runs in the shared process-number space of the build machine.

## OI-127 — PyYAML is installed through the root development group

- ID: OI-127
- TYPE: ASSUMPTION
- NEEDED: Confirmation, by the first task that installs `eii_custodian` outside the root dependency group `dev`, that `pyyaml` moves into the custodian manifest `custodian/pyproject.toml` in that task's pull request.
- WHY: The source registry of task S2-T01 is the committed file `custodian/publicdata/sources.yaml`, and the PyYAML package reads it. A member manifest cannot gain a third-party dependency while the clean-environment guard of task S0-T02 installs the members offline from an empty cache (OI-60, OI-116). PyYAML has no type stubs, so the one import carries the same `type: ignore[import-untyped]` mark that two existing checks already use.
- DONE SO FAR: `pyyaml` 6.0.3 is pinned exactly in the root group `dev` and in `pins.toml` with the retreat 6.0.2 and the label ASSUMPTION. The loader calls `yaml.safe_load` only; a test fails if the loader source holds `yaml.load` or lacks `safe_load`. No other package was added.
- OPTIONS: **Recommendation:** keep the package in the root group through slice S2; the task that first runs `build-public` or the registry from an environment without the `dev` group declares `pyyaml` in the custodian manifest and changes the clean-environment guard in the same pull request. Alternative: keep the registry in JSON, which needs no package, at the cost of comments and a harder review of 138 rows.
- NEEDED BY: slice S2 pin confirmation; the first task that loads the registry outside the root development group.
- UPDATE: 2026-11-14, by the base update of task S2-T01's pull request: the sentence above that PyYAML has no type stubs, and that the import carries a `type: ignore[import-untyped]` mark, no longer holds. The stub package `types-pyyaml` 6.0.12.20261113 is pinned exactly in the root group `dev` and in `pins.toml` with the retreat 6.0.12.20261111 and the label ASSUMPTION, and the mark is removed from the loader's import and from the two existing checks that carried it. The assumption of this item is unchanged, and it now covers both packages: they move together into the custodian manifest in the pull request of the task that first loads the registry outside the root development group.

## OI-128 — The investment sources are used by the owner's decision of 2026-11-12

- ID: OI-128
- TYPE: CLOSED
- NEEDED: Nothing; recorded so that the basis of use of the two investment sources is visible beside their terms.
- WHY: Criterion 8 of task S2-T01 asks the registry to record the publisher's terms as read at fetch and the basis of use. The publisher's terms of use, read on 2026-11-13 at `https://www.invest.qa/en/terms-and-conditions?tab=terms-of-use`, allow copies for personal and non-commercial use while viewing and ask for the publisher's prior written permission and an acknowledgement of the source before the material is copied, modified or reproduced. The owner had decided on 2026-11-12, for this personal internal project: "use both sources fully, no permission needed."
- DONE SO FAR: Both rows (`fdi_projects`, `investqa_pages`) name the terms page and record the owner's decision of 2026-11-12, in his words, as the basis of use. At every fetch the build reads the terms page, records its SHA-256 and retrieval time, and logs a line when the page has changed since the previous build; the sources are not switched off. The fetched data stays under `data/` and never enters the repository or a committed fixture; tests use synthetic pages shaped like the real ones. Every figure keeps its source and retrieval date (PUB-87, PUB-88).
- OPTIONS: Closed by the owner's decision.
- NEEDED BY: none.

## OI-129 — One sandbox timing test failed once under machine load

- ID: OI-129
- TYPE: OPEN
- NEEDED: The cause of one failure of `test_die_with_parent` in `scripts/tests/test_sandbox_mounts.py`, or a record that it did not recur over a stated number of runs.
- WHY: AGENTS.md rule 39: a random failure is recorded, and a green re-run alone does not close it.
- DONE SO FAR: During task S2-T01 (2026-11-13), the builder's whole test run at seed 2026111377 failed this test once with "a sandboxed process outlived its driver", while the machine was loaded (a load average of 74 on 32 processors, ruling L-106 of the run). The same test passed in the lead's whole runs at seeds 2026111378 and 2026111382, which ran at lower priority and finished with 0 failed. In the same builder run, two tests of the version check failed because that tool's shell had Node 24 first on its path instead of the pinned 22; that is an environment fault and not a random failure, and the lead's runs with Node 22 passed. No code was changed because of either.
- OPTIONS: **Recommendation:** count the failures of this test over the next ten local runs and record the count here; if it recurs, make the test wait for the process group to end for a stated time before it judges, never loosen the assertion that the process does not outlive its driver.
- NEEDED BY: the slice S2 gate.

## OI-130 — Showing the live traffic layer outside internal evaluation

- ID: OI-130
- TYPE: OPEN
- NEEDED: The owner's decision whether the optional live traffic layer (decision 0019, task S6-T19) is shown to anyone outside his own evaluation and testing.
- WHY: The provider's terms, read by the lead in full on 2026-11-13 (`https://docs.tomtom.com/legal/terms-and-conditions`; no date or version on the page), license the free plan "for Evaluation Use only", defined as "internal evaluation and testing by you of the Licensed Products"; a demonstration to a ministry is not clearly internal evaluation.
- DONE SO FAR: Document 04 records the terms on the two provider rows: Evaluation Use only; caching or storing results prohibited except in a client under the result's cache-control headers and never to serve several users (nothing is stored, as decision 0019 already says); the logos and copyright notices the provider's interfaces generate are kept, and other attribution comes from the provider's copyright interface; the page says nothing on showing the layer beside other map data. The layer stays off by default.
- OPTIONS: **Recommendation:** keep the live layer for the owner's own evaluation and show the simulated traffic in every demonstration; if the owner wants the live layer in a demonstration, take a plan whose terms allow that use first.
- NEEDED BY: task S6-T19.

## OI-131 — Public split declarations of the registry rows

- ID: OI-131
- TYPE: OPEN
- NEEDED: The registry rows of Public split tables declare the split dimensions their tables carry (DAT-141, PUB-90).
- WHY: Review round 1 of S2-T01 found that the six `active_nat_occ_act` rows declare a nationality split but not the sex split their table `pub_active_nationality_occupation` carries, and that `sec_hr_comp_occ`, `wage_bands_priv`, `ref_min_wage` and the three `visitors_markets` rows declare no split on tables that are Public split tables.
- DONE SO FAR: Recorded at the review of S2-T01; S2-T01 builds the fetchers and the registry, not the split tables.
- OPTIONS: **Recommendation:** task S2-T11, which builds the Public split tables, sets each row's `public_splits` to the dimensions of its table and adds a test that compares the registry with the table contracts.
- NEEDED BY: task S2-T11.

## OI-164 — The registry loader does not yet follow decision 0026

- ID: OI-164
- TYPE: PENDING (was OPEN)
- NEEDED: The registry loader, the terms handling of the fetch and the registry rows follow [decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md): `owner_decision` is the basis of every source with no open licence covering the use, with no source admitted one by one and no separate decision record; the basis `none_stated` is gone; and terms read at a fetch never switch off a source that a visitor can read, or limit its release or display.
- WHY: Decision 0026 merged (pull request 44) after task S2-T01 was built and approved. It rewrote two acceptance criteria of that task and named no task for the change of code. At the merge of S2-T01 the loader (`custodian/src/eii_custodian/publicdata/fetch/registry.py`) still admits an `owner_decision` source only when it is listed in `OWNER_DECISION_SOURCES` and names a record of `DECISION_RECORDS`, and keeps the basis `none_stated`, which 19 rows of `custodian/publicdata/sources.yaml` carry and for which `release_refused` refuses every release slot; and the fetch (`_switch_off_on_terms` in `custodian/src/eii_custodian/publicdata/fetch/build.py`) switches a source off when the terms read at a fetch forbid the use.
- DONE SO FAR: The two criteria are moved, unticked and word for word, from the entry of S2-T01 to the new task S2-T21 in TASKS.md, and S2-T21 is added to what the pack assembly S2-T08 depends on. No code is changed by the move. The 10 sources admitted by name keep working, so no task built ahead is blocked.
- OPTIONS: **Default:** task S2-T21 changes the loader, the fetch, the rows and their tests before the slice S2 gate; until then the loader stands as built and reviewed.
- NEEDED BY: the slice S2 gate (task S2-T21, before the pack assembly S2-T08).
- UPDATE: 2026-11-15, by the ledger of merge train C (task S2-T21): PENDING, not closed. Task S2-T21 changed the loader, the fetch, the rows and their tests under one design review, two code reviews and four confirmations by another maker, and merges as its part A. The list of admitted sources, the basis `none_stated` and the switch-off on terms are gone. Both criteria stay unticked (part B): they wait for the publishers' words (OI-209), the reasons of six skipped rows (OI-210), the release proof of S2-T08 (OI-211) and DHA-102 (OI-212).

## OI-166 — Placing a location that has no base cell

- ID: OI-166
- TYPE: OPEN
- NEEDED: A rule, in its own decision record, for placing a location whose point has no base cell under [decision 0030](docs/decisions/0030-frame-grid-by-index-ownership-and-two-nullable-keys.md) item 2: a register company's registered location, a case sample file's depot and a synthetic record. What a pin, a gazetteer key with a null `cell`, the release unit of a site under PRV-126 and card C33, and the candidate depot of card C29 get is already decided (no protected or Simulated figure, PRV-135; item 10), and so is a Public supply point of a Simulated access layer (item 11, put to the owner with its default); they are not part of this item.
- WHY: The fixed grid does not cover the land exactly. On the real boundaries, 460 resolution-9 places with their centre in the mapped land area, about 48.45 km² in three municipalities outside Greater Doha that reach the coast or the border, have no owner, and edge pieces of places centred at sea or beyond the border have no cell, in Greater Doha too (decision 0030 item 12). PRV-11 fails the build for a contributor whose cell is not a row of `grid_cell`, and no cell is substituted for a point (item 2), so a location there can be neither placed nor moved.
- DONE SO FAR: Decision 0030 records the question under "What is not decided" and "Open questions and assumptions", and ruling L-280 part (6) enters it here. Until the first task that places such a location decides it in its own record, three things hold: PRV-11 fails the build for a contributor; DAT-164's null `registered_cell` puts a register company in no area; the build report counts such locations first, so the size of the case is known before a rule is chosen. No generator moves a contributor into a neighbouring cell. Nothing is built.
- OPTIONS: **Default until decided:** the three holds above. The rule is decided by the first task that places such a location, after its build report has counted the cases; the lead's default owner for the register companies' registered locations is task S4-T02. For a case sample file's depot and for a synthetic record no owner task is named: the task that first places one names this item in its plan.
- NEEDED BY: the first task that places such a location (task S4-T02 by default, for the register companies), before its build places one.

## OI-167 — A null-district fixture for the generator of SYN-32 and its fidelity check F15

- ID: OI-167
- TYPE: OPEN
- NEEDED: When the generator of SYN-32 (family-housing residents sorted mildly by wage toward districts with higher median sale prices, at the rank correlation `res.wage_sorting`) and its fidelity check F15 (the rank correlation of family-housing wage with district sale price, within 0.1 of `res.wage_sorting`) are built, their fixtures include a cell with a null `district_key` in a reviewed district-free zone; a missing district price is never substituted, and no fidelity tolerance is relaxed for it.
- WHY: Under [decision 0030](docs/decisions/0030-frame-grid-by-index-ownership-and-two-nullable-keys.md) item 7, `grid_cell.district_key` is null for a cell whose centre lies in a zone listed in `zones_without_districts.csv`; the real frame has five such cells, all in zone 99. A reader that finds the null gives no district context and substitutes no neighbouring district (item 9), so SYN-32 and F15, which read a district's sale price, meet cells without one.
- DONE SO FAR: Proposed by the one design review of decision 0030 (OpenAI GPT-6 Astra through Codex) and entered as an open item by ruling L-294; the record carries it under "Open questions and assumptions". Nothing is built.
- OPTIONS: **Default:** the fixture and the two prohibitions of NEEDED are part of the owning task's tests. The owner is the task whose plan first covers the generator of SYN-32 and check F15; no task of TASKS.md lists SYN-32 in its Requirements line on main, so the plan of that task names this item.
- NEEDED BY: that task, before its first world build.

## OI-170 — The `Employed` indicator of the municipal population source is not loaded

- ID: OI-170
- TYPE: OPEN
- NEEDED: the privacy judgement whether a count of the employed by municipality of residence belongs in what the attacker is assumed to know, taken at the design of slice S5; until then the count stays unloaded.
- WHY: the source `pop_muni` holds an `Employed` indicator that maps to no contract token of `pub_population_municipality`; whether such a count is part of the attacker's assumed knowledge is a privacy judgement, not a mapping the task may choose (the lead's ruling for the seventh pass).
- DONE SO FAR: `custodian/publicdata/review/population_indicators.csv` lists `Employed` with a blank token; the live build reports the unmapped indicators' rows as not loaded (192 rows on the real run, `Employed` among them), refuses an indicator the file does not list with the source and the indicator named, and a test pins the committed file with two planted edits of a copy.
- OPTIONS: **Recommendation:** decide at the slice S5 privacy design, before any task loads or uses the count; loading it earlier needs that decision first.
- NEEDED BY: the design of slice S5.

## OI-171 — Three bed-linen lines whose two descriptions disagree

- ID: OI-171
- TYPE: OPEN
- NEEDED: A decision whether the three customs lines whose English description says table linen while the Arabic says bed linen enter the hotel basket on the nomenclature's text, or stay excluded.
- WHY: The bilingual review read the English as the publisher's error, and the international subheading supports that reading; but the review's own rule is that a line whose two descriptions disagree is not used, and settling it needs the nomenclature cited as a source, which the pack does not hold. Keeping a line out cannot put another product's imports into a unit value.
- DONE SO FAR: The three lines stay excluded with the corrected reason; the input 'bed linen' is narrower than its name and says so.
- OPTIONS: **Recommendation:** keep the lines out until the OI-03 sign-off decides; including them needs the nomenclature as a cited source.
- NEEDED BY: the OI-03 sign-off; the hotel basket.

## OI-172 — Owner's confirmation of the reviewed customs baskets

- ID: OI-172
- TYPE: OPEN
- NEEDED: The owner's confirmation of the reviewed baskets in `custodian/publicdata/review/baskets.yaml`.
- WHY: The baskets are reviewed by two expert personas of two makers (a procurement persona proposed the lines; a bilingual customs persona checked every line in both languages), not by a person; the file says so in its status and reviewer fields.
- DONE SO FAR: 24 inputs over three activities; 74 included and 96 excluded lines, each with reasons, reviewer role, date and the hash of the source read; the build checks every listed code against the customs source's own twelve-digit lines and every sibling under an included eight-digit parent.
- OPTIONS: **Recommendation:** confirm at the OI-03 sign-off, or name the lines to re-review.
- NEEDED BY: the unit-value figures of PUB-65 and the estimates that read the baskets.

## OI-173 — MTH-30 historical selection not called by the build

- ID: OI-173
- TYPE: OPEN
- NEEDED: Wire the historical selection of `baskets.py` into the series build so a 2019-era eight-digit parent that also holds excluded lines is marked "includes excluded lines" or withheld (PUB-44, MTH-30).
- WHY: The function exists and is tested, but `build_series` never calls it; 2019 contract rows carry no rollup_note.
- DONE SO FAR: The function and its tests exist; the point was proposed by the first review and restated by the confirmation review as a slice follow-up. The owned anchors are 2025 figures.
- OPTIONS: **Recommendation:** assign to the slice's follow-up task.
- NEEDED BY: any 2019-period customs contract row.

## OI-174 — The task's municipality alias file is replaced by the frame's crosswalk

- ID: OI-174
- TYPE: PENDING
- NEEDED: When this task joins a main that holds the frame (S2-T02), replace this task's own alias file `custodian/publicdata/review/municipality_aliases.json` (empty) by the frame's crosswalk file (PUB-27); the licence-file spelling that waited for a reviewed alias resolves there.
- WHY: The pack rules municipality names through the frame's committed crosswalk: an exact lookup after white-space normalisation, and an unmapped spelling fails the build.
- DONE SO FAR: The exact-match join and its named check are built; the alias file ships empty; the lead's real-cache runs reported one unmatched spelling. Merge train A carries this task and S2-T02 with each task's approved change unchanged (decision 0032 item 2), so the join itself does not make the replacement.
- OPTIONS: **Recommendation:** task S2-T08 adopts the frame's names file for the licence series and drops the task's own alias file, with the test that an unmapped spelling fails the build.
- NEEDED BY: task S2-T08 (the Public pack assembly), whose build joins the series with the frame; before the slice S2 gate.

## OI-175 — PUB-67 incomplete by design on this task's inputs

- ID: OI-175
- TYPE: PENDING
- NEEDED: Nothing of this task: five of the nine PUB-67 stage values are S2-T04's and the frame's. This record keeps the handoff visible.
- WHY: On this task's inputs the stage names PUB-67 as the first incomplete anchor and exits 1, as designed; a complete run is proved only when the tasks are joined.
- DONE SO FAR: This task's four own values hold on the real cache; the reconciliation file names the handoff; the nine literals are asserted against the code's table and the document.
- OPTIONS: **Recommendation:** close when S2-T04's five values are asserted at the join.
- NEEDED BY: the section 9 regression criterion, when task S2-T04 stands on the same tree (S2-T04 is not in merge train A).
- UPDATE: 2026-11-15, by the ledger of merge train B5: task S2-T04 stands on the same tree as S2-T03 from this train. Whether its five PUB-67 stage values are asserted on the joined tree is not shown by any record of this ledger; the item stays PENDING until that assertion is run and recorded.

## OI-176 — Five low defects of the public-series calculations, fixed on the calculation layer's final form

- ID: OI-176
- TYPE: CLOSED (was OPEN)
- NEEDED: The five defects D1 to D5 that the internal verification of task S2-T03 found are fixed once, with a planted test each, on the final form of the calculation layer: the branch of task S2-T07, which replaces `core/src/eii_core/calc/public_series.py` whole.
- WHY: The verification (2026-11-15, at the commit dde9aeedd273c9f82c6e74b6b921ba1b3ee4f4c6; a helper of the lead on the lead's own maker and model, so an internal second reading and not another maker's review) found every formula equal to its card and no defect on a recorded figure of the task. The five defects, each reproduced on invented inputs:
  - D1, an exact half can round the wrong way, and the identity of MTH-21 is not exact (functions `ratio`, `weighted_mean` and `decomposition`): division is made at 28 digits before the later steps, so the value handed to `rounded` is already rounded once. Invented input: before, 5 workers at wage 1 and 1 at wage 0; after, 2 at wage 1 and 1 at wage 2; the means are 5/6 and 4/3 and the change is exactly 0.5. Got "0"; expected "1". Two more invented cases: a within part of exactly 8.5 printed "8", expected "9"; a mix share of exactly 6.25 per cent printed "6.2", expected "6.3". A breach of "round only at the end" (document 04 section 10).
  - D2, a negative zero is printed (function `rounded`). Invented input: minus 0.4 at zero places gives "-0", expected "0"; minus 0.004 at two places gives "-0.00", expected "0.00".
  - D3, a silent zero in PUB-64 (the series build's figures module). Invented input: the four tables present, one indicator row for activity 561 and 2022, no size row for that activity and year. Got establishments "0" and employees "0"; expected a refusal (MTH-09: never zero for an unknown).
  - D4, dated cancellations outside the calendar of card C2 are left out of the rule without notice but stay in the totals (the PUB-68 branch of the figures module; `bulk_months`). Invented input: three named months of 42, 9 and 8, one other month of 2, 4 in June 2025, 6 in December 2014 and 9 undated. Got a dated total of 71 and a share of 83; expected the calendar's own total and share, 61 and 97, with the outside rows counted apart, or a refusal that names the period.
  - D5, a sum of quantities whose unit the source does not state (`country_totals` of the figures module; an internal evidence file only). Invented input: two rows of one country with quantities 3 and 40. Got a quantity of 43; expected no such total (PUB-45: other units are counted, never combined).
- DONE SO FAR: The lead's ruling L-354 keeps S2-T03 in merge train A: the lead's real-cache run at the task's fix commit printed every value of PUB-62 to PUB-66 and PUB-68 to PUB-70 equal to the pack's figures, and the lead's count on the real cancelled-licence file on 2026-11-15 found 40,472 rows, 1,221 undated, 39,251 inside the calendar of card C2 and 0 outside it. A fix pass on the branch of task S2-T07 runs since 2026-11-15 (started again as a join-and-fix pass after the lead's ruling L-357 on the square root of the interval method). The verification's list of tests that could pass on wrong code (its section V7, in the task's log) goes to the same pass.
- OPTIONS: **Default:** the fix as the verification writes it for each defect (exact rationals up to the output and a sign-safe `rounded` for D1 and D2; a refusal for D3; a refusal or a separate count for D4; no summed quantity for D5), on S2-T07's branch only; `public_series.py` as merged by train A is not patched apart.
- NEEDED BY: the merge of task S2-T07, which does not merge without the fix. Closes when S2-T07's review confirms the five fixes, each with its planted test, on its approved commit.
- UPDATE: 2026-11-15, by the ledger of merge train C (task S2-T07): CLOSED. The five defects D1 to D5 are fixed on the final form of the calculation layer, commit 4bbaa98e91a3bd26b3eb6a7f9cfa94253b67b274 of the task's own change `6ccc85b..5090b40`. Each was reproduced red on the item's own invented inputs and fixed with its planted test: exact rationals up to the output and one rounding (D1), no negative zero (D2), a refusal for the empty size table (D3), a refusal by source and period for a dated row outside the calendar of card C2 (D4), no summed quantity (D5). The task's reviewer (Cognition SWE-2 High through Devin) confirmed the five fixes on the approved commit 5090b40c448a6657da4ecba9b0e2717243318294, check C1 PASS, with five values worked by hand. The item's closing rule is met.

## OI-177 — Secret-scanner evidence of S2-T12, pinned at its turn

- ID: OI-177
- TYPE: CLOSED (was PENDING)
- NEEDED: The pinned secret-scanner result of task S2-T12 — its command, the exact commit it ran on and its exit status — recorded at the task's turn, beside the hosted checks.
- WHY: Both external review rounds found no secret and no real custodian record in the patch, but the supplied evidence does not establish that the secret scanner passed; the first review's record point asks for the pinned result and the confirmation repeats it.
- DONE SO FAR: The lead's local checks at commit 0682edc ran the documentation check with the owner's private pattern list, exit 0; the reviews' own reading found nothing. At the train's turn the hosted secret scan of the first pushed head (pull request 51, closed unmerged) failed on one invented fixture key of the task's test, which is no secret; the value was changed inside the task's commit of the rebuilt train, and the scanner's command `uv run --locked python scripts/ci_history_scan.py scan` exits 0 at the joined work commit, as a row of the train's ledger records.
- OPTIONS: **Recommendation:** record the hosted scan's result on the merged head with the closing record of the train's pull request, and close this item there.
- NEEDED BY: the task's pull request (merge train A of slice S2).
- CLOSED: 2026-11-15, by the closing record of pull request 52 in PROGRESS.md: the hosted job secret-scan passed on the merged head `f169bcc4948047910f145bc6b5b3e352f7b637d2`, https://github.com/albarami/economic-investment-intelligence/actions/runs/43669038415/job/132674745610 , and the scanner's command exits 0 at that commit in the lead's head checks.

## OI-178 — Document 03 section 7.3 against the investment cache records

- ID: OI-178
- TYPE: OPEN
- NEEDED: Complete the deferred delivery records and reconcile the release column list of section 7.3 of document 03 with the records the reader writes, when decision record 0029 lands.
- WHY: The release column list still describes the earlier keys and record types, while the reader's cache holds page records and heading-led block records with their text items, links, order and parent; the confirmation review records the difference, and the lead ruled that decision record 0029 settles it.
- DONE SO FAR: The task's row of section 7.3 says what the reader writes and that the release table keeps DAT-143's rule (no paragraph column) meanwhile; the train join dropped the clause that had predicted the amendment under record 0026, which amends no word of DAT-143.
- OPTIONS: **Recommendation:** wait for record 0029's pull request and write the column list once from its accepted design, not piecemeal.
- NEEDED BY: decision record 0029's pull request; the release build that first uses `pub_investqa_record`.

## OI-179 — Coordinate digit runs and the release text-token scan

- ID: OI-179
- TYPE: OPEN
- NEEDED: The release scan of text tokens (TST-142) to read the release's coordinate values as numbers, not as text.
- WHY: The dashboard page's coordinate literals carry runs of exactly eight or eleven digits after the decimal point (the lead counted 36 `lat` and 74 `lng` literals on its cached versions); the digit-run check therefore applies to text fields only in the reader, and a release scan that read coordinates as text would flag them wrongly — or be weakened to pass, which rule 12 forbids.
- DONE SO FAR: The reader applies the check to text fields only; a coordinate given as a number literal is a number; the lead's run on the real pages found no text field of any record with such a run.
- OPTIONS: **Recommendation:** a note for the release tasks that own TST-142's scan: coordinates are numbers wherever the scan reads the built release.
- NEEDED BY: the release-build tasks and their scan, after slice S2.

## OI-180 — Loading assumptions of the investment readers

- ID: OI-180
- TYPE: ASSUMPTION
- NEEDED: The lead's confirmation (or the owner's, where a display decision depends on it) that the four loading rules the lead set are right; until confirmed they stand as written.
- WHY: The rules record how the page's own empty forms load: both coordinates exactly 0 is the page's empty form (129 records on the cached pages) and loads as null; a capex of 0 with an empty currency (3 records) loads a null unit; the capex unit is `Mn USD` from the page's labels and the record's currency; texts are kept exactly as published, white space at their ends included.
- DONE SO FAR: All four are built and are consistent with the lead's field-by-field decode of the real pages; documents 03 and 04 state the first three.
- OPTIONS: **Recommendation:** keep them; a changed page that breaks one fails the build by source name and is seen at the next fetch.
- NEEDED BY: the slice S2 gate, with the task's confirmation records.

## OI-181 — The agency's Arabic pages

- ID: OI-181
- TYPE: OPEN
- NEEDED: A later reading task for the Arabic side of the agency's site: the page list, the kind rules if the Arabic structure differs, and its own live comparison.
- WHY: The task's inventory holds the 27 English pages only; where the agency publishes a page in Arabic and in English, the quotation decision is that each language shows the agency's own text, so the Arabic pages are needed before that rule can be met.
- DONE SO FAR: The English inventory, reader and batch build are confirmed on the real pages; the record point that the inventory holds English pages only is recorded with the task.
- OPTIONS: **Recommendation:** schedule the Arabic reading as its own task when the quotation design (record 0029) is settled.
- NEEDED BY: the quotation display of decision record 0029; no version-1 gate unless the owner names it.

## OI-182 — Crosswalk lookups of `fdi_projects` are empty maps

- ID: OI-182
- TYPE: OPEN
- NEEDED: The committed, reviewed crosswalks that fill `source_country_iso3`, `municipality_code` and `place_key`.
- WHY: The lookups are empty maps in this task by design: country, municipality and place keys stay null until a reviewed crosswalk links them (location is kept as the page's text meanwhile), and no value is edited by hand.
- DONE SO FAR: The columns and the null rule are built and documented; the fields load empty on the real pages.
- OPTIONS: **Recommendation:** leave to the crosswalk tasks that own the country, municipality and gazetteer maps.
- NEEDED BY: the tasks owning the crosswalks and the cards that display mapped geography.

## OI-183 — Mutation-sweep pass over the merged-task survivors (with S2-T11, S2-T15)

- ID: OI-183
- TYPE: OPEN
- NEEDED: A mutation-sweep pass over the campaign survivors that lie outside their own tasks' changed lines, proposed for this task together with S2-T11 and S2-T15.
- WHY: Another task's mutation campaign recorded survivors outside its own lines that are lines of merged task S2-T01, and the lead proposed the sweep pass naming this task among the ones that carry it.
- DONE SO FAR: Nothing; proposed by the lead's ruling after the task's approval.
- OPTIONS: **Recommendation:** scope the sweep when the pass is briefed; the survivors' counts and locations are in the lead's campaign records, not this task's.
- NEEDED BY: the slice S2 gate or the affected tasks' pull requests, as the lead rules.
- UPDATE: 2026-11-15, by the ledger of merge train C (task S2-T21): the item stays open and gains the survivors of that task's campaigns that stand outside its changed lines. Before the join, the campaigns on the three fetch modules left 508 survivor or not-covered lines, of which one stood on a line of that task and is explained; three more mutants of two `__init__` methods could not be placed by their hunk text and stand on no line of the task. The second code review recorded them in the reviewer's words (Cognition SWE-2, proposed item P3): "the owed mutation campaign on the three fetch modules ended exit 1 with 504 survivors and 3 not-located `__init__` mutants, all on lines of earlier tasks, not of this task — the lead holds the list; closure belongs to the slice's follow-up task." On the joined local tree at 858141106b9160505bdb0db813e78a9593743d3d the campaigns ended with exit code 1 each, and none is a pass: `kinds.py` made 855, killed 560, survived 295; `build.py` made 544, killed 439, survived 100, not covered 5; `receipts.py` made 167, killed 107, survived 60; `terms_text.py` made 46, killed 37, survived 9. By the lead's placing against the lines the task changed: `receipts.py` none on the task's 4 lines; `build.py` none on its 61 lines; `kinds.py` one on its 41 lines, explained by its row, and two not located (two `__init__` lines); `terms_text.py` was not changed by the task. The loader `registry.py` is no longer part of the sweep: its campaign ends with 546 of 547 killed and the one survivor explained.

## OI-184 — One unexplained failure of the scripts unit suite in a quick-row run

- ID: OI-184
- TYPE: OPEN
- NEEDED: The name and the cause of one test of `scripts/tests` that failed once on the joined head of merge train A, or a recorded finding that it cannot be reproduced after the stated runs.
- WHY: Rule 39: a green re-run alone does not close a random failure. On 2026-11-15 the lead's quick-row run of the train's ledger commands ended its row for `uv run --locked python -m unittest discover -s scripts/tests -p 'test_*.py' -v` with exit code 1. The lead's ledger tool kept no output of a refused row then, so the failing test is not known.
- DONE SO FAR: The same suite passed on the same commit in the lead's local checks a few minutes before (exit 0) and in a rerun with its whole output kept a few minutes after (814 tests, OK, exit 0). The failed run overlapped the start of another task's web mutation campaign on the same machine: the lead's capacity reading rose from a load of about 16 to about 57 on 28 usable processors within those minutes, and that campaign was then stopped under the run's capacity rule. The ledger tool now keeps the whole output of every refused row. The suite's row of this ledger entry is a further run on the timing lane.
- OPTIONS: **Default:** watch the suite's next runs on this head and on main; if a test fails again, its kept output names it and this item takes the cause; if the next ten recorded runs of the suite pass, the item is closed as not reproduced, with those runs listed. No test is skipped, retried inside a run or given a longer limit for it.
- NEEDED BY: the slice S2 gate.

## OI-185 — The new read-only mount roles of the world build

- ID: OI-185
- TYPE: OPEN
- NEEDED: A later decision record on the new read-only mount roles of the `build-world` profile, with a security review.
- WHY: [decision 0033](docs/decisions/0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 9 leaves this part of document 05 Q11 to its own pass; it does not decide those roles.
- DONE SO FAR: Part A proves the existing proofs unchanged, explicit input arguments or settings, and snapshot staging in an explicitly supplied scratch folder.
- OPTIONS: **Default until decided:** S4-T02's “sandbox proof passes” criterion is NOT PROVED for the new inputs. The later record and security review must rule the roles before that criterion can be claimed.
- NEEDED BY: before task S4-T02's pull request claims that criterion.

## OI-186 — Register rows without a registration number

- ID: OI-186
- TYPE: OWNER DECISION
- NEEDED: Whether another number the register publishes can key a company whose row has no registration number.
- WHY: Document 03 section 6.1 makes the registration number non-null and the key joining attached records to their company; DAT-12 governs its validation.
- DONE SO FAR: [decision 0033](docs/decisions/0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 1 records 1,458 such rows in the commercial file as read on 2026-11-15.
- OPTIONS: **Default until the owner says otherwise:** count these rows and leave them out of the snapshot and stock, with their reason. An owner's decision on another published number would replace that default; no alternative key is settled here.
- NEEDED BY: before the first real world build.

## OI-187 — Proving DAT-24 for a register without activity codes

- ID: OI-187
- TYPE: OPEN
- NEEDED: A later decision establishing how the unchanged DAT-24 is proved for a register file without activity codes.
- WHY: The file publishes neither a code list nor a code column. Null activity codes are allowed when only text exists, but that does not prove DAT-24's code-distribution check.
- DONE SO FAR: [decision 0033](docs/decisions/0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 2 calls this an interim Part A state, not a final reading allowed by DAT-24.
- OPTIONS: **Default until decided:** the code-distribution check remains NOT PROVED and code fields stay null until a register file shows a code. A later decision must establish the proof; the requirement stays unchanged.
- NEEDED BY: before a finished `business_register.v1` feed or a release.

## OI-188 — Reviewing the register's activity texts

- ID: OI-188
- TYPE: OPEN
- NEEDED: The owner's step: a person's review of the register's 78 category texts and 8 type texts to ISIC sections.
- WHY: A company's ISIC section comes only through the reviewed activity map keyed by normalised activity text, never through a model, keyword or prefix (DAT-22; DAT-24).
- DONE SO FAR: [decision 0033](docs/decisions/0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 2 sets published category text as activity text, with type text where the category is empty.
- OPTIONS: **Default pending review:** only the reviewed activity map may place a company in an ISIC section. The person's review supplies that mapping; it does not replace it with inferred codes.
- NEEDED BY: before the first real world build can place a company in an activity cell of the calibration table.

## OI-189 — Specifying the workers' nationality shares

- ID: OI-189
- TYPE: OWNER DECISION
- NEEDED: An approved specification of the workers' nationality shares, answering document 05 Q17.
- WHY: A share needed by the build cannot be supplied without an approved specification; any committed share must be an ASSUMED manifest entry under SYN-06, with no real origin or origin in a Public split under SYN-13.
- DONE SO FAR: [decision 0033](docs/decisions/0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 4 routes group keys through `EII_NATIONALITY_GROUPS_FILE`, read by key and SHA-256.
- OPTIONS: **Default until the owner says otherwise:** commit no share; refuse with `missing_calibration` when a needed share lacks an approved specification. The approved specification would supply what is missing under the stated constraints.
- NEEDED BY: before the first real world build.

## OI-190 — Companies whose register publishes no activity

- ID: OI-190
- TYPE: OPEN
- NEEDED: How the financial centre's companies stand in the feed when their register publishes no activity, under DAT-21 and DAT-23.
- WHY: Their resolved share alone is below the suite's quality line, and their activity treatment remains open under document 05 Q19.
- DONE SO FAR: [decision 0033](docs/decisions/0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 5 requires them to be read, counted, name-checked for SYN-20 and given identifiers in canonical order.
- OPTIONS: **Default in Part A:** give them no jobs, report their count and exclude them from the December snapshot. Owner task S4-T01 or a later decision record must settle their feed treatment; Part B may add their rows.
- NEEDED BY: Part B of task S4-T02.

## OI-191 — Stating the calibration table's conditions in the repository

- ID: OI-191
- TYPE: OWNER DECISION
- NEEDED: Whether the calibration table's conditions may be stated in the repository.
- WHY: The lead reads these conditions as checks on an input's declared format, not values that generate records or belong in the manifest or generator constants.
- DONE SO FAR: [decision 0033](docs/decisions/0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 7 puts that reading to the owner without repeating the exact values.
- OPTIONS: **Default until the owner says otherwise:** the real table's declared-format file stays outside the repository beside the table; the committed stand-in has its own file with invented values. An owner's decision allowing the conditions to be stated would replace this restriction.
- NEEDED BY: no build waits for it.

## OI-192 — Mapping the register's establishment nationality

- ID: OI-192
- TYPE: OPEN
- NEEDED: A reviewed mapping from the register's two nationality columns to the closed list of `establishment_nationality`, read with OI-154.
- WHY: Neither column's values are keys of the owner's group list. The register holds nationality columns, so section 6.1's “null when the register shows none” is not the reason for Part A's null.
- DONE SO FAR: [decision 0033](docs/decisions/0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 8 leaves both columns unread in Part A.
- OPTIONS: **Default in Part A:** keep the field null and name it as not read in the snapshot's README and `coverage.json`. The reviewed mapping must settle how the published values reach the closed list.
- NEEDED BY: Part B of task S4-T02.

## OI-193 — Reading the register's statuses and licence dates

- ID: OI-193
- TYPE: OPEN
- NEEDED: A later decision record ruling the reading of the register's two statuses and two licence dates.
- WHY: Section 6.1 allows null statuses when no register file shows them; here the file does. Its date nulls mean not recorded or open-ended, neither of which Part A's unread fields establish.
- DONE SO FAR: [decision 0033](docs/decisions/0033-the-part-a-defaults-of-the-register-and-employment-world.md) item 8 names the later record as drafted, not yet in the pack.
- OPTIONS: **Default in Part A:** leave `registration_status`, `licence_status`, `licence_valid_from` and `licence_valid_to` null as “not read”, named in the README and `coverage.json`. Part B fills them after the later record rules their reading; no release uses this interim snapshot.
- NEEDED BY: Part B of task S4-T02.

## OI-194 — Fetching and confirming the census workbook schema

- ID: OI-194
- TYPE: OPEN
- NEEDED: The fetch and schema confirmation of `census_2020_workbook`.
- WHY: The source's row in document 04 still says “to be confirmed at slice S2”; confirmation is needed before the first real world build.
- DONE SO FAR: [decision 0033](docs/decisions/0033-the-part-a-defaults-of-the-register-and-employment-world.md), “Amended passages”, names this work among the open items to be entered with the record's ledger.
- OPTIONS: **Pending confirmation:** retain the row's “to be confirmed at slice S2” state. Fetching the workbook and confirming its schema would replace that pending state; the record names the work but supplies no confirmed schema or alternative source.
- NEEDED BY: before the first real world build.

## OI-195 — Places that rest on a source whose licence is not open or not confirmed stand until a go-live

- ID: OI-195
- TYPE: CLOSED for version 1 (was OPEN)
- NEEDED: Nothing in version 1. At a go-live: for each place of item 3 of [decision 0034](docs/decisions/0034-licence-questions-of-public-sources-are-answered-at-a-go-live.md), the licence or the terms of its source are settled by the legal route of that day.
- WHY: Item 5 of [decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md) allows no record, name or value of a source not under an open licence in the repository. An audit of the committed tree on 2026-11-15, which names places, kinds and counts and no value, found three places that broke it, and the review of the repair a fourth; no task was named for their removal, so the lead added task S2-T22 by a re-plan of that day (a repair of a rule's breach is not a new feature, and the scope stays frozen). The review's finding F3 named two further places that a repair cannot remove without changing what the pack means, and the audit left other groups unclassified. A forward repair changes the head of the base branch only: the removed values stay readable in the public history.
- DONE SO FAR: Task S2-T22 removed the four places from the head and added a guard with a planted violation, under one review and its confirmations by another maker. The lead had the licence statements of five sources read on 2026-11-15 (metadata and terms pages only, no data record). The lead prepared the remaining places as questions for the owner; the owner answered that version 1 is a personal, local project and that licence questions are answered at a go-live, not at this stage. Decision 0034 records that word, what was found and done, the reading, and in its item 3 the places that stand as they are until a go-live: the wage-band scheme of document 03 with DAT-16, the statutory minimum in documents 04, 05 and 07, the year bounds of the two investment rows, three committed review files, the registry rows on basis `none_stated`, and the public history. No registry row changed, and the history was not rewritten (rule 40 of AGENTS.md).
- OPTIONS: **Decided by the owner (decision 0034):** the listed places stand; tasks build from the pack as it is written; item 5 of decision 0026 stays the rule for every new commit; no further audit, repair task or review is opened for a reason of licence or terms in version 1. The lead keeps one list of the places for the go-live, outside the pack.
- NEEDED BY: a go-live; not before.

## OI-196 — The contract of `pub_place_fsq` and the pack's facts about the copy, corrected to the source's real shape

- ID: OI-196
- TYPE: OPEN
- NEEDED: The slice S2 gate confirms the corrections of fact that task S2-T15 made in its own change to documents 03 and 04, or names the one it does not accept.
- WHY: The pack described the copy from a reading of 2026-11-12. The lead's helpers read the copy's structure on 2026-11-14 (structure and counts only): its listing holds four dated releases, not three; its schema has one name field and no Arabic name, two parallel category lists and no confidence field. A contract column that the source cannot fill is a contract question, and nothing is manufactured for it (the lead's rulings of 2026-11-14 on the task's briefs and on its first return).
- DONE SO FAR: In the row of `pub_place_fsq` in document 03 section 7.3 the one `category` column gave way to `category_ids` and `category_labels`, semicolon-separated in the source's order, the form the pack already uses for `merged_ids` (the contract has no list type); the three dates are nullable as published; `name_ar` is always null. DAT-157 and the source row, the freshness row, the attribution text and PUB-102 of document 04 say four releases and the selection through the copy's own summary file. The release used stays the one the owner chose, dated 2025-01-10 (OI-96, closed, whose text still says three releases; this item is the correction of that count). The publisher now delivers newer releases only through a portal that needs an account, so the public copy is frozen; one release newer than the one used stands in the copy and is not used. Both confirmations of the task passed the changed rows.
- OPTIONS: **Recommendation:** accept the corrections at the slice gate as facts of the source; the product category of a place is returned beside its row by the reviewed mapping and is not a column of the table. Alternative: a contract change of its own task, if a consumer needs a column the source does not give.
- NEEDED BY: the slice S2 gate (PLN-25).

## OI-197 — The live fetch of `places_fsq` and its checks on real files are owed

- ID: OI-197
- TYPE: OPEN
- NEEDED: The lead runs `./eii build-public` for the source in its own shell and records the outcome; criteria 2 and 3 of S2-T15 stay open in TASKS.md until then.
- WHY: Every test of the task reads hand-made files with invented values. No builder, no reviewer and no ledger command has contacted the copy. The second confirmation asks, in the reviewer's words: "lead live fetch: check where the copy places its geo key, which GeoParquet version its files declare, and whether the pinned engine then reports the geometry column as BLOB with conversion off (L3 and L5)." The first confirmation: "EVIDENCE.txt section 6 leaves the whole ./eii test, live fetch and reviewed category-mapping rows pending." and "run the pending spatial-loaded parser proof."
- DONE SO FAR: The fetch, the selection and the parser are built and approved on fixtures. The lead ruled on 2026-11-14 that, if the real summary file carries no list of column orders, the source is refused by the stricter rule and that outcome is brought back as a ruling, not guessed. The whole test command runs with this ledger. The three checks that the second confirmation named are entered apart as OI-202, so that each gets its own recorded answer.
- OPTIONS: **Recommendation:** one run records: that only allow-listed hosts were contacted; the files selected and that they are the ones that cover Qatar (the `ASSUMPTION` of criterion 3); whether the summary carries the column orders; the three points of the reviewer above (OI-202); the parser run with the engine's spatial extension loaded; the receipt and hash of each fetched file. Nothing fetched is committed, and no value of a fetched row is written to a record.
- NEEDED BY: the slice S2 gate; before any task reads `pub_place_fsq` from real data.

## OI-198 — The reviewed rows of the category mapping of `places_fsq` are owed

- ID: OI-198
- TYPE: OPEN
- NEEDED: Reviewed rows in `custodian/publicdata/review/places_fsq_categories.csv`; criterion 7 of S2-T15 stays open in TASKS.md until then.
- WHY: The committed file holds its header alone, so every place is unmapped and gets no product category. The code refuses an unsigned row, an unknown target and a conflicting repeat, and its tests prove that on invented rows; the criterion asks for "a reviewed, committed category mapping".
- DONE SO FAR: The loader, its refusals and the count of unmapped places are built and approved. The first confirmation: "reviewed rows remain the lead's."
- OPTIONS: **Recommendation:** the lead enters the rows after the live fetch shows which source categories occur in the fetched files, each row with its mapping version, review status, reviewer role, review date and rationale, and no value edited by hand in a place's record. A source category is an identifier and a label of the publisher's own category list; the registry row records the licence the copy states with basis `dataset`, and item 5 of [decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md) stays the rule for the commit of the rows.
- NEEDED BY: the slice S2 gate; before S3-T12 shows a product category for a place of this source.

## OI-199 — The terms of the copy of `places_fsq` are recorded as "terms to be read"

- ID: OI-199
- TYPE: OPEN
- NEEDED: The pack requires the registry to record, for every source, the publisher's terms in its own words with the date read and the basis of use (PUB-97; [decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md)). The cells `basis_note` of the registry row `places_fsq/copy-2025-01-10` and `host_terms` of `custodian/publicdata/review/places_fsq_policy.yaml` say "terms to be read; checked 2026-11-14"; criterion 1 of S2-T15 ("the terms as read") stays open in TASKS.md until they hold the words read and the date.
- WHY: The row records the publisher, the licence the copy states (Apache License, Version 2.0, basis `dataset`), the licence address, the release and the publisher's copyright line. Terms of the host of the copy were not found on the day of the check. The first confirmation, in the reviewer's words: "Close the lead’s live terms reading and update the registry basis_note and policy host_terms from “terms to be read” ", and under its check K13: "The “terms to be read” cell is a lead record, not a code rejection." A source listed as "terms to be read" with the date checked stays in use; the terms never switch it off (decision 0026). This item is about the record alone: whether the terms allow a use is not weighed in version 1 and nothing is asked of the owner (item 1 of [decision 0034](docs/decisions/0034-licence-questions-of-public-sources-are-answered-at-a-go-live.md)).
- DONE SO FAR: The row and its test (`test_registry_row_records_publisher_licence_terms_and_release`) are built and approved; a missing terms address does not stop the fetch and a missing basis of use does (`test_missing_terms_do_not_stop_the_fetch_and_missing_basis_does`).
- OPTIONS: **Recommendation:** with the live fetch of OI-197, the two cells are filled with what the host's pages say on that day, in their own words with the date read, or with the sentence that none was found and the date; no other cell changes.
- NEEDED BY: the slice S2 gate.

## OI-200 — The engine's READ rows for the Parquet behaviour are owed in the reference notes

- ID: OI-200
- TYPE: OPEN
- NEEDED: The READ rows of the engine's official pages in `docs/REFERENCE_NOTES.md`, entered by the lead with the notes check (rule 42).
- WHY: The review's finding 6 found only observed entries for the Parquet behaviour the task uses. The lead ruled on 2026-11-14 that it enters the engine's rows (two pages, four statements) with the task's change, and that the facts of the file format, the compact protocol and GeoParquet are cited in the package README instead, because the checker's lists are closed. At the approved commit the notes hold the observed run R10 and statement S28 of the task and no new READ row. The first confirmation, in the reviewer's words: "The lead still owes the two DuckDB READ rows in docs/REFERENCE_NOTES.md; their absence is expressly a lead record, not a finding."
The lead ruled on 2026-11-15 that the rows stay this open item: nothing is added to an approved commit for them.
- DONE SO FAR: The package README cites the engine's configuration page for the conversion setting with its date read and quote, and the format's pages for the rest; the second confirmation passed those citations.
- OPTIONS: **Recommendation:** the lead enters the rows from the format check of 2026-11-14 in a documents change of its own after this task merges, and runs `uv run --locked python scripts/check_reference_notes.py`. Alternative: one line here says why the README's citation is the record and the rows are not entered.
- NEEDED BY: the slice S2 gate.

## OI-201 — Timeouts of the mutation campaigns of `places_fsq`: five to replay, two with no proven cause (rule 39)

- ID: OI-201
- TYPE: OPEN
- NEEDED: (a) The replay, alone and at normal load, of the five mutants of `footer.py` that time out on the joined tree. (b) The cause of the two timeouts of `_rows` in `parse.py` in the final campaign of fix pass 2.
- WHY: A timeout is reported apart from a kill, and a green re-run alone does not close an unexplained failure (rule 39). (a) The five are mutants of the fixture writer's loop for variable-length integers; the builder replayed each alone for eight seconds, none returned, and it names for each the change that keeps the loop from ending; the lead's campaign of the joined commit shows the same five (`timed_out=5`). (b) The two timed out while ordinary suites also ran on the machine and passed alone inside thirty seconds; in the lead's later campaign they did not time out and are survivors with their explained rows. The builder's words: "Concurrency is an observed circumstance, not a proven cause. Retain logs and investigate timing before closure; do not increase a timeout or erase failures to obtain green." The first confirmation: "Replay the five joined-footer timeout mutants alone; retain the two parser timeout incidents with their unproven timing cause."
- DONE SO FAR: The counts are kept as they were in the task's log; no timeout was raised and no result replaced. No test of the task failed at random in any recorded run: each failing run in the returns has its named cause (unformatted files, an import-order line, a digit literal in a fixture) and its corrected run.
- OPTIONS: **Recommendation:** the lead replays the five as a recorded step of this task and enters the outcome here; the two parser incidents stay open until a campaign of `parse.py` alone on a quiet machine and one under load are compared, or until one line says why the load is the cause.
- NEEDED BY: the slice S2 gate.

## OI-202 — Three checks of the live fetch of `places_fsq` that the second confirmation named

- ID: OI-202
- TYPE: OPEN
- NEEDED: Three recorded answers from the first live fetch of the source (OI-197): (a) where the files of the copy place their `geo` key; (b) which GeoParquet version the files declare; (c) what the pinned engine then reports as the type of the geometry column, with its GeoParquet conversion set off.
- WHY: The footer reader and the parser were built from the official pages and proved on hand-made files; no file of the copy has been read. The reading of the official pages of 2026-11-15 left twelve points; the lead ruled that none changes code, that five are stated in the package README as the reader's own allowances, and that two are checks of the live fetch. The second confirmation recorded them, in the reviewer's words: "lead live fetch: check where the copy places its geo key, which GeoParquet version its files declare, and whether the pinned engine then reports the geometry column as BLOB with conversion off (L3 and L5)." The answers decide whether the reader's allowances are ever used and whether the parser meets the column type it expects.
- DONE SO FAR: The package README names the reader's allowances as its own: they touch only the recorded box of a file, which the selection does not use, or end in a named refusal. `test_fsq_connection_disables_geoparquet_conversion` proves that the conversion is set off before any read, on a hand-made file. The second confirmation passed the README's citations and the allowances paragraph (its checks N1a to N1d).
- OPTIONS: **Recommendation:** the run of OI-197 records the three answers as header facts and yes-or-no answers only, with no value of a fetched row. If an answer differs from what the reader or the parser expects (a key in a place the reader does not read, a version the pages read do not cover, a column type other than the one the parser expects), the source is refused by its named error and the difference comes back as a ruling; nothing is guessed and no fixture is changed to fit.
- NEEDED BY: the slice S2 gate; before any task reads `pub_place_fsq` from real data.

## OI-203 — The human review of the activity spine on the real feeds

- ID: OI-203
- TYPE: OPEN
- NEEDED: A named person's review of the mandatory queue of the activity spine, code by code, recorded in `custodian/publicdata/review/activity_spine.csv` with the reviewer's role and date and with the binding file beside it. Criteria 1 to 3 of task S2-T04 stay unticked until then. Before that review, the queue is computed again with the supplier membership of the reviewed baskets of S2-T03, so that the supplier activities are in it.
- WHY: PUB-33 admits a mapping only when a person approves that the Arabic activity name fits the class title, and no model signs a review (the lead's ruling of 2026-11-15). The reader, the queue and their guards are built and approved; the reviewed data set is not delivered.
- DONE SO FAR: The lead's run on the real public cache at commit c193a12 (2026-11-15, counts only) reads 4,901 activity codes: 2,125 `unreviewed`, 1,369 `not_mappable_legacy` (a code that is not seven digits long) and 1,407 `not_mappable_invalid_prefix` (a seven-digit code whose first four digits are not a class of the classification file, which holds 419 classes). The review queue holds 243 codes; 349 rows are left out in four groups and counted. The committed review file holds one `unreviewed` row and claims no decision; the category list is empty. The run's record does not state the supplier membership it was given, and the builder's documented call passes an empty complete membership. OI-16 (who signs, and whether batches are allowed) is not decided.
- OPTIONS: **Default until a person is named:** no mapping is admitted and every consumer treats the spine as unreviewed. The review is done by the person OI-16 names, each code on its own unless the owner approves a batch rule.
- NEEDED BY: task S2-T08 (the Public pack assembly) for any figure by activity class; before the slice S2 gate.

## OI-204 — The terms of the classification file are not read

- ID: OI-204
- TYPE: OPEN
- NEEDED: The publisher's own words on the use of the classification file `cls_isic4`, with the date read, recorded in the registry row and in the terms cell of document 04; or the lead's decision on how they are recorded when the page that holds them is on a host the fetcher may not contact.
- WHY: PUB-03 holds the file's host on the allow-list. The helper's reading of 2026-11-15 found that the host's own pages carry only a footer line whose terms and copyright links lead to another host, which is not on the allow-list and was not contacted; the file itself carries no terms line. So `terms_url` cannot be a page of the allow-listed host.
- DONE SO FAR: Part 2 of S2-T04 confirmed the file's direct address, its extension and its two columns in the registry row and filled the "how fetched" cell of document 04; the licence fields are unchanged, the basis stays `none_stated` and `terms_url` stays empty. The release mode of the activity graph refuses the source. The terms cell of document 04 says that the exact wording and the date read are to be recorded and names the owner's decision as the basis (PUB-12).
- OPTIONS: **Default:** the row stays as it is and the graph's release mode keeps refusing titles from this source until the words are recorded. **Recommendation of the helper that read the host:** pass the point to task S2-T21, whose loader asks every row for the terms words and the date read under decision 0026.
- NEEDED BY: task S2-T21's join pass (its loader refuses a registry row without the two terms fields); before any release that shows a class title.

## OI-205 — One unexplained failure of the scripts unit suite in the builder's sandbox of S2-T05

- ID: OI-205
- TYPE: OPEN
- NEEDED: The name and the cause of the test of `scripts/tests` that failed in the build pass of task S2-T05, or a recorded finding that it cannot be reproduced after the stated runs.
- WHY: Rule 39: a green re-run alone does not close a random failure. On 2026-11-14 the builder of S2-T05 (OpenAI GPT-6 Astra through Codex) ran `uv run --locked python -m unittest discover -s scripts/tests -p 'test_*.py'` at the end of its pass and recorded exit code 1. Its wrapper kept only the trailing output, so the failing test and the suite's total are not known. The builder did not run it again and reported the cause as unknown.
- DONE SO FAR: The lead ran the same discovery at the task's local commit 00e3394b0a2d3cdaace7933a511ead58f9be5bf4 on the build machine on the same day: 708 tests, OK, exit 0. The independent reviewer read both records and judged that the failed run leaves no acceptance criterion unmet (REV-11). Two explained causes of an exit 1 of this suite are on record for other runs and are not shown to be the cause here: the interrupt test under a launch that ignores the interrupt signal (PO-S2-06), and, in a later pass of another task in another tool's sandbox, the two version tests failing because that sandbox's Node was outside the pinned line. The return of S2-T05 says that Node 22 was put first on the path for its runs.
- OPTIONS: **Default:** the item is closed as not reproduced when the suite's recorded runs on the joined head of merge train B5 and on main after the merge pass, with those runs listed; if a test of `scripts/tests` fails in a builder's sandbox again, its kept output names it and this item takes the cause. Builders' wrappers keep the whole output of a failed suite. No test is skipped, retried inside a run or given a longer limit for it.
- NEEDED BY: the slice S2 gate.

## OI-206 — The qualification that a keyed run of the spine triage needs

- ID: OI-206
- TYPE: OPEN
- NEEDED: The lead's decision, before any keyed run of `scripts/spine_triage.py`, whether the present qualification of the gateway covers the rubric, the language and the route that the triage of the activity spine would use, or which requalification is run first.
- WHY: [Decision 0014](docs/decisions/0014-typed-decision-gateway.md), section "What would change this decision", ties a qualification to its model, rubric, language and route. The tool refuses a keyed provider unless a qualification record names exactly those four, and the task's change holds no such record, so today every keyed run is refused. The plan of S2-T05 raised the question, and the lead's rulings for the build left it open on purpose: "Whether the present qualification covers this rubric is the lead's decision before any keyed run."
- DONE SO FAR: The task is built, reviewed and accepted with provider `none` and with recorded answers only; no keyed run and no live call was made by the builder, a test or the lead. The refusal is tested: a keyed request without a qualification record, and one whose record differs in the model, the rubric identifier, the rubric hash, the language or the route, are refused before a gateway object is made. OI-15 (human-labelled qualification sets) names "any changed model, rubric, language or route" under NEEDED BY; OI-16 names who signs a mapping.
- OPTIONS: **Default:** no keyed run of the triage tool; the queue is ordered with provider `none` or with recorded answers. A keyed run follows only after the lead records, with its evidence, a qualification for exactly this rubric, language and route, inside the token allowance of the owner's recorded answer to OI-18 and from the lead's own shell.
- NEEDED BY: the first keyed run of `scripts/spine_triage.py`; not needed by any gate, which all run with provider `none` (rule 27).

## OI-207 — Card C2's rule as written flags 42 of the 125 months

- ID: OI-207
- TYPE: OPEN
- NEEDED: A decision on the bulk-month rule of card C2 (document 07): it stays as written, or it is amended by a decision record.
- WHY: The lead's count over the pinned cancellations file (2026-11-14): 153,669 dated and 7,386 undated cancellations, the card's own counts; the median of the 125 months is 305 and the threshold 915; the rule flags 42 of the 125 months, among them every month of 2023 and of 2024, holding 89.7 per cent of the dated cancellations. The three months the card names hold 43.1 per cent, which is the card's printed share. So the card's own open question (which other months the rule flags) has the answer 42, and "excluding flagged months" is empty for 2023 and 2024, the year of the card's own worked example.
- DONE SO FAR: The lead changed no method (scope is frozen; a method amendment is a decision record). The data test `custodian/data_tests/test_pinned_methods.py` pins the three named months with their exact counts and their share 43.1, and the count of flagged months (42), their list and the share 89.7 as facts of the pinned file. It passed on the real cache at the approved commit of task S2-T07.
- OPTIONS: **Default:** the rule stays as written in version 1 and the method note lists the 42 months. Alternative: a median over a moving window, by decision record.
- NEEDED BY: task S2-T09 (the method cards), before the card's churn figure excluding flagged months is shown.

## OI-208 — The rounding of a negative half

- ID: OI-208
- TYPE: ASSUMPTION
- NEEDED: Confirmation that a negative exact half rounds away from zero in every displayed figure of the calculation layer.
- WHY: The pack says half-up and round once at the end (document 04 section 10) and does not say which way a negative half goes. The layer rounds half away from zero on the magnitude; tests pin it.
- DONE SO FAR: The lead's ruling of 2026-11-14 on the second verification of task S2-T07 took half away from zero as the assumption and asked for this item. The confirmation of 2026-11-15 read the rounding function and found one rounding and no second one.
- OPTIONS: **Default:** half away from zero, as built. Alternative: half towards positive infinity, which changes the sign rule of the one rounding function and the tests that pin it.
- NEEDED BY: task S2-T09, where the method cards state their rounding.

## OI-209 — 136 registry rows carry the marker `terms to be read` in place of the publisher's words

- ID: OI-209
- TYPE: OPEN
- NEEDED: For each source, the publisher's terms in its own words with the date read and the basis of use, recorded in document 04 and in the two registry fields `terms_words` and `terms_read_on` (PUB-12; item 3 of [decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md)). This is a record that the pack requires, made by reading each terms page as a visitor; it is not a question of permission, and under item 1 of the record no reading switches a source off.
- WHY: Task S2-T21 added the two fields to all 138 rows of `custodian/publicdata/sources.yaml` and read no terms page. 136 rows carry the marker `terms to be read` with the date checked, 2026-11-14; two rows (`fdi_projects` and `busy_gmaps`) carry words that document 04 already held, which a guard test compares with that document. Both acceptance criteria of S2-T21 ask for the publisher's own words for every source, so neither is ticked on the marker, and the task merged as its part A. At the train C head a raw read counts 139 rows and 136 markers; the additional places file row lacks both terms fields. The permitted registry test fails; see the train log and CHECK.md. This item records the original task debt, not a passing joined registry.
- DONE SO FAR: The loader requires both fields on every row and refuses an empty text or a date that is not a calendar date; the marker is the designed state of decision 0026 item 3 until a page is read (the first code review's REV-13). The fetch fingerprints every terms page a row records and prints a line when one changes. Raised by the builder of S2-T21 (xAI Grok 4.7; the return signs "SpaceXAI, Grok 4.7") as its proposed item (b).
- OPTIONS: **Default:** the lead's live reading fills the words and the date row by row, in document 04 first and then in the registry, so that the guard test covers each row as it is filled; a row whose page cannot be read as a visitor keeps the marker and says so.
- NEEDED BY: task S2-T08 (its criterion that every Public source in the release carries the publisher's terms in its own words), before the slice S2 gate; the two criteria of S2-T21 are ticked no earlier (its part B).

## OI-210 — Six rows are skipped with one phrase that names no actual technical reason

- ID: OI-210
- TYPE: OPEN
- NEEDED: The actual technical reason of each of the six rows that carry `skip_reason` `publisher_or_schema_unconfirmed` (`wage_sector`, `wage_bands_priv`, `work_hours_act`, `cpi_group`, `accident`, `bnd_muni_2025`), or the confirmation that the row can be fetched.
- WHY: PUB-13 and the second criterion of S2-T21 ask that an absent source is absent "with the actual reason recorded", and decision 0026 allows no absence for a reason of licence or terms. The rows carried `publisher_or_licence_unconfirmed` before the task; the loader now refuses a skip reason that names a licence or terms, and the build gave all of them the one phrase its brief named, which states no reason row by row.
- DONE SO FAR: The first build renamed nine rows. At the join onto the tree of train B three of them (`zone_population`, `est_census`, `census_hh_type_2020`) kept the licence cells and skip reasons that the tree had since confirmed, so six rows carry the phrase at `5147fdecdcac222a150464e0e43644d26f89d24d`. Raised by the builder of S2-T21 as its proposed item (c): the rows "stay skipped until the lead states the actual technical reason of each or confirms the row fetchable".
- OPTIONS: **Default:** the lead reads each source as a visitor and records the reason found (an unconfirmed file, address or schema, a failed check) or clears the skip; a row skipped for its licence alone becomes fetchable.
- NEEDED BY: task S2-T08 (source completeness), before the slice S2 gate.

## OI-211 — The release half of both criteria of S2-T21 is proved by the pack assembly

- ID: OI-211
- TYPE: OPEN
- NEEDED: Tests of task S2-T08 at the release boundary: every admitted source reaches the release whatever its terms words or basis, and a source absent for a technical reason reaches it as `NO_DATA` with its actual reason and caveat. The two criteria of S2-T21 are ticked with this item named beside them, never on fetch success alone.
- WHY: The fetch that S2-T21 changes assembles no release and shows nothing. The design review's finding F3 said so of the plan, and both code reviews carried it. The reviewer's words (Cognition SWE-2, proposed item P1 of both local code reviews): "acceptance criteria 1 and 2, release half: this commit proves the loader/fetch/registry half; that every admitted source reaches the release whatever its terms, and every technical absence reaches it as `NO_DATA` with its reason and caveat, is S2-T08's proof".
- DONE SO FAR: S2-T21 proves its own boundary on invented inputs: a cached file and a receipt for an admitted row; no usable output and the recorded reason for a technical absence. Task S2-T08 depends on S2-T21 and its second criterion already asks that every Public source in the release carries its terms "with no terms-based exclusion" under decision 0026. Raised first by the builder of S2-T21 as its proposed item (a).
- OPTIONS: **Default:** S2-T08's plan names the two tests and this item; when they pass on its approved commit, that task's ledger ticks the boxes of S2-T21 that then wait for nothing else.
- NEEDED BY: task S2-T08, before the slice S2 gate.

## OI-212 — DHA-102 is not updated by S2-T21

- ID: OI-212
- TYPE: OPEN
- NEEDED: What the second criterion of S2-T21 asks of document 17: "changed terms update document 17, DHA-102, where permission or a licence is needed for real use". The list of DHA-102 is brought in line with the registry's terms record when the words of OI-209 are read.
- WHY: The plan listed document 17 among its files; the build did not touch it, and its return says so under what is not proved. No terms page was read by the task, so no changed terms were seen; the fetch now prints a line when a recorded terms page changes, and nothing joins that line or the registry to the list of DHA-102.
- DONE SO FAR: Nothing in document 17. The builder named a machine check that joins the DHA-102 list to the registry as hardening that it did not build (PO-S2-65).
- OPTIONS: **Default:** the pass that records the publishers' words (OI-209) updates DHA-102 in the same change and the criterion's clause is judged then.
- NEEDED BY: the tick of the second criterion of S2-T21; before the slice S2 gate.

## OI-213 — One timed-out mutant of the loader's campaign was not classified

- ID: OI-213
- TYPE: OPEN
- NEEDED: The lead's replay, alone and at normal load, of the one mutant of `custodian/src/eii_custodian/publicdata/fetch/registry.py` that timed out, or a recorded finding that it cannot be named from the records.
- WHY: Rule 39: a green re-run alone does not close an unexplained failure. The lead's campaign of the loader on the joined tree, after the thin test pass, ended with the line `made=547 killed=452 survived=94 timed_out=1 not_covered=0 incomplete=0`. The runner prints a hunk for a survivor and for a not-covered mutant only, so the campaign's record holds no hunk for the timeout, and the builder of the mutation pass could not say whether it is a loop that cannot end or a slow mutant.
- DONE SO FAR: The three later campaigns of the module count `timed_out=0` with 546 of 547 killed; the builder's reading is that a new test may have killed the mutant before a timeout. That campaign's own line gives 7,481 seconds of wall time, where the later ones give about 1,000 seconds each; the records this item rests on do not say why.
- OPTIONS: **Default:** the lead names the mutant from the tester's own result store of that campaign if it is kept, replays it alone and records the result apart from killed mutants; if the store is gone, the item is closed as not reproducible with the three later count lines listed.
- NEEDED BY: the slice S2 gate.

## Change control

Close an item only with evidence and the named decision or test that resolves it. Record the closure in [PROGRESS.md](PROGRESS.md), preserve the earlier entry, and add a decision record for any material change. Do not silently delete an unresolved item.

## Proposed open items from reviews

Each item below was proposed by an independent reviewer outside the verdict ([REV-41](docs/15_REVIEWER_CHECKLIST.md)), or was found by the lead after a merge where its RAISED BY line says so. The follow-up task of its slice closes it before the slice gate, by a fix or by one line saying why it is not valid or is out of scope under REV-42 ([decision 0015](docs/decisions/0015-review-rounds-and-the-scope-of-repository-checks.md)).

### PO-S0-01 — Count list of the S0-T02 plan against the delivered sub-cases

- ID: PO-S0-01
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review round 1 of S0-T02 (Zhipu AI GLM-5.3 High), 2026-11-12, proposed item P1
- CONCERNS: REV-16 (the work follows the plan)
- EVIDENCE: `test_member_list_wrong_fails` runs 8 sub-cases where the plan's count list says 7, `test_missing_and_unparsable_lock_fail` counts 4 where it says 3, `test_lock_ignores_self_and_third_party_edges` runs three blocks with no count assertion where it says 2, and `test_output_order` asserts no count where it says 3; the ledger says only that sub-cases were added. The plan is a project record held by the owner, not in this repository.
- NEEDED: the plan record states the delivered sub-cases and counts, or the additions are annotated.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-13, by S0-T15: the additions are annotated: the ledger of this task in [PROGRESS.md](PROGRESS.md) states the delivered sub-cases of the four tests against the plan's count list. The plan record itself is held by the owner outside this repository and is not changed.

### PO-S0-02 — Suppression comments ahead of the checks of S0-T04

- ID: PO-S0-02
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review round 1 of S0-T02 (Zhipu AI GLM-5.3 High), 2026-11-12, proposed item P2
- CONCERNS: REV-15 (no check weakened)
- EVIDENCE: `scripts/tests/workspace_fields.py` carries `# noqa: E402` for the bottom import that the split into two modules needs, and `scripts/tests/test_workspace_metadata.py` carries several `# type: ignore[...]` comments; no check that runs today is weakened.
- NEEDED: S0-T04 confirms that its ruff selection accepts that import without the suppression and that each type-ignore marker matches its type checker, or removes them.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-12, by S0-T15: the bottom re-export and its `# noqa: E402` are removed from `scripts/tests/workspace_fields.py`; case tables stay in `scripts/tests/workspace_fields_tables.py` and `scripts/tests/test_workspace_metadata.py` imports them there, so ruff needs no suppression and `__all__` lists no undefined names; proved by `uv run --locked ruff check .` and the workspace metadata tests. `scripts/tests/test_workspace_metadata.py` holds 0 `type: ignore` comments; the item's "several" is stale.

### PO-S0-03 — A file write that the next statement overwrites in the test of the Hypothesis profile

- ID: PO-S0-03
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review round 1 of S0-T05, part 1 (Zhipu AI GLM-5.3 High), 2026-11-12, proposed item P1
- CONCERNS: REV-13, as the reviewer names it (a statement with no effect, left from an edit)
- EVIDENCE: `test_profile_is_eii_and_survives_a_ci_variable` in `scripts/tests/test_test_bootstrap.py` writes `fx/profile/test_profile.py` twice in a row; the second write replaces the file before anything reads it, so the first has no effect. No behaviour is wrong.
- NEEDED: the first write is deleted, and the test still passes.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-12, by S0-T15: the first of the two writes of `fx/profile/test_profile.py` in `test_profile_is_eii_and_survives_a_ci_variable` is deleted; proved by the unchanged `test_profile_is_eii_and_survives_a_ci_variable` in `scripts/tests/test_test_bootstrap.py`.

### PO-S0-04 — The test support of the Python checks makes a folder that no ignore rule covers

- ID: PO-S0-04
- TYPE: CLOSED (was OPEN)
- RAISED BY: the lead, 2026-11-12, while checking S0-T12; not a reviewer's item
- CONCERNS: rule 13 of [AGENTS.md](AGENTS.md) (tests use only their documented repository, cache and temporary paths); REV-42 (the same result on a fresh clone)
- EVIDENCE: `home_tmpdir()` in `scripts/tests/pychecks_support.py`, delivered by S0-T04, creates the folder `.overnight/tmp` under the repository root, and the tests of the Python checks make their temporary folders in it. No rule of `.gitignore` covers that folder, so on a fresh clone the tests leave an untracked folder behind. The cause was the wording of the build brief on temporary folders. No verdict so far depends on it.
- NEEDED: the support takes its temporary folders from `tempfile` under the environment's settings, and the tests leave nothing behind in the checkout.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-12, by S0-T15: `home_tmpdir()` in `scripts/tests/pychecks_support.py` returns `Path(tempfile.gettempdir())` and creates nothing under the repository root; each call in `scripts/tests/test_pychecks_config.py`, `scripts/tests/test_pychecks_ruff.py` and `scripts/tests/test_pychecks_mypy.py` that creates a folder under the returned directory removes that folder by `addCleanup`. Proved by the new test `test_home_tmpdir_is_the_system_temp` in `scripts/tests/test_pychecks_config.py`, which fails on the old support.

### PO-S0-05 — A dead assignment in a test of the extension files

- ID: PO-S0-05
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review round 1 of S0-T11, part 1 (Zhipu AI GLM-5.3 High), 2026-11-12, proposed item P1
- CONCERNS: REV-16 (house style: a target, never a verdict finding)
- EVIDENCE: `test_launcher_binds_the_checked_files` in `scripts/tests/test_sandbox_extensions.py` assigns `binaries` from the files with an empty suffix and assigns it again in the next statement from the files whose name ends in `.duckdb_extension`; the first assignment has no effect.
- NEEDED: the first assignment is removed, and the tests still pass.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-12, by S0-T15: the dead first `binaries` assignment and its comment are removed from `test_launcher_binds_the_checked_files` in `scripts/tests/test_sandbox_extensions.py`; proved by the unchanged `test_launcher_binds_the_checked_files`.

### PO-S0-06 — Two exit-1 paths of the test command print no meaning line

- ID: PO-S0-06
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review round 1 of S0-T09 (Google Gemini 4 Carbon), 2026-11-12, proposed item P2
- CONCERNS: OPS-26 (one exit code of the table and its meaning on failure); OI-80
- EVIDENCE: every command under `scripts/commands/` prints `eii: exit <code>: <meaning>` on failure. The launcher `eii` exits 1 when `uv` is not found, and `scripts/run_tests.py` exits 1 when a suite of `./eii test` fails; neither prints that line, and OI-80 names only the usage line of `./eii test`. Both paths were delivered by S0-T05 and were outside the scope of S0-T09.
- NEEDED: OI-80 names the two paths, or they print the meaning line.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-12, by S0-T15: OI-80's DONE SO FAR now names the two exit-1 paths that print no meaning line and keep their own lines (the launcher when `uv` is not found, and `./eii test` when a suite fails).

### PO-S0-07 — Planted bad anchors only in one table of the notes fixture

- ID: PO-S0-07
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review of S0-T13 part B (Zhipu AI GLM-5.3 High), 2026-11-12, proposed item P1
- CONCERNS: REV-15; TST-01 (planted violations of the rule `pack-cite`)
- EVIDENCE: every planted bad anchor of `test_pack_cites` in `scripts/tests/test_reference_notes_rows.py` sits in one row of the Statements table. The earlier planted cases in the confirmation table and in the coverage table, and the missing-file case, were removed with the line form. The anchor check is called for both tables and the real notes pass through it, but a change that dropped the call for one of them would fail no planted test.
- NEEDED: one planted bad anchor in the confirmation table, one in the coverage table, and one anchor into a missing file, each proved by the notes test modules.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-12, by S0-T15: `test_pack_cites` in `scripts/tests/test_reference_notes_rows.py` gained three sub-cases (a8 a bad anchor in the Slice S1 confirmation table, a9 a bad anchor in the coverage table, a10 an anchor into a missing file), each expecting the exact `pack-cite` FAIL line; each is proved by removing the `check_cite` call for its table, which leaves that line unreported.

### PO-S0-08 — The other side of the anchor masking has no committed test

- ID: PO-S0-08
- TYPE: CLOSED (was OPEN)
- RAISED BY: the lead, 2026-11-12, while reading the build of S0-T13 part B, and the independent review of that part (Zhipu AI GLM-5.3 High), proposed item P2
- CONCERNS: REV-15 (the claim-word rule of the notes check)
- EVIDENCE: `mask_verified_anchors` in `scripts/pack_anchors.py` blanks a verified anchor before the claim-word scan. The tests hold one control: a claim word inside a verified row anchor is not reported. The lead probed the other side on 2026-11-12 with the tests' own fixture: anchor-shaped text that does not verify (a row that is not in the section, an absent heading, an absent file) is not masked and its claim word is reported, and a claim word outside a verified anchor is reported. No committed test holds those cases.
- NEEDED: the three cases of text that does not verify, and the case of a word outside a verified anchor, as committed sub-cases of the claim-word test.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-12, by S0-T15: `test_claim_words` in `scripts/tests/test_reference_notes_rows.py` gained four sub-cases beside `control-fast-inside-verified-anchor`: a row not in the section, an absent heading, an absent file, and a claim word outside a verified anchor; each expects exactly one `claim-word` FAIL line.

### PO-S0-09 — Five rows of the pin record repeat one section anchor

- ID: PO-S0-09
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review of the S0-T12 follow-up (Google Gemini 4 Carbon), 2026-11-12, proposed item P1
- CONCERNS: REV-16 (house consistency: a target, never a verdict finding)
- EVIDENCE: the rows `@deck.gl/core`, `@deck.gl/layers`, `@deck.gl/geo-layers`, `@deck.gl/extensions` and `@deck.gl/maplibre` of `pins.toml` hold the `cite` value `docs/10_FRONTEND.md section "Stack and pins"; docs/10_FRONTEND.md section "Stack and pins"`: the two lines that the old values named lie in one section, so the conversion wrote the same anchor twice. The row `maplibre-gl` cites its table row first and the section second.
- NEEDED: each of the five rows cites the table row of its package in that section first, or the repeated anchor is written once.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-13, by S0-T15: the `cite` value of `@deck.gl/core`, `@deck.gl/layers`, `@deck.gl/geo-layers`, `@deck.gl/extensions` and `@deck.gl/maplibre` in `pins.toml` is `docs/10_FRONTEND.md section "Stack and pins"` once. Proved by those five rows.

### PO-S0-10 — The closure line of PO-S0-04 says more than the change did

- ID: PO-S0-10
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review of S0-T15 part A (Alibaba Qwen 3.8 Max Thinking), 2026-11-12, proposed item P1
- CONCERNS: REV-17 (documents current)
- EVIDENCE: the CLOSED line of PO-S0-04 says "every test that takes a folder from it removes it by `addCleanup`". The change added the cleanup to one caller, `test_support_module_contract` in `scripts/tests/test_pychecks_config.py`, and left the other eight call sites as they were (five in `scripts/tests/test_pychecks_config.py`, one in `scripts/tests/test_pychecks_ruff.py`, two in `scripts/tests/test_pychecks_mypy.py`). The requirement of PO-S0-04 itself is met: `home_tmpdir()` returns the system temporary folder and creates nothing under the repository root.
- NEEDED: an appended line says what the change did, or the other call sites remove what they create.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-13, by S0-T15: every call of `home_tmpdir()` in `scripts/tests/test_pychecks_config.py`, `scripts/tests/test_pychecks_ruff.py` and `scripts/tests/test_pychecks_mypy.py` was read; each call that creates a folder under the returned directory already removes it by `addCleanup`, so no test was changed, and the last clause of PO-S0-04 now states that. Proved by those calls.

### PO-S0-11 — One sentence of decision record 0020 says more for each document than its change

- ID: PO-S0-11
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review of S0-T08 part B (Cognition SWE-2 High), 2026-11-12, proposed item P1
- CONCERNS: REV-16 (the work follows the plan and the standards)
- EVIDENCE: the consequences of [decision 0020](docs/decisions/0020-freeze-bundle-check-and-project-database-port.md) say that documents 08, 12, 13, 14 and 16 read "normal severity" through the corrected preflight table and use the documented default address. Document 16 holds no "normal severity" phrase (its change is the port), and documents 08, 12 and 14 name no address. The reviewer calls a collective reading defensible.
- NEEDED: the sentence is corrected in the way the change control of decision records allows, or one line says why it stands.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-13, by S0-T15: an accepted decision record is amended only by a new record (AGENTS.md rule 46); the sentence reads collectively, which the reviewer calls defensible; what each document changed is in the record's amended documents and in PROGRESS.md. No file of the record changes.

### PO-S0-12 — The ledger of S0-T08 part B names another reviewer than the one who gave the verdict

- ID: PO-S0-12
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review of S0-T08 part B (Cognition SWE-2 High), 2026-11-12, proposed item P2
- CONCERNS: REV-17 (PROGRESS.md current)
- EVIDENCE: the task log of S0-T08 part B in [PROGRESS.md](PROGRESS.md) names a Google model as the reviewer. The tool that was to run that review refused the job before it began, and the lead gave the review to Cognition SWE-2 High through the Devin command-line tool, whose verdict is the one review of the part. The closing record of the part, appended to PROGRESS.md with this entry, names the reviewer who gave the verdict; the earlier row is not rewritten.
- NEEDED: the reviewer of the follow-up task checks that the appended record corrects the reviewer line.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-13, by S0-T15: the closing record of part B in PROGRESS.md (section heading "S0-T08: independent review of part B: APPROVED") names the reviewer who gave the verdict and says what happened; the earlier row is not rewritten.

### PO-S0-13 — Status lines and the status table do not name decisions 0019 and 0020

- ID: PO-S0-13
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review of S0-T08 part B (Cognition SWE-2 High), 2026-11-12, proposed item P3
- CONCERNS: REV-17 (documents current)
- EVIDENCE: documents 02, 08, 12, 13, 14 and 16 were amended by decision 0020 on 2026-11-12, and the pack by decision 0019 on the same day. Their header status lines, and their rows in the table of section "Status on 2026-11-12" of [docs/README.md](docs/README.md), list decisions 0016 to 0018 only, although each amending decision is listed by precedent.
- NEEDED: one sweep of the status lines and of the table rows, now that both records are merged.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-13, by S0-T15: the header status lines of documents 02, 08, 12, 13, 14 and 16 name decision 0020 beside the decisions they already listed, and each status cell for documents 01 to 17 and the glossary in section "Status on 2026-11-12" of [docs/README.md](docs/README.md) matches that document's header. Proved by those header rows and that table.

### PO-S0-14 — An unused parameter of a test helper of the history scan

- ID: PO-S0-14
- TYPE: CLOSED (was OPEN)
- RAISED BY: second independent review of round 1 of S0-T07 (Google Gemini), 2026-11-12, proposed item P2; raised again by review round 2 (xAI Grok 4.7), 2026-11-13, proposed item P1
- CONCERNS: REV-13, as the reviewer names it (code with no effect)
- EVIDENCE: `history_repo` in `scripts/tests/ci_support.py` takes a parameter `shallow` whose branch fetches from a remote that the fresh scratch repository does not have; no test passes it as true. `test_shallow_checkout_refusal` in `scripts/tests/test_ci_history_scan.py` replaces the git call instead of making a shallow clone.
- NEEDED: the parameter is removed, or the test makes a real shallow clone of a local repository.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-13, by S0-T15: the parameter `shallow` of `history_repo` in `scripts/tests/ci_support.py`, the two lines only it reaches, and the argument at every call are removed. No test changes its meaning. Proved by `scripts/tests/ci_support.py`, `scripts/tests/test_ci_history_scan.py` and `scripts/tests/test_ci_plants.py`.

### PO-S0-15 — The sections of this file are out of numeric order

- ID: PO-S0-15
- TYPE: CLOSED (was OPEN)
- RAISED BY: the lead, 2026-11-12, after three pull requests were updated with the base branch; not a reviewer's item
- CONCERNS: REV-17 (documents current; house style: a target, never a verdict finding)
- EVIDENCE: three pull requests had each appended open items at the same place of this file. The updates with the base branch kept every line of both sides, the base branch's first, so OI-110 to OI-112 stand before OI-96 to OI-103, and OI-95 and OI-104 to OI-108 after them. No item is lost or changed.
- NEEDED: the sections are put back in numeric order, with no change of their text.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-13, by S0-T15: the sections that begin with "## OI-" stand in ascending numeric order, and the move changed no line inside a section. Proved by the order of those headings in this file and by a comparison of every section with its text before the move. Two sections, OI-13 and OI-95, are closed by this same task with the evidence of S0-T14; that is their only change.

### PO-S0-16 — Two refusals of the case-table validator have no planted table of their own

- ID: PO-S0-16
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review round 2 of S0-T07 (xAI Grok 4.7), 2026-11-13, proposed item P2
- CONCERNS: TST-04 (planted failures), as the reviewer's evidence implies; the rule of the plan, a closed case table, has its one planted violation
- EVIDENCE: `validate_cases` in `scripts/ci_plants.py` refuses a repeated case name and an unregistered plant. The tests plant a duplicated guard name only, so deleting those two refusals leaves the suite green.
- NEEDED: one planted table for each of the two refusals, or one line saying why the rule's one planted violation suffices.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-13, by S0-T15: `test_one_case_per_guard` in `scripts/tests/test_ci_plants.py` plants a repeated case name and an unregistered plant, and each raises `PlantError`. Proved by removing each matching refusal (the condition with its raise) from `validate_cases` in turn, which fails that test, and restoring it; `scripts/ci_plants.py` is unchanged.

### PO-S0-17 — The same three identifiers head two sets of rows in document 17

- ID: PO-S0-17
- TYPE: CLOSED (was OPEN)
- RAISED BY: the lead, 2026-11-13, after pull requests 17 and 20 merged; not a reviewer's item
- CONCERNS: REV-16, pinned names are used exactly, and REV-17
- EVIDENCE: Two pull requests each added three rows under DHA-81, DHA-82 and DHA-83. Section "Public and investment sources if hosted publicly" holds the traffic provider, the relative busyness of named venues and the weather history. Section "Hardening register" holds the three AppArmor entries. PROGRESS.md records the register rows under those identifiers.
- NEEDED: The register rows keep DHA-81, DHA-82 and DHA-83. The three rows of section 6 become DHA-85, DHA-86 and DHA-87. Every citation that means the section 6 rows follows.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-13, by S0-T15: the section 6 rows are DHA-85, DHA-86 and DHA-87 and the section 9 rows stay DHA-81, DHA-82 and DHA-83; OPS-69, DHA-51, the open-questions line and the sources line of document 17 that mean the section 6 rows now cite them (the sources line cites DHA-84 to DHA-87, with the forecast row). Proved by those rows in [17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md) and by OPS-69 in [13_DEPLOYMENT_AND_OPERATIONS.md](docs/13_DEPLOYMENT_AND_OPERATIONS.md). PROGRESS.md was not changed; its citations name the register rows.

### PO-S0-18 — A docstring of a preflight test names the old counts

- ID: PO-S0-18
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review of S0-T08 part C (Zhipu AI GLM-5.3 High), 2026-11-13, proposed item P1
- CONCERNS: REV-16 (house style: a target, never a verdict finding)
- EVIDENCE: the docstring of `test_foundation_keeps_other_severities` in `scripts/tests/test_preflight_run.py` said "first five status 1, last two 0". Since part C the method has eleven labels, of which the first nine give exit status 1 and the last two 0.
- NEEDED: the docstring says what the method does.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-13, by S0-T15: the docstring reads "first nine status 1, last two 0"; the method's assertions are unchanged and the guard suite passes.

### PO-S0-19 — The plan of S0-T08 part C counts fewer test methods than were delivered

- ID: PO-S0-19
- TYPE: CLOSED (was OPEN)
- RAISED BY: independent review of S0-T08 part C (Zhipu AI GLM-5.3 High), 2026-11-13, proposed item P2
- CONCERNS: REV-16 (the work follows the plan)
- EVIDENCE: the plan's section on files and counts names six added test methods and forty-nine after part C; the build added twelve and the ledger records fifty-five. The six further methods were added by the builder's break pass for breaks that no test had caught.
- NEEDED: one line that reconciles the two counts.
- CLOSED BY: S0-T15
- CLOSED: 2026-11-13, by S0-T15: the ledger of this task in [PROGRESS.md](PROGRESS.md) states the reconciliation by test module (forty-nine planned, six added by the break pass, fifty-five delivered).

### PO-S1-01 — The commit guard's list lacked the two keys of decision 0019

- ID: PO-S1-01
- TYPE: CLOSED (was OPEN)
- RAISED BY: gate review of slice S0, round 1, designated reviewer (Google Gemini), 2026-11-13, proposed item P2; found by the lead's own sweep on the same day
- CONCERNS: OPS-71; TST-141 (the commit guard of task S0-T06)
- EVIDENCE: `SECRET_NAMES` in `scripts/commit_guard.py` held `ANTHROPIC_API_KEY`, `JEV_PRO_API_KEY` and `EII_DATABASE_URL`. The variable table of document 13 marks `TOMTOM_API_KEY` and `EARTHDATA_API_KEY` as never printed as well, and the guard's rule for its list is that table (OI-92).
- NEEDED: the two names join the list, so that a staged copy of either local value is refused.
- CLOSED BY: S0-T16
- CLOSED: 2026-11-13, by S0-T16: the list holds the five names. Proved by `test_new_key_staged_value_refused`, `test_new_key_short_value_fails_closed` and `test_new_key_clean_file_passes` in `scripts/tests/test_hooks_guard.py`, each for both names, from the environment and from a fixture file.

### PO-S1-02 — The boundary guard's list of environment names does not hold the night-lights key

- ID: PO-S1-02
- TYPE: CLOSED (was OPEN)
- RAISED BY: gate review of slice S0, round 1, designated reviewer (Google Gemini), 2026-11-13, proposed item P1
- CONCERNS: ARC-81, as the reviewer names it (the variables that belong to build and evaluation tooling only)
- EVIDENCE: `ENV_NAMES` in `scripts/tests/import_boundary_guard.py` holds `EII_DECISION_PROVIDER` and `JEV_PRO_API_KEY`. Document 02 says that `EARTHDATA_API_KEY` belongs to build and evaluation tooling only and is read by the public fetchers of `./eii build-public`; no test refuses a reference to it under `product/` or `core/` (OI-52).
- NEEDED: the guard refuses a reference to `EARTHDATA_API_KEY` under `product/` and `core/` while `custodian/` may read it, with one planted violation; or one line saying why it is not needed.
- CLOSED BY: S1-T10
- CLOSED: 2026-11-14, by S1-T10: the import-boundary guard refuses `EARTHDATA_API_KEY` under `product/` and `core/` and allows it in the custodian plane and the tooling; `TOMTOM_API_KEY` stays allowed in the product plane. Proved by `test_earthdata_product_and_core` and `test_earthdata_custodian_and_tooling_tomtom_product_allowed` in `scripts/tests/test_s1_followup.py`.

### PO-S1-03 — Document 17 and its identifiers are outside the documentation check

- ID: PO-S1-03
- TYPE: CLOSED (was OPEN)
- RAISED BY: gate review of slice S0, round 1, designated reviewer (Google Gemini), 2026-11-13, proposed item P3
- CONCERNS: TST-140
- EVIDENCE: `REQUIRED_FILES` of `scripts/check_docs.py` does not hold `docs/17_DEPLOYMENT_HARDENING.md`, and `REQUIREMENT_PREFIXES` does not hold `DHA`. An identifier of document 17 that heads two rows therefore passes the check; PO-S0-17 was such a case and was found by hand.
- NEEDED: the file and the prefix join the two lists, with one planted violation each; or one line saying why not.
- CLOSED BY: S1-T10
- CLOSED: 2026-11-14, by S1-T10: the documentation check requires `docs/17_DEPLOYMENT_HARDENING.md` and checks the `DHA` identifiers. Proved by `test_hardening_file_required`, `test_duplicate_hardening_identifier` and `test_unknown_hardening_identifier` in `scripts/tests/test_s1_followup.py`.

### PO-S1-04 — No test compares the tables of the documents with the lists the code holds

- ID: PO-S1-04
- TYPE: CLOSED (was OPEN)
- RAISED BY: the lead, 2026-11-13, from the cause of the rejected first round of the slice S0 gate
- CONCERNS: OPS-06; OPS-71; TST-141
- EVIDENCE: The first round of the slice S0 gate was rejected because `CHECKS` of `scripts/preflight.py` held fifteen of the seventeen rows of the preflight table of document 13, and `.env.example`, `ENV_EXAMPLE_NAMES` of `scripts/check_tree.py` and `SECRET_NAMES` of `scripts/commit_guard.py` lacked the variables that decision 0019 had added to the variable tables. Each list was right when its task was built and went stale when a later decision changed its table. No test reads a table and its list together, so nothing failed.
- NEEDED: for each of these lists, one test that reads the table of the document and the list in the code and fails on any difference, with one planted violation each; or one line saying why not.
- CLOSED BY: S1-T10
- CLOSED: 2026-11-14, by S1-T10: `scripts/tests/test_operations_parity.py` reads the tables of document 13 by section heading and column and compares them with `.env.example`, `ENV_EXAMPLE_NAMES` of `scripts/check_tree.py`, `SECRET_NAMES` of `scripts/commit_guard.py` and `CHECKS` of `scripts/preflight.py`, and the code was brought to the document. Proved by `test_document_and_code_inventories`, `test_added_table_row_is_refused` and `test_removed_code_name_is_refused`.

### PO-S1-05 — The hardening lists of the slice S1 spikes are not in the register of document 17

- ID: PO-S1-05
- TYPE: CLOSED (was OPEN)
- RAISED BY: the lead, 2026-11-13, with the ledger of task S1-T04
- CONCERNS: TASKS.md, section "Queue rules" (hardening beyond an acceptance criterion is listed, not built); document 17, section 9
- EVIDENCE: Six tasks of slice S1 are built at the same time, so no builder edits document 17. Each task log of the slice in [PROGRESS.md](PROGRESS.md) records, in its line "Hardening listed, not built", the points its plan and its builder set aside.
- NEEDED: one entry of the hardening register for each point of those lines that is not needed in version 1, each with its origin; or one line saying why a point needs no entry.
- CLOSED BY: S1-T10
- CLOSED: 2026-11-14, by S1-T10: section 9 of [17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md) holds DHA-103 to DHA-127, DHA-129 and DHA-130, one entry with its origin for each point of the seven lines "Hardening listed, not built" of the slice's task logs that version 1 does not need; each point that version 1 needs belongs to a task of the plan, as the return of the task's correction pass accounts point by point.

### PO-S1-06 — The product manifest does not declare the routing engine and the grid library that the areas spike imports

- ID: PO-S1-06
- TYPE: CLOSED (was OPEN)
- RAISED BY: the reviewer of task S1-T03 (xAI Grok 4.7, through the Cursor command-line tool), 2026-11-13, point P1 of its verdict on pull request 33 (REV-17)
- CONCERNS: BE-82; ARC-88; OI-60; OI-116
- EVIDENCE: `product/src/eii_product/areas_spike/engine.py` imports `valhalla`, and `shapes.py` and `snap.py` of the same package import `h3`, while `product/pyproject.toml` declares neither: both packages sit in the root dependency group `engine` (the build ruling of the task, for the reason OI-60 gives). `product/README.md` states that home. No open item records that the task which builds the area tool must declare them in the product manifest or keep the exception; OI-116 records the same kind of gap for FastAPI only.
- NEEDED: one sentence in an open item (OI-116 or OI-120) that names the task which declares `pyvalhalla` and `h3` in `product/pyproject.toml` together with the change of the clean-environment guard, or one line saying why the root group stays their home.
- CLOSED BY: S1-T10
- CLOSED: 2026-11-14, by S1-T10: the sentence its NEEDED asks for stands in OI-116, as its update of 2026-11-14: task S3-T04 declares `pyvalhalla` and `h3` in `product/pyproject.toml` together with the change of the clean-environment guard; until then both stay in the root group `engine` under OI-60.

### PO-S1-07 — The request judges of the two map spikes pass a scheme they do not know

- ID: PO-S1-07
- TYPE: CLOSED (was OPEN)
- RAISED BY: the lead, 2026-11-13, at its check of task S1-T02
- CONCERNS: FE-56; OI-115
- EVIDENCE: `requestDecision` of `web/spikes/glyphs/guards.mjs` and `foreignRequest` of `web/spikes/performance/tests/performance.spec.ts` judge an address that begins with `http://` or `https://` by its origin and treat `data:` and `blob:` as local; an address with any other scheme is counted as same-origin. The content security policy of both spike servers stops such a request, and the browser tool does not report a WebSocket through the request event that the tests record, so no test sees one.
- NEEDED: both judges count a scheme outside `http`, `https`, `data` and `blob` as foreign, with one planted case each; or one line saying why not.
- CLOSED BY: S1-T10
- CLOSED: 2026-11-14, by S1-T10: both judges count a scheme outside `http`, `https`, `data` and `blob` as foreign. Proved by "unknown request schemes are blocked" in `web/spikes/glyphs/tests/guards.node-test.mjs` and "unknown or file request schemes are refused rather than ignored" in `web/spikes/performance/tests/foreign-request.node-test.mjs`.

### PO-S1-09 — Files of the listed set that no pattern reads

- ID: PO-S1-09
- TYPE: CLOSED (was OPEN)
- RAISED BY: the reviewer of the S1-T14 design, 2026-11-14
- CONCERNS: TST-140; OI-93
- EVIDENCE: 114 of the 477 files git lists at commit a9db6c8 are never read by any pattern, built-in or private, because their suffix is not on the text list of `scripts/check_docs.py` (75 `.mjs`, 4 `.mts`, `.pyi`, `.env.example`, `uv.lock`, `.nvmrc`, `.python-version`, `.prettierignore`, and binary files); OI-93 does not name `.mjs`. Check 8 of TST-263 reads them only for a listed name.
- NEEDED: the text list covers every UTF-8 file git lists, or one line saying why not.
- CLOSED BY: S1-T10
- CLOSED: 2026-11-14, by S1-T10: the documentation check reads every regular file that git lists with the identifier-number rule and the private patterns, so no listed file stays unread; this is wider than the text list the item asks for. Proved by `test_eight_digit_run_in_mjs_and_private_pattern_in_non_utf8` in `scripts/tests/test_s1_followup.py`, whose plants include an `.mjs` file, files that are not UTF-8 and a file of an invented suffix that no list names.

### PO-S1-10 — An unreadable private patterns file is ignored without a message

- ID: PO-S1-10
- TYPE: CLOSED (was OPEN)
- RAISED BY: the reviewer of the S1-T14 design, 2026-11-14
- CONCERNS: TST-140; REV-25; OI-93
- EVIDENCE: when `EII_FORBIDDEN_PATTERNS_FILE` is set but names no readable file, `scripts/check_docs.py` ignores it without a message, which silently turns off every private name, including the refusal that TST-263 relies on outside its places.
- NEEDED: a set but unreadable file fails the check with one line that does not echo the path, with a planted case; or one line saying why not.
- CLOSED BY: S1-T10
- CLOSED: 2026-11-14, by S1-T10: a set private-patterns variable that names a missing path or a folder fails the check with one fixed line that prints no part of the path. Proved by `test_missing_private_pattern_file_fails_closed` and `test_directory_private_pattern_file_fails_closed` in `scripts/tests/test_s1_followup.py`.

### PO-S1-11 — Scans of the built bundle and the exports need the place rule

- ID: PO-S1-11
- TYPE: CLOSED (was OPEN)
- RAISED BY: the reviewer of the S1-T14 design, 2026-11-14
- CONCERNS: TST-142; TST-263
- EVIDENCE: the built web bundle and the exports of TST-142 and decision 0012 will carry the map's credit, so any scan of them with the private list refuses the name unless it applies the same place rule.
- NEEDED: the task that scans the bundle or the exports states how the credit is judged there, or one line saying why not.
- CLOSED BY: S1-T10
- CLOSED: 2026-11-14, by S1-T10: task S3-T16 states in its entry of TASKS.md that its scan of the built bundle and of the rendered page judges the map's credit by the place rule of TST-263. No task of the plan scans an export with the private list, so there is nothing to place for the exports.

### PO-S2-01 — The rules configuration names an open item that does not exist

- ID: PO-S2-01
- TYPE: OPEN
- RAISED BY: the second reviewer of the slice S1 gate, round 1 (OpenAI GPT-6 Astra), 2026-11-14, proposed item P1 (its second half)
- CONCERNS: REV-17 (documents agree with the work)
- EVIDENCE: the first line of `custodian/src/eii_custodian/privacy/rules.toml` is a comment that says the owner's choices on its values "are recorded under open item OI-124". This file holds no OI-124 (it goes from OI-123 to OI-125); the task log of S1-T10 in PROGRESS.md ("Records corrected here") says so and says where the question of the window stands.
- NEEDED: the comment names the place where the choices are recorded, or names no item. No value of the file changes, and the committed gate record of the rules still matches it (`custodian/tests/test_rules_config.py`). Or one line saying why not.

### PO-S2-02 — The copied verdict of the second round of S1-T08 answers another list of checks

- ID: PO-S2-02
- TYPE: OPEN
- RAISED BY: the second reviewer of the slice S1 gate, round 1 (OpenAI GPT-6 Astra), 2026-11-14, proposed item P3
- CONCERNS: REV-16; the verdict format of [15_REVIEWER_CHECKLIST.md](docs/15_REVIEWER_CHECKLIST.md)
- EVIDENCE: the entry "S1-T08: independent review, round 2 (the confirmation): APPROVED" of PROGRESS.md copies a verdict whose checks are six numbered lines and REV-01 to REV-11, not REV-10 to REV-29 and REV-38, and whose lines are not in the order of the verdict format. The verdict is copied unchanged, as REV-09 requires; the pull request was merged on it.
- NEEDED: a new entry beside the copied verdict that says how its checks relate to the checklist's, or a statement by a reviewer in the required format for the same commit; the copied verdict is not rewritten (TST-171). Or one line saying why the item is not valid.

### PO-S2-03 — Document 10 still lists the 3D view among the questions for the spike of slice S1

- ID: PO-S2-03
- TYPE: OPEN
- RAISED BY: the reviewer of the gate-fix task S1-T17 (OpenAI GPT-6 Astra), 2026-11-14, proposed item P1
- CONCERNS: REV-17 (documents agree with the work); PLN-28
- EVIDENCE: [10_FRONTEND.md](docs/10_FRONTEND.md), section "Open questions and assumptions", the sentence that starts "Questions for the spike in slice S1" ends with "whether the 3D view holds the frame-rate gate". The gate-fix task S1-T17 moved the clause on the optional 3D view and its evidence clause (TST-242) from the slice S1 row to the slice S6 row of the gate table of document 12 (section 5), where document 14 places the view (PLN-28; S6-T18). The spike of slice S1 did not build the view and answered no such question; no record claims that it did.
- NEEDED: with the next change of document 10, the sentence says that this question is answered by S6-T18 under TST-242, with the frame-rate configuration of slice S1 as its reference. No requirement, bound or test changes. Or one line saying why the item is not valid.

### PO-S2-05 — Starting-table values dated to slice S1 that no open item holds

- ID: PO-S2-05
- TYPE: OPEN
- RAISED BY: the designated reviewer of round 2 of the slice S1 gate record, pull request 47 (DeepSeek V4.1 Flash through Devin), 2026-11-14, proposed item P1; numbered by the lead's ruling L-332 and named by the closing record of that pull request
- CONCERNS: the starting table of the calibration manifest in document 05 (SYN-69 validates the manifest before any generator runs; SYN-77 reads the range values)
- EVIDENCE: The reviewer's point, in the ruling's words: the starting-table values that document 05 dates to slice S1 and that no open item holds, `mob.range_multiple` among them. The lead's ruling L-61 of 2026-11-13 had recorded for task S1-T09 that the two range values of SYN-77 are entries of that manifest and are fixed by no task of slice S1. Slice S1 closed without them.
- NEEDED: one item, not two: the list of those values, each with the task that fixes it, is entered with the ledger of task S4-T07, which owes the slice S1 values of the calibration manifest. Or one line saying why the item is not valid.

### PO-S2-06 — The test runner's interrupt path assumes that the interrupt signal is not ignored

- ID: PO-S2-06
- TYPE: OPEN
- RAISED BY: the lead's ruling L-285 of 2026-11-14, part (5), on two failed runs of the scripts unit suite at the local commit 4a05f9e of task S2-T02; numbered by the closing record of pull request 47
- CONCERNS: document 17 (a proposed hardening point); rule 39 (the failure is explained, so it is not entered as a random failure)
- EVIDENCE: `test_runner_failures.RunnerFailures.test_interrupt_kills_the_process_group` failed in two runs of the scripts unit suite (687 tests, 1 failure, exit 1 each) and passed in the third (687 tests, OK, exit 0). In the second run's report the test found the runner's time-out line (no result within 30 s; the process group was killed) where it expected the line of an interrupted run. The cause is the lead's own launch form: a job started in the background from a non-interactive shell inherits an ignored interrupt signal, so the interrupt that the test sends never arrives. The ruling found no random failure and no defect of either change under test; the records of both failed runs are kept.
- NEEDED: a hardening entry of document 17: the test runner's interrupt path, and its test, assume that the interrupt signal is not ignored when the runner starts. The ruling proposes the point and names no fix: whether the runner restores the signal's default handling at its start or refuses to start is decided when the entry is written. Or one line saying why the item is not valid.

### PO-S2-07 — The pack's two-resolution wording amended by record 0030

- ID: PO-S2-07
- TYPE: OPEN
- RAISED BY: the independent review of S2-T02 on its local commit (xAI Grok 4.7; the verdict file names SpaceXAI Grok 4.7), 2026-11-14, proposed item P1.
- CONCERNS: REV-19 (amendments to settled pack wording go through a decision record).
- EVIDENCE: the code follows the record's selection, so resolution-9 cells exist outside Greater Doha (598 on the real run); the sentences that still say resolution 9 in Greater Doha and 8 elsewhere are the glossary's "Base cell", document 03 section 1.1 "Base cell", DAT-51, SYN-10, document 02 "Grid and release unit", document 04 section 5 "Grid cell", document 06 sections 4.1, 4.2 and the Child K sentence of 4.3, and decision 0006 item 1.
- NEEDED: those sentences are the amended passages of decision record 0030, which merged by pull request 49 on 2026-11-15, before this train; the item closes when the merge that carries both is checked against the record's passage list.

### PO-S2-08 — The two required keys of document 03 section 7.3 amended by record 0030

- ID: PO-S2-08
- TYPE: OPEN
- RAISED BY: the independent review of S2-T02 on its local commit (xAI Grok 4.7; the verdict file names SpaceXAI Grok 4.7), 2026-11-14, proposed item P2.
- CONCERNS: REV-19.
- EVIDENCE: document 03 section 7.3 makes `grid_cell.district_key` a required string and `gazetteer.cell` a required cell; the build stores nulls in the one reviewed case of each (five cells of zone 99 with reason `zone_without_district`; five district gazetteer rows with reason `point_without_base_cell`). Record 0030 items 7, 8 and 13 are the amendment, merged by pull request 49.
- NEEDED: as PO-S2-07: the item closes when the joined tree is checked against the record's passage list.

### PO-S2-09 — The fourth criterion's source points are task S2-T06's

- ID: PO-S2-09
- TYPE: OPEN
- RAISED BY: the independent review of S2-T02 on its local commit (xAI Grok 4.7; the verdict file names SpaceXAI Grok 4.7), 2026-11-14, proposed item P3; the move was the lead's ruling before the review.
- CONCERNS: REV-10 (the acceptance criteria); the task's fourth criterion.
- EVIDENCE: `reviewed_points` resolves a landmark or building only when its spec has `source_id` and `record_key` and the point dict contains that pair; the committed `showcase_gazetteer.yaml` and `flagship_candidates.yaml` set both to null (4 landmarks, 7 buildings) and `build_live_frame` records `source point pending S2-T06` for each, ending `frame: partial; place points remain`.
- NEEDED: the criterion moves, unticked and word for word, to task S2-T06 by a re-plan recorded in PROGRESS.md; S2-T06 fills the reviewed keys, supplies the source points and merges the rows. The frame keeps refusing an unfilled entry by name.

### PO-S2-10 — A stale skipped-sources sentence in the frame README

- ID: PO-S2-10
- TYPE: OPEN
- RAISED BY: the independent review of S2-T02 on its local commit (xAI Grok 4.7; the verdict file names SpaceXAI Grok 4.7), 2026-11-14, proposed item P5.
- CONCERNS: REV-17.
- EVIDENCE: `custodian/src/eii_custodian/publicdata/frame/README.md` still says `est_census`, `zone_population` and `census_hh_type_2020` remain skipped; `est_census` has an empty `skip_reason` and the live build writes two `pub_census_national` rows; the other two sources stay skipped.
- NEEDED: the sentence names only `zone_population` and `census_hh_type_2020` with their reason, or describes `est_census` as read.

### PO-S2-11 — `source_id` missing from the `pub_census_zone` column list

- ID: PO-S2-11
- TYPE: OPEN
- RAISED BY: the independent review of S2-T02 on its local commit (xAI Grok 4.7; the verdict file names SpaceXAI Grok 4.7), 2026-11-14, proposed item P6.
- CONCERNS: REV-20 (source and retrieval date on every Public row).
- EVIDENCE: the `pub_census_zone` column list of document 03 section 7.3 omits `source_id`; `census_rows` and `test_census_release_columns_match_dat_contract` require it, and the map-layer acceptance criterion requires the source. The retrieval date is the receipt field `retrieved_utc`, which `test_r4_measures_and_receipt_lineage` checks.
- NEEDED: the column list gains `source_id`.

### PO-S2-12 — Likely-missing spellings for `municipality_names.csv`

- ID: PO-S2-12
- TYPE: OPEN
- RAISED BY: the Arabic-expert model review of the municipality spellings (Google Gemini 4 Carbon), 2026-11-14, advisory outside its APPROVED verdict; and the first expert reading of 2026-11-15 (Moonshot AI Kimi K3.1 Pro High), point (c) of its notes on the table
- CONCERNS: the coverage of the committed names file `custodian/publicdata/review/municipality_names.csv` (PUB-27)
- EVIDENCE: Both readers list spellings that public datasets are likely to use and that the file does not hold. The review of 2026-11-14: counterparts of variants already present (the forms with the word for municipality in front of four of the names, and the two-part name with its conjunction spaced), and final-ha forms (of two one-word names, of the forms of a third, of the two-part name, and of the word for municipality itself). The reading of 2026-11-15, by the rows of the list it read: the final-ha form of row 15; rows 18, 8 and 3 with the word for municipality in front; row 5 with its conjunction unspaced. The exact strings are in the two returns, which are kept with the run's records; they are not repeated here. The file fails closed on any unmapped spelling, so a missing spelling refuses a build and cannot misjoin a row.
- NEEDED: a spelling enters the file, reviewed, when a source that is read really writes it; none is added from a list alone. Or one line saying why the item is not valid.

### PO-S2-13 — The Arabic name of one municipality is displayed in its official form

- ID: PO-S2-13
- TYPE: OPEN
- RAISED BY: the lead's ruling L-356 of 2026-11-15 on the two expert readings of row 21 of the Arabic rows of the names file (Moonshot AI Kimi K3.1 Pro High; xAI Grok 4.7, which signs itself "SpaceXAI, Grok 4.7"), both recorded as model reviews
- CONCERNS: PUB-27 (the names file maps names as sources write them); the Arabic wording of slice S3
- EVIDENCE: Row 21 of the Arabic rows of `custodian/publicdata/review/municipality_names.csv` is a spelling that one read source writes for the municipality of rows 1 and 2. The first reading calls it WRONG, a misspelling of row 1's form. The second says that the official form is row 1's and rules REMOVE; it also says that row 21 names only this municipality and is SAFE in a join table. By the lead's ruling the row stays in the join table. A join table of source spellings is not a list of names for display.
- NEEDED: the product displays this municipality's Arabic name in row 1's form and never in row 21's, checked where the name is first displayed, by the wording task of slice S3. Or one line saying why the item is not valid.

### PO-S2-14 — The mutation campaign on the custodian series modules of S2-T03

- ID: PO-S2-14
- TYPE: OPEN
- RAISED BY: the lead, 2026-11-15, at the mutation run of task S2-T03
- CONCERNS: mutation testing of the modules that compute or compare numbers (rule 44, `scripts/mutation.py`)
- EVIDENCE: The campaign on `core/src/eii_core/calc/public_series.py` is complete (130 mutants made, 127 killed, 3 survived and explained, exit 0). The three custodian series modules of the same task, `figures.py`, `baskets.py` and `reconcile.py` under `custodian/src/eii_custodian/publicdata/series/`, have no campaign: on the task's base the mutation copy lacks the scripts folder that one test of S2-T01 imports, so the custodian suite cannot run in it.
- NEEDED: the campaign on the three modules, every survivor killed or explained. The lead runs it on the joined tree of the train that carries task S2-T21, where the mutation copy holds what the custodian suite imports; a survivor goes to the builder's maker of S2-T03. Or one line saying why the item is not valid.
- UPDATE: 2026-11-15, by the ledger of merge train C (task S2-T07): the calculation change now joins main. The campaign record of train B5 above stays unchanged: the runs were on train B4 trees that held this task, not on this joined head. The task brings the changed figures.py and reconcile.py back; the 150, 12 and 20 survivors recorded above remain with the same thin test pass, and exit code 1 remains not a pass. The lead's identity account says that every mutated source file of the tasks is byte-identical to its approved form except fetch/build.py, whose rerun is recorded in this train's log.
- UPDATE: 2026-11-15, by the ledger of merge train B5 (tasks S2-T04 and S2-T05): the item stays open. The campaign of `figures.py` ran to its end for the first time on a trial tree of train B4 at bbc5bfa869bc0a24f37c4a70ab10d0bd6a652577: made 1,891, killed 1,741, survived 150, timed out 0, not covered 0, exit code 1. The run was possible because the repair of the mutation runner by task S1-T19 (pull request 54) stood under that tree, not because of task S2-T21, which the train does not carry. The explanations file holds no entry for the module, so all 150 survivors are unexplained: 149 stand on lines of S2-T03 that are byte-equal on main, and one stands on a line that S2-T07 added (line 342, the text of a refusal message that its test matches by a search). That tree, and train B4's first cut cafd8b741dd2d16cb7514b4945d8413482fa7ad2, both held S2-T07, which changed ten lines of `figures.py` and two of `reconcile.py`; S2-T07 left the train at the split this ledger records, so neither changed blob is one this train merges. In the joined work commit b89fc325514b92e82d9fd8318d5c44b38d3309a6 all three modules are the blobs main a46e6ff7722d2ca0f966f1bd78a95c3462887497 holds and this train changes no line of them, read by `git rev-parse <commit>:<path>` at both: `figures.py` 48c4dd6d61783ba4a7669739041dd82cfb41c4cd, `reconcile.py` f4c02552639938b3f3b09edd1e9574ce4309d070, `baskets.py` 03043734490a1ea353933e82e353804c45cdca0a. On train B4's first cut the lead's campaign of 2026-11-15 ran all three in one run with exit code 1: `reconcile.py` made 193, killed 181, survived 12; `baskets.py` made 238, killed 218, survived 20; `figures.py` made 1,891, killed 1,741, survived 150 again. The exit code 1 is recorded as it is and is not a pass. By the lead's ruling of 2026-11-15 the survivors go to one thin test pass on its own branch, built by the maker that built S2-T03 and reviewed by another maker, on a base that holds the runner's repair; all three modules go to that pass.

### PO-S2-15 — The filled tender confirmation once S2-T19 fetches the source

- ID: PO-S2-15
- TYPE: OPEN
- RAISED BY: the independent review of S2-T13, rounds 1 and 2 (xAI Grok 4.7 through Cursor), proposed item P1
- CONCERNS: REV-10 and PLN-25 (the first and last acceptance criteria stand on the mechanism only)
- EVIDENCE: The committed record `custodian/publicdata/review/s2_t13_confirmation.yaml` is `not_yet_recorded`; `completion_evidence` rejects it as incomplete and `tender_disposition` returns `NO_DATA` with the document-04 caveat. The lead's recorded reading of the portal (its own evidence file of 2026-11-14) is not installed in the commit.
- NEEDED: S2-T19 supplies the registry row and the fetch receipt; the record is then filled from the lead's reading (`terms_do_not_cover`, the publisher's own words, the date read, basis `owner_decision`, the go-live permission flag), and both confirmations reach the slice-S2 gate evidence.

### PO-S2-16 — The unamended tender rule in the documents and the registry loader

- ID: PO-S2-16
- TYPE: OPEN
- RAISED BY: the independent review of S2-T13, round 2 (xAI Grok 4.7 through Cursor), proposed item P3
- CONCERNS: REV-16, REV-17, REV-19
- EVIDENCE: PUB-108, PUB-93, document 14's S2-T19 bullet and TASKS.md S2-T19 still carry the pack's earlier tender rule (a source whose terms are absent, do not cover or forbid the use is switched off and not shown), and decision record 0026 is not in this commit; the registry loader's OWNER_DECISION_SOURCES does not include `tenders_pub` and its DECISION_RECORDS holds only the earlier records, so it cannot yet accept the `owner_decision`/`0026` row the filled confirmation will require.
- NEEDED: the documents are amended by decision record 0026's own pass (the record says so) and the loader change is task S2-T21's (OI-164); record that the row cannot load before S2-T21 merges.

### PO-S2-17 — The recorded form of an absent or disabled tender source for S2-T19

- ID: PO-S2-17
- TYPE: OPEN
- RAISED BY: the lead's internal review of S2-T13 (the optional point of confirmed finding C9), not a verdict finding
- CONCERNS: the registry handoff between this task's record and S2-T19's registry row
- EVIDENCE: `completion_evidence` accepts an evidenced absence only as a registry row whose `skip_reason` equals the outcome with no release tables; the module docstring does not say that S2-T19 must write it that way, and a row that records forbidding terms with an empty `skip_reason` is not accepted (the internal review's note, written before the owner's decision 0026 changed which outcomes remain switch-offs).
- NEEDED: state the convention in the module docstring, or accept the recorded switch-off form the registry already has; the lead decides which.

### PO-S2-18 — The tender portal's certificate chain, a fact for S2-T19

- ID: PO-S2-18
- TYPE: OPEN
- RAISED BY: the lead's recorded reading of the tender portal (the ruling text of 2026-11-14 names it a fact for task S2-T19)
- CONCERNS: the fetcher of S2-T19
- EVIDENCE: The portal's server omits its issuer's intermediate certificate; the lead completed the chain from the address the certificate names, verified it against the system roots and fetched with verification on. A fetcher needs the same completed chain; nothing disables verification.
- NEEDED: S2-T19's fetcher completes the chain the same way and the fact is recorded in that task's brief.

### PO-S2-19 — The index of `docs/README.md` does not name decision 0032 on three documents

- ID: PO-S2-19
- TYPE: OPEN
- RAISED BY: the reviewer of decision record 0032, pull request 50 (xAI Grok 4.7; the verdict signs "SpaceXAI, Grok 4.7"), proposed item P2
- CONCERNS: REV-17 (documents agree with the work)
- EVIDENCE: The status cells for documents 12, 14 and 15 in the index of `docs/README.md` do not name decision 0032, while those documents' own Status rows do.
- NEEDED: with the next change of `docs/README.md`, the three status cells name decision 0032. No rule changes. Or one line saying why the item is not valid.

### PO-S2-20 — Card C40 and the reason order of `site_estimate` for a point without a base cell

- ID: PO-S2-20
- TYPE: OPEN
- RAISED BY: the lead's ruling on round 1 of the review of decision record 0030 (pull request 49), carried by that pull request's closing record
- CONCERNS: card C40 (its eligibility list) and the closed tool contract `site_estimate` of document 08 section 6.2, under PRV-135 and decision 0030 item 10
- EVIDENCE: The fix of round 1 added the case of PRV-135 to four tool contracts, `location_allocation` among them; it decides nothing about the eligibility list of card C40. Two points stay open: how card C40 treats a candidate that has no base cell, and which reason key comes first when `inputs_not_entered` and `point_without_base_cell` both hold for `site_estimate`.
- NEEDED: both are decided by the task that builds card C40 and by the task that builds `site_estimate`, each in its plan, with a test for the order. Or one line saying why the item is not valid.

### PO-S2-21 — Mutants of the performance page and server on lines of earlier tasks

- ID: PO-S2-21
- TYPE: OPEN
- RAISED BY: the lead's web mutation run for S1-T18 (2026-11-15)
- CONCERNS: AGENTS.md rule 44 (the web mutation runner); `web/spikes/performance/server.mjs` and `web/spikes/performance/main.ts`
- EVIDENCE: At db0b98e the run made 455 mutants in `server.mjs` (195 killed, 18 survived, 242 timed out) and 517 in `main.ts` (409 killed, 70 survived, 38 timed out). S1-T18 settled the one survivor and the three timeouts on the lines it changed. The others stand on lines of earlier tasks: 18 survivors and 239 timeouts in `server.mjs`, 69 survivors and 38 timeouts in `main.ts`. They are not killed, explained or replayed.
- NEEDED: the follow-up task of slice S2 kills or explains these survivors and replays these timeouts alone at normal load, each result recorded apart from the killed mutants, as rule 44 asks.

### PO-S2-22 — Test clients that never finish when a response stays open

- ID: PO-S2-22
- TYPE: OPEN
- RAISED BY: the replay of S1-T18's timed-out mutants (the builder's return; check K4 of the confirmation review)
- CONCERNS: AGENTS.md rule 44 (a timeout is reported apart from killed mutants); `web/spikes/performance/tests/mutation-server.node-test.mjs` and `web/spikes/performance/tests/trace.node-test.mjs`
- EVIDENCE: With the body of the server's `send` emptied, no response is ever ended. The isolation test fails with `timed-out`, but the two test files named above stay pending, because their waiting client has no time limit of its own; the replay ends on the command's limit of 120 s with exit code 124. This mutant can therefore only time out; it is recorded as a timeout, not as a killed mutant.
- NEEDED: the follow-up task of slice S2 assesses a time limit for the waiting test clients and shows with this planted mutant that a response that never ends then fails a test and ends the run.

### PO-S2-23 — The browser's rendering threads choose their own processors

- ID: PO-S2-23
- TYPE: OPEN
- RAISED BY: the lead's measurement of 2026-11-15, entered with S1-T18
- CONCERNS: AGENTS.md rule 44 (a timeout is replayed alone at normal load); any run whose result is a time
- EVIDENCE: The headless browser of the browser tests, started inside a run bound to a set of processors, keeps its own process on that set, but its sixteen rendering threads hold processors 0 to 11: the renderer sets its threads' processors itself, and a set given from outside does not bind them. A browser suite therefore loads processors 0 to 11 whatever set its run was given, and a timed run beside it is not clean. Nothing in the repository is changed; binding those threads would need a system setting that is the owner's.
- NEEDED: the follow-up task of slice S2 looks at the renderer's own thread options. Until then the lead takes a run whose result is a time only while no browser suite is in flight, and replays a timed-out mutant or a time-limit failure seen beside a browser suite after that suite has ended, keeping both results.

### PO-S2-24 — Temporary folders of the spike's tests left after a process is ended from outside

- ID: PO-S2-24
- TYPE: OPEN
- RAISED BY: the lead's record of 2026-11-15, during S1-T18's web mutation run
- CONCERNS: the tests under `web/spikes/performance/tests/` and their folders under the system's temporary folder
- EVIDENCE: The performance spike's test folders under the system's temporary folder are not removed when a test process is ended from outside: more than 300 were left while the web mutation run went. S1-T18 does not change this.
- NEEDED: the follow-up task of slice S2 assesses a cleanup that also holds when a test process is ended from outside, with that case planted and the state of the folders recorded.

### PO-S2-25 — The remaining git variables and the runner's own listing of the workspace

- ID: PO-S2-25
- TYPE: OPEN
- RAISED BY: the confirmation review of S1-T19 (check K6 and its hardening item) and the lead's run at e5a2be8
- CONCERNS: `scripts/mutation.py` (`package_environment` and `main`); S1-T19
- EVIDENCE: The fix of finding F1 removes the six repository-redirecting variables from the package run's environment. The configuration family (`GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM`, `GIT_CONFIG_COUNT/KEY/VALUE`) and `GIT_CEILING_DIRECTORIES`, `GIT_DISCOVERY_ACROSS_FILESYSTEM` and `GIT_NAMESPACE` stay: a package test in the copy then sees the same global git settings as in the workspace's ordinary run, and the reviewer agrees (K6). The runner's own listing of the workspace still follows the caller's git variables: with variables that name an outside repository it refuses with exit code 2 before any copy is made, and that repository's 19 files are unchanged.
- NEEDED: the follow-up task of slice S2 assesses the handling of those remaining variables and of the listing, with tests. The recorded refusal is fail-closed; it is not a completed campaign.

### PO-S2-26 — The package copy's pytest settings still differ from the project's

- ID: PO-S2-26
- TYPE: OPEN
- RAISED BY: the builder of S1-T19 and its independent review, round 1 (Moonshot AI Kimi K3.1 Pro High through Devin), proposed item P3
- CONCERNS: REV-16; `scripts/mutation.py` (the settings it writes into the copied package)
- EVIDENCE: The repairs of S1-T19 make the copy's test path and the tests' file paths agree with the project's. The copy's pytest settings still omit the project's markers, its strict setting, its Hypothesis profile and its `not nightly` filter. The review records this as a follow-up, not as a finding.
- NEEDED: the follow-up task of slice S2 assesses these remaining differences. The review names the follow-up task of slice S1, which is done; the item is carried to slice S2 on the lead's reading of decision 0018 item 8.

### PO-S2-27 — The nine surviving mutants of the terms-text module

- ID: PO-S2-27
- TYPE: OPEN
- RAISED BY: the lead's real campaign for S1-T19 at e5a2be8
- CONCERNS: AGENTS.md rule 44; `custodian/src/eii_custodian/publicdata/fetch/terms_text.py`; S2-T21
- EVIDENCE: The isolated campaign of the module made 46 mutants, killed 37 and left 9 survivors, exit code 1. That the campaign reaches its counts line proves the runner's repair; the nine survivors are not settled by S1-T19.
- NEEDED: the nine survivors are killed or explained in task S2-T21, to which the lead assigns the module. The campaign's exit code 1 is not recorded anywhere as a pass.

### PO-S2-28 — The remaining qualifications of git's answer in the copy

- ID: PO-S2-28
- TYPE: OPEN
- RAISED BY: the builder of S1-T19, recorded in the lead's ruling of 2026-11-15
- CONCERNS: `scripts/mutation.py` (`run_packages`); S1-T19
- EVIDENCE: The builder named three qualifications of git's answer in the copy against a checkout. The copy's index is empty, so a path tracked despite a matching ignore rule would answer differently; nothing under the cache path is tracked. The copy's local exclude file is the fresh template. The user-level exclude file applies in both. The empty repository does not reproduce a checkout's whole git state.
- NEEDED: the follow-up task of slice S2 assesses these limits and states them where the runner is documented, keeping the two differences (the index, the local exclude file) apart from the one behaviour the copy and a checkout share (the user-level exclude file).

### PO-S2-29 — A mutation explanation stops matching when lines move

- ID: PO-S2-29
- TYPE: OPEN
- RAISED BY: the lead's record of another task on 2026-11-15, entered with S1-T19
- CONCERNS: AGENTS.md rule 44; `scripts/mutation_explained.toml`
- EVIDENCE: An explained row holds the tool's difference text with its line numbers, so a row stops matching when lines are added above the mutation in the module. This was seen on another task on 2026-11-15. A form that survives such a move is not built.
- NEEDED: the follow-up task of slice S2 assesses a form of explanation that survives a move of lines and still names the one mutation it explains.

### PO-S2-30 — Records that still say the native trace is owed

- ID: PO-S2-30
- TYPE: OPEN
- RAISED BY: the ledger of S1-T12 and the addendum of the slice S1 gate (2026-11-15)
- CONCERNS: `pins.toml` (the key `spike_result` and the notes of the rows `maplibre-gl`, `@deck.gl/core`, `@deck.gl/layers`, `@deck.gl/geo-layers` and `@deck.gl/extensions`); `web/REFERENCE_NOTES.md` (the paragraph on the fields that wait for task S1-T12 and the rows "spike result that chose between pin and retreat", "pixel-ratio cap value" and "load trial of 110,000 hexagons and 50,000 particles"); `web/spikes/performance/README.md`
- EVIDENCE: The native traces are committed and the evidence command passes on the gate's load. The addendum of the slice S1 gate answers the fields that the frame rate decides, but the rows above still read "not yet confirmed" and the README still says that the native frame-rate gate is pending. The scope of S1-T12 is the evidence folder only.
- NEEDED: the follow-up task of slice S2 brings these rows and sentences in line with the addendum, with the pin check and the reference-notes check run on the result. No pin, retreat, bound or cap value changes.

### PO-S2-31 — No frame-rate statement exists for the map with the road layer

- ID: PO-S2-31
- TYPE: OPEN
- RAISED BY: the ledger of S1-T12 (2026-11-15)
- CONCERNS: document 10, table row "Spike frame-rate gate (slice S1)" and FE-89; `web/spikes/performance/trace.mjs` (a road set records its share and has no minimum); the tasks of slice S3 that depend on map performance
- EVIDENCE: The two native road traces of S1-T12 are recorded with a share of frame intervals under 16.7 ms of 0.8961 (100,004 road features) and 0.9017 (250,004 road features), both under the minimum of 0.95 that the gate sets for the hexagon and particle load alone; neither trace holds an interval over 17.08 ms. No document states a bound for the map with the road layer, and no pass is claimed for it.
- NEEDED: before a task of slice S3 that depends on map performance is reviewed, a decision whether the map with the road layer gets a frame-rate statement of its own or the recorded shares stand as evidence without a bound. No bound is restated or added without a decision record.

### PO-S2-32 — The header of an alias file is not validated strictly

- ID: PO-S2-32
- TYPE: OPEN
- RAISED BY: the code review of S2-T22 (OpenAI GPT-6, 2026-11-15), outside its verdict, as hardening
- CONCERNS: `custodian/src/eii_custodian/publicdata/frame/crosswalk.py` (`read_csv`); `custodian/src/eii_custodian/publicdata/frame/live.py` (`district_aliases`); `custodian/src/eii_custodian/publicdata/frame/joins.py`; the committed file `custodian/publicdata/review/district_layer_aliases.csv` and the local file of the same header in the uncommitted cache
- EVIDENCE: The reviewer's words: "frame/crosswalk.py:read_csv does not validate the raw header; duplicate column names can collapse silently before joins.py checks dictionary keys. Validate exact unique headers and row widths for both alias paths, with malformed-file plants." Its check Q5 passed and says that strict header validation is absent in both paths, the committed one and the local one that S2-T22 adds; the gap is older than the task and the task did not widen what the parser accepts.
- NEEDED: the follow-up task of slice S2 validates the exact header, with unique column names, and the width of every row for both alias paths, each refusal with its planted malformed file; or says in one line why it is not valid.

### PO-S2-33 — The two local files of S2-T22 are written by hand

- ID: PO-S2-33
- TYPE: OPEN
- RAISED BY: the builder of S2-T22 (Cognition SWE-2, 2026-11-15), in the return of the build pass
- CONCERNS: the local record `local_expectations/PUB-71.json` and the local file `review/district_layer_aliases.csv` inside the uncommitted cache `data/public_cache/`; `custodian/src/eii_custodian/publicdata/stage.py` (`_local_expected`); `custodian/src/eii_custodian/publicdata/frame/live.py` (`district_aliases`); `custodian/README.md`
- EVIDENCE: The builder's words: "The local expectations record and the cache `review/` folder are written by hand; no command produces them. If a build step should scaffold or validate their presence (beyond the stage's fixed refusal), a task could own that." The stage refuses a record of another shape and fails the build when a produced figure has no record; nothing checks that the alias file is present, and with none a district that needs an alias is reported as unmatched. No run of the real build with a real local record is recorded for S2-T22. The builder also noted that the frame's README still says that the committed alias file supplies the reviewed aliases.
- NEEDED: the follow-up task of slice S2 decides whether a build step writes, checks or only reports the two local files, and brings the frame's README sentence in line; no value of a source without an open licence is committed by either.

### PO-S2-34 — The performance spike's page writes a trace that the web format check refuses

- ID: PO-S2-34
- TYPE: OPEN
- RAISED BY: the lead, at the merge of pull request 55 (task S1-T12, 2026-11-15)
- CONCERNS: `web/spikes/performance/` (the loopback server of `npm run spike:performance:serve`, which writes a trace under `web/spikes/performance/evidence/`); `npm run format:check`; the README of the spike
- EVIDENCE: The server writes a trace as one line of JSON. The web format check reads every JSON file under `web/`, so the first head of pull request 55 failed the hosted job static-checks at its step "Check web format" and the job planted-failures at its plant of the same check. The three traces were then rewritten by the project's formatter and the digests of their capture records updated, with a proof that nothing but whitespace differs; no check was changed. A later native trace would fail in the same way.
- NEEDED: the follow-up task of slice S2 makes the server write a trace in the form the formatter keeps (or the spike's README tells the person who takes a trace to run the formatter and update the capture record's digest before committing); the format check and its ignore list are not changed for it; or one line says why it is not valid.

### PO-S2-35 — Files of the copy that are not selected are not checked against the summary

- ID: PO-S2-35
- TYPE: OPEN
- RAISED BY: the confirmations of S2-T15 (Moonshot AI Kimi K3.1 Pro High, 2026-11-15), outside their verdicts, as hardening; first proposed by the builder of the second fix pass (OpenAI, 2026-11-14) and ruled not built by the lead on 2026-11-14
- CONCERNS: `custodian/src/eii_custodian/publicdata/places_fsq/select.py` (`select_partitions`); `custodian/src/eii_custodian/publicdata/places_fsq/fetch.py` (`fetch_release`); the section "Limits" of the package README; document 17
- EVIDENCE: The reviewer's words, first confirmation: "Files not selected are not checked against the summary, as the package README’s limitation sentence records." Second confirmation: "files not selected remain outside summary verification, as the README's Limits section discloses." The fetch compares the footer of each selected file with the summary and refuses a difference before anything is stored; a file that the summary wrongly places outside the frame is never fetched, so a stale summary can hide it. The lead did not have the check built because it would fetch every footer of the release. The builder's words: "selected-file consistency does not prove correct exclusion of other files. Add a reviewed way to validate excluded-file coverage before deployment reliance, preserving the format’s warning that summary files were never formally specified."
- NEEDED: the follow-up task of slice S2 assesses a bounded check of the files not selected (for example the footers alone, by byte range), with its planted stale file; or says in one line why the limit stands, and whether document 17 names it for real use.

### PO-S2-36 — The later column orders of the file format are treated as unknown

- ID: PO-S2-36
- TYPE: OPEN
- RAISED BY: the lead's ruling of 2026-11-14 on the format check of S2-T15 (defect D1), and the reading of the official pages by the lead's helper on 2026-11-15
- CONCERNS: `custodian/src/eii_custodian/publicdata/places_fsq/footer.py` (`file_metadata`, the resolution of column orders); the package README
- EVIDENCE: The reader uses a modern bound only where the file's list of column orders gives the column the type-defined order; under any other order it takes the deprecated bounds where present, and otherwise the statistic is missing and the file set is refused. The return of the second fix pass: "IEEE total order, member 2, is UNKNOWN in this pass". The reading of 2026-11-15 found that the format's definition now names two further column orders and a rule for a zero bound under the type-defined order that the reader does not apply; the lead ruled that none of its twelve points changes code, and the first confirmation passed the pair of bounds from mixed sources "unchanged as ruled" (its check K9). The reader fails closed: a copy written with a later order is refused by name and never read by a guessed order.
- NEEDED: the follow-up task of slice S2 decides, after the live fetch shows which order the copy declares, whether the reader learns the later orders and the zero rule, each with its hand-encoded plant; or says in one line why refusal is enough.

### PO-S2-37 — A sentence of document 04 section 6 says the classification source stays unconfirmed

- ID: PO-S2-37
- TYPE: OPEN
- RAISED BY: the lead's pack note for review round 2 of S2-T04, 2026-11-14 (one sentence of the fix states the pack's then rule on a source's terms, which the owner's decision of that day changes through a decision record of its own); found again on train B4's trial tree by the helper that drafted this ledger block, 2026-11-15
- CONCERNS: document 04 section 6, the sentence after PUB-40 that begins "S2-T04 builds the offline activity spine"; the terms row of `cls_isic4` in the same document; PUB-13
- EVIDENCE: The sentence, added by the first fix pass of S2-T04, ends: "the classification source stays unconfirmed so titles derived from it stay barred from release (PUB-13)". On the joined work commit of merge train B5 the same document's terms row for `cls_isic4`, as main holds it under decision 0026, ends: "titles and mappings may enter a release; any permission needed for real use goes on document 17's list". Part 2 of S2-T04 confirmed the file's address and columns and did not touch the sentence. The code agrees with the sentence, not with the row: the graph's release mode refuses the source while its basis is `none_stated`.
- NEEDED: one wording for section 6 that agrees with decision 0026 and with what is still unconfirmed (the terms words, OI-204), made with the document pass of S2-T21 or of decision 0026; the code follows the loader of S2-T21 (PO-S2-38). Or one line saying why the item is not valid.

### PO-S2-38 — This task's own confirmation of what the registry loader of S2-T21 changes in it

- ID: PO-S2-38
- TYPE: OPEN
- RAISED BY: the scout's report of train B4 (a helper's trial join on main, 2026-11-15), points F1 and F2; the lead's ruling of 2026-11-15 06:34, part 1
- CONCERNS: `custodian/src/eii_custodian/publicdata/review/graph.py`, `custodian/tests/test_activity_planted.py`, `custodian/tests/test_activity_real_shape.py`; rule 33 of AGENTS.md (a forced code or test difference needs that task's own confirmation by another maker); decision 0026
- EVIDENCE: `graph.py` imports `release_refused` from the registry module and calls it in the title check of `cls_isic4`, and tests the basis against `none_stated`; `test_activity_planted.py` imports and asserts `release_refused` and plants a `none_stated` source; `test_activity_real_shape.py` asserts that the row `cls_isic4` has the basis `none_stated`. S2-T21 removes the function and the basis and holds the row as `owner_decision` with decision record 0026. S2-T21 left train B4 for a join pass on train B4's tree; the lead ruled that where the two meet, the other tasks' code and tests follow the record's loader, each change named in that pass's return.
- NEEDED: the changed lines of these three files, confirmed for S2-T04 by another maker than the one that makes them, with the train that carries S2-T21; the release bar on the classification file's titles is then stated by the loader's rule and by OI-204, not by the removed basis. Or one line saying why the item is not valid.

### PO-S2-39 — Hardening points of the activity review

- ID: PO-S2-39
- TYPE: OPEN
- RAISED BY: the builder of the first fix pass of S2-T04 (xAI Grok 4.7 through Cursor), 2026-11-14, under "HARDENING" in its return; the first builder's return names the file-length point too
- CONCERNS: document 17 (a proposed hardening point); TST-51
- EVIDENCE: The return says that a cryptographic reviewer signature and a review screen are not built: a review is recorded as a role and a date in a committed file, bound to its inputs by the binding file. It also says that `activity.py` and the larger activity test files are past the 500-line target, which the plan treats as a warning and not as a failure; the files were not split.
- NEEDED: one entry of document 17 for the reviewer signature, with no change of scope (the scope is frozen); a decision whether the long files are split by a later task. Or one line saying why the item is not valid.

### PO-S2-40 — Three type diagnostics of the activity refusal tests, visible only to an unconfigured type check

- ID: PO-S2-40
- TYPE: OPEN
- RAISED BY: the confirmation of the mutation pass of task S2-T04 (Cognition SWE-2 High through Devin, 2026-11-15), its one proposed item, marked record (check M7); the builder's return of the thin repair names the same three places
- CONCERNS: `custodian/tests/test_activity_survivors_refusals.py` and `custodian/tests/test_activity_survivors_refusals_decisions.py`; the file list of the type check in `pyproject.toml`; REV-15
- EVIDENCE: A direct type check of the two files reports three `dict.update` mismatches, one in the first file and two in the second. The two files stand outside the configured file list of the type check, so the configured run reports no issue. The reviewer's reading: the three updates behave as intended and are no defect of what the tests prove; they are not suppression comments.
- NEEDED: if these test files ever join the configured file list of the type check, the literal dictionaries are annotated as `dict[str, object]`. Or one line saying why the item is not valid.

### PO-S2-41 — One test of the spine triage prints a line of the tool into the suite's output

- ID: PO-S2-41
- TYPE: OPEN
- RAISED BY: the independent review of S2-T05 on its local commit (xAI Grok 4.7 through Cursor), 2026-11-14, proposed item P1 (REV-11), a record point.
- CONCERNS: TST-155; rule 36 of `AGENTS.md` (a failure is never hidden).
- EVIDENCE: `test_none_preserves_queue_without_network_or_key_access` in `scripts/tests/test_spine_triage.py` calls `main` without redirecting standard output, so every run of the suite prints the tool's success line `OK unsigned queue` after the suite's own result. The lead's discovery at the commit exited 0 (708 tests, OK), so the line hid no failure there. The line is the last line of the builder's failed discovery too, where it stood under a run that had exited 1.
- NEEDED: the test redirects the tool's standard output, as the file's own helper for calling `main` does, so that the last line of the suite's output is the suite's own; a change of one test, made by a later task that owns the file. Or one line saying why the item is not valid.

### PO-S2-42 — The count of project commands in `README.md` after S2-T05 added one to rule 44

- ID: PO-S2-42
- TYPE: OPEN
- RAISED BY: the independent review of S2-T05 on its local commit (xAI Grok 4.7 through Cursor), 2026-11-14, proposed item P2 (REV-17), a record point.
- CONCERNS: rule 44 of `AGENTS.md`; `README.md`, section "Current status".
- EVIDENCE: `README.md` says "Thirty-two project commands run from the repository root today" and the commit of S2-T05 added `uv run --locked python scripts/spine_triage.py` and its test command to rule 44. The plan limited the task's README edit to one paragraph, so the count was left as it stood. The sentence still reads so on the joined work commit of merge train B5.
- NEEDED: the count and the list of that sentence are brought in line with rule 44 by the next documents change that touches `README.md`; whether the README keeps a count at all is decided there. Or one line saying why the item is not valid.

### PO-S2-43 — A failure while the gateway builds its provider may leave no decision record

- ID: PO-S2-43
- TYPE: OPEN
- RAISED BY: the builder's return of S2-T05 (OpenAI GPT-6 Astra through Codex), 2026-11-14, under NOT DONE and in its proposed open-item sentence; not a verdict finding. The review did not rule on it.
- CONCERNS: DAT-126 (the decision record); the gateway of task S1-T07, which is outside the scope of S2-T05.
- EVIDENCE: The builder reports that the triage tool returns the unchanged queue when the gateway cannot be built, and that the gateway builds its provider before the block that writes a decision record, so a failure at that step may be persisted in no record. The gateway's code was not changed by the task. With provider `none` and with recorded answers, the only providers of the build and of every gate, no test shows the case. This draft did not read the gateway's code to confirm the order.
- NEEDED: the lead's reading of the gateway's start-up order, and then one of: a hardening entry of document 17 for the gateway (a start-up failure writes a record of outcome `UNAVAILABLE` or `ERROR`), or a recorded statement that a failure before any call needs no DAT-126 record. Or one line saying why the item is not valid.

### PO-S2-44 — The part of the break pass of S2-T05 that was not done, and one surviving negation

- ID: PO-S2-44
- TYPE: OPEN
- RAISED BY: the builder's return of S2-T05 (OpenAI GPT-6 Astra through Codex), 2026-11-14, under BREAKS and NOT DONE, and its proposed open-item sentence; not a verdict finding.
- CONCERNS: rule 37 of `AGENTS.md` (every guard has a planted violation); the build brief's break pass (every comparison, boolean operand, early return and listed value); TST-155.
- EVIDENCE: The builder's break pass negated 62 conditions of `scripts/spine_triage.py` and `scripts/spine_triage_io.py`; nine were caught by no test, assertions were added, and a follow-up of twelve runs caught eleven. One negation survives: the empty-string operand of `gateway.endpoint or ""` in `triage`, explained by the builder as unreachable for an admitted keyed run. The builder states that listed values and early returns were not broken one by one. The review approved on the acceptance criteria with a planted refusal for each new guard (REV-11) and raised no point on the break pass. The two modules are under `scripts/`, and no mutation campaign was run on them.
- NEEDED: the lead's ruling whether the remaining breaks are owed (a thin break pass by the builder over the listed values and early returns of the two modules, with the surviving operand killed or its explanation recorded) or whether the reviewer's planted-refusal reading closes the point. Or one line saying why the item is not valid.

### PO-S2-45 — No run of the spine triage on the real public cache is recorded

- ID: PO-S2-45
- TYPE: OPEN
- RAISED BY: the builder's return of S2-T05, 2026-11-14, under NOT DONE ("No admission-path test for a real Parquet cache; no claim of live qualification or source readiness"), read with the lead's lesson of 2026-11-15 on S2-T04 ("an approval on invented fixtures with normalised names says nothing about the real shape; the real-cache run belongs before the review").
- CONCERNS: the first acceptance criterion of task S2-T05 (provider `none` leaves a valid deterministic queue); PUB-35.
- EVIDENCE: Every test of the task runs on an invented cache. The build brief ruled that the real structures are S2-T04's matter and that the lead confirms them on the real cache before either task's turn. The lead's real-cache runs of 2026-11-15 are runs of S2-T04's spine, and its further pass rewrote the invented cache of the triage tests in the real shapes; the records hold no run of `scripts/spine_triage.py` itself on the real cache.
- NEEDED: one run of `uv run --locked python scripts/spine_triage.py` with provider `none` on the real public cache from the lead's own shell, recorded with counts and field names only: the exit code, the number of queue rows, and whether the queue written equals S2-T04's recomputed queue byte for byte; entered with the ledger of the task that integrates the spine. Or one line saying why the item is not valid.

### PO-S2-46 — The table of lineage node types of the activity graph is read only by a test

- ID: PO-S2-46
- TYPE: OPEN
- RAISED BY: the confirmation of the mutation pass of the graph module of task S2-T04 (Cognition SWE-2 High through Devin, 2026-11-15), a proposed item marked record (check G1); the builder's return names the same point
- CONCERNS: `LINEAGE_NODE_TYPES` in `custodian/src/eii_custodian/publicdata/review/graph.py`; `custodian/tests/test_activity_graph_survivors_refusals.py`; DAT-100 to DAT-103
- EVIDENCE: The pass removed the refusal "lineage edge has no lineage end" from `_check_edge`, which no input could reach behind `_check_edge_ends`. Since the removal no production line reads the table `LINEAGE_NODE_TYPES`; it stays as the declared table that `test_every_lineage_edge_type_has_a_lineage_node_at_one_end` reads, and that test fails if a later change gives a lineage edge type two public ends.
- NEEDED: when the graph module is next changed, either the table gets a production reader again or the test states in its own text that it is the table's only reader. Or one line saying why the item is not valid.

### PO-S2-47 — Three tests of the graph module's mutation pass rest on the behaviour of the Linux platform

- ID: PO-S2-47
- TYPE: OPEN
- RAISED BY: the confirmation of the mutation pass of the graph module of task S2-T04 (Cognition SWE-2 High through Devin, 2026-11-15), a proposed item marked hardening (checks G2 and G3)
- CONCERNS: `custodian/tests/test_activity_graph_survivors_writes.py` and `custodian/tests/test_activity_graph_survivors.py`; rule 37 of `AGENTS.md`
- EVIDENCE: The test of the staging removal plants a folder that cannot be removed by its mode bits: under a process that may remove any folder the plant has no effect, the three mutants it kills would survive, and the test would still pass. The test of the read under the C locale loses its kill under the interpreter's UTF-8 mode and never fails wrongly. The tests of the staging prefix assume a longest file name of 255 bytes and a temporary folder on another device than the shared-memory folder. All hold on the declared platform and in the lead's campaigns; none can fail wrongly.
- NEEDED: if the suite is ever run on another platform or as a privileged user, each of the three tests either proves its plant took effect before it asserts or is skipped there by name with its reason. Or one line saying why the item is not valid.

### PO-S2-48 — Card C8: the replay from a pinned file and the source entry of its fixture block

- ID: PO-S2-48
- TYPE: OPEN
- RAISED BY: the designated reviewer of task S2-T07 (Cognition SWE-2 High through Devin), 2026-11-14 and 2026-11-15: finding F1 of round 1 (its deferred part) and proposed item P5 of round 2
- CONCERNS: MTH-03 (a data test for each worked example); card C8 of document 07; `core/tests/fixtures/methods/public_methods.json`
- EVIDENCE: The arithmetic test on card C8's printed inputs exists since the fix of F1. The data replay was not added: the national census table is not among the pinned sources of the lead's cache (the pins file names ten sources, none of them that table). The fixture's source entry `pub_census_national` carries only the dataset name, where its sibling entries carry publisher, address and licence; the card states that the census layers state no licence.
- NEEDED: when the national census table is pinned, the replay of card C8 in `custodian/data_tests/` and the publisher and retrieval date in the fixture's source entry, by the task that writes the method-card pins. Or one line saying why the item is not valid.

### PO-S2-49 — The four calculation modules share one mutable decimal context

- ID: PO-S2-49
- TYPE: OPEN
- RAISED BY: the designated reviewer of task S2-T07, round 1, 2026-11-14, proposed item P2
- CONCERNS: document 17 (a proposed hardening point); `core/src/eii_core/calc/public_series.py`
- EVIDENCE: The reviewer's point: the modules share one mutable context object, `CALC_CONTEXT`; all arithmetic runs inside a local copy of it and nothing reads its flags, so results are unaffected, but a per-call copy or an immutable settings record would remove the surface a later edit could misuse. The confirmation of 2026-11-15 found exactly one stated decimal context in the module.
- NEEDED: a hardening entry of document 17, or one line saying why the item is not valid.

### PO-S2-50 — Two row types admit text fields without the exact-type check

- ID: PO-S2-50
- TYPE: OPEN
- RAISED BY: the designated reviewer of task S2-T07, round 1, 2026-11-14, proposed item P3
- CONCERNS: document 17 (a proposed hardening point); `core/src/eii_core/calc/public_methods.py`
- EVIDENCE: The reviewer's point: `TradeRow` and `AnnualEnergy` admit their text fields (`product`, `origin`, `month`, `unit`, `zone`) without the exact-type check that every other admission point applies. Only a subclass of the text type differs, and every numeric field still passes the exact-type checks.
- NEEDED: a hardening entry of document 17, or one line saying why the item is not valid.

### PO-S2-51 — Card C1: its two unprinted denominators and its data test

- ID: PO-S2-51
- TYPE: OPEN
- RAISED BY: the design review of task S2-T07 (xAI Grok 4.7 through Cursor, 2026-11-14, its fifth finding), the lead's ruling of 2026-11-14 on it, and the designated reviewer of the task, round 1, proposed item P4
- CONCERNS: card C1 of document 07 (task S2-T09 owns the cards); MTH-03; `custodian/data_tests/`
- EVIDENCE: Card C1 prints the two location quotients 1.39 and 3.05 and not the two counts they need. The lead read both from the cached open-licence table of active licences through the frame's municipality crosswalk and checked both quotients by hand within the card's tolerance of 0.01; the counts entered the method fixture with their source. That check is the lead's hand-check and no committed replay. Card C1 has no data test: it waits for the frame's population table.
- NEEDED: card C1 prints both counts (task S2-T09); a replay in `custodian/data_tests/` asserts both denominators from the pinned file and the two quotients, and the card's data test follows when the frame's table stands on the same tree. Or one line saying why the item is not valid.

### PO-S2-52 — The third worked row of card C2, by activity class, has no data test

- ID: PO-S2-52
- TYPE: OPEN
- RAISED BY: the lead's ruling of 2026-11-14 on the questions of the third pass of task S2-T07 (its third question)
- CONCERNS: card C2 of document 07; MTH-03; `custodian/data_tests/test_pinned_methods.py`
- EVIDENCE: The data tests replay the national cancellations and two municipal rows of card C2. The third worked row, by activity class, needs the reviewed activity spine of task S2-T04. The spine's code joined main with train B5 (pull request 59); its human review remains OI-203 on main.
- NEEDED: the data test of the third row once the spine is reviewed, named with its owner task. Or one line saying why the item is not valid.

### PO-S2-53 — One check value is divided under the caller's decimal context

- ID: PO-S2-53
- TYPE: OPEN
- RAISED BY: the designated reviewer of task S2-T07, confirmation of 2026-11-15, a proposed point marked record and hardening
- CONCERNS: document 17 (a proposed hardening point); `custodian/src/eii_custodian/publicdata/series/figures.py`, function `compute_checks`, key `value_bn_2dp`
- EVIDENCE: The reviewer's point: the exact total is divided by a Decimal power of ten under the ambient context. It is exact for every reachable total, and sensitive to the caller's context in principle, where the exact rational form would not be.
- NEEDED: a hardening entry of document 17, or one line saying why the item is not valid.

### PO-S2-54 — The refusal distance of an approximate value is absolute

- ID: PO-S2-54
- TYPE: OPEN
- RAISED BY: the designated reviewer of task S2-T07, confirmation of 2026-11-15, a proposed point marked record and hardening
- CONCERNS: document 17 (a proposed hardening point); `core/src/eii_core/calc/public_series.py`, constant `BOUNDARY_DISTANCE`
- EVIDENCE: The reviewer's point: the band of 1e-40 covers the stored error of a fifty-digit value only for magnitudes below roughly 1e9. Every value the layer produces stays far under that; a later approximate path at larger magnitudes would need the band scaled.
- NEEDED: a hardening entry of document 17, or one line saying why the item is not valid.

### PO-S2-55 — The calendar of card C2 is written twice

- ID: PO-S2-55
- TYPE: OPEN
- RAISED BY: the designated reviewer of task S2-T07, confirmation of 2026-11-15, a proposed point marked record and hardening
- CONCERNS: document 17 (a proposed hardening point); `core/src/eii_core/calc/public_methods.py`, function `licence_churn`, and the constant `C2_CALENDAR` of `public_series.py`
- EVIDENCE: The reviewer's point: `licence_churn` keeps its own copy of the 125-month calendar, identical to the constant; sharing the constant would prevent drift.
- NEEDED: a hardening entry of document 17, or one line saying why the item is not valid.

### PO-S2-56 — The mutation runner's copy of the `docs` folder after the repair of task S1-T19

- ID: PO-S2-56
- TYPE: OPEN
- RAISED BY: the lead, at the join of merge train B4, 2026-11-15
- CONCERNS: `scripts/mutation.py`, function `run_packages`; document 17
- EVIDENCE: Task S2-T07 added three lines that copy the repository's `docs` folder into each package copy, because a package's tests run one folder deeper there and `core/tests/test_second_fix.py` reads `docs/03_DATA_CONTRACTS.md` by walking up from its own file. The repair of task S1-T19, on main since pull request 54, makes the copy's root an empty git repository and adds a shared root lookup for tests (`custodian/tests/repository_root.py`). Whether the three lines are still needed after it was not tested.
- NEEDED: one run of the campaign of a `core/src` module with the three lines removed; then the lines stay with a comment that says why, or go with the test brought to the shared lookup. Or one line saying why the item is not valid.

### PO-S2-57 — Values that are not numbers under names ending `_unrounded`

- ID: PO-S2-57
- TYPE: OPEN
- RAISED BY: the lead's ruling of 2026-11-14 on the questions of the third pass of task S2-T07 (its tenth question)
- CONCERNS: the result types of `core/src/eii_core/calc/`; DAT-90
- EVIDENCE: The ruling's words: non-number values under names ending `_unrounded` stay in version 1 with an open item. The fields concerned were not listed on the joined tree when this item was entered.
- NEEDED: the list of those fields and one decision: they are renamed, or the name's meaning is written into the contract. Or one line saying why the item is not valid.

### PO-S2-58 — Hardening of the fact layer that was recorded and not built

- ID: PO-S2-58
- TYPE: OPEN
- RAISED BY: the lead's ruling of 2026-11-14 on the second verification of task S2-T07 (its list "not built, recorded")
- CONCERNS: document 17 (proposed hardening points); DAT-134; the fact schema's task
- EVIDENCE: The ruling lists, as beyond the task's criteria or in another task's file: making a fact constructible only through the wrapper (the language cannot enforce it; the origin check of DAT-134 belongs to the fact schema's task); a closed licence list, a host rule for a source address, and a retrieval date checked against the period; and the plain-decimal form of the decomposition that the public-series figures of S2-T03 call. Whether that plain form still exists after the exact-arithmetic fix was not checked when this item was entered.
- NEEDED: a hardening entry of document 17 for each point that still holds, with its owner task. Or one line saying why the item is not valid.

### PO-S2-59 — The purity guard names four modules; the apportioning module is not among them

- ID: PO-S2-59
- TYPE: OPEN
- RAISED BY: a helper of the lead at the trial join of merge train B4, 2026-11-15; checked again on the joined work commit for this ledger
- CONCERNS: the first criterion of task S2-T07 in TASKS.md; `core/tests/test_calculation_purity.py`; `core/src/eii_core/calc/apportion.py` (task S2-T13)
- EVIDENCE: The guard imports and lists `facts`, `public_methods`, `public_series` and `sector_economics` by name. Main gained `apportion.py` in the same package with pull request 52, after this task's base. On the joined tree the guard does not read it, and no test fails when a calculation module is added without joining the list.
- NEEDED: the guard reads every module of `core/src/eii_core/calc/` (a listing of the folder, with a plant), or the list gains the module with one test that fails for an unlisted file. Or one line saying why the item is not valid.

### PO-S2-60 — The data-test command stands in no rules file

- ID: PO-S2-60
- TYPE: OPEN
- RAISED BY: a helper of the lead, 2026-11-15, from the lead's ruling of 2026-11-14 on the second verification of task S2-T07 (its point on data tests) read against rule 44
- CONCERNS: rule 44 of AGENTS.md and CLAUDE.md; TST-197 and TST-198; `custodian/data_tests/`
- EVIDENCE: The ruling says that the data tests stand outside the whole test command's discovery, that the lead runs them on the real cache with the evidence in the ledger, and that their command joins rule 44 in the task's document part. Rule 44 on the joined tree names no data-test command, and neither `README.md` nor `core/README.md` names the folder. The lead ran them as `uv run --locked python -m pytest custodian/data_tests -q -p no:cacheprovider` with the public cache linked into the workspace.
- NEEDED: the command and its condition (the real public cache, the lead's shell only, never a test, a gate or CI) in rule 44 of both rules files, by a documents change; or one line saying why rule 44 does not need it.

### PO-S2-61 — The runner's refusal of `PYTEST_ADDOPTS` reads the process environment only

- ID: PO-S2-61
- TYPE: OPEN
- RAISED BY: the confirmation of the joined `scripts/mutation.py` for task S2-T07 (Cognition SWE-2 High through Devin, 2026-11-15), its one proposed item, marked hardening
- CONCERNS: `scripts/mutation.py`, function `run_copy`; tasks S2-T07 and S1-T19; document 17 (a proposed hardening point)
- EVIDENCE: The reviewer's point: the refusal of a set `PYTEST_ADDOPTS` in `run_copy` reads the process environment and not the `environment` mapping that a caller may pass. No caller in the tree can bypass it: the package run derives its environment from the process environment, so the refusal fires first, and the typed-decision run uses the process environment directly (check K3 of the confirmation). A later caller that passes a hand-built environment holding the variable would not be refused. The point is beyond both tasks' acceptance criteria.
- NEEDED: the refusal also reads the mapping that is passed, with a planted test; or one line saying why the item is not valid.

### PO-S2-62 — `GraphRefused` is exported and nothing raises it

- ID: PO-S2-62
- TYPE: OPEN
- RAISED BY: the confirmation of the joined change of S2-T21 (Cognition SWE-2 through Devin, 2026-11-15), proposed item
- CONCERNS: `custodian/src/eii_custodian/publicdata/review/graph.py` (the class `GraphRefused` and the module's export list), a file of task S2-T04
- EVIDENCE: The reviewer's words: "GraphRefused stays exported in graph.py (__all__, line 762) and nothing raises it — dead export for a later owner to remove." The join of S2-T21 removed the one raise, the release refusal on a licence that items 1 and 9 of [decision 0026](docs/decisions/0026-public-sources-used-in-full-locally.md) end; the builder's return says the same under its check for the lead.
- NEEDED: the follow-up task of slice S2, or the next task that owns the graph module, removes the class and its export with any import of it; or one line says why it stays.

### PO-S2-63 — Three mentions of the basis `none_stated` that no loaded row can reach

- ID: PO-S2-63
- TYPE: OPEN
- RAISED BY: the builder of the join pass of S2-T21 (xAI Grok 4.7 through Cursor) and the confirmation of the joined change (Cognition SWE-2 through Devin), 2026-11-15
- CONCERNS: `custodian/src/eii_custodian/publicdata/frame/live.py` (`build_live_frame`); `custodian/src/eii_custodian/publicdata/frame/census.py` (`census_rows`); `custodian/src/eii_custodian/publicdata/confirm_s2_t13.py` (`BASES`); their tests that plant the basis
- EVIDENCE: The reviewer's words: "frame/live.py, frame/census.py and confirm_s2_t13.py still name the basis none_stated; unreachable from a loaded registry row — cleanup belongs to a task that owns those files." The loader refuses the basis, so only a planted entry takes the two frame arms, and the confirmation module reads no registry row. The lead's ruling for the join left the three as they are.
- NEEDED: the follow-up task of slice S2 removes the two dead arms and the two values of `BASES` that decision 0026 retired, with the tests that plant them changed to the bases that exist; or one line says why each stays.

### PO-S2-64 — No test builds the cached graph in release mode after the join

- ID: PO-S2-64
- TYPE: OPEN
- RAISED BY: the confirmation of the joined change of S2-T21 (Cognition SWE-2 through Devin, 2026-11-15), proposed item
- CONCERNS: `custodian/src/eii_custodian/publicdata/review/graph.py` (`build_cached_graph`); `custodian/tests/test_activity_planted.py`
- EVIDENCE: The reviewer's words: "No test calls build_cached_graph with mode="release" after the join — a coverage point, not a weakened assertion." The join removed `test_cached_release_refusal_writes_nothing`, which planted only the licence refusal that the record ends; the release build of the uncached path is covered by `test_release_build_of_the_classification_source_is_not_refused`.
- NEEDED: the follow-up task of slice S2 adds one test that builds the cached graph in release mode on invented inputs and asserts what it writes; or one line says why it is not valid.

### PO-S2-65 — Hardening of the terms record that S2-T21 named and did not build

- ID: PO-S2-65
- TYPE: OPEN
- RAISED BY: the builder of S2-T21 (xAI Grok 4.7 through Cursor, 2026-11-14), in the return of the build pass; the design review (OpenAI GPT-6) had ruled the three deferred
- CONCERNS: `custodian/src/eii_custodian/publicdata/fetch/registry.py`; `custodian/publicdata/sources.yaml` (the fields `licence_id`, `terms_words`); the build log of `./eii build-public`; document 17, DHA-102
- EVIDENCE: The builder's words: "A machine check joining the DHA-102 list to the registry. A normalised `licence_id` vocabulary. A build-log count of `terms to be read` rows." The design review's words on them: "Leave the DHA-102 cross-check, licence vocabulary and pending-row count deferred." Two further leftovers of the same change stand by design: the registry flag `terms_watch`, which two rows set and which now changes nothing, and the receipt field `switched_off`, which is always false.
- NEEDED: the follow-up task of slice S2 decides each of the three (built with a planted violation, or one line why not) and whether the two inert fields leave the registry and the receipt with a schema change of their own.

### PO-S2-66 — The busy-venue name scan fails on a bytecode file under the tests folder

- ID: PO-S2-66
- TYPE: OPEN
- RAISED BY: the lead, from the return of the mutation pass of S2-T21 (xAI Grok 4.7 through Cursor, 2026-11-15) and from a second helper run on a former candidate tree (2026-11-15); a failure with a known cause, recorded once for merge train C under rule 39, under S2-T21, whose test it is
- CONCERNS: `custodian/tests/test_publicdata_registry.py` (`test_no_non_python_test_file_names_busy_gmaps` and the scan it calls, `non_python_files_naming_busy`); document 17 (a proposed hardening point)
- EVIDENCE: The scan reads as UTF-8 text every file under `custodian/tests` that is not a Python file, so a binary file there stops it with a decoding error that names no rule. The input records describe two occurrences. In the mutation pass of S2-T21 one run of the custodian tests ended with exit code 1 on a bytecode file of the new test file, written by the test runner under `custodian/tests/__pycache__/`; the builder removed the file, ran the tests again with bytecode writing switched off and recorded 1,311 passed, exit code 0. On that former candidate tree a helper's run of `uv run --locked python -m pytest custodian/tests/test_publicdata_registry.py custodian/tests/test_publicdata_behaviour.py -q -p no:cacheprovider`, after five other pytest commands in the same tree, ended with exit code 1, `1 failed, 69 passed`, on the same test and a compiled file that its own earlier runs had written; its shell had not set the no-bytecode variable. Why the lead's own runs pass: the whole test command sets the no-bytecode variable for its test processes (`scripts/run_tests_exec.py`), and the commands of a ledger run in a tree with no bytecode files and with that variable set. So run on the former trial tree, the same command gave 70 passed, exit code 0. These are historical results, not results on train C. The permitted registry-file run at the train C work commit also met the decoding failure (15 failed, 14 passed overall, exit 1); the other failures concern the missing terms fields of the places file row.
- NEEDED: the follow-up task of slice S2 makes the scan read the files that git lists, or read bytes and search them, so that a cache file can neither stop it nor hide a named file from it, with a planted binary file; the scan is not narrowed to pass. Until then the commands of a ledger run in a tree with no bytecode files and with the no-bytecode variable set. Or one line says why it is not valid.

### PO-S2-67 — Two test files of S2-T21 are longer than the briefs' target

- ID: PO-S2-67
- TYPE: OPEN
- RAISED BY: the builder of S2-T21 (xAI Grok 4.7 through Cursor, 2026-11-14), in the return of the build pass, as a check for the lead
- CONCERNS: `custodian/tests/test_publicdata_behaviour.py`; `custodian/tests/test_publicdata_registry.py`
- EVIDENCE: The builder's words at the build pass: "`custodian/tests/test_publicdata_behaviour.py` is 1094 lines and `test_publicdata_registry.py` is 634. The brief says 500 lines is a target, not a failure. They were not split." At `5147fdecdcac222a150464e0e43644d26f89d24d` the two files hold 1,318 and 679 lines.
- NEEDED: the follow-up task of slice S2 splits the two files by subject with no test changed, removed or renamed (the names are cited by this ledger), or one line says that the target does not bind test files.

- ID: PO-S2-68
- TYPE: OPEN
- RAISED BY: the lead (Anthropic Claude), 2026-11-15, from the rerun of the campaign of fetch/build.py on merge train C
- CONCERNS: `custodian/src/eii_custodian/publicdata/fetch/build.py`; `scripts/mutation_explained.toml`
- EVIDENCE: At `5147fdecdcac222a150464e0e43644d26f89d24d` the campaign of the module made 630 mutants: 494 killed, 131 survived, 5 not covered, exit 1. Placed by `git blame` over the train's commits, all 136 stand on lines main already held (S2-T01, train A, S2-T22, S2-T15) and none on the 61 lines of S2-T21; the explanations file holds no row for the module.
- NEEDED: a thin test pass of slice S2 kills each survivor or proves it equivalent with a row of the explanations file, before the slice S2 gate; no test of the module is weakened.

## Sources

- The master open-item decisions and defaults reflected in [01_PROJECT_BRIEF.md](docs/01_PROJECT_BRIEF.md), [09_AI_ASSISTANT.md](docs/09_AI_ASSISTANT.md) and [decision 0014](docs/decisions/0014-typed-decision-gateway.md).
- Additional open questions and assumptions recorded in documents 01 to 16 and the decision records indexed in [docs/README.md](docs/README.md).
