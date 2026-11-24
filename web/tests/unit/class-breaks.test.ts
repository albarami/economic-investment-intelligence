import { describe, expect, it } from 'vitest';
import hero from '../fixtures/hero-layer.json';
import land from '../fixtures/land-price-layer.json';
import { routeRegistry } from '../fixtures/public-route-registry';
import { acceptPayload } from '../../src/stage/layers/refuse';
import type { LayerPayload } from '../../src/stage/layers/payload';
import type { Fact } from '../../src/facts/types';
const body = land as unknown as { facts: Fact[]; payload: LayerPayload };
describe('closed present-class breaks', () => {
  it.each([
    'absent',
    'missing',
    'wrong',
    'unknown',
    'backward',
    'repeat',
    'low',
    'unbound',
    'empty',
    'group',
    'no_group',
  ])('refuses plant %s', (plant) => {
    const p = structuredClone(body.payload);
    const l = p.layers[0]!;
    const g = l.class_breaks![0]!;
    let code = 'class_break_invalid';
    if (plant === 'absent') {
      delete l.class_breaks;
      code = 'class_break_missing';
    }
    if (plant === 'missing') {
      g.breaks.splice(0, 1);
      code = 'class_break_missing';
    }
    if (plant === 'wrong') g.breaks[0]!.fact_id = g.breaks[1]!.fact_id;
    if (plant === 'unknown') g.breaks[0]!.class_id = 'band_top';
    if (plant === 'backward') g.breaks.reverse();
    if (plant === 'repeat') g.breaks.push(g.breaks[0]!);
    if (plant === 'low') g.breaks[0]!.low = 1;
    if (plant === 'unbound') g.breaks[0]!.fact_id = 'INVENTED-missing';
    if (plant === 'empty')
      g.breaks.push({ class_id: 'band_high', fact_id: g.breaks[0]!.fact_id });
    if (plant === 'group') l.class_breaks!.push(g);
    if (plant === 'no_group') {
      delete l.features[0]!.class_group;
      code = 'class_break_missing';
    }
    expect(acceptPayload(p, routeRegistry(body))).toMatchObject({
      ok: false,
      code,
    });
  });
  it.each([
    ['band_low', 'band_high'],
    ['band_mid'],
    ['band_high'],
    ['band_mid_low', 'band_high'],
  ])('accepts sparse ordered keys %j', (...keys) => {
    const b = structuredClone(hero) as unknown as typeof body;
    const l = b.payload.layers[0]!;
    l.features = l.features.slice(0, keys.length);
    for (const [i, f] of l.features.entries()) f.class_id = keys[i];
    l.class_breaks = [
      {
        group_key: null,
        breaks: l.features.map((f) => ({
          class_id: f.class_id!,
          fact_id: f.fact_id!,
        })),
      },
    ];
    const a = acceptPayload(b.payload, routeRegistry(b));
    expect(a.ok).toBe(true);
    if (a.ok)
      expect(
        a.draw.layers[0]!.classBreaks[0]!.breaks.map((b) => b.class_id),
      ).toEqual(keys);
  });
});
