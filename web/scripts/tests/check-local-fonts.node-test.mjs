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
const PASS_TAIL = /^checked \d+ files: OK$/;

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

function makeDist(css, html = '<!doctype html>\n') {
  const home = fs.mkdtempSync(path.join(root, 'eii-fonts-'));
  fs.mkdirSync(path.join(home, 'dist', 'assets'), { recursive: true });
  fs.mkdirSync(path.join(home, 'dist', 'licences'), { recursive: true });
  fs.writeFileSync(path.join(home, 'dist', 'index.html'), html);
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

// R1 — built HTML is scanned: preload links and inline styles reach the check.

test('an HTML preload of an embedded font fails', () => {
  const html =
    '<!doctype html><link rel="preload" as="font" type="font/woff2" ' +
    'href="data:font/woff2;base64,AA" crossorigin>';
  assertFail(
    run(['--root', makeDist(FACE_LATIN + FACE_ARABIC, html), '--dist']),
    'FAIL font-preload-embedded: dist/index.html:1: data:font/woff2;base64,AA',
  );
});

test('an HTML preload of a missing local font fails', () => {
  const html =
    '<!doctype html><link rel="preload" as="font" type="font/woff2" ' +
    'href="/assets/review-missing.woff2" crossorigin>';
  assertFail(
    run(['--root', makeDist(FACE_LATIN + FACE_ARABIC, html), '--dist']),
    'FAIL font-preload-missing: dist/index.html:1: /assets/review-missing.woff2',
  );
});

test('an HTML preload of an external font fails', () => {
  const html =
    '<!doctype html><link rel="preload" as="font" type="font/woff2" ' +
    'href="https://fonts.example/x.woff2" crossorigin>';
  assertFail(
    run(['--root', makeDist(FACE_LATIN + FACE_ARABIC, html), '--dist']),
    'FAIL font-preload-external: dist/index.html:1: https://fonts.example/x.woff2',
  );
});

test('an HTML preload that traverses out of dist fails', () => {
  const html =
    '<!doctype html><link rel="preload" as="font" type="font/woff2" ' +
    'href="../../package.json" crossorigin>';
  assertFail(
    run(['--root', makeDist(FACE_LATIN + FACE_ARABIC, html), '--dist']),
    'FAIL font-preload-traversal: dist/index.html:1: ../../package.json',
  );
});

test('an inline style with an embedded font fails', () => {
  const html =
    '<!doctype html><style>@font-face{font-family:Review;' +
    'src:url(data:font/woff2;base64,AA)}</style>';
  assertFail(
    run(['--root', makeDist(FACE_LATIN + FACE_ARABIC, html), '--dist']),
    'FAIL font-url-embedded: dist/index.html:1: data:font/woff2;base64,AA',
  );
});

test('an inline style face counts toward the family requirement', () => {
  const html =
    "<!doctype html><style>@font-face{font-family:'IBM Plex Sans Arabic';" +
    "src:url(/assets/arabic-400.woff2) format('woff2');}</style>";
  assertPass(run(['--root', makeDist(FACE_LATIN, html), '--dist']));
});

test('a style attribute face is scanned but never counts as delivered', () => {
  const html =
    '<!doctype html><body style="@font-face{font-family:\'IBM Plex Sans ' +
    'Arabic\';src:url(data:font/woff2;base64,AA)}">';
  const home = makeDist(FACE_LATIN, html);
  const result = run(['--root', home, '--dist']);
  assertFail(
    result,
    'FAIL font-url-embedded: dist/index.html:1: data:font/woff2;base64,AA',
  );
  assertFail(result, 'FAIL font-family-missing: dist: IBM Plex Sans Arabic');
});

test('an HTML stylesheet link to a missing file fails', () => {
  const html =
    '<!doctype html><link rel="stylesheet" href="/assets/missing.css">';
  assertFail(
    run(['--root', makeDist(FACE_LATIN + FACE_ARABIC, html), '--dist']),
    'FAIL font-stylesheet-missing: dist/index.html:1: /assets/missing.css',
  );
});

test('an HTML stylesheet link to an external host fails', () => {
  const html =
    '<!doctype html><link rel="stylesheet" href="https://fonts.example/x.css">';
  assertFail(
    run(['--root', makeDist(FACE_LATIN + FACE_ARABIC, html), '--dist']),
    'FAIL font-stylesheet-external: dist/index.html:1: https://fonts.example/x.css',
  );
});

test('an HTML stylesheet link that traverses out of dist fails', () => {
  const html = '<!doctype html><link rel="stylesheet" href="../outside.css">';
  assertFail(
    run(['--root', makeDist(FACE_LATIN + FACE_ARABIC, html), '--dist']),
    'FAIL font-stylesheet-traversal: dist/index.html:1: ../outside.css',
  );
});

test('a stylesheet link inside dist is followed and scanned', () => {
  const home = makeDist(
    FACE_LATIN + FACE_ARABIC,
    '<!doctype html><link rel="stylesheet" href="/assets/b.css">',
  );
  fs.writeFileSync(
    path.join(home, 'dist', 'assets', 'b.css'),
    '@font-face{font-family:Review;src:url(data:font/woff2;base64,AA)}',
  );
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL font-url-embedded: dist/assets/b.css:1: data:font/woff2;base64,AA',
  );
});

// R2 — the CSS is tokenized: at-keywords match case-insensitively with
// escapes, comments never deliver a font.

test('an uppercase @FONT-FACE with an embedded font fails', () => {
  const css =
    '@FONT-FACE{font-family:Review;src:url(data:font/woff2;base64,AA)}' +
    FACE_LATIN +
    FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-url-embedded: dist/assets/a.css:1: data:font/woff2;base64,AA',
  );
});

test('a comment before the brace does not hide a font face', () => {
  const css =
    '@font-face/**/{font-family:Review;src:url(data:font/woff2;base64,AA)}' +
    FACE_LATIN +
    FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-url-embedded: dist/assets/a.css:1: data:font/woff2;base64,AA',
  );
});

test('a fully commented-out font face neither delivers nor refuses', () => {
  const css =
    '/*@font-face{font-family:Review;src:url(data:font/woff2;base64,AA)}*/' +
    FACE_LATIN +
    FACE_ARABIC;
  assertPass(run(['--root', makeDist(css), '--dist']));
});

test('a commented-out required family fails', () => {
  const css = `/*${FACE_ARABIC}*/${FACE_LATIN}`;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-family-missing: dist: IBM Plex Sans Arabic',
  );
});

test('an uppercase @IMPORT of a missing local file fails', () => {
  const css = '@IMPORT url(/missing.css);' + FACE_LATIN + FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-import-missing: dist/assets/a.css:1: /missing.css',
  );
});

test('every active at-keyword spelling and comment placement refuses the embedded font', () => {
  const spellings = [
    '@font-face',
    '@FONT-FACE',
    '@Font-Face',
    '@fOnT-fAcE',
    '@font-FACE',
    '@FONT-face',
    '@\\66 ont-face',
    '@font-\\66 ace',
    '@\\46 ont-face',
    '@\\66\\6f nt-face',
    '@font-\\66\\61 ce',
  ];
  const placements = [
    (rule) => rule,
    (rule) => `/*c*/${rule}`,
    (rule) => rule.replace('{', '/*c*/{'),
    (rule) => rule.replace('{', ' /*c*/ {'),
    (rule) => rule.replace('{', '{/*c*/'),
    (rule) => rule.replace(';src:', ';/*c*/src:'),
    (rule) => rule.replace('src:url', 'src:/*c*/url'),
    (rule) => `${rule}/*c*/`,
  ];
  const blocks = [];
  for (const spelling of spellings) {
    for (const place of placements) {
      blocks.push(
        place(
          `${spelling}{font-family:Review;` +
            'src:url(data:font/woff2;base64,AA)}',
        ),
      );
    }
  }
  const line =
    'FAIL font-url-embedded: dist/assets/a.css:1: data:font/woff2;base64,AA';
  const result = run([
    '--root',
    makeDist(blocks.join('') + FACE_LATIN + FACE_ARABIC),
    '--dist',
  ]);
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  const count = result.stdout
    .split('\n')
    .filter((entry) => entry === line).length;
  assert.equal(count, spellings.length * placements.length, result.stdout);
});

// R3 — the resolver uses browser URL semantics with containment.

test('a font URL that traverses out of dist fails', () => {
  const home = makeDist(
    FACE_LATIN.replace('/assets/latin-400.woff2', '../../package.json') +
      FACE_ARABIC,
  );
  fs.writeFileSync(path.join(home, 'package.json'), '{}');
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL font-url-traversal: dist/assets/a.css:1: ../../package.json',
  );
});

test('a percent-encoded traversal fails', () => {
  const css =
    FACE_LATIN.replace(
      '/assets/latin-400.woff2',
      '%2e%2e/%2e%2e/package.json',
    ) + FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-url-traversal: dist/assets/a.css:1: %2e%2e/%2e%2e/package.json',
  );
});

test('a font URL that targets a directory fails as missing', () => {
  const css =
    FACE_LATIN.replace('/assets/latin-400.woff2', '/assets') + FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-file-missing: dist/assets/a.css:1: /assets',
  );
});

test('an encoded separator inside a segment fails as traversal', () => {
  const css =
    FACE_LATIN.replace(
      '/assets/latin-400.woff2',
      'x%2f..%2f..%2fpackage.json',
    ) + FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-url-traversal: dist/assets/a.css:1: x%2f..%2f..%2fpackage.json',
  );
});

test('a font URL that stays inside dist after dot segments passes', () => {
  const css =
    FACE_LATIN.replace('/assets/latin-400.woff2', '../assets/latin-400.woff2') +
    FACE_ARABIC;
  assertPass(run(['--root', makeDist(css), '--dist']));
});

test('a symlink that escapes dist fails', () => {
  const home = makeDist(
    FACE_LATIN.replace('/assets/latin-400.woff2', '/assets/evil.woff2') +
      FACE_ARABIC,
  );
  fs.writeFileSync(path.join(home, 'package.json'), '{}');
  fs.symlinkSync(
    path.join(home, 'package.json'),
    path.join(home, 'dist', 'assets', 'evil.woff2'),
  );
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL font-url-symlink-escape: dist/assets/a.css:1: /assets/evil.woff2',
  );
});

test('a preload target that is a symlink escaping dist fails', () => {
  const home = makeDist(
    FACE_LATIN + FACE_ARABIC,
    '<!doctype html><link rel="preload" as="font" href="/assets/evil.woff2">',
  );
  fs.writeFileSync(path.join(home, 'package.json'), '{}');
  fs.symlinkSync(
    path.join(home, 'package.json'),
    path.join(home, 'dist', 'assets', 'evil.woff2'),
  );
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL font-preload-symlink-escape: dist/index.html:1: /assets/evil.woff2',
  );
});

test('a symlink that stays inside dist passes', () => {
  const home = makeDist(
    FACE_LATIN.replace('/assets/latin-400.woff2', '/assets/alias.woff2') +
      FACE_ARABIC,
  );
  fs.symlinkSync(
    path.join(home, 'dist', 'assets', 'latin-400.woff2'),
    path.join(home, 'dist', 'assets', 'alias.woff2'),
  );
  assertPass(run(['--root', home, '--dist']));
});

test('an import that traverses out of dist fails', () => {
  const css = '@import url(../../package.json);' + FACE_LATIN + FACE_ARABIC;
  const home = makeDist(css);
  fs.writeFileSync(path.join(home, 'package.json'), '{}');
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL font-import-traversal: dist/assets/a.css:1: ../../package.json',
  );
});

test('an embedded font import fails as external', () => {
  const css =
    '@import url(data:text/css;base64,QQ);' + FACE_LATIN + FACE_ARABIC;
  assertFail(
    run(['--root', makeDist(css), '--dist']),
    'FAIL font-import-external: dist/assets/a.css:1: data:text/css;base64,QQ',
  );
});

test('an import through a symlink that escapes dist fails', () => {
  const home = makeDist(
    '@import url(/assets/evil.css);' + FACE_LATIN + FACE_ARABIC,
  );
  fs.writeFileSync(path.join(home, 'package.json'), '{}');
  fs.symlinkSync(
    path.join(home, 'package.json'),
    path.join(home, 'dist', 'assets', 'evil.css'),
  );
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL font-import-symlink-escape: dist/assets/a.css:1: /assets/evil.css',
  );
});

test('a stylesheet link through a symlink that escapes dist fails', () => {
  const home = makeDist(
    FACE_LATIN + FACE_ARABIC,
    '<!doctype html><link rel="stylesheet" href="/assets/evil.css">',
  );
  fs.writeFileSync(path.join(home, 'package.json'), '{}');
  fs.symlinkSync(
    path.join(home, 'package.json'),
    path.join(home, 'dist', 'assets', 'evil.css'),
  );
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL font-stylesheet-symlink-escape: dist/index.html:1: /assets/evil.css',
  );
});

test('a stylesheet link to an embedded data URL fails', () => {
  const html =
    '<!doctype html><link rel="stylesheet" href="data:text/css;base64,QQ">';
  assertFail(
    run(['--root', makeDist(FACE_LATIN + FACE_ARABIC, html), '--dist']),
    'FAIL font-stylesheet-embedded: dist/index.html:1: data:text/css;base64,QQ',
  );
});

test('a stylesheet link without an href is inert and passes', () => {
  const html = '<!doctype html><link rel="stylesheet">';
  assertPass(
    run(['--root', makeDist(FACE_LATIN + FACE_ARABIC, html), '--dist']),
  );
});

test('a style element mentioned only inside a script is not inline CSS', () => {
  const html =
    '<!doctype html><script>const s = "<style>@font-face{src:url(' +
    'data:font/woff2;base64,AA)}</style>";</script>';
  assertPass(
    run(['--root', makeDist(FACE_LATIN + FACE_ARABIC, html), '--dist']),
  );
});

test('a style element inside an HTML comment is not inline CSS', () => {
  const html =
    '<!doctype html><!--<style>@font-face{src:url(data:font/woff2;' +
    'base64,AA)}</style>-->';
  assertPass(
    run(['--root', makeDist(FACE_LATIN + FACE_ARABIC, html), '--dist']),
  );
});

test('an unreadable html file fails', () => {
  const home = cleanFonts();
  const file = path.join(home, 'dist', 'locked.html');
  fs.writeFileSync(file, '<!doctype html>');
  fs.chmodSync(file, 0o000);
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL unreadable-file: dist/locked.html: EACCES',
  );
});

test('a licence path that is a directory fails as missing', () => {
  const home = cleanFonts();
  fs.rmSync(path.join(home, 'dist', 'licences', 'ibm-plex-sans.txt'));
  fs.mkdirSync(path.join(home, 'dist', 'licences', 'ibm-plex-sans.txt'));
  assertFail(
    run(['--root', home, '--dist']),
    'FAIL font-licence-missing: dist/licences/ibm-plex-sans.txt',
  );
});

test('an unwalkable directory inside dist fails as an internal error', () => {
  const home = cleanFonts();
  const dir = path.join(home, 'dist', 'assets', 'secret');
  fs.mkdirSync(dir);
  fs.chmodSync(dir, 0o000);
  const result = run(['--root', home, '--dist']);
  fs.chmodSync(dir, 0o755);
  assert.equal(result.status, 1, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stdout, /^FAIL internal-error: EACCES: /);
});

test('usage', async (t) => {
  await t.test('the check needs --dist', () => {
    const result = run(['--root', WEB]);
    assert.equal(result.status, 2, result.stdout);
    assert.equal(result.stdout, 'USAGE: the font check needs --dist\n');
  });
  await t.test('unknown flag', () => {
    const result = run(['--dist', '--not-a-flag']);
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
