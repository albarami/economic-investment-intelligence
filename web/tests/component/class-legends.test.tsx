// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import land from '../fixtures/land-price-layer.json';
import { routeRegistry } from '../fixtures/public-route-registry';
import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import type { LayerPayload } from '../../src/stage/layers/payload';
import type { Fact } from '../../src/facts/types';
afterEach(cleanup);
it('binds only the three present commercial boundary chips', () => {
  const body = land as unknown as { facts: Fact[]; payload: LayerPayload };
  const { container } = render(
    <PublicLayers
      payload={body.payload}
      registry={routeRegistry(body)}
      language="en"
      onOpenChain={() => {}}
    />,
  );
  const bands = [...container.querySelectorAll('li[data-class]')];
  expect(bands.map((li) => li.getAttribute('data-class'))).toEqual([
    'band_low',
    'band_mid_low',
    'band_mid',
  ]);
  expect(
    bands.every(
      (li) =>
        li.querySelector('[data-fact-id]')?.getAttribute('data-state') ===
        'ready',
    ),
  ).toBe(true);
  expect(
    bands.map((li) => li.querySelector('.chip-figure')?.textContent),
  ).toEqual([
    '3QAR per square foot',
    '8QAR per square foot',
    '21QAR per square foot',
  ]);
  const breaks = body.payload.layers[0]!.class_breaks![0]!.breaks;
  expect(
    bands.map((li) =>
      li.querySelector('[data-fact-id]')?.getAttribute('data-fact-id'),
    ),
  ).toEqual(breaks.map((b) => b.fact_id));
});
