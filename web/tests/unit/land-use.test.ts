// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { afterEach, expect, it, vi } from 'vitest';
import land from '../fixtures/land-price-layer.json';
import { routeRegistry } from '../fixtures/public-route-registry';
import type { Fact } from '../../src/facts/types';
import type { LayerPayload } from '../../src/stage/layers/payload';
import { acceptPayload } from '../../src/stage/layers/refuse';
import { overlayFor } from '../../src/stage/layers/overlay';
import {
  activeUse,
  chooseUse,
  forUse,
  landGroupKeys,
  readUseChoice,
  resetUseChoice,
} from '../../src/stage/layers/land-use';
const body = land as unknown as { facts: Fact[]; payload: LayerPayload };
const registry = routeRegistry(body);
const accepted = acceptPayload(body.payload, registry);
if (!accepted.ok) throw Error(accepted.code);
const layers = accepted.draw.layers;
afterEach(resetUseChoice);
it('uses held keys only, preserves group order and other layer identities', () => {
  expect(readUseChoice()).toEqual({ kind: 'initial' });
  expect(landGroupKeys(layers)).toEqual([
    'invented_commercial',
    'invented_residential',
  ]);
  expect(activeUse(landGroupKeys(layers), { kind: 'initial' })).toBe(
    'invented_commercial',
  );
  expect(
    activeUse(landGroupKeys(layers), {
      kind: 'chosen',
      key: 'invented_residential',
    }),
  ).toBe('invented_residential');
  expect(
    activeUse(landGroupKeys(layers), { kind: 'chosen', key: 'absent' }),
  ).toBe('invented_commercial');
  expect(activeUse([], { kind: 'initial' })).toBeNull();
  expect(landGroupKeys([])).toEqual([]);
  const other = { ...layers[0]!, key: 'zoning' };
  const selected = forUse([...layers, other], 'invented_residential');
  expect(selected[1]).toBe(other);
  expect(selected[0]!.features).toEqual(
    layers[0]!.features.filter((f) => f.class_group === 'invented_residential'),
  );
  expect(selected[0]!.classBreaks).toEqual([layers[0]!.classBreaks[1]]);
});
for (const clock of [false, true])
  it(`propagates use into overlay and later clock changes (${clock})`, () => {
    const overlay = overlayFor(body.payload, null, registry, clock);
    const props = vi.spyOn(overlay, 'setProps');
    const initial = overlay._props.layers as Array<{
      id: string;
      props: { data: { features: unknown[] } };
    }>;
    expect(
      initial.find((l) => l.id === 'land_prices:GeoJsonLayer')!.props.data
        .features,
    ).toHaveLength(10);
    chooseUse('invented_residential');
    function rows() {
      return (props.mock.lastCall![0].layers as typeof initial).find(
        (l) => l.id === 'land_prices:GeoJsonLayer',
      )!.props.data.features;
    }
    const expected = forUse(layers, 'invented_residential')[0]!.features;
    const assertRows = () =>
      expect(rows()).toEqual(
        expected.map((f) =>
          expect.objectContaining({
            properties: expect.objectContaining({
              featureId: f.feature_id,
              classId: f.class_id,
            }),
          }),
        ),
      );
    assertRows();
    if ('applySun' in overlay) {
      overlay.applySun([0, 0, 1], { setLight: vi.fn(), setSky: vi.fn() });
      assertRows();
      overlay.setClock(0);
      assertRows();
      overlay.applySun([0, 0, -1], { setLight: vi.fn(), setSky: vi.fn() });
      assertRows();
    }
    overlay.onRemove(null as never);
    props.mockClear();
    chooseUse('invented_commercial');
    expect(props).not.toHaveBeenCalled();
  });
it('keeps numeric values and facts outside the selected-use store', () => {
  const source = readFileSync('src/stage/layers/land-use.ts', 'utf8');
  for (const pattern of [
    /facts\//,
    /Number\(/,
    /parseFloat/,
    /Math\./,
    /<=/,
    />=/,
    /fact_id/,
    /\bvalue\b/,
  ])
    expect(source).not.toMatch(pattern);
});
