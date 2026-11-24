/**
 * S3-T12: the mounted invented accident and rail HTTP bodies
 * (`accident-layer.json`, proven equal to the live mounted routes by
 * `product/tests/test_accident_mounted_http.py`), joined into one scene.
 * A plant changes one input of this valid scene.
 */
import mounted from './accident-layer.json';
import { unique } from '../../src/api/public-opening';
import { createRegistry } from '../../src/facts/registry';
import type {
  Fact,
  FactBinding,
  LineageRow,
  ReleaseTable,
  SourceRow,
} from '../../src/facts/types';
import type {
  LayerFeature,
  LayerPayload,
  LayerRequest,
} from '../../src/stage/layers/payload';

export type LayerBody = { facts: Fact[]; payload: LayerPayload };

export const ACCIDENT_HTTP = mounted as unknown as Record<
  'accidents' | 'rail_plan' | 'geography_missing' | 'source_missing',
  LayerBody & { status: string; reason?: string }
> & {
  release: { tables: ReleaseTable[] };
  chains: Record<string, MountedChain>;
};

/**
 * CF1 finding 2: the values an uncast HTTP body can put where a text field
 * is expected, beside the two empty texts. None of them is a nonempty string.
 */
export const NOT_TEXT = [
  ['null', null],
  ['a number', 51],
  ['an array', ['51']],
  ['an object', { value: '51' }],
  ['an empty text', ''],
  ['a blank text', '  '],
] as const;

/** One `/api/facts/{id}/lineage` body of the mounted route. */
export interface MountedChain {
  lineage: LineageRow;
  sources: SourceRow[];
  binding: Pick<FactBinding, 'metricKey' | 'presentation'>;
}

/** A valid planned line beside the mounted station (rail lines carry no status). */
export const PLANNED_LINE: LayerFeature = {
  feature_id: 'rail_plan:INVENTED-line',
  metric_key: 'rail_feature',
  provenance: 'public',
  subject: 'gis_feature',
  geometry_kind: 'line',
  source_id: 'src-invented',
  path: [
    [0, 0],
    [3, 3],
  ],
};

export interface SceneParts {
  accident: LayerFeature;
  accidents: LayerRequest;
  station: LayerFeature;
  line: LayerFeature;
}

export function accidentScene(change?: (parts: SceneParts) => void): LayerBody {
  const accidents = structuredClone(ACCIDENT_HTTP.accidents);
  const rail = structuredClone(ACCIDENT_HTTP.rail_plan);
  const railLayer = rail.payload.layers[0]!;
  railLayer.features = [...railLayer.features, { ...PLANNED_LINE }];
  const accidentLayer = accidents.payload.layers[0]!;
  change?.({
    accident: accidentLayer.features[0]!,
    accidents: accidentLayer,
    station: railLayer.features[0]!,
    line: railLayer.features[1]!,
  });
  return {
    facts: [...accidents.facts, ...rail.facts],
    payload: {
      ...accidents.payload,
      layers: [accidentLayer, railLayer],
    },
  };
}

/** The scene's registry from the mounted route's own chains and bindings. */
export function chainRegistry(
  facts: readonly Fact[],
  mountedChains: Record<string, MountedChain> = ACCIDENT_HTTP.chains,
) {
  const chains = facts.map((fact) => mountedChains[fact.fact_id]!);
  return createRegistry({
    facts: facts.map((fact, index) => ({
      fact,
      metricKey: chains[index]!.binding.metricKey,
      presentation: chains[index]!.binding.presentation,
    })),
    lineages: unique(
      chains.map((chain) => chain.lineage),
      (row) => row.lineageId,
    ),
    sources: unique(
      chains.flatMap((chain) => chain.sources),
      (row) => row.sourceId,
    ),
    tables: ACCIDENT_HTTP.release.tables,
    releases: [{ releaseId: facts[0]!.release_id }],
  });
}

/** The scene with its registry: binding checks run. */
export function boundScene(change?: (parts: SceneParts) => void) {
  const body = accidentScene(change);
  return { body, registry: chainRegistry(body.facts) };
}
