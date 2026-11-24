/** Qualified import boundary. N1 assets and P1 hash-checked dependency transforms. */
import { Tile3DLayer, type Tile3DLayerProps } from '@deck.gl/geo-layers';
import { Tiles3DLoader } from '@loaders.gl/3d-tiles';
import dracoJS from '../../node_modules/@loaders.gl/draco/dist/libs/draco_wasm_wrapper.js?url';
import dracoWasm from '../../node_modules/@loaders.gl/draco/dist/libs/draco_decoder.wasm?url';

export const decoderAssets = Object.freeze([dracoJS, dracoWasm]);
const modules = Object.freeze({
  'draco_wasm_wrapper.js': dracoJS,
  'draco_decoder.wasm': dracoWasm,
});
const fail = () => new Error('photoreal unavailable');

export function visibleCredits(values: unknown[]): string {
  const counts = new Map<string, number>();
  for (const value of values) {
    if (
      typeof value !== 'string' ||
      !value.trim() ||
      [...value].some(
        (char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) === 127,
      )
    )
      throw fail();
    const entries = value
      .split(';')
      .map((x) => x.trim())
      .filter(Boolean);
    if (entries.length === 0) throw fail();
    for (const item of entries) counts.set(item, (counts.get(item) ?? 0) + 1);
  }
  return [...counts.keys()]
    .sort(
      (a, b) => counts.get(b)! - counts.get(a)! || (a < b ? -1 : a > b ? 1 : 0),
    )
    .join('; ');
}
export function validateGLB(data: ArrayBuffer): void {
  try {
    const view = new DataView(data);
    if (
      data.byteLength < 20 ||
      view.getUint32(0, true) !== 0x46546c67 ||
      view.getUint32(4, true) !== 2 ||
      view.getUint32(8, true) !== data.byteLength ||
      view.getUint32(16, true) !== 0x4e4f534a
    )
      throw fail();
    const size = view.getUint32(12, true);
    if (size % 4 || size > data.byteLength - 20) throw fail();
    // The decoder keeps the last JSON chunk: admit one JSON chunk,
    // followed by at most one binary chunk and nothing else.
    const rest = 20 + size;
    if (rest !== data.byteLength) {
      if (
        data.byteLength - rest < 8 ||
        view.getUint32(rest + 4, true) !== 0x004e4942 ||
        rest + 8 + view.getUint32(rest, true) !== data.byteLength
      )
        throw fail();
    }
    const json = JSON.parse(
      new TextDecoder('utf-8', { fatal: true }).decode(
        new Uint8Array(data, 20, size),
      ),
    );
    if (json.asset?.version !== '2.0') throw fail();
    visibleCredits([json.asset.copyright]);
    for (const list of [
      json.extensionsUsed ?? [],
      json.extensionsRequired ?? [],
    ]) {
      if (
        !Array.isArray(list) ||
        list.some((x) => x !== 'KHR_draco_mesh_compression')
      )
        throw fail();
    }
    const visit = (value: unknown): void => {
      if (!value || typeof value !== 'object') return;
      for (const [key, child] of Object.entries(value)) {
        if (key === 'uri' || key === 'url') throw fail();
        if (
          key === 'extensions' &&
          (!child ||
            typeof child !== 'object' ||
            Object.keys(child).some((x) => x !== 'KHR_draco_mesh_compression'))
        )
          throw fail();
        visit(child);
      }
    };
    visit(json);
    // The browser chooses the image codec from bytes, regardless of its label.
    const binary = data.byteLength - rest - 8;
    const signature = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
    for (const image of json.images ?? []) {
      const part = json.bufferViews?.[image.bufferView];
      const offset = part?.byteOffset ?? 0;
      if (
        !Number.isInteger(image.bufferView) ||
        image.mimeType !== 'image/png' ||
        part?.buffer !== 0 ||
        !Number.isInteger(offset) ||
        offset < 0 ||
        !Number.isInteger(part.byteLength) ||
        part.byteLength < signature.length ||
        offset + part.byteLength > binary ||
        signature.some(
          (byte, index) => view.getUint8(rest + 8 + offset + index) !== byte,
        )
      )
        throw fail();
    }
  } catch {
    throw fail();
  }
}
export function qualifiedLayer(
  props: Tile3DLayerProps,
  fetchTile: typeof fetch,
) {
  const transport: typeof fetch = async (input, init) => {
    try {
      const response = await fetchTile(input, init);
      if (typeof input === 'string' && input.split('?')[0]?.endsWith('.glb'))
        validateGLB(await response.clone().arrayBuffer());
      return response;
    } catch {
      throw fail();
    }
  };
  const layer: Tile3DLayer = new Tile3DLayer({
    ...props,
    loader: Tiles3DLoader,
    loadOptions: {
      ...props.loadOptions,
      image: { type: 'imagebitmap' },
      worker: false,
      core: { worker: false, fetch: transport },
      fetch: transport,
      modules,
    },
    // A tile's sublayer does not inherit this layer's error callback. Route its
    // errors through it, without exposing the tile's address or content. A
    // sublayer can fail while the pinned layer manager updates its layers, and
    // that manager drops a layer list set before its update returns: raise
    // after the current step, so that the removal the callback issues is kept.
    _subLayerProps: {
      scenegraph: {
        onError: () => {
          queueMicrotask(() => layer.raiseError(fail(), ''));
          return true;
        },
      },
    },
  });
  // The pinned layer leaves its root-load promise unobserved. Route refusal
  // through the existing error callback without exposing decoder error text.
  const root = layer as unknown as {
    _loadTileset(url: string): Promise<void>;
  };
  const load = root._loadTileset;
  root._loadTileset = (url) =>
    load.call(layer, url).catch(() => layer.raiseError(fail(), ''));
  // The pinned layer also leaves its tile set's update promise unobserved, and
  // the pinned tile set runs its traversal inside a timer and leaves each tile
  // load's promise unobserved. Route all three the same way, once for each
  // tile set.
  const updates = layer as unknown as {
    state?: {
      tileset3d?: {
        selectTiles(viewports: unknown): Promise<number>;
        doUpdate(viewports: unknown): void;
        _onTileLoad(tile: unknown, loaded: unknown): void;
      };
    };
    _updateTileset(viewports: unknown): void;
  };
  const guarded = new WeakSet<object>();
  const update = updates._updateTileset;
  updates._updateTileset = (viewports) => {
    const tileset = updates.state?.tileset3d;
    if (tileset && !guarded.has(tileset)) {
      guarded.add(tileset);
      const select = tileset.selectTiles;
      tileset.selectTiles = (selected) =>
        select.call(tileset, selected).catch(() => {
          layer.raiseError(fail(), '');
          return new Promise<number>(() => {});
        });
      const traverse = tileset.doUpdate;
      tileset.doUpdate = (selected) => {
        try {
          traverse.call(tileset, selected);
        } catch {
          layer.raiseError(fail(), '');
        }
      };
      const loaded = tileset._onTileLoad;
      tileset._onTileLoad = (tile, content) => {
        try {
          loaded.call(tileset, tile, content);
        } catch {
          layer.raiseError(fail(), '');
        }
      };
    }
    update.call(layer, viewports);
  };
  return layer;
}
