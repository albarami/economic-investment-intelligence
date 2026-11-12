import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SCRIPT = path.join(HERE, '..', 'check-import-boundary.mjs');
const IMP = 'imp' + 'ort';
const REQ = 'req' + 'uire';
const FROM = 'fr' + 'om';
const META = 'me' + 'ta';
const GLOB = 'gl' + 'ob';
const URLW = 'UR' + 'L';
const BT = String.fromCharCode(96);
const SPEC = '../../../core/x';
const STYLE_EXTENSIONS = ['.css', '.scss', '.sass', '.less', '.styl', '.pcss'];

function cleanEnv(extra) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-env-'));
  const base = { PATH: process.env.PATH, HOME: home, TMPDIR: home, LANG: 'C' };
  return { ...base, ...extra };
}

function run(root) {
  return spawnSync(process.execPath, [SCRIPT, '--root', root], {
    encoding: 'utf8',
    env: cleanEnv(),
  });
}

function makeRoot() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-form-'));
  fs.mkdirSync(path.join(root, 'src', 'app'), { recursive: true });
  fs.writeFileSync(
    path.join(root, 'tsconfig.json'),
    `${JSON.stringify({ include: ['src'] })}\n`,
  );
  return root;
}

function lineOf(text, needle) {
  const at = text.indexOf(needle);
  assert.notEqual(at, -1);
  return text.slice(0, at).split('\n').length;
}

function quoted(spec, quote) {
  return `${quote}${spec}${quote}`;
}

const cases = [];

function add(name, text, options = {}) {
  cases.push({
    name,
    text,
    file: options.file ?? 'src/app/case.ts',
    rule: options.rule === undefined ? 'outside-web' : options.rule,
    needle: options.needle === undefined ? SPEC : options.needle,
    form: options.form ?? null,
  });
}

function addQuoted(name, build, options) {
  for (const quote of ["'", '"']) {
    add(`${name} ${quote}`, build(quote), options);
  }
}

addQuoted('import from', (quote) => `${IMP} x ${FROM} ${quoted(SPEC, quote)};\n`);
addQuoted('import type from', (quote) => `${IMP} type { T } ${FROM} ${quoted(SPEC, quote)};\n`);
addQuoted('export from', (quote) => `export { y } ${FROM} ${quoted(SPEC, quote)};\n`);
addQuoted('export star from', (quote) => `export * ${FROM} ${quoted(SPEC, quote)};\n`);
addQuoted('export star as from', (quote) => `export * as n ${FROM} ${quoted(SPEC, quote)};\n`);
addQuoted('multiline from', (quote) => `${IMP} {\n  // don't\n  a\n} ${FROM} ${quoted(SPEC, quote)};\n`);
addQuoted('block comment from', (quote) => `${IMP} a /* don't */ ${FROM} ${quoted(SPEC, quote)};\n`);
addQuoted(
  'string binding from',
  (quote) => `${IMP} { 'a-b' as c } ${FROM} ${quoted(SPEC, quote)};\n`,
);
addQuoted('comment before string', (quote) => `export * ${FROM} /* x */ ${quoted(SPEC, quote)};\n`);
addQuoted('side effect', (quote) => `${IMP} ${quoted(SPEC, quote)};\n`);
addQuoted('import equals require', (quote) => `${IMP} x = ${REQ}(${quoted(SPEC, quote)});\n`);
addQuoted('require call', (quote) => `${REQ}(${quoted(SPEC, quote)});\n`);
addQuoted('dynamic import', (quote) => `${IMP}(${quoted(SPEC, quote)});\n`);
addQuoted('typeof dynamic import', (quote) => `typeof ${IMP}(${quoted(SPEC, quote)});\n`);
addQuoted(
  'dynamic import with options',
  (quote) => `${IMP}(${quoted(SPEC, quote)}, { with: { type: 'json' } });\n`,
);
addQuoted(
  'dynamic import trailing comma',
  (quote) => `${IMP}(\n  ${quoted(SPEC, quote)},\n);\n`,
);
addQuoted(
  'dynamic import comment',
  (quote) => `${IMP}(\n  /* note */\n  ${quoted(SPEC, quote)}\n);\n`,
);
addQuoted(
  'new URL one line',
  (quote) => `new ${URLW}(${quoted(SPEC, quote)}, ${IMP}.${META}.url);\n`,
);
addQuoted(
  'new URL multiline',
  (quote) => `new ${URLW}(\n  ${quoted(SPEC, quote)},\n  ${IMP}.${META}.url,\n);\n`,
);
addQuoted('glob string', (quote) => `${IMP}.${META}.${GLOB}(${quoted(SPEC, quote)});\n`);
addQuoted(
  'glob array',
  (quote) => `${IMP}.${META}.${GLOB}(['./ok.ts', ${quoted(SPEC, quote)}]);\n`,
);
addQuoted(
  'glob array trailing comma',
  (quote) => `${IMP}.${META}.${GLOB}([\n  './ok.ts',\n  ${quoted(SPEC, quote)},\n]);\n`,
);
add('backtick import()', `${IMP}(${BT}${SPEC}${BT});\n`);
add('backtick new URL', `new ${URLW}(${BT}${SPEC}${BT}, ${IMP}.${META}.url);\n`);
add('backtick glob', `${IMP}.${META}.${GLOB}(${BT}${SPEC}${BT});\n`);
add('backtick require', `${REQ}(${BT}${SPEC}${BT});\n`);
addQuoted(
  'reference path',
  (quote) => `/// <reference path=${quoted(SPEC, quote)} />\n`,
);
add(
  'reference types single',
  '/// <reference types="custodian" />\n',
  { rule: 'forbidden-package', needle: 'custodian' },
);
add(
  'reference types double',
  "/// <reference types='custodian' />\n",
  { rule: 'forbidden-package', needle: 'custodian' },
);

for (const ext of STYLE_EXTENSIONS) {
  const file = `src/app/s${ext}`;
  for (const quote of ["'", '"']) {
    add(`style import ${ext} ${quote}`, `@${IMP} ${quoted(SPEC, quote)};\n`, { file });
    add(`style import url ${ext} ${quote}`, `@${IMP} url(${quoted(SPEC, quote)});\n`, { file });
    add(`style url ${ext} ${quote}`, `a { background: url(${quoted(SPEC, quote)}); }\n`, { file });
  }
  add(`style relative a ${ext}`, 'a { background: url(a/../../../../x.png); }\n', {
    file,
    needle: 'a/../../../../x.png',
  });
  add(`style relative dots ${ext}`, 'a { background: url(../../../x.png); }\n', {
    file,
    needle: '../../../x.png',
  });
}
add(
  'style data and fragment pass',
  'a { background: url(data:image/png,aaaa); mask: url(#frag); }\n',
  { file: 'src/app/s.css', rule: null, needle: null },
);
add('non literal import template', `${IMP}(${BT}\${name}${BT});\n`, {
  rule: 'non-literal-import',
  needle: null,
  form: `${IMP}()`,
});
add('non literal require template', `${REQ}(${BT}\${name}${BT});\n`, {
  rule: 'non-literal-import',
  needle: null,
  form: `${REQ}()`,
});
add('non literal URL template', `new ${URLW}(${BT}\${name}${BT}, ${IMP}.${META}.url);\n`, {
  rule: 'non-literal-import',
  needle: null,
  form: `new ${URLW}()`,
});
add('non literal import name', `${IMP}(name);\n`, {
  rule: 'non-literal-import',
  needle: null,
  form: `${IMP}()`,
});
add('non literal require name', `${REQ}(name);\n`, {
  rule: 'non-literal-import',
  needle: null,
  form: `${REQ}()`,
});
add('comment line', `// ${IMP} x ${FROM} '${SPEC}';\n`, { rule: null, needle: null });
add('comment block', `/* ${IMP} x ${FROM} '${SPEC}'; */\n`, { rule: null, needle: null });
add('two-slash reference', `// <reference path="${SPEC}">\n`, { rule: null, needle: null });
add('string then import', `const a = "//"; ${IMP} x ${FROM} '${SPEC}';\n`);
add(
  'template substitution then import',
  `const t = ${BT}` + '${"' + "'{}" + '"}' + `${BT};\n${IMP} x ${FROM} '${SPEC}';\n`,
);
add(
  'unterminated string then import',
  `const a = 'unterminated\n${IMP} x ${FROM} '${SPEC}';\n`,
);
add(
  'not handled worker and name',
  `new ${'Wor' + 'ker'}('${SPEC}');\nnew ${URLW}(name, ${IMP}.${META}.url);\n`,
  { rule: null, needle: null },
);
add('regex hides the rest of the line', `const r = /'/; ${IMP} x ${FROM} '${SPEC}';\n`, {
  rule: null,
  needle: null,
});

test('reference forms', async (t) => {
  for (const item of cases) {
    await t.test(item.name, () => {
      const root = makeRoot();
      const full = path.join(root, item.file);
      fs.mkdirSync(path.dirname(full), { recursive: true });
      fs.writeFileSync(full, item.text);
      const result = run(root);
      if (item.rule === null) {
        assert.equal(result.status, 0, `${item.name}\n${result.stdout}`);
        assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
        return;
      }
      assert.equal(result.status, 1, `${item.name}\n${result.stdout}\n${result.stderr}`);
      const line = item.needle === null ? null : lineOf(item.text, item.needle);
      const prefix =
        line === null
          ? `FAIL ${item.rule}: ${item.file}`
          : `FAIL ${item.rule}: ${item.file}:${line}`;
      const hit = result.stdout.split('\n').some((row) => row.startsWith(prefix));
      assert.equal(hit, true, `${prefix}\n${result.stdout}`);
      if (item.form !== null) assert.ok(result.stdout.includes(item.form), result.stdout);
    });
  }
});
