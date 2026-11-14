# Reference notes: map libraries

| | |
|---|---|
| Status | Draft written by task S0-T13 on 2026-11-12; every row is as true as the page or run it names, on the date it names |
| Date | 2026-11-12 |
| Owner | Project owner (see OPEN_ITEMS.md) |
| Purpose | Record the official pages read and the idioms that changed from earlier major versions for MapLibre GL JS 6, deck.gl 9.4 and the deck.gl MapLibre module (FE-02), and the two confirmations of DES-25 and DES-45 recorded in the section "Confirmations assigned to this task". |
| Read first | [docs/10_FRONTEND.md](../docs/10_FRONTEND.md) section 2, [the notes for DuckDB, PostgreSQL and the Claude API](../docs/REFERENCE_NOTES.md) |

## How to read these notes

Every statement in a table has one kind. READ: an official page, read on the date given, whose quoted words support the statement and nothing more. OBSERVED: a command run on the date given with the package and version named; the command and its output are in the Runs table of the section, and no browser was used. PACK: the pack says it, the pack anchor is given, and it could be neither read nor observed here, so the statement says "not verified". A page can change after its date: quoted words are searched for again when the notes are checked.

The last section of each file lists the statements of the pack about these libraries and where each stands: a row of these notes, or "not covered" with the reason. The notes name a series, not a pin. Exact pins and retreat pins are the rows of `pins.toml`, which a check compares with the manifests; the table at the end of each section lists what slice S1 still has to confirm, with unmeasured fields marked "not yet confirmed". The task appended to each non-native field's Pack source owns confirmation when the product first uses that behaviour; a retreat-dependent field is checked only if that retreat is selected. The existing validator permits no separate assigned-task value, so the task is recorded in that field's source instead of inventing a measured confirmation. A value beginning "confirmed: " records only the measurement named in its PROGRESS.md task-log heading; it does not confirm untested retreats or broader capabilities. The notes make no claim that a library works in this project: no row says so, because the original READ and OBSERVED rows describe the S0-T13 date; the S1 confirmation fields now cite later project measurements. `scripts/check_reference_notes.py` checks the form of these notes (sections, kinds, sources, allowed addresses, dates, the confirmation tables and the coverage table), that each anchor exists in the cited file and not what the anchored text says, and nothing about whether a quotation is still on its page.

The MapLibre GL JS exact-pin and retreat field, the deck.gl four-layer exact-pin and retreat field, the MapLibre-module replacement field, the MapLibre GL JS and deck.gl spike-result fields, the load trial of 110,000 hexagons and 50,000 particles, and the pixel-ratio cap value remain "not yet confirmed" for the same reason: "waits for the native trace of task S1-T12, which the owner takes at the console; closes with the addendum of the slice S1 gate" (TASKS.md S1-T08 and S1-T12; owner ruling L-82).

The section "Confirmations assigned to this task" is not about a library. It records what was observed in the files of the two Fontsource packages for IBM Plex Sans and IBM Plex Sans Arabic (the weights of DES-25, docs/11_DESIGN_DIRECTION.md DES-25) and in the package that holds the Carbon icons, with the licence of that package and of its repository (DES-45, docs/11_DESIGN_DIRECTION.md DES-45). It adds no package to a manifest and pins nothing: the two font packages are rows of `pins.toml`, and the pack says that the icons are vendored locally with their licence recorded in the repository and names no slice for it. A row of the font table is the files of one subset at one weight; nothing is said about glyph coverage or font features.

## MapLibre GL JS 6

Used here for the basemap, camera, building extrusion and label rendering (docs/10_FRONTEND.md section "Stack and pins" row "`maplibre-gl`"). Series 6; the pins.toml rows are `maplibre-gl` and `@mapbox/mapbox-gl-rtl-text`.

### Pages read

| Id | Address | Page title | Date read |
|---|---|---|---|
| P1 | https://maplibre.org/maplibre-gl-js/docs/guides/v5-to-v6-migration-guide/ | v5 to v6 migration guide - MapLibre GL JS | 2026-11-12 |
| P2 | https://maplibre.org/maplibre-gl-js/docs/ | Introduction - MapLibre GL JS | 2026-11-12 |
| P3 | https://raw.githubusercontent.com/maplibre/maplibre-gl-js/main/CHANGELOG.md | CHANGELOG.md (repository file; entries are named by their version heading) | 2026-11-12 |
| P4 | https://maplibre.org/maplibre-gl-js/docs/API/functions/setRTLTextPlugin/ | ~~setRTLTextPlugin()~~ - MapLibre GL JS | 2026-11-12 |
| P5 | https://maplibre.org/maplibre-gl-js/docs/API/type-aliases/MapOptions/ | MapOptions - MapLibre GL JS | 2026-11-12 |
| P6 | https://raw.githubusercontent.com/maplibre/maplibre-agent-skills/main/README.md | README.md (repository file of MapLibre Agent Skills) | 2026-11-12 |
| P7 | https://raw.githubusercontent.com/maplibre/maplibre-agent-skills/main/skills/maplibre-fonts-glyphs/SKILL.md | SKILL.md (repository file; a secondary source, its own text says to follow the migration guide where they differ) | 2026-11-12 |

### Runs

Setup, in an empty folder: three sub-folders `v6`, `v5` and `mb`, each with a `package.json` that holds `"private": true`, `"type": "module"` and exact dependencies (`v6`: `maplibre-gl` 6.17.0, `@deck.gl/core` 9.4.1, `@deck.gl/maplibre` 9.4.1; `v5`: `maplibre-gl` 5.24.1; `mb`: `@deck.gl/mapbox` 9.4.1), then `npm install --ignore-scripts --no-audit --no-fund` in each. Node 22 on Linux. A run's output is the last line printed (the standard error stream included).

| Id | Package and version | Date | Command | Output |
|---|---|---|---|---|
| R1 | maplibre-gl 6.17.0 | 2026-11-12 | `cd v6 && node -e 'try{require("maplibre-gl")}catch(e){console.log(e.code)}'` | ERR_PACKAGE_PATH_NOT_EXPORTED |
| R2 | maplibre-gl 6.17.0 | 2026-11-12 | `cd v6 && node --input-type=module -e 'import * as m from "maplibre-gl"; console.log("default" in m, typeof m.setWorkerUrl, typeof m.GPUInitializationError, m.getVersion())'` | false function function 6.17.0 |
| R3 | maplibre-gl 5.24.1 | 2026-11-12 | `cd v5 && node -e 'const m=require("maplibre-gl");console.log(typeof m.Map,typeof m.setRTLTextPlugin,typeof m.GPUInitializationError)'` | function function undefined |
| R4 | maplibre-gl 6.17.0 | 2026-11-12 | `cd v6 && node -e 'const t=require("fs").readFileSync("node_modules/maplibre-gl/dist/maplibre-gl.d.ts","utf8");console.log(t.includes("class Map$1 extends Camera"),t.includes("class Map$1 extends Evented"))'` | false true |
| R5 | maplibre-gl 5.24.1 | 2026-11-12 | `cd v5 && node -e 'const t=require("fs").readFileSync("node_modules/maplibre-gl/dist/maplibre-gl.d.ts","utf8");console.log(t.includes("class Map$1 extends Camera"),t.includes("class Map$1 extends Evented"))'` | true false |
| R6 | maplibre-gl 6.17.0 | 2026-11-12 | `cd v6 && node -e 'const t=require("fs").readFileSync("node_modules/maplibre-gl/dist/maplibre-gl.d.ts","utf8");const i=t.indexOf("declare function setRTLTextPlugin");console.log(t.slice(t.lastIndexOf("/**",i),i).includes("@deprecated"))'` | true |
| R7 | maplibre-gl 5.24.1 | 2026-11-12 | `cd v5 && node -e 'const t=require("fs").readFileSync("node_modules/maplibre-gl/dist/maplibre-gl.d.ts","utf8");const i=t.indexOf("declare function setRTLTextPlugin");console.log(t.slice(t.lastIndexOf("/**",i),i).includes("@deprecated"))'` | false |
| R8 | maplibre-gl 6.17.0 | 2026-11-12 | `cd v6 && node -e 'const f=require("fs");const t=f.readFileSync("node_modules/maplibre-gl/dist/maplibre-gl.d.ts","utf8");console.log(t.includes("declare function setWorkerUrl(value: string): void"),f.existsSync("node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs"))'` | true true |

### Idioms that changed

| Id | Earlier form | Current form | Kind | Source | Quote |
|---|---|---|---|---|---|
| I1 | `import maplibregl from 'maplibre-gl'` (default import) | `import * as maplibregl from 'maplibre-gl'`, or named imports such as `import {Map, setWorkerUrl} from 'maplibre-gl'` | READ | P1 | "If you used the default import (import maplibregl from 'maplibre-gl'), switch to either named imports or a namespace import" |
| I2 | `require('maplibre-gl')`, the UMD file and the separate CSP build | the ES module file `maplibre-gl.mjs` and its worker file `maplibre-gl-worker.mjs` | READ | P1 | "The UMD bundle, the separate CSP build, and the CommonJS (require('maplibre-gl')) entry from v5 are all gone. The bundle file is now maplibre-gl.mjs" |
| I3 | a `<script src>` element that loads the UMD file | a `<script type="module">` element that imports the module file (the product serves it from its own server, FE-05) | READ | P1 | `"If you load maplibre-gl via <script src>, switch to a module script"` |
| I4 | `setRTLTextPlugin(url, lazy)` called so that Arabic is drawn | no call; MapLibre draws Arabic and Hebrew labels itself from version 6.9.0 | READ | P3 | "draws Arabic and Hebrew labels correctly without loading a right-to-left text plugin" |
| I5 | code that reads or sets `map.transform` | the public API of Map | READ | P1 | "The internal map.transform property has been removed; Map now composes a Camera rather than extending it. Use Map's public API instead of reaching into transform." |
| I6 | a Map constructor that returns a map when WebGL2 is unavailable | the Map constructor throws `GPUInitializationError` when WebGL2 is unavailable | READ | P1 | "When WebGL2 is unavailable, the Map constructor throws a GPUInitializationError (check with instanceof GPUInitializationError, exported from maplibre-gl) instead of returning a map." |

### Statements

| Id | Statement | Kind | Source | Quote |
|---|---|---|---|---|
| S1 | The changelog entry of version 6.7.0 says the Map constructor throws GPUInitializationError when the WebGL2 context cannot be created; the entry of version 6.0.0 says the WebGL error can be listened for as an error event. | READ | P3 | "Throw GPUInitializationError from the Map constructor when the WebGL2 context cannot be created ... You can now listen to the webgl error via" |
| S2 | With maplibre-gl 6.17.0 installed, `require` of the package stops with the code ERR_PACKAGE_PATH_NOT_EXPORTED. | OBSERVED | R1 | - |
| S3 | With maplibre-gl 5.24.1 installed, `require` loads the package and it exposes Map and setRTLTextPlugin but not GPUInitializationError. | OBSERVED | R3 | - |
| S4 | The module namespace of maplibre-gl 6.17.0 has no default export; it exports setWorkerUrl and GPUInitializationError, and getVersion() returns 6.17.0. | OBSERVED | R2 | - |
| S5 | Under a bundler, each consuming application still makes one setWorkerUrl call. | READ | P1 | "each consumer still needs a one-time setWorkerUrl() call" |
| S6 | For Vite, the introduction page gets the worker address from an import with the ?worker&url query. | READ | P2 | "Use Vite's ?worker&url query to get a bundled, self-contained worker URL" |
| S7 | The typings of maplibre-gl 6.17.0 declare setWorkerUrl(value: string): void, and the file dist/maplibre-gl-worker.mjs exists in the package. | OBSERVED | R8 | - |
| S8 | In the typings of maplibre-gl 6.17.0 the Map class extends Evented and not Camera. | OBSERVED | R4 | - |
| S9 | In the typings of maplibre-gl 5.24.1 the Map class extends Camera. | OBSERVED | R5 | - |
| S10 | The API page of setRTLTextPlugin is marked deprecated, because MapLibre shapes Arabic itself. | READ | P4 | "MapLibre shapes Arabic and reorders bidirectional text itself" |
| S11 | The typings of maplibre-gl 6.17.0 carry a deprecated tag on setRTLTextPlugin. | OBSERVED | R6 | - |
| S12 | The typings of maplibre-gl 5.24.1 carry no deprecated tag on setRTLTextPlugin. | OBSERVED | R7 | - |
| S13 | The retreat to a 5.x release loses the built-in Arabic shaping (docs/10_FRONTEND.md section "Stack and pins"); the changelog places the shaping at version 6.9.0, the retreat has not been run, and Arabic shaping itself was not run here (no browser): not verified. | PACK | docs/10_FRONTEND.md section "Stack and pins" | - |
| S14 | Arabic labels need real glyphs; the skill file names serving the glyph files, or a local fallback that depends on the environment. | READ | P7 | "Arabic, Hebrew and other alphabetic scripts - need real glyphs ... serve its glyph PBFs ... which is environment-dependent" |
| S15 | Version 6.7.0 added map.setFontFaces and map.getFontFaces for the font-faces property of the style specification. | READ | P3 | "Support the style specification's font-faces property, with map.setFontFaces and map.getFontFaces" |
| S16 | A page that loads the library through the latest tag goes to a blank grey screen under version 6. | READ | P1 | "a page pinned to @latest goes to a blank gray screen" |
| S17 | A canvas larger than maxCanvasSize is not refused: the pixel ratio is lowered to fit. | READ | P5 | "the pixel ratio is lowered to fit and a warning is logged once" |
| S18 | The pixelRatio option defaults to the device pixel ratio. | READ | P5 | "Defaults to devicePixelRatio if not specified" |
| S19 | The project's agent-skills repository lists a skill for the version 6 migration (maplibre-v6-migration). | READ | P6 | "A v5 app breaks after upgrading to v6, or before pinning a v6 install" |
| S20 | The project's agent-skills repository lists a skill for hosting tiles without a tile server (maplibre-pmtiles-patterns). | READ | P6 | "Hosting tiles without a tile server" |
| S21 | The pack gives the light position of the MapLibre style specification as an azimuthal angle clockwise from north and a polar angle of 0 directly overhead (docs/11_DESIGN_DIRECTION.md section "The map"); no page of the style specification was read here: not verified. | PACK | docs/11_DESIGN_DIRECTION.md section "The map" | - |

### Slice S1 confirmation

| Field | Value | Rows in pins.toml | Pack source |
|---|---|---|---|
| exact pin, last 5.x release and right-to-left plugin for the retreat | not yet confirmed | maplibre-gl, @mapbox/mapbox-gl-rtl-text | docs/10_FRONTEND.md section "Stack and pins"; TASKS.md S1-T12 |
| spike result that chose between pin and retreat | not yet confirmed | maplibre-gl | docs/10_FRONTEND.md FE-03; TASKS.md S1-T12 |
| Arabic glyph route (glyph files or font-faces) | confirmed: MapLibre 6.17.0 shaped the five fixture names through local font-faces without the plugin; native reading still owed; PROGRESS.md heading "S1-T01 — Arabic glyph and label-order spike: task log" | - | docs/10_FRONTEND.md section "The basemap" |
| hexagons under labels | confirmed: one hexagon rendered below the first label layer; PROGRESS.md heading "S1-T01 — Arabic glyph and label-order spike: task log" | - | docs/10_FRONTEND.md FE-46 |
| pixel-ratio cap value | not yet confirmed | - | docs/10_FRONTEND.md section "Layouts, presenter mode and big-screen rules"; TASKS.md S1-T12 |
| watermark mechanism | not yet confirmed | - | docs/10_FRONTEND.md FE-53; TASKS.md S3-T09 |

## deck.gl 9.4

Used here for the data layers, interleaved with the basemap through `@deck.gl/maplibre` (docs/10_FRONTEND.md section "Stack and pins"). Series 9.4; the pins.toml rows are `@deck.gl/core`, `@deck.gl/layers`, `@deck.gl/geo-layers` and `@deck.gl/extensions`.

### Pages read

| Id | Address | Page title | Date read |
|---|---|---|---|
| P1 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |
| P2 | https://deck.gl/docs/developer-guide/performance | Performance Optimization - deck.gl | 2026-11-12 |
| P3 | https://deck.gl/docs/upgrade-guide | Upgrade Guide - deck.gl | 2026-11-12 |
| P4 | https://deck.gl/docs/developer-guide/webgpu | WebGPU - deck.gl | 2026-11-12 |
| P5 | https://deck.gl/docs/api-reference/extensions/fill-style-extension | FillStyleExtension - deck.gl | 2026-11-12 |
| P6 | https://deck.gl/docs/api-reference/core/lighting-effect | LightingEffect - deck.gl | 2026-11-12 |

### Runs

Same setup and folders as the Runs table of the MapLibre section.

| Id | Package and version | Date | Command | Output |
|---|---|---|---|---|
| R1 | @deck.gl/core 9.4.1 | 2026-11-12 | `cd v6 && node -e 'const p=JSON.parse(require("fs").readFileSync("node_modules/@deck.gl/core/package.json","utf8"));console.log("visgl:webgl-only" in p.exports["."])'` | true |

### Idioms that changed

| Id | Earlier form | Current form | Kind | Source | Quote |
|---|---|---|---|---|---|
| I1 | the controller option `touchRotate: true` | `multiTouchDrag: 'rotate'` (the 9.4 upgrade notes call the older option deprecated) | READ | P3 | "touchRotate: true is now treated as an alias for multiTouchDrag: 'rotate'" |

### Statements

| Id | Statement | Kind | Source | Quote |
|---|---|---|---|---|
| S1 | The release date of deck.gl 9.4 is 2026-09-05. | READ | P1 | "Release date: September 5, 2026" |
| S2 | The page expects 9.4 to be the final release of the version 9 series. | READ | P1 | "deck.gl v9.4 is expected to be the final release in the v9 series" |
| S3 | WebGPU support is described as experimental and not yet recommended for production. | READ | P1 | "WebGPU support remains experimental and is not yet recommended for production" |
| S4 | The WebGPU developer-guide page says that no current base map integration path supports WebGPU interleaving. | READ | P4 | "No current base map integration path supports WebGPU interleaving" |
| S5 | Applications that target WebGL2 only can resolve the export condition visgl:webgl-only, which selects builds without the WebGPU branches. | READ | P1 | "configure their bundler to resolve the custom export condition visgl:webgl-only" |
| S6 | The export map of @deck.gl/core 9.4.1 contains the condition visgl:webgl-only. | OBSERVED | R1 | - |
| S7 | When the data prop of a layer changes, the layer recalculates all of its GPU buffers. | READ | P2 | "When the data prop changes, the layer will recalculate all of its GPU buffers" |
| S8 | Whether FillStyleExtension and PathStyleExtension apply through the sublayers of H3HexagonLayer is not confirmed by the pack (docs/10_FRONTEND.md section "Map layers") and was not looked for here: not verified. | PACK | docs/10_FRONTEND.md section "Map layers" | - |
| S9 | The pack says the documented dash extension has no control for dash phase (docs/11_DESIGN_DIRECTION.md DES-67); the extension page was not searched for it here: not verified. | PACK | docs/11_DESIGN_DIRECTION.md DES-67 | - |
| S10 | The performance page says that on 2015 hardware with dual graphics cards most basic layers render at 60 FPS during pan and zoom up to about one million data items. | READ | P2 | "On 2015 ... with dual graphics cards ... renders fluidly at 60 FPS during pan and zoom operations up to about 1M (one million) data items" |
| S11 | The fillPatternSizeUnits property of FillStyleExtension takes the units meters, common or pixels. | READ | P5 | "fillPatternSizeUnits (string, optional) ... The units of the pattern size, one of 'meters', 'common' and 'pixels'" |
| S12 | The LightingEffect page calls the shadow effect experimental. | READ | P6 | "For rendering experimental shadow effect, _shadow prop of DirectionalLight must be set to true" |

### Slice S1 confirmation

| Field | Value | Rows in pins.toml | Pack source |
|---|---|---|---|
| exact pin and retreat pin of the four layer packages | not yet confirmed | @deck.gl/core, @deck.gl/layers, @deck.gl/geo-layers, @deck.gl/extensions | docs/10_FRONTEND.md section "Stack and pins"; TASKS.md S1-T12 |
| spike result that chose between pin and retreat | not yet confirmed | @deck.gl/core | docs/10_FRONTEND.md FE-03; TASKS.md S1-T12 |
| style extensions through H3HexagonLayer | not yet confirmed | - | docs/10_FRONTEND.md section "Map layers"; TASKS.md S6-T03 |
| method for moving dashes | not yet confirmed | - | docs/10_FRONTEND.md section "Open questions and assumptions"; TASKS.md S6-T03 |
| load trial of 110,000 hexagons and 50,000 particles | not yet confirmed | - | TASKS.md S1-T12 |
| no code path enables WebGPU | confirmed: the glyph spike used WebGL2 and enabled no WebGPU path; PROGRESS.md heading "S1-T01 — Arabic glyph and label-order spike: task log" | - | docs/10_FRONTEND.md FE-04 |

## deck.gl MapLibre module

The module `@deck.gl/maplibre` is used here through `MapLibreOverlay`, interleaved with the basemap (docs/10_FRONTEND.md section "Stack and pins"). The pins.toml rows are `@deck.gl/maplibre` and, for the retreat, `@deck.gl/mapbox`.

### Pages read

| Id | Address | Page title | Date read |
|---|---|---|---|
| P1 | https://deck.gl/docs/api-reference/maplibre/overview | MapLibreOverlay - deck.gl | 2026-11-12 |
| P2 | https://deck.gl/docs/developer-guide/base-maps/using-with-maplibre | Using with MapLibre - deck.gl | 2026-11-12 |
| P3 | https://deck.gl/docs/whats-new | What's New - deck.gl | 2026-11-12 |

### Runs

Same setup and folders as the Runs table of the MapLibre section.

| Id | Package and version | Date | Command | Output |
|---|---|---|---|---|
| R1 | @deck.gl/maplibre 9.4.1 | 2026-11-12 | `cd v6 && node --input-type=module -e 'import * as m from "@deck.gl/maplibre"; console.log(Object.keys(m).join(","))'` | MapLibreOverlay |
| R2 | @deck.gl/mapbox 9.4.1 | 2026-11-12 | `cd mb && node --input-type=module -e 'import * as m from "@deck.gl/mapbox"; console.log(Object.keys(m).join(","))'` | MapboxOverlay |
| R3 | @deck.gl/maplibre 9.4.1 | 2026-11-12 | `cd v6 && node -e 'const p=JSON.parse(require("fs").readFileSync("node_modules/@deck.gl/maplibre/package.json","utf8")).peerDependencies["maplibre-gl"];console.log(p.includes("^5.0.0"),p.includes("^6.0.0"))'` | true true |

### Idioms that changed

| Id | Earlier form | Current form | Kind | Source | Quote |
|---|---|---|---|---|---|
| I1 | `MapboxOverlay` from the former `@deck.gl/mapbox` module, which the pack names as the old idiom (docs/10_FRONTEND.md section "Stack and pins") | `MapLibreOverlay` from `@deck.gl/maplibre` (the older export still exists: S3) | READ | P3 | "New @deck.gl/maplibre module is forked from the former @deck.gl/mapbox module. It provides support for overlaid and interleaved rendering with MapLibre GL JS v4, v5, and the recently released v6." |

### Statements

| Id | Statement | Kind | Source | Quote |
|---|---|---|---|---|
| S1 | The page says applications on MapLibre version 4.5.1, 5 and 6 should use MapLibreOverlay from @deck.gl/maplibre. | READ | P2 | "MapLibre GL JS v4.5.1, v5, and v6 applications should use MapLibreOverlay from @deck.gl/maplibre" |
| S2 | @deck.gl/maplibre 9.4.1 exports one name, MapLibreOverlay. | OBSERVED | R1 | - |
| S3 | @deck.gl/mapbox 9.4.1 still exports MapboxOverlay. | OBSERVED | R2 | - |
| S4 | The peer range of @deck.gl/maplibre 9.4.1 for maplibre-gl includes the 5 and 6 series. | OBSERVED | R3 | - |
| S5 | The interleaved option inserts deck.gl layers into the MapLibre style layer stack, shares its WebGL2 context, and is false by default. | READ | P1 | "may be inserted into its style layer stack. The default is false." |
| S6 | In interleaved mode, a beforeId property on a deck.gl layer renders it before a MapLibre style layer. | READ | P1 | "add a beforeId property to a deck.gl layer to render it before a MapLibre style layer" |
| S7 | Only one interleaved overlay may be attached to a map. | READ | P1 | "One interleaved overlay may be attached to a map." |
| S8 | MapLibre creates its WebGL context with antialias set to false by default, and in interleaved mode layers whose edges depend on MSAA, such as PathLayer, render with hard, aliased edges. | READ | P1 | "render with hard, aliased edges" |
| S9 | The props useDevicePixels and device are ignored in interleaved mode, because MapLibre owns the shared canvas. | READ | P1 | "useDevicePixels and device are ignored in interleaved mode" |
| S10 | Globe integration uses the experimental GlobeView of deck.gl. | READ | P1 | "Globe integration uses deck.gl's experimental GlobeView" |
| S11 | Interleaved mode needs WebGL2. | READ | P1 | "Interleaved mode only works when WebGL2 is available" |
| S12 | The retreat uses @deck.gl/mapbox in place of this module (docs/10_FRONTEND.md section "Stack and pins"); it has not been installed or run for this retreat here: not verified. | PACK | docs/10_FRONTEND.md section "Stack and pins" | - |

### Slice S1 confirmation

| Field | Value | Rows in pins.toml | Pack source |
|---|---|---|---|
| exact pin and the retreat that replaces the module | not yet confirmed | @deck.gl/maplibre, @deck.gl/mapbox | docs/10_FRONTEND.md section "Stack and pins"; TASKS.md S1-T12 |
| interleaved mode with the pinned MapLibre on WebGL2 | confirmed: one MapLibreOverlay of deck.gl 9.4.1 interleaved with MapLibre 6.17.0 on WebGL2; PROGRESS.md heading "S1-T01 — Arabic glyph and label-order spike: task log" | - | docs/10_FRONTEND.md FE-04 |
| layers under labels through beforeId | confirmed: the overlay layer inserted before the first label; insertion before style load appeared after first idle; PROGRESS.md heading "S1-T01 — Arabic glyph and label-order spike: task log" | - | docs/10_FRONTEND.md section "Map layers" |

## Confirmations assigned to this task

The owner decided on 2026-11-11 that the lead assigns each slice S0 requirement that no task owned to the nearest task; the lead assigned DES-25 and DES-45 to S0-T13.

### Pages read

| Id | Address | Page title | Date read |
|---|---|---|---|
| P1 | https://raw.githubusercontent.com/carbon-design-system/carbon/main/README.md | README.md (repository file of the Carbon Design System) | 2026-11-12 |
| P2 | https://raw.githubusercontent.com/carbon-design-system/carbon/main/LICENSE | LICENSE (repository file of the Carbon Design System) | 2026-11-12 |

### Runs

Setup, in an empty folder: three sub-folders `f1`, `f2` and `ic`; in each, `npm pack` of one package at its exact version writes the tarball into the folder (`@fontsource/ibm-plex-sans` 5.3.0 in `f1`, `@fontsource/ibm-plex-sans-arabic` 5.3.0 in `f2`, `@carbon/icons` 11.92.0 in `ic`). Node 22 and Python 3.14 on Linux. A run's output is the last line printed. The font runs count the files of the normal style at the weights 400, 500 and 600; they say nothing about the glyphs in the files.

| Id | Package and version | Date | Command | Output |
|---|---|---|---|---|
| R1 | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | `cd f1 && python3 -I -c "import re,tarfile;f=[n for n in tarfile.open('fontsource-ibm-plex-sans-5.3.0.tgz').getnames() if re.search(r'/files/.*-[456]00-normal\.woff2?\Z',n)];print(len(f),sorted({re.search(r'/ibm-plex-sans-(.*)-[456]00-',n).group(1) for n in f}),sorted({re.search(r'-([456]00)-',n).group(1) for n in f}),sorted({n.rsplit('.',1)[1] for n in f}))"` | 36 ['cyrillic', 'cyrillic-ext', 'greek', 'latin', 'latin-ext', 'vietnamese'] ['400', '500', '600'] ['woff', 'woff2'] |
| R2 | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | `cd f2 && python3 -I -c "import re,tarfile;f=[n for n in tarfile.open('fontsource-ibm-plex-sans-arabic-5.3.0.tgz').getnames() if re.search(r'/files/.*-[456]00-normal\.woff2?\Z',n)];print(len(f),sorted({re.search(r'/ibm-plex-sans-arabic-(.*)-[456]00-',n).group(1) for n in f}),sorted({re.search(r'-([456]00)-',n).group(1) for n in f}),sorted({n.rsplit('.',1)[1] for n in f}))"` | 24 ['arabic', 'cyrillic-ext', 'latin', 'latin-ext'] ['400', '500', '600'] ['woff', 'woff2'] |
| R3 | @carbon/icons 11.92.0 | 2026-11-12 | `cd ic && tar xzf carbon-icons-11.92.0.tgz package/package.json package/LICENSE && python3 -I -c "import json;p=json.load(open('package/package.json'));print(p['name'],p['version'],p['license'],' '.join(open('package/LICENSE').read().split()[:6]))"` | @carbon/icons 11.92.0 Apache-2.0 Apache License Version 2.0, January 2004 |

### Font weights

| Id | Family | Subset | Weight | Files found in the package | Kind | Package and version | Date | Source |
|---|---|---|---|---|---|---|---|---|
| F1 | IBM Plex Sans | cyrillic | 400 | ibm-plex-sans-cyrillic-400-normal.woff2, ibm-plex-sans-cyrillic-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F2 | IBM Plex Sans | cyrillic | 500 | ibm-plex-sans-cyrillic-500-normal.woff2, ibm-plex-sans-cyrillic-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F3 | IBM Plex Sans | cyrillic | 600 | ibm-plex-sans-cyrillic-600-normal.woff2, ibm-plex-sans-cyrillic-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F4 | IBM Plex Sans | cyrillic-ext | 400 | ibm-plex-sans-cyrillic-ext-400-normal.woff2, ibm-plex-sans-cyrillic-ext-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F5 | IBM Plex Sans | cyrillic-ext | 500 | ibm-plex-sans-cyrillic-ext-500-normal.woff2, ibm-plex-sans-cyrillic-ext-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F6 | IBM Plex Sans | cyrillic-ext | 600 | ibm-plex-sans-cyrillic-ext-600-normal.woff2, ibm-plex-sans-cyrillic-ext-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F7 | IBM Plex Sans | greek | 400 | ibm-plex-sans-greek-400-normal.woff2, ibm-plex-sans-greek-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F8 | IBM Plex Sans | greek | 500 | ibm-plex-sans-greek-500-normal.woff2, ibm-plex-sans-greek-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F9 | IBM Plex Sans | greek | 600 | ibm-plex-sans-greek-600-normal.woff2, ibm-plex-sans-greek-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F10 | IBM Plex Sans | latin | 400 | ibm-plex-sans-latin-400-normal.woff2, ibm-plex-sans-latin-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F11 | IBM Plex Sans | latin | 500 | ibm-plex-sans-latin-500-normal.woff2, ibm-plex-sans-latin-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F12 | IBM Plex Sans | latin | 600 | ibm-plex-sans-latin-600-normal.woff2, ibm-plex-sans-latin-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F13 | IBM Plex Sans | latin-ext | 400 | ibm-plex-sans-latin-ext-400-normal.woff2, ibm-plex-sans-latin-ext-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F14 | IBM Plex Sans | latin-ext | 500 | ibm-plex-sans-latin-ext-500-normal.woff2, ibm-plex-sans-latin-ext-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F15 | IBM Plex Sans | latin-ext | 600 | ibm-plex-sans-latin-ext-600-normal.woff2, ibm-plex-sans-latin-ext-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F16 | IBM Plex Sans | vietnamese | 400 | ibm-plex-sans-vietnamese-400-normal.woff2, ibm-plex-sans-vietnamese-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F17 | IBM Plex Sans | vietnamese | 500 | ibm-plex-sans-vietnamese-500-normal.woff2, ibm-plex-sans-vietnamese-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F18 | IBM Plex Sans | vietnamese | 600 | ibm-plex-sans-vietnamese-600-normal.woff2, ibm-plex-sans-vietnamese-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans 5.3.0 | 2026-11-12 | R1 |
| F19 | IBM Plex Sans Arabic | arabic | 400 | ibm-plex-sans-arabic-arabic-400-normal.woff2, ibm-plex-sans-arabic-arabic-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R2 |
| F20 | IBM Plex Sans Arabic | arabic | 500 | ibm-plex-sans-arabic-arabic-500-normal.woff2, ibm-plex-sans-arabic-arabic-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R2 |
| F21 | IBM Plex Sans Arabic | arabic | 600 | ibm-plex-sans-arabic-arabic-600-normal.woff2, ibm-plex-sans-arabic-arabic-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R2 |
| F22 | IBM Plex Sans Arabic | cyrillic-ext | 400 | ibm-plex-sans-arabic-cyrillic-ext-400-normal.woff2, ibm-plex-sans-arabic-cyrillic-ext-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R2 |
| F23 | IBM Plex Sans Arabic | cyrillic-ext | 500 | ibm-plex-sans-arabic-cyrillic-ext-500-normal.woff2, ibm-plex-sans-arabic-cyrillic-ext-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R2 |
| F24 | IBM Plex Sans Arabic | cyrillic-ext | 600 | ibm-plex-sans-arabic-cyrillic-ext-600-normal.woff2, ibm-plex-sans-arabic-cyrillic-ext-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R2 |
| F25 | IBM Plex Sans Arabic | latin | 400 | ibm-plex-sans-arabic-latin-400-normal.woff2, ibm-plex-sans-arabic-latin-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R2 |
| F26 | IBM Plex Sans Arabic | latin | 500 | ibm-plex-sans-arabic-latin-500-normal.woff2, ibm-plex-sans-arabic-latin-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R2 |
| F27 | IBM Plex Sans Arabic | latin | 600 | ibm-plex-sans-arabic-latin-600-normal.woff2, ibm-plex-sans-arabic-latin-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R2 |
| F28 | IBM Plex Sans Arabic | latin-ext | 400 | ibm-plex-sans-arabic-latin-ext-400-normal.woff2, ibm-plex-sans-arabic-latin-ext-400-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R2 |
| F29 | IBM Plex Sans Arabic | latin-ext | 500 | ibm-plex-sans-arabic-latin-ext-500-normal.woff2, ibm-plex-sans-arabic-latin-ext-500-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R2 |
| F30 | IBM Plex Sans Arabic | latin-ext | 600 | ibm-plex-sans-arabic-latin-ext-600-normal.woff2, ibm-plex-sans-arabic-latin-ext-600-normal.woff | OBSERVED | @fontsource/ibm-plex-sans-arabic 5.3.0 | 2026-11-12 | R2 |

### Icon package licence

| Id | Package and version | Licence identifier | Licence file | Kind | Source | Quote | Date |
|---|---|---|---|---|---|---|---|
| C1 | @carbon/icons 11.92.0 | Apache-2.0 | LICENSE in the package, which begins with the words Apache License Version 2.0, January 2004 | OBSERVED | R3 | - | 2026-11-12 |
| C2 | @carbon/icons | Apache 2.0 License | LICENSE in the repository root, linked by the README | READ | P1 | "@carbon/icons ... Icon assets and framework packages ... Licensed under the ... Apache 2.0 License" | 2026-11-12 |
| C3 | - | Apache License Version 2.0 | LICENSE in the repository root | READ | P2 | "Apache License ... Version 2.0, January 2004" | 2026-11-12 |

## Pack statements and where each stands

| Pack claim | Pack source | Where |
|---|---|---|
| Version 6 is ESM-only | docs/10_FRONTEND.md section "Stack and pins" | MapLibre GL JS 6 I2 |
| Version 6 is WebGL2-only | docs/10_FRONTEND.md section "Stack and pins" | MapLibre GL JS 6 I6 |
| Version 6 removed map.transform | docs/10_FRONTEND.md section "Stack and pins" | MapLibre GL JS 6 I5 |
| Version 6 needs one worker-URL call under a bundler | docs/10_FRONTEND.md section "Stack and pins" | MapLibre GL JS 6 S5 |
| Version 6 throws an initialisation error when WebGL2 is missing | docs/10_FRONTEND.md section "Stack and pins" | MapLibre GL JS 6 S1 |
| Since 6.9.0 MapLibre shapes Arabic itself, which deprecates setRTLTextPlugin | docs/10_FRONTEND.md section "Stack and pins" | MapLibre GL JS 6 I4; MapLibre GL JS 6 S10 |
| The font-faces calls setFontFaces exist since 6.7 | docs/10_FRONTEND.md section "The basemap" | MapLibre GL JS 6 S15 |
| Coding agents default to version 4 and 5 idioms | docs/10_FRONTEND.md section "Stack and pins" | MapLibre GL JS 6 I1 |
| pixelRatio and maxCanvasSize lower the ratio to fit | docs/10_FRONTEND.md section "Layouts, presenter mode and big-screen rules" | MapLibre GL JS 6 S17 |
| The light position has an azimuthal angle clockwise from north and a polar angle of 0 overhead | docs/11_DESIGN_DIRECTION.md section "The map" | MapLibre GL JS 6 S21 |
| The default font set may not cover Arabic, so real Arabic glyphs are needed | docs/10_FRONTEND.md section "The basemap" | MapLibre GL JS 6 S14 |
| The retreat to a 5.x release loses built-in Arabic shaping | docs/10_FRONTEND.md section "Stack and pins" | MapLibre GL JS 6 S13 |
| WebGPU is not production-ready | docs/10_FRONTEND.md section "Stack and pins" row "WebGPU in deck.gl" | deck.gl 9.4 S3 |
| WebGPU cannot interleave with the basemap | docs/10_FRONTEND.md section "Stack and pins" row "WebGPU in deck.gl" | deck.gl 9.4 S4 |
| Basic layers render at 60 frames per second up to about one million items | docs/decisions/0006-fixed-grid-and-pin-based-areas.md section "Evidence"; docs/10_FRONTEND.md section "Performance budgets" | deck.gl 9.4 S10 |
| Changing the data prop rebuilds every buffer | docs/10_FRONTEND.md section "State management" | deck.gl 9.4 S7 |
| Whether the style extensions apply through the sublayers of H3HexagonLayer is not confirmed | docs/10_FRONTEND.md section "Map layers" | deck.gl 9.4 S8 |
| The documented dash extension has no control for dash phase | docs/11_DESIGN_DIRECTION.md DES-67 | deck.gl 9.4 S9 |
| The shadow effect of the overlay library is documented as experimental | docs/11_DESIGN_DIRECTION.md DES-146 | deck.gl 9.4 S12 |
| FillStyleExtension gives pixel-sized textures | docs/11_DESIGN_DIRECTION.md section "Sources" | deck.gl 9.4 S11 |
| The pixel-ratio cap applies to deck.gl through useDevicePixels set to a number | docs/10_FRONTEND.md section "Layouts, presenter mode and big-screen rules" | deck.gl MapLibre module S9 |
| The module is used interleaved through MapLibreOverlay and MapboxOverlay is the old idiom | docs/10_FRONTEND.md section "Stack and pins"; docs/10_FRONTEND.md section "Stack and pins" | deck.gl MapLibre module I1; deck.gl MapLibre module S5 |
| GlobeView is experimental | docs/10_FRONTEND.md section "Stack and pins" row "deck.gl `GlobeView`" | deck.gl MapLibre module S10 |
| Data layers sit beneath the label layers through the interleaved beforeId placement | docs/10_FRONTEND.md section "Map layers" | deck.gl MapLibre module S6 |
| The retreat uses @deck.gl/mapbox in place of the module | docs/10_FRONTEND.md section "Stack and pins" | deck.gl MapLibre module S12 |
