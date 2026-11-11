# 0014 — Typed-decision gateway, behind the stage only

| | |
|---|---|
| Status | Accepted, 2026-11-11 (amendment 1 to the first pack) |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why version 1 includes a provider-neutral typed-decision gateway for build-time work, which jobs it may do, what it may never do, why nothing on screen depends on it, and the measurement behind the decision. |
| Read first | [02_ARCHITECTURE.md](../02_ARCHITECTURE.md), [09_AI_ASSISTANT.md](../09_AI_ASSISTANT.md), [0008](0008-assistant-never-types-a-number.md), [the qualification set](../../evals/typed_decisions/README.md) |

## Context

- A typed-decision model returns a bounded judgment over supplied inputs: a yes/no score, or one label from an enumerated list with scores. It does not retrieve, compute or write. The first provider considered is Jev (a "System One" model), which the owner already subscribes to through an independent gateway.
- The owner asked whether it has a place in this product. None of the earlier research had considered it.
- Before any measurement, three researchers and three other vendors' models advised the same thing: keep it off the live path, allow it only behind a replaceable interface, default off, and only after it is measured against ordinary code and a general model.
- Two facts made the question practical. The key for the main model is deferred (open item OI-01), so today the build has no general model at all. And the activity spine cannot be built from code structure alone: 84.6% of the licence count sits under 7-digit codes whose first four digits are an international class, 4.5% under 7-digit codes whose prefix is not a class, 10.8% under 6-digit legacy codes, 138 of which have a prefix that only looks like a class, and the remaining 0.1% under codes of five or eight digits (recomputed on 2026-11-11 from the open licence dataset and the UN ISIC Rev.4 structure file).
- The measurement was then made, and four independent rulings were taken with it in hand (two judges and two other vendors' models).

## Decision

1. Version 1 includes a provider-neutral typed-decision gateway, used behind the stage only. The default provider is `none`. Nothing on any screen depends on it. Every gate, the guided story, `./eii up`, preflight and freeze pass with the provider set to `none` and the network unplugged.
2. The first provider is Jev, pinned to `jev-1.14.0`, behind the setting `EII_DECISION_PROVIDER` (`none` or `jev`). The key is read from the environment variable `JEV_PRO_API_KEY` only.
3. Its answers are decision evidence. They are never facts, never numbers and never an authority.
4. Exactly five decision classes exist in version 1:

| Class | Where | Status ("admitted" = may be used for the stated effect; the full protocol on a human-labelled set is still owed, OI-15) | The only effect allowed | Fallback |
|---|---|---|---|---|
| `spine_match` | build time, public data | admitted | orders and pre-fills the human review queue of the activity spine | queue ordered by licence count; every row stays "not reviewed" |
| `router_miss_finder` | build time, team-written paraphrases | admitted | lists requests where the deterministic router and the provider disagree; each confirmed miss becomes a new rule and a permanent test case | rules and tests stay as they are |
| `brief_second_reader` | evaluation harness | admitted, advisory and raise-only | adds briefs to the human review sample; can never pass, fail or clear anything | "second reader not run"; gates are decided by code |
| `question_route` | harness and scripted rehearsals, team-written questions only | shadow | records what it would have routed beside the parser's result; changes nothing on screen | none needed |
| `string_parity` | build time, project text | experiment first | once admitted on 200 pairs labelled by the native reviewer: flags English and Arabic pairs for that reviewer | the reviewer reads everything |

5. No run-time use in version 1. A run-time routing assist and a live second check of model prose each need an approved route (OI-14), a connected main model and fresh human-labelled evidence, and each needs its own decision record.
6. Rules that apply to every class:
   - Scores are ranking signals, not calibrated probabilities. For ordering and flagging human work, 0.90 and 0.10 count as confident. For anything that removes an item from human view, 0.95 and 0.05. Everything else is `BELOW_THRESHOLD`, which is the application's outcome, not a provider answer.
   - A choice is asked in two fixed option orders and accepted only when both agree.
   - The model version is pinned and every decision is memoised by the hash of its class, rubric, inputs and model identifier. The first stored answer stands.
   - Every call writes a decision record, and a token cap applies to every run.
   - Results may only order a human review queue, flag an item in a report, or, after a person confirms it, become a deterministic rule or a test case.
   - Every activity mapping that enters a release carries a named human sign-off. A build check refuses a row whose only evidence is a decision record.
7. Forbidden in every mode: any call on visitor-typed text; any role in the "Try to break it" scene; any privacy or disclosure decision; any number; the provenance class or evidence status of a fact; tool arguments; approving prose for display; any recommendation, ranking or forecast; acting as the defence against instruction injection or as the must-decline gate; being a slice gate, a CI gate or a required step of any command; Arabic sign-off; showing its score to a user; training any model on its outputs; sending any real custodian data, real identifier, credential or real company question.
8. Data: the current route is an independent gateway that names no legal entity, stores submitted text and reports its own model identity. The owner has cleared it for public data, invented or synthetic text, text already in this public repository, and questions written by the team. The gateway code refuses every other class.
9. On screen: one lineage line under the activity spine in the Proof room, rendered from the review log: "N activity codes; review order machine-assisted; every mapping signed by a person." No panel, no badge, no score, no live call.

## Evidence

Measured by the lead on 2026-11-11 through the owner's existing subscription, on public and invented inputs only. The 260 labelled cases, the blind label sets and the aggregate results are in [evals/typed_decisions](../../evals/typed_decisions/README.md).

| Job (cases) | Jev 1.14 | Ordinary code | Small general model (blind, batch) |
|---|---|---|---|
| Arabic activity name against an international class, yes/no (100) | 94 (true matches 40 of 40; mis-filed legacy codes 20 of 20; sibling-class negatives 24 of 30) | code-prefix rule 80 (mis-filed legacy codes 0 of 20) | 100 |
| Pick the class among four (30) | 28 | not run | 29 |
| Route a request or decline it (50; half Arabic) | 50 (must-decline 12 of 12) | a quick keyword router 34 (must-decline 6 of 12); internal comparison only | 50 |
| Wording checks of a draft (60; half Arabic) | 57 (English 30 of 30; Arabic 27 of 30) | not run | 60 |
| English and Arabic say the same thing (20) | 19 | not run | 19 |
| Overall | 248 of 260, 95.4% (95% interval 92.1 to 97.3) | n/a | 258 of 260, 99.2% |

- Reliability: 780 calls over three identical runs, all answered. Median 0.55 s, 95th percentile 0.81 s, 99th percentile 1.17 s, maximum 3.1 s. About 371 input tokens per decision.
- Repeatability: 3 of 260 answers changed across the three runs, all with scores near the boundary. None changed while confident.
- At 0.90 and 0.10 it was confident on 173 of 260 cases and matched the label on 172. At 0.95 and 0.05, on 126, and matched all 126.
- Two option orders (the acceptance rule for a choice): each of the 80 pick-one cases was asked again with its options reversed, on the pinned version. Routing: the same answer in both orders on 50 of 50, all correct. Class choice: the same answer on 29 of 30, 28 of them correct. Where both orders were confident (65 cases), every answer matched the label.
- Vendor documentation, read 2026-11-11: the model is not a calculator, leans toward the first option of a choice, can be swayed by injected text, exposes no abstain answer, and is not deterministic on borderline items.
- Terms, read 2026-11-11: the official provider hosts in the United States, says it does not train on inputs, states no fixed retention period, and forbids using outputs to train a model that imitates the service. The independent gateway's terms name no legal entity, and its privacy page says it stores submitted text.

What the measurement does not show. Accuracy against human ground truth: the labels and the best baseline come from one model family. The official provider route. Which model actually answered: the identifier is self-reported by the gateway. Availability on another day. Robustness to injection: three items here, and an independent paper reports a much lower score on a public set. Real visitor phrasing or Gulf dialect. How the cut-offs hold on fresh data. Reviewer minutes saved.

## Consequences

- The activity spine gains a meaning check on every code, so human review goes where the mismatches are. No mapping enters a release on a model's word.
- The deterministic router and the must-decline tests are hardened with phrasings a person might not have thought of. Six such requests found on 2026-11-11 are added as permanent cases.
- A reader from a different maker checks the wording of generated briefs in the harness, and can only add work for a person.
- One more outside service exists at build time. It is never required, and an import-boundary test keeps it out of the fact model, the privacy engine, the release builder and the whole serving plane.
- A small general model is more accurate on this set. Once the main model key exists it runs through the same contract; if it is at least as good on a like-for-like run, the Jev provider is retired.

## What would change this decision

- A requalification run that fails to reproduce the recorded results within their intervals: the affected class is switched off.
- A change of model version, rubric, language or route: requalify before use.
- An approved route (OI-14) together with fresh human-labelled evidence from the shadow run: a run-time routing assist may then be proposed in a new decision record.
- The owner overruling this record.

## Open questions and assumptions

- OI-14: an approved route before any run-time use or any real question.
- OI-15: who labels the fresh human qualification sets.
- OI-16: who signs activity mappings, and the audit rule for batch sign-off.
- OI-17: whether a measurement panel ever appears in the Proof room. Default: no.
- OI-18: the token cap for this project on the existing subscription, and a key rotation date.
- ASSUMPTION: the cut-offs 0.90, 0.10, 0.95 and 0.05 come from one set of 260 cases and are to be re-derived on fresh, human-labelled data at each requalification.
