import responses from './public-layer-responses.json';
import type { Fact } from '../../src/facts/types';
import type { LayerPayload } from '../../src/stage/layers/payload';
export const outer = [
  [0, 0],
  [3, 0],
  [3, 3],
  [0, 3],
  [0, 0],
];
export const hole = [
  [1, 1],
  [1, 2],
  [2, 2],
  [2, 1],
  [1, 1],
];
export const island = [
  [4, 0],
  [5, 0],
  [5, 1],
  [4, 1],
  [4, 0],
];
export const sourceGeometries = [
  { type: 'Point', coordinates: [1, 2] },
  {
    type: 'LineString',
    coordinates: [
      [0, 0],
      [3, 3],
    ],
  },
  { type: 'Polygon', coordinates: [outer, hole] },
  { type: 'MultiPolygon', coordinates: [[outer, hole], [island]] },
] as const;
export function geometryScene(geometry: unknown) {
  const body = structuredClone(responses.zoning) as unknown as {
    facts: Fact[];
    payload: LayerPayload;
  };
  const layer = body.payload.layers[0]!;
  const feature = layer.features[0]!;
  delete feature.ring;
  layer.features = [
    { ...feature, geometry_kind: 'outline', geometry } as typeof feature,
  ];
  return body;
}
