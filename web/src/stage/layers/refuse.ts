import { validSourceGeometry } from './source-geometry';
/**
 * Closed refusal codes. Each one is a planted input in the layer tests.
 * Metric keys are matched as strings. No feature value is read as a number.
 */
import type { FactRegistry } from '../../facts/registry';
import {
  bindingProblem,
  chainProblem,
  creditsReady,
  countYearMissing,
  digitInPlain,
  companyPointsProblem,
  fcCompanyProblem,
  fcSectionProblem,
  fdiReferenceProblem,
  geometryDeckType,
  plainHoldsDigit,
  publishedFdiPoint,
  sameSegmentList,
  segmentsBlank,
} from './checks';
import { fdiFilterAllowed, FDI_FILTERS, FDI_WORD_FIELDS } from './fdi';
import { legendLineSamples } from './legend';
import { expandNightCells, guardHexResolution } from './night';
import type {
  InvestmentCredits,
  LayerFeature,
  LayerPayload,
  LayerRequest,
  TextSegment,
} from './payload';
import {
  CLASSED_LAYER_KEYS,
  NOT_RANKED_REASONS,
  FC_LEGEND_CLASS_KEYS,
  type ClassBreakGroup,
  type NotRankedZone,
} from './payload';
import { fcFeatureClass, knownDirection, rampToken } from './ramp';
import { labelsDrawn, layerEntry, type LayerEntry } from './registry';
import { type RefusalCode } from './codes';

export { REFUSAL_CODES, type RefusalCode } from './codes';

const PARCEL_FORBIDDEN = new Set([
  'approved',
  'available',
  'vacant',
  'for_sale',
]);
const ZONING_FORBIDDEN = new Set(['approval', 'permit', 'availability']);
const GUIDE_FORBIDDEN = new Set(['deal_price', 'rent']);
const WAGE_KEYS = new Set(['wage', 'wage_bill', 'wage_month']);
const ESTIMATE_METRICS = new Set(['fdi_capex', 'fdi_jobs']);
export const OUTLINE_LAYER_KEYS = new Set([
  'parcels',
  'health_centres',
  'rail_plan',
  'accidents',
]);
/** The only presentation an accident outline may carry: never a verdict. */
const ACCIDENT_LABELS = new Set(['accident_count_context']);
const ACCIDENT_CAVEAT = 'accidents_recorded_not_risk';
/** The reviewed keys of an accident feature, exactly as the read sends them. */
const ACCIDENT_FEATURE_KEYS = new Set([
  'feature_id',
  'metric_key',
  'provenance',
  'fact_id',
  'subject',
  'geometry_kind',
  'source_id',
  'geography_code',
  'source_zone',
  'source_zone_fact_id',
  'year',
  'label_key',
  'evidence_status',
  'caveat_keys',
  'ring',
  'geometry',
  'name_segments',
]);
/** The word and the status the screen renders, and the layer of each. */
export const PRESENTATION_OWNER = {
  permitted_use: 'zoning',
  permitted_empty: 'parcels',
} as const;
/** The one layer whose features carry published address numbers. */
export const ADDRESS_OWNER = 'address_points';
/** Words any layer may name its feature with; the screen reads no others. */
const NAME_WORDS = ['name', 'company'];
const STATUS_LAYERS = new Set([
  'rail_plan',
  'parcels',
  'zoning',
  'land_prices',
]);
const LABEL_SUBJECTS = new Set(['place', 'business']);

export interface DrawnHex {
  cell: string;
  factId: string;
  classId: string;
  featureId: string;
}

export interface DrawnLayer {
  key: string;
  sourceChainFactId: string;
  retrievalDate: string;
  attribution: TextSegment[];
  sourceIds: string[];
  layerType: string;
  treatment: 'solid';
  filled: boolean;
  marks: string[];
  labels: string[];
  hexes: DrawnHex[];
  features: LayerFeature[];
  notRanked: readonly NotRankedZone[];
  classBreaks: readonly ClassBreakGroup[];
}

export interface DrawModel {
  fcFirms: LayerPayload['fc_firms'] | null;
  layers: DrawnLayer[];
  labelsDrawn: boolean;
  listingsNote: boolean;
  boundarySentence: true;
  boundaryOutline: false;
  visibleHero: string | null;
  fdiListed: string[];
  fdiMarks: string[];
  credits: InvestmentCredits | null;
  filters: readonly string[];
  splitCategories: readonly (readonly TextSegment[])[] | null;
  night: LayerPayload['night'] | null;
  nightAttribution: TextSegment[];
  countFactIds: readonly string[];
  lineSamples: ReturnType<typeof legendLineSamples>;
}

export type AcceptResult =
  | { ok: false; code: RefusalCode; layerKey?: string }
  | { ok: true; draw: DrawModel };

const RAMP_LAYERS = new Set([
  'zone_electricity_growth',
  'night_lights',
  'land_prices',
  'fc_firms_per_tower',
]);

function refuse(code: RefusalCode, layerKey?: string): AcceptResult {
  return layerKey === undefined
    ? { ok: false, code }
    : { ok: false, code, layerKey };
}

/** Not a nonempty string: the uncast HTTP body can hold any JSON value. */
function blank(value: unknown): boolean {
  return typeof value !== 'string' || value.trim() === '';
}

/** An optional text: absent or null reads as empty, any other non-string as null. */
function optionalText(value: unknown): string | null {
  const read = value ?? '';
  return typeof read === 'string' ? read : null;
}

/** A caveat key counts only as a whole member of a real list. */
function hasCaveat(feature: LayerFeature, key: string): boolean {
  return (
    Array.isArray(feature.caveat_keys) && feature.caveat_keys.includes(key)
  );
}

export function featureProblem(
  entry: LayerEntry,
  request: LayerRequest,
  feature: LayerFeature,
  payload: LayerPayload,
): RefusalCode | null {
  if (
    feature.geometry !== undefined &&
    (!validSourceGeometry(feature.geometry) ||
      feature.position !== undefined ||
      feature.path !== undefined ||
      feature.ring !== undefined ||
      (feature.geometry.type === 'Point'
        ? feature.geometry_kind !== 'point'
        : feature.geometry.type === 'LineString'
          ? feature.geometry_kind !== 'line'
          : !['fill', 'outline'].includes(feature.geometry_kind)))
  )
    return 'source_geometry_invalid';
  if (feature.words) {
    for (const value of Object.values(feature.words)) {
      if (plainHoldsDigit(value)) return 'numeral_in_plain_segment';
    }
  }
  if (digitInPlain(feature.name_segments)) return 'numeral_in_plain_segment';
  if (
    Object.keys(feature.field_segments ?? {}).some(
      (key) => !(FDI_WORD_FIELDS as readonly string[]).includes(key),
    )
  )
    return 'measure_on_named_feature';
  if (Object.values(feature.field_segments ?? {}).some(digitInPlain))
    return 'numeral_in_plain_segment';
  if (entry.key === 'accidents') {
    const accident = accidentProblem(feature);
    if (accident) return accident;
  }
  if (presentationProblem(entry.key, feature))
    return 'presentation_field_unexpected';
  if (!entry.layerTypes.includes(geometryDeckType(feature.geometry_kind))) {
    return 'wrong_layer_type';
  }
  if (entry.key === 'fc_firms_per_tower') {
    if (!fcFeatureClass(feature.class_id ?? '')) return 'night_class_missing';
  } else if (RAMP_LAYERS.has(entry.key) && !rampToken(feature.class_id ?? '')) {
    return 'night_class_missing';
  }
  if (feature.display_rule === 'withheld') return 'below_display_threshold';
  if (
    (optionalText(feature.identifier)?.startsWith('SYN-') ?? true) ||
    WAGE_KEYS.has(feature.metric_key)
  ) {
    return 'wage_or_synthetic_id';
  }
  if (feature.provenance !== 'public') return 'not_public';
  if (
    (payload.fixture_hero === 'synthetic' ||
      payload.fixture_hero === 'simulated') &&
    feature.label_key &&
    LABEL_SUBJECTS.has(feature.subject)
  ) {
    return 'label_while_synthetic_hero';
  }
  if (feature.force_invented_mark) return 'invented_point';
  if (feature.omit_mark) return 'fdi_mark_missing';
  if (feature.subject === 'fdi_project' && (feature.omit_year || !feature.year))
    return 'fdi_year_missing';
  if (
    (ESTIMATE_METRICS.has(feature.metric_key) ||
      Boolean(feature.capex_fact_id) ||
      Boolean(feature.jobs_fact_id)) &&
    !hasCaveat(feature, 'fdi_estimates')
  ) {
    return 'announced_estimate_unlabelled';
  }
  if (!entry.metricKeys.includes(feature.metric_key))
    return 'measure_on_named_feature';
  if (entry.key === 'rail_plan' && feature.geometry_kind === 'point') {
    if (feature.status_key === 'operating') return 'station_as_operating';
    if (feature.status_key !== 'planned') return 'planned_label_missing';
  }
  if (
    entry.key === 'rail_plan' &&
    feature.geometry_kind === 'line' &&
    feature.status_key !== undefined &&
    feature.status_key !== 'planned'
  )
    return 'rail_as_operating';
  if (
    entry.key === 'parcels' &&
    feature.status_key &&
    PARCEL_FORBIDDEN.has(feature.status_key)
  ) {
    return 'parcel_forbidden_label';
  }
  if (
    entry.key === 'zoning' &&
    feature.status_key &&
    ZONING_FORBIDDEN.has(feature.status_key)
  ) {
    return 'zoning_as_approval';
  }
  if (
    entry.key === 'zoning' &&
    (request.filled || feature.geometry_kind === 'fill')
  ) {
    return 'zoning_categorical_fill';
  }
  if (
    entry.key === 'land_prices' &&
    feature.status_key &&
    GUIDE_FORBIDDEN.has(feature.status_key)
  ) {
    return 'guide_price_as_deal_or_rent';
  }
  if (OUTLINE_LAYER_KEYS.has(entry.key) && request.filled)
    return 'outline_filled';
  if (feature.apportioned_from) {
    if (
      feature.evidence_status !== 'inferred' ||
      blank(feature.method_id) ||
      blank(feature.geography_code)
    ) {
      return 'apportioned_unlabelled';
    }
  }
  if (entry.key === 'address_points' && feature.label_key)
    return 'address_label';
  if (entry.key === 'night_lights' && feature.draw_native)
    return 'mixed_resolution';
  if (entry.key === 'fc_firms_per_tower') {
    if (
      feature.geometry_kind === 'point' &&
      (feature.subject === 'statistic' ||
        (optionalText(feature.geography_code)?.startsWith('district:') ?? true))
    ) {
      return 'invented_point';
    }
    if (!feature.fact_id) return 'measure_on_named_feature';
  }
  return null;
}

/** A word or status outside its layer's closed presentation (RV1 finding 1). */
export function presentationProblem(
  layerKey: string,
  feature: LayerFeature,
): boolean {
  const words: readonly string[] = [
    ...NAME_WORDS,
    ...(layerKey === 'fdi_projects' ? FDI_WORD_FIELDS : []),
    ...(layerKey === PRESENTATION_OWNER.permitted_use ? ['permitted_use'] : []),
  ];
  if (Object.keys(feature.words ?? {}).some((key) => !words.includes(key)))
    return true;
  if (feature.address !== undefined && layerKey !== ADDRESS_OWNER) return true;
  const status = feature.status_key;
  if (status === undefined) return false;
  return (
    !STATUS_LAYERS.has(layerKey) ||
    (status === 'permitted_empty' &&
      layerKey !== PRESENTATION_OWNER.permitted_empty)
  );
}

/** An accident count stays on its whole source-zone outline (S3-T12). */
function accidentProblem(feature: LayerFeature): RefusalCode | null {
  if (Object.keys(feature).some((key) => !ACCIDENT_FEATURE_KEYS.has(key)))
    return 'accident_field_unexpected';
  if (feature.geometry_kind === 'fill') return 'outline_filled';
  if (feature.geometry_kind === 'point' || feature.geometry_kind === 'hex')
    return 'accident_point_map';
  if (!ACCIDENT_LABELS.has(feature.label_key ?? ''))
    return 'accident_safety_verdict';
  if (!hasCaveat(feature, ACCIDENT_CAVEAT)) return 'accident_caveat_missing';
  // An outline without its bound count would skip the geography binding.
  if (!feature.fact_id) return 'legend_count_unbound';
  if (blank(feature.source_zone) || blank(feature.source_zone_fact_id))
    return 'accident_zone_unbound';
  return null;
}

function splitProblem(payload: LayerPayload): RefusalCode | null {
  const split = payload.split_chip;
  if (!split) return null;
  if (split.as_layer) return 'split_as_layer';
  if (split.geography_code !== split.source_geography)
    return 'split_off_geography';
  if (
    split.provenance !== 'public' ||
    split.evidence_status !== 'observed' ||
    blank(split.source_id) ||
    blank(split.year) ||
    split.categories.length === 0
  ) {
    return 'split_incomplete';
  }
  const source = payload.sources.find(
    (row) => row.sourceId === split.source_id,
  );
  if (!source || source.year !== split.year) return 'split_incomplete';
  if (source.geographyCode !== split.geography_code) return 'split_incomplete';
  const delivered = source.categories ?? [];
  if (
    delivered.length !== split.categories.length ||
    delivered.some(
      (item, index) => !sameSegmentList(item, split.categories[index] ?? []),
    )
  ) {
    return 'split_incomplete';
  }
  return null;
}

function nightProblem(
  payload: LayerPayload,
  nightOn: boolean,
): RefusalCode | null {
  if (!nightOn) return null;
  const night = payload.night;
  if (!night || blank(night.unit) || night.unit !== 'radiance_nw_cm2_sr') {
    return 'night_unit_missing';
  }
  if (blank(night.month)) return 'night_month_missing';
  if (blank(night.direction) || !knownDirection(night.direction)) {
    return 'night_direction_missing';
  }
  if (blank(night.class_id) || !rampToken(night.class_id)) {
    return 'night_class_missing';
  }
  if (night.caveat_key !== 'night_lights_not_activity')
    return 'night_caveat_missing';
  if (night.hide_acknowledgement) return 'night_acknowledgement_missing';
  return null;
}

function notRankedProblem(layer: LayerRequest): RefusalCode | null {
  if (layer.not_ranked === undefined) return null;
  if (
    layer.key !== 'zone_electricity_growth' ||
    !Array.isArray(layer.not_ranked)
  )
    return 'not_ranked_invalid';
  const seen = new Set(layer.features.map((f) => f.feature_id));
  for (const zone of layer.not_ranked) {
    if (
      !zone ||
      Object.keys(zone).sort().join(',') !==
        (zone.geometry === undefined
          ? 'feature_id,name_segments,reason_key,ring'
          : 'feature_id,geometry,name_segments,reason_key') ||
      typeof zone.feature_id !== 'string' ||
      !zone.feature_id ||
      seen.has(zone.feature_id) ||
      !NOT_RANKED_REASONS.some((r) => r === zone.reason_key) ||
      !Array.isArray(zone.name_segments) ||
      zone.name_segments.length === 0 ||
      (zone.geometry !== undefined
        ? !validSourceGeometry(zone.geometry) ||
          !['Polygon', 'MultiPolygon'].includes(zone.geometry.type)
        : !Array.isArray(zone.ring) ||
          zone.ring.length < 4 ||
          zone.ring.some(
            (p: readonly number[]) =>
              !Array.isArray(p) ||
              p.length !== 2 ||
              p.some(
                (n: number) => typeof n !== 'number' || !Number.isFinite(n),
              ),
          ))
    )
      return 'not_ranked_invalid';
    if (digitInPlain(zone.name_segments)) return 'numeral_in_plain_segment';
    if (
      zone.name_segments.some((s: TextSegment) =>
        s.kind === 'plain'
          ? typeof s.text !== 'string' || !s.text.trim()
          : s.kind !== 'reference' ||
            s.referenceKind !== 'published_text' ||
            typeof s.value !== 'string' ||
            !s.value.trim() ||
            typeof s.recordId !== 'string',
      )
    )
      return 'not_ranked_invalid';
    seen.add(zone.feature_id);
  }
  return null;
}

function classBreakProblem(
  layer: LayerRequest,
  registry?: FactRegistry,
): RefusalCode | null {
  const classed = CLASSED_LAYER_KEYS.some((k) => k === layer.key);
  if (!classed)
    return layer.class_breaks === undefined ? null : 'class_break_invalid';
  if (layer.features.length === 0)
    return layer.class_breaks === undefined ? null : 'class_break_invalid';
  if (!Array.isArray(layer.class_breaks) || layer.class_breaks.length === 0)
    return 'class_break_missing';
  if (
    layer.key === 'land_prices' &&
    layer.features.some(
      (f) => typeof f.class_group !== 'string' || !f.class_group.trim(),
    )
  )
    return 'class_break_missing';
  const groups = new Set<string | null>();
  for (const group of layer.class_breaks) {
    if (
      !group ||
      Object.keys(group).sort().join(',') !== 'breaks,group_key' ||
      (layer.key === 'land_prices'
        ? typeof group.group_key !== 'string' || !group.group_key.trim()
        : group.group_key !== null) ||
      groups.has(group.group_key) ||
      !Array.isArray(group.breaks) ||
      group.breaks.length === 0
    )
      return 'class_break_invalid';
    groups.add(group.group_key);
    const features = layer.features.filter(
      (f) => layer.key !== 'land_prices' || f.class_group === group.group_key,
    );
    let remaining: readonly string[] = FC_LEGEND_CLASS_KEYS;
    const seen = new Set<string>();
    for (const band of group.breaks) {
      if (
        !band ||
        Object.keys(band).sort().join(',') !== 'class_id,fact_id' ||
        typeof band.fact_id !== 'string'
      )
        return 'class_break_invalid';
      const index = remaining.indexOf(band.class_id);
      if (index === -1 || seen.has(band.class_id)) return 'class_break_invalid';
      remaining = remaining.slice(index + 1);
      seen.add(band.class_id);
      if (
        !features.some(
          (f) => f.class_id === band.class_id && f.fact_id === band.fact_id,
        ) ||
        (registry && chainProblem(band.fact_id, registry))
      )
        return 'class_break_invalid';
    }
    if (features.some((f) => !seen.has(f.class_id ?? '')))
      return 'class_break_missing';
  }
  if (
    layer.features.some(
      (f) => !groups.has(layer.key === 'land_prices' ? f.class_group! : null),
    )
  )
    return 'class_break_missing';
  return null;
}

function defaultType(entry: LayerEntry, feature: LayerFeature): string {
  if (feature.geometry_kind === 'hex') return 'H3HexagonLayer';
  if (feature.geometry_kind === 'line') return 'PathLayer';
  if (feature.geometry_kind === 'point') {
    return entry.layerTypes.includes('ScatterplotLayer')
      ? 'ScatterplotLayer'
      : entry.layerTypes[0]!;
  }
  return entry.layerTypes.includes('GeoJsonLayer')
    ? 'GeoJsonLayer'
    : entry.layerTypes[0]!;
}

export function acceptPayload(
  payload: LayerPayload,
  registry?: FactRegistry,
): AcceptResult {
  const visible = payload.layers.filter((layer) => layer.visible);
  for (const layer of visible) {
    if (!layerEntry(layer.key)) return refuse('unknown_layer');
  }
  for (const layer of visible) {
    const entry = layerEntry(layer.key);
    if (entry && !entry.implemented)
      return refuse('not_implemented', layer.key);
  }
  const heroes = visible.filter((layer) => layerEntry(layer.key)?.hero);
  if (heroes.length > 1) return refuse('two_hero_layers');
  if (payload.draw_boundaries || payload.frame_under_source)
    return refuse('boundaries_absent');
  if (payload.company_search !== undefined)
    return refuse('company_name_lookup');
  if (
    payload.filter_key !== undefined &&
    !fdiFilterAllowed(payload.filter_key)
  ) {
    return refuse('filter_outside_list');
  }
  if (payload.omit_listings_note) return refuse('listings_note_removed');
  if (payload.count_without_fact) return refuse('legend_count_unbound');
  if (countYearMissing(payload)) return refuse('fdi_year_missing');
  const sectionVerdict = fcSectionProblem(
    payload.fc_firms,
    registry,
    payload.count_facts,
  );
  if (sectionVerdict && !sectionVerdict.ok) return refuse(sectionVerdict.code);
  const companyCode = fcCompanyProblem(payload);
  if (companyCode) return refuse(companyCode);
  const pointsCode = companyPointsProblem(payload, registry);
  if (pointsCode) return refuse(pointsCode);
  for (const source of payload.sources) {
    if (
      digitInPlain(source.attribution) ||
      digitInPlain(source.publisher) ||
      (source.categories ?? []).some((category) => digitInPlain(category))
    ) {
      return refuse('numeral_in_plain_segment');
    }
  }
  if (
    payload.credits &&
    (digitInPlain(payload.credits.publisher) ||
      digitInPlain(payload.credits.gatherer))
  ) {
    return refuse('numeral_in_plain_segment');
  }
  if (payload.filter_options) {
    for (const choices of Object.values(payload.filter_options)) {
      if (
        choices.some((choice) =>
          typeof choice === 'string'
            ? plainHoldsDigit(choice)
            : digitInPlain(choice.label),
        )
      ) {
        return refuse('numeral_in_plain_segment');
      }
      if (registry)
        for (const choice of choices) {
          if (typeof choice === 'string') continue;
          const problem = fdiReferenceProblem(choice.label, registry);
          if (problem) return refuse(problem);
        }
    }
  }
  const splitCode = splitProblem(payload);
  if (splitCode) return refuse(splitCode);

  const drawn: DrawnLayer[] = [];
  let nightOn = false;
  for (const layer of visible) {
    const entry = layerEntry(layer.key);
    if (!entry) return refuse('unknown_layer');
    if (blank(layer.source_chain_fact_id))
      return refuse('incomplete_source_chain');
    if (registry && chainProblem(layer.source_chain_fact_id, registry)) {
      return refuse('incomplete_source_chain');
    }
    if (layer.forced_type && !entry.layerTypes.includes(layer.forced_type)) {
      return refuse('wrong_layer_type');
    }
    const sourceIds: string[] = [];
    for (const feature of layer.features) {
      const problem = featureProblem(entry, layer, feature, payload);
      if (problem) return refuse(problem);
      if (registry) {
        const bound = bindingProblem(entry, feature, registry);
        if (bound) return refuse(bound);
      }
      const sourceId = feature.source_id || layer.source_id;
      if (!sourceIds.includes(sourceId)) sourceIds.push(sourceId);
    }
    if (sourceIds.length === 0) sourceIds.push(layer.source_id);
    for (const sourceId of sourceIds) {
      const row = payload.sources.find((item) => item.sourceId === sourceId);
      if (!row || segmentsBlank(row.attribution))
        return refuse('missing_attribution');
    }
    const source = payload.sources.find(
      (row) => row.sourceId === layer.source_id,
    );
    if (!source || segmentsBlank(source.attribution))
      return refuse('missing_attribution');
    if (entry.key === 'fdi_projects' && !creditsReady(payload.credits))
      return refuse('missing_attribution');
    if (entry.key === 'night_lights') nightOn = true;
    const layerType = defaultType(
      entry,
      layer.features[0] ?? {
        feature_id: '',
        metric_key: '',
        provenance: 'public',
        subject: 'geometry',
        geometry_kind: 'point',
      },
    );
    const hexes: DrawnHex[] = [];
    if (entry.key === 'night_lights') {
      for (const feature of layer.features) {
        if (!feature.cell || !feature.resolution) continue;
        const expanded = expandNightCells([
          {
            cell: feature.cell,
            resolution: feature.resolution,
            factId: feature.fact_id ?? layer.source_chain_fact_id,
          },
        ]);
        const guarded = guardHexResolution(
          expanded.cells.map((cell) => cell.cell),
        );
        if (!guarded.ok) return refuse('mixed_resolution');
        for (const cell of expanded.cells) {
          hexes.push({
            cell: cell.cell,
            factId: cell.factId,
            classId: feature.class_id ?? '',
            featureId: feature.feature_id,
          });
        }
      }
    }
    const showLabels = labelsDrawn({
      visibleHero: heroes[0]?.key ?? null,
      fixtureHero: payload.fixture_hero ?? null,
    });
    drawn.push({
      key: entry.key,
      sourceChainFactId: layer.source_chain_fact_id,
      retrievalDate: source.retrievalDate,
      attribution: source.attribution,
      sourceIds,
      layerType,
      treatment: 'solid',
      filled:
        entry.key === 'zoning' || OUTLINE_LAYER_KEYS.has(entry.key)
          ? false
          : true,
      marks:
        entry.key === 'fdi_projects'
          ? layer.features
              .filter(
                (feature) =>
                  (feature.place_key &&
                    payload.gazetteer_points.includes(feature.place_key)) ||
                  publishedFdiPoint(feature, registry),
              )
              .map((feature) => feature.feature_id)
          : layer.features.map((feature) => feature.feature_id),
      labels: showLabels
        ? layer.features
            .map((feature) => feature.label_key)
            .filter((label): label is string => Boolean(label))
        : [],
      hexes,
      features: layer.features,
      notRanked: layer.not_ranked ?? [],
      classBreaks: layer.class_breaks ?? [],
    });
  }
  const nightCode = nightProblem(payload, nightOn);
  if (nightCode) return refuse(nightCode);
  for (const layer of visible) {
    const excluded = notRankedProblem(layer);
    if (excluded) return refuse(excluded);
    const breaks = classBreakProblem(layer, registry);
    if (breaks) return refuse(breaks);
  }
  const fdi = drawn.find((layer) => layer.key === 'fdi_projects');
  const placesOn = drawn.some(
    (layer) =>
      layer.key === 'public_places' || layer.key === 'commercial_points',
  );
  return {
    ok: true,
    draw: {
      fcFirms: sectionVerdict?.ok ? sectionVerdict.section : null,
      layers: drawn,
      labelsDrawn: labelsDrawn({
        visibleHero: heroes[0]?.key ?? null,
        fixtureHero: payload.fixture_hero ?? null,
      }),
      listingsNote: placesOn,
      boundarySentence: true,
      boundaryOutline: false,
      visibleHero: heroes[0]?.key ?? null,
      fdiListed: fdi ? fdi.features.map((feature) => feature.feature_id) : [],
      fdiMarks: fdi ? fdi.marks : [],
      credits: payload.credits ?? null,
      filters: FDI_FILTERS,
      splitCategories: payload.split_chip?.categories ?? null,
      night: nightOn ? (payload.night ?? null) : null,
      nightAttribution: nightOn
        ? (drawn.find((layer) => layer.key === 'night_lights')?.attribution ??
          [])
        : [],
      countFactIds: payload.count_fact_ids ?? [],
      lineSamples: legendLineSamples(),
    },
  };
}
