# S3-T10 implementation audit

Maker/model: OpenAI / Codex, GPT-6 family. Builder persona: senior bilingual
frontend engineer. Strict self-review persona: principal design, accessibility
and data-visualisation reviewer. This is a builder's self-review; another maker's
independent audit and native Arabic approval have not occurred.

## Verdict

REJECTED for slice-gate readiness. The implementation is handed over for review,
with the opening-chip criterion unmet and the independent and native reviews
waiting. Automated fixture results do not establish the live-release gate.

## Scope and source of evidence

The approved S3-T10 plan revision 3 and ruling L-1136 govern this implementation.
Requirements are TASKS **S3-T10**, document 11 **Design audit gates**, document 12
**TST-90**, document 15, and document 14 **slice S3**. The capture index is
`matrix.json`; commands, actual exits and negative proofs are in `checks.txt`.

The browser serves a built production bundle through the actual application and
its typed routes. Its complete invented Public-only release is checked and
loaded through the existing loader into the embedded store. Its other loader
connection is a recording test connection, not a running second store. Local
invented map, glyph and routing fixtures are used. These captures establish
layout and route behaviour on that fixture, not geographic completeness, native
label quality, or live two-store parity. No API or lineage response is intercepted
or replaced in the success path.

## Checks and acceptance limits

- Opening: quiet map, application-owned question, working Guided story and Site
  choice. Only the currently provided journey is offered. The unavailable
  electricity sentence is a catalogue fragment; no proxy value is displayed.
- Layout: the capture matrix covers the specified portrait and landscape sizes,
  both languages and both themes, at opening, area, answer, comparison, evidence
  and source drawer. Separate wall captures use greyscale and reduced motion.
  Drawing controls sit in the stage at its inline start. Native disclosures keep
  map and evidence controls compact, with scrollable content on short screens.
- Accessibility: automated checks cover opening visibility, overflow, targeted
  copy clipping, Arabic leading, reading direction, unmirrored stage, contrast
  and target size. Keyboard drawer close restores the originating Fact chip's
  focus; the language control has a visible focus indication. These checks do
  not certify every accessibility requirement or replace human inspection.
- Facts: existing Fact-chip and context-card components render the returned
  values, reference dates, comparison and evidence levels. Registry identity is
  shared across levels and language changes. Missing chains refuse rendering.
  Withheld negative fixtures retain their reason and lock and reveal no value.
- Interaction: named areas, polygon vertex selection and tap destination,
  distance, walk and drive preserve the selected typed request. Camera buttons
  provide pan, zoom and home without a drag. The existing RTL plugin remains.
  Reset clears cards, selections, outline, drawer, map mode, clock input and
  land-use selection. Delayed work cannot repopulate a reset story.
- The drawer title remains "Source chain" in both languages, as DES-95 requires;
  its proposed Arabic title is not silently approved or substituted.
- Fonts: the first application frame waits for both bundled interface scripts
  and shipped weights. Missing faces display an application-owned unavailable
  message. Pins, retreat pins and visual baselines are unchanged.
- Public context: mounted tests cover radiance, relative busyness and population
  cards. Busyness has its retrieval date and relative-busyness caveat, never a
  people estimate. Source geometry and class breaks use the existing readers and
  renderers. The firms layer's missing-input path is tested; a successful firms
  chain through the production release mount remains unproved.

## Findings and required follow-up

- **Major / opening evidence, DES-132 and S3-T10 first-screen criterion.**
  `web/src/journeys/PublicOpening.tsx:38`, the
  `opening_electricity_unavailable` fragment mount: the dated opening Fact chip
  is absent. This is the required refusal under L-1136 C3: the current layer's
  `ranked_ratio` is not an approved Scene 0 growth fact. Exact fix: the lead must
  confirm or provide the fact identity, period and wording, then bind that
  verified fact and its date through the existing Fact-chip family and test both
  languages. Do not substitute another metric. Retest: opening browser and full
  capture matrix. **Waiting; no criterion tick.**
- **Waiting / firms success path, S3-T10 Public layers criterion.**
  `product/src/eii_product/api/app.py:131`, `mounted_layer`, and
  `product/src/eii_product/api/layers.py:146`, `get_layer`: the special firms route
  is outside the ordinary mounted-layer readers. Code inspection therefore does
  not establish that a successful response is registered for the production
  fact-chain endpoint. Exact next step: the lead assigns or confirms its owning
  backend task and supplies a complete invented loaded-register fixture with a
  successful fact-chain read. Reuse the existing layer and chain checks; never
  invent a browser registry or weaken chain validation. **Unproved.**
- **Waiting / DES-41 and OI-09.** New Arabic control strings carry pending native
  review metadata. Obtain native copy and map-label approval, then record the
  independent maker's audit on the exact reviewed head. No native approval is
  inferred from automated direction, font or clipping checks.
- **Waiting / slice S3 gate.** Lead-owned real-release load receipts, live
  two-store query parity, configured preflight, exact-head reviews, hosted checks
  and fresh-seed whole-test evidence are outside this worker run. The brief
  forbids this worker from running the whole test. Prior stack evidence is not
  evidence for this changed head.

No baseline was refreshed. No timeout, retry, skip, assertion tolerance, security
rule or privacy rule was relaxed. Earlier failures remain in the check record,
with causal fixes or their stated unverified limits.


## Review round one correction record

The builder self-review above is historical. The supplied other-maker design
review, Anthropic / Claude Fable 5.2, reviewed
fe47090b1b9d17ba9011bc8497ebf3f1e396c1be and returned REJECTED for F1 to F8
and A1 to A6. The supplied review is identified in the appended S3-T10 block in
PROGRESS; its verdict does not approve the repaired tree. Native Arabic approval
(OI-09) and the Arabic Source chain title review (DES-95) remain separate.

Correction to the earlier Accessibility entry: the contrast check reads DOM
backgrounds only; text drawn over the map canvas, the attribution included,
was not measured against its pixels. The repair gives the attribution its own
opaque surface and adds it to that same audit. Measured contrast is
9.960669285697975 in dark and 14.691199565465228 in light. A transparent plate
fails. These measurements describe the plate, not arbitrary map pixels.

The Arabic radiance caveat now begins with Arabic. Source chips use inline-start
alignment; selection captions and the layer picker's distinct name are present;
boundaries wording is inside the selection disclosure; refused layers are
unavailable alerts. The withheld state retains its lock, reason and reference
period without a separate empty value box. Both existing zero/empty plants
remain unchanged and fail at their intended post-corruption assertion.

Fresh captures, contrast measurements, exact source-removal records, command
exits and the repair's review record are kept in the adjacent fix1 evidence.
Earlier captures and baselines are preserved. The dated opening chip, successful
firms chain, native Arabic approval and lead-owned slice-gate evidence remain
waiting; no independent approval is inferred from this self-review.


A further capture inspection found the reused compact marker size wrapping the
withheld word over its reason. The context disclosure now uses the marker's
intrinsic size. A new browser assertion in the existing negative-context case
first failed with a word height of 48 against a line height of 24, then passed
for every existing language/theme/size variant after the correction. The
pre-correction captures remain in the command evidence; fresh captures show the
complete lock and word above the reason. No existing assertion was removed.


The phone credit capture also exposed the selected-area outline painting above
the plate. The credits now use the existing tools stacking token. A new matrix
assertion requires their computed level above the area overlay; the Arabic
phone case failed before the change. The pre-correction captures and source
snapshot are retained, and the final matrix is recaptured after this repair.


The final unchanged-source local aggregate exits zero with 1158 passed and no
failures or skips. Its S3-T10 browser wrapper includes the stacking assertion,
all matrix cells and both story languages. The final packet has 298 indexed
captures and 48 contrast records; every delivered hash verifies. One incidental
compressed-byte collision is resolved by lossless level-nine encoding with
identical decoded scanlines and other chunks, as recorded in the index. This
remains builder evidence; the independent/native and lead gate items above stay
waiting.
