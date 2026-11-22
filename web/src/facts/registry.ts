/**
 * Resolves an injected fact to loading, ready or refused.
 * A value is ready only when every source-chain link is present.
 */
import type {
  FactBinding,
  InputClass,
  LineageRow,
  MissingLink,
  Provenance,
  RegistryInput,
  Resolution,
  ReleaseArtefact,
  ReleaseTable,
  SourceKind,
  SourceRow,
} from './types';

export type {
  FactBinding,
  InputClass,
  LineageRow,
  Provenance,
  RegistryInput,
  ReleaseRecord,
  ReleaseTable,
  SourceKind,
  SourceRow,
} from './types';

export type { Fact, EvidenceStatus, Reliability } from './types';

/** DAT-107. Absent terms are never treated as a licence of their own. */
export const SOURCE_KIND_CLASS: Record<SourceKind, InputClass> = {
  public_dataset: 'public',
  public_document: 'public',
  reviewed_config: 'public',
  synthetic_feed: 'synthetic',
  simulation_output: 'simulated',
};

/** DAT-91 order: Public is more real than Synthetic, then Simulated. */
const CLASS_RANK: Readonly<Record<string, number>> = {
  public: 0,
  synthetic: 1,
  simulated: 2,
};

/**
 * FE-42 (DAT-91): the least-real class of a fact's input classes.
 * A user's typed input takes no part. No release class, or an unknown
 * class, gives null, which never equals a provenance.
 */
export function leastRealClass(
  inputClasses: readonly string[],
): Exclude<Provenance, 'suppressed'> | null {
  let worst: Exclude<Provenance, 'suppressed'> | null = null;
  for (const item of inputClasses) {
    if (item === 'user_input') continue;
    const rank = CLASS_RANK[item];
    if (rank === undefined) return null;
    if (worst === null || rank > (CLASS_RANK[worst] ?? 0))
      worst = item as Exclude<Provenance, 'suppressed'>;
  }
  return worst;
}

export interface FactRegistry {
  resolve(factId: string): Resolution;
  directionReferencers(directionId: string): readonly string[];
}

function blank(value: string | undefined): boolean {
  return value === undefined || value.trim() === '';
}

function refused(missing: MissingLink): Resolution {
  return { status: 'refused', missing };
}

function sourceProblem(row: SourceRow): MissingLink | null {
  const mapped = SOURCE_KIND_CLASS[row.kind];
  if (mapped === undefined || mapped !== row.inputClass) return 'source_kind';
  if (blank(row.publisher)) return 'publisher';
  if (blank(row.datasetOrPage)) return 'dataset_or_page';
  if (blank(row.licenceOrTerms)) return 'licence_or_terms';
  if (blank(row.retrievalDate)) return 'retrieval_date';
  if (blank(row.sha256)) return 'hash';
  return null;
}

function chainOf(
  binding: FactBinding,
  input: RegistryInput,
  stack: ReadonlySet<string>,
): Resolution {
  if (binding.loading) return { status: 'loading' };
  if (binding.noData) return { status: 'no_data' };
  const fact = binding.fact;
  if (blank(fact.fact_id) || blank(fact.lineage_ref) || blank(fact.release_id))
    return refused('fact');
  if (input.releases.length === 0) return refused('release');
  const release = input.releases.find(
    (row) => row.releaseId === fact.release_id && !blank(row.releaseId),
  );
  if (!release) return refused('release_identity');
  const lineage =
    input.lineages.find(
      (row) =>
        row.lineageId === fact.lineage_ref && row.factId === fact.fact_id,
    ) ??
    input.lineages.find(
      (row) => row.lineageId === fact.lineage_ref && row.factId === undefined,
    );
  if (!lineage) return refused('lineage');
  if (blank(lineage.method)) return refused('method');
  if (blank(lineage.methodVersion)) return refused('method_version');
  if (lineage.releaseId !== fact.release_id) return refused('release_identity');
  let table: ReleaseTable | undefined;
  let artefact: ReleaseArtefact | undefined;
  if (lineage.link === 'table') {
    if ('artefactPath' in lineage || 'artefactSha256' in lineage)
      return refused('link_kind');
    if (input.tables.length === 0) return refused('table');
    table = input.tables.find(
      (row) =>
        row.releaseId === fact.release_id &&
        row.tableName === lineage.tableName,
    );
    if (!table) {
      const sameRelease = input.tables.some(
        (row) => row.releaseId === fact.release_id,
      );
      return refused(sameRelease ? 'table' : 'release_identity');
    }
    if (blank(table.tableName)) return refused('table');
  } else if (lineage.link === 'artefact') {
    if ('tableName' in lineage) return refused('link_kind');
    artefact = input.artefacts.find(
      (row) =>
        row.releaseId === fact.release_id && row.path === lineage.artefactPath,
    );
    if (!artefact) {
      const foreign = input.artefacts.some(
        (row) => row.path === lineage.artefactPath,
      );
      return refused(foreign ? 'release_identity' : 'artefact');
    }
    if (blank(artefact.sha256) || artefact.sha256 !== lineage.artefactSha256)
      return refused('artefact_hash');
  } else return refused('link_kind');
  if (lineage.sourceIds.length === 0) return refused('source');
  if (lineage.inputClasses.length === 0) return refused('input_class_source');
  if (!classSetsAgree(fact.input_classes, lineage.inputClasses))
    return refused('input_class_source');
  if (
    fact.provenance !== 'suppressed' &&
    leastRealClass(fact.input_classes) !== fact.provenance
  )
    return refused('provenance_class');
  const sources: SourceRow[] = [];
  for (const sourceId of lineage.sourceIds) {
    const row = input.sources.find((item) => item.sourceId === sourceId);
    if (!row) return refused('source');
    const problem = sourceProblem(row);
    if (problem) return refused(problem);
    sources.push(row);
  }
  for (const inputClass of lineage.inputClasses) {
    if (inputClass === 'user_input') continue;
    const held = sources.some((row) => row.inputClass === inputClass);
    if (!held) return refused('input_class_source');
  }
  const companion = companionGap(binding, input, stack);
  if (companion) return refused('companion');
  const display: 'withheld' | 'value' =
    fact.provenance === 'suppressed' ? 'withheld' : 'value';
  const ready = {
    status: 'ready' as const,
    binding,
    lineage,
    sources,
    display,
  };
  return table
    ? { ...ready, link: 'table', table }
    : { ...ready, link: 'artefact', artefact: artefact! };
}

function classSetsAgree(
  factClasses: readonly string[],
  lineageClasses: readonly string[],
): boolean {
  if (new Set(factClasses).size !== factClasses.length) return false;
  if (new Set(lineageClasses).size !== lineageClasses.length) return false;
  if (factClasses.length !== lineageClasses.length) return false;
  const left = [...factClasses].sort();
  const right = [...lineageClasses].sort();
  return left.every((item, index) => item === right[index]);
}

function companionGap(
  binding: FactBinding,
  input: RegistryInput,
  stack: ReadonlySet<string>,
): boolean {
  const ids = companionIds(binding);
  if (ids === null) return true;
  for (const id of ids) {
    if (stack.has(id)) return true;
    const next = input.facts.find((item) => item.fact.fact_id === id);
    if (!next) return true;
    const resolved = chainOf(next, input, new Set([...stack, id]));
    if (resolved.status !== 'ready' || resolved.display !== 'value')
      return true;
  }
  return false;
}

function companionIds(binding: FactBinding): string[] | null {
  if (binding.presentation === 'ordinary' || binding.presentation === 'change')
    return [];
  if (binding.presentation === 'estimated_count') {
    if (!binding.rangeLowId || !binding.rangeHighId) return null;
    return [binding.rangeLowId, binding.rangeHighId];
  }
  if (binding.presentation === 'forecast') {
    if (
      !binding.intervalLowId ||
      !binding.intervalHighId ||
      !binding.backtestErrorId
    )
      return null;
    return [
      binding.intervalLowId,
      binding.intervalHighId,
      binding.backtestErrorId,
    ];
  }
  if (binding.presentation === 'site_estimate') {
    if (!binding.estimateLowId || !binding.estimateHighId) return null;
    return [binding.estimateLowId, binding.estimateHighId];
  }
  if (binding.presentation === 'base_rate') {
    if (!binding.numeratorId || !binding.denominatorId || !binding.periodId)
      return null;
    return [binding.numeratorId, binding.denominatorId, binding.periodId];
  }
  return null;
}

export function createRegistry(input: RegistryInput): FactRegistry {
  const facts = [...input.facts];
  const frozen: RegistryInput = {
    facts,
    releases: [...input.releases],
    tables: [...input.tables],
    artefacts: [...input.artefacts],
    lineages: [...input.lineages],
    sources: [...input.sources],
  };
  return {
    resolve(factId: string): Resolution {
      const binding = frozen.facts.find((item) => item.fact.fact_id === factId);
      if (!binding) return { status: 'no_data' };
      return chainOf(binding, frozen, new Set([factId]));
    },
    directionReferencers(directionId: string): readonly string[] {
      const parents: string[] = [];
      for (const binding of frozen.facts) {
        if (binding.directionId === directionId)
          parents.push(binding.fact.fact_id);
      }
      return parents;
    },
  };
}

export function readyLineage(resolution: Resolution): LineageRow | null {
  if (resolution.status !== 'ready') return null;
  return resolution.lineage;
}
