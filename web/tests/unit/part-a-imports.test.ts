import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { expect, it } from 'vitest';
import { assertQualifiedImport } from '../../scripts/photoreal-assets.mjs';

it('restricts tile layers, loaders and decoders to the qualified boundary', () => {
  const files = readdirSync('src', {
    recursive: true,
    withFileTypes: true,
  }).filter((entry) => entry.isFile() && /\.[cm]?[jt]sx?$/.test(entry.name));
  for (const file of files) {
    const path = join(file.parentPath, file.name);
    const source = readFileSync(path, 'utf8');
    expect(() => assertQualifiedImport(source, resolve(path))).not.toThrow();
  }
});

it('keeps the deferred renderer reason bilingual and Arabic pending native review', () => {
  const en = JSON.parse(readFileSync('src/i18n/en.json', 'utf8'));
  const ar = JSON.parse(readFileSync('src/i18n/ar.json', 'utf8'));
  expect(en.strings['mapModes.renderer_unavailable']).toBe(
    'Renderer unavailable',
  );
  expect(ar.strings['mapModes.renderer_unavailable']).toBe(
    'عارض المشهد غير متاح',
  );
  expect(ar.review['mapModes.renderer_unavailable']).toBe(
    'pending-native-review',
  );
});

it('rejects a planted unqualified import in the same build guard', () => {
  expect(() =>
    assertQualifiedImport(
      "import { Tile3DLayer } from '@deck.gl/geo-layers';",
      resolve('src/stage/plant.ts'),
    ),
  ).toThrow('unqualified-photoreal-import');
});
