import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
function scan(
  file,
  read = (key) => fs.readFileSync(key, 'utf8'),
  seen = new Set(),
) {
  if (seen.has(file)) return;
  seen.add(file);
  assert.ok(!file.includes('/spikes/'), 'production-spike-import');
  const source = ts.createSourceFile(
    file,
    read(file),
    ts.ScriptTarget.Latest,
    true,
  );
  function visit(node) {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteral(node.moduleSpecifier)
    )
      follow(node.moduleSpecifier.text);
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword
    ) {
      assert.ok(
        node.arguments.length === 1 && ts.isStringLiteral(node.arguments[0]),
        'dynamic-import-not-literal',
      );
      follow(node.arguments[0].text);
    }
    ts.forEachChild(node, visit);
  }
  function follow(specifier) {
    assert.ok(!specifier.includes('spikes/'), 'production-spike-import');
    if (!specifier.startsWith('.')) return;
    const base = path.resolve(path.dirname(file), specifier);
    const next = [
      base,
      `${base}.ts`,
      `${base}.tsx`,
      `${base}/index.ts`,
      `${base}/index.tsx`,
    ].find((p) => fs.existsSync(p) && fs.statSync(p).isFile());
    if (next && /\.[jt]sx?$/.test(next)) scan(next, read, seen);
  }
  visit(source);
}
test('actual product import graph excludes all spikes', () =>
  scan(path.resolve('src/main.tsx')));
for (const statement of [
  "import '../../spikes/charts/main.tsx';",
  "export * from '../../spikes/charts/main.tsx';",
  "import('../../spikes/charts/main.tsx');",
])
  test(`planted graph edge ${statement}`, () =>
    assert.throws(
      () => scan('src/plant.ts', () => statement),
      /production-spike-import/,
    ));
