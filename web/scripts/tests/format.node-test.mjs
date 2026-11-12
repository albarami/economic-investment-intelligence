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
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-web-format-'));
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

function warnPaths(output) {
  return output
    .split('\n')
    .filter(
      (line) =>
        line.startsWith('[warn] ') && !line.includes('Code style issues found'),
    )
    .map((line) => line.slice('[warn] '.length).trim())
    .sort();
}

describe('format', () => {
  test('scripts wiring', () => {
    const pkg = JSON.parse(
      fs.readFileSync(path.join(WEB, 'package.json'), 'utf8'),
    );
    assert.equal(
      pkg.scripts['format:check'],
      'prettier --check --no-editorconfig .',
    );
    assert.equal(pkg.scripts.format, 'prettier --write --no-editorconfig .');
    const rc = JSON.parse(
      fs.readFileSync(path.join(WEB, '.prettierrc.json'), 'utf8'),
    );
    assert.deepEqual(rc, { singleQuote: true });
    const ignore = fs.readFileSync(path.join(WEB, '.prettierignore'), 'utf8');
    for (const line of ['dist/', 'package-lock.json', '*.md']) {
      assert.ok(ignore.includes(line), line);
    }
  });

  test('clean copy passes', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    const result = npmRun(copy, 'format:check', [], env);
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
    const text = `${result.stdout}\n${result.stderr}`;
    assert.ok(text.includes('All matched files use Prettier code style!'));
  });

  test('rules have teeth', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    writeFile(copy, 'src/app/p_quotes.ts', 'export const a = "x";\n');
    writeFile(copy, 'src/app/p_spaces.ts', 'export const  b =  1;\n');
    writeFile(copy, 'src/app/p_semi.ts', 'export const c = 1\n');
    writeFile(
      copy,
      'src/app/p_indent.ts',
      'export function f() {\n    return 1;\n}\n',
    );
    writeFile(copy, 'src/app/p.json', '{"a":1}\n');
    writeFile(copy, 'src/app/p.css', 'a{color:red}\n');
    const result = npmRun(copy, 'format:check', [], env);
    assert.equal(result.status, 1);
    const paths = warnPaths(`${result.stdout}\n${result.stderr}`);
    assert.deepEqual(paths, [
      'src/app/p.css',
      'src/app/p.json',
      'src/app/p_indent.ts',
      'src/app/p_quotes.ts',
      'src/app/p_semi.ts',
      'src/app/p_spaces.ts',
    ]);
  });

  test('write mode', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    writeFile(copy, 'src/app/p_quotes.ts', 'export const a = "x";\n');
    writeFile(copy, 'src/app/p_spaces.ts', 'export const  b =  1;\n');
    writeFile(copy, 'src/app/p_semi.ts', 'export const c = 1\n');
    writeFile(
      copy,
      'src/app/p_indent.ts',
      'export function f() {\n    return 1;\n}\n',
    );
    writeFile(copy, 'src/app/p.json', '{"a":1}\n');
    writeFile(copy, 'src/app/p.css', 'a{color:red}\n');
    writeFile(copy, 'dist/p.js', 'const  a=1\n');
    writeFile(copy, 'notes.md', '#   Title\n');
    fs.writeFileSync(path.join(copy, 'package-lock.json'), '{"a":1}\n');
    const distBefore = fs.readFileSync(path.join(copy, 'dist/p.js'));
    const mdBefore = fs.readFileSync(path.join(copy, 'notes.md'));
    const fmt = npmRun(copy, 'format', [], env);
    assert.equal(fmt.status, 0, `${fmt.stdout}\n${fmt.stderr}`);
    const check = npmRun(copy, 'format:check', [], env);
    assert.equal(check.status, 0, `${check.stdout}\n${check.stderr}`);
    assert.equal(
      fs.readFileSync(path.join(copy, 'dist/p.js')).equals(distBefore),
      true,
    );
    assert.equal(
      fs.readFileSync(path.join(copy, 'notes.md')).equals(mdBefore),
      true,
    );
    assert.equal(
      fs.readFileSync(path.join(copy, 'package-lock.json')).toString(),
      '{"a":1}\n',
    );
  });

  test('ignored files', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    fs.mkdirSync(path.join(copy, 'dist'), { recursive: true });
    writeFile(copy, 'dist/p.js', 'const  a=1\n');
    writeFile(copy, 'notes.md', '#   Title\n');
    fs.writeFileSync(path.join(copy, 'package-lock.json'), '{"a":1}\n');
    const result = npmRun(copy, 'format:check', [], env);
    assert.equal(result.status, 0);
    const text = `${result.stdout}\n${result.stderr}`;
    assert.equal(text.includes('[warn]'), false);
    const direct = tool(
      copy,
      'prettier/bin/prettier.cjs',
      ['--check', '--no-editorconfig', 'dist/p.js'],
      env,
    );
    assert.equal(direct.status, 0);
  });

  test('nothing matched', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    const result = tool(
      copy,
      'prettier/bin/prettier.cjs',
      ['--check', '--no-editorconfig', 'nonexist'],
      env,
    );
    assert.equal(result.status, 2);
    const text = `${result.stdout}\n${result.stderr}`;
    assert.ok(text.includes('No files matching the pattern'));
  });

  test('editorconfig', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    writeFile(copy, '.editorconfig', '[*]\nindent_style = tab\n');
    writeFile(
      copy,
      'src/app/p_ok.ts',
      'export function f() {\n  return 1;\n}\n',
    );
    const scripted = npmRun(copy, 'format:check', [], env);
    assert.equal(scripted.status, 0);
    const direct = tool(
      copy,
      'prettier/bin/prettier.cjs',
      ['--check', 'src/app/p_ok.ts'],
      env,
    );
    assert.equal(direct.status, 1);
    const text = `${direct.stdout}\n${direct.stderr}`;
    assert.ok(text.includes('src/app/p_ok.ts'));
  });

  test('missing and malformed config', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    fs.writeFileSync(path.join(copy, '.prettierrc.json'), '{');
    const result = npmRun(copy, 'format:check', [], env);
    assert.equal(result.status, 2);
    const text = `${result.stdout}\n${result.stderr}`;
    assert.ok(text.includes('JSON Error'));
  });
});
