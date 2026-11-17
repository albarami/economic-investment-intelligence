import { temporaryFolder } from './temporary-folder.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { CSP } from '../../glyphs/guards.mjs';
import { startStaticServer, startViteServer } from '../server.mjs';

const SPIKE = fileURLToPath(new URL('..', import.meta.url));
const OPENER = 'cross-origin-opener-policy';
const EMBEDDER = 'cross-origin-embedder-policy';
const OPENER_VALUE = 'same-origin';
const EMBEDDER_VALUE = 'require-corp';

function requireIsolation(headers) {
  assert.equal(headers[OPENER], OPENER_VALUE);
  assert.equal(headers[EMBEDDER], EMBEDDER_VALUE);
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
            headers: response.headers,
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

function assertDocumentHeaders(response) {
  assert.equal(response.status, 200, response.body);
  requireIsolation(response.headers);
  assert.equal(response.headers['cache-control'], 'no-store');
  assert.equal(response.headers['content-security-policy'], CSP);
}

test('an isolation check fails when either header is missing', () => {
  assert.throws(() =>
    requireIsolation({
      [OPENER]: OPENER_VALUE,
    }),
  );
  assert.throws(() =>
    requireIsolation({
      [EMBEDDER]: EMBEDDER_VALUE,
    }),
  );
  assert.throws(() =>
    requireIsolation({
      [OPENER]: 'unsafe-none',
      [EMBEDDER]: EMBEDDER_VALUE,
    }),
  );
  assert.throws(() =>
    requireIsolation({
      [OPENER]: OPENER_VALUE,
      [EMBEDDER]: 'credentialless',
    }),
  );
});

test('the static server isolates the document, an asset and the trace routes', async () => {
  const root = temporaryFolder('eii-perf-static-');
  const sink = path.join(root, 'sink');
  const evidence = path.join(root, 'evidence');
  fs.mkdirSync(evidence);
  fs.writeFileSync(path.join(root, 'index.html'), '<p>synthetic spike</p>\n');
  fs.writeFileSync(path.join(root, 'asset.js'), 'synthetic asset\n');
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
    assertDocumentHeaders(page);
    const asset = await ask(started.origin, {
      method: 'GET',
      path: '/asset.js',
    });
    assert.equal(asset.status, 200, asset.body);
    requireIsolation(asset.headers);
    assert.equal(asset.headers['content-security-policy'], CSP);
    assert.equal(asset.headers['cache-control'], 'no-store');
    const trace = await ask(started.origin, {
      method: 'POST',
      path: '/__perf/trace',
      body: '{',
    });
    assert.equal(trace.status, 400, trace.body);
    requireIsolation(trace.headers);
    assert.equal(trace.headers['content-security-policy'], CSP);
    assert.equal(trace.headers['cache-control'], 'no-store');
    const posts = await ask(started.origin, {
      method: 'GET',
      path: '/__perf/posts',
    });
    assert.equal(posts.status, 200, posts.body);
    requireIsolation(posts.headers);
  } finally {
    await started.close();
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('the development server isolates the document, an asset and the trace routes', async () => {
  const root = temporaryFolder('eii-perf-vite-');
  const sink = path.join(root, 'sink');
  const evidence = path.join(root, 'evidence');
  fs.mkdirSync(evidence);
  const started = await startViteServer({
    mode: 'development',
    root: SPIKE,
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
    assert.equal(page.status, 200, page.body);
    requireIsolation(page.headers);
    const asset = await ask(started.origin, {
      method: 'GET',
      path: '/style.css',
    });
    assert.equal(asset.status, 200, asset.body);
    requireIsolation(asset.headers);
    const trace = await ask(started.origin, {
      method: 'POST',
      path: '/__perf/trace',
      body: '{',
    });
    assert.equal(trace.status, 400, trace.body);
    requireIsolation(trace.headers);
    const posts = await ask(started.origin, {
      method: 'GET',
      path: '/__perf/posts',
    });
    assert.equal(posts.status, 200, posts.body);
    requireIsolation(posts.headers);
  } finally {
    await started.close();
    fs.rmSync(root, { recursive: true, force: true });
  }
});
