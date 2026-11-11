# Open items

| | |
|---|---|
| Status | Draft v0.2, corrected after independent review on 2026-11-11 (see PROGRESS.md) |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Track every unresolved owner decision, assumption, pending correction and technical unknown without implying closure. |
| Read first | [docs/README.md](docs/README.md), [PROGRESS.md](PROGRESS.md) |

## In brief

- OPEN means a decision, source or proof is still needed.
- ASSUMPTION means work may use the stated default, but the named owner must confirm or replace it.
- PENDING means review or correction work has not yet supplied evidence.
- The recommendation is the safe default, not a new decision. A material change needs a decision record.
- Items OI-01 to OI-18 carry the master decisions; OI-19 onwards come from the written pack.
- OI-36 to OI-38 record what the review of 2026-11-11 left open: an objection of two reviewers that was not accepted for version 1, and two sets of last corrections that another maker has not yet read.
- OI-35 records which parameter set is exported. A lead ruling of 2026-11-11 sets the default to A; the owner or a data owner may overrule it before the slice S1 gate.

## OI-01 — Main model key and spend cap

- ID: OI-01
- TYPE: OPEN
- NEEDED: The owner to supply the main model key and set daily and total spend caps.
- WHY: Live-model evaluation and operation cannot be claimed until the key and cost limits exist.
- DONE SO FAR: The template writer and recorded provider are the default; live gates remain open.
- OPTIONS: **Recommendation:** keep template/recorded mode until the owner supplies both. Alternative: enable the live adapter only within the approved caps.
- NEEDED BY: slice S8 live-model gates; slice S11 stage decision.

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
- TYPE: OPEN
- NEEDED: Written licence confirmation for the statistics authority's census map layers and associated boundary use.
- WHY: Redistribution and display rights are not stated.
- DONE SO FAR: A source with no stated licence is validation-only until its terms are recorded. No value, derived share, title or geometry from it enters a release. The coverage bar uses the finest licensed geography available (zone, otherwise municipality, otherwise national) and names it.
- OPTIONS: **Recommendation:** obtain and record written confirmation; until then keep the source validation-only and use the finest separately licensed geography for coverage and boundary geometry.
- NEEDED BY: slice S2 public frame and coverage data.

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
- TYPE: OPEN
- NEEDED: Owner decision on whether later item L8 may include a clearly fictional list of firms.
- WHY: A synthetic prospect list can read as a real recommendation and reopens the firm channel.
- DONE SO FAR: No prospect list is in version 1; firm and owner networks are dropped.
- OPTIONS: **Recommendation:** keep it excluded. Any later list needs an owner-approved decision and a fresh privacy and wording review.
- NEEDED BY: After slice S11, backlog item L8.

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
- TYPE: OPEN
- NEEDED: Data owners to set real privacy thresholds before any real-data pilot.
- WHY: Sets A and B are proposals measured only on synthetic data, not approved production rules.
- DONE SO FAR: Both parameter sets, stable treatment and attack requirements are specified. Both are evaluated inside the custodian plane, but exactly one selected set's protected tables are exported in a release. A lead ruling of 2026-11-11 accepts the rewritten privacy document as the disclosure-control reference. A lead ruling of 2026-11-11 sets the demonstrator default `export_parameter_set` to `A` (open item OI-35). A lead ruling of 2026-11-11 defines `window_key` as the SHA-256 of canonical JSON holding the protected `period` and the four name-ordered `{name, sha256}` pairs for `business_register.v1`, `employment.v1`, `residence.v1` and `wages.v1`, using each feed's manifest `feed_sha256`; nothing else enters it. Continuous integration checks the register alone and allows one `protected_sha256` per `window_key` and one `window_key` per `world_seed`; for a frozen release, the installed application's register is the allow-list and `freeze.json` must say complete. No signed receipt file is added. A lead ruling of 2026-11-11 limits exact sums to one additive family. Real thresholds remain for data owners, so this item stays open.
- OPTIONS: **Recommendation:** retain both for custodian-plane evaluation and export only the selected set for the demonstrator; custodians supply and hold real values for a pilot. Never tune a rule to make an area look finer.
- NEEDED BY: slice S5; any real-data pilot.

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
- NEEDED: Owner confirmation of the project token cap and a key rotation date.
- WHY: Offline provider use still needs a hard cost limit and credential hygiene.
- DONE SO FAR: Default cap is 5 million tokens in total; no agent may purchase, upgrade or renew.
- OPTIONS: **Recommendation:** confirm or tighten the default and record rotation before provider use; agents never change the subscription.
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
- DONE SO FAR: A lead ruling of 2026-11-11 decides the acceptance model: one model, every published leaf fixed to its untreated aggregate, knowledge fixtures checked against sealed truth before use, published-means-passed constraints, one solve per target class, and a time budget set from a measured run at the start of slice S5. What the layout tells about a failed population is not in that model; the typed attack suite holds one attack per layout signal. The audit is evidence under a stated attacker, not a proof. A lead ruling of 2026-11-11 pins `artefacts/attacker_view_public_totals.json` (PRV-115), and the audit configuration is `artefacts/attacker_view_audit.json`. A lead ruling of 2026-11-11 closes the count indicators that may be enabled: `residents` (`persons`), `households` (`households`), `establishments` (`establishments`) and `employees` (`persons`). A lead ruling of 2026-11-11 requires the inventory to equal the source registry plus every Public-table row. Which of those rows a release marks enabled is still selected at slice S5. Cross-period complement fixtures and mover attacks are part of backlog item L4. Whether an independent human attacker session precedes a real-data pilot is still open.
- OPTIONS: **Recommendation:** derive the list from the reviewed public registry in slice S5 and require an independent human attack before any real-data pilot.
- NEEDED BY: slice S5; real-data pilot gate.

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
- TYPE: OPEN
- NEEDED: The custodian to confirm its database platform, approved region, data-residency terms and operating environment.
- WHY: Public provider offerings do not prove what a custodian runs or permits.
- DONE SO FAR: Available managed offerings were researched; no fit is claimed.
- OPTIONS: **Recommendation:** make no deployment-fit statement until written custodian confirmation; keep the build plane inside that environment.
- NEEDED BY: Later deployment only, not the local version 1 demonstrator.

## OI-27 — Company-seat notice and decision scope

- ID: OI-27
- TYPE: ASSUMPTION
- NEEDED: Owner approval of the company-seat recording notice and confirmation that cross-country entry comparison and serving the region stay outside the current backlog.
- WHY: The project brief classifies these points without a master owner decision.
- DONE SO FAR: Draft wording discloses aggregate oversight recording; those two wider decisions are currently outside version 1 and the ordered backlog.
- OPTIONS: **Recommendation:** keep the disclosure and limited scope unless the owner adds work by decision record.
- NEEDED BY: slice S3 company interface; backlog review after slice S11.

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
- NEEDED BY: slice S8 live-model tuning; any later provider change.

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
- DONE SO FAR: A lead ruling of 2026-11-11 sets the default `export_parameter_set` to `A`, fixed in the rules configuration at the slice S1 gate, before any world is built, together with `presence_scale` and `flow_scale` (PRV-59). A lead ruling of 2026-11-11 writes that fix into the slice S1 gate. A lead ruling of 2026-11-11 defines `window_key` as the SHA-256 of canonical JSON holding the protected `period` and the four name-ordered `{name, sha256}` pairs for `business_register.v1`, `employment.v1`, `residence.v1` and `wages.v1`, using each feed's manifest `feed_sha256`; nothing else enters it. The register shipped inside an installed application is the allow-list for a frozen release, and `freeze.json` must say complete. The owner or a data owner may overrule the default set.
- OPTIONS: **Recommendation:** export set A unless the owner or a data owner records another choice before the slice S1 gate. Do not export a second treatment of the same window.
- NEEDED BY: the slice S1 gate, before the first world build.

## OI-36 — Layout signals outside the audit acceptance model

- ID: OI-36
- TYPE: OPEN
- NEEDED: Before any real-data pilot, either model the disclosure-control failure branches, with predicates that separate what a rule publishes by design from what it leaks, or run an attack against every released instance of each layout signal.
- WHY: Layout signals are outside the acceptance model of the audit. Two independent reviewers object that one typed attack per kind of signal can miss a disclosure at another instance.
- DONE SO FAR: A lead ruling of 2026-11-11 keeps layout signals outside the acceptance model for version 1 (section 17 of the privacy document). The limit is stated, and the typed attack suite covers at least one merged band, category pooled into `other`, merged sibling set, withheld remainder and released reason code.
- OPTIONS: **Recommendation:** retain that ruling for the synthetic demonstration and state the limit. Before a real-data pilot, choose and complete one of the two needed routes; do not call the current audit a general proof.
- NEEDED BY: Before any real-data pilot.

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

## Change control

Close an item only with evidence and the named decision or test that resolves it. Record the closure in [PROGRESS.md](PROGRESS.md), preserve the earlier entry, and add a decision record for any material change. Do not silently delete an unresolved item.

## Sources

- The master open-item decisions and defaults reflected in [01_PROJECT_BRIEF.md](docs/01_PROJECT_BRIEF.md), [09_AI_ASSISTANT.md](docs/09_AI_ASSISTANT.md) and [decision 0014](docs/decisions/0014-typed-decision-gateway.md).
- Additional open questions and assumptions recorded in documents 01 to 16 and the decision records indexed in [docs/README.md](docs/README.md).
