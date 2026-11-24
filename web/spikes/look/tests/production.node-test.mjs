import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { findMarkers } from '../guards.mjs';

const web = path.resolve(import.meta.dirname, '../../..');

function readTree(root) {
  const pending = [root];
  let text = '';
  while (pending.length > 0) {
    const current = pending.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) pending.push(full);
      else if (entry.isFile()) text += fs.readFileSync(full, 'latin1');
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
  assert.deepEqual(findMarkers('route /ar/_look here'), ['/ar/_look']);
  assert.deepEqual(findMarkers('eii-look-proof'), ['eii-look-proof']);
});

test('the production build holds nothing of the look page', async () => {
  // The production build of web/ with its own configuration, written to a
  // temporary folder so that no other test's dist/ is touched.
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-prod-'));
  try {
    const built = spawnSync(
      process.execPath,
      [
        path.join(web, 'node_modules', 'vite', 'bin', 'vite.js'),
        'build',
        '--outDir',
        outDir,
        '--emptyOutDir',
      ],
      { cwd: web, encoding: 'utf8' },
    );
    assert.equal(built.status, 0, `${built.stdout}\n${built.stderr}`);
    assert.ok(fs.existsSync(path.join(outDir, 'index.html')));
    assert.deepEqual(findMarkers(readTree(outDir)), []);
    const server = http.createServer((request, response) => {
      const url = new URL(request.url ?? '/', 'http://127.0.0.1');
      const file = path.resolve(outDir, `.${url.pathname}`);
      if (!file.startsWith(`${outDir}${path.sep}`)) {
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
    try {
      if (address === null || typeof address === 'string') {
        throw new Error('production probe did not bind');
      }
      assert.equal(await get(address.port, '/en/_look'), 404);
      assert.equal(await get(address.port, '/ar/_look'), 404);
    } finally {
      await new Promise((resolve) => server.close(resolve));
    }
  } finally {
    fs.rmSync(outDir, { recursive: true, force: true });
  }
});
