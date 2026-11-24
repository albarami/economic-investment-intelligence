import type { Fact } from '../facts/types';
import {
  createRegistry,
  type FactRegistry,
  type RegistryInput,
} from '../facts/registry';
import type { LayerPayload } from '../stage/layers/payload';
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
  | 'company_points';

export async function loadPublicLayer(
  key: PublicLayerKey | 'fc_firms_per_tower',
): Promise<{
  payload: LayerPayload;
  registry: FactRegistry;
  input: RegistryInput;
}> {
  const response = await fetch('/api/layers/' + key, {
    credentials: 'same-origin',
    redirect: 'error',
  });
  if (!response.ok) throw new Error('layer_refused');
  const body = (await response.json()) as {
    facts: Fact[];
    payload: LayerPayload;
    status: string;
    coverage_report: unknown;
  };
  if (
    Object.keys(body).sort().join() !==
      ['coverage_report', 'facts', 'payload', 'status'].join() ||
    !Array.isArray(body.facts) ||
    !['ok', 'NO_DATA'].includes(body.status)
  )
    throw new Error('layer_refused');
  const input = await loadRegistryInput(body.facts);
  const registry = createRegistry(input);
  return { payload: body.payload, registry, input };
}
