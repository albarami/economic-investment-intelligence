# 0032 — Approved tasks of one slice may merge as a train

| | |
|---|---|
| Status | Accepted, 2026-11-15 |
| Date | 2026-11-15 |
| Owner | albarami |
| Decided by | The owner, in the note of 2026-11-15 allowing approved tasks to merge as a train |
| Amends | Rule 33 of AGENTS.md and CLAUDE.md, the queue rules of TASKS.md, and the workflow passages listed below |
| Purpose | Allow approved tasks of one slice to share a branch and pull request, preserving each task's work and review and all gates. |
| Read first | [AGENTS.md](../../AGENTS.md) rules 33 to 41, [TASKS.md](../../TASKS.md) Queue rules, [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md) PLN-04, [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md) |

## Context

Approved tasks wait one behind another for their pull requests to merge. Each pull request costs one run of the hosted checks and one whole test. The work itself is already reviewed. The owner's note allows those approved tasks to merge together within one slice, under the conditions below.

## Decision

The owner's note of 2026-11-15, word for word: "Owner note: I allow approved tasks to merge as a train. Tasks of one slice that are each approved on their own local commit by another maker, and whose dependencies are merged or in the same train, may be joined into one pull request: one ledger with every task’s own rows and verdict, the six checks once on the joined head, the lead’s whole test on the exact merge result, and one confirmation by another maker that the joined head holds exactly the approved commits and the records. If the joined head fails a check, the train is split and retried. Every task keeps its own plan, build, checks and review. Gates are unchanged. The lead records this as an amendment of rule 33 and of the queue rule “one task uses one branch and one pull request”, reviewed by another maker."

1. Tasks of one slice may be joined into one train branch and one pull request only when each is approved on its own local commit by another maker and its dependencies are merged or in the same train. One ledger holds every task's own rows and verdict. The six required hosted checks run once on the joined head; the lead runs the whole test command on the exact merge result. One confirmation by another maker says that the joined head holds exactly the approved commits and the records. If the joined head fails a check, the train is split and the parts are retried. Every task keeps its own plan, build, checks and review. Gates are unchanged.
2. For every task, the change of its approved local commits arrives on the joined head unchanged. The lead shows this by a script, file by file, and lists every difference forced by the join (a line that main changed since the task was built), each with its reason. A forced difference that changes a task's code or test is not a record: that task gets its own confirmation of the difference by another maker, or leaves the train. The records are the ledger rows, the status lines of TASKS.md, the open items and the pin headings that the ledger adds.
3. Builder and reviewer of each task remain from different makers (rule 35); the train confirmation comes from a maker other than the one that joined it. No check is dropped or run on less: required hosted checks, the lead's whole test with a fresh seed and head checks remain. Pushes stay one at a time, never to the base branch and never forced (rule 40). A slice gate is judged as before. An unapproved task, or a task whose dependency is neither merged nor in the train, does not ride. Decision records and other documents-only changes keep their own pull requests unless they are a task's own documents.

## Evidence

The owner's note of 2026-11-15 and the lead's reading of it supply the decision and its meaning. The review by another maker ordered by the note judges whether these amendments say exactly that decision, whether any passage still forbids it and whether any passage allows more. This record does not claim that such a review, a train or its checks has completed.

## Consequences

- One task per branch and pull request remains the general rule; this is its one stated exception.
- A train shares the hosted run and merge evidence, while its ledger preserves each task's own work, checks and verdict.
- The file-by-file proof and independent confirmation protect the approved changes through the join. A code or test difference cannot be treated as ledger text.
- A failed joined head is split and retried; no check is weakened or bypassed.

## Amended passages

- [AGENTS.md](../../AGENTS.md) and [CLAUDE.md](../../CLAUDE.md): header Status and rule 33.
- [TASKS.md](../../TASKS.md), Queue rules: the one-task branch and pull-request rule, the built-ahead task's push and merge order, and the gate-fix task's own branch and pull request.
- [README.md](../../README.md): header Status and Build and review workflow.
- [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md): header Status; In brief, the built-ahead task and the one-task branch and pull-request bullets; PLN-04; section 3, steps 2, 7, 8 and 10.
- [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md): header Status; REV-02, REV-04, REV-09, REV-11, REV-12 and REV-41; section 1.1, steps 1 and 4.
- [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md): header Status; TST-162, TST-163, TST-164 and TST-170.
- [docs/README.md](../README.md): header Status; In brief, the accepted-record list; Decision records, the row for this record.

## What would change this decision

A further owner decision changing the train's conditions or withdrawing the exception.

## What is not decided

No task approval, slice-gate approval, change of task scope or relaxation of a check is granted here. This record sets no cross-slice train, no train of unapproved tasks and no general exception for documents-only pull requests.

## Open questions and assumptions

None added by this decision.

## Sources

- The owner's note of 2026-11-15 allowing approved tasks to merge as a train, quoted above (project record held by the owner).
- The lead's reading of that note, points 1 to 3, for the unchanged changes, the records and the checks (project record held by the owner).
- [AGENTS.md](../../AGENTS.md) rules 33 to 41; [TASKS.md](../../TASKS.md) Queue rules; [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md) PLN-04 and section 3, for the workflow amended.
