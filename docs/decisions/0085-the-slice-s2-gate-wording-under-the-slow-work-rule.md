# Decision 0085: The slice S2 gate wording under the slow-work rule

| | |
|---|---|
| Status | Accepted, 2026-11-21 |
| Date | 2026-11-21 |
| Owner | The owner |
| Decided by | The owner's words of 2026-11-21 (22:16, 22:18, 22:28, 22:30, 22:32 and 23:07, quoted below; OWNER_RULES 34), applied row by row by the advisor under that delegation; the gate reviewer judges the wording |
| Amends | [document 14](../14_IMPLEMENTATION_PLAN.md): new PLN-32, section 10 "Slice S2" gate bullet on the tender portal, and **ENHANCEMENT BACKLOG**; [document 12](../12_TESTING_AND_QUALITY.md): TST-168, new TST-280 and the slice S2 row of section 5; [document 15](../15_REVIEWER_CHECKLIST.md): REV-33 and REV-41; [TASKS.md](../../TASKS.md): S2-T44, S2-T10 and the slice S2 gate paragraph; [OPEN_ITEMS.md](../../OPEN_ITEMS.md): appended lines for OI-319, OI-341, PO-S2-129 and OI-360. It does not amend PLN-02, PLN-25, TST-165 to TST-167, TST-169, AGENTS.md rules 12, 33, 36, 37 and 39, decision 0055, decision 0069, decision 0071 or decision 0084 |
| Purpose | Reword, in one record, the slice S2 gate rows that were written before the slow-work rule, so that a slow item no later work needs moves to after go-live and a slow item later work needs runs in the background, with no check, test, plant or bound changed |
| Read first | Decision 0084, which lands with its code in the sibling task of the same train that builds the tenders own run; [decision 0055](0055-mutation-testing-moves-to-after-go-live.md) and TST-278, the earlier record of the same kind; [decision 0071](0071-after-go-live-operations-and-continuous-promotion.md) item 3; [decision 0079](0079-dated-gis-snapshot-and-structured-address-search.md) item 3; TASKS.md S2-T44, S2-T10, S2-T13 and S7-T09; OPEN_ITEMS.md OI-319, OI-341 and PO-S2-129 |

## Context and evidence

The owner's words, typing preserved (OWNER_RULES 34):

> good do it like this . anything that takes very long or very slow should stop our development to reaching go live if it can run in the background run it as we move forward if it can be postponed to after golive with enhancements also fine you evaluate and decide .

> i think probably if something takes long or very slow but has a dependency goes to the background and if something slow or takes long and doesnt have a dependency goes to enhancements after go live

> the gate is not a deciding factor the gate is written based on previous rule. you evaluate based on what we agreed on now. and tell me what do you suggest? does it have dependency to go to the background or its slow with no dependencies that can go after go live?

> we are not dropping it anyway we are only moving it to another stage so quality is not lost it will still run at a different time

> the gate wording can change based on the enhancements we just did i think our approach is more smart more integrated and faster value without loosing quality

The test this record applies to each slow item (the rule 34 test): **does anything before go-live use its
result?** If a named task, release step or reader does, the item runs in the **background** (own run, own seat,
named owner) and is picked up before that dependent starts. If none does, the item is **moved** to the
after-go-live list, word for word, with its depth, bound and plants. A gate row is not itself a dependent.

Evidence read in this checkout:

- TASKS.md S2-T44: "Depends: none"; no Depends line of any task names S2-T44. Criteria 2 to 6 are ticked;
  criterion 1 was re-opened by the train S2-11 records audit and asks for one more post-fix phase trace.
  OPEN_ITEMS.md keeps OI-319 and OI-341 as **CARRIED — GATE HOLD** and PO-S2-129 as **PARTIAL — ASSERTION
  CLOSED**. No task or release step reads the trace.
- One dependent by wording, not by result, exists and the advisor's note did not name it: TASKS.md S2-T10
  "Depends: every other task of slice S2 except S2-T46", with its criteria "no item is deferred out of this
  task" and "no item of the slice is left open". TST-168, REV-33 and REV-41 say the same of the gate: "The gate
  is not passed while an item of the slice is open". None of these uses the trace; each would still hold the
  moved box and its three items on the gate path unless it is reworded here.
- Tenders: decision 0084 and its plan. Readers of `pub_tender` are the D4 tender questions (PUB-93) and
  S7-T09. The slice S2 gate bullet of document 14 section 10 also says "The gate records its workbook hash,
  cut-off, pages read, stop page, actual continuity-page count and last page read"; three of those exist only
  after the tenders own run, so that sentence, not PLN-25, is what needs new words.

**Two stages of going live.** The owner's words of 23:07 settle the two senses:

> thats the first go live but the enhancements start after the final complete go live. so after s3 the portal will launch and we will keep updating it with features as we move forward s4 s5 s6 and so on and when all the s are complete enhancements will start and will keep updating the portal with features and enhancements.

1. **First go-live**: the portal launches at the slice S3 gate (decision 0071 item 1). Slices S4, S5, S6 and on
   then add features to the live portal, each through its own slice gate.
2. **Final go-live**: when every slice is complete. Only then do the enhancements start (decisions 0055 and 0070,
   document 14 **ENHANCEMENT BACKLOG**).

In this record "go-live" alone, and "after go-live" for a moved item, mean the **final** go-live: a moved item is
released after the last slice, never at the slice S3 gate. A slow item's dependency is judged against the slice
that needs it, and a background item is picked up before that slice's gate. Anything the first go-live itself
needs at the slice S3 gate is never moved past that gate. Under this reading S7-T09 needs the tenders own run, so
tenders run in the background and are picked up before S7-T09 starts (item 3); S2-T44 criterion 1 is needed by no
slice, the S3 launch included (the regression fix and the loaded and normal passes of its criteria 2 to 6 are
already in), so it moves to after the final go-live (item 2).

## Decision

1. **The rule enters the plan (new PLN-32).** "Under decision 0085, slow work whose result a named task,
   release step or reader before go-live needs runs in the background, in its own run with a named owner, and
   is picked up before that dependent starts; slow work that nothing before go-live needs is moved, word for
   word, with its depth, bound and plants, to **ENHANCEMENT BACKLOG**, 'Slow work moved by decision 0085'.
   Each move names its row, its open items and its owner role in a decision record. A gate row is not a
   dependent. No check, test, plant, bound, hosted check, whole test or review is removed or loosened, and no
   item touching scope, spend, anything public, privacy or security is moved without the owner's own words."

2. **S2-T44 criterion 1 is moved, with OI-319, OI-341 and PO-S2-129.** Rule 34 test: dependent before
   go-live, **none** (S2-T44 has no dependents; S2-T10's blanket line and the open-item rows are wording, items
   4 to 6). The criterion moves word for word, with the audit's NEEDED text, to the backlog row of item 8.
   The three items stay **OPEN** and are listed there; nothing closes them but the evidence they already name.
   This item applies only if the measurement round running when this record is filed does not settle the
   criterion; if it does, the box is ticked on that evidence and nothing is moved. No further measurement or
   review round on S2-T44 is launched before go-live.

3. **Tenders stay on decision 0084: background, picked up before S7-T09.** Rule 34 test: dependents **D4
   tender questions (PUB-93) and S7-T09**. This record adds only the gate words of items 7 and 9. OI-360 (the
   unexplained tender-host refusal) stays **OPEN** and travels with the tenders own run: it is settled on that
   run's evidence before the S7-T09 start check of decision 0084 item 6, never by a green run alone.

4. **Checklist row C-P4** (gate checklist, section 4 "Preconditions of any slice gate").
   As it stands — check: "Every task of the slice is done"; evidence: "TASKS.md: every S2 status line done,
   every box ticked or carried by a pack rule; S2-T46 excluded (decision 0070 item E)".
   New words — check unchanged; evidence: "TASKS.md: every S2 status line done; every box ticked, carried by a
   pack rule, or moved word for word to the after-go-live list by decision 0085 with its open items and its
   row in document 14 **ENHANCEMENT BACKLOG**. Moved at this gate: S2-T44 criterion 1 only. Excluded: S2-T46
   (decision 0070 item E) and S2-T51's background acquisition (decision 0079 item 3)."

5. **Checklist row C-P5** (same section).
   As it stands — "OPEN_ITEMS.md records every random failure; every in-scope proposal is closed by S2-T10 or
   carried by a pack rule; no unresolved non-exempt S2 item is hidden".
   New words — the same sentence, then: "Carried open by decision 0085, each with an appended dated line: OI-319,
   OI-341 and PO-S2-129 (moved with S2-T44 criterion 1, item 2) and OI-360 (with the tenders own run, item 3).
   No other item is carried by that record."

6. **Document 12, section 6.2: TST-168 and new TST-280; document 15: REV-33 and REV-41; TASKS.md S2-T10.**
   - TST-168 as it stands ends: "The gate is not passed while an item of the slice is open, except for
     mutation-only items deferred to the handoff under decision 0055 items 2 and 3; their evidence and
     unresolved status stay recorded." New words: after "items 2 and 3" insert "and for the items a decision
     record names as moved or carried under PLN-32 (TST-280)".
   - TST-165 as it stands: "Every task of the slice is done." Unchanged; TST-280 reads it, as TST-278 does.
   - New TST-280: "Under decision 0085 and PLN-32, a criterion moved word for word to **ENHANCEMENT BACKLOG**,
     and the open items its decision record names with it, are excluded from the task-completion and open-item
     closure conditions of TST-165 and TST-168. The gate record lists each moved criterion, its items, its
     backlog row and its owner role; an item carried with a background run is listed with the dependent that
     must not start before it is settled. Absent evidence is not a pass; a moved item is never recorded as
     closed; every other gate item and check remains required."
   - REV-33 as it stands says: "The gate is not passed while a proposed open item of the slice is open
     (REV-41)." REV-41 as it stands says: "The gate is not passed while an item of the slice is open." New
     words: each of the two sentences gains "except as TST-168 states". Nothing else in either row changes.
   - S2-T10 as it stands — "Depends: every other task of slice S2 except S2-T46, which runs after the gate
     (decision 0070 item E)." New words: one added line beside the decision 0079 exclusion: "Exclusion under
     decision 0085 item 2: S2-T44 criterion 1 and OI-319, OI-341 and PO-S2-129 are outside this task's blanket
     dependency and its criteria 3 and 4; OI-360 is carried with the tenders own run (decision 0084). No other
     item leaves this task." Criteria 1 to 4 keep their words.

7. **Document 14, section 10 "Slice S2", gate bullet on the tender portal; the same two states, in short, in
   the TASKS.md slice S2 gate paragraph and in the slice S2 row of document 12 section 5.**
   PLN-25 as it stands — "the slice S2 gate must record the visitor-readable tender portal, used and shown in
   full with its terms read and recorded, or its absence for an access or technical reason, never its terms".
   Unchanged: it already admits the recorded technical absence.
   Bullet sentence as it stands — "The gate records its workbook hash, cut-off, pages read, stop page, actual
   continuity-page count and last page read, or the closed intake reason for a full awarded-list read".
   New words — "Under decision 0084 the portal lists are fetched in the tenders own run, in the background.
   The gate records the workbook hash and cut-off of the verified intake and one of two states: picked up,
   with the own run's retrieval date, archive hash, pages read, stop page, actual continuity-page count and
   last page read, or the closed intake reason for a full awarded-list read; or pending, with the source
   registered, its terms read and recorded, `NO_DATA`, reason `own_run_pending`, its caveat and no tender
   shown. A pending record is an absence for a technical reason, never the terms. The pages read, stop page,
   continuity-page count and last page are then recorded at pick-up, before S7-T09 starts (decision 0084
   item 6)." The rest of the bullet (five lists full reads, ordering refusals blocking, items 3 and 4 of
   decision 0069) keeps its words.

8. **The after-go-live list.** It lives in document 14 **ENHANCEMENT BACKLOG**, the list decision 0070
   **Enhancement backlog** opened, in a new sub-heading "Slow work moved by decision 0085"; the value-study
   table above it keeps its words. One row:

   | Moved item | What runs there, unchanged | Open items carried | Owner role | Release |
   |---|---|---|---|---|
   | S2-T44 criterion 1: "normal and controlled CPU-load phase measurements identify the cause" | The audit's NEEDED text word for word: a post-fix phase trace under the same four owned load loops with taskset and the same scene seed, naming the remaining load-sensitive phase (first idle, samples or orbit); a regression under `web/spikes/performance/tests` red for that phase and green after the fix; the three items closed on that evidence only. No time limit, retry, skip, assertion, plant, layer count or committed evidence changes (S2-T44 criterion 5; AGENTS.md rules 12, 36, 37, 39) | OI-319, OI-341, PO-S2-129, each OPEN | Lead delivery role, with S2-T44's builder persona and a reviewer of another maker; handed to the team that takes over after go-live with the record, as decision 0055 item 1 does for its work | release: after go-live |

   Promotion of anything that run changes follows decision 0071 item 3 in full. The trigger is go-live as read
   above; no earlier gate or task depends on the row.

9. **Checklist row C-09** (gate checklist, section 5 "Gate statements of slice S2").
   As it stands — "PLN-25: the tender portal is recorded, or its absence for an access or technical reason
   (never its terms), with the decision 0069 record"; evidence "K5 receipts for `tenders_pub`; PLN-25 record;
   K1 (`test_tender_chain.py`, `test_tenders.py`)".
   New words — check: "PLN-25: the tender portal is recorded as picked up from its own run, or as absent from
   this build for a technical reason (never its terms) while that run is pending, with the decision 0069
   record of the workbook hash and cut-off (decisions 0084 and 0085 item 7)". Evidence: "K5 assembly record
   for `tenders_pub`: `in use` with the own run's archive receipt, or `NO_DATA` with reason `own_run_pending`
   and its caveat; PLN-25 record in the words of decision 0084 item 5; K1 (`test_tender_chain.py`,
   `test_tenders.py` and the own-run tests of decision 0084)". Who: lead; the tenders own run has its named
   owner and is not a gate command.

## Other slow rows, with the rule 34 test answer

Searched: every C-row of the gate checklist and every gate bullet of document 14 section 10 "Slice S2",
against the open boxes of the S2 entries in TASKS.md. No row below is reworded by this record.

Already worded to the rule (no change):

| Row | Slow item | Dependent before go-live | Standing |
|---|---|---|---|
| C-P4, C-P5, C-P6 | Mutation campaigns, S2-T32 | none | After go-live: decision 0055, PLN-31, TST-278 |
| C-P4 | S2-T46 older awarded pages | S7-T35 | Post-gate own acquisition: decision 0070 item E |
| C-P4 | S2-T51 imagery snapshot fetch | none before go-live for the fetch (decision 0079 item 3) | Background: decision 0079 |
| C-23 | S2-T29 amendment, every `report_url` re-checked (OI-277) | S7-T09 | Already written "in the background" (decision 0064 item 41) |

Slow, with dependents, and the gate itself reads the result (keep on the path; run beside the work):

| Row | Slow item | Dependent | Answer |
|---|---|---|---|
| C-01, C-02, C-05, C-07, C-11, C-12, C-17, C-19, C-22, C-23, C-24, C-27, C-P7, C-P8 | The live public build and its figure draw | REV-34 twenty figures, S2-T08, S2-T09, every S3 and later reader of the Public tables | Keep. It already runs in the lead's shell beside other work; decision 0084 removes its longest and least reliable part. No row reworded |
| C-12 | S2-T14 keyed night-lights fetch and its later months | S3-T12, S3-T14, S3-T16, S4-T09, S4-T10 | Background by its own words (lead's shell, "no test, gate or command needs" the key); later months are registered as published. Uses a key: no wording moved here |
| C-20 | S2-T20 landmark hand list and the building-atlas measurement (OI-310) | S3-T16 | Keep. The reason to wait is a missing cited list and an unconfirmed acquisition, not only time |
| C-03 | Census producer and spine review (PO-S2-48, PO-S2-52, OI-203) | S2-T10 amendment; later cards | Keep. Review and code are owed, not time |

Stays with the owner (touches scope, spend, anything public, privacy or security; not moved, not reworded):

| Row | Item | Why it is the owner's |
|---|---|---|
| C-P1, C-P2, C-P3 | Six hosted checks on the exact head, the lead's whole test with a fresh seed, provider `none` and no network | Merge conditions of rule 33 and security controls of rule 12; the owner's words keep them unchanged |
| C-P7, C-02, C-27 | Another maker's APPROVED on the slice; the reviewer's twenty figures | Rule 35, REV-33, REV-34; unchanged by the owner's words |
| C-P5 | OI-359, five portal rows under a robots-disallowed path | Public access to a publisher's host |
| C-P5 | OI-358, S2-T48 company-web search, fetch and review (rule 34 test: no task depends on it) | Public web reading and storage of pages about real companies, decision 0076 |
| C-P4 | S2-T41 optional satellite backup (rule 34 test: no task depends on it) | A credential pair and a provider's free allowance: security and spend |
| C-12 | S2-T16 box 13 and its amendment, the capped keyed busyness run | Spend: the owner's monthly credit cap |
| C-P4 | S2-T23 box 11, plan price for an unmet free plan | Spend |
| C-23 | S2-T29 amendments: sign-in for a source that refuses automated reading; personal fields of the school directory | Spend or set-up choice; privacy |
| C-P4 | S2-T27 amendment, archive copied to a drive the owner holds | The owner's own action on a path outside the repository (rule 13) |
| C-P4 | S2-T50 box 4, recount from the owner's company workbook | Privacy boundary of decision 0074 |
| — | PLN-02, "a later slice must not start until the preceding slice gate is recorded as passed" | Build order and scope. If the owner wants slice S3 building beside the live run, that needs his own words and its own record |

## Value lost

- **S2-T44 criterion 1: none in the end.** It is moved, not dropped, and runs later at the same depth with the
  same bound and plants. Stated plainly for the interval: until that run, there is no proof that no second
  load-sensitive phase remains in the browser spike, so a readiness timeout under load may recur in a whole
  test or a hosted check. A recurrence still fails its run, is still recorded under rule 39, and is never
  answered by a retry, a skip or a wider limit.
- **Tenders: none, provided the pick-up precedes S7-T09** (decision 0084 item 6). Until then tender questions
  answer `NO_DATA` with a true caveat.
- **OI-360:** nothing lost; it stays open and is settled on the own run's evidence.

## Unchanged

Every check, test, plant, bound, time limit and tolerance (rules 12, 36, 37); the six required hosted checks,
another maker's APPROVED and the lead's whole test on the exact merge result (rule 33); rule 39 (a green
re-run alone closes no random failure); the twenty-figure check (REV-34); PLN-02 and PLN-25; TST-165 to
TST-167 and TST-169; decisions 0055, 0069 and 0071. No command is added by this record.

## Files this record's change must touch

- `docs/decisions/0085-the-slice-s2-gate-wording-under-the-slow-work-rule.md` (this record) and the decision index of `docs/README.md`.
- `docs/14_IMPLEMENTATION_PLAN.md`: the status row, PLN-32 in section 1, the tender gate bullet of section 10
  "Slice S2", and **ENHANCEMENT BACKLOG** (sub-heading and row of item 8).
- `docs/12_TESTING_AND_QUALITY.md`: TST-168, new TST-280, and the tender clause of the slice S2 row of
  section 5.
- `docs/15_REVIEWER_CHECKLIST.md`: REV-33 and REV-41.
- `TASKS.md`: S2-T44 (criterion 1 marked moved, with its words kept; status line), S2-T10 (exclusion line),
  the slice S2 gate paragraph (tender clause).
- `OPEN_ITEMS.md`: appended dated lines for OI-319, OI-341, PO-S2-129 and OI-360; no earlier line rewritten.
- `PROGRESS.md`: the gate record's appended rows for C-P4, C-P5 and C-09.
- The gate working papers (checklist rows C-P4, C-P5, C-09 and the gate review brief), which are not tracked.
- Not touched by this record: `AGENTS.md` and `CLAUDE.md` (decision 0084 amends rule 44, in its own change),
  the S7-T09 dependency line (decision 0084 item 6), any code or test.

## What would change this decision

- A task, release step or reader before go-live that is found to read the S2-T44 trace: the criterion returns
  to the background, picked up before that dependent.
- A slice, the S3 launch included, found to need an item moved here: that item comes back before that
  slice's gate.
- A recurrence of the load-sensitive timeout frequent enough to block merges: the moved row is brought forward.
- Any wish to move a row of the "stays with the owner" table: the owner's own words and a new record.

## Sources

- The owner's words of 2026-11-21 quoted above, relayed exactly in the advisor's notes of 22:16, 22:18, 22:28,
  22:30, 22:32 and 23:07; OWNER_RULES 34.
- The slice S2 gate checklist (r5), rows C-P1 to C-P8 and C-01 to C-27; decision 0084 items 1 to 6
  and its plan, sections 2 and 5.
- [TASKS.md](../../TASKS.md): S2-T10, S2-T13, S2-T14, S2-T16, S2-T20, S2-T23, S2-T27, S2-T29, S2-T32, S2-T41,
  S2-T44, S2-T46, S2-T48, S2-T50, S2-T51, S7-T09 and the slice S2 gate paragraph.
- [OPEN_ITEMS.md](../../OPEN_ITEMS.md): OI-277, OI-310, OI-319, OI-341, OI-358, OI-359, OI-360, PO-S2-129.
- [Document 14](../14_IMPLEMENTATION_PLAN.md): PLN-02, PLN-25, PLN-31, section 10 "Slice S2" gate bullets,
  "Priority before go-live — decision 0070" and **ENHANCEMENT BACKLOG**; [document 12](../12_TESTING_AND_QUALITY.md):
  TST-165 to TST-169 and TST-278; [document 15](../15_REVIEWER_CHECKLIST.md): REV-33, REV-34 and REV-41.
- Decisions [0055](0055-mutation-testing-moves-to-after-go-live.md) item 1,
  [0070](0070-the-decision-pack-of-the-value-studies.md) item E and **Enhancement backlog**,
  [0071](0071-after-go-live-operations-and-continuous-promotion.md) items 1 and 3 and
  [0079](0079-dated-gis-snapshot-and-structured-address-search.md) item 3.
