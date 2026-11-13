import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
import * as config from '../config.mjs';
import * as roads from '../roads.mjs';
import { roadLayer } from '../road-layer.ts';
import { createPlayback } from '../road-playback.ts';
import data from '../road-data.json' with { type: 'json' };

async function mountFixture(enabled, plant = '', pixel, options = {}) {
  const observed = {
    mapOptions: null,
    turns: [],
    pixels: [],
    events: {},
    workers: [],
    motion: [],
    removed: [],
  };
  class GPUError extends Error {}
  let held = [];
  const canvas = {
    width: 1920,
    height: 1080,
    getContext: (name) => {
      assert.equal(name, 'webgl2');
      return pixel
        ? {
            readPixels(_x, _y, _width, _height, _format, _type, target) {
              observed.pixels.push([_x, _y, _width, _height]);
              target.set(typeof pixel === 'function' ? pixel(_x, _y) : pixel);
            },
          }
        : null;
    },
    addEventListener(name, callback) {
      observed.events[name] = callback;
    },
  };
  class MapDouble {
    constructor(props) {
      observed.mapOptions = props;
    }
    addControl(overlay) {
      held = overlay.props.layers;
    }
    once(event, callback) {
      if (event === 'idle' && !options.fail) queueMicrotask(callback);
      if (event === 'error' && options.fail)
        queueMicrotask(() => callback({ error: options.fail }));
    }
    off(name) {
      observed.removed.push(name);
    }
    getCanvas() {
      return canvas;
    }
    getBearing() {
      return 13;
    }
    jumpTo(props) {
      observed.turns.push(props);
    }
  }
  class OverlayDouble {
    constructor(props) {
      this.props = props;
      assert.equal(props.interleaved, true);
    }
    setProps(props) {
      held = props.layers;
    }
  }
  class LayerDouble {
    constructor(props) {
      this.props = props;
    }
    getNumInstances() {
      return this.props.data.length;
    }
    getSubLayers() {
      return options.sublayers
        ? options.sublayers.map((count) => ({ getNumInstances: () => count }))
        : [];
    }
  }
  const modules = {
    '@deck.gl/geo-layers': { H3HexagonLayer: LayerDouble },
    '@deck.gl/layers': { ScatterplotLayer: LayerDouble },
    '@deck.gl/maplibre': { MapLibreOverlay: OverlayDouble },
    'maplibre-gl': {
      Map: MapDouble,
      setWorkerUrl(url) {
        observed.workers.push(url);
      },
      GPUInitializationError: GPUError,
    },
    './config.mjs': config,
    './roads.mjs': roads,
    './road-data.json': { default: data },
    './geometry.mjs': {
      placeParticles(...args) {
        observed.motion.push(args);
      },
    },
    './trace.mjs': { readUnmaskedRenderer: () => 'synthetic-renderer' },
    'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url': {
      default: 'synthetic-worker',
    },
    './road-layer': {
      roadLayer(...args) {
        const layer = roadLayer(...args);
        layer.state = {
          pathTesselator: {
            vertexStarts: Array.from(
              { length: args[0].length + 1 },
              (_, index) => index * 2,
            ),
            getPathSegmentIndices: (index) => [index * 2],
          },
        };
        return layer;
      },
    },
  };
  const source = fs.readFileSync(
    new URL('../layers.ts', import.meta.url),
    'utf8',
  );
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      esModuleInterop: false,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const exported = {};
  vm.runInNewContext(compiled, {
    exports: exported,
    require: (name) => modules[name] ?? {},
    console,
    process,
    Error,
  });
  const payload = roads.generateRoads(data, data.roads.links.length * 3);
  const playback = createPlayback(false);
  const scene = await exported.mountScene({
    container: {},
    cap: config.CAP_VALUE,
    cells: ['synthetic-cell'],
    particles: options.particles ?? [],
    showHexagons: options.visible ?? true,
    showParticles: options.visible ?? true,
    roads: enabled ? payload : undefined,
    playback: enabled ? playback : undefined,
    plant,
  });
  return {
    scene,
    payload,
    playback,
    layers: () => held,
    observed,
    exported,
    GPUError,
  };
}

test('composition retains two opacity passes with actual hourly accessors and stable data', async () => {
  const h = await mountFixture(true);
  assert.equal(h.scene.roadInstances, h.payload.length);
  assert.equal(h.scene.roadDashEnabled, true);
  assert.equal(h.layers().length, 4);
  h.playback.tick(0);
  for (let index = 0; index < data.hours.length - 1; index++) {
    h.playback.tick(index * (config.HOUR_HOLD_MS + config.SCENE_MS));
    h.playback.tick(
      index * (config.HOUR_HOLD_MS + config.SCENE_MS) +
        config.HOUR_HOLD_MS +
        config.SCENE_MS / 2,
    );
    h.scene.step(h.playback.elapsed, 0, false);
    const passes = h.layers().slice(2);
    assert.deepEqual(
      Array.from(passes, (pass) => pass.id),
      index % 2 === 0
        ? ['simulated-roads-0', 'simulated-roads-1']
        : ['simulated-roads-1', 'simulated-roads-0'],
    );
    assert.equal(passes[0].props.opacity, 1);
    assert.equal(passes[1].props.opacity, 0.5);
    assert.notEqual(passes[0].id, passes[1].id);
    for (const pass of passes) assert.equal(pass.props.data, h.payload);
    const snapshot = h.scene.roadSnapshot();
    assert.equal(snapshot.hour, data.hours[index]);
    assert.equal(snapshot.nextHour, data.hours[index + 1]);
    assert.equal(snapshot.trigger, data.hours[index]);
    assert.equal(snapshot.stableData, true);
    const sample = [
      ...h.payload.slice(0, data.roads.links.length * 2),
      ...h.payload.slice(-data.roads.links.length),
    ];
    assert.deepEqual(
      Array.from(snapshot.bands),
      roads.bandsAt(sample, data.hours[index]),
    );
    assert.deepEqual(
      Array.from(snapshot.nextBands),
      roads.bandsAt(sample, data.hours[index + 1]),
    );
  }
});

test('map options retain the fixed extent, drawing buffer and noninteractive scene', async () => {
  const h = await mountFixture(false);
  assert.deepEqual(JSON.parse(JSON.stringify(h.observed.mapOptions)), {
    container: {},
    style: {
      version: 8,
      name: 'Synthetic extent',
      sources: {
        extent: {
          type: 'geojson',
          data: {
            type: 'Feature',
            properties: {},
            geometry: {
              type: 'Polygon',
              coordinates: [
                [
                  [-1.18, -1.18],
                  [1.22, -1.18],
                  [1.22, 1.22],
                  [-1.18, 1.22],
                  [-1.18, -1.18],
                ],
              ],
            },
          },
        },
      },
      layers: [
        {
          id: 'extent',
          type: 'fill',
          source: 'extent',
          paint: { 'fill-color': '#c5d0c8' },
        },
      ],
    },
    center: [0.02, 0.02],
    zoom: 9,
    bearing: 0,
    pitch: 0,
    interactive: false,
    attributionControl: false,
    maplibreLogo: false,
    fadeDuration: 0,
    pixelRatio: 1,
    canvasContextAttributes: {
      preserveDrawingBuffer: true,
      contextType: 'webgl2',
    },
  });
});

test('base layer properties retain flat filled hexagons and pixel particles', async () => {
  const h = await mountFixture(false);
  const [hex, particle] = h.layers();
  assert.equal(hex.props.id, 'synthetic-hexagons');
  assert.equal(hex.props.highPrecision, false);
  assert.equal(hex.props.extruded, false);
  assert.equal(hex.props.filled, true);
  assert.equal(hex.props.stroked, false);
  assert.deepEqual(Array.from(hex.props.getFillColor), [32, 96, 112, 230]);
  assert.equal(particle.props.id, 'synthetic-particles');
  assert.equal(particle.props.radiusUnits, 'pixels');
  assert.deepEqual(Array.from(particle.props.getFillColor), [214, 92, 32, 240]);
});

test('composition keeps the original set and reports hidden and undashed road plants', async () => {
  const base = await mountFixture(false);
  assert.equal(base.layers().length, 2);
  assert.equal(base.scene.roadInstances, 0);
  assert.equal(base.scene.roadDashEnabled, false);
  const hidden = await mountFixture(true, 'hide-roads');
  assert.equal(hidden.scene.roadInstances, 0);
  const solid = await mountFixture(true, 'omit-road-dash');
  assert.equal(solid.scene.roadDashEnabled, false);
});

test('mid-fade composite keeps unchanged colours exact and blends changed colours', async () => {
  const h = await mountFixture(true);
  h.playback.tick(0);
  h.playback.tick(config.HOUR_HOLD_MS + config.SCENE_MS / 2);
  h.scene.step(h.playback.elapsed, 0, false);
  const [outgoing, incoming] = h.layers().slice(2);
  const composite = (a, b) =>
    a.map(
      (channel, index) =>
        b[index] * incoming.props.opacity +
        channel * outgoing.props.opacity * (1 - incoming.props.opacity),
    );
  assert.deepEqual(composite([20, 40, 60], [20, 40, 60]), [20, 40, 60]);
  assert.deepEqual(composite([20, 40, 60], [60, 80, 100]), [40, 60, 80]);
});

test('canvas sample recognises opaque road colours and rejects background', async () => {
  for (const color of config.ROAD_COLORS) {
    const h = await mountFixture(true, '', color);
    assert.equal(h.scene.sample().road, true);
  }
  const blank = await mountFixture(false, '', [197, 208, 200, 255]);
  assert.equal(blank.scene.sample().road, false);
});

test('road pixel recognition requires every RGB channel to match', async () => {
  for (const color of config.ROAD_COLORS) {
    for (const channel of [0, 1, 2]) {
      const near = [...color];
      near[channel] += 1;
      const h = await mountFixture(true, '', near);
      assert.equal(h.scene.sample().road, false);
    }
  }
});

test('scene reports actual counts, accessors, motion, renderer and context events', async () => {
  const particles = [{ position: [2, 3] }, { position: [4, 5] }];
  const h = await mountFixture(false, '', undefined, { particles });
  assert.equal(h.scene.hexagonInstances, 1);
  assert.equal(h.scene.particleInstances, 2);
  assert.deepEqual(Array.from(h.scene.roads), []);
  const [hex, particle] = h.layers();
  assert.equal(hex.props.getHexagon('synthetic-cell'), 'synthetic-cell');
  assert.equal(particle.props.getPosition(particles[0]), particles[0].position);
  h.scene.step(125, 27, false);
  assert.equal(h.observed.motion.length, 1);
  assert.equal(h.observed.motion[0][0], particles);
  assert.equal(h.observed.motion[0][1], 125);
  assert.equal(h.layers()[1].props.updateTriggers.getPosition, 125);
  assert.deepEqual(JSON.parse(JSON.stringify(h.observed.turns)), [
    { center: [0.02, 0.02], zoom: 9, bearing: 27, pitch: 0 },
  ]);
  h.scene.step(250, 27, true);
  assert.equal(h.observed.motion.length, 1);
  assert.equal(h.scene.bearing(), 13);
  assert.equal(h.scene.renderer(), 'synthetic-renderer');
  let prevented = 0,
    notified = 0;
  h.scene.onContextLost(() => notified++);
  h.observed.events.webglcontextlost({
    preventDefault() {
      prevented++;
    },
  });
  assert.equal(prevented, 1);
  assert.equal(notified, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(h.scene.sample())), {
    hex: false,
    particle: false,
    road: false,
  });
  const hidden = await mountFixture(false, '', undefined, {
    particles,
    visible: false,
  });
  assert.equal(hidden.scene.hexagonInstances, 0);
  assert.equal(hidden.scene.particleInstances, 0);
  const sub = await mountFixture(false, '', undefined, { sublayers: [2, 3] });
  assert.equal(sub.scene.hexagonInstances, 5);
  assert.equal(sub.scene.particleInstances, 5);
  assert.deepEqual(Array.from(h.observed.workers), ['synthetic-worker']);
  assert.deepEqual(h.observed.removed, ['error', 'error']);
  assert.equal(
    h.exported.webglFailure(new h.GPUError('synthetic')),
    'webgl2-unavailable',
  );
  assert.equal(
    h.exported.webglFailure(new Error('synthetic failure')),
    'synthetic failure',
  );
  assert.equal(h.exported.webglFailure(null), 'map failed');
  assert.deepEqual(JSON.parse(JSON.stringify(h.exported.WALL)), {
    width: 1920,
    height: 1080,
  });
});

test('map failures reject without leaving the idle callback registered', async () => {
  await assert.rejects(
    mountFixture(false, '', undefined, {
      fail: new Error('synthetic failure'),
    }),
    /^Error: synthetic failure$/,
  );
  await assert.rejects(
    mountFixture(false, '', undefined, { fail: 'synthetic failure' }),
    /^Error: map failed$/,
  );
});

test('sampling uses every interior grid point and separates pixel categories', async () => {
  const h = await mountFixture(false, '', (x, y) =>
    x === 60 && y === 33
      ? [32, 96, 112, 255]
      : x === 180 && y === 33
        ? [214, 92, 32, 255]
        : [197, 208, 200, 255],
  );
  assert.deepEqual(JSON.parse(JSON.stringify(h.scene.sample())), {
    hex: true,
    particle: true,
    road: false,
  });
  assert.equal(h.observed.pixels.length, 256);
  const expected = [];
  for (let row = 0; row < 16; row++)
    for (let column = 0; column < 16; column++)
      expected.push([60 + 120 * column, Math.floor(33.75 + 67.5 * row), 1, 1]);
  assert.deepEqual(h.observed.pixels, expected);
  for (const [pixel, hex, particle] of [
    [[161, 149, 119, 255], false, true],
    [[160, 149, 119, 255], false, false],
    [[161, 150, 119, 255], false, false],
    [[161, 149, 120, 255], false, false],
    [[100, 101, 121, 255], true, false],
    [[100, 101, 120, 255], false, false],
    [[100, 100, 121, 255], false, false],
    [[100, 101, 190, 255], false, false],
    [[197, 208, 200, 255], false, false],
  ]) {
    const candidate = await mountFixture(false, '', pixel);
    assert.deepEqual(JSON.parse(JSON.stringify(candidate.scene.sample())), {
      hex,
      particle,
      road: false,
    });
  }
});
