/**
 * The 3D buildings of the live map (S3-T16): one fixed read of the heights,
 * the shadow selection again on every view change, building updates through
 * the persistent map handle, and the picked building for "More evidence".
 */
import { useEffect, useState } from 'react';

import { requestLocal } from '../api/address-search.mjs';
import {
  buildingLayers,
  NO_SHADOWS,
  PROVISIONAL_BUILDING_CAP,
  readBuildingHeights,
  shadowSelection,
  type BuildingHeightsRead,
  type BuildingRow,
  type ShadowSelection,
} from './buildings3d';
import type { MapHandle } from './map-boot';

export interface DrawnBuildings {
  heights: BuildingHeightsRead;
  selection: ShadowSelection;
  picked?: BuildingRow;
}

type HeightsState = BuildingHeightsRead | 'refused' | null;

function signature(selection: ShadowSelection): string {
  const keys = selection.casting.map((row) => row.building_key);
  return JSON.stringify([keys, selection.limited]);
}

/** The heights read once the map is ready; a refused read draws nothing. */
function useHeights(
  ready: boolean,
): [HeightsState, (next: HeightsState) => void] {
  const [heights, setHeights] = useState<HeightsState>(null);
  useEffect(() => {
    if (!ready || heights !== null) return;
    const controller = new AbortController();
    void requestLocal('/api/building-heights', {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then(async (response) =>
        response.ok ? readBuildingHeights(await response.json()) : null,
      )
      .then((result) => {
        if (controller.signal.aborted) return;
        setHeights(result?.ok ? result.read : 'refused');
      })
      .catch(() => {
        if (!controller.signal.aborted) setHeights('refused');
      });
    return () => controller.abort();
  }, [ready, heights]);
  return [heights, setHeights];
}

export function useBuildings({
  isLive,
  handle,
  ready,
  hidden,
  cap = PROVISIONAL_BUILDING_CAP,
}: {
  /** Whether a handle is still the stage's map; a removed map is never updated. */
  isLive: (handle: MapHandle) => boolean;
  handle: MapHandle | null;
  ready: boolean;
  hidden: boolean;
  cap?: number;
}): DrawnBuildings | null {
  // Read only for a map that can draw buildings and report its view.
  const drawable = !!handle?.setBuildings && !!handle.viewBounds;
  const [heights, setHeights] = useHeights(ready && drawable);
  const [selection, setSelection] = useState<ShadowSelection>(NO_SHADOWS);
  const [picked, setPicked] = useState<BuildingRow | undefined>(undefined);
  const read = typeof heights === 'object' ? heights : null;
  useEffect(() => {
    if (!handle || !isLive(handle) || !ready || !read || hidden) return;
    let drawn: string | null = null;
    let frame: ReturnType<typeof setTimeout> | null = null;
    const apply = () => {
      frame = null;
      const view = handle.viewBounds?.();
      if (!view) return;
      try {
        const next = shadowSelection(read.buildings, view, cap);
        if (signature(next) === drawn) return;
        handle.setBuildings?.(
          buildingLayers(read.buildings, next, setPicked),
          cap,
        );
        drawn = signature(next);
        setSelection(next);
      } catch {
        handle.setBuildings?.([], cap);
        setHeights('refused');
      }
    };
    // One selection per task at most, however many view events arrive.
    const schedule = () => {
      if (frame === null) frame = setTimeout(apply, 0);
    };
    apply();
    handle.bindView(schedule);
    return () => {
      if (frame !== null) clearTimeout(frame);
      handle.unbindView(schedule);
      if (isLive(handle)) handle.setBuildings?.([], cap);
      setSelection(NO_SHADOWS);
    };
  }, [isLive, handle, ready, read, hidden, cap, setHeights]);
  if (!read || hidden || !handle || !ready) return null;
  return { heights: read, selection, picked };
}
