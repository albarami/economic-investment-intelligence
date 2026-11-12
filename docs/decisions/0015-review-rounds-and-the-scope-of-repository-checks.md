# 0015 — Review rounds after the first, and what the repository's own checks defend against

| | |
|---|---|
| Status | Accepted, 2026-11-12 (amendment 2 to the first pack) |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Record the owner's decisions of 2026-11-12 that limit what a review round after the first may reject for, say what follows a rejected third round, and state what the repository's own checks are meant to withstand. |
| Read first | [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md), [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md), [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md) |

## Context

- The first pack made every review round a full review in which any finding rejects: REV-06 and REV-08 as first written, and the sentence in document 14 that the reviewer rechecks the full task, not only the changed lines.

## Decision

1. Round 1 of a review stays the full review. Its brief tells the reviewer that later rounds are limited as point 2 says, so everything the reviewer can find must be reported in round 1.
2. In every later round the reviewer still answers every check, but a verdict finding may only be one of four kinds: an earlier finding that is not fixed; a defect in, or caused by, lines changed since the commit the reviewer last reviewed; a secret, real data or a private path anywhere in the pull request; an acceptance criterion of the task that is not met. Every other valid point goes under the heading PROPOSED OPEN ITEMS, outside the verdict.
3. If a reviewer puts a point outside those four kinds into the verdict, the lead asks an advisor once. The advisor rules on the kind of the point only, and that ruling stands.
4. The same limit applies when a plan is reviewed again.
5. Every verdict finding is still fixed before the merge. There is still no "approved with comments".
6. If round 3 is REJECTED and the lead judges its findings valid, the task is not blocked yet. The findings are fixed by a stronger builder from a maker other than the reviewer's, and the same reviewer gives up to two confirmation reviews under point 2. If the second confirmation review is still REJECTED, the task is blocked for the owner and is not merged.
7. Valid proposed open items are entered in [OPEN_ITEMS.md](../../OPEN_ITEMS.md) and closed in one follow-up pull request per slice, before that slice's gate review. The gate reviewer checks that none is left open.
8. The repository's own checks (the tree check, the documentation check, the hooks, the commit guard and the CI scripts) protect against mistakes in three settings: a fresh clone, the CI runner, and a checkout used through the documented commands. That includes ordinary differences between machines, such as personal git configuration, locale or a linked path.
9. Someone deliberately defeating a check on their own checkout is outside the scope of those checks: for example an index flag such as assume-unchanged, a replaced program, or a race by a second local process. A point that needs such tampering is a proposed open item, not a verdict finding.
10. The generator sandbox is judged by what the sandboxed program can do, not by what a second local process could do to the launcher.
11. Plans already written keep what they have.

## Evidence

- The owner's decisions of 2026-11-12, which this record states.

## Consequences

- REV-06 and REV-08 in document 15 are amended and REV-39 to REV-42 are added; the sentences on re-review in document 14 are amended. This record is their source.
- The brief for round 1 quotes points 1 and 2. The brief for a later round names the commit last reviewed, so that "lines changed since" has one meaning.
- A proposed open item is not lost: it is entered in the open-items file and closed before the slice gate, where an independent reviewer checks it.
- No check of the repository is made weaker by this record. What changes is which points may reject a commit after round 1, and which threats a check is judged against.
- The security and privacy rules of the product are untouched: there is still no fallback for sandbox enforcement, store parity or any security check (AGENTS.md rule 12; REV-37).

## What would change this decision

- A defect that reached the base branch because a later round could not reject for it and that the slice gate did not catch.
- A setting other than the three named in which the repository's checks are relied on, for example a build machine shared by several users.

## Open questions and assumptions

- ASSUMPTION: "lines changed since the commit the reviewer last reviewed" is judged on the difference between that commit and the new head, lines of tests and documents included.
- ASSUMPTION: the advisor is a model from a maker other than the builder's and the reviewer's, because a second opinion from the same maker is not independent.
- ASSUMPTION: a confirmation review uses the verdict format of document 15, section 4.

## Sources

- The owner's decisions of 2026-11-12.
- [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md), [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md) and [12_TESTING_AND_QUALITY.md](../12_TESTING_AND_QUALITY.md). No external source was used.
