# 10 — Front End

| | |
|---|---|
| Status | Draft v0.2, corrected after independent review on 2026-11-11 (see PROGRESS.md) |
| Date | 2026-11-11 |
| Owner | albarami |
| Purpose | Tell a builder exactly how the browser application of the EII proof of concept is structured, what each component does, how the map draws provenance, and how the front end is tested. |
| Read first | [01 Project brief](01_PROJECT_BRIEF.md), [02 Architecture](02_ARCHITECTURE.md), [08 Back end](08_BACKEND.md), [09 AI assistant](09_AI_ASSISTANT.md), [11 Design direction](11_DESIGN_DIRECTION.md) |

## In brief

- The front end is one React 19 single-page application in `web/`, built with Vite 8 and served by the same FastAPI process as the API. Nothing is built yet; everything below is a requirement.
- The map is MapLibre GL JS 6 with deck.gl 9.4 interleaved on WebGL2, over a self-hosted PMTiles basemap with self-hosted Arabic glyphs. The page makes no third-party request at run time.
- Both map libraries are newer than most model training data. Builders read the current official documentation before writing map code.
- The Fact chip is the only component allowed to render a numeral. It refuses a fact without a complete source chain. A lint rule enforces the component boundary at build time and an automated provenance audit enforces it in the running page.
- Every displayed number and comparison comes from deterministic tested code in `eii_core.calc`, the release build, or a fixed application-schema read function listed by the data contracts and covered by tests. The browser formats returned values; it never calculates a displayed value.
- Brief sentences are application-owned bilingual claim templates filled with Fact chips. The assistant selects structured claim and component keys; no model-written prose reaches the screen.
- Provenance is shown by texture and line style as well as by word: solid = Public, dotted = Synthetic, moving dashes = Simulated, grey hatch with a lock = Suppressed. One hero layer is shown at a time. A watermark is drawn into the canvas and every export.
- Arabic mirrors the chrome and reading order, not the map, charts, numerals or the dial. Digits are Western in both languages.
- Visual tokens, motion, typography sizes and the storyboard are owned by [11 Design direction](11_DESIGN_DIRECTION.md). This document links to them and does not restate them.

## 1. Scope and boundaries

This document covers the browser application only. Other documents own neighbouring concerns:

| Concern | Owner |
|---|---|
| API routes, server-sent event names and payloads, seat sessions | [08 Back end](08_BACKEND.md) |
| What the assistant sends, the nine tools, refusal and caveat templates | [09 AI assistant](09_AI_ASSISTANT.md) |
| Colours, textures, type scale, motion durations, icons, storyboard per step | [11 Design direction](11_DESIGN_DIRECTION.md) |
| Fact object fields and release tables | [03 Data contracts](03_DATA_CONTRACTS.md) |
| Privacy rules and suppression reasons | [06 Privacy and disclosure control](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) |
| Break-even, overlap and pay-decomposition formulas | [07 Economic methods](07_ECONOMIC_METHODS.md) |
| Test strategy across the repository, CI | [12 Testing and quality](12_TESTING_AND_QUALITY.md) |
| Start-up, presenter machine, rehearsals | [13 Deployment and operations](13_DEPLOYMENT_AND_OPERATIONS.md), [16 Demo runbook](16_DEMO_RUNBOOK.md) |

Where this document names an API path or event name, it is the front end's expectation. If [08 Back end](08_BACKEND.md) defines a different name, 08 wins and the front-end client is changed to match.

Two code families share the letter S. Capability references are always written "capability M1" to "capability M8" or "capability S1" to "capability S11". Build references are always written "slice S0" to "slice S11".

The front end never computes a statistic, comparison, rank, breakpoint or other displayed number, never rounds a released value differently, never chooses a refusal or caveat wording, and never holds record-level data. Every number is produced by a deterministic tested server function in `eii_core.calc` or by the release build. The break-even panel posts its inputs to that server method. The browser only formats returned facts.

The seat picker sets the signed `eii_seat` session cookie for the browser profile. The API reads the seat from that cookie, never from an address or request field. This is query isolation after a seat is chosen, not an account, identity system or tenant authentication. Presenter routes additionally require the per-session `X-EII-Presenter-Token`.

Run instructions use the pinned command boundaries: `./eii preflight` only probes and never starts or stops anything; `./eii db-up` and `./eii db-down` start and stop the database; `./eii up` never starts a database.

## 2. Stack and pins

The versions below are the latest releases found by the stack research on 2026-11-11. Exact pins are confirmed at the spike in slice S1 with written retreat pins, and recorded in `web/package.json` with exact versions (no `^` or `~`) and a committed lock file.

| Package | Pin (research, 2026-11-11) | Role | Licence |
|---|---|---|---|
| Node.js | 22 (22.12 or later; Vite 8 needs 20.19+ or 22.12+) | build tool runtime | MIT |
| `vite` | 8.3.x (8.3.8 latest) | bundler and dev server | MIT |
| `react`, `react-dom` | 19.3.1 | UI | MIT |
| `typescript` | pinned at slice S0 (not covered by the research) | types | Apache-2.0 |
| `maplibre-gl` | 6.17.0 | basemap, camera, building extrusion, label rendering | BSD-3-Clause |
| `@deck.gl/core`, `@deck.gl/layers`, `@deck.gl/geo-layers`, `@deck.gl/extensions`, `@deck.gl/maplibre` | 9.4.1 | data layers, interleaved through `MapLibreOverlay` | MIT |
| `pmtiles` | 4.5.0 | PMTiles protocol for MapLibre | BSD-3-Clause |
| `@protomaps/basemaps` | 5.7.2 | basemap style generated in code | BSD-3-Clause |
| `h3-js` | 4.5.0 | cell boundaries and outlines of released units | Apache-2.0 |
| `apache-arrow` | 21.2.0 | decoding layer payloads above about 10,000 rows | Apache-2.0 |
| IBM Plex Sans, IBM Plex Sans Arabic | pinned at slice S0 | interface fonts | SIL OFL 1.1 |

Retreat pins (stack research): `maplibre-gl` 5.x with `@mapbox/mapbox-gl-rtl-text` 0.3.0 for Arabic shaping, and deck.gl 9.3.12 with `@deck.gl/mapbox`. The last 5.x MapLibre version must be confirmed on npm before it is relied on. Retreat loses built-in Arabic shaping.

Not used in v1, with the reason:

| Not used | Reason |
|---|---|
| WebGPU in deck.gl | Not production-ready and cannot interleave with the basemap (deck.gl 9.4 notes) |
| deck.gl `GlobeView` | Experimental; the opening uses MapLibre's own projection if a globe shot is chosen in [11](11_DESIGN_DIRECTION.md) |
| Client-side aggregation layers (`HexagonLayer`, `HeatmapLayer`, `ScreenGridLayer`) and DuckDB-Wasm | Aggregation and suppression happen before release; the browser receives released aggregates only |
| terra-draw or any drawing library | Free-drawn areas are dropped; areas come only from a pin |
| `react-map-gl` | Mounting MapLibre imperatively in one component has fewer moving parts (stack research) |
| A charting library | Bars and the supplier lens are small SVG components so that every label goes through the Fact chip |
| Any CDN, hosted font, hosted tile or analytics service | Offline operation and the no-third-party rule (section 7) |

**Newer than most training data.** MapLibre GL JS 6 (released 22 July 2026) is ESM-only and WebGL2-only, removed `map.transform`, needs one worker-URL call under a bundler, throws an initialisation error when WebGL2 is missing, and since 6.9.0 shapes Arabic itself, which deprecates `setRTLTextPlugin`. deck.gl 9.4 (5 September 2026) added `@deck.gl/maplibre`. Coding agents default to v4 and v5 idioms (default imports, UMD script tags, `setRTLTextPlugin`, `MapboxOverlay` from `@deck.gl/mapbox`). Before writing map code, a builder reads the MapLibre v5-to-v6 migration guide, the MapLibre v6 API pages, the deck.gl "What's new" and `@deck.gl/maplibre` pages, and loads the MapLibre agent skills (`maplibre-v6-migration`, `maplibre-pmtiles-patterns`, `maplibre-fonts-glyphs`). No API in this document is to be taken as certain without that check.

| ID | Requirement | Slice |
|---|---|---|
| FE-01 | `web/package.json` lists every dependency with an exact version and the lock file is committed; CI fails on a range specifier. | slice S0 |
| FE-02 | `web/REFERENCE_NOTES.md` records, for MapLibre GL JS 6, deck.gl 9.4 and `@deck.gl/maplibre`, the documentation pages read, the date read, and the idioms that changed from earlier majors. | slice S0 |
| FE-03 | Each pin has a written retreat pin and the spike result that chose between them, recorded before slice S3 starts. | slice S1 |
| FE-04 | deck.gl runs on WebGL2 through `MapLibreOverlay` in interleaved mode; no code path enables WebGPU. | slice S1 |
| FE-05 | No dependency is loaded from a CDN; every script, style, font, glyph, sprite and tile is served by the local FastAPI process. | slice S0 |
| FE-06 | Versions are frozen for the demonstration by `./eii freeze`; after a freeze, changing `web/package.json` requires a new rehearsal. | slice S11 |

## 3. Application structure

### 3.1 Folders

```
web/
  package.json  package-lock.json  vite.config.ts  tsconfig.json  index.html
  eslint.config.js            flat config; loads the local eii rules
  eslint-rules/               custom rules and their RuleTester tests
  REFERENCE_NOTES.md          FE-02
  src/
    main.tsx                  boot: worker URL, PMTiles protocol, providers, router
    app/                      shell layout, router, route table, error boundaries
    state/                    store, slices, selectors
    api/                      typed REST client, SSE client, generated types
    facts/                    FactChip, formatters, NumericInput, fact registry, least-real check
    i18n/                     en.json, ar.json, t(), direction helpers, review status
    stage/                    map bootstrap, basemap style, layer registry, layers/, camera, watermark
    brief/                    Brief, PlanRail, catalogue renderer, AskBar, understanding chips
    cards/                    one folder per evidence card type (section 4.3)
    controls/                 Dial, SnapReport, PrivacyReceipt, CoverageBar, BreakEven, SupplierLens, NeighboursChips
    seats/                    SeatPicker, ViewingAsBadge
    rooms/                    TrustCentre, ProofRoom, Oversight
    story/                    StoryStepper, PresenterConsole, presenter channel, story script
    pack/                     BriefingPack print page
    shell/                    StandingStrip, ProvenanceLegend, Reset, status badges
    styles/                   tokens.css generated from the tokens of document 11; base styles
  tests/
    unit/  component/  e2e/  visual/  audit/  fixtures/
```

`web/` imports nothing from `custodian/`, `core/` or `product/`. Types for API payloads are generated from the FastAPI OpenAPI schema into `src/api/generated/` and CI fails when the generated file differs from a fresh generation (ASSUMPTION: generation keeps one source of truth for payload shapes; the generator is chosen and pinned at slice S0).

### 3.2 Routes

Every view has a URL, so a view can be shared within the session, reproduced in a test and restored after a reload. The language is the first path segment.

| Route | Screen | Seats allowed |
|---|---|---|
| `/{lang}/seat` | seat picker | before a seat is chosen |
| `/{lang}/` | home: ask bar, three journey cards, Stage | `company_a`, `company_b` |
| `/{lang}/brief/{brief_id}` | workspace: Stage, Brief, Plan rail | owner seat of the brief |
| `/{lang}/compare/{brief_id}/{brief_id}` | two doors side by side (capability S6) | owner seat of both |
| `/{lang}/story/{step}` | guided story, steps 0 to 7 (the eight scenes of the master story; storyboard in [11](11_DESIGN_DIRECTION.md)) | any |
| `/{lang}/trust` | Trust centre | any |
| `/{lang}/proof` | Proof room | any |
| `/{lang}/oversight` | Oversight screen (capability S4) | `oversight` |
| `/{lang}/pack/{brief_id}` | briefing pack page (capability S11) | owner seat of the brief |
| `/{lang}/presenter` | presenter console window | any, presenter mode only |

`{lang}` is `en` or `ar`; a bare `/` redirects to `EII_LANG_DEFAULT` as reported by the server. View state that is not a brief (pin, area mode and cut-off, dial position, summer switch, hero layer) is held in the query string. The router is an in-house component over the History API (ASSUMPTION: ten routes do not justify a routing dependency; replace with a pinned library if it grows past about 150 lines).

### 3.3 State management

One store holds application state; React components subscribe with `useSyncExternalStore` through selectors (ASSUMPTION: no state library in v1; a reducer and selectors are enough for one session per window).

| Slice | Holds | Written by |
|---|---|---|
| `session` | seat key from the signed session cookie, display name of the seat, language, presenter mode, release id | seat picker, router, `/api` config |
| `view` | pin, area request, hero layer, dial situation, summer switch, compare pair | user controls, `stage` directives, story |
| `brief` | answer id, brief id, lifecycle state, plan steps, facts by id, structured brief keys and slots, validated layout, receipt | SSE client |
| `story` | current step, prepared-run flag, controls locked or unlocked | stepper, presenter channel |
| `connectivity` | server reachable, model available or template writer, store `postgres` or `embedded`, oversight paused | health polling, SSE status events |

The camera is not React state. MapLibre owns the camera; the store receives a debounced camera summary for the URL and for `stage` directives. Layer data is passed to deck.gl by reference; changes of time or selection use update triggers or filter uniforms, not new data arrays (deck.gl performance guide: changing `data` rebuilds every buffer).

### 3.4 Data fetching

- One typed client in `src/api/` wraps every REST call; components never call `fetch` directly.
- Responses are cached per `release_id`. The release is immutable, so a cached response is valid until the release id changes; a change clears the cache and reloads the shell.
- Layers above about 10,000 rows travel as Arrow and smaller results as JSON (stack research recommendation). The client decodes Arrow off the main thread in a Web Worker.
- Every fact received is put into the fact registry (`src/facts/registry.ts`) keyed by `fact_id`. Components render facts by id from the registry, never from ad-hoc copies.
- Requests carry an abort signal; asking a new question aborts the previous answer connection.

### 3.5 Server-sent-event client

A question is posted to `/api/ask`, the server returns an `answer_id` and `events_url`, and the client opens one `EventSource` on `/api/answers/{answer_id}/events` (an `EventSource` cannot post). The oversight seat opens `/api/oversight/ledger/events`. The front end consumes the event names and payloads of [08 Back end](08_BACKEND.md):

| Event kind | Payload and effect on screen |
|---|---|
| `plan_step` | `{step_id, tool, label_en, label_ar, state}` adds or updates a Plan rail step |
| `stage` | one directive from the closed list (section 3.6) |
| `evidence` | `{card_id, kind, status, fact_ids, facts, caveat_keys, template_key}` registers facts; a component appears only after its instance validates |
| `narrative` | one structured brief item emitted only after the complete brief passes the accounting gate and the item validates: a `claim_key` with fact-id `slots`, or the pinned key and slots for another section; it carries no model-written prose |
| `withdrawn` | `{item_ids}` removes those rendered brief items before the repaired or template replacement appears |
| `receipt` | the privacy receipt, the accounting result and an egress summary |
| `status` | `{writer, status, template_key, note_key}` updates the writer and fallback state |
| `done` | `{answer_id, brief}` stores the completed brief and closes the stream |
| `error` | `{code, message_key, error_id}` shows the governed error and closes the stream |

Rules: the SSE `id` is the sequence number and is applied once, in order, keyed by `(answer_id, id)`. Browser reconnection resumes with the `Last-Event-ID` header; the client ignores duplicates. A structured brief item is held until the complete brief passes all five accounting checks and every slot fact is in the registry with a complete source chain. Evidence therefore reaches the screen before the application-owned claim template that cites it. On `withdrawn`, the named items are removed before their replacement is shown. On oversight `paused`, the screen shows Paused; on `resumed`, it shows the live ledger without a reload.

The completed brief contains structured data only: `catalogue_version`; `headline_key`; `decision_template_key`; `observed[]` and `inferred[]`, each item carrying `claim_key` and fact-id `slots`, with `strength` on inferred items; application-selected `still_to_test[]` and `not_measured[]`; `next_questions[]` carrying `question_key` and `slots`; `layout[]` as an ordered list of `{component, props}`; and `stage[]` directives. Every Observed and Inferred sentence is an application-owned English or Arabic template selected by `claim_key`, with its slots rendered only as Fact chips. The layout is drawn from the closed catalogue: evidence cards, comparison table, band bar, small trend chart, `supplier_lens`, neighbours chips, break-even calculator, coverage bar, snap report and map directives. Properties are fact ids, release-unit ids or enumerations. An invalid item rejects the brief; after one repair attempt, the template writer supplies the playbook's default selection and layout.

A claim slot validates its metric key, unit, geography role, period rule and allowed provenance. Every required slot and caveat must be present; extra slots, an unknown `claim_key`, component or property, and a fact of the wrong kind reject the brief. The five pipeline stages are defined in [09](09_AI_ASSISTANT.md). The Plan rail shows only the application-defined step labels of that document and DES-90; it adds no stage panel.

A Synthetic or Simulated fact is rendered only in a claim or component whose catalogue subject is `area`, titled as a statistic of the area within reach of the pin. A claim or component whose subject is `place_public` accepts Public facts only. The check uses the resolved place and slot semantics, never wording.

### 3.6 Stage directives

The `stage` tool's directives are a closed TypeScript discriminated union: `fly`, `layer`, `highlight`, `rings`, `dial`, `split`, `set_scenario_inputs` (exact payload shapes from [08 Back end](08_BACKEND.md), section 6.2). A directive outside the union, or with an invalid payload, is ignored and logged, never partly executed. A directive never carries a number to render; it carries ids and coordinates.

### 3.7 Error boundaries

| Boundary | Catches | Fallback |
|---|---|---|
| App | anything not caught below | full-page error with Reload and Reset; standing strip stays |
| Stage | map initialisation failure, WebGL2 missing, context loss, layer errors | "The map is paused on this display" panel; the Brief keeps working |
| Brief | claim-template, layout or card render errors | the validated cards already shown stay; the failed item shows its governed error state |
| Each card | one card's render error | that card's error state only |
| Each room | Trust centre, Proof room, Oversight errors | room error state with a way back |

| ID | Requirement | Slice |
|---|---|---|
| FE-07 | `web/` has the folder layout of section 3.1; an import-boundary check fails if `web/src` imports from outside `web/`. | slice S0 |
| FE-08 | Every route of section 3.2 renders in both languages, and reloading any route restores the same view from the URL. | slice S3 |
| FE-09 | A route requested from a seat that is not allowed shows the not-allowed state of section 10 and makes no data request. | slice S9 |
| FE-10 | Camera position is never stored in React state on every frame; a test asserts no React render is triggered per animation frame during a camera flight. | slice S3 |
| FE-11 | All API access goes through `src/api/`; a lint rule forbids `fetch` and `EventSource` elsewhere. | slice S0 |
| FE-12 | The SSE client applies answer events exactly once in sequence order, resumes with `Last-Event-ID`, handles `withdrawn`, and handles oversight `paused` and `resumed` without duplicating items. | slice S6 |
| FE-13 | A structured brief item or component is rendered only after the complete brief passes all five accounting checks, the item or component validates and every fact in its slots is in the registry with a complete source chain. | slice S6 |
| FE-14 | No model-written prose is rendered. Every Observed and Inferred sentence is an application-owned claim template filled only through validated fact slots; every component is in the closed catalogue or the playbook default is shown. | slice S8 |
| FE-15 | An unknown or malformed `stage` directive changes nothing on screen and is logged. | slice S8 |
| FE-16 | Each boundary of section 3.7 exists; a test throws inside each and checks that the fallback appears and the standing strip remains. | slice S3 |
| FE-17 | When MapLibre cannot create a WebGL2 context, or the context is lost, the Stage shows its paused panel and the Brief continues to work. | slice S3 |

## 4. Component inventory

Names follow the pinned interface vocabulary. Visual specification of each component is in [11](11_DESIGN_DIRECTION.md). The last column names the capability, so a cut in the order of the master plan removes a whole row.

### 4.1 Shell and session

| Component | Responsibility | Inputs | States | Capability |
|---|---|---|---|---|
| Standing strip | the permanent demonstrator notice; never dismissible; present on every route, in presenter mode and in the pack | language | always shown | capability M5 |
| Provenance legend | the four marks with word and texture; shows the hero layer's class | hero layer, language | always shown | capability M5 |
| Viewing-as badge | states which seat is looking ("Viewing as") | seat key and display name | company seat, oversight seat | capability S4 |
| Seat picker | chooses `oversight`, `company_a` or `company_b` for this window; three windows on one machine | seat list from the API | loading, ready, error | capability S4 |
| Reset | returns to the home view and closes every panel; always visible in explore mode | none | enabled, disabled during a locked story step | story |
| Status badges | "Template writer", "Spend cap reached", offline, store `embedded`, oversight paused, "prepared" replay | connectivity slice | hidden when normal | capability M7 |
| Theme switch | switches between the complete dark and light themes without a reload | presenter setting | dark, light | story |
| Room scale | applies `1.0`, `1.15` or `1.3` to wall type tokens | presenter setting | three closed values | story |
| Pause motion | stops continuous motion and applies the reduced-motion state | presenter setting, operating-system preference | running, paused | story |
| Presenter pointer | shows the 40 px room-visible presenter pointer | presenter setting, pointer position | hidden, shown | story |

The seat picker writes the signed `eii_seat` cookie. The stage window and presenter console share one browser profile, so they share the selected seat and `BroadcastChannel`; the oversight and other company windows use separate profiles.

### 4.2 Question and brief

| Component | Responsibility | Inputs | States | Capability |
|---|---|---|---|---|
| Ask bar | bilingual question entry with autocomplete from `resolve` for places and activities | text, language | idle, suggesting, submitting, disabled | capability M7 |
| Understanding chips | "We understood your question as…" chips: commerce activity code, ISIC Rev.4 class, public place category, and the "not mappable" bucket | `resolve` candidates | confirmed, ambiguous (choose one), not mappable | capability M8 |
| Stage | the map: basemap, buildings, door pin, released area, one hero layer, watermark | view slice, layer data | loading, ready, paused, offline-tiles error | all |
| Brief | the answer column: headline; decision sentence; the three evidence-status sections Observed, Inferred and Still to test; the separate coverage section Not measured; validated component layout; Explain, Compare, Pin, Pack and live-only Regenerate; three suggested next questions | brief slice | idle, gathering, writing, complete, partial, declined | capability M7 |
| Plan rail | the steps of the current answer; tap a step to see its tool and status | plan steps | pending, running, done, suppressed, failed | capability M7 |
| Evidence card | one block of evidence (types in 4.3); headline, chips, coverage bar, caveats | card descriptor and fact ids | loading, ready, suppressed, no data, error | capability M1 to capability S11 |
| Fact chip | renders one fact only after its complete source chain resolves: value with unit, provenance mark and word, reliability mark, "your inputs" tag; opens the Evidence drawer; refuses an incomplete chain | `fact_id`, variant | loading chain, value, suppressed, inferred-from-your-inputs, error (provenance or chain mismatch) | capability M5 |
| Evidence drawer | labelled "Source chain"; shows fact → release table → method and version → publisher, dataset, licence, retrieval date and file hash, plus value, provenance, `input_classes`, evidence status, period, geography, rule, coverage, caveats and release | `fact_id`, `lineage_ref` | loading, ready, error | capability M5 |
| Snap report | requested area against released area, number of units, rules that set it; drives the snap animation | `make_area` facts | animating, settled | capability M4 |
| Privacy receipt | per answer: rules version, parameter set, units used, suppressed elements with reasons, release id, what went to the AI, and the accounting result labelled "Checked before display" | `receipt` event | collapsed, expanded | capability M4 |
| "Why can't I see this?" | on every blank: the suppression or no-data reason and the nearest publishable alternative | status, template key, reason key | shown on every suppressed or no-data element | capability M4 |

### 4.3 Evidence card types in v1

| Card type | Content | Release source | Provenance | Capability |
|---|---|---|---|---|
| `work_pay` | "People who work within reach": rounded count of covered earners, median wage band, quartile band range, band distribution bar; mean wage and wage bill only under "More evidence" with "the average alone is not enough" | `worker_pay` | Synthetic | capability M1 |
| `live_pay` | "People who live within reach": the same, plus the housing split of covered earners (`family_housing`, `labour_accommodation`, `institution` and `unknown`, and an explicit `other` row when pooling occurred) with the not-measured coverage count shown separately. The count and the shares beside it come from one additive family (FE-100) | `resident_pay` | Synthetic | capability M1 |
| `presence` | who is present around the door (workers, residents, visitors) as an index for the dial situation; Public monthly context series shown separately on their own Public cards for context and not matched to the dial hour by hour | `presence_index`, `pub_transit_monthly`, `pub_hotel_monthly`, `pub_price_index` | Simulated; context cards Public | capability M2 |
| `public_context` | licences in the municipality against the national rate; zone electricity growth; metro and tram riders | `pub_licence_active`, `pub_zone_utility`, `pub_transit_monthly` | Public | capability M3 |
| `places` | named public places with network distances; the standing "open listings are incomplete" note | `pub_place` via `scan_places` | Public | capability M3 |
| `property_price` | sale price per square metre, always with its deal count | `pub_property_sale` | Public | capability M3 |
| `unit_economics` | sector cost structure for the activity, with the break-even calculator | `pub_sector_accounts` via `sector_facts` | Public; result Inferred, "your inputs" | capability M6 |
| `licensed_vs_operating` | share of licensed food outlets within reach that show payroll activity, by size band; an aggregate strip visually separate from named places | `outlet_register` | Synthetic | capability S1 |
| `staffing_pay` | pay bands for the outlet's jobs among people living within reach, for occupation groups `0` to `9` and `unmapped`, with an explicit `other` row when pooling occurred, beside national averages and the statutory minimum. The not-measured count is not an occupation group | `occupation_pay`, `pub_wage_table` | Synthetic and Public, marked per chip | capability S2 |
| `national_pay` | what moved national average pay (pay against workforce mix), with the table named | `pub_wage_table` | Public | capability S3 |
| `supplier_lens` | ranked horizontal bars, one block per basket input and at most five origins per input, with share, "Calculated import unit value (QAR per kg)", valuation basis as the source states it or "not stated by the source", concentration and trend | `pub_customs_import`, `graph_node`, `graph_edge` | Public | capability S5 |
| `compare` | the same evidence for two doors and their shared reach ("shared reach", never lost sales) | `compare_areas` | least-real of inputs | capability S6 |
| `churn` | licence cancellations against the active stock, bulk months flagged | `pub_licence_cancelled`, `pub_licence_active` | Public | capability S8 |
| `neighbours` | at most six chips, "found near", with the coverage note | graph co-location pairs, `pub_place` | Public | capability S9 |
| `home_area` | coarse, protected home-area share of the door's workers, no finer than a large pooled district | `home_area_share` | Synthetic | capability S10 |

The flagship shows four hero cards (`presence`, `places`, `work_pay` with `live_pay`, `unit_economics`); further cards sit behind "More evidence".

While OI-03 is open, restaurant totals, the `unit_economics` hero and the break-even panel stay off screen, and the `national_pay` card is not rendered.

### 4.4 Stage controls and small visual components

| Component | Responsibility | Inputs | States | Capability |
|---|---|---|---|---|
| Dial with the summer switch | four stored situations `weekday_lunch`, `weekday_evening`, `friday_evening`, `ramadan_iftar`; the `summer` switch applies to the first three and is disabled, with its reason, on `ramadan_iftar`; crossfades between stored blocks; shows an index, never a count | view slice | each situation; summer on, off, not applicable | capability M2 |
| Area controls | distance, walk or drive cut-offs from the closed schema; drive 30 minutes is available only on `staffing_and_pay` | pin and playbook | distance 250 m, 500 m, 1 km; walk 5, 10, 15 minutes; drive 5, 10, 15 minutes and staffing-only 30 minutes | capability M1, capability S2 |
| Coverage bar | the licensed C8 Public proxy, naming its geography, with the remainder labelled "outside this proxy", never Not measured; while OI-04 is open it uses the finest separately licensed geography or returns `NO_DATA`. The separate protected `not_measured_count` appears only beside the resident housing split as its own population; no not-measured share is derived by subtracting the Public proxy. A chart, so not mirrored | coverage facts | ready, suppressed, no data | capability M5 |
| Reliability mark | marks small-count figures by reliability band | `reliability` of the fact | none, low | capability M5 |
| Break-even calculator | The break-even panel shows six inputs, in this order: monthly rent in QAR, seats (whole number, at least 1), average bill in QAR, opening days (default 30, editable), expected covers per day (optional), monthly staff cost in QAR (optional). It posts them to the server method in document 07. Results are inferred "your inputs" chips: 2022 covers per day, and the minimum and maximum of that figure across 2018–2022. Breakpoints appear only when expected covers is filled: maximum rent, minimum bill and, in mode B (the user's staff cost), maximum staff cost; the track's tick is maximum rent and the marker is the entered rent. With expected covers empty, no breakpoint is shown. The optional second result line is labelled "to earn the sector's 2022 surplus share" and is never called break-even. Rent opens empty. | Public norms, user inputs | empty, valid, invalid input, computed | capability M6 |
| Supplier lens | SVG horizontal bars, one block per basket input, at most five origins, longest bar first, each origin a Public fact chip for share and for "Calculated import unit value (QAR per kg)", the valuation basis as the source states it or "not stated by the source", plus a concentration chip and a trend line. The browser draws the tool's list and does not truncate, rank or recompute it. No map and no arcs. | ordered list from `supplier_lens` | ready, empty, error | capability S5 |
| Neighbours chips | at most six category chips; present ones marked, absent ones "not found in public places data" | `neighbours` facts | ready, no data | capability S9 |

The break-even calculation runs on the server through the deterministic tested method of [07](07_ECONOMIC_METHODS.md), called on input change after a short debounce. The browser sends typed inputs and renders returned `inferred` facts with the "your inputs" tag; it does not calculate, compare, round, rank or choose a displayed value. Results are never stored in the release.

### 4.5 Rooms

| Component | Responsibility | Inputs | States | Capability |
|---|---|---|---|---|
| Oversight screen | fixed de-identified ledger projection and roll-ups of where and what companies are asking above the distinct-organisation minimum; no organisation identity, question text or brief text; live rows tagged "this session", seeded history marked Synthetic (OI-08 default) | ledger stream, roll-up facts | live, paused (store away), empty | capability S4 |
| Trust centre | rules in plain language from the live `rules_version`, what the AI can see, egress records, sources and licences, limits, prohibited claims, and the sentence in FE-101 | API | loading, ready, error | capability M4, capability M5 |
| Proof room | attack replay (labelled as a replay of signed build-time results), survival figures for parameter sets A and B, protected tables for exactly the one set exported in the mounted release, two-engine parity results, sealed reveal and fidelity report; a canary is named only by its scenario label; one line read from the review log, and nothing else from the typed-decision gateway: "N activity codes; review order machine-assisted; every mapping signed by a person." No score, badge, panel or run-time call; `web/` does not import the gateway. | API | loading, ready, error | capability M4, capability S7 |

### 4.6 Story and presenter

| Component | Responsibility | Inputs | States | Capability |
|---|---|---|---|---|
| Story stepper | steps 0 to 7 of the guided story; discrete and reversible; a visible position indicator; at step 7 controls unlock on the same map with a permanent Reset | story script, step | locked step, transition, unlocked | story |
| Presenter controls | next, back, language, reset, offline, one-way store switch at a request boundary, theme, room scale, Pause motion and 40 px presenter pointer; presenter API calls carry `X-EII-Presenter-Token` | keyboard, clicker, presenter console | presenter mode on or off | story |
| Presenter console | a second window in the stage window's browser profile, with notes, the same controls and every field of `GET /health`, polled every 5 s; synchronised with `BroadcastChannel` (same-origin, no network for window synchronisation) | channel messages, health response | connected, disconnected, degraded | story |

The story script (`web/src/story/script.json`) lists, per step, the route, camera target, hero layer, dial situation and the prepared brief id; its content follows the storyboard in [11](11_DESIGN_DIRECTION.md). While a story step is locked, map pan, zoom and a new pin are ignored. The stepper, dial, summer switch, language control, Fact chips, break-even inputs, attack Run buttons and Pack stay enabled. Reset is disabled only during a scripted camera move. In explore mode a user gesture interrupts any camera move.

### 4.7 Briefing pack page

The pack is one A4 portrait page in the light theme, bilingual on that page: English label, Fact chip, Arabic label, so each number is printed once. A second page is used only when the content overflows. Simulated prints as static dashes. The standing strip and watermark are on every page. The four provenance words use print-safe textures, and the Source chain section lists each fact's release table, method and version, publisher, dataset, licence, retrieval date, file hash and release. A pack inherits the classes of its facts.

| ID | Requirement | Slice |
|---|---|---|
| FE-18 | Every component of sections 4.1 to 4.7 exists under the name given, with each listed state reachable from a component test fixture. | per row |
| FE-19 | The standing strip appears on every route, in presenter mode and on every printed pack page, and no control hides it. | slice S3 |
| FE-20 | The Viewing-as badge shows the seat read from the signed session cookie on every route after the seat picker; no route or request field selects a seat. | slice S9 |
| FE-21 | The `live_pay` card always shows `family_housing`, `labour_accommodation`, `institution` and `unknown` for covered earners, an explicit `other` row when pooling occurred, and the not-measured count separately from those rows. The count and the shares beside it come from one additive family (FE-100). The not-measured count is a separate population. A fixture missing any of the four classes, or missing the not-measured count, fails the card test. A pooled release that omits `other` fails the card test. | slice S6 |
| FE-100 | Every card that shows a count with adjacent non-ratio shares takes both from one additive family named in the fact lineage (PRV-30). The closed ratio-statistic list is mean wage and the coverage, irregular and deployed-elsewhere shares. Each ratio uses numerator and denominator columns from the same stored rows — one table, one partition, one unit set and one measure where applicable — even when those columns belong to two additive families, and its fact lineage names both. No other card figure uses two families, and no screen sets two routes to one population side by side as two numbers. | slice S6 |
| FE-101 | The Trust centre shows this sentence: "Figures from different tables can differ slightly because each table is protected on its own." | slice S10 |
| FE-22 | Mean wage and wage bill appear only under "More evidence", together with the reading guidance "the average alone is not enough". Exception: scene 2's two guidance plates show the mean chips, then the median band, the band bar, the housing split and the coverage bar. No other surface shows the mean or the wage bill outside More evidence. | slice S6 |
| FE-99 | The `staffing_pay` card lists occupation groups `0` to `9` and `unmapped`, and an explicit `other` row only when pooling occurred. It does not show the not-measured count as an occupation group. | slice S7 |
| FE-23 | The `presence` card and the Dial show an index, never a count, and never name a building as the subject of presence. | slice S6 |
| FE-24 | The `places` card shows Public facts only and always shows the "open listings are incomplete" note; a Synthetic or Simulated fact passed to it is a test failure. | slice S3 |
| FE-25 | The `property_price` card never shows a price without its deal count. | slice S3 |
| FE-26 | The `licensed_vs_operating` strip is rendered as an aggregate, in a container visually separate from named places, with no place names inside it. | slice S6 |
| FE-27 | The summer switch is disabled on `ramadan_iftar` and shows why. | slice S6 |
| FE-28 | The break-even panel shows six inputs, in this order: monthly rent in QAR, seats (whole number, at least 1), average bill in QAR, opening days (default 30, editable), expected covers per day (optional), monthly staff cost in QAR (optional). It posts them to the server method in document 07. Results are inferred "your inputs" chips: 2022 covers per day, and the minimum and maximum of that figure across 2018–2022. Breakpoints appear only when expected covers is filled: maximum rent, minimum bill and, in mode B (the user's staff cost), maximum staff cost; the track's tick is maximum rent and the marker is the entered rent. With expected covers empty, no breakpoint is shown. The optional second result line is labelled "to earn the sector's 2022 surplus share" and is never called break-even. Rent opens empty. The whole panel stays off screen while OI-03 is open. | slice S7 |
| FE-29 | The `supplier_lens` component draws SVG horizontal bars, one block per basket input and at most five origins per input, in the order returned by the tool. Each origin has Public fact chips for share and "Calculated import unit value (QAR per kg)", the valuation basis as the source states it or "not stated by the source", plus a concentration chip and trend line. The browser does not truncate, rank or recompute the list; it draws no supplier map, arc or node graph. | slice S7 |
| FE-30 | Neighbours chips show at most six chips, use the words "found near", and show the coverage note. | slice S7 |
| FE-31 | The Oversight screen never receives or displays an organisation identity, seat display name, question text or brief text in ledger rows or roll-ups. | slice S9 |
| FE-32 | The Oversight screen shows "paused" when the ledger store is away and resumes without a reload. | slice S9 |
| FE-33 | The Proof room labels the attack comparison as a replay of signed build-time results, names canaries only by scenario label, may show survival figures for both parameter sets but protected tables for exactly the exported set, and shows only the activity-spine lineage line from the typed-decision review log: no gateway score, badge, panel, control or run-time call. | slice S10 |
| FE-34 | The story stepper advances and reverses one step at a time from keyboard, clicker and console. During locked steps only map pan, zoom and a new pin are disabled; Reset is disabled only during a scripted camera move; step 7 unlocks exploration on the same map. | slice S10 |
| FE-35 | The presenter console shares the stage window's browser profile, stays in step through `BroadcastChannel`, polls every `GET /health` field every 5 s, and sends the per-session presenter token on presenter routes. | slice S10 |
| FE-36 | A replayed prepared run shows the "prepared" badge for its whole duration. | slice S10 |
| FE-37 | Explain, Compare, Pin and Pack appear on every complete brief, followed by three suggested next questions. Explain opens the Evidence drawer for the brief's first fact; Pin drops the brief's pin and runs the snap. Regenerate also appears and is enabled only in `live` mode. | slice S6 |
| FE-38 | The pack is bilingual on one A4 portrait page unless it overflows. Every printed number is one Fact chip between its English and Arabic labels, and its complete source chain appears in the pack's Source chain section. | slice S10 |

## 5. The Fact chip rule

**Rule.** No numeral may be rendered anywhere in the interface except by the Fact chip family in `web/src/facts/`. A "numeral" is any character of Unicode category Nd: Western digits, Arabic-Indic digits and Extended Arabic-Indic digits all count.

The family has four variants, all one component:

| Variant | Use |
|---|---|
| `value` | a released fact, with provenance mark and word |
| `compact` | the same inside a chart label or legend bin; the word stays in the accessible name |
| `input` | `NumericInput` for user-entered values in the break-even calculator; tagged "your inputs" |
| `reference` | a release id, brief id, activity code, ISIC class, zone code or rules version in the receipt, drawer and pack; carries no provenance mark |

Non-fact positions that need a number for assistive technology (for example the story position "step 3 of 8" in an `aria-label`) are produced by `formatUiOrdinal` in `src/facts/`, never by a literal or by `String(n)` elsewhere.

**How the lint rule works.** A custom ESLint rule, `eii/numerals-only-in-fact-chip`, runs on every `.ts` and `.tsx` file outside `src/facts/` and reports:

1. JSX text containing a numeral;
2. a string literal or template-literal part containing a numeral that is a JSX child, or the value of a rendered attribute (`title`, `alt`, `placeholder`, `label`, `aria-label`, `aria-description`, `aria-valuetext`);
3. a JSX expression whose TypeScript type is `number` or `bigint` (type-aware, using the TypeScript parser services), and a template literal in a rendered position that interpolates such a value;
4. any call to `Intl.NumberFormat`, `Intl.DateTimeFormat`, `toLocaleString`, `toFixed` or `toPrecision`;
5. any use of deck.gl `TextLayer`, and any MapLibre `text-field` expression that reads a property other than the name fields allowed by the style generator.

Two companion checks run in the same CI step: a catalogue test that fails when `en.json` or `ar.json` contains a numeral or a number word from the versioned lexicon in `product/assistant/lexicons/` named by [09](09_AI_ASSISTANT.md) AI-38 (placeholders are allowed only for fact slots), and a search that fails on any `eslint-disable` comment naming this rule. The rule has its own RuleTester tests with cases for each item above and for each digit script.

**What it exempts.** Files in `web/src/facts/`; test files and fixtures; numbers in non-rendered positions (style values, SVG geometry attributes such as `x`, `width`, `d` and `viewBox`, coordinates, array indices, `key` and `data-*` attributes); and basemap labels drawn by MapLibre from tiles. For the last, the style generator hides label layers that are numeric-only (house numbers and road reference numbers), and keeps official place and zone names, which are Public geography names (ASSUMPTION: zone numbers are part of public place names in Qatar and are not facts). The `/{lang}/_perf` route is exempt from the numeral rule and provenance audit, is registered only in development builds and is absent from the frozen bundle.

**Runtime net.** In development builds a mutation observer outlines in red any text node with a numeral outside a chip. The gate is the provenance audit of section 13.

| ID | Requirement | Slice |
|---|---|---|
| FE-39 | The ESLint rule `eii/numerals-only-in-fact-chip` exists, reports all five cases of section 5, and its RuleTester suite covers Western, Arabic-Indic and Extended Arabic-Indic digits. | slice S3 |
| FE-40 | CI fails on any numeral or number word from the versioned `product/assistant/lexicons/` lexicon named by AI-38 in the string catalogues, and on any disable comment for the rule. The development-only `_perf` route is the sole route exemption and is absent from the frozen bundle. | slice S3 |
| FE-41 | A fact-valued chip refuses to render until its complete source chain resolves. The Fact chip renders the provenance word in its accessible name in the `value`, `compact` and `input` variants, shows the texture swatch in `value` and `compact`, and the `reference` variant shows no provenance mark. | slice S3 |
| FE-42 | The Fact chip recomputes the least-real class from `input_classes` (Public more real than Synthetic, more real than Simulated) and shows its error state if it differs from `provenance`. | slice S3 |
| FE-43 | A Suppressed chip shows no digit, shows the lock and the word, and opens "Why can't I see this?". | slice S5 |
| FE-44 | An `inferred` fact built from user inputs shows the "your inputs" tag. | slice S7 |
| FE-45 | The browser formats values returned by the server by applying grouping and the unit pattern only. It never calculates, compares, ranks, re-rounds, compacts or converts a displayed value, and an unknown unit code renders the chip's error state. | slice S3 |

## 6. Map layers

Layer order: basemap fill and line layers, then deck.gl data layers placed beneath the basemap label layers using the interleaved `beforeId` placement, then labels, then the watermark. "Hexagons under labels" is a spike gate in slice S1.

| What is drawn | Data | Layer type | Line and texture |
|---|---|---|---|
| Land, roads, water, place names | PMTiles basemap | MapLibre style from `@protomaps/basemaps` | context, no mark |
| Buildings | basemap `buildings` layer (height, min_height) and a curated landmark list | MapLibre `fill-extrusion` | heights labelled estimates (below) |
| Door pin | user pin | deck.gl `IconLayer` | context |
| Requested area | `make_area` snap report | deck.gl `PathLayer` | solid 2 px accent line with a 2 px casing in `--eii-bg`; after the snap, the same line at 35% opacity. It is not dashed or dotted. |
| Released units | `grid_cell`, `release_unit`, `unit_member` | deck.gl `H3HexagonLayer`, one per resolution (9 and 8); unit outlines from `h3-js` cell-set boundaries in a `PathLayer` | outline in the class of the hero layer |
| Pay of workers or residents | `worker_pay`, `resident_pay` | `H3HexagonLayer`, flat fill by band, never extruded | dotted (Synthetic) |
| Presence index | `presence_index` | `H3HexagonLayer`, flat fill by index band; crossfade on dial change | moving dashes (Simulated) |
| Simulated flows | `flow_od` | particle layer (below) | moving particles (Simulated) |
| Where the door's workers live | `home_area_share` | `GeoJsonLayer` of pooled districts | dotted (Synthetic) |
| Suppressed elements | `suppression_reason` | cell polygons with `FillStyleExtension` hatch; lock icon at the unit's centre | grey hatch with lock |
| Zones and municipalities | `zone`, `municipality`, `pub_zone_utility`, `pub_licence_active` | `GeoJsonLayer` fill and outline | solid (Public) |
| Metro and tram | `pub_transit_monthly`, station points from the gazetteer | `ScatterplotLayer` | solid (Public) |
| Public places | `pub_place` | `ScatterplotLayer` or `IconLayer`; names in a MapLibre symbol layer | solid (Public) |
| Distance connectors | `scan_places` | `PathLayer` | solid (Public) |

**Provenance textures.** The four treatments are fixed: solid = Public, dotted = Synthetic, moving dashes = Simulated, grey hatch with a lock = Suppressed, each always with its word in the legend and on the chip. Colours and pattern sizes come from [11](11_DESIGN_DIRECTION.md). The research names `FillStyleExtension` (procedural hatch and dot fills) and `PathStyleExtension` (dashed lines) as the deck.gl mechanisms. Whether these extensions apply through `H3HexagonLayer`'s sublayers, and how moving dashes are animated, is not confirmed; the spike settles both and records the method. The fallback is a `PolygonLayer` of cell boundaries from `h3-js`. With reduced motion, moving dashes become a static dash, still distinct from dots.

**Particles.** Particles are drawn only from the aggregated, released `flow_od` table. Bands 1 to 5 place 2, 4, 8, 16 and 32 particles on each released origin-destination pair. The layer caps at 50,000 particles by dropping pairs from the smallest band. The seed is 1. Paths are straight or arced between the two unit centres, never routed street traces. The legend states that a moving dot is a visual unit of a simulated aggregate flow, not a person or a trip. Agent trails are dropped; particles never carry an individual path.

**Extruded buildings.** Open height data is nearly absent: in a Greater Doha box, 920 of 170,611 OpenStreetMap building ways carry a height tag and 5,705 carry a number of levels (Overpass counts, stack research, 2026-11-11). Buildings therefore use the basemap height where present, an estimated height otherwise (rule set at slice S1 and written in the asset manifest), and a hand-curated list of landmark heights. The legend and the Trust centre state "building heights are estimates". No data value is ever encoded as building height; wage towers are dropped.

**One hero layer at a time.** The layer registry holds hero layers (`worker_pay`, `resident_pay`, `presence`, `flows`, `home_area`, `zone_momentum`, `licence_density`, `transit`) and context layers (basemap, buildings, door, released-area outline, places). Turning a hero layer on turns the previous one off. Only the hero layer may use a colour scale; its legend bins are rendered in the DOM with `compact` Fact chips.

**Watermark.** A watermark is drawn into the map canvas itself, so a screenshot of the canvas and every export (pack, image) carry it. It cannot be switched off from the interface. The rendering mechanism (a MapLibre custom layer drawing a screen-space quad, or a deck.gl screen-space layer) is chosen at slice S1. Its wording and look are set in [11](11_DESIGN_DIRECTION.md); it contains no numeral.

**Camera.** Story moves use MapLibre camera animations with durations from [11](11_DESIGN_DIRECTION.md). The initial view is Qatar; the area tools work only inside the frame of the release.

| ID | Requirement | Slice |
|---|---|---|
| FE-46 | Data layers render beneath basemap labels in interleaved mode; a visual test shows a label legible over a hexagon. | slice S1 |
| FE-47 | Each data source of section 6 is drawn only with the layer type listed; any other layer type for a release table fails review. | slice S3 |
| FE-48 | Each provenance class is drawn with its line and texture treatment, independent of colour; a greyscale visual test still distinguishes all four. | slice S3 |
| FE-49 | At most one hero layer is visible; turning one on turns the previous one off; a test asserts the registry never holds two. | slice S6 |
| FE-50 | No layer is extruded to encode a data value; only buildings are extruded. | slice S6 |
| FE-51 | Particles are generated only from released `flow_od` rows: bands 1 to 5 place 2, 4, 8, 16 and 32 particles per pair; the 50,000-particle cap drops pairs from the smallest band; seed 1 fixes placement and timing; paths are straight or arced between unit centres. | slice S6 |
| FE-52 | The legend states that building heights are estimates whenever buildings are extruded. | slice S3 |
| FE-53 | The watermark is present in the canvas in every frame and in every export; a pixel probe test on an exported image finds it. | slice S3 |
| FE-54 | `H3HexagonLayer` instances each hold one resolution only. | slice S1 |
| FE-55 | Released-unit outlines are computed in the browser only as geometry from cell ids; no statistic is computed or aggregated in the browser. | slice S5 |

## 7. The basemap

- **Tiles.** One PMTiles extract of Qatar cut from the Protomaps daily build with `pmtiles extract` and a bounding box (Protomaps documentation). Hot-linking the builds is discouraged by Protomaps, so the extract is fetched once by the asset pipeline (section 14), hashed and stored under `data/` (not committed). FastAPI serves it with HTTP Range support (Starlette `FileResponse` supports Range since 0.39.0). The `pmtiles` JavaScript protocol is registered with MapLibre at boot.
- **Style.** Generated in code with `@protomaps/basemaps` (layers for a named flavour and a language). The flavour and any overrides come from [11](11_DESIGN_DIRECTION.md). A language switch regenerates the label layers with `name:ar` or `name:en`; tiles do not change.
- **Glyphs.** MapLibre 6.9 and later shape Arabic without a plugin, but Arabic needs real Arabic glyphs. The default Protomaps font set (Noto Sans) may not cover Arabic, so the pipeline adds Noto Sans Arabic glyph ranges, or uses MapLibre font-faces (`setFontFaces`, since 6.7); the spike picks one. Glyphs and sprites are served from the same origin.
- **No third-party requests at run time.** The style contains no absolute URL to another host. The page sends a Content Security Policy that allows `'self'` (plus `blob:` and `data:` where MapLibre workers and images need them) and nothing else. Telemetry of any kind is absent.
- **Label check.** Before slice S3 closes, a reviewer checks in both languages how the basemap names the Gulf, neighbouring territories and Qatari districts, and hides or edits labels as needed (design research: a mandatory check, not a known fault).
- **Attribution.** OpenStreetMap and Protomaps attribution stays visible on the map (ODbL Produced Work); Overture attribution is shown whenever Overture-derived places are on screen.

| ID | Requirement | Slice |
|---|---|---|
| FE-56 | With the network disabled except for the local server, the basemap, labels in both languages, buildings and data layers all render; an end-to-end test blocks every non-same-origin request and fails if one is attempted. | slice S1 |
| FE-57 | Arabic map labels render with connected, correctly ordered glyphs from self-hosted glyph files; a visual test covers five reviewed Arabic place names. | slice S1 |
| FE-58 | The PMTiles file is served with range requests by the FastAPI process; no separate tile server runs. | slice S1 |
| FE-59 | Switching language changes basemap label language without reloading tiles or moving the camera. | slice S3 |
| FE-60 | OpenStreetMap and Protomaps attribution is visible on every map view and in every export. | slice S3 |

## 8. Bilingual and right-to-left rules

The route sets `lang` and `dir` on the root element. All component styles use CSS logical properties (`margin-inline-start`, `inset-inline-end` and so on); a style check fails on physical `left` and `right` properties in component styles, except inside the Stage canvas container.

| Mirrors in Arabic | Does not mirror |
|---|---|
| order of the Brief column, Plan rail and drawers (drawers open from the inline end) | the map and its canvas (north stays up; nothing is flipped) |
| text alignment and reading order | charts: band distribution bar, coverage bar, supplier lens |
| directional icons (back and next arrows) | numerals and number ranges |
| the story stepper's Back and Next buttons; the Dial's position moves to the other side | the Dial's quadrants, clockwise motion and order of its four situations |
| card order within a row | time order |

Keys are physical: the clicker's next key and the Right arrow key always mean "next" in the story, in both languages, because a presenter's hand must not depend on the language. In the Dial, the Right arrow key always moves to the next situation in its fixed order.

**Numbers.** All numbers are formatted in `src/facts/` with `Intl.NumberFormat` using `en-QA` and `ar-QA-u-nu-latn`, and with the `numberingSystem: 'latn'` option set as well (MDN: the option takes precedence over the locale key). CLDR's default numbering system for `ar-QA` is Arabic-Indic, so the explicit setting is required; Qatari official Arabic sites use Western digits (design research). The same applies to dates. A test asserts that, for every fact in a fixture brief, the digit sequence shown in Arabic equals the one shown in English, and that grouping and decimal separators are identical. The formatter removes bidirectional control characters that `Intl` may insert, because isolation is done by markup.

**Isolation.** Every Fact chip root is an isolate (`bdi`, or `unicode-bidi: isolate`), and its numeric run sits in its own left-to-right isolate, so ranges, signs, percentages and units do not reorder inside an Arabic sentence. Place names, activity names and ids from the API are wrapped in `bdi`. A test renders, inside Arabic sentences, a band range, a negative change, a percentage, a currency amount with an Arabic unit word and a Latin place name, and compares against reviewed screenshots.

**Strings.** All interface text comes from `src/i18n/en.json` and `ar.json` by key; no literal interface text in components. Each Arabic string carries a review status; the provenance words (عام · اصطناعي · محاكاة · محجوب), the three evidence-status words (مرصود · مستنتج · يحتاج إلى اختبار) and the separate coverage label Not measured (غير مقيس) are the master design's proposals, pending native review. A development badge counts strings pending review; the slice S10 gate requires zero pending prepared strings (OI-09).

**Fonts.** IBM Plex Sans and IBM Plex Sans Arabic for the interface, self-hosted as WOFF2 from the pinned npm packages, with tabular figures for every chip (the presence of the tabular-figures feature in the chosen files is checked at slice S1). Noto Sans and Noto Sans Arabic for map glyphs. Sizes, weights and the relative size of Arabic text are in [11](11_DESIGN_DIRECTION.md). The story does not start until `document.fonts` reports ready.

| ID | Requirement | Slice |
|---|---|---|
| FE-61 | Switching language changes `lang` and `dir`, mirrors the items in the left column of section 8 and none in the right column; visual tests in both languages confirm it. | slice S3 |
| FE-62 | Every number in both languages uses Western digits; a test scans the rendered Arabic page for Arabic-Indic and Extended Arabic-Indic digits and finds none. | slice S3 |
| FE-63 | For one brief, the set of `fact_id` values and their displayed digit strings are identical in English and Arabic. | slice S6 |
| FE-64 | Every Fact chip and every API-supplied name is bidirectionally isolated; the five mixed-direction cases of section 8 match reviewed screenshots. | slice S3 |
| FE-65 | Component styles use logical properties only; the style check passes. | slice S3 |
| FE-66 | Story and Dial keys keep their physical meaning in both languages. | slice S10 |
| FE-67 | No interface text is written as a literal in a component; a lint rule enforces it. | slice S3 |
| FE-68 | Interface and map fonts are self-hosted, and the first story frame is drawn only after fonts are ready. | slice S3 |

## 9. Layouts, presenter mode and big-screen rules

| Layout | Applies when | Arrangement |
|---|---|---|
| Wall | viewport width at least 1600 CSS px, or presenter mode | Plan rail as one row at the top of the Brief; Stage and Brief side by side. The Brief is 5 columns (706 px) on the 1920 × 1080 canvas. |
| Laptop | width 1200 to 1599 CSS px | Stage and Brief side by side; the Plan rail collapses into step chips above the Brief |
| Tablet | width 768 to 1199 CSS px, touch first | Stage full width; the Brief is a bottom sheet over the map; drawers are full-height sheets |
| Below 768 | narrower windows | a notice asks for a larger screen (a phone layout is not in v1) |

Breakpoint values are ASSUMPTIONS chosen so that each pinned viewport below falls in its named layout; they are adjusted after the first visual review. Pinned visual-test viewports are 3840 × 2160, 1920 × 1080, 1440 × 900 and 1024 × 768. The 3840 × 2160 case measures the pixel-ratio cap; presenter mode still expects a 1920 × 1080 CSS viewport.

**Presenter mode** (`EII_PRESENTER=1`, or the presenter control) applies the big-screen rules of the master design: the 1920 × 1080 design canvas, no text under 28 px, 5% safe margins (96 px left and right and 54 px top and bottom at 1080 lines, design research), no hover-only information, and a pixel-ratio cap for 4K. Presenter mode expects a 1920 × 1080 CSS viewport; the 3840 × 2160 test measures the cap. Theme, room scale, Pause motion and the 40 px presenter pointer remain available. The cap is applied to both MapLibre (`pixelRatio`, and `maxCanvasSize`, which lowers the ratio to fit; MapLibre MapOptions page, retrieved 2026-11-11) and deck.gl (`useDevicePixels` set to a number). The default cap value is set at slice S1 from the frame-rate measurement.

**No hover-only information.** Nothing important is shown only on hover. Every chip, legend entry and map feature that has detail opens it on tap, click or Enter. The `title` attribute is not used for information.

**Touch targets.** Interactive targets are at least 24 x 24 CSS px everywhere (WCAG 2.2 success criterion 2.5.8, Level AA) and at least 44 x 44 CSS px in tablet layout and presenter mode (ASSUMPTION: a larger target for fingers and for a room). An optional idle timer that returns to the opening view is available to the presenter and is off by default (ASSUMPTION: a timer can surprise a Minister exploring alone).

| ID | Requirement | Slice |
|---|---|---|
| FE-69 | Each layout of section 9 renders without overlap or horizontal scroll at its pinned viewports in both languages. | slice S6 |
| FE-70 | In presenter mode no rendered text is smaller than 28 px, and no interactive or informative element lies within the 5% safe margins; an automated check measures both. | slice S10 |
| FE-71 | A pixel-ratio cap applies to MapLibre and deck.gl when presenter mode is on, and its value is configurable. | slice S1 |
| FE-72 | No information is available only on hover; a keyboard-only and a touch-only end-to-end run reach every drawer. | slice S6 |
| FE-73 | Interactive targets meet 24 x 24 CSS px everywhere and 44 x 44 CSS px in tablet layout and presenter mode. | slice S6 |

## 10. States

The front end never writes its own refusal or caveat wording. Each status arrives with a template key chosen by the application ([09](09_AI_ASSISTANT.md)); the front end renders that template from the catalogue.

Before an answer is shown, the product plane runs the fixed accounting gate: Sources, Assumptions, Nothing invented, Scope and Limits stated. The front end renders an answer only with the gate result, shown in its receipt under "Checked before display". If any check fails, it removes any withdrawn items and renders the template writer's default answer. The Arabic labels for "Source chain" and "Checked before display" remain pending the owner's review.

| State | Trigger | What the user sees |
|---|---|---|
| Loading | request in flight | card skeletons and Plan rail steps; no placeholder numbers, no spinner digits or percentages |
| Empty | no pin yet, or a new session | the ask bar and three journey cards; "Ask about here" when the user taps the map |
| No data (`NO_DATA`) | nothing released for that element | the coverage label Not measured where the template says so, the reason, and "Why can't I see this?"; never a zero |
| Suppressed (`SUPPRESSED`) | a rule withheld the element | grey hatch with lock and the word Suppressed; "Why can't I see this?" opens the reason from `suppression_reason` and the nearest publishable alternative |
| Out of scope (`OUT_OF_SCOPE`) | a question outside the product | a scope card with three in-scope suggestions |
| Error | a request or render failed | the element's error state with Retry; validated evidence already shown stays; a failed structured item or layout is withdrawn before the template writer's default appears |
| Offline | the model is unreachable or no API key exists | the Template writer badge; the default claim selection and component layout use the same facts and catalogues |
| Store paused | PostgreSQL is away | company seats continue on the embedded reader with the store badge; the Oversight screen shows "paused" |
| Server unreachable | the local server does not answer | a full-page reconnect state; the standing strip stays |
| Not allowed | a seat opens a brief or room it may not see | a neutral not-available message that does not confirm whether the brief exists |

| ID | Requirement | Slice |
|---|---|---|
| FE-74 | Each state of section 10 has a component test and an end-to-end test that drives it from a recorded API fixture. | slice S6 |
| FE-75 | No state renders a zero, dash or blank in place of a missing or suppressed value without its reason affordance. | slice S5 |
| FE-76 | Every suppressed or no-data element offers "Why can't I see this?". | slice S6 |
| FE-77 | Refusal and caveat text is rendered only from the template key received with the status. | slice S8 |
| FE-78 | An answer is rendered only after all five accounting checks pass, and the receipt shows their result under "Checked before display". If a check fails or model access is blocked, the template writer's default answer is rendered from the same facts and catalogues and the badge reads "Template writer". | slice S8 |
| FE-79 | Company B opening Company A's brief URL sees the not-allowed state and no fact from that brief reaches the page. | slice S9 |

## 11. Accessibility

Target: WCAG 2.2 Level AA for every route, with these specific requirements.

| ID | Requirement | Slice |
|---|---|---|
| FE-80 | Every control is reachable and operable by keyboard with a visible focus indicator; the focus order follows the reading order in both directions. | slice S3 |
| FE-81 | Provenance is never carried by colour alone: word, texture and line style are always present. | slice S3 |
| FE-82 | Each hero layer offers "Show as table": an accessible table of the same released facts, rendered with Fact chips. | slice S6 |
| FE-83 | The Brief announces each completed section through a polite live region after the accounting gate has passed, not each token of the buffered brief. | slice S6 |
| FE-84 | With `prefers-reduced-motion: reduce`, camera flights become cuts, particles stop, moving dashes become static dashes, and the snap shows its end state. | slice S6 |
| FE-85 | Text contrast meets the ratios set in [11](11_DESIGN_DIRECTION.md) and at least WCAG AA; an axe-based scan (version pinned at slice S0) reports no serious or critical violation on any route in either language. | slice S6 |
| FE-86 | Arabic and English runs carry correct `lang` attributes so screen readers switch voice. | slice S3 |
| FE-87 | The laptop layout remains usable at 200% browser zoom. | slice S6 |

## 12. Performance budgets

All figures are targets, to be measured on the build machine in a native desktop browser with hardware-accelerated WebGL2 (not a Linux browser under WSL, which can fall back to software rendering; stack research). They are not promises. The deck.gl performance guide puts basic layers at about one million items at 60 frames per second, so the gate below sits within documented limits; it still has to be measured.

| Measure | Target | Source of the target |
|---|---|---|
| Spike frame-rate gate (slice S1) | 110,000 hexagons and 50,000 particles at 60 frames per second at the wall canvas with the pixel-ratio cap; defined as at least 95% of frames under 16.7 ms over a 30-second scripted camera orbit with particles animating (ASSUMPTION on the definition) | master design, slice S1 gate |
| Evidence on screen | within 2 s of submitting a question | master design |
| Checked brief, no live model | within 6 s (template writer or recorded provider). The brief is buffered until the accounting gate has passed; evidence cards may appear earlier | master design |
| Checked brief, live model | within 20 s when a live model composes it | master design |
| Dial change | crossfade completes within the duration set in [11](11_DESIGN_DIRECTION.md), with no frame over 33 ms (ASSUMPTION) | design direction |
| Map ready | first basemap frame within 3 s of route load from the local server (ASSUMPTION) | estimate |
| Memory | heap growth under 50 MB across three loops of the full story (ASSUMPTION) | estimate |

A development-only route `/{lang}/_perf` loads generated hexagons and particles at the gate sizes and records frame times with `requestAnimationFrame`; the result, the browser, the display and the cap are recorded in `PROGRESS.md`. CI cannot measure GPU frame rates, so the frame-rate gate is run on the build machine in slice S1 and repeated before each rehearsal. Bundle size is measured and reported at every build; no size limit is set until slice S3 gives a baseline.

| ID | Requirement | Slice |
|---|---|---|
| FE-88 | The `_perf` route exists in development builds only and records frame-time percentiles for the gate configuration. | slice S1 |
| FE-89 | The slice S1 frame-rate gate passes its named test. A technical alternative is accepted only if it keeps the same user-visible capability, passes the same assertion and is recorded in an owner-approved decision record. | slice S1 |
| FE-90 | Evidence and checked-brief times are measured in the end-to-end suite and reported against the targets at every slice from slice S6: evidence within 2 s; the checked brief within 6 s when no live model is called, and within 20 s when a live model composes it. | slice S6 |
| FE-91 | Time and selection changes update deck.gl layers through update triggers or filter uniforms, without replacing the data arrays. | slice S6 |

## 13. Testing

Tool choices not covered by the research are ASSUMPTIONS, pinned at slice S0: Vitest with React Testing Library for unit and component tests, Playwright with Chromium for end-to-end, visual and audit tests, and axe-core through its Playwright integration. Repository-wide strategy is in [12](12_TESTING_AND_QUALITY.md).

Every interface task uses `frontend-design-pro`; every chart task uses `dataviz`; `design-audit` is the interface gate, including web, Arabic and right-to-left behaviour, and data density.

| Level | What it covers |
|---|---|
| Unit | formatters in both languages, least-real check, SSE sequence and withdrawal handling, directive validation, store reducers, router, particle generation determinism |
| Lint rule | RuleTester cases for `eii/numerals-only-in-fact-chip` (section 5) |
| Component | every component and every listed state from recorded fixtures; Fact chip variants; card types with Public, Synthetic, Simulated and Suppressed facts |
| Visual | key screens at the four pinned viewports in English and Arabic: home, flagship workspace with four hero cards, Evidence drawer, Dial at each situation, suppressed card, Oversight screen, Trust centre, Proof room, pack page; animations off and fonts ready; fixed camera; reviewed baseline images |
| End-to-end | the public-only flagship (slice S3), the joined door (slice S6), language flip with identical numbers, the guided story by keyboard, store paused, template writer, seat isolation, no third-party request, reduced motion |
| Provenance audit | section below |

**Automated provenance audit** (`tests/audit/`, Playwright). On every route and every story step, in both languages and at the wall and tablet viewports, the audit:

1. walks all visible text nodes and fails on any numeral not inside a Fact chip element;
2. resolves every chip's `fact_id` to a fact in the registry with `provenance`, `input_classes`, `lineage_ref` and `release_id` present, and refuses any incomplete source chain;
3. recomputes the least-real class independently and compares it with the chip's mark;
4. opens every chip's drawer, checks the "Source chain" label and follows fact → release table → method and version → publisher, dataset, licence, retrieval date and file hash;
5. checks that Suppressed chips contain no digit and offer the reason affordance;
6. resolves each claim and component's catalogue subject and fails any Synthetic or Simulated fact outside subject `area`, or any non-Public fact under `place_public`, regardless of wording;
7. exports the canvas and the pack and checks for the watermark and the standing strip;
8. compares the English and Arabic fact sets for the same brief, checks the five-part accounting result in every receipt, and verifies that a failed check selects the template writer's default.

The audit is a gate for slice S3, slice S6, slice S7 and slice S10.

| ID | Requirement | Slice |
|---|---|---|
| FE-92 | Unit, component, visual, end-to-end and audit suites run with `./eii test`; visual and audit suites also run in CI with software rendering and fixed baselines. | slice S3 |
| FE-93 | Visual tests cover the listed screens at all four pinned viewports in both languages, and every baseline change is approved in review. | slice S6 |
| FE-94 | The provenance audit passes all eight checks on every route and story step. | slice S3 |
| FE-95 | Tests never print or snapshot API keys, and fixtures use only synthetic identifiers of the form `SYN-E-7F3K2Q`. | slice S0 |

## 14. Asset pipeline

A script under `scripts/` (named in [13](13_DEPLOYMENT_AND_OPERATIONS.md)) builds the map assets into `data/` and writes an asset manifest listing, for each file, the source URL, retrieval date, licence and SHA-256. The Trust centre reads the manifest to show licences and attributions. Nothing in `data/` is committed.

| Asset | Source | Licence | Build step | Committed |
|---|---|---|---|---|
| Basemap tiles | Protomaps daily build | ODbL Produced Work, OpenStreetMap attribution required | `pmtiles extract` (go-pmtiles CLI, v1.31.2 at research time) to a Qatar bounding box; maximum zoom checked | no |
| Basemap style | `@protomaps/basemaps` | BSD-3-Clause | generated in the browser at run time | code only |
| Map glyphs | `protomaps/basemaps-assets` fonts (Noto Sans) plus Noto Sans Arabic | SIL OFL | downloaded; Arabic glyph ranges built or font-faces configured at slice S1 | no |
| Sprites | `protomaps/basemaps-assets` | to confirm at slice S2 before use (not stated in the research) | downloaded | no |
| Landmark heights | hand-entered estimates keyed by name and coordinates | project's own | joined to basemap footprints at build | the list only |
| Interface fonts | IBM Plex Sans, IBM Plex Sans Arabic npm packages | SIL OFL 1.1 | bundled by Vite with the licence text | via lock file |
| Icons | the set chosen in [11](11_DESIGN_DIRECTION.md) | as stated there | bundled by Vite | as stated there |
| Zone geometry | per [04 Public data pack](04_PUBLIC_DATA_PACK.md) (census map layers: no stated licence, OI-04) | per 04 | fetched at build time, never committed; excluded from release assets while OI-04 is open | no |

| ID | Requirement | Slice |
|---|---|---|
| FE-96 | The asset pipeline records source URL, retrieval date, licence and SHA-256 for every map asset. A build fails when an asset lacking a stated licence is included in a release asset set; a validation-only fetch excluded from that set does not fail for existing in the build cache. | slice S2 |
| FE-97 | The OFL licence text ships with every bundled font. | slice S3 |
| FE-98 | Two runs of the asset pipeline on the same inputs produce files with identical hashes. | slice S2 |

## Open questions and assumptions

ASSUMPTIONS (each with its reason):

1. API payload types are generated from the FastAPI OpenAPI schema; one source of truth for shapes (section 3.1).
2. In-house router over the History API; ten routes do not justify a dependency (section 3.2).
3. No state library; one store with selectors is enough for one session per window (section 3.3).
4. Zone numbers inside official place names are Public geography labels, not facts, and are exempt from the lint (section 5).
5. Breakpoints 1600 and 1200 CSS px (section 9).
6. 44 x 44 CSS px targets in tablet layout and presenter mode; idle timer off by default (section 9).
7. Definition of the 60-frames gate, dial frame limit, map-ready and memory targets (section 12).
8. Vitest, React Testing Library, Playwright with Chromium and axe-core as test tools, pinned at slice S0 (section 13).

Open items from the master design that touch this document:

- OI-01: without an API key the front end runs with the template writer and shows its badge.
- OI-03: restaurant totals, unit economics, the break-even panel and the national pay card stay off screen until the conflicting public tables are reconciled.
- OI-04: while OI-04 is open, the source is validation-only: it is fetched at build time, never committed, and no value, derived share, title or geometry enters a release. The coverage bar uses the finest separately licensed geography or returns `NO_DATA`. After the licence is recorded, derived shares carry attribution.
- OI-05: the product name and Arabic name shown in the shell and pack await the owner's clearance; the working title is used.
- OI-06: source labels on screen use neutral record-type names by default; naming custodians is a configuration value read from the API, never hard-coded.
- OI-08: label for live ledger rows and the distinct-organisation minimum on the Oversight screen.
- OI-09: native Arabic review of all prepared strings, a gate at slice S10.
- OI-14: the typed-decision gateway has no front-end or run-time role without an approved route.
- OI-17: no typed-decision measurement panel appears in the Proof room; only the activity-spine lineage line appears.

Questions for the spike in slice S1: whether `FillStyleExtension` and `PathStyleExtension` work through `H3HexagonLayer`; how moving dashes are animated; the watermark mechanism; Arabic glyph route (glyph files or font-faces); tabular figures in the chosen font files; the pixel-ratio cap value.

## Sources

All retrieved 2026-11-11, through the stack research and design research files of this pack unless marked "checked by this document's author".

- MapLibre GL JS releases and v6.0.0, v6.7.0, v6.9.0 release notes; v5-to-v6 migration guide; API documentation and examples; `setRTLTextPlugin` page. maplibre.org and github.com/maplibre/maplibre-gl-js.
- MapLibre agent skills, github.com/maplibre/maplibre-agent-skills.
- MapLibre GL JS MapOptions (`pixelRatio`, `maxCanvasSize`), maplibre.org/maplibre-gl-js/docs/API/type-aliases/MapOptions/ (checked by this document's author).
- deck.gl documentation: What's new; `@deck.gl/maplibre` overview; performance guide; `H3HexagonLayer`; `TripsLayer`; `FillStyleExtension`; `PathStyleExtension`; `DataFilterExtension`; WebGPU guide. deck.gl.
- npm registry entries for `maplibre-gl`, `@deck.gl/core`, `@deck.gl/maplibre`, `pmtiles`, `@protomaps/basemaps`, `h3-js`, `apache-arrow`.
- Protomaps documentation (downloads, flavours, localisation, MapLibre, PMTiles CLI) and github.com/protomaps/basemaps-assets.
- Starlette release notes (Range support in `FileResponse`), starlette.dev.
- Vite 8 announcement and releases; React releases. vite.dev, github.com/facebook/react.
- Overpass API counts of building ways and height tags in a Greater Doha box (stack research).
- Unicode CLDR number data for `ar-QA` and `ar-AE`; MDN `Intl.NumberFormat`; W3C "Inline markup and bidirectional text"; W3C Arabic layout requirements; Material Design bidirectionality guidance (design research).
- Microsoft "Designing for Xbox and TV"; Android TV layout guidance; Amazon Fire TV design guidelines (design research, big-screen rules).
- IBM Plex, github.com/IBM/plex (SIL OFL).
- WCAG 2.2 Understanding 2.5.8 Target Size (Minimum), w3.org/WAI/WCAG22/Understanding/target-size-minimum.html (checked by this document's author).
- MDN `BroadcastChannel`, developer.mozilla.org/en-US/docs/Web/API/BroadcastChannel (checked by this document's author).
- MDN `prefers-reduced-motion`, developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-reduced-motion (checked by this document's author).
