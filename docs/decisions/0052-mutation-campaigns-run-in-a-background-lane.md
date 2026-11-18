# Decision 0052: Mutation campaigns run in a background lane; every campaign closes before its slice gate

| | |
|---|---|
| Status | Accepted; items 1 to 7 amended by [decision 0055](0055-mutation-testing-moves-to-after-go-live.md), the record of the owner's decision of 2026-11-18 14:10 |
| Date | 2026-11-17 |
| Owner | The owner |
| Decided by | The owner's decision of 2026-11-17, relayed with the conditions of the owner-approved advisor note of the same minute, under AGENTS.md rule 46 |
| Amends | Document 12 sections 6.1 and 6.2 (new rows TST-277 and TST-278); document 14 section 1 (new row PLN-31); the accepted-record sentence and the Decision records table of docs/README.md |
| Purpose | Let a task or train merge once every other check holds, while its mutation campaign runs in full afterwards, and keep the slice gate closed until every campaign of the slice is finished and answered. |
| Read first | AGENTS.md rules 16, 33, 36, 37 and 44; decision 0032; document 12 sections 5 and 6; document 14 section 3 |

## Context

Mutation testing runs on every Python or web module that computes or compares numbers, through `scripts/mutation.py` and `scripts/mutation_web.py` (AGENTS.md rule 44). Until this decision the lead ran each campaign before the task or train merged. A campaign runs one mutant at a time per module, so a large module takes many hours while most processors of the build machine stay idle; the joined-head campaign of one slice S2 train held every task queued behind that train's merge.

The owner's words, in answer to the proposal to merge a task once its tests and reviews pass, run its mutation campaign in the background right after, have the lead order fixes for survivors, and close every campaign before the slice gate, with nothing skipped: "i agree lets move own while it runs in the back grownd and kee completeing the system by the time we reach go live it will alos be done".

This decision changes when a campaign must be finished, not whether it runs. No review, hosted check, whole test, campaign, survivor rule or gate is removed.

## Decision items

1. **A merge does not wait for its campaign.** A task or train may merge when every other check of document 14 section 3 and AGENTS.md rule 33 holds: another maker's APPROVED on the exact head, the six required hosted checks green on that head, the lead's whole test with a fresh seed on the exact merge result, and, for a train, the confirmation of the join by another maker. Its mutation campaign runs in the background lane on idle processor blocks and need not be finished before the merge.

2. **Every campaign still runs in full.** Each campaign runs over the whole module, on the merged commit or on the approved head, with the module's file hash recorded. A partial campaign never closes. Timeouts are replayed alone at normal load as their own recorded step. No timeout, mutant set or test selection is changed to finish sooner.

3. **Every survivor is answered and confirmed.** Each survivor is killed by a new test or explained in `scripts/mutation_explained.toml`, and the kill or explanation is confirmed by a maker other than its writer. The fix goes through its own task or train under the normal review and merge rules.

4. **A real defect is fixed at once.** A survivor that shows a real defect in merged code, a wrong number or a wrong refusal, becomes a fix task at once, with its own entry in TASKS.md, and is not held for the gate.

5. **Changed again means campaigned again.** A module changed after its campaign's commit is campaigned again on the new commit; an earlier campaign of a different file hash never closes it.

6. **No slice gate with an open campaign.** No slice gate is approved while any campaign of that slice is open or any of its survivors is unanswered. The gate record lists each campaign of the slice with its module, commit, file hash, counts and result.

7. **The lane is visible.** The lead keeps a lane table, campaign, module, head, mutants done of total, age and the owner of the fix, in the run's state record and in each seats line, and a ledger whose campaign is still running says so with its lane row instead of a result.

## Consequences

Tasks behind a slow campaign start sooner, and the campaign's processors no longer set the pace of merges. A survivor found after merge costs a fix task instead of a rework before merge; item 4 bounds the time a real defect stays in merged code. The slice gate carries the full mutation evidence of the slice, so the gate cannot pass on unfinished campaigns.

## Sources

The owner's decision and the owner-approved advisor note on the lane's conditions, both of 2026-11-17, recorded word for word in the run's extracts; AGENTS.md rules 33, 44 and 46; decision 0032.
