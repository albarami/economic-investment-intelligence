import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { collectReferences } from '../import-tokenizer.mjs';

function violations(source) {
  const { references } = collectReferences(source);
  return references.some((ref) =>
    /(?:^|[/])(?:tests|fixtures)(?:[/]|$)|public-route-registry/.test(
      ref.specifier,
    ),
  )
    ? ['fixture_provenance']
    : [];
}
test('mounted source dependency path rejects fixture registry imports', () => {
  assert.deepEqual(
    violations(
      "import {routeRegistry} from '../../tests/fixtures/public-route-registry';",
    ),
    ['fixture_provenance'],
  );
});
test('production source graph contains no fixture provenance', () => {
  const root = path.resolve('src');
  function walk(folder) {
    for (const item of fs.readdirSync(folder, { withFileTypes: true })) {
      const name = path.join(folder, item.name);
      if (item.isDirectory()) walk(name);
      else if (/\.(ts|tsx)$/.test(name))
        assert.deepEqual(
          violations(fs.readFileSync(name, 'utf8')),
          [],
          path.relative(root, name),
        );
    }
  }
  walk(root);
});
