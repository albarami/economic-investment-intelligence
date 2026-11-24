import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { runSuite } from './run.mjs';

test('the look browser suite passes in the headless shell', async () => {
  const failures = [];
  const status = await runSuite({
    onFailure: (names) => failures.push(...names),
  });
  assert.equal(status, 0, `Failed browser cases:\n${failures.join('\n')}`);
});

// Ruling L-119 item 3: without the extract (the hosted job has none) the
// page stands on plain land with no lit unit, and every browser test passes.
test('the look browser suite passes without the basemap extract', async () => {
  const bare = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-bare-'));
  try {
    assert.equal(fs.existsSync(path.join(bare, 'data', 'basemap')), false);
    const failures = [];
    const status = await runSuite({
      repositoryRoot: bare,
      onFailure: (names) => failures.push(...names),
    });
    assert.equal(status, 0, `Failed browser cases:\n${failures.join('\n')}`);
  } finally {
    fs.rmSync(bare, { recursive: true, force: true });
  }
});
