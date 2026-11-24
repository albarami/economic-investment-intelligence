/** Invented context values, never provider data. */
import type { ContextPayload } from '../../src/cards/PublicContextCard';
import { createRegistry } from '../../src/facts/registry';
import {
  factId,
  makeBinding,
  makeFact,
  makeLineage,
  makeSource,
} from './facts';

export const contextPayloads: readonly ContextPayload[] = [
  { family: 'night_lights', state: 'ready', factId: factId(0) },
  {
    family: 'venue_busyness',
    state: 'ready',
    factId: factId(1),
    retrievedOn: '2026-01-01',
    providerUpdatedOn: null,
    day: 'monday',
    hour: '9',
  },
  {
    family: 'population_age_sex',
    state: 'ready',
    factId: factId(2),
    ageBand: '20',
    sex: 'female',
  },
];

export function contextInput() {
  const tables = [
    'pub_night_lights',
    'pub_venue_busyness',
    'pub_pop_agesex_grid',
  ];
  const metrics = [
    'night_lights_radiance',
    'venue_busyness_index',
    'population_grid_people',
  ];
  const units = ['radiance_nw_cm2_sr', 'relative_index', 'count'];
  const periods = ['2024-01', '2026-01-01', '2025'];
  const caveats = [
    'night_lights_not_activity',
    'relative_busyness_not_people',
    'grid_cells_summed',
  ];
  const facts = tables.map((table, index) =>
    makeBinding({
      metricKey: metrics[index],
      ...(index === 1
        ? { qualifiers: { day_of_week: 'monday', hour: '9' } }
        : index === 2
          ? { qualifiers: { age_band: '20', sex: 'female' as const } }
          : {}),
      fact: makeFact({
        fact_id: factId(index),
        value: [7, 40, 23][index],
        unit: units[index],
        period: periods[index],
        lineage_ref: `lin_${table}`,
        caveat_keys: [caveats[index] ?? ''],
        geography:
          index === 1
            ? { kind: 'public', public_code: 'place:fixture_venue' }
            : { kind: 'area_shape', area_id: 'fixture_area' },
        label_en: [
          'Night-time radiance',
          'BestTime relative busyness',
          'Population by age and sex',
        ][index],
        label_ar: [
          'الإشعاع الضوئي الليلي',
          'مؤشر الانشغال النسبي من BestTime',
          'السكان حسب العمر والجنس',
        ][index],
      }),
    }),
  );
  const releaseId = facts[0]?.fact.release_id ?? '';
  return {
    facts,
    releases: [{ releaseId }],
    tables: tables.map((tableName) => ({ releaseId, tableName })),
    lineages: tables.map((tableName) =>
      makeLineage({
        lineageId: `lin_${tableName}`,
        tableName,
        ...(tableName === 'pub_venue_busyness'
          ? { rowRetrievalDate: '2026-01-01', providerUpdatedOn: null }
          : {}),
      }),
    ),
    sources: [makeSource()],
  };
}

export function contextRegistry() {
  return createRegistry(contextInput());
}
