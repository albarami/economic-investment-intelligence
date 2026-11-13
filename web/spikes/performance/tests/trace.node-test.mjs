import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import {
  CAP_LABEL,
  CAP_VALUE,
  CONTRACT,
  FRAME_BUDGET_MS,
  HEXAGON_COUNT,
  LAYER_SET_HEXAGONS_PARTICLES,
  ORBIT_MS,
  PARTICLE_COUNT,
  PROFILE_GATE,
  SHARE_MINIMUM,
  WALL_CSS_HEIGHT,
  WALL_CSS_WIDTH,
  readUnmaskedRenderer,
  summariseFrames,
  validateGate,
} from '../trace.mjs';
import {
  MAX_BODY_BYTES,
  assertDevelopment,
  startStaticServer,
} from '../server.mjs';
import { verifyEvidence } from '../verify-evidence.mjs';

const LAYER = LAYER_SET_HEXAGONS_PARTICLES;

function last(values) {
  return values[values.length - 1];
}

function summariseOk(timestamps) {
  const result = summariseFrames(timestamps);
  assert.equal(result.ok, true, result.failure);
  return result;
}

test('the budget and the share minimum are the spike gate', () => {
  assert.equal(FRAME_BUDGET_MS, 16.7);
  assert.equal(SHARE_MINIMUM, 0.95);
  assert.equal(HEXAGON_COUNT, 110000);
  assert.equal(PARTICLE_COUNT, 50000);
  assert.equal(WALL_CSS_WIDTH, 1920);
  assert.equal(WALL_CSS_HEIGHT, 1080);
  assert.equal(CAP_VALUE, 1);
  assert.equal(CAP_LABEL, 'ASSUMPTION');
  assert.equal(ORBIT_MS, 30000);
});

test('nearest rank uses the ceiling rank', () => {
  const result = summariseOk([0, 10, 30, 60, 100]);
  assert.equal(result.frameCount, 4);
  assert.equal(result.durationMs, 100);
  assert.deepEqual(result.intervals, [10, 20, 30, 40]);
  assert.equal(result.percentiles.p50, 20);
  assert.equal(result.percentiles.p95, 40);
  assert.equal(result.percentiles.p99, 40);
});

test('the share is the unrounded count strictly under the budget', () => {
  const timestamps = [0];
  for (let index = 0; index < 95; index += 1) {
    timestamps.push(last(timestamps) + 10);
  }
  for (let index = 0; index < 5; index += 1) {
    timestamps.push(last(timestamps) + 20);
  }
  const result = summariseOk(timestamps);
  assert.equal(result.frameCount, 100);
  assert.equal(result.shareUnderBudget, 0.95);
});

test('a frame at the budget is outside the share', () => {
  const alone = summariseOk([0, FRAME_BUDGET_MS]);
  assert.equal(alone.intervals[0], FRAME_BUDGET_MS);
  assert.equal(alone.shareUnderBudget, 0);
  const timestamps = [0, FRAME_BUDGET_MS];
  let cursor = FRAME_BUDGET_MS;
  for (let index = 0; index < 18; index += 1) {
    cursor += 10;
    timestamps.push(cursor);
  }
  timestamps.push(cursor + 20);
  const result = summariseOk(timestamps);
  assert.equal(result.frameCount, 20);
  assert.equal(result.intervals[0], FRAME_BUDGET_MS);
  assert.equal(result.shareUnderBudget, 0.9);
});

test('empty, non-finite and non-increasing timestamps are refused', () => {
  assert.equal(summariseFrames([]).failure, 'empty-timestamps');
  assert.equal(summariseFrames([0]).failure, 'empty-timestamps');
  assert.equal(summariseFrames(null).failure, 'invalid-timestamps');
  assert.equal(
    summariseFrames([0, Number.NaN]).failure,
    'non-finite-timestamp',
  );
  assert.equal(
    summariseFrames([0, Number.POSITIVE_INFINITY]).failure,
    'non-finite-timestamp',
  );
  assert.equal(summariseFrames([0, '10']).failure, 'non-finite-timestamp');
  assert.equal(
    summariseFrames([0, 10, 10]).failure,
    'non-increasing-timestamps',
  );
  assert.equal(
    summariseFrames([0, 10, 9]).failure,
    'non-increasing-timestamps',
  );
});

function fastOrbit() {
  const frames = ORBIT_MS / 15;
  const timestamps = [];
  for (let index = 0; index <= frames; index += 1) timestamps.push(index * 15);
  return timestamps;
}

function captureRecord() {
  return {
    role: 'owner',
    host: 'windows-native',
    browser: 'chrome',
    tracePath:
      'web/spikes/performance/evidence/hexagons-particles.rfixture.json',
    sha256: `sha256:${'ab'.repeat(32)}`,
  };
}

function gateTrace(patch) {
  const timestamps = fastOrbit();
  const summary = summariseOk(timestamps);
  const trace = {
    contract: CONTRACT,
    version: 1,
    provenance: 'Synthetic',
    seed: 1,
    layerSet: LAYER,
    profile: PROFILE_GATE,
    codeCommit: 'fixture',
    lockSha256: `sha256:${'cd'.repeat(32)}`,
    userAgent:
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    webglRenderer: 'ANGLE (NVIDIA, synthetic adapter)',
    window: { width: 1600, height: 900 },
    canvas: { cssWidth: WALL_CSS_WIDTH, cssHeight: WALL_CSS_HEIGHT },
    drawingBuffer: {
      width: WALL_CSS_WIDTH * CAP_VALUE,
      height: WALL_CSS_HEIGHT * CAP_VALUE,
    },
    devicePixelRatio: 2,
    cap: { value: CAP_VALUE, label: CAP_LABEL },
    counts: { hexagons: HEXAGON_COUNT, particles: PARTICLE_COUNT },
    timestamps,
    summary: {
      frameCount: summary.frameCount,
      durationMs: summary.durationMs,
      percentiles: summary.percentiles,
      shareUnderBudget: summary.shareUnderBudget,
    },
    camera: { completed: true },
    animation: { active: true },
    interruptions: {
      visibilityLost: false,
      resized: false,
      contextLost: false,
    },
  };
  return patch === undefined ? trace : patch(trace);
}

test('a complete native trace passes the gate', () => {
  const result = validateGate(gateTrace(), LAYER, captureRecord());
  assert.equal(result.ok, true, result.failure);
  const edge = validateGate(
    gateTrace((trace) => ({
      ...trace,
      userAgent:
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    })),
    LAYER,
    { ...captureRecord(), browser: 'edge' },
  );
  assert.equal(edge.ok, true, edge.failure);
});

test('a native trace on the Microsoft Basic Render Driver is refused as a software renderer', () => {
  const result = validateGate(
    gateTrace((trace) => ({
      ...trace,
      webglRenderer: 'Microsoft Basic Render Driver',
    })),
    LAYER,
    captureRecord(),
  );
  assert.equal(result.failure, 'software-renderer');
});

test('a native trace whose renderer names WARP as its own word is refused', () => {
  const warped = validateGate(
    gateTrace((trace) => ({
      ...trace,
      webglRenderer: 'ANGLE (synthetic, D3D11 WARP)',
    })),
    LAYER,
    captureRecord(),
  );
  assert.equal(warped.failure, 'software-renderer');
});

test('a renderer word that merely contains the letters warp still passes the gate', () => {
  const inside = validateGate(
    gateTrace((trace) => ({
      ...trace,
      webglRenderer: 'Synthetic warping adapter',
    })),
    LAYER,
    captureRecord(),
  );
  assert.equal(inside.ok, true, inside.failure);
});

test('the renderer reading returns the unmasked value when it differs from the masked one', () => {
  const masked = 'Masked synthetic renderer';
  const unmasked = 'Unmasked synthetic adapter';
  const context = {
    RENDERER: 0x1f01,
    getExtension(name) {
      if (name !== 'WEBGL_debug_renderer_info') return null;
      return { UNMASKED_RENDERER_WEBGL: 0x9246 };
    },
    getParameter(parameter) {
      if (parameter === 0x1f01) return masked;
      if (parameter === 0x9246) return unmasked;
      return null;
    },
  };
  assert.notEqual(masked, unmasked);
  assert.equal(readUnmaskedRenderer(context), unmasked);
  const hidden = {
    RENDERER: 0x1f01,
    getExtension() {
      return null;
    },
    getParameter(parameter) {
      if (parameter === 0x1f01) return masked;
      return unmasked;
    },
  };
  assert.equal(readUnmaskedRenderer(hidden), '');
});

test('a headless Windows user agent is refused as non-native', () => {
  const result = validateGate(
    gateTrace((trace) => ({
      ...trace,
      userAgent:
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/120.0.0.0 Safari/537.36',
    })),
    LAYER,
    captureRecord(),
  );
  assert.equal(result.failure, 'non-native');
});

test('the gate rejects each disqualifying trace by name', () => {
  const cases = [
    ['unknown-field', (trace) => ({ ...trace, extra: true })],
    [
      'missing-field',
      (trace) => {
        const next = { ...trace };
        delete next.seed;
        return next;
      },
    ],
    ['unknown-layer-set', (trace) => trace, 'roads'],
    ['layer-set-mismatch', (trace) => ({ ...trace, layerSet: 'roads' })],
    [
      'reduced-counts',
      (trace) => ({
        ...trace,
        counts: { hexagons: HEXAGON_COUNT - 1, particles: PARTICLE_COUNT },
      }),
    ],
    [
      'reduced-counts',
      (trace) => ({
        ...trace,
        counts: { hexagons: HEXAGON_COUNT, particles: PARTICLE_COUNT - 1 },
      }),
    ],
    ['wrong-contract', (trace) => ({ ...trace, contract: 'other' })],
    ['wrong-version', (trace) => ({ ...trace, version: 2 })],
    ['wrong-provenance', (trace) => ({ ...trace, provenance: 'Public' })],
    ['wrong-seed', (trace) => ({ ...trace, seed: 2 })],
    ['missing-commit', (trace) => ({ ...trace, codeCommit: '' })],
    ['missing-lock', (trace) => ({ ...trace, lockSha256: 'sha256:abcd' })],
    [
      'missing-window',
      (trace) => ({ ...trace, window: { width: 0, height: 900 } }),
    ],
    ['missing-ratio', (trace) => ({ ...trace, devicePixelRatio: 0 })],
    ['client-path', (trace) => ({ ...trace, path: 'evidence/chosen.json' })],
    [
      'wrong-viewport',
      (trace) => ({
        ...trace,
        canvas: { cssWidth: WALL_CSS_WIDTH - 1, cssHeight: WALL_CSS_HEIGHT },
      }),
    ],
    [
      'wrong-cap',
      (trace) => ({ ...trace, cap: { value: 2, label: CAP_LABEL } }),
    ],
    [
      'wrong-cap',
      (trace) => ({ ...trace, cap: { value: CAP_VALUE, label: 'tuned' } }),
    ],
    [
      'dimension-mismatch',
      (trace) => ({
        ...trace,
        drawingBuffer: {
          width: WALL_CSS_WIDTH * 2,
          height: WALL_CSS_HEIGHT * 2,
        },
      }),
    ],
    ['smoke-profile', (trace) => ({ ...trace, profile: 'smoke' })],
    ['unknown-profile', (trace) => ({ ...trace, profile: 'tuned' })],
    [
      'incomplete-orbit',
      (trace) => ({ ...trace, camera: { completed: false } }),
    ],
    [
      'stopped-animation',
      (trace) => ({ ...trace, animation: { active: false } }),
    ],
    [
      'visibility-lost',
      (trace) => ({
        ...trace,
        interruptions: { ...trace.interruptions, visibilityLost: true },
      }),
    ],
    [
      'resized',
      (trace) => ({
        ...trace,
        interruptions: { ...trace.interruptions, resized: true },
      }),
    ],
    [
      'context-lost',
      (trace) => ({
        ...trace,
        interruptions: { ...trace.interruptions, contextLost: true },
      }),
    ],
    ['missing-renderer', (trace) => ({ ...trace, webglRenderer: '' })],
    ['software-renderer', (trace) => ({ ...trace, webglRenderer: 'llvmpipe' })],
    [
      'software-renderer',
      (trace) => ({ ...trace, webglRenderer: 'Google SwiftShader' }),
    ],
    [
      'non-native',
      (trace) => trace,
      LAYER,
      { ...captureRecord(), host: 'wsl' },
    ],
    [
      'non-native',
      (trace) => ({
        ...trace,
        userAgent: 'Mozilla/5.0 (X11; Linux x86_64) HeadlessChrome/120.0.0.0',
      }),
    ],
    [
      'forged-summary',
      (trace) => ({
        ...trace,
        summary: { ...trace.summary, shareUnderBudget: 0.5 },
      }),
    ],
  ];
  for (const [failure, patch, descriptor, capture] of cases) {
    const result = validateGate(
      patch(gateTrace()),
      descriptor ?? LAYER,
      capture ?? captureRecord(),
    );
    assert.equal(result.ok, false, failure);
    assert.equal(result.failure, failure);
  }
});

test('a short orbit is refused even when every frame is fast', () => {
  const timestamps = [0, 15, 30, 45];
  const summary = summariseOk(timestamps);
  const trace = gateTrace();
  trace.timestamps = timestamps;
  trace.summary = {
    frameCount: summary.frameCount,
    durationMs: summary.durationMs,
    percentiles: summary.percentiles,
    shareUnderBudget: summary.shareUnderBudget,
  };
  const result = validateGate(trace, LAYER, captureRecord());
  assert.equal(result.failure, 'short-orbit');
});

test('a slow trace keeps its measured share and fails the frame-rate gate', () => {
  const frames = 600;
  const timestamps = [];
  for (let index = 0; index <= frames; index += 1) timestamps.push(index * 50);
  const summary = summariseOk(timestamps);
  assert.equal(summary.durationMs, 30000);
  assert.equal(summary.shareUnderBudget, 0);
  const trace = gateTrace();
  trace.timestamps = timestamps;
  trace.summary = {
    frameCount: summary.frameCount,
    durationMs: summary.durationMs,
    percentiles: summary.percentiles,
    shareUnderBudget: summary.shareUnderBudget,
  };
  const result = validateGate(trace, LAYER, captureRecord());
  assert.equal(result.ok, false);
  assert.equal(result.failure, 'frame-rate');
});

function slowTrace() {
  const frames = 600;
  const timestamps = [];
  for (let index = 0; index <= frames; index += 1) timestamps.push(index * 50);
  const summary = summariseOk(timestamps);
  const trace = gateTrace();
  trace.timestamps = timestamps;
  trace.summary = {
    frameCount: summary.frameCount,
    durationMs: summary.durationMs,
    percentiles: summary.percentiles,
    shareUnderBudget: summary.shareUnderBudget,
  };
  return trace;
}

function ask(origin, input) {
  return new Promise((resolve, reject) => {
    const url = new URL(input.path, origin);
    const payload =
      input.body === undefined ? null : Buffer.from(input.body, 'utf8');
    const headers = { host: url.host };
    if (input.originHeader !== null)
      headers.origin = input.originHeader ?? origin;
    if (payload) {
      headers['content-type'] = 'application/json';
      headers['content-length'] = String(payload.length);
    }
    const request = http.request(
      {
        hostname: '127.0.0.1',
        port: url.port,
        path: `${url.pathname}${url.search}`,
        method: input.method,
        headers,
      },
      (response) => {
        const chunks = [];
        response.on('data', (chunk) => chunks.push(chunk));
        response.on('end', () => {
          resolve({
            status: response.statusCode,
            body: Buffer.concat(chunks).toString('utf8'),
          });
        });
      },
    );
    request.on('error', reject);
    if (payload) request.write(payload);
    request.end();
  });
}

test('production mode is refused before the server listens', () => {
  const refused = assertDevelopment('production');
  assert.equal(refused.ok, false);
  assert.equal(refused.failure, 'non-development');
  assert.equal(assertDevelopment('development').ok, true);
});

test('the trace server records a failed measurement and refuses a bad post', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-perf-'));
  const sink = path.join(root, 'sink');
  const evidence = path.join(root, 'evidence');
  fs.mkdirSync(evidence);
  fs.writeFileSync(path.join(root, 'index.html'), '<p>synthetic spike</p>\n');
  const started = await startStaticServer({
    mode: 'development',
    root,
    sink,
    evidenceDir: evidence,
    native: false,
  });
  assert.equal(started.ok, true, started.failure);
  try {
    const page = await ask(started.origin, {
      method: 'GET',
      path: '/en/_perf',
    });
    assert.equal(page.status, 200);
    assert.match(page.body, /synthetic spike/);
    const arabic = await ask(started.origin, {
      method: 'GET',
      path: '/ar/_perf',
    });
    assert.equal(arabic.status, 200);
    const unknown = await ask(started.origin, {
      method: 'GET',
      path: '/en/other',
    });
    assert.equal(unknown.status, 404);
    assert.equal(unknown.body, 'unknown-route');
    const method = await ask(started.origin, {
      method: 'GET',
      path: '/__perf/trace',
    });
    assert.equal(method.status, 405);
    const posted = await ask(started.origin, {
      method: 'POST',
      path: '/__perf/trace',
      body: JSON.stringify(slowTrace()),
    });
    assert.equal(posted.status, 200, posted.body);
    const receipt = JSON.parse(posted.body);
    assert.equal(receipt.ok, true);
    assert.equal(receipt.path.includes('evidence'), false);
    const saved = JSON.parse(
      fs.readFileSync(path.join(sink, receipt.path), 'utf8'),
    );
    assert.equal(
      validateGate(saved, LAYER, captureRecord()).failure,
      'frame-rate',
    );
    const before = fs.readdirSync(sink);
    const rejected = await ask(started.origin, {
      method: 'POST',
      path: '/__perf/trace',
      body: JSON.stringify({ ...slowTrace(), extra: true }),
    });
    assert.equal(JSON.parse(rejected.body).failure, 'unknown-field');
    const clientPath = await ask(started.origin, {
      method: 'POST',
      path: '/__perf/trace',
      body: JSON.stringify({ ...slowTrace(), path: 'evidence/chosen.json' }),
    });
    assert.equal(JSON.parse(clientPath.body).failure, 'client-path');
    const foreign = await ask(started.origin, {
      method: 'POST',
      path: '/__perf/trace',
      body: JSON.stringify(slowTrace()),
      originHeader: 'http://evil.invalid',
    });
    assert.equal(JSON.parse(foreign.body).failure, 'wrong-origin');
    const malformed = await ask(started.origin, {
      method: 'POST',
      path: '/__perf/trace',
      body: '{',
    });
    assert.equal(JSON.parse(malformed.body).failure, 'malformed-payload');
    const traversal = slowTrace();
    traversal.layerSet = '../secret';
    const escaped = await ask(started.origin, {
      method: 'POST',
      path: '/__perf/trace',
      body: JSON.stringify(traversal),
    });
    assert.equal(JSON.parse(escaped.body).failure, 'unknown-layer-set');
    assert.deepEqual(fs.readdirSync(sink), before);
  } finally {
    await started.close();
    fs.rmSync(root, { recursive: true, force: true });
  }
});

function bodyJustAbove(limit) {
  const trace = slowTrace();
  trace.userAgent = 'x';
  const base = Buffer.byteLength(JSON.stringify(trace));
  trace.userAgent = 'x'.repeat(limit - base + 2);
  const body = JSON.stringify(trace);
  assert.equal(Buffer.byteLength(body), limit + 1);
  return body;
}

test('a post just above the body limit is refused by name and writes nothing', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-perf-limit-'));
  const sink = path.join(root, 'sink');
  const evidence = path.join(root, 'evidence');
  fs.mkdirSync(evidence);
  fs.writeFileSync(path.join(root, 'index.html'), '<p>synthetic spike</p>\n');
  const started = await startStaticServer({
    mode: 'development',
    root,
    sink,
    evidenceDir: evidence,
    native: false,
  });
  assert.equal(started.ok, true, started.failure);
  try {
    const before = fs.existsSync(sink) ? fs.readdirSync(sink) : [];
    const refused = await ask(started.origin, {
      method: 'POST',
      path: '/__perf/trace',
      body: bodyJustAbove(MAX_BODY_BYTES),
    });
    assert.equal(refused.status, 400);
    assert.equal(JSON.parse(refused.body).failure, 'malformed-payload');
    const after = fs.existsSync(sink) ? fs.readdirSync(sink) : [];
    assert.deepEqual(after, before);
  } finally {
    await started.close();
    fs.rmSync(root, { recursive: true, force: true });
  }
});

const KEPT_TRACE = Buffer.from('synthetic-kept-trace\n');
const COLLIDING_NAME = 'hexagons-particles.rcollxkept.json';
const FRESH_NAME = 'hexagons-particles.rfreshxkept.json';

async function withTraceName(traceName, check) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-perf-name-'));
  const sink = path.join(root, 'sink');
  const evidence = path.join(root, 'evidence');
  fs.mkdirSync(sink);
  fs.mkdirSync(evidence);
  fs.writeFileSync(path.join(sink, COLLIDING_NAME), KEPT_TRACE);
  fs.writeFileSync(path.join(root, 'index.html'), '<p>synthetic spike</p>\n');
  const started = await startStaticServer({
    mode: 'development',
    root,
    sink,
    evidenceDir: evidence,
    native: false,
    traceName,
  });
  assert.equal(started.ok, true, started.failure);
  try {
    await check({ origin: started.origin, sink });
  } finally {
    await started.close();
    fs.rmSync(root, { recursive: true, force: true });
  }
}

test('a colliding trace name leaves the existing file unchanged and writes another name', async () => {
  let calls = 0;
  await withTraceName(
    () => {
      calls += 1;
      return calls === 1 ? COLLIDING_NAME : FRESH_NAME;
    },
    async ({ origin, sink }) => {
      const posted = await ask(origin, {
        method: 'POST',
        path: '/__perf/trace',
        body: JSON.stringify(slowTrace()),
      });
      assert.equal(posted.status, 200, posted.body);
      const receipt = JSON.parse(posted.body);
      assert.equal(receipt.path, FRESH_NAME);
      assert.notEqual(receipt.path, COLLIDING_NAME);
      assert.deepEqual(
        fs.readFileSync(path.join(sink, COLLIDING_NAME)),
        KEPT_TRACE,
      );
      const saved = JSON.parse(
        fs.readFileSync(path.join(sink, FRESH_NAME), 'utf8'),
      );
      assert.equal(saved.layerSet, LAYER);
    },
  );
});

test('a generator that always collides is refused by name and writes nothing', async () => {
  await withTraceName(
    () => COLLIDING_NAME,
    async ({ origin, sink }) => {
      const refused = await ask(origin, {
        method: 'POST',
        path: '/__perf/trace',
        body: JSON.stringify(slowTrace()),
      });
      assert.equal(refused.status, 400);
      assert.equal(JSON.parse(refused.body).failure, 'trace-name-collision');
      assert.deepEqual(fs.readdirSync(sink), [COLLIDING_NAME]);
      assert.deepEqual(
        fs.readFileSync(path.join(sink, COLLIDING_NAME)),
        KEPT_TRACE,
      );
    },
  );
});

test('a test server cannot write the native evidence directory', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-perf-native-'));
  const evidence = path.join(root, 'evidence');
  fs.mkdirSync(evidence);
  const started = await startStaticServer({
    mode: 'development',
    root,
    sink: evidence,
    evidenceDir: evidence,
    native: false,
  });
  assert.equal(started.ok, false);
  assert.equal(started.failure, 'native-evidence-protected');
  fs.rmSync(root, { recursive: true, force: true });
});

function plantEvidence(trace, hash) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-perf-evidence-'));
  const relative =
    'web/spikes/performance/evidence/hexagons-particles.rfix01.json';
  const file = path.join(root, relative);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(trace)}\n`);
  const sha =
    hash ??
    `sha256:${createHash('sha256').update(fs.readFileSync(file)).digest('hex')}`;
  fs.writeFileSync(
    path.join(path.dirname(file), 'native-capture.md'),
    [
      'role: owner',
      'date: 2026-11-13',
      'host: windows-native',
      'browser: chrome',
      `trace: ${relative}`,
      `sha256: ${sha}`,
      '',
    ].join('\n'),
  );
  return { root, evidenceDir: path.dirname(file) };
}

test('the evidence command names a missing native trace and planted faults', () => {
  const empty = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-perf-empty-'));
  const evidenceDir = path.join(empty, 'evidence');
  fs.mkdirSync(evidenceDir);
  assert.equal(
    verifyEvidence({ root: empty, evidenceDir, git: () => 'clean' }).failure,
    'missing-native-trace',
  );
  fs.rmSync(empty, { recursive: true, force: true });

  const slow = plantEvidence(slowTrace());
  assert.equal(
    verifyEvidence({ ...slow, git: () => 'untracked' }).failure,
    'uncommitted-trace',
  );
  assert.equal(
    verifyEvidence({ ...slow, git: () => 'changed' }).failure,
    'changed-trace',
  );
  const mismatched = plantEvidence(slowTrace(), `sha256:${'ab'.repeat(32)}`);
  assert.equal(
    verifyEvidence({ ...mismatched, git: () => 'clean' }).failure,
    'changed-trace',
  );
  assert.equal(
    verifyEvidence({ ...slow, git: () => 'clean' }).failure,
    'frame-rate',
  );
  const passing = plantEvidence(gateTrace());
  assert.equal(verifyEvidence({ ...passing, git: () => 'clean' }).ok, true);
  fs.rmSync(slow.root, { recursive: true, force: true });
  fs.rmSync(mismatched.root, { recursive: true, force: true });
  fs.rmSync(passing.root, { recursive: true, force: true });
});
