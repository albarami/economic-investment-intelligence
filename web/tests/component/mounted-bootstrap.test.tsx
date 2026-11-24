// @vitest-environment jsdom
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import { MountedPublicShell } from '../../src/app/MountedPublicShell';

const api = vi.hoisted(() => ({ basemap: vi.fn(), layer: vi.fn() }));
vi.mock('../../src/api/release', () => ({ loadBasemapUrl: api.basemap }));
vi.mock('../../src/api/public-layer', () => ({ loadPublicLayer: api.layer }));
vi.mock('../../src/shell/AnswerShell', () => ({
  AnswerShell: ({ extractUrl }: { extractUrl: string | null }) => (
    <div data-extract={extractUrl ?? 'absent'} />
  ),
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

it.each([null, '/tiles/basemap.pmtiles'])(
  'waits for the mounted extract name and preserves the selection: %s',
  async (url) => {
    let finish!: (url: string | null) => void;
    api.basemap.mockReturnValue(
      new Promise<string | null>((resolve) => {
        finish = resolve;
      }),
    );
    // An unavailable opening figure must not hide a configured basemap.
    api.layer.mockRejectedValue(new Error('layer_refused'));
    const view = render(
      <MountedPublicShell extractUrl="/tiles/basemap.pmtiles" />,
    );
    expect(
      view.container
        .querySelector('[data-extract]')
        ?.getAttribute('data-extract'),
    ).toBe('absent');
    await act(async () => finish(url));
    expect(
      view.container
        .querySelector('[data-extract]')
        ?.getAttribute('data-extract'),
    ).toBe(url ?? 'absent');
  },
);

it('keeps an absent or refused mount empty', async () => {
  api.basemap.mockRejectedValue(new Error('chain_refused'));
  api.layer.mockRejectedValue(new Error('layer_refused'));
  const view = render(
    <MountedPublicShell extractUrl="/tiles/basemap.pmtiles" />,
  );
  await act(async () => undefined);
  expect(
    view.container
      .querySelector('[data-extract]')
      ?.getAttribute('data-extract'),
  ).toBe('absent');
});
