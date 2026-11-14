# Performance spike

A development page that draws 110,000 synthetic hexagons and 50,000 synthetic particles on an invented extent. The extent is centred on longitude 0.02 and latitude 0.02. It has no place name and no basemap of a real place. The seed is 1. Hexagons are H3 resolution 8, and the first 110,000 cells of a disk are kept. Nothing here is a feature screen.

## Strings that wait for the owner's native reading

- محاكاة `pending native review`
- إيقاف الحركة مؤقتًا `pending native review`
- عرض اصطناعي. امتداد مخترع. بلا اسم مكان. `pending native review`

The notices and provenance words live in `notices.json`. The page reads them from that file. A model does not change the mark to approved.

The map canvas is 1920 by 1080 CSS pixels. Its pixel ratio is capped at 1 device pixel per CSS pixel. That cap is an assumption: it is held constant, recorded on the trace, and never searched. Text on the page stays at the display's own pixel ratio.

## Commands

From the repository root, with Node 22 first on `PATH`. The headless shell is the one the glyph spike already fetched. This spike does not install a browser.

- `npm --prefix web run spike:glyphs:install-browser` is the prerequisite when the shell is missing. It needs the network once. A missing browser fails the suite and names this command.
- `npm --prefix web run test:spike:performance` runs the Node tests. The browser tests build the page into a temporary folder, assert the layer counts (two, or three with roads) and the recorder contract, and do not assert a frame rate.
- `npm --prefix web run spike:performance:serve` starts a loopback server and prints three addresses (original set, first road load, full street load; see Road trace hand-off). Open the first in Windows Chrome or Edge on the host. When the page does not refuse the environment, it runs a 30-second orbit itself, shows the result, and posts the trace. The server writes the file under `web/spikes/performance/evidence/`.
- `npm --prefix web run spike:performance:verify-evidence` checks a committed native trace. Until the owner commits one, it fails with `missing-native-trace` and writes nothing.

`./eii test` runs these Node tests with the other web checks. Those runs use a short orbit. They report counts. They do not decide the frame-rate gate. The native frame-rate gate is pending.

## What the owner records

The serve command prints a line that ends in `/en/_perf`. Open that exact address in Windows Chrome or Edge, outside WSL. Leave the page open until it shows a path. That path is a JSON file under `web/spikes/performance/evidence/`. The page also says `native frame-rate gate pending`.

The evidence command also needs `web/spikes/performance/evidence/native-capture.md`, committed with the trace. Its lines are `role`, `date`, `host`, `browser`, `trace` and `sha256`. `role` is `owner`, `host` is `windows-native`, `browser` is `chrome` or `edge`, `date` is `YYYY-MM-DD`, `trace` is the repository path of the JSON file, and `sha256` is `sha256:` plus the file's digest. Both files must be committed and unchanged. This spike does not create that capture file and does not invent a trace.

## Trace

The contract name is `eii.performance-trace`, version 1, provenance Synthetic. The original layer set is `hexagons-particles`; the road sets are described below. A gate profile runs for 30 seconds. A smoke profile runs for 400 milliseconds and is refused by the name `smoke-profile`. The share is the unrounded count of frame intervals strictly under 16.7 milliseconds, divided by the interval count. The gate needs that share to be at least 0.95 on a native Windows trace. Percentiles and the share come from `summariseFrames` in `trace.mjs`. The page does not compute them itself.

The server accepts a well-formed trace and stores it even when the gate later refuses it. The evidence command is what qualifies the stored file. A test server cannot write the native evidence directory. The serve command's server stores a posted trace, and the test `the development server stores a posted smoke trace from the page origin` in `tests/vite-server.node-test.mjs` proves it.

## Plants

The browser suite loads the page with one plant at a time: omit one hexagon, hide the hexagon layer, omit one particle, hide the particle layer, freeze the clock, post no timestamps, blank the renderer, add an unknown field, ignore the cap, rename the profile, request a remote image, and skip WebGL2. The blank-renderer plant posts the gate profile after a short orbit so the refusal name is `missing-renderer`. The remote image is `https://assets.invalid/spike.png` and the content security policy blocks it. The gate profile also plants a software renderer, a remote renderer, a capped frame interval on the empty canvas, and a slow full scene whose empty canvas is at 60.

## Renderer and early refusals

As soon as the page has a WebGL2 context, and before the orbit starts, it shows one line with the unmasked renderer: the string `readUnmaskedRenderer` returns. When that string is empty, the line says `none is available`. The line is reference text, on both the English and the Arabic page.

The gate profile refuses on screen at once, does not run the orbit, and posts nothing, when the renderer is missing, a software renderer, the Windows software driver, or WARP (`refused: missing-renderer` or `refused: software-renderer`), or when the renderer names a remote display adapter as its own word (`refused: remote-renderer`). Before the map and its layers load, the same profile counts frames on the empty canvas for about two seconds. If that empty canvas does not reach 60 frames a second, the page shows `refused: capped-frame-rate` with the measured frames a second. It does not load the layers and it posts nothing. If the empty canvas reaches 60 and the full scene does not, the orbit runs and the trace is stored, and the gate judges that trace. A slow full scene is not refused as a bad environment.

If the page refuses, sit at the computer, not through Remote Desktop. Use Chrome at 100% zoom with Energy Saver off.

## Hourly road sets (S1-T11 round two)

`hexagons-particles-roads` adds the recorded fixture links and an invented load of 100,000 short links. `hexagons-particles-roads-250k` uses 250,000 load links. Both retain the original hexagons and particles. These are load sizes fixed by the owner on 2026-11-13, based on his counts of ways: 24,367 motorway to tertiary; 76,703 including residential; 122,720 including service roads. Attribution of that basis: **OpenStreetMap contributors, counted by the owner through the Overpass service**. Ways are not links; the second load represents a full street network. This is the owner's supplied sizing basis, not a public dataset imported by the page or an independently verified count. No figure about a place appears on the page.

`build-road-data.mjs` reads only the recorded product fixtures `hourly_rows.json` and `hourly_roads.json` under `product/tests/fixtures/areas_spike/assignment/`. Run `node web/spikes/performance/build-road-data.mjs` from the repository root to regenerate `road-data.json`. The Node test regenerates it and compares bytes, including the provenance, evidence status, caveat, withheld-flow note and source hashes. No assignment is calculated in the browser. The road load uses the same seeded generator as the original geometry and cycles through the fixture links' classes and hourly bands. It has no names.

One payload holds all stored hours. The paths and their data array remain the same throughout playback; `getColor` update triggers select a stored hour. Width follows road class. Colour follows the closed volume-band keys of the round-one parameter file, with the first band for a missing row. Equal consecutive stored band states stay equal. Two persistent path passes keep the outgoing hour opaque and draw the incoming hour over it at the blend opacity during a cross-fade; a zero-opacity pass retains its data but is not drawn; no band or width is interpolated. Road counts count rendered links once, excluding the path tessellator's invalid terminal padding and the second opacity pass.

Both passes use `PathStyleExtension` with static dashes (DES-67). The legend combines a dashed sample with `Simulated` or `محاكاة`; the Arabic word remains **pending native review** in `notices.json`. The assignment's speeds, ratios and volumes never appear as numerals. Hour labels are marked `reference`.

The configuration names `HOUR_HOLD_MS` for `--eii-hour-hold` (2,500 ms, the `--eii-dur-fly-medium` starting assumption) and `SCENE_MS` for `--eii-dur-scene` (800 ms), from the design document's Motion section. Playback records the hours actually displayed, proceeds in stored order and stops at the last hour. A delayed frame does not skip stored hours. Pause motion stops playback, particles and camera turn; pressing it again resumes. Reduced motion prevents playback, particle motion and camera turn. The page does **not** build arrow-key stepping, manual stepping under reduced motion, or the placement of Play and Pause on the product's Hour control. Those belong to the map foundation (FE-106, DES-51, DES-168).

### Road trace hand-off (S1-T12)

The serve command now prints three addresses: original set, first road load, full street load. Open them in that order in the owner's native browser. The same recorder, server and trace contract are used. Each road trace records all three counts, whether playback was uninterrupted, the reduced-motion state and the displayed hour sequence. Keep motion running and reduced motion off throughout the orbit. Every original qualification still applies, except the road sets record the frame-budget share without imposing a pass threshold. A headless smoke run establishes no native frame-rate result.

For each road set, commit its trace and its own capture file alongside it:

- `native-capture.hexagons-particles-roads.md`
- `native-capture.hexagons-particles-roads-250k.md`

Use the same capture fields documented above and the digest of that specific trace. Then run `npm --prefix web run spike:performance:verify-evidence -- hexagons-particles-roads` and `npm --prefix web run spike:performance:verify-evidence -- hexagons-particles-roads-250k`. Without an argument the evidence command still checks the original set and `native-capture.md`. Missing captures fail with `missing-native-trace`. No native trace is taken by this task.

Run the local web mutation check with `uv run --locked python scripts/mutation_web.py web/spikes/performance/{trace,roads,build-road-data,config,geometry,server,verify-evidence}.mjs web/spikes/performance/{main,layers,road-layer,road-playback}.ts`; it runs the Node tests without the browser suite in a temporary copy and refuses unexplained survivors.

## Browser test fixtures

The browser suite keeps each named assertion test and each distinct plant. Tests
with the same initial language, motion setting and road load share a page within
a default-mode group; a failure does not skip later tests, and selecting one test
still creates its fixture. Each group closes its page before the next one starts.
The uninterrupted road scene records the full stored-hour cycle. A fresh English
pause scene first checks the live paused mark and legend, then supplies one real
pause/resume observation to both the hour-clock and particle
tests, with a guard that the pause starts before the final hour. The first input
action is shared; visibility assertions are not cached. Each consumer asserts
its initial state, and selecting any one test still creates and pauses the scene.
Initial reduced-motion scenes remain separate in both languages. Distinct plants
each load their own page. Independent DOM assertions run together. Layer counts, frame waits, viewport, pixel ratios and
all timeout values remain unchanged. The list reporter gives individual test
durations; shared scene setup durations are printed separately and included in
the measured browser wall time.

Readiness waits on the same animation-frame condition and captures diagnostics
in that callback; the host still enforces the same readiness timeout. The
reduced-motion frame wait likewise returns its snapshot in the callback that
observes more than two further motion frames. The pause
button helper batches checks of visibility, native and inherited ARIA enabled
state, inert ancestors, nonzero bounds, two-frame stability and the centre hit target before sending
real mouse input. It verifies a trusted click on the target afterwards, so an
intercepted click cannot count as a press. This helper is specific to the spike's
static pause button, not a general replacement for Playwright actions. Small-page
browser tests plant absent, hidden, disabled, inert, covered, moving and zero-area
controls, direct and inherited ARIA-disabled controls, an explicit ARIA-enabled
override, interception after preparation, and an offscreen control that must be
scrolled into view. Each named assertion stays. The suite keeps one worker.
Tests whose assertions do not read the canvas size, the viewport, the device
pixel ratio, or a qualification decided after the canvas check load the same
page with the map style at 480 by 270 CSS pixels. The page source stays 1920 by
1080. The full wall is kept for the trace-contract smoke test, the pixel-ratio
cap, the nonblank canvas checks, the gate qualifications decided after the
canvas size, the uninterrupted road trace, the paused-playback plant, the full
street load of 250,000 links, the English pause scene, and the Arabic
reduced-motion scene. The English pause scene is the trusted click on the live
scene. The Arabic reduced-motion scene is opened through the page helper, so
the foreign-request check and the readiness wait both run, and the render
finishes at the full wall. That scene is what covers Arabic and reduced motion
together at the full size: `roads mark and legend are visible ar reduced`.
The English reduced-motion scene, the Arabic playing road scene, and the Arabic
notice route stay on the small map.
A node test reads every call that takes a canvas choice, after comments are
stripped. FULL and SMALL are different values, and the small-map helper shrinks
the style only for SMALL. The set of small-map call sites equals a closed list,
as the set of full-wall call sites does. A test body that reads a size field or
a qualification decided after the canvas check cannot use a canvas other than
the full wall. Switching a listed scene, hiding a full call in a comment, or
adding a size-reading test on the small map fails that test.
The two remote-asset refusal tests close as soon as the refusal is seen. Their
purpose is the refusal. The completion of those two planted scenes is no longer
waited for. A foreign address seen before the page commits is refused by the
helper's scan after readiness, and a node test reaches that scan.
An unhidden small-map scene asserts that the hexagon sample and the particle
sample are present, and an unhidden small-map road scene asserts that the road
sample is present, so a blank sample on the small map can fail.
The small-map road plants that expect reduced-counts rely on the count check
being decided before the canvas check. A node test pins that order.
A foreign request rejects the page helper as soon as the request is seen once
the page URL is http. The rejection text is unchanged.
The JSON reporter also writes `test-results/performance-timings.json` relative to this spike's
Playwright configuration directory, allowing the repository test run's individual
browser durations and overall Playwright duration to be inspected without a
second full browser run.

The mutation runner sets `workers = min(4, processors)` and passes
`--test-concurrency=max(1, processors // workers)` to Node in every mutant's test
command, so the product of worker count and test files in flight does not exceed
the processor count. An unavailable processor count conservatively uses one.
Run only one mutation job on the machine, at normal priority. Killed, survived,
timed-out, uncovered and error counts remain separate. The runner prints exact
locations and replacements for timed-out mutants as well as survivors, so every
timeout can be replayed alone at normal load before interpreting it as evidence.
