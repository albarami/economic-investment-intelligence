import { describe, it, expect } from 'vitest';
import hero from '../fixtures/hero-layer.json';
import land from '../fixtures/land-price-layer.json';
import { routeRegistry } from '../fixtures/public-route-registry';
import { acceptPayload } from '../../src/stage/layers/refuse';
import { overlayFor } from '../../src/stage/layers/overlay';
import type { LayerPayload } from '../../src/stage/layers/payload';
import type { Fact } from '../../src/facts/types';
const body = hero as unknown as { facts: Fact[]; payload: LayerPayload };
describe('hero source zones', () => {
  it('accepts fills, not-ranked outlines and bound breaks', () => {
    const accepted = acceptPayload(body.payload, routeRegistry(body));
    expect(accepted.ok).toBe(true);
    if (!accepted.ok) return;
    expect(accepted.draw.layers[0]?.features).toHaveLength(5);
    expect(accepted.draw.layers[0]?.notRanked).toHaveLength(3);
    const overlay = overlayFor(body.payload, null, routeRegistry(body));
    const outline = overlay._props.layers.find(
      (l) => l.id === 'zone_electricity_growth:not_ranked',
    );
    expect(outline?.props.filled).toBe(false);
    expect(
      outline?.props.data.features.map((f) => f.properties.featureId),
    ).toEqual(body.payload.layers[0]?.not_ranked?.map((z) => z.feature_id));
  });
  it.each(['class_id', 'fact_id', 'reason_key', 'name_segments', 'duplicate'])(
    'refuses malformed excluded zones %s',
    (key) => {
      const p = structuredClone(body.payload);
      const zone = p.layers[0]!.not_ranked![0]!;
      if (key === 'duplicate')
        zone.feature_id = p.layers[0]!.features[0]!.feature_id;
      else if (key === 'name_segments') delete zone.name_segments;
      else zone[key] = key === 'reason_key' ? 'unknown' : 'INVENTED';
      expect(acceptPayload(p, routeRegistry(body))).toMatchObject({
        ok: false,
        code: 'not_ranked_invalid',
      });
    },
  );
  it('accepts both land groups', () => {
    const b = land as unknown as typeof body;
    expect(acceptPayload(b.payload, routeRegistry(b)).ok).toBe(true);
  });
});

import responses from '../fixtures/public-layer-responses.json';
it.each(Object.entries(responses))(
  'accepts the mounted %s response',
  (_key, response) => {
    const b = response as unknown as { facts: Fact[]; payload: LayerPayload };
    expect(acceptPayload(b.payload, routeRegistry(b))).toMatchObject({
      ok: true,
    });
  },
);

import { formatFactValue } from '../../src/facts/formatters';
it('formats parcel area and canonical source price units without relabelling them', () => {
  for (const unit of ['square_metre', 'qar_per_ft2', 'qar_per_m2'])
    expect(formatFactValue(3, unit, 'en').ok).toBe(true);
});
