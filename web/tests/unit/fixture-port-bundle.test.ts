import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const DIST = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../dist',
);

const MARKERS = ['eii-fixture-plain-port', 'plainPort', 'portForPlate'];

function files(dir: string): string[] {
  if (!existsSync(dir)) return [];
  const found: string[] = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) {
      found.push(...files(full));
      continue;
    }
    if (name.endsWith('.js')) found.push(full);
  }
  return found;
}

describe('fixture port bundle', () => {
  it('keeps the fixture port marker out of the production bundle', () => {
    const built = files(DIST);
    expect(built.length).toBeGreaterThan(0);
    const hits = built.filter((file) => {
      const source = readFileSync(file, 'utf8');
      return MARKERS.some((marker) => source.includes(marker));
    });
    expect(hits).toEqual([]);
  });
});
