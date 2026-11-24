/** Document 03 mounted Public projections. No ID decoding or provenance defaults. */
import { createRegistry } from '../facts/registry';
import type {
  Fact,
  FactBinding,
  LineageRow,
  RegistryInput,
  ReleaseTable,
  SourceRow,
} from '../facts/types';

export function closed(
  value: unknown,
  keys: readonly string[],
): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value))
    throw new Error('chain_refused');
  const row = value as Record<string, unknown>;
  if (
    Object.keys(row).length !== keys.length ||
    keys.some((key) => !Object.hasOwn(row, key))
  )
    throw new Error('chain_refused');
  return row;
}
export function text(value: unknown): string {
  if (typeof value !== 'string' || value.trim() === '')
    throw new Error('chain_refused');
  return value;
}
function list(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new Error('chain_refused');
  return value;
}
function appendConsistent<T>(
  rows: T[],
  row: T,
  identity: (row: T) => string,
): void {
  const existing = rows.find((item) => identity(item) === identity(row));
  if (existing && JSON.stringify(existing) !== JSON.stringify(row))
    throw new Error('chain_refused');
  if (!existing) rows.push(row);
}

/** The fifteen fields of document 03's fact object, closed. */
export const FACT_KEYS = [
  'fact_id',
  'value',
  'unit',
  'period',
  'geography',
  'provenance',
  'input_classes',
  'evidence_status',
  'reliability',
  'coverage_keys',
  'caveat_keys',
  'label_en',
  'label_ar',
  'lineage_ref',
  'release_id',
] as const;

/** A Public lineage source row, closed; any other kind or class is refused. */
export function sourceRow(value: unknown): SourceRow {
  const source = closed(value, [
    'sourceId',
    'kind',
    'inputClass',
    'publisher',
    'datasetOrPage',
    'licenceOrTerms',
    'retrievalDate',
    'sha256',
  ]);
  if (
    !['public_dataset', 'public_document', 'reviewed_config'].includes(
      text(source.kind),
    ) ||
    source.inputClass !== 'public'
  )
    throw new Error('chain_refused');
  return {
    sourceId: text(source.sourceId),
    kind: source.kind as SourceRow['kind'],
    inputClass: 'public',
    publisher: text(source.publisher),
    datasetOrPage: text(source.datasetOrPage),
    licenceOrTerms: text(source.licenceOrTerms),
    retrievalDate: text(source.retrievalDate),
    sha256: text(source.sha256),
  };
}

async function get(path: string): Promise<unknown> {
  const response = await fetch(path, {
    method: 'GET',
    credentials: 'same-origin',
    redirect: 'error',
  });
  if (!response.ok) throw new Error('chain_refused');
  return response.json();
}

async function readRelease() {
  const release = closed(await get('/api/release'), [
    'release_id',
    'release_kind',
    'rules_version_id',
    'tables',
    'hour_keys',
    'day_keys',
    'month_keys',
    'basemap_url',
  ]);
  const releaseId = text(release.release_id);
  if (release.release_kind !== 'public_only') throw new Error('chain_refused');
  text(release.rules_version_id);
  for (const key of ['hour_keys', 'day_keys', 'month_keys'])
    list(release[key]).forEach(text);
  const tables: ReleaseTable[] = list(release.tables).map((value) => {
    const row = closed(value, ['releaseId', 'tableName']);
    if (row.releaseId !== releaseId) throw new Error('chain_refused');
    return { releaseId, tableName: text(row.tableName) };
  });
  if (
    release.basemap_url !== null &&
    release.basemap_url !== '/tiles/basemap.pmtiles'
  )
    throw new Error('chain_refused');
  return { releaseId, tables, basemapUrl: release.basemap_url };
}

export async function loadBasemapUrl(): Promise<string | null> {
  return (await readRelease()).basemapUrl;
}

export async function loadRegistryInput(
  facts: readonly Fact[],
): Promise<RegistryInput> {
  const { releaseId, tables } = await readRelease();
  const bindings: FactBinding[] = [];
  const lineages: LineageRow[] = [];
  const sources: SourceRow[] = [];
  for (const fact of facts) {
    closed(fact, FACT_KEYS);
    if (
      !/^f_[0-9a-f]{32}$/.test(fact.fact_id) ||
      fact.release_id !== releaseId ||
      fact.provenance !== 'public' ||
      fact.input_classes.length !== 1 ||
      fact.input_classes[0] !== 'public'
    )
      throw new Error('chain_refused');
    const chain = closed(await get('/api/facts/' + fact.fact_id + '/lineage'), [
      'fact_id',
      'release_id',
      'lineage',
      'sources',
      'binding',
    ]);
    if (chain.fact_id !== fact.fact_id || chain.release_id !== releaseId)
      throw new Error('chain_refused');
    const citation =
      typeof chain.lineage === 'object' &&
      chain.lineage !== null &&
      Object.hasOwn(chain.lineage, 'rowRetrievalDate');
    const row = closed(chain.lineage, [
      'lineageId',
      'releaseId',
      'tableName',
      'method',
      'methodVersion',
      'sourceIds',
      'inputClasses',
      ...(citation ? ['rowRetrievalDate', 'providerUpdatedOn'] : []),
    ]);
    if (
      row.lineageId !== fact.lineage_ref ||
      row.releaseId !== releaseId ||
      JSON.stringify(row.inputClasses) !== JSON.stringify(['public'])
    )
      throw new Error('chain_refused');
    const lineage: LineageRow = {
      factId: fact.fact_id,
      lineageId: text(row.lineageId),
      releaseId,
      tableName: text(row.tableName),
      method: text(row.method),
      methodVersion: text(row.methodVersion),
      sourceIds: list(row.sourceIds).map(text),
      inputClasses: ['public'],
      ...(citation
        ? {
            rowRetrievalDate: text(row.rowRetrievalDate),
            providerUpdatedOn:
              row.providerUpdatedOn === null
                ? null
                : text(row.providerUpdatedOn),
          }
        : {}),
    };
    if (!tables.some((table) => table.tableName === lineage.tableName))
      throw new Error('chain_refused');
    const base = (row: LineageRow) => ({
      lineageId: row.lineageId,
      releaseId: row.releaseId,
      tableName: row.tableName,
      method: row.method,
      methodVersion: row.methodVersion,
      sourceIds: row.sourceIds,
      inputClasses: row.inputClasses,
    });
    if (
      lineages.some(
        (row) =>
          row.lineageId === lineage.lineageId &&
          JSON.stringify(base(row)) !== JSON.stringify(base(lineage)),
      )
    )
      throw new Error('chain_refused');
    appendConsistent(
      lineages,
      lineage,
      (row) => row.lineageId + ':' + row.factId,
    );
    for (const value of list(chain.sources)) {
      const held = sourceRow(value);
      appendConsistent(sources, held, (row) => row.sourceId);
    }
    const companion = closed(chain.binding, [
      'metricKey',
      'presentation',
      'qualifiers',
    ]);
    if (companion.presentation !== 'ordinary') throw new Error('chain_refused');
    const qualifiers = companion.qualifiers;
    if (
      qualifiers === null ||
      typeof qualifiers !== 'object' ||
      Array.isArray(qualifiers)
    )
      throw new Error('chain_refused');
    if (
      Object.entries(qualifiers).some(
        ([key, value]) =>
          !['day_of_week', 'hour', 'age_band', 'sex'].includes(key) ||
          typeof value !== 'string',
      )
    )
      throw new Error('chain_refused');
    bindings.push({
      fact,
      metricKey: text(companion.metricKey),
      presentation: 'ordinary',
      qualifiers: qualifiers as FactBinding['qualifiers'],
    });
  }
  const input: RegistryInput = {
    facts: bindings,
    releases: [{ releaseId }],
    tables,
    lineages,
    sources,
  };
  const registry = createRegistry(input);
  if (facts.some((fact) => registry.resolve(fact.fact_id).status !== 'ready'))
    throw new Error('chain_refused');
  return input;
}
