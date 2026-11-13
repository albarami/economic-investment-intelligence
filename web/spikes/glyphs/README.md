# Glyph spike

A synthetic page that draws invented geometry and invented names with MapLibre GL JS 6.17.0 and one interleaved deck.gl polygon layer. It is not a feature screen and it does not load a real basemap or a tile.

The five Arabic names are منطقة الاختبار ألف, حي المحاكاة باء, مدينة المثال جيم, قرية العرض دال and شارع التجربة هاء. Each string in `names.json` is marked `pending native review`. The same mark is in `evidence/visual-review.md`. A model does not change that mark to approved.

IBM Plex Sans and IBM Plex Sans Arabic are the chrome faces. Noto Sans and Noto Sans Arabic are the map faces, declared with `font-faces` and loaded from the npm packages. The four SIL licence texts are copied into `public/licences/` and served by the spike.

## Commands

From the repository root, with Node 22 first on `PATH`:

- `npm --prefix web run spike:glyphs:install-browser` installs the headless shell the tests launch into the uncommitted folder `data/tools/playwright/`; in the CI environment it also installs the system libraries the shell needs, and on any other machine it changes nothing outside the repository. It needs the network once.
- `npm --prefix web run spike:glyphs:build` writes `web/spikes/glyphs/dist/` for a developer. The suite and the recorder do not read that folder.
- `npm --prefix web run test:spike:glyphs` builds the page into a temporary folder, serves that folder and runs the browser tests. The pixel comparison runs in the hosted job's own step, or a direct run of the command with `CI=true`, and does not run in `./eii test`, anywhere. A missing browser fails and names the install command.
- `npm --prefix web run spike:glyphs:record` builds the same way and writes the three screenshots, `run.json`, `network.json` and `asset-manifest.json` under `evidence/`.
- `npm --prefix web run spike:glyphs:verify-evidence` checks that record against the pending review.
- `npm --prefix web run spike:glyphs:capture` runs the suite's screenshot captures into `data/glyph-captures/` only when `CI` is `true`. The pixel comparison runs in the hosted job's own step, or a direct run of the command with `CI=true`, and does not run in `./eii test`, anywhere; that folder is not the folder the comparison reads.

`./eii test` runs the spike's Node tests with the other web checks. The pixel comparison runs in the hosted job's own step, or a direct run of the command with `CI=true`, and does not run in `./eii test`, anywhere. The hosted `tests` job installs the browser, captures the three screenshots, uploads `data/glyph-captures/`, and compares in its own step before `./eii test`; the pixel comparison runs in that step, or a direct run of the command with `CI=true`, and does not run in `./eii test`, anywhere, and a missing or differing baseline fails that step and names the file.

The page says it is a synthetic fixture. Every request is same-origin, `data:` or `blob:`. A planted remote font is blocked.
