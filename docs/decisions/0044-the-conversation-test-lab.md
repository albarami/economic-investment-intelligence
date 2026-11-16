# 0044 — The conversation test lab

| | |
|---|---|
| Status | Accepted |
| Date | 2026-11-16 |
| Owner | albarami |
| Decided by | The owner, in the notes of 2026-11-16 relayed by the advisor (on the combination, on comparison and the correction on parity); and the lead's rulings L-680, L-684, L-685 and L-686 |
| Amends | Decision 0038 |

## Context

The owner's note of 2026-11-16 asks to test the conversational experience with hundreds and thousands of questions from every angle, to ensure it is smooth, valuable, visually appealing, and accurate. Decision 0038 already accepted the question factory, but this record widens its scope and raises its priority to cover the entire conversational experience, including the map. The owner's relayed notes of 2026-11-16 on the combination and on comparison also establish EII's own properties as criteria; the lead's ruling L-686, on the owner's correction of the same day, keeps every comparison with another product or service out of the repository.

## Decision

1. **Angles and grid.** The angle grid of the note (activity or industry, place, intent, persona and phrasing, language, device, hour and day type, and conversation shape) with per-cell coverage and listed empty cells, must-decline, must-suppress, out-of-scope, adversarial and injection sets; every persona, dialect and voice transcript invented.
2. **Accurate.** By deterministic oracles only (Fact chip to oracle value, closed keys, expected refusals and suppressions, geocoding oracle for the map target, pins within the shape, rankings equal the ranking tool, no recoverable hidden count); an invented figure or a disclosure fails as the existing gates already require.
3. **Smooth.** Measured as p50, p95 and worst on the stage laptop and a phone (time to first map action, first Fact chip, complete brief; frame rate during flights and re-ranking; layout shift; interruption and undo), budgets proposed by the task (first map action under 500 ms at p95 once data is loaded) and never loosened after a run.
4. **Valuable.** By deterministic presence checks and interactions to value.
5. **Visually appealing.** Screenshots per answer at stage and phone width, both languages and themes; automated checks (overlap, clipping, contrast, right-to-left mirroring with unmirrored numerals, pins on land, legend present, diff against approved baselines); a model look score is NOT added to the run-time gateway (rule 30 allows five closed classes only): it is a review job by another maker with design-audit and dataviz on a curated sample, advisory only; the owner judges beauty on a page of about 30 screenshots that the advisor sends.
6. **Scale and cost.** Generated questions are invented test inputs made on idle seats, screened, never real company questions; expected results come only from oracles; the held-out set stays sealed from authors; failures become catalogue entries, playbooks, paraphrases, refusals or fixes through the normal task loop.
7. **Operation.** One command, `./eii question-lab run --n N --seed S`, added to AGENTS.md rule 44 by the task that builds it, writing a coverage map, a per-question table and a screenshot gallery, reachable from the owner's devices through the remote mode of S3-T20 once it exists.
8. **EII's own properties as acceptance criteria.** EII's properties are stated never as a comparison: (i) every number carries its provenance class in the application and reaches it through the evidence thread, with decision 0035 binding (no origin word, class, texture or label on an audience surface); (ii) reviewed clarifying questions visibly change the criteria and re-rank the map; (iii) no model-written display prose (AGENTS.md rules 21 to 23); (iv) tested Arabic and English parity across speech, cards, ranking explanations and layout, one parity contract executed by S3-T21 for cards and layout, by S6-T11 for ranking explanations and by S8-T10 for speech; (v) the complete offline stage demonstration (AGENTS.md rule 27). No committed file, brief, briefing pack or gate evidence names another product or service or compares EII with one (AGENTS.md rule 15); EII's margins are its own thresholds, set by a later decision record; no text of the product, its templates, catalogues or briefing pack claims to be first, only or unique.

## Evidence and consequences

The owner's notes of 2026-11-16 and rulings L-680, L-684, L-685 and L-686 provide the authority. This decision widens the question factory from decision 0038 without rewriting it. Task S3-T21 "Conversation test lab, first version" is added to slice S3 to run 100 questions. Subsequent slice gates require higher counts (500 for S6, 1,000 for S8 and S10) as evidence, never as a relaxed threshold. The five properties of EII are established as its own acceptance criteria, and no committed file names another product or service or compares EII with one (AGENTS.md rule 15). No gate is weakened, and no check or limit is changed.

## Amended passages

- TASKS.md: A new entry S3-T21 "Conversation test lab, first version" is added after S3-T20. Named sub-steps for decision 0044 are added to S8-T12 and S8-T13. The slice S3, S6, S8, and S10 gate paragraphs gain an evidence sentence with their respective question counts. Amendment lines for decision 0044 are added to S6-T11, S3-T21, S8-T10, S10-T05, and S8-T03 to enforce clarifying-question re-ranking, the parity contract and where each part of it is executed, and the prohibition of claims to be first, only, or unique and comparisons with other products.
- docs/14_IMPLEMENTATION_PLAN.md: S3-T21 is added to the slice S3 task list.
- docs/12_TESTING_AND_QUALITY.md: A pointer sentence naming decision 0044 is added to the golden set description.
- docs/README.md: 0044 is added to the list and table of accepted records.

## Open questions and change control

Material changes to this decision require a new decision record under rule 46.

## Sources

- Owner's notes of 2026-11-16, relayed by the advisor.
- Lead's rulings L-680, L-684, L-685 and L-686.
- [Decision 0038](0038-advanced-methods-are-measured-spikes.md).
- [AGENTS.md](../../AGENTS.md), rules 16 to 18, 21 to 25, 26 to 32, 33, 44, 46, 47.
