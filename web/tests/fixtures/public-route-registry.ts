import { createRegistry } from '../../src/facts/registry';
import type { Fact, RegistryInput } from '../../src/facts/types';
import type { LayerPayload } from '../../src/stage/layers/payload';
export function routeRegistry(body: { facts: Fact[]; payload: LayerPayload }) {
  const facts = body.facts;
  const sources = body.payload.sources.map((s) => ({
    sourceId: s.sourceId,
    kind: 'public_dataset' as const,
    inputClass: 'public' as const,
    publisher: 'INVENTED-publisher',
    datasetOrPage: s.datasetOrPage,
    licenceOrTerms: s.licenceOrTerms,
    retrievalDate: s.retrievalDate,
    sha256: 'ab'.repeat(32),
  }));
  const lineages = [...new Set(facts.map((f) => f.lineage_ref))].map((id) => ({
    lineageId: id,
    releaseId: facts[0]!.release_id,
    tableName: id.replace('lin_', ''),
    method: 'invented.read',
    methodVersion: 'v1',
    sourceIds: sources.map((s) => s.sourceId),
    inputClasses: ['public' as const],
  }));
  const input: RegistryInput = {
    facts: facts.map((f) => ({
      fact: f,
      metricKey:
        body.payload.layers
          .flatMap((l) => l.features)
          .find((feature) => feature.fact_id === f.fact_id)?.metric_key ??
        'electricity_growth_class',
      presentation: 'ordinary',
    })),
    lineages,
    sources,
    tables: lineages.map((l) => ({
      tableName: l.tableName,
      releaseId: l.releaseId,
    })),
    releases: [{ releaseId: facts[0]!.release_id }],
  };
  return createRegistry(input);
}
