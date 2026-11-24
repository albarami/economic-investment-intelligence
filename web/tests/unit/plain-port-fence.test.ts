import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const SRC = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../src',
);

function sources(dir: string): string[] {
  const found: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) {
      found.push(...sources(full));
      continue;
    }
    if (name.endsWith('.ts') || name.endsWith('.tsx')) found.push(full);
  }
  return found;
}

const FRACTION = [
  /longitude[^\n]{0,48}\*[^\n]{0,48}width/,
  /latitude[^\n]{0,48}\*[^\n]{0,48}height/,
  /\.x\s*\/\s*[^\n;]{0,48}width/,
  /\.y\s*\/\s*[^\n;]{0,48}height/,
  /plainPort/,
  /portForPlate/,
  /plain-port/,
  /eii-fixture-plain-port/,
];

describe('plain port fence', () => {
  it('keeps plainPort out of production sources', () => {
    const hits = sources(SRC).filter((file) =>
      readFileSync(file, 'utf8').includes('plainPort'),
    );
    expect(hits).toEqual([]);
  });

  it('keeps screen-fraction projection out of production sources', () => {
    const hits = sources(SRC).filter((file) => {
      const source = readFileSync(file, 'utf8');
      return FRACTION.some((pattern) => pattern.test(source));
    });
    expect(hits).toEqual([]);
  });
});
