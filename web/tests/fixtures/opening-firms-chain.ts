/**
 * Invented successful firms-per-tower chain for the opening screen (S3-T10).
 * It answers the same-origin paths that the existing API client reads:
 * `/api/release`, `/api/layers/fc_firms_per_tower` and one
 * `/api/facts/{fact_id}/lineage` per fact. Every value is invented and
 * visibly synthetic; nothing here is imported by production code.
 */
import type { Fact } from '../../src/facts/types';
import { makeFact, makeLineage, makeSource, tableWire } from './facts';
import {
  FC_ALEPH,
  FC_BREAKS,
  FC_DISTRICT,
  FC_GIMEL,
  fcPayload,
} from './fc-firms';

const TABLE = 'pub_register_company';
const LINEAGE = makeLineage({
  lineageId: 'lin_invented_fc_register',
  tableName: TABLE,
  method: 'eii_core.calc.firms_per_tower',
  methodVersion: 'v1',
  sourceIds: ['src_places'],
});
const SOURCE = makeSource({
  sourceId: 'src_places',
  publisher: 'Sample Publisher',
  datasetOrPage: 'Sample register page',
});

/** The registry values of `fcRegistry`: Aleph 4, Gimel 1, district 1, bands 1 to 5. */
const COUNTS: readonly [string, number, string | null][] = [
  [FC_ALEPH, 4, 'place:INV-TOWER-ALEPH'],
  [FC_GIMEL, 1, 'place:INV-TOWER-GIMEL'],
  [FC_DISTRICT, 1, 'district:INV-NORTH'],
  ...FC_BREAKS.map((id, index): [string, number, null] => [
    id,
    index + 1,
    null,
  ]),
];

export interface FirmsChain {
  release: Record<string, unknown>;
  layer: {
    status: string;
    facts: Fact[];
    coverage_report: unknown;
    payload: unknown;
  };
  lineages: Record<string, Record<string, unknown> | undefined>;
  /** HTTP status by path for a found body; 200 when absent. */
  status: Record<string, number>;
}

/** A fresh, mutable copy, so a plant changes one input of one test only. */
export function firmsChain(): FirmsChain {
  const facts = COUNTS.map(([fact_id, value, code]) =>
    makeFact({
      fact_id,
      value,
      unit: 'count',
      period: '2024',
      geography: code
        ? { kind: 'public', public_code: code }
        : { kind: 'national' },
      lineage_ref: LINEAGE.lineageId,
      label_en: 'Firms registered here',
      label_ar: 'الشركات المسجلة هنا',
    }),
  );
  return structuredClone({
    release: {
      release_id: LINEAGE.releaseId,
      release_kind: 'public_only',
      rules_version_id: 'INVENTED-rules',
      tables: [{ releaseId: LINEAGE.releaseId, tableName: TABLE }],
      artefacts: [],
      hour_keys: [],
      day_keys: [],
      month_keys: [],
      basemap_url: null,
    },
    layer: {
      status: 'ok',
      facts,
      coverage_report: { counts: {} },
      payload: fcPayload(),
    },
    lineages: Object.fromEntries(
      facts.map((fact) => [
        fact.fact_id,
        {
          fact_id: fact.fact_id,
          release_id: LINEAGE.releaseId,
          lineage: tableWire(LINEAGE),
          sources: [SOURCE],
          binding: {
            metricKey: 'firms_per_tower',
            presentation: 'ordinary',
            qualifiers: {},
          },
        },
      ]),
    ),
    status: {},
  });
}

/** A same-origin `fetch` over the chain. Any other path, or any absolute URL,
 * answers 404 and is recorded, so no request ever leaves the test. */
export function chainFetch(chain: FirmsChain, seen: string[] = []) {
  return async (url: RequestInfo | URL): Promise<Response> => {
    const path = String(url);
    seen.push(path);
    const lineage = /^\/api\/facts\/([^/]+)\/lineage$/.exec(path);
    const body =
      path === '/api/release'
        ? chain.release
        : path === '/api/layers/fc_firms_per_tower'
          ? chain.layer
          : lineage
            ? chain.lineages[lineage[1] ?? '']
            : undefined;
    return body === undefined
      ? new Response('{}', { status: 404 })
      : new Response(JSON.stringify(body), {
          status: chain.status[path] ?? 200,
          headers: { 'content-type': 'application/json' },
        });
  };
}
