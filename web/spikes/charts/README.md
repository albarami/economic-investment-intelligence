# Chart integration spike — part one

Authority: TASKS.md S6-T34, decision 0042 items 2, 8, 9 and 13,
document 10 section 12, approved PLAN-S6-T34 and lead ruling L-974.
No production import, chart adoption or native-performance pass is claimed.

## Pre-run contract

`contract.json` freezes the approved budgets; `fixtures/profiles.json` holds
invented renderer coordinates only, with no real subject or economic claim.
Cardinalities remain proposals under L-974(d), not owner-approved workloads.
`workload.ts` gives all adapters the same closed fixture and selection keys.
Comparison has two panels; the range case has lower and upper boundary lines.
No range is calculated by an economic model. There is no model call.

The adapters disable numeric labels and axes. They are build-measurement inputs,
not mounted by the page. The bilingual page renders only a blocked message.
No second Fact chip family is created. Governance descriptor tests do not certify
actual DOM accessibility, actual lineage or shared Fact-chip enforcement.

## Offline commands

From `web/`, run `npm run test:spike:charts`, `npm run spike:charts:build`
and `npm run spike:charts:measure`. Measurement uses pinned Vite, minified ES
library output, all emitted asset bytes, gzip level 9 and Brotli quality 11.
`evidence/bundle.json` records absolute emitted bytes and empty-shell deltas.
Every variant uses benchmark.tsx as the same React shell, with only the renderer import changed; the empty variant supplies a no-op renderer. These are export-preserving common-shell measurements, not integrated product bundle costs. No arbitrary size or parse cutoff is invented.

`npm run spike:charts:serve` serves optimized blocked-page output on loopback.
It does not accept uploads or write native traces. `npm run
spike:charts:verify-evidence` exits nonzero until a reviewed native protocol and
full matrix exist. `recorder.ts` refuses collection rather than recording idle
animation frames as completed chart renders. Native measurement remains blocked.

## Guards and limits

`guards.node-test.mjs` plants each forbidden input before the render callback,
missing table/description, mismatched facts, numeral bypass, both non-Western
digit ranges, parity mismatch, absent lineage and origin texture. Its positive
view is an invented descriptor, not an application Fact or DOM.
`isolation.node-test.mjs` traverses actual product static imports/re-exports and
literal dynamic imports, rejects nonliteral dynamic imports, and plants all three
edge forms. Existing import-boundary checks remain unchanged.
`trace.node-test.mjs` tests the timing policy against invented raw samples and
missing/malformed/stale/forged/headless/stopped evidence, strict latency/rate
boundaries, frame, transition and full-story memory limits. `judge` is explicitly
a policy unit checker, not capture authentication. No exported evidence checker
accepts these invented controls as native evidence.

## Owner and lead handoff

Before recording: merge the S3 Fact family, confirm fixture cardinalities and
selection protocol, approve paint/parse/memory instrumentation and phone OS,
browser and on-device loopback or USB forwarding. Never silently bind LAN.
The offline matrix validator binds capture digests, device/browser/viewport and owner attestation; it checks every matrix cell. The CLI still refuses native qualification. Then integrate validated capture collection, build/lock/contract/fixture
identity and matrix completeness: every library, chart, language and device,
three runs, twenty warmups, two hundred selections, at least thirty seconds of
completed playback. Record every run with no favourable-run selection.

Recompute nearest-rank p95 strictly below 100 ms and completed-render rate
strictly above 30 fps; reject any hourly frame above 33 ms and crossfade above
800 ms. Full-story memory must remain below 50 MB over three loops; chart-only
loops cannot satisfy it. The unchanged S1 wall-canvas orbit gate remains separate.
All missing evidence stays BLOCKED. ECharts remains the designated baseline,
without an unearned pass; Plot and visx are not adopted.

## Package reading

READ, 2026-11-18: package README at version 6.1.0 for `echarts`,
package README at version 0.6.18 for `@observablehq/plot`, and package README
at version 4.0.0 for `@visx/shape`, `@visx/scale`, `@visx/group`, installed
under `web/node_modules/`. ECharts `package.README.md` Public and private and
TypeScript entries were also read: selective core/charts/components/renderers
entries are exported. Its type declarations expose init, setOption and dispose;
the spike uses them for a fixed application-owned line chart, disables axes,
labels and tooltips, and disposes the chart on cleanup.

Plot `src/index.d.ts` and `src/plot.d.ts` describe plot dimensions, marks and
scales. The adapter uses plot and line, fixed domains, suppressed axes and no
tips. Installed Plot's exports do not expose its declarations to bundler-mode
TypeScript here (observed build exit 2); spike tsconfig maps only its type
specifier to that same installed package's `src/index.d.ts`. Runtime resolution
is unchanged. No ambient-any declaration or dependency upgrade is used.

visx package index declarations, shape `LinePath.d.ts`/`Area.d.ts`, scale
`linear.d.ts` and group `Group.d.ts` were read. LinePath renders application-owned
points; scaleLinear maps fixed domains to pixels; Group wraps SVG marks. No
numeric label is generated by these adapters. These are renderer-coordinate
transforms, not economic calculations. The packages ship no changelog found by
the package-local changelog search; no online release-note reading is claimed.

Pins and retreats follow lead ruling L-974(a), recorded in pins.toml. Retreats
were not exercised. Publisher web-page reading remains a lead open item under
L-974(b); local package reading does not claim that step passed. Native parse,
heap, device latency and visual accessibility remain blocked. Sources: TASKS.md
S6-T34; decision 0042 items 2, 8 and 9; document 10 section 12; installed package
files named above. No network was used by this task.
