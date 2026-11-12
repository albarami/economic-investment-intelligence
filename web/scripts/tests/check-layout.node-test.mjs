import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '..', '..');
const SCRIPT = path.join(WEB, 'scripts', 'check-layout.mjs');
const LONG_NAME_LENGTH = 300;

const REQUIRED_DIRECTORIES = [
  'src',
  'src/app',
  'src/state',
  'src/api',
  'src/facts',
  'src/i18n',
  'src/stage',
  'src/brief',
  'src/cards',
  'src/controls',
  'src/seats',
  'src/rooms',
  'src/story',
  'src/pack',
  'src/shell',
  'src/styles',
  'tests',
  'tests/unit',
  'tests/component',
  'tests/e2e',
  'tests/visual',
  'tests/audit',
  'tests/fixtures',
  'eslint-rules',
];
const MARKER_DIRECTORIES = [
  'src/state',
  'src/api',
  'src/facts',
  'src/i18n',
  'src/stage',
  'src/brief',
  'src/cards',
  'src/controls',
  'src/seats',
  'src/rooms',
  'src/story',
  'src/pack',
  'src/shell',
  'src/styles',
  'tests/unit',
  'tests/component',
  'tests/e2e',
  'tests/visual',
  'tests/audit',
  'tests/fixtures',
  'eslint-rules',
];
const REQUIRED_FILES = [
  'package.json',
  'package-lock.json',
  'vite.config.ts',
  'tsconfig.json',
  'index.html',
  'src/main.tsx',
];
const FORBIDDEN_CONFIGS = [
  'vite.config.js',
  'vite.config.mjs',
  'vite.config.cjs',
  'vite.config.mts',
  'vite.config.cts',
];

function cleanEnv(extra) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-env-'));
  const base = { PATH: process.env.PATH, HOME: home, TMPDIR: home, LANG: 'C' };
  return { ...base, ...extra };
}

function run(args, env) {
  return spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: 'utf8',
    env: env ?? cleanEnv(),
  });
}

function makeFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-layout-'));
  for (const dir of REQUIRED_DIRECTORIES) {
    fs.mkdirSync(path.join(root, dir), { recursive: true });
  }
  for (const dir of MARKER_DIRECTORIES) {
    fs.writeFileSync(path.join(root, dir, '.gitkeep'), '');
  }
  fs.writeFileSync(path.join(root, 'src', 'app', 'App.tsx'), 'export {}\n');
  for (const file of REQUIRED_FILES) {
    const full = path.join(root, file);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, 'x\n');
  }
  return root;
}

function emptyDirectory(root, dir) {
  const full = path.join(root, dir);
  for (const name of fs.readdirSync(full)) {
    fs.rmSync(path.join(full, name), { recursive: true, force: true });
  }
}

function snapshot(root) {
  const rows = [];
  const walk = (dir) => {
    for (const name of fs.readdirSync(dir).sort()) {
      const full = path.join(dir, name);
      const info = fs.lstatSync(full);
      const rel = path.relative(root, full).split(path.sep).join('/');
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

function assertFail(result, prefix) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const hit = result.stdout.split('\n').some((line) => line.startsWith(prefix));
  assert.equal(hit, true, result.stdout);
}

test('complete fixture', () => {
  const root = makeFixture();
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const notes = result.stdout.split('\n').filter((line) => line.startsWith('NOTE deferred:'));
  assert.equal(notes.length, 2);
  const lines = result.stdout.trim().split('\n');
  assert.equal(lines[lines.length - 1], 'checked 30 entries: OK');
});

test('real web passes', () => {
  const result = run(['--root', WEB]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const lines = result.stdout.trim().split('\n');
  assert.match(lines[lines.length - 1], /^checked \d+ entries: OK$/);
});

test('deferred file present', () => {
  const root = makeFixture();
  fs.writeFileSync(path.join(root, 'eslint.config.js'), 'x\n');
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  const notes = result.stdout.split('\n').filter((line) => line.startsWith('NOTE deferred:'));
  assert.equal(notes.length, 1);
});

test('each required directory removed', async (t) => {
  for (const dir of REQUIRED_DIRECTORIES) {
    await t.test(dir, () => {
      const root = makeFixture();
      fs.rmSync(path.join(root, dir), { recursive: true, force: true });
      assertFail(run(['--root', root]), `FAIL missing-directory: ${dir}`);
    });
  }
});

test('each required directory emptied', async (t) => {
  for (const dir of REQUIRED_DIRECTORIES) {
    await t.test(dir, () => {
      const root = makeFixture();
      emptyDirectory(root, dir);
      assertFail(run(['--root', root]), `FAIL empty-directory: ${dir}`);
    });
  }
});

test('marker-holding directory with the wrong content', async (t) => {
  await t.test('empty subfolder', () => {
    const root = makeFixture();
    fs.rmSync(path.join(root, 'src', 'state', '.gitkeep'));
    fs.mkdirSync(path.join(root, 'src', 'state', 'empty'));
    assertFail(run(['--root', root]), 'FAIL empty-directory: src/state');
  });
  await t.test('dangling link named x', () => {
    const root = makeFixture();
    fs.rmSync(path.join(root, 'src', 'state', '.gitkeep'));
    fs.symlinkSync(path.join(root, 'missing-target'), path.join(root, 'src', 'state', 'x'));
    assertFail(run(['--root', root]), 'FAIL empty-directory: src/state');
  });
  await t.test('dangling link named .gitkeep', () => {
    const root = makeFixture();
    fs.rmSync(path.join(root, 'src', 'state', '.gitkeep'));
    fs.symlinkSync(path.join(root, 'missing-target'), path.join(root, 'src', 'state', '.gitkeep'));
    assertFail(run(['--root', root]), 'FAIL empty-directory: src/state');
  });
  await t.test('folder named .gitkeep', () => {
    const root = makeFixture();
    fs.rmSync(path.join(root, 'src', 'state', '.gitkeep'));
    fs.mkdirSync(path.join(root, 'src', 'state', '.gitkeep'));
    assertFail(run(['--root', root]), 'FAIL empty-directory: src/state');
  });
  await t.test('link named .gitkeep to an existing file', () => {
    const root = makeFixture();
    const target = path.join(root, 'package.json');
    fs.rmSync(path.join(root, 'src', 'state', '.gitkeep'));
    fs.symlinkSync(target, path.join(root, 'src', 'state', '.gitkeep'));
    assertFail(run(['--root', root]), 'FAIL empty-directory: src/state');
  });
});

test('content directory with the wrong content', async (t) => {
  await t.test('src/app empty subfolder only', () => {
    const root = makeFixture();
    emptyDirectory(root, 'src/app');
    fs.mkdirSync(path.join(root, 'src', 'app', 'empty'));
    assertFail(run(['--root', root]), 'FAIL empty-directory: src/app');
  });
  await t.test('src/app dangling link only', () => {
    const root = makeFixture();
    emptyDirectory(root, 'src/app');
    fs.symlinkSync(path.join(root, 'missing-target'), path.join(root, 'src', 'app', 'x'));
    assertFail(run(['--root', root]), 'FAIL empty-directory: src/app');
  });
  await t.test('tests markers removed folders kept', () => {
    const root = makeFixture();
    for (const dir of ['unit', 'component', 'e2e', 'visual', 'audit', 'fixtures']) {
      fs.rmSync(path.join(root, 'tests', dir, '.gitkeep'));
    }
    assertFail(run(['--root', root]), 'FAIL empty-directory: tests');
  });
});

test('a file in place of a directory', () => {
  const root = makeFixture();
  fs.rmSync(path.join(root, 'src', 'state'), { recursive: true });
  fs.writeFileSync(path.join(root, 'src', 'state'), 'x\n');
  assertFail(run(['--root', root]), 'FAIL missing-directory: src/state');
});

test('each required file removed', async (t) => {
  for (const file of REQUIRED_FILES) {
    await t.test(file, () => {
      const root = makeFixture();
      fs.rmSync(path.join(root, file));
      assertFail(run(['--root', root]), `FAIL missing-file: ${file}`);
    });
  }
});

test('each required file empty', async (t) => {
  for (const file of REQUIRED_FILES) {
    await t.test(file, () => {
      const root = makeFixture();
      fs.writeFileSync(path.join(root, file), '');
      assertFail(run(['--root', root]), `FAIL empty-file: ${file}`);
    });
  }
});

test('a directory in place of a file', () => {
  const root = makeFixture();
  fs.rmSync(path.join(root, 'index.html'));
  fs.mkdirSync(path.join(root, 'index.html'));
  assertFail(run(['--root', root]), 'FAIL missing-file: index.html');
});

test('each forbidden configuration name', async (t) => {
  for (const name of FORBIDDEN_CONFIGS) {
    await t.test(name, () => {
      const root = makeFixture();
      fs.writeFileSync(path.join(root, name), 'x\n');
      const result = run(['--root', root]);
      assertFail(result, `FAIL unexpected-config: ${name}`);
      const summary = result.stdout
        .trim()
        .split('\n')
        .find((line) => line.startsWith('checked '));
      assert.match(summary, /^checked \d+ entries: 1 failure\(s\)$/);
    });
  }
});

test('forbidden name as a dangling link or a folder', async (t) => {
  await t.test('dangling link', () => {
    const root = makeFixture();
    fs.symlinkSync(path.join(root, 'missing-target'), path.join(root, 'vite.config.mjs'));
    assertFail(run(['--root', root]), 'FAIL unexpected-config: vite.config.mjs');
  });
  await t.test('folder', () => {
    const root = makeFixture();
    fs.mkdirSync(path.join(root, 'vite.config.mjs'));
    assertFail(run(['--root', root]), 'FAIL unexpected-config: vite.config.mjs');
  });
});

test('extra entry allowed', () => {
  const root = makeFixture();
  fs.mkdirSync(path.join(root, 'scripts'));
  fs.writeFileSync(path.join(root, 'README.md'), 'x\n');
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout.trim().split('\n').at(-1), /^checked \d+ entries: OK$/);
});

test('usage', async (t) => {
  await t.test('root is not a directory', () => {
    const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'eii-file-')), 'root');
    fs.writeFileSync(file, 'x\n');
    const result = run(['--root', file]);
    assert.equal(result.status, 2, result.stdout);
    assert.ok(result.stdout.startsWith('USAGE: '));
  });
  await t.test('root absent', () => {
    const missing = path.join(os.tmpdir(), 'eii-absent-root');
    const result = run(['--root', missing]);
    assert.equal(result.status, 2, result.stdout);
    assert.ok(result.stdout.startsWith('USAGE: '));
  });
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
  const root = path.join(os.tmpdir(), 'n'.repeat(LONG_NAME_LENGTH));
  const result = run(['--root', root]);
  assert.equal(result.status, 1);
  assert.equal(result.stdout, 'FAIL internal-error: ENAMETOOLONG: name too long, stat\n');
  assert.equal(result.stdout.includes('    at '), false);
  assert.equal(result.stderr.includes('    at '), false);
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
  const root = makeFixture();
  const before = snapshot(root);
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.equal(snapshot(root), before);
});
