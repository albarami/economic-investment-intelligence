import { expect, it } from 'vitest';
import { areaScene } from '../fixtures/area-source-layers';
import { routeRegistry } from '../fixtures/public-route-registry';
import type { AreaOutline } from '../../src/api/areas';
import { filterPublicToOutline } from '../../src/stage/layers/area-filter';
import { acceptPayload } from '../../src/stage/layers/refuse';
const outlines: AreaOutline[] = [
  {
    type: 'Polygon',
    coordinates: [
      [
        [0, 0],
        [1, 0],
        [1, 1],
        [0, 1],
        [0, 0],
      ],
    ],
  },
  { type: 'Circle', coordinates: [0.2, 0.2], radius_m: 250 },
];
for (const key of ['land_prices', 'zone_electricity_growth', 'zoning'] as const)
  for (const outline of outlines)
    it(`preserves ${key} source geography under ${outline.type}`, () => {
      const body = areaScene(key);
      expect(acceptPayload(body.payload, routeRegistry(body)).ok).toBe(true);
      const result = filterPublicToOutline(body.payload, outline, {
        public_places: ['inside'],
      });
      expect(result.layers[1]).toBe(body.payload.layers[1]);
      expect(result.layers[1]!.features.length).toBeGreaterThan(0);
      expect(result.layers[0]!.features.map((f) => f.feature_id)).toEqual([
        'inside',
      ]);
      expect(acceptPayload(result, routeRegistry(body)).ok).toBe(true);
    });
