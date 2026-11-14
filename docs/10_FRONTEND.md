# 10 — Front End

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016, 0017, 0018 and 0019 on 2026-11-12, and by decision 0022 on 2026-11-13 and decision 0024 on 2026-11-14 |
| Date | 2026-11-13 |
| Owner | albarami |
| Purpose | Tell a builder exactly how the browser application of the EII proof of concept is structured, what each component does, how the map draws provenance, and how the front end is tested. |
| Read first | [01 Project brief](01_PROJECT_BRIEF.md), [02 Architecture](02_ARCHITECTURE.md), [08 Back end](08_BACKEND.md), [09 AI assistant](09_AI_ASSISTANT.md), [11 Design direction](11_DESIGN_DIRECTION.md), [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) |

## In brief

- The front end is one React 19 single-page application in `web/`, built with Vite 8 and served by the same FastAPI process as the API. Nothing is built yet; everything below is a requirement.
- Version 1 covers the whole initiative ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)). The Stage is one living map of Qatar: real public geography, roads and business points; the establishment points of the public business register, each of which opens its company card; firm counts and density from the register; workers as density and statistics from the synthetic labour and residence records attached to the register companies ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)); estimated people and traffic by hour, animated through the day, with an event-day selector and the summer switch.
- The user draws an area, sets a radius from presets, or picks a walk or drive time with an hour control. Public points and Simulated estimates are computed for that exact shape; only figures of the protected record types snap to whole release units, and only they bring the snap report.
- New views serve the seven decision journeys, the three services and the four cases: the ranking panel with editable weights and the rank-stability sentence beside every rank, the reverse view, similar areas, the monthly period selector with "what changed", the labour-market view, lists of register companies with the company card, the FDI layer and the case gallery. The home screen offers the seven decisions, three services and four cases.
- The sample files of cases C3 and C4 are the shipped synthetic files only. The browser chooses one by a closed key and the server loads it; no file is uploaded, dropped or hashed in the browser. A loaded file stays in the session and seat that loaded it, and the browser receives none of its rows.
- The map is MapLibre GL JS 6 with deck.gl 9.4 interleaved on WebGL2, over a self-hosted PMTiles basemap with self-hosted Arabic glyphs. The page contacts only its own origin and makes no third-party request at run time; with the optional live traffic provider on, the local server fetches the provider's tiles and passes them on (section 6).
- Both map libraries are newer than most model training data. Builders read the current official documentation before writing map code.
- The Fact chip is the only component allowed to render a numeral. It refuses a fact without a complete source chain. A lint rule enforces the component boundary at build time and an automated provenance audit enforces it in the running page.
- Every displayed number and comparison comes from deterministic tested code in `eii_core.calc`, the release build, or a fixed application-schema read function listed by the data contracts and covered by tests. The browser formats returned values; it never calculates a displayed value.
- Brief sentences are application-owned bilingual claim templates filled with Fact chips. The assistant selects structured claim and component keys; no model-written prose reaches the screen.
- Forecasts of listed series (Public series, and the released monthly statistics of the custodian-type feeds, which carry the Synthetic class), base rates, the site estimate and the user's scenarios are outputs of tested code ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md)). A forecast shows its interval and its measured backtest error, a base rate its counts and period, an estimate its low, middle and high cases and, on simulated inputs, its label, and a scenario every assumption, editable and never called a forecast. The browser draws what it receives. Nothing forecasts the success of a venture.
- Provenance is shown by texture and line style as well as by word: solid = Public, dotted = Synthetic, moving dashes = Simulated, grey hatch with a lock = Suppressed. One hero layer is shown at a time. A watermark is drawn into the canvas and every export. Every estimated count shows its range, a register company's employee count carries the Synthetic mark of its attached records, and a Public split or FDI figure carries the Public mark with its year.
- Arabic mirrors the chrome and reading order, not the map, charts, numerals or the dial. Digits are Western in both languages.
- Visual tokens, motion, typography sizes and the storyboard are owned by [11 Design direction](11_DESIGN_DIRECTION.md). This document links to them and does not restate them.

## 1. Scope and boundaries

This document covers the browser application only. Other documents own neighbouring concerns:

| Concern | Owner |
|---|---|
| API routes, server-sent event names and payloads, seat sessions, the closed tool and stage-directive lists, the routes for drawn shapes, weights and sample files | [08 Back end](08_BACKEND.md) |
| What the assistant sends, the playbooks, the claim and component catalogues, refusal and caveat templates | [09 AI assistant](09_AI_ASSISTANT.md) |
| Colours, textures, type scale, motion durations, icons, fixed sentences, storyboard per step | [11 Design direction](11_DESIGN_DIRECTION.md) |
| Fact object fields and release tables, including hourly presence counts with ranges, traffic by hour, monthly periods, `register_company_list` and `pub_register_company`, `fdi_projects`, and the tables `pub_venue_busyness`, `pub_night_lights`, `pub_place_fsq` and `pub_pop_agesex_grid` | [03 Data contracts](03_DATA_CONTRACTS.md) |
| Privacy rules and suppression reasons, including those for drawn shapes, months and the register-company list | [06 Privacy and disclosure control](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) |
| Break-even, overlap, pay-decomposition, ranking, rank-stability, reachable-access, projection and apportioning methods, and the forecast and backtest, base-rate, people-present-by-pay-band, site-estimate, catchment-share, revenue-range, night-lights, relative-busyness and grid-sum methods of cards C30 to C38 | [07 Economic methods](07_ECONOMIC_METHODS.md) |
| Public sources, the added portal datasets, the two investment sources, and the self-serve sources and the two keys of [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) | [04 Public data pack](04_PUBLIC_DATA_PACK.md) |
| Test strategy across the repository, CI | [12 Testing and quality](12_TESTING_AND_QUALITY.md) |
| Start-up, presenter machine, rehearsals | [13 Deployment and operations](13_DEPLOYMENT_AND_OPERATIONS.md), [16 Demo runbook](16_DEMO_RUNBOOK.md) |

Where this document names an API path or event name, it is the front end's expectation. If [08 Back end](08_BACKEND.md) defines a different name, 08 wins and the front-end client is changed to match.

Three code families share the letter S. Capability references are always written "capability M1" to "capability M8" or "capability S1" to "capability S11". Build references are always written "slice S0" to "slice S11". The three services of [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) are always written "service S1" to "service S3". Likewise the seven decisions are "journey D1" to "journey D7" and the four cases "case C1" to "case C4", never bare.

Requirements added for decision 0016 name the build phase of that decision's item 15 in their Slice column: "map foundation", "flagship" (the location choice in full depth) or "journeys" (the other journeys, the services and the cases). [14 Implementation plan](14_IMPLEMENTATION_PLAN.md) maps each phase to its slices.

The front end never computes a statistic, comparison, rank, breakpoint, density, apportioned share or other displayed number, never rounds a released value differently, never chooses a refusal or caveat wording, and never holds record-level data other than a register company's released card fields and employee count (FE-115). Every number is produced by a deterministic tested server function in `eii_core.calc` or by the release build. The break-even panel, the ranking weights and a drawn shape are posted to server methods; a sample file is chosen only by its closed key, which the browser posts, and the server loads the committed file (FE-120). The browser never reads, uploads, drops or hashes a file. A forecast's interval and backtest error, an estimate's cases and drivers, a base rate, a scenario share and a sum of grid cells are returned facts like any other. The browser only formats returned facts.

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
| `react-map-gl` | Mounting MapLibre imperatively in one component has fewer moving parts (stack research) |
| A charting library | Bars, the people-by-hour chart, trend lines with projections, the forecast chart with its interval band, the base-rate table, the pay-band and busyness charts, the estimate and scenario charts, ranking tables and the supplier lens are small SVG components so that every label goes through the Fact chip |
| Any CDN, hosted font, hosted tile or analytics service | Offline operation and the no-third-party rule (section 7); the optional live traffic tiles are fetched by the local server, so the browser still contacts its own origin only |

**Drawing tools.** Free-drawn areas return with [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) (item 19). The polygon, radius and travel-time tools are built either on a drawing library that supports MapLibre GL JS 6 or in house over MapLibre pointer events. The spike of slice S1 chooses one and records it with an exact pin and a written retreat; the stack research of 2026-11-11 did not cover a drawing library, so no version is named here.

**Newer than most training data.** MapLibre GL JS 6 (released 22 July 2026) is ESM-only and WebGL2-only, removed `map.transform`, needs one worker-URL call under a bundler, throws an initialisation error when WebGL2 is missing, and since 6.9.0 shapes Arabic itself, which deprecates `setRTLTextPlugin`. deck.gl 9.4 (5 September 2026) added `@deck.gl/maplibre`. Coding agents default to v4 and v5 idioms (default imports, UMD script tags, `setRTLTextPlugin`, `MapboxOverlay` from `@deck.gl/mapbox`). Before writing map code, a builder reads the MapLibre v5-to-v6 migration guide, the MapLibre v6 API pages, the deck.gl "What's new" and `@deck.gl/maplibre` pages, and loads the MapLibre agent skills (`maplibre-v6-migration`, `maplibre-pmtiles-patterns`, `maplibre-fonts-glyphs`). No API in this document is to be taken as certain without that check.

| ID | Requirement | Slice |
|---|---|---|
| FE-01 | `web/package.json` lists every dependency with an exact version and the lock file is committed; CI fails on a range specifier. | slice S0 |
| FE-02 | `web/REFERENCE_NOTES.md` records, for MapLibre GL JS 6, deck.gl 9.4 and `@deck.gl/maplibre`, the documentation pages read, the date read, and the idioms that changed from earlier majors. | slice S0 |
| FE-03 | Each pin has a written retreat pin and the spike result that chose between them, recorded before slice S3 starts. | slice S1 |
| FE-04 | deck.gl runs on WebGL2 through `MapLibreOverlay` in interleaved mode; no code path enables WebGPU. | slice S1 |
| FE-05 | No dependency is loaded from a CDN; every script, style, font, glyph, sprite and tile is served by the local FastAPI process. | slice S0 |
| FE-06 | Versions are frozen for the demonstration by `./eii freeze`; after a freeze, changing `web/package.json` requires a new rehearsal. | slice S11 |
| FE-102 | The drawing approach (a pinned drawing library or in-house pointer handling) is chosen at the spike and recorded in `web/REFERENCE_NOTES.md` with the documentation pages read, an exact pin where a library is used, and a written retreat. | slice S1 |

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
    controls/                 Dial, HourControl, DaySelector, MonthSelector, DrawTools, SnapReport, PrivacyReceipt,
                              CoverageBar, BreakEven, SupplierLens, NeighboursChips
    journeys/                 JourneyHome, journey workspace layouts, service entries
    views/                    RankingPanel, ReverseView, SimilarAreas, LabourMarketView, WhatChanged,
                              RegisterCompanyList, CompanyCard, BusinessList, FdiList, AgencyRecords
    cases/                    CaseGallery, CaseStepper, SampleFileLoader
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
| `/{lang}/` | home: ask bar, the journey home (seven decisions, three services, four cases), the living map on the Stage | `company_a`, `company_b` |
| `/{lang}/brief/{brief_id}` | workspace: Stage, Brief, Plan rail; the journey's layout (ranking, reverse, labour market, register-company lists, what changed and the other views of section 4.8 are layouts of a brief) | owner seat of the brief |
| `/{lang}/compare/{brief_id}/{brief_id}` | two doors side by side (capability S6) | owner seat of both |
| `/{lang}/story/{step}` | guided story, steps 0 to 9 (the ten scenes; storyboard in [11](11_DESIGN_DIRECTION.md)) | any |
| `/{lang}/case/{case}/{step}` | one case story, `{case}` being `c1` to `c4` (section 4.9) | `company_a`, `company_b` |
| `/{lang}/trust` | Trust centre | any |
| `/{lang}/proof` | Proof room | any |
| `/{lang}/oversight` | Oversight screen (capability S4) | `oversight` |
| `/{lang}/pack/{brief_id}` | briefing pack page (capability S11) | owner seat of the brief |
| `/{lang}/presenter` | presenter console window | any, presenter mode only |

`{lang}` is `en` or `ar`; a bare `/` redirects to `EII_LANG_DEFAULT` as reported by the server. View state that is not a brief (pin, area mode and cut-off, the identifier the server gave a drawn shape, dial position, summer switch, hour, day type or event day, month, hero layer, the 3D view switch, ranking weights and public-only mode) is held in the query string. The vertices of a drawn shape and the rows of a sample file are never put in the address. The router is an in-house component over the History API (ASSUMPTION: eleven routes do not justify a routing dependency; replace with a pinned library if it grows past about 150 lines).

### 3.3 State management

One store holds application state; React components subscribe with `useSyncExternalStore` through selectors (ASSUMPTION: no state library in v1; a reducer and selectors are enough for one session per window).

| Slice | Holds | Written by |
|---|---|---|
| `session` | seat key from the signed session cookie, display name of the seat, language, presenter mode, release id, whether a sample file is loaded, its case and its closed key (never its rows) | seat picker, router, `/api` config, sample-file loader |
| `view` | pin, area request (mode, cut-off or radius preset, the drawn shape's identifier), hero layer, 3D view switch, dial situation, summer switch, hour, day type or event day, month, playback running or paused, ranking weights, public-only mode, compare pair | user controls, `stage` directives, story |
| `brief` | answer id, brief id, lifecycle state, plan steps, facts by id, structured brief keys and slots, validated layout, receipt | SSE client |
| `story` | current step, prepared-run flag, controls locked or unlocked | stepper, presenter channel |
| `connectivity` | server reachable, model available or template writer, store `postgres` or `embedded`, oversight paused, traffic provider on or off (never the key) | health polling, SSE status events |

The camera is not React state. MapLibre owns the camera; the store receives a debounced camera summary for the URL and for `stage` directives. Layer data is passed to deck.gl by reference; changes of time or selection use update triggers or filter uniforms, not new data arrays (deck.gl performance guide: changing `data` rebuilds every buffer).

### 3.4 Data fetching

- One typed client in `src/api/` wraps every REST call; components never call `fetch` directly.
- Responses are cached per `release_id`. The release is immutable, so a cached response is valid until the release id changes; a change clears the cache and reloads the shell.
- Layers above about 10,000 rows travel as Arrow and smaller results as JSON (stack research recommendation). The client decodes Arrow off the main thread in a Web Worker.
- Every fact received is put into the fact registry (`src/facts/registry.ts`) keyed by `fact_id`. Components render facts by id from the registry, never from ad-hoc copies.
- Requests carry an abort signal; asking a new question aborts the previous answer connection.
- An hourly layer (estimated people, crowd density, traffic) loads every stored hour of the selected day type, season and month in one payload; the hour is then selected through update triggers or filter uniforms, never by fetching or rebuilding data per hour (FE-91). The live traffic layer (FE-136) is not an hourly payload.
- A drawn shape and ranking weights are posted to their server routes ([08 Back end](08_BACKEND.md)). A sample file is never posted: the Sample-file loader posts only the closed key of a case's shipped file, and the server loads the committed file that the key names (FE-120). The application has no file input, no drag-and-drop or paste path for files and no client-side hashing. The browser never receives a sample file or its rows: no local storage, IndexedDB, Cache Storage or service worker holds them, and the browser holds only the facts the server returns.

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

The completed brief contains structured data only: `catalogue_version`; `headline_key`; `decision_template_key`; `observed[]` and `inferred[]`, each item carrying `claim_key` and fact-id `slots`, with `strength` on inferred items; application-selected `still_to_test[]` and `not_measured[]`; `next_questions[]` carrying `question_key` and `slots`; `layout[]` as an ordered list of `{component, props}`; and `stage[]` directives. Every Observed and Inferred sentence is an application-owned English or Arabic template selected by `claim_key`, with its slots rendered only as Fact chips. The layout is drawn from the closed catalogue: evidence cards, comparison table, band bar, small trend chart, `supplier_lens`, neighbours chips, break-even calculator, coverage bar, snap report and map directives, and the components of the families added in [09](09_AI_ASSISTANT.md) section 5.1 (people card and people-by-hour chart, traffic-by-hour chart, ranking and fit tables, similar-areas list, access card, register-company list and company card, business and tender lists, qualification route, Public series card, Public split card, FDI list, agency records, trend with projection, what-changed list, published-visits card, gateway table, imports screen, own-records card, case gallery and brief export), and the families of [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md): `series_forecast` (the forecast chart with its interval band and caption), `base_rates` (base-rate rows with their counts), `site_estimate` and the scenario families `catchment_scenario` and `revenue_range_scenario` (the estimate and scenario panels, every assumption editable), `present_by_pay_band` (the chart on whole release units), `venue_busyness` (the busyness bars), `night_lights`, `population_age_sex` (display only) and `view_3d` (the switch of the optional 3D view). Properties are fact ids, release-unit ids, record ids or enumerations. An invalid item rejects the brief; after one repair attempt, the template writer supplies the playbook's default selection and layout.

A claim slot validates its metric key, unit, geography role, period rule and allowed provenance. Every required slot and caveat must be present; extra slots, an unknown `claim_key`, component or property, and a fact of the wrong kind reject the brief. The five pipeline stages are defined in [09](09_AI_ASSISTANT.md). The Plan rail shows only the application-defined step labels of that document and DES-90; it adds no stage panel.

A Synthetic or Simulated fact is rendered only in a claim or component whose catalogue subject is `area`, titled as a statistic of the area (the shape the user drew, or the area within reach of the pin), or, for one register company, `register_company` ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)), which holds the Public facts of its card, the Synthetic `employee_count` of its attached records and, in a list, the rank and fit facts of tested code, and never a Simulated fact, an estimate, share or score, or a wage, wage bill or other labour or residence fact of the company ([03 Data contracts](03_DATA_CONTRACTS.md) section 9.1, DAT-145). Named synthetic firms and the subject `synthetic_firm` are retired. A claim or component whose subject is `place_public` or `fdi_project` accepts Public facts only. The site estimate, the scenario panels and the figure of people present by pay band have the subject `area`. The relative busyness of a named venue is a Public fact of the subject `place_public`. A forecast, a base rate and a sum of grid cells keep the subject and geography of their series or source; a forecast of a released monthly series is Synthetic and has the subject `area` of its series. The check uses the resolved place and slot semantics, never wording.

### 3.6 Stage directives

The `stage` tool's directives are a closed TypeScript discriminated union: `fly`, `layer`, `highlight`, `rings`, `dial`, `split`, `set_scenario_inputs` (exact payload shapes from [08 Back end](08_BACKEND.md), section 6.2). [Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) lets the closed list grow to cover the journeys; the front end expects directives that select a stored hour, a day type or event day and a month, whose names and payloads 08 fixes. A directive outside the union, or with an invalid payload, is ignored and logged, never partly executed. A directive never carries a number to render; it carries ids, enumeration keys and coordinates, and never the vertices of a shape or a weight.

### 3.7 Error boundaries

| Boundary | Catches | Fallback |
|---|---|---|
| App | anything not caught below | full-page error with Reload and Reset; standing strip stays |
| Stage | map initialisation failure, WebGL2 missing, context loss, layer errors | "The map is paused on this display" panel; the Brief keeps working |
| Brief | claim-template, layout or card render errors | the validated cards already shown stay; the failed item shows its governed error state |
| Each card | one card's render error | that card's error state only |
| Each view | a ranking, reverse, labour-market, what-changed, list or case-story view error | that view's error state with a way back; the Stage, the Brief and the ask bar keep working |
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

Names follow the pinned interface vocabulary. Visual specification of each component is in [11](11_DESIGN_DIRECTION.md). The last column names the capability or journey that each row serves, so each row is built with the slice that builds it; [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) replaced the cut order with the build order.

### 4.1 Shell and session

| Component | Responsibility | Inputs | States | Capability |
|---|---|---|---|---|
| Standing strip | the permanent demonstrator notice; never dismissible; present on every route, in presenter mode and in the pack | language | always shown | capability M5 |
| Provenance legend | the four marks with word and texture; shows the hero layer's class | hero layer, language | always shown | capability M5 |
| Viewing-as badge | states which seat is looking ("Viewing as") | seat key and display name | company seat, oversight seat | capability S4 |
| Seat picker | chooses `oversight`, `company_a` or `company_b` for this window; three windows on one machine | seat list from the API | loading, ready, error | capability S4 |
| Reset | returns to the home view and closes every panel, clears drawn shapes and ranking weights, returns the hour, day and month to their defaults and unloads a session sample file; always visible in explore mode | none | enabled, disabled during a locked story step | story |
| Status badges | "Template writer", "Spend cap reached", offline, store `embedded`, oversight paused, "prepared" replay, "Live traffic" while the provider layer is on | connectivity slice | hidden when normal | capability M7 |
| Theme switch | switches between the complete dark and light themes without a reload | presenter setting | dark, light | story |
| Room scale | applies `1.0`, `1.15` or `1.3` to wall type tokens | presenter setting | three closed values | story |
| Pause motion | stops continuous motion and applies the reduced-motion state | presenter setting, operating-system preference | running, paused | story |
| Presenter pointer | shows the 40 px room-visible presenter pointer | presenter setting, pointer position | hidden, shown | story |

The seat picker writes the signed `eii_seat` cookie. The stage window and presenter console share one browser profile, so they share the selected seat and `BroadcastChannel`; the oversight and other company windows use separate profiles.

### 4.2 Question and brief

| Component | Responsibility | Inputs | States | Capability |
|---|---|---|---|---|
| Ask bar | bilingual question entry with autocomplete from `resolve` for places and activities, on every module (FE-123) | text, language | idle, suggesting, submitting, disabled | capability M7 |
| Understanding chips | "We understood your question as…" chips: commerce activity code, ISIC Rev.4 class, public place category, and the "not mappable" bucket | `resolve` candidates | confirmed, ambiguous (choose one), not mappable | capability M8 |
| Stage | the living map: basemap, buildings, real business points, the register's establishment points, door pin, drawn shape, released area, one hero layer, watermark | view slice, layer data | loading, ready, paused, offline-tiles error | all |
| Brief | the answer column: headline; decision sentence; the three evidence-status sections Observed, Inferred and Still to test; the separate coverage section Not measured; validated component layout; Explain, Compare, Pin, Pack and live-only Regenerate; three suggested next questions | brief slice | idle, gathering, writing, complete, partial, declined | capability M7 |
| Plan rail | the steps of the current answer; tap a step to see its tool and status | plan steps | pending, running, done, suppressed, failed | capability M7 |
| Evidence card | one block of evidence (types in 4.3); headline, chips, coverage bar, caveats | card descriptor and fact ids | loading, ready, suppressed, no data, error | capability M1 to capability S11; journeys D1 to D7 |
| Fact chip | renders one fact only after its complete source chain resolves: value with unit, provenance mark and word, reliability mark, "your inputs" tag; opens the Evidence drawer; refuses an incomplete chain | `fact_id`, variant | loading chain, value, suppressed, inferred-from-your-inputs, error (provenance or chain mismatch) | capability M5 |
| Evidence drawer | labelled "Source chain"; shows fact → release table → method and version → publisher, dataset, licence, retrieval date and file hash, plus value, provenance, `input_classes`, evidence status, period, geography, rule, coverage, caveats and release | `fact_id`, `lineage_ref` | loading, ready, error | capability M5 |
| Snap report | requested area against released area, number of units, rules that set it; drives the snap animation; shown only when a figure of a protected record type is on screen for the area (FE-109) | `make_area` facts | animating, settled, not shown (Public and Simulated figures only) | capability M4 |
| Privacy receipt | per answer: rules version, parameter set, units used, suppressed elements with reasons, release id, what went to the AI, and the accounting result labelled "Checked before display" | `receipt` event | collapsed, expanded | capability M4 |
| "Why can't I see this?" | on every blank: the suppression or no-data reason and the nearest publishable alternative | status, template key, reason key | shown on every suppressed or no-data element | capability M4 |

### 4.3 Evidence card types in v1

| Card type | Content | Release source | Provenance | Capability |
|---|---|---|---|---|
| `work_pay` | "People who work within reach": rounded count of covered earners, median wage band, quartile band range, band distribution bar; mean wage and wage bill only under "More evidence" with "the average alone is not enough" | `worker_pay` | Synthetic | capability M1 |
| `live_pay` | "People who live within reach": the same, plus the housing split of covered earners (`family_housing`, `labour_accommodation`, `institution` and `unknown`, and an explicit `other` row when pooling occurred) with the not-measured coverage count shown separately. The count and the shares beside it come from one additive family (FE-100) | `resident_pay` | Synthetic | capability M1 |
| `presence` | "Estimated people around this location": the estimated count with its range for the selected stored hour, day type, season and month, split into workers, residents and visitors, and a people-by-hour chart of the stored hours with range marks ([11](11_DESIGN_DIRECTION.md)); never the footfall of a building or business; its lineage names the calibration anchors of the simulation (decision 0019 item 18), and its split by pay band is the separate `present_by_pay_band` card. Public monthly context series are shown separately on their own Public cards for context and are not matched to the hour | the hourly presence release table with ranges ([03](03_DATA_CONTRACTS.md)), `pub_transit_monthly`, `pub_hotel_monthly`, `pub_price_index` | Simulated; context cards Public | capability M2 |
| `public_context` | licences in the municipality against the national rate; zone electricity growth; metro and tram riders | `pub_licence_active`, `pub_zone_utility`, `pub_transit_monthly` | Public | capability M3 |
| `places` | named public places with network distances; the standing "open listings are incomplete" note | `pub_place` and `pub_place_fsq` via `scan_places` | Public | capability M3 |
| `property_price` | sale price per square metre, and residential unit sales of the weekly bulletin, each always with its deal count | `pub_property_sale`; the residential unit sales of [04](04_PUBLIC_DATA_PACK.md) | Public | capability M3 |
| `unit_economics` | sector cost structure for the activity, with the break-even calculator | `pub_sector_accounts` via `sector_facts` | Public; result Inferred, "your inputs" | capability M6 |
| `licensed_vs_operating` | share of licensed food outlets within reach that show payroll activity, by size band; an aggregate strip visually separate from named places | `outlet_register` | Synthetic | capability S1 |
| `staffing_pay` | pay bands for the outlet's jobs among people living within reach, for occupation groups `0` to `9` and `unmapped`, with an explicit `other` row when pooling occurred, beside national averages and the statutory minimum. The not-measured count is not an occupation group | `occupation_pay`, `pub_wage_table` | Synthetic and Public, marked per chip | capability S2 |
| `national_pay` | what moved national average pay (pay against workforce mix), with the table named | `pub_wage_table` | Public | capability S3 |
| `supplier_lens` | ranked horizontal bars, one block per basket input and at most five origins per input, with share, "Calculated import unit value (QAR per kg)", valuation basis as the source states it or "not stated by the source", concentration and trend | `pub_customs_import`, `graph_node`, `graph_edge` | Public | capability S5 |
| `compare` | the same evidence for two doors and their shared reach ("shared reach", never lost sales) | `compare_areas` | least-real of inputs | capability S6 |
| `churn` | licence cancellations against the active stock, bulk months flagged; no net figure of issues minus cancellations is formed, and the base rates are on the `base_rates` card | `pub_licence_cancelled`, `pub_licence_active` | Public | capability S8 |
| `neighbours` | at most six chips, "found near", with the coverage note | graph co-location pairs, `pub_place` | Public | capability S9 |
| `home_area` | coarse, protected home-area share of the door's workers, no finer than a large pooled district | `home_area_share` | Synthetic | capability S10 |

Card types added for [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) and [decision 0017](decisions/0017-public-data-additions-and-public-splits.md). Release tables are named by content where [03](03_DATA_CONTRACTS.md) fixes their names.

| Card type | Content | Release source | Provenance | Capability |
|---|---|---|---|---|
| `traffic` | "Traffic by hour": the simulated slowdown on the roads of the area for the selected stored hour, and the drive-time area at that hour against the same area at another hour, compared by a returned fact; with the live provider on, a drive-time area of the session from the provider, marked with the provider and its retrieval time (FE-136) | traffic link speeds by hour and drive-time areas ([03](03_DATA_CONTRACTS.md)) | Simulated with the default provider; a provider area carries its provider mark and its figures the least-real class of their inputs | journey D2 |
| `ranking` | the ranking table (FE-110): candidate areas, every criterion's value, the weights, the rank and the rank-stability sentence beside every rank; public-only mode; a forecast, a base rate or the site estimate may be a criterion, shown with its interval, counts or range and removable by the user | ranking and rank-stability facts (method card C11 of [07](07_ECONOMIC_METHODS.md)) | the least-real class of the criteria; Public in public-only mode, where the site estimate, a forecast of a released series and every criterion with a Simulated or Synthetic input are off and a forecast or base rate of a Public series stays | journey D2 |
| `site_fit` | the reverse (FE-111): activities ranked by fit for the site, with the same table rules | as `ranking` | the least-real class of the criteria | journey D2 |
| `similar_areas` | at most three area types, the official zones ordered by similarity (of the selected type when one is chosen) with the rank-stability sentence beside every position, and each type's stability figure (FE-112) | area types ([07](07_ECONOMIC_METHODS.md) method card C17) | Public | journey D2 |
| `access` | reachable access: the travel-time catchment score, by hour where congestion changes travel time | method card C12 of [07](07_ECONOMIC_METHODS.md) | Simulated by hour with the default provider; otherwise the least-real class | journey D2 |
| `register_company_list` | register companies (FE-115, [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)): prospects, partners, suppliers and complementary firms, each with its card fields and employee count, ordered by tested code over criteria the user can see and change where the journey orders, with the criteria and the rank-stability sentence; no wages, wage bill or other labour or residence detail; selecting a row opens the company card | `register_company_list` and `pub_register_company` ([03](03_DATA_CONTRACTS.md) DAT-140) | Public card fields; the employee count Synthetic, from the attached records | journeys D3, D4 and D7; service S3; cases C2 and C3 |
| `company_card` | the company card of one register company (FE-115): every field the public business register publishes for it, person names excluded, and its employee count from the attached records; opened from an establishment point of the map or a list row; no wages, wage bill or other labour or residence detail | `pub_register_company`, `register_company_list` | Public card fields; the employee count Synthetic, from the attached records | the living map; journeys D3, D4 and D7; service S3; cases C2 and C3 |
| `business_list` | real businesses from public places data and public listings, with the "open listings are incomplete" note; never in the container of a register-company list or a company card | `pub_place`, `pub_place_fsq`; public listings ([04](04_PUBLIC_DATA_PACK.md)) | Public | journeys D1, D3, D4 and D7 |
| `tenders` | public tenders, only where a public source exists; otherwise the card is not offered | the tender source confirmed at slice S2 | Public | journey D4 |
| `qualification_route` | the fixed steps of the structured qualification route, from the catalogue; no figure | catalogue | none | journey D4; service S3 |
| `public_series` | Public figures from the added portal datasets, on their own geography: employer scale by size and activity, industrial capacity, wholesale and retail context, population by age, labour force, students, hotels, visitor arrivals, building permits and completions, certificates of origin and arriving vessels; each with source, reference year or month and retrieval date, and each dataset's known traps as caveats; forecasts of listed series are on the `series_forecast` card and the population grid by age and sex on the `population_age_sex` card | the added datasets of [04](04_PUBLIC_DATA_PACK.md) | Public | per dataset, as [04](04_PUBLIC_DATA_PACK.md) lists |
| `public_split` | an official figure split by sex or nationality (FE-117), tabulated on the source's geography and categories, with source and year; a sum of the population grid over an area is the separate `population_age_sex` card | the split datasets of [04](04_PUBLIC_DATA_PACK.md) | Public | journeys D1, D3 and D5 |
| `fdi_projects` | announced investment projects (FE-116): counts by sector, source country, period and stated location; the list of projects as published announcements with their fields; capex and jobs only with the source's estimate note | `fdi_projects` | Public | journeys D1, D4, D6 and D7; services S1 and S2 |
| `agency_records` | sector context, opportunities, set-up steps, incentive packages and law links from the agency's pages (FE-121), each with its page link and retrieval date | the agency page records of [04](04_PUBLIC_DATA_PACK.md) | Public | journey D1; service S1; the break-even calculator |
| `labour_market` | the labour-market view (FE-114): area pay and occupations with pay bands, middle ranges and earner counts from permitted released units; the wage trend of the same earners for a municipality or nationally, never by sector; national wage trends by sector from the Public activity table, separated from the employment mix; Public series and splits; projections marked as projections; no protected pay band by sector | released monthly pay tables ([03](03_DATA_CONTRACTS.md)); Public series ([04](04_PUBLIC_DATA_PACK.md)) | Synthetic and Public, marked per chip | journey D5 |
| `what_changed` | changes between the selected month and the month compared (FE-113): for synthetic months, the cohort counts of each pair of adjacent months and the wage index of the same earners for each municipality unit that contains units of the area and nationally, a carried-forward pair shown as suppressed, never zero; for Public series, change facts with sign and word; openings and closures; every Synthetic change with its caveat | monthly periods ([03](03_DATA_CONTRACTS.md)); public licence issues and cancellations | Synthetic or Public, per row | journeys D2 and D6; case C4 |
| `published_visits` | published visitor counts of named public places (museums and exhibitions by month, health centres by year), with source and period (FE-125) | the visitor datasets of [04](04_PUBLIC_DATA_PACK.md) | Public | journey D2, as context |
| `gateways` | travel times from the area to the ports, the airport, the free zones and the land routes, as times from this area (FE-126) | road network; traffic by hour | Public (free-flow travel time); Simulated (travel time by hour, with the default provider) | journey D7 |
| `imports_screen` | imports against local production for a product group, worded as a screen, with no currency label until the currency is confirmed | method card C13 of [07](07_ECONOMIC_METHODS.md) | Public | journey D7 |
| `own_records` | facts from the session's sample file by area (case C3 delivery records, case C4 branch sales), tagged "your inputs" | the session's sample file | Synthetic, "your inputs" | cases C3 and C4 |

Card types added for [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md). Release tables are named by content where [03](03_DATA_CONTRACTS.md) fixes their names; the method cards are those of [07](07_ECONOMIC_METHODS.md).

| Card type | Content | Release source | Provenance | Capability |
|---|---|---|---|---|
| `series_forecast` | the forecast of a series of the closed list of method card C30: history, forecast points and the interval as a band, with the caption of `forecast_backtest_range` and the measured backtest error (FE-128); a released monthly series with a carried-forward month in its window shows the `CARRIED_FORWARD` suppression, not a line; `NO_DATA` with the reason `series_too_short`, shown as "not enough history", for a series too short for the backtest | forecast facts of method card C30, from the series' own release table | Inferred; the class of the series (Public, or Synthetic with its Synthetic caveats for a released monthly series) | journeys D1, D6 and D7, as context |
| `base_rates` | entry and closure base rates by activity and on the source's own geography, labelled approximate, each with its numerator, denominator and period; the survival base rate, and any rate whose denominator the Public tables do not carry, as `NO_DATA` with the reason `no_denominator` (FE-129) | base-rate facts of method card C31, from the Public licence tables | Public | journey D3 |
| `present_by_pay_band` | simulated workers and residents present by pay band for a whole release unit, a day type and an hour (FE-130) | the figure of method card C32, from published presence rows and published pay-band shares | Simulated; Inferred | journey D2, behind "More evidence" |
| `site_estimate` | the low, middle and high cases of the site demand and revenue estimate with its main drivers and, on simulated inputs, the label "estimate on simulated inputs" (FE-131) | estimate facts of method card C33 | the least-real class of the inputs (Simulated); Inferred | journey D2, behind "More evidence" |
| `catchment_scenario` | the share of the user's outlet as a chip and the shares of the competitors as a small table by competitor category and distance band, never a row for a named competitor, a cell of a single competitor merged into the next wider cell and the table left out where method card C34 returns no split, from the user's assumptions (FE-132) | scenario facts of method card C34; Public listings as counts and distances | the least-real class of the inputs; Inferred, "your inputs" | journey D2 |
| `revenue_range_scenario` | low, middle and high cases and the break-even point of the user's outlet, from the user's assumptions (FE-132) | scenario facts of method card C35 | the least-real class of the inputs; Inferred, "your inputs" | journey D2 |
| `venue_busyness` | the relative busyness by hour of a named venue, titled "Google Maps popular times", with its retrieval date (FE-133) | `pub_venue_busyness` | Public | journey D2, as context |
| `night_lights` | night-time radiance by area and month, with the NASA acknowledgement (FE-134) | `pub_night_lights` | Public | journeys D1 and D6 |
| `population_age_sex` | the population by age band and sex summed over whole grid cells of an area the user chose, display only (FE-135) | `pub_pop_agesex_grid` | Public | journeys D1, D3 and D5 |

The flagship shows four hero cards (`presence`, `places`, `work_pay` with `live_pay`, `unit_economics`); further cards, `traffic` among them, sit behind "More evidence". The estimate, scenario and pay-band cards of the table above sit behind it too; none is a fifth hero card.

While OI-03 is open, restaurant totals, the `unit_economics` hero, the break-even panel, the `site_estimate` card and the `revenue_range_scenario` card stay off screen, and the `national_pay` card is not rendered.

### 4.4 Stage controls and small visual components

| Component | Responsibility | Inputs | States | Capability |
|---|---|---|---|---|
| Dial with the summer switch | four stored situations `weekday_lunch`, `weekday_evening`, `friday_evening`, `ramadan_iftar`; choosing one sets its day type and season and moves the Hour control to the first hour of the situation's window; the `summer` switch applies to the first three and is disabled, with its reason, on `ramadan_iftar`; crossfades between stored hours; its centre shows the estimated count with its range for the selected area, never a count without its range and never an index | view slice | each situation; no situation (an event day is selected); summer on, off, not applicable | capability M2 |
| Hour control | steps through the hours the release stores for the selected day type, season and month, one stored hour at a time; Play animates the day by holding each stored hour and cross-fading to the next, never drawing an interpolated frame; Pause motion and reduced motion stop playback; hour labels are `reference` chips (section 5) | view slice; the release's closed hour list | an hour selected; playing; paused; unavailable | journey D2 (map foundation) |
| Day selector | the day of the hourly layers: the day types behind the dial situations, and the three event days (National Day, a day in Ramadan, a major match), each a simulated day type with its own hour-by-hour profile; choosing an event day clears the dial's situation; the summer switch is disabled, with its reason, where the release holds no summer profile for the selected day | view slice; the release's closed list of day types | a day type; an event day; summer not applicable | journey D2 (flagship) |
| Month selector | the month of every monthly figure, from the release's monthly periods inside its one protected window; a Public monthly layer, such as night-time radiance, keeps its own list of months with the month on every chip (DES-169 of [11](11_DESIGN_DIRECTION.md)); choosing a second month for comparison opens "What changed"; month labels are `reference` chips | view slice; the release's closed month list | one month; a comparison pair | journeys D5 and D6 |
| Drawing tools | polygon (vertices placed by pointer, touch or keyboard, editable until the shape is submitted), radius (a circle from the closed presets) and walk or drive time (from the closed cut-offs, a drive time at the hour of the Hour control); the submitted shape is posted to the server, which returns its identifier and its facts; limits on vertices, size and frame are those of [08 Back end](08_BACKEND.md), and a refused shape shows its governed reason | pointer, keyboard, view slice | idle, drawing, editing, submitted, refused | journey D2 (flagship) |
| Area controls | distance (radius presets), walk or drive cut-offs from the closed schema, or a drawn polygon; drive 30 minutes is available only on `staffing_and_pay` | pin and playbook | distance 250 m, 500 m, 1 km; walk 5, 10, 15 minutes; drive 5, 10, 15 minutes and staffing-only 30 minutes, each drive time at a stored hour with the default provider (with the live provider on, a traffic-aware drive-time area is requested through the server, FE-136); a drawn polygon | capability M1, capability S2, journey D2 |
| Coverage bar | the C8 Public proxy, naming its geography, with the remainder labelled "outside this proxy", never Not measured; it uses the finest admitted geography, the census map layers included under [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 10, or returns `NO_DATA`. The separate protected `not_measured_count` appears only beside the resident housing split as its own population; no not-measured share is derived by subtracting the Public proxy. A chart, so not mirrored | coverage facts | ready, suppressed, no data | capability M5 |
| Reliability mark | marks small-count figures by reliability band | `reliability` of the fact | none, low | capability M5 |
| Break-even calculator | The break-even panel shows six inputs, in this order: monthly rent in QAR, seats (whole number, at least 1), average bill in QAR, opening days (default 30, editable), expected covers per day (optional), monthly staff cost in QAR (optional). It posts them to the server method in document 07. Results are inferred "your inputs" chips: 2022 covers per day, and the minimum and maximum of that figure across 2018–2022. Breakpoints appear only when expected covers is filled: maximum rent, minimum bill and, in mode B (the user's staff cost), maximum staff cost; the track's tick is maximum rent and the marker is the entered rent. With expected covers empty, no breakpoint is shown. The optional second result line is labelled "to earn the sector's 2022 surplus share" and is never called break-even. Rent opens empty. An optional input after the six chooses one incentive package from the agency's pages (FE-28); the scenario tools of FE-132 sit beside it | Public norms, user inputs, the agency's incentive packages | empty, valid, invalid input, computed | capability M6 |
| Supplier lens | SVG horizontal bars, one block per basket input, at most five origins, longest bar first, each origin a Public fact chip for share and for "Calculated import unit value (QAR per kg)", the valuation basis as the source states it or "not stated by the source", plus a concentration chip and a trend line. The browser draws the tool's list and does not truncate, rank or recompute it. No map and no arcs. | ordered list from `supplier_lens` | ready, empty, error | capability S5 |
| Neighbours chips | at most six category chips; present ones marked, absent ones "not found in public places data" | `neighbours` facts | ready, no data | capability S9 |
| Scenario tools | the inputs of the catchment-share scenario and of the revenue-range scenario (FE-132): the attractiveness of the user's outlet against the competitors as a group or by competitor category, the competitor-distance setting, the capture rate and the average bill; each is an `input` chip, and the results are the user's scenario | typed inputs; the results from the server | empty, valid, invalid input, computed, off while OI-03 is open (revenue range) | journey D2 (flagship) |
| 3D view switch | turns the optional 3D view of the hero layer on and off (FE-138); off by default, off in the guided story, and absent when the hero layer has no unit statistic to extrude | view slice | off, on, unavailable | journey D2 (map foundation) |

The break-even calculation runs on the server through the deterministic tested method of [07](07_ECONOMIC_METHODS.md), called on input change after a short debounce. The browser sends typed inputs and renders returned `inferred` facts with the "your inputs" tag; it does not calculate, compare, round, rank or choose a displayed value. Results are never stored in the release. The same holds for a drawn shape, the ranking weights and the Hour, Day and Month controls: each posts or selects typed inputs and closed keys, and every figure on screen is a returned fact.

### 4.5 Rooms

| Component | Responsibility | Inputs | States | Capability |
|---|---|---|---|---|
| Oversight screen | fixed de-identified ledger projection and roll-ups of where and what companies are asking above the distinct-organisation minimum; no organisation identity, question text or brief text; live rows tagged "this session", seeded history marked Synthetic (OI-08 default) | ledger stream, roll-up facts | live, paused (store away), empty | capability S4 |
| Trust centre | rules in plain language from the live `rules_version`, what the AI can see, egress records, sources and licences with their retrieval dates (for the two investment sources, the relative-busyness source, the traffic provider and the weather source, the publisher's terms as read at fetch and the basis of use recorded under [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) and [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md); for the relative-busyness source the basis `owner_decision`), the method card of the forecasts with its backtest summary, limits (among them that each model reads the release contract it will read later, while synthetic and simulated data fill it now), prohibited claims, and the sentence in FE-101 | API | loading, ready, error | capability M4, capability M5 |
| Proof room | attack replay (labelled as a replay of signed build-time results), survival figures for parameter sets A and B, protected tables for exactly the one set exported in the mounted release, two-engine parity results, sealed reveal and fidelity report; a canary is named only by its scenario label; one line read from the review log, and nothing else from the typed-decision gateway: "N activity codes; review order machine-assisted; every mapping signed by a person." No score, badge, panel or run-time call; `web/` does not import the gateway. | API | loading, ready, error | capability M4, capability S7 |

### 4.6 Story and presenter

| Component | Responsibility | Inputs | States | Capability |
|---|---|---|---|---|
| Story stepper | steps 0 to 9 of the guided story; discrete and reversible; a visible position indicator; at step 9 controls unlock on the same map with a permanent Reset | story script, step | locked step, transition, unlocked | story |
| Presenter controls | next, back, language, reset, offline, one-way store switch at a request boundary, theme, room scale, Pause motion and 40 px presenter pointer; Next also applies a step's prepared inputs (a drawn shape, an hour, a day, ranking weights, the closed key of a case's shipped sample file); presenter API calls carry `X-EII-Presenter-Token` | keyboard, clicker, presenter console | presenter mode on or off | story |
| Presenter console | a second window in the stage window's browser profile, with notes, the same controls and every field of `GET /health` (08 fixes the fields; the state of the traffic provider, on or off with its last status and never the key, is expected among them), polled every 5 s; synchronised with `BroadcastChannel` (same-origin, no network for window synchronisation) | channel messages, health response | connected, disconnected, degraded | story |

The story script (`web/src/story/script.json`) lists, per step, the route, camera target, hero layer, dial situation, hour, day type or event day, month, the prepared drawn shape, the prepared ranking weights, the closed key of the case's shipped sample file and the prepared brief id; its content follows the storyboard in [11](11_DESIGN_DIRECTION.md). A prepared shape is a typed input recorded in the script, so the prepared answer's memo key matches; the presenter never draws freehand in a locked step. While a story step is locked, map pan, zoom, a new pin and the drawing tools are ignored. The stepper, dial, summer switch, Hour control, Day selector, language control, Fact chips, break-even inputs, ranking weights, attack Run buttons and Pack stay enabled. Reset is disabled only during a scripted camera move. In explore mode a user gesture interrupts any camera move.

### 4.7 Briefing pack page

The pack is one A4 portrait page in the light theme, bilingual on that page: English label, Fact chip, Arabic label, so each number is printed once. It is the one-page brief export of [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) (item 14) for every journey, service and case brief, built from the same validated brief and facts. A second page is used only when the content overflows. Simulated prints as static dashes. The standing strip and watermark are on every page. The four provenance words use print-safe textures, and the Source chain section lists each fact's release table, method and version, publisher, dataset, licence, retrieval date, file hash and release. A pack inherits the classes of its facts.

### 4.8 Journey views

Each view is a layout of a brief from the closed component catalogue of [09](09_AI_ASSISTANT.md); the Stage beside it shows the view's hero layer. Visual rules are in [11](11_DESIGN_DIRECTION.md).

| Component | Responsibility | Inputs | States | Capability |
|---|---|---|---|---|
| Ranking panel | candidate areas with every criterion's value, its weight as an editable `input` chip, the rank and the rank-stability sentence beside every rank; a public-only switch; edits post the weights and render the returned ranks | ranking facts, user weights | ready, recomputing, public-only, suppressed, error | journey D2 |
| Reverse view | activities ranked by fit for the selected site, with the Ranking panel's table rules | fit facts, user weights | ready, recomputing, error | journey D2 |
| Similar areas | at most three area types, the areas of the selected type on the Stage, and each type's stability figure | area-type facts | ready, no data | journey D2 |
| What changed | rows of change facts between two months, each with its sign and word, Public or Synthetic per row; selecting a row highlights its area on the Stage | month pair, change facts | ready, no change, no data | journeys D2 and D6; case C4 |
| Labour-market view | area pay and occupations with pay bands, middle ranges and earner counts from permitted released units; the wage trend of the same earners for a municipality or nationally, never by sector; national wage trends by sector from the Public activity table, separated from the employment mix; Public series and splits; projections | labour facts, month | ready, suppressed, no data | journey D5 |
| Register-company list | register companies with their card fields and employee counts, ordered by tested code over criteria the user can see and change where the journey orders, with the rank-stability sentence; selecting one opens its company card | `register_company` facts | ready, shortened by a privacy rule, suppressed, no data | journeys D3, D4 and D7; service S3 |
| Company card | one register company: every field the public business register publishes for it, person names excluded, and its employee count from the attached records | `register_company` facts | ready, employee count withheld (`CARRIED_FORWARD`), no data | the living map; journeys D3, D4 and D7; service S3 |
| Business list | real businesses from public places data and public listings, in their own container | `place_public` facts | ready, no data | journeys D1, D3, D4 and D7 |
| FDI list | announced investment projects as published announcements, filtered by sector, source country, period and stated location | `fdi_projects` facts | ready, filtered, no data | journeys D1, D4, D6 and D7; services S1 and S2 |
| Agency records | sector context, opportunities, set-up steps in their published order, incentive packages and law links, each with its page link and retrieval date | agency record ids and facts | ready, no data | journey D1; service S1 |

### 4.9 Journey home, cases and sample files

| Component | Responsibility | Inputs | States | Capability |
|---|---|---|---|---|
| Journey home | the ask bar over three groups: the seven decisions, journeys D1 to D7; the three services, S1 to S3; the four cases, C1 to C4. Each card has a one-line question and the class words of the evidence it will show | catalogue | decisions, services, cases (the group shown) | journeys |
| Case gallery | the four case cards, each with its question, the illustrative-case note and a one-click start | catalogue | ready | cases C1 to C4 |
| Case stepper | the steps of one case story; discrete and reversible; "Prepared" on prepared answers; ends with the case's answer | case script, step | step, transition, ended | cases C1 to C4 |
| Sample-file loader | for cases C3 and C4 only: one closed control for each shipped synthetic sample file of the case, which posts that file's closed key so that the server loads the committed file into the session and seat; shows its Synthetic mark and fixed sentence, and unloads it; it has no file input and no drop area (FE-120) | the closed key chosen, session | empty, loading, loaded, refused, unloaded | cases C3 and C4 |

| ID | Requirement | Slice |
|---|---|---|
| FE-18 | Every component of sections 4.1 to 4.9 exists under the name given, with each listed state reachable from a component test fixture. | per row |
| FE-19 | The standing strip appears on every route, in presenter mode and on every printed pack page, and no control hides it. | slice S3 |
| FE-20 | The Viewing-as badge shows the seat read from the signed session cookie on every route after the seat picker; no route or request field selects a seat. | slice S9 |
| FE-21 | The `live_pay` card always shows `family_housing`, `labour_accommodation`, `institution` and `unknown` for covered earners, an explicit `other` row when pooling occurred, and the not-measured count separately from those rows. The count and the shares beside it come from one additive family (FE-100). The not-measured count is a separate population. A fixture missing any of the four classes, or missing the not-measured count, fails the card test. A pooled release that omits `other` fails the card test. | slice S6 |
| FE-100 | Every card that shows a count with adjacent non-ratio shares takes both from one additive family named in the fact lineage (PRV-30). The closed ratio-statistic list is mean wage and the coverage, irregular and deployed-elsewhere shares. Each ratio uses numerator and denominator columns from the same stored rows — one table, one partition, one unit set and one measure where applicable — even when those columns belong to two additive families, and its fact lineage names both. No other card figure uses two families, and no screen sets two routes to one population side by side as two numbers. The base rates of method card C31 are Public ratios of counts from the Public licence tables: each is shown with its numerator and its denominator as chips, its lineage names the tables of both, and it lies outside the closed list above, which governs protected rows. | slice S6 |
| FE-101 | The Trust centre shows this sentence: "Figures from different tables can differ slightly because each table is protected on its own." | slice S10 |
| FE-22 | Mean wage and wage bill appear only under "More evidence", together with the reading guidance "the average alone is not enough". Exception: scene 2's two guidance plates show the mean chips, then the median band, the band bar, the housing split and the coverage bar. No other surface shows the mean or the wage bill outside More evidence. | slice S6 |
| FE-99 | The `staffing_pay` card lists occupation groups `0` to `9` and `unmapped`, and an explicit `other` row only when pooling occurred. It does not show the not-measured count as an occupation group. | slice S7 |
| FE-23 | The `presence` card and the Dial show estimated counts of people, always with their range, labelled "Estimated people around this location", and never name a building or business as the subject of presence; no surface shows a count of people without its range or as the footfall of a named building or business ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), item 7, which replaces the earlier index). | slice S6 |
| FE-24 | The `places` card shows Public facts only and always shows the "open listings are incomplete" note; a Synthetic or Simulated fact passed to it is a test failure. | slice S3 |
| FE-25 | The `property_price` card never shows a price without its deal count. | slice S3 |
| FE-26 | The `licensed_vs_operating` strip is rendered as an aggregate, in a container visually separate from named places, with no place names inside it. | slice S6 |
| FE-27 | The summer switch is disabled on `ramadan_iftar` and shows why. | slice S6 |
| FE-28 | The break-even panel shows six inputs, in this order: monthly rent in QAR, seats (whole number, at least 1), average bill in QAR, opening days (default 30, editable), expected covers per day (optional), monthly staff cost in QAR (optional). It posts them to the server method in document 07. Results are inferred "your inputs" chips: 2022 covers per day, and the minimum and maximum of that figure across 2018–2022. Breakpoints appear only when expected covers is filled: maximum rent, minimum bill and, in mode B (the user's staff cost), maximum staff cost; the track's tick is maximum rent and the marker is the entered rent. With expected covers empty, no breakpoint is shown. The optional second result line is labelled "to earn the sector's 2022 surplus share" and is never called break-even. Rent opens empty. After the six inputs, an optional input chooses one incentive package from the agency's pages: it lists only the packages the release holds, each with its source page and retrieval date; the choice is posted with the other inputs; the results keep the "your inputs" tag; and no Public figure changes ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)). The scenario tools of FE-132 add their own inputs beside the panel and leave the six inputs as they are. The whole panel stays off screen while OI-03 is open, and so does the revenue range of FE-132. | slice S7 |
| FE-29 | The `supplier_lens` component draws SVG horizontal bars, one block per basket input and at most five origins per input, in the order returned by the tool. Each origin has Public fact chips for share and "Calculated import unit value (QAR per kg)", the valuation basis as the source states it or "not stated by the source", plus a concentration chip and trend line. The browser does not truncate, rank or recompute the list; it draws no supplier map, arc or node graph. | slice S7 |
| FE-30 | Neighbours chips show at most six chips, use the words "found near", and show the coverage note. | slice S6 |
| FE-31 | The Oversight screen never receives or displays an organisation identity, seat display name, question text or brief text in ledger rows or roll-ups. | slice S9 |
| FE-32 | The Oversight screen shows "paused" when the ledger store is away and resumes without a reload. | slice S9 |
| FE-33 | The Proof room labels the attack comparison as a replay of signed build-time results, names canaries only by scenario label, may show survival figures for both parameter sets but protected tables for exactly the exported set, and shows only the activity-spine lineage line from the typed-decision review log: no gateway score, badge, panel, control or run-time call. | slice S10 |
| FE-34 | The story stepper advances and reverses one step at a time from keyboard, clicker and console. During locked steps only map pan, zoom, a new pin and the drawing tools are disabled; Reset is disabled only during a scripted camera move; step 9 unlocks exploration on the same map. | slice S10 |
| FE-35 | The presenter console shares the stage window's browser profile, stays in step through `BroadcastChannel`, polls every `GET /health` field every 5 s, and sends the per-session presenter token on presenter routes. | slice S10 |
| FE-36 | A replayed prepared run shows the "prepared" badge for its whole duration. | slice S10 |
| FE-37 | Explain, Compare, Pin and Pack appear on every complete brief, followed by three suggested next questions. Explain opens the Evidence drawer for the brief's first fact; Pin drops the brief's pin and runs the snap. Regenerate also appears and is enabled only in `live` mode. | slice S6 |
| FE-38 | The pack is bilingual on one A4 portrait page unless it overflows. Every printed number is one Fact chip between its English and Arabic labels, and its complete source chain appears in the pack's Source chain section. | slice S10 |
| FE-106 | The Hour control offers only the release's stored hours for the selected day type, season and month. Play steps one stored hour at a time with the hold and cross-fade of [11](11_DESIGN_DIRECTION.md) and never draws an interpolated frame or value; Pause motion and `prefers-reduced-motion` stop it; the Right and Left arrow keys step one hour forward and back in both languages; hour labels are `reference` chips. | map foundation |
| FE-107 | The Day selector offers the day types behind the dial situations and the three event days as simulated day types. Choosing an event day clears the dial's situation, disables the summer switch with its reason where the release holds no summer profile for that day, and shows the fixed event-day caveat of [11](11_DESIGN_DIRECTION.md): the profile is simulated and is not a measurement of the event or the attendance of any venue. | flagship |
| FE-108 | The drawing tools offer a polygon, a radius from the closed presets and a walk or drive time from the closed cut-offs at the hour of the Hour control. A polygon can be drawn by pointer, by touch and by keyboard (a crosshair moved by the arrow keys, a vertex placed by Enter). The submitted shape is posted to the server, which returns its identifier, its facts or a governed refusal; the browser computes no area, intersection, apportioned share or other figure for it. | flagship |
| FE-109 | The snap animation and the snap report appear only when a figure of a protected record type (business register, employment, residence, wages) is shown for the area, and always before that figure. When only Public points and Simulated estimates are shown for a drawn shape, the exact-shape caption of [11](11_DESIGN_DIRECTION.md) appears instead and names the apportioning method of the Simulated estimates; a Public statistic apportioned to the shape shows as Inferred, naming its method and its official geography ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), item 6). In a public-only release, which holds no protected figure, the snap report that `make_area` emits as technical metadata (BE-105) appears only in the Privacy receipt. | flagship |
| FE-110 | The Ranking panel shows, for every candidate area, every criterion with its value as a Fact chip, its weight as an `input` chip the user can edit, the rank as a Fact chip, and the rank-stability sentence beside every rank; no rank is ever shown without that sentence. Editing a weight posts the weights to the server, which returns the new ranks and stability facts; the browser never orders, ranks, normalises or re-weights anything. A public-only switch ranks on Public criteria only. The title and labels carry no advice or verdict wording ([11](11_DESIGN_DIRECTION.md)). | flagship |
| FE-111 | The Reverse view lists activities ranked by fit for the selected site, for property owners matching tenants to the business mix and the catchment's pay profile, under the same rules as FE-110. | flagship |
| FE-112 | Similar areas shows at most three area types, the official zones ordered by similarity with the rank-stability sentence beside every position (MTH-72), the areas of the selected type on the Stage, and each type's stability figure as a Fact chip (MTH-49); every figure in it is Public. | flagship |
| FE-113 | The Month selector offers only the release's monthly periods. Choosing a comparison month opens What changed: each row is a returned fact: for synthetic months, a cohort count of a pair of adjacent months (joiners, leavers and stayers; openings and closures) or the wage index of the same earners for one unit at municipality level or coarser (a municipality unit that contains units of the area, or the national unit), labelled with that unit's own released area; for a Public series, a change fact with an explicit sign and its catalogue word; a carried-forward pair shows its suppressed state and reason, never zero or no change; Public rows stay on their official geography; every Synthetic row carries the fixed caveat that a change between synthetic months is not a change in Qatar. Openings and closures are two separate hero layers, never one net layer. | journeys |
| FE-114 | The Labour-market view shows, as separate views ([11](11_DESIGN_DIRECTION.md) DES-182): area pay, with pay bands, middle ranges and earner counts read only from permitted released units (the whole release units of a snapped area, a municipality unit of the four pay partitions or the national unit), each statistic from the one partition that [07](07_ECONOMIC_METHODS.md) MTH-55 assigns it (a municipality's one earner count from its money unit, its bands and their denominator from its quartile unit, never a second earner count), and the pay figures for the chosen municipality or nationally (Synthetic); occupations with pay bands, middle ranges and earner counts; the wage trend of the same earners only for a municipality unit or the national unit, never for a smaller area and never by sector (Synthetic), each Synthetic figure labelled with its own released area; wage trends by sector only from the public wage series by economic activity (`wage_act`) and only nationally, as each activity's mean pay beside its paid-worker count, with the national change split into within-sector and employment-mix components (Public); no protected pay band by sector, and no sector figure for an area or a municipality; Public series and Public splits with source and year, and projections drawn as [11](11_DESIGN_DIRECTION.md) sets, each labelled a projection with its method and period and never called a forecast. A forecast of method card C30 is not a projection: it appears on its own `series_forecast` card (FE-128). | journeys |
| FE-115 | Named synthetic firms are retired ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)). A Register-company list shows register companies, each with its card fields and its employee count from the attached records, and selecting a row opens its company card. The company card shows every field the public business register publishes for the company, person names excluded, and its employee count; it opens from an establishment point of the map (FE-103) or a list row. Neither shows a company's wages, wage bill or any other labour or residence detail. A list's order is the output of tested code over criteria the user can see and change, shown with its criteria and the rank-stability sentence, and never uses, or breaks a tie by, a company's wages or another unreleased labour or residence value. Showing a card is not a lookup; the front end offers no search by company name and no lookup of an owner or a person. A register-company list or a company card never shares a container, list or row with the Business list of public places data and public listings, which keeps its "open listings are incomplete" note. | journeys |
| FE-116 | The FDI layer draws announced projects at the geography the source states, as solid Public marks, with their counts as `compact` chips in the DOM legend, never at an invented address. The FDI list shows each project as a published announcement with its fields, filters by sector, source country, period and stated location, and offers no search by company name. Every capex and jobs chip carries the source's estimate note, and every FDI chip shows the Public mark with its year. | journeys |
| FE-117 | A Public split appears only on its own Public card, on the source's geography and categories, with the Public mark, source and year, and never as a map layer. A tabulated split is never drawn on a drawn shape, never apportioned to one, never set on one chart or row with a Synthetic or Simulated figure, and no control applies it to a synthetic figure. The one case of a split over an area the user chose is the `population_age_sex` card of FE-135: whole cells of the published grid, summed, Public and display only. | journeys |
| FE-118 | The Journey home shows the ask bar and three groups: the seven decisions, the three services and the four cases. Each decision or service card starts its playbook with one prepared example on a tap; each case card starts its case story with one click. | journeys |
| FE-119 | A case story runs its prepared steps from `/{lang}/case/{case}/{step}`, discrete and reversible, with the "Prepared" mark on prepared answers and the fixed note that the case is illustrative and its company fictional, and ends with the case's answer named in [09](09_AI_ASSISTANT.md) section 3. | journeys |
| FE-120 | No file enters the product from the browser. For cases C3 and C4 the Sample-file loader offers only closed controls, one for each shipped synthetic sample file of the case, and posts only the case key and that file's closed key to the case route ([08 Back end](08_BACKEND.md) fixes the route); the server loads the committed synthetic file that the key names and uses it only when its SHA-256 equals the committed value. The application has no file input, no drag-and-drop or paste path for files and no client-side hashing, and the route accepts only a closed key: it refuses a file body, a path, a URL or an unknown key with the governed refusal and keeps nothing. A loaded file is held only for the session and seat that loaded it and is unloaded by Reset, by a change of seat and at the end of the session; the browser receives none of its rows (section 3.4). Every fact from it carries the Synthetic mark and the "your inputs" tag, and the loader shows the fixed sentence that the file is synthetic, stands for the company's own records and stays in this session. Tests: a scan of the built pages and a browser test find no file-input element and no drop handler on any page; the route loads each closed key and refuses each other body. | journeys |
| FE-121 | Agency records show sector context, opportunities, set-up steps in their published order, incentive packages and law links as Public source records, each with its page link and retrieval date. A record's text is an isolated run with its language marked, and every number in it is a Fact chip. | journeys |
| FE-123 | The ask bar is present on every module (the home, the living map, every journey workspace and view, every case story) in both languages, and every question goes through the pipeline of [09](09_AI_ASSISTANT.md). | journeys |
| FE-125 | Published visitor counts of named public places appear on their own Public cards with source and period, titled as published counts, and the relative busyness of a named venue (a relative index, never a count of people) appears on its own Public card with its retrieval date; each sits in a container apart from any estimated-people figure. | journeys |
| FE-126 | The gateway table shows travel times from the area to the ports, the airport, the free zones and the land routes as times from this area; each destination is a Public label, and each Simulated time by hour carries the Simulated mark. | journeys |
| FE-128 | The `series_forecast` card draws a forecast of a series of the closed list of method card C30 as a small SVG chart: the history as filled markers, a divider labelled "Forecast", the forecast points as open markers and the interval as a stepped band (DES-195), with the caption of the caveat key `forecast_backtest_range` whose two counts are Fact chips. Each forecast value, its two interval ends and its measured backtest error are Fact chips of an Inferred fact that shows the class word of its series; the method and its version are in the Source chain. A forecast of a released monthly series of the custodian-type feeds (pay level, earner count and wage bill, the stayer index at municipality level, establishments and employment by area) is Synthetic: it shows the word "forecast", its subject is the `area` of its series, its origin is the last released month, and it carries `synthetic_not_evidence_about_qatar` and `synthetic_change` beside `forecast_backtest_range`. A released series with a carried-forward month in its window is not forecast: the card shows the Suppressed mark with the reason `CARRIED_FORWARD` that the server returns, never a line, a flat forecast or a zero. A series too short for the backtest shows its history, the words "not enough history" with the reason key `series_too_short`, and "Why can't I see this?", never a line, a flat forecast or a zero. The browser draws the returned points and ends and computes nothing. No label calls the band a probability or a confidence, and a projection is never labelled a forecast. | flagship |
| FE-129 | The `base_rates` card shows, for an activity and on the source's own geography, the entry and closure base rates of method card C31, each a flow over the published active stock of the same activity and geography and labelled approximate, with its numerator, denominator and period as Fact chips beside it, and months flagged where the method's rule for bulk months applied. It is Public. The survival base rate always shows `NO_DATA` with the reason key `no_denominator`, because the Public licence tables do not link a cancellation to its issue, and so does any rate whose denominator the Public tables do not carry. It is never computed for a drawn shape and never from the Synthetic births and closures, it forms and shows no figure of issues minus cancellations, it keeps the screen words "licence issues" and "licence cancellations", and its caption is `base_rate_not_your_chance`. | journeys |
| FE-130 | The `present_by_pay_band` card is a chart of the figure of method card C32: for the whole release units of a snapped area, a day type and a stored hour, the Simulated workers present and residents present, each split by pay band in its own chart, with visitors in a separate bar labelled as having no pay band. Visitors have no pay band and are shown as one count without a band. The band shares are those of the unit's covered earners, so the figure does not separate people who have no wage record: it assumes that the workers and residents present have the pay bands of the unit's covered workers and residents, and its caveat says so. Every count is a Fact chip with the range it carries (FE-124). A row that is withheld, suppressed, carried forward or remainder is drawn as Suppressed with the reason the server returns, and nothing is filled in. The card is Inferred, carries the Simulated mark and the caveat key `present_by_pay_band_assumed`, has the subject `area`, is never apportioned to a drawn outline (the snap report comes first, FE-109), is not split by activity, and is never called spending, spending power, income present or purchasing power. It sits behind "More evidence" and not in the story before scene 3 (DES-116). | flagship |
| FE-131 | The `site_estimate` card shows the estimate of method card C33 for the chosen area or pin: the low, middle and high cases as Fact chips, the main drivers in the order the server returns them, the seed as a `reference` chip and, while any input is Simulated or Synthetic, the label "estimate on simulated inputs" (the key `estimate_on_simulated_inputs`). Every uncertain parameter, the range of spend per person by pay band among them, is an `input` chip with its range, visible and editable. Its subject is `area`: it is never worded as the revenue of a named building or business, and no figure for a named competitor is computed, shown or kept. It is off in public-only mode and off while OI-03 is open. Editing a parameter posts typed inputs; the browser computes nothing. | flagship |
| FE-132 | The scenario tools show two scenarios of the user, and neither is called a forecast. The catchment-share scenario of method card C34 shows the share of the user's outlet as a Fact chip and the shares of the competitors as a small table by competitor category (from the reviewed category mapping of the places layer) and distance band, for example Italian restaurants within 500 m and other restaurants, never a row, share or figure for one named competitor; a cell that holds a single competitor is merged into the next wider cell (the same category in the next distance band, then "other"), and the table is left out where method card C34 returns no split; the competitors are Public marks with only their Public facts and their distance. The revenue range of method card C35 shows low, middle and high cases and the break-even point from the Public survey as benchmark, the simulated people present around the location at area grain, the capture rate and the average bill. Every assumption is an `input` chip, visible and editable; each result is Inferred, carries the "your inputs" tag, the least-real class of its inputs and the caveat key `scenario_not_forecast`. The revenue range is off screen while OI-03 is open. | flagship |
| FE-133 | The `venue_busyness` card shows the relative busyness by hour of a named venue as bars, titled "Google Maps popular times", with its retrieval date as a `reference` chip and the caveat key `relative_busyness_not_people`. It is a Public fact of the subject `place_public`, a relative index and never a count of people, never worded as footfall, and it has no total. It is in its own container, never beside or inside the container of an estimated-people figure, and it takes no part in any chart, row or sentence with one. | flagship |
| FE-134 | The `night_lights` card shows night-time radiance by area and month from `pub_night_lights`, Public, with the month on every chip, the NASA acknowledgement and the caveat key `night_lights_not_activity`. It is worded as night-time radiance and never as a measure of business activity or of people. | map foundation |
| FE-135 | The `population_age_sex` card shows the population by age band and sex from `pub_pop_agesex_grid` as the sum of the whole cells of the published grid whose centre lies inside the area the user chose; no cell is split, and the sum is not an apportionment. It is Public with its year on every chip, its caption is `grid_cells_summed`, and the categories follow the source's order. It is display only: it is never a criterion of a ranking, never set in a pay card, and never combined with, or charted with, a protected or Simulated figure. It is a card, never a map layer. | journeys |

## 5. The Fact chip rule

**Rule.** No numeral may be rendered anywhere in the interface except by the Fact chip family in `web/src/facts/`. A "numeral" is any character of Unicode category Nd: Western digits, Arabic-Indic digits and Extended Arabic-Indic digits all count.

The family has four variants, all one component:

| Variant | Use |
|---|---|
| `value` | a released fact, with provenance mark and word; an estimated count carries its range (FE-124) |
| `compact` | the same inside a chart label or legend bin; the word stays in the accessible name |
| `input` | `NumericInput` for user-entered values in the break-even calculator, in the scenario tools and in the parameters of the site estimate (capture rate, attractiveness, competitor-distance setting, the range of spend per person by pay band) and for ranking weights, and the chosen area cut-off or radius preset; tagged "your inputs" |
| `reference` | a release id, brief id, activity code, ISIC class, zone code or rules version in the receipt, drawer and pack; the hour and month labels of the Hour control and Month selector; a retrieval date in a source line; carries no provenance mark |

Non-fact positions that need a number for assistive technology (for example the story position "step 3 of 10" in an `aria-label`) are produced by `formatUiOrdinal` in `src/facts/`, never by a literal or by `String(n)` elsewhere.

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
| FE-40 | CI fails on any numeral or number word from the versioned `product/assistant/lexicons/` lexicon named by AI-38 in the string catalogues, and on any disable comment for the rule. It also fails on the words that stay off screen ("best", "odds", "chance", "probability", "confidence", "likely", "will", "spending power", "income present", "purchasing power", and "footfall of" a named place) and on the word "forecast" in any string other than those of the `series_forecast` family and the fixed denials of section 10.13 of [11](11_DESIGN_DIRECTION.md). The development-only `_perf` route is the sole route exemption and is absent from the frozen bundle. | slice S3 |
| FE-41 | A fact-valued chip refuses to render until its complete source chain resolves. The Fact chip renders the provenance word in its accessible name in the `value`, `compact` and `input` variants, shows the texture swatch in `value` and `compact`, and the `reference` variant shows no provenance mark. | slice S3 |
| FE-42 | The Fact chip recomputes the least-real class from `input_classes` (Public more real than Synthetic, more real than Simulated) and shows its error state if it differs from `provenance`. | slice S3 |
| FE-43 | A Suppressed chip shows no digit, shows the lock and the word, and opens "Why can't I see this?". | slice S5 |
| FE-44 | An `inferred` fact built from user inputs shows the "your inputs" tag. | slice S7 |
| FE-45 | The browser formats values returned by the server by applying grouping, to numeric units only, and the unit pattern only. It never calculates, compares, ranks, re-rounds, compacts or converts a displayed value, and an unknown unit code renders the chip's error state. | slice S3 |
| FE-127 | The Fact chip renders a fact of unit `calendar_date`, `calendar_month` or `calendar_year` ([03_DATA_CONTRACTS.md](03_DATA_CONTRACTS.md) DAT-155) in the `value` and `compact` variants with its provenance mark, formatted in `src/facts/` with the pinned locales and Western digits at exactly the precision the fact carries (a day, a month named by a word, or a year), never padded to a finer precision and with no grouping; it renders a fact of unit `published_text` verbatim as one bidirectionally isolated run, with no grouping, digit conversion or other formatting; a value outside its unit's form renders the chip's error state. | slice S3 |
| FE-122 | Hour and month labels of the time controls and retrieval dates in source lines are rendered only by the `reference` variant, formatted in `src/facts/` with the pinned locales and Western digits; the month is always a word. They carry no provenance mark and are not facts. | map foundation |
| FE-124 | A `value` chip of an estimated count shows the estimate and, as one isolated left-to-right range run beneath it, the range the fact carries; a fact of an estimated count without its range renders the chip's error state, never the estimate alone. The same holds for a forecast value without its interval ends and its backtest error, a site-estimate case without its low and high ends, and a base rate without its numerator, denominator and period: the chip renders its error state, never the figure alone. | map foundation |

## 6. Map layers

Layer order: basemap fill and line layers, then deck.gl data layers placed beneath the basemap label layers using the interleaved `beforeId` placement, then labels, then the watermark. "Hexagons under labels" is a spike gate in slice S1.

| What is drawn | Data | Layer type | Line and texture |
|---|---|---|---|
| Land, roads, water, place names | PMTiles basemap | MapLibre style from `@protomaps/basemaps` | context, no mark |
| Buildings | basemap `buildings` layer (height, min_height) and a curated landmark list | MapLibre `fill-extrusion` | heights labelled estimates (below) |
| Door pin | user pin | deck.gl `IconLayer` | context |
| Requested or drawn area | `make_area` snap report, or the shape the user drew | deck.gl `PathLayer` | solid 2 px accent line with a 2 px casing in `--eii-bg`; after a snap, the same line at 35% opacity. It is not dashed or dotted, except a drive-time outline at a stored hour, which takes the Simulated outline of [11](11_DESIGN_DIRECTION.md). |
| Released units | `grid_cell`, `release_unit`, `unit_member` | deck.gl `H3HexagonLayer`, one per resolution (9 and 8); unit outlines from `h3-js` cell-set boundaries in a `PathLayer` | outline in the class of the hero layer |
| Pay of workers or residents | `worker_pay`, `resident_pay` | `H3HexagonLayer`, flat fill by band, never extruded except in the optional 3D view (FE-138) | dotted (Synthetic) |
| Crowd density (the presence layer) | the hourly presence release table with ranges ([03](03_DATA_CONTRACTS.md)), as estimated people per square kilometre computed by the release build or `eii_core.calc` | `H3HexagonLayer` (or the fallback `PolygonLayer`), flat fill by class; one stored hour selected by filter; cross-fade between stored hours | moving dashes (Simulated) |
| Traffic | traffic link speeds by hour on the road graph ([03](03_DATA_CONTRACTS.md)) | `PathLayer` of road links, colour and width by class; one stored hour selected by filter; this is the traffic layer of the default setting `simulated` | static dashes (Simulated; [11](11_DESIGN_DIRECTION.md)) |
| Firm density (`firm_density`) | register companies counted by release unit from `pub_register_company`: firm counts and density come from the register ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)) | `H3HexagonLayer`, flat fill by class | solid (Public) |
| Worker density | employment aggregates of the synthetic records attached to the register companies, by release unit ([03](03_DATA_CONTRACTS.md)) | `H3HexagonLayer`, flat fill by class | dotted (Synthetic) |
| Openings; closures | public licence issues and cancellations on their official geography; synthetic firm births and closures by release unit and pair of adjacent months, all activity classes together, a carried-forward pair shown as suppressed, never zero | `GeoJsonLayer` (Public) or `H3HexagonLayer` (Synthetic), one hero layer each | solid (Public) or dotted (Synthetic) |
| Simulated flows | `flow_hourly`, one stored hour | particle layer (below) | moving particles (Simulated) |
| Where the door's workers live | `home_area_share` | `GeoJsonLayer` of pooled districts | dotted (Synthetic) |
| Suppressed elements | `suppression_reason` | cell polygons with `FillStyleExtension` hatch; lock icon at the unit's centre | grey hatch with lock |
| Zones and municipalities | `zone`, `municipality`, `pub_zone_utility`, `pub_licence_active` | `GeoJsonLayer` fill and outline | solid (Public) |
| Metro and tram | `pub_transit_monthly`, station points from the gazetteer | `ScatterplotLayer` | solid (Public) |
| Public places and real businesses | `pub_place`, `pub_place_fsq` and public listings | `ScatterplotLayer` or `IconLayer`; names in a MapLibre symbol layer, only while no Synthetic or Simulated hero layer is on | solid (Public) |
| Register companies (`company_points`) | `pub_register_company`, each company at its registered location as the register publishes it; each point opens the company card (FE-115) | `ScatterplotLayer` or `IconLayer`; names in a MapLibre symbol layer, only while no Synthetic or Simulated hero layer is on | solid (Public) |
| Distance connectors | `scan_places` | `PathLayer` | solid (Public) |
| Announced investment projects | `fdi_projects`, at the geography the source states | `ScatterplotLayer` at that geography's gazetteer point; counts in the DOM legend | solid (Public) |
| Property prices; construction pipeline | residential sales with their deal counts, and building permits and completion certificates, on their official geography ([04](04_PUBLIC_DATA_PACK.md)) | `GeoJsonLayer` fill and outline | solid (Public) |
| Night-time lights | `pub_night_lights`, by frame cell (whole pixels, no split) and month, with a Public month list of its own | `H3HexagonLayer`, flat fill on the five-class ramp, one resolution (confirmed at the spike) | solid (Public) |
| Live traffic (optional) | the provider's flow tiles, fetched by the local server and passed on from its own paths; in no table | a raster tile layer over local-path tiles (a MapLibre raster source or a deck.gl `TileLayer`, chosen at the spike) | a picture shown as the provider draws it; no provenance class, because no fact is read from it; the provider's attribution (FE-136) |
| Optional 3D view | the unit statistic or the crowd density of the hero layer already on | the same `H3HexagonLayer` with extrusion on, a fixed height step for each class of the layer's five breaks | the class texture of the flat layer (FE-138) |
| Ranked or similar areas (highlight, not a hero layer) | the candidate areas of a ranking, or the areas of one similar-area type | `PathLayer` outlines; the selected area in the accent | the least-real class of the ranking's criteria |

**Provenance textures.** The four treatments are fixed: solid = Public, dotted = Synthetic, moving dashes = Simulated, grey hatch with a lock = Suppressed, each always with its word in the legend and on the chip. Colours and pattern sizes come from [11](11_DESIGN_DIRECTION.md). The research names `FillStyleExtension` (procedural hatch and dot fills) and `PathStyleExtension` (dashed lines) as the deck.gl mechanisms. Whether these extensions apply through `H3HexagonLayer`'s sublayers, and how moving dashes are animated, is not confirmed; the spike settles both and records the method. The fallback is a `PolygonLayer` of cell boundaries from `h3-js`. With reduced motion, moving dashes become a static dash, still distinct from dots.

**Particles.** Particles are drawn only from the aggregated, released `flow_hourly` table, for the selected stored hour. Bands 1 to 5 place 2, 4, 8, 16 and 32 particles on each released origin-destination pair. The layer caps at 50,000 particles by dropping pairs from the smallest band. The seed is 1. Paths are straight or arced between the two unit centres, never routed street traces. The legend states that a moving dot is a visual unit of a simulated aggregate flow, not a person or a trip. Agent trails are dropped; particles never carry an individual path.

**Extruded buildings.** Open height data is nearly absent: in a Greater Doha box, 920 of 170,611 OpenStreetMap building ways carry a height tag and 5,705 carry a number of levels (Overpass counts, stack research, 2026-11-11). Buildings therefore use the basemap height where present, an estimated height otherwise (rule set at slice S1 and written in the asset manifest), and a hand-curated list of landmark heights. The legend and the Trust centre state "building heights are estimates". No data value is ever encoded as the height of a building: a building keeps its own height in every view, including the optional 3D view of FE-138, where only whole release units are extruded. Wage towers on buildings are dropped.

**One hero layer at a time.** The layer registry holds hero layers (`worker_pay`, `resident_pay`, `crowd_density`, `traffic`, `flows`, `home_area`, `zone_momentum`, `licence_density`, `transit`, `firm_density`, `openings`, `closures`, `fdi_projects`, `property_prices`, `construction_pipeline`, `night_lights`, `live_traffic`) and context layers (basemap, buildings, real businesses, register companies (`company_points`), door, drawn shape, released-area outline, places). Turning a hero layer on turns the previous one off. Only the hero layer may use a colour scale; its legend bins are rendered in the DOM with `compact` Fact chips; the live traffic layer is the exception, a picture shown as the provider draws it, with no legend bins and no numeral read from it. The optional 3D view is a mode of the hero layer that is on, not a layer of its own. The ranked areas of a ranking and the areas of a similar-area type are outlines drawn through the `highlight` directive, not hero layers. Official splits by sex or nationality appear on cards only, never as a map layer. The layer keys are the front end's expectation; the closed layer list of [08 Back end](08_BACKEND.md) wins.

**Hourly layers.** Crowd density and the simulated traffic hold every stored hour of the selected day type, season and month in one data array, and the hour is selected by a filter uniform or an update trigger (FE-91). Playback steps through stored hours only (FE-106). These two layers are the only ones animated through the day ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), item 19), and crowd density is always marked Simulated, as is traffic with the default provider. The live traffic layer, when the provider is on, is a picture of current flow with no stored-hour payload; it has no hour control and is not played. The `presence` layer values of [08 Back end](08_BACKEND.md) (estimated people per unit) feed the presence card and its chart, not a map fill: release units differ in size, so the map shows people per square kilometre only.

**Living map.** Real businesses from public places data and public listings, and the establishment points of the public business register, are context points. While a Synthetic or Simulated hero layer is on they stay unlabelled. Selecting a public place or listing opens its Public facts in a Public-only panel; selecting a register company opens its company card, with its published fields and its employee count only (FE-115). Firm counts and density come from the register; workers appear only as density and statistics by release unit from the attached records ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)). No layer, label, marker or panel shows a company's wages or other labour or residence detail. Named synthetic firms are retired.

**Watermark.** A watermark is drawn into the map canvas itself, so a screenshot of the canvas and every export (pack, image) carry it. It cannot be switched off from the interface. The rendering mechanism (a MapLibre custom layer drawing a screen-space quad, or a deck.gl screen-space layer) is chosen at slice S1. Its wording and look are set in [11](11_DESIGN_DIRECTION.md); it contains no numeral.

**Camera.** Story moves use MapLibre camera animations with durations from [11](11_DESIGN_DIRECTION.md). The initial view is Qatar; the area tools work only inside the frame of the release.

| ID | Requirement | Slice |
|---|---|---|
| FE-46 | Data layers render beneath basemap labels in interleaved mode; a visual test shows a label legible over a hexagon. | slice S1 |
| FE-47 | Each data source of section 6 is drawn only with the layer type listed; any other layer type for a release table fails review. | slice S3 |
| FE-48 | Each provenance class is drawn with its line and texture treatment, independent of colour; a greyscale visual test still distinguishes all four. | slice S3 |
| FE-49 | At most one hero layer is visible; turning one on turns the previous one off; a test asserts the registry never holds two. | slice S6 |
| FE-50 | No layer is extruded to encode a data value, and a building is never extruded by a data value. The one exception is the optional 3D view of FE-138, which extrudes whole release units and is off by default. Buildings are extruded to their own height only. | slice S6 |
| FE-51 | Particles are generated only from released `flow_hourly` rows: bands 1 to 5 place 2, 4, 8, 16 and 32 particles per pair; the 50,000-particle cap drops pairs from the smallest band; seed 1 fixes placement and timing; paths are straight or arced between unit centres. | slice S6 |
| FE-52 | The legend states that building heights are estimates whenever buildings are extruded. | slice S3 |
| FE-53 | The watermark is present in the canvas in every frame and in every export; a pixel probe test on an exported image finds it. | slice S3 |
| FE-54 | `H3HexagonLayer` instances each hold one resolution only. | slice S1 |
| FE-55 | Released-unit outlines are computed in the browser only as geometry from cell ids; no statistic is computed or aggregated in the browser. | slice S5 |
| FE-103 | The living map draws real businesses from public places data and public listings as solid Public points, and the establishment points of the public business register as the solid Public layer `company_points`, each of which opens its company card (FE-115, [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)); both stay unlabelled while a Synthetic or Simulated hero layer is on. No layer's data, label, marker or legend carries a company's wages, wage bill or other labour or residence detail; a test fails if a planted wage of one company or a `SYN-` identifier reaches any map layer or the canvas. | map foundation |
| FE-104 | Crowd density is a hero layer of release-unit fills of estimated people per square kilometre for the selected stored hour, with the Simulated texture. Changing the hour cross-fades between two stored hours and never draws an interpolated value; the legend names the unit, the word "estimated" and the class. | map foundation |
| FE-105 | With the default provider, traffic is a hero layer of road links classed by simulated speed against free-flow speed for the selected stored hour, on the real road network, with the static dash texture and width by class of [11](11_DESIGN_DIRECTION.md). A drive-time outline re-forms for the selected hour and keeps the Simulated outline; Public chips beside it stay solid. | flagship |
| FE-136 | With `EII_TRAFFIC_PROVIDER` at `tomtom`, the key present and the presenter's offline control not set, the Stage offers the live traffic layer: a picture layer whose tiles the browser requests only from the local server's own paths. The browser never holds the key and makes no request to another origin (FE-56). The layer is shown as the provider draws it, carries no provenance class, and no numeral is read from a tile. While it is on, the provider attribution is visible (FE-139), its retrieval time shows as a `reference` chip, the caveat key `live_traffic_provider` shows, and the status badge "Live traffic" shows. It has no hour control and is not played. A traffic-aware drive-time area is requested through the server and enters as an area of the session, bound to its session and seat like a drawn shape and marked with the provider and its retrieval time; figures over it follow the rules of a drawn shape and carry the least-real class of their inputs. A failed fetch shows the layer's paused state and keeps nothing. With the default setting, the provider layer is not offered; the guided story, every test and every gate need no provider. | map foundation |
| FE-137 | The night-lights layer draws `pub_night_lights` for the selected month of its own Public month list, as a flat fill on the five-class ramp with the solid Public treatment. Its legend names the unit, the month, the direction in words and the class; the NASA acknowledgement shows while it is on (FE-139). For any drawn shape it returns the Public, Observed mean of `pub_night_lights` frame-cell values whose centres lie inside it, counting each cell once, splitting nothing and performing no C18 apportioning, with method card C36 and the area named in lineage and neither `apportioned_from` nor `grid_cells_summed`. A front-end fixture with cell values 4 and 10 renders 7 as Public and Observed without an apportioned label. | map foundation |
| FE-138 | The optional 3D view extrudes whole release units by one protected area statistic or by the simulated crowd density of the hero layer that is on. It is off by default and off in the guided story. Each extruded value is also readable as a Fact chip in the flat view, "Show as table" stays, and the marks, the suppression and the snap rule are those of the flat view: a Suppressed unit stays flat, hatched and locked. The height is a fixed step for each class of the layer's five breaks, read from the style and not computed in the browser, and the legend names the extruded quantity, its unit, period and class. A building keeps its own height and is never extruded by a data value. Only traffic and crowd density animate, and the pitch stays within the cap of DES-49. | map foundation |

## 7. The basemap

- **Tiles.** One PMTiles extract of Qatar cut from the Protomaps daily build with `pmtiles extract` and a bounding box (Protomaps documentation). Hot-linking the builds is discouraged by Protomaps, so the extract is fetched once by the asset pipeline (section 14), hashed and stored under `data/` (not committed). FastAPI serves it with HTTP Range support (Starlette `FileResponse` supports Range since 0.39.0). The `pmtiles` JavaScript protocol is registered with MapLibre at boot.
- **Style.** Generated in code with `@protomaps/basemaps` (layers for a named flavour and a language). The flavour and any overrides come from [11](11_DESIGN_DIRECTION.md). A language switch regenerates the label layers with `name:ar` or `name:en`; tiles do not change.
- **Glyphs.** MapLibre 6.9 and later shape Arabic without a plugin, but Arabic needs real Arabic glyphs. The default Protomaps font set (Noto Sans) may not cover Arabic, so the pipeline adds Noto Sans Arabic glyph ranges, or uses MapLibre font-faces (`setFontFaces`, since 6.7); the spike picks one. Glyphs and sprites are served from the same origin.
- **Live traffic (optional).** With `EII_TRAFFIC_PROVIDER` at `tomtom`, the key present and the presenter's offline control not set, the API process fetches the provider's flow tiles and traffic-aware drive-time areas and passes them on from its own paths. The browser never holds the key. Nothing of a response is written to disk, to the release or to a log ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 17), and no response of a live service is committed.
- **No third-party requests at run time.** The style contains no absolute URL to another host. The page sends a Content Security Policy that allows `'self'` (plus `blob:` and `data:` where MapLibre workers and images need them) and nothing else. Telemetry of any kind is absent.
- **Label check.** Before slice S3 closes, a reviewer checks in both languages how the basemap names the Gulf, neighbouring territories and Qatari districts, and hides or edits labels as needed (design research: a mandatory check, not a known fault).
- **Attribution.** OpenStreetMap and Protomaps attribution stays visible on the map (ODbL Produced Work); Overture attribution is shown whenever Overture-derived places are on screen, Foursquare Open Source Places attribution whenever its places are on screen, the NASA acknowledgement with the product DOI whenever the night-lights layer is on, and the provider attribution "© TomTom" whenever the live traffic layer is on. The satellite imagery provider's credit is written in one line of web code only: `export const MAP_ATTRIBUTION =` followed by one template literal and a semicolon, in `web/src/stage/attribution.ts`, a file that holds nothing else but blank lines and `//` comments; the template literal keeps the line whole under the formatter. The credit is shown as written in both languages and is not in `src/i18n/en.json` or `ar.json` (an exception to the Strings rule of section 8); no translated, transliterated or shortened form of the provider's name is written anywhere. A name of the private list passes there only under TST-263 ([12](12_TESTING_AND_QUALITY.md)).

| ID | Requirement | Slice |
|---|---|---|
| FE-56 | With the network disabled except for the local server, the basemap, labels in both languages, buildings and data layers all render; an end-to-end test blocks every non-same-origin request and fails if one is attempted; it runs with the live traffic provider on, served by a hand-made fixture of the documented response format, and off. | slice S1 |
| FE-57 | Arabic map labels render with connected, correctly ordered glyphs from self-hosted glyph files; a visual test covers five reviewed Arabic place names. | slice S1 |
| FE-58 | The PMTiles file is served with range requests by the FastAPI process; no separate tile server runs. | slice S1 |
| FE-59 | Switching language changes basemap label language without reloading tiles or moving the camera. | slice S3 |
| FE-60 | OpenStreetMap and Protomaps attribution is visible on every map view and in every export. | slice S3 |
| FE-139 | The attribution of each source on screen is visible while its layer or places are on: "© TomTom" while the live traffic layer is on, the NASA acknowledgement with the product DOI while the night-lights layer is on, and the Foursquare Open Source Places attribution while its places are on. It leaves the screen when the layer is turned off. | map foundation |

## 8. Bilingual and right-to-left rules

The route sets `lang` and `dir` on the root element. All component styles use CSS logical properties (`margin-inline-start`, `inset-inline-end` and so on); a style check fails on physical `left` and `right` properties in component styles, except inside the Stage canvas container.

| Mirrors in Arabic | Does not mirror |
|---|---|
| order of the Brief column, Plan rail and drawers (drawers open from the inline end) | the map and its canvas (north stays up; nothing is flipped) |
| text alignment and reading order | charts: band distribution bar, coverage bar, supplier lens |
| directional icons (back and next arrows) | numerals and number ranges |
| the story stepper's Back and Next buttons; the Dial's position moves to the other side | the Dial's quadrants, clockwise motion and order of its four situations |
| card order within a row; the column order of the ranking, fit and list tables | time order: the Hour control, the Month selector, the people-by-hour chart and every trend axis, earliest at the left |

Keys are physical: the clicker's next key and the Right arrow key always mean "next" in the story, in both languages, because a presenter's hand must not depend on the language. In the Dial, the Right arrow key always moves to the next situation in its fixed order; in the Hour control it always moves to the next stored hour.

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
| FE-66 | Story, Dial and Hour control keys keep their physical meaning in both languages. | slice S10 |
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
| Empty | no pin yet, or a new session | the ask bar and the journey home (seven decisions, three services, four cases); "Ask about here" when the user taps the map |
| No data (`NO_DATA`) | nothing released for that element | the coverage label Not measured where the template says so, the reason, and "Why can't I see this?"; never a zero |
| Suppressed (`SUPPRESSED`) | a rule withheld the element | grey hatch with lock and the word Suppressed; "Why can't I see this?" opens the reason from `suppression_reason` and the nearest publishable alternative |
| Out of scope (`OUT_OF_SCOPE`) | a question outside the product | a scope card with three in-scope suggestions |
| Error | a request or render failed | the element's error state with Retry; validated evidence already shown stays; a failed structured item or layout is withdrawn before the template writer's default appears |
| Offline | the model is unreachable or no API key exists | the Template writer badge; the default claim selection and component layout use the same facts and catalogues |
| Store paused | PostgreSQL is away | company seats continue on the embedded reader with the store badge; the Oversight screen shows "paused" |
| Server unreachable | the local server does not answer | a full-page reconnect state; the standing strip stays |
| Not allowed | a seat opens a brief or room it may not see | a neutral not-available message that does not confirm whether the brief exists |
| Shape refused | a drawn shape outside the limits the server sets | the governed reason and the closed presets as alternatives; no figure is shown for the refused shape |
| Sample file refused | a request whose key is not one of the closed sample-file keys of the case | the governed refusal sentence; nothing is loaded or kept |
| Playback paused | Pause motion or reduced motion is on, or the user paused | the Hour control shows the selected stored hour and Play; nothing moves |

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
| FE-82 | Each hero layer offers "Show as table": an accessible table of the same released facts, rendered with Fact chips; for crowd density and traffic, the table holds the selected stored hour for the units or road links of the selected area or the current view. The live traffic layer, a picture with no readable value, offers instead a note with the provider, the retrieval time and the attribution. | slice S6 |
| FE-83 | The Brief announces each completed section through a polite live region after the accounting gate has passed, not each token of the buffered brief. | slice S6 |
| FE-84 | With `prefers-reduced-motion: reduce`, camera flights become cuts, particles stop, moving dashes become static dashes, the snap shows its end state, and hour playback does not start: the hour changes only when the user steps it. | slice S6 |
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
| Hour change, day change and playback step | as the dial change: the cross-fade completes within its duration in [11](11_DESIGN_DIRECTION.md), with no frame over 33 ms, for crowd density and for traffic (ASSUMPTION: the dial-change target applied to the hourly layers) | design direction |
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
| Component | every component and every listed state from recorded fixtures; Fact chip variants; one Fact chip fixture for each of the units `calendar_date`, `calendar_month`, `calendar_year` and `published_text`, in English and Arabic; card types with Public, Synthetic, Simulated and Suppressed facts |
| Visual | key screens at the four pinned viewports in English and Arabic: home and journey home, flagship workspace with four hero cards, a forecast series with its interval band, the site estimate, the pay-band chart, the venue busyness card, the night-lights layer, the population card, the 3D view, Evidence drawer, Dial at each situation, crowd density and traffic at one stored hour, an event day, a drawn shape with and without the snap report, the ranking panel, the reverse view, the labour-market view, What changed, a register-company list beside a business list, a company card, the FDI list, a case story step with a sample file loaded, suppressed card, Oversight screen, Trust centre, Proof room, pack page; animations off and fonts ready; fixed camera; reviewed baseline images |
| End-to-end | the public-only flagship (slice S3), the joined door (slice S6), language flip with identical numbers, the guided story by keyboard, store paused, template writer, seat isolation, no third-party request (with the live traffic provider on and off), reduced motion; drawing a polygon by pointer and by keyboard; hour playback and its pause; a weight edit returning new ranks; sample-file load by its closed key, refusal of any other key or body, the absence of any file-input element or drop handler, and unload on Reset and at the end of the session; each case story from one click; the FDI list with no search by name |
| Provenance audit | section below |

**Automated provenance audit** (`tests/audit/`, Playwright). On every route, every story step and every case-story step, in both languages and at the wall and tablet viewports, the audit:

1. walks all visible text nodes and fails on any numeral not inside a Fact chip element;
2. resolves every chip's `fact_id` to a fact in the registry with `provenance`, `input_classes`, `lineage_ref` and `release_id` present, and refuses any incomplete source chain;
3. recomputes the least-real class independently and compares it with the chip's mark;
4. opens every chip's drawer, checks the "Source chain" label and follows fact → release table → method and version → publisher, dataset, licence, retrieval date and file hash;
5. checks that Suppressed chips contain no digit and offer the reason affordance;
6. resolves each claim and component's catalogue subject and, regardless of wording, applies the subject rules of [03 Data contracts](03_DATA_CONTRACTS.md) section 9.1, judging a Suppressed fact by the class it would otherwise have: Synthetic and Simulated facts are allowed under `area`, and under `register_company` the Public facts of the company's card, the Synthetic `employee_count` of its attached records and, in a list, the rank and fit facts of tested code ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)); it fails any fact other than a Public one under `place_public` or `fdi_project`, any Simulated fact, estimate, share or score and any wage, wage bill or other labour or residence fact under `register_company`, the retired subject `synthetic_firm`, and any Synthetic or Simulated fact under every other subject. Its fixtures show a register company's employee count under `register_company` passing, a planted wage of one company under `register_company` failing and a non-Public fact under `fdi_project` failing;
7. exports the canvas and the pack and checks for the watermark and the standing strip;
8. compares the English and Arabic fact sets for the same brief, checks the five-part accounting result in every receipt, and verifies that a failed check selects the template writer's default;
9. fails any count of people shown without its range or worded as footfall, any rank or fit shown without its rank-stability sentence, and any forecast, estimate or base-rate fact shown without its interval, range or counts (FE-124);
10. fails any wage, wage bill or other labour or residence detail of one company on a company card, in a register-company list, in the map canvas or in a layer's data (the planted cases of [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) item 7), any `SYN-` identifier in the map canvas or in a layer's data, and any register-company list or company card sharing a container, list or row with the Business list of public places data and public listings;
11. fails any Public split or FDI chip without its year, any FDI capex or jobs chip without the source's estimate note, any tabulated Public split on a drawn shape, any Public split beside a Synthetic or Simulated figure, and any population-grid sum that splits a cell or sits on one chart with a protected or Simulated figure;
12. fails any snap report shown with no protected figure on screen, and any figure of a protected record type shown without the snap report before it;
13. fails any relative-busyness figure of a named venue that shares a container with an estimated-people figure or is worded as a count of people or as footfall;
14. fails any site estimate shown without its low, middle and high cases or, while an input is Simulated or Synthetic, without the label "estimate on simulated inputs", any figure for a named competitor, and any scenario, estimate or base rate worded as a forecast;
15. fails any live traffic layer on screen without the provider attribution, any night-lights layer without the NASA acknowledgement, and any figure of people present by pay band worded as spending.

The audit is a gate for slice S3, slice S6, slice S7 and slice S10, and for every build phase of [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) and every task of [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) that changes the screen.

| ID | Requirement | Slice |
|---|---|---|
| FE-92 | Unit, component, visual, end-to-end and audit suites run with `./eii test`; visual and audit suites also run in CI with software rendering and fixed baselines. | slice S3 |
| FE-93 | Visual tests cover the listed screens at all four pinned viewports in both languages, and every baseline change is approved in review. | slice S6 |
| FE-94 | The provenance audit passes all fifteen checks on every route, story step and case-story step. | slice S3 |
| FE-95 | Tests never print or snapshot API keys (`TOMTOM_API_KEY` and `EARTHDATA_API_KEY` among them), and fixtures use only synthetic identifiers of the form `SYN-E-7F3K2Q`. Tests never call a live service: fixtures of provider responses are made by hand in the documented format, and no response of a live service is committed. | slice S0 |

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
| Zone geometry | per [04 Public data pack](04_PUBLIC_DATA_PACK.md) (licensed `bnd_hdx`; the census map layers state no licence) | per 04 | fetched at build time, never committed; the 2020 boundary layers only check `bnd_hdx` (PUB-13) | no |

| ID | Requirement | Slice |
|---|---|---|
| FE-96 | The asset pipeline records source URL, retrieval date, licence and SHA-256 for every map asset. A build fails when an asset lacking a stated licence is included in a release asset set; a validation-only fetch excluded from that set does not fail for existing in the build cache. Relative-busyness values and responses of the live traffic provider are never part of an asset set and never committed. | slice S2 |
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
9. Eleven routes, with case stories on a route of their own (section 3.2).
10. The sample-file loader offers only closed keys for the shipped synthetic sample files of cases C3 and C4, and the server loads the committed file that a key names, so that no file enters from the browser and no real company record can enter a session ([AGENTS.md](../AGENTS.md) rule 3) (FE-120).
11. The hour-change target is the dial-change target (section 12).
12. Openings and closures are two hero layers, never one net layer, because the single magnitude ramp of [11](11_DESIGN_DIRECTION.md) has no diverging form (FE-113).
13. The scenario tools sit beside the break-even panel as a component of their own, so that the catchment-share scenario is not tied to OI-03, which the record names for the revenue range only (FE-132).
14. The night-lights layer is drawn as an `H3HexagonLayer` because its table is keyed by frame cell; the spike confirms it (FE-137).
15. The build phases in the Slice column of FE-128 to FE-139 follow the pairing of [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) with the phases of [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) item 15; the lead confirms them.

Open points from decisions 0016 and 0017:

- OPEN: the names and payloads of the new stage directives, the closed layer keys, and the routes for drawn shapes, weights and sample files are fixed in [08 Back end](08_BACKEND.md); this document states the front end's expectation, and 08 wins.
- OPEN: the limits on a drawn polygon (vertices, size, frame) and any radius or travel-time presets beyond the closed lists are fixed in [08 Back end](08_BACKEND.md) with the closure checks of [06 Privacy and disclosure control](06_PRIVACY_AND_DISCLOSURE_CONTROL.md).
- The four dial situations select hours of the hourly day types through `situation_windows`, and the event day types are released with `summer = false` only ([03 Data contracts](03_DATA_CONTRACTS.md) DAT-76); the summer switch is disabled on the three event days ([05 Synthetic world and simulation](05_SYNTHETIC_WORLD_AND_SIMULATION.md) SYN-52). The controls follow.
- [Decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md) items 6 and 17 keep decision 0006 items 3 and 4 for protected figures only: any requested or drawn shape snaps to whole release units before a protected figure is read, as FE-109 does and as PRV-17 of [06](06_PRIVACY_AND_DISCLOSURE_CONTROL.md) and `make_area` of [08](08_BACKEND.md) confirm.
- OPEN: the drawing approach and its pin are chosen at the slice S1 spike (FE-102).
- OPEN: the FDI source's location field may name a place coarser than a point; the FDI layer draws only at the geography it names (FE-116), confirmed against the page structure at slice S2 ([decision 0017](decisions/0017-public-data-additions-and-public-splits.md)).
- OPEN: the public source of tenders is confirmed at slice S2; without one, the tenders card is not offered.
- OPEN: the closed layer keys `night_lights` and `live_traffic`, the switch of the 3D view and the traffic provider field of `GET /health` are fixed in [08 Back end](08_BACKEND.md); this document states the front end's expectation, and 08 wins.
- OPEN: the provenance mark of the live traffic layer. It is a picture from which no fact is read and carries no provenance class here; whether the watermark and the provenance legend name it is for the lead to rule.

Open points from [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md):

- OPEN (decision 0022): the route and key that serve a company card, so that no registration number enters a URL, an API log or a ledger row; [08 Back end](08_BACKEND.md) fixes them, and 08 wins.
- OPEN (decision 0022): whether `company_points` draws a point the register publishes or the centre of the company's registered cell, set with the columns of `pub_register_company` ([03 Data contracts](03_DATA_CONTRACTS.md)).
- OPEN (decision 0022): the licensed-versus-operating strip (`licensed_vs_operating`, FE-26) and the synthetic openings and closures of What changed and of the `openings` and `closures` layers (FE-113) stay as written until the open points of [01 Project brief](01_PROJECT_BRIEF.md) on BRF-09 and BRF-62 are settled.

Open items from the master design that touch this document:

- OI-01: the key is supplied for go-live and is not used during the build; the front end runs with the template writer throughout the build and shows its badge. `TOMTOM_API_KEY` and `EARTHDATA_API_KEY` lie outside that set and may be used by the build ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 16); no test, gate or guided story needs either.
- OI-03: restaurant totals, unit economics, the break-even panel and the national pay card stay off screen until the conflicting public tables are reconciled.
- OI-04: closed for version 1 by [decision 0017](decisions/0017-public-data-additions-and-public-splits.md) item 10: the census map layers enter the local release, each figure with its source and retrieval date, and are never committed. The coverage bar uses the finest admitted geography or returns `NO_DATA`.
- OI-05: the product name and Arabic name shown in the shell and pack await the owner's clearance; the working title is used.
- OI-06: source labels on screen use neutral record-type names by default; naming custodians is a configuration value read from the API, never hard-coded.
- OI-08: label for live ledger rows and the distinct-organisation minimum on the Oversight screen.
- OI-09: native Arabic review of all prepared strings, a gate at slice S10.
- OI-14: the typed-decision gateway has no front-end or run-time role without an approved route.
- OI-17: no typed-decision measurement panel appears in the Proof room; only the activity-spine lineage line appears.

Questions for the spike in slice S1: whether `FillStyleExtension` and `PathStyleExtension` work through `H3HexagonLayer`; how moving dashes are animated; the watermark mechanism; Arabic glyph route (glyph files or font-faces); tabular figures in the chosen font files; the pixel-ratio cap value; the drawing approach; whether road links with a static dash texture and width by class, and crowd density at every stored hour, hold the frame-rate gate; whether the live traffic picture layer is a MapLibre raster source or a deck.gl tile layer; whether the 3D view holds the frame-rate gate.

## Sources

- [Decision 0016 — Version 1 covers the whole initiative](decisions/0016-version-1-covers-the-whole-initiative.md) and [decision 0017 — Public data additions and public splits](decisions/0017-public-data-additions-and-public-splits.md), accepted 2026-11-12: the living map, drawn areas, hourly layers, event days, rankings, named synthetic firms, monthly periods, cases and sample files, Public splits, the FDI projects dashboard and the agency's pages.
- [Decision 0022 — Real register companies with a synthetic labour and residence world attached](decisions/0022-real-register-companies-with-a-synthetic-world.md), accepted 2026-11-13: register companies replace named synthetic firms; the company card, the register-company list and the map's establishment points.
- [Decision 0019 — Forecasts, estimates and scenarios by tested code; six self-serve sources; citations by stable anchor](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), accepted 2026-11-12: the forecast, base-rate, estimate and scenario cards, people present by pay band, the optional 3D view, the live traffic provider, relative busyness, night-time lights and the population grid by age and sex.

Unless dated otherwise, retrieved 2026-11-11, through the stack research and design research files of this pack unless marked "checked by this document's author".

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
