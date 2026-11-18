# Decision 0055: Mutation testing moves to after go live

| | |
|---|---|
| Status | Proposed, for the owner's approval as the record of the owner's decision of 2026-11-18 14:10 |
| Date | 2026-11-18 |
| Owner | The owner |
| Decided by | The owner's decision of 2026-11-18 14:10, under AGENTS.md rule 46; approval of this written record is pending |
| Amends | Decision 0052 items 1 to 7 as specified below; TASKS.md queue rules and S2-T22; document 12 sections 4, 6.1, 6.2 and 6.3; document 14 PLN-31; the decision index of docs/README.md |
| Purpose | Defer mutation campaigns, kill passes and survivor-fix tasks until after go live, preserve their unfinished work for handoff, and remove campaign closure from slice gates. |
| Read first | [Decision 0052](0052-mutation-campaigns-run-in-a-background-lane.md); [document 12](../12_TESTING_AND_QUALITY.md) sections 6.1 and 6.2; [document 14](../14_IMPLEMENTATION_PLAN.md) PLN-31; AGENTS.md rules 12, 16, 35, 36, 37 and 46 |

## Context

Decision 0052 allowed merges before a mutation campaign finished, but required every campaign and its survivors to be answered before the slice gate. On 2026-11-18 at 14:10 the owner decided to stop this work before go live. The owner's reason was that it takes too long and, in the owner's judgment, does not affect go live until the synthetic data is replaced by real data. That is the owner's reason for changing the schedule, not evidence that the unfinished testing has found every defect.

The owner's further notes of 14:11 to 14:13 request a detailed handoff that explains the work to people working by hand, leaving their choice of tools to them.

## Decision items

1. **Mutation work moves to after go live.** No mutation campaign, kill pass or survivor-fix task runs before go live. Campaigns and their unfinished follow-up are handed to the team that takes over after go live, if that team approves the work. This replaces the background-running schedule of decision 0052 item 1 and defers the work required by its items 2, 3 and 5. It does not mark an incomplete campaign complete. For campaigns running at the time of the owner's decision, partial counts and the killed, survived and timed-out lists per module are preserved in a readable record before the campaigns end. Kill-pass tests already written and in review or correction finish only what is needed for acceptance as ordinary tests; no new campaign or survivor-fix task is started.

2. **No slice gate waits for mutation closure.** A task, train, slice gate or go live does not wait for a mutation campaign, kill pass, survivor disposal or a mutation-only follow-up item. This replaces decision 0052 item 6 and its gate-record requirement. General task-completion and open-item closure clauses do not reintroduce that wait. Mutation lane entries become deferred handoff records, preserving each known module, measured commit, file hash, counts, result and unfinished follow-up without treating missing evidence as a pass. This replaces the active-lane requirement of decision 0052 item 7.

3. **Confirmed defects stay visible.** A survivor already confirmed as a wrong number or a wrong refusal is recorded in [OPEN_ITEMS.md](../../OPEN_ITEMS.md) for the handoff, with its evidence and any known fix status. It is not dropped or represented as fixed by this deferral. This replaces decision 0052 item 4's requirement to start a fix task at once. An unexplained survivor alone does not establish a production defect.

4. **The other checks stay unchanged.** Unit, property, integration and parity tests, independent review under AGENTS.md rule 35, the accounting gate, the privacy and number checks, and the full test command with fresh seeds remain required. Their assertions, refusal rules, tolerances and evidence standards are unchanged. The non-mutation merge conditions preserved by decision 0052 item 1 remain required. Existing ordinary tests remain in the suite; this decision changes no code, command permission or version pin.

5. **The handoff preserves what remains.** The separate document `docs/18_MUTATION_TESTING_HANDOFF.md` is to record the tasks, modules, measured versions, survivors, timeouts, unfinished work and evidence needed to understand and resume mutation testing. It is to include the production defect in `page_shapes.workbook` found by a kill pass and fixed, distinguishing that completed repair from open work. It is to explain the method and completion rules without prescribing tools. Existing supporting scripts and version pins, including untested work, remain in the repository for later assessment; their presence does not establish that they work or require the receiving team to use them. Deferred requirements of decision 0052 items 2, 3 and 5 remain handoff context: a campaign covers the whole module, each survivor needs a test or a written equivalence reason, timeouts retain their category and are checked separately, and evidence for a different code version cannot close the version that is delivered.

## Consequences

The build can proceed through its ordinary checks and slice gates without waiting for mutation work. Unfinished mutation work remains unfinished and visible for a later team to assess. Neither the deferral nor a passing ordinary suite is a claim that every survivor is equivalent or that no production defect remains.

## Amended passages

- Decision 0052: an amendment notice points here; its approved decision text remains unchanged.
- TASKS.md: the queue rules state the deferral and its narrow exception to mutation-only open-item closure; S2-T22's campaign criterion ceases to be a gate requirement. Previously completed campaign evidence remains historical evidence.
- Document 12: sections 4 and 6.3 retain the earlier pilot procedure as deferred reference; TST-277 and TST-278 state the new schedule; TST-168 exempts only mutation-only handoff items from its closure requirement.
- Document 14: PLN-31 preserves the other merge conditions and changes the active lane and slice-gate wait to deferred handoff records.
- docs/README.md: decision 0055 is listed as proposed and decision 0052 points to this amendment, pending approval of the record.

## Sources

The owner's relayed decision of 2026-11-18 14:10 and the further handoff notes of 14:11, 14:12 and 14:13; decision 0052 items 1 to 7; TASKS.md S2-T22; document 12 TST-168, TST-277 and TST-278; document 14 PLN-31. The separate handoff document is to carry the detailed mutation evidence; this record claims no new campaign result or passed slice gate.
