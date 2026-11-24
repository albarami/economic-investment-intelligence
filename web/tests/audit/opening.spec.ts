import { test, expect } from '../e2e/opening-fixture';
import { openingProblems, openingReport } from './opening-audit';
import path from 'node:path';
import { mkdirSync, writeFileSync } from 'node:fs';

const SIZES = [
  [360, 640],
  [640, 360],
  [390, 844],
  [844, 390],
  [768, 1024],
  [1024, 768],
  [1366, 768],
  [1440, 900],
  [1920, 1080],
  [2560, 1440],
  [3440, 1440],
  [3840, 2160],
] as const;
const EVIDENCE = path.resolve('../.overnight/tmp/S3-T10-captures');
for (const [width, height] of SIZES)
  for (const lang of ['en', 'ar'] as const)
    for (const theme of ['dark', 'light'] as const) {
      test(`opening audit ${width}x${height} ${lang} ${theme}`, async ({
        page,
        mounted,
      }) => {
        await page.setViewportSize({ width, height });
        await page.goto(`${mounted.origin}/?lang=${lang}&theme=${theme}`);
        await page.locator('.stage[data-state="ready"]').waitFor();
        await page.evaluate(() => document.fonts.ready);
        const report = await openingReport(page);
        mkdirSync(EVIDENCE, { recursive: true });
        writeFileSync(
          path.join(
            EVIDENCE,
            `contrast-${width}x${height}-${lang}-${theme}.json`,
          ),
          JSON.stringify(report.contrast, null, 2) + '\n',
        );
        console.log(
          'attribution contrast ' +
            JSON.stringify(
              report.contrast.filter(
                (row) => row.selector === '.stage-credits',
              ),
            ),
        );
        await expect(page.locator('[data-scene="opening"] h1')).toBeVisible();
        await expect(
          page.locator('[data-action="guided-story"]'),
        ).toBeVisible();
        expect(await openingProblems(page)).toEqual([]);
        const language = page.locator('[data-action="language"]');
        await language.focus();
        expect(
          await language.evaluate(
            (node) => getComputedStyle(node).outlineStyle,
          ),
        ).not.toBe('none');
        mkdirSync(EVIDENCE, { recursive: true });
        await page.screenshot({
          path: path.join(
            EVIDENCE,
            `opening-${width}x${height}-${lang}-${theme}.png`,
          ),
        });
        await page.locator('[data-action="guided-story"]').click();
        await expect(page.locator('[data-scene="area"]')).toBeVisible();
        expect(await openingProblems(page)).toEqual([]);
        await page.screenshot({
          path: path.join(
            EVIDENCE,
            `area-${width}x${height}-${lang}-${theme}.png`,
          ),
        });
        await page
          .locator('[data-picker="activity"] input')
          .fill(lang === 'en' ? 'INVENTED-Craft' : 'حرفة مخترعة');
        await page
          .locator('[data-picker="activity"] button[type="submit"]')
          .click();
        await page.locator('[data-picker="activity"] [data-candidate]').click();
        await page
          .locator('[data-picker="place"] input')
          .fill(lang === 'en' ? 'INVENTED-Garden' : 'حديقة مخترعة');
        await page
          .locator('[data-picker="place"] button[type="submit"]')
          .click();
        await page.locator('[data-picker="place"] [data-candidate]').click();
        await page.locator('[data-place-preset="walk-a"]').click();
        await expect(page.locator('[data-action="story-next"]')).toBeEnabled();
        await page.locator('[data-action="story-next"]').click();
        const card = page.locator('[data-context-family="night_lights"]');
        await expect(card).toBeVisible();
        const creditStack = await page
          .locator('.stage-credits')
          .evaluate((node) => {
            const overlay = node
              .closest('.stage')!
              .querySelector('.area-overlay')!;
            return {
              credits: getComputedStyle(node).zIndex,
              overlay: getComputedStyle(overlay).zIndex,
            };
          });
        expect(Number(creditStack.credits)).toBeGreaterThan(
          Number(creditStack.overlay),
        );
        const caveat = card.locator(
          '[data-caveat="night_lights_not_activity"] bdi',
        );
        expect(
          await caveat.evaluate((node) => getComputedStyle(node).direction),
        ).toBe(lang === 'ar' ? 'rtl' : 'ltr');
        const chip = card.locator('[data-fact-chip="value"]');
        await chip.scrollIntoViewIfNeeded();
        expect(await openingProblems(page)).toEqual([]);
        await page.screenshot({
          path: path.join(
            EVIDENCE,
            `answer-${width}x${height}-${lang}-${theme}.png`,
          ),
        });
        for (const level of ['comparison', 'evidence']) {
          await card
            .locator(`[data-context-level="${level}"] > button`)
            .click();
          await card
            .locator(`[data-context-level="${level}"] > button`)
            .scrollIntoViewIfNeeded();
          expect(await openingProblems(page)).toEqual([]);
          await page.screenshot({
            path: path.join(
              EVIDENCE,
              `${level}-${width}x${height}-${lang}-${theme}.png`,
            ),
          });
        }
        await chip.click();
        const dialog = page.getByRole('dialog');
        await expect(dialog).toBeVisible();
        await dialog.evaluate((node) =>
          Promise.all(
            node.getAnimations().map((animation) => animation.finished),
          ),
        );
        const drawer = await dialog.boundingBox();
        expect(drawer).not.toBeNull();
        if (width >= 1200)
          expect(
            lang === 'ar' ? drawer!.x : drawer!.x + drawer!.width,
          ).toBeCloseTo(lang === 'ar' ? 0 : width, 0);
        const pairs = await dialog.locator('.chain-pair').evaluateAll((nodes) =>
          nodes.map((node) => ({
            align: getComputedStyle(node).alignItems,
            value: getComputedStyle(node.querySelector('.chain-value')!)
              .textAlign,
          })),
        );
        expect(pairs.length).toBeGreaterThan(0);
        for (const pair of pairs)
          expect(pair).toEqual({ align: 'flow-start', value: 'start' });
        if (lang === 'ar') {
          await caveat.evaluate((node) => node.setAttribute('dir', 'ltr'));
          expect(await openingProblems(page)).toContain(
            'wrong-caveat-direction',
          );
          await caveat.evaluate((node) => node.removeAttribute('dir'));
        }
        expect(await openingProblems(page)).toEqual([]);
        await page.screenshot({
          path: path.join(
            EVIDENCE,
            `drawer-${width}x${height}-${lang}-${theme}.png`,
          ),
        });
        await page.keyboard.press('Escape');
        await expect(chip).toBeFocused();
      });
    }

test('overflow, numeral, origin, Arabic clipping and mirrored-map plants fail their own guards', async ({
  page,
  mounted,
}) => {
  await page.goto(mounted.origin + '/?lang=ar');
  await page.locator('.stage[data-state="ready"]').waitFor();
  expect(await openingProblems(page)).toEqual([]);
  await page.evaluate(() => {
    const title = document.querySelector<HTMLElement>('.public-opening h1')!;
    title.textContent += ' 123 Synthetic';
    title.setAttribute('aria-label', 'INVENTED 123');
    title.style.width = '5000px';
    title.style.height = '4px';
    title.style.overflow = 'hidden';
    title.style.lineHeight = '1';
    const overflow = document.createElement('div');
    overflow.style.width = '5000px';
    overflow.style.height = '1px';
    document.body.append(overflow);
    document.querySelector('.stage')!.setAttribute('dir', 'rtl');
    document.querySelector('.shell')!.setAttribute('dir', 'ltr');
    const action = document.querySelector<HTMLElement>(
      '[data-action="guided-story"]',
    )!;
    action.style.cssText =
      `position:fixed;left:${innerWidth + 20}px;top:0;` +
      'min-width:0;min-height:0;width:4px;height:4px;padding:0;border:0';
  });
  const found = await openingProblems(page);
  for (const problem of [
    'page-overflow',
    'loose-numeral',
    'accessible-numeral',
    'origin-word',
    'clipped-copy',
    'arabic-type',
    'mirrored-map',
    'wrong-reading-direction',
    'opening-outside-viewport',
    'small-target',
    'control-overflow',
  ])
    expect(found).toContain(problem);
});

test('wall greyscale and reduced-motion opening preserve the same controls', async ({
  page,
  mounted,
}) => {
  await page.setViewportSize({ width: 3840, height: 2160 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  for (const lang of ['en', 'ar']) {
    await page.goto(mounted.origin + '/?lang=' + lang);
    await page.locator('.stage[data-state="ready"]').waitFor();
    await page.addStyleTag({ content: 'html { filter: grayscale(1); }' });
    expect(await openingProblems(page)).toEqual([]);
    await page.screenshot({
      path: path.join(EVIDENCE, `wall-greyscale-${lang}.png`),
    });
  }
});

test('a planted unreadable control fails the contrast audit', async ({
  page,
  mounted,
}) => {
  await page.goto(mounted.origin);
  await page.locator('.stage[data-state="ready"]').waitFor();
  await page.locator('[data-action="guided-story"]').evaluate((node) => {
    const button = node as HTMLElement;
    button.style.color = 'rgb(20,20,20)';
    button.style.backgroundColor = 'rgb(20,20,20)';
  });
  expect(await openingProblems(page)).toContain('contrast');
});

test('map attribution has its own measured plate and a transparent plant is refused', async ({
  page,
  mounted,
}) => {
  for (const theme of ['dark', 'light']) {
    await page.goto(mounted.origin + '/?theme=' + theme);
    await page.locator('.stage[data-state="ready"]').waitFor();
    const report = await openingReport(page);
    expect(report.problems).toEqual([]);
    const measured = report.contrast.filter(
      (row) => row.selector === '.stage-credits',
    );
    expect(measured).toHaveLength(1);
    console.log(
      'attribution contrast ' + theme + ' ' + JSON.stringify(measured),
    );
    expect(measured[0]!.ratio).toBeGreaterThanOrEqual(4.5);
    await page.locator('.stage-credits').evaluate((node) => {
      (node as HTMLElement).style.backgroundColor = 'transparent';
    });
    expect(await openingProblems(page)).toContain('attribution-plate');
  }
});

test('opening audit leaves focus where it was', async ({ page, mounted }) => {
  await page.goto(mounted.origin + '/?lang=en');
  await page.locator('.stage[data-state="ready"]').waitFor();
  const control = page.locator('[data-action="guided-story"]');
  await control.focus();
  await expect(control).toBeFocused();
  expect(await openingProblems(page)).toEqual([]);
  await expect(control).toBeFocused();
});

test('a planted control cover is rejected when it hides the usable map', async ({
  page,
  mounted,
}) => {
  await page.goto(mounted.origin);
  await page.locator('.stage[data-state="ready"]').waitFor();
  await page.evaluate(() => {
    const cover = document.createElement('div');
    cover.style.cssText =
      'position:absolute;inset:0;z-index:99;background:black';
    document.querySelector('.stage')!.append(cover);
  });
  expect(await openingProblems(page)).toContain('map-hidden-by-controls');
});
