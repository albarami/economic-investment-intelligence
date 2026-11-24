import { expect, test, type Page } from '@playwright/test';

import { ANSWER_VIEWPORTS, PHONE_VIEWPORTS } from '../fixtures/viewports';

test('context levels open by keyboard and pointer in both languages', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    await page.goto(
      `/tests/visual/index.html?scene=context&lang=${lang}&theme=dark`,
    );
    const labels =
      lang === 'ar'
        ? ['الإجابة', 'المقارنة', 'الأدلة والمنهج']
        : ['Answer', 'Comparison', 'Evidence and method'];
    for (const card of await page.locator('.public-context-card').all()) {
      for (const label of labels) {
        const control = card.getByRole('button', { name: label, exact: true });
        const initial = await control.getAttribute('aria-expanded');
        await control.focus();
        await expect(control).toBeFocused();
        await page.keyboard.press('Enter');
        await expect(control).toHaveAttribute(
          'aria-expanded',
          initial === 'true' ? 'false' : 'true',
        );
        await page.keyboard.press('Space');
        await expect(control).toHaveAttribute('aria-expanded', initial!);
        if (initial === 'false') await control.tap();
        await expect(control).toHaveAttribute('aria-expanded', 'true');
        const content = page.locator(
          `[id="${await control.getAttribute('aria-controls')}"]`,
        );
        await expect(content).toBeVisible();
        await expect(content).toHaveAccessibleName(label);
        await page.keyboard.press('Tab');
        expect(
          await control.evaluate((node) => node === document.activeElement),
        ).toBe(false);
      }
    }
    await page.setViewportSize({ width: 390, height: 844 });
    for (const card of await page.locator('.public-context-card').all()) {
      expect(
        await card.evaluate((node) => node.scrollWidth <= node.clientWidth),
      ).toBe(true);
      expect(
        await card.evaluate((node) => getComputedStyle(node).direction),
      ).toBe(lang === 'ar' ? 'rtl' : 'ltr');
      if (lang === 'ar') {
        const leading = await card
          .locator('.context-level-body p')
          .evaluateAll((nodes) =>
            nodes.map((node) => {
              const style = getComputedStyle(node);
              return {
                actual: parseFloat(style.lineHeight),
                expected: Math.round(parseFloat(style.fontSize) * 1.6),
              };
            }),
          );
        for (const line of leading) expect(line.actual).toBe(line.expected);
      }
    }
    await page.setViewportSize({ width: 1440, height: 900 });
  }
});

test('Public context cards fit in both languages and themes', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    for (const theme of ['dark', 'light'] as const) {
      for (const width of [1024, 1440, 1920]) {
        await page.setViewportSize({ width, height: 1080 });
        const plant =
          process.env.EII_VISUAL_PLANT === 'line-height'
            ? '&plant=line-height'
            : '';
        await page.goto(
          `/tests/visual/index.html?scene=context&lang=${lang}&theme=${theme}${plant}`,
        );
        const cards = page.locator('[data-context-scene]');
        await expect(cards.locator('article')).toHaveCount(3);
        await expect(cards.locator('[data-fact-chip="value"]')).toHaveCount(3);
        expect(await cards.getAttribute('dir')).toBe(
          lang === 'ar' ? 'rtl' : 'ltr',
        );
        const fits = await cards
          .locator('article')
          .evaluateAll((nodes) =>
            nodes.every((node) => node.scrollWidth <= node.clientWidth),
          );
        expect(fits).toBe(true);
        if (lang === 'ar') {
          const typography = await cards
            .locator('article p[data-caveat]')
            .evaluateAll((nodes) =>
              nodes.map((node) => {
                const actual = getComputedStyle(node);
                const probe = document.createElement('span');
                probe.style.font = 'var(--eii-type-body)';
                node.append(probe);
                const token = getComputedStyle(probe);
                const result = {
                  fontSize: parseFloat(actual.fontSize),
                  lineHeight: parseFloat(actual.lineHeight),
                  tokenLineHeight: parseFloat(token.lineHeight),
                };
                probe.remove();
                return result;
              }),
            );
          // DES-28: body token and inherited prose use whole-pixel Arabic leading.
          expect(typography).toEqual(
            typography.map(({ fontSize }) => ({
              fontSize,
              lineHeight: Math.round(fontSize * 1.6),
              tokenLineHeight: Math.round(fontSize * 1.6),
            })),
          );
        }
        const prose = await cards.evaluate((node) => {
          const clone = node.cloneNode(true) as HTMLElement;
          clone
            .querySelectorAll('[data-fact-chip]')
            .forEach((chip) => chip.remove());
          return clone.textContent;
        });
        expect(prose).not.toMatch(/\p{N}/u);
        if (width === 1440)
          await cards.screenshot({
            path: `../.overnight/evidence/context-${lang}-${theme}.png`,
          });
      }
    }
  }
});

test('reduced motion drops the drawer entrance', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/tests/visual/index.html?lang=en&theme=dark');
  await page.locator('.brief [data-fact-chip]').click();
  const name = await page
    .getByRole('dialog')
    .evaluate((node) => getComputedStyle(node).animationName);
  expect(name).toBe('none');
});

test('nothing overflows at the answer viewports', async ({ page }) => {
  for (const viewport of ANSWER_VIEWPORTS) {
    await page.setViewportSize({
      width: viewport.width,
      height: viewport.height,
    });
    for (const lang of ['en', 'ar'] as const) {
      for (const theme of ['dark', 'light'] as const) {
        await page.goto(`/tests/visual/index.html?lang=${lang}&theme=${theme}`);
        for (const drawer of ['closed', 'open'] as const) {
          if (drawer === 'open') {
            await page.locator('.brief [data-fact-chip]').click();
          }
          await visibleAnswer(
            page,
            drawer === 'open'
              ? '.drawer [data-fact-chip="value"]'
              : '.brief [data-fact-chip]',
          );
          const overflow = await page.evaluate(
            () =>
              document.documentElement.scrollWidth >
              document.documentElement.clientWidth,
          );
          expect(overflow, `${viewport.width} ${lang} ${theme} ${drawer}`).toBe(
            false,
          );
          if (drawer === 'open') {
            await page.keyboard.press('Escape');
          }
        }
      }
    }
  }
});

async function visibleAnswer(page: Page, selector = '.brief [data-fact-chip]') {
  const answer = page.locator(selector);
  await expect(answer).toBeVisible();
  await expect(answer).toBeInViewport({ ratio: 1 });
  const shown = await answer.evaluate((node) => {
    const box = node.getBoundingClientRect();
    const hit = document.elementFromPoint(
      box.x + box.width / 2,
      box.y + box.height / 2,
    );
    return (
      box.x >= 0 &&
      box.y >= 0 &&
      box.right <= window.innerWidth &&
      box.bottom <= window.innerHeight &&
      node.contains(hit)
    );
  });
  expect(
    shown,
    'the answer must be inside the viewport and above the map/sheet',
  ).toBe(true);
  const overflow = await page
    .locator('.shell')
    .evaluate(
      (node) =>
        node.scrollWidth > node.clientWidth ||
        node.scrollHeight > node.clientHeight,
    );
  expect(overflow, 'the shell must not overflow either axis').toBe(false);
}

for (const viewport of PHONE_VIEWPORTS) {
  for (const lang of ['en', 'ar'] as const) {
    for (const theme of ['dark', 'light'] as const) {
      test(`phone answer ${viewport.width} ${lang} ${theme}: visible and contained`, async ({
        page,
      }) => {
        await page.setViewportSize(viewport);
        await page.goto(`/tests/visual/index.html?lang=${lang}&theme=${theme}`);
        await visibleAnswer(page);
      });

      test(`phone sheet ${viewport.width} ${lang} ${theme}: answer, map and keyboard`, async ({
        page,
      }) => {
        await page.setViewportSize(viewport);
        await page.goto(`/tests/visual/index.html?lang=${lang}&theme=${theme}`);
        // The absent-asset Stage has no map controls. Supply one to test that
        // the nonmodal sheet can yield keyboard focus back to the map.
        await page.locator('.stage').evaluate((node) => {
          const control = document.createElement('button');
          control.textContent = node.getAttribute('aria-label');
          control.dataset.testStageControl = '';
          control.style.position = 'absolute';
          control.style.insetBlockStart = '80px';
          control.style.insetInlineEnd = '16px';
          node.append(control);
        });
        const toggle = page.locator('.sheet-toggle');
        await expect(toggle).toBeVisible();
        await expect(toggle).toHaveAccessibleName(
          lang === 'ar' ? 'توسيع الموجز' : 'Expand Brief',
        );
        await expect(toggle).toHaveAttribute('aria-expanded', 'false');
        await expect(page.locator('.shell')).toHaveAttribute(
          'dir',
          lang === 'ar' ? 'rtl' : 'ltr',
        );
        await expect(page.locator('.stage')).toHaveAttribute('dir', 'ltr');
        let collapsedHeight = 0;
        for (const expanded of [false, true]) {
          if (expanded) {
            await toggle.focus();
            await page.keyboard.press('Enter');
          }
          await expect(toggle).toHaveAttribute(
            'aria-expanded',
            String(expanded),
          );
          await expect(toggle).toHaveAccessibleName(
            lang === 'ar'
              ? expanded
                ? 'طي الموجز'
                : 'توسيع الموجز'
              : expanded
                ? 'Collapse Brief'
                : 'Expand Brief',
          );
          await visibleAnswer(page);
          if (viewport.width === 375) {
            await page.screenshot({
              path: test
                .info()
                .outputPath(expanded ? 'expanded.png' : 'collapsed.png'),
            });
          }
          const geometry = await page
            .locator('.answer-sheet')
            .evaluate((node) => {
              const box = node.getBoundingClientRect();
              // S3-T13's toolbar occupies the start side of the map column.
              // Probe the exposed map beside it in either writing direction.
              const exposed = document.elementFromPoint(
                document.documentElement.dir === 'rtl'
                  ? 1
                  : window.innerWidth - 1,
                box.y / 2,
              );
              return {
                bottom: box.bottom,
                top: box.top,
                height: box.height,
                mapVisible: Boolean(exposed?.closest('.stage')),
              };
            });
          expect(geometry.bottom).toBe(viewport.height);
          if (expanded)
            expect(geometry.height).toBeGreaterThan(collapsedHeight);
          else collapsedHeight = geometry.height;
          expect(geometry.top).toBeGreaterThan(viewport.height / 5);
          expect(geometry.mapVisible).toBe(true);
          await expect(
            page.locator('[data-part="attribution"]'),
          ).toBeInViewport();
          const chip = page.locator('.brief [data-fact-chip]');
          await chip.focus();
          await page.keyboard.press('Enter');
          const drawer = page.getByRole('dialog');
          await expect(drawer).toBeVisible();
          await visibleAnswer(page, '.drawer [data-fact-chip="value"]');
          await expect(page.locator('.answer-sheet')).toHaveAttribute(
            'inert',
            '',
          );
          await page.keyboard.press('Shift+Tab');
          expect(
            await page.evaluate(() =>
              Boolean(document.activeElement?.closest('[role="dialog"]')),
            ),
          ).toBe(true);
          await page.keyboard.press('Tab');
          await page.keyboard.press('Escape');
          await expect(chip).toBeFocused();
          await expect(toggle).toHaveAttribute(
            'aria-expanded',
            String(expanded),
          );
          await visibleAnswer(page);
          await toggle.focus();
          await page.keyboard.press('Shift+Tab');
          await expect(page.locator('[data-test-stage-control]')).toBeFocused();
          await page.keyboard.press('Tab');
          await expect(toggle).toBeFocused();
          await page.keyboard.press('Tab');
          await expect(chip).toBeFocused();
        }
        await page.keyboard.press('Escape');
        await expect(toggle).toHaveAttribute('aria-expanded', 'false');
        await expect(toggle).toBeFocused();
        expect(
          (await page.locator('.answer-sheet').boundingBox())?.height,
        ).toBe(collapsedHeight);
        await page.keyboard.press('Tab');
        await expect(page.locator('.brief [data-fact-chip]')).toBeFocused();
        await page.keyboard.press('Shift+Tab');
        await expect(toggle).toBeFocused();
        await page.setViewportSize({ width: 1440, height: 900 });
        await expect(toggle).toBeHidden();
        await expect(page.locator('.brief')).toBeFocused();
        expect(
          await page
            .locator('.answer-sheet')
            .evaluate((node) => getComputedStyle(node).display),
        ).toBe('contents');
      });
    }
  }
}
