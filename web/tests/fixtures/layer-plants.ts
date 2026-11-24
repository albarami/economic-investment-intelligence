import {
  CHAIN_ID,
  NIGHT_PARENT,
  SAMPLE_CREDITS,
  basePayload,
  category,
  plain,
} from './layers';
import type { LayerPayload } from '../../src/stage/layers/payload';

export const PLANTS: Record<(typeof REFUSAL_CODES)[number], LayerPayload> = {
  source_geometry_invalid: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        features: [
          {
            ...basePayload().layers[0]!.features[0]!,
            geometry: { type: 'Point', coordinates: [NaN, 0] },
          },
        ],
      },
    ],
  }),
  unknown_layer: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'not_a_layer',
      },
    ],
  }),
  not_implemented: basePayload({
    layers: [{ ...basePayload().layers[0]!, key: 'presence' }],
  }),
  boundaries_absent: basePayload({ draw_boundaries: true }),
  two_hero_layers: basePayload({
    layers: [
      { ...basePayload().layers[0]!, key: 'land_prices', source_id: 'src_gis' },
      {
        ...basePayload().layers[0]!,
        key: 'night_lights',
        source_id: 'src_night',
      },
    ],
  }),
  incomplete_source_chain: basePayload({
    layers: [{ ...basePayload().layers[0]!, source_chain_fact_id: '' }],
  }),
  missing_attribution: basePayload({
    sources: [{ ...basePayload().sources[0]!, attribution: [] }],
  }),
  below_display_threshold: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        features: [
          {
            ...basePayload().layers[0]!.features[0]!,
            display_rule: 'withheld',
          },
        ],
      },
    ],
  }),
  wage_or_synthetic_id: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        features: [
          {
            ...basePayload().layers[0]!.features[0]!,
            identifier: 'SYN-E-7F3K2Q',
          },
        ],
      },
    ],
  }),
  not_public: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        features: [
          {
            ...basePayload().layers[0]!.features[0]!,
            provenance: 'synthetic',
          },
        ],
      },
    ],
  }),
  measure_on_named_feature: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        features: [
          {
            ...basePayload().layers[0]!.features[0]!,
            metric_key: 'fx_estimate',
          },
        ],
      },
    ],
  }),
  invented_point: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'fdi_projects',
        source_id: 'src_fdi',
        features: [
          {
            feature_id: 'feat_fdi_aleph',
            metric_key: 'fdi_sector',
            provenance: 'public',
            subject: 'fdi_project',
            geometry_kind: 'point',
            place_key: null,
            force_invented_mark: true,
            fact_id: CHAIN_ID,
            year: '2024',
            caveat_keys: [],
          },
        ],
      },
    ],
    sources: [
      {
        sourceId: 'src_fdi',
        attribution: [plain('Sample investment credit')],
        retrievalDate: '2024-03-14',
        publisher: [plain('Sample Agency')],
        datasetOrPage: 'Sample dashboard',
        licenceOrTerms: 'Terms recorded for this sample',
      },
    ],
    credits: SAMPLE_CREDITS,
  }),
  company_name_lookup: basePayload({ company_search: 'aleph' }),
  filter_outside_list: basePayload({ filter_key: 'company' }),
  station_as_operating: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'rail_plan',
        source_id: 'src_gis',
        features: [
          {
            feature_id: 'feat_station',
            metric_key: 'rail_feature',
            provenance: 'public',
            subject: 'gis_feature',
            geometry_kind: 'point',
            status_key: 'operating',
            fact_id: CHAIN_ID,
          },
        ],
      },
    ],
  }),
  parcel_forbidden_label: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'parcels',
        features: [
          {
            feature_id: 'feat_parcel',
            metric_key: 'plot_state',
            provenance: 'public',
            subject: 'gis_feature',
            geometry_kind: 'outline',
            status_key: 'approved',
            fact_id: CHAIN_ID,
          },
        ],
      },
    ],
  }),
  zoning_as_approval: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'zoning',
        features: [
          {
            feature_id: 'feat_zone',
            metric_key: 'permitted_use',
            provenance: 'public',
            subject: 'gis_feature',
            geometry_kind: 'outline',
            status_key: 'approval',
            fact_id: CHAIN_ID,
          },
        ],
      },
    ],
  }),
  zoning_categorical_fill: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'zoning',
        filled: true,
        features: [
          {
            feature_id: 'feat_zone',
            metric_key: 'permitted_use',
            provenance: 'public',
            subject: 'gis_feature',
            geometry_kind: 'fill',
            fact_id: CHAIN_ID,
          },
        ],
      },
    ],
  }),
  outline_filled: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'health_centres',
        filled: true,
        features: [
          {
            feature_id: 'feat_catchment',
            metric_key: 'health_centre_name',
            provenance: 'public',
            subject: 'gis_feature',
            geometry_kind: 'outline',
            fact_id: CHAIN_ID,
          },
        ],
      },
    ],
  }),
  guide_price_as_deal_or_rent: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'land_prices',
        features: [
          {
            feature_id: 'feat_guide',
            metric_key: 'guide_price_class',
            provenance: 'public',
            subject: 'statistic',
            geometry_kind: 'fill',
            status_key: 'deal_price',
            fact_id: CHAIN_ID,
            class_id: 'band_low',
          },
        ],
      },
    ],
  }),
  apportioned_unlabelled: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'property_prices',
        features: [
          {
            feature_id: 'feat_sale',
            metric_key: 'district_sale',
            provenance: 'public',
            subject: 'statistic',
            geometry_kind: 'fill',
            fact_id: CHAIN_ID,
            apportioned_from: 'sample_parent',
            evidence_status: 'observed',
          },
        ],
      },
    ],
  }),
  address_label: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'address_points',
        features: [
          {
            feature_id: 'feat_address',
            metric_key: 'address_zone',
            provenance: 'public',
            subject: 'gis_feature',
            geometry_kind: 'point',
            label_key: 'house',
            fact_id: CHAIN_ID,
          },
        ],
      },
    ],
  }),
  label_while_synthetic_hero: basePayload({
    fixture_hero: 'synthetic',
    layers: [
      {
        ...basePayload().layers[0]!,
        features: [
          {
            ...basePayload().layers[0]!.features[0]!,
            label_key: 'aleph',
          },
        ],
      },
    ],
  }),
  mixed_resolution: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'night_lights',
        source_id: 'src_night',
        features: [
          {
            feature_id: 'feat_night',
            metric_key: 'radiance_class',
            provenance: 'public',
            subject: 'statistic',
            geometry_kind: 'hex',
            cell: NIGHT_PARENT,
            resolution: 8,
            draw_native: true,
            fact_id: CHAIN_ID,
            class_id: 'band_low',
          },
        ],
      },
    ],
  }),
  split_as_layer: basePayload({
    split_chip: {
      provenance: 'public',
      evidence_status: 'observed',
      source_id: 'src_places',
      year: '2024',
      categories: [category('group_b'), category('group_a')],
      geography_code: 'sample_geo',
      source_geography: 'sample_geo',
      as_layer: true,
    },
  }),
  split_off_geography: basePayload({
    split_chip: {
      provenance: 'public',
      evidence_status: 'observed',
      source_id: 'src_places',
      year: '2024',
      categories: [category('group_b')],
      geography_code: 'other_geo',
      source_geography: 'sample_geo',
    },
  }),
  split_incomplete: basePayload({
    split_chip: {
      provenance: 'public',
      evidence_status: 'observed',
      source_id: 'src_places',
      year: '',
      categories: [category('group_b')],
      geography_code: 'sample_geo',
      source_geography: 'sample_geo',
    },
  }),
  announced_estimate_unlabelled: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'fdi_projects',
        source_id: 'src_fdi',
        features: [
          {
            feature_id: 'feat_fdi_aleph',
            metric_key: 'fdi_capex',
            provenance: 'public',
            subject: 'fdi_project',
            geometry_kind: 'point',
            place_key: 'gx_sample_aleph',
            fact_id: CHAIN_ID,
            year: '2024',
            caveat_keys: [],
          },
        ],
      },
    ],
    credits: SAMPLE_CREDITS,
  }),
  listings_note_removed: basePayload({ omit_listings_note: true }),
  legend_count_unbound: basePayload({ count_without_fact: true }),
  fdi_mark_missing: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'fdi_projects',
        source_id: 'src_fdi',
        features: [
          {
            feature_id: 'feat_fdi_aleph',
            metric_key: 'fdi_sector',
            provenance: 'public',
            subject: 'fdi_project',
            geometry_kind: 'point',
            place_key: 'gx_sample_aleph',
            fact_id: CHAIN_ID,
            year: '2024',
            omit_mark: true,
          },
        ],
      },
    ],
    credits: SAMPLE_CREDITS,
  }),
  fdi_year_missing: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'fdi_projects',
        source_id: 'src_fdi',
        features: [
          {
            feature_id: 'feat_fdi_aleph',
            metric_key: 'fdi_sector',
            provenance: 'public',
            subject: 'fdi_project',
            geometry_kind: 'point',
            place_key: 'gx_sample_aleph',
            fact_id: CHAIN_ID,
            omit_year: true,
          },
        ],
      },
    ],
    credits: SAMPLE_CREDITS,
  }),
  not_ranked_invalid: basePayload({
    layers: [{ ...basePayload().layers[0]!, not_ranked: [] }],
  }),
  class_break_invalid: basePayload({
    layers: [{ ...basePayload().layers[0]!, class_breaks: [] }],
  }),
  class_break_missing: (() => {
    const p = nightPlant({});
    delete p.layers[0]!.class_breaks;
    return p;
  })(),
  wrong_layer_type: basePayload({
    layers: [{ ...basePayload().layers[0]!, forced_type: 'TextLayer' }],
  }),
  night_unit_missing: nightPlant({ unit: '' }),
  night_month_missing: nightPlant({ month: '' }),
  night_direction_missing: nightPlant({ direction: '' }),
  night_class_missing: nightPlant({ class_id: '' }),
  night_caveat_missing: nightPlant({ caveat_key: '' }),
  night_acknowledgement_missing: nightPlant({ hide_acknowledgement: true }),
  numeral_in_plain_segment: basePayload({
    sources: [
      {
        ...basePayload().sources[0]!,
        attribution: [plain('Sample credit 4')],
      },
    ],
  }),
  planned_label_missing: basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'rail_plan',
        features: [
          {
            feature_id: 'feat_station',
            metric_key: 'rail_feature',
            provenance: 'public',
            subject: 'gis_feature',
            geometry_kind: 'point',
            fact_id: CHAIN_ID,
            position: [51.5, 25.3],
          },
        ],
      },
    ],
  }),
};

function nightPlant(
  night: Partial<NonNullable<LayerPayload['night']>>,
): LayerPayload {
  return basePayload({
    layers: [
      {
        ...basePayload().layers[0]!,
        key: 'night_lights',
        features: [
          {
            feature_id: 'feat_night',
            metric_key: 'radiance_class',
            provenance: 'public',
            subject: 'statistic',
            geometry_kind: 'hex',
            cell: '89536bc1ea3ffff',
            resolution: 9,
            fact_id: CHAIN_ID,
            class_id: 'band_low',
          },
        ],
      },
    ],
    night: {
      month: '2024-03',
      direction: 'higher',
      class_id: 'band_low',
      unit: 'radiance_nw_cm2_sr',
      caveat_key: 'night_lights_not_activity',
      ...night,
    },
  });
}
