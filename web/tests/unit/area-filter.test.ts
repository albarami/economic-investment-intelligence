import { describe, expect, it } from 'vitest';

import { filterPublicToOutline } from '../../src/stage/layers/area-filter';
import type {
  LayerFeature,
  LayerPayload,
} from '../../src/stage/layers/payload';

const RING = [
  [0, 0],
  [1, 0],
  [1, 1],
  [0, 1],
  [0, 0],
] as const;

function point(id: string, position?: readonly [number, number]): LayerFeature {
  return {
    feature_id: id,
    metric_key: 'place_listing',
    provenance: 'public',
    subject: 'place',
    geometry_kind: 'point',
    position,
  };
}

function payload(): LayerPayload {
  return {
    layers: [
      {
        key: 'public_places',
        visible: true,
        source_chain_fact_id: 'fact-places',
        source_id: 'src-places',
        features: [
          point('inside', [0.2, 0.2]),
          point('outside', [2, 2]),
          point('unplaced'),
        ],
      },
      {
        key: 'presence',
        visible: true,
        source_chain_fact_id: 'fact-presence',
        source_id: 'src-presence',
        features: [point('kept-outside', [2, 2])],
      },
    ],
    sources: [],
    gazetteer_points: [],
  };
}

describe('public layer filter', () => {
  it('keeps a public feature inside the outline and drops one outside', () => {
    const filtered = filterPublicToOutline(
      payload(),
      {
        type: 'Polygon',
        coordinates: [RING],
      },
      { public_places: ['inside'] },
    );
    const places = filtered.layers.find(
      (layer) => layer.key === 'public_places',
    );
    const presence = filtered.layers.find((layer) => layer.key === 'presence');
    expect(places?.features.map((feature) => feature.feature_id)).toEqual([
      'inside',
    ]);
    expect(presence?.features.map((feature) => feature.feature_id)).toEqual([
      'kept-outside',
    ]);
  });

  it('keeps a public point inside a returned circle and drops one outside', () => {
    const filtered = filterPublicToOutline(
      payload(),
      {
        type: 'Circle',
        coordinates: [0.2, 0.2],
        radius_m: 250,
      },
      { public_places: ['inside'] },
    );
    const places = filtered.layers.find(
      (layer) => layer.key === 'public_places',
    );
    expect(places?.features.map((feature) => feature.feature_id)).toEqual([
      'inside',
    ]);
  });
});
