# 0008 — The assistant never types a number

| | |
|---|---|
| Status | Accepted, 2026-11-11 |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Record why the model plans and narrates but every number on screen is rendered by the application from a governed fact. |
| Read first | [09_AI_ASSISTANT.md](../09_AI_ASSISTANT.md), [02_ARCHITECTURE.md](../02_ARCHITECTURE.md) |

## Context

- Owner decision 7: AI is required and may be an online model. The API key arrives later, so the product must work fully without a model.
- A model that writes figures can write a wrong one, or one that is not in the release. One invented number on a wall screen discredits every real one beside it.
- Assistants over maps are already common. An assistant is not what makes this product different; a structural guarantee can be.

## Decision

1. The model plans with at most nine typed tools over the fixed release and receives tool results only.
2. Evidence lands on screen before words: a playbook fetches the facts first.
3. The application, not the model, renders every number. In version 1 no model-written prose reaches the screen: the model outputs only approved text-fragment keys, claim keys and fact references, and quantitative statements are prepared fragments containing fact slots. The Fact chip is the only component allowed to render a numeral.
4. A validator checks every brief item against its claim definition in the versioned claim catalogue (`product/assistant/catalogue/claims.yaml`): the fact in each slot must match the slot's metric key, unit, geography role, period rule and allowed provenance; every required slot is filled; no extra slot. One invalid item rejects the brief; after one repair attempt the template writer composes the brief from the playbook's default selection. Sentence templates are scanned at build time (no numerals, no number words, no names of real places inside `area` claims, no go or no-go wording), and a lint rule forbids numerals outside the Fact chip in the front end.
5. The application chooses the refusal or caveat template from the tool status: `OK`, `SUPPRESSED`, `NO_DATA` or `OUT_OF_SCOPE`.
6. Without a model, a template writer produces the same brief from the same facts. A model failure or refusal falls through to it.
7. There are no model-written queries (text-to-SQL or text-to-Cypher), no web tool, and no tool that sends data anywhere.

## Evidence

- Claude API reference bundled with Claude Code (model table cached 2026-11-03, read 2026-11-11): on `claude-opus-5-5` thinking cannot be switched off, a forced tool choice returns an error, sampling parameters are rejected, and a `refusal` stop reason exists. Neither grounding nor repeatability can therefore come from model settings. Both are enforced in code and by a memo.
- Engineering judge (2026-11-11): a digit validator as first written would miss Arabic-Indic digits and spelled-out numbers, and would fire on times, activity codes and distances unless those are rendered as fact chips too. Decisions 3 and 4 close both gaps.
- AI-patterns research (2026-11-11): in a published benchmark of April 2026 (small, and written by a vendor) a governed query layer scored above free text-to-SQL, and its failures were error messages, not plausible wrong answers. Free-form queries also let a model compose arbitrary filters, which is the subtraction attack surface.
- Same research, from the provider's documentation: structured output is schema-valid except on refusal or truncation, and it cannot be combined with citations. Hence numbers by reference with a validator, and not citations.
- The judges' reading of published descriptions (2026-11-11): assistants already exist in this market, so an assistant by itself earns nothing.
- slice S8 gates, which are targets and not results: zero unreferenced digits in 500 generated briefs — 500 distinct structured briefs returned by the model before repair or fallback, with every fallback counted and reported and template output not counted as a model-written brief; the must-decline set at 100%; an injection suite with zero successes; the golden set passing five runs out of five.

## Consequences

- Arabic and English show identical numbers, because the prose of neither language contains one.
- The model may select and order different claims when an answer is regenerated. The wording of each claim comes from its template, and numbers cannot change.
- Times, codes and distances must also be facts. This is extra work in the tools and the front end.
- Latency is managed by playbooks that fetch evidence first, not by model settings.
- The product is whole without a key (open item OI-01): the template writer and a recorded provider serve until the key exists.
- The typed-decision gateway of [0014](0014-typed-decision-gateway.md) may, in the offline evaluation harness, add a brief to the human review sample. It never changes a brief, refusal, tool call or runtime output. It never renders, selects or approves a number, and it does not replace the validator.

## What would change this decision

- Nothing short of the owner giving up "proof on every number".
- A different model, or a local model (backlog item L7), must pass the same evaluation set before use. The rule does not change with the model.
- A tool server over the same governed tools (backlog item L6) keeps the rule: tools return facts.

## Open questions and assumptions

- OI-01: API key and spend cap are deferred by the owner. Live-model gates run when the key exists.
- This record makes no ASSUMPTION. API statements are verified in document 09; builders must read the current official documentation first.

## Sources

- Anthropic, Claude API reference bundled with Claude Code (the `claude-api` skill; model table cached 2026-11-03), read 2026-11-11.
- Anthropic, structured outputs page, https://platform.claude.com/docs/en/build-with-claude/structured-outputs ; retrieved by the research on 2026-11-11.
- dbt Labs, blog post on a semantic layer against text-to-SQL, https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026 ; retrieved by the research on 2026-11-11.
- EII AI-patterns research, engineering-and-delivery-risk judgement and feasibility-and-cost judgement, 2026-11-11 (project records held by the owner).
