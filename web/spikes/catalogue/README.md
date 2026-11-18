# S6-T33 — Offline catalogue enforcement spike, part 1

Builder: OpenAI GPT-6 Codex, senior frontend architect for measured technology
spikes. Later reviewer: strict design and code reviewer for frontend spikes,
from another maker; independent review is not claimed.

Authority: TASKS.md S6-T33; document 14 slice S6; decision 0042 items 4–6,
8, 9 and 13; document 09 AI-35, AI-36, AI-46, AI-48–50; approved plan and
lead ruling L-974 supplied in the workspace brief.

## Run and inspect

From `web/`, use `npm run test:spike:catalogue`,
`npm run spike:catalogue:record` and `npm run spike:catalogue:verify-evidence`.
The first command type-checks this isolated spike, runs its guard tests and
checks existing evidence without updating it. Recording is an explicit separate
operation. No network, model, database, random seed or data cache is required.
The launcher confines these commands to its assigned processor affinity.

`contract.json` and `fixtures/manifest.json` freeze the acceptance contract and
invented inputs. All candidates losslessly wrap the exact same `raw` brief
bytes from `fixtures/cases.json`. A separately frozen `fixtures/paired-manifest.json` adds a genuine two-slot
symmetric swap and its valid control without changing the original corpus or
thresholds. The fixture builder reuses the S3-T07 test
builders and shipped catalogue foundation files; it does not populate production
claims. `oracle.py` calls the existing `load_catalogue` and `check_brief` for
each submitted brief. Additional spike-only source-chain, assumption, scope,
limit and companion checks are explicit; these are not the future production
accounting gate. Fictional source-chain strings assert nothing about public data.

## Boundaries and evidence

One dispatcher owns opaque, single-use receipts. Story, Explore and assistant
are aliases of the same harness entry. Rejected briefs obtain no receipt.
Only application-owned note wording reaches the native or json-render server
renderer. Actual numeric Fact-chip output is BLOCKED; no replacement chip family
is defined. Withheld results show a number-free application-owned reason.

`stream.ts` buffers bytes until explicit completion, then waits for accounting.
Cancellation invalidates the pending commit even if the validator returns later.
Every envelope is split at every byte boundary, completed, interrupted, cancelled
and sent late chunks in `scenarios.mjs`. These are harness sink observations,
not a browser render-commit or accessibility trace. The repair controller records
one appended request, verifies preserved turns, and validates the same-facts
fallback after invalid repair or terminal provider status. There is no provider
call; statuses are invented replay inputs.

Side-effect activation is single-use and expires at the microtask boundary.
The positive control uses an application-injected host seam; a forged payload
does not grant activation. A real browser user-event/lifetime proof remains
BLOCKED, and the harness is not a production integration.

A2UI's Node import raises `HTMLElement is not defined`. Its runtime entry is
kept separate, type-checked and explicitly BLOCKED. No browser or DOM substitute
is supplied. The A2UI and json-render buffer envelopes do not claim to implement
their full wire grammars. The json-render renderer receives only an application-
constructed constant spec, never model fields, expressions, query strings,
watchers or action bindings. Its provider supplies contexts but no application
action handlers. Server markup only is recorded.

AG-UI uses its actual CUSTOM event schema around the same closed EII event as
plain events. The shared machine checks keys, sequence, run identity and terminal
state. This measures CUSTOM envelope overhead and the declared failure modes;
it does not exercise every AG-UI event family. `count-lines.mjs` fixes the file
list and reports shared, candidate, harness, tests, generated and vendor groups.
TypeScript scanner token lines exclude whitespace/comments. Python excludes
blank/comment lines and counts string literals as code. No numeric advantage
threshold was added.

`evidence/results.json` holds every fixture outcome, rule/path, sink timeline,
server markup, stream cut counts, fallback conversation, failure matrix and LOC.
`evidence/checksums.json` covers maintained sources, the input manifest, the
existing S3 validator, package manifest and supplied lock. Missing or mismatched
files fail verification. Frozen inputs and generated evidence are excluded only
from formatting to preserve byte hashes; all other checks still apply. A
formatting pass briefly touched inputs before recording; the original pre-run
hashes were restored and verified byte-for-byte before evidence was generated.

The import graph test scans every production script under `web/src`, follows
extensionless relative edges, and plants direct/transitive spike imports and a
nonliteral path. Nothing under production imports this runtime.

## Result and open evidence

Keep native. L-974 permits retention only when every criterion passes and an
adapter removes code. Browser DOM/accessibility/transient exposure, full A2UI
surface execution, application Fact chips, real user activation, official
publisher web-page reading and different-maker implementation review remain
BLOCKED. No owner device run is required by S6-T33. Decision 0056 is Proposed;
the lead confirms its number and runs the whole repository test. See
`docs/decisions/0056-catalogue-and-transport-spike-result.md` from the repository
root. No production dependency, threshold, privacy rule or gate is changed.

Skills applied: project-orientation, task-standards, github-flow,
sanad-provenance, muhasabah-gate. Test-driven-development and
verification-before-completion are unavailable by those installed names; their
plain meanings are applied through red tests, planted violations, positive
controls, real exits and a final evidence audit. No commit is made by this build.
