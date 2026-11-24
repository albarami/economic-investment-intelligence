# 0110 — A pilot of APPROVED-WITH-SMALL-FIXES

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-24 |
| Owner | The owner |
| Amends | Nothing until accepted by the owner; then, for the pilot only, rule 35 of AGENTS.md and CLAUDE.md and the L-30 wording "no approved-with-comments" |
| Purpose | Remove a second review round only for exactly specified small fixes, with every finding fixed before merge and all merge checks preserved |
| Read first | [CLAUDE.md](../../CLAUDE.md) rules 35 and 46; [decision 0032](0032-approved-tasks-of-one-slice-may-merge-as-a-train.md) items 1 to 3 |

## Context

The owner's answer "yes", relayed on 2026-11-24 at 17:47, authorizes
drafting this record in response to the question about a pilot limited to
small, non-number, non-privacy fixes. It is not acceptance of this record.
The owner's six-point note supplies the scope and evidence below. No pilot
job runs before the owner accepts the record.

## Decision

1. **A pilot exception only.** Add the third verdict
   `APPROVED-WITH-SMALL-FIXES` to rule 35's `APPROVED` and `REJECTED`, for
   the pilot only. Amend L-30's "no approved-with-comments" only to admit
   this verdict under items 2 to 4. Every finding still has to be fixed
   before merge. Only the second review round for this class of fixes is
   removed; the verdict is not permission to merge with outstanding findings.

2. **Eligibility: all conditions hold.** A first full review always happens.
   The reviewer marks every finding small and names its exact fix. No finding
   touches a number, a privacy rule, a calculation, a gate, a security control
   or a test bound. The verdict is never used for the first review of a slice
   gate (L-47). A finding outside this class requires the normal `REJECTED`
   round; a small label alone does not establish eligibility.

3. **Closure by script.** The builder applies exactly the fixes named by the
   reviewer. A script checks the diff against the approved head: only the
   named files and lines may change, and the changes must be exactly the
   named fixes. It also checks that the task's tests and checks are green on
   the resulting head, with their commands and real exits recorded. Any other
   change, missing fix or failed check returns the task to the normal
   `REJECTED` round. The approved head here is the full commit reviewed for
   the conditional verdict, not an arbitrary later base. Closure evidence
   binds that head, the reviewer's exact fixes and the resulting full commit;
   it cannot transfer approval to a different head. The train confirmation
   and the lead's whole test on the exact merge result remain the backstop.

4. **The reviewer brief's finding format.** The brief requires the reviewed
   full commit hash, the verdict and, for every finding, these fields:

   | Field | Required content |
   |---|---|
   | Finding | An identifier for this finding |
   | Size | The explicit mark `small`, with the reason it qualifies |
   | Location | Repository-relative file and exact lines at the reviewed head; an insertion names its exact anchor |
   | Defect | What is wrong |
   | Exact fix | Literal before/after text or an exact patch, with no choice left to the builder |
   | Exclusions | Explicit confirmation that the finding touches none of the number, privacy-rule, calculation, gate, security-control or test-bound exclusions |

   Every finding must have the complete format and satisfy item 2. The failure
   watched is the reviewer marking a real defect small in order to approve
   it, as the owner's note on reviewer calibration warns. The label never
   waives fixing the defect or proving the exact change.

5. **Measurement and stopping.** Declare the pilot as 20 uses of the verdict.
   Record reviews and rounds saved, defects found after approval on pilot
   tasks, and the reviewer, builder and finding-size mix. Record those defects
   in the run's escape register, `ESCAPES.tsv`, tagged `pilot-small-fixes`.
   The advisor reads the measurements. Stop at the first escape caused by an
   applied small fix and report it to the owner. Otherwise, after 20 uses,
   report the measurements and ask the owner whether to keep the exception;
   continuation is not automatic.

6. **Evidence and its limits.** The owner's note reports an advisor analysis
   of 411 reviews and 180 classified rejections; sizes are the classifier's
   reading. Of those rejections, 48 (27 percent) had only small findings;
   44 (24 percent) had small findings and no number/privacy finding;
   34 (19 percent) also had an exact fix. For the four reviewers reported in
   the note, in its order and without their names, rejections with small
   findings only were 7 of 10, 6 of 9, 11 of 54 and 5 of 35. These are the
   note's counts and shares, not independently reproduced results or a count
   proved eligible under every exclusion in item 2. Its caution is that
   48 percent of later findings were repeats or introduced by a fix; hence
   closure by script, not trust. No saved-round or safety result for this
   pilot is claimed.

7. **What does not change.** The builder and the reviewer remain from
   different makers; the reviewer edits nothing. The six required hosted
   checks, another maker's approval on the exact head, the slice gates, every
   test and every check remain required. The conditional verdict and the
   script's exact-change proof do not waive exact-head approval. Train
   confirmation remains with another maker, and the lead's whole test runs
   on the exact merge result under decision 0032 and rule 33. No privacy,
   calculation, security, gate or test-bound rule is relaxed.

## Consequences and acceptance

This draft implements no script, changes no active reviewer brief and starts
no pilot. After acceptance, AGENTS.md and CLAUDE.md must be amended together
and remain byte-identical. The matching two-verdict workflow wording,
including [TASKS.md](../../TASKS.md) **Queue rules**, must reflect only the
accepted exception. The pilot briefs and closure script must enforce items
2 to 4 before use. Until then the existing two-verdict rule applies.

## What would change this decision

The owner may accept, reject or amend the proposal. Keeping the exception
after the declared pilot requires the owner's decision on item 5's report;
widening its class or changing a retained check requires a further decision
under rule 46.

## Open questions and assumptions

Owner acceptance of this proposed record remains pending. No other choice is
delegated to the builder by this draft.

## Sources

- The owner's six-point decision note, relayed 2026-11-24 at 17:47, including
  the exact answer "yes" to the drafting question at 17:45 (project record
  supplied with this task): items 1 to 3 for the exception and closure,
  item 4 for measurement, item 5 for the reported evidence and caution,
  and item 6 for reviewer calibration, referring to note 1748. The note
  identifies the standing rulings L-30, L-0043, L-0044 and L-47.
- [CLAUDE.md](../../CLAUDE.md) rules 35 and 46: the current two verdicts,
  different makers and the requirement for a decision record.
- [Decision 0032](0032-approved-tasks-of-one-slice-may-merge-as-a-train.md)
  items 1 to 3, and [AGENTS.md](../../AGENTS.md) rule 33: unchanged train,
  exact-head approval and merge-result checks.
