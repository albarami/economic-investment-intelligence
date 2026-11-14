/** Runs the real page coordinator against deterministic DOM/scene doubles.
 * Rendering remains covered by the full-count browser tests.
 */
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
import * as config from '../config.mjs';
import * as roads from '../roads.mjs';
import { createPlayback } from '../road-playback.ts';
import * as traceMethods from '../trace.mjs';
const { validateGate } = traceMethods;
import data from '../road-data.json' with { type: 'json' };
import notices from '../notices.json' with { type: 'json' };

export async function pageHarness(
  query = '',
  reduced = false,
  arabic = false,
  options = {},
) {
  const handlers = { window: {}, document: {} };
  const sent = {
    opens: [],
    headers: [],
    images: [],
    probes: [],
    lostContexts: 0,
  };
  class Element {
    hidden = true;
    textContent = '';
    style = {};
    attributes = {};
    onclick = null;
    append(canvas) {
      sent.probes.push(canvas);
    }
    removeAttribute(key) {
      delete this.attributes[key];
      if (key === 'hidden') this.hidden = false;
    }
    setAttribute(key, value) {
      this.attributes[key] = value;
    }
  }
  const nodes = new Map(
    [
      '#notice',
      '#renderer',
      '#road-mark',
      '#road-legend',
      '#pause-motion',
      '#map',
      '#hour-current',
      '#hour-next',
      '#result',
      '#map-failure',
    ].map((id) => [id, new Element()]),
  );
  const document = {
    querySelector: (id) =>
      options.missingMap && id === '#map' ? null : nodes.get(id),
    createElement: (tag) => {
      if (tag !== 'canvas') throw new Error('unexpected element');
      return {
        width: 0,
        height: 0,
        removed: false,
        getContext(name) {
          if (name !== 'webgl2') throw new Error('wrong context');
          return options.noContext
            ? null
            : {
                getExtension(extension) {
                  return extension === 'WEBGL_lose_context'
                    ? {
                        loseContext() {
                          sent.lostContexts++;
                        },
                      }
                    : { UNMASKED_RENDERER_WEBGL: 7 };
                },
                getParameter: () =>
                  options.renderer ?? 'Synthetic hardware adapter',
              };
        },
        remove() {
          this.removed = true;
        },
      };
    },
    documentElement: {},
    addEventListener(name, callback) {
      handlers.document[name] = callback;
    },
    hidden: false,
  };
  const media = {
    matches: reduced,
    addEventListener(type, handler) {
      this.change = handler;
    },
  };
  const window = {
    location: {
      search:
        options.search ??
        `?profile=smoke&layers=hexagons-particles-roads${query}`,
      pathname: arabic ? '/ar/_perf' : '/en/_perf',
    },
    matchMedia: () => media,
    devicePixelRatio: 1,
    innerWidth: config.WALL_CSS_WIDTH,
    innerHeight: config.WALL_CSS_HEIGHT,
    addEventListener(name, callback) {
      handlers.window[name] = callback;
    },
  };
  const callbacks = [];
  const requests = [];
  let mountInput;
  let orbit;
  let clock = 0;
  let bearing = 0;
  const particles = options.particles ?? [{ position: [1, 2] }];
  const scene = {
    canvas: {
      clientWidth: config.WALL_CSS_WIDTH,
      clientHeight: config.WALL_CSS_HEIGHT,
      width: config.WALL_CSS_WIDTH,
      height: config.WALL_CSS_HEIGHT,
    },
    hexagonInstances: config.HEXAGON_COUNT,
    particleInstances: config.PARTICLE_COUNT,
    roadInstances: config.LAYER_SETS['hexagons-particles-roads'].roads,
    roadDashEnabled: true,
    bearing: () => bearing,
    renderer: () => options.renderer ?? 'Synthetic hardware adapter',
    sample: () => ({ hex: true, particle: true, road: true }),
    onContextLost(callback) {
      handlers.contextLost = callback;
    },
    step(elapsed, nextBearing, freeze) {
      bearing = nextBearing;
      if (!freeze && particles[0]) particles[0].position[0] = elapsed + 2;
    },
    roadSnapshot() {
      const state = mountInput.playback.state;
      return {
        hour: data.hours[state.index],
        nextHour: data.hours[state.next],
        blend: state.blend,
        bands: [],
        nextBands: [],
        trigger: data.hours[state.index],
        stableData: true,
      };
    },
  };
  Object.assign(scene, options.scene ?? {});
  class Request {
    open(...args) {
      sent.opens.push(args);
    }
    setRequestHeader(...args) {
      sent.headers.push(args);
    }
    send(payload) {
      const trace = JSON.parse(payload);
      requests.push(trace);
      this.responseText =
        options.responseText ??
        JSON.stringify({
          ok: true,
          path: 'synthetic-trace.json',
          qualification: validateGate(trace, trace.layerSet, null).failure,
        });
      if (options.networkError) this.onerror();
      else this.onload();
    }
  }
  const modules = {
    './config.mjs': config,
    './roads.mjs': roads,
    './road-playback': { createPlayback },
    './road-data.json': { default: data },
    './notices.json': { default: notices },
    './geometry.mjs': {
      generateHexagons: () => ['synthetic-cell'],
      generateParticles: () => particles,
    },
    './layers': {
      mountScene: async (input) => {
        mountInput = input;
        if (options.mountError) throw options.mountError;
        return scene;
      },
      webglFailure: (error) => error.message,
    },
    './recorder': {
      recordOrbit: (input) => {
        orbit = input;
      },
    },
    './trace.mjs': traceMethods,
  };
  const source = fs.readFileSync(
    new URL('../main.ts', import.meta.url),
    'utf8',
  );
  const exported = {};
  const compiled = ts.transpileModule(
    source +
      '\nexport {postTrace,readProfile,environmentGate,plantedRenderer,rendererLine,refuse,showRenderer,probeContext,plantedTimestamps,liveTimestamps,emptyCanvasTimestamps,finish,spike};',
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        esModuleInterop: false,
        target: ts.ScriptTarget.ES2022,
      },
    },
  ).outputText;
  vm.runInNewContext(compiled, {
    exports: exported,
    require: (name) => modules[name] ?? {},
    window,
    document,
    HTMLElement: Element,
    XMLHttpRequest: Request,
    URLSearchParams,
    navigator: { userAgent: 'Synthetic headless test' },
    performance: { now: () => clock },
    requestAnimationFrame: (callback) => callbacks.push(callback),
    Image: class {
      set src(value) {
        sent.images.push(value);
      }
    },
    console,
    process,
  });
  await new Promise((resolve) => setImmediate(resolve));
  // S1-T13 displays the renderer for one frame before registering the orbit.
  if (!options.deferFrames) {
    for (let index = 0; index < 200 && callbacks.length && !orbit; index++) {
      clock = index * 16;
      callbacks.shift()(clock);
      await new Promise((resolve) => setImmediate(resolve));
    }
  }
  return {
    setClock(time) {
      clock = time;
    },
    window,
    document,
    handlers,
    sent,
    api: exported,
    scene,
    nodes,
    media,
    requests,
    get orbit() {
      return orbit;
    },
    get input() {
      return mountInput;
    },
    frame(time) {
      clock = time;
      orbit.onFrame(time);
    },
    async finish(timestamps) {
      orbit.onDone(timestamps);
      await new Promise((resolve) => setImmediate(resolve));
    },
    tick(time) {
      clock = time;
      callbacks.shift()(time);
    },
  };
}
