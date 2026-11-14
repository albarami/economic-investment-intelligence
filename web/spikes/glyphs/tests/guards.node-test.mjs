import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  FIRST_LABEL_ID,
  REMOTE_FONT,
  REVIEW_APPROVED,
  REVIEW_PENDING,
  judgeBeforeId,
  judgeCsp,
  judgeDigits,
  judgeDirection,
  judgeFonts,
  judgeLetterSpacing,
  judgeLicences,
  judgeNames,
  judgeNetwork,
  judgeRequests,
  judgeRtlPlugin,
  judgeWebGpu,
} from '../guards.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function source(name) {
  return fs.readFileSync(path.join(ROOT, name), 'utf8');
}

test('a content-security-policy without default-src self fails', () => {
  const result = judgeCsp("script-src 'self'");
  assert.equal(result.ok, false);
  assert.match(result.detail, /content-security-policy/);
});

test('a same-origin data url is not a blocked request', () => {
  const result = judgeRequests(['data:image/svg+xml,ok'], 'http://127.0.0.1:1');
  assert.equal(result.ok, true);
});

test('a missing content-security-policy header fails', () => {
  const result = judgeCsp(null);
  assert.equal(result.ok, false);
  assert.match(result.detail, /content-security-policy/);
});

test('a remote font url fails the request guard', () => {
  const result = judgeRequests([REMOTE_FONT], 'http://127.0.0.1:1');
  assert.equal(result.ok, false);
  assert.match(result.detail, /assets\.invalid/);
});

test('a layer without beforeId fails', () => {
  const missing = judgeBeforeId(null, FIRST_LABEL_ID);
  assert.equal(missing.ok, false);
  const after = judgeBeforeId('buildings', FIRST_LABEL_ID);
  assert.equal(after.ok, false);
});

test('a missing first label id fails', () => {
  const result = judgeBeforeId('', '');
  assert.equal(result.ok, false);
  assert.match(result.detail, /first label/);
});

test('a source without the webgl-only condition fails', () => {
  const result = judgeWebGpu('layers: []');
  assert.equal(result.ok, false);
  assert.match(result.detail, /WebGL/);
});

test('an enabled WebGPU fixture fails', () => {
  const result = judgeWebGpu('visgl:webgl-only\nwebgpu: true\n');
  assert.equal(result.ok, false);
  assert.match(result.detail, /WebGPU/);
});

test('a right-to-left plugin call fails', () => {
  const result = judgeRtlPlugin('setRTLTextPlugin(url);\n');
  assert.equal(result.ok, false);
  assert.match(result.detail, /plugin/);
});

test('a missing Latin face fails', () => {
  const result = judgeFonts(['Noto Sans Arabic Regular'], false);
  assert.equal(result.ok, false);
  assert.match(result.detail, /Latin/);
});

test('an Arabic-Indic digit fails', () => {
  const result = judgeDigits('١٢٣');
  assert.equal(result.ok, false);
  assert.match(result.detail, /digit/);
});

test('a non-zero Arabic letter spacing fails', () => {
  const result = judgeLetterSpacing('2px');
  assert.equal(result.ok, false);
  assert.match(result.detail, /spacing/);
});

test('a left-to-right Arabic document fails', () => {
  const result = judgeDirection('ltr', 0, false);
  assert.equal(result.ok, false);
  assert.match(result.detail, /rtl/);
});

test('a mirrored map fails', () => {
  const result = judgeDirection('rtl', 0, true);
  assert.equal(result.ok, false);
  assert.match(result.detail, /mirrored/);
});

test('mixed review states fail', () => {
  const result = judgeNames([
    { nameAr: 'منطقة الاختبار ألف', review: REVIEW_PENDING },
    { nameAr: 'حي المحاكاة باء', review: REVIEW_APPROVED },
  ]);
  assert.equal(result.ok, false);
});

test('a short licence set fails', () => {
  const result = judgeLicences(['SIL Open Font License']);
  assert.equal(result.ok, false);
  assert.match(result.detail, /licence/);
});

test('a text that is not the SIL licence fails', () => {
  const result = judgeLicences(['one', 'two', 'three', 'four']);
  assert.equal(result.ok, false);
  assert.match(result.detail, /licence/);
});

test('a network record that is not a list fails', () => {
  const result = judgeNetwork(null);
  assert.equal(result.ok, false);
  assert.match(result.detail, /network/);
});

test('an absolute url that was not blocked fails', () => {
  const result = judgeNetwork([
    { url: REMOTE_FONT, decision: 'blocked' },
    { url: 'https://assets.invalid/other.woff2', decision: 'same-origin' },
  ]);
  assert.equal(result.ok, false);
  assert.match(result.detail, /assets\.invalid\/other/);
});

test('a network record without the planted block fails', () => {
  const result = judgeNetwork([
    { url: '/assets/font.woff2', decision: 'same-origin' },
  ]);
  assert.equal(result.ok, false);
  assert.match(result.detail, /assets\.invalid/);
});

test('an omitted Arabic face fails', () => {
  const result = judgeFonts(['Noto Sans Regular'], true);
  assert.equal(result.ok, false);
  assert.match(result.detail, /Arabic/);
});

test('the spike sources keep the primary pin guards', () => {
  const files = ['main.ts', 'map.ts', 'fonts.ts', 'vite.config.ts'];
  for (const name of files) {
    assert.equal(fs.existsSync(path.join(ROOT, name)), true, name);
  }
  const page = files.map((name) => source(name)).join('\n');
  assert.equal(judgeRtlPlugin(page).ok, true, judgeRtlPlugin(page).detail);
  assert.equal(judgeWebGpu(page).ok, true, judgeWebGpu(page).detail);
});

test('unknown request schemes are blocked', () => {
  for (const url of [
    'ftp://example.invalid/tile.pbf',
    'ws://127.0.0.1:1/socket',
    'file:///synthetic.txt',
  ]) {
    const result = judgeRequests([url], 'http://127.0.0.1:1');
    assert.equal(result.ok, false);
    assert.equal(result.rows[0].decision, 'blocked');
  }
});
