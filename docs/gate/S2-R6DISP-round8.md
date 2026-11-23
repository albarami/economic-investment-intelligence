# S2-R8D — Round-8 gate records before L6

Date: 2026-11-23. Inspected head: `6d5466e3bb`. Builder: OpenAI Codex,
meticulous gate-records engineer. Strict self-review persona: an auditor rejecting
unsupported closures and unproved live results. Different-maker records review
remains with the lead; this document supplies no such verdict or slice-gate pass.

## Scope and sources

This refresh covers every table item and the separate unowned row of the supplied
`.overnight/IN/S2-R6DISP.r1.return.md`. It is not a census of every S2 open item.
The supplied `.overnight/IN/S2-PATH.md`, table 1 rows 24, 30–34, 39, 40 and 53,
table 3 U8b and **Shortest ordered sequence to gate record round 8**, item 9,
define this records task. `.overnight/IN/S2-GATE-CHECKLIST.md` retains its
preconditions and the moved-box check. Those supplied inputs are lead working
papers, not new committed evidence. No earlier evidence row is replaced.

Repository authorities are TASKS.md S2-T10/S2-T13/S2-T19; OPEN_ITEMS.md's named
items and **Slice S2 gate record — round 6 dispositions** / **round 7 dispositions**;
PROGRESS.md **S2-GATE-R6**, **Train S2-19 records**, **Train S2-20 round 4 records**
and **Train S2-21 records**; and decisions 0079, 0084, 0085 and 0098.
The acceptance/access-disposition update is recorded in OPEN_ITEMS.md and
PROGRESS.md **S2 records change — owner acceptance of decisions 0091, 0095 and
0102**, committed as `fa669eedf1`, corrected by `6d5466e3bb`.

State words: CLOSED discharges only the obligation explicitly named in its row;
OPEN names the accountable owner and next deciding evidence; CARRIED remains
pending under the cited decision item, with its consumer/start check. A merged
mechanism, accepted decision or later green run supplies no missing historical
run or real-source proof. All commit references below are ten-character hashes
found in `git log HEAD`; task-original identities quoted by historical ledgers
are not substituted for their containing commits.

L6 means the lead's main gate public build in S2-PATH table 2. L7 is the lead's
real-cache data tests, L8 the award replay/live proof, L9 the different-maker
twenty-figure review-file step, L11 the whole test and L12 the records checks.
This worker runs none of the live/cache steps and reads no `data/`.

## Legacy imagery selection — U8b

S2-T19#5 is ticked for a legitimate empty legacy selection, `views: []`, in
`custodian/publicdata/review/gis_imagery_views.yaml`. Decision 0079 item 1 assigns
the dated national snapshots to S2-T51; item 2 requires its separate closed
acquisition; item 3 excludes background acquisition/completion from earlier
gates; item 4 requires explicitly selected verified all-date release artifacts.
The existing S2-T19 decision-0079 amendment records the free choice of dates
and unchanged guards for unselected legacy fixed views. This does not assert
that S2-T51 has fetched or integrated imagery.

The unchanged `custodian/tests/test_gis_imagery_views.py` contains
`test_export_for_a_key_off_the_list_is_refused` and
`test_empty_committed_list_builds_no_request`, each asserting the specific
`view_absent` refusal. `test_invented_list_exports_before_and_after` checks both
closed export parameter lists, including `bboxSR` and `imageSR` 3857.
`custodian/src/eii_custodian/publicdata/gis/imagery_views.py::export_request`
checks the projection, service and side and refuses an absent view before
constructing a request. The tests are on this head through `2c0b9a528d`;
decision 0079 and the existing task amendment are in that train too. This round
inspects their text; it does not claim a new execution of those pytest tests.
The single replacement YAML comment preserves the historically asserted
no-service-path wording, identifies it as history, and cites items 1–4 separately.

## Tender confirmations and C-09

S2-T13#5 is ticked as a records-only confirmation. The committed
`custodian/publicdata/review/s2_t13_confirmation.yaml`, **tender**, records the
visitor-readable `tenders_pub` source, dated terms/page identities, the terms
reading and decision-0026 owner basis; **weight** confirms area apportioning,
`grid_admitted: false` and `agesex_is_weight: false`. Both blocks are present
at `5b240c8172`; the area-weight criteria already stand ticked under S2-T13.
The tender block's `terms_do_not_cover` records the terms reading, and `shown`
records the visitor-source policy; neither field proves a tender table exists.
Decision 0084 item 2 and decision 0085 items 7 and 9 supply the separate
technical-pending disposition, never a terms-based absence.

S2-T13#11 stays OPEN. Decision 0085 item 9 (`6f40a51abb`) supplies C-09's
wording, not the actual selected L6 assembly evidence. The unchanged
`gate_report.py::tender_evidence` and `confirm_s2_t13.py::own_run_pending`
implement the pending branch (`5b240c8172`); no K5 assembly record, verified
intake identity/cut-off or final-head binding is supplied to this task.
OI-378 also still requires the lead's application of the working-paper wording.

Draft C-09 line to complete after L6: **tenders_pub — NO_DATA, reason
own_run_pending, caveat tender_fetch_own_run; no pub_tender, tender layer or
source-table edge; technical absence while the own run is pending, never the
terms. Bind the actual L6 command/head/seed, assembly record, verified workbook
hash and cut-off here.** This is an unexecuted draft, not an observed outcome.
If L6 instead verifies a selected own-run archive, record its original date/hash
and both awarded-language readings' cut-off/page/continuity evidence under
decision 0084 items 3–6. OI-370's start-day and pre-freeze checks remain owed.

## Refreshed R6DISP rows

| ID | State | Evidence / accountable owner and deciding step |
|---|---|---|
| OI-03 | OPEN (records follow-up only) | Sign-off itself is CLOSED by OPEN_ITEMS.md **OI-03**, decision 0025 and `2c0b9a528d`. Gate lead still appends the winning closure pointer to `custodian/publicdata/review/reconciliation_oi03.md` and supersedes the stale hold; that file still says open. L6 must separately verify the bound local sign-off. No new sign-off is requested. |
| OI-235 | OPEN | S2-T08 data lead executes and records all required complete draws, seeds and review IDs; different-maker reviewer checks the actual twenty-figure draw with zero mismatches. Waits on L6, reviewer comparison and L9; ordinary build success is insufficient. |
| OI-358 | CARRIED | Decision 0098 items 3–4 and **Box carry ledger**, S2-T48's exact moved boxes: company-web field-review/acquisition seat and independent reviewer after final go-live retain E1–E7, original cf1 finding disposition, path/byte identity, W/B guards and actual counts. Existing S2 security/default controls and unresolved validator obligations remain path under items 6, 8 and 9; no successful live search or blanket security exemption. |
| OI-359 | OPEN | Access disposition is now recorded in OPEN_ITEMS.md **S2 records change**, L-1581 (`fa669eedf1`, corrected `6d5466e3bb`): approved paced named-dataset API access. Lead still supplies attributable receipts for the five named portal rows at L6; no export/fetchability is proved by the disposition. |
| OI-286 | OPEN | Gate lead appends PR 89's actual hosted merge-check evidence, both then-required custodian parts with run IDs/conclusions. Keep the fixed ZipInfo dates/clock plant. Later tests cannot replace that historical record. |
| OI-323 | OPEN | Gate lead supplies PR 103's six hosted checks and fresh-seed exact-result command/head/seed/exit/counts under **MERGE TRAIN S2-6**; otherwise lead/owner records the required missing-evidence ruling. L11 does not recreate PR 103 evidence. |
| PO-S2-128 | OPEN | Gate lead and original runner append the PR 104 exact merge-result row and six hosted conclusions under **MERGE TRAIN S2-7**, retaining the requested seed and runner from OPEN_ITEMS.md's audit reopening. A moved-head run is not that record. |
| PO-S2-22 | OPEN | S2-T44 web/performance owner replays emptied `send` and proves both named clients end with response timeout before the command limit, or supplies the specified lifecycle case / killed-mutant record; another-maker review follows. This guard proof is not carried merely because a performance measurement moved. |
| PO-S2-36 | OPEN | S2-T15 data/security lead and OI-197/OI-202 live-fetch lead read the actual places column order at L6, or append the permitted post-fetch refusal disposition. Offline hand-encoded orders do not decide it. |
| PO-S2-81 | OPEN | Gate lead records the NOT VALID ruling's ID/date/exact words and another maker confirms it, or audit-tool owner supplies separate summary/detail outputs with a planted collision refusal at first reuse. No such ruling is invented here. |
| OI-362 | OPEN | Lead live-build/process owner identifies the waiting step and cause using unbuffered diagnostics and working-directory process inspection. L6 must retain those diagnostics; a green result alone does not close the earlier hang. |
| OI-363 | OPEN | Web fake-server test owner and lead establish port isolation or causally identify the colliding process. An isolated green run is insufficient under rule 39; evidence is needed for final-ledger reliability. |
| OI-366 | OPEN | Clean-environment test owner and lead decide disk-backed copy placement or a named space preflight/refusal. Until reviewed, each dependent ledger records disk-backed TMPDIR and environment; a green L11 alone does not close it. |
| PO-S2-T51-06 | OPEN | Lead engine/environment investigator reproduces the named invented-road engine failure under controlled temporary roots, establishes the baseline/working-tree difference and routes any fix to the places-area engine owner. Decision 0079's acquisition exception does not dispose of this independent engine failure. |
| OI-372 | OPEN | Gate lead and different-maker records reviewer complete the decision-0086 amendment inventory/index/S2-T34 pointer and append-only OI-285 attribution correction. Later decision 0101's limits do not supply those historical record corrections. |
| OI-377 | OPEN | Gate lead verifies **S2-P39** / **Append-only record inputs** in PROGRESS.md against OI-377's requested full original/pick identity, tracked deciders and attributed code-practice figures, then obtains records confirmation. Existing partial mappings/figures are acknowledged; no full closure is inferred. |
| OI-382 | OPEN | Gate lead and different-maker records reviewer reconcile **S2-TSKIP** / **Append-only record inputs** with the complete initial/final original/pick identities and rv1/cf1 rejection versus cf2 approval. Existing abbreviated mappings are not silently promoted to the requested complete identity proof. |
| OI-378 | OPEN | Lead working-paper owner applies decision 0085 items 4, 5 and 9 to the actual C-P4/C-P5/C-09 papers and records application before gate use. The committed wording and this C-09 draft do not prove that action occurred. |
| OI-379 | OPEN | Lead records the command/head/seed/exit/counts and outcome of the already-running measurement round, resolving decision 0085 item 2's condition before relying on the S2-T44#1 move. No new round is requested. |
| OI-277 / S2-T29 | OPEN | Decisions 0091/0095 are now Accepted with recorded acceptance review (`fa669eedf1`, corrected `6d5466e3bb`); S2-P46 is merged `e7edf54613`, S2-P66 `ac06afc77d`. Lead/S2-T29 data-security owner still supplies P66 different-maker approval and L6/L8 real-cache replay/live proof: once per distinct link, refusals/zero-match outcomes, registration matching, measured rates and double-space count. |
| OI-360 | CARRIED | Decision 0085 item 3 and decision 0084 item 6: tenders own-run lead retains bounded unbuffered liveness evidence and establishes cause/remedy for each terminated run/replacement seed before S7-T09's start check. Green alone never closes it. |
| OI-370 | CARRIED | Decision 0084 items 1, 4 and 6, retained by decision 0098 item 4's tender lane: tenders lead and independent binding reviewer prove original archive/visible-text terms hashes, verified handoff, same pin and latest successful in-use pub_tender assembly on S7-T09 start day and pre-freeze. Its prior same-day-index/checks wording also remains owed under PO-S2-P40; no live archive is inferred. |
| OI-386 | OPEN (later-slice observation) | S5-T05/process-identity owner and lead diagnose the concurrent-load process_identity_mismatch in the two scripts tests before the next ledger depending on them. OPEN_ITEMS.md **OI-386** requires causal evidence, not function/module-root enumeration. It is not a new S2 blocker or an authorised closed item. |
| S2-T46 older awards | CARRIED | Decision 0070 item E: S2-T46 data lead performs the one-time older-awarded-pages enrichment after the S2 gate, before S7-T35 consumes it, with original receipts/coverage/matches/conflicts and review. No synthetic substitute or register-wide award-rate claim. |
| OI-131 | CLOSED (declaration/test/review only) | `0b3e59d304` merges S2-P49's `test_s2_t10_split_contract.py::test_registry_splits_match_the_recorded_columns`; OPEN_ITEMS.md **round 6 dispositions**, F4/S4, and PROGRESS.md **S2-GATE-R6**, C-21, record different-maker APPROVED and the specific declaration plants (`154333b523`). This corrects R6DISP's unrelated decision-0035/test_release_reports rationale. L6/final-head Public-split evidence remains separate. |
| OI-365 / PO-S2-REC1-2 | CLOSED (wording/guard only) | `154333b523` contains OPEN_ITEMS.md **round 7 dispositions**, F5: Zhipu GLM-5.3 S2-gate.r6rv APPROVED, wording EXACT, lead value-free scan exit 0 and new-copy plant exit 1, with TASKS.md S2-T35#2 ticked. R6DISP's Moonshot attribution is superseded by that repository record. No census value is repeated here. |
| OI-103 keyless reopening / PO-S2-REC1-1 | CLOSED (offline reopening only) | `6f40a51abb` contains `test_night_lights.py::test_night_absent_key_build_succeeds`; OPEN_ITEMS.md **round 6 dispositions** and PROGRESS.md **S2-T14 — sixth acceptance item, absent Earthdata key** (`154333b523`) record Cognition S2-T14.krv1 APPROVED, successful Production fetch-stage omission and three plants. Keyed acquisition/C-12 stay for L6. |
| OI-375 | OPEN (nonblocking next edit) | S2-T14 test owner retains OPEN_ITEMS.md **OI-375**'s directory-nonexistence observation and assembly-seam documentation observation for the next test edit. The supplied disposition's additional proposals do not replace that original obligation or reopen the accepted no-key test. |
| S2-T24#7 / S2-T25#8 | CLOSED (two existing ticks only) | `7ef9dc96c7` contains P35's reading/configuration changes; PROGRESS.md **S2-GATE-R6**, F6 (`154333b523`), records S2-TICKS-RV1 TICK for these two despite the overall candidate rejection, and S2-P35.cf1 CONFIRMED. TASKS.md retains those ticks; both whole tasks and dated acquisition remain open for L6. |
| PO-S2-48 | CLOSED (C8 producer/replay obligation) | Producer `c4e8660427`, accepted decision 0089, and OPEN_ITEMS.md **round 7 dispositions** / PROGRESS.md's recorded ten-pass real-cache C1/C8 replay are on head through `154333b523`. This dated row retains R6DISP's scoped closure and supersedes its stale gate-hold status; L6/L7 final-gate data proof and PO-S2-51/52 remain separate. |
| PO-S2-51 | OPEN | PROGRESS.md **Train S2-19 records** (`37af82e2e8`) now records the lead's C1 real-cache pass and Moonshot source-chain APPROVED. Methods/data lead and independent reviewer still bind the requested source/unit/census-exclusion scope and final-head C1 data evidence to L6/L7. Do not claim there was no source review; do not restamp that earlier review as a final-head run. |
| PO-S2-52 | OPEN | S2-T07 methods/data lead and S2-T04 spine reviewer supply the third C2 activity-class data test with basket-derived membership, unknown-code refusal and signed-input binding after OI-203 signing/audit (L5), then L7. BT-1 membership alone is insufficient. |
| OI-203 | OPEN | S2-T04 lead, basket reviewer, signing model and different-maker auditor follow decision 0075's real-cache preparation/signing/draw/audit/admission procedure (L5). P57/P60 tooling is merged (`88aea3ca5b`, `37af82e2e8`); no real signature or isolation audit follows from invented tests. |
| S2-P47 / decision 0090 prerequisites | CLOSED (offline prerequisite only) | P47 is merged `e7edf54613`; `154333b523` records accepted decision 0090 and the reviewed outside-boundary input. S2-T20's national frame/source-chain proof still waits on L6 and its real data test; C-20 is not closed. |
| S2-T20 / S2-P53 / C-20 | OPEN | S2-P53/citation metadata is merged `ac06afc77d`. S2-T20 data/height lead and independent source reviewer still acquire selected citations with immutable receipts, review the local nonempty hand list, prove unique building ties and measure all fallback/GBA errors with source/hash/date chains at L6. Metadata alone is not acquired evidence. |
| OI-310 | OPEN | S2-T20 lead measures GBA errors against recorded heights at L6, then puts placement to the owner before S3-T16 uses it. OPEN_ITEMS.md **OI-310** / decision 0064 item 25 require measurement before the order question; R6DISP's owner-choice-before-measurement sequence is corrected. Current height order stays unchanged. |
| PO-S2-P55-01 / S2-P58 | OPEN | P55/P58 producers are merged `88aea3ca5b` / `37af82e2e8`. S2-T08 data lead supplies L6/L7 local PUB-71 expectation, PUB-72/73 production, final-audit comparison and require_complete with every required stage/local-source check present. No merge wait remains; live proof does. |
| S2-18-RF1 / S2-HYPO | CLOSED (timer cause/fix) | `88aea3ca5b` carries the exhaustive section-10 state test; `37af82e2e8` merges the reviewed S2-HYPO class sweep. OPEN_ITEMS.md **S2-18-RF1** says it closes when the train merges with the change; PROGRESS.md **Train S2-19 records** records different-maker APPROVED. Later green whole-test evidence in **Train S2-20 round 4 records** is attributed history, not a rerun of the original failed head. |
| S2-T06 flagship producer / S2-P61 | OPEN | P61 is merged `37af82e2e8`. S2-T06 data lead still fills reviewed candidate/building inputs and produces actual flagship parts, flagship_calibration and zoom thresholds with source/licence chain at L6. Offline approval is retained without a live tick. |
| S2-T06 refusal observability / S2-P56 / S2-RDP | OPEN | RDP/P54/P56 are merged `37af82e2e8`, `88aea3ca5b`, `ac06afc77d`. S2-T06 data lead/gate lead still verifies real retained refusal reasons, place/building rows and final_audit stored values at L6. Keys/counts alone are insufficient. |
| S2-T07 bank-credit replay / S2-P59 | OPEN | P59 is merged `37af82e2e8`, contrary to the old unmerged account. S2-T07 methods/data lead still records exact-Decimal real-cache bank-credit replay, independent expectation/source chain and the final-head ledger after L6. The later consumer lane of decision 0098 item 5 does not waive an actual S2 method/regression binding. |
| PO-S2-REC1-3 | OPEN | OPEN_ITEMS.md **PO-S2-REC1-3 — S2-T50 box 4** requires independent recomputation of the lead's national totals on the actual extract, with final evidence binding; S2-T50 lead and different-maker recompute seat act after L7. R6DISP's registry/index-delta description is not this item: S2-T08 lead still reconciles that attributed delta after L6 and identifies its existing tracking record; neither obligation closes here. |
| PO-S2-P46-02 | OPEN | P46 builder and lead establish the SIGTERM cause through bounded observation, working-directory/process/lock identity and pending-build evidence, with different-maker remedy review. The recorded tool-time-limit hypothesis is unproved; a green L11 is insufficient. |
| PO-S2-P46-03 | CLOSED (recorded merge condition) | `e7edf54613` lands P47's once-per-process registry fixture read (`custodian/tests/singles_entries.py`); OPEN_ITEMS.md's P46-03 lead disposition establishes timed per-example registry parsing as the cause and says closure is on merge. This is the registry-read class fix, not the selection_reason rationale in R6DISP. No deadline, population or assertion is relaxed. |
| PO-S2-P46-04 | OPEN | P46 lead and actual failing-suite owners retain the incomplete whole-custodian validation and importer-coverage obligation from OPEN_ITEMS.md; reconcile the exact returned-task evidence with the final ledger/L11 and investigate each broader failure by cause. No decision item authorises treating this as a closed or carried pass. |

## Former unowned MTH-03 row

| ID | State | Decision / accountable owner and next step |
|---|---|---|
| MTH-03 / S2-T09 C6/C7 result-pin producer | CARRIED | Decision 0094 items 1–4 is accepted and merged by `37af82e2e8`; S6-T10 owns the three C6 result pins and S7-T05 the two C7 result pins, under OI-283, all required by S7. These replace R6DISP's incorrect later-task owners. All other S2 input/configuration pins remain path; their actual producer is now merged in `ac06afc77d` (P63/C2), with L6 production and independent source review still owed. S2-T09 as a whole stays open. |

## Remaining gate accounting

S2-T10#1–#4 and #7 stay unticked. This document neither resolves every S2 item
nor supplies another maker's closure review. Its scoped CLOSED rows do not
override PO-S2-36's live requirement, the final source/method/draw checks,
historical hosted-evidence gaps or random-failure cause requirements.
Decision 0098 item 8 exempts only its exact carry ledger and named constituents;
item 9 retains current fully-required-source refusals until independently
reviewed carry implementation exists. OI-308's dated inventory remains **to
complete after L6**, under S2-T08#13. The lead records actual L6–L12 evidence
and the normal review/train/hosted checks on the containing final head.
