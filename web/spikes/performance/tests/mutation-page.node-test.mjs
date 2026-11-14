import assert from 'node:assert/strict';
import { test } from 'node:test';
import { pageHarness } from './page-harness.mjs';
import notices from '../notices.json' with { type: 'json' };
const plain = (value) => JSON.parse(JSON.stringify(value));

test('page helper decisions preserve every supported profile and environment plant', async () => {
  const h = await pageHarness('', false, false, {
    missingMap: true,
    search: '',
  });
  const m = h.api;
  assert.equal(m.readProfile(new URLSearchParams(), 'rename-profile'), 'tuned');
  assert.equal(
    m.readProfile(new URLSearchParams('profile=smoke'), ''),
    'smoke',
  );
  assert.equal(
    m.readProfile(new URLSearchParams('profile=unknown'), ''),
    'gate',
  );
  for (const plant of [
    '',
    'software-renderer',
    'remote-renderer',
    'capped-frame-rate',
    'slow-scene',
  ]) {
    assert.equal(m.environmentGate('gate', plant), true);
    assert.equal(m.environmentGate('smoke', plant), false);
  }
  assert.equal(m.environmentGate('gate', 'freeze'), false);
  assert.equal(
    m.plantedRenderer('real', 'software-renderer'),
    'Microsoft Basic Render Driver',
  );
  assert.equal(
    m.plantedRenderer('real', 'remote-renderer'),
    'Microsoft Remote Display Adapter',
  );
  for (const plant of ['capped-frame-rate', 'slow-scene'])
    assert.equal(m.plantedRenderer('real', plant), 'Synthetic passing adapter');
  assert.equal(m.plantedRenderer('real', ''), 'real');
  assert.equal(m.rendererLine('   '), 'none is available');
  assert.equal(m.rendererLine('real'), 'real');
  m.refuse('synthetic');
  assert.equal(h.window.__spike.failure, 'synthetic');
  assert.equal(h.window.__spike.phase, 'failed');
  assert.equal(h.nodes.get('#map-failure').textContent, 'refused: synthetic');
  m.refuse('synthetic', 30);
  assert.equal(
    h.nodes.get('#map-failure').textContent,
    'refused: synthetic 30',
  );
  assert.equal(h.document.documentElement.lang, 'en');
  assert.equal(h.document.documentElement.dir, 'ltr');
  assert.equal(h.nodes.get('#notice').textContent, notices.english);
});

test('page timestamps retain clock origin, endpoint and each planted interval', async () => {
  const h = await pageHarness('', false, false, {
    missingMap: true,
    search: '',
  });
  const m = h.api;
  assert.deepEqual(Array.from(m.plantedTimestamps(7, 20)), [0, 7, 14, 21]);
  const live = m.liveTimestamps(20);
  h.tick(100);
  h.tick(119);
  h.tick(120);
  assert.deepEqual(Array.from(await live), [100, 119, 120]);
  const capped = await m.emptyCanvasTimestamps('capped-frame-rate');
  assert.equal(capped.length, 61);
  assert.equal(capped[0], 0);
  assert.equal(capped.at(-1), 60 * (1000 / 30));
  const slow = await m.emptyCanvasTimestamps('slow-scene');
  assert.equal(slow.length, 121);
  assert.equal(slow[1], 16.67);
  assert.equal(slow.at(-1), 120 * 16.67);
  const normal = m.emptyCanvasTimestamps('');
  h.tick(0);
  h.tick(2000);
  assert.deepEqual(Array.from(await normal), [0, 2000]);
});

test('renderer probe releases its context and displayed renderer waits one frame', async () => {
  const options = { missingMap: true, search: '' };
  const h = await pageHarness('', false, false, options);
  const m = h.api;
  const probe = m.probeContext(h.nodes.get('#map'));
  const canvas = h.sent.probes.at(-1);
  assert.equal(canvas.width, 2);
  assert.equal(canvas.height, 2);
  assert.equal(probe.renderer, 'Synthetic hardware adapter');
  probe.close();
  assert.equal(canvas.removed, true);
  assert.equal(h.sent.lostContexts, 1);
  options.noContext = true;
  const absent = m.probeContext(h.nodes.get('#map'));
  assert.equal(absent.renderer, '');
  absent.close();
  assert.equal(h.sent.lostContexts, 1);
  const shown = m.showRenderer('synthetic-renderer');
  assert.equal(h.nodes.get('#renderer').hidden, false);
  assert.equal(h.nodes.get('#renderer').textContent, 'synthetic-renderer');
  assert.equal(h.window.__spike.webglRenderer, 'synthetic-renderer');
  assert.equal(h.window.__spike.phase, 'renderer');
  h.tick(0);
  await shown;
});

test('posting preserves protocol fields and all response failure forms', async () => {
  const options = { missingMap: true, search: '' };
  const h = await pageHarness('', false, false, options);
  for (const [responseText, expected] of [
    [
      '{"ok":true,"path":"synthetic.json","qualification":"synthetic"}',
      { failure: '', path: 'synthetic.json', qualification: 'synthetic' },
    ],
    [
      '{"ok":false,"failure":"synthetic-refusal"}',
      { failure: 'synthetic-refusal', path: '', qualification: '' },
    ],
    ['{}', { failure: 'submission-failed', path: '', qualification: '' }],
    ['{', { failure: 'malformed-payload', path: '', qualification: '' }],
  ]) {
    options.responseText = responseText;
    assert.deepEqual(
      plain(await h.api.postTrace('{"synthetic":true}')),
      expected,
    );
  }
  options.networkError = true;
  assert.deepEqual(plain(await h.api.postTrace('{}')), {
    failure: 'submission-failed',
    path: '',
    qualification: '',
  });
  for (const args of h.sent.opens)
    assert.deepEqual(args, ['POST', '/__perf/trace']);
  for (const args of h.sent.headers)
    assert.deepEqual(args, ['content-type', 'application/json']);
});

test('environment refusal happens before layers, orbit and post', async () => {
  for (const [plant, failure] of [
    ['software-renderer', 'software-renderer'],
    ['remote-renderer', 'remote-renderer'],
    ['capped-frame-rate', 'capped-frame-rate'],
    ['no-webgl2', 'webgl2-unavailable'],
  ]) {
    const h = await pageHarness('', false, false, {
      search: `?profile=gate&plant=${plant}`,
    });
    assert.equal(h.window.__spike.failure, failure);
    assert.equal(h.window.__spike.phase, 'failed');
    assert.equal(h.input, undefined);
    assert.equal(h.orbit, undefined);
    assert.equal(h.requests.length, 0);
    assert.equal(h.window.__spike.hexagonInstances, 0);
    assert.equal(h.window.__spike.particleInstances, 0);
    assert.equal(h.window.__spike.roadInstances, 0);
    assert.equal(h.window.__spike.motionFrames, 0);
    assert.equal(h.window.__spike.hex, false);
    assert.equal(h.window.__spike.particle, false);
    assert.equal(h.window.__spike.road, false);
  }
  const missing = await pageHarness('', false, false, {
    search: '?profile=gate',
    renderer: '',
  });
  assert.equal(missing.window.__spike.failure, 'missing-renderer');
  assert.equal(missing.input, undefined);
});

test('page serialises scene dimensions, flags, failures and empty summaries exactly', async () => {
  const h = await pageHarness('', false, true, { search: '?profile=smoke' });
  assert.equal(h.document.documentElement.lang, 'ar');
  assert.equal(h.document.documentElement.dir, 'rtl');
  assert.equal(h.input.roads, undefined);
  assert.equal(h.input.playback, undefined);
  assert.equal(h.input.cap, 1);
  assert.equal(h.input.showHexagons, true);
  assert.equal(h.input.showParticles, true);
  h.frame(0);
  h.frame(400);
  assert.equal(h.scene.bearing(), 120);
  h.document.hidden = false;
  h.handlers.document.visibilitychange();
  h.handlers.window.resize();
  await h.finish([100, 110, 130]);
  let trace = h.requests.at(-1);
  assert.deepEqual(trace.interruptions, {
    visibilityLost: false,
    resized: false,
    contextLost: false,
  });
  assert.deepEqual(trace.summary, {
    frameCount: 2,
    durationMs: 30,
    percentiles: { p50: 10, p95: 20, p99: 20 },
    shareUnderBudget: 0.5,
  });
  assert.deepEqual(trace.window, { width: 1920, height: 1080 });
  assert.deepEqual(trace.canvas, { cssWidth: 1920, cssHeight: 1080 });
  assert.deepEqual(trace.drawingBuffer, { width: 1920, height: 1080 });
  assert.equal(trace.devicePixelRatio, 1);
  assert.deepEqual(trace.cap, { value: 1, label: 'ASSUMPTION' });
  assert.equal(trace.codeCommit, 'page');
  assert.equal(trace.lockSha256, `sha256:${'ab'.repeat(32)}`);
  assert.equal(trace.userAgent, 'Synthetic headless test');
  assert.equal(trace.webglRenderer, 'Synthetic hardware adapter');
  assert.equal(trace.contract, 'eii.performance-trace');
  assert.equal(trace.version, 1);
  assert.equal(trace.provenance, 'Synthetic');
  assert.equal(trace.seed, 1);
  assert.equal(trace.layerSet, 'hexagons-particles');
  assert.equal(trace.profile, 'smoke');
  assert.deepEqual(trace.counts, { hexagons: 110000, particles: 50000 });
  assert.deepEqual(trace.camera, { completed: true });
  assert.deepEqual(trace.animation, { active: true });
  assert.equal(h.window.__spike.savedPath, 'synthetic-trace.json');
  assert.equal(h.window.__spike.submitFailure, '');
  assert.equal(h.window.__spike.phase, 'done');
  assert.equal(
    h.nodes.get('#result').textContent,
    'native frame-rate gate pending\nshare 0.5\nframes 2\nsynthetic-trace.json',
  );
  h.document.hidden = true;
  h.handlers.document.visibilitychange();
  h.scene.canvas.clientWidth = 1900;
  h.handlers.window.resize();
  h.handlers.contextLost();
  await h.finish([0, 10]);
  trace = h.requests.at(-1);
  assert.deepEqual(trace.interruptions, {
    visibilityLost: true,
    resized: true,
    contextLost: true,
  });
  await h.api.finish(
    h.scene,
    [],
    { visibilityLost: false, resized: false, contextLost: false },
    'no-samples',
    [0, 10],
  );
  trace = h.requests.at(-1);
  assert.deepEqual(trace.timestamps, []);
  assert.deepEqual(trace.summary, {
    frameCount: 0,
    durationMs: 0,
    percentiles: { p50: 0, p95: 0, p99: 0 },
    shareUnderBudget: 0,
  });
  assert.equal(h.window.__spike.shareUnderBudget, null);
  assert.equal(h.window.__spike.positionEnd, 0);
  await h.api.finish(
    h.scene,
    [],
    { visibilityLost: false, resized: false, contextLost: false },
    'fail-submit',
    [0, 10],
  );
  assert.equal(h.requests.at(-1).extra, true);
});

test('scene plants keep explicit load choices and failures visible', async () => {
  for (const [query, hex, particle] of [
    ['plant=hide-hexagons', false, true],
    ['plant=hide-particles', true, false],
    ['isolate=particles', false, true],
    ['isolate=hexagons', true, false],
  ]) {
    const h = await pageHarness('', false, false, {
      search: '?profile=smoke&' + query,
    });
    assert.equal(h.input.showHexagons, hex);
    assert.equal(h.input.showParticles, particle);
  }
  const failure = await pageHarness('', false, false, {
    search: '?profile=smoke',
    mountError: new Error('synthetic map failure'),
  });
  assert.equal(failure.window.__spike.failure, 'synthetic map failure');
  assert.equal(failure.window.__spike.phase, 'failed');
  assert.equal(
    failure.nodes.get('#map-failure').textContent,
    'synthetic map failure',
  );
  const slow = await pageHarness('', false, false, {
    search: '?profile=gate&plant=slow-scene',
  });
  assert.equal(slow.orbit, undefined);
  assert.equal(slow.requests.length, 1);
  assert.deepEqual(
    slow.requests[0].timestamps,
    [0, 50, 100, 150, 200, 250, 300, 350, 400],
  );
  assert.equal(slow.requests[0].summary.shareUnderBudget, 0);
});
