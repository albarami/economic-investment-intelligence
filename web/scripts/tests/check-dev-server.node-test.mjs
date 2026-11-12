import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { resolveViteBin } from '../check-dev-server.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '..', '..');
const SCRIPT = path.join(WEB, 'scripts', 'check-dev-server.mjs');
const LONG_NAME_LENGTH = 300;
const MAX_PORT = 65535;
const PAGE = '<!doctype html><script type="module" src="/main.js"></script>\n';

function cleanEnv(extra) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-env-'));
  const base = { PATH: process.env.PATH, HOME: home, TMPDIR: home, LANG: 'C' };
  return { ...base, ...extra };
}

function run(args) {
  return spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: 'utf8',
    env: cleanEnv(),
  });
}

function tempRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'eii-dev-'));
}

function writer(root) {
  const file = path.join(root, 'writer.mjs');
  fs.writeFileSync(file, "import fs from 'node:fs';\nconst name = 'started';\nfs.writeFileSync(name, '1');\n");
  return file;
}

function assertFail(result, prefix) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const hit = result.stdout.split('\n').some((line) => line.startsWith(prefix));
  assert.equal(hit, true, result.stdout);
}

function assertUsage(result) {
  assert.equal(result.status, 2, result.stdout + result.stderr);
  assert.ok(result.stdout.startsWith('USAGE: '), result.stdout);
}

test('real shell starts', { timeout: 60000 }, () => {
  const result = run(['--root', WEB]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /^PASS dev-server http:\/\/127\.0\.0\.1:/m);
});

test('minimal root starts', { timeout: 60000 }, () => {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  fs.writeFileSync(path.join(root, 'main.js'), 'export {}\n');
  const bin = resolveViteBin(WEB);
  const result = run(['--root', root, '--vite-bin', bin]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /^PASS dev-server http:\/\/127\.0\.0\.1:/m);
});

test('absent package.json uses the default flags', () => {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  fs.writeFileSync(path.join(root, 'main.js'), 'export {}\n');
  const bin = path.join(root, 'server.mjs');
  fs.writeFileSync(
    bin,
    [
      "import fs from 'node:fs';",
      "import http from 'node:http';",
      "import path from 'node:path';",
      'const args = process.argv.slice(2);',
      "fs.writeFileSync(path.join(process.cwd(), 'argv.json'), JSON.stringify(args));",
      "const port = Number(args[args.indexOf('--port') + 1]);",
      "const host = args[args.indexOf('--host') + 1];",
      'const server = http.createServer((req, res) => {',
      "  if (req.url.split('?')[0] === '/') {",
      "    res.writeHead(200, { 'Content-Type': 'text/html' });",
      "    res.end(fs.readFileSync(path.join(process.cwd(), 'index.html')));",
      '    return;',
      '  }',
      "  res.writeHead(200, { 'Content-Type': 'text/javascript' });",
      "  res.end('export {};');",
      '});',
      'server.listen(port, host, () => {',
      '  process.stdout.write(`  Local:   http://127.0.0.1:${port}/\\n`);',
      '});',
      '',
    ].join('\n'),
  );
  const result = run(['--root', root, '--vite-bin', bin]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const argv = JSON.parse(fs.readFileSync(path.join(root, 'argv.json'), 'utf8'));
  assert.deepEqual(argv.slice(0, -1), ['--host', '127.0.0.1', '--strictPort', '--port']);
  assert.match(argv.at(-1), /^\d+$/);
});

test('package.json not JSON', () => {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'package.json'), '{');
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  assertFail(run(['--root', root, '--vite-bin', writer(root)]), 'FAIL dev-script: package.json: not valid JSON');
  assert.equal(fs.existsSync(path.join(root, 'started')), false);
});

test('no scripts.dev', async (t) => {
  await t.test('scripts absent', () => {
    const root = tempRoot();
    fs.writeFileSync(path.join(root, 'package.json'), '{}\n');
    fs.writeFileSync(path.join(root, 'index.html'), PAGE);
    const result = run(['--root', root, '--vite-bin', writer(root)]);
    assertFail(result, 'FAIL dev-script: package.json: no scripts.dev string');
    assert.equal(fs.existsSync(path.join(root, 'started')), false);
  });
  await t.test('dev a number', () => {
    const root = tempRoot();
    fs.writeFileSync(path.join(root, 'package.json'), '{"scripts":{"dev":1}}\n');
    fs.writeFileSync(path.join(root, 'index.html'), PAGE);
    const result = run(['--root', root, '--vite-bin', writer(root)]);
    assertFail(result, 'FAIL dev-script: package.json: no scripts.dev string');
    assert.equal(fs.existsSync(path.join(root, 'started')), false);
  });
});

test('script flags wrong', async (t) => {
  const scripts = [
    'vite',
    'vite --host 0.0.0.0 --strictPort',
    'vite --host 127.0.0.1',
    'webpack --host 127.0.0.1 --strictPort',
    'vite --host=127.0.0.1 --strictPort',
    'vite --host 127.0.0.1 --strictPort --port 4000',
    'vite --host 127.0.0.1 --strictPort --port=4000',
    'vite --strictPort --host',
  ];
  for (const dev of scripts) {
    await t.test(dev, () => {
      const root = tempRoot();
      fs.writeFileSync(path.join(root, 'package.json'), JSON.stringify({ scripts: { dev } }));
      fs.writeFileSync(path.join(root, 'index.html'), PAGE);
      const result = run(['--root', root, '--vite-bin', writer(root)]);
      assertFail(result, 'FAIL dev-script: package.json');
      assert.equal(fs.existsSync(path.join(root, 'started')), false);
    });
  }
});

test('entry source faults', async (t) => {
  const pages = [
    ['no index.html', null],
    ['no module script', '<!doctype html><h1>shell</h1>\n'],
    ['two module scripts', '<script type="module" src="/a.js"></script><script type="module" src="/b.js"></script>\n'],
    ['module script without src', '<script type="module"></script>\n'],
    ['only a classic script', '<script src="/main.js"></script>\n'],
  ];
  for (const [name, html] of pages) {
    await t.test(name, () => {
      const root = tempRoot();
      fs.writeFileSync(
        path.join(root, 'package.json'),
        JSON.stringify({ scripts: { dev: 'vite --host 127.0.0.1 --strictPort' } }),
      );
      if (html !== null) fs.writeFileSync(path.join(root, 'index.html'), html);
      const result = run(['--root', root, '--vite-bin', writer(root)]);
      assertFail(result, 'FAIL entry-source: index.html');
      assert.equal(fs.existsSync(path.join(root, 'started')), false);
    });
  }
});

test('module script with a hosted src', () => {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'index.html'), '<script type="module" src="https://example.com/app.js"></script>\n');
  assertFail(run(['--root', root, '--vite-bin', writer(root)]), 'FAIL entry-source: index.html');
  assert.equal(fs.existsSync(path.join(root, 'started')), false);
});

test('bin field shape', async (t) => {
  const bodies = [
    ['object without vite', { bin: { other: 'server.mjs' } }],
    ['absent', {}],
    ['a number', { bin: 1 }],
    ['an empty string', { bin: '' }],
  ];
  for (const [name, body] of bodies) {
    await t.test(name, () => {
      const root = tempRoot();
      fs.writeFileSync(path.join(root, 'index.html'), PAGE);
      const pkg = path.join(root, 'node_modules', 'vite');
      fs.mkdirSync(pkg, { recursive: true });
      fs.writeFileSync(path.join(pkg, 'package.json'), `${JSON.stringify(body)}\n`);
      assertFail(
        run(['--root', root]),
        'FAIL start-failed: node_modules/vite/package.json: bin field is absent or has no entry named vite',
      );
    });
  }
});

test('vite package.json faults', async (t) => {
  await t.test('missing', () => {
    const root = tempRoot();
    fs.writeFileSync(path.join(root, 'index.html'), PAGE);
    assertFail(run(['--root', root]), 'FAIL start-failed: node_modules/vite/package.json');
  });
  await t.test('not JSON', () => {
    const root = tempRoot();
    fs.writeFileSync(path.join(root, 'index.html'), PAGE);
    const pkg = path.join(root, 'node_modules', 'vite');
    fs.mkdirSync(pkg, { recursive: true });
    fs.writeFileSync(path.join(pkg, 'package.json'), '{');
    assertFail(run(['--root', root]), 'FAIL start-failed: node_modules/vite/package.json');
  });
  await t.test('a folder', () => {
    const root = tempRoot();
    fs.writeFileSync(path.join(root, 'index.html'), PAGE);
    fs.mkdirSync(path.join(root, 'node_modules', 'vite', 'package.json'), { recursive: true });
    assertFail(run(['--root', root]), 'FAIL start-failed: node_modules/vite/package.json');
  });
});

test('bin target absent', () => {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  const pkg = path.join(root, 'node_modules', 'vite');
  fs.mkdirSync(pkg, { recursive: true });
  fs.writeFileSync(path.join(pkg, 'package.json'), '{"bin":"missing.mjs"}\n');
  assertFail(run(['--root', root]), 'FAIL start-failed: vite binary not found');
});

test('vite-bin absent', () => {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  const missing = path.join(root, 'missing.mjs');
  assertFail(run(['--root', root, '--vite-bin', missing]), 'FAIL start-failed: vite binary not found');
});

test('resolveViteBin', () => {
  const found = resolveViteBin(WEB);
  assert.equal(path.isAbsolute(found), true);
  assert.equal(fs.statSync(found).isFile(), true);
  const root = tempRoot();
  const pkg = path.join(root, 'node_modules', 'vite');
  fs.mkdirSync(pkg, { recursive: true });
  fs.writeFileSync(path.join(pkg, 'package.json'), '{"bin":1}\n');
  assert.throws(() => resolveViteBin(root), (error) => error.rule === 'start-failed');
});

test('symlink run', () => {
  const root = tempRoot();
  fs.writeFileSync(path.join(root, 'package.json'), '{"scripts":{"dev":"vite"}}\n');
  fs.writeFileSync(path.join(root, 'index.html'), PAGE);
  const linkParent = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-link-'));
  const link = path.join(linkParent, 'scripts');
  fs.symlinkSync(path.join(WEB, 'scripts'), link);
  const result = spawnSync(
    process.execPath,
    [path.join(link, 'check-dev-server.mjs'), '--root', root],
    { encoding: 'utf8', env: cleanEnv() },
  );
  assertFail(result, 'FAIL dev-script: package.json');
});

test('usage', async (t) => {
  const cases = [
    ['unknown flag', ['--not-a-flag']],
    ['root without a value', ['--root']],
    ['port without a value', ['--port']],
    ['timeout without a value', ['--timeout-ms']],
    ['vite-bin without a value', ['--vite-bin']],
    ['port zero', ['--port', '0']],
    ['port above the range', ['--port', String(MAX_PORT + 4465)]],
    ['port not a number', ['--port', 'abc']],
    ['timeout zero', ['--timeout-ms', '0']],
  ];
  for (const [name, args] of cases) {
    await t.test(name, () => {
      assertUsage(run(args));
    });
  }
});

test('internal error', () => {
  const root = path.join(os.tmpdir(), 'n'.repeat(LONG_NAME_LENGTH));
  const result = run(['--root', root]);
  assert.equal(result.status, 1);
  assert.equal(result.stdout, 'FAIL internal-error: ENAMETOOLONG: name too long, stat\n');
  assert.equal(`${result.stdout}${result.stderr}`.includes('    at '), false);
});
