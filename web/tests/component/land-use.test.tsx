// @vitest-environment jsdom
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import land from '../fixtures/land-price-layer.json';
import { routeRegistry } from '../fixtures/public-route-registry';
import type { Fact } from '../../src/facts/types';
import type { LayerPayload } from '../../src/stage/layers/payload';
import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { overlayFor } from '../../src/stage/layers/overlay';
import { resetUseChoice } from '../../src/stage/layers/land-use';
const body = land as unknown as { facts: Fact[]; payload: LayerPayload };
afterEach(() => {
  cleanup();
  resetUseChoice();
});
it('shares click, Enter and Space use selection across plate, panel, legend and map', () => {
  const registry = routeRegistry(body);
  const overlay = overlayFor(body.payload, null, registry);
  const props = vi.spyOn(overlay, 'setProps');
  const view = render(
    <PublicLayers
      payload={body.payload}
      registry={registry}
      language="en"
      onOpenChain={() => {}}
    />,
  );
  const layer = body.payload.layers[0]!;
  function check(key: string) {
    const features = layer.features.filter((f) => f.class_group === key);
    expect(
      view.container
        .querySelector(`[data-use="${key}"]`)
        ?.getAttribute('aria-pressed'),
    ).toBe('true');
    const legend = view.container.querySelector(
      '[data-part="land-price-legend"]',
    )!;
    expect(legend.getAttribute('data-group')).toBe(key);
    expect(
      [...legend.querySelectorAll('[data-fact-id]')].map((c) =>
        c.getAttribute('data-fact-id'),
      ),
    ).toEqual(
      layer
        .class_breaks!.find((g) => g.group_key === key)!
        .breaks.map((b) => b.fact_id),
    );
    expect(
      [...view.container.querySelectorAll('button[data-feature]')].map((c) =>
        c.getAttribute('data-feature'),
      ),
    ).toEqual(features.map((f) => f.feature_id));
    if (props.mock.lastCall) {
      const layers = props.mock.lastCall[0].layers as Array<{
        id: string;
        props: {
          data: {
            features: Array<{
              properties: { featureId: string; classId: string };
            }>;
          };
        };
      }>;
      expect(
        layers
          .find((l) => l.id === 'land_prices:GeoJsonLayer')!
          .props.data.features.map((f) => f.properties),
      ).toEqual(
        features.map((f) => ({
          id: f.feature_id,
          featureId: f.feature_id,
          classId: f.class_id,
        })),
      );
    }
  }
  check('invented_commercial');
  const commercial = layer.features.find(
    (f) => f.class_group === 'invented_commercial',
  )!;
  fireEvent.click(
    view.container.querySelector(`[data-feature="${commercial.feature_id}"]`)!,
  );
  expect(
    view.container.querySelector('[data-part="feature-panel"]'),
  ).not.toBeNull();
  for (const [key, event] of [
    ['invented_residential', 'click'],
    ['invented_commercial', 'Enter'],
    ['invented_residential', ' '],
  ]) {
    const button = view.container.querySelector(
      `[data-use="${key}"]`,
    )! as HTMLElement;
    button.focus();
    act(() => {
      if (event === 'click') fireEvent.click(button);
      else fireEvent.keyDown(button, { key: event });
    });
    check(key!);
    if (key === 'invented_residential')
      expect(
        view.container.querySelector('[data-part="feature-panel"]'),
      ).toBeNull();
  }
  const residential = layer.features.find(
    (f) => f.class_group === 'invented_residential',
  )!;
  fireEvent.click(
    view.container.querySelector(`[data-feature="${residential.feature_id}"]`)!,
  );
  const panel = view.container.querySelector('[data-part="feature-panel"]')!;
  expect(
    panel.querySelector(`[data-fact-id="${residential.fact_id}"]`),
  ).not.toBeNull();
  expect(
    panel.querySelector(`[data-fact-id="${commercial.fact_id}"]`),
  ).toBeNull();
  overlay.onRemove(null as never);
});
