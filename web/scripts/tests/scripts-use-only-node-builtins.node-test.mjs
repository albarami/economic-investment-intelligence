import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { collectReferences, tokenize } from '../import-tokenizer.mjs';

const root = fs.mkdtempSync(
  path.join(os.tmpdir(), 'eii-test-scripts-use-only-node-builtins-'),
);
after(() => fs.rmSync(root, { recursive: true, force: true }));

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCRIPTS = path.resolve(HERE, '..');
const IMP = 'imp' + 'ort';
const REQ = 'req' + 'uire';
const FROM = 'fr' + 'om';
const SPAWN_NAMES = [
  'spawn',
  'spawnSync',
  'execSync',
  'execFile',
  'execFileSync',
  'fork',
  'exec',
];
const REQUIRED_SPAWN_NAMES = [
  'spawn',
  'spawnSync',
  'execSync',
  'execFile',
  'execFileSync',
  'fork',
  'exec',
];

function scriptFiles() {
  return fs
    .readdirSync(SCRIPTS)
    .filter((name) => name.endsWith('.mjs'))
    .map((name) => path.join(SCRIPTS, name));
}

function testFiles() {
  return fs
    .readdirSync(HERE)
    .filter((name) => name.endsWith('.node-test.mjs'))
    .map((name) => path.join(HERE, name));
}

function wholeEnvAt(tokens, index) {
  const dot = tokens[index + 1];
  const env = tokens[index + 2];
  const after = tokens[index + 3];
  if (!dot || dot.type !== 'punct' || dot.value !== '.') return false;
  if (!env || env.type !== 'word' || env.value !== 'env') return false;
  if (
    after &&
    after.type === 'punct' &&
    (after.value === '.' || after.value === '[')
  )
    return false;
  return true;
}

function calleeBefore(tokens, parenIndex) {
  const word = tokens[parenIndex - 1];
  return word && word.type === 'word' ? word.value : '';
}

function envViolations(text) {
  const tokens = tokenize(text);
  const hits = [];
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (
      token.type !== 'word' ||
      token.value !== 'process' ||
      !wholeEnvAt(tokens, index)
    )
      continue;
    const before = tokens[index - 1];
    const before2 = tokens[index - 2];
    const after = tokens[index + 3];
    if (
      before2 &&
      before2.type === 'word' &&
      before2.value === 'env' &&
      before &&
      before.value === ':'
    ) {
      hits.push('env-value');
    }
    const dots = [tokens[index - 1], tokens[index - 2], tokens[index - 3]];
    if (
      dots.every((item) => item && item.type === 'punct' && item.value === '.')
    )
      hits.push('spread');
    const callNames = new Set(['assign', 'stringify', ...SPAWN_NAMES]);
    if (
      before &&
      (before.value === '(' || before.value === ',') &&
      after &&
      (after.value === ',' || after.value === ')')
    ) {
      let depth = 0;
      let paren = -1;
      for (let cursor = index; cursor >= 0; cursor -= 1) {
        const item = tokens[cursor];
        if (item.type === 'punct' && item.value === ')') depth += 1;
        if (item.type === 'punct' && item.value === '(') {
          if (depth === 0) {
            paren = cursor;
            break;
          }
          depth -= 1;
        }
      }
      if (paren !== -1 && callNames.has(calleeBefore(tokens, paren)))
        hits.push('argument');
    }
  }
  return hits;
}

function spawnViolations(text) {
  const tokens = tokenize(text);
  const hits = [];
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (token.type !== 'word' || !SPAWN_NAMES.includes(token.value)) continue;
    const previous = tokens[index - 1];
    if (previous && previous.type === 'punct' && previous.value === '.')
      continue;
    const open = tokens[index + 1];
    if (!open || open.value !== '(') continue;
    let depth = 0;
    let hasEnv = false;
    for (let cursor = index + 1; cursor < tokens.length; cursor += 1) {
      const item = tokens[cursor];
      if (item.type === 'punct' && item.value === '(') depth += 1;
      else if (item.type === 'punct' && item.value === ')') {
        depth -= 1;
        if (depth === 0) break;
      } else if (item.type === 'word' && item.value === 'env') {
        const next = tokens[cursor + 1];
        if (
          next &&
          (next.value === ':' || next.value === ',' || next.value === '}')
        )
          hasEnv = true;
      }
    }
    if (!hasEnv) hits.push(token.value);
  }
  return hits;
}

function markerPattern() {
  const skip = 'sk' + 'ip';
  const todo = 'to' + 'do';
  const only = 'on' + 'ly';
  return new RegExp(
    `\\b(?:${skip}|${todo}|${only})['"]?\\s*:|\\.(?:${skip}|${todo}|${only})\\s*\\(`,
  );
}

function importViolations(text) {
  const { references } = collectReferences(text);
  return references.filter(
    (item) =>
      !item.specifier.startsWith('node:') && !item.specifier.startsWith('.'),
  );
}

test('imports', () => {
  const found = [...scriptFiles(), ...testFiles()];
  assert.ok(found.length > 0);
  for (const file of found) {
    const bad = importViolations(fs.readFileSync(file, 'utf8'));
    assert.deepEqual(bad, [], file);
  }
  const samples = [
    `${IMP} x ${FROM} 'left-pad';\n`,
    `const a = 1; ${IMP} x ${FROM} 'left-pad';\n`,
    `${IMP} {\n  x\n} ${FROM} 'left-pad';\n`,
    `${IMP}('left-pad');\n`,
    `${REQ}('left-pad');\n`,
  ];
  for (const sample of samples)
    assert.ok(importViolations(sample).length > 0, sample);
  assert.deepEqual(importViolations("import fs from 'node:fs';\n"), []);
});

test('process env', () => {
  for (const file of [...scriptFiles(), ...testFiles()]) {
    assert.deepEqual(envViolations(fs.readFileSync(file, 'utf8')), [], file);
  }
  const proc = 'process' + '.env';
  const bad = [
    `{ env: ${proc} }`,
    `{ ...${proc} }`,
    `Object.assign({}, ${proc})`,
    `Object.assign(${proc}, x)`,
    `JSON.stringify(${proc})`,
    `spawn(${proc})`,
  ];
  for (const sample of bad) assert.ok(envViolations(sample).length > 0, sample);
  const good = [
    'Object.assign({}, { PATH: process.env.PATH })',
    "Object.assign({}, process.env['PATH'])",
    '{ env: { PATH: process.env.PATH } }',
    'const { PATH } = process.env;',
  ];
  for (const sample of good)
    assert.deepEqual(envViolations(sample), [], sample);
});

test('spawn name list is complete', () => {
  assert.deepEqual([...SPAWN_NAMES].sort(), [...REQUIRED_SPAWN_NAMES].sort());
});

test('spawn calls carry env', () => {
  for (const file of [...scriptFiles(), ...testFiles()]) {
    assert.deepEqual(spawnViolations(fs.readFileSync(file, 'utf8')), [], file);
  }
  for (const name of SPAWN_NAMES) {
    assert.ok(spawnViolations(`${name}('x')`).includes(name), name);
    assert.ok(
      spawnViolations(`${name}('x', { cwd: '.' })`).includes(name),
      name,
    );
  }
  assert.ok(spawnViolations("spawn('x', { note: 'env:' })").includes('spawn'));
  assert.deepEqual(spawnViolations("spawn('x', { env })"), []);
  assert.deepEqual(spawnViolations('x.exec(s)'), []);
});

test('skip markers', () => {
  const pattern = markerPattern();
  for (const file of testFiles()) {
    assert.equal(pattern.test(fs.readFileSync(file, 'utf8')), false, file);
  }
  const skip = 'sk' + 'ip';
  const todo = 'to' + 'do';
  const only = 'on' + 'ly';
  const shapes = [
    `{ ${skip}: true }`,
    `{ ${todo}: true }`,
    `{ ${only}: true }`,
    `it.${skip}(`,
    `test.${todo}(`,
    `describe.${only}(`,
    `{ '${skip}': true }`,
    `{ "${only}": true }`,
  ];
  for (const shape of shapes) assert.equal(pattern.test(shape), true, shape);
  assert.equal(pattern.test('const value = 1;\n'), false);
});

test('the helper is not blind', () => {
  assert.deepEqual(importViolations("import fs from 'node:fs';\n"), []);
  assert.deepEqual(envViolations('const path = process.env.PATH;\n'), []);
  assert.deepEqual(spawnViolations("spawn('x', { env: {} })"), []);
  assert.equal(markerPattern().test('const value = 1;\n'), false);
});
