/**
 * Fact registries whose metric, provenance and table match a layer slot.
 * Values differ on purpose: acceptance never reads them.
 */
import {
  createRegistry,
  type FactRegistry,
  type Provenance,
} from '../../src/facts/registry';
import type { Geography } from '../../src/facts/types';
import {
  factId,
  makeBinding,
  makeFact,
  makeLineage,
  makeSource,
} from './facts';

export interface LayerFactSpec {
  id: string;
  metric: string;
  table: string;
  provenance?: Provenance;
  retrievalDate?: string;
  value?: number;
  unit?: string;
  geography?: Geography;
}

export function layerRegistry(rows: readonly LayerFactSpec[]): FactRegistry {
  const release = makeFact().release_id;
  const dated = rows.find((row) => row.retrievalDate !== undefined);
  const retrieval = dated ? dated.retrievalDate : '2024-03-14';
  return createRegistry({
    facts: rows.map((row, index) =>
      makeBinding({
        fact: makeFact({
          fact_id: row.id,
          provenance: row.provenance ?? 'public',
          lineage_ref: `lin_layer_${index}`,
          value: row.value ?? 48,
          unit: row.unit ?? 'count',
          ...(row.geography ? { geography: row.geography } : {}),
        }),
        metricKey: row.metric,
      }),
    ),
    releases: [{ releaseId: release }],
    tables: rows.map((row) => ({ releaseId: release, tableName: row.table })),
    lineages: rows.map((row, index) =>
      makeLineage({
        lineageId: `lin_layer_${index}`,
        tableName: row.table,
      }),
    ),
    sources: [
      makeSource({
        retrievalDate: retrieval ?? '2024-03-14',
      }),
    ],
  });
}

export function sceneRegistry(): FactRegistry {
  return layerRegistry([
    { id: factId(0), metric: 'place_listing', table: 'pub_place', value: 3 },
    { id: factId(1), metric: 'poi_category', table: 'pub_poi_comm', value: 9 },
    { id: factId(2), metric: 'fdi_capex', table: 'fdi_projects', value: 12 },
    { id: factId(3), metric: 'fdi_jobs', table: 'fdi_projects', value: 4 },
    { id: factId(4), metric: 'rail_feature', table: 'pub_rail_plan', value: 1 },
  ]);
}
