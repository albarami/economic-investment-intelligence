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
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-web-typecheck-'));
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

function tscDiagnostics(text) {
  const rows = [];
  const re = /^(.+)\((\d+),\d+\): error (TS\d+):/gm;
  let match = re.exec(text);
  while (match !== null) {
    rows.push([match[1], Number(match[2]), match[3]]);
    match = re.exec(text);
  }
  rows.sort(
    (a, b) =>
      a[0].localeCompare(b[0]) || a[1] - b[1] || a[2].localeCompare(b[2]),
  );
  return rows;
}

describe('typecheck', () => {
  test('scripts wiring', () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.join(WEB, 'package.json'), 'utf8'),
    );
    assert.equal(pkg.scripts.typecheck, 'tsc --noEmit');
    assert.equal(typeof tool, 'function');
  });

  test('clean copy passes', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    const result = npmRun(copy, 'typecheck', [], env);
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  });

  test('rules have teeth', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    writeFile(
      copy,
      'src/app/p_assign.ts',
      "export const a: number = 'text';\n",
    );
    writeFile(copy, 'src/app/p_implicit.ts', 'export const f = (x) => x;\n');
    writeFile(
      copy,
      'src/app/p_unused.ts',
      'export function g(): number {\n  const unused = 1;\n  return 2;\n}\n',
    );
    const result = npmRun(copy, 'typecheck', [], env);
    assert.equal(result.status, 2, `${result.stdout}\n${result.stderr}`);
    const text = `${result.stdout}\n${result.stderr}`;
    const diag = tscDiagnostics(text);
    assert.deepEqual(diag, [
      ['src/app/p_assign.ts', 1, 'TS2322'],
      ['src/app/p_implicit.ts', 1, 'TS7006'],
      ['src/app/p_unused.ts', 2, 'TS6133'],
    ]);
  });

  test('missing tsconfig', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    fs.rmSync(path.join(copy, 'tsconfig.json'));
    const result = npmRun(copy, 'typecheck', [], env);
    assert.equal(result.status, 1);
    const text = `${result.stdout}\n${result.stderr}`;
    assert.equal(text.includes('error TS'), false);
    assert.match(text, /^tsc: The TypeScript Compiler/m);
  });
});
