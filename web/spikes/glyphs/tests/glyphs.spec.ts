import fs from 'node:fs';
import { expect, test, type Page } from '@playwright/test';
import {
  FIRST_LABEL_ID,
  LICENCE_PATHS,
  REMOTE_FONT,
  arabicNames,
  judgeCsp,
  judgeDigits,
  judgeDirection,
  judgeFonts,
  judgeLetterSpacing,
  judgeLicences,
  judgeRequests,
  loadNames,
} from '../guards.mjs';

const ARABIC = arabicNames();
const ENGLISH = loadNames().places.map(
  (place: { nameEn: string }) => place.nameEn,
);

function requestKind(
  url: string,
  pageUrl: string,
): 'local' | 'same-origin' | 'blocked' {
  if (url.startsWith('data:') || url.startsWith('blob:')) return 'local';
  const target = new URL(url);
  const settled = pageUrl !== '' && pageUrl !== 'about:blank';
  if (settled)
    return target.origin === new URL(pageUrl).origin
      ? 'same-origin'
      : 'blocked';
  return target.hostname === '127.0.0.1' ? 'same-origin' : 'blocked';
}

async function arm(page: Page, seen: string[]): Promise<void> {
  await page.route('**/*', (route) => {
    const url = route.request().url();
    seen.push(url);
    if (requestKind(url, page.url()) === 'blocked') return route.abort();
    return route.continue();
  });
}

async function open(page: Page, query: string): Promise<SpikeDiagnostics> {
  const seen: string[] = [];
  page.on('request', (request) => {
    seen.push(request.url());
  });
  await arm(page, seen);
  await page.goto(`/${query}`);
  await page.waitForFunction(() => {
    const spike = window.__spike;
    return spike !== undefined && (spike.ready || spike.failure !== '');
  });
  const verdict = judgeRequests(seen, new URL(page.url()).origin);
  if (!verdict.ok) throw new Error(verdict.detail);
  const spike = await page.evaluate(() => window.__spike);
  return (
    spike ?? {
      ready: false,
      failure: 'map-ready diagnostics are absent',
      labelNames: [],
    }
  );
}

function baseline(name: string): void {
  const relative = `spikes/glyphs/tests/baselines/${name}-chromium-linux.png`;
  const file = new URL(
    `./baselines/${name}-chromium-linux.png`,
    import.meta.url,
  );
  if (!fs.existsSync(file)) {
    throw new Error(`missing baseline: ${relative}`);
  }
}

async function comparePixels(page: Page, name: string): Promise<void> {
  if (process.env.CI !== 'true') return;
  if (process.env.SPIKE_CAPTURE !== '1') baseline(name);
  await expect(page).toHaveScreenshot(`${name}.png`);
}

test('Arabic labels render from local assets', async ({ page }) => {
  const spike = await open(page, '?lang=ar');
  const gaps: string[] = [];
  if (!spike.ready)
    gaps.push(spike.failure || 'map-ready diagnostics are absent');
  if (spike.labelNames?.join('\n') !== ARABIC.join('\n')) {
    gaps.push('reviewed Arabic output is absent');
  }
  expect(gaps, gaps.join('; ')).toEqual([]);
  const fonts = judgeFonts(spike.fontFaceFamilies ?? [], false);
  expect(fonts.ok, fonts.detail).toBe(true);
  await comparePixels(page, 'arabic-labels');
});

test('English labels render from the same local fixture', async ({ page }) => {
  const spike = await open(page, '?lang=en');
  expect(spike.ready, spike.failure).toBe(true);
  expect(spike.labelNames).toEqual(ENGLISH);
  await comparePixels(page, 'english-labels');
});

test('hexagons sit below the first label layer', async ({ page }) => {
  const spike = await open(page, '?lang=ar&frame=overlap');
  expect(spike.ready, spike.failure).toBe(true);
  expect(spike.interleaved).toBe(true);
  expect(spike.overlayCount).toBe(1);
  expect(spike.webgpu).toBe(false);
  expect(spike.firstLabelId).toBe(FIRST_LABEL_ID);
  expect(spike.beforeId).toBe(FIRST_LABEL_ID);
  await comparePixels(page, 'hexagons-below-labels');
});

test('both languages render the synthetic basemap, buildings, labels and polygons', async ({
  page,
}) => {
  const arabic = await open(page, '?lang=ar');
  const english = await open(page, '?lang=en');
  for (const spike of [arabic, english]) {
    expect(spike.ready, spike.failure).toBe(true);
    expect(spike.layerIds).toEqual(
      expect.arrayContaining(['land', 'buildings', 'labels']),
    );
    expect(spike.featureKey).toBe(arabic.featureKey);
    expect(spike.bearing).toBe(0);
  }
});

test('a remote font attempt is blocked', async ({ page }) => {
  const seen: string[] = [];
  page.on('console', (message) => {
    if (message.text().includes(REMOTE_FONT)) seen.push(REMOTE_FONT);
  });
  await arm(page, seen);
  await page.goto('/?lang=en&plant=remote-font');
  await page.waitForFunction(() => {
    const spike = window.__spike;
    return spike !== undefined && (spike.ready || spike.failure !== '');
  });
  expect(seen.some((url) => url.startsWith(REMOTE_FONT))).toBe(true);
  const verdict = judgeRequests(seen, new URL(page.url()).origin);
  expect(verdict.ok).toBe(false);
  expect(verdict.detail).toContain('assets.invalid');
});

test('the ordinary page helper rejects a remote font attempt', async ({
  page,
}) => {
  await expect(open(page, '?lang=en&plant=remote-font')).rejects.toThrow(
    /assets\.invalid/,
  );
});

test('the server sends a same-origin content security policy', async ({
  request,
  baseURL,
}) => {
  const response = await request.get(`${baseURL}/`);
  const verdict = judgeCsp(
    response.headers()['content-security-policy'] ?? null,
  );
  expect(verdict.ok, verdict.detail).toBe(true);
});

test('four local licence texts are served', async ({ request, baseURL }) => {
  const texts: string[] = [];
  for (const licencePath of LICENCE_PATHS) {
    const response = await request.get(`${baseURL}${licencePath}`);
    expect(response.status(), licencePath).toBe(200);
    texts.push(await response.text());
  }
  const verdict = judgeLicences(texts);
  expect(verdict.ok, verdict.detail).toBe(true);
});

test('Arabic chrome is right to left and the map is not mirrored', async ({
  page,
}) => {
  const spike = await open(page, '?lang=ar');
  expect(spike.ready, spike.failure).toBe(true);
  const spacing = judgeLetterSpacing(spike.letterSpacing ?? '');
  expect(spacing.ok, spacing.detail).toBe(true);
  const direction = judgeDirection(
    spike.direction ?? '',
    spike.bearing ?? 1,
    spike.mirrored ?? true,
  );
  expect(direction.ok, direction.detail).toBe(true);
  const digits = judgeDigits(await page.locator('body').innerText());
  expect(digits.ok, digits.detail).toBe(true);
  expect(spike.latinFamily).toContain('IBM Plex Sans');
  expect(spike.arabicFamily).toContain('IBM Plex Sans Arabic');
  const notice = page.locator('.chrome-latin bdi');
  await expect(notice).toHaveAttribute('lang', 'en');
  await expect(notice).toHaveAttribute('dir', 'ltr');
  expect(await notice.evaluate((el) => getComputedStyle(el).direction)).toBe(
    'ltr',
  );
  expect(
    await page
      .locator('.chrome-latin')
      .evaluate((el) => getComputedStyle(el).direction),
  ).toBe('rtl');
});

test('an omitted Arabic face fails font readiness', async ({ page }) => {
  const spike = await open(page, '?lang=ar&plant=omit-arabic-face');
  const verdict = judgeFonts(spike.fontFaceFamilies ?? [], true);
  expect(verdict.ok).toBe(false);
  expect(spike.fontFacesReady).toBe(false);
});
