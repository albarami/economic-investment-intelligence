import assert from 'node:assert/strict';
import { AsyncLocalStorage } from 'node:async_hooks';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test as declareTest } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '..', '..');
const SCRIPT = path.join(WEB, 'scripts', 'check-no-third-party-hosts.mjs');
const BT = String.fromCharCode(96);
const BINARY = [
  '.woff',
  '.woff2',
  '.ttf',
  '.otf',
  '.eot',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.webp',
  '.avif',
  '.ico',
  '.bmp',
  '.mp3',
  '.mp4',
  '.webm',
  '.ogg',
  '.wav',
  '.pdf',
  '.wasm',
  '.zip',
  '.gz',
];
const TEXT_FILES = [
  'src/a.mts',
  'src/b.cts',
  'src/c.scss',
  'src/d.htm',
  'src/e.unknownext',
  'src/f.svg',
  'src/g.json',
  'src/h.map',
  'public/i.txt',
  'src/j',
];
const SCHEMES = [
  'http://example.com/x',
  'https://example.com/x',
  'ws://example.com/x',
  'wss://example.com/x',
  'ftp://example.com/x',
  'file:///x',
  'chrome-extension://example/x',
];
const BACKSLASH = [
  'https:\\\\host.example/x',
  'https:/\\host.example/x',
  'https:\\/host.example/x',
];

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-test-check-no-third-party-hosts-forms-'));
const currentTest = new AsyncLocalStorage();
after(() => fs.rmSync(root, { recursive: true, force: true }));

function bindTest(t) {
  const own = t.test.bind(t);
  t.test = (name, options, fn) => {
    if (typeof options === 'function') {
      fn = options;
      options = undefined;
    }
    const wrapped = (sub) => currentTest.run(sub, () => {
      bindTest(sub);
      return fn(sub);
    });
    if (options === undefined) return own(name, wrapped);
    return own(name, options, wrapped);
  };
}

function test(name, options, fn) {
  if (typeof options === 'function') {
    fn = options;
    options = undefined;
  }
  const wrapped = (t) => currentTest.run(t, () => {
    bindTest(t);
    return fn(t);
  });
  if (options === undefined) return declareTest(name, wrapped);
  return declareTest(name, options, wrapped);
}

function tempDir(prefix) {
  const dir = fs.mkdtempSync(path.join(root, prefix));
  currentTest.getStore().after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function childTemp(home) {
  const dir = path.join(home, 'tmp');
  fs.mkdirSync(dir);
  return dir;
}

function cleanEnv(extra) {
  const home = tempDir('eii-env-');
  const tmp = childTemp(home);
  const base = { PATH: process.env.PATH, HOME: home, TMPDIR: tmp, TMP: tmp, TEMP: tmp, LANG: 'C' };
  return { ...base, ...extra };
}

function runNode(script, args) {
  return spawnSync(process.execPath, [script, ...args], {
    encoding: 'utf8',
    env: cleanEnv(),
  });
}

function makeRoot() {
  const root = tempDir('eii-host-');
  fs.mkdirSync(path.join(root, 'src'), { recursive: true });
  fs.writeFileSync(path.join(root, 'index.html'), '<!doctype html><title>shell</title>\n');
  return root;
}

function assertFail(result, prefix) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const hit = result.stdout.split('\n').some((line) => line.startsWith(prefix));
  assert.equal(hit, true, result.stdout);
}

test('scheme forms', async (t) => {
  for (const sample of SCHEMES) {
    await t.test(sample, () => {
      const root = makeRoot();
      fs.writeFileSync(path.join(root, 'src', 'a.ts'), `const u = '${sample}';\n`);
      assertFail(runNode(SCRIPT, ['--root', root]), 'FAIL absolute-url');
    });
  }
});

test('escaped slashes', () => {
  const root = makeRoot();
  fs.writeFileSync(path.join(root, 'src', 'a.ts'), "const u = 'https:\\/\\/host.example/x';\n");
  assertFail(runNode(SCRIPT, ['--root', root]), 'FAIL absolute-url');
});

test('backslash forms', async (t) => {
  for (const sample of BACKSLASH) {
    await t.test(sample, () => {
      const root = makeRoot();
      fs.writeFileSync(path.join(root, 'src', 'a.ts'), `const u = '${sample}';\n`);
      assertFail(runNode(SCRIPT, ['--root', root]), 'FAIL absolute-url');
    });
  }
});

test('protocol-relative forms', async (t) => {
  const samples = [
    '<img src="//host.example/x">',
    '<img src=//host.example/x>',
    'a { background: url(//host.example/x); }',
    '@import "//host.example/x";',
    '<img srcset="a.png 1x, //host.example/x 2x">',
    `const u = ${BT}//host.example/x${BT};`,
    'const u = "\\\\host.example\\x";',
    'const u = "/\\host.example/x";',
  ];
  for (const sample of samples) {
    await t.test(sample, () => {
      const root = makeRoot();
      const ext = sample.startsWith('a ') || sample.startsWith('@') ? 'a.css' : 'a.ts';
      if (sample.startsWith('<')) {
        fs.writeFileSync(path.join(root, 'index.html'), `${sample}\n`);
      } else {
        fs.writeFileSync(path.join(root, 'src', ext), `${sample}\n`);
      }
      assertFail(runNode(SCRIPT, ['--root', root]), 'FAIL protocol-relative-url');
    });
  }
});

test('protocol-relative host stops at a comma or a closing parenthesis', async (t) => {
  const samples = [
    '<img srcset="//cdn,//host.example/x">',
    'a { background: url(//host.example); }',
  ];
  for (const sample of samples) {
    await t.test(sample, () => {
      const root = makeRoot();
      if (sample.startsWith('<')) {
        fs.writeFileSync(path.join(root, 'index.html'), `${sample}\n`);
      } else {
        fs.writeFileSync(path.join(root, 'src', 'a.css'), `${sample}\n`);
      }
      assertFail(runNode(SCRIPT, ['--root', root]), 'FAIL protocol-relative-url');
    });
  }
});

test('each character that may precede the slashes', async (t) => {
  const samples = [
    ['double quote', '"//host.example/x"'],
    ['single quote', "'//host.example/x'"],
    ['backtick', `${BT}//host.example/x${BT}`],
    ['paren', 'url(//host.example/x)'],
    ['equals', 'src=//host.example/x'],
    ['comma', 'srcset="a.png 1x, //host.example/x 2x"'],
    ['space after equals', 'src= //host.example/x'],
    ['space after quote', '" //host.example/x"'],
  ];
  for (const [name, sample] of samples) {
    await t.test(name, () => {
      const root = makeRoot();
      fs.writeFileSync(path.join(root, 'src', 'a.ts'), `${sample}\n`);
      assertFail(runNode(SCRIPT, ['--root', root]), 'FAIL protocol-relative-url');
    });
  }
});

test('host names that are not dotted', () => {
  const root = makeRoot();
  fs.writeFileSync(path.join(root, 'src', 'a.ts'), 'const a = "//cdn/x";\nconst b = "//[::1]/x";\n');
  const result = runNode(SCRIPT, ['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('allowed schemes', () => {
  const root = makeRoot();
  fs.writeFileSync(path.join(root, 'index.html'), '<a href="data:,">x</a>\n');
  fs.writeFileSync(path.join(root, 'src', 'a.ts'), "const b = 'blob:x';\n");
  const result = runNode(SCRIPT, ['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('CSS url absolute', () => {
  const root = makeRoot();
  fs.writeFileSync(path.join(root, 'src', 'a.css'), 'a { background: url("https://example.com/x"); }\n');
  assertFail(runNode(SCRIPT, ['--root', root]), 'FAIL absolute-url');
});

test('font-face source', () => {
  const root = makeRoot();
  fs.writeFileSync(
    path.join(root, 'src', 'a.css'),
    '@font-face { src: url(https://example.com/font.woff2); }\n',
  );
  assertFail(runNode(SCRIPT, ['--root', root]), 'FAIL absolute-url');
});

test('namespace string in sources', () => {
  const root = makeRoot();
  fs.writeFileSync(path.join(root, 'src', 'a.tsx'), "const ns = 'http://www.w3.org/2000/svg';\n");
  assertFail(runNode(SCRIPT, ['--root', root]), 'FAIL absolute-url');
});

test('file types read as text', async (t) => {
  for (const rel of TEXT_FILES) {
    await t.test(rel, () => {
      const root = makeRoot();
      const full = path.join(root, rel);
      fs.mkdirSync(path.dirname(full), { recursive: true });
      fs.writeFileSync(full, 'https://example.com/x\n');
      assertFail(runNode(SCRIPT, ['--root', root]), 'FAIL absolute-url');
    });
  }
});

test('upper-case extension', async (t) => {
  for (const name of ['K.TS', 'L.SVG']) {
    await t.test(name, () => {
      const root = makeRoot();
      fs.writeFileSync(path.join(root, 'src', name), 'https://example.com/x\n');
      assertFail(runNode(SCRIPT, ['--root', root]), 'FAIL absolute-url');
    });
  }
});

test('binary list is counted and not scanned', async (t) => {
  for (const ext of BINARY) {
    await t.test(ext, () => {
      const root = makeRoot();
      fs.writeFileSync(path.join(root, 'src', `x${ext}`), 'https://example.com/x');
      const result = runNode(SCRIPT, ['--root', root]);
      assert.equal(result.status, 0, result.stdout);
      const line = result.stdout.trim().split('\n').at(-1);
      assert.match(line, /^checked \d+ files: OK$/);
      const found = Number(line.match(/^checked (\d+) files: OK$/)[1]);
      assert.equal(found, 2);
    });
  }
});

test('run through a symbolic link', () => {
  const root = makeRoot();
  fs.writeFileSync(path.join(root, 'index.html'), '<script src="https://example.com/x.js"></script>\n');
  const linkParent = tempDir('eii-link-');
  const link = path.join(linkParent, 'scripts');
  fs.symlinkSync(path.join(WEB, 'scripts'), link);
  const result = runNode(path.join(link, 'check-no-third-party-hosts.mjs'), ['--root', root]);
  assertFail(result, 'FAIL absolute-url: index.html');
});
