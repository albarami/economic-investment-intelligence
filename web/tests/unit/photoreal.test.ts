import { expect, it, vi } from 'vitest';
const state = vi.hoisted(() => ({
  viewport: { id: 'invented-current-viewport' },
  ready: (_value: object) => {
    void _value;
  },
}));
vi.mock('../../src/stage/photoreal-session', () => ({
  photorealSession: () => ({
    open: async () => '/api/photoreal/3dtiles/root.json',
    fetch: vi.fn(),
    dispose: vi.fn(),
  }),
}));
vi.mock('../../src/stage/photoreal-loader', () => ({
  qualifiedLayer: (props: { onTilesetLoad(value: object): void }) => {
    state.ready = props.onTilesetLoad;
    return { context: { viewport: state.viewport } };
  },
  visibleCredits: vi.fn(),
}));
import { photoreal } from '../../src/stage/photoreal';
it('starts a late root on the existing viewport and refuses root completion after exit', async () => {
  const renderer = photoreal(vi.fn(), vi.fn(), vi.fn());
  await renderer.start();
  const tileset = { selectTiles: vi.fn(async () => 1), destroy: vi.fn() };
  state.ready(tileset);
  expect(tileset.selectTiles).toHaveBeenCalledExactlyOnceWith([state.viewport]);
  renderer.dispose();
  expect(tileset.destroy).toHaveBeenCalledTimes(1);
  const late = { selectTiles: vi.fn(async () => 1), destroy: vi.fn() };
  state.ready(late);
  expect(late.selectTiles).not.toHaveBeenCalled();
  expect(late.destroy).toHaveBeenCalledTimes(1);
});
