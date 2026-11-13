# Performance spike

A development page that draws 110,000 synthetic hexagons and 50,000 synthetic particles on an invented extent. The extent is centred on longitude 0.02 and latitude 0.02. It has no place name and no basemap of a real place. The seed is 1. Hexagons are H3 resolution 8, and the first 110,000 cells of a disk are kept. Nothing here is a feature screen.

## Strings that wait for the owner's native reading

- عرض اصطناعي. امتداد مخترع. بلا اسم مكان. `pending native review`

The two notices live in `notices.json`. The page reads them from that file. A model does not change the mark to approved.

The map canvas is 1920 by 1080 CSS pixels. Its pixel ratio is capped at 1 device pixel per CSS pixel. That cap is an assumption: it is held constant, recorded on the trace, and never searched. Text on the page stays at the display's own pixel ratio.

## Commands

From the repository root, with Node 22 first on `PATH`. The headless shell is the one the glyph spike already fetched. This spike does not install a browser.

- `npm --prefix web run spike:glyphs:install-browser` is the prerequisite when the shell is missing. It needs the network once. A missing browser fails the suite and names this command.
- `npm --prefix web run test:spike:performance` runs the Node tests. The browser tests build the page into a temporary folder, assert the two counts and the recorder contract, and do not assert a frame rate.
- `npm --prefix web run spike:performance:serve` starts a loopback server and prints one address. Open that address in Windows Chrome or Edge on the host. When the page does not refuse the environment, it runs a 30-second orbit itself, shows the result, and posts the trace. The server writes the file under `web/spikes/performance/evidence/`.
- `npm --prefix web run spike:performance:verify-evidence` checks a committed native trace. Until the owner commits one, it fails with `missing-native-trace` and writes nothing.

`./eii test` runs these Node tests with the other web checks. Those runs use a short orbit. They report counts. They do not decide the frame-rate gate. The native frame-rate gate is pending.

## What the owner records

The serve command prints a line that ends in `/en/_perf`. Open that exact address in Windows Chrome or Edge, outside WSL. Leave the page open until it shows a path. That path is a JSON file under `web/spikes/performance/evidence/`. The page also says `native frame-rate gate pending`.

The evidence command also needs `web/spikes/performance/evidence/native-capture.md`, committed with the trace. Its lines are `role`, `date`, `host`, `browser`, `trace` and `sha256`. `role` is `owner`, `host` is `windows-native`, `browser` is `chrome` or `edge`, `date` is `YYYY-MM-DD`, `trace` is the repository path of the JSON file, and `sha256` is `sha256:` plus the file's digest. Both files must be committed and unchanged. This spike does not create that capture file and does not invent a trace.

## Trace

The contract name is `eii.performance-trace`, version 1, provenance Synthetic. The layer set name is `hexagons-particles`. A gate profile runs for 30 seconds. A smoke profile runs for 400 milliseconds and is refused by the name `smoke-profile`. The share is the unrounded count of frame intervals strictly under 16.7 milliseconds, divided by the interval count. The gate needs that share to be at least 0.95 on a native Windows trace. Percentiles and the share come from `summariseFrames` in `trace.mjs`. The page does not compute them itself.

The server accepts a well-formed trace and stores it even when the gate later refuses it. The evidence command is what qualifies the stored file. A test server cannot write the native evidence directory. The serve command's server stores a posted trace, and the test `the development server stores a posted smoke trace from the page origin` in `tests/vite-server.node-test.mjs` proves it.

## Plants

The browser suite loads the page with one plant at a time: omit one hexagon, hide the hexagon layer, omit one particle, hide the particle layer, freeze the clock, post no timestamps, blank the renderer, add an unknown field, ignore the cap, rename the profile, request a remote image, and skip WebGL2. The blank-renderer plant posts the gate profile after a short orbit so the refusal name is `missing-renderer`. The remote image is `https://assets.invalid/spike.png` and the content security policy blocks it. The gate profile also plants a software renderer, a remote renderer, a capped frame interval on the empty canvas, and a slow full scene whose empty canvas is at 60.

## Renderer and early refusals

As soon as the page has a WebGL2 context, and before the orbit starts, it shows one line with the unmasked renderer: the string `readUnmaskedRenderer` returns. When that string is empty, the line says `none is available`. The line is reference text, on both the English and the Arabic page.

The gate profile refuses on screen at once, does not run the orbit, and posts nothing, when the renderer is missing, a software renderer, the Windows software driver, or WARP (`refused: missing-renderer` or `refused: software-renderer`), or when the renderer names a remote display adapter as its own word (`refused: remote-renderer`). Before the map and its layers load, the same profile counts frames on the empty canvas for about two seconds. If that empty canvas does not reach 60 frames a second, the page shows `refused: capped-frame-rate` with the measured frames a second. It does not load the layers and it posts nothing. If the empty canvas reaches 60 and the full scene does not, the orbit runs and the trace is stored, and the gate judges that trace. A slow full scene is not refused as a bad environment.

If the page refuses, sit at the computer, not through Remote Desktop. Use Chrome at 100% zoom with Energy Saver off.
