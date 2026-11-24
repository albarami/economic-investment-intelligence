# S3-T10 repair evidence

Builder: OpenAI / Codex, GPT-6 family. This packet records scoped fixes and
fixture verification; it is not native, independent-maker, live-parity or
slice-gate approval.

- `review-record.md`: supplied historical reviews and their limits.
- `guard-removals/manifest.json`: 26 one-at-a-time removals covering the
  20 requested guard IDs and the worker recorder assertion, their exact
  edits, commands, exits, deciding assertions and restored source hashes.
- `ui-removals/manifest.json`: 18 individual UI/copy reversions and assertion
  failures. Browser and unit baselines pass before and after the primary batch;
  the two extra caption/scope probes restore bytes and the component group
  passes again.
- `withheld-layout-before/`: pre-correction captures of the marker-size defect,
  retained as red evidence. Current captures are indexed separately.
- `source-hashes.json`: implementation and test bytes held fixed through the
  final aggregate. PROGRESS and the final return identify the original head.

Each negative command exits one for the named assertion failure. Restored
baselines exit zero; deselected Python cases are reported separately from
skips. No timeout, setup failure or interrupted run is counted as a kill.
The remaining previously killed guards in lens B's table were not removed
again here; their assertions remain in the passing ordinary suites.

Paths in distributable diagnostics are redacted. Assertions, actual exits and
counts are retained. The custom probes follow the brief's closed removal list;
no general mutation campaign or overall test-adequacy claim is made.

The final command ledger, capture index and contrast reports are packaged after
the full aggregate finishes. Earlier failed commands remain in that ledger.


Final packet: `commands.json`, `checks/`, `matrix.json`, `contrast.json` and
`captures/` now contain the completed evidence. The exact final aggregate exits
zero with 1158 passed, no failed/cancelled/skipped/todo cases. The frozen source
hashes remain unchanged through it. The command note that anticipated RLE as the
final encoding was an intermediate attempt; it failed and was superseded by the
later documented decoding-view correction and fixed level-nine delivery. No
original evidence row is rewritten. The final index records the actual storage
method and byte-equality proofs.
