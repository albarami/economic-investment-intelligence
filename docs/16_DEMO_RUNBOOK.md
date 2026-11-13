# 16 — Demo Runbook

| | |
|---|---|
| Status | Draft v0.3, amended by decisions 0016, 0017, 0018, 0019 and 0020 on 2026-11-12, and by decision 0022 on 2026-11-13 |
| Date | 2026-11-13 |
| Owner | albarami |
| Purpose | The exact steps, checks, story, recoveries and words for a live EII session in front of a Minister. |
| Read first | [13_DEPLOYMENT_AND_OPERATIONS.md](13_DEPLOYMENT_AND_OPERATIONS.md), [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md), [10_FRONTEND.md](10_FRONTEND.md), [11_DESIGN_DIRECTION.md](11_DESIGN_DIRECTION.md), [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md) |

## In brief

- This runbook is written before the product exists. The work in slice S11 must make every command and expected result below true, or change this file.
- Start with `./eii up`. Stop with `./eii down`. Nothing else is typed during the session.
- Checklists run the day before, one hour before and five minutes before. Each step names its command and the result that counts as a pass.
- The guided story has ten scenes ([decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md)). It opens on the living map's real public evidence, shows the Qatari day hour by hour, gives the reading guidance, makes the flagship location choice with a drawn area, presence by hour, an event day and traffic by hour, ranks where else fits, then runs costs, the privacy attack, the oversight minute and the four cases as one-click stories before the hand-over. Its total keeps the 8 to 9 minute target of BRF-33; the targets of the new scenes are set at the first full rehearsal of slice S11. Each scene names what to tap, what must appear, the provenance marks to point at, and the fallback, and every scene keeps the honesty lines.
- Twelve failures are rehearsed: database not answering, network down, model refusing or slow, blank map tiles, missing Arabic glyphs, browser or machine failure, refused freeze, refused frozen-bundle install or start, and, for the new scenes, hourly layers stalled or blank, a drawn area or its evidence failing, a ranking that does not update, and a case story or sample file failing. Each has one decision and one recovery.
- Honest answers to sixteen hard questions, the prohibited claims, a pilot-request template and the after-session record close the runbook.

## 1. Roles, kit and rules

| Role | Does |
|---|---|
| Presenter | Speaks, taps the wall screen or clicker, owns every recovery decision |
| Operator | Watches the presenter console on the second monitor, calls out health changes, runs no command during the session |

| Kit | Note |
|---|---|
| Stage machine | Runs the frozen bundle ([13_DEPLOYMENT_AND_OPERATIONS.md](13_DEPLOYMENT_AND_OPERATIONS.md), section 7) |
| Wall display over HDMI | Shows the stage window, presenter mode, 1920×1080 design canvas |
| Second monitor | Presenter console only; never mirrored to the wall |
| Clicker | Next and Back on the presenter console |
| Separate device with the backup recording | Last line of defence; plugged into the display's second HDMI input before the audience arrives |
| Removable storage | Freeze bundle and the latest `app` backup |

| ID | Requirement |
|---|---|
| RUN-01 | ASSUMPTION: two people run a session, a presenter and an operator. Reason: one person cannot speak to a Minister and watch health at the same time. |
| RUN-02 | During the session nobody types a terminal command, a Docker command or a service command on the stage machine. All recovery uses presenter-console controls or the browser. |
| RUN-03 | The presenter console offers exactly these controls: Next, Back, Language, Offline, Switch to embedded reader, Reset, Theme (dark or light), Room scale (1.0, 1.15, 1.3), Pause motion, and Scenario inputs (which types the break-even values into the wall). Next also applies each step's prepared inputs from the story script: the drawn shape, the hour, the day, the ranking weights and a case's shipped sample file. It shows every field of `GET /health`, polled every 5 s. Every presenter control sends the per-session presenter token; a call without it is refused. |
| RUN-04 | Every guided-story and case-story question is answered from its prepared recording (see [09_AI_ASSISTANT.md](09_AI_ASSISTANT.md)) and shows the "Prepared" mark. During the build, and at any rehearsal before go-live, scene 9 has no live question. Once the owner has switched the live adapter on at go-live, scene 9 may ask one live question when a key is present and the session is online. The answer is still claim templates and catalogue components. It shows no "Prepared" mark. If the returned layout is invalid, the playbook default is shown and the presenter does not comment on a model. |
| RUN-05 | Every story scene and every case-story step has a URL; reloading the browser returns to the start of the current scene or step with the same seat and language. |
| RUN-06 | The presenter never reads a Synthetic or Simulated number aloud as a fact about a real place, says "estimated people around this location" and never "footfall of" a named building or business, says "relative busyness by hour, Public, from Google Maps popular times" for the hourly index of a named venue, and never states a prohibited claim (section 8). |
| RUN-07 | Every command and expected result in this runbook is executed in the three slice S11 rehearsals; a step that fails is fixed in the product or rewritten here before the first session. |
| RUN-12 | `./eii freeze` requires a recorded human review of the release: the reviewer's role, the date, and that the survival report and the signed attack report were read. No review record, no freeze. The day-before checklist confirms that record before the session. |
| RUN-13 | `./eii freeze` takes no new flag and is run twice. Its first run writes the data bundle, checksum list and pending `freeze.json` and appends the seven-field register line; its second run, from the base-branch commit containing that line, builds and verifies the application archive, writes its checksum beside the bundle and marks `freeze.json` complete. Continuous integration checks the register file alone: existing lines unchanged, one `protected_sha256` per `window_key`, and one `window_key` per `world_seed` (PRV-120). For a frozen release only, install and `./eii up` require the complete descriptor and matching line in the installed application's register; otherwise they exit 7. A build release with no `freeze.json` is not checked. No signed receipt file replaces these checks. |
| RUN-14 | The limits page carries this sentence: "Figures from different tables can differ slightly because each table is protected on its own." |
| RUN-15 | During the story the presenter never draws a shape freehand, edits a weight by hand or loads any file: each prepared input is applied by Next from the story script, so that every prepared answer's memo key matches. Free drawing, other weights and live questions belong to the hand-over. |
| RUN-16 | Every scene and case story keeps the honesty lines of DES-187 in [11_DESIGN_DIRECTION.md](11_DESIGN_DIRECTION.md). The presenter says "estimated people around this location", "ranked by the criteria you set", "projection", "your scenario", "estimate on simulated inputs", "relative busyness" and "night-time radiance". The presenter says "forecast" only for a forecast of a published series or of a released monthly series (the latter marked Synthetic), with its range and its backtest error, and never for a projection, a ranking, a fit, an estimate or the user's scenario. The presenter never says "footfall of" a named place, "real company", "the best location", "odds", "probability", "confidence", "spending power", "income present" or "purchasing power"; FDI capex and jobs are always called the source's estimates. |
| RUN-17 | Cases C3 and C4 load only their shipped synthetic sample files. No company's real records are loaded at any time, and a sample file is unloaded by Reset, by a change of seat and at the end of the session. |
| RUN-18 | The guided story and the three slice S11 rehearsals run with `EII_TRAFFIC_PROVIDER` at its default `simulated` and need neither `TOMTOM_API_KEY` nor `EARTHDATA_API_KEY`, so every traffic layer and drive-time outline in the story is Simulated and no step needs the network ([decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) item 17). If the owner switches the live provider on for a hand-over, the presenter says that the layer is live traffic from the provider, shown as a picture with the provider's attribution, that no figure is read from it, and that a drive-time area from the provider is the session's own area; the console never shows a key. |

## 2. One start, one stop, health

Start, inside Ubuntu, from the repository root:

```
./eii up
```

Expected: preflight prints only `PASS` lines, then the links for the three seats and the presenter console, `store: postgres`, the frozen `release_id`, and the model mode. The command stays in the foreground.

`./eii preflight` only probes and never starts or stops anything. `./eii up` never starts a database: it serves from the store that preflight found. `./eii db-up` starts the database and waits up to 60 s for it to answer; `./eii db-down` stops it.

If it prints a `WARN` and `store: embedded`, PostgreSQL did not answer. Before the session that is a failed check: stop with Ctrl+C, run `./eii db-up` (step H4), repeat step H5, and start again. Present on `embedded` only as a recorded decision, knowing the oversight seat will show "paused".

Stop, after the session:

```
./eii down
```

Expected: exit code 0; the API stops; volumes, releases and the local ledger are kept.

Health check, from a second Ubuntu terminal before the session (never during it):

```
curl -s http://127.0.0.1:8000/health
```

Healthy looks like this (values in angle brackets are the frozen release's own):

```json
{
  "status": "ok",
  "store": "postgres",
  "postgres": "up",
  "release_id": "<frozen release id>",
  "release_hash": "<frozen release hash>",
  "parity": "identical",
  "ledger": "postgres",
  "local_ledger_rows": 0,
  "model": "live",
  "traffic": "simulated",
  "tiles": "ok",
  "fonts": "ok",
  "replays": "ok"
}
```

`model` reads `replay` or `template` when the session is planned offline or without a key; that is healthy. The full contract of this page is in [13_DEPLOYMENT_AND_OPERATIONS.md](13_DEPLOYMENT_AND_OPERATIONS.md), section 6.1.

## 3. Checklists

Checklist steps are named D (the day before), H (one hour before) and F (five minutes before). The seven company decisions are always written "journey D1" to "journey D7", the services "service S1" to "service S3" and the cases "case C1" to "case C4", so that no step is mistaken for a journey.

### 3.1 The day before

| Step | Command or action | Pass when |
|---|---|---|
| D1 | `git status --short` and `git describe --tags` | Empty status; the tag of the frozen version |
| D2 | `./eii test` | Exit 0 |
| D3 | `./eii db-up`, then `./eii preflight` | Exit 0; every line `PASS` |
| D4 | `cd data/freeze/<release_id> && sha256sum -c SHA256SUMS` | Every line ends `OK` |
| D5 | Full rehearsal with PostgreSQL up, timed per scene | Each scene within 30 s of its planned time; no fallback used |
| D6 | Rehearsal with PostgreSQL stopped at scene 3: in a second terminal run `./eii db-down`, then use "Switch to embedded reader" | Story completes; every figure equals rehearsal D5; oversight seat shows "paused" |
| D7 | `./eii db-up`, then `./eii down` and `./eii up` | `./eii up` reports the number of local ledger rows replayed; health `ledger: postgres` |
| D8 | Offline rehearsal: switch Windows networking off, press Offline on the presenter console, then run the whole story | Model mode `replay` or `template`; Trust centre egress record shows zero outbound calls, with the traffic provider off (its default); map and fonts intact |
| D9 | At the venue resolution, open the browser's GPU status page (`chrome://gpu` or `edge://gpu`) | WebGL2 reported as hardware accelerated |
| D10 | Flip to Arabic on scenes 0, 3 and 4 | Every label shaped and legible; no empty boxes; numbers identical to English |
| D11 | Record a passing run of the full story on screen | Recording copied to the separate device and plays there |
| D12 | Copy the freeze bundle and the latest `app` dump to removable storage | Copy verifies with `sha256sum -c SHA256SUMS` |
| D13 | Only at go-live, after the owner has switched the live adapter on: `./eii preflight` | Model line reads `present`; spend cap confirmed in the provider console by the owner. During the build the line reads template mode and this step is skipped |
| D14 | Pause Windows updates, notifications and sleep for the day | Settings show paused or off |
| D15 | Complete the pilot request (section 9) and print two copies | Every field filled by the owner |
| D16 | Prepare the session record (section 10) outside the repository | Blank record ready |
| D17 | On the venue display, choose the theme (dark or light) and the room scale (1.0, 1.15, 1.3) | Both written in the session record; every scene legible at the chosen scale |
| D18 | Confirm the recorded human review of this release before relying on `./eii freeze` (RUN-12): role, date, and that the survival report and the signed attack report were read | The record is present. Freeze is not run, and a frozen bundle is not used, without it |
| D19 | Confirm the completed two-run freeze before the bundle is installed or started on the stage machine (RUN-13) | `freeze.json` exists and says `complete`; the register line is on the base branch; the application archive was built by the second no-flag `./eii freeze` run from a base-branch commit containing the line; its checksum verifies; and the register inside the installed application holds this bundle's `window_key` and `protected_sha256`. No signed receipt file is accepted in its place |
| D20 | At the first full rehearsal, time scenes 1, 3, 4 and 8 and the whole story | Each time and the total are written into this runbook and the targets of DES-113; the total meets the 8 to 9 minute target of BRF-33 unless the owner changes that target; later rehearsals keep each scene within 30 s of its target |
| D21 | Play scene 1 and the first act of scene 3 at the venue resolution | Every stored hour lands in order with no visible stall; Pause motion stops playback; the traffic layer and the drive-time outline change with the hour |
| D22 | Load and unload the shipped sample files of cases C3 and C4, then post an unknown sample key and a file body to the case route | Each sample loads with its Synthetic mark and sentence; Reset unloads it; both requests are refused and nothing of either is kept or shown |
| D23 | Open the FDI list, the agency records and one Public split card in the frozen release | Each shows its source and retrieval date; the estimate note sits under the FDI list; every FDI and split chip shows its year |
| D24 | Open one forecast of a published series, one base rate and, when the release holds them, one venue's relative busyness, one people-present-by-pay-band view and, only when OI-03 is closed, one site estimate | The forecast shows its range, its caption with two counts and its measured backtest error; the base rate shows numerator, denominator and period; the busyness is labelled "Google Maps popular times" with its retrieval date; the pay-band view shows the Simulated mark and its caveat; the estimate shows "estimate on simulated inputs" and its low, middle and high cases; none uses a word that RUN-16 keeps off screen |

### 3.2 One hour before

| Step | Command or action | Pass when |
|---|---|---|
| H1 | Mains power connected; stage machine booted | Running on mains; no low-power warning |
| H2 | Windows PowerShell: `wsl --list --running` | Only the Ubuntu distribution is listed. Otherwise `wsl --terminate <name>` for each other one |
| H3 | Ubuntu: `cmd.exe /c ver` | Prints a Windows version. If "Exec format error": `sudo systemctl restart systemd-binfmt`, then repeat |
| H4 | `./eii db-up` | Exit 0; the database answers within 60 s |
| H5 | `pg_isready -h 127.0.0.1 -p 55440 -t 5` (the documented default host and port of `EII_DATABASE_URL`) | "accepting connections", exit 0 |
| H6 | Decide online or offline. If offline, switch networking off now | Decision written in the session record |
| H7 | `./eii up` | As in section 2 |
| H8 | `curl -s http://127.0.0.1:8000/health` | As in section 2 |
| H9 | The stage window and the presenter console are one browser profile. Open `company_a` (the stage window) on the wall and the presenter console on the second monitor in that profile. The `oversight` window and the `company_b` window are two further profiles, so each seat cookie stays in its own profile | One Alt+Tab from the stage profile brings the oversight profile forward |
| H10 | Run scene 0, the evidence step of scene 3 and the first step of case C3 once, then Reset | All three appear within their targets; Reset unloads the sample file |
| H11 | Browser full screen (F11), zoom 100% | No browser chrome on the wall |

### 3.3 Five minutes before

| Step | Command or action | Pass when |
|---|---|---|
| F1 | Look at the presenter console: every field of `GET /health`, refreshed every 5 s | `store: postgres`, `postgres: up`, `ledger: postgres`, model mode as decided, `traffic: simulated`, replays ok |
| F2 | Open `/{lang}/story/0` | Scene 0 is on the wall; the standing strip is visible; the four provenance marks are in the strip before the first figure |
| F3 | Language | Set to the opening language agreed with the host |
| F4 | Windows focus mode on; sound muted | No pop-ups possible |
| F5 | Clicker | Next and Back move the console and are then reset |
| F6 | Backup recording | Cued on the separate device |
| F7 | Wall | No terminal, file browser or console visible |

## 4. The guided story

Latency targets, to be measured, not promised: evidence on screen within 2 s; the checked brief within 6 s when no live model is called (template writer or recorded provider), and within 20 s when a live model composes it. The brief is buffered until the accounting gate has passed; evidence cards may appear earlier. If evidence has not landed by 5 s, use the scene's fallback.

The flagship building is the one chosen in slice S2 after its public places were checked by hand ([04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md)). Do not substitute another building on the day. The story runs with the default traffic provider (RUN-18). The prepared shape drawn around it, the event days, the hours and the ranking weights are those of the story script; do not change them on the day (RUN-15).

### Scene 0 — The living map, real public evidence first (30 s)

| | |
|---|---|
| Tap | Next |
| Appears | The living map's roads and the business points of public places data; then the zone map lit by real electricity growth, licence density and metro and tram ridership and, when the release holds it, night-time radiance by area and month; the standing strip and the four provenance marks dock and stay |
| Point at | The solid Public line style; one figure: Lusail zone 69 electricity rose 3.34 times from 2021 to 2025 against 1.34 nationally (Qatar Open Data Portal, checked 2026-11-11) |
| Say | "Everything marked Public is real and cited: these roads and business points, electricity, licences, metro riders and, when shown, night-time radiance. Everything else is invented, simulated or worked out from real data by tested code, and marked." |
| Fallback | Map blank: recovery R4. Strip or marks missing: reload the scene (RUN-05); if still missing, play this scene from the recording. Never continue without the strip |

### Scene 1 — The Qatari day, hour by hour (target set at rehearsal, step D20)

| | |
|---|---|
| Tap | Next to play a weekday; then the dial through `weekday_lunch`, `weekday_evening`, `friday_evening`, `ramadan_iftar`; then the summer switch; then the event-day chip "National Day" |
| Appears | Crowd density over the city, as estimated people per square kilometre, playing through the stored hours of a weekday; each dial turn moves the Hour control to that situation's window; National Day plays its own stored hours; separate Public monthly context cards beside the dial; no wages yet |
| Point at | Moving dashes: Simulated. The legend: estimated people per square kilometre. On National Day, the caption: a simulated day profile, not a measurement of the event |
| Say | "This is a simulation built locally from public rules: estimated people around each part of the city, hour by hour. The Public monthly series beside it are context and are not matched to the hour. It is not the footfall of any building, and no telecom data is used." |
| Fallback | Dial or Hour control does not respond: Reload (RUN-05). Playback stalls or the layer is blank: recovery R9. Still stuck: describe the day over the static map and move on |

### Scene 2 — Read it honestly (60 s)

| | |
|---|---|
| Tap | Next |
| Appears | The residence wage view, only together with `family_housing`, `labour_accommodation`, `institution` and `unknown` for covered earners, an explicit `other` row when pooling occurred, beside the count that is not measured. The count and the shares beside it come from one additive family. The not-measured count is a separate population. Two areas with the same average are different markets |
| Point at | Dotted: Synthetic. The "average alone is not enough" pair |
| Say | "The same average can hide two different markets. That is why the card never shows the average alone." |
| Fallback | Wage view appears without the housing split: Back at once. If the split is still missing, play scene 2 from the recording and say it is a recording. Do not open the pay cards in scene 3 |

If OI-03 is open, do not show the unit-economics hero or the national pay card. Say: "Those two published tables stay off screen until they are reconciled." The break-even panel (method card C4), the catchment-share scenario and the revenue range of the user's outlet (cards C34 and C35) and the site estimate (card C33) are also off screen until OI-03 is closed, so scene 5 then shows the supplier lens only (MTH-23 and MTH-29 in [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md)).

### Scene 3 — The flagship: one location, drawn (target set at rehearsal, step D20)

| | |
|---|---|
| Tap | Next through its three acts |
| Appears | Act 1: fly; the prepared shape drawn around the door, with the caption that Public points and simulated estimates are computed for that exact shape; estimated people around this location with their range, hour by hour, split into workers, residents and visitors; a major match day beside a regular weekday; the traffic layer, with the drive-time outline re-forming between a morning and an evening hour. Act 2: listed places of the same kind, with the open-listings note; the snap report as the pay cards open, then pay of workers and of residents with the coverage bar; real restaurant unit economics (skipped while OI-03 is open). Act 3: the checked brief is buffered until the accounting gate has passed, then appears as the decision sentence, then the three evidence-status sections Observed, Inferred and Still to test, plus the separate coverage section Not measured; items may then appear one after another for legibility, each component only after it validates, and its receipt shows "Checked before display". Then Language: Arabic, with identical numbers |
| Point at | The exact-shape caption; the range beside every estimated count; the Simulated outline of the drive-time area; the snap caption before the pay cards; the "open listings are incomplete" note; the Synthetic pay cards, titled as statistics of the area, beside the Public coverage bar; the unit-economics source, only when OI-03 is closed (restaurants, activity 561, 2022: production value QAR 6,337,897 thousand; 2,086 establishments; 41,458 employees, Qatar Open Data Portal, checked 2026-11-11); tap one number to open its Source chain drawer |
| Say | "Draw any area and you see estimated people around this location through the day, with a range, and the traffic of each hour. These are simulated, and none of it is this building's footfall. Pay is different: the area is fitted to whole grid cells before any pay figure is read. Every number is computed on the server and traces to its table, source and release. The words come from fixed templates. Observed does not mean real: these pay figures are Synthetic." |
| Fallback | No evidence by 5 s: recovery R1. Shape or its evidence fails: recovery R10. Hourly layer stalls: recovery R9. Evidence but no words: recovery R3. Arabic looks wrong: recovery R5 |

### Scene 4 — Where else fits (target set at rehearsal, step D20)

| | |
|---|---|
| Tap | Next: the ranking lands; Next applies the prepared weight change; then the "Public criteria only" switch; then the Reverse view; then Similar areas |
| Appears | Candidate areas for the same activity ranked by the criteria shown, each rank with its stability sentence; after the weight change the order re-forms and the sentences change with it; in public-only mode the ranks carry the Public mark; the Reverse view ranks activities by fit for the flagship area; Similar areas shows at most three area types with their stability figures |
| Point at | The weights tagged "your inputs"; one rank-stability sentence; the caveat "Ranked by the criteria and weights shown. Not advice, and not a forecast." |
| Say | "The order comes from criteria you can see and weights you can change, and the sentence beside each rank says how firm it is. It is not advice and not a forecast." |
| Fallback | Ranks do not update: recovery R11. A view is missing: move on without comment |

### Scene 5 — Costs and suppliers (60 s)

| | |
|---|---|
| Tap | Break-even; on the presenter console enter rent 40000, seats 60, average bill 120, opening days 30, expected covers 50; then change rent to 60000; then, when the release holds one for this activity, Next applies the prepared incentive package; then the supplier lens |
| Appears | The break-even panel opens empty, with six inputs in this order: monthly rent, seats (a whole number, at least 1), average bill, opening days (default 30, editable), expected covers (optional), monthly staff cost (optional). Rent opens empty. The panel posts the inputs to the server method and renders the returned facts; the browser computes nothing. Results are Inferred "your inputs" chips: the 2022 covers per day and the minimum and maximum across 2018–2022. Breakpoints appear only because expected covers is filled: maximum rent, minimum bill and, when monthly staff cost is entered, maximum staff cost; the track's tick is maximum rent and its marker is the entered rent. The optional second result line reads "to earn the sector's 2022 surplus share" and is never called break-even. An optional input after the six chooses one incentive package from the agency's pages, shown with its source page and retrieval date; the results stay "your inputs". Then the supplier lens: ranked bars, one block per basket input, at most five origins per input, with chips labelled "Calculated import unit value (QAR per kg)" and the valuation basis as the source states it or "not stated by the source" |
| Point at | The "your inputs" tag; the incentive package's source page and retrieval date, when shown; one basket-line chip labelled "Calculated import unit value (QAR per kg)" that the release actually shows |
| Say | "The cost structure is public; the break-even is your own scenario, and an incentive package is an option you choose from the agency's published page. This is not a sales forecast." |
| Fallback | If OI-03 is open, skip the break-even and the scenario tools and show the supplier lens only. Calculator error: Reload; if it still fails, show the break-even page of the printed pack. Supplier lens missing: move on without comment |

### Scene 6 — Try to break it (90 s)

| | |
|---|---|
| Tap | Next, then Run on each of the four rows already on the prepared safety-regression panel |
| Appears | Named-entity pay is declined by the application; two different shapes snap to the same units and return the identical answer; the complement step calls `POST /api/proof/scene` (PRV-119), where one manifest-listed fixture id selects two prepared pin, mode and cut-off requests that differ by one published merged unit of at least two base cells, and no figure exists for any member base cell alone; the endpoint returns their pre-validated unit sets; the typed phrase "the city minus this cell" is declined separately by the application; the signed injection fixture supplies invalid structured output, catalogue validation rejects it and its one prepared invalid repair, and the playbook fallback appears, logged from the signed fixture identity; the unprotected comparison is a replay labelled as signed build-time results. Any canary is named only by its scenario label |
| Point at | The privacy receipt; grey hatch with a lock: Suppressed; the "replay" label on the unprotected comparison |
| Say | "This is a prepared safety regression against disclosure controls with stated rules, not a certified or formally private system. It does not claim general injection detection. The thresholds are proposals for data owners." |
| Fallback | Any attack appears to succeed: stop the scene, say "that should not happen; we will report back", record it (section 10). Never improvise an explanation |

### Scene 7 — The Minister minute (60 s)

| | |
|---|---|
| Tap | The national pay card, only when OI-03 is closed; then Alt+Tab to the `oversight` window |
| Appears | The national pay card, only when OI-03 is closed: mean monthly pay QAR 10,084 in 2020 to QAR 11,855 in 2025, QAR 38 from pay change within occupation groups and QAR 1,733 (97.8%) from workforce mix, with the published table named on the card (Qatar Open Data Portal, checked 2026-11-11). Then the questions asked in this session arriving in the ledger, with seeded history marked Synthetic and no company identity |
| Point at | The table name on the pay card, when OI-03 is closed; the "this session" tag on live rows |
| Say | "Composition drove most of the average." Do not say that wages did not rise |
| Fallback | Oversight shows "paused": say "the ledger is held locally and will catch up", show the pay card only when OI-03 is closed |

Alt+Tab back to the `company_a` window before scene 8.

### Scene 8 — The four cases (target set at rehearsal, step D20)

| | |
|---|---|
| Tap | The "Cases" group of the Journey home; Start on case C1, then Next through its steps; the same for cases C2, C3 and C4. In cases C3 and C4, Next on the first step loads the shipped sample file |
| Appears | Case C1, an industrial services firm: employer scale by size and activity, industrial capacity and announced investment projects with the source's estimate note, ending with a targeted commercial assessment to run before committing. Case C2, a technology supplier: licensed activities and employer concentrations by sector, then a prospect list of register companies with their card fields and employee counts ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)), ending with a focused list to approach. Case C3, a distributor: the sample delivery file card marked Synthetic, customer concentrations by area, drive-time areas by hour from two candidate sites and their shared reach, ending with a defined trial before the capital commitment. Case C4, a retail chain with a weak branch: the sample branch sales card, estimated people around the branch by hour, residential pay bands after the snap and what changed in the area, ending with a test of hours or offer |
| Point at | "Illustrative case. The company is fictional."; the criteria and the rank-stability sentence beside every company list; the sample-file sentence; the FDI estimate note; each case's answer is a test to run, not a verdict |
| Say | "Four illustrative companies, each with its own question. The companies on these lists come from the public business register, ordered by criteria you can see and change; the sample files are synthetic and stay in this session, and every case ends with a test to run, not a verdict." |
| Fallback | A case does not start or a sample file fails: recovery R12. Any figure without its mark: stop the case and go to scene 9 |

### Scene 9 — Hand-over (30 s)

| | |
|---|---|
| Tap | Pack; then, if online with a key, one of the three suggested next questions asked live; then hand the controls over |
| Appears | The one-page bilingual briefing pack; the live answer with evidence first and no "Prepared" mark; controls unlock on the same map with the Journey home and a permanent Reset |
| Point at | Every pack figure keeps its mark; the assistant mode badge beside the Brief |
| Fallback | Pack fails: offer the printed pack from the day before. Live answer slow or refused: recovery R3 |

A staffing question uses the 30-minute drive. No other question offers that cut-off.

If the Proof room is opened, the only machine-assistance sentence is the activity-spine lineage line: "N activity codes; review order machine-assisted; every mapping signed by a person." Do not say a model is choosing facts or writing the brief.

## 5. Recovery for each rehearsed failure

| ID | Requirement |
|---|---|
| RUN-08 | Each recovery below is rehearsed at least once before the first session and its rehearsal result is recorded. |
| RUN-09 | The presenter decides within 10 s of the symptom. ASSUMPTION: 10 s is the longest silence a ministerial audience tolerates without comment. |

### R1 — Database not answering

| | |
|---|---|
| Symptom | Evidence cards do not land; console shows `postgres: down`; oversight seat stops updating |
| Do | 1. "Switch to embedded reader". 2. Reload to restart the current scene. 3. In scene 7, if OI-03 is closed, show the pay card only |
| Say | "We have moved to the embedded copy of the same release. The figures are identical; the two engines are checked against each other." |
| Do not | Start, stop or inspect PostgreSQL or Docker during the session. Switch back during the session |

### R2 — Network down

| | |
|---|---|
| Symptom | At go-live, the live question stalls with evidence on screen; the console shows the model unreachable. Story scenes are unaffected because they are prepared |
| Do | "Offline". Prepared recordings and the template writer then serve every question. The map, tiles and fonts are local and are unaffected |
| Say | "The product does not need the network. The wording now comes from prepared and template answers; the numbers are the same." |

### R3 — Model refusing or slow

| | |
|---|---|
| Symptom | A refusal: the application has already replaced the answer with a template brief marked "Template writer". Or slow: the checked brief has not appeared by its target (6 s when no live model is called, 20 s when a live model composes it) with the evidence already on screen |
| Do | Refusal: press Offline. The playbook default layout and the claim templates remain, with the same numbers. Slow: read the evidence cards aloud, which are complete without the words; then press Offline for the rest of the session |
| Say | "The evidence comes first by design. The words come from fixed templates; the model only selects which claims to show." |

### R4 — Blank map tiles

| | |
|---|---|
| Symptom | Data layers over an empty background, or a grey stage |
| Do | 1. Check console `tiles`. 2. Reload once (RUN-05). 3. If still blank, carry on: cards, brief and pack do not depend on the basemap. For scenes 0 and 1, the first act of scene 3 and the Stage of scene 4, which do, play that scene or act from the recording and say so |
| After | Check the PMTiles file hash, range requests and the browser cache |

### R5 — Missing Arabic glyphs

| | |
|---|---|
| Symptom | Empty boxes, unshaped letters or missing labels after the Arabic flip |
| Do | Reload once. If still wrong, flip back to English and show the Arabic flip from the recording, saying it is a recording. Never leave broken Arabic on screen |
| After | Check console `fonts`, the Arabic glyph ranges served with the basemap, and the interface font files |

### R6 — Browser or machine failure

| | |
|---|---|
| Do | Browser crash: reopen the stage link from the console; the scene URL resumes. Machine failure: select the display's second HDMI input and finish from the recording. Say that it is a recording |

### R7 — Freeze refused

| | |
|---|---|
| Symptom | The first `./eii freeze` run exits 7 before the session because the same `window_key` is already registered with different protected tables, the same `world_seed` has a different `window_key`, or the human review record is missing |
| Do | Stop. Never edit or remove a register line. For a register conflict, any change after a freeze to rules version, exported set, treatment code or world generator requires a new `world_seed` and a new build before another freeze (PRV-120). For a missing review, complete and record the review, then rerun the first freeze step |
| Do not | Retry the conflicting build unchanged, or use a new seed to disguise a second treatment of the registered window |

### R8 — Frozen bundle refused at install or start

| | |
|---|---|
| Symptom | Installer or `./eii up` exits 7 because the installed application's register lacks the bundle's line or `freeze.json` is not complete |
| Do | Finish the freeze. Merge the register line by normal pull request if needed, then run `./eii freeze` a second time with no new flag from a base-branch commit containing the line. Verify the application archive checksum and that `freeze.json` says `complete`, then reinstall |
| Do not | Change the seed, edit the register inside the installed application or add a receipt file |

### R9 — Hourly layers stalled or blank

| | |
|---|---|
| Symptom | Crowd density or traffic stops on one hour, skips hours, or draws nothing while the Hour control moves |
| Do | 1. Pause motion, then step the hour by hand on the Hour control. 2. If the layer is still blank, reload the scene once (RUN-05). 3. If it is still blank, show one stored hour, describe the day over it, and move on; for scene 1 or the first act of scene 3, play it from the recording and say so |
| Say | "This is a simulated day; here it is one stored hour at a time." |
| Do not | Describe movement that is not on screen, or name a building as the place where people are counted |

### R10 — Drawn area or its evidence fails

| | |
|---|---|
| Symptom | The prepared shape does not draw, or a refusal or an error appears in place of its evidence |
| Do | 1. Back, then Next, to apply the prepared shape again. 2. If it still fails, play the first act of scene 3 from the recording and say so, then continue with the second act |
| Say | "The area is the user's own input; the recording shows the same steps on the same release." |
| Do not | Draw a new shape freehand on the wall: it has no prepared answer (RUN-15) |

### R11 — The ranking does not update

| | |
|---|---|
| Symptom | After the prepared weight change, the ranks stay dimmed or do not move |
| Do | Back, then Next, to apply the prepared weights again. If it is still stuck, show the ranking as it first landed, say that the order depends on the weights shown, and move on |
| Say | "The order is only as firm as the sentence beside each rank says." |
| Do not | Name a "best" area, or re-order anything by hand |

### R12 — Case story or sample file fails

| | |
|---|---|
| Symptom | A case does not start from its card, or its sample file is refused or does not load |
| Do | 1. Reset, which unloads any sample file, open the "Cases" group and start the case again. 2. If the file is refused again, skip that case and say so. 3. If a case story fails twice, play it from the recording and say so |
| Say | "Each case uses its own synthetic sample file, and that file never leaves this session." |
| Do not | Load any other file, or describe a case result that is not on screen |

## 6. Prepared answers to hard questions

Each answer is short and true. If a question goes beyond these, say "I will come back to you in writing" and record it.

| Question | Answer |
|---|---|
| Is this real footfall? | No. The people shown are estimates from a local simulation built from public rules, always with a range, for an area you draw or choose. They are never the footfall of a named building or business. Their seasonal shape is calibrated and checked against published monthly museum visitor counts, which are real Public counts for those named places and are shown separately as such. The hourly shape of the simulated visits is also calibrated to the relative busyness by hour of the named venues of each place category, pooled; a named venue's own relative busyness by hour is a Public fact from Google Maps popular times, with its retrieval date, a relative index and not a count of people, and it never sits in one component with an estimated-people figure. Separate Public monthly context series sit beside them on their own cards and are not matched to the hour. No telecom operator was contacted. |
| Is any of this real data? | Only the figures marked Public, each with its source, licence and date, and what tested code works out from them: a forecast of a Public series is marked Inferred and keeps that source; a base rate of a Public series is marked Observed and keeps that source; and a forecast of a released monthly series is marked Synthetic. The companies are the real ones of the public business register and of the financial centre's public register, with the fields those registers publish; every person, and every employment, wage and residence record attached to the companies, is invented, shaped like the real custodian records ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)). |
| Are these companies real? | The companies are. Every company on a card or in a prospect, partner or supplier list is a real company of the public business register or of the financial centre's public register, shown with the fields the register publishes. The workers, wages and residence behind them are generated records shaped like the real custodian records, and the number of employees on a card is counted from those records; every source is under "More evidence". A company's wages and other labour and residence details are never shown for that company, only inside protected figures for an area. Other real businesses appear only from public places data and public listings, in their own list. The two company seats and the four cases are fictional. |
| Is the ranking a recommendation? | No. It orders areas by criteria you can see and weights you can change, and the sentence beside each rank says how much the order depends on those weights. It is not advice, a probability or a forecast. |
| Where do the investment projects and the agency's information come from, and may you use them? | From the FDI projects dashboard of the national investment promotion agency, whose data come from fDi Markets, and from the agency's sector, opportunity, incentive, set-up and law pages, read by the fetcher at each build. Capex and jobs are the source's own estimates of publicly announced projects, and the dashboard does not capture every project. The registry records the publisher's terms as read at fetch and the basis of use: the owner's decision for this personal internal project, made without a permission request. Citing a source is not an endorsement: the agency has not endorsed this work. If the demonstrator were ever hosted publicly, the owner would decide then which sources stay on. |
| Can I load my own company's records? | Not in this demonstrator. Cases C3 and C4 load only their shipped synthetic sample files, which stand for a company's own records and stay in the session that loaded them. A company's real records would be real data, which the demonstrator never takes. |
| What leaves the building to the model, and who approved it? | Only tool results: protected aggregates, public figures and simulated aggregates. Never a record, and never a row of a sample file. Every call is listed in the egress record in the Trust centre. The owner approved an online model for this synthetic demonstrator. The model runs on the provider's servers, not on this machine; no in-country processing is claimed. Using it with real data would be the custodians' decision. Today it can run with no model at all. |
| Is other AI used? | One typed-decision model sits behind the stage only for build, evaluation and scripted-rehearsal work. It never sees visitor-typed text or chooses screen content. It may order the human review queue, but every mapping is signed by a person; the Proof room shows that lineage in one line. |
| Can a company look up a competitor or a person? | No. A company's public card, with the fields the register publishes and its number of employees, can be opened from the map or a list; that is not a lookup, and it shows no pay. Owners and people cannot be looked up. Pay for a named entity is declined, and no estimate, share or score is made for a named competitor. Real named places carry only public facts: name, category, distance. The list of announced investment projects shows published announcements and cannot be searched by company name. Each company seat sees only its own briefs: the seat is a signed session cookie in its own browser profile, and where two-company separation shipped and PostgreSQL is running, the database refuses another seat's brief. This is query isolation after a seat is selected, not an account or tenant authentication; confirm before the session which applies. |
| How do you know the privacy rules hold? | Each selected release passes exhaustive structural closure checks, at least 10,000 fuzz pairs per release and parameter set, and typed attacks with controls off and on. The attacker-view audit is evidence under a stated attacker, not a proof. It uses one model: every published leaf is fixed to its untreated aggregate, knowledge fixtures are checked against sealed truth before use, and a published leaf is treated as having passed its rules. The audit does not model what the layout tells about a population that failed a rule; the typed attack suite holds one attack for each such signal. Figures from different tables can differ slightly because each table is protected on its own. Version 1 makes no consecutive-window claim. Its monthly periods sit inside that one protected window, and the attack suite adds differencing across months, apportioning to drawn shapes and linking the list of register companies, with every company's employee count known to the attacker, with area figures; each must recover nothing with the controls on. Both parameter sets are evaluated inside the custodian plane, but exactly one selected set's protected tables are exported. `window_key` is the SHA-256 of canonical JSON holding the protected `period` and, in name order, `{name, sha256}` for `business_register.v1`, `employment.v1`, `residence.v1` and `wages.v1`, using each feed's manifest `feed_sha256`; nothing else enters it. Continuous integration allows one `protected_sha256` per `window_key` and one `window_key` per `world_seed`. For a frozen release, the register inside the installed application is the allow-list and `freeze.json` must say complete; a window is never exported under two treatments (PRV-120). The Proof room may show survival figures for both sets and tables for the exported set only. No person-level protection is claimed for movement. These are proposals for data owners, not a certification, and real suppression rates are unknown until the engine runs on real data inside a custodian's environment. Before the session, confirm in the Proof room that the release on screen passed. |
| Why not use the existing services? | They do their own jobs well. Existing public business maps show where businesses are. This adds what only joined records can show, pay and residence and estimated people around a location, under visible protection. It is designed to plug in beside them, not replace them. |
| Has any ministry endorsed or used this? | No. It is a demonstrator built on invented records and public data. |
| What would it take to make it real? | The same engine run inside a custodian's environment on real feeds, publishing only protected statistics. The models read the release tables that the five feeds fill, named by their contracts, so the same code runs on real feeds; nothing here says that real records are used. The pilot request (section 9) states which feeds and how we would judge it. |
| Where do popular times, live traffic, night-time lights, places and weather come from, and may you use them? | The project's own build reads them from their publishers into a local cache: relative busyness by hour of named venues from Google Maps popular times, night-time radiance from NASA, population by age and sex from WorldPop, hourly weather from Open-Meteo, and a further open places dataset from the public Source Cooperative copy (`places_fsq`), read without an account; the owner decided on 2026-11-12 that this copy, dated 2025-01-10, is used for version 1 as it is, and where a place of it disagrees with OpenStreetMap or Overture the newer source wins. The registry records each one's publisher, licence or terms, and retrieval date. The popular-times source states no licence for reuse and the publisher's terms name automated reading; the registry records those terms as read, and the basis of use is the owner's decision for this personal internal project (`licence_basis: owner_decision`). Its values stay in the uncommitted cache, in no test fixture and out of the nightly fetch. Live traffic is off by default, and the traffic is then simulated locally. If the owner switches the provider on, the API process fetches flow tiles and traffic-aware drive-time areas from the provider, shows its attribution, reads no number from a tile and stores nothing of a response; the browser contacts only this machine. If the demonstrator were ever hosted publicly or for a commercial purpose, the provider, popular times and the free weather interface would be off until the owner decides. |
| Can it forecast whether a venture would succeed? | No. It gives no forecast of the success of a venture, no verdict and no advice. What it gives is computed by tested code and shown with its method and source: a forecast of a published series, such as licence issues or hotel room rates (or of a released monthly series, marked Synthetic), with a range taken from the model's own past errors, the number of past values that fell inside the range that the other past errors gave and its measured error; a base rate, which is a share of past licences of an activity and area with its counts and period, not the chance that your own venture survives; an estimate for a place with low, middle and high cases of the model, labelled "estimate on simulated inputs" while an input is simulated; and your own scenario, with every assumption visible and editable, which is never a forecast. None of them is made for a named business or competitor. |
| Is the pay of the people present what they spend? | No. The figure of people present by pay band assumes that the workers and residents present have the pay bands of the unit's covered workers and residents; it is simulated, inferred and marked so. A pay band is a wage statistic and not a spending figure. Visitors have no pay band and are shown as one count without a band; the figure does not separate people who have no wage record. |

## 7. Tone

- Say "demonstrator" and "proof of method". Say "Synthetic", "Simulated" and "Public" exactly as the marks do.
- Say "estimated people around this location", "ranked by the criteria you set", "projection", "your scenario", "estimate on simulated inputs", "relative busyness" and "the source's estimates" (for FDI capex and jobs), and "forecast" only for a forecast of a published or released series with its backtest error, exactly as the screen does (RUN-16).
- Volunteer a limit before you are asked: coverage is partial; wages paid are not spending power; open listings are incomplete; estimated people are not purchases; a pay band is not spending; a base rate describes past licences and not your venture; the range of a forecast is the record of its own backtest and not a promise about the next value; relative busyness is an index and not a count; a change between synthetic months is not a change in Qatar.

## 8. Prohibited claims

Never say or imply that:

1. the POC uses real custodian data;
2. a Synthetic or Simulated figure describes a real place;
3. a Simulated or Synthetic footfall figure, or an estimate, share or score, belongs to a named building or business (say "estimated people around this location");
4. the privacy engine is certified or formally private;
5. an existing public service is wrong or inferior;
6. the ministries have endorsed or run the system;
7. a forecast of the success of a venture is given, or a forecast, estimate or base rate is shown that tested code did not compute or that lacks its interval, range or counts, its method and its source;
8. any firm, owner or individual can be looked up (showing a register company's public card and its employee count is not a lookup: [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md)).

Under [decision 0016](decisions/0016-version-1-covers-the-whole-initiative.md), [decision 0017](decisions/0017-public-data-additions-and-public-splits.md), [decision 0019](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md) and [decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md), also never say or imply that:

- a ranking, fit or suggestion is advice to act, a verdict, a probability or a confidence;
- a fictional company seat or case (`company_a`, `company_b`, cases C1 to C4) is, or stands for, a real business; named synthetic firms are retired ([decision 0022](decisions/0022-real-register-companies-with-a-synthetic-world.md));
- a projection is a forecast;
- a scenario, an estimate, a ranking or a fit is a forecast;
- a base rate is the chance that the user's own venture survives, or the range of a forecast or the cases of an estimate are a probability or a confidence;
- the people present by pay band are spending, spending power or income present;
- relative busyness by hour is a count of people or the footfall of a venue, or night-time radiance measures business activity;
- an FDI capex or jobs figure is exact or complete, or that the investment promotion agency endorses this work;
- an official split by sex or nationality describes the synthetic records, or is apportioned to a drawn area (whole cells of the published population grid, summed over an area, are shown as that sum, Public, with their year);
- a change between synthetic months is a change in Qatar.

If a slip happens, correct it on the spot in one sentence and record it.

## 9. The closing ask: pilot request template

The owner completes every field before the session (D15). Fields left blank mean the ask is not ready and is not presented.

```
PILOT REQUEST — Economic & Investment Intelligence (EII)

1. Purpose (one sentence):            <owner>
2. Feeds requested
   Record type(s):                    <business_register | employment | wages | residence | mobility>
   Fields and level:                  <owner, per contract in docs/03_DATA_CONTRACTS.md>
   Reference period:                  <owner>
   Custodian of each feed:            <owner>
3. The pilot
   Scope (activity, area):            <owner>
   Where it runs:                     inside the custodian's environment; only protected statistics leave
   Duration and checkpoints:          <owner>
   Who operates it:                   <owner>
4. Pass criteria (all must hold)
   - Condition: <owner: e.g. every feed passes its conformance suite>
     Threshold: <owner>
     Named judge: <owner>
   - Condition: <owner: e.g. the attack suite recovers no canary under the agreed parameter set>
     Threshold: <owner>
     Named judge: <owner>
   - Condition: <owner: share of earners published at the agreed geography, threshold set with the data owners>
     Threshold: <owner>
     Named judge: <owner>
   - Condition: <owner: named users answer the agreed questions within the agreed time>
     Threshold: <owner>
     Named judge: <owner>
5. Kill criteria (any one stops the pilot)
   - Condition: <owner: e.g. no lawful basis to link the requested feeds>
     Threshold: <owner>
     Named judge: <owner>
   - Condition: <owner: e.g. protected statistics too coarse to answer the agreed questions>
     Threshold: <owner>
     Named judge: <owner>
   - Condition: <owner: e.g. any confirmed disclosure>
     Threshold: <owner>
     Named judge: <owner>
6. Decision requested today:          <owner>
7. Decision owner and date:           <owner>
```

Every pass and kill condition carries a condition, a threshold and a named judge (BRF-53 and BRF-54 in [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md)). The example criteria are prompts for the owner, not commitments.

## 10. After the session

| ID | Requirement |
|---|---|
| RUN-10 | The session record is kept outside the repository and never committed. `PROGRESS.md` receives only a summary with no personal names, no organisation names of attendees and no quotation. |
| RUN-11 | Within 24 hours the team records each item below. |

| Record | Detail |
|---|---|
| Session facts | Date, duration, venue screen, online or offline, store used |
| Timings | Actual time per scene against the plan |
| Failures | Each symptom, recovery used, time to recover, whether the audience noticed |
| Questions | Every question asked, the answer given, and any promised written follow-up |
| Slips | Any prohibited claim or unclear statement, and the correction given |
| Ledger | The count of ledger rows tagged "this session" and of egress records; export aggregates only |
| Sample files | Confirmation that every sample file loaded in the session was unloaded at its end (RUN-17) |
| Outcome | The pilot request's status and the decision owner's response |
| Actions | Fixes to the product or to this runbook, each as a task in `TASKS.md` |

Then run `./eii down`, back up the `app` schema and the local ledger ([13_DEPLOYMENT_AND_OPERATIONS.md](13_DEPLOYMENT_AND_OPERATIONS.md), section 9), and return the removable storage.

## Open questions and assumptions

ASSUMPTIONS made in this document:

- Two people run each session (RUN-01).
- The presenter decides on recovery within 10 s (RUN-09). A slow checked brief uses the latency targets in section 4, not that 10 s limit.
- The single live question, at go-live only, sits in scene 9, after the pack (RUN-04).
- The presenter console carries the Scenario inputs control, because the wall has no keyboard (RUN-03); the other prepared inputs are applied by Next from the story script (RUN-15).
- The wall shows the `company_a` window; `oversight` is reached by one Alt+Tab (step H9).
- The API address `127.0.0.1:8000` and the health fields follow [13_DEPLOYMENT_AND_OPERATIONS.md](13_DEPLOYMENT_AND_OPERATIONS.md), which marks them as assumptions too.
- The story plays National Day in scene 1 and a major match in scene 3, one event day per scene, so that each scene keeps one idea.
- The four cases run in order in scene 8, each from one click.

Open points from decisions 0016, 0017, 0019 and 0022:

- OPEN: the targets of scenes 1, 3, 4 and 8 are set at the first full rehearsal of slice S11 (step D20) and written here and into DES-113 of [11_DESIGN_DIRECTION.md](11_DESIGN_DIRECTION.md), within the 8 to 9 minute total of BRF-33 unless the owner changes that target.
- OPEN: whether the release holds an incentive package that the break-even method of [07_ECONOMIC_METHODS.md](07_ECONOMIC_METHODS.md) accepts for the flagship activity; scene 5 shows the package only if it does.
- OPEN: whether `GET /health` reports the state of the hourly layers, the traffic source, the investment sources or the sample files is for [13_DEPLOYMENT_AND_OPERATIONS.md](13_DEPLOYMENT_AND_OPERATIONS.md) to decide; this runbook checks them by steps D21 to D24.
- OPEN: whether the story shows any figure of decision 0019 (a forecast, the site estimate, people present by pay band, popular times or the 3D view) is set at the first full rehearsal (step D20). Until then the ten scenes and their targets are unchanged and none of these figures is in the story; they are available at the hand-over, under the honesty lines of RUN-16. Scene 1 stays free of pay.
- OPEN: whether the 3D view is staged as a prepared step applied by Next, or set at start. The closed list of presenter controls in RUN-03 changes only by an owner decision. The guided story runs with simulated traffic (RUN-18); any live-provider hand-over is configured at process start, outside the guided story.
- OPEN (decision 0022): whether the story opens a register company's card from the map or a list, beyond the company lists of case C2 in scene 8, is set at the first full rehearsal (step D20).

Open items from the master design that touch this document: OI-01 (key supplied for go-live, not used during the build; spend cap set at go-live), OI-02 (demonstration date), OI-03 (restaurant totals and wage-table means must be reconciled before scenes 3, 5 and 7 show them), OI-06 (source labels on screen), OI-08 (label for live ledger rows), OI-09 (native Arabic reviewer), OI-11 (privacy thresholds are proposals), OI-14 (no run-time use of the typed-decision gateway before an approved route), OI-18 (token cap on the subscription), OI-35 (which parameter set is exported; default A until the owner or a data owner decides, needed before the slice S1 gate).

## Sources

- [Decision 0016 — Version 1 covers the whole initiative](decisions/0016-version-1-covers-the-whole-initiative.md) and [decision 0017 — Public data additions and public splits](decisions/0017-public-data-additions-and-public-splits.md), accepted 2026-11-12: the ten-scene story's new content, the cases and sample files, the investment sources and their basis of use.
- [Decision 0019 — Forecasts, estimates and scenarios by tested code; six self-serve sources](decisions/0019-forecasts-estimates-scenarios-and-self-serve-sources.md), accepted 2026-11-12: the presenter words for forecasts, estimates, scenarios and base rates, the default traffic provider of the story, popular times and its basis of use, and the prohibited claims it adds.
- [Decision 0022 — Real register companies with a synthetic labour and residence world attached](decisions/0022-real-register-companies-with-a-synthetic-world.md), accepted 2026-11-13: the words for register companies in scene 8 and section 6, and the prohibited claims of section 8.
- FDI projects dashboard of the national investment promotion agency, `https://fdiprojects.invest.qa/` (data from fDi Markets), read 2026-11-12 as recorded in decision 0017: the estimate note quoted in section 6.
- Qatar Open Data Portal (CC BY), zone electricity, wage, restaurant-sector and customs tables, figures checked 2026-11-11 as recorded in [04_PUBLIC_DATA_PACK.md](04_PUBLIC_DATA_PACK.md).
- EII architecture-options research, 2026-11-11 (project research record held by the owner): WSL interoperability failure and its fix.
- EII feasibility-and-cost and minister-impact judgements, 2026-11-11 (project research records held by the owner): stage risks, the closing-ask requirement.
- Microsoft, WSL issue 8952, https://github.com/microsoft/WSL/issues/8952, retrieved 2026-11-11.
- PostgreSQL Global Development Group, "pg_isready", https://www.postgresql.org/docs/18/app-pg-isready.html, retrieved 2026-11-11.
