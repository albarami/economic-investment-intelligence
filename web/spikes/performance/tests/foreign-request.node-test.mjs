import assert from 'node:assert/strict';
import fs from 'node:fs';
import { test } from 'node:test';
import {
  foreignBeforeCommit,
  refuseForeignAfterReady,
} from './foreign-request.mjs';
import { stripComments } from './scene-size.mjs';

const SPEC = new URL('./performance.spec.ts', import.meta.url);
const FOREIGN = 'https://assets.invalid/spike.png';

test('a foreign address seen before the page commits is refused after readiness', () => {
  assert.equal(foreignBeforeCommit(FOREIGN, 'about:blank'), '');
  assert.throws(
    () => refuseForeignAfterReady([FOREIGN], 'http://127.0.0.1:4173'),
    /non-same-origin request: https:\/\/assets\.invalid\/spike\.png/,
  );
});

test('the page helper reaches that scan after readiness', () => {
  const source = stripComments(fs.readFileSync(SPEC, 'utf8'));
  const readyAt = source.indexOf('return ready(page)');
  const scanAt = source.indexOf('refuseForeignAfterReady(seen, origin)');
  assert.ok(readyAt !== -1, 'readiness wait');
  assert.ok(scanAt > readyAt, 'scan after readiness');
});
