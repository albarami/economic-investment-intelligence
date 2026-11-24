/**
 * Production basemap browser spec runner plus the source scans whose
 * planted removals (pmtiles protocol, RTL plugin, glyph template,
 * extract wiring) must fail.
 */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '../..');
const ROOT = path.resolve(WEB, '..');
const BROWSERS = path.join(ROOT, 'data', 'tools', 'playwright');

const MAP_BOOT = path.join(WEB, 'src/stage/map-boot.ts');
const BASEMAP = path.join(WEB, 'src/stage/basemap.ts');
const APP = path.join(WEB, 'src/app/App.tsx');
const MAIN = path.join(WEB, 'src/main.tsx');

test('map boot keeps the pmtiles protocol and the retained rtl plugin', () => {
  const source = readFileSync(MAP_BOOT, 'utf8');
  assert.match(source, /addProtocol\('pmtiles', protocol\.tile\)/);
  assert.match(source, /setRTLTextPlugin\(rtlPluginUrl, true\)/);
  assert.match(source, /rtlPluginUrl/);
});

test('basemap holds the same-origin glyph template and no external host', () => {
  const source = readFileSync(BASEMAP, 'utf8');
  assert.match(source, /'\/fonts\/\{fontstack\}\/\{range\}\.pbf'/);
  assert.match(source, /location/);
  assert.doesNotMatch(source, /https?:\/\//);
});

test('the application bootstrap wires the mounted extract', () => {
  const source = readFileSync(APP, 'utf8');
  assert.match(source, /EXTRACT_URL = '\/tiles\/basemap\.pmtiles'/);
  assert.match(source, /extractUrl=\{EXTRACT_URL\}/);
});

test('the bundled interface fonts stay imported', () => {
  const source = readFileSync(MAIN, 'utf8');
  assert.match(source, /ibm-plex-sans/);
  assert.match(source, /ibm-plex-sans-arabic/);
});

test('map browser specs', () => {
  assert.equal(existsSync(path.join(WEB, 'playwright.map.config.ts')), true);
  const result = spawnSync(
    process.execPath,
    [
      path.join(WEB, 'node_modules', 'playwright', 'cli.js'),
      'test',
      '--config',
      'playwright.map.config.ts',
    ],
    {
      cwd: WEB,
      encoding: 'utf8',
      timeout: 600_000,
      env: {
        PATH: process.env.PATH ?? '',
        HOME: process.env.HOME ?? '',
        TMPDIR: process.env.TMPDIR ?? '',
        TMP: process.env.TMP ?? '',
        TEMP: process.env.TEMP ?? '',
        LANG: process.env.LANG ?? 'C',
        PLAYWRIGHT_BROWSERS_PATH: BROWSERS,
        UV_CACHE_DIR:
          process.env.UV_CACHE_DIR ??
          path.join(ROOT, '.overnight', 'tmp', 'uv-cache'),
        UV_OFFLINE: '1',
      },
    },
  );
  const output = `${result.stdout ?? ''}\n${result.stderr ?? ''}`;
  if (result.status !== 0) {
    const first = output
      .split('\n')
      .map((line) => line.trim())
      .find((line) => line.length > 0);
    const missing =
      output.includes("Executable doesn't exist") ||
      output.includes('browserType.launch') ||
      output.includes('Failed to launch');
    if (missing) assert.fail(`NOT RUN ${first ?? 'browser'}`);
    assert.equal(result.status, 0, output);
  }
});
