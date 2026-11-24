/**
 * The map boots from one options object. Both controls stay off.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const file = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../src/stage/map-boot.ts',
);
const source = fs.readFileSync(file, 'utf8');

test('map options keep attribution and the logo off', () => {
  assert.match(source, /export const MAP_OPTIONS = \{/);
  assert.match(source, /attributionControl: false/);
  assert.match(source, /maplibreLogo: false/);
  assert.match(source, /\.\.\.MAP_OPTIONS/);
  assert.doesNotMatch(source, /addControl|AttributionControl|LogoControl/);
});
