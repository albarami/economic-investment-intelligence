import assert from 'node:assert/strict';
import { test } from 'node:test';
import { installsSystemLibraries } from '../system-libraries.mjs';

test('system libraries are installed only when CI is true', () => {
  assert.equal(installsSystemLibraries('true'), true);
  assert.equal(installsSystemLibraries(undefined), false);
  assert.equal(installsSystemLibraries(''), false);
  assert.equal(installsSystemLibraries('false'), false);
});
