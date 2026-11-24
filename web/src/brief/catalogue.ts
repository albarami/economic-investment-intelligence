/**
 * Closed catalogue binding. Unknown keys withdraw the answer.
 * The file is produced by scripts/export_web_catalogue.py.
 */
import generated from './catalogue.generated.json' with { type: 'json' };
import { contextFamilies } from '../cards/public-context-contract';

import type { FactRegistry } from '../facts/registry';
import type { Provenance, Resolution } from '../facts/types';
import {
  factKind,
  subjectAllowsFact,
  subjectFactFromMetric,
  type SubjectFact,
} from './subject';

export type { FactKind, SubjectFact } from './subject';

const TOP_KEYS = [
  'claims',
  'components',
  'directives',
  'fragments',
  'questions',
  'version',
] as const;

export type SubjectKind =
  'area' | 'place_public' | 'fdi_project' | 'register_company';

export interface AnswerSlot {
  name?: string;
  factId: string;
  provenance: Provenance;
  metric: string;
}

export type DirectiveValue = string | boolean | readonly string[];

export interface AnswerDirective {
  name: string;
  fields: Record<string, DirectiveValue>;
}

export interface AnswerDraft {
  catalogueVersion: string;
  accountingPassed: boolean;
  subject: SubjectKind;
  componentKey: string;
  claimKey?: string;
  inList?: boolean;
  props: readonly string[];
  directive: AnswerDirective | null;
  slots: readonly AnswerSlot[];
}

interface FieldSpec {
  name: string;
  kind: string;
  values: string[];
  const: string | boolean | null;
  minimum: number | null;
  maximum: number | null;
}

const FIELD_KINDS = new Set([
  'target',
  'enumeration',
  'identifier',
  'boolean',
  'fact_id',
  'identifier_list',
  'area_ids',
]);

interface DirectiveSpec {
  name: string;
  alternatives: { fields: FieldSpec[] }[];
}

interface FragmentSpec {
  key: string;
  kind: string;
  fields: [string, string][];
}

interface ComponentSpec {
  key: string;
  max_count: number;
  props: string[];
}

interface CatalogueFile {
  version: string;
  claims: unknown[];
  components: ComponentSpec[];
  directives: DirectiveSpec[];
  fragments: FragmentSpec[];
  questions: { key: string; fields: [string, string][] }[];
}

function asCatalogue(value: unknown): CatalogueFile {
  if (!value || typeof value !== 'object') throw new Error('catalogue shape');
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record);
  if (
    keys.length !== TOP_KEYS.length ||
    TOP_KEYS.some((key) => !(key in record))
  )
    throw new Error('catalogue keys');
  if (
    typeof record.version !== 'string' ||
    !/^[0-9a-f]{64}$/.test(record.version)
  )
    throw new Error('catalogue version');
  return record as unknown as CatalogueFile;
}

export const catalogue: CatalogueFile = asCatalogue(generated);

export function fragmentField(key: string, field: string): string | null {
  const fragment = catalogue.fragments.find((item) => item.key === key);
  if (!fragment) return null;
  const pair = fragment.fields.find((row) => row[0] === field);
  return pair ? pair[1] : null;
}

function listOk(value: DirectiveValue, field: FieldSpec): boolean {
  if (!Array.isArray(value)) return false;
  if (value.some((item) => typeof item !== 'string')) return false;
  if (typeof field.minimum === 'number' && value.length < field.minimum)
    return false;
  if (typeof field.maximum === 'number' && value.length > field.maximum)
    return false;
  return true;
}

export function fieldValueAccepted(
  field: FieldSpec,
  value: DirectiveValue | undefined,
): boolean {
  if (value === undefined || !FIELD_KINDS.has(field.kind)) return false;
  if (field.kind === 'boolean') {
    if (typeof value !== 'boolean') return false;
    return field.const === null || value === field.const;
  }
  if (field.kind === 'identifier_list' || field.kind === 'area_ids')
    return listOk(value, field);
  if (typeof value !== 'string' || value.length === 0) return false;
  if (field.kind === 'enumeration') return field.values.includes(value);
  if (field.values.length > 0 && !field.values.includes(value)) return false;
  return typeof field.const !== 'string' || value === field.const;
}

export function directiveAccepted(
  name: string,
  fields: Record<string, DirectiveValue>,
): boolean {
  const spec = catalogue.directives.find((item) => item.name === name);
  if (!spec) return false;
  const given = Object.keys(fields);
  return spec.alternatives.some((alternative) => {
    if (alternative.fields.length !== given.length) return false;
    return alternative.fields.every((field) => {
      if (!given.includes(field.name)) return false;
      return fieldValueAccepted(field, fields[field.name]);
    });
  });
}

export function subjectAllows(
  subject: string,
  factOrProvenance: SubjectFact | Provenance | string,
  metric?: string,
): boolean {
  const fact =
    typeof factOrProvenance === 'string'
      ? subjectFactFromMetric(factOrProvenance, metric ?? '')
      : factOrProvenance;
  return subjectAllowsFact(subject, fact);
}

interface CarriedSlot {
  name: string;
  metric_key: string;
  unit: string;
  geography_role: string;
  period_rule: string;
  allowed_provenance: readonly string[];
  breakdown: string;
}

type Ready = Extract<Resolution, { status: 'ready' }>;

function textList(value: unknown): readonly string[] | null {
  if (!Array.isArray(value)) return null;
  if (value.some((item) => typeof item !== 'string')) return null;
  return value as string[];
}

function carriedSlot(value: unknown): CarriedSlot | null {
  if (!value || typeof value !== 'object') return null;
  const row = value as Record<string, unknown>;
  const allowed = textList(row.allowed_provenance);
  if (
    typeof row.name !== 'string' ||
    typeof row.metric_key !== 'string' ||
    typeof row.unit !== 'string' ||
    typeof row.geography_role !== 'string' ||
    typeof row.period_rule !== 'string' ||
    typeof row.breakdown !== 'string' ||
    allowed === null
  )
    return null;
  return {
    name: row.name,
    metric_key: row.metric_key,
    unit: row.unit,
    geography_role: row.geography_role,
    period_rule: row.period_rule,
    allowed_provenance: allowed,
    breakdown: row.breakdown,
  };
}

function carriedSlots(value: unknown): readonly CarriedSlot[] | null {
  if (!value || typeof value !== 'object' || !('slots' in value)) return null;
  const slots = (value as { slots?: unknown }).slots;
  if (!Array.isArray(slots)) return null;
  const parsed: CarriedSlot[] = [];
  for (const item of slots) {
    const slot = carriedSlot(item);
    if (!slot) return null;
    parsed.push(slot);
  }
  return parsed;
}

function claimSlots(claimKey: string): readonly CarriedSlot[] | null {
  const claim = catalogue.claims.find(
    (item) =>
      !!item &&
      typeof item === 'object' &&
      (item as { key?: unknown }).key === claimKey,
  );
  if (!claim) return null;
  return carriedSlots(claim);
}

function componentSlots(
  component: ComponentSpec,
): readonly CarriedSlot[] | null | undefined {
  if (!Object.hasOwn(component, 'slots')) return undefined;
  return carriedSlots(component);
}

const RANK_STABILITY_METRIC = 'rank_stability';

function stabilityReady(registry: FactRegistry, parent: Ready): boolean {
  const id = parent.binding.stabilityId;
  if (!id || id === parent.binding.fact.fact_id) return false;
  const companion = registry.resolve(id);
  if (companion.status !== 'ready' || companion.display !== 'value')
    return false;
  if (companion.binding.metricKey !== RANK_STABILITY_METRIC) return false;
  if (companion.binding.fact.unit !== 'rank') return false;
  return true;
}

function subjectOf(
  draft: AnswerDraft,
  registry: FactRegistry,
  resolved: Ready,
  metric: string,
): SubjectFact {
  return {
    provenance: resolved.binding.fact.provenance,
    kind: factKind(metric),
    underlyingClass: null,
    inList: draft.inList === true,
    stabilityPresent: stabilityReady(registry, resolved),
  };
}

function readySlot(
  draft: AnswerDraft,
  registry: FactRegistry,
  slot: AnswerSlot,
): Ready | null {
  const resolved = registry.resolve(slot.factId);
  if (resolved.status !== 'ready') return null;
  if (resolved.binding.fact.provenance !== slot.provenance) return null;
  if (resolved.binding.metricKey !== slot.metric) return null;
  if (
    !subjectAllowsFact(
      draft.subject,
      subjectOf(draft, registry, resolved, slot.metric),
    )
  )
    return null;
  return resolved;
}

function ruleHolds(rule: CarriedSlot, resolved: Ready): boolean {
  const fact = resolved.binding.fact;
  if (resolved.binding.metricKey !== rule.metric_key) return false;
  if (fact.unit !== rule.unit) return false;
  if (fact.geography.kind !== rule.geography_role) return false;
  return rule.allowed_provenance.includes(fact.provenance);
}

function closedSlots(
  draft: AnswerDraft,
  registry: FactRegistry,
  defined: readonly CarriedSlot[],
): boolean {
  if (draft.slots.length !== defined.length) return false;
  const byName = new Map(defined.map((slot) => [slot.name, slot]));
  if (byName.size !== defined.length) return false;
  const seenNames = new Set<string>();
  const seenFacts = new Set<string>();
  for (const slot of draft.slots) {
    if (!slot.name || seenNames.has(slot.name)) return false;
    if (!slot.factId || seenFacts.has(slot.factId)) return false;
    const rule = byName.get(slot.name);
    if (!rule) return false;
    const resolved = readySlot(draft, registry, slot);
    if (!resolved || !ruleHolds(rule, resolved)) return false;
    seenNames.add(slot.name);
    seenFacts.add(slot.factId);
  }
  return defined.every((slot) => seenNames.has(slot.name));
}

export function answerAccepted(
  draft: AnswerDraft,
  registry: FactRegistry | null,
): boolean {
  // The runtime boundary must stay closed even for a structurally typed caller.
  // Extra model properties never become an accepted display candidate.
  const keys = [
    'catalogueVersion',
    'accountingPassed',
    'subject',
    'componentKey',
    'claimKey',
    'inList',
    'props',
    'directive',
    'slots',
  ];
  if (Object.keys(draft).some((key) => !keys.includes(key))) return false;
  if (registry === null) return false;
  // Context displays require their typed card renderer, which always carries
  // their caveat and selection metadata. Generic Brief slots cannot render them.
  if (
    draft.slots.some((slot) =>
      Object.values(contextFamilies).some(
        (spec) => spec.metric === slot.metric,
      ),
    )
  )
    return false;
  if (draft.catalogueVersion !== catalogue.version) return false;
  if (!draft.accountingPassed) return false;
  const component = catalogue.components.find(
    (item) => item.key === draft.componentKey,
  );
  if (!component) return false;
  if (draft.props.some((prop) => !component.props.includes(prop))) return false;
  if (draft.slots.length > component.max_count) return false;
  if (
    draft.directive &&
    !directiveAccepted(draft.directive.name, draft.directive.fields)
  )
    return false;
  const defined = draft.claimKey
    ? claimSlots(draft.claimKey)
    : componentSlots(component);
  if (defined === null) return false;
  if (defined) return closedSlots(draft, registry, defined);
  return draft.slots.every((slot) => readySlot(draft, registry, slot) !== null);
}
