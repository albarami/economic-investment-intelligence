import assert from 'node:assert/strict';
import { test } from 'node:test';
import { runSuite } from './run.mjs';

test('the browser suite reports counts and the recorder contract', async () => {
  const status = await runSuite();
  assert.equal(status, 0);
});
