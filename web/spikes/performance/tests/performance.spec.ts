import { expect, test, type Page } from '@playwright/test';

const HEXAGONS = 110000;
const PARTICLES = 50000;
const WALL_WIDTH = 1920;
const WALL_HEIGHT = 1080;

type Spike = NonNullable<Window['__spike']>;

async function ready(page: Page): Promise<Spike> {
  await page.waitForFunction(
    () =>
      window.__spike?.phase === 'done' || window.__spike?.phase === 'failed',
    undefined,
    { timeout: 170000 },
  );
  const value = await page.evaluate(() => window.__spike);
  if (value === undefined) throw new Error('spike diagnostics are absent');
  return value;
}

function foreignRequest(url: string, origin: string): string {
  if (url.startsWith('data:') || url.startsWith('blob:')) return '';
  if (url.startsWith('http://') || url.startsWith('https://')) {
    try {
      return new URL(url).origin === origin ? '' : url;
    } catch {
      return url;
    }
  }
  return '';
}

async function open(page: Page, path: string): Promise<Spike> {
  const seen: string[] = [];
  page.on('request', (request) => {
    seen.push(request.url());
  });
  await page.goto(path);
  const spike = await ready(page);
  const origin = new URL(page.url()).origin;
  for (const url of seen) {
    const foreign = foreignRequest(url, origin);
    if (foreign !== '') throw new Error(`non-same-origin request: ${foreign}`);
  }
  return spike;
}

test('the smoke orbit draws both layers and records a trace', async ({
  page,
}) => {
  const spike = await open(page, '/en/_perf?profile=smoke');
  expect(spike.phase).toBe('done');
  expect(spike.failure).toBe('');
  expect(spike.hexagonInstances).toBe(HEXAGONS);
  expect(spike.particleInstances).toBe(PARTICLES);
  expect(spike.hex).toBe(true);
  expect(spike.particle).toBe(true);
  expect(spike.bearingEnd).not.toBe(spike.bearingStart);
  expect(spike.positionEnd).not.toBe(spike.positionStart);
  expect(spike.cssWidth).toBe(WALL_WIDTH);
  expect(spike.cssHeight).toBe(WALL_HEIGHT);
  expect(spike.bufferWidth).toBe(WALL_WIDTH);
  expect(spike.bufferHeight).toBe(WALL_HEIGHT);
  expect(spike.textPixelRatio).toBe(2);
  expect(spike.cap).toBe(1);
  expect(spike.devicePixelRatio).toBe(2);
  expect(spike.webglRenderer.length).toBeGreaterThan(0);
  expect(spike.submitFailure).toBe('');
  expect(spike.qualification).toBe('smoke-profile');
  expect(spike.savedPath.length).toBeGreaterThan(0);
  expect(spike.shareUnderBudget).not.toBeNull();
  expect(spike).not.toHaveProperty('framesPerSecond');
  await expect(page.locator('#pending')).toHaveText(
    'native frame-rate gate pending',
  );
  await expect(page.locator('#notice')).toHaveText(
    'Synthetic fixture. Invented extent. No place name.',
  );
});

test('the Arabic route uses the Arabic notice', async ({ page }) => {
  await open(page, '/ar/_perf?profile=smoke');
  await expect(page.locator('#notice')).toHaveText(
    'عرض اصطناعي. امتداد مخترع. بلا اسم مكان.',
  );
  await expect(page.locator('html')).toHaveAttribute('lang', 'ar');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
});

test('isolating hexagons leaves the hex canvas nonblank', async ({ page }) => {
  const spike = await open(page, '/en/_perf?profile=smoke&isolate=hexagons');
  expect(spike.hexagonInstances).toBe(HEXAGONS);
  expect(spike.particleInstances).toBe(0);
  expect(spike.hex).toBe(true);
  expect(spike.particle).toBe(false);
});

test('isolating particles leaves the particle canvas nonblank', async ({
  page,
}) => {
  const spike = await open(page, '/en/_perf?profile=smoke&isolate=particles');
  expect(spike.hexagonInstances).toBe(0);
  expect(spike.particleInstances).toBe(PARTICLES);
  expect(spike.particle).toBe(true);
  expect(spike.hex).toBe(false);
});

test('omitting one hexagon lowers the drawn count', async ({ page }) => {
  const spike = await open(page, '/en/_perf?profile=smoke&plant=omit-hexagon');
  expect(spike.hexagonInstances).toBe(HEXAGONS - 1);
});

test('hiding the hexagon layer reports no hexagon instances', async ({
  page,
}) => {
  const spike = await open(page, '/en/_perf?profile=smoke&plant=hide-hexagons');
  expect(spike.hexagonInstances).toBe(0);
  expect(spike.hex).toBe(false);
});

test('omitting one particle lowers the drawn count', async ({ page }) => {
  const spike = await open(page, '/en/_perf?profile=smoke&plant=omit-particle');
  expect(spike.particleInstances).toBe(PARTICLES - 1);
});

test('hiding the particle layer reports no particle instances', async ({
  page,
}) => {
  const spike = await open(
    page,
    '/en/_perf?profile=smoke&plant=hide-particles',
  );
  expect(spike.particleInstances).toBe(0);
  expect(spike.particle).toBe(false);
});

test('a frozen clock leaves the first particle in place', async ({ page }) => {
  const spike = await open(page, '/en/_perf?profile=smoke&plant=freeze');
  expect(spike.positionEnd).toBe(spike.positionStart);
});

test('an empty timestamp list is refused by name', async ({ page }) => {
  const spike = await open(page, '/en/_perf?profile=smoke&plant=no-samples');
  expect(spike.submitFailure).toBe('empty-timestamps');
});

test('a blank renderer is refused by name', async ({ page }) => {
  const spike = await open(page, '/en/_perf?plant=missing-renderer');
  expect(spike.webglRenderer).toBe('');
  expect(spike.profile).toBe('gate');
  expect(spike.qualification).toBe('missing-renderer');
});

test('an unknown field is refused by name', async ({ page }) => {
  const spike = await open(page, '/en/_perf?profile=smoke&plant=fail-submit');
  expect(spike.submitFailure).toBe('unknown-field');
});

test('ignoring the cap is qualified as the wrong cap', async ({ page }) => {
  const spike = await open(page, '/en/_perf?profile=smoke&plant=ignore-cap');
  expect(spike.cap).toBe(spike.textPixelRatio);
  expect(spike.cap).toBe(2);
  expect(spike.bufferWidth).toBe(WALL_WIDTH * spike.cap);
  expect(spike.qualification).toBe('wrong-cap');
});

test('a renamed profile is qualified by name', async ({ page }) => {
  const spike = await open(
    page,
    '/en/_perf?profile=smoke&plant=rename-profile',
  );
  expect(spike.profile).toBe('tuned');
  expect(spike.qualification).toBe('unknown-profile');
});

test('the ordinary page helper rejects a remote asset', async ({ page }) => {
  await expect(
    open(page, '/en/_perf?profile=smoke&plant=remote-asset'),
  ).rejects.toThrow(/assets\.invalid/);
});

test('a remote image does not load', async ({ page }) => {
  const failed: string[] = [];
  page.on('requestfailed', (request) => {
    if (request.url().includes('assets.invalid')) failed.push(request.url());
  });
  await page.goto('/en/_perf?profile=smoke&plant=remote-asset');
  const spike = await ready(page);
  expect(spike.phase).toBe('done');
  expect(failed.length).toBeGreaterThan(0);
});

test('the no-webgl2 plant names the failure without a map', async ({
  page,
}) => {
  const spike = await open(page, '/en/_perf?profile=smoke&plant=no-webgl2');
  expect(spike.phase).toBe('failed');
  expect(spike.failure).toBe('webgl2-unavailable');
  await expect(page.locator('#map-failure')).toHaveText('webgl2-unavailable');
});
