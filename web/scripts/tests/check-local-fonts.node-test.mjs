import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '..', '..');
const SCRIPT = path.join(WEB, 'scripts', 'check-local-fonts.mjs');
const PASS_TAIL = /^checked \d+ css files: OK$/;

const root = fs.mkdtempSync(
  path.join(os.tmpdir(), 'eii-test-check-local-fonts-'),
);
after(() => fs.rmSync(root, { recursive: true, force: true }));

function run(args) {
  return spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: 'utf8',
    env: {
      PATH: process.env.PATH,
      HOME: process.env.HOME,
      TMPDIR: process.env.TMPDIR,
      TMP: process.env.TMP,
      TEMP: process.env.TEMP,
      LANG: 'C',
    },
  });
}

function licenceBytes(name) {
  return fs.readFileSync(
    path.join(WEB, 'node_modules', '@fontsource', name, 'LICENSE'),
  );
}

const FACE_LATIN =
  "@font-face{font-family:'IBM Plex Sans';font-style:normal;" +
  "font-weight:400;src:url(/assets/latin-400.woff2) format('woff2');}";
const FACE_ARABIC =
  "@font-face{font-family:'IBM Plex Sans Arabic';font-style:normal;" +
  "font-weight:400;src:url('./arabic-400.woff2') format('woff2');}";

function makeDist(css) {
  const home = fs.mkdtempSync(path.join(root, 'eii-fonts-'));
  fs.mkdirSync(path.join(home, 'dist', 'assets'), { recursive: true });
  fs.mkdirSync(path.join(home, 'dist', 'licences'), { recursive: true });
  fs.writeFileSync(path.join(home, 'dist', 'index.html'), '<!doctype html>\n');
  fs.writeFileSync(path.join(home, 'dist', 'assets', 'a.css'), css);
  fs.writeFileSync(path.join(home, 'dist', 'assets', 'latin-400.woff2'), 'lf');
  fs.writeFileSync(path.join(home, 'dist', 'assets', 'arabic-400.woff2'), 'af');
  fs.writeFileSync(
    path.join(home, 'dist', 'licences', 'ibm-plex-sans.txt'),
    licenceBytes('ibm-plex-sans'),
  );
  fs.writeFileSync(
    path.join(home, 'dist', 'licences', 'ibm-plex-sans-arabic.txt'),
    licenceBytes('ibm-plex-sans-arabic'),
  );
  return home;
}

function cleanFonts() {
  return makeDist(FACE_LATIN + FACE_ARABIC);
}

function assertPass(result) {
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stdout.trim().split('\n').at(-1), PASS_TAIL);
}

function assertFail(result, line) {
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  assert.ok(result.stdout.split('\n').includes(line), result.stdout);
}

function snapshot(home) {
  const rows = [];
  const walk = (dir) => {
    for (const name of fs.readdirSync(dir).sort()) {
      const full = path.join(dir, name);
      const info = fs.lstatSync(full);
      const rel = path.relative(home, full).split(path.sep).join('/');
      if (info.isDirectory()) {
        rows.push(`dir ${rel}`);
        walk(full);
      } else {
        rows.push(`file ${rel} ${info.size}`);
      }
    }
  };
  walk(home);
  return rows.join('\n');
}

test('clean built fonts pass', () => {
  assertPass(run(['--root', cleanFonts(), '--dist']));
});

test('a font file missing from the built output fails', () => {
  const home = cleanFonts();
  fs.rmSync(path.join(home, 'dist', 'assets', 'latin-400.woff2'));
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL font-file-missing: dist/assets/a.css:1: /assets/latin-400.woff2',
  );
});

test('an external font URL fails', () => {
  const css =
    FACE_LATIN.replace(
      '/assets/latin-400.woff2',
      'https://fonts.example/x.woff2',
    ) + FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-url-external: dist/assets/a.css:1: https://fonts.example/x.woff2',
  );
});

test('a protocol-relative font URL fails', () => {
  const css =
    FACE_LATIN.replace('/assets/latin-400.woff2', '//fonts.example/x.woff2') +
    FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-url-external: dist/assets/a.css:1: //fonts.example/x.woff2',
  );
});

test('an embedded data font URL fails', () => {
  const css =
    FACE_LATIN.replace('/assets/latin-400.woff2', 'data:font/woff2;base64,AA') +
    FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-url-embedded: dist/assets/a.css:1: data:font/woff2;base64,AA',
  );
});

test('a missing font licence text fails', () => {
  const home = cleanFonts();
  fs.rmSync(path.join(home, 'dist', 'licences', 'ibm-plex-sans.txt'));
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL font-licence-missing: dist/licences/ibm-plex-sans.txt',
  );
});

test('a font licence text with one byte changed fails', () => {
  const home = cleanFonts();
  const bytes = Buffer.from(licenceBytes('ibm-plex-sans-arabic'));
  bytes[0] = bytes[0] === 0x41 ? 0x42 : 0x41;
  fs.writeFileSync(
    path.join(home, 'dist', 'licences', 'ibm-plex-sans-arabic.txt'),
    bytes,
  );
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL font-licence-changed: dist/licences/ibm-plex-sans-arabic.txt',
  );
});

test('a built output without any font face fails', () => {
  assertFail(
    run(['--root', makeDist('a{color:red}'), '--dist']),
    'FAIL font-face-absent: dist: no @font-face rule',
  );
});

test('a missing typeface family fails', () => {
  assertFail(
    run(['--root', makeDist(FACE_LATIN), '--dist']),
    'FAIL font-family-missing: dist: IBM Plex Sans Arabic',
  );
});

test('a font face without a served file fails', () => {
  const css =
    "@font-face{font-family:'IBM Plex Sans';" +
    "src:local('IBM Plex Sans');}" +
    FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-face-no-file: dist/assets/a.css:1: IBM Plex Sans',
  );
});

test('an external font import fails', () => {
  const css =
    '@import url(https://fonts.example/x.css);' + FACE_LATIN + FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-import-external: dist/assets/a.css:1: https://fonts.example/x.css',
  );
});

test('a missing local font import fails', () => {
  const css = '@import url(/missing.css);' + FACE_LATIN + FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-import-missing: dist/assets/a.css:1: /missing.css',
  );
});

test('dist missing fails', () => {
  const home = fs.mkdtempSync(path.join(root, 'eii-fonts-empty-'));
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL dist-missing: dist: absent',
  );
});

test('dist that is not a directory fails', () => {
  const home = fs.mkdtempSync(path.join(root, 'eii-fonts-file-'));
  fs.writeFileSync(path.join(home, 'dist'), 'not a directory');
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL dist-missing: dist: not a directory',
  );
});

test('an unreadable css symlink fails', () => {
  const home = cleanFonts();
  fs.symlinkSync(
    path.join(home, 'missing-target'),
    path.join(home, 'dist', 'assets', 'broken.css'),
  );
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL unreadable-file: dist/assets/broken.css: ENOENT',
  );
});

test('an unreadable css file fails', () => {
  const home = cleanFonts();
  const file = path.join(home, 'dist', 'assets', 'locked.css');
  fs.writeFileSync(file, FACE_LATIN);
  fs.chmodSync(file, 0o000);
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL unreadable-file: dist/assets/locked.css: EACCES',
  );
});

test('usage', async (t) => {
  await t.test('the check needs --dist', () => {
    const result = run(['--root', WEB]);
    assert.equal(result.status, 2, result.stdout);
    assert.equal(result.stdout, 'USAGE: the font check needs --dist\n');
  });
  await t.test('unknown flag', () => {
    const result = run(['--not-a-flag']);
    assert.equal(result.status, 2, result.stdout);
    assert.equal(result.stdout, 'USAGE: unknown flag --not-a-flag\n');
  });
  await t.test('root without a value', () => {
    const result = run(['--dist', '--root']);
    assert.equal(result.status, 2, result.stdout);
    assert.equal(result.stdout, 'USAGE: flag --root needs a value\n');
  });
  await t.test('root is not a directory', () => {
    const file = path.join(root, 'not-a-directory.txt');
    fs.writeFileSync(file, 'x');
    const result = run(['--root', file, '--dist']);
    assert.equal(result.status, 2, result.stdout);
    assert.equal(result.stdout, 'USAGE: root is not a directory\n');
  });
  await t.test('root does not exist', () => {
    const result = run(['--root', path.join(root, 'no-such-root'), '--dist']);
    assert.equal(result.status, 2, result.stdout);
    assert.equal(result.stdout, 'USAGE: root is not a directory\n');
  });
});

test('internal error', () => {
  const longName = path.join(root, 'n'.repeat(300));
  const result = run(['--root', longName, '--dist']);
  assert.equal(result.status, 1);
  assert.equal(
    result.stdout,
    'FAIL internal-error: ENAMETOOLONG: name too long, stat\n',
  );
  assert.equal(`${result.stdout}${result.stderr}`.includes('    at '), false);
});

test('reads only', () => {
  const home = cleanFonts();
  const before = snapshot(home);
  const result = run(['--root', home, '--dist']);
  assert.equal(result.status, 0, result.stdout);
  assert.equal(snapshot(home), before);
});
