import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  judgeSubmission,
  judgeRenderer,
  judgeEmptyCanvas,
  readUnmaskedRenderer,
  summariseFrames,
  validateGate,
} from '../trace.mjs';

import { mutationTrace, mutationCapture } from './mutation-fixtures.mjs';

const gate = (trace, capture = mutationCapture()) =>
  validateGate(trace, 'hexagons-particles', capture);
const failed = (result, failure) =>
  assert.deepEqual(result, { ok: false, failure });

test('mutation trace has independent totals with a nonzero clock origin', () => {
  assert.deepEqual(gate(mutationTrace()), { ok: true });
  assert.deepEqual(judgeSubmission(mutationTrace()), { ok: true });
  assert.deepEqual(summariseFrames([100, 140, 150, 180, 200]), {
    ok: true,
    frameCount: 4,
    durationMs: 100,
    intervals: [40, 10, 30, 20],
    percentiles: { p50: 20, p95: 40, p99: 40 },
    shareUnderBudget: 0.25,
  });
});

test('every stored summary field and nested shape is checked independently', () => {
  for (const field of ['frameCount', 'durationMs', 'shareUnderBudget']) {
    const trace = mutationTrace();
    trace.summary[field] += 1;
    failed(judgeSubmission(trace), 'forged-summary');
  }
  for (const field of ['p50', 'p95', 'p99']) {
    const trace = mutationTrace();
    trace.summary.percentiles[field] += 1;
    failed(judgeSubmission(trace), 'forged-summary');
  }
  for (const field of [
    'window',
    'canvas',
    'drawingBuffer',
    'cap',
    'counts',
    'camera',
    'animation',
    'interruptions',
    'summary',
  ]) {
    for (const invalid of [null, [], 1, 'synthetic', false]) {
      const trace = mutationTrace();
      trace[field] = invalid;
      failed(judgeSubmission(trace), 'missing-field');
    }
    const trace = mutationTrace();
    trace[field].unexpected = true;
    failed(judgeSubmission(trace), 'unknown-field');
  }
  for (const invalid of [undefined, null, [], 1, 'synthetic', false]) {
    failed(judgeSubmission(invalid), 'missing-field');
    const trace = mutationTrace();
    trace.summary.percentiles = invalid;
    failed(judgeSubmission(trace), 'missing-field');
  }
  const trace = mutationTrace();
  trace.summary.percentiles.unexpected = 1;
  failed(judgeSubmission(trace), 'unknown-field');
  failed(
    judgeSubmission({ ...mutationTrace(), outputPath: 'synthetic.json' }),
    'client-path',
  );
  const bad = mutationTrace();
  bad.timestamps = [0, NaN];
  failed(judgeSubmission(bad), 'non-finite-timestamp');
});

test('empty-canvas median handles unordered odd and even intervals and exact boundary', () => {
  assert.deepEqual(judgeEmptyCanvas([100, 110]), {
    ok: true,
    failure: '',
    framesPerSecond: 100,
  });
  assert.deepEqual(judgeEmptyCanvas([100, 125, 135]), {
    ok: true,
    failure: '',
    framesPerSecond: 57.14,
  });
  assert.deepEqual(judgeEmptyCanvas([100, 130, 140, 160]), {
    ok: false,
    failure: 'capped-frame-rate',
    framesPerSecond: 50,
  });
  for (const stamps of [
    null,
    [],
    [0],
    [0, 0],
    [10, 0],
    [NaN, 10],
    [0, NaN],
    ['0', 10],
    [0, '10'],
    [Infinity, 10],
    [-Infinity, 0, 10, 20],
    [0, Infinity],
  ]) {
    assert.deepEqual(judgeEmptyCanvas(stamps), {
      ok: false,
      failure: 'capped-frame-rate',
      framesPerSecond: 0,
    });
  }
  for (const stamps of [
    [NaN, 10],
    [Infinity, 10],
    ['0', 10],
    [null, 10],
  ])
    failed(summariseFrames(stamps), 'non-finite-timestamp');
});

test('renderer words and context failures are refused at each boundary', () => {
  for (const word of ['warp', 'warp adapter', 'adapter warp'])
    assert.equal(judgeRenderer(word), 'software-renderer');
  for (const word of ['remote', 'remote adapter', 'adapter remote'])
    assert.equal(judgeRenderer(word), 'remote-renderer');
  for (const value of [null, undefined, 1, {}, '', '   '])
    assert.equal(judgeRenderer(value), 'missing-renderer');
  const valid = {
    getExtension: () => ({ UNMASKED_RENDERER_WEBGL: 7 }),
    getParameter: () => 'Synthetic unmasked',
  };
  assert.equal(readUnmaskedRenderer(valid), 'Synthetic unmasked');
  for (const value of [
    null,
    undefined,
    1,
    'synthetic',
    () => {},
    {},
    { ...valid, getExtension: 1 },
    { ...valid, getParameter: null },
  ])
    assert.equal(readUnmaskedRenderer(value), '');
  for (const extension of [
    null,
    7,
    'synthetic',
    {},
    { UNMASKED_RENDERER_WEBGL: '7' },
  ])
    assert.equal(
      readUnmaskedRenderer({ ...valid, getExtension: () => extension }),
      '',
    );
  for (const value of [null, 1, undefined, '', '   '])
    assert.equal(
      readUnmaskedRenderer({ ...valid, getParameter: () => value }),
      '',
    );
});

test('native qualification checks each capture and user-agent component', () => {
  const capture = mutationCapture();
  for (const [key, value] of [
    ['role', 'test'],
    ['host', 'synthetic'],
    ['browser', 'synthetic'],
    ['tracePath', 1],
    ['tracePath', '../synthetic.json'],
    ['tracePath', 'synthetic.json'],
    ['sha256', 1],
    ['sha256', 'prefix' + capture.sha256],
    ['sha256', capture.sha256 + 'suffix'],
  ]) {
    failed(gate(mutationTrace(), { ...capture, [key]: value }), 'non-native');
  }
  for (const userAgent of [
    1,
    '',
    'Synthetic Chrome',
    'Windows Synthetic',
    'Windows Chrome Edg',
  ]) {
    failed(gate({ ...mutationTrace(), userAgent }), 'non-native');
  }
  failed(gate(mutationTrace(), { ...capture, browser: 'edge' }), 'non-native');
  assert.deepEqual(
    gate(
      { ...mutationTrace(), userAgent: 'Synthetic Windows Edg' },
      { ...capture, browser: 'edge' },
    ),
    { ok: true },
  );
});

test('qualification rejects invalid numeric and identity fields without coercion', () => {
  failed(gate({ ...mutationTrace(), codeCommit: 1 }), 'missing-commit');
  for (const lockSha256 of [
    1,
    'prefix' + mutationTrace().lockSha256,
    mutationTrace().lockSha256 + 'suffix',
  ])
    failed(gate({ ...mutationTrace(), lockSha256 }), 'missing-lock');
  for (const value of ['1', true, NaN, Infinity, -1, 0]) {
    failed(
      gate({ ...mutationTrace(), devicePixelRatio: value }),
      'missing-ratio',
    );
    for (const key of ['width', 'height']) {
      const trace = mutationTrace();
      trace.window[key] = value;
      failed(gate(trace), 'missing-window');
    }
  }
  for (const key of ['width', 'height']) {
    const trace = mutationTrace();
    trace.drawingBuffer[key] += 1;
    failed(gate(trace), 'dimension-mismatch');
  }
});

test('full road hours and exactly the frame-share threshold remain valid', async () => {
  const { default: data } = await import('../road-data.json', {
    with: { type: 'json' },
  });
  const trace = mutationTrace();
  trace.layerSet = 'hexagons-particles-roads';
  trace.counts.roads = 100000 + data.roads.links.length;
  Object.assign(trace.animation, {
    playbackActive: true,
    reducedMotion: false,
    hoursShown: data.hours,
  });
  assert.deepEqual(validateGate(trace, trace.layerSet, mutationCapture()), {
    ok: true,
  });
  const exact = mutationTrace();
  exact.timestamps = [100];
  for (let block = 0; block < 30; block++) {
    for (let index = 0; index < 100; index++)
      exact.timestamps.push(exact.timestamps.at(-1) + (index < 95 ? 10 : 20));
  }
  exact.summary = {
    frameCount: 3000,
    durationMs: 31500,
    percentiles: { p50: 10, p95: 10, p99: 20 },
    shareUnderBudget: 0.95,
  };
  assert.deepEqual(gate(exact), { ok: true });
});

test('digest arrays are not strings and malformed extension objects remain refused', () => {
  failed(
    gate({ ...mutationTrace(), lockSha256: [mutationTrace().lockSha256] }),
    'missing-lock',
  );
  failed(
    gate(mutationTrace(), {
      ...mutationCapture(),
      sha256: [mutationCapture().sha256],
    }),
    'non-native',
  );
  const trace = mutationTrace();
  trace.canvas.cssHeight += 1;
  failed(gate(trace), 'wrong-viewport');
  assert.equal(
    readUnmaskedRenderer({
      getExtension: () => undefined,
      getParameter: () => 'synthetic',
    }),
    '',
  );
});
