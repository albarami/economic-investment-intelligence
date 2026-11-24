// @vitest-environment jsdom
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { LAYER_ENTRIES } from '../../src/stage/layers/registry';
import type { LayerPayload } from '../../src/stage/layers/payload';
import { sceneRegistry } from '../fixtures/layer-registry';
import { CHAIN_ID, SAMPLE_CREDITS, basePayload } from '../fixtures/layers';

afterEach(() => {
  cleanup();
});

const NIGHT: NonNullable<LayerPayload['night']> = {
  month: '2024-03',
  direction: 'higher',
  class_id: 'band_low',
  unit: 'radiance_nw_cm2_sr',
  caveat_key: 'night_lights_not_activity',
};

function emptyLayer(key: string): LayerPayload {
  return basePayload({
    layers: [
      {
        key,
        visible: true,
        source_chain_fact_id: CHAIN_ID,
        source_id: 'src_places',
        features: [],
      },
    ],
    credits: key === 'fdi_projects' ? SAMPLE_CREDITS : undefined,
    night: key === 'night_lights' ? NIGHT : undefined,
  });
}

function fdiFeature(
  featureId: string,
  words?: Record<string, string>,
): LayerPayload['layers'][number]['features'][number] {
  return {
    feature_id: featureId,
    metric_key: 'fdi_sector',
    provenance: 'public',
    subject: 'fdi_project',
    geometry_kind: 'point',
    year: '2024',
    words,
  };
}

function fdiPayload(
  features: LayerPayload['layers'][number]['features'],
): LayerPayload {
  return basePayload({
    layers: [
      {
        key: 'fdi_projects',
        visible: true,
        source_chain_fact_id: CHAIN_ID,
        source_id: 'src_places',
        features,
      },
    ],
    credits: SAMPLE_CREDITS,
  });
}

describe('fix pass 4 screen', () => {
  it('F2 opens the source chain of an empty layer for every implemented key', () => {
    const implemented = LAYER_ENTRIES.filter((entry) => entry.implemented);
    expect(implemented.length).toBeGreaterThan(0);
    for (const entry of implemented) {
      cleanup();
      const open = { id: '' };
      const view = render(
        <PublicLayers
          payload={emptyLayer(entry.key)}
          language="en"
          registry={sceneRegistry()}
          onOpenChain={(id) => {
            open.id = id;
          }}
        />,
      );
      expect(
        view.container.querySelector('[data-part="layer-refusal"]'),
        entry.key,
      ).toBeNull();
      expect(
        view.container.querySelector('[data-part="feature-panel"]'),
        entry.key,
      ).toBeNull();
      const chain = view.container.querySelector(
        `[data-action="source-chain"][data-scope="layer"][data-layer="${entry.key}"]`,
      );
      expect(chain, entry.key).toBeTruthy();
      fireEvent.click(chain!);
      expect(open.id, entry.key).toBe(CHAIN_ID);
      const credit = view.container.querySelector(
        `[data-credit="${entry.key}"]`,
      );
      expect(credit?.getAttribute('data-retrieved'), entry.key).toBe(
        '2024-03-14',
      );
      expect(
        credit?.querySelector('[data-fact-chip="reference"]')?.textContent,
        entry.key,
      ).toContain('2024');
    }
  });

  it('F3 selects distinct company names from the keyboard', () => {
    const view = render(
      <PublicLayers
        payload={fdiPayload([
          fdiFeature('feat_north', { company: 'Sample North House' }),
          fdiFeature('feat_south', { company: 'Sample South House' }),
        ])}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    const north = view.container.querySelector('[data-feature="feat_north"]');
    const south = view.container.querySelector('[data-feature="feat_south"]');
    expect(north?.textContent).toContain('Sample North House');
    expect(south?.textContent).toContain('Sample South House');
    expect(north?.getAttribute('aria-label')).toBe('Sample North House');
    expect(south?.getAttribute('aria-label')).toBe('Sample South House');
    expect(north?.textContent).not.toContain('feat_north');
    expect(south?.textContent).not.toContain('feat_south');
    fireEvent.keyDown(north!, { key: 'Enter' });
    expect(
      view.container.querySelector('[data-label="name"]')?.textContent,
    ).toContain('Sample North House');
    fireEvent.keyDown(south!, { key: ' ' });
    expect(
      view.container.querySelector('[data-label="name"]')?.textContent,
    ).toContain('Sample South House');
    expect(view.container.textContent).not.toContain('feat_north');
    expect(view.container.textContent).not.toContain('feat_south');
  });

  it('F3 shows the unnamed catalogue name when a feature has no name', () => {
    const view = render(
      <PublicLayers
        payload={basePayload()}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    const button = view.container.querySelector(
      '[data-feature="feat_place_aleph"]',
    );
    expect(button?.textContent).toContain('Listed item');
    expect(button?.getAttribute('aria-label')).toBe('Listed item');
    expect(button?.textContent).not.toContain('feat_place_aleph');
    fireEvent.keyDown(button!, { key: 'Enter' });
    expect(
      view.container.querySelector('[data-label="name"]')?.textContent,
    ).toContain('Listed item');
    cleanup();
    const arabic = render(
      <PublicLayers
        payload={basePayload()}
        language="ar"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    expect(
      arabic.container.querySelector('[data-feature="feat_place_aleph"]')
        ?.textContent,
    ).toContain('عنصر مدرج');
  });
});
