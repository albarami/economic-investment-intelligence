/**
 * Fact bindings and geometry types. A value is never read.
 */
import type { ReferenceKind } from '../../facts/FactChip';
import type { FactRegistry } from '../../facts/registry';
import type { Fact, Resolution } from '../../facts/types';
import type { RefusalCode } from './codes';
import {
  COMPANY_ABSENT_REASON,
  COMPANY_CARD_FIELDS,
  FC_DIRECTION_KEYS,
  FC_LEGEND_CLASS_KEYS,
  SCREEN_NOTE_KEYS,
  type FcCardField,
  type FcCompanyRow,
  type FcDirection,
  type FcFirmsSection,
  type FcLegendClass,
  type InvestmentCredits,
  type LayerFeature,
  type LayerPayload,
  type ScreenNoteKey,
  type TextSegment,
} from './payload';
import { rampToken } from './ramp';
import { layerEntry, type LayerEntry } from './registry';
import { isRecord } from '../../guards';

/** A decimal digit of any script, as in `scripts/check-answer.mjs`. */
const PLAIN_DIGIT = /\p{Nd}/u;
const CARD_FIELDS = new Set(['trade_name', 'activity']);
const SYNTHETIC_MARK = 'SYN-';
const REFERENCE_KINDS = [
  'calendar_date',
  'calendar_month',
  'calendar_year',
  'published_text',
] as const satisfies readonly ReferenceKind[];

type SameUnion<Left, Right> = [Left] extends [Right]
  ? [Right] extends [Left]
    ? true
    : false
  : false;

const referenceKindsClosed: SameUnion<
  (typeof REFERENCE_KINDS)[number],
  ReferenceKind
> = true;
void referenceKindsClosed;

export type FcSectionVerdict =
  { ok: true; section: FcFirmsSection } | { ok: false; code: RefusalCode };

function hasOnlyKeys(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  return Object.keys(value).every((key) => keys.includes(key));
}

function isClosedMember<T extends string>(
  keys: readonly T[],
  value: unknown,
): value is T {
  return keys.some((key) => key === value);
}

function optionalString(value: unknown): boolean {
  return value === undefined || typeof value === 'string';
}

function isSegment(value: unknown): value is TextSegment {
  if (!isRecord(value)) return false;
  if (value.kind === 'plain')
    return (
      hasOnlyKeys(value, ['kind', 'text']) && typeof value.text === 'string'
    );
  if (value.kind !== 'reference') return false;
  return (
    hasOnlyKeys(value, ['kind', 'referenceKind', 'value', 'recordId']) &&
    isClosedMember(REFERENCE_KINDS, value.referenceKind) &&
    typeof value.value === 'string' &&
    typeof value.recordId === 'string'
  );
}

function isCardField(value: unknown): value is FcCardField {
  if (!isRecord(value) || typeof value.key !== 'string') return false;
  if (!hasOnlyKeys(value, ['key', 'text', 'segments'])) return false;
  if (!optionalString(value.text)) return false;
  if (value.segments === undefined) return true;
  return Array.isArray(value.segments) && value.segments.every(isSegment);
}

function isCompanyRow(value: unknown): value is FcCompanyRow {
  if (!isRecord(value)) return false;
  if (
    !hasOnlyKeys(value, [
      'feature_id',
      'row_id',
      'fields',
      'wage_key',
      'identifier',
      'employee_count',
      'attached',
    ])
  )
    return false;
  if (
    typeof value.feature_id !== 'string' ||
    typeof value.row_id !== 'string'
  ) {
    return false;
  }
  if (!Array.isArray(value.fields) || !value.fields.every(isCardField)) {
    return false;
  }
  return (
    optionalString(value.wage_key) &&
    optionalString(value.identifier) &&
    optionalString(value.employee_count) &&
    optionalString(value.attached)
  );
}

function isCompanyList(value: unknown): value is readonly FcCompanyRow[] {
  return Array.isArray(value) && value.every(isCompanyRow);
}

function syntheticText(value: string | undefined): boolean {
  return (value ?? '').startsWith(SYNTHETIC_MARK);
}

function fieldHoldsSynthetic(field: FcCardField): boolean {
  if (syntheticText(field.text)) return true;
  for (const segment of field.segments ?? []) {
    if (segment.kind === 'plain' && syntheticText(segment.text)) return true;
    if (
      segment.kind === 'reference' &&
      (syntheticText(segment.value) || syntheticText(segment.recordId))
    ) {
      return true;
    }
  }
  return false;
}

const COMPANY_CARD_KEYS = 'employee_count,feature_id,fields,row_id';
const COMPANY_FIELD_KEYS = 'key,segments';
const COMPANY_COUNT_KEYS = 'reason_key,state';
/** Point keys a register company may carry; a word or label is never one. */
const COMPANY_FEATURE_KEYS = new Set([
  'feature_id',
  'metric_key',
  'provenance',
  'fact_id',
  'subject',
  'geometry_kind',
  'source_id',
  'position',
]);

function hasExactKeys(value: Record<string, unknown>, keys: string): boolean {
  return Object.keys(value).sort().join(',') === keys;
}

/**
 * Every value of a point is a string; a supplied position is one number
 * pair. A point without a position is not placed, as on every layer.
 */
function companyPointValuesClosed(feature: LayerFeature): boolean {
  for (const [key, value] of Object.entries(feature)) {
    if (key !== 'position' && typeof value !== 'string') return false;
  }
  const position: unknown = feature.position;
  return (
    position === undefined ||
    (Array.isArray(position) &&
      position.length === 2 &&
      position.every(
        (value) => typeof value === 'number' && Number.isFinite(value),
      ))
  );
}

/**
 * A fact a register company's point or card names (rules 7 and 19): a ready
 * Public fact of the register table, of the layer's own closed metric list.
 * Without a registry, or without a named fact, nothing is bound.
 */
function companyFactProblem(
  recordId: string | undefined,
  registry: FactRegistry | undefined,
): BindingCode | Extract<Resolution, { status: 'ready' }> {
  const entry = layerEntry('company_points');
  if (!registry || !entry || !recordId) return 'incomplete_source_chain';
  const resolved = registry.resolve(recordId);
  if (resolved.status !== 'ready') return 'incomplete_source_chain';
  if (resolved.binding.fact.provenance !== 'public') return 'not_public';
  if (
    resolved.table?.tableName !== entry.table ||
    !entry.metricKeys.includes(resolved.binding.metricKey)
  )
    return 'measure_on_named_feature';
  return resolved;
}

/**
 * No number without its fact (rules 7 and 23): a card reference names a
 * ready Public fact of the register table, of the layer's own closed metric
 * list, with the reference's own kind and value.
 */
function companyReferenceProblem(
  segments: readonly TextSegment[],
  registry: FactRegistry | undefined,
): BindingCode | null {
  for (const segment of segments) {
    if (segment.kind !== 'reference') continue;
    const resolved = companyFactProblem(segment.recordId, registry);
    if (typeof resolved === 'string') return resolved;
    if (
      resolved.binding.fact.unit !== segment.referenceKind ||
      resolved.binding.fact.value !== segment.value
    )
      return 'measure_on_named_feature';
  }
  return null;
}

/**
 * A register company's point or card holds its published fields only: a
 * wage, a wage bill or any other labour or residence detail, a word or a
 * label, and any employee count other than the public_only absence refuse
 * the payload (FE-103, FE-115, DAT-140). The card is closed at every nesting
 * level: a card, a field, a segment and the count each hold exactly their
 * keys, and a point's fact and a reference segment each bind a fact of the
 * registry.
 */
export function companyPointsProblem(
  payload: LayerPayload,
  registry?: FactRegistry,
): RefusalCode | null {
  for (const layer of payload.layers) {
    if (layer.key !== 'company_points') continue;
    for (const feature of layer.features) {
      if (Object.keys(feature).some((key) => !COMPANY_FEATURE_KEYS.has(key)))
        return 'wage_or_synthetic_id';
      if (!companyPointValuesClosed(feature)) return 'wage_or_synthetic_id';
      if (feature.provenance !== 'public' || feature.subject !== 'business')
        return 'not_public';
      // No point without its fact: bound as a card reference is bound.
      const bound = companyFactProblem(feature.fact_id, registry);
      if (typeof bound === 'string') return bound;
    }
  }
  const cards: unknown = payload.company_cards ?? [];
  if (!Array.isArray(cards)) return 'wage_or_synthetic_id';
  for (const card of cards as readonly unknown[]) {
    if (
      !isRecord(card) ||
      !hasExactKeys(card, COMPANY_CARD_KEYS) ||
      typeof card.feature_id !== 'string' ||
      typeof card.row_id !== 'string' ||
      !Array.isArray(card.fields)
    )
      return 'wage_or_synthetic_id';
    const count = card.employee_count;
    if (
      !isRecord(count) ||
      !hasExactKeys(count, COMPANY_COUNT_KEYS) ||
      count.state !== 'absent' ||
      count.reason_key !== COMPANY_ABSENT_REASON
    )
      return 'wage_or_synthetic_id';
    for (const field of card.fields as readonly unknown[]) {
      if (
        !isRecord(field) ||
        !hasExactKeys(field, COMPANY_FIELD_KEYS) ||
        !isClosedMember(COMPANY_CARD_FIELDS, field.key) ||
        !Array.isArray(field.segments) ||
        field.segments.length === 0 ||
        !field.segments.every(isSegment)
      )
        return 'wage_or_synthetic_id';
      const segments: readonly TextSegment[] = field.segments;
      if (fieldHoldsSynthetic({ key: field.key, segments }))
        return 'wage_or_synthetic_id';
      if (digitInPlain(segments)) return 'numeral_in_plain_segment';
      const unbound = companyReferenceProblem(segments, registry);
      if (unbound) return unbound;
    }
  }
  return null;
}

export function fcCompanyProblem(payload: LayerPayload): RefusalCode | null {
  for (const row of payload.fc_firms?.companies ?? []) {
    if (row.wage_key || row.employee_count || row.attached)
      return 'wage_or_synthetic_id';
    if (syntheticText(row.identifier)) return 'wage_or_synthetic_id';
    for (const field of row.fields) {
      if (!CARD_FIELDS.has(field.key) || fieldHoldsSynthetic(field)) {
        return 'wage_or_synthetic_id';
      }
      const digit =
        (field.text !== undefined && plainHoldsDigit(field.text)) ||
        digitInPlain(field.segments);
      if (digit) return 'numeral_in_plain_segment';
    }
  }
  return null;
}

function refuseSection(code: RefusalCode): FcSectionVerdict {
  return { ok: false, code };
}

export function fcSectionProblem(
  section: unknown,
  registry: FactRegistry | undefined,
  countFacts: readonly { fact_id: string; year: string }[] | undefined,
): FcSectionVerdict | null {
  if (section == null) return null;
  if (!isRecord(section)) return refuseSection('legend_count_unbound');
  if (
    !hasOnlyKeys(section, [
      'direction',
      'companies',
      'coverage_note_keys',
      'breaks',
      'no_data',
    ])
  )
    return refuseSection('legend_count_unbound');
  if (section.no_data !== undefined && typeof section.no_data !== 'boolean')
    return refuseSection('legend_count_unbound');
  if (!isClosedMember(FC_DIRECTION_KEYS, section.direction)) {
    return refuseSection('legend_count_unbound');
  }
  const direction: FcDirection = section.direction;
  if (!Array.isArray(section.coverage_note_keys)) {
    return refuseSection('legend_count_unbound');
  }
  const notes: ScreenNoteKey[] = [];
  for (const note of section.coverage_note_keys) {
    if (!isClosedMember(SCREEN_NOTE_KEYS, note)) {
      return refuseSection('legend_count_unbound');
    }
    notes.push(note);
  }
  if (!Array.isArray(section.breaks)) {
    return refuseSection('night_class_missing');
  }
  const entry = layerEntry('fc_firms_per_tower');
  const tables = (entry?.table ?? '')
    .split(',')
    .map((name) => name.trim())
    .filter((name) => name !== '');
  const breaks: { class_id: FcLegendClass; fact_id: string }[] = [];
  for (const band of section.breaks) {
    if (
      !isRecord(band) ||
      !isClosedMember(FC_LEGEND_CLASS_KEYS, band.class_id)
    ) {
      return refuseSection('night_class_missing');
    }
    if (!rampToken(band.class_id)) return refuseSection('night_class_missing');
    if (typeof band.fact_id !== 'string') {
      return refuseSection('legend_count_unbound');
    }
    if (!hasOnlyKeys(band, ['class_id', 'fact_id']))
      return refuseSection('legend_count_unbound');
    if (!registry) return refuseSection('legend_count_unbound');
    const resolved = registry.resolve(band.fact_id);
    if (resolved.status !== 'ready')
      return refuseSection('legend_count_unbound');
    const fact = resolved.binding.fact;
    if (resolved.binding.metricKey !== 'firms_per_tower') {
      return refuseSection('legend_count_unbound');
    }
    if (fact.provenance !== 'public')
      return refuseSection('legend_count_unbound');
    if (fact.unit !== 'count') return refuseSection('legend_count_unbound');
    if (!tables.includes(resolved.table?.tableName ?? '')) {
      return refuseSection('legend_count_unbound');
    }
    const year = (countFacts ?? []).find((row) => row.fact_id === band.fact_id);
    if (!year) return refuseSection('legend_count_unbound');
    breaks.push({ class_id: band.class_id, fact_id: band.fact_id });
  }
  if (!isCompanyList(section.companies)) {
    return refuseSection('legend_count_unbound');
  }
  const companies = structuredClone(section.companies);
  const closed: FcFirmsSection = {
    direction,
    companies,
    coverage_note_keys: notes,
    breaks,
  };
  if (typeof section.no_data === 'boolean') closed.no_data = section.no_data;
  return { ok: true, section: closed };
}

export function plainHoldsDigit(text: string): boolean {
  return PLAIN_DIGIT.test(text);
}

export function digitInPlain(
  segments: readonly TextSegment[] | undefined,
): boolean {
  if (!segments) return false;
  return segments.some(
    (segment) => segment.kind === 'plain' && PLAIN_DIGIT.test(segment.text),
  );
}

export function segmentsBlank(
  segments: readonly TextSegment[] | undefined,
): boolean {
  if (!segments || segments.length === 0) return true;
  return segments.every((segment) =>
    segment.kind === 'plain'
      ? segment.text.trim() === ''
      : segment.value.trim() === '',
  );
}

export function sameSegmentList(
  left: readonly TextSegment[],
  right: readonly TextSegment[],
): boolean {
  if (left.length !== right.length) return false;
  return left.every((item, index) => sameSegment(item, right[index]));
}

function sameSegment(
  left: TextSegment,
  right: TextSegment | undefined,
): boolean {
  if (!right || left.kind !== right.kind) return false;
  if (left.kind === 'plain' && right.kind === 'plain') {
    return left.text === right.text;
  }
  if (left.kind === 'reference' && right.kind === 'reference') {
    return (
      left.referenceKind === right.referenceKind &&
      left.value === right.value &&
      left.recordId === right.recordId
    );
  }
  return false;
}

export function countYearMissing(payload: LayerPayload): boolean {
  const facts = payload.count_facts ?? [];
  if (facts.some((row) => row.year.trim() === '')) return true;
  for (const id of payload.count_fact_ids ?? []) {
    const row = facts.find((item) => item.fact_id === id);
    if (!row || row.year.trim() === '') return true;
  }
  return false;
}

export function creditsReady(credits: InvestmentCredits | undefined): boolean {
  if (!credits) return false;
  return (
    !segmentsBlank(credits.publisher) &&
    !segmentsBlank(credits.gatherer) &&
    credits.read_on.trim() !== '' &&
    credits.dashboard_url.trim() !== ''
  );
}

export type BindingCode =
  | 'incomplete_source_chain'
  | 'measure_on_named_feature'
  | 'not_public'
  | 'accident_geography_allocation'
  | 'accident_zone_mismatch';

export function fdiReferenceProblem(
  segments: readonly TextSegment[],
  registry: FactRegistry,
): BindingCode | null {
  for (const segment of segments) {
    if (segment.kind !== 'reference') continue;
    const resolved = registry.resolve(segment.recordId);
    if (resolved.status !== 'ready') return 'incomplete_source_chain';
    if (resolved.binding.fact.provenance !== 'public') return 'not_public';
    if (
      resolved.table?.tableName !== 'fdi_projects' ||
      resolved.binding.metricKey !== 'fdi_field' ||
      resolved.binding.fact.unit !== segment.referenceKind ||
      resolved.binding.fact.value !== segment.value
    )
      return 'measure_on_named_feature';
  }
  return null;
}

/**
 * The refusal wording of a layer this version does not draw. A layer whose
 * registry class is not Public says only that it has no map in this
 * version: the audience is never told a data origin (decision 0035 item 1).
 * The registry class stays a backend field and still decides the refusal.
 */
export function unimplementedReason(
  key: string,
): 'layers.refused.writer' | 'layers.refused.pending' {
  const entry = layerEntry(key);
  if (!entry || !entry.className.includes('Public'))
    return 'layers.refused.pending';
  if (entry.key === 'firm_density') {
    return 'layers.refused.pending';
  }
  return 'layers.refused.writer';
}

export function geometryDeckType(kind: LayerFeature['geometry_kind']): string {
  if (kind === 'hex') return 'H3HexagonLayer';
  if (kind === 'line') return 'PathLayer';
  if (kind === 'point') return 'ScatterplotLayer';
  return 'GeoJsonLayer';
}

/** Acceptance only: a published point must equal its two verified source facts. */
export function publishedFdiPoint(
  feature: LayerFeature,
  registry: FactRegistry | undefined,
): boolean {
  const position =
    feature.position ??
    (feature.geometry?.type === 'Point'
      ? feature.geometry.coordinates
      : undefined);
  if (!registry || !position || !feature.lon_fact_id || !feature.lat_fact_id)
    return false;
  const lon = registry.resolve(feature.lon_fact_id);
  const lat = registry.resolve(feature.lat_fact_id);
  if (lon.status !== 'ready' || lat.status !== 'ready') return false;
  return (
    [lon, lat].every(
      (resolved) =>
        resolved.binding.metricKey === 'fdi_location' &&
        resolved.binding.fact.provenance === 'public' &&
        resolved.table?.tableName === 'fdi_projects' &&
        resolved.binding.fact.unit === 'decimal_degree',
    ) &&
    lon.binding.fact.value === position[0] &&
    lat.binding.fact.value === position[1]
  );
}

export function bindingProblem(
  entry: LayerEntry,
  feature: LayerFeature,
  registry: FactRegistry,
): BindingCode | null {
  for (const segments of Object.values(feature.field_segments ?? {})) {
    const problem = fdiReferenceProblem(segments, registry);
    if (problem) return problem;
  }
  const slots: { id: string; metric: string }[] = [];
  if (feature.fact_id)
    slots.push({ id: feature.fact_id, metric: feature.metric_key });
  if (feature.capex_fact_id)
    slots.push({ id: feature.capex_fact_id, metric: 'fdi_capex' });
  if (feature.jobs_fact_id)
    slots.push({ id: feature.jobs_fact_id, metric: 'fdi_jobs' });
  if (feature.lon_fact_id)
    slots.push({ id: feature.lon_fact_id, metric: 'fdi_location' });
  if (feature.lat_fact_id)
    slots.push({ id: feature.lat_fact_id, metric: 'fdi_location' });
  const tables = entry.table.split(',').map((name) => name.trim());
  for (const slot of slots) {
    const resolved = registry.resolve(slot.id);
    if (resolved.status !== 'ready') return 'incomplete_source_chain';
    if (resolved.binding.metricKey !== slot.metric)
      return 'measure_on_named_feature';
    if (resolved.binding.fact.provenance !== feature.provenance)
      return 'not_public';
    if (!tables.includes(resolved.table?.tableName ?? ''))
      return 'measure_on_named_feature';
    if (entry.key === 'fc_firms_per_tower') {
      const geography = resolved.binding.fact.geography;
      const point = feature.geometry_kind === 'point';
      const prefix = point ? 'place:' : 'district:';
      if (
        geography.kind !== 'public' ||
        feature.subject !== (point ? 'place' : 'statistic') ||
        (!point && feature.geometry_kind !== 'fill') ||
        !feature.geography_code?.startsWith(prefix) ||
        geography.public_code !== feature.geography_code
      )
        return 'measure_on_named_feature';
    }
    if (entry.key === 'accidents') {
      // The count stays on the zone it was published for; no reallocation.
      const geography = resolved.binding.fact.geography;
      if (
        geography.kind !== 'public' ||
        geography.public_code !== feature.geography_code
      )
        return 'accident_geography_allocation';
      if (accidentZone(feature, resolved.binding.fact, registry) === null)
        return 'accident_zone_mismatch';
    }
  }
  return null;
}

/**
 * The source zone an accident outline shows (RV1 finding 2): the value of its
 * `accident_source_zone` fact, of the count's own release row (same table,
 * geography and period) and equal to the feature's reference; else null.
 */
export function accidentZone(
  feature: LayerFeature,
  count: Fact,
  registry: FactRegistry,
): string | null {
  const resolved = registry.resolve(feature.source_zone_fact_id ?? '');
  if (resolved.status !== 'ready') return null;
  const zone = resolved.binding.fact;
  // The count's own lineage row fixes the zone's table and release.
  return resolved.binding.metricKey === 'accident_source_zone' &&
    zone.provenance === 'public' &&
    zone.unit === 'published_text' &&
    zone.lineage_ref === count.lineage_ref &&
    zone.period === count.period &&
    zone.geography.kind === 'public' &&
    zone.geography.public_code === feature.geography_code &&
    typeof zone.value === 'string' &&
    zone.value === feature.source_zone
    ? zone.value
    : null;
}

export function chainProblem(
  factId: string,
  registry: FactRegistry,
): 'incomplete_source_chain' | null {
  const resolved = registry.resolve(factId);
  if (resolved.status !== 'ready') return 'incomplete_source_chain';
  return null;
}
