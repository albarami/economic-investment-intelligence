# Offline typed-decision gateway

`eii_gateway` is the fourth Python workspace member. It has no third-party runtime
dependency. Only tooling under `scripts/` and `evals/` may consume it. There is no
serving integration, application decision table or screen output.

## Contract

`Gateway(repository_root).decide(Request(...))` accepts tooling-owned inputs and
returns decision evidence in the closed [DAT-126 schema](../docs/03_DATA_CONTRACTS.md#121-offline-typed-decision-records-not-an-application-table).
Every admitted call writes a JSON file under `evals/typed_decisions/runs/`, including
memo replays, disabled and unavailable outcomes. Raw input text, credentials and
provider exception text are never written. Tests use temporary repository roots
from `tempfile` with the launcher's environment.

The five classes and effects follow [decision 0014, item 4](../docs/decisions/0014-typed-decision-gateway.md#decision).
`brief_second_reader` only adds human review work. `question_route` is shadow
recording; `string_parity` is experimental recording. There is no operation that
clears a gate, removes an item from human review, supplies a fact, changes a tool
argument or approves a mapping or Arabic text.

Data policy checks the declared class before provider construction or persistence.
Only `public`, `synthetic`, `project_text` and `team_question` are admitted.
Router questions require `team_question`; parity requires `project_text`.
Other declarations raise `DataPolicyBlocked("BLOCKED_BY_DATA_POLICY")` without
serialising their content. The caller is responsible for truthful classification;
this is not a classifier that detects real data disguised as synthetic input.
Rejected declarations cannot be stored in DAT-126 because its `input_class` field
admits only the four cleared classes. A refused request is therefore not a call and
leaves no record; this reading is open item OI-117 of [OPEN_ITEMS.md](../OPEN_ITEMS.md)
for the owner.

## Providers and replay

`EII_DECISION_PROVIDER` defaults to `none`. This provider neither opens sockets nor
reads `JEV_PRO_API_KEY`, and returns `DISABLED` with fallback. It imports no configured
HTTP adapter. `recorded` requires an explicit fixture file; the tiny fixtures under
`scripts/tests/gateway/fixtures/recorded/` are hand-authored synthetic examples,
not live measurements or qualification evidence.

Memo keys include the decision class, rubric hash, normalised input and request
context, model identifier and adapter version. The first persisted answer stands.
Choice requests run in an input-hash-derived order and its reverse; both labels and
both confidence cutoffs must agree. Ranking signals are private decision evidence,
never probabilities or facts. Since no supported effect removes an item from human
view, only the ordering/flagging thresholds of decision 0014 item 6 apply.

The `jev` adapter follows the provider's public API reference as read by the lead
on 2026-11-13: the body contains exactly `model`, `state` and `questions`, and the
reply supplies `model`, `answers.decision` and `usage.input_tokens` plus
`usage.output_tokens`; the adapter cuts the yes/no label at weight 0.5.
It accepts only rubric form 1, never retries or follows redirects, uses a
30-second timeout, and refuses a call when the remaining token limit is below
the encoded body's byte count; that cap guard is not a guarantee, and the
unchanged gateway checks actual usage after the call.
The caller supplies the address, kept out of the repository by the owner's
instruction; no default test or command calls the service, loopback tests import
the adapter only within their explicit test boundary, and the keyed run is made
by the lead alone under the owner's answer to OI-18.

The adapter reads `JEV_PRO_API_KEY` only from the environment after explicit
provider selection; the default zero cap permits no configured-provider call.
No key or live call was used for S1-T07 or this wire-shape pass.

## Validation

The existing `scripts/tests` suite discovers the gateway contract tests and the new
consumer guard. The original three-plane import and environment guards remain in
force. Workspace metadata and clean-install guards include the fourth member;
`./eii test` gains no suite. Use the repository's standard test, lint and type-check
commands; [PROGRESS.md](../PROGRESS.md) records the observed results.
