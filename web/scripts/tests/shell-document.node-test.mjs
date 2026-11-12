import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-test-shell-document-'));
after(() => fs.rmSync(root, { recursive: true, force: true }));

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '..', '..');
const TITLE = 'Economic &amp; Investment Intelligence (EII)';
const REQUEST = 'fe' + 'tch';
const STATE = 'use' + 'State';
const EFFECT = 'use' + 'Effect';

const SHELL = `<!doctype html>
<html lang="en" dir="ltr">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${TITLE}</title>
  </head>
  <body>
    <h1>${TITLE}</h1>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
`;

function assertShell(html) {
  const problems = [];
  if (!html.includes('lang="en"')) problems.push('lang');
  if (!html.includes('dir="ltr"')) problems.push('dir');
  if (!html.includes('name="viewport"')) problems.push('viewport');
  const titles = [...html.matchAll(/<title>([\s\S]*?)<\/title>/g)].map(
    (item) => item[1],
  );
  if (titles.length !== 1 || titles[0] !== TITLE) problems.push('title');
  const headings = html.match(/<h1\b/g) ?? [];
  if (headings.length !== 1) problems.push('h1');
  if (/<link\b[^>]*rel="stylesheet"/i.test(html)) problems.push('stylesheet');
  if (/<style\b/i.test(html)) problems.push('style');
  if (/<meta\b[^>]*http-equiv/i.test(html)) problems.push('http-equiv');
  if (!html.includes('id="root"')) problems.push('root');
  const scripts = [...html.matchAll(/<script\b([^>]*)>/gi)].map(
    (item) => item[1],
  );
  const modules = scripts.filter((attrs) =>
    /type\s*=\s*["']module["']/i.test(attrs),
  );
  if (modules.length !== 1) problems.push('module');
  if (
    scripts.some(
      (attrs) =>
        !/\ssrc\s*=/.test(` ${attrs}`) && !attrs.trim().startsWith('src='),
    )
  ) {
    problems.push('inline-script');
  }
  if (problems.length > 0) throw new Error(problems.join(','));
}

function assertMain(source) {
  if (!source.includes("getElementById('root')")) throw new Error('id');
  if (!source.includes('throw new Error')) throw new Error('throw');
}

function assertApp(source) {
  if (!source.includes('export function App')) throw new Error('export');
  if (
    source.includes(REQUEST) ||
    source.includes(STATE) ||
    source.includes(EFFECT)
  ) {
    throw new Error('runtime');
  }
}

function assertConfig(value) {
  const options = value.compilerOptions ?? {};
  const flags = [
    'strict',
    'noUncheckedIndexedAccess',
    'noUnusedLocals',
    'noUnusedParameters',
    'noEmit',
  ];
  for (const flag of flags) {
    if (options[flag] !== true) throw new Error(flag);
  }
  if (
    Object.hasOwn(value, 'ignoreDeprecations') ||
    Object.hasOwn(options, 'ignoreDeprecations')
  ) {
    throw new Error('ignoreDeprecations');
  }
}

test('shell document helper', () => {
  assert.doesNotThrow(() => assertShell(SHELL));
  const plants = [
    ['lang', SHELL.replace('lang="en"', 'lang="fr"')],
    ['dir', SHELL.replace('dir="ltr"', 'dir="rtl"')],
    ['viewport', SHELL.replace('name="viewport"', 'name="other"')],
    ['title', SHELL.replace(`<title>${TITLE}</title>`, '')],
    ['other title', SHELL.replace(TITLE, 'Other title', 1)],
    ['second h1', SHELL.replace('<h1>', '<h1></h1><h1>')],
    [
      'stylesheet',
      SHELL.replace('</head>', '<link rel="stylesheet" href="/a.css"></head>'),
    ],
    ['style', SHELL.replace('</head>', '<style>a{}</style></head>')],
    ['inline script', `${SHELL}<script>a</script>\n`],
    [
      'second module',
      SHELL.replace(
        '</body>',
        '<script type="module" src="/b.js"></script></body>',
      ),
    ],
    [
      'http-equiv',
      SHELL.replace(
        '</head>',
        '<meta http-equiv="refresh" content="0"></head>',
      ),
    ],
    ['root', SHELL.replace('id="root"', 'id="app"')],
  ];
  for (const [name, html] of plants) {
    assert.throws(() => assertShell(html), Error, name);
  }
  assert.doesNotThrow(() =>
    assertShell(fs.readFileSync(path.join(WEB, 'index.html'), 'utf8')),
  );
});

test('main and app', () => {
  const main = fs.readFileSync(path.join(WEB, 'src', 'main.tsx'), 'utf8');
  const app = fs.readFileSync(path.join(WEB, 'src', 'app', 'App.tsx'), 'utf8');
  assert.doesNotThrow(() => assertMain(main));
  assert.doesNotThrow(() => assertApp(app));
  assert.throws(() =>
    assertMain(main.replace("getElementById('root')", "getElementById('app')")),
  );
  assert.throws(() =>
    assertMain(main.replace('throw new Error', 'return null')),
  );
  assert.throws(() => assertApp(`${app}\n${REQUEST}('/x');\n`));
  assert.throws(() =>
    assertApp(
      app.replace('export function App', 'export default function App'),
    ),
  );
});

test('tsconfig strictness', () => {
  const real = JSON.parse(
    fs.readFileSync(path.join(WEB, 'tsconfig.json'), 'utf8'),
  );
  assert.doesNotThrow(() => assertConfig(real));
  const flags = [
    'strict',
    'noUncheckedIndexedAccess',
    'noUnusedLocals',
    'noUnusedParameters',
    'noEmit',
  ];
  for (const flag of flags) {
    const missing = structuredClone(real);
    delete missing.compilerOptions[flag];
    assert.throws(() => assertConfig(missing), Error, flag);
    const disabled = structuredClone(real);
    disabled.compilerOptions[flag] = false;
    assert.throws(() => assertConfig(disabled), Error, flag);
  }
  const deprecated = structuredClone(real);
  deprecated.ignoreDeprecations = '6.0';
  assert.throws(() => assertConfig(deprecated));
});
