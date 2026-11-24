/** Ephemeral native renderer on the map's existing interleaved overlay. */
import type { Layer } from '@deck.gl/core';
import { qualifiedLayer, visibleCredits } from './photoreal-loader';
import { ModeFailure, type ModeFailureReason } from './map-modes';
import { photorealSession } from './photoreal-session';

let serial = 0;
interface VisibleTile {
  content: {
    gltf?: {
      asset?: { copyright?: unknown };
      images?: { image?: { close?: () => void } }[];
    };
  } | null;
}
function releaseImages(tile: VisibleTile) {
  for (const image of tile.content?.gltf?.images ?? []) image.image?.close?.();
}
export function photoreal(
  attach: (layer: Layer | null) => void,
  credit: (text: string) => void,
  failure: (reason: ModeFailureReason) => void,
) {
  const session = photorealSession();
  let closed = false;
  const decoded = new Set<VisibleTile>();
  let tileset: { destroy(): void } | null = null;
  function dispose() {
    if (closed) return;
    closed = true;
    session.dispose();
    for (const tile of decoded) releaseImages(tile);
    decoded.clear();
    attach(null);
    credit('');
    tileset?.destroy();
    tileset = null;
  }
  const fail = (reason: ModeFailureReason) => {
    if (!closed) {
      dispose();
      failure(reason);
    }
  };
  const failed = () => fail('network');
  return {
    dispose,
    async start() {
      let reason: ModeFailureReason = 'network';
      try {
        const root = await session.open();
        if (closed) return;
        reason = 'renderer_unavailable';
        const layer = qualifiedLayer(
          {
            id: `photoreal:${serial++}`,
            data: root,
            onTilesetLoad(value) {
              if (closed) value.destroy();
              else {
                tileset = value;
                // Root completion can follow the layer's viewport-change pass.
                // Start traversal from the current viewport even if it did not move.
                void value.selectTiles([layer.context.viewport]).catch(failed);
              }
            },
            onTileUnload(tile) {
              releaseImages(tile);
              decoded.delete(tile);
            },
            onTileLoad(tile) {
              if (closed) releaseImages(tile);
              else decoded.add(tile);
            },
            onTileError: failed,
            onError: () => {
              failed();
              return true;
            },
            loadOptions: {
              tileset: {
                onTraversalComplete(selected: VisibleTile[]) {
                  if (closed) return [];
                  try {
                    credit(
                      visibleCredits(
                        selected.map(
                          (tile) => tile.content?.gltf?.asset?.copyright,
                        ),
                      ),
                    );
                  } catch {
                    failed();
                    return [];
                  }
                  return selected;
                },
              },
            },
          },
          session.fetch,
        );
        if (!closed) attach(layer);
      } catch {
        fail(reason);
        throw new ModeFailure(reason);
      }
    },
  };
}
