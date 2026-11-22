import { expect, test, type Page } from '@playwright/test';
import { build } from 'vite';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

// Invented geometry only. The MapLibre shell owns the colour pass; the
// coincident deck caster participates only in the shadow pass.
const SCENE = String.raw`
import {Map, setWorkerUrl} from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import {AmbientLight, DirectionalLight, LightingEffect} from '@deck.gl/core';
import {SolidPolygonLayer} from '@deck.gl/layers';
import {MapLibreOverlay} from '@deck.gl/maplibre';
setWorkerUrl(workerUrl);
const plant = new URL(location.href).searchParams.get('plant');
const box = (x, y, r) => [[x-r,y-r],[x+r,y-r],[x+r,y+r],[x-r,y+r],[x-r,y-r]];
const caster = box(0, 0, 0.00008);
const none = box(0.0006, 0.0006, 0.00008);
const receiver = box(0.00025, 0.00025, 0.0006);
const features = [
  {type:'Feature', properties:{id:'SYN-B-caster',height:40}, geometry:{type:'Polygon',coordinates:[caster]}},
  {type:'Feature', properties:{id:'SYN-B-none',height:null}, geometry:{type:'Polygon',coordinates:[none]}}
];
if (!document.createElement('canvas').getContext('webgl2')) {
  globalThis.buildingsScene = {unavailable:'buildings_webgl2_unavailable'};
  throw new Error('buildings_webgl2_unavailable');
}
const map = new Map({
  container:'map', center:[0.0001,0.0001], zoom:18, pitch:40, bearing:0,
  interactive:false, attributionControl:false, fadeDuration:0,
  canvasContextAttributes:{preserveDrawingBuffer:true,antialias:false},
  style:{version:8, sources:{buildings:{type:'geojson',data:{type:'FeatureCollection',features}}}, layers:[
    {id:'base',type:'background',paint:{'background-color':'#306090'}},
    {id:'none',type:'fill',source:'buildings',filter:['==',['get','id'],'SYN-B-none'],paint:{'fill-color':'#30a060','fill-antialias':false}},
    {id:'shell',type:'fill-extrusion',source:'buildings',filter:['==',['get','id'],'SYN-B-caster'],paint:{'fill-extrusion-height':['get','height'],'fill-extrusion-color':'#d04030','fill-extrusion-vertical-gradient':false}}
  ]}
});
const failures = [];
map.on('error', e => failures.push(e.error.message));
let overlay;
let colourCasters = [];
class ShadowCaster extends SolidPolygonLayer {
  static layerName = 'InventedShadowCaster';
  draw(options) {
    if (!options.shaderModuleProps.shadow?.drawToShadowMap) colourCasters.push(this.id);
    super.draw(options);
  }
}
function layers() {
  const result = [];
  if (plant !== 'receiver-removed') result.push(new SolidPolygonLayer({
    id:'receiver',data:[receiver],getPolygon:d=>d,extruded:false,
    getFillColor:[220,220,220,255],shadowEnabled:true,beforeId:'none'
  }));
  if (plant !== 'caster-removed') result.push(new ShadowCaster({
    id:'caster',data:plant === 'none-caster' ? [caster, none] : [caster],getPolygon:d=>d,extruded:true,getElevation:40,
    getFillColor:[208,64,48,255],shadowEnabled:true,beforeId:'none'
  }));
  return result;
}
function effect(enabled) {
  const light = new DirectionalLight({direction:[-1,-1,-1],intensity:1,_shadow:enabled && plant !== 'shadow-off'});
  const effect = new LightingEffect({ambient:new AmbientLight({intensity:1}),sun:light});
  effect.shadowColor = [0,0,0,0.8];
  return effect;
}
const ready = map.once('load').then(() => {
  map.setPixelRatio(1);
  overlay = new MapLibreOverlay({interleaved:true,effects:[effect(false)],layers:layers(),
    onError:e=>failures.push(e.message),
    layerFilter:({layer,renderPass})=> {
      if (layer.id !== 'caster' || renderPass === 'shadow') return true;
      if (plant === 'second-shell') return true;
      return false;
    }
  });
  map.addControl(overlay);
});
async function capture(enabled) {
  await ready;
  colourCasters = [];
  overlay.setProps({effects:[effect(enabled)]});
  await new Promise(resolve => { map.once('idle', resolve); map.triggerRepaint(); });
  map.redraw();
  const canvas = map.getCanvas();
  const gl = canvas.getContext('webgl2');
  if (!gl) throw new Error('buildings_webgl2_unavailable');
  const samples = {};
  for (const [name, point] of Object.entries({receiver:[-0.00025,-0.00025],none:[0.0006,0.0006],noneShadow:[0.00045,0.00045],base:[-0.00045,0.0003]})) {
    const p = map.project(point);
    const pixels = new Uint8Array(7*7*4);
    gl.readPixels(Math.round(p.x)-3,canvas.height-1-Math.round(p.y)-3,7,7,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
    samples[name] = Array.from(pixels).filter((_,index)=>index%4!==3);
  }
  const rendererInfo = gl.getExtension('WEBGL_debug_renderer_info');
  return {samples,colourCasters:[...new Set(colourCasters)],failures,
    shells:[...new Set(map.queryRenderedFeatures({layers:['shell']}).map(f=>f.properties.id))],
    renderer:gl.getParameter(rendererInfo ? rendererInfo.UNMASKED_RENDERER_WEBGL : gl.RENDERER)};
}
globalThis.buildingsScene = {capture,remove:()=>map.remove()};
`;

type Capture = {
  samples: Record<'receiver' | 'none' | 'noneShadow' | 'base', number[]>;
  colourCasters: string[];
  failures: string[];
  shells: string[];
  renderer: string;
};

declare global {
  var buildingsScene: {
    unavailable?: string;
    capture(enabled: boolean): Promise<Capture>;
    remove(): void;
  };
}

let dist = '';
test.beforeAll(async () => {
  dist = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-buildings-scene-'));
  await build({
    configFile: false,
    envDir: false,
    cacheDir: path.join(dist, 'vite-cache'),
    publicDir: false,
    define: { 'process.env.NODE_ENV': JSON.stringify('production') },
    logLevel: 'error',
    resolve: { conditions: ['visgl:webgl-only'] },
    plugins: [
      {
        name: 'invented-shadow-scene',
        resolveId: (id) =>
          id.endsWith('shadow-scene') ? '\0shadow-scene' : undefined,
        load: (id) => (id === '\0shadow-scene' ? SCENE : undefined),
      },
    ],
    build: {
      outDir: dist,
      emptyOutDir: true,
      lib: { entry: 'shadow-scene', formats: ['es'], fileName: 'scene' },
    },
  });
});
test.afterAll(() => {
  if (dist) fs.rmSync(dist, { recursive: true, force: true });
});

async function openScene(page: Page) {
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    expect(url.origin, 'buildings_external_request').toBe(
      'http://invented.invalid',
    );
    if (url.pathname === '/')
      return route.fulfill({
        contentType: 'text/html',
        body: '<style>body{margin:0}#map{width:640px;height:480px}</style><div id="map"></div><script type="module" src="/scene.js"></script>',
      });
    const name = url.pathname.slice(1);
    expect(
      fs.readdirSync(dist, { recursive: true }),
      'buildings_unknown_asset',
    ).toContain(name);
    await route.fulfill({
      contentType: 'text/javascript',
      body: fs.readFileSync(path.join(dist, name)),
    });
  });
  const plant = process.env.EII_BUILDINGS_PLANT ?? '';
  const entry =
    plant === 'foreign-origin'
      ? 'http://foreign.invalid/'
      : plant === 'unknown-asset'
        ? 'http://invented.invalid/SYN-missing.js'
        : `http://invented.invalid/?plant=${plant}`;
  await page.goto(entry);
  await page.waitForFunction(() => !!globalThis.buildingsScene);
  expect(
    await page.evaluate(() => globalThis.buildingsScene.unavailable ?? ''),
    'buildings_webgl2_unavailable',
  ).toBe('');
}

function mean(values: number[]) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

test('receiver darkens; none and basemap stay equal; one visible shell', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await openScene(page);
  const off = await page.evaluate(() =>
    globalThis.buildingsScene.capture(false),
  );
  const on = await page.evaluate(() => globalThis.buildingsScene.capture(true));
  console.log(
    JSON.stringify({
      renderer: on.renderer,
      off: mean(off.samples.receiver),
      on: mean(on.samples.receiver),
    }),
  );
  expect(off.samples.receiver, 'buildings_receiver_missing').toEqual(
    Array(147).fill(220),
  );
  expect(off.samples.none, 'buildings_none_missing').toEqual(
    Array(49).fill([48, 160, 96]).flat(),
  );
  expect(off.samples.base, 'buildings_base_missing').toEqual(
    Array(49).fill([48, 96, 144]).flat(),
  );
  expect(errors, 'buildings_page_error').toEqual([]);
  expect(on.failures, 'buildings_draw_error').toEqual([]);
  expect(off.shells, 'buildings_shell_missing').toEqual(['SYN-B-caster']);
  expect(on.colourCasters, 'buildings_second_shell').toEqual([]);
  expect(
    mean(off.samples.receiver) - mean(on.samples.receiver),
    'buildings_shadow_pass_not_drawn',
  ).toBeGreaterThanOrEqual(20);
  expect(off.samples.noneShadow, 'buildings_none_casts').toEqual(
    Array(147).fill(220),
  );
  expect(on.samples.noneShadow, 'buildings_none_casts').toEqual(
    off.samples.noneShadow,
  );
  expect(on.samples.none, 'buildings_none_changed').toEqual(off.samples.none);
  expect(on.samples.base, 'buildings_base_changed').toEqual(off.samples.base);
  await page.evaluate(() => globalThis.buildingsScene.remove());
});

test('missing WebGL2 refuses with its own renderer diagnostic', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
      value: function (
        this: HTMLCanvasElement,
        contextId: string,
        options?: unknown,
      ) {
        if (contextId === 'webgl2') return null;
        return Reflect.apply(original, this, [contextId, options]);
      },
    });
  });
  await expect(openScene(page)).rejects.toThrow('buildings_webgl2_unavailable');
});
