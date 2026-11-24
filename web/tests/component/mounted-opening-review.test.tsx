// @vitest-environment jsdom
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { AnswerShell } from '../../src/shell/AnswerShell';
import type { ResolvePicker } from '../../src/journeys/ResolvePicker';
import { MountedPublicShell } from '../../src/app/MountedPublicShell';
import { createRegistry } from '../../src/facts/registry';
import {
  resetArea,
  registerFetch,
  releaseAreaClient,
  submitPlaceArea,
} from '../../src/state/area-actions';
import { contextInput, contextPayloads } from '../fixtures/public-context';
import { text } from '../../src/i18n';

const api = vi.hoisted(() => ({
  basemap: vi.fn(),
  layer: vi.fn(),
  story: vi.fn(),
}));
vi.mock('../../src/api/release', () => ({ loadBasemapUrl: api.basemap }));
vi.mock('../../src/api/public-layer', () => ({ loadPublicLayer: api.layer }));
vi.mock('../../src/api/public-opening', async (original) => ({
  ...(await original<typeof import('../../src/api/public-opening')>()),
  runPublicStory: api.story,
}));
vi.mock('../../src/shell/AnswerShell', () => ({
  AnswerShell: ({ renderBrief }: React.ComponentProps<typeof AnswerShell>) => (
    <div>
      {renderBrief?.(
        () => undefined,
        () => undefined,
      )}
    </div>
  ),
}));
vi.mock('../../src/journeys/ResolvePicker', () => ({
  ResolvePicker: ({
    kind,
    onSelect,
  }: React.ComponentProps<typeof ResolvePicker>) => (
    <button
      type="button"
      onClick={() =>
        onSelect(
          kind === 'activity'
            ? {
                kind,
                key: 'INVENTED-activity',
                commerce_code: 'INVENTED-code',
                source: 'activity_spine',
                match: 'exact',
                isic_class: 'INVENTED-class',
                place_category: 'INVENTED-category',
                not_mappable: false,
                label_en: 'INVENTED-Craft',
                label_ar: 'حرفة مخترعة',
              }
            : {
                kind,
                key: 'INVENTED-place',
                label_en: 'INVENTED-Garden',
                label_ar: 'حديقة مخترعة',
                source: 'gazetteer',
                match: 'exact',
              },
        )
      }
    >
      {kind === 'activity' ? 'INVENTED-activity' : 'INVENTED-place'}
    </button>
  ),
}));

afterEach(() => {
  cleanup();
  resetArea();
  releaseAreaClient();
  vi.resetAllMocks();
  history.replaceState(null, '', '/');
});

function setup(language: 'en' | 'ar') {
  history.replaceState(null, '', '/?lang=' + language);
  const input = contextInput();
  api.basemap.mockResolvedValue(null);
  api.layer.mockResolvedValue({
    input,
    registry: createRegistry(input),
    payload: { layers: [], sources: [] },
  });
  api.story.mockResolvedValue({
    input,
    cards: [contextPayloads[0]],
    accountingPassed: true,
  });
  registerFetch(async () => ({
    status: 200,
    json: async () => ({
      tool: 'make_area',
      status: 'OK',
      call_id: 'INVENTED-call',
      engine: 'embedded',
      release_id: 'INVENTED-release',
      blocks: [],
      facts: [],
      caveat_keys: [],
      payload: {
        area_id: 'INVENTED-area',
        units: {},
        snap_report: null,
        record: { anchor_cell: null, traffic: 'free_flow', shape: 'polygon' },
        outline: {
          type: 'Polygon',
          coordinates: [
            [
              [0, 0],
              [1, 0],
              [1, 1],
              [0, 0],
            ],
          ],
        },
        point_feature_ids: {},
      },
    }),
  }));
  return render(<MountedPublicShell extractUrl="/tiles/basemap.pmtiles" />);
}

for (const language of ['en', 'ar'] as const) {
  it(`replaces the selected area without retaining the previous story cards (${language})`, async () => {
    const view = setup(language);
    await act(async () => undefined);
    fireEvent.click(
      view.container.querySelector('[data-action="guided-story"]')!,
    );
    fireEvent.click(view.getByRole('button', { name: 'INVENTED-activity' }));
    await act(async () => submitPlaceArea('INVENTED-a', 'walk-a'));
    await act(async () =>
      fireEvent.click(
        view.container.querySelector('[data-action="story-next"]')!,
      ),
    );
    expect(
      view.container.querySelector('[data-context-family]'),
    ).not.toBeNull();
    expect(api.story).toHaveBeenCalledTimes(1);
    await act(async () => submitPlaceArea('INVENTED-b', 'walk-a'));
    expect(view.container.querySelector('[data-context-family]')).toBeNull();
    expect(api.story).toHaveBeenCalledTimes(1);
    await act(async () =>
      fireEvent.click(
        view.container.querySelector('[data-action="story-next"]')!,
      ),
    );
    expect(
      view.container.querySelector('[data-context-family]'),
    ).not.toBeNull();
    expect(api.story.mock.calls[1]?.[2]).toEqual({
      place_key: 'INVENTED-b',
      mode: 'walk',
      cutoff: 5,
    });
  });

  it(`a refused night-lights chain is an alert with unavailable wording (${language})`, async () => {
    const view = setup(language);
    await act(async () => undefined);
    fireEvent.click(
      view.container.querySelector('[data-action="guided-story"]')!,
    );
    api.layer.mockRejectedValue(new Error('layer_refused'));
    await act(async () =>
      fireEvent.change(view.getByRole('combobox'), {
        target: { value: 'night_lights' },
      }),
    );
    expect(view.getByRole('alert').textContent).toBe(
      language === 'ar'
        ? 'طبقة الخريطة هذه غير متاحة.'
        : 'This map layer is unavailable.',
    );
    expect(view.queryByText(text(language, 'layers.fc.nodata'))).toBeNull();
  });

  it(`labels the layer picker, selected activity and place, and scopes the boundary message (${language})`, async () => {
    const view = setup(language);
    await act(async () => undefined);
    fireEvent.click(
      view.container.querySelector('[data-action="guided-story"]')!,
    );
    expect(
      view.getByRole('combobox', {
        name: language === 'ar' ? 'طبقة الخريطة' : 'Map layer',
      }),
    ).toBeTruthy();
    fireEvent.click(view.getByRole('button', { name: 'INVENTED-activity' }));
    fireEvent.click(view.getByRole('button', { name: 'INVENTED-place' }));
    expect(
      view.container.querySelector(
        '[data-part="activity-selected"] .selection-caption',
      )?.textContent,
    ).toBe(language === 'ar' ? 'النشاط' : 'Activity');
    expect(
      view.container.querySelector(
        '[data-part="place-selected"] .selection-caption',
      )?.textContent,
    ).toBe(language === 'ar' ? 'المكان' : 'Place');
    const boundaries = view.getByText(
      text(language, 'layers.boundaries.absent'),
    );
    expect(boundaries.closest('.story-selection')).not.toBeNull();
    expect(boundaries.classList.contains('story-caption')).toBe(true);
  });
}
