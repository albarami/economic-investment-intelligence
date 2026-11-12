# 0018 — Priorities of the proof of concept, and amendments to decision 0015

| | |
|---|---|
| Status | Accepted, 2026-11-12 (amendment 5 to the first pack) |
| Date | 2026-11-12 |
| Owner | albarami |
| Purpose | Record the owner's note of 2026-11-12 that sets where security stays strict in this proof of concept, sends every other hardening to the deployment-hardening document, amends seven points of decision 0015 on review rounds, proposed open items, the scope of the repository's checks, building ahead and build briefs, sets how extra reviewers count, and updates OI-01 (the main model key is supplied for go-live and not used during the build). |
| Read first | [decision 0015](0015-review-rounds-and-the-scope-of-repository-checks.md), [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md), [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md), `docs/17_DEPLOYMENT_HARDENING.md` |

## Context

- This proof of concept runs on public and synthetic data. What matters is value, accuracy, depth and design.
- [Decision 0015](0015-review-rounds-and-the-scope-of-repository-checks.md) limited what a review round after the first may reject for, set how proposed open items are closed, defined what the repository's own checks defend against, and allowed a task to be built ahead of its base.
- Reviews of slice S0 spent rounds on hardening of tooling (sandbox, hooks, commit guard, CI scripts) beyond the acceptance criteria of the tasks, while the product's own value waits.
- On 2026-11-12 the owner decided the priorities below and seven amendments to decision 0015, to be recorded in the version-1 documentation pull request. They are in force from that day.

## Decision

### Priorities

1. Security stays strict in two places only: nothing secret, real or private reaches the public repository (REV-14, REV-25, REV-28), and numbers and claims stay right (REV-15, REV-20 to REV-24, REV-26, REV-29).
2. Every other security requirement (the generator sandbox, the hooks, the commit guard, the CI rules, the repository settings, tamper resistance) is built in its simplest form that meets its acceptance criterion in [TASKS.md](../../TASKS.md).
3. Hardening beyond that is never a verdict finding, in any round. It goes into `docs/17_DEPLOYMENT_HARDENING.md` with where it came from (the review, plan or document that raised it), and it is not built now.
4. At each plan's one refresh (above all S0-T06, S0-T07, S0-T11, S0-T12 and S0-T14), such hardening moves out of the plan into document 17.

### Amendments to decision 0015

5. **Kind (c) of a later-round finding** (0015 point 2) becomes: a violation of REV-14, REV-15, REV-20 to REV-29 or REV-38 anywhere in the pull request. REV-18 leaves the list, under point 2 above.
6. **The advisor's ruling** (0015 point 4). When the advisor rules that a point does not belong in the verdict, the point leaves the verdict for good and is never an earlier finding later; a verdict left with no finding counts as APPROVED for that commit. Before every merge the lead reads the proposed open items of the last verdict: one that belongs to a kind that may reject is fixed before the merge.
7. **Confirmation reviews** (0015 points 8 and 9). There is no limit of two confirmation reviews: the same reviewer keeps confirming under the round rules until APPROVED. For a finding NOT FIXED twice, the lead fixes it, and the advisor rules on it and checks the lines of the lead's fix for kinds (c) and (d).
8. **Where proposed items go** (0015 points 11 and 12). The proposed open items of an approved pull request are entered by the next pull request's ledger commit, never on the approved head. An item from a plan review goes into that task's build brief. An item raised by the review of a slice's follow-up task, or by a gate re-review, goes to the next slice's follow-up task; in the last slice, into the final report. Findings of a rejected gate review are fixed in a gate-fix task with its own entry in [TASKS.md](../../TASKS.md).
9. **Mistakes are in scope** (0015 points 13 and 14). Anything that happens without anyone meaning it (a staged file that differs from the work tree, a busy port, a left-over process, another tool version) is a mistake, not tampering, and stays in the scope of the repository's checks.
10. **Building ahead** (0015 point 16) stays inside the task's own slice.
11. **Build briefs and internal review lenses.** Every build brief makes the builder break each condition of the code it writes, add a test for any break that nothing catches, and list the breaks in its return. A lead review with several internal lenses is used only for the calculation layer, the privacy engine and the release build; the difficulty "hard" in [TASKS.md](../../TASKS.md) no longer decides it.

### The main model key

12. **OI-01 stays open, updated.** The product's main model key is supplied for go-live and is not used during the build. It is one of the API keys that the owner's note of 2026-11-12 covers, held in the uncommitted `.env` file: none of those keys is used during the build, for anything, so no model, research or review service is called through any of them, and the assistant stays in template mode (BRF-23). The keys stay in the environment only and are never printed, logged, committed or copied (AGENTS.md rule 14). The note does not name the provider key of the typed-decision gateway, which is not one of those keys: [decision 0014](0014-typed-decision-gateway.md) and OI-18 govern its use unchanged.

### Extra reviewers

13. **One designated reviewer decides.** For a pull request that also has extra reviewers, one designated reviewer of a maker other than the builder's gives the verdict. Extra reviewers are advisory: the lead judges each of their points; a valid point of a kind that may reject in that round is fixed in the same round, and every other valid point becomes a proposed open item. Only the designated reviewer's verdict decides.

### Rules serve the project

14. **Targets, not gates** (owner's note of 2026-11-12). The 500-line limit per code file is a target: a file a little over is fine, size never rejects a commit, never fails CI and never causes a rework round on its own, a file is split only at a natural seam, and any check, proof block or lint rule that fails on file length becomes a warning. The same holds for the other house-style points (docstrings, naming, formatting the formatter does not fix): the builder follows them, a reviewer may note them, they never reject; type checks and tests stay as they are. Plan sizes (about 300 lines for a routine task, 600 for a hard one) are targets, and a plan may hold a short code snippet that pins down a hard detail. Every rule must protect value, accuracy, depth or design: a rule that causes rework or delay without protecting against a public leak or a wrong number or claim is relaxed, the change is recorded in one line, and work carries on. Review by another maker, green CI before a merge and the owner's hard limits stay as they are.

## Evidence

- The owner's note of 2026-11-12 (project record held by the owner), recorded word for word by the lead the day it arrived.
- Slice S0 history in [PROGRESS.md](../../PROGRESS.md): review rounds of S0-T01 and S0-T02 that turned on tooling details beyond the tasks' acceptance criteria.

## Consequences

- [15_REVIEWER_CHECKLIST.md](../15_REVIEWER_CHECKLIST.md): REV-39 (kind (c)), REV-40 (confirmation reviews and the advisor), REV-41 (where proposed items go, the gate-fix task) and REV-42 (mistakes in scope) change, REV-43 records the designated reviewer and the advisory extra reviewers, and the checklist says that hardening beyond an acceptance criterion is never a verdict finding and goes to document 17.
- [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md) and the queue rules of [TASKS.md](../../TASKS.md): building ahead inside the slice; the gate-fix task; the break-each-condition step of every build brief; internal review lenses only for the calculation layer, the privacy engine and the release build.
- `docs/17_DEPLOYMENT_HARDENING.md` holds a register of hardening items with their origin. The first entries come from this pull request: the items the owner's note of the same day moved from [OPEN_ITEMS.md](../../OPEN_ITEMS.md), and the proposed item of the first review of S0-T03 on a URL whose user part hides a third-party host.
- Decision 0015 stays accepted; this record amends its points 2, 4, 8, 9, 11 to 14 and 16 as stated.

## What would change this decision

- A further owner decision, for example before any use with real records, when document 17 becomes the work list.

## Open questions and assumptions

- This record makes no ASSUMPTION.

## Sources

- Owner's note of 2026-11-12 on priorities and on decision 0015 (project record held by the owner).
