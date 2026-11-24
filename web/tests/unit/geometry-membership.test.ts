import { describe, expect, it } from 'vitest';
import { filterPublicToOutline } from '../../src/stage/layers/area-filter';
import { readEnvelope } from '../../src/api/areas';
import type { LayerPayload } from '../../src/stage/layers/payload';

const outline = {
  type: 'Polygon' as const,
  coordinates: [
    [
      [0, 0],
      [1, 0],
      [1, 1],
      [0, 1],
      [0, 0],
    ] as const,
  ],
};
const payload: LayerPayload = {
  layers: [
    {
      key: 'zoning',
      visible: true,
      source_chain_fact_id: 'fact-zone',
      source_id: 'src-zone',
      features: [
        {
          feature_id: 'ring',
          metric_key: 'zoning',
          provenance: 'public',
          subject: 'statistic',
          geometry_kind: 'fill',
          ring: [
            [0.2, 0.2],
            [0.4, 0.2],
            [0.4, 0.4],
            [0.2, 0.2],
          ],
        },
      ],
    },
    {
      key: 'rail_plan',
      visible: true,
      source_chain_fact_id: 'fact-rail',
      source_id: 'src-rail',
      features: [
        {
          feature_id: 'path',
          metric_key: 'rail_plan',
          provenance: 'public',
          subject: 'geometry',
          geometry_kind: 'line',
          path: [
            [2, 2],
            [3, 3],
          ],
        },
      ],
    },
    {
      key: 'public_places',
      visible: true,
      source_chain_fact_id: 'fact-place',
      source_id: 'src-place',
      features: [
        {
          feature_id: 'edge',
          metric_key: 'place_listing',
          provenance: 'public',
          subject: 'place',
          geometry_kind: 'point',
          position: [0.5, 1],
        },
        {
          feature_id: 'vertex',
          metric_key: 'place_listing',
          provenance: 'public',
          subject: 'place',
          geometry_kind: 'point',
          position: [1, 1],
        },
        {
          feature_id: 'not-selected',
          metric_key: 'place_listing',
          provenance: 'public',
          subject: 'place',
          geometry_kind: 'point',
          position: [0.5, 0.5],
        },
      ],
    },
  ],
  sources: [],
  gazetteer_points: [],
};

describe('server-owned exact-shape membership', () => {
  it('P4: keeps Public rings and paths unchanged on their own geography', () => {
    const filtered = filterPublicToOutline(payload, outline, {});
    expect(filtered.layers[0]?.features).toEqual(payload.layers[0]?.features);
    expect(filtered.layers[1]?.features).toEqual(payload.layers[1]?.features);
  });
  it('P5: renders server edge and vertex membership without a browser intersection', () => {
    const filtered = filterPublicToOutline(payload, outline, {
      public_places: ['edge', 'vertex'],
    });
    expect(
      filtered.layers[2]?.features.map((feature) => feature.feature_id),
    ).toEqual(['edge', 'vertex']);
  });
  it('does not infer membership from point positions when the server omits it', () => {
    const filtered = filterPublicToOutline(payload, outline, null);
    expect(filtered.layers[2]?.features).toEqual([]);
  });
  it('carries returned membership through the area client', () => {
    const envelope = readEnvelope({
      tool: 'make_area',
      call_id: 'INVENTED-call',
      release_id: 'INVENTED-release',
      engine: 'embedded',
      blocks: [],
      facts: [],
      caveat_keys: [],
      status: 'OK',
      payload: {
        area_id: 'area-review',
        outline,
        point_feature_ids: { public_places: ['edge', 'vertex'] },
        record: {},
      },
    });
    expect(envelope.kind).toBe('envelope');
    if (envelope.kind !== 'envelope') throw new Error('invalid test envelope');
    expect(envelope.envelope.payload?.point_feature_ids).toEqual({
      public_places: ['edge', 'vertex'],
    });
  });
  it.each([undefined, { public_places: ['edge', 1] }, ['edge']])(
    'refuses malformed membership %j',
    (point_feature_ids) => {
      const envelope = readEnvelope({
        tool: 'make_area',
        call_id: 'INVENTED-call',
        release_id: 'INVENTED-release',
        engine: 'embedded',
        blocks: [],
        facts: [],
        caveat_keys: [],
        status: 'OK',
        payload: {
          area_id: 'area-review',
          outline,
          point_feature_ids,
          record: {},
        },
      });
      expect(envelope.kind).toBe('envelope');
      if (envelope.kind !== 'envelope')
        throw new Error('invalid test envelope');
      expect(envelope.envelope.payload?.point_feature_ids).toBeNull();
    },
  );
});
