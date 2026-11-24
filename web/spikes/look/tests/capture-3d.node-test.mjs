// The capture of the photoreal mode is run by the lead alone, with the key.
// These tests never call Google and never open a browser: with an empty key
// the command refuses before either could happen.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { REFUSED, VIEWS_3D, capture3d } from '../capture-3d.mjs';
import { RELEASE_BLOCK } from '../server.mjs';

test("the 3D capture shows the brief's two views at sixty degrees", () => {
  assert.deepEqual(VIEWS_3D, [
    {
      name: 'westbay',
      center: [51.53, 25.322],
      zoom: 16,
      pitch: 60,
      bearing: -25,
    },
    {
      name: 'lusail',
      center: [51.524, 25.385],
      zoom: 16,
      pitch: 60,
      bearing: 20,
    },
  ]);
});

test('without the key the 3D capture refuses: no browser, no upstream request, no file', async () => {
  const repository = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-3d-'));
  const root = path.join(repository, 'page');
  const outDir = path.join(repository, 'out');
  const sessionFile = path.join(repository, 'photoreal', 'session.json');
  fs.mkdirSync(root);
  fs.writeFileSync(
    path.join(root, 'index.html'),
    `<!doctype html><html><body>${RELEASE_BLOCK}</body></html>`,
  );
  let upstream = 0;
  let launched = 0;
  const lines = [];
  try {
    const result = await capture3d({
      outDir,
      repository,
      serverOptions: {
        apiKey: '',
        sessionFile,
        fetch: async () => {
          upstream += 1;
          throw new Error('a test never calls the upstream');
        },
      },
      build: async () => root,
      remove: () => undefined,
      launch: async () => {
        launched += 1;
        throw new Error('a test never opens a browser here');
      },
      log: (line) => lines.push(line),
    });
    assert.equal(result.ok, false);
    assert.equal(result.detail, REFUSED);
    assert.match(result.detail, /MAPTILE_API_KEY/);
    assert.equal(launched, 0);
    assert.equal(upstream, 0);
    assert.equal(fs.existsSync(outDir), false);
    assert.equal(fs.existsSync(sessionFile), false);
    assert.match(
      lines[0] ?? '',
      /^photoreal counter before: 0 billable root requests of \d+, \d+ remaining/,
    );
  } finally {
    fs.rmSync(repository, { recursive: true, force: true });
  }
});
