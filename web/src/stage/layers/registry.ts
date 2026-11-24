/**
 * Every key of the closed layer list. A key is drawn only when its table
 * is Public and a named writer task of this task owns it.
 */

export interface LayerEntry {
  key: string;
  table: string;
  className: string;
  writer: string;
  implemented: boolean;
  reason: string;
  hero: boolean;
  layerTypes: readonly string[];
  metricKeys: readonly string[];
}

const PLACE = ['place_listing'] as const;
const FDI = [
  'fdi_capex',
  'fdi_jobs',
  'fdi_sector',
  'fdi_source_country',
  'fdi_period',
  'fdi_location',
  'fdi_company',
  'fdi_field',
  'fdi_sub_sector',
  'fdi_function',
  'fdi_project_type',
  'fdi_announced',
] as const;

const OUTSIDE = 'writer is outside S2-T06, S2-T12, S2-T14, S2-T19 and S2-T15';

export const LAYER_ENTRIES: readonly LayerEntry[] = [
  {
    key: 'zone_electricity_growth',
    table: 'pub_zone_utility',
    className: 'Public',
    writer: 'S2-T03',
    implemented: true,
    reason: '',
    hero: true,
    layerTypes: ['GeoJsonLayer'],
    metricKeys: ['electricity_growth_class'],
  },
  {
    key: 'licence_density',
    table: 'pub_licence_active',
    className: 'Public',
    writer: 'S2-T03',
    implemented: false,
    reason: OUTSIDE,
    hero: true,
    layerTypes: ['GeoJsonLayer'],
    metricKeys: [],
  },
  {
    key: 'transit_riders',
    table: 'pub_transit_monthly',
    className: 'Public',
    writer: 'S2-T03',
    implemented: false,
    reason: OUTSIDE,
    hero: true,
    layerTypes: ['ScatterplotLayer'],
    metricKeys: [],
  },
  {
    key: 'presence',
    table: 'presence_count',
    className: 'Simulated',
    writer: 'S5-T09',
    implemented: false,
    reason: 'class is not Public',
    hero: false,
    layerTypes: [],
    metricKeys: [],
  },
  {
    key: 'crowd_density',
    table: 'presence_count',
    className: 'Simulated',
    writer: 'S5-T09',
    implemented: false,
    reason: 'class is not Public',
    hero: true,
    layerTypes: ['H3HexagonLayer'],
    metricKeys: [],
  },
  {
    key: 'traffic',
    table: 'traffic_hourly',
    className: 'Simulated',
    writer: 'S5-T09',
    implemented: false,
    reason: 'class is not Public',
    hero: true,
    layerTypes: ['PathLayer'],
    metricKeys: [],
  },
  {
    key: 'flows',
    table: 'flow_hourly',
    className: 'Simulated',
    writer: 'S5-T09',
    implemented: false,
    reason: 'class is not Public',
    hero: true,
    layerTypes: ['PathLayer'],
    metricKeys: [],
  },
  {
    key: 'public_places',
    table: 'pub_place, pub_place_fsq',
    className: 'Public',
    writer: 'S2-T06, S2-T15',
    implemented: true,
    reason: '',
    hero: false,
    layerTypes: ['ScatterplotLayer'],
    metricKeys: PLACE,
  },
  {
    key: 'release_units',
    table: 'release_unit',
    className: 'Frame',
    writer: 'S5-T01',
    implemented: false,
    reason: 'class is not Public',
    hero: false,
    layerTypes: ['H3HexagonLayer'],
    metricKeys: [],
  },
  {
    key: 'openings',
    table: 'pub_licence_issued',
    className: 'Public',
    writer: 'S2-T03',
    implemented: false,
    reason: OUTSIDE,
    hero: true,
    layerTypes: ['GeoJsonLayer'],
    metricKeys: [],
  },
  {
    key: 'closures',
    table: 'pub_licence_cancelled',
    className: 'Public',
    writer: 'S2-T03',
    implemented: false,
    reason: OUTSIDE,
    hero: true,
    layerTypes: ['GeoJsonLayer'],
    metricKeys: [],
  },
  {
    key: 'firm_density',
    table: 'pub_register_company',
    className: 'Public',
    writer: 'unnamed (OI-162)',
    implemented: false,
    reason: 'OI-162: the register-company map task is unnamed',
    hero: true,
    layerTypes: ['H3HexagonLayer'],
    metricKeys: [],
  },
  {
    key: 'company_points',
    table: 'pub_register_company',
    className: 'Public',
    writer: 'S3-T12',
    implemented: true,
    reason: '',
    hero: false,
    layerTypes: ['ScatterplotLayer'],
    metricKeys: ['register_company_point'],
  },
  {
    key: 'fc_firms_per_tower',
    table: 'pub_register_company',
    className: 'Public',
    writer: 'S3-T17',
    implemented: true,
    reason: '',
    hero: true,
    layerTypes: ['ScatterplotLayer', 'GeoJsonLayer'],
    metricKeys: ['firms_per_tower'],
  },
  {
    key: 'land_prices',
    table: 'pub_land_price',
    className: 'Public',
    writer: 'S2-T19',
    implemented: true,
    reason: '',
    hero: true,
    layerTypes: ['GeoJsonLayer'],
    metricKeys: ['guide_price_class'],
  },
  {
    key: 'rail_plan',
    table: 'pub_rail_plan',
    className: 'Public',
    writer: 'S2-T19',
    implemented: true,
    reason: '',
    hero: false,
    layerTypes: ['PathLayer', 'ScatterplotLayer', 'GeoJsonLayer'],
    metricKeys: ['rail_feature'],
  },
  {
    // S3-T12: whole source-zone outlines with a bound count, beside rail.
    key: 'accidents',
    table: 'pub_accident_zone',
    className: 'Public',
    writer: 'S3-T12',
    implemented: true,
    reason: '',
    hero: false,
    layerTypes: ['GeoJsonLayer'],
    metricKeys: ['accident_count'],
  },
  {
    key: 'health_centres',
    table: 'pub_health_centre',
    className: 'Public',
    writer: 'S2-T19',
    implemented: true,
    reason: '',
    hero: false,
    layerTypes: ['ScatterplotLayer', 'GeoJsonLayer'],
    metricKeys: ['health_centre_name'],
  },
  {
    key: 'zoning',
    table: 'pub_zoning',
    className: 'Public',
    writer: 'S2-T19',
    implemented: true,
    reason: '',
    hero: false,
    layerTypes: ['GeoJsonLayer'],
    metricKeys: ['permitted_use'],
  },
  {
    key: 'commercial_points',
    table: 'pub_poi_comm',
    className: 'Public',
    writer: 'S2-T19',
    implemented: true,
    reason: '',
    hero: false,
    layerTypes: ['ScatterplotLayer'],
    metricKeys: ['poi_category'],
  },
  {
    key: 'address_points',
    table: 'pub_address_point',
    className: 'Public',
    writer: 'S2-T19',
    implemented: true,
    reason: '',
    hero: false,
    layerTypes: ['ScatterplotLayer'],
    metricKeys: ['address_zone', 'address_street', 'address_building'],
  },
  {
    key: 'parcels',
    table: 'pub_parcel',
    className: 'Public',
    writer: 'S2-T19',
    implemented: true,
    reason: '',
    hero: false,
    layerTypes: ['GeoJsonLayer'],
    metricKeys: ['parcel_area', 'plot_state'],
  },
  {
    key: 'landmarks',
    table: 'gazetteer',
    className: 'Frame (Public)',
    writer: 'S2-T19',
    implemented: true,
    reason: '',
    hero: false,
    layerTypes: ['ScatterplotLayer'],
    metricKeys: ['landmark_name'],
  },
  {
    key: 'fdi_projects',
    table: 'fdi_projects',
    className: 'Public',
    writer: 'S2-T12',
    implemented: true,
    reason: '',
    hero: true,
    layerTypes: ['ScatterplotLayer'],
    metricKeys: FDI,
  },
  {
    key: 'property_prices',
    table: 'pub_property_sale',
    className: 'Public',
    writer: 'S2-T19',
    implemented: true,
    reason: '',
    hero: true,
    layerTypes: ['GeoJsonLayer'],
    metricKeys: ['district_sale'],
  },
  {
    key: 'construction_pipeline',
    table: 'pub_building_permits',
    className: 'Public',
    writer: 'S2-T11',
    implemented: false,
    reason: OUTSIDE,
    hero: true,
    layerTypes: ['GeoJsonLayer'],
    metricKeys: [],
  },
  {
    key: 'night_lights',
    table: 'pub_night_lights',
    className: 'Public',
    writer: 'S2-T14',
    implemented: true,
    reason: '',
    hero: true,
    layerTypes: ['H3HexagonLayer'],
    metricKeys: ['radiance_class'],
  },
];

export function layerEntry(key: string): LayerEntry | undefined {
  return LAYER_ENTRIES.find((entry) => entry.key === key);
}

export interface HeroState {
  visibleHero: string | null;
  fixtureHero: 'public' | 'synthetic' | 'simulated' | null;
}

export function selectHero(
  state: HeroState,
  key: string,
): { ok: true; state: HeroState } | { ok: false; code: 'unknown_layer' } {
  const entry = layerEntry(key);
  if (!entry?.hero) return { ok: false, code: 'unknown_layer' };
  return { ok: true, state: { ...state, visibleHero: key } };
}

export function labelsDrawn(state: HeroState): boolean {
  if (state.fixtureHero === 'synthetic' || state.fixtureHero === 'simulated')
    return false;
  return true;
}
