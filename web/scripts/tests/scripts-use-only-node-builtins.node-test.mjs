import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { collectReferences, tokenize } from '../import-tokenizer.mjs';
import { nonLiteralModuleLoadViolations } from '../non-literal-module-load.mjs';

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

function scriptFiles(directory = SCRIPTS) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) return scriptFiles(file);
    return entry.name.endsWith('.mjs') ? [file] : [];
  });
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

// The two pinned dev-tooling parsers of check-local-fonts.mjs (ruling
// L-1531): the only bare package specifiers a script may import, matched
// exactly so a look-alike name or subpath still fails.
const ALLOWED_PACKAGE_IMPORTS = new Set(['css-tree', 'parse5']);

function importReason(item, file, scripts) {
  if (item.specifier.startsWith('node:')) return null;
  if (ALLOWED_PACKAGE_IMPORTS.has(item.specifier)) return null;
  if (!item.specifier.startsWith('.')) return 'non-node-import';
  // Resource URLs do not import modules; retain their existing checks.
  if (item.form === 'new URL()') return null;
  let target;
  try {
    target = fs.realpathSync(new URL(item.specifier, pathToFileURL(file)));
    if (!fs.statSync(target).isFile()) return 'relative-import-unresolved';
  } catch {
    return 'relative-import-unresolved';
  }
  const relative = path.relative(fs.realpathSync(scripts), target);
  if (
    relative === '..' ||
    relative.startsWith(`..${path.sep}`) ||
    path.isAbsolute(relative)
  )
    return 'relative-import-outside-scripts';
  return null;
}

function importViolations(
  text,
  file = fileURLToPath(import.meta.url),
  scripts = SCRIPTS,
) {
  const found = collectReferences(text);
  const fromReferences = found.references.flatMap((item) => {
    const reason = importReason(item, file, scripts);
    return reason ? [{ ...item, reason }] : [];
  });
  return fromReferences.concat(
    nonLiteralModuleLoadViolations(found.nonLiteral, file, scripts),
  );
}

test('imports', () => {
  const found = scriptFiles();
  assert.ok(found.length > 0);
  for (const file of found) {
    const bad = importViolations(fs.readFileSync(file, 'utf8'), file);
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
    assert.deepEqual(
      importViolations(sample).map((item) => item.reason),
      ['non-node-import'],
      sample,
    );
  assert.deepEqual(importViolations("import fs from 'node:fs';\n"), []);
});

test('only the two pinned parser packages import by name', () => {
  for (const name of ['parse5', 'css-tree']) {
    assert.deepEqual(
      importViolations(`${IMP} { x } ${FROM} '${name}';\n`),
      [],
      name,
    );
  }
  for (const specifier of [
    'parse5/subpath',
    'css-tree2',
    'PARSE5',
    'postcss',
    '#parse5',
  ]) {
    assert.deepEqual(
      importViolations(`${IMP} { x } ${FROM} '${specifier}';\n`).map(
        (item) => item.reason,
      ),
      ['non-node-import'],
      specifier,
    );
  }
});

// These fixtures differ only in the module specifier; all target modules exist.
const FIXTURE_SCRIPTS = path.join(root, 'web/scripts');
const FIXTURE_IMPORTERS = ['entry.mjs', 'tests/entry.node-test.mjs'];
for (const name of ['scripts/tests', 'scripts/nested', 'scripts-peer', 'tests'])
  fs.mkdirSync(path.join(root, 'web', name), { recursive: true });
for (const name of [
  'scripts/kept.mjs',
  'scripts-peer/kept.mjs',
  'tests/kept.mjs',
])
  fs.writeFileSync(path.join(root, 'web', name), 'export {};\n');
fs.symlinkSync('../tests/kept.mjs', path.join(FIXTURE_SCRIPTS, 'escape.mjs'));

function moduleForms(specifier) {
  const quoted = JSON.stringify(specifier);
  return [
    `${IMP} x ${FROM} ${quoted};`,
    `${IMP} ${quoted};`,
    `export { x } ${FROM} ${quoted};`,
    `export * ${FROM} ${quoted};`,
    `${IMP}(${quoted});`,
    `${REQ}(${quoted});`,
  ];
}

function importReasons(source, file) {
  return importViolations(source, file, FIXTURE_SCRIPTS).map(
    (item) => item.reason,
  );
}

test('relative module imports stay inside scripts from scripts and tests', () => {
  for (const importer of FIXTURE_IMPORTERS) {
    const file = path.join(FIXTURE_SCRIPTS, importer);
    const prefix = importer.startsWith('tests/') ? '../' : './';
    for (const source of moduleForms(`${prefix}kept.mjs`))
      assert.deepEqual(importReasons(source, file), []);
    for (const target of [
      '../tests/kept.mjs',
      '../scripts-peer/kept.mjs',
      '../tests/kept.mjs?fixture#module',
      '../%74ests/kept.mjs',
      'escape.mjs',
    ]) {
      for (const source of moduleForms(`${prefix}${target}`))
        assert.deepEqual(importReasons(source, file), [
          'relative-import-outside-scripts',
        ]);
    }
  }
});

test('relative module imports must resolve to files', () => {
  const file = path.join(FIXTURE_SCRIPTS, 'entry.mjs');
  for (const specifier of ['./absent.mjs', './nested/', './%2fkept.mjs']) {
    for (const source of moduleForms(specifier))
      assert.deepEqual(importReasons(source, file), [
        'relative-import-unresolved',
      ]);
  }
});

const NON_LITERAL_MODULE_LOAD = 'non-literal-module-load';
const NEW_URL_IMPORT =
  "import(new URL('../tests/credit-place/credit-place-dom.mjs', import.meta.url));\n";

function loadReasons(source, file = path.join(FIXTURE_SCRIPTS, 'entry.mjs')) {
  return importViolations(source, file, FIXTURE_SCRIPTS).map(
    (item) => item.reason,
  );
}

test('import(new URL) is a non-literal module load', () => {
  assert.deepEqual(loadReasons(NEW_URL_IMPORT), [NON_LITERAL_MODULE_LOAD]);
  assert.deepEqual(
    importViolations(
      NEW_URL_IMPORT,
      path.join(SCRIPTS, 'tests/check-dev-server.node-test.mjs'),
      SCRIPTS,
    ).map((item) => item.reason),
    [NON_LITERAL_MODULE_LOAD],
  );
});

test('a non-literal require is a non-literal module load', () => {
  assert.deepEqual(loadReasons('require(name);\n'), [NON_LITERAL_MODULE_LOAD]);
  assert.deepEqual(
    importViolations(
      'require(name);\n',
      path.join(SCRIPTS, 'tests/photoreal-assets.node-test.mjs'),
      SCRIPTS,
    ).map((item) => item.reason),
    [NON_LITERAL_MODULE_LOAD],
  );
});

test('a substituted import template is a non-literal module load', () => {
  const devTemplate =
    'import(`${pathToFileURL(SCRIPT).href}?timed=${t.name}`);\n';
  const otherTemplate =
    'import(`${pathToFileURL(SCRIPT).href}?other=${t.name}`);\n';
  const devFile = path.join(SCRIPTS, 'tests/check-dev-server.node-test.mjs');
  assert.deepEqual(loadReasons('import(`${name}`);\n'), [
    NON_LITERAL_MODULE_LOAD,
  ]);
  assert.deepEqual(
    importViolations(devTemplate, path.join(SCRIPTS, 'entry.mjs'), SCRIPTS).map(
      (item) => item.reason,
    ),
    [NON_LITERAL_MODULE_LOAD],
  );
  assert.deepEqual(
    importViolations(otherTemplate, devFile, SCRIPTS).map(
      (item) => item.reason,
    ),
    [NON_LITERAL_MODULE_LOAD],
  );
  assert.deepEqual(importViolations(devTemplate, devFile, SCRIPTS), []);
  const photo =
    'import(`data:text/javascript,${encodeURIComponent(changed)}`);\n';
  const photoFile = path.join(SCRIPTS, 'tests/photoreal-assets.node-test.mjs');
  assert.deepEqual(importViolations(photo, photoFile, SCRIPTS), []);
  assert.deepEqual(
    importViolations(photo, devFile, SCRIPTS).map((item) => item.reason),
    [NON_LITERAL_MODULE_LOAD],
  );
});

test('non-literal module-load shapes keep their reason', () => {
  const file = path.join(FIXTURE_SCRIPTS, 'entry.mjs');
  const refused = [
    NEW_URL_IMPORT,
    "import(\nnew URL('../tests/credit-place/credit-place-dom.mjs', import.meta.url)\n);\n",
    'import(`${name}`);\n',
    'require(name);\n',
    'require(new URL("../tests/a.mjs", import.meta.url));\n',
    'import();\n',
    'import(new URL(`../tests/${name}.mjs`, import.meta.url));\n',
  ];
  const allowed = [
    '',
    "import('node:fs');\n",
    "import('./kept.mjs');\n",
    'import(`./kept.mjs`);\n',
    "new URL('../tests/kept.mjs');\n",
    'new URL(`../tests/${name}.mjs`);\n',
    "// import(new URL('../tests/a.mjs', import.meta.url));\n",
    'const text = "import(new URL(\'../tests/a.mjs\', import.meta.url))";\n',
  ];
  for (const source of allowed)
    assert.deepEqual(loadReasons(source, file), [], source);
  for (const source of refused)
    assert.deepEqual(
      loadReasons(source, file),
      [NON_LITERAL_MODULE_LOAD],
      source,
    );
  const doubled = `${NEW_URL_IMPORT}${NEW_URL_IMPORT}`;
  assert.deepEqual(loadReasons(doubled, file), [
    NON_LITERAL_MODULE_LOAD,
    NON_LITERAL_MODULE_LOAD,
  ]);
  assert.deepEqual(
    loadReasons(`require(name);\nimport(\`\${name}\`);\n`, file),
    [NON_LITERAL_MODULE_LOAD, NON_LITERAL_MODULE_LOAD],
  );
});

test('relative module resolution is invariant under neutral path segments', () => {
  let prefixes = ['./'];
  for (let depth = 0; depth < 4; depth += 1) {
    prefixes = prefixes.flatMap((prefix) => [
      `${prefix}./`,
      `${prefix}nested/../`,
    ]);
    for (const prefix of prefixes) {
      for (const [target, expected] of [
        ['kept.mjs', []],
        ['%6bept.mjs?fixture#module', []],
        ['../tests/kept.mjs', ['relative-import-outside-scripts']],
      ]) {
        const sources = moduleForms(`${prefix}${target}`);
        for (const source of sources)
          assert.deepEqual(
            importReasons(source, path.join(FIXTURE_SCRIPTS, 'entry.mjs')),
            expected,
          );
      }
    }
  }
});

test('process env', () => {
  for (const file of scriptFiles()) {
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
  for (const file of scriptFiles()) {
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
