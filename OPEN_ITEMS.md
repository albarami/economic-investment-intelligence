# Open items

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016, 0017 and 0018 on 2026-11-12 (see PROGRESS.md) |
| Date | 2026-11-12 |
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

## OI-01 — Main model key (supplied for go-live; not used during the build)

- ID: OI-01
- TYPE: OPEN
- NEEDED: At go-live only: the owner's decision to switch the live adapter on, with any spend caps set then. During the build the key is not used.
- WHY: Live-model evaluation and operation cannot be claimed until the key and cost limits exist.
- DONE SO FAR: The template writer and recorded provider are used throughout the build; no build, CI or slice gate calls a keyed model service, and live-model runs (prepared recordings refreshed live, model-returned briefs, a full live run) form a go-live gate enabled by an owner decision after this item is closed.
- OPTIONS: **Recommendation:** keep the template writer and the recorded provider for the whole build; the live adapter and its evaluation gates wait for the owner's go-live decision.
- NEEDED BY: go-live (not before; the build runs in template mode).
- UPDATE: 2026-11-12, by the owner's note of that day, recorded in [decision 0018](docs/decisions/0018-priorities-and-amendments-to-decision-0015.md): key supplied for go-live; not used during the build. The assistant stays in template mode during the build.

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
- DONE SO FAR: The candidate sources and reconciliation steps are documented; affected display cards stay blocked.
- OPTIONS: **Recommendation:** follow the documented reconciliation and default to the named production-value and occupation tables only after sign-off. Otherwise leave the figures hidden.
- NEEDED BY: slice S2 reconciliation; slice S7 methods and affected story scenes.

## OI-04 — Census map-layer licence

- ID: OI-04
- TYPE: CLOSED for version 1 (was OPEN)
- NEEDED: Written licence confirmation for the statistics authority's census map layers and associated boundary use.
- WHY: Redistribution and display rights are not stated.
- DONE SO FAR: A source with no stated licence is validation-only until its terms are recorded. No value, derived share, title or geometry from it enters a release. The coverage bar uses the finest licensed geography available (zone, otherwise municipality, otherwise national) and names it.
- OPTIONS: **Recommendation:** obtain and record written confirmation; until then keep the source validation-only and use the finest separately licensed geography for coverage and boundary geometry.
- NEEDED BY: slice S2 public frame and coverage data.
- CLOSED: 2026-11-12, by the owner's note of that day, recorded in [decision 0017](docs/decisions/0017-public-data-additions-and-public-splits.md): the census map layers of the statistics authority's public map service are used in this internal project. The written licence question for any use beyond it is a real-deployment item in [docs/17_DEPLOYMENT_HARDENING.md](docs/17_DEPLOYMENT_HARDENING.md), section "Items moved from OPEN_ITEMS.md".

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
- DONE SO FAR: No prospect list is in version 1; firm and owner networks are dropped.
- OPTIONS: **Recommendation:** keep it excluded. Any later list needs an owner-approved decision and a fresh privacy and wording review.
- NEEDED BY: After slice S11, backlog item L8.
- CLOSED: 2026-11-12, by the owner's decisions of that day, recorded in [decision 0016](docs/decisions/0016-version-1-covers-the-whole-initiative.md) (item 12): named synthetic firms are allowed in version 1 as prospects, partners and suppliers, always marked Synthetic, with names that never resemble real ones; networks of firms or owners stay dropped.

## OI-08 — Oversight labels and organisation minimum

- ID: OI-08
- TYPE: OPEN
- NEEDED: Approve the live-row label, confirm the distinct-organisation minimum for demand aggregates, and align the canonical read function.
- WHY: Oversight must show demand without exposing company identity or small-group behaviour.
- DONE SO FAR: Live rows default to “this session”, seeded history to Synthetic, and no company identity is shown. The minimum is two for the two-company demonstration; this is demonstration configuration, not a disclosure threshold.
- OPTIONS: **Recommendation:** keep the labels and the demonstration minimum of two; any other value needs an owner decision and must not be presented as a privacy rule.
- NEEDED BY: slice S9 oversight and database tests.

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
- DONE SO FAR: Preflight uses whichever answers; CI always uses a service container.
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
- TYPE: OPEN
- NEEDED: Enable secret scanning, push protection and branch protection under the owner's standing permission.
- WHY: Public-repository safety needs platform controls as well as local scans.
- DONE SO FAR: The requirement is assigned to slice S0; local documentation and identifier checks exist.
- OPTIONS: **Recommendation:** enable all three and record the settings evidence; do not weaken them to make CI pass.
- NEEDED BY: slice S0.

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
- TYPE: OPEN
- NEEDED: Owner confirmation of the project token cap and a key rotation date, and of whether the gateway's provider key may be used during the build: the owner's note of 2026-11-12 keeps the API keys of the uncommitted `.env` file for go-live and does not name this key ([decision 0018](docs/decisions/0018-priorities-and-amendments-to-decision-0015.md) item 12).
- WHY: Offline provider use still needs a hard cost limit and credential hygiene.
- DONE SO FAR: Default cap is 5 million tokens in total; no agent may purchase, upgrade or renew.
- OPTIONS: **Recommendation:** confirm or tighten the default and record rotation before provider use; agents never change the subscription. No keyed provider run is made before the owner answers.
- NEEDED BY: slice S1 gateway qualification and every later provider run.

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
- DONE SO FAR: Candidate mechanisms and named spike tests are documented.
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
- DONE SO FAR: Default is yes. The presenter console carries Scenario inputs for the break-even method, and the server calculates from those typed values.
- OPTIONS: **Recommendation:** permit numeric entry only in the presenter's Scenario inputs control, limited to the six documented method inputs; keep the browser and model from calculating or inventing values.
- NEEDED BY: slice S7 break-even method; slice S10 presenter controls and guided story.

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
- WHY: The pack pins Python 3.14 managed with `uv` as one workspace of `core`, `custodian` and `product` (docs/02_ARCHITECTURE.md lines 499 and 522) but does not say how that Python request is written in the workspace metadata and in `.python-version`. The documents read for this task (docs/02_ARCHITECTURE.md sections 7 and 8, docs/08_BACKEND.md section 2, docs/12_TESTING_AND_QUALITY.md TST-60) do not describe the workspace root, the package version or where the metadata tests live. The pack requires code shared by the two Python planes to live only in `core/` (ARC-01, docs/02_ARCHITECTURE.md line 112) and forbids every other edge (ARC-06, docs/02_ARCHITECTURE.md line 186; BE-01 to BE-03, docs/08_BACKEND.md lines 64 to 66); this permits, but does not require, the two edges to `eii-core` before any shared code exists.
- DONE SO FAR: A non-package root `eii-workspace` (`[tool.uv] package = false`, no dependencies, no build system) with the three members `core`, `custodian` and `product`; `gateway/` is not a member. Each member uses the `src` layout (docs/08_BACKEND.md line 29, itself an assumption), version `0.0.0` and `requires-python = ">=3.14"`; `.python-version` holds `3.14`. `eii-custodian` and `eii-product` each declare `dependencies = ["eii-core"]` with `eii-core = { workspace = true }` in `[tool.uv.sources]`; `eii-core` declares no dependency. No sub-module exists yet. The guard and its tests are three standard-library files under `scripts/tests/` (`workspace_guard.py`, `workspace_fields.py` and `test_workspace_metadata.py`) and the clean-environment tests a fourth. The two edges, and the absence of every other edge between the three packages, are proved by `uv run --locked python -m unittest discover -s scripts/tests -p 'test_*.py' -v` (test `test_real_workspace_passes`, rules `workspace-source`, `dependency-edge` and `lock`) and by `uv lock --check`.
- OPTIONS: **Recommendation:** keep; a version scheme is decided when the first release is built, and per-package tests move to pytest in a later task. Alternatives: declare no dependency until the first import of `eii_core` exists (the two `[tool.uv.sources]` tables and the guard's two expected lock edges are then removed in that change); make `gateway/` a fourth member; or use a root without a `[project]` table.
- NEEDED BY: slice S0 gate.

## OI-40 — uv version and build-backend bound

- ID: OI-40
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm, and an exact `uv` pin at task S0-T12.
- WHY: The pack says `uv` is pinned at slice S0 but gives no number (docs/02_ARCHITECTURE.md line 499), and the preflight row for locked dependencies requires that nothing is downloaded (docs/13_DEPLOYMENT_AND_OPERATIONS.md line 71).
- DONE SO FAR: The build machine has uv 0.11.31. All three members declare `requires = ["uv_build>=0.11.31,<0.12"]`. Tests in scripts/tests/test_clean_environment.py check the lock and install the members with an empty cache and --offline, without a download. uv is pinned by task S0-T12: `required-version` in the root `pyproject.toml`, recorded in `pins.toml` (OI-54). That task re-checked the table and the child environment named below: the pin is 0.11.31, the version they were written for, and `scripts/check_versions.py` reads `required-version` from the file because uv ignores it under `UV_NO_CONFIG=1`. The metadata guard's table of dependency-bearing fields and the child environment of the clean-environment tests were written for uv 0.11.31; that child environment sets `UV_NO_CONFIG=1`, which also makes uv ignore settings written in a `pyproject.toml` `[tool.uv]` table, so a task that adds such a setting revisits it. The uv documentation on configuration files names a project-level `uv.toml`, which takes precedence over the `[tool.uv]` table of a `pyproject.toml` in the same folder; the metadata guard does not read such a file, the clean-environment tests switch it off with `UV_NO_CONFIG=1`, and task S0-T12 (version pins) is the place to forbid or scan it.
- OPTIONS: **Recommendation:** task S0-T12 pins uv to the version on the build machine, keeps the bound in step with it, and re-checks the table of dependency-bearing fields and the child environment whenever the pin changes. Alternative: raise the bound together with an upgrade of uv on the build machine, once the owner approves that upgrade.
- NEEDED BY: task S0-T12; confirmed at slice S1.

## OI-41 — Conventions of the web skeleton

- ID: OI-41
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of eleven conventions of `web/`, each one a choice the pack permits and does not require: (1) the empty folders of the section 3.1 layout are kept by empty `.gitkeep` files; (2) `web/scripts/` holds the checks beside the pinned layout; (3) files owned by other tasks are not created and are named as deferred by the layout check; (4) the shell is English, with `lang="en" dir="ltr"` on the root element, an empty `main` element, a `data:,` icon and only the working title as text; (5) the development server binds `127.0.0.1` with a strict port through the flags of the `dev` script, keeping Vite's default port, and `engines.node` is the range `>=22.12.0 <23`; (6) the scan rules: the scan of the built JavaScript allows four named hosts, and the host scan and the import-boundary check handle closed lists of forms, each with a stated "not handled" part; (7) the TypeScript compiler options in `tsconfig.json` (strict family flags, `ES2022`, `bundler` resolution, `react-jsx`, `types` empty, no emit) and the `build` script `tsc --noEmit && vite build`; (8) the checks are dependency-free Node scripts run as `check:*` and `test:checks`, tested with Node's built-in runner in `*.node-test.mjs` files; (9) the package metadata (`name` `eii-web`, `private`, version `0.0.0`, licence `UNLICENSED`) and the absence of an `.npmrc`; (10) the import-boundary check reads `src/`, `tests/`, `eslint-rules/` and `vite.config.ts`, which is wider than FE-07, whose words name `web/src` only, and does not read `scripts/`, and the layout check fails a second Vite configuration file name beside `vite.config.ts`; (11) code files under `web/` aim at no more than 500 lines, a house target that the pack does not state, so the larger check scripts and test files were split by theme into several files; by [decision 0018](docs/decisions/0018-priorities-and-amendments-to-decision-0015.md) item 14 the limit is a target, never a gate: a file a little over is fine and a size check only warns.
- WHY: The pack fixes the layout and the file names of `web/` (docs/10 section 3.1, lines 93 to 122), Node 22 with npm (docs/02 lines 508 and 522), React 19.3.1 and Vite 8.3.x (docs/10 lines 55 and 56), the built front end served at `/` and `/assets/*` (docs/08 line 498), no third-party host (FE-05, DES-24), the import-boundary check (FE-07: it fails if `web/src` imports from outside `web/`, docs/10 line 205) and the document language and direction set at the root (DES-143). It does not say how an empty folder is kept, does not list `scripts/` in the layout, gives no compiler options, no script names, no package metadata and no limit on the length of a code file, and names Vitest for front-end tests with tools pinned at slice S0 (docs/10 line 569, docs/12 line 443). The product name is not cleared (OI-05) and language switching is slice S3 (FE-61). Node is given as "22 (22.12 or later ...)", a range, while FE-01 asks for exact versions of dependencies. React ships namespace and message URLs that are not requests.
- DONE SO FAR: 21 empty marker files (14 under `src/`, 6 under `tests/`, 1 `eslint-rules/`), proved by `npm run check:layout`. `REFERENCE_NOTES.md` (S0-T13) is named as deferred, not created; `eslint.config.js` was moved into the required list by task S0-T04. The allowed hosts for built JavaScript are `www.w3.org`, `react.dev`, `reactjs.org` and `github.com`, taken from the contents of the React packages, applied to built JavaScript only; a host outside the list found in a real build is reported to the lead and never added by the builder. The compiler options are observed by `npm run build`. The shell files and the `dev` flags are proved by `npm run test:checks` and `npm run check:dev`; the `engines` key is required to be present and its value is not judged. On 2026-11-11 the owner decided that the lead assigns each slice S0 requirement that no task owned to the nearest task and records it; the lead then assigned the import-boundary check of FE-07 to S0-T03, FE-11 to S0-T04, and the confirmation of font weights and of the icon licence (DES-25, DES-45) to S0-T13. The exact Node patch and version files are S0-T12; the test runner choice for the front end is S0-T05.
- OPTIONS: **Recommendation:** keep these readings; the end-to-end test that blocks other origins (ARC-36) and the server Content Security Policy are the later guards. Alternative: a one-line `README.md` in each marker folder; a scanner that parses the built JavaScript; moving the check tests to Vitest when S0-T05 lands; reading `web/src` only in the import-boundary check.
- NEEDED BY: slice S0 gate.

## OI-42 — Web dependency versions taken from the registry

- ID: OI-42
- TYPE: ASSUMPTION
- NEEDED: Confirmation of the web pins at the slice S1 spike, and a decision on TypeScript 7 then. Owner confirmation that no `@types/node` is added.
- WHY: The pack pins React and React DOM at 19.3.1 and Vite at 8.3.x with 8.3.8 as the latest (docs/10 lines 55 and 56), and says `typescript` is "pinned at slice S0 (not covered by the research)" (docs/10 line 57), so it gives no TypeScript number. It names neither the Vite React plugin nor the React type packages. FE-01 asks for exact versions.
- DONE SO FAR: `react` 19.3.1, `react-dom` 19.3.1 and `vite` 8.3.8 are pack pins to confirm at slice S1. ASSUMPTION, taken from the registry on 2026-11-11 with the commands recorded in the research notes of the task: `@vitejs/plugin-react` 6.3.0, `@types/react` 19.3.0, `@types/react-dom` 19.3.0 and `typescript` 6.0.3. TypeScript is held at 6.0.3, not 7.0.2, because the lint rules of S0-T04 need `typescript-eslint` 8.72.2, which declares the peer range `>=4.8.4 <6.1.0`, and TypeScript 7.0 ships no compiler API; 6.0.3 is the newest release inside that range. No required peer of the set is unmet. `@types/node` is not added because the shell uses no Node API and the registry has no such package for Node 22.22.3. No retreat pin is recorded for the front end.
- OPTIONS: **Recommendation:** keep, and re-evaluate TypeScript 7 at slice S1. Alternative: pin TypeScript 7.0.2 once a typescript-eslint release supports it.
- NEEDED BY: slice S1 spike.

## OI-43 — Fonts are not bundled in the skeleton

- ID: OI-43
- TYPE: ASSUMPTION
- NEEDED: Confirmation that the web skeleton bundles no font, and the choice of the font package for IBM Plex Sans and IBM Plex Sans Arabic.
- WHY: The pack fixes IBM Plex Sans and IBM Plex Sans Arabic, self-hosted as WOFF2 from pinned npm packages (docs/10 line 463), with the pin at slice S0 (docs/10 line 64), and DES-24 requires the font files and licence text to be served by the application and no font fetched from a third-party host. FE-97 (licence text with every bundled font) is slice S3 and the tabular-figures check is slice S1. The pack does not name the npm package and does not say which task adds the files. The shell has no styled text.
- DONE SO FAR: The skeleton adds no font, no font declaration and no font package, and its host scan fails a URL with a scheme and two separators and a protocol-relative URL with a dotted host, so the scan fails the listed URL forms in the files it reads (see `web/README.md`). On 2026-11-11 the owner decided that the lead assigns each slice S0 requirement that no task owned to the nearest task and records it; the lead then assigned the import-boundary check of FE-07 to S0-T03, FE-11 to S0-T04, and the confirmation of font weights and of the icon licence (DES-25, DES-45) to S0-T13. Vendoring the font files with the licence text stays with slice S3 (FE-97). Registry facts for four candidate packages (`@fontsource/ibm-plex-sans` and `@fontsource/ibm-plex-sans-arabic` 5.3.0, `@ibm/plex-sans` and `@ibm/plex-sans-arabic` 1.1.0, all OFL-1.1) are in the research notes of the task.
- OPTIONS: **Recommendation:** vendor at slice S3 with FE-97 after the S0-T13 confirmation. Alternative: add the font packages to the S0-T12 pins now.
- NEEDED BY: S0-T13 (confirmations); slice S3 (vendoring).

## OI-44 — Python lint, format and type-check tools

- ID: OI-44
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of the Python lint, format and type-check tools and settings.
- WHY: The pack requires lint, format and type checks (docs/12 line 313; docs/14 line 190) but names no Python tool, rule set, strictness level or version.
- DONE SO FAR: `ruff` 0.17.4 (lint and format) and `mypy` 2.4.1 (strict mode) are declared with exact versions in the `dev` dependency group of the root `pyproject.toml`, which `uv run` installs by default, and are locked in `uv.lock`; the versions are the registry releases of 2026-11-05 and 2026-10-28, read on 2026-11-11. Ruff rule families: `E4`, `E7`, `F`, `B`, `I`, `UP`, `RUF` (explicit, because the official pages describe the default set inconsistently); `fix = false`; ruff's `target-version` is `py312` because the documentation workflow runs `scripts/check_docs.py` on Python 3.12 and the formatter would otherwise write syntax that Python 3.12 rejects, while mypy checks against the Python 3.14 the pack pins; Markdown files are excluded from the formatter, as the ruff page recommends. The checks cover `scripts/`, `core/src`, `custodian/src` and `product/src`; `evals/` and `gateway/` hold no Python file yet. No suppression comment, per-file ignore or weaker setting was added to make the code pass; the files that needed an annotation or a formatting change are listed in the pull request. Three places in the clean-environment tests of S0-T02 were adjusted: the shared sync command (one constant, used by its class set-up and its hostile-surroundings test) gained `--no-dev`, because the dev group cannot be downloaded offline; the stale-lock test prepares a lock without registry packages, because a lock with registry packages cannot be re-resolved offline; and the hostile-surroundings test's per-variable runs use a workspace copy whose root dependency-groups table is removed and whose lock is regenerated offline, because without that step offline sync tries to satisfy the dev group from the cache and the per-variable sub-test fails for that reason instead of the variable under test. Each of the three commands has planted violations in the three `scripts/tests/test_pychecks_*.py` test files. The suppression comments that S0-T02 left (one `noqa: E402`, five `type: ignore`; proposed item PO-S0-02 below) are judged by the new checks: a comment that ruff or mypy reports as unused is removed, one that the tool shows to be used stays, and the pull request lists the result. House style (a ruling of the lead, an ASSUMPTION, not stated by the pack): files aim at 500 lines or fewer, every function signature is annotated, public non-test functions are documented in the Google style, and no bare `except` is used. Mypy in strict mode enforces the annotations. File length and the other house-style points are targets, not gates: they never fail a commit, a test or a check, and no tool configured by this task enforces a file-length limit or docstrings. The pack states neither.
- OPTIONS: **Recommendation:** keep. Alternatives: `basedpyright` in strict mode instead of `mypy`; a wider ruff rule set later (for example the numeric-literal lint of SYN-02 in the generator slice).
- NEEDED BY: slice S0 gate.

## OI-45 — Web lint, format and type-check tools and the scope of FE-11

- ID: OI-45
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of the web lint, format and type-check tools, of the lint scope, and of the way FE-11 is enforced.
- WHY: The pack names ESLint, a flat configuration `eslint.config.js` and a folder `eslint-rules/` (docs/10 lines 98 and 99) and a custom rule in slice S3 (lines 356 to 372), and FE-11 asks for a lint rule that forbids `fetch` and `EventSource` elsewhere than `src/api/` (line 209), and names no exception for tests or tool scripts. It names no formatter, no type-check command, no ESLint version and no rule preset.
- DONE SO FAR: The owner decided on 2026-11-11 that the lead assigns each slice S0 requirement that no task owned to the nearest task; the lead assigned FE-11 to S0-T04. `eslint` 10.14.0, `@eslint/js` 10.0.1, `typescript-eslint` 8.72.2 (untyped `recommended` preset), `eslint-plugin-react-hooks` 7.1.1, `globals` 17.14.0 and `prettier` 3.9.10 (check only) are exact development dependencies, taken from the registry on 2026-11-11; Prettier 3.10.0 was the latest release but was published on that day, so the previous release is pinned. FE-11 uses the built-in rule `no-restricted-globals` (no custom rule). ASSUMPTION put to the owner: the rule applies to every file ESLint lints under `web/` (the eight extensions `js`, `mjs`, `cjs`, `jsx`, `ts`, `mts`, `cts`, `tsx`; tests, `scripts/` and configuration files included) with the single exception `src/api/**`, because the pack states the requirement without an exception; the tested forms are listed in `web/scripts/tests/lint-fe11.node-test.mjs`. ESLint skips every other file type silently, so the list of extensions is part of the configuration. ESLint also reads `web/scripts/` (the check scripts of S0-T03 and their tests, with the JavaScript rule set), except the generated folders `dist/` and `node_modules/`; no rule is switched off for any folder, and one may be switched off only by the lead's decision, written in `eslint.config.js` with its reason and recorded here; Prettier reads everything except `dist/`, `package-lock.json` and Markdown. The write-mode commands `uv run --locked ruff format .` and `npm run format` are in rule 44. ESLint 10.14.0 needs Node `^22.13.0`, while `engines.node` of `web/package.json` allows `>=22.12.0 <23`; the exact Node pin is S0-T12. The numerals rule and the local `eii` rules are slice S3 and are not loaded yet.
- OPTIONS: **Recommendation:** keep. Alternative: typed linting after a second `tsconfig` covers tests and configuration files.
- NEEDED BY: slice S0 gate.

## OI-46 — Test tools, seeds and conventions of the test runner

- ID: OI-46
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of the test tools and of twelve conventions of `./eii test`, each a choice the pack permits and does not require: (1) the tools `pytest` 9.2.0, `hypothesis` 6.170.15 and `vitest` 5.1.0 at exact versions; (2) six suites, named `python-guards`, `python-core`, `python-custodian`, `python-product`, `web-checks`, `web-unit`, listed in one table in `scripts/run_tests.py`; (3) counts read from JUnit XML elements, from a small counting reporter for Node's runner and from the assertion results of Vitest's JSON file; (4) the default pytest selection `-m "not nightly"`, so that `postgres`, `live_model` and `sandbox` tests are selected; (5) a run fails when a suite reports no test, when any skipped or TODO test that the tool reports lacks a reason containing OI-01 or OI-10, when a pytest expected failure (`xfail`, which the JUnit file holds as a skipped item) lacks one, and when a tool's exit status disagrees with its counts; two Vitest forms are not exposed by its JSON reporter and so escape this rule, an `it.fails` or `test.fails` test whose body fails as expected (written as passed, with no marker) and a `describe.todo` without a body (omitted), and are left to review and lint, as is an unmarked OI-10 skip; (6) one seed per run, ten decimal digits from 1000000000 to 4294967295 (so that it never forms an exactly-eight or exactly-eleven digit run, which the identifier scan rejects), printed first, passed to pytest as `--hypothesis-seed`, to Python children as `PYTHONHASHSEED` and to Vitest as `--sequence.seed` with test shuffling on; a Hypothesis test with its own `derandomize=True` is the same in every run and is not changed by the seed (observed with 6.170.15); (7) every suite runs with `EII_DECISION_PROVIDER=none` and an allow-list environment from which any variable named `ANTHROPIC_API_KEY`, `JEV_PRO_API_KEY` or ending in `_KEY`, `_TOKEN` or `_SECRET` is absent, and no database variable is passed in this task (a task that gives `postgres` tests a database adds its names to the allow-list); (8) one Hypothesis profile `eii` restating the default example count (100) and deadline (200 ms), with no example database, and Hypothesis's own storage folder moved to a temporary folder; (9) pytest `strict = true`, `--import-mode=importlib` and `scripts/tests` on the pytest path, so that test modules which import a support module or a base test module of the same folder by name collect as they do under unittest; (10) the first version of `./eii test` runs neither a parity suite nor the preflight groups, and never exits 3; (11) a Vitest unit test needs no DOM library; (12) the limits of the runner, each chosen and not measured (the builder reports the real durations): time-outs of 3600 seconds for the guard suite, 1800 for the Node suite and 600 for each other suite; a minimum of one test for each suite; an output block of the last 200 lines with test names cut at 120 characters; no pytest cache and no bytecode written by children; result files written through each tool's own output option (`--junit-xml`, the counting reporter's destination, Vitest's `--outputFile.json`); a Python test that uses subtests counts once; a Node file that registers no test and a skipped Node `describe` each count as one skipped item; a Vitest file that fails without a failed test counts as one failed test; a module-level pytest skip counts as a skipped item and can never carry a standing reason; child output is decoded as UTF-8 with replacement; a time-out kills the child's process group, and an interrupt (Ctrl-C, KeyboardInterrupt) during a suite kills the child's process group, prints `FAIL interrupted` and makes `./eii test` exit 1; SIGTERM installs no handler, so the runner stops as the operating system stops it.
- WHY: The pack requires `./eii test` to run every pull-request-level suite that needs no network, print passed, failed and skipped counts per suite and exit non-zero on any failure or error (TST-15, docs/12 line 60), seeded randomness with the seed printed (TST-07, line 30), only two standing skips (TST-06, line 29), the markers `postgres`, `sandbox`, `nightly` and `live_model` (TST-16, line 61, itself an assumption), pytest for the packages (TST-10, line 72) and Vitest for the front end (TST-14, line 76), and says that pytest, Hypothesis, Vitest and Playwright are "Pinned at slice S0" with no retreat pin and no version number (docs/02 line 516) and that Hypothesis tests run in pull-request CI with a fixed seed passed as `--hypothesis-seed` (TST-27, line 91). It does not give the versions, the default marker selection, suite names, how counts are read, the form of a seed or how Vitest receives one. docs/13 line 207 says `./eii test` includes parity on both engines and runs the preflight groups Tools and PostgreSQL, and line 221 gives exit status 3 for a PostgreSQL that does not answer; the slice S0 gate (docs/14 line 207) asks only that `./eii test` exits zero.
- DONE SO FAR: `scripts/run_tests.py` with two helper modules, `conftest.py`, the `[tool.pytest]` table, `web/vitest.config.ts`, `web/scripts/count-reporter.mjs`, one package test per Python package and one Vitest test; the versions are the registry releases of 2026-10-27, 2026-11-06 and 2026-11-02, read on 2026-11-12, and the tools were run in a scratch project before the plan was finished. A secret in a variable with another name than the covered ones (the two names and three suffixes) is kept out only by the allow-list. A skip reason cannot be tied to a marker, so OI-10 on an unmarked test is accepted by the rule and left to the reviewer; Vitest's JSON gives no reason, so any skipped or TODO Vitest test that it reports fails; the two forms that it does not report (a failing `it.fails` or `test.fails` test, written as passed, and a `describe.todo` without a body, omitted) pass silently and are left to review and lint. `evals/` holds no test yet and `gateway/` no code; each later suite (boundary, parity, conformance, API, harness) adds a row to the table when it exists. The fixed seed that TST-27 asks of pull-request CI is passed by S0-T07 as `./eii test --seed N`.
- OPTIONS: **Recommendation:** keep. Alternatives: select `-m "not nightly and not postgres and not live_model"` and run those markers in separate suites; read Node counts from the TAP trailer (documented as unstable) instead of the reporter; allow a longer seed form.
- NEEDED BY: slice S0 gate.

## OI-47 — The `eii` launcher is created with one command

- ID: OI-47
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that task S0-T05 creates the root launcher `eii` with the single command `test`, and that task S0-T09 later adds the other eleven commands and replaces the usage text.
- WHY: TASKS.md gives task S0-T09 the scope "root `eii` launcher and `scripts/commands/`" (line 105) and the goal to create every pinned command entry point, while the goal of task S0-T05 is that `./eii test` runs the suites (line 75) and its scope is test configuration, test bootstrap files and the `scripts/` test runner (line 77). The pack does not say which task creates the launcher first. docs/13 lines 207 and 219 to 220 give the command and the exit codes 1 and 2 that the launcher uses.
- DONE SO FAR: `eii` is a short POSIX shell script. Any word other than `test`, or none, prints one line and exits 2; a missing `uv` prints one `FAIL` line and exits 1; otherwise it runs the runner through `uv run --locked` and passes the runner's exit status on. Its behaviour is tested by `scripts/tests/test_launcher.py`, whose tests name no word that a later task pins as a command and pin the usage text only by its prefix `eii: usage error:`, so that adding the other eleven commands does not require editing them. Task S0-T09 owns the usage text for all twelve commands and the test that lists them.
- OPTIONS: **Recommendation:** keep. Alternative: leave the launcher entirely to S0-T09 and run the runner as `uv run --locked python -I scripts/run_tests.py` until then.
- NEEDED BY: slice S0 gate.

## OI-48 — Component and browser test tools are not installed in slice S0

- ID: OI-48
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation that task S0-T05 installs only the tools that an existing test uses, and that Playwright with Chromium, axe-core, React Testing Library and a DOM environment for Vitest are installed and pinned with the first test that needs them.
- WHY: The pack names Vitest with React Testing Library, Playwright with Chromium and axe-core as test tools "pinned at slice S0" (docs/10 lines 569 and 634; docs/02 line 516 for Playwright), gives the unit, component, visual, end-to-end and audit suites to slice S3 (FE-92, docs/10 line 597) and requires `./eii test` to run suites that need no network (TST-15, docs/12 line 60). TASKS.md gives pins to task S0-T12 (lines 123 to 129). Playwright needs a browser downloaded by its own install command, which uses the network; the pack does not say how that is reconciled with TST-15.
- DONE SO FAR: Only `vitest` is installed (OI-46). Registry versions read on 2026-11-12 for the later decision: `@playwright/test` 1.65.0, `@axe-core/playwright` 4.14.0, `@testing-library/react` 16.3.3, `@testing-library/dom` 10.4.2, `jsdom` 31.0.0 (Node `^22.22.2` or later), `happy-dom` 21.0.4. The one unit test renders `App` with `react-dom/server`, which needs none of them.
- OPTIONS: **Recommendation:** keep; the first component test (slice S3) installs a DOM environment and Testing Library at exact versions, and the first end-to-end test installs Playwright and fetches its browser in a separate, documented, network step before `./eii test`. Alternative: install and pin all four now, unused.
- NEEDED BY: slice S0 gate (the pin record of S0-T12) and slice S3.

## OI-50 — Home and runner of the import-boundary test

- ID: OI-50
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that the import-boundary test is a set of standard-library `unittest`-style modules under `scripts/tests/`, run by the unittest command of rule 44 and collected by the suite `python-guards` of `./eii test`, and that it may be split into several modules around a 500-line target that the pack does not state.
- WHY: The pack requires the test from slice S0 and says it runs in `./eii test` and in continuous integration (docs/08_BACKEND.md line 67, BE-04). It lists `pytest` as the tool of the Boundary test class (docs/12_TESTING_AND_QUALITY.md line 45) and names no file or folder for the boundary test; TASKS.md line 112 says only "boundary test module". The `./eii test` command and its suite `python-guards`, which runs pytest over `scripts/tests`, are the work of task S0-T05 (TASKS.md line 74), which had merged before this item was entered.
- DONE SO FAR: The boundary test is a set of modules under `scripts/tests/`: four support modules `scripts/tests/import_boundary_*.py`, whose names do not match the discovery pattern `test_*.py`, and five test modules `scripts/tests/test_import_boundary_*.py`, which do. It is split around a target of about 500 lines per code file, which is house style and never a failure; the pack states no such limit, so this is an ASSUMPTION put to the owner. The test modules are `unittest.TestCase` classes and import no `pytest`; the suite `python-guards` collects them through the pytest configuration of S0-T05, and the unittest command of rule 44 runs them too. Proved by `test_tables_have_their_sizes` and `test_real_tree_static_passes` in `scripts/tests/test_import_boundary_real.py`, by the whole suite command of rule 44 and by `./eii test`.
- OPTIONS: **Recommendation:** keep. Alternatives: write the tests as plain `pytest` functions with fixtures, which would no longer run under the unittest command of rule 44; or join the nine files into one module if the owner prefers one module to a split made for a target the pack does not state.
- NEEDED BY: the owner, before the S0 gate.

## OI-51 — Dynamic imports that the boundary test cannot resolve

- ID: OI-51
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm that a call of `importlib.import_module` or `__import__` whose target cannot be resolved statically from literal arguments is reported as a note and does not fail the boundary test, and that the forms listed under DONE SO FAR are not judged.
- WHY: The pack requires failure for "string arguments to `importlib.import_module`" (docs/12_TESTING_AND_QUALITY.md line 180, TST-60; docs/08_BACKEND.md line 67, BE-04) and for "a module name passed as a string" (docs/02_ARCHITECTURE.md line 187, ARC-06). It says nothing about a name built at run time, and it does not enumerate the other ways a module can be loaded.
- DONE SO FAR: A call whose name is an absolute string literal fails when it names a forbidden module: for `import_module` also when `*args` or `**kwargs` follow the name; for `__import__` when the level is the literal integer 0, or is absent with no `*args` or `**kwargs` in the call. A call prints a `NOTE dynamic-import` line and never fails when the name is not a string literal (concatenation, f-string, variable, `*args`, `**kwargs`, no argument); when a relative name has no literal, non-empty package that `importlib.util.resolve_name` accepts; when `__import__` is given a name that starts with a dot; and when its level is not the literal integer 0 or cannot be read because `*args` or `**kwargs` could carry it. The direct and alias forms of `importlib.import_module`, `importlib.__import__` and `builtins.__import__` are judged. Not judged at all: a judged function reached by any other route (an assignment alias, `getattr`, an attribute of another module such as `pkgutil.importlib.import_module`, a `sys.modules` lookup, `importlib._bootstrap._gcd_import`, a lookup in `builtins.__dict__`, an alias of a module `__init__`); `exec`, `eval`, `compile`, `pkgutil.resolve_name` and assignment to `sys.modules`; loading code by file path (`importlib.util.spec_from_file_location`, `runpy`), `ctypes` and a Python subprocess; functions of other libraries that take a module name; function references such as `map(importlib.import_module, ...)`; a sourceless `.pyc` or an extension module, in a folder with or without `__init__.py` (the `.py` files of a folder without `__init__.py` are parsed); `.pyi` stubs; an environment name split across two literals. The fresh-interpreter test sees only what loads or requests a forbidden module while the packages are imported, and only the modules that `pkgutil.walk_packages` yields and what those import; a form inside a function that does not run at import time is seen by neither guard. `test_not_judged_forms_in_the_child` asserts the result for ten planted forms: `exec`, an assignment to `sys.modules`, `importlib.util.find_spec` (reported as an attempted import), `map(importlib.import_module, ...)` and a sourceless `.pyc` directly in a package are reported; `importlib.util.spec_from_file_location`, `runpy`, `ctypes`, a Python subprocess and a sourceless `.pyc` in a folder without `__init__.py` are reported by neither guard and are left to code review. The sandbox of task S0-T11 does not judge imports; it limits what generator code can read or open. For the other forms no committed test asserts what the fresh-interpreter test reports. Proved by `test_non_literal_dynamic_is_a_note`, `test_declared_not_judged_forms_pass`, `test_not_judged_forms_in_the_child` and `test_every_edge_every_mechanism` in `scripts/tests/test_import_boundary_forms.py`, and `test_fresh_every_edge_import_time` in `scripts/tests/test_import_boundary_fresh.py`.
- OPTIONS: **Recommendation:** keep, because a later slice may need a dynamic import inside its own package and failing it now would force the guard to be loosened. Alternative: fail every such call and allow named exceptions in a reviewed list.
- NEEDED BY: slice S0 gate.

## OI-52 — Environment names, the gateway edge and package metadata

- ID: OI-52
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm three narrow readings of the gateway rules in the boundary test, and to assign the vault requirements the boundary test leaves.
- WHY: The pack says nothing under `core/`, `custodian/` or `product/` imports `eii_gateway` or reads `EII_DECISION_PROVIDER` or `JEV_PRO_API_KEY` (docs/02_ARCHITECTURE.md line 462, ARC-81; docs/08_BACKEND.md line 70, BE-102; docs/15_REVIEWER_CHECKLIST.md line 76, REV-38). It does not say how "reads" is tested. The folder `gateway/` holds a note only (task S0-T01), so no package named `eii_gateway` exists yet. TST-60 asks for package metadata tests of "forbidden dependency" (docs/12_TESTING_AND_QUALITY.md line 180) without naming the gateway. BE-05 (docs/08_BACKEND.md line 68), SYN-68 (docs/05_SYNTHETIC_WORLD_AND_SIMULATION.md line 494) and PRV-02 (docs/06_PRIVACY_AND_DISCLOSURE_CONTROL.md line 53) name the import-boundary test or the vault path, and no task of TASKS.md names them.
- DONE SO FAR: (1) Only the three package trees `core/src/eii_core`, `custodian/src/eii_custodian` and `product/src/eii_product` are read; other files under `core/`, `custodian/` and `product/` are not. The two names must not occur at all in any file of those trees, matched as exact, case-sensitive text in the bytes of every file except the `.pyc` files directly inside a folder named `__pycache__`; this is stricter than "reads" because comments, strings and longer names that contain a name also fail, while a name split into two literals or written with an escape is not caught. (2) The gateway edge is judged by the module name `eii_gateway`, in the same three trees. (3) A dependency on the gateway in a `pyproject.toml` is not judged: the metadata guard of S0-T02 judges the three plane names only. (4) The vault clauses of BE-05, SYN-68 and PRV-02 are not tested, including the path segment `vault` in module names. Proved by `test_environment_names` in `scripts/tests/test_import_boundary_files.py`, `test_every_edge_every_mechanism` in `scripts/tests/test_import_boundary_forms.py`, `test_fresh_every_edge_import_time` in `scripts/tests/test_import_boundary_fresh.py` and `test_metadata_guard_is_wired` in `scripts/tests/test_import_boundary_real.py`.
- OPTIONS: **Recommendation:** keep; the gateway slice revisits the layout of `gateway/` and the metadata table. Alternatives: judge only reads of the process environment (a closed table of forms, weaker); add the gateway name to the metadata guard (a change to its reviewed table, re-checked by S0-T12). For point 4 the owner names the task that takes BE-05, SYN-68 and PRV-02.
- NEEDED BY: slice S0 gate.

## OI-53 — What the fresh-interpreter test judges

- ID: OI-53
- TYPE: ASSUMPTION
- NEEDED: The owner to confirm the scope and strictness of the fresh-interpreter test and of reading the working tree.
- WHY: The pack says to import `eii_product` in a fresh interpreter and fail if any `eii_custodian` module is loaded (docs/02_ARCHITECTURE.md line 187, ARC-06) and that fresh-interpreter tests assert no forbidden module is loaded (docs/12_TESTING_AND_QUALITY.md line 180, TST-60). ARC-06 names one fresh-interpreter case, importing `eii_product` and failing on any `eii_custodian` module; TST-60 says only "no forbidden module is loaded". Neither names the other packages, interpreter options or a way to find the packages. AGENTS.md rule 13 keeps "every folder that git ignores or does not track" off-limits for tests and allows only documented repository, cache and temporary paths.
- DONE SO FAR: Each of the three packages is imported in its own isolated child interpreter (`-I -S -B`, an environment built from an empty dictionary, the three working-tree source folders first on the path), together with every package and module under it that `pkgutil.walk_packages` yields and any module a walked module imports. It fails when a forbidden package (for `eii_product`: `eii_custodian` and `eii_gateway`) is loaded or only requested, or when any import fails. This is wider than the words of ARC-06. A symbolic link under a source tree, or in a folder above it, also fails. The child's path gets, after the source folders, the global package folders of the running interpreter (`site.getsitepackages()`), never the user folder, and a module that reads an environment variable when it is imported fails the test. The static guard reads every file under the three source trees as it is in the working tree, tracked or not, and the fresh-interpreter test imports (executes) the packages and modules it finds there, tracked or not; whether rule 13 allows this is put to the owner. Proved by the tests in `scripts/tests/test_import_boundary_fresh.py` and `scripts/tests/test_import_boundary_surroundings.py` whose names start `test_fresh_`, and by `test_symbolic_links_fail` in `scripts/tests/test_import_boundary_files.py`.
- OPTIONS: **Recommendation:** keep. Alternatives: test `eii_product` against `eii_custodian` only, as worded, and widen later; judge only the files that git lists (tracked, or untracked and not ignored) for the real tree.
- NEEDED BY: slice S0 gate.

## OI-54 — Pin record, version files and pins that no document gives

- ID: OI-54
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of the pin record, of the toolchain pins and of the versions taken from the registries; the slice S1 confirmation of every pin and retreat pin (S1-T08), which also writes the spike result.
- WHY: The pack pins Python 3.14 managed by `uv`, Node 22 (22.12 or later), React 19.3.1, Vite 8.3.x with 8.3.8, MapLibre GL JS 6.17.0, deck.gl 9.4.1, `pmtiles` 4.5.0, `@protomaps/basemaps` 5.7.2, `h3` and `h3-js` 4.5.0, `apache-arrow` 21.2.0, `pyvalhalla` 3.9.1, FastAPI 0.162.x, DuckDB 2.0.x, PostgreSQL 18 and PostGIS 3.6, and writes retreat pins for DuckDB, MapLibre, deck.gl and routing (docs/02 lines 499 to 516; docs/10 lines 54 to 66). It says exact pins are confirmed at the slice S1 spike (docs/02 line 495; docs/10 lines 50 and 86; rule 42) and also that they are "pinned in slice S0 and confirmed at the spike" (docs/13 line 65). It gives no number for `uv`, npm, TypeScript, pytest, Hypothesis, Vitest, Playwright, axe-core, React Testing Library, the Plex font packages, the OpenAPI generator, the SQL parser, the Anthropic SDK, psycopg, NumPy, SciPy or NetworkX, and names lock files and `web/package.json` as places where pins are recorded (docs/02 line 495; docs/10 line 50) but no single record of every pin with its retreat pin and label, and no format for the version list of the freeze bundle (docs/13 line 274). FE-03 (docs/10 line 86) asks for the retreat pin and the spike result that chose between them before slice S3 starts. PLN-15 (docs/14 line 39) asks for a re-estimate after the slice S1 spike.
- DONE SO FAR: `pins.toml` at the repository root records 57 components (4 toolchains, 15 Python, 32 npm, 6 external names): 27 values taken from the pack and labelled "pack, confirm at slice S1", 30 labelled ASSUMPTION with their source (the registry or the build machine, read on 2026-11-12, or the task that chose them). A retreat pin is written only where the pack names one, with one exception: for bubblewrap the pack names as its retreat "An equivalent mount-namespace and network-namespace sandbox enforcing the same mounts and passing the same sentinel tests, recorded as a decision; otherwise the build fails" (docs/02 line 514), and the record says "none recorded" for it because rule 12 of AGENTS.md says "No fallback is allowed for sandbox enforcement" (AGENTS.md rule 12 and the lead's ruling that bubblewrap is the only sandbox, put to the owner here); every other row for which the pack names no retreat pin says "none recorded". Libraries the product will use later are recorded and not installed. `.nvmrc` holds `22`, the root `pyproject.toml` gains `required-version = "==0.11.31"`, and `uv run --locked python scripts/check_versions.py` fails when a dependency named in a judged place of a manifest, a locked version of a recorded component, a version file, a version field, or the running Python, `uv`, Node or npm differs from the record, or when a manifest, lock or version file outside its closed set is among the files that git tracks or would track (the places it does not judge are in the docstring of `scripts/check_versions.py`), with a planted test for each of its seventeen rules. ASSUMPTIONS put to the owner: the file, its format and its place; `uv` at the exact version of the build machine, 0.11.31 (the newest release found on 2026-11-12 is 0.13.7; moving to it needs the three `uv_build` bounds of S0-T02, one in each member, changed in the same step); npm as the series 10.9.x that Node 22.22 bundles; the Node floor stays at the pack's 22.12.0 although the installed ESLint 10.14.0 declares `^22.13.0`, so Node 22.12 passes this check and is outside the engines that ESLint 10.14.0 declares (`^22.13.0`, read from the registry on 2026-11-12; a scratch run of ESLint 10.14.0 alone under Node 22.12.0 printed its findings and exited 1 for a finding and 0 for a clean file, and whether `npm run lint` fails there was not run); Node 22 reaches the end of its life on 2027-04-30 (the Node release schedule); the versions the pack does not give, taken from the registries; the label and `state` words; `psycopg` is LGPL-3.0-only by its registry entry, noted for the owner's licence review. A library for which the pack names no number and this task chose none (`uvicorn`, `pydantic`, `shapely`, `pyarrow`, `jsonschema`, `go-pmtiles`) has no row; a manifest that names one fails rule `manifest-unrecorded` until a task adds its row. DuckDB 2.0.x is recorded and not installed here; S0-T11, built after this task, adds it to a manifest and changes its row to installed. The check does not read which registry a lock names (the index URL of `uv.lock`, the `resolved` and `integrity` fields of the npm lock), so a changed index setting would pass; a `uv.toml`, an `.npmrc`, an `npm-shrinkwrap.json` or any manifest outside the closed set fails when git lists it. `required-version` is ignored by `uv` when `UV_NO_CONFIG=1` is set, as in the clean-environment tests of S0-T02, so the check reads the file itself. The documentation workflow still uses Python 3.12 (`.github/workflows/docs.yml`); TST-153 asks CI to use Python 3.14 managed by `uv` and Node 22, and S0-T07 writes the workflow that must install the pinned `uv`, read `.python-version` and `.nvmrc`, and run the check. This task cannot close FE-03 or PLN-15: FE-03 is a requirement labelled slice S1 (docs/10 line 86), whose spike result only S1-T08 can write, and this task provides a retreat value for every row and the place `spike_result`, left as "not yet run"; PLN-15 is an effort re-estimate rule for after the slice S1 spike (docs/14 line 39), and this task changes no effort figure. Node is pinned as the series 22.x with the floor 22.12.0 (the pack's own series); the exact Node pin that OI-45 leaves to this task is therefore this series, and the floor question is the option below. Rule `unscanned` takes its candidate files from `git ls-files -z --cached --others --exclude-standard`, run in the repository root with the user's and the system's git configuration switched off, that is the files git tracks and the untracked files that no `.gitignore` file or `.git/info/exclude` line of the repository ignores; a file that git ignores and does not track is never listed or judged (AGENTS.md rule 13), no folder is walked, and the check needs `git` on the path and the root to be the top of a work tree.
- OPTIONS: **Recommendation:** keep the record and the `uv` pin as they are. Option for the Node floor: raise it to 22.13.0, the lower bound that the installed ESLint 10.14.0 declares, by exactly two edits: the `floor` field of the `node` row of `pins.toml` becomes `22.13.0`, and `engines.node` of `web/package.json` becomes `>=22.13.0 <23`; nothing else changes, because the check derives the expected string from the row. Alternatives: keep the pack's floor 22.12.0; pin `uv` 0.13.7 and change the three `uv_build` bounds in the same step.
- NEEDED BY: the Node floor and `uv` choices before S0-T07 writes the workflow; the rest at the slice S1 spike (S1-T08).

## OI-55 — SQL parser for the portability lint

- ID: OI-55
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of `sqlglot` 30.31.0 as the parser of the portability lint, or another choice.
- WHY: TST-43 (docs/12 line 125) says the parser is "chosen in slice S0"; BE-13 (docs/08 line 146) says "parser chosen at slice S0; a tokeniser over the allow-list is the fallback"; no parser is named. The lint must read queries for PostgreSQL 18 and DuckDB 2.0 that use the neutral placeholder `:name` and must reject extension functions and forbidden constructs (docs/08 lines 140 and 153).
- DONE SO FAR: Registry facts and runs of 2026-11-12 on Python 3.14.6. `sqlglot` 30.31.0 (MIT, pure Python, no run-time dependency) parsed PostgreSQL-with-PostGIS and DuckDB samples to a syntax tree with the placeholder, kept function names, ignored function names in comments and strings, and flagged `WITH RECURSIVE` and several statements; it is lenient across dialects (it accepted `QUALIFY` when reading as PostgreSQL), so the allow-list has to be applied to the tree and each query parsed under both dialects. `sqlparse` 0.6.1 (BSD) is a tokeniser that accepts invalid SQL. `pglast` 8.7 reads PostgreSQL only, is GPL-3.0-or-later and needs the placeholder rewritten. `sqloxide` 0.61.1 (MIT, compiled) is also lenient. DuckDB's own serialiser reads one engine and SELECT statements only. `sqlglot` is recorded in `pins.toml` as an ASSUMPTION, state recorded, first use S3-T01; it is not installed. The owner decided the method on 2026-11-11 and the lead assigned the requirement to this task.
- OPTIONS: **Recommendation:** `sqlglot`, exactly pinned, each query parsed under both dialects and both required to succeed. Alternatives: `pglast` with DuckDB's parser (authoritative for each engine; a GPL licence and a rewrite of the placeholder); the pack's fallback, a tokeniser over the allow-list (no dependency, no syntax tree).
- NEEDED BY: slice S3 (S3-T01).

## OI-56 — Generator of TypeScript types from the OpenAPI schema

- ID: OI-56
- TYPE: ASSUMPTION
- NEEDED: Owner confirmation of `@hey-api/openapi-ts` 0.99.0, or another choice, and of the Node floor it implies.
- WHY: docs/10 line 122 says types for API payloads are generated from the FastAPI OpenAPI schema into `src/api/generated/`, that CI fails when the file differs from a fresh generation, and that "the generator is chosen and pinned at slice S0" (assumption 1, line 627); no generator is named.
- DONE SO FAR: Run on 2026-11-12 with TypeScript 6.0.3 on a schema produced by FastAPI 0.162.4 (an enum, a literal, an optional number, a list with a default, a nested model). `@hey-api/openapi-ts` 0.99.0 installs beside TypeScript 6.0.3 with no extra manifest key, writes types only with the `@hey-api/typescript` plugin, gives the same output twice, has no suppression comment and passes `tsc` in strict mode; it declares Node 22.18 or later (above the pack's 22.12), is below version 1, and its output holds a `ClientOptions` type whose template text contains the input file name. `openapi-typescript` 7.13.0 declares the peer `typescript ^5.x`, so beside TypeScript 6.0.3 it installs only with a root `overrides` entry (which the FE-01 check of S0-T03 reads, so the value must be the exact `6.0.3`), and its newest 7.x release is dated 2026-02-11; its output is otherwise clean. `swagger-typescript-api` 13.14.0 writes `eslint-disable` and `@ts-nocheck` lines at the top of its output, which the rules of S0-T04 (no suppression comment) forbid. `@hey-api/openapi-ts` is recorded as an ASSUMPTION, state recorded; it is not installed. Whichever generator is adopted, its output must pass `npm run lint` and `npm run format:check` of S0-T04 or the owner approves how it is excluded. The owner decided the method on 2026-11-11 and the lead assigned the requirement to this task.
- OPTIONS: **Recommendation:** `@hey-api/openapi-ts` 0.99.0, with the types plugin only, and raise the Node floor together with the decision in OI-54 (22.18.0 would cover this generator). Alternative: `openapi-typescript` 7.13.0 with the exact override.
- NEEDED BY: slice S3 (the API slice).

## OI-57 — Package family for the IBM Plex interface fonts

- ID: OI-57
- TYPE: ASSUMPTION
- NEEDED: Owner choice between the Fontsource packages and the IBM-published packages for IBM Plex Sans and IBM Plex Sans Arabic.
- WHY: docs/10 line 64 says the fonts are "pinned at slice S0" and line 463 says they are self-hosted as WOFF2 from "the pinned npm packages"; no package name or version is given. docs/10 line 431 says telemetry of any kind is absent from the page at run time.
- DONE SO FAR: Registry facts of 2026-11-11 and 2026-11-12. `@fontsource/ibm-plex-sans` and `@fontsource/ibm-plex-sans-arabic` 5.3.0 (OFL-1.1, a repackaging, no dependency, no install script, WOFF2 and WOFF files) are recorded as ASSUMPTION rows, state recorded; they are not installed. `@ibm/plex-sans` and `@ibm/plex-sans-arabic` 1.1.0 (OFL-1.1, from the typeface's own repository) depend on IBM's telemetry package and run a `postinstall` script that starts a collector at install time; its README gives an environment variable as the opt-out. That is an install-time matter, not the run-time page that line 431 describes, and the pack does not address it. Vendoring the files with the licence text is slice S3 (FE-97, OI-43); the weight confirmation is S0-T13.
- OPTIONS: **Recommendation:** the Fontsource packages. Alternative: the IBM packages installed with install scripts switched off and the opt-out variable set, which the pack does not mention.
- NEEDED BY: slice S3 (FE-97).

## Change control

Close an item only with evidence and the named decision or test that resolves it. Record the closure in [PROGRESS.md](PROGRESS.md), preserve the earlier entry, and add a decision record for any material change. Do not silently delete an unresolved item.

## Proposed open items from reviews

Each item below was proposed by an independent reviewer outside the verdict ([REV-41](docs/15_REVIEWER_CHECKLIST.md)). The follow-up task of its slice closes it before the slice gate, by a fix or by one line saying why it is not valid or is out of scope under REV-42 ([decision 0015](docs/decisions/0015-review-rounds-and-the-scope-of-repository-checks.md)).

### PO-S0-01 — Count list of the S0-T02 plan against the delivered sub-cases

- ID: PO-S0-01
- TYPE: OPEN
- RAISED BY: independent review round 1 of S0-T02 (Zhipu AI GLM-5.3 High), 2026-11-12, proposed item P1
- CONCERNS: REV-16 (the work follows the plan)
- EVIDENCE: `test_member_list_wrong_fails` runs 8 sub-cases where the plan's count list says 7, `test_missing_and_unparsable_lock_fail` counts 4 where it says 3, `test_lock_ignores_self_and_third_party_edges` runs three blocks with no count assertion where it says 2, and `test_output_order` asserts no count where it says 3; the ledger says only that sub-cases were added. The plan is a project record held by the owner, not in this repository.
- NEEDED: the plan record states the delivered sub-cases and counts, or the additions are annotated.
- CLOSED BY: S0-T15

### PO-S0-02 — Suppression comments ahead of the checks of S0-T04

- ID: PO-S0-02
- TYPE: OPEN
- RAISED BY: independent review round 1 of S0-T02 (Zhipu AI GLM-5.3 High), 2026-11-12, proposed item P2
- CONCERNS: REV-15 (no check weakened)
- EVIDENCE: `scripts/tests/workspace_fields.py` carries `# noqa: E402` for the bottom import that the split into two modules needs, and `scripts/tests/test_workspace_metadata.py` carries several `# type: ignore[...]` comments; no check that runs today is weakened.
- NEEDED: S0-T04 confirms that its ruff selection accepts that import without the suppression and that each type-ignore marker matches its type checker, or removes them.
- CLOSED BY: S0-T15

## Sources

- The master open-item decisions and defaults reflected in [01_PROJECT_BRIEF.md](docs/01_PROJECT_BRIEF.md), [09_AI_ASSISTANT.md](docs/09_AI_ASSISTANT.md) and [decision 0014](docs/decisions/0014-typed-decision-gateway.md).
- Additional open questions and assumptions recorded in documents 01 to 16 and the decision records indexed in [docs/README.md](docs/README.md).
