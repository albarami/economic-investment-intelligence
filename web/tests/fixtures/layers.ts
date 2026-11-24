/**
 * Invented layer fixtures. No real place, firm or measurement.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import type {
  InvestmentCredits,
  LayerPayload,
  TextSegment,
} from '../../src/stage/layers/payload';
import { factId } from './facts';

export const NIGHT_PARENT = '88536bc1ebfffff';
export const GAZETTEER_POINT = 'gx_sample_aleph';
export const CHAIN_ID = factId(0);

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../src/stage/layers',
);

export function plain(text: string): TextSegment {
  return { kind: 'plain', text };
}

export function category(text: string): TextSegment[] {
  return [plain(text)];
}

export const SAMPLE_CREDITS: InvestmentCredits = {
  publisher: [plain('Sample Agency')],
  gatherer: [plain('Sample Gatherer')],
  read_on: '2024-03-14',
  dashboard_url: 'https://example.invalid/dashboard',
};

export function layerSource(name: string): string {
  return readFileSync(path.join(root, name), 'utf8');
}

export function basePayload(
  overrides: Partial<LayerPayload> = {},
): LayerPayload {
  const payload: LayerPayload = {
    layers: [
      {
        key: 'public_places',
        visible: true,
        source_chain_fact_id: CHAIN_ID,
        source_id: 'src_places',
        features: [
          {
            feature_id: 'feat_place_aleph',
            metric_key: 'place_listing',
            provenance: 'public',
            subject: 'place',
            geometry_kind: 'point',
            fact_id: CHAIN_ID,
          },
        ],
      },
    ],
    sources: [
      {
        sourceId: 'src_places',
        attribution: [plain('Sample overture credit')],
        retrievalDate: '2024-03-14',
        publisher: [plain('Sample Publisher')],
        datasetOrPage: 'Sample places page',
        licenceOrTerms: 'Terms recorded for this sample',
      },
    ],
    gazetteer_points: [GAZETTEER_POINT],
    ...overrides,
  };
  // F12: matching present-band metadata only; existing features/assertions stay.
  for (const layer of payload.layers) {
    if (
      !['night_lights', 'land_prices', 'zone_electricity_growth'].includes(
        layer.key,
      ) ||
      layer.features.length === 0
    )
      continue;
    const group = layer.key === 'land_prices' ? 'INVENTED-use' : null;
    if (group)
      for (const feature of layer.features) feature.class_group ??= group;
    layer.class_breaks ??= [
      {
        group_key: group,
        breaks: [
          'band_low',
          'band_mid_low',
          'band_mid',
          'band_mid_high',
          'band_high',
        ].flatMap((classId) => {
          const feature = layer.features.find((f) => f.class_id === classId);
          return feature
            ? [
                {
                  class_id:
                    classId as import('../../src/stage/layers/payload').FcLegendClass,
                  fact_id: feature.fact_id ?? layer.source_chain_fact_id,
                },
              ]
            : [];
        }),
      },
    ];
  }
  return payload;
}
