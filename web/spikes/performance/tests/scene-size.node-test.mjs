import assert from 'node:assert/strict';
import fs from 'node:fs';
import { test } from 'node:test';
import {
  ARABIC_REDUCED,
  FULL,
  FULL_STREET_LOAD,
  GATE_BLANK_RENDERER,
  GATE_SLOW_SCENE,
  HEX_NONBLANK,
  PARTICLE_NONBLANK,
  PAUSE_SCENE,
  PIXEL_CAP,
  RENAMED_PROFILE,
  ROAD_PAUSE_PLANT,
  ROAD_TRACE_SCENE,
  SMALL,
  TRACE_CONTRACT,
} from './canvas-mode.mjs';
import { FULL_SITES } from './scene-size-sites.mjs';
import {
  assertLateSizeReads,
  assertSceneSizes,
  shrinkSite,
} from './scene-size.mjs';

const SPEC = new URL('./performance.spec.ts', import.meta.url);
const MODES = new URL('./canvas-mode.mjs', import.meta.url);
const SMALL_MAP = new URL('./small-map.ts', import.meta.url);

function read(url) {
  return fs.readFileSync(url, 'utf8');
}

test('size-dependent scenes keep the full wall canvas', () => {
  assert.equal(TRACE_CONTRACT, FULL);
  assert.equal(HEX_NONBLANK, FULL);
  assert.equal(PARTICLE_NONBLANK, FULL);
  assert.equal(GATE_BLANK_RENDERER, FULL);
  assert.equal(PIXEL_CAP, FULL);
  assert.equal(RENAMED_PROFILE, FULL);
  assert.equal(GATE_SLOW_SCENE, FULL);
  assert.equal(ROAD_TRACE_SCENE, FULL);
  assert.equal(ROAD_PAUSE_PLANT, FULL);
  assert.equal(FULL_STREET_LOAD, FULL);
  assert.equal(PAUSE_SCENE, FULL);
  assert.equal(ARABIC_REDUCED, FULL);
  assert.notEqual(FULL, SMALL);
  assertSceneSizes(read(SPEC), read(MODES), read(SMALL_MAP));
});

test('shrinking a size-dependent scene is refused', () => {
  const spec = read(SPEC);
  const modes = read(MODES);
  const smallMap = read(SMALL_MAP);
  for (const entry of FULL_SITES) {
    assert.throws(
      () => assertSceneSizes(shrinkSite(spec, entry.key), modes, smallMap),
      new RegExp(entry.label),
    );
  }
});

test('a comment cannot stand in for a full canvas call', () => {
  const broken = read(SPEC).replace(
    "open(page, '/en/_perf?profile=smoke', TRACE_CONTRACT)",
    "open(page, '/en/_perf?profile=smoke', SMALL) // was: open(page, '/en/_perf?profile=smoke', TRACE_CONTRACT)",
  );
  assert.throws(
    () => assertSceneSizes(broken, read(MODES), read(SMALL_MAP)),
    /trace contract/,
  );
});

test('full and small differ and the small map shrinks only for small', () => {
  const spec = read(SPEC);
  const modes = read(MODES);
  const smallMap = read(SMALL_MAP);
  const same = modes.replace(
    "export const FULL = 'full';",
    "export const FULL = 'small';",
  );
  assert.throws(() => assertSceneSizes(spec, same, smallMap), /FULL and SMALL/);
  const shrinksFull = smallMap.replace(
    'if (canvas !== SMALL) return;',
    'if (canvas !== FULL) return;',
  );
  assert.throws(
    () => assertSceneSizes(spec, modes, shrinksFull),
    /shrink only for SMALL/,
  );
});

test('a new small-map test that reads the canvas size is refused', () => {
  const planted = `${read(SPEC)}
    test('new size test', async ({ page }) => {
      const spike = await open(page, '/en/_perf?profile=smoke', SMALL);
      expect(spike.cssWidth).toBe(WALL_WIDTH);
    });
  `;
  assert.throws(() => assertLateSizeReads(planted), /cssWidth/);
  const withoutSize = planted.replace(
    'expect(spike.cssWidth).toBe(WALL_WIDTH);',
    '',
  );
  assert.throws(
    () => assertSceneSizes(withoutSize, read(MODES), read(SMALL_MAP)),
    /unexpected canvas/,
  );
});

const STREET_LOAD =
  'roads full street load draws every link and carries the Simulated mark';

test('moving prepareCanvas into the full street load is refused', () => {
  const spec = read(SPEC);
  const removed = spec.replace(
    "  await prepareCanvas(page, SMALL);\n  await page.goto('/en/_perf?profile=smoke&plant=remote-asset');",
    "  await page.goto('/en/_perf?profile=smoke&plant=remote-asset');",
  );
  const open = `  const spike = await open(
    page,
    \`/en/_perf?profile=smoke&layers=\${ROAD_LARGE}\`,
    FULL_STREET_LOAD,
  );`;
  const planted = removed.replace(
    open,
    `  await prepareCanvas(page, SMALL);\n${open}`,
  );
  assert.notEqual(planted, spec);
  assert.throws(
    () => assertSceneSizes(planted, read(MODES), read(SMALL_MAP)),
    new RegExp(STREET_LOAD),
  );
});

test('an aliased canvas import is refused', () => {
  const planted = read(SPEC).replace('  SMALL,\n', '  SMALL as PAUSE_SCENE,\n');
  assert.notEqual(planted, read(SPEC));
  assert.throws(
    () => assertSceneSizes(planted, read(MODES), read(SMALL_MAP)),
    /canvas import alias/,
  );
});

test('a local binding of a full canvas name is refused', () => {
  const needle = `test('${STREET_LOAD}', async ({\n  page,\n}) => {\n`;
  const planted = read(SPEC).replace(
    needle,
    `${needle}  const FULL_STREET_LOAD = SMALL;\n`,
  );
  assert.notEqual(planted, read(SPEC));
  assert.throws(
    () => assertSceneSizes(planted, read(MODES), read(SMALL_MAP)),
    /canvas mode binding: FULL_STREET_LOAD/,
  );
});

test('the open helper must default to the full canvas', () => {
  const planted = read(SPEC).replace(
    'canvas: string = FULL',
    'canvas: string = SMALL',
  );
  assert.notEqual(planted, read(SPEC));
  assert.throws(
    () => assertSceneSizes(planted, read(MODES), read(SMALL_MAP)),
    /open defaults to FULL/,
  );
});

test('the small map must import SMALL without an alias', () => {
  const planted = read(SMALL_MAP).replace(
    "import { SMALL } from './canvas-mode.mjs';",
    "import { SMALL as CANVAS } from './canvas-mode.mjs';",
  );
  assert.notEqual(planted, read(SMALL_MAP));
  assert.throws(
    () => assertSceneSizes(read(SPEC), read(MODES), planted),
    /small-map import/,
  );
});
