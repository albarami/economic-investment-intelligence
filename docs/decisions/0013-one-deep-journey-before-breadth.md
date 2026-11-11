# 0013 — One deep journey before breadth

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why version 1 builds one journey in depth, with closed lists of tools and playbooks, and leaves breadth to an ordered backlog. |
| Read first | [01_PROJECT_BRIEF.md](../01_PROJECT_BRIEF.md), [14_IMPLEMENTATION_PLAN.md](../14_IMPLEMENTATION_PLAN.md) |

## Context

- The brief lists many company decisions: where to open, how to staff and pay, whom to buy from, where demand is, where to place a depot, why a branch is weak. Nine reports proposed dozens of capabilities.
- One person builds the product with coding agents. The judges' estimates put the full list well beyond the time a first version can take.
- A demonstration on a wall screen is judged by its weakest visible part.

## Decision

1. Version 1 builds one deep journey: the flagship site check for an Italian restaurant at a Lusail building, chosen only after its public places data has been checked. Two short journeys support it: staffing and pay, and costs and suppliers.
2. There are exactly three playbooks (`site_check`, `staffing_and_pay`, `costs_and_suppliers`) and exactly nine tools. The typed-decision gateway is not a tenth tool, a playbook step or a runtime dependency.
3. Breadth waits in an ordered backlog, L1 to L10. Each item is its own slice after slice S11.
4. If time slips, the cut order of the master design applies: company separation, neighbours chips, the churn panel, two-door comparison, supplier baskets beyond the flagship, where workers live, then the oversight seat. Never cut: the public-only answer, the privacy engine, the coverage and provenance marks, the Arabic review.
5. slices S0 to S11 each end at a gate with an independent reviewer. Nothing half-built sits behind a gate.

## Evidence

- Feasibility judge (2026-11-11): the research adds roughly seven to nine weeks to a plan whose own minimum cut was about seven, and "a half-built product with ten shallow modules loses to one deep journey". The judge's estimate for the whole of version 1 is fourteen weeks, to be re-planned after the spike. All of these are estimates, not measurements.
- Minister-impact judge (2026-11-11): breadth without depth is among the outcomes most likely to make the audience refuse the product; build one flawless door, then one economy-level scene.
- Engineering judge (2026-11-11), on the leading design before it was narrowed: still too much for one person, with 21 features, seven playbooks and eleven tools.
- The flagship must be chosen from data. In the open places extract one candidate tower had no restaurant within 250 m, while another Lusail landmark had fifteen (research check, 2026-11-11).

## Consequences

- The tool list, the playbook list and the list of stage directives are closed. A new capability is a new slice with its own gate and, where it changes the architecture, its own decision record.
- The architecture favours vertical slices: slice S3 answers end to end on public data before the synthetic world exists ([0010](0010-story-opens-on-public-evidence.md)).
- Features below the cut line are absent, not half-working.
- A prospect list of fictional firms is not in version 1, because a synthetic company list reads as a real recommendation (open item OI-07).

## What would change this decision

- The owner re-ordering the backlog after slice S11, or setting a demonstration date (open item OI-02) that forces the cut order.
- The spike (slice S1) showing that the plan is materially faster or slower than estimated. The plan is then re-drawn; breadth is not added in the middle of a slice.

## Open questions and assumptions

- OI-02: no demonstration date yet, so no date-driven freeze.
- OI-07: whether backlog item L8 includes a clearly fictional prospect list is the owner's decision.
- This record makes no ASSUMPTION.

## Sources

- Master design, value stack, cut order and slices (project record held by the owner, 2026-11-11).
- EII feasibility-and-cost judgement, minister-impact judgement and engineering-and-delivery-risk judgement, 2026-11-11 (project records held by the owner).
