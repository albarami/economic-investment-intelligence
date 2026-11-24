// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MountedPublicShell } from '../../src/app/MountedPublicShell';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  history.replaceState(null, '', '/');
});

it('opens with the decision question and a working guided-story action', async () => {
  vi.stubGlobal('fetch', async () => ({ ok: false }));
  render(<MountedPublicShell extractUrl="/tiles/basemap.pmtiles" />);
  expect(
    screen.queryByRole('heading', { name: 'What decision are you making?' }),
  ).not.toBeNull();
  expect(screen.queryByRole('button', { name: 'Guided story' })).not.toBeNull();
});

it('offers only the provided site action and guides it into the area scene', () => {
  vi.stubGlobal('fetch', async () => ({ ok: false }));
  const view = render(
    <MountedPublicShell extractUrl="/tiles/basemap.pmtiles" />,
  );
  const journeys = view.container.querySelectorAll('[data-journey]');
  expect(
    [...journeys].map((node) => node.getAttribute('data-journey')),
  ).toEqual(['site']);
  expect(view.container.querySelector('[data-fact-chip="value"]')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Site choice' }));
  expect(view.container.querySelector('[data-scene="area"]')).not.toBeNull();
  expect(
    view.container
      .querySelector('.drawing-disclosure')
      ?.closest('.stage-column'),
  ).not.toBeNull();
  expect(view.container.querySelector('[data-scene="opening"]')).toBeNull();
});

it('changes language on the same route and keeps the question application-owned', () => {
  vi.stubGlobal('fetch', async () => ({ ok: false }));
  const view = render(
    <MountedPublicShell extractUrl="/tiles/basemap.pmtiles" />,
  );
  fireEvent.click(view.container.querySelector('[data-action="language"]')!);
  expect(document.documentElement.lang).toBe('ar');
  expect(document.documentElement.dir).toBe('rtl');
  expect(location.pathname).toBe('/');
  expect(new URLSearchParams(location.search).get('lang')).toBe('ar');
  expect(
    screen.getByRole('heading', { name: 'ما القرار الذي تفكر فيه؟' }),
  ).not.toBeNull();
});
