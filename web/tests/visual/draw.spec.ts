import { expect, test } from '@playwright/test';
import { text } from '../../src/i18n';

const VIEWPORTS = [
  { width: 3840, height: 2160 },
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1024, height: 768 },
] as const;

for (const language of ['en', 'ar'] as const) {
  test(`${language}: keyboard draws a polygon and the summary sits beside the answer`, async ({
    page,
  }) => {
    await page.goto(`/tests/visual/draw.html?lang=${language}&theme=dark`);
    await page
      .getByRole('button', { name: text(language, 'draw.polygon') })
      .focus();
    await page.keyboard.press('Enter');
    await expect(
      page.getByRole('button', { name: text(language, 'draw.crosshair') }),
    ).toBeFocused();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('Enter');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    await page.keyboard.press('ArrowLeft');
    await page.keyboard.press('Enter');
    await page.keyboard.press('Shift+Tab');
    await page.keyboard.press('Shift+Tab');
    await page.keyboard.press('Shift+Tab');
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-closed="yes"]')).toHaveCount(1);
    await page
      .getByRole('button', { name: text(language, 'draw.use') })
      .focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-line="accent"]')).toBeVisible();
    await expect(
      page.locator('.brief-column [data-part="no-mode"]'),
    ).toBeVisible();
  });

  test(`${language}: touch places vertices and a knob drag moves one vertex`, async ({
    page,
  }) => {
    await page.goto(`/tests/visual/draw.html?lang=${language}&theme=dark`);
    await page
      .getByRole('button', { name: text(language, 'draw.polygon') })
      .tap();
    const overlay = page.locator('.area-overlay');
    const box = await overlay.boundingBox();
    expect(box).not.toBeNull();
    if (!box) return;
    const first = { x: box.x + box.width * 0.55, y: box.y + box.height * 0.35 };
    const second = {
      x: box.x + box.width * 0.75,
      y: box.y + box.height * 0.35,
    };
    const third = { x: box.x + box.width * 0.75, y: box.y + box.height * 0.6 };
    await page.touchscreen.tap(first.x, first.y);
    await page.touchscreen.tap(second.x, second.y);
    await page.touchscreen.tap(third.x, third.y);
    await page.locator('[data-part="knob"][data-index="0"]').tap();
    await expect(page.locator('[data-closed="yes"]')).toHaveCount(1);
    const knob = page.locator('[data-part="knob"][data-index="1"]');
    const start = await knob.boundingBox();
    expect(start).not.toBeNull();
    if (!start) return;
    const before = await knob.evaluate((node) => node.getAttribute('style'));
    await touchDrag(
      page,
      { x: start.x + start.width / 2, y: start.y + start.height / 2 },
      { x: start.x + 70, y: start.y + 40 },
    );
    const after = await knob.evaluate((node) => node.getAttribute('style'));
    expect(after).not.toBe(before);
    const stage = await page.locator('.stage').boundingBox();
    expect(stage).not.toBeNull();
    if (!stage || !start) return;
    const beforeLon = (start.x + start.width / 2 - stage.x) / stage.width;
    await page.getByRole('button', { name: text(language, 'draw.use') }).tap();
    await expect(page.locator('[data-part="no-mode"]')).toBeVisible();
    const shaped = JSON.parse(
      (await page.locator('html').getAttribute('data-shape-request')) ?? '{}',
    ) as { geometry?: { coordinates?: number[][][] } };
    expect(await requestLog(page, 'shape')).toHaveLength(1);
    expect(await requestLog(page, 'area')).toHaveLength(1);
    const edited = shaped.geometry?.coordinates?.[0]?.[1];
    expect(edited).toBeTruthy();
    expect(Math.abs((edited?.[0] ?? beforeLon) - beforeLon)).toBeGreaterThan(
      0.01,
    );
  });

  test(`${language}: keyboard edits a polygon vertex and the request stays a shape`, async ({
    page,
  }) => {
    await page.goto(`/tests/visual/draw.html?lang=${language}&theme=dark`);
    const stage = await page.locator('.stage').boundingBox();
    await page
      .getByRole('button', { name: text(language, 'draw.polygon') })
      .focus();
    await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('Enter');
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');
    const knob = page.locator('[data-part="knob"][data-index="1"]');
    await knob.focus();
    const before = await knob.getAttribute('style');
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    expect(await knob.getAttribute('style')).not.toBe(before);
    await page.locator('[data-part="knob"][data-index="0"]').focus();
    await page.keyboard.press('Enter');
    await page
      .getByRole('button', { name: text(language, 'draw.use') })
      .focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-part="no-mode"]')).toBeVisible();
    const shaped = JSON.parse(
      (await page.locator('html').getAttribute('data-shape-request')) ?? '{}',
    ) as { geometry?: unknown };
    expect(shaped.geometry).toBeTruthy();
    expect(JSON.stringify(shaped)).not.toContain('situation');
    const followUp = await requestBody(page);
    expect(JSON.stringify(followUp)).not.toContain('situation');
    await expect(page.locator('.stage')).toHaveAttribute('dir', 'ltr');
    const after = await page.locator('.stage').boundingBox();
    expect(after).toEqual(stage);
  });

  test(`${language}: keyboard completes a radius and a drive without a pointer`, async ({
    page,
  }) => {
    await page.goto(`/tests/visual/draw.html?lang=${language}&theme=dark`);
    const stage = await page.locator('.stage').boundingBox();
    await page
      .getByRole('button', { name: text(language, 'draw.radius') })
      .focus();
    await page.keyboard.press('Enter');
    await page
      .getByRole('button', { name: text(language, 'draw.crosshair') })
      .focus();
    await page.keyboard.press('Enter');
    await page.locator('[data-preset="distance-c"]').focus();
    await page.keyboard.press('Enter');
    await page
      .getByRole('button', { name: text(language, 'draw.use') })
      .focus();
    await page.keyboard.press('Enter');
    await expect(
      page.locator('[data-outline="circle"] .area-line-accent'),
    ).toBeVisible();
    await expect(page.locator('[data-shape="radius"]')).toBeVisible();
    const radius = await requestBody(page);
    expect(await requestLog(page, 'area')).toHaveLength(1);
    expect(radius).toMatchObject({ mode: 'distance', cutoff: 1000 });
    expect(radius.pin).toBeUndefined();
    expect(await page.locator('.stage').boundingBox()).toEqual(stage);

    await page.goto(`/tests/visual/draw.html?lang=${language}&theme=dark`);
    await page
      .getByRole('button', { name: text(language, 'draw.travel') })
      .focus();
    await page.keyboard.press('Enter');
    await page
      .getByRole('button', { name: text(language, 'draw.crosshair') })
      .focus();
    await page.keyboard.press('Enter');
    await page.locator('[data-preset="drive-b"]').focus();
    await page.keyboard.press('Enter');
    await page
      .getByRole('button', { name: text(language, 'draw.use') })
      .focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-part="free-flow"]')).toBeVisible();
    const drive = await requestBody(page);
    expect(Object.keys(drive).sort()).toEqual([
      'cutoff',
      'latitude',
      'longitude',
      'mode',
    ]);
    expect(drive).toMatchObject({ mode: 'drive', cutoff: 10 });
    expect(JSON.stringify(drive)).not.toContain('hour_key');
  });

  test(`${language}: touch completes a radius and a walk without a mouse`, async ({
    page,
  }) => {
    await page.goto(`/tests/visual/draw.html?lang=${language}&theme=dark`);
    const stage = await page.locator('.stage').boundingBox();
    await page
      .getByRole('button', { name: text(language, 'draw.radius') })
      .tap();
    const overlay = page.locator('.area-overlay');
    const box = await overlay.boundingBox();
    expect(box).not.toBeNull();
    if (!box) return;
    await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
    await page.locator('[data-preset="distance-a"]').tap();
    await page.getByRole('button', { name: text(language, 'draw.use') }).tap();
    await expect(
      page.locator('[data-outline="circle"] .area-line-accent'),
    ).toBeVisible();
    const radius = await requestBody(page);
    expect(radius).toMatchObject({ mode: 'distance', cutoff: 250 });
    expect(await page.locator('.stage').boundingBox()).toEqual(stage);

    await page.goto(`/tests/visual/draw.html?lang=${language}&theme=dark`);
    await page
      .getByRole('button', { name: text(language, 'draw.travel') })
      .tap();
    const again = await page.locator('.area-overlay').boundingBox();
    expect(again).not.toBeNull();
    if (!again) return;
    await page.touchscreen.tap(
      again.x + again.width / 2,
      again.y + again.height / 2,
    );
    await page.locator('[data-preset="walk-a"]').tap();
    await page.getByRole('button', { name: text(language, 'draw.use') }).tap();
    await expect(page.locator('[data-part="mode-word"]')).toHaveText(
      text(language, 'draw.mode.walk'),
    );
    const walk = await requestBody(page);
    expect(walk).toMatchObject({ mode: 'walk', cutoff: 5 });
    expect(walk.pin).toBeUndefined();
  });

  test(`${language}: tap moves a vertex and Cancel clears the drawing`, async ({
    page,
  }) => {
    await page.goto(`/tests/visual/draw.html?lang=${language}&theme=dark`);
    await page
      .getByRole('button', { name: text(language, 'draw.polygon') })
      .tap();
    const box = await page.locator('.area-overlay').boundingBox();
    expect(box).not.toBeNull();
    if (!box) throw new Error('overlay absent');
    for (const [x, y] of [
      [0.55, 0.35],
      [0.75, 0.35],
      [0.75, 0.6],
    ]) {
      await page.touchscreen.tap(
        box.x + box.width * x!,
        box.y + box.height * y!,
      );
    }
    await page.locator('[data-part="knob"][data-index="0"]').tap();
    const knob = page.locator('[data-part="knob"][data-index="1"]');
    await knob.tap();
    const before = await knob.getAttribute('style');
    await page.touchscreen.tap(
      box.x + box.width * 0.85,
      box.y + box.height * 0.5,
    );
    expect(await knob.getAttribute('style')).not.toBe(before);
    await expect(page.locator('[data-part="knob"]')).toHaveCount(3);
    await page
      .getByRole('button', { name: text(language, 'draw.cancel') })
      .tap();
    await expect(page.locator('[data-phase="idle"]')).toHaveCount(1);
    await expect(page.locator('[data-part="knob"]')).toHaveCount(0);
    expect(await requestLog(page, 'area')).toHaveLength(0);
    expect(await requestLog(page, 'shape')).toHaveLength(0);
  });
}

test('the drawer covers the drawing controls on a tablet in both languages', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  for (const lang of ['en', 'ar'] as const) {
    await page.goto(`/tests/visual/draw.html?lang=${lang}&theme=dark&drawer=1`);
    await page.locator('.brief [data-fact-chip]').click();
    const tools = page.locator('.draw-tools');
    const drawer = page.locator('.drawer');
    await expect(drawer).toBeVisible();
    const covered = await tools.evaluate(
      (node) => node.closest('[inert]') !== null,
    );
    expect(covered).toBe(true);
    const toolBox = await tools.boundingBox();
    const drawerBox = await drawer.boundingBox();
    expect(toolBox).not.toBeNull();
    expect(drawerBox).not.toBeNull();
    if (!toolBox || !drawerBox) return;
    expect(drawerBox.x).toBeLessThanOrEqual(toolBox.x + 1);
    expect(drawerBox.y).toBeLessThanOrEqual(toolBox.y + 1);
    expect(drawerBox.x + drawerBox.width).toBeGreaterThanOrEqual(
      toolBox.x + toolBox.width - 1,
    );
    expect(drawerBox.y + drawerBox.height).toBeGreaterThanOrEqual(
      toolBox.y + toolBox.height - 1,
    );
    const before = await page
      .locator('[data-tool="polygon"]')
      .getAttribute('aria-pressed');
    await page.locator('[data-tool="polygon"]').click({ force: true });
    expect(
      await page.locator('[data-tool="polygon"]').getAttribute('aria-pressed'),
    ).toBe(before);
  }
});

test('knobs meet the target size and show a focus ring', async ({ page }) => {
  await page.goto('/tests/visual/draw.html?lang=en&theme=dark');
  await page.getByRole('button', { name: 'Polygon' }).focus();
  const ring = await page
    .getByRole('button', { name: 'Polygon' })
    .evaluate((node) => {
      const style = getComputedStyle(node);
      return style.outlineStyle;
    });
  expect(ring).not.toBe('none');
  await page.keyboard.press('Enter');
  await page.keyboard.press('Enter');
  const knob = page.locator('[data-part="knob"]').first();
  const size = await knob.boundingBox();
  expect(size).not.toBeNull();
  if (!size) return;
  expect(size.width).toBeGreaterThanOrEqual(44);
  expect(size.height).toBeGreaterThanOrEqual(44);
});

test('Arabic tools touch the stage edge that English leaves on the other side', async ({
  page,
}) => {
  await page.goto('/tests/visual/draw.html?lang=ar&theme=dark');
  await expect(page.locator('.stage')).toHaveAttribute('dir', 'ltr');
  await expect(page.locator('.draw-tools')).toHaveAttribute('dir', 'rtl');
  await expect(page.locator('.stage .draw-tools')).toHaveCount(0);
  const arabic = await edges(page);
  expect(Math.abs(arabic.toolsRight - arabic.stageRight)).toBeLessThan(2);
  await page.goto('/tests/visual/draw.html?lang=en&theme=dark');
  const english = await edges(page);
  expect(Math.abs(english.toolsLeft - english.stageLeft)).toBeLessThan(2);
});

test('drawing does not overflow the four viewports', async ({ page }) => {
  for (const viewport of VIEWPORTS) {
    await page.setViewportSize({
      width: viewport.width,
      height: viewport.height,
    });
    for (const lang of ['en', 'ar'] as const) {
      await page.goto(`/tests/visual/draw.html?lang=${lang}&theme=dark`);
      const overflow = await page.evaluate(
        () =>
          document.documentElement.scrollWidth >
          document.documentElement.clientWidth,
      );
      expect(overflow, `${viewport.width} ${lang}`).toBe(false);
    }
  }
});

async function requestLog(
  page: import('@playwright/test').Page,
  kind: 'area' | 'shape',
): Promise<unknown[]> {
  const name = kind === 'area' ? 'data-area-requests' : 'data-shape-requests';
  const raw = await page.locator('html').getAttribute(name);
  return JSON.parse(raw ?? '[]') as unknown[];
}

async function requestBody(
  page: import('@playwright/test').Page,
): Promise<Record<string, unknown>> {
  const raw = await page.locator('html').getAttribute('data-area-request');
  return JSON.parse(raw ?? '{}') as Record<string, unknown>;
}

async function touchDrag(
  page: import('@playwright/test').Page,
  from: { x: number; y: number },
  to: { x: number; y: number },
) {
  const client = await page.context().newCDPSession(page);
  await client.send('Input.dispatchTouchEvent', {
    type: 'touchStart',
    touchPoints: [{ x: Math.round(from.x), y: Math.round(from.y), id: 1 }],
  });
  await client.send('Input.dispatchTouchEvent', {
    type: 'touchMove',
    touchPoints: [{ x: Math.round(to.x), y: Math.round(to.y), id: 1 }],
  });
  await client.send('Input.dispatchTouchEvent', {
    type: 'touchEnd',
    touchPoints: [{ x: Math.round(to.x), y: Math.round(to.y), id: 1 }],
  });
  await client.detach();
}

async function edges(page: import('@playwright/test').Page) {
  const stage = await page.locator('.stage').boundingBox();
  const tools = await page.locator('.draw-tools').boundingBox();
  expect(stage).not.toBeNull();
  expect(tools).not.toBeNull();
  if (!stage || !tools) {
    return { stageRight: 0, toolsRight: 0, stageLeft: 0, toolsLeft: 0 };
  }
  return {
    stageRight: stage.x + stage.width,
    toolsRight: tools.x + tools.width,
    stageLeft: stage.x,
    toolsLeft: tools.x,
  };
}
