import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '..', '..');
const SCRIPT = path.join(WEB, 'scripts', 'check-no-third-party-hosts.mjs');
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-test-inert-hosts-'));
after(() => fs.rmSync(scratch, { recursive: true, force: true }));

function chars(...codes) {
  return String.fromCharCode(...codes);
}

const TWO_BACKSLASHES = chars(92, 92);
const SLASH_BACKSLASH = chars(47, 92);
const COMMENT_SLASHES = chars(47, 92, 47, 92, 47);

// Exact group-3 and group-4 text from the current built page.
const PROTOCOL_TOKENS = [
  {
    name: 'luma deprecation',
    slashes: TWO_BACKSLASHES,
    host: 'b${e.old}',
    body: '`' + TWO_BACKSLASHES + 'b${e.old}`',
  },
  {
    name: 'luma line comment',
    slashes: COMMENT_SLASHES,
    host: '.*$',
    body: '.replace(' + COMMENT_SLASHES + '.*$/)',
  },
  {
    name: 'luma hook signature',
    slashes: SLASH_BACKSLASH,
    host: '(.+',
    body: '.replace(' + SLASH_BACKSLASH + '(.+/)',
  },
  {
    name: 'luma fragment input',
    slashes: TWO_BACKSLASHES,
    host: 'b${U(l.name',
    body: '`' + TWO_BACKSLASHES + 'b${U(l.name)}`',
  },
  {
    name: 'loaders extension',
    slashes: SLASH_BACKSLASH,
    host: '.([^.]+',
    body: '=' + SLASH_BACKSLASH + '.([^.]+)$/',
  },
  {
    name: 'loaders svg',
    slashes: SLASH_BACKSLASH,
    host: '.svg((',
    body: '=' + SLASH_BACKSLASH + '.svg((' + chars(92) + '?|#).*)?$/',
  },
];

function run(args) {
  return spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: 'utf8',
    env: {
      PATH: process.env.PATH,
      HOME: scratch,
      TMPDIR: scratch,
      LANG: 'C',
    },
  });
}

function makeRoot() {
  const home = fs.mkdtempSync(path.join(scratch, 'eii-host-'));
  fs.mkdirSync(path.join(home, 'src'), { recursive: true });
  fs.writeFileSync(
    path.join(home, 'index.html'),
    '<!doctype html><title>shell</title>\n',
  );
  fs.writeFileSync(path.join(home, 'vite.config.ts'), 'export default {};\n');
  fs.writeFileSync(path.join(home, 'src', 'main.tsx'), 'export {}\n');
  return home;
}

function distFile(home, rel, body) {
  const full = path.join(home, rel);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, body);
}

function builtScript(home, body) {
  distFile(
    home,
    'dist/index.html',
    '<!doctype html><html><head></head><body></body></html>\n',
  );
  distFile(home, 'dist/assets/a.js', body);
}

function assertOk(result) {
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
}

function assertFail(result, prefix) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const hit = result.stdout.split('\n').some((line) => line.startsWith(prefix));
  assert.equal(hit, true, result.stdout);
}

test('en.wikipedia.org is allowed only in a built script', () => {
  const script = makeRoot();
  builtScript(
    script,
    'const note = "https://en.wikipedia.org/wiki/Find_first_set";\n',
  );
  assertOk(run(['--root', script, '--dist']));

  const sheet = makeRoot();
  builtScript(sheet, 'var n = 1;\n');
  distFile(
    sheet,
    'dist/assets/a.css',
    '/* https://en.wikipedia.org/wiki/Find_first_set */\n',
  );
  assertFail(
    run(['--root', sheet, '--dist']),
    'FAIL absolute-url: dist/assets/a.css',
  );
});

test('listed protocol-relative tokens are allowed only in a built script', () => {
  for (const token of PROTOCOL_TOKENS) {
    const script = makeRoot();
    builtScript(script, token.body + '\n');
    const allowed = run(['--root', script, '--dist']);
    assert.equal(allowed.status, 0, `${token.name}\n${allowed.stdout}`);

    const sheet = makeRoot();
    builtScript(sheet, 'var n = 1;\n');
    distFile(sheet, 'dist/assets/a.css', token.body + '\n');
    const refused = run(['--root', sheet, '--dist']);
    assert.equal(refused.status, 1, token.name);
    assert.equal(
      refused.stdout.includes('FAIL protocol-relative-url: dist/assets/a.css'),
      true,
      `${token.name}\n${refused.stdout}`,
    );
  }
});

test('a real protocol-relative address in a built script still fails', () => {
  const quoted = makeRoot();
  builtScript(quoted, '"//cdn.syn-example.test/x.js"\n');
  assertFail(
    run(['--root', quoted, '--dist']),
    'FAIL protocol-relative-url: dist/assets/a.js',
  );

  const slashed = makeRoot();
  builtScript(slashed, "'" + TWO_BACKSLASHES + "syn-host.example.test'\n");
  assertFail(
    run(['--root', slashed, '--dist']),
    'FAIL protocol-relative-url: dist/assets/a.js',
  );
});

test('a listed protocol-relative token with one character changed still fails', () => {
  const home = makeRoot();
  builtScript(home, '`' + TWO_BACKSLASHES + 'b${e.olx}`\n');
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL protocol-relative-url: dist/assets/a.js',
  );
});

test('https://unpkg.com/ is allowed only in a built script', () => {
  const script = makeRoot();
  builtScript(script, 'const cdn = "https://unpkg.com/";\n');
  assertOk(run(['--root', script, '--dist']));

  const page = makeRoot();
  builtScript(page, 'var n = 1;\n');
  distFile(page, 'dist/extra.html', '<p>https://unpkg.com/</p>\n');
  assertFail(
    run(['--root', page, '--dist']),
    'FAIL absolute-url: dist/extra.html',
  );
});
