import { createHash } from 'node:crypto';
import path from 'node:path';

// Exact installed identities: N1 and S3-T16 Part P qualification.
export const replacements = [
  {
    path: '@loaders.gl/tiles/dist/tileset/tileset-3d.js',
    sha256: '62cd2d50e333aae7726491b994492be5ec7659f5d36f7125b129a7529aaab559',
    kind: 'log',
  },
  {
    path: '@loaders.gl/draco/dist/lib/draco-module-loader.js',
    sha256: '22a9a7be411d921c49a24caae8185d3afe8440d05e6c3f4ecdff01c4b022aa9b',
    kind: 'draco',
  },
  {
    path: '@loaders.gl/worker-utils/dist/lib/worker-api/get-worker-url.js',
    sha256: '22395c55fcfb7df1c6eec77485b3f13e6d74149c039351024ca3d03041f6c80e',
    kind: 'worker',
  },
  {
    path: '@loaders.gl/worker-utils/dist/lib/library-utils/library-utils.js',
    sha256: 'fcdf9152108459269d60a8834b12e84fe02a3ce65742f770238efd1d4a959115',
    kind: 'library',
  },
  {
    path: '@luma.gl/gltf/node_modules/@loaders.gl/draco/dist/lib/draco-module-loader.js',
    sha256: 'f64915b3a2a58db176f4f78046cab1ebd6d852612b84c87c887045a191946599',
    kind: 'draco',
  },
  {
    path: '@luma.gl/gltf/node_modules/@loaders.gl/worker-utils/dist/lib/worker-api/get-worker-url.js',
    sha256: '4ad48a10614714aad827cf3784d575b089b205f75a2390eef977b25a20a16efd',
    kind: 'worker',
  },
  {
    path: '@luma.gl/gltf/node_modules/@loaders.gl/worker-utils/dist/lib/library-utils/library-utils.js',
    sha256: '29637121abba2837ce9e2d6b8eefb9b885507c4dbbbce7a3a904bcb602b8dfe6',
    kind: 'library',
  },
  {
    path: '@luma.gl/shadertools/dist/modules/lighting/pbr-material/pbr-material-glsl.js',
    sha256: '4334190e33ab9b6f1e9b4a40cf0cff699db4bfe9f8bd7d30988c6eea4e8e6044',
    kind: 'comment',
  },
  {
    path: '@luma.gl/shadertools/dist/modules/lighting/pbr-material/pbr-material-wgsl.js',
    sha256: '4c6fd72c1f53474fb4b85219ffa1c79917d57482b6914bf3f3a49c344bbc5271',
    kind: 'comment',
  },
  {
    path: '@luma.gl/shadertools/dist/lib/shader-assembly/shader-plugin-varyings.js',
    sha256: 'f633660aba43914f107b34ba7012401ae826a4887373dc29a9025e10be5ea210',
    kind: 'boundary',
  },
];
export const assets = [
  {
    path: '@loaders.gl/draco/dist/libs/draco_wasm_wrapper.js',
    sha256: 'b93f6384147828f857456c84845f4dbceada5b7a8455991109c853e236a1f018',
  },
  {
    path: '@loaders.gl/draco/dist/libs/draco_decoder.wasm',
    sha256: '0103c8bff79532c2f1a496dd9ea0764ac692ed8585d9136596ef9f043873a61f',
  },
];
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');
export function verifyAssets(read) {
  for (const row of assets) {
    const messageKey = 'unqualified-asset:' + path.basename(row.path);
    const refused = () =>
      Object.assign(new Error(messageKey), {
        code: 'unqualified-asset',
        message_key: messageKey,
      });
    let bytes;
    try {
      bytes = read(row.path);
    } catch {
      throw refused();
    }
    if (digest(bytes) !== row.sha256) throw refused();
  }
}
export function assertQualifiedImport(code, id, webRoot = process.cwd()) {
  if (
    id.startsWith(path.resolve(webRoot, 'src') + path.sep) &&
    /\.[cm]?[jt]sx?$/.test(id) &&
    !id.endsWith('/stage/photoreal-loader.ts') &&
    /Tile3DLayer|Tiles3DLoader|@loaders\.gl|draco|basis_transcoder/.test(code)
  )
    throw new Error('unqualified-photoreal-import');
}
export function transformDependency(
  code,
  id,
  webRoot = process.cwd(),
  matched = new Set(),
) {
  assertQualifiedImport(code, id, webRoot);
  const row = [...replacements]
    .sort((a, b) => b.path.length - a.path.length)
    .find((entry) => id.endsWith('/node_modules/' + entry.path));
  if (!row) return null;
  if (digest(code) !== row.sha256) throw new Error('unqualified-dependency');
  matched.add(row.path);
  switch (row.kind) {
    case 'log':
      return code.replace(
        /console\.error\(`A 3D tile failed to load:[^`]+`\);/,
        "console.error('photoreal unavailable');",
      );
    case 'draco':
      return code
        .replace(
          /const STATIC_DECODER_URL = `[^`]+`;/,
          "const STATIC_DECODER_URL = '/unsupported-photoreal-codec';",
        )
        .replace(
          /(\[DRACO_EXTERNAL_LIBRARIES.ENCODER\]: )`[^`]+`/,
          "$1'/unsupported-photoreal-codec/draco_encoder.js'",
        );
    case 'worker':
      // No loader worker is qualified. MapLibre's worker is a separate package.
      return `// loaders.gl; SPDX-License-Identifier: MIT; Copyright vis.gl contributors
export function getWorkerName() { return 'disabled-loader-worker'; }
export function getWorkerURL() { throw new Error('photoreal-worker-disabled'); }
`;
    case 'library': {
      const start = code.indexOf('export function getLibraryUrl(');
      const end = code.indexOf('async function loadLibraryFromFile(', start);
      if (start < 0 || end < 0) throw new Error('unqualified-dependency');
      const loadersStart = code.indexOf(
        'async function loadAsArrayBuffer(',
        end,
      );
      const loadersEnd = code.indexOf(
        '/*\nasync function loadScriptFromFile(',
        loadersStart,
      );
      if (loadersStart < 0 || loadersEnd < 0)
        throw new Error('unqualified-dependency');
      return (
        code.slice(0, start) +
        String.raw`export function getLibraryUrl(library, moduleName, options = {}, libraryName = null) {
  const name = libraryName || library;
  const allowed = ['draco_wasm_wrapper.js', 'draco_decoder.wasm'];
  const url = options.modules?.[name];
  if (!allowed.includes(name) || typeof url !== 'string' || !/^\/assets\/[a-zA-Z0-9_.-]+$/.test(url)) {
    throw new Error('unqualified-decoder-location');
  }
  return url;
}
` +
        code.slice(end, loadersStart) +
        String.raw`async function qualifiedLibraryResponse(url) {
  if (typeof url !== 'string' || !/^\/assets\/[a-zA-Z0-9_.-]+$/.test(url)) throw new Error('unqualified-decoder-location');
  const response = await fetch(url, { cache: 'no-store', redirect: 'error' });
  if (!response.ok) throw new Error('unqualified-decoder-location');
  return response;
}
async function loadAsArrayBuffer(url) { return await (await qualifiedLibraryResponse(url)).arrayBuffer(); }
async function loadAsText(url) { return await (await qualifiedLibraryResponse(url)).text(); }
` +
        code.slice(loadersEnd)
      );
    }
    case 'comment':
      // Retain the reference's title; its address is inert shader comment text.
      return code.replace(
        /(Implementation from Lambert's Photometria) https:[^\n]+/,
        '$1',
      );
    case 'boundary':
      // Equivalent ASCII identifier boundary, without an address-shaped regexp token.
      return code.replace(
        '\\\\b${escapeRegExp(fragmentInput.name)}',
        '(?:^|[^A-Za-z0-9_])${escapeRegExp(fragmentInput.name)}',
      );
    default:
      throw new Error('unqualified-dependency');
  }
}

export function browserModules(bundle) {
  const modules = Object.values(bundle).flatMap((chunk) =>
    chunk.type === 'chunk' ? Object.keys(chunk.modules) : [],
  );
  if (modules.some((id) => /\/(?:texture-compressor|image-size)\//.test(id)))
    throw new Error('unqualified-browser-package');
  return [
    ...new Set(
      modules.map((id) =>
        id.includes('/node_modules/')
          ? id.slice(id.indexOf('/node_modules/') + 1)
          : id.includes('/web/')
            ? id.slice(id.lastIndexOf('/web/') + 5)
            : 'bundler-runtime',
      ),
    ),
  ].sort();
}

export function verifyReplacements(matched) {
  if (replacements.some((row) => !matched.has(row.path)))
    throw new Error('unqualified-dependency');
}
