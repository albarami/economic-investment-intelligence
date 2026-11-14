import assert from 'node:assert/strict';
import fs from 'node:fs';
import { test } from 'node:test';
import {
  foreignBeforeCommit,
  foreignRequest,
  refuseForeignAfterReady,
} from './foreign-request.mjs';
import { stripComments } from './scene-size.mjs';

const SPEC = new URL('./performance.spec.ts', import.meta.url);
const FOREIGN = 'https://assets.invalid/spike.png';
const ORIGIN = 'http://127.0.0.1:4173';

test('a foreign address seen before the page commits is refused after readiness', () => {
  assert.equal(foreignBeforeCommit(FOREIGN, 'about:blank'), '');
  assert.throws(
    () => refuseForeignAfterReady([FOREIGN], ORIGIN),
    /non-same-origin request: https:\/\/assets\.invalid\/spike\.png/,
  );
});

test('unknown or file request schemes are refused rather than ignored', () => {
  assert.equal(foreignRequest('data:image/png;base64,AAAA', ORIGIN), '');
  assert.equal(foreignRequest('blob:http://127.0.0.1:4173/asset', ORIGIN), '');
  for (const url of [
    'ftp://example.invalid/tile.pbf',
    'ws://127.0.0.1:4173/socket',
    'wss://example.invalid/socket',
    'file:///synthetic.txt',
    'not a url',
  ]) {
    assert.equal(foreignRequest(url, ORIGIN), url);
    assert.throws(
      () => refuseForeignAfterReady([url], ORIGIN),
      /non-same-origin request:/,
    );
  }
});

test('the page helper reaches that scan after readiness', () => {
  const source = stripComments(fs.readFileSync(SPEC, 'utf8'));
  const readyAt = source.indexOf('return ready(page)');
  const scanAt = source.indexOf('refuseForeignAfterReady(seen, origin)');
  assert.ok(readyAt !== -1, 'readiness wait');
  assert.ok(scanAt > readyAt, 'scan after readiness');
});
