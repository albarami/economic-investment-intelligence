import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { INSTALL, browserHome, shellInstalled } from './browser-home.mjs';
import { buildPage, removePage } from './build-page.mjs';
import { IMAGE_FILES, REMOTE_FONT } from './guards.mjs';
import { startServer } from './server.mjs';

process.env.PLAYWRIGHT_BROWSERS_PATH = browserHome(import.meta.url);

const SPIKE = path.dirname(fileURLToPath(import.meta.url));
const EVIDENCE = path.join(SPIKE, 'evidence');
const VIEWPORT = { width: 960, height: 640 };
const FRAMES = [
  { file: 'arabic-labels.png', query: '?lang=ar' },
  { file: 'english-labels.png', query: '?lang=en' },
  { file: 'hexagons-below-labels.png', query: '?lang=ar&frame=overlap' },
];

function fail(message) {
  console.error(`FAIL ${message}`);
  process.exitCode = 1;
}

function browserMissing() {
  return !shellInstalled(browserHome(import.meta.url));
}

function hashFile(file) {
  const bytes = fs.readFileSync(file);
  return `sha256:${createHash('sha256').update(bytes).digest('hex')}`;
}

function walk(dir, root, files) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, root, files);
    else if (entry.isFile())
      files.push(path.relative(root, full).split(path.sep).join('/'));
  }
}

function recordRequest(rows, url, origin) {
  if (url.startsWith('data:') || url.startsWith('blob:')) {
    rows.push({ url, decision: 'local' });
    return 'local';
  }
  try {
    const parsed = new URL(url);
    const decision = parsed.origin === origin ? 'same-origin' : 'blocked';
    const stored =
      decision === 'same-origin' ? `${parsed.pathname}${parsed.search}` : url;
    rows.push({ url: stored, decision });
    return decision;
  } catch {
    rows.push({ url, decision: 'blocked' });
    return 'blocked';
  }
}

async function main() {
  if (browserMissing()) {
    fail(`missing browser. Run: ${INSTALL}`);
    return;
  }
  const built = buildPage();
  if (!built.ok) {
    fail(built.detail);
    return;
  }
  const { chromium } = await import('@playwright/test');
  fs.mkdirSync(EVIDENCE, { recursive: true });
  let server;
  let browser;
  const rows = [];
  try {
    server = await startServer(built.outDir);
    browser = await chromium.launch();
    const page = await browser.newPage({
      viewport: VIEWPORT,
      deviceScaleFactor: 1,
    });
    page.on('console', (message) => {
      if (!message.text().includes(REMOTE_FONT)) return;
      if (rows.some((row) => row.url === REMOTE_FONT)) return;
      rows.push({ url: REMOTE_FONT, decision: 'blocked' });
    });
    await page.route('**/*', (route) => {
      const url = route.request().url();
      const decision = recordRequest(rows, url, server.origin);
      if (decision === 'blocked') return route.abort();
      return route.continue();
    });
    for (const frame of FRAMES) {
      await page.goto(`${server.origin}/${frame.query}`);
      await page.waitForFunction(
        () => window.__spike && window.__spike.ready === true,
      );
      await page.screenshot({ path: path.join(EVIDENCE, frame.file) });
    }
    await page.goto(`${server.origin}/?lang=en&plant=remote-font`);
    await page.waitForFunction(
      () => window.__spike && (window.__spike.ready || window.__spike.failure),
    );
    if (
      !rows.some((row) => row.url === REMOTE_FONT && row.decision === 'blocked')
    ) {
      throw new Error(`missing blocked request: ${REMOTE_FONT}`);
    }
    const assetHashes = {};
    for (const name of IMAGE_FILES) {
      assetHashes[name] = hashFile(path.join(EVIDENCE, name));
    }
    const assets = [];
    walk(built.outDir, built.outDir, assets);
    const manifest = {};
    for (const relative of assets.sort())
      manifest[relative] = hashFile(path.join(built.outDir, relative));
    fs.writeFileSync(
      path.join(EVIDENCE, 'run.json'),
      `${JSON.stringify({ outcome: 'recorded', assetHashes }, null, 2)}\n`,
    );
    fs.writeFileSync(
      path.join(EVIDENCE, 'network.json'),
      `${JSON.stringify({ requests: rows }, null, 2)}\n`,
    );
    fs.writeFileSync(
      path.join(EVIDENCE, 'asset-manifest.json'),
      `${JSON.stringify(manifest, null, 2)}\n`,
    );
    console.log('recorded spike evidence');
  } finally {
    if (browser) await browser.close();
    if (server) await server.close();
    removePage(built.outDir);
  }
}

await main();
