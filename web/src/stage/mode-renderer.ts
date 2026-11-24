import type { Layer } from '@deck.gl/core';
import { photoreal } from './photoreal';
/** Ephemeral renderer: all remote bytes cross the existing local transport. */
import {
  addProtocol,
  removeProtocol,
  type Map,
  type StyleSpecification,
} from 'maplibre-gl';
import { requestLocal } from '../api/address-search.mjs';
import type { MapMode, ModeFailureReason, SpendMeter } from './map-modes';

let serial = 0;
export function modeRenderer(
  map: Map,
  open: StyleSpecification,
  onFailure?: (mode: MapMode, reason: ModeFailureReason) => void,
  attach: (layer: Layer | null) => void = () => undefined,
  onMeter: ((meter: SpendMeter) => void) | undefined = undefined,
) {
  const protocol = `eii-imagery-${serial++}`;
  let active: AbortController | null = null;
  let registered = false;
  let native: ReturnType<typeof photoreal> | null = null;
  function clear() {
    active?.abort();
    native?.dispose();
    native = null;
    if (registered) removeProtocol(protocol);
    registered = false;
  }
  return {
    remove: clear,
    async setMode(mode: MapMode, credit: (value: string) => void) {
      clear();
      credit('');
      const controller = new AbortController();
      active = controller;
      const failed = (reason: ModeFailureReason = 'network') => {
        if (!controller.signal.aborted) onFailure?.(mode, reason);
      };
      const credits = new Set<string>();
      const read = async (path: string, signal = controller.signal) => {
        const response = await requestLocal(path, {
          cache: 'no-store',
          signal,
        }).catch((error: unknown) => {
          failed();
          throw error;
        });
        if (!response.ok) {
          failed();
          throw new Error('tile refused');
        }
        const value = response.headers.get('x-attribution');
        if (!value) {
          failed();
          throw new Error('credit absent');
        }
        if (controller.signal.aborted) throw new Error('view closed');
        credits.add(value);
        credit([...credits].join(' · '));
        return response;
      };
      if (mode === 'open') {
        map.setStyle(open);
        return;
      }
      if (mode === 'satellite') {
        addProtocol(protocol, async (request, abort) => {
          const path = request.url.replace(
            `${protocol}://`,
            '/api/imagery/tiles/',
          );
          if (!/^\/api\/imagery\/tiles\/\d+\/\d+\/\d+$/.test(path))
            throw new Error('tile path');
          const response = await read(
            path,
            AbortSignal.any([controller.signal, abort.signal]),
          );
          return {
            data: await response.arrayBuffer(),
            cacheControl: 'no-store',
          };
        });
        registered = true;
        map.setStyle({
          version: 8,
          sources: {
            imagery: { type: 'raster', tiles: [`${protocol}://{z}/{x}/{y}`] },
          },
          layers: [{ id: 'imagery', type: 'raster', source: 'imagery' }],
        });
        return;
      }
      const renderer = photoreal(attach, credit, failed, onMeter);
      native = renderer;
      await renderer.start();
      if (!controller.signal.aborted)
        map.setStyle({ version: 8, sources: {}, layers: [] });
    },
  };
}
