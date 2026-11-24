import assert from 'node:assert/strict';
import fs from 'node:fs';
import { before, test } from 'node:test';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  transformDependency,
  replacements,
  verifyAssets,
  browserModules,
  assertQualifiedImport,
  assets,
} from '../photoreal-assets.mjs';

const webRoot = fileURLToPath(new URL('../..', import.meta.url));
// Keep the Node test runner dependency-free; Vite runs in an isolated child.
// Its returned asset output crosses as JSON, never through shared web/dist.
function currentBuild(renamedPath = '') {
  const result = spawnSync(
    process.execPath,
    [
      '--input-type=module',
      '--eval',
      String.raw`
        import { build, loadConfigFromFile } from 'vite';
        import path from 'node:path';
        const [root, renamedPath] = process.argv.slice(1);
        let renamed = false;
        let config = {};
        if (renamedPath) {
          const loaded = await loadConfigFromFile(
            { command: 'build', mode: 'production' },
            path.join(root, 'vite.config.ts'),
          );
          config = loaded.config;
          const plugin = config.plugins.find(
            (item) => item.name === 'qualified-photoreal-assets',
          );
          const transform = plugin.transform;
          plugin.transform = function (code, id) {
            if (id.endsWith('/node_modules/' + renamedPath)) {
              renamed = true;
              id += '.invented-renamed';
            }
            return transform.call(this, code, id);
          };
        }
        try {
          const result = await build({
            ...config,
            root,
            configFile: renamedPath ? false : path.join(root, 'vite.config.ts'),
            envFile: false,
            build: { write: false },
            logLevel: 'silent',
          });
          process.stdout.write(JSON.stringify({
            renamed,
            output: result.output.map((item) => ({
              fileName: item.fileName,
              source: item.fileName === 'photoreal-modules.json' ? item.source : null,
            })),
          }));
        } catch (error) {
          if (!renamedPath) throw error;
          process.stdout.write(JSON.stringify({ renamed, error: error.message }));
        }
      `,
      webRoot,
      renamedPath,
    ],
    {
      cwd: webRoot,
      encoding: 'utf8',
      env: {
        PATH: process.env.PATH ?? '',
        TMPDIR: process.env.TMPDIR ?? '',
      },
    },
  );
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}
let output;
before(() => {
  output = currentBuild().output;
});

test('qualified dependency transforms reject a changed upstream byte', () => {
  for (const row of replacements) {
    const source = fs.readFileSync(
      new URL(`../../node_modules/${row.path}`, import.meta.url),
      'utf8',
    );
    assert.notEqual(
      transformDependency(source, `/node_modules/${row.path}`),
      source,
    );
    assert.throws(
      () => transformDependency(source + '\n', `/node_modules/${row.path}`),
      /unqualified-dependency/,
    );
  }
});
test('decoder manifest rejects a missing wasm and changed bytes', () => {
  const read = (relative) =>
    fs.readFileSync(new URL(`../../node_modules/${relative}`, import.meta.url));
  assert.doesNotThrow(() => verifyAssets(read));
  assert.throws(
    () =>
      verifyAssets((relative) =>
        relative.endsWith('.wasm') ? Buffer.from('invented') : read(relative),
      ),
    /unqualified-asset/,
  );
  assert.throws(
    () =>
      verifyAssets(() => {
        throw new Error('invented-missing');
      }),
    /invented-missing/,
  );
});

test('both loader worker implementations refuse construction paths', async () => {
  for (const row of replacements.filter((entry) => entry.kind === 'worker')) {
    const source = fs.readFileSync(
      new URL(`../../node_modules/${row.path}`, import.meta.url),
      'utf8',
    );
    const changed = transformDependency(source, `/node_modules/${row.path}`);
    const module = await import(
      `data:text/javascript,${encodeURIComponent(changed)}`
    );
    assert.throws(
      () => module.getWorkerURL({ id: 'draco' }, { worker: true }),
      /photoreal-worker-disabled/,
    );
  }
});

test('library URLs require a qualified module override', () => {
  for (const row of replacements.filter((entry) => entry.kind === 'library')) {
    const source = fs.readFileSync(
      new URL(`../../node_modules/${row.path}`, import.meta.url),
      'utf8',
    );
    const changed = transformDependency(source, `/node_modules/${row.path}`);
    const start = changed.indexOf('export function getLibraryUrl(');
    const end = changed.indexOf('async function loadLibraryFromFile(', start);
    const getUrl = new Function(
      changed.slice(start, end).replace('export ', '') +
        '; return getLibraryUrl;',
    )();
    assert.throws(
      () => getUrl('draco_decoder.wasm', 'draco', {}),
      /unqualified-decoder-location/,
    );
    assert.throws(
      () =>
        getUrl('unknown', 'draco', {
          modules: { unknown: '/assets/test.wasm' },
        }),
      /unqualified-decoder-location/,
    );
    assert.equal(
      getUrl('draco_decoder.wasm', 'draco', {
        modules: { 'draco_decoder.wasm': '/assets/invented.wasm' },
      }),
      '/assets/invented.wasm',
    );
  }
});

test('tile failure logging never exposes the URL or upstream payload', () => {
  const relative = '@loaders.gl/tiles/dist/tileset/tileset-3d.js';
  const source = fs.readFileSync(
    new URL(`../../node_modules/${relative}`, import.meta.url),
    'utf8',
  );
  const changed =
    transformDependency(source, `/node_modules/${relative}`) ?? source;
  assert.equal(
    /console\.error\(`A 3D tile failed to load:/.test(changed),
    false,
  );
});

test('built browser closure excludes command-line texture packages', () => {
  const manifest = JSON.parse(
    output.find((item) => item.fileName === 'photoreal-modules.json').source,
  );
  assert.equal(
    manifest.some((id) => /texture-compressor|image-size/.test(id)),
    false,
  );
});

test('planted command-line dependency fails bundle qualification', () => {
  for (const name of ['texture-compressor', 'image-size'])
    assert.throws(
      () =>
        browserModules({
          chunk: {
            type: 'chunk',
            modules: { ['/node_modules/' + name + '/index.js']: {} },
          },
        }),
      /unqualified-browser-package/,
    );
});

test('actual upstream tile-error method sends no URL or payload to console', () => {
  const relative = '@loaders.gl/tiles/dist/tileset/tileset-3d.js';
  const source = fs.readFileSync(
    new URL(`../../node_modules/${relative}`, import.meta.url),
    'utf8',
  );
  const changed = transformDependency(source, `/node_modules/${relative}`);
  const start = changed.indexOf('    _onTileLoadError(tile, error) {');
  const end = changed.indexOf('    _onTileLoad(tile, loaded) {', start);
  const messages = [];
  const sink = { error: (...args) => messages.push(args.join(' ')) };
  const method = changed
    .slice(start, end)
    .replace('_onTileLoadError(tile, error)', 'function handler(tile, error)');
  const handler = new Function(
    'console',
    'TILES_LOAD_FAILED',
    method + '; return handler;',
  )(sink, 'invented');
  handler.call(
    {
      stats: { get: () => ({ incrementCount() {} }) },
      options: { onTileError() {} },
    },
    { url: '/api/photoreal/3dtiles/invented.glb' },
    new Error('SYN-payload'),
  );
  assert.equal(
    messages.some(
      (x) => x.includes('/api/photoreal/') || x.includes('SYN-payload'),
    ),
    false,
  );
});

test('both library implementations fetch decoder bytes without caching or redirects', async (t) => {
  for (const row of replacements.filter((entry) => entry.kind === 'library')) {
    const source = fs.readFileSync(
      new URL(`../../node_modules/${row.path}`, import.meta.url),
      'utf8',
    );
    const changed = transformDependency(source, `/node_modules/${row.path}`);
    // Execute the whole transformed module with its environment imports injected.
    const module = new Function(
      'isBrowser',
      'isWorker',
      'assert',
      'VERSION',
      changed.replace(/^import .*;$/gm, '').replace(/^export /gm, '') +
        '\n; return { loadAsArrayBuffer, loadAsText };',
    )(true, false, assert, 'invented');
    for (const load of Object.values(module)) {
      const fetcher = t.mock.method(
        globalThis,
        'fetch',
        async () => new Response('invented'),
      );
      await load('/assets/invented.wasm');
      assert.deepEqual(fetcher.mock.calls[0].arguments, [
        '/assets/invented.wasm',
        { cache: 'no-store', redirect: 'error' },
      ]);
      fetcher.mock.mockImplementation(
        async () => new Response('invented', { status: 404 }),
      );
      await assert.rejects(
        load('/assets/invented.wasm'),
        /unqualified-decoder-location/,
      );
      for (const url of [
        '/outside/invented.wasm',
        '//foreign.invalid/a.wasm',
        '/assets/a.wasm?extra=yes',
        '/assets/../a.wasm',
      ])
        await assert.rejects(load(url), /unqualified-decoder-location/);
      assert.equal(fetcher.mock.callCount(), 2);
      fetcher.mock.restore();
    }
  }
});

test('checkout directories named src do not turn dependencies into application source', () => {
  const webRoot = path.resolve('invented/src/worktree/web');
  assert.doesNotThrow(() =>
    assertQualifiedImport(
      'draco',
      path.join(webRoot, 'node_modules/invented/index.js'),
      webRoot,
    ),
  );
  assert.throws(
    () =>
      assertQualifiedImport(
        'draco',
        path.join(webRoot, 'src/stage/plant.ts'),
        webRoot,
      ),
    /unqualified-photoreal-import/,
  );
  assert.doesNotThrow(() =>
    assertQualifiedImport(
      'draco',
      path.join(webRoot, 'src-neighbour/plant.ts'),
      webRoot,
    ),
  );
});

test('unqualified Basis executable assets and overrides are absent', () => {
  assert.equal(
    assets.some((row) => /basis/i.test(row.path)),
    false,
  );
  const webRoot = fileURLToPath(new URL('../..', import.meta.url));
  const loader = fs.readFileSync(
    path.join(webRoot, 'src/stage/photoreal-loader.ts'),
    'utf8',
  );
  assert.equal(/basis_transcoder/.test(loader), false);
  assert.equal(
    output.some((item) =>
      /basis_transcoder|BASIS-(LICENSE|NOTICE)/.test(item.fileName),
    ),
    false,
  );
  for (const row of replacements.filter((entry) => entry.kind === 'library')) {
    const source = fs.readFileSync(
      path.join(webRoot, 'node_modules', row.path),
      'utf8',
    );
    const changed = transformDependency(source, `/node_modules/${row.path}`);
    const getUrl = new Function(
      changed
        .slice(
          changed.indexOf('export function getLibraryUrl('),
          changed.indexOf('async function loadLibraryFromFile('),
        )
        .replace('export ', '') + '; return getLibraryUrl;',
    )();
    for (const name of ['basis_transcoder.js', 'basis_transcoder.wasm'])
      assert.throws(
        () =>
          getUrl(name, 'invented', {
            modules: { [name]: '/assets/invented.wasm' },
          }),
        /unqualified-decoder-location/,
      );
  }
});

test('a renamed replacement module path fails the current build', () => {
  const row = replacements.find((entry) => entry.kind === 'worker');
  const result = currentBuild(row.path);
  assert.match(result.error, /unqualified-dependency/);
  assert.equal(result.renamed, true);
});
