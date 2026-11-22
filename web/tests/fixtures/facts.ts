/**
 * Hand-made records for tests. Identifiers are visibly invented.
 * Nothing here is imported by production code.
 */
import {
  createRegistry,
  type FactBinding,
  type FactRegistry,
  type InputClass,
  type LineageRow,
  type Provenance,
  type RegistryInput,
  type ReleaseRecord,
  type SourceKind,
  type SourceRow,
} from '../../src/facts/registry';
import type {
  Fact,
  Reliability,
  EvidenceStatus,
  TableLineage,
} from '../../src/facts/types';

const RELEASE =
  'a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8a1b2c3d4e5f6a7b8';

const HEADS = [
  'ab',
  'cd',
  'ef',
  'ba',
  'dc',
  'fe',
  'ac',
  'ce',
  'ea',
  'bd',
  'db',
  'fa',
];

export function factId(index: number): string {
  const head = HEADS[index] ?? 'ab';
  return `f_${head}c3d4e5f6a7b8c3d4e5f6a7b8c3d4e5`;
}

export function hashId(index: number): string {
  const head = HEADS[index] ?? 'ab';
  return `${head}c3d4e5f6a7b8c3d4e5f6a7b8c3d4e5f6a7b8c3d4e5f6a7b8c3d4e5f6`;
}

export const SYNTHETIC_COMPANY = 'SYN-E-7F3K2Q';

export function makeFact(
  overrides: Partial<Fact> & { fact_id?: string } = {},
): Fact {
  const id = overrides.fact_id ?? factId(0);
  return {
    fact_id: id,
    value: 48,
    unit: 'count',
    period: '2024-03',
    geography: { kind: 'national' },
    provenance: 'public',
    input_classes: ['public'],
    evidence_status: 'observed',
    reliability: 'standard',
    coverage_keys: ['rows_kept'],
    caveat_keys: ['limits_named'],
    label_en: 'People in the drawn area',
    label_ar: 'الأشخاص في المنطقة المرسومة',
    lineage_ref: 'lin_sample_chain',
    release_id: RELEASE,
    ...overrides,
  };
}

export function makeSource(overrides: Partial<SourceRow> = {}): SourceRow {
  return {
    sourceId: 'src_alpha',
    kind: 'public_dataset',
    inputClass: 'public',
    publisher: 'Sample Publisher',
    datasetOrPage: 'Sample page of counts',
    licenceOrTerms: 'Terms recorded for this sample',
    retrievalDate: '2024-03-14',
    sha256: hashId(0),
    ...overrides,
  };
}

export function makeLineage(
  overrides: Partial<TableLineage> = {},
): TableLineage {
  return {
    link: 'table',
    lineageId: 'lin_sample_chain',
    releaseId: RELEASE,
    tableName: 'sample_counts',
    method: 'sample_method',
    methodVersion: 'v1',
    sourceIds: ['src_alpha'],
    inputClasses: ['public'],
    ...overrides,
  };
}

export function makeBinding(overrides: Partial<FactBinding> = {}): FactBinding {
  return {
    fact: makeFact(),
    metricKey: 'people',
    presentation: 'ordinary',
    ...overrides,
  };
}

export function completeInput(): RegistryInput {
  return {
    facts: [makeBinding()],
    releases: [{ releaseId: RELEASE }],
    artefacts: [],
    tables: [{ releaseId: RELEASE, tableName: 'sample_counts' }],
    lineages: [makeLineage()],
    sources: [makeSource()],
  };
}

export function registryFrom(input: RegistryInput): FactRegistry {
  return createRegistry(input);
}

export function completeRegistry(): FactRegistry {
  return registryFrom(completeInput());
}

export interface ChainCut {
  name: string;
  input: RegistryInput;
}

function dropFact(): RegistryInput {
  const input = completeInput();
  return { ...input, facts: [] };
}

function dropRelease(): RegistryInput {
  const input = completeInput();
  return { ...input, releases: [] };
}

function dropTable(): RegistryInput {
  const input = completeInput();
  return { ...input, tables: [] };
}

function dropLineage(): RegistryInput {
  const input = completeInput();
  return { ...input, lineages: [] };
}

function blank(field: 'method' | 'methodVersion'): RegistryInput {
  const input = completeInput();
  const lineage = makeLineage({ [field]: '' });
  return { ...input, lineages: [lineage] };
}

function dropSource(which: 'first' | 'second'): RegistryInput {
  const input = twoSourceInput();
  const id = which === 'first' ? 'src_alpha' : 'src_beta';
  return {
    ...input,
    sources: input.sources.filter((row) => row.sourceId !== id),
  };
}

export function twoSourceInput(): RegistryInput {
  const input = completeInput();
  const second = makeSource({
    sourceId: 'src_beta',
    kind: 'public_document',
    publisher: 'Second Publisher',
    datasetOrPage: 'Second sample page',
    sha256: hashId(1),
  });
  return {
    ...input,
    lineages: [
      makeLineage({
        sourceIds: ['src_alpha', 'src_beta'],
        inputClasses: ['public'],
      }),
    ],
    sources: [makeSource(), second],
  };
}

function blankSource(field: keyof SourceRow): RegistryInput {
  const input = completeInput();
  return {
    ...input,
    sources: [makeSource({ [field]: '' } as Partial<SourceRow>)],
  };
}

export function chainCuts(): ChainCut[] {
  const mismatched = completeInput();
  const other =
    'b1c2d3e4f5a6b7c8b1c2d3e4f5a6b7c8b1c2d3e4f5a6b7c8b1c2d3e4f5a6b7c8';
  return [
    { name: 'fact', input: dropFact() },
    { name: 'release', input: dropRelease() },
    { name: 'table', input: dropTable() },
    { name: 'lineage', input: dropLineage() },
    { name: 'method', input: blank('method') },
    { name: 'method_version', input: blank('methodVersion') },
    { name: 'source-first', input: dropSource('first') },
    { name: 'source-second', input: dropSource('second') },
    { name: 'publisher', input: blankSource('publisher') },
    { name: 'dataset_or_page', input: blankSource('datasetOrPage') },
    { name: 'licence_or_terms', input: blankSource('licenceOrTerms') },
    { name: 'retrieval_date', input: blankSource('retrievalDate') },
    { name: 'hash', input: blankSource('sha256') },
    {
      name: 'release_identity',
      input: {
        ...mismatched,
        releases: [{ releaseId: other } satisfies ReleaseRecord],
      },
    },
    {
      name: 'input_class_source',
      input: {
        ...completeInput(),
        lineages: [makeLineage({ inputClasses: ['public', 'synthetic'] })],
      },
    },
    {
      name: 'source_kind',
      input: {
        ...completeInput(),
        sources: [
          makeSource({
            kind: 'synthetic_feed' satisfies SourceKind,
            inputClass: 'public',
          }),
        ],
      },
    },
  ];
}

export function calendarFact(
  unit: 'calendar_date' | 'calendar_month' | 'calendar_year' | 'published_text',
  value: string,
): FactRegistry {
  const fact = makeFact({
    unit,
    value,
    provenance: 'public' satisfies Provenance,
    input_classes: ['public'] satisfies InputClass[],
    evidence_status: 'observed' satisfies EvidenceStatus,
    reliability: 'not_applicable' satisfies Reliability,
  });
  const input = completeInput();
  return registryFrom({ ...input, facts: [makeBinding({ fact })] });
}

export { RELEASE };

/** The unchanged server table wire shape, before the client adapter. */
export function tableWire(row: LineageRow) {
  const { link, ...wire } = row;
  void link;
  return wire;
}
