# 0056 — S6-T33 catalogue and transport spike result

| | |
|---|---|
| Status | Proposed |
| Date | 2026-11-18 |
| Owner | The owner |
| Purpose | Record offline part-1 measurements and retain the native baseline pending missing evidence. |
| Read first | TASKS.md S6-T33; document 14 slice S6; decision 0042 items 4–6, 8, 9 and 13; document 09 AI-35, AI-36, AI-46, AI-48–50 |

## Context

The approved plan and lead ruling L-974 authorize an isolated offline spike.
This is an implementation proposal, not independent approval or a production
integration. The lead confirms the proposed decision number before merge.
The supplied exact dependency pins and lock are retained; retreats were not run.
Publisher web-page reading remains open for the lead under L-974.

## Proposed result

Retain native alone. L-974 requires that every criterion pass and that a retained
adapter remove code; otherwise native remains. Missing evidence is BLOCKED, never
PASS. No runtime dependency enters the critical path. No requirement, threshold,
privacy check, attack size, tolerance or release gate is relaxed.

## Measured offline evidence

Source: [frozen contract](../../web/spikes/catalogue/contract.json),
[input manifest](../../web/spikes/catalogue/fixtures/manifest.json),
[results](../../web/spikes/catalogue/evidence/results.json) and
[source checksums](../../web/spikes/catalogue/evidence/checksums.json).
The original corpus is unchanged. A separately hashed supplement adds a valid
two-slot control and a symmetric fact swap; its expected refusals were fixed
before the supplement ran. No threshold changed. See the
[paired manifest](../../web/spikes/catalogue/fixtures/paired-manifest.json).
Every fact in this section is an invented-fixture harness measurement, not a
statement about public or custodian data. Randomness: none. Provider: none.

The frozen corpus contains 31 cases per candidate. Each candidate has identical canonical case coverage and lossless envelopes. Native and json-render produce application-owned, number-free server markup for valid controls; invalid briefs obtain no dispatch receipt. A2UI runtime rendering is BLOCKED: its Node import raises `HTMLElement is not defined`.

- native: 18264 envelope byte-cut positions, 1787 authorized control commits, 0 premature sink commits and 0 stale sink commits. These are harness results; browser transient exposure remains BLOCKED.
- a2ui: 21279 envelope byte-cut positions, 2078 authorized control commits, 0 premature sink commits and 0 stale sink commits. These are harness results; browser transient exposure remains BLOCKED.
- json-render: 20752 envelope byte-cut positions, 2027 authorized control commits, 0 premature sink commits and 0 stale sink commits. These are harness results; browser transient exposure remains BLOCKED.

Maintained nonblank/noncomment source lines, using the frozen file list and convention in `count-lines.mjs`:

- shared: 412 lines; maintained flag `true`.
- native: 18 lines; maintained flag `true`.
- a2ui: 21 lines; maintained flag `true`.
- json-render: 27 lines; maintained flag `true`.
- plain-events: 5 lines; maintained flag `true`.
- ag-ui: 21 lines; maintained flag `true`.
- harness: 750 lines; maintained flag `true`.
- tests: 547 lines; maintained flag `true`.
- generated: 1947 lines; maintained flag `false`.
- vendor: 0 lines; maintained flag `false`.

The recorder observed 0 network attempts under the network sink guard. Both plain and AG-UI CUSTOM envelopes accept normal events and reject malformed, duplicate, reordered and late events; interrupted runs cancel without a commit. Recorded conversations show validated same-facts template fallback for invalid repair, refusal, max_tokens, API error and timeout.

## Acceptance status

- **PASS — predeclare_identical_fixtures**: contract and fixture hashes; all candidates have every canonical envelope case.
- **BLOCKED — zero_unauthorized_output**: oracle and dispatch sinks pass plants; native/json-render server markup only, A2UI and live DOM/accessibility/render commits need browser.
- **BLOCKED — interrupted_streams**: every-byte harness commits and cancellation pass; transient browser observation pending.
- **PASS — shared_dispatcher**: story, explore, assistant are the same entry function; equal corpus logs; forged receipt rejected.
- **BLOCKED — versions_severity_activation**: version/severity/host activation seam plants pass; real same-turn user event proof pending.
- **PASS — closed_schema_slots**: existing check_brief bridge; each invalid case has exact rule/path and valid control.
- **PASS — repair_fallback**: append-only recorded turns, one repair, invalid repair and terminal statuses use validated same-facts template.
- **BLOCKED — withheld_unchanged_controls**: withheld wording, full source-chain and companion plants pass; numeric Fact chip display absent, production accounting gate not claimed.
- **PASS — transport_comparison**: frozen line lists plus both transports over every failure mode; these are CUSTOM-envelope harness events only.
- **BLOCKED — decision_isolation**: native retained and import/evidence guards pass; lead confirms Proposed decision number and different-maker review.

## Limits and follow-up

The envelopes preserve the canonical brief rather than implementing every
candidate wire grammar. AG-UI measures its CUSTOM envelope, not its full event
lifecycle API. No full A2UI surface, live browser DOM/accessibility/render-commit
trace or numeric Fact-chip rendering was measured. The dispatcher activation
positive control is a host seam, not a real browser user event. Supplementary
accounting in the bridge is limited to the declared fixture context; it does not
complete the production accounting gate.

The lead must obtain official publisher-page reading, authorize the browser
provisioning/path for a full renderer run, arrange application Fact-chip
integration, and obtain an independent different-maker implementation verdict.
No owner device run is required by this task; optional inspection is not a gate.
The whole repository test and ledger/open-item numbering remain with the lead.
No adoption claim follows from this proposed partial result.
