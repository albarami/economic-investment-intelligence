import responses from './public-layer-responses.json';
import land from './land-price-layer.json';
import hero from './hero-layer.json';
import type { Fact } from '../../src/facts/types';
import type { LayerPayload } from '../../src/stage/layers/payload';
export function areaScene(
  key: 'land_prices' | 'zone_electricity_growth' | 'zoning',
) {
  const points = structuredClone(responses.public_places) as unknown as {
    facts: Fact[];
    payload: LayerPayload;
  };
  const source = (key === 'land_prices'
    ? land
    : key === 'zoning'
      ? responses.zoning
      : hero) as unknown as typeof points;
  const point = points.payload.layers[0]!.features[0]!;
  points.payload.layers[0]!.features = [
    { ...point, feature_id: 'inside', position: [0.2, 0.2] },
    { ...point, feature_id: 'outside', position: [2, 2] },
    { ...point, feature_id: 'unplaced', position: undefined },
  ];
  return {
    facts: [...points.facts, ...source.facts],
    payload: {
      ...source.payload,
      layers: [...points.payload.layers, ...source.payload.layers],
      sources: [...points.payload.sources, ...source.payload.sources],
    },
  };
}
