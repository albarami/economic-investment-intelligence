/**
 * Injected layer payload. The browser does not fetch it.
 * Display decisions arrive already made; this shape holds no score of a place.
 */
import type { SourceGeometry } from './source-geometry';
import type { ReferenceKind } from '../../facts/FactChip';
import { CLASS_RAMP, DIRECTION_KEYS } from './ramp';

export type TextSegment =
  | { kind: 'plain'; text: string }
  | {
      kind: 'reference';
      referenceKind: ReferenceKind;
      value: string;
      recordId: string;
    };

export type LayerProvenance =
  'public' | 'synthetic' | 'simulated' | 'suppressed';

export type LayerSubject =
  | 'place'
  | 'business'
  | 'building'
  | 'fdi_project'
  | 'gis_feature'
  | 'statistic'
  | 'geometry';

export type GeometryKind = 'point' | 'line' | 'outline' | 'fill' | 'hex';

export interface AttributionSource {
  sourceId: string;
  /** Plain segments and reference segments. The browser does not split them. */
  attribution: TextSegment[];
  retrievalDate: string;
  publisher: TextSegment[];
  datasetOrPage: string;
  licenceOrTerms: string;
  /** The source release used by the release build, at its published precision. */
  sourceRelease?: {
    referenceKind: 'calendar_date' | 'calendar_month' | 'calendar_year';
    value: string;
    recordId: string;
  };
  year?: string;
  /** Source categories as typed segments. The browser does not split them. */
  categories?: readonly (readonly TextSegment[])[];
  geographyCode?: string;
}

/** Document 08 payload row: the investment layer's four credit fields. */
export interface InvestmentCredits {
  publisher: TextSegment[];
  gatherer: TextSegment[];
  read_on: string;
  dashboard_url: string;
}

export interface FdiFilterValue {
  sector?: string;
  source_country?: string;
  period?: string;
  stated_location?: string;
}

export type FdiFilterOption =
  | string
  | {
      key: string;
      label: readonly TextSegment[];
    };

export interface LayerFeature {
  feature_id: string;
  metric_key: string;
  provenance: LayerProvenance;
  subject: LayerSubject;
  geometry_kind: GeometryKind;
  display_rule?: 'kept' | 'withheld';
  label_key?: string;
  status_key?: string;
  cell?: string;
  resolution?: 8 | 9;
  draw_native?: boolean;
  class_id?: string;
  class_group?: string;
  place_key?: string | null;
  force_invented_mark?: boolean;
  words?: Record<string, string>;
  /** Closed published FDI fields; digit-bearing text arrives as typed references. */
  field_segments?: Partial<
    Record<import('./fdi').FdiWordField, readonly TextSegment[]>
  >;
  fact_id?: string;
  year?: string;
  caveat_keys?: string[];
  apportioned_from?: string;
  evidence_status?: 'observed' | 'inferred' | 'still_to_test';
  method_id?: string;
  geography_code?: string;
  identifier?: string;
  omit_mark?: boolean;
  omit_year?: boolean;
  /** Record-level source. Absent means the layer source. */
  source_id?: string;
  capex_fact_id?: string;
  jobs_fact_id?: string;
  lon_fact_id?: string;
  lat_fact_id?: string;
  /** Typed announced date. A date in `words` stays a plain word and is refused. */
  announced?: {
    referenceKind: 'calendar_year' | 'calendar_month' | 'calendar_date';
    value: string;
    recordId: string;
  };
  /** Visible name when it may hold a digit. Never the feature id. */
  name_segments?: readonly TextSegment[];
  filter?: FdiFilterValue;
  address?: { zone: string; street: string; building: string };
  /** Closed source geometry, mutually exclusive with position/path/ring. */
  geometry?: SourceGeometry;
  /** Supplied point. The browser does not place a feature that lacks one. */
  position?: readonly [number, number];
  /** Supplied line. */
  path?: readonly (readonly [number, number])[];
  /** Supplied polygon ring. */
  ring?: readonly (readonly [number, number])[];
}

export const NOT_RANKED_REASONS = [
  'below_ranking_floor',
  'no_denominator',
  'missing_input',
] as const;
export interface NotRankedZone {
  feature_id: string;
  geometry?: Extract<SourceGeometry, { type: 'Polygon' | 'MultiPolygon' }>;
  ring?: readonly (readonly [number, number])[];
  reason_key: (typeof NOT_RANKED_REASONS)[number];
  name_segments: readonly TextSegment[];
}
export interface ClassBreak {
  class_id: FcLegendClass;
  fact_id: string;
}
export interface ClassBreakGroup {
  group_key: string | null;
  breaks: readonly ClassBreak[];
}
export const CLASSED_LAYER_KEYS = [
  'night_lights',
  'land_prices',
  'zone_electricity_growth',
] as const;

export interface LayerRequest {
  key: string;
  visible: boolean;
  source_chain_fact_id: string;
  source_id: string;
  features: LayerFeature[];
  not_ranked?: readonly NotRankedZone[];
  class_breaks?: readonly ClassBreakGroup[];
  filled?: boolean;
  forced_type?: string;
}

export interface SplitChipInput {
  provenance: LayerProvenance;
  evidence_status: 'observed' | 'inferred' | 'still_to_test';
  source_id: string;
  year: string;
  categories: readonly (readonly TextSegment[])[];
  geography_code: string;
  source_geography: string;
  as_layer?: boolean;
}

export interface NightLegendInput {
  month: string;
  direction: string;
  class_id: string;
  unit: string;
  caveat_key: string;
  hide_acknowledgement?: boolean;
}

export interface FcCardField {
  key: string;
  text?: string;
  segments?: readonly TextSegment[];
}

export interface FcCompanyRow {
  feature_id: string;
  row_id: string;
  fields: readonly FcCardField[];
  wage_key?: string;
  identifier?: string;
  employee_count?: string;
  attached?: string;
}

/**
 * S3-T12 box 12: the card of one register company behind an establishment
 * point. The employee count is Synthetic and lives only in the Protected
 * `register_company_list`; a public_only release holds it as absent, with
 * its reason, and never as a zero (DAT-140).
 */
export const COMPANY_CARD_FIELDS = ['establishment_nationality'] as const;
export const COMPANY_ABSENT_REASON = 'protected_not_in_public_release';
export interface CompanyEmployeeCount {
  state: 'absent';
  reason_key: typeof COMPANY_ABSENT_REASON;
}
/** Exactly a closed key and its typed segments; no bare text, nothing else. */
export interface CompanyCardField {
  key: (typeof COMPANY_CARD_FIELDS)[number];
  segments: readonly TextSegment[];
}
export interface CompanyCardRow {
  feature_id: string;
  row_id: string;
  fields: readonly CompanyCardField[];
  employee_count: CompanyEmployeeCount;
}

/** The ramp's direction list. The section union is this array's members. */
export const FC_DIRECTION_KEYS = DIRECTION_KEYS;
export type FcDirection = (typeof FC_DIRECTION_KEYS)[number];

/** The five legend class keys. A district count is not one of them. */
export const FC_LEGEND_CLASS_KEYS = [
  'band_low',
  'band_mid_low',
  'band_mid',
  'band_mid_high',
  'band_high',
] as const satisfies readonly (keyof typeof CLASS_RAMP)[];
export type FcLegendClass = (typeof FC_LEGEND_CLASS_KEYS)[number];

/** Screen notes the firms legend may show. Today one key. */
export const SCREEN_NOTE_KEYS = ['zone_without_district'] as const;
export type ScreenNoteKey = (typeof SCREEN_NOTE_KEYS)[number];

type SameMembers<Left, Right> = [Left] extends [Right]
  ? [Right] extends [Left]
    ? true
    : false
  : false;

const legendKeysMatchRamp: SameMembers<FcLegendClass, keyof typeof CLASS_RAMP> =
  true;
void legendKeysMatchRamp;

export interface FcFirmsSection {
  direction: FcDirection;
  companies: readonly FcCompanyRow[];
  coverage_note_keys: readonly ScreenNoteKey[];
  breaks: readonly { class_id: FcLegendClass; fact_id: string }[];
  no_data?: boolean;
}

export interface LayerPayload {
  layers: LayerRequest[];
  sources: AttributionSource[];
  gazetteer_points: string[];
  credits?: InvestmentCredits;
  fixture_hero?: 'public' | 'synthetic' | 'simulated';
  company_search?: string;
  filter_key?: string;
  draw_boundaries?: boolean;
  frame_under_source?: boolean;
  omit_listings_note?: boolean;
  count_fact_ids?: string[];
  count_facts?: readonly { fact_id: string; year: string }[];
  count_without_fact?: boolean;
  filter_options?: {
    sector: readonly FdiFilterOption[];
    source_country: readonly FdiFilterOption[];
    period: readonly FdiFilterOption[];
    stated_location: readonly FdiFilterOption[];
  };
  split_chip?: SplitChipInput;
  night?: NightLegendInput;
  fc_firms?: FcFirmsSection;
  company_cards?: readonly CompanyCardRow[];
  visitor_fact_id?: string;
  estimated_people_fact_id?: string;
  selected_feature_id?: string;
  address_numbers?: { zone: string; street: string; building: string };
}
