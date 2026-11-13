import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  CONTRACT_VERSION,
  PROFILE_SMOKE,
  PROVENANCE,
  SEED,
  SMOKE_MS,
} from '../config.mjs';
import { startViteServer } from '../server.mjs';
import {
  CAP_LABEL,
  CAP_VALUE,
  CONTRACT,
  HEXAGON_COUNT,
  LAYER_SET_HEXAGONS_PARTICLES,
  PARTICLE_COUNT,
  WALL_CSS_HEIGHT,
  WALL_CSS_WIDTH,
  summariseFrames,
} from '../trace.mjs';

const SPIKE = fileURLToPath(new URL('..', import.meta.url));
const NATIVE_EVIDENCE = fileURLToPath(new URL('../evidence', import.meta.url));
const TRACE_FILE = 'hexagons-particles.rvitex.json';
const STAMP = {
  codeCommit: 'server-stamp',
  lockSha256: `sha256:${'ab'.repeat(32)}`,
};
const PAGE_MARKER = 'Synthetic performance spike';
const MODULE_MARKER = '/__perf/trace';

function filesUnder(dir) {
  if (!fs.existsSync(dir)) return [];
  const found = [];
  const pending = [dir];
  while (pending.length > 0) {
    const current = pending.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) pending.push(full);
      else if (entry.isFile()) found.push(full);
    }
  }
  found.sort();
  return found;
}

function smokeTrace() {
  const timestamps = [0, SMOKE_MS];
  const summary = summariseFrames(timestamps);
  assert.equal(summary.ok, true, summary.failure);
  return {
    contract: CONTRACT,
    version: CONTRACT_VERSION,
    provenance: PROVENANCE,
    seed: SEED,
    layerSet: LAYER_SET_HEXAGONS_PARTICLES,
    profile: PROFILE_SMOKE,
    codeCommit: 'posted-commit',
    lockSha256: `sha256:${'cd'.repeat(32)}`,
    userAgent: 'synthetic-smoke-agent',
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
}

function ask(origin, input) {
  return new Promise((resolve, reject) => {
    const url = new URL(input.path, origin);
    const payload =
      input.body === undefined ? null : Buffer.from(input.body, 'utf8');
    const headers = { host: url.host };
    if (input.originHeader !== null) {
      headers.origin = input.originHeader ?? origin;
    }
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
            type: response.headers['content-type'] ?? '',
            body: Buffer.concat(chunks).toString('utf8'),
          });
        });
      },
    );
    request.setTimeout(2000, () => {
      request.destroy(new Error('timed-out'));
    });
    request.on('error', reject);
    if (payload) request.write(payload);
    request.end();
  });
}

async function withViteServer(check) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-perf-vite-'));
  const sink = path.join(root, 'sink');
  const evidence = path.join(root, 'evidence');
  fs.mkdirSync(evidence);
  const nativeBefore = filesUnder(NATIVE_EVIDENCE);
  let started;
  try {
    started = await startViteServer({
      mode: 'development',
      root: SPIKE,
      sink,
      evidenceDir: evidence,
      native: false,
      stamp: STAMP,
      traceName: () => TRACE_FILE,
    });
    assert.equal(started.ok, true, started.failure);
    await check({
      origin: started.origin,
      sink,
      root,
      nativeBefore,
    });
    const origin = started.origin;
    await started.close();
    started = undefined;
    await assert.rejects(ask(origin, { method: 'GET', path: '/en/_perf' }));
    fs.rmSync(root, { recursive: true, force: true });
    assert.equal(fs.existsSync(root), false);
  } finally {
    if (started !== undefined) await started.close();
    fs.rmSync(root, { recursive: true, force: true });
  }
}

test('the development server stores a posted smoke trace from the page origin', async () => {
  await withViteServer(async ({ origin, sink, root, nativeBefore }) => {
    const page = await ask(origin, { method: 'GET', path: '/en/_perf' });
    assert.equal(page.status, 200);
    assert.match(page.body, new RegExp(PAGE_MARKER));
    const posted = await ask(origin, {
      method: 'POST',
      path: '/__perf/trace',
      body: JSON.stringify(smokeTrace()),
    });
    assert.equal(posted.status, 200, posted.body);
    assert.match(posted.type, /application\/json/);
    const receipt = JSON.parse(posted.body);
    assert.equal(receipt.ok, true);
    assert.equal(receipt.qualification, 'smoke-profile');
    assert.equal(receipt.path, TRACE_FILE);
    const stored = JSON.parse(
      fs.readFileSync(path.join(sink, TRACE_FILE), 'utf8'),
    );
    const expected = smokeTrace();
    expected.codeCommit = STAMP.codeCommit;
    expected.lockSha256 = STAMP.lockSha256;
    assert.deepEqual(stored, expected);
    assert.deepEqual(filesUnder(root), [path.join(sink, TRACE_FILE)]);
    assert.deepEqual(filesUnder(NATIVE_EVIDENCE), nativeBefore);
  });
});

test('the development server refuses a trace posted from another origin', async () => {
  await withViteServer(async ({ origin, sink, root, nativeBefore }) => {
    const posted = await ask(origin, {
      method: 'POST',
      path: '/__perf/trace',
      body: JSON.stringify(smokeTrace()),
      originHeader: 'http://other.invalid',
    });
    assert.equal(posted.status, 403, posted.body);
    assert.equal(JSON.parse(posted.body).failure, 'wrong-origin');
    assert.deepEqual(filesUnder(root), []);
    assert.deepEqual(filesUnder(sink), []);
    assert.deepEqual(filesUnder(NATIVE_EVIDENCE), nativeBefore);
  });
});

test('the development server still serves the page and its module', async () => {
  await withViteServer(async ({ origin }) => {
    const page = await ask(origin, { method: 'GET', path: '/en/_perf' });
    assert.equal(page.status, 200);
    assert.match(page.body, new RegExp(PAGE_MARKER));
    assert.match(page.body, /\/@vite\/client/);
    const module = await ask(origin, { method: 'GET', path: '/main' });
    assert.equal(module.status, 200, module.body);
    assert.match(module.type, /javascript/);
    assert.match(module.body, new RegExp(MODULE_MARKER));
  });
});
