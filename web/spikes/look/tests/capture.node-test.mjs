import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { captureLook, captureTarget } from '../capture.mjs';

test('the capture command writes into the ignored overnight folder', () => {
  const target = captureTarget(import.meta.url);
  assert.ok(
    target.split(path.sep).join('/').endsWith('/.overnight/OUT/look'),
    target,
  );
});

test('without the basemap extract the capture fails, names the file and writes nothing', async () => {
  const repository = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-root-'));
  const outDir = path.join(repository, 'out');
  try {
    const result = await captureLook({ outDir, repository });
    assert.equal(result.ok, false);
    assert.match(
      result.detail,
      /missing basemap extract: data\/basemap\/qatar-\*\.pmtiles/,
    );
    assert.equal(fs.existsSync(outDir), false);
  } finally {
    fs.rmSync(repository, { recursive: true, force: true });
  }
});
