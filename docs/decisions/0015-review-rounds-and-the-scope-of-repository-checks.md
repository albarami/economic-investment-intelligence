# 0015 — Review rounds, the scope of repository checks, and building ahead

| | |
|---|---|
| Status | Accepted, 2026-11-12 (amendment 2 to the first pack) |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Record the owner's decisions of 2026-11-12 on what a review round after the first may reject for, how proposed open items are closed, what follows a rejected third round, what the repository's own checks defend against, and when a task may be built ahead of its base. |
| Read first | [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md), [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md), [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md) |

## Context

- The first pack made every review round a full review in which any finding rejects: REV-06 and REV-08 as first written, and the sentence in document 14 that the reviewer rechecks the full task, not only the changed lines.
- The first pack let a dependent task start only after the merged commit of its base was green (document 14, step 10 of the protocol).

## Decision

Review rounds

1. Round 1 of a review is the full review. Its brief says that later rounds are limited as point 2 says, so that everything the reviewer can find is reported in round 1.
2. After round 1 a review still answers every check, but it may reject only for: (a) an earlier finding that is not fixed; (b) a defect in, or caused by, lines that the task's own patch changed since the commit last reviewed (changes that come only from updating the base do not count); (c) a violation of a safety check anywhere in the pull request: REV-14, REV-15, REV-18, REV-20 to REV-29, REV-38; (d) an acceptance criterion of the task that is not met. Every other valid point is a proposed open item, outside the verdict.
3. From the second confirmation review on, kind (b) no longer rejects: a new point in changed lines becomes a proposed open item. For S0-T01 the review after the current fix round is its second confirmation review.
4. If a reviewer puts a point outside the kinds that may reject into the verdict, the lead asks an advisor once, and the advisor's ruling on the kind of the point stands.
5. The same limits apply when a plan is reviewed again.
6. A check whose only defects are points outside the kinds that may reject reads OPEN with the ids of its proposed open items, not PASS and not FAIL. OPEN does not reject.
7. Every verdict finding is fixed before the merge. There is no "approved with comments".
8. If round 3 is REJECTED and the lead judges its findings valid, the task is not blocked: the findings are fixed by a stronger builder from a maker other than the reviewer's, and the same reviewer gives up to two confirmation reviews under points 2 and 3.
9. There is no blocked end. If the same finding is NOT FIXED twice in a row, the lead fixes it and asks the advisor to rule on that finding; if the advisor rules that it is not fixed, the lead applies the fix the advisor names and asks again. When every finding of the last verdict is fixed by the reviewer's word or the advisor's ruling, the commit counts as APPROVED. CI that stays red is handled the same way: the lead finds the cause and never weakens a check.
10. The first review of a slice gate is always a full review. Its later rounds follow points 2, 3 and 9.

Proposed open items

11. Each proposed open item names the requirement it concerns and its evidence. The lead enters every one in [OPEN_ITEMS.md](../../OPEN_ITEMS.md).
12. Each slice ends with a follow-up task before its gate, listed in [TASKS.md](../../TASKS.md): its own branch, its own pull request and a full independent review. It closes each item by a fix, or by one line saying why the item is not valid or is out of scope under point 14; its reviewer checks every closure. Nothing is deferred out of that task. The gate is not passed while an item is open.

What the repository's own checks defend against

13. The repository's own checks (the tree check, the documentation check, the hooks, the commit guard and the CI scripts) protect against mistakes in three settings: a fresh clone, the CI runner, and a checkout used through the documented commands, including ordinary differences between machines such as personal git configuration, locale or a linked path.
14. Outside their scope is only: someone on the same machine replacing the checker, git or a hook program; an index flag set by hand; a race by a second local process. This never covers an input whose pin, digest or checksum must be verified: dependencies, downloads, images, bundles, releases. Line-ending conversion and personal git configuration are in scope. For the generator sandbox the launcher must build and verify the documented mounts and namespaces, and the guarantee covers what the launched program can read, write and reach. A point that needs such tampering is recorded as out of scope in one line and needs no fix, unless it is already a verdict finding.
15. Plans already written keep what they have.

Building ahead

16. A task may be built in a worktree on the pushed head of one base task that is still in review, in a fix round or in CI, when the lead's checks are green on that head and its open findings do not change what the new task builds on. One level only: never on a task that is itself built ahead. Nothing built ahead is pushed or gets a pull request before its base is merged and it is rebased onto `main`; then every check is rerun and the review sees that head.

## Evidence

- The owner's decisions of 2026-11-12, given in two messages to the lead, which this record states.

## Consequences

- Document 15: REV-05, REV-06, REV-08 and REV-33 are amended and REV-39 to REV-42 are added; together they state points 1 to 14, and the verdict format gains the mark OPEN, the block PROPOSED OPEN ITEMS and, after round 1, the block EARLIER FINDINGS.
- Document 14: the sentences on re-review and steps 2, 8, 9 and 10 of the protocol follow points 2, 9 and 16.
- Document 12: TST-164, TST-168 and TST-169 follow points 9 to 12.
- TASKS.md: the queue rules state points 2, 12 and 16, each slice lists its follow-up task, and the criterion of the final reviews follows point 9.
- This record does not change AGENTS.md rule 12 or REV-37: there is still no fallback for sandbox enforcement, store parity or any security check.

## What would change this decision

- A defect that reached the base branch because a later round could not reject for it and the slice's follow-up task and gate did not catch it.
- A setting other than the three named in point 13 in which the repository's checks are relied on, for example a build machine shared by several users.

## Open questions and assumptions

- ASSUMPTION: "lines that the task's own patch changed since the commit last reviewed" is judged on the difference between that commit and the new head, lines of tests and documents included, with any update from the base branch taken out.
- ASSUMPTION: the advisor is a model from a maker other than the builder's and the reviewer's, because a second opinion from the same maker is not independent.
- ASSUMPTION: when the second confirmation review is REJECTED for a finding that no earlier round raised, the lead fixes it and asks the advisor to rule on it as point 9 says, because point 9 allows no blocked end and point 8 allows no third confirmation review.
- ASSUMPTION: a confirmation review uses the verdict format of document 15, section 4.

## Sources

- The owner's decisions of 2026-11-12.
- [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md), [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md) and [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md). No external source was used.
