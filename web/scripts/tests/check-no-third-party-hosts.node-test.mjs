import assert from 'node:assert/strict';
import { AsyncLocalStorage } from 'node:async_hooks';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test as declareTest } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '..', '..');
const SCRIPT = path.join(WEB, 'scripts', 'check-no-third-party-hosts.mjs');
const LONG_NAME_LENGTH = 300;
const HOSTS = ['www.w3.org', 'react.dev', 'reactjs.org', 'github.com'];
const REQUEST = 'fe' + 'tch';

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-test-check-no-third-party-hosts-'));
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

function run(args, env) {
  return spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: 'utf8',
    env: env ?? cleanEnv(),
  });
}

function makeRoot() {
  const root = tempDir('eii-host-');
  fs.mkdirSync(path.join(root, 'src'), { recursive: true });
  fs.writeFileSync(path.join(root, 'index.html'), '<!doctype html><title>shell</title>\n');
  fs.writeFileSync(path.join(root, 'vite.config.ts'), 'export default {};\n');
  fs.writeFileSync(path.join(root, 'src', 'main.tsx'), 'export {}\n');
  return root;
}

function assertFail(result, prefix) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const hit = result.stdout.split('\n').some((line) => line.startsWith(prefix));
  assert.equal(hit, true, result.stdout);
}

function snapshot(root) {
  const rows = [];
  const walk = (dir) => {
    for (const name of fs.readdirSync(dir).sort()) {
      const full = path.join(dir, name);
      const info = fs.lstatSync(full);
      const rel = path.relative(root, full).split(path.sep).join('/');
      if (info.isSymbolicLink()) {
        rows.push(`link ${rel}`);
        continue;
      }
      if (info.isDirectory()) {
        rows.push(`dir ${rel}`);
        walk(full);
      } else {
        const digest = createHash('sha256').update(fs.readFileSync(full)).digest('hex');
        rows.push(`file ${rel} ${info.size} ${digest}`);
      }
    }
  };
  walk(root);
  return rows.join('\n');
}

function hostileEnv() {
  const base = cleanEnv();
  return cleanEnv({
    npm_config_registry: 'http://127.0.0.1:9/',
    npm_config_prefix: path.join(base.HOME, 'missing-prefix'),
    npm_config_userconfig: path.join(base.HOME, 'missing.npmrc'),
    HOST: '0.0.0.0',
    PORT: '1',
    VITE_PORT: '1',
    BROWSER: 'firefox',
    NODE_ENV: 'production',
    NODE_OPTIONS: '--no-warnings',
    HTTP_PROXY: 'http://127.0.0.1:9/',
    HTTPS_PROXY: 'http://127.0.0.1:9/',
  });
}

function builtPage(src) {
  return `<!doctype html><html><head><script type="module" crossorigin src="${src}"></script><link rel="icon" href="data:,"></head></html>\n`;
}

test('clean sources', () => {
  const result = run(['--root', makeRoot()]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('real web sources pass', () => {
  const result = run(['--root', WEB]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout.trim().split('\n').at(-1), /^checked \d+ files: OK$/);
});

test('index.html missing', () => {
  const root = makeRoot();
  fs.rmSync(path.join(root, 'index.html'));
  assertFail(run(['--root', root]), 'FAIL missing-file: index.html');
});

test('index.html unreadable', () => {
  const root = makeRoot();
  fs.rmSync(path.join(root, 'index.html'));
  fs.symlinkSync(path.join(root, 'missing-target'), path.join(root, 'index.html'));
  assertFail(run(['--root', root]), 'FAIL unreadable-file: index.html');
});

test('unreadable file in src', () => {
  const root = makeRoot();
  fs.symlinkSync(path.join(root, 'missing-target'), path.join(root, 'src', 'x.ts'));
  assertFail(run(['--root', root]), 'FAIL unreadable-file: src/x.ts');
});

test('hosted font stylesheet', () => {
  const root = makeRoot();
  fs.writeFileSync(
    path.join(root, 'index.html'),
    '<link rel="stylesheet" href="https://fonts.example/x.css">\n',
  );
  assertFail(run(['--root', root]), 'FAIL absolute-url: index.html');
});

test('hosted script', () => {
  const root = makeRoot();
  fs.writeFileSync(
    path.join(root, 'index.html'),
    '<script src="https://cdn.example/app.js"></script>\n',
  );
  assertFail(run(['--root', root]), 'FAIL absolute-url: index.html');
});

test('request in code', () => {
  const root = makeRoot();
  const body = `${REQUEST}('https://example.com/x');\n`;
  fs.writeFileSync(path.join(root, 'src', 'call.ts'), body);
  assertFail(run(['--root', root]), 'FAIL absolute-url: src/call.ts');
});

test('scripts and tests are not read', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'scripts'));
  fs.mkdirSync(path.join(root, 'tests'));
  fs.writeFileSync(path.join(root, 'scripts', 'p.mjs'), 'const u = "https://example.com/x";\n');
  fs.writeFileSync(path.join(root, 'tests', 'p.ts'), 'const u = "https://example.com/x";\n');
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('vite config with a URL', () => {
  const root = makeRoot();
  fs.writeFileSync(path.join(root, 'vite.config.ts'), 'const u = "https://example.com/x";\n');
  assertFail(run(['--root', root]), 'FAIL absolute-url: vite.config.ts');
});

test('dist missing', () => {
  assertFail(run(['--root', makeRoot(), '--dist']), 'FAIL dist-missing');
});

test('dist present without page', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'dist', 'assets'), { recursive: true });
  fs.writeFileSync(path.join(root, 'dist', 'assets', 'a.js'), 'export {}\n');
  assertFail(run(['--root', root, '--dist']), 'FAIL missing-file: dist/index.html');
});

test('dist clean built page', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'dist', 'assets'), { recursive: true });
  fs.writeFileSync(path.join(root, 'dist', 'index.html'), builtPage('/assets/a.js'));
  fs.writeFileSync(path.join(root, 'dist', 'assets', 'a.js'), 'http://www.w3.org/2000/svg\n');
  const result = run(['--root', root, '--dist']);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('listed hosts allowed in JavaScript', async (t) => {
  for (const host of HOSTS) {
    for (const scheme of ['http', 'https']) {
      await t.test(`${scheme} ${host}`, () => {
        const root = makeRoot();
        fs.mkdirSync(path.join(root, 'dist', 'assets'), { recursive: true });
        fs.writeFileSync(path.join(root, 'dist', 'index.html'), builtPage('/assets/a.js'));
        fs.writeFileSync(
          path.join(root, 'dist', 'assets', 'a.js'),
          `${scheme}://${host}/x\n`,
        );
        const result = run(['--root', root, '--dist']);
        assert.equal(result.status, 0, result.stdout);
        assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
      });
    }
  }
});

test('JavaScript with another host', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'dist', 'assets'), { recursive: true });
  fs.writeFileSync(path.join(root, 'dist', 'index.html'), builtPage('/assets/a.js'));
  fs.writeFileSync(path.join(root, 'dist', 'assets', 'a.js'), 'https://example.com/x\n');
  assertFail(run(['--root', root, '--dist']), 'FAIL absolute-url-js');
});

test('listed host with another scheme', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'dist', 'assets'), { recursive: true });
  fs.writeFileSync(path.join(root, 'dist', 'index.html'), builtPage('/assets/a.js'));
  fs.writeFileSync(path.join(root, 'dist', 'assets', 'a.js'), 'ws://www.w3.org/x\n');
  assertFail(run(['--root', root, '--dist']), 'FAIL absolute-url-js');
});

test('listed host written in capitals', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'dist', 'assets'), { recursive: true });
  fs.writeFileSync(path.join(root, 'dist', 'index.html'), builtPage('/assets/a.js'));
  fs.writeFileSync(path.join(root, 'dist', 'assets', 'a.js'), 'HTTP://WWW.W3.ORG/x\n');
  const result = run(['--root', root, '--dist']);
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('relative asset URL', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'dist'), { recursive: true });
  fs.writeFileSync(path.join(root, 'dist', 'index.html'), builtPage('./assets/a.js'));
  assertFail(run(['--root', root, '--dist']), 'FAIL asset-url-shape');
});

test('protocol-relative asset URL', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'dist'), { recursive: true });
  fs.writeFileSync(path.join(root, 'dist', 'index.html'), builtPage('//h.example/a.js'));
  assertFail(run(['--root', root, '--dist']), 'FAIL asset-url-shape');
});

test('href not root-relative', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'dist'), { recursive: true });
  fs.writeFileSync(
    path.join(root, 'dist', 'index.html'),
    '<link rel="stylesheet" href="./a.css">\n',
  );
  assertFail(run(['--root', root, '--dist']), 'FAIL asset-url-shape');
});

test('built mjs with another host', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'dist', 'assets'), { recursive: true });
  fs.writeFileSync(path.join(root, 'dist', 'index.html'), builtPage('/assets/a.js'));
  fs.writeFileSync(path.join(root, 'dist', 'assets', 'a.js'), 'var n = 1;\n');
  fs.writeFileSync(path.join(root, 'dist', 'assets', 'a.mjs'), 'https://example.com/x\n');
  assertFail(run(['--root', root, '--dist']), 'FAIL absolute-url-js');
});

test('srcset candidate not root-relative', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'dist'), { recursive: true });
  fs.writeFileSync(
    path.join(root, 'dist', 'index.html'),
    '<img srcset="./a.png 1x">\n',
  );
  assertFail(run(['--root', root, '--dist']), 'FAIL asset-url-shape');
});

test('absolute asset URL', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'dist'), { recursive: true });
  fs.writeFileSync(
    path.join(root, 'dist', 'index.html'),
    builtPage('https://example.com/a.js'),
  );
  assertFail(run(['--root', root, '--dist']), 'FAIL absolute-url');
});

test('dist CSS with another host', () => {
  const root = makeRoot();
  fs.mkdirSync(path.join(root, 'dist', 'assets'), { recursive: true });
  fs.writeFileSync(path.join(root, 'dist', 'index.html'), builtPage('/assets/a.js'));
  fs.writeFileSync(path.join(root, 'dist', 'assets', 'a.js'), 'var n = 1;\n');
  fs.writeFileSync(
    path.join(root, 'dist', 'assets', 'a.css'),
    'a { background: url(https://example.com/x.png); }\n',
  );
  assertFail(run(['--root', root, '--dist']), 'FAIL absolute-url');
});

test('lock file and package.json are not scanned', () => {
  const root = makeRoot();
  fs.writeFileSync(path.join(root, 'package.json'), '{"name":"eii-web"}\n');
  fs.writeFileSync(
    path.join(root, 'package-lock.json'),
    '{"packages":{"https://registry.npmjs.org/react":{}}}\n',
  );
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('usage', async (t) => {
  await t.test('unknown flag', () => {
    const result = run(['--not-a-flag']);
    assert.equal(result.status, 2, result.stdout);
    assert.ok(result.stdout.startsWith('USAGE: '));
  });
  await t.test('root without a value', () => {
    const result = run(['--root']);
    assert.equal(result.status, 2, result.stdout);
    assert.ok(result.stdout.startsWith('USAGE: '));
  });
});

test('internal error', () => {
  const longName = path.join(root, 'n'.repeat(LONG_NAME_LENGTH));
  const result = run(['--root', longName]);
  assert.equal(result.status, 1);
  assert.equal(result.stdout, 'FAIL internal-error: ENAMETOOLONG: name too long, stat\n');
  assert.equal(`${result.stdout}${result.stderr}`.includes('    at '), false);
});

test('hostile surroundings', () => {
  const clean = run(['--root', WEB], cleanEnv());
  const hostile = run(['--root', WEB], hostileEnv());
  assert.equal(clean.status, 0, clean.stdout + clean.stderr);
  assert.match(clean.stdout.trim().split('\n').at(-1), /OK$/);
  assert.equal(hostile.status, clean.status);
  assert.equal(hostile.stdout, clean.stdout);
});

test('reads only', () => {
  const root = makeRoot();
  const before = snapshot(root);
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.equal(snapshot(root), before);
});
