/**
 * Invented firms-by-tower payload. Counts are registry values.
 */
import type { FactRegistry } from '../../src/facts/registry';
import type {
  LayerFeature,
  LayerPayload,
} from '../../src/stage/layers/payload';
import { factId } from './facts';
import { layerRegistry } from './layer-registry';
import { basePayload, plain } from './layers';

export const FC_CHAIN = factId(0);
export const FC_ALEPH = factId(0);
export const FC_GIMEL = factId(1);
export const FC_DISTRICT = factId(2);
export const FC_BREAKS = [
  factId(3),
  factId(4),
  factId(5),
  factId(6),
  factId(7),
];

const CLASSES = [
  'band_low',
  'band_mid_low',
  'band_mid',
  'band_mid_high',
  'band_high',
] as const;

export function fcRegistry(value = 4): FactRegistry {
  const rows = [
    { id: FC_ALEPH, value, publicCode: 'place:INV-TOWER-ALEPH' },
    { id: FC_GIMEL, value: 1, publicCode: 'place:INV-TOWER-GIMEL' },
    { id: FC_DISTRICT, value: 1, publicCode: 'district:INV-NORTH' },
    ...FC_BREAKS.map((id, index) => ({
      id,
      value: index + 1,
      publicCode: undefined,
    })),
  ];
  return layerRegistry(
    rows.map((row) => ({
      id: row.id,
      metric: 'firms_per_tower',
      table: 'pub_register_company',
      value: row.value,
      geography: { kind: 'public', public_code: row.publicCode },
    })),
  );
}

export function fcFeature(overrides: Partial<LayerFeature> = {}): LayerFeature {
  return {
    feature_id: 'feat-invented-tower-aleph',
    metric_key: 'firms_per_tower',
    provenance: 'public',
    subject: 'place',
    geometry_kind: 'point',
    class_id: 'band_mid_low',
    fact_id: FC_ALEPH,
    geography_code: 'place:INV-TOWER-ALEPH',
    position: [51.5, 25.3],
    words: { name: 'Invented Tower Aleph' },
    ...overrides,
  };
}

export function fcPayload(overrides: Partial<LayerPayload> = {}): LayerPayload {
  const features = [
    fcFeature(),
    fcFeature({
      feature_id: 'feat-invented-tower-gimel',
      class_id: 'band_low',
      fact_id: FC_GIMEL,
      geography_code: 'place:INV-TOWER-GIMEL',
      position: undefined,
      words: { name: 'Invented Tower Gimel' },
    }),
    fcFeature({
      feature_id: 'feat-district-inv-north',
      geometry_kind: 'fill',
      subject: 'statistic',
      class_id: 'band_low',
      fact_id: FC_DISTRICT,
      position: undefined,
      geography_code: 'district:INV-NORTH',
      ring: [
        [51.4, 25.2],
        [51.6, 25.2],
        [51.6, 25.4],
        [51.4, 25.2],
      ],
      words: { name: 'Invented North District' },
    }),
  ];
  return basePayload({
    layers: [
      {
        key: 'fc_firms_per_tower',
        visible: true,
        source_chain_fact_id: FC_CHAIN,
        source_id: 'src_places',
        features,
      },
    ],
    count_fact_ids: [FC_ALEPH, FC_GIMEL, FC_DISTRICT, ...FC_BREAKS],
    count_facts: [FC_ALEPH, FC_GIMEL, FC_DISTRICT, ...FC_BREAKS].map(
      (fact_id) => ({ fact_id, year: '2024' }),
    ),
    fc_firms: {
      direction: 'higher',
      coverage_note_keys: ['zone_without_district'],
      companies: [
        {
          feature_id: 'feat-invented-tower-aleph',
          row_id: 'row-aleph-one',
          fields: [
            { key: 'trade_name', text: 'Invented House Aleph' },
            { key: 'activity', text: 'Sample finance activity' },
          ],
        },
        {
          feature_id: 'feat-invented-tower-aleph',
          row_id: 'row-aleph-two',
          fields: [
            { key: 'trade_name', text: 'Invented House Aleph Two' },
            { key: 'activity', text: 'Sample finance activity' },
          ],
        },
      ],
      breaks: CLASSES.map((class_id, index) => ({
        class_id,
        fact_id: FC_BREAKS[index] ?? FC_ALEPH,
      })),
    },
    sources: [
      {
        sourceId: 'src_places',
        attribution: [plain('Sample register credit')],
        retrievalDate: '2024-03-14',
        publisher: [plain('Sample Publisher')],
        datasetOrPage: 'Sample register page',
        licenceOrTerms: 'Terms recorded for this sample',
      },
    ],
    ...overrides,
  });
}
