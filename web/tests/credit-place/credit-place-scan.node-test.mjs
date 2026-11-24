/**
 * Built-bundle and rendered-page credit scan (S3-T16 box 8, TST-263 place).
 * A planted credit outside the collapsed credits must exit 1.
 */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';

import { judgeBuiltStage } from './credit-place-scan.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '../..');
const SCAN = path.join(WEB, 'tests/credit-place/credit-place-scan.mjs');
const CREDIT = 'SYN-credit';
const ROOT = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-credit-place-'));
after(() => fs.rmSync(ROOT, { recursive: true, force: true }));

const PLACE_BUNDLE = [
  'function credits(mode){',
  'return mode==="satellite"?',
  'React.createElement("details",null,',
  'React.createElement("summary",null,"Map credits"),',
  `${JSON.stringify(CREDIT)},`,
  'chip("map-satellite-credit")):null}',
].join('');

const MARKER_ONLY_BUNDLE = [
  'function credits(mode){',
  'return mode==="satellite"?',
  'React.createElement("details",null,',
  'React.createElement("summary",null,"Map credits"),',
  'chip("map-satellite-credit")):null}',
].join('');

function write(name, text) {
  const file = path.join(ROOT, name);
  fs.writeFileSync(file, text);
  return file;
}

function collapsedPage(credit) {
  return [
    '<div class="stage-credits" data-part="attribution">',
    '<p>Open map credit line</p>',
    '<details>',
    '<summary>Map credits</summary>',
    `<p>${credit}</p>`,
    '</details>',
    '</div>',
  ].join('');
}

function run(page, bundle) {
  return spawnSync(
    process.execPath,
    [SCAN, '--page', page, '--bundle', bundle, '--credit', CREDIT],
    {
      cwd: WEB,
      encoding: 'utf8',
      env: {
        PATH: process.env.PATH,
        HOME: process.env.HOME,
      },
    },
  );
}

test('collapsed satellite credit passes the place scan', () => {
  const page = write('page-ok.html', collapsedPage(CREDIT));
  const bundle = write('bundle-ok.js', PLACE_BUNDLE);
  const result = run(page, bundle);
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.equal(result.stdout, 'credit-place-ok\n');
});

test('a credit outside the collapsed credits fails the place scan', () => {
  const page = write(
    'page-plant.html',
    `${collapsedPage(CREDIT)}<p>${CREDIT}</p>`,
  );
  const bundle = write('bundle-ok-again.js', PLACE_BUNDLE);
  const result = run(page, bundle);
  assert.equal(result.status, 1, result.stdout);
  assert.equal(result.stdout, 'credit-outside-collapsed\n');
});

test('a credit planted in the bundle outside the collapsed place fails', () => {
  const page = write('page-ok-bundle.html', collapsedPage(CREDIT));
  const bundle = write('bundle-plant.js', `${PLACE_BUNDLE}\n${CREDIT}\n`);
  const result = run(page, bundle);
  assert.equal(result.status, 1, result.stdout);
  assert.equal(result.stdout, 'credit-outside-collapsed\n');
});

test('an open details element is not the collapsed place', () => {
  const page = write(
    'page-open.html',
    collapsedPage(CREDIT).replace('<details>', '<details open>'),
  );
  const bundle = write('bundle-open.js', PLACE_BUNDLE);
  const result = run(page, bundle);
  assert.equal(result.status, 1, result.stdout);
  assert.equal(result.stdout, 'credit-outside-collapsed\n');
});

test('a place marker without a credit occurrence is not enough', () => {
  const page = write('page-marker.html', collapsedPage(CREDIT));
  const bundle = write('bundle-marker.js', MARKER_ONLY_BUNDLE);
  const result = run(page, bundle);
  assert.equal(result.status, 1, result.stdout);
  assert.equal(result.stdout, 'credit-place-missing\n');
});

test('a credit split across nested elements outside the collapsed credits fails', () => {
  const page = write(
    'page-split.html',
    `${collapsedPage(CREDIT)}<p>SYN-<span>&#99;redit</span></p>`,
  );
  const bundle = write('bundle-split.js', PLACE_BUNDLE);
  const result = run(page, bundle);
  assert.equal(result.status, 1, result.stdout);
  assert.equal(result.stdout, 'credit-outside-collapsed\n');
});

test('a credit split inside collapsed details still belongs there', () => {
  const page = write(
    'page-split-inside.html',
    collapsedPage(CREDIT).replace(
      `<p>${CREDIT}</p>`,
      '<p>SYN-<span>credit</span></p>',
    ),
  );
  const bundle = write('bundle-split-inside.js', PLACE_BUNDLE);
  const result = run(page, bundle);
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.equal(result.stdout, 'credit-place-ok\n');
});

test('a sibling details element does not cover a credit beside it', () => {
  const page = write(
    'page-sibling.html',
    [
      '<div class="stage-credits" data-part="attribution">',
      '<details><summary>Map credits</summary></details>',
      `<p>${CREDIT}</p>`,
      '</div>',
    ].join(''),
  );
  const bundle = write('bundle-sibling.js', PLACE_BUNDLE);
  const result = run(page, bundle);
  assert.equal(result.status, 1, result.stdout);
  assert.equal(result.stdout, 'credit-outside-collapsed\n');
});

test(
  'the built stage keeps the satellite credit inside closed attribution details',
  { timeout: 180000 },
  async () => {
    const verdict = await judgeBuiltStage({
      webRoot: WEB,
      outDir: path.join(ROOT, 'stage-dist'),
      credit: CREDIT,
    });
    assert.equal(verdict, 'credit-place-ok');
  },
);
