# Decision 0113: Activity-spine sign-off in the background lane

| | |
|---|---|
| Status | Proposed by the lead, 2026-11-24; different-maker review and acceptance remain pending |
| Date | 2026-11-24 |
| Owner | The owner |
| Proposed by | The lead, under its ruling L-1817 item 2, which directs one record in the shape of [decision 0084](0084-public-tenders-in-a-separate-run.md) and implements the owner's slow-work rule ([decision 0085](0085-the-slice-s2-gate-wording-under-the-slow-work-rule.md)) and the owner's lane rule ([decision 0098](0098-s2-sources-follow-their-first-field-reader.md)) |
| Amends | Nothing until accepted. On acceptance, and without editing that accepted record's text: the lane values of the `S2-T04#1` and `S2-T04#2` rows of decision 0098's **Complete box inventory** (item 1); on acceptance, only the placement of the spine review and PO-S2-52 in decision 0085's **Other slow rows** table, row C-03, is superseded, and that row's census obligation is kept; the TASKS.md S2-T04 carry lines, added marked proposed in this change and effective on acceptance (item 5); the decisions index of [docs/README.md](../README.md). It amends no requirement row, test, plant, bound, refusal or gate wording of any other document |
| Purpose | Take the activity-spine review sign-off and the category allow-list off the slice S2 gate path into the background lane ordered for slice S3, keeping every code, the full review depth and the honest refetch cost |
| Read first | TASKS.md S2-T04 and S3-T03; [decision 0075](0075-activity-mappings-signed-by-model-review.md); decision 0098 **Complete box inventory** and **Box carry ledger**; document 04 section 6 and PUB-38; AGENTS.md rules 33, 44 and 46 |

## Context

The activity spine's review sign-off (S2-T04#1, the review of the largest 200
codes, all food-service codes and all playbook codes; S2-T04#2, sign-off of
every admitted mapping under decision 0075) was inventoried `path` by decision
0098. The lead's ruling L-1817 item 2 of 2026-11-24 reads: slice S3 reads the
activity map only through S3-T03 `resolve`, whose box "unmapped codes stay
visible" holds with no admitted batch; so the admission leaves the S2 gate
path for the background lane, ordered for S3 — the release takes the admitted
state at its build time — with every code kept, and one record in the shape of
0084 follows. The later state of the same day (ruling L-1832) is: batch 3 of
the seeded audit was refused with `audit_decision_differs` (4 of 30 sampled
codes differ), the refusal stands by ruling L-1832 and was recorded in
lead-local commit
`82f6cb4fb1b7c176f63f658300f9713dda44b28f`; the base branch holds no persisted refusal
record: its `custodian/publicdata/review/activity_spine_refusals.json`
is empty. The admission stays in the background lane, and the L6 build does not
wait for it.

The second reading of the source census (record S2-CENSUS r4, rows N04, N05
and N06, by a maker other than the first reading's)
traces the three files `activity_spine.csv`, `activity_spine_audits.json` and
`category_allowlist.csv`: no ordinary build refuses on them in their unsigned
state — `build_spine` keeps `unreviewed` and `awaiting_human_review` rows and
the class-level refusal lives in `finalise_spine`, which only
`scripts/spine_review.py` calls; `_require_model_audits` returns early while
nothing is model-signed and no audit hash is bound; `read_allowlist` returns
the file's rows, an empty list for a header-only file, and
`build_graph(mode="release")` then adds no `listed_as` edge. N06 is S2 by
scope only — document 04 section 6 assigns both review files to S2-T04 and
PUB-38 requires the reviewed allow-list — and its final rows wait for the
signed spine. This record claims no admitted batch, no live build and no gate
pass.

## Decision

1. **The two boxes leave the S2 gate path for the background lane ordered for
   S3, and the allow-list follows the signed spine in the same lane.** The
   lane values of rows `S2-T04#1 | path` and `S2-T04#2 | path` of decision
   0098's **Complete box inventory** are amended to `background (S3, consumer
   S3-T03)` — by this line, never by editing the accepted record's text; the
   inventory's arithmetic becomes path 93, background 16 (background S3: 3),
   after final go-live 24, total 133 unchanged. `category_allowlist.csv`
   (PUB-38, document 04 section 6) follows the signed spine in the same lane:
   its final rows reconcile the allow-list to the freshly signed and audited
   spine, so it settles on the same condition as the two boxes. The full
   criterion texts, tests, plants, bounds and the decision-0075 audit
   obligations of both boxes are unchanged and travel with the carry. OI-203
   and PO-S2-52 stay open and travel by their existing identities, with
   `custodian/data_tests/test_pinned_methods.py::test_pinned_c2_isic_5610`
   carried with the spine; the other open rows that name the unsigned spine
   do the same — their slice-S2 gate hold is carried with the boxes under
   TST-280, and nothing closes or renumbers an item by the move.

2. **Nothing is dropped.** The review pipeline keeps running at full
   priority in the rule-44 order — prepare, triage, sign, draw, audit,
   assemble, finalise-check — under decision 0075's model signer and
   different-maker seeded audit at zero errors, and decision 0103's
   derived-row acknowledgement under the same audit. The batch-3 refusal
   stands by ruling L-1832 and was recorded in lead-local commit
   `82f6cb4fb1b7c176f63f658300f9713dda44b28f`; the base branch holds no persisted refusal
   record: its
   `custodian/publicdata/review/activity_spine_refusals.json` is empty. A later
   admission runs the same order at the same bar,
   never a shortcut and never a lowered one. Every code stays visible as
   unmapped until admitted: S3-T03's criterion holds with no admitted batch,
   so the map's resolve shows an unadmitted code as unmapped, never silently
   mapped and never dropped. The S3 release build takes the admitted state at
   its build time — the batches admitted when that build runs are what the
   release carries.

3. **The cost is stated honestly.** All three files are tracked under
   `custodian/publicdata`. Under the current partition of accepted decision
   0114's **Partition inventory**, `fetch/fingerprint.py::INPUT_PARTITION`
   classifies `review/activity_spine.csv` and `review/category_allowlist.csv`
   as shared fetch-pass inputs, and `review/activity_spine_audits.json` and
   `review/activity_spine_refusals.json` as post-loop-only;
   `fetch/fingerprint.py::_global_input` binds the shared inputs into every
   entry's fingerprint. The first build after an admission commit that changes
   the CSV or allow-list refetches every entry — the lead's measured figure for
   that refetch class is about 78 minutes of fetch and verify plus about 28
   minutes of assembly to the frame, plus the unmeasured stages after it
   (ruling L-1832). The graph is also written once — `assembly_graph_exists`
   refuses a replacement — so a later admission is a new build in any case. A
   change to the audit or refusal JSON alone does not force every entry's
   refetch, while a change to the CSV or the allow-list does; that refetch is
   paid in the background lane, never on the gate path.

4. **The S3 gate condition that keeps the value.** Before the slice S3 gate
   records a pass, each of the two boxes and the allow-list's final rows is
   either admitted — the admitted batch's audit evidence under decision 0075
   recorded and the reconciled allow-list committed — or carried past that
   gate by its own later decision record naming where each obligation lands.
   The S3 gate record lists the actual state of each; a pending state is
   never recorded as admitted, never ticks the original criterion, and the
   gate never passes with a box silently unaccounted. Under PLN-32 and
   TST-280 the S2 gate record lists the two boxes as carried, with consumer
   S3-T03 and this condition. S3-T03 may be built and pass while no batch is
   admitted — its criterion holds either way — so the carry's blocking point
   is the slice S3 gate record, not S3-T03's start.

   While the spine is unsigned, the C-03 gate record lists PO-S2-52 as
   carried open and, beside an otherwise-green K7 run, records exactly:
   `K7: exit 1; otherwise green (every other K7 test passed); FAILED
   custodian/data_tests/test_pinned_methods.py::test_pinned_c2_isic_5610 -
   Failed: C2-ISIC-5610:spine_refused; no skip, no deselection`. The failed
   test and exit 1 are shown, never a green K7 claim; the test still runs
   and fails closed until the spine is signed.

   The two spine boxes and PO-S2-52 leave the carry only after the spine is
   signed and audited under item 2 and a subsequent lead-shell K7 run of
   `uv run --locked python -m pytest custodian/data_tests -vv -p
   no:cacheprovider` exits 0 with `test_pinned_c2_isic_5610` passing.
   PO-S2-52 closes on that recorded evidence. The allow-list's final-row
   condition above is separate and unchanged.

5. **The documents this change touches are updated in the same change.**
   TASKS.md S2-T04 gains two carry lines, marked proposed and effective on
   this record's acceptance; the decisions index of docs/README.md gains
   this record's row. Decision 0098's accepted text is not edited — item 1
   supplies the amendment. No other document, requirement row, test, plant,
   bound, refusal or gate wording changes: PUB-38's obligation and document
   04 section 6's assignment of the two review files to S2-T04 are
   unchanged — only the delivery lane moves.

## Evidence

- Ruling L-1817 item 2 (2026-11-24), quoted in **Context**: the lane
  decision, the admitted-state-at-build-time rule and the "every code kept"
  condition; it names this record's shape as 0084's.
- Ruling L-1832 (2026-11-24): batch 3 refused (4 of 30 sampled codes differ;
  `audit_decision_differs`, the assembly refusal of `scripts/spine_review.py`
  recorded in `scripts/spine_triage.md`), the refusal stands by ruling L-1832
  and was recorded in lead-local commit
  `82f6cb4fb1b7c176f63f658300f9713dda44b28f`; the base branch holds no persisted refusal record: its
  `custodian/publicdata/review/activity_spine_refusals.json` is empty; a later
  admission pays its one refetch in the background, not on the gate path;
  L6 does not wait for it.
- The census second reading (record S2-CENSUS r4, rows N04, N05, N06):
  unsigned-state traces summarised in **Context**; the file anchors
  `review/activity.py::build_spine` and `finalise_spine`,
  `review/activity.py::_require_model_audits`,
  `review/graph.py::read_allowlist` and `build_graph`, and
  `fetch/fingerprint.py::_global_input`; the L6 consequence that the graph
  is written once.
- TASKS.md S2-T04 criteria 1 and 2 and its unedited part-B amendment
  (decision 0064 item 33), which stays on the path; S3-T03's criterion
  "unmapped codes stay visible" and its Depends line naming S2-T04, a
  planning dependency, not a field read (decision 0098 item 1).
- Document 04 section 6 (the spine build assignment) and PUB-38 (the
  allow-list obligation); PUB-33 and decision 0075 items 2 to 4 (the
  sign-off rule the carry keeps).
- OPEN_ITEMS.md PO-S2-52, **U10 UPDATE** and **U10 ROUND-3 UPDATE**: the
  class data test is built and never skipped, and the item stays open for
  the lead's real-cache replay on the signed spine.
  `custodian/data_tests/test_pinned_methods.py::test_pinned_c2_isic_5610`
  calls the shared closed-case boundary; `custodian/data_tests/cache.py`
  `closed_reason` maps `SpineError` to `spine_refused`, and `closed_case`
  emits `C2-ISIC-5610:spine_refused` as the test failure.

## Consequences

- The slice S2 gate can record the two boxes as carried under TST-280 with
  consumer S3-T03 and the item-4 condition; the gate's other items are
  unchanged, and pending is never a pass or a partial tick.
- The S3 release carries only admitted mappings; an unadmitted code shows as
  unmapped through S3-T03, so no Public map feature loses its coverage
  claim and none gains one.
- Every admission commit under `custodian/publicdata` costs one full
  refetch, so admissions are committed together where the pipeline allows;
  the cost is paid in the background lane, never on a gate path.
- Review depth, the seeded different-maker audit at zero errors and the
  PUB-38 reconciliation to the signed spine are all retained; value is not
  lost because nothing is dropped.

## What would change it

- A newly proved earlier field reader of the admitted spine or of the
  allow-list pulls the affected work back onto the path before that reader,
  under decision 0098 item 3's own rule.
- The owner's own words narrowing or widening the item-4 gate condition.
- An admission that completes before this record's acceptance turns the
  record into a carry record of a state that already holds; a refusal of
  the whole review route would need its own record, never a silent drop.

## Acceptance

Proposed by the lead under ruling L-1817 item 2 ("one record in the shape of
0084"), implementing the owner's slow-work rule (decision 0085) and lane rule
(decision 0098, accepted "option B" with the owner's value words that nothing
is dropped). Different-maker review and acceptance remain pending; on
acceptance the TASKS.md carry lines take effect and the S2 gate records the
carry under TST-280.
