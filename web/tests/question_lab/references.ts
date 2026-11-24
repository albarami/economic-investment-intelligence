/** The trusted reference source of the browser lab (S3-B12 round 7): the
 * release the opening fixture serves, read from its `work` folder on disk
 * in Node through the server's own checked reader, never from the page.
 * Every refusal throws `ReferenceSourceError` with a named reason; no
 * reader returns an empty list.
 */
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import type { ReferenceKind, ReferenceRecord } from './contract';

export class ReferenceSourceError extends Error {
  constructor(readonly reason: string) {
    super(`reference_source:${reason}`);
  }
}

/** One answer fact's citation chain as its card renders it. */
export interface ReferenceChain {
  factId: string;
  tableName: string;
  lineageId: string;
  method: string;
  methodVersion: string;
  sources: readonly {
    sourceId: string;
    publisher: string;
    datasetOrPage: string;
    licenceOrTerms: string;
    retrievalDate: string;
    sha256: string;
  }[];
}

/** The evidence-level reference records of one chain, in chip order: the
 * release table, the method and its version, then each source's five. */
export function chainReferences(chain: ReferenceChain): ReferenceRecord[] {
  const refs: ReferenceRecord[] = [];
  const add = (record: string, kind: ReferenceKind, value: string) =>
    refs.push({ record, kind, value });
  add(chain.factId, 'published_text', chain.tableName);
  add(chain.lineageId, 'published_text', chain.method);
  add(chain.lineageId, 'published_text', chain.methodVersion);
  for (const source of chain.sources) {
    add(source.sourceId, 'published_text', source.publisher);
    add(source.sourceId, 'published_text', source.datasetOrPage);
    add(source.sourceId, 'published_text', source.licenceOrTerms);
    add(source.sourceId, 'calendar_date', source.retrievalDate);
    add(source.sourceId, 'published_text', source.sha256);
  }
  return refs;
}

/** The release values one card family cites, before an answer exists. */
export interface ReleaseReferences {
  releaseId: string;
  /** The latest period of the table: the playbook's `month_key`. */
  period: string;
  chain: Omit<ReferenceChain, 'factId'>;
}

type Row = Record<string, unknown>;

/** The raw rows the bridge reads; every field is checked before use. */
export interface ReleaseDump {
  release_id: unknown;
  fact_lineage: unknown;
  source_registry: unknown;
  periods: unknown;
}

const ROOT = path.resolve(process.cwd(), '..');

// The server's own checked reader (`check_release` recomputes every hash;
// `_parquet_rows` is the loader's and the mounted release's row reader).
const BRIDGE = `
import json, sys
from pathlib import Path
from eii_product.store.loader import _parquet_rows
from eii_product.store.release_check import ReleaseRefusal, check_release
folder = Path(sys.argv[1])
try:
    checked = check_release(folder)
except ReleaseRefusal as refusal:
    print(json.dumps({"refused": refusal.reason}))
    raise SystemExit(0)
def rows(name):
    return _parquet_rows(folder / ("tables/" + name + ".parquet"), checked.schemas[name])
print(json.dumps({
    "release_id": checked.document["release_id"],
    "fact_lineage": rows("fact_lineage"),
    "source_registry": rows("source_registry"),
    "periods": sorted({r["period"] for r in rows(sys.argv[2])}),
}, default=str))
`;

/** One offline `uv run --locked python -c` from the repository root, in
 * the opening fixture's environment; `pythonPath` adds an import root. */
export function runPython(
  code: string,
  args: readonly string[],
  pythonPath?: string,
): { status: number | null; stdout: string; stderr: string } {
  const tmp = path.join(ROOT, '.overnight/tmp');
  return spawnSync('uv', ['run', '--locked', 'python', '-c', code, ...args], {
    cwd: ROOT,
    encoding: 'utf8',
    timeout: 120_000,
    env: {
      PATH: process.env.PATH ?? '',
      HOME: process.env.HOME ?? '',
      TMPDIR: tmp,
      UV_CACHE_DIR: process.env.UV_CACHE_DIR ?? path.join(tmp, 'uv-cache'),
      UV_OFFLINE: '1',
      ...(pythonPath === undefined ? {} : { PYTHONPATH: pythonPath }),
    },
  });
}

/** Read the release folder of the fixture's `work` through the bridge. */
export function readReleaseDump(work: string, table: string): ReleaseDump {
  const run = runPython(BRIDGE, [path.join(work, 'release'), table]);
  return bridgeDump(run.status, run.stdout);
}

/** The bridge's exit and output as a dump: a failed exit, an output that
 * is not one JSON object, or a release refusal throws its named reason. */
export function bridgeDump(status: number | null, stdout: string): ReleaseDump {
  if (status !== 0) throw new ReferenceSourceError('bridge_failed');
  let parsed: unknown;
  try {
    parsed = JSON.parse(stdout);
  } catch {
    throw new ReferenceSourceError('bridge_output');
  }
  if (!isRow(parsed)) throw new ReferenceSourceError('bridge_output');
  if (parsed.refused !== undefined)
    throw new ReferenceSourceError(`release:${String(parsed.refused)}`);
  return parsed as unknown as ReleaseDump;
}

function isRow(value: unknown): value is Row {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function rowsOf(value: unknown): Row[] {
  if (!Array.isArray(value) || !value.every(isRow))
    throw new ReferenceSourceError('dump_shape');
  return value;
}

function text(row: Row, key: string, reason = 'source_field'): string {
  const value = row[key];
  if (typeof value !== 'string' || value.trim() === '')
    throw new ReferenceSourceError(reason);
  return value;
}

const MONTH = /^[0-9]{4}-(?:0[1-9]|1[0-2])$/;
const DAY = /^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])$/;

/** Mirror the server's chain read for one table (`public_lineage_for_table`,
 * `sector_facts_sources`, `MountedRelease.project`) and its latest period
 * (`layer_night_lights_months`, the playbook's last month). */
export function releaseReferences(
  dump: ReleaseDump,
  table: string,
): ReleaseReferences {
  const releaseId = dump.release_id;
  if (typeof releaseId !== 'string' || !/^[0-9a-f]{64}$/.test(releaseId))
    throw new ReferenceSourceError('release_id');
  const lines = rowsOf(dump.fact_lineage).filter(
    (row) => row.table_name === table,
  );
  if (lines.length === 0) throw new ReferenceSourceError('lineage_missing');
  const ids = new Set(lines.map((row) => row.lineage_id));
  if (ids.size !== 1) throw new ReferenceSourceError('lineage_ambiguous');
  const lineageId = text(lines[0]!, 'lineage_id', 'lineage_missing');
  const all = rowsOf(dump.fact_lineage).filter(
    (row) => row.lineage_id === lineageId,
  );
  if (all.some((row) => row.table_name !== table))
    throw new ReferenceSourceError('lineage_table');
  const whole = lines[0]!.transform;
  const at = typeof whole === 'string' ? whole.lastIndexOf('@') : -1;
  if (
    typeof whole !== 'string' ||
    new Set(all.map((row) => row.transform)).size !== 1 ||
    at <= 0 ||
    at === whole.length - 1
  )
    throw new ReferenceSourceError('transform');
  const registry = rowsOf(dump.source_registry);
  const sourceRows = [
    ...new Set(all.map((row) => text(row, 'source_id', 'source_missing'))),
  ]
    .sort()
    .map((sourceId) => {
      const found = registry.filter((row) => row.source_id === sourceId);
      if (found.length === 0) throw new ReferenceSourceError('source_missing');
      if (found.length > 1) throw new ReferenceSourceError('source_duplicate');
      return found[0]!;
    });
  const sources = sourceRows.map((row) => {
    const retrievalDate = text(row, 'retrieved_on');
    if (!DAY.test(retrievalDate))
      throw new ReferenceSourceError('source_field');
    return {
      sourceId: text(row, 'source_id'),
      publisher: text(row, 'publisher'),
      datasetOrPage: text(row, 'title'),
      licenceOrTerms: text(row, 'licence'),
      retrievalDate,
      sha256: text(row, 'sha256'),
    };
  });
  const periods = dump.periods;
  if (!Array.isArray(periods) || periods.length === 0)
    throw new ReferenceSourceError('period_missing');
  if (
    !periods.every((period) => typeof period === 'string' && MONTH.test(period))
  )
    throw new ReferenceSourceError('period_shape');
  return {
    releaseId,
    period: [...(periods as string[])].sort().at(-1)!,
    chain: {
      tableName: table,
      lineageId,
      method: whole.slice(0, at),
      methodVersion: whole.slice(at + 1),
      sources,
    },
  };
}

/** The one area the server issued for the case's typed selection mode:
 * the story also issues a wider drive ring, which is never the answer's
 * area for another mode. None is `area_missing`; two are `area_ambiguous`. */
export function answerArea(
  issued: readonly (string | null)[],
  mode: string,
): string {
  const found = new Set(
    issued.filter(
      (area): area is string => area !== null && area.split('/')[2] === mode,
    ),
  );
  if (found.size === 0) throw new ReferenceSourceError('area_missing');
  if (found.size > 1) throw new ReferenceSourceError('area_ambiguous');
  return [...found][0]!;
}

/** DAT-93 (`eii_core.facts.fact_id`) for an area-shape answer fact with no
 * qualifiers: the area id is the one the server issued for this release. */
export function answerFactId(
  refs: ReleaseReferences,
  metricKey: string,
  areaId: string,
): string {
  if (!areaId.startsWith(`ma1/${refs.releaseId.slice(0, 16)}/`))
    throw new ReferenceSourceError('area_release');
  const encoded = JSON.stringify({
    geography: { area_id: areaId, kind: 'area_shape' },
    metric_key: metricKey,
    period: refs.period,
    qualifiers: {},
    release_id: refs.releaseId,
  });
  return 'f_' + createHash('sha256').update(encoded).digest('hex').slice(0, 32);
}

/** The trusted records one capture of a night-lights card must bind: the
 * answer level's month, and the citation chain once evidence is open. */
export function nightLightsReferences(
  refs: ReleaseReferences,
  factId: string,
  evidenceOpen: boolean,
): ReferenceRecord[] {
  return [
    { record: factId, kind: 'calendar_month', value: refs.period },
    ...(evidenceOpen ? chainReferences({ ...refs.chain, factId }) : []),
  ];
}
