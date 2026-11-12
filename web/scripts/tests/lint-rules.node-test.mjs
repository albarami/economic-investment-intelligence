import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, describe, test } from 'node:test';

const WEB = path.resolve(import.meta.dirname, '../..');
const TIMEOUT_MS = 300000;

const copies = [];
after(() => {
  for (const tmp of copies) {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

function makeCopy() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-web-lint-'));
  copies.push(tmp);
  const copy = path.join(tmp, 'web');
  fs.mkdirSync(copy, { recursive: true });
  for (const name of [
    'eslint.config.js',
    '.prettierrc.json',
    '.prettierignore',
    'index.html',
    'package.json',
    'package-lock.json',
    'tsconfig.json',
    'vite.config.ts',
  ]) {
    fs.copyFileSync(path.join(WEB, name), path.join(copy, name));
  }
  for (const dir of ['src', 'scripts']) {
    fs.cpSync(path.join(WEB, dir), path.join(copy, dir), { recursive: true });
  }
  fs.symlinkSync(
    path.join(WEB, 'node_modules'),
    path.join(copy, 'node_modules'),
  );
  return copy;
}

function cleanEnv(tmp) {
  const userconfig = path.join(tmp, 'npm-userconfig');
  const globalconfig = path.join(tmp, 'npm-globalconfig');
  fs.writeFileSync(userconfig, '');
  fs.writeFileSync(globalconfig, '');
  return {
    PATH: process.env.PATH,
    HOME: tmp,
    TMPDIR: tmp,
    LANG: 'C',
    npm_config_userconfig: userconfig,
    npm_config_globalconfig: globalconfig,
    npm_config_update_notifier: 'false',
  };
}

function npmRun(copy, script, args, env) {
  return spawnSync('npm', ['run', script, '--silent', '--', ...args], {
    cwd: copy,
    env,
    encoding: 'utf8',
    timeout: TIMEOUT_MS,
  });
}

function tool(copy, bin, args, env) {
  const file = path.join(copy, 'node_modules', bin);
  return spawnSync(process.execPath, [file, ...args], {
    cwd: copy,
    env,
    encoding: 'utf8',
    timeout: TIMEOUT_MS,
  });
}

function writeFile(copy, rel, text) {
  const full = path.join(copy, rel);
  fs.mkdirSync(path.dirname(full), { recursive: true });
  fs.writeFileSync(full, text);
}

function lintFiles(copy, result) {
  const data = JSON.parse(result.stdout);
  return data
    .map((entry) =>
      path.relative(copy, entry.filePath).split(path.sep).join('/'),
    )
    .sort();
}

function lintMessages(copy, result) {
  const data = JSON.parse(result.stdout);
  const rows = [];
  for (const entry of data) {
    const rel = path.relative(copy, entry.filePath).split(path.sep).join('/');
    for (const msg of entry.messages) {
      rows.push([rel, msg.ruleId, msg.severity, msg.line]);
    }
  }
  rows.sort(
    (a, b) =>
      a[0].localeCompare(b[0]) ||
      a[3] - b[3] ||
      String(a[1]).localeCompare(String(b[1])),
  );
  return rows;
}

function runLint(copy, env) {
  const result = npmRun(copy, 'lint', ['--format', 'json'], env);
  const messages = result.stdout.trim() ? lintMessages(copy, result) : [];
  return { result, messages };
}

describe('lint-rules', () => {
  test('scripts wiring', () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.join(WEB, 'package.json'), 'utf8'),
    );
    assert.equal(pkg.scripts.lint, 'eslint --max-warnings 0 .');
    assert.equal(pkg.scripts.build, 'tsc --noEmit && vite build');
  });

  test('config extends recommended sets', () => {
    const config = fs.readFileSync(path.join(WEB, 'eslint.config.js'), 'utf8');
    assert.ok(config.includes('extends: [js.configs.recommended]'));
    assert.ok(
      config.includes('tseslint.configs.recommended') &&
        config.includes('reactHooks.configs.flat.recommended'),
    );
  });

  test('clean copy passes', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    const { result, messages } = runLint(copy, env);
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
    assert.equal(messages.length, 0);
  });

  test('rules have teeth', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    writeFile(copy, 'src/app/p_debugger.ts', 'debugger;\n');
    writeFile(copy, 'src/app/p_js.js', 'debugger;\n');
    writeFile(copy, 'scripts/p_debugger.mjs', 'debugger;\n');
    writeFile(copy, 'scripts/p_unused.mjs', 'const unused = 1;\n');
    writeFile(copy, 'src/app/p_any.ts', 'export const a: any = 1;\n');
    writeFile(copy, 'src/app/p_unused.ts', 'const unused = 1;\n');
    writeFile(
      copy,
      'src/app/p_hooks.tsx',
      "import { useState } from 'react';\n" +
        'export function C({ on }: { on: boolean }) {\n' +
        '  if (on) { useState(0); }\n  return null;\n}\n',
    );
    writeFile(
      copy,
      'src/app/p_directive.ts',
      `/* ${'eslint'}-disable no-debugger */\nexport const x = 1;\n`,
    );
    const { result, messages } = runLint(copy, env);
    assert.equal(result.status, 1);
    const pick = (suffix) => messages.filter((row) => row[0].endsWith(suffix));
    for (const name of ['p_debugger.ts', 'p_js.js', 'p_debugger.mjs']) {
      const rows = pick(name);
      assert.equal(rows.length, 1);
      assert.equal(rows[0][1], 'no-debugger');
      assert.equal(rows[0][2], 2);
      assert.equal(rows[0][3], 1);
    }
    const unusedMjs = pick('p_unused.mjs');
    assert.equal(unusedMjs[0][1], 'no-unused-vars');
    assert.deepEqual(
      messages.filter((row) => row[0] === 'src/app/p_any.ts'),
      [['src/app/p_any.ts', '@typescript-eslint/no-explicit-any', 2, 1]],
    );
    assert.deepEqual(
      messages.filter((row) => row[0] === 'src/app/p_unused.ts'),
      [['src/app/p_unused.ts', '@typescript-eslint/no-unused-vars', 2, 1]],
    );
    const hooks = messages.find((row) => row[0] === 'src/app/p_hooks.tsx');
    assert.equal(hooks[1], 'react-hooks/rules-of-hooks');
    const directive = messages.find(
      (row) => row[0] === 'src/app/p_directive.ts',
    );
    assert.equal(directive[1], null);
    assert.equal(directive[2], 1);
    const watched = new Set([
      'src/app/p_debugger.ts',
      'src/app/p_js.js',
      'scripts/p_debugger.mjs',
      'scripts/p_unused.mjs',
      'src/app/p_any.ts',
      'src/app/p_unused.ts',
      'src/app/p_hooks.tsx',
      'src/app/p_directive.ts',
    ]);
    for (const row of messages) {
      if (!watched.has(row[0])) {
        assert.fail(`unexpected lint message for ${row[0]}`);
      }
    }
  });

  test('warnings fail', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    writeFile(
      copy,
      'src/app/p_deps.tsx',
      'import { useEffect, useState } from "react";\n' +
        'export function C() {\n  const [value] = useState(0);\n' +
        '  useEffect(() => { document.title = String(value); }, []);\n  return null;\n}\n',
    );
    const { result, messages } = runLint(copy, env);
    assert.equal(result.status, 1);
    const dep = messages.filter(
      (row) => row[1] === 'react-hooks/exhaustive-deps',
    );
    assert.equal(dep.length, 1);
    assert.equal(dep[0][2], 1);
    assert.equal(messages.length, 1);
  });

  test('jsx files parse', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    writeFile(copy, 'src/app/p_jsx.jsx', 'export const el = <main />;\n');
    writeFile(copy, 'src/app/p_jsx.js', 'export const el = <main />;\n');
    let { result, messages } = runLint(copy, env);
    assert.equal(result.status, 0);
    assert.equal(messages.length, 0);
    const configPath = path.join(copy, 'eslint.config.js');
    const config = fs.readFileSync(configPath, 'utf8');
    const stripped = config.replace(
      'parserOptions: { ecmaFeatures: { jsx: true } },',
      '',
    );
    assert.notEqual(stripped, config);
    fs.writeFileSync(configPath, stripped);
    ({ result, messages } = runLint(copy, env));
    assert.equal(result.status, 1);
    for (const name of ['src/app/p_jsx.jsx', 'src/app/p_jsx.js']) {
      const rows = messages.filter((row) => row[0] === name);
      assert.equal(rows.length, 1);
      assert.equal(rows[0][1], null);
      assert.equal(rows[0][2], 2);
    }
  });

  test('unlisted extensions are not linted', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    writeFile(copy, 'src/app/p.vue', 'debugger;\n');
    writeFile(copy, 'src/app/p.foo', 'debugger;\n');
    writeFile(copy, 'x.json', '[1]\n');
    const { result, messages } = runLint(copy, env);
    assert.equal(result.status, 0);
    const paths = new Set(messages.map((row) => row[0]));
    for (const name of ['src/app/p.vue', 'src/app/p.foo', 'x.json']) {
      assert.equal(paths.has(name), false);
    }
    const direct = tool(
      copy,
      'eslint/bin/eslint.js',
      ['--max-warnings', '0', 'src/app/p.foo'],
      env,
    );
    assert.equal(direct.status, 1);
    assert.ok(
      `${direct.stdout}\n${direct.stderr}`.includes(
        'no matching configuration',
      ),
    );
  });

  test('ignores are the closed list', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    fs.mkdirSync(path.join(copy, 'dist'), { recursive: true });
    writeFile(copy, 'dist/p.js', 'debugger;\n');
    const { result } = runLint(copy, env);
    assert.equal(result.status, 0);
    const files = lintFiles(copy, result);
    for (const rel of files) {
      assert.equal(rel.startsWith('dist/'), false);
      assert.equal(rel.includes('node_modules'), false);
    }
    assert.ok(files.some((rel) => rel.startsWith('scripts/')));
  });

  test('missing and malformed config', async (t) => {
    await t.test('deleted config', () => {
      const copy = makeCopy();
      const env = cleanEnv(path.dirname(copy));
      fs.rmSync(path.join(copy, 'eslint.config.js'));
      const { result } = runLint(copy, env);
      assert.equal(result.status, 2);
    });
    await t.test('syntax error', () => {
      const copy = makeCopy();
      const env = cleanEnv(path.dirname(copy));
      fs.writeFileSync(
        path.join(copy, 'eslint.config.js'),
        'export default [;\n',
      );
      const { result } = runLint(copy, env);
      assert.equal(result.status, 2);
    });
    await t.test('missing pattern', () => {
      const copy = makeCopy();
      const env = cleanEnv(path.dirname(copy));
      const direct = tool(copy, 'eslint/bin/eslint.js', ['nonexist'], env);
      assert.equal(direct.status, 2);
    });
    await t.test('unknown rule in config', () => {
      const copy = makeCopy();
      const env = cleanEnv(path.dirname(copy));
      const text = fs.readFileSync(path.join(copy, 'eslint.config.js'), 'utf8');
      fs.writeFileSync(
        path.join(copy, 'eslint.config.js'),
        text.replace("'no-restricted-globals'", "'no-such-rule-xyz'"),
      );
      const direct = tool(copy, 'eslint/bin/eslint.js', ['.'], env);
      assert.equal(direct.status, 2);
    });
    await t.test('misspelt checkGlobalObject', () => {
      const copy = makeCopy();
      const env = cleanEnv(path.dirname(copy));
      const text = fs.readFileSync(path.join(copy, 'eslint.config.js'), 'utf8');
      fs.writeFileSync(
        path.join(copy, 'eslint.config.js'),
        text.replace('checkGlobalObject', 'checkGlobalObjectX'),
      );
      const direct = tool(copy, 'eslint/bin/eslint.js', ['.'], env);
      assert.equal(direct.status, 2);
    });
    await t.test('unknown rule in directive', () => {
      const copy = makeCopy();
      const env = cleanEnv(path.dirname(copy));
      const rule = 'no-such-rule-abc';
      writeFile(
        copy,
        'src/app/p_bad_directive.ts',
        `/* ${'eslint'}-disable ${rule} */\nexport const x = 1;\n`,
      );
      const { result, messages } = runLint(copy, env);
      assert.equal(result.status, 1);
      const row = messages.find(
        (entry) => entry[0] === 'src/app/p_bad_directive.ts',
      );
      assert.equal(row[1], rule);
      assert.equal(row[2], 2);
    });
  });
});
