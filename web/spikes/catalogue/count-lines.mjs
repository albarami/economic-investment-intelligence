import fs from 'node:fs';
import ts from 'typescript';

// Frozen before measurement. No generated fixture, vendor or documentation line is maintained runtime.
export const groups = Object.freeze({
  shared: [
    'native-dispatch.ts',
    'stream.ts',
    'repair.ts',
    'transport.ts',
    'wording.ts',
    'oracle.py',
    'network-guard.mjs',
  ],
  native: ['adapters/native.ts'],
  a2ui: ['adapters/a2ui.ts', 'adapters/a2ui-runtime.ts'],
  'json-render': ['adapters/json-render.ts'],
  'plain-events': ['adapters/plain-events.ts'],
  'ag-ui': ['adapters/ag-ui.ts'],
  harness: [
    'guards.mjs',
    'record.mjs',
    'verify-evidence.mjs',
    'count-lines.mjs',
    'fixture-builder.py',
    'main.tsx',
    'vite.config.ts',
    'tests/run.mjs',
  ],
  tests: ['scenarios.mjs', 'tests/helpers.mjs', 'tests/guards.node-test.mjs'],
  generated: [
    'fixtures/cases.json',
    'fixtures/manifest.json',
    'fixtures/paired-cases.json',
    'fixtures/paired-manifest.json',
    'fixtures/catalogue/claims.yaml',
    'fixtures/catalogue/components.yaml',
    'fixtures/catalogue/fragments.yaml',
    'fixtures/catalogue/questions.yaml',
    'fixtures/catalogue-paired/claims.yaml',
    'fixtures/catalogue-paired/components.yaml',
    'fixtures/catalogue-paired/fragments.yaml',
    'fixtures/catalogue-paired/questions.yaml',
  ],
  vendor: [],
});
export function countSource(source, file) {
  if (file.endsWith('.py') || file.endsWith('.yaml'))
    return source
      .split('\n')
      .filter((line) => line.trim() && !line.trim().startsWith('#')).length;
  const scanner = ts.createScanner(
    ts.ScriptTarget.Latest,
    true,
    ts.LanguageVariant.JSX,
    source,
  );
  const lines = new Set();
  while (scanner.scan() !== ts.SyntaxKind.EndOfFileToken) {
    const start = source.slice(0, scanner.getTokenPos()).split('\n').length;
    const end = source.slice(0, scanner.getTextPos()).split('\n').length;
    for (let line = start; line <= end; line += 1) lines.add(line);
  }
  return lines.size;
}
export function countLines() {
  return Object.fromEntries(
    Object.entries(groups).map(([group, files]) => [
      group,
      {
        files,
        maintained: !['generated', 'vendor'].includes(group),
        lines: files.reduce(
          (sum, file) =>
            sum +
            countSource(
              fs.readFileSync(new URL(file, import.meta.url), 'utf8'),
              file,
            ),
          0,
        ),
      },
    ]),
  );
}
