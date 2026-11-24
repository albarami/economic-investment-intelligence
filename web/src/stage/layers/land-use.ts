/** One selected category, shared by the map and plate. No numeric facts. */
import { useSyncExternalStore } from 'react';
import type { DrawnLayer } from './refuse';

export type UseChoice = { kind: 'initial' } | { kind: 'chosen'; key: string };
let choice: UseChoice = { kind: 'initial' };
const listeners = new Set<() => void>();
export function readUseChoice(): UseChoice {
  return choice;
}
export function chooseUse(key: string): void {
  choice = { kind: 'chosen', key };
  listeners.forEach((listener) => listener());
}
export function resetUseChoice(): void {
  choice = { kind: 'initial' };
  listeners.forEach((listener) => listener());
}
export function subscribeUseChoice(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
export function useLandUse(): UseChoice {
  return useSyncExternalStore(subscribeUseChoice, readUseChoice, readUseChoice);
}
export function landGroupKeys(layers: readonly DrawnLayer[]): string[] {
  return (
    layers
      .find((layer) => layer.key === 'land_prices')
      ?.classBreaks.flatMap((group) =>
        group.group_key === null ? [] : [group.group_key],
      ) ?? []
  );
}
export function activeUse(
  groups: readonly string[],
  selected: UseChoice,
): string | null {
  return selected.kind === 'chosen' && groups.includes(selected.key)
    ? selected.key
    : (groups[0] ?? null);
}
export function forUse(
  layers: readonly DrawnLayer[],
  active: string | null,
): DrawnLayer[] {
  return layers.map((layer) =>
    layer.key === 'land_prices'
      ? {
          ...layer,
          features: layer.features.filter(
            (feature) => feature.class_group === active,
          ),
          classBreaks: layer.classBreaks.filter(
            (group) => group.group_key === active,
          ),
        }
      : layer,
  );
}
