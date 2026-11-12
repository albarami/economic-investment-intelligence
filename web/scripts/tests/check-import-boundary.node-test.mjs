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
const SCRIPT = path.join(WEB, 'scripts', 'check-import-boundary.mjs');
const LONG_NAME_LENGTH = 300;
const IMP = 'imp' + 'ort';
const FROM = 'fr' + 'om';
const OUTSIDE = '../../../core/x';

const SCRIPT_EXTENSIONS = ['.ts', '.tsx', '.mts', '.cts', '.js', '.jsx', '.mjs', '.cjs'];
const STYLE_EXTENSIONS = ['.css', '.scss', '.sass', '.less', '.styl', '.pcss'];
const FORBIDDEN = [
  'custodian/x',
  'core',
  'product/y',
  'gateway',
  'contracts',
  'evals',
  'infra',
  'data',
  'eii_core',
  'eii_custodian',
  'eii_product',
  'eii_gateway',
];
const ABSOLUTE = [
  'file:///x',
  '/@fs/x',
  '\\x',
  '\\\\server\\share\\x',
  '..\\..\\x',
  'C:\\x',
  'C:/x',
  '//host/x',
  '/../x',
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

function makeRoot() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-bound-'));
  fs.mkdirSync(path.join(root, 'src', 'app'), { recursive: true });
  fs.writeFileSync(
    path.join(root, 'tsconfig.json'),
    `${JSON.stringify({ compilerOptions: { strict: true }, include: ['src'] })}\n`,
  );
  return root;
}

function plant(root, rel, text) {
  const full = path.join(root, rel);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, text);
}

function fromLine(spec) {
  return `${IMP} x ${FROM} '${spec}';\n`;
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

test('clean src', () => {
  const root = makeRoot();
  plant(root, 'src/app/inside.ts', `${fromLine('./local')}${fromLine('../../package.json')}`);
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('real web passes', () => {
  const result = run(['--root', WEB]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(
    result.stdout.trim().split('\n').at(-1),
    /^checked \d+ references in \d+ files: OK$/,
  );
});

test('src missing', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-bound-'));
  fs.writeFileSync(path.join(root, 'tsconfig.json'), '{}\n');
  assertFail(run(['--root', root]), 'FAIL missing-source');
});

test('tsconfig.json shape', async (t) => {
  await t.test('missing', () => {
    const root = makeRoot();
    fs.rmSync(path.join(root, 'tsconfig.json'));
    assertFail(run(['--root', root]), 'FAIL tsconfig-json: tsconfig.json');
  });
  await t.test('not JSON', () => {
    const root = makeRoot();
    fs.writeFileSync(path.join(root, 'tsconfig.json'), '{');
    assertFail(run(['--root', root]), 'FAIL tsconfig-json: tsconfig.json');
  });
  await t.test('top level an array', () => {
    const root = makeRoot();
    fs.writeFileSync(path.join(root, 'tsconfig.json'), '[]\n');
    assertFail(run(['--root', root]), 'FAIL tsconfig-json: tsconfig.json');
  });
  await t.test('include a string', () => {
    const root = makeRoot();
    fs.writeFileSync(path.join(root, 'tsconfig.json'), '{"include":"src"}\n');
    assertFail(run(['--root', root]), 'FAIL tsconfig-json: tsconfig.json');
  });
});

test('unreadable file in src', () => {
  const root = makeRoot();
  fs.symlinkSync(path.join(root, 'missing-target'), path.join(root, 'src', 'x.ts'));
  assertFail(run(['--root', root]), 'FAIL unreadable-file: src/x.ts');
});

test('directories read', async (t) => {
  await t.test('tests/unit', () => {
    const root = makeRoot();
    plant(root, 'tests/unit/p.ts', fromLine(OUTSIDE));
    assertFail(run(['--root', root]), 'FAIL outside-web: tests/unit/p.ts');
  });
  await t.test('eslint-rules', () => {
    const root = makeRoot();
    plant(root, 'eslint-rules/p.ts', fromLine(OUTSIDE));
    assertFail(run(['--root', root]), 'FAIL outside-web: eslint-rules/p.ts');
  });
  await t.test('vite.config.ts', () => {
    const root = makeRoot();
    plant(root, 'vite.config.ts', fromLine('../core/x'));
    assertFail(run(['--root', root]), 'FAIL outside-web: vite.config.ts');
  });
});

test('scripts is not read', () => {
  const root = makeRoot();
  plant(root, 'scripts/p.mjs', fromLine(OUTSIDE));
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('script extensions', async (t) => {
  for (const ext of SCRIPT_EXTENSIONS) {
    await t.test(ext, () => {
      const root = makeRoot();
      plant(root, `src/app/g${ext}`, fromLine('../../../core/secret'));
      assertFail(run(['--root', root]), `FAIL outside-web: src/app/g${ext}`);
    });
  }
});

test('style extensions', async (t) => {
  for (const ext of STYLE_EXTENSIONS) {
    await t.test(ext, () => {
      const root = makeRoot();
      plant(root, `src/app/s${ext}`, `@${IMP} "../../../x";\n`);
      assertFail(run(['--root', root]), `FAIL outside-web: src/app/s${ext}`);
    });
  }
});

test('other extensions are not read', () => {
  const root = makeRoot();
  const text = fromLine(OUTSIDE);
  plant(root, 'src/app/n.txt', text);
  plant(root, 'src/app/n.json', text);
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('depth is counted from the file', async (t) => {
  await t.test('src/a.ts leaves', () => {
    const root = makeRoot();
    plant(root, 'src/a.ts', fromLine('../../x'));
    assertFail(run(['--root', root]), 'FAIL outside-web: src/a.ts');
  });
  await t.test('src/app/b.ts stays', () => {
    const root = makeRoot();
    plant(root, 'src/app/b.ts', fromLine('../../x'));
    const result = run(['--root', root]);
    assert.equal(result.status, 0, result.stdout);
    assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
  });
  await t.test('src/app/b.ts leaves', () => {
    const root = makeRoot();
    plant(root, 'src/app/b.ts', fromLine('../../../x'));
    assertFail(run(['--root', root]), 'FAIL outside-web: src/app/b.ts');
  });
});

test('symbolic link out', () => {
  const root = makeRoot();
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-out-'));
  fs.writeFileSync(path.join(outside, 'secret.ts'), 'export const value = 1;\n');
  fs.symlinkSync(outside, path.join(root, 'src', 'linked'));
  plant(root, 'src/app/use.ts', fromLine('../linked/secret.ts'));
  assertFail(run(['--root', root]), 'FAIL outside-web');
});

test('forbidden package names', async (t) => {
  for (const spec of FORBIDDEN) {
    await t.test(spec, () => {
      const root = makeRoot();
      plant(root, 'src/app/p.ts', fromLine(spec));
      assertFail(run(['--root', root]), 'FAIL forbidden-package');
    });
  }
});

test('scoped and other bare packages', () => {
  const root = makeRoot();
  const lines = [
    fromLine('@scope/core'),
    fromLine('react'),
    fromLine('node:path'),
    fromLine('data:text/plain,a'),
  ];
  plant(root, 'src/app/p.ts', lines.join(''));
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('absolute and file forms', async (t) => {
  for (const spec of ABSOLUTE) {
    await t.test(JSON.stringify(spec), () => {
      const root = makeRoot();
      plant(root, 'src/app/p.ts', fromLine(spec));
      assertFail(run(['--root', root]), 'FAIL absolute-path');
    });
  }
});

test('root-relative inside web', () => {
  const root = makeRoot();
  plant(root, 'src/app/p.ts', fromLine('/src/app/App'));
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.match(result.stdout.trim().split('\n').at(-1), /OK$/);
});

test('tsconfig outside', async (t) => {
  const cases = [
    ['include', { include: ['../core'] }],
    ['exclude', { include: ['src'], exclude: ['../core'] }],
    ['files', { include: ['src'], files: ['../core'] }],
    ['extends string', { include: ['src'], extends: '../core' }],
    ['extends array', { include: ['src'], extends: ['../core'] }],
    ['references', { include: ['src'], references: [{ path: '../core' }] }],
    ['rootDirs', { include: ['src'], compilerOptions: { rootDirs: ['../core'] } }],
    ['typeRoots', { include: ['src'], compilerOptions: { typeRoots: ['../core'] } }],
    ['paths', { include: ['src'], compilerOptions: { paths: { a: ['../core/x'] } } }],
    ['baseUrl', { include: ['src'], compilerOptions: { baseUrl: '..' } }],
  ];
  for (const [name, body] of cases) {
    await t.test(name, () => {
      const root = makeRoot();
      fs.writeFileSync(path.join(root, 'tsconfig.json'), `${JSON.stringify(body)}\n`);
      assertFail(run(['--root', root]), 'FAIL tsconfig-outside');
    });
  }
});

test('tsconfig inside', () => {
  const root = makeRoot();
  fs.writeFileSync(
    path.join(root, 'tsconfig.json'),
    `${JSON.stringify({
      include: ['src'],
      compilerOptions: { paths: { a: ['./src/x'] }, baseUrl: '.' },
    })}\n`,
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
  const root = path.join(os.tmpdir(), 'n'.repeat(LONG_NAME_LENGTH));
  const result = run(['--root', root]);
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
  plant(root, 'src/app/inside.ts', fromLine('./local'));
  const before = snapshot(root);
  const result = run(['--root', root]);
  assert.equal(result.status, 0, result.stdout);
  assert.equal(snapshot(root), before);
});
