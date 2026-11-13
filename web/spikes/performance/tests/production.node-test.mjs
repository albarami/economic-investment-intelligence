import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const web = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../..',
);

const MARKERS = [
  'eii.performance-trace',
  '/__perf/trace',
  '/en/_perf',
  '/ar/_perf',
  'hexagons-particles',
];

export function findSpikeMarkers(text) {
  return MARKERS.filter((marker) => text.includes(marker));
}

function readTree(root) {
  const pending = [root];
  let text = '';
  while (pending.length > 0) {
    const current = pending.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) pending.push(full);
      else if (entry.isFile()) text += fs.readFileSync(full, 'utf8');
    }
  }
  return text;
}

function get(port, route) {
  return new Promise((resolve, reject) => {
    const request = http.request(
      { host: '127.0.0.1', port, path: route, method: 'GET' },
      (response) => {
        response.resume();
        response.on('end', () => resolve(response.statusCode));
      },
    );
    request.on('error', reject);
    request.end();
  });
}

test('a planted marker is found without a build', () => {
  assert.deepEqual(findSpikeMarkers('route /en/_perf'), ['/en/_perf']);
});

test('the production build contains no spike route or contract', async () => {
  const built = spawnSync('npm', ['run', 'build'], {
    cwd: web,
    encoding: 'utf8',
  });
  assert.equal(built.status, 0, `${built.stdout}\n${built.stderr}`);
  const dist = path.join(web, 'dist');
  assert.deepEqual(findSpikeMarkers(readTree(dist)), []);
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? '/', 'http://127.0.0.1');
    const file = path.resolve(dist, `.${url.pathname}`);
    if (!file.startsWith(`${dist}${path.sep}`) && file !== dist) {
      response.writeHead(404);
      response.end('missing');
      return;
    }
    fs.readFile(file, (error, body) => {
      if (error) {
        response.writeHead(404);
        response.end('missing');
        return;
      }
      response.writeHead(200);
      response.end(body);
    });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  if (address === null || typeof address === 'string') {
    server.close();
    throw new Error('production probe did not bind');
  }
  try {
    assert.equal(await get(address.port, '/en/_perf'), 404);
    assert.equal(await get(address.port, '/ar/_perf'), 404);
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});
