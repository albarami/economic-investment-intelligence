import { build } from 'vite';
import { gzipSync, brotliCompressSync, constants } from 'node:zlib';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
const hash = (file) =>
  createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const sourceFiles = [
  'measure-build.mjs',
  'contract.json',
  'fixtures/profiles.json',
  'main.tsx',
  'benchmark.tsx',
  'workload.ts',
  'guards.mjs',
  'adapters/echarts.tsx',
  'adapters/plot.tsx',
  'adapters/visx.tsx',
];
const sources = Object.fromEntries(
  sourceFiles.map((name) => [name, hash(`spikes/charts/${name}`)]),
);
const totals = {};
for (const name of ['empty', 'echarts', 'plot', 'visx']) {
  const result = await build({
    configFile: false,
    logLevel: 'silent',
    plugins: [
      {
        name: 'identical-chart-benchmark-shell',
        resolveId(id, importer) {
          if (
            id === 'chart-benchmark' ||
            id === path.resolve('chart-benchmark')
          )
            return '\0chart-benchmark';
          if (importer === '\0chart-benchmark' && id.startsWith('.'))
            return path.resolve('spikes/charts', id);
        },
        load(id) {
          if (id !== '\0chart-benchmark') return;
          const renderer =
            name === 'empty'
              ? 'const render = () => () => {};'
              : `import { render } from './adapters/${name}.tsx';`;
          return `import { mountBenchmark } from './benchmark.tsx'; ${renderer} export function mount(host,input) { return mountBenchmark(host,render,input); }`;
        },
      },
    ],
    build: {
      write: false,
      minify: true,
      lib: {
        entry: 'chart-benchmark',
        formats: ['es'],
        fileName: name,
      },
      rollupOptions: { external: [] },
    },
  });
  const outputs = Array.isArray(result)
    ? result.flatMap((r) => r.output)
    : result.output;
  const bytes = outputs.map((o) =>
    Buffer.from(o.type === 'chunk' ? o.code : o.source),
  );
  totals[name] = {
    raw: bytes.reduce((n, b) => n + b.length, 0),
    gzip: bytes.reduce((n, b) => n + gzipSync(b, { level: 9 }).length, 0),
    brotli: bytes.reduce(
      (n, b) =>
        n +
        brotliCompressSync(b, {
          params: { [constants.BROTLI_PARAM_QUALITY]: 11 },
        }).length,
      0,
    ),
  };
}
const baseline = totals.empty;
const deltas = Object.fromEntries(
  Object.entries(totals)
    .filter(([key]) => key !== 'empty')
    .map(([key, value]) => [
      key,
      Object.fromEntries(
        Object.entries(value).map(([kind, count]) => [
          kind,
          count - baseline[kind],
        ]),
      ),
    ]),
);
const report = {
  kind: 'offline-bundle-only',
  sources,
  environment: {
    node: process.version,
    platform: process.platform,
    architecture: process.arch,
  },
  settings: {
    mode: 'production',
    format: 'es',
    minify: true,
    gzipLevel: 9,
    brotliQuality: 11,
  },
  identity: {
    lock: hash('package-lock.json'),
    contract: hash('spikes/charts/contract.json'),
    fixture: hash('spikes/charts/fixtures/profiles.json'),
  },
  totals,
  deltas,
  parse: 'BLOCKED: native parse/compile attribution unavailable',
  memory: 'BLOCKED: full-story instrumentation unavailable',
};
fs.writeFileSync(
  'spikes/charts/evidence/bundle.json',
  JSON.stringify(report, null, 2) + '\n',
);
console.log(JSON.stringify(report));
