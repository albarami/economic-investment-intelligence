import { expect, it, vi } from 'vitest';

const captured: { loadOptions?: { tileset?: object } }[] = [];
vi.mock('../../src/stage/photoreal-session', async () => {
  const actual = await vi.importActual<
    typeof import('../../src/stage/photoreal-session')
  >('../../src/stage/photoreal-session');
  return {
    ...actual,
    photorealSession: () => ({
      open: async () => '/api/photoreal/3dtiles/root.json',
      fetch: vi.fn(),
      dispose: vi.fn(),
    }),
  };
});
vi.mock('../../src/stage/photoreal-loader', () => ({
  qualifiedLayer: (props: { loadOptions?: { tileset?: object } }) => {
    captured.push(props);
    return { context: { viewport: { id: 'invented-viewport' } } };
  },
  visibleCredits: vi.fn(),
}));

import { photoreal } from '../../src/stage/photoreal';
import { tilePath } from '../../src/stage/photoreal-session';

function tileShape(options: { tileset?: object } | undefined) {
  const tileset = options?.tileset ?? {};
  return {
    keys: Object.keys(tileset).sort(),
    lowersDetail: 'maximumScreenSpaceError' in tileset,
  };
}

it('keeps the same tile parameters below and above the spend warning', async () => {
  expect(photoreal.length).toBe(3);
  const below = photoreal(vi.fn(), vi.fn(), vi.fn());
  await below.start();
  const above = photoreal(vi.fn(), vi.fn(), vi.fn());
  await above.start();
  expect(captured).toHaveLength(2);
  const first = tileShape(captured[0]?.loadOptions);
  const second = tileShape(captured[1]?.loadOptions);
  expect(second).toEqual(first);
  expect(first.lowersDetail).toBe(false);
  const path = tilePath('/api/photoreal/3dtiles/invented.glb', 'a'.repeat(32));
  const query = new URL(path, 'http://fixture.invalid').searchParams;
  expect([...query.keys()]).toEqual(['view']);
  expect(query.get('maximumScreenSpaceError')).toBeNull();
});
