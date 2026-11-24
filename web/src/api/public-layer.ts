import type { Fact } from '../facts/types';
import {
  createRegistry,
  type FactRegistry,
  type RegistryInput,
} from '../facts/registry';
import {
  LAYER_NO_DATA_REASONS,
  type LayerNoDataReason,
  type LayerPayload,
} from '../stage/layers/payload';
import { mergeInputs, unique } from './public-opening';
import { loadRegistryInput } from './release';

export type PublicLayerKey =
  | 'zone_electricity_growth'
  | 'parcels'
  | 'night_lights'
  | 'land_prices'
  | 'public_places'
  | 'rail_plan'
  | 'health_centres'
  | 'zoning'
  | 'commercial_points'
  | 'address_points'
  | 'landmarks'
  | 'fdi_projects'
  | 'property_prices'
  | 'company_points'
  | 'accidents';

export interface PublicLayerResult {
  payload: LayerPayload;
  registry: FactRegistry;
  input: RegistryInput;
  status: 'ok' | 'NO_DATA';
  /** The closed reason of a NO_DATA envelope; null when the route gives none. */
  reason: LayerNoDataReason | null;
}

const ENVELOPE = ['coverage_report', 'facts', 'payload', 'status'];

/**
 * The closed envelope: its four keys, or five when a NO_DATA body names a
 * closed reason and draws nothing. Undefined refuses the body.
 */
function envelopeReason(
  body: Record<string, unknown>,
): LayerNoDataReason | null | undefined {
  const keys = Object.keys(body).sort().join();
  if (keys === ENVELOPE.join()) return null;
  if (keys !== [...ENVELOPE, 'reason'].sort().join()) return undefined;
  const layers = (body.payload as Partial<LayerPayload> | null)?.layers;
  if (
    body.status !== 'NO_DATA' ||
    !(LAYER_NO_DATA_REASONS as readonly unknown[]).includes(body.reason) ||
    (body.facts as unknown[]).length !== 0 ||
    !Array.isArray(layers) ||
    layers.some(
      (layer) => !Array.isArray(layer.features) || layer.features.length,
    )
  )
    return undefined;
  return body.reason as LayerNoDataReason;
}

export async function loadPublicLayer(
  key: PublicLayerKey | 'fc_firms_per_tower',
): Promise<PublicLayerResult> {
  const response = await fetch('/api/layers/' + key, {
    credentials: 'same-origin',
    redirect: 'error',
  });
  if (!response.ok) throw new Error('layer_refused');
  const body = (await response.json()) as unknown;
  if (typeof body !== 'object' || body === null)
    throw new Error('layer_refused');
  const fields = body as Record<string, unknown>;
  const status = fields.status;
  if (!Array.isArray(fields.facts) || (status !== 'ok' && status !== 'NO_DATA'))
    throw new Error('layer_refused');
  const reason = envelopeReason(fields);
  if (reason === undefined) throw new Error('layer_refused');
  const input = await loadRegistryInput(fields.facts as Fact[]);
  const registry = createRegistry(input);
  return {
    payload: fields.payload as LayerPayload,
    registry,
    input,
    status,
    reason,
  };
}

/**
 * The chosen layer with its context layers (S3-T12: accidents beside the
 * planned rail). One release only; a NO_DATA layer draws nothing and the
 * chosen layer's status and reason stay its own.
 */
export function composeLayers(
  results: readonly PublicLayerResult[],
): PublicLayerResult {
  const [chosen] = results;
  if (!chosen) throw new Error('layer_refused');
  if (results.length === 1) return chosen;
  const drawn = results.filter((result) => result.status === 'ok');
  const input = mergeInputs(results.map((result) => result.input));
  return {
    ...chosen,
    payload: {
      ...chosen.payload,
      layers: drawn.flatMap((result) => result.payload.layers),
      sources: unique(
        drawn.flatMap((result) => result.payload.sources),
        (row) => row.sourceId,
      ),
    },
    input,
    registry: createRegistry(input),
  };
}
