import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, describe, test } from 'node:test';

const WEB = path.resolve(import.meta.dirname, '../..');
const TIMEOUT_MS = 300000;

const FORMS = [
  ['f1', "fetch('/x')"],
  ['f2', 'fetch'],
  ['f3', "window.fetch('/x')"],
  ['f4', "globalThis.fetch('/x')"],
  ['f5', "self.fetch('/x')"],
  ['f6', "new EventSource('/x')"],
  ['f7', "new window.EventSource('/x')"],
  ['f8', "new globalThis.EventSource('/x')"],
  ['f9', "new self.EventSource('/x')"],
];

const REPORTED_DIRS = [
  'src/app',
  'src/apix',
  'src/app/api',
  'tests/unit',
  'scripts',
  '',
];

const EXTENSIONS = ['js', 'mjs', 'cjs', 'jsx', 'ts', 'mts', 'cts', 'tsx'];

const ALLOWED_API_DIRS = ['src/api', 'src/api/generated'];

const FETCH_MSG =
  "Unexpected use of 'fetch'. FE-11: call the backend only through src/api/.";
const EVENT_MSG =
  "Unexpected use of 'EventSource'. FE-11: open event streams only through src/api/.";

const copies = [];
after(() => {
  for (const tmp of copies) {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

function makeCopy() {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-web-fe11-'));
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

function bodyForForm(expr, ext) {
  if (ext === 'cjs' || ext === 'cts') {
    return `module.exports = ${expr};\n`;
  }
  return `export const r = ${expr};\n`;
}

function plantReported(copy) {
  const files = [];
  for (const dir of REPORTED_DIRS) {
    for (const [form, expr] of FORMS) {
      const rel = dir ? `${dir}/fe11_${form}.ts` : `fe11_${form}.ts`;
      writeFile(copy, rel, bodyForForm(expr, 'ts'));
      files.push(rel);
    }
  }
  writeFile(copy, 'src/api.ts', bodyForForm(FORMS[0][1], 'ts'));
  files.push('src/api.ts');
  for (let index = 1; index <= 9; index += 1) {
    const expr = FORMS[index - 1][1];
    const rel = `src/api.${index}.ts`;
    writeFile(copy, rel, bodyForForm(expr, 'ts'));
    files.push(rel);
  }
  for (const ext of EXTENSIONS) {
    for (const [form, expr] of FORMS) {
      const rel = `src/ext/e_${form}.${ext}`;
      writeFile(copy, rel, bodyForForm(expr, ext));
      files.push(rel);
    }
  }
  return files;
}

function plantAllowed(copy) {
  const files = [];
  for (const dir of ALLOWED_API_DIRS) {
    for (const [form, expr] of FORMS) {
      const rel = `${dir}/fe11_${form}.ts`;
      writeFile(copy, rel, bodyForForm(expr, 'ts'));
      files.push(rel);
    }
  }
  for (const ext of EXTENSIONS) {
    const expr = FORMS[0][1];
    const rel = `src/api/e_f1.${ext}`;
    writeFile(copy, rel, bodyForForm(expr, ext));
    files.push(rel);
  }
  return files;
}

function plantNotRestricted(copy) {
  writeFile(
    copy,
    'src/app/nr_xhr.ts',
    'export const r = new XMLHttpRequest();\n',
  );
  writeFile(copy, 'src/app/nr_ws.ts', "export const r = new WebSocket('x');\n");
}

function lintDetails(copy, result) {
  const data = JSON.parse(result.stdout);
  const byFile = new Map();
  const all = [];
  for (const entry of data) {
    const rel = path.relative(copy, entry.filePath).split(path.sep).join('/');
    const msgs = entry.messages.map((msg) => ({
      ruleId: msg.ruleId,
      severity: msg.severity,
      line: msg.line,
      text: msg.message,
    }));
    byFile.set(rel, msgs);
    for (const msg of msgs) {
      all.push([rel, msg.ruleId, msg.severity, msg.line, msg.text]);
    }
  }
  all.sort((a, b) => a[0].localeCompare(b[0]) || a[3] - b[3]);
  return { byFile, all };
}

function runLint(copy, env) {
  return npmRun(copy, 'lint', ['--format', 'json'], env);
}

describe('lint-fe11', () => {
  test('config carries FE-11 messages', () => {
    const config = fs.readFileSync(path.join(WEB, 'eslint.config.js'), 'utf8');
    assert.ok(
      config.includes('FE-11: call the backend only through src/api/.'),
    );
    assert.ok(
      config.includes('FE-11: open event streams only through src/api/.'),
    );
  });

  test('helpers wired', () => {
    assert.equal(typeof tool, 'function');
  });

  test('plant counts', () => {
    const copy = makeCopy();
    const reported = plantReported(copy);
    const allowed = plantAllowed(copy);
    plantNotRestricted(copy);
    assert.equal(reported.length, 136);
    assert.equal(allowed.length, 26);
    assert.equal(fs.existsSync(path.join(copy, 'src/app/nr_xhr.ts')), true);
    assert.equal(fs.existsSync(path.join(copy, 'src/app/nr_ws.ts')), true);
  });

  test('FE-11 reported', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    const reported = new Set(plantReported(copy));
    assert.equal(reported.size, 136);
    const result = runLint(copy, env);
    assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
    const { byFile, all } = lintDetails(copy, result);
    for (const rel of reported) {
      const msgs = byFile.get(rel) ?? [];
      assert.equal(msgs.length, 1, rel);
      assert.deepEqual(
        [msgs[0].ruleId, msgs[0].severity, msgs[0].line],
        ['no-restricted-globals', 2, 1],
      );
    }
    const f1 = byFile.get('src/app/fe11_f1.ts')?.[0]?.text;
    const f6 = byFile.get('src/app/fe11_f6.ts')?.[0]?.text;
    assert.equal(f1, FETCH_MSG);
    assert.equal(f6, EVENT_MSG);
    for (const [rel, ruleId, severity, line] of all) {
      if (!reported.has(rel)) {
        assert.fail(
          `unexpected message in ${rel}: ${ruleId} ${severity} ${line}`,
        );
      }
    }
  });

  test('FE-11 allowed alone', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    const allowed = new Set(plantAllowed(copy));
    assert.equal(allowed.size, 26);
    const result = runLint(copy, env);
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
    const stdout = result.stdout.trim();
    if (stdout) {
      const { all } = lintDetails(copy, result);
      assert.equal(all.length, 0);
    }
  });

  test('FE-11 not restricted', () => {
    const copy = makeCopy();
    const env = cleanEnv(path.dirname(copy));
    plantNotRestricted(copy);
    const result = runLint(copy, env);
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
    const stdout = result.stdout.trim();
    if (stdout) {
      const { all } = lintDetails(copy, result);
      assert.equal(all.length, 0);
    }
  });
});
