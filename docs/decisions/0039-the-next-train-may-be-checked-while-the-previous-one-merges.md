# 0039 — The next train may be checked while the previous one merges

| | |
|---|---|
| Status | Accepted, 2026-11-15 |
| Date | 2026-11-15 |
| Owner | albarami |
| Decided by | The owner, in the task brief of 2026-11-15 |
| Amends | AGENTS.md and CLAUDE.md rule 33; the sequential hosted-run clauses of TASKS.md and document 14 |
| Purpose | Pipeline train preparation and checks while preserving approval, exact-head checks and the exact merged-result test. |
| Read first | [Decision 0032](0032-approved-tasks-of-one-slice-may-merge-as-a-train.md) items 1 to 3; [AGENTS.md](../../AGENTS.md) rules 33 to 41 |

## Context

Decision 0032 allows individually approved tasks of one slice to share a train. The owner now allows preparation and checking of the next pull request while the preceding hosted run proceeds, without allowing it to merge on stale evidence.

## Decision

1. The next pull request may open while the previous one's hosted run proceeds. Its hosted checks, train confirmation and the lead's ledger run in parallel.
2. After the previous merge, bring the next head onto the new main. If this move touches only records (ledger rows, TASKS.md status lines, open items and pin headings), approval stays valid with the move's diff attached. A move touching code or tests needs a new confirmation. This does not expand what counts as a record or authorize any other change under a records-only approval.
3. Rerun the required hosted checks on the moved head. In parallel, the lead runs the whole test with a fresh seed on the exact squash-merge result. Earlier hosted checks do not substitute for checks on the moved head.
4. Merge only when required checks are green on that exact head, another maker's APPROVED holds for it, and the local merged-result test is green. If the head or merge result changes, the evidence must apply to the actual candidate before merge.
5. Nothing else changes: decision 0032's task approvals, same-slice scope, file-by-file proof, train confirmation and failure handling remain; head checks, gates and the hard limit remain. Pushes stay one at a time, never to the base branch and never forced. This decision overlaps work; it grants no task, train or gate approval.

## Evidence

The owner's Decision 0039 in the task brief of 2026-11-15 supplies this authority. Decision 0032 supplies the existing train rules. This record claims no completed hosted run, confirmation or merged-result test.

## Consequences

The next train may be prepared and checked earlier, but must move to the new main and satisfy all three merge conditions on the actual candidate. Records-only moves preserve approval with an attached diff; code or test changes require new confirmation. The sequential push rule is unchanged.

## Amended passages

- AGENTS.md and CLAUDE.md: Status and rule 33.
- TASKS.md: Queue rules, the built-ahead task's hosted-check timing.
- Document 14: Branch, pull request and evidence protocol, the pipelined-train amendment.
- docs/README.md: accepted-record list and decision index.

## What would change this decision

A further owner decision changing the concurrency or approval conditions, recorded under rule 46.

## Open questions and assumptions

None added. The existing hard limit is unchanged; this record assigns no new value to it.

## Sources

- The owner's task brief of 2026-11-15, Decision 0039 (project record of this assignment).
- Decision 0032 items 1 to 3; AGENTS.md rules 33, 35, 36 and 40.
