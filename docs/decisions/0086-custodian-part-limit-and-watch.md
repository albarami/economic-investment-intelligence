# Decision 0086: Three custodian parts have one 1,200-second limit and a hosted watch

| | |
|---|---|
| Status | Accepted, 2026-11-21; the owner's decision relayed through his delegated advisor and lead ruling L-1404 |
| Date | 2026-11-21 |
| Owner | The owner |
| Decided by | The owner's words of 2026-11-21 23:11, the advisor's delegated decision, and lead ruling L-1404 |
| Amends | [Decision 0060](0060-the-custodian-suite-runs-in-two-named-parts.md) items 2 and 4, including its “never by a raised limit” sentence; [decision 0027](0027-hosted-web-checks-time-limit.md) item 4's one-value-everywhere wording as applied to the custodian parts; document 12 section 2.1 and the `scripts/run_tests.py` suite table |
| Purpose | Keep all custodian tests in three complete parts and distinguish a slow hosted runner from a hung suite. |
| Read first | AGENTS.md rules 33, 36, 37 and 46; decision 0060; document 12 TST-03, TST-04 and TST-15 |

## Implementation amendment — S2-P67

The proposed [decision 0097](0097-custodian-shard-headroom.md) records this implementation amendment separately for review.

Ruling L-1517 item 2 authorises five complete SHA-256 parts, modulo 5, named `python-custodian-1` through `python-custodian-5`, in place of item 1 below. The original decision and evidence remain historical. Items 2 to 4, including the 1,200-second limit, 720-second hosted watch, process-group kill and complete coverage, remain in force. Shared-machine measurements and the split prediction are recorded in PROGRESS.md under **S2-P67 — custodian shard headroom**; hosted confirmation and different-maker review remain pending.

## Context

The owner's words, quoted exactly from the relayed note: “if this 600 limit affect us change it we created this limit i want you to evaluate it and decide should we keep it as is or change it”. The choice to **change** the limit, and the watch threshold, are the advisor's delegated decision, not words attributed to the owner. Lead ruling L-1404 applies that decision to the existing three-part build.

The advisor read hosted logs: part 1 took 342 seconds and then 528 seconds on the same tests two hours later (1.54 times as long). Part 2 took 428, 452 and 516 seconds on successive runs, then returned no result within 600 seconds on the [main run](https://github.com/albarami/economic-investment-intelligence/actions/runs/44899177577). Its test count grew from 4,181 to 5,054 in one day. An earlier 569-second run under the 600-second limit is recorded in OI-285. The three-part local build measured 225.60, 305.88 and 253.40 seconds, with 3,690, 3,533 and 3,552 passing tests respectively; those counts sum to the unsplit 10,775 cases. Local times do not predict hosted times.

## Decision

1. **Three complete parts.** Keep `python-custodian-1`, `python-custodian-2` and `python-custodian-3`. A whole module belongs to one part by the SHA-256 of its repository-relative POSIX path modulo 3, plus 1. The manifest guard proves disjoint and complete test IDs and counts, and no empty part. This supersedes decision 0060 item 2's modulo-2 split; its no-skip and complete-collection requirements remain.
2. **One limit everywhere.** Set the suite-table timeout of each of the three parts to 1,200 seconds on every runner. The common `suite_timeout` path uses that one table value. `python-core`, `python-product` and `web-unit` remain at 600 seconds, `python-guards` at 3,600 seconds and `web-checks` at 1,800 seconds. This amends decision 0060 item 4's 600-second custodian limit and its instruction to split again “never by a raised limit”. Decision 0027 item 4's restored one-value-everywhere wording is applied to the custodian rows; its web-checks value remains 1,800 everywhere.
3. **Watch green hosted time.** The runner prints each suite's elapsed time and share of its limit. If a custodian part's **green hosted** time passes 720 seconds (60 percent of 1,200), split that part by a further decision record using decision 0060's method. The watch is a review trigger, not a second kill threshold or a reason to change a privacy or security tolerance.
4. **Keep failure detection.** The timeout still kills the process group. Its dedicated test retains a small independent limit and a planted disabled-kill failure. No test is removed, skipped, deselected from the complete run or retried. Rule 36 and the six hosted check names are unchanged.

## Evidence and consequences

The part counts, local durations, focused partition guard, disabled-kill plant and runner tests are recorded in PROGRESS.md under S2-P41 and in the builder's return. The hosted log evidence above is the advisor's reading, not a hosted run of this new head. A hang may now take up to 1,200 seconds to stop; a green hosted performance regression triggers review after 720 seconds. The raised timeout is authorised by this record under document 12 TST-03. No owner hard limit names 600 seconds for these suites (lead ruling L-1404).

## What would change this decision

A green hosted custodian part above the watch threshold calls for a further split record. A different timeout or watch rule needs a further decision record.

## Open questions and assumptions

Hosted time of the new three-part head remains to be measured; the local durations are not substituted for it.

## Sources

- The owner's relayed words and delegated advisor decision, 2026-11-21 23:11, in the task brief's `OWNER-DECISION.md`.
- Lead ruling L-1404, 2026-11-21 23:13.
- [Decision 0060](0060-the-custodian-suite-runs-in-two-named-parts.md), OI-285, and the S2-P41 evidence row in [PROGRESS.md](../../PROGRESS.md).
