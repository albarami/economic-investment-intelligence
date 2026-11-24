/**
 * The area part of the view slice. Reset calls clearArea.
 * Vertices stay in memory. They never reach the address or browser storage.
 */
import { useSyncExternalStore } from 'react';

import type { LayerPayload } from '../stage/layers/payload';
import type { Session } from '../controls/draw-session';
import { idleSession } from '../controls/draw-session';
import type { Presented } from '../controls/present';

export interface AreaMemory {
  session: Session;
  presented: Presented | null;
  filtered: LayerPayload | null;
  ownPin: { latitude: number; longitude: number } | null;
}

const listeners = new Set<() => void>();

let current: AreaMemory = emptyMemory();

function emptyMemory(): AreaMemory {
  return {
    session: idleSession(),
    presented: null,
    filtered: null,
    ownPin: null,
  };
}

export function getArea(): AreaMemory {
  return current;
}

export function useArea(): AreaMemory {
  return useSyncExternalStore(subscribeArea, getArea, getArea);
}

export function subscribeArea(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function replaceArea(next: AreaMemory): void {
  current = next;
  for (const listener of listeners) listener();
}

export function clearArea(): void {
  replaceArea(emptyMemory());
}

export function addressSnapshot(state: AreaMemory): {
  mode: string | null;
  cutoff: number | null;
  shapeId: string | null;
} {
  return {
    mode: state.session.mode,
    cutoff: state.session.cutoff,
    shapeId: null,
  };
}

/** Writes nothing. A coordinate payload is refused before any storage call. */
export function guardStorageWrite(
  storage: { setItem(key: string, value: string): void },
  key: string,
  value: string,
): boolean {
  if (holdsCoordinateText(value)) return false;
  storage.setItem(key, value);
  return true;
}

export function holdsCoordinateText(value: string): boolean {
  return (
    value.includes('latitude') ||
    value.includes('longitude') ||
    value.includes('vertices')
  );
}

export function commitView(
  storage: { setItem(key: string, value: string): void },
  location: { search: string },
): { search: string } {
  const snap = addressSnapshot(current);
  void snap;
  void storage;
  return { search: location.search };
}
