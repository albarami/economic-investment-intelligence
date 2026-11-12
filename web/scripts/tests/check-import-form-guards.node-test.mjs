import assert from 'node:assert/strict';
import test from 'node:test';
import { collectReferences } from '../import-tokenizer.mjs';

const KEPT = './kept.js';

function found(text) {
  const result = collectReferences(text);
  return {
    references: result.references.map(
      (item) => `${item.form} ${item.specifier}`,
    ),
    nonLiteral: result.nonLiteral.map((item) => item.form),
  };
}

test('import forms keep their lookaheads', () => {
  const absent = [
    `import.other.glob("${KEPT}")`,
    `import.meta,glob("${KEPT}")`,
    `import.meta.other("${KEPT}")`,
    `import.meta.glob["${KEPT}"]`,
    `import.meta.glob(name, "${KEPT}")`,
    `require, "${KEPT}"`,
    `new URL, "${KEPT}"`,
    'import.',
    'import.meta.glob',
  ];
  for (const text of absent) {
    assert.deepEqual(found(text), { references: [], nonLiteral: [] }, text);
  }
  assert.deepEqual(found(`import.meta.glob("${KEPT}")`), {
    references: [`glob ${KEPT}`],
    nonLiteral: [],
  });
  assert.deepEqual(found(`require("${KEPT}")`), {
    references: [`require() ${KEPT}`],
    nonLiteral: [],
  });
  assert.deepEqual(found(`new URL("${KEPT}")`), {
    references: [`new URL() ${KEPT}`],
    nonLiteral: [],
  });
});
