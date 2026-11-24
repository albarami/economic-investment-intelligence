// @vitest-environment jsdom
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { AnswerShell } from '../../src/shell/AnswerShell';
import { MountedPublicShell } from '../../src/app/MountedPublicShell';
import { ApiRefusal } from '../../src/api/refusal';
import { text } from '../../src/i18n';
const api = vi.hoisted(() => ({
  basemap: vi.fn(),
  layer: vi.fn(),
  story: vi.fn(),
  selection: { shape_id: 'INVENTED' },
}));
vi.mock('../../src/api/release', () => ({ loadBasemapUrl: api.basemap }));
vi.mock('../../src/api/public-layer', () => ({ loadPublicLayer: api.layer }));
vi.mock('../../src/api/public-opening', async (original) => ({
  ...(await original<typeof import('../../src/api/public-opening')>()),
  runPublicStory: api.story,
}));
vi.mock('../../src/state/area-actions', async (original) => ({
  ...(await original<typeof import('../../src/state/area-actions')>()),
  selectedAreaRequest: () => api.selection,
}));
vi.mock('../../src/journeys/PublicStory', () => ({
  PublicStory: ({ onRun }: { onRun: (activity: string) => void }) => (
    <button onClick={() => onRun('INVENTED')}>INVENTED-run</button>
  ),
}));
vi.mock('../../src/shell/AnswerShell', () => ({
  AnswerShell: ({ renderBrief }: React.ComponentProps<typeof AnswerShell>) => (
    <div data-map-mounted>
      {renderBrief?.(
        () => undefined,
        () => undefined,
      )}
    </div>
  ),
}));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  history.replaceState(null, '', '/');
});
for (const language of ['en', 'ar'] as const) {
  it.each(['layer', 'basemap'] as const)(
    `carries the exact %s refusal to the ${language} catalogue`,
    async (boundary) => {
      history.replaceState(null, '', '/?lang=' + language);
      const state = {
        http_status: 503,
        code: 'STORE_UNAVAILABLE',
        message_key: 'chain_refused',
        catalogue_key: 'layers.refused.registry',
      } as const;
      api.basemap.mockResolvedValue(null);
      api.layer.mockReturnValue(new Promise(() => undefined));
      api[boundary].mockRejectedValue(new ApiRefusal(state));
      const view = render(
        <MountedPublicShell extractUrl="/tiles/basemap.pmtiles" />,
      );
      await act(async () => undefined);
      if (boundary === 'layer')
        fireEvent.click(
          view.container.querySelector('[data-action="guided-story"]')!,
        );
      const alert = view.getByRole('alert');
      expect(alert.getAttribute('data-http-status')).toBe('503');
      expect(alert.getAttribute('data-refusal-code')).toBe('STORE_UNAVAILABLE');
      expect(alert.getAttribute('data-message-key')).toBe('chain_refused');
      expect(alert.getAttribute('data-catalogue-key')).toBe(
        'layers.refused.registry',
      );
      expect(alert.textContent).toBe(text(language, 'layers.refused.registry'));
      expect(alert.textContent).not.toMatch(
        /503|STORE_UNAVAILABLE|chain_refused/,
      );
      if (boundary === 'basemap')
        expect(view.container.querySelector('[data-map-mounted]')).toBeNull();
    },
  );
}

it.each(['en', 'ar'] as const)(
  'retains a story refusal in %s without rendering server text',
  async (language) => {
    history.replaceState(null, '', '/?lang=' + language);
    api.basemap.mockResolvedValue(null);
    api.layer.mockReturnValue(new Promise(() => undefined));
    api.story.mockRejectedValue(
      new ApiRefusal({
        http_status: 504,
        code: 'QUERY_TIMEOUT',
        message_key: 'operation_timeout',
        catalogue_key: 'mapModes.network',
      }),
    );
    const view = render(
      <MountedPublicShell extractUrl="/tiles/basemap.pmtiles" />,
    );
    await act(async () => undefined);
    fireEvent.click(
      view.container.querySelector('[data-action="guided-story"]')!,
    );
    await act(async () => fireEvent.click(view.getByText('INVENTED-run')));
    const alert = view.getByRole('alert');
    expect(alert.getAttribute('data-http-status')).toBe('504');
    expect(alert.getAttribute('data-refusal-code')).toBe('QUERY_TIMEOUT');
    expect(alert.getAttribute('data-message-key')).toBe('operation_timeout');
    expect(alert.textContent).toBe(text(language, 'mapModes.network'));
  },
);
it('refuses a basemap mismatch instead of silently choosing a plain style', async () => {
  api.basemap.mockResolvedValue('/tiles/basemap.pmtiles');
  api.layer.mockReturnValue(new Promise(() => undefined));
  const view = render(<MountedPublicShell extractUrl="/INVENTED.pmtiles" />);
  await act(async () => undefined);
  expect(view.container.querySelector('[data-map-mounted]')).toBeNull();
  expect(view.getByRole('alert').getAttribute('data-message-key')).toBe(
    'chain_refused',
  );
});
it('shows only the existing catalogue text for an unstructured release error', async () => {
  api.basemap.mockRejectedValue(
    new Error('INVENTED secret https://INVENTED.invalid /private'),
  );
  api.layer.mockReturnValue(new Promise(() => undefined));
  const view = render(
    <MountedPublicShell extractUrl="/tiles/basemap.pmtiles" />,
  );
  await act(async () => undefined);
  expect(view.getByRole('alert').textContent).toBe(text('en', 'stage.error'));
  expect(view.getByRole('alert').getAttribute('data-message-key')).toBe(
    'operation_failed',
  );
});
