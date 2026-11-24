import { expect, test, type Page } from '@playwright/test';

import { NAMED_SIZES } from '../fixtures/viewports';

const VIEWPORTS = [
  { width: 3840, height: 2160 },
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1024, height: 768 },
] as const;

test('S3-T10 negative context keeps its withheld reason in both languages and themes', async ({
  page,
}) => {
  for (const [width, height] of [
    [390, 844],
    [1440, 900],
  ] as const)
    for (const lang of ['en', 'ar'] as const)
      for (const theme of ['dark', 'light'] as const) {
        await page.setViewportSize({ width, height });
        await page.goto(
          `/tests/visual/index.html?lang=${lang}&theme=${theme}&scene=context&mark=suppressed`,
        );
        await page.evaluate(() => document.fonts.ready);
        const card = page.locator('[data-context-family="night_lights"]');
        await expect(card.locator('[data-mark="withheld"]')).toBeVisible();
        const reason = card.locator('.context-withheld p');
        await expect(reason).toBeVisible();
        expect((await reason.innerText()).trim()).not.toBe('');
        const marker = await card
          .locator('.context-withheld .chip-withheld')
          .evaluate((node) => {
            const word = node.querySelector('.mark-word')!;
            return {
              wordHeight: word.getBoundingClientRect().height,
              lineHeight: parseFloat(getComputedStyle(word).lineHeight),
              markerHeight: node.getBoundingClientRect().height,
            };
          });
        expect(marker.wordHeight).toBeLessThanOrEqual(marker.lineHeight);
        expect(marker.markerHeight).toBeGreaterThanOrEqual(marker.wordHeight);
        await expect(
          card.locator('[data-fact-chip="value"] .chip-num'),
        ).toHaveCount(0);
        await expect(
          card.locator('[data-fact-chip="reference"]').first(),
        ).toBeVisible();
        expect(await card.innerText()).not.toMatch(/987|(?<![0-9])0(?![0-9])/);
        await card.scrollIntoViewIfNeeded();
        await page.screenshot({
          path: `../.overnight/tmp/S3-T10-captures/negative-withheld-${width}x${height}-${lang}-${theme}.png`,
        });
      }
});

test('Enter opens the chain and Escape returns focus', async ({ page }) => {
  await page.goto('/tests/visual/index.html?lang=en&theme=dark');
  const chip = page.locator('.brief [data-fact-chip]');
  await chip.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(chip).toBeFocused();
});

test('a tap opens the chain', async ({ page }) => {
  await page.goto('/tests/visual/index.html?lang=en&theme=dark');
  await page.locator('.brief [data-fact-chip]').tap();
  await expect(page.getByRole('dialog')).toBeVisible();
});

test('Arabic keeps the stage unmirrored', async ({ page }) => {
  await page.goto('/tests/visual/index.html?lang=ar&theme=light');
  await expect(page.locator('.shell')).toHaveAttribute('dir', 'rtl');
  await expect(page.locator('.stage')).toHaveAttribute('dir', 'ltr');
  const chip = page.locator('.brief [data-fact-chip]');
  await chip.focus();
  await page.keyboard.press('Enter');
  await page.keyboard.press('Escape');
  await expect(chip).toBeFocused();
});

test('withheld and status words stay beside their shapes in greyscale', async ({
  page,
}) => {
  await page.goto(
    '/tests/visual/index.html?lang=en&theme=dark&scene=open&mark=suppressed',
  );
  await page.evaluate(() => {
    document.documentElement.style.filter = 'grayscale(1)';
  });
  const shapes = await page
    .locator('.drawer [data-mark]')
    .evaluateAll((nodes) =>
      nodes.map((node) => ({
        mark: node.getAttribute('data-mark'),
        shape: node.getAttribute('data-shape'),
        word: node.textContent ?? '',
      })),
    );
  expect(shapes.map((mark) => mark.mark).sort()).toEqual([
    'status',
    'withheld',
  ]);
  for (const mark of shapes) {
    expect(mark.shape).toBeTruthy();
    expect(mark.word.trim().length).toBeGreaterThan(0);
  }
});

test('the ten digits share one width', async ({ page }) => {
  await page.goto('/tests/visual/index.html?lang=en&theme=dark');
  const widths = await page
    .locator('[data-measure="digits"] span')
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getBoundingClientRect().width),
    );
  expect(widths).toHaveLength(10);
  const first = widths[0] ?? 0;
  for (const width of widths) expect(Math.abs(width - first)).toBeLessThan(0.5);
});

test('a numeric run stays isolated inside the chip', async ({ page }) => {
  await page.goto('/tests/visual/index.html?lang=ar&theme=dark');
  const nested = page.locator(
    '.brief [data-fact-chip] bdi.chip-root bdi.chip-num',
  );
  await expect(nested.first()).toBeVisible();
  await expect(nested.first()).toHaveAttribute('dir', 'ltr');
});

const MIXED = ['range', 'negative', 'percent', 'currency', 'place'] as const;

test('five mixed-direction cases keep their isolates', async ({ page }) => {
  await page.goto('/tests/visual/index.html?lang=ar&theme=light');
  for (const name of MIXED) {
    await expect(page.locator(`[data-case="${name}"]`)).toHaveAttribute(
      'dir',
      'rtl',
    );
  }
  for (const name of ['range', 'negative', 'percent', 'currency'] as const) {
    const isolate = page.locator(
      `[data-case="${name}"] bdi.chip-root bdi.chip-num`,
    );
    await expect(isolate.first()).toHaveAttribute('dir', 'ltr');
  }
  await expect(
    page.locator('[data-case="range"] bdi.chip-num').last(),
  ).toContainText('\u2013');
  await expect(page.locator('[data-case="currency"]')).toContainText('ر.ق');
  await expect(page.locator('[data-case="place"] bdi')).toHaveText(
    'Sample Reach',
  );
});

const CLASS_WORD =
  /(?:^|[^\p{L}\p{N}])(?:Public|Private|protected|Suppressed|Synthetic|Simulated|fictional|invented|fixture|Demonstrator|عام|العام|عامة|العامة|علني|العلني|علنية|العلنية|اصطناعي|الاصطناعي|اصطناعية|الاصطناعية|محاكاة|المحاكاة|بالمحاكاة|محجوب|المحجوب|محجوبة|المحجوبة)(?=$|[^\p{L}\p{N}])/iu;

async function faceFaults(page: Page) {
  return page.evaluate((pattern) => {
    const word = new RegExp(pattern, 'iu');
    const faults: string[] = [];
    const root = document.body;
    const seen = root.innerText;
    if (word.test(seen)) faults.push('class-word');
    for (const node of root.querySelectorAll('[aria-label]')) {
      const label = node.getAttribute('aria-label') ?? '';
      if (word.test(label)) faults.push('class-word-name');
    }
    for (const node of root.querySelectorAll('body *')) {
      if (node.closest('[role="dialog"]')) continue;
      const style = getComputedStyle(node);
      const decoration = style.textDecorationLine;
      const form = style.textDecorationStyle;
      if (
        decoration.includes('underline') &&
        (form === 'solid' || form === 'dotted' || form === 'dashed')
      ) {
        faults.push('class-underline');
      }
      const image = style.backgroundImage;
      if (/repeating-linear-gradient|hatch|texture/i.test(image)) {
        faults.push('class-hatch');
      }
    }
    return faults;
  }, CLASS_WORD.source);
}

test('the closed face has no class word or mark', async ({ page }) => {
  for (const lang of ['en', 'ar'] as const) {
    for (const theme of ['dark', 'light'] as const) {
      await page.goto(`/tests/visual/index.html?lang=${lang}&theme=${theme}`);
      expect(await faceFaults(page)).toEqual([]);
    }
  }
});

test('map attribution is visible in both directions', async ({ page }) => {
  const foreign: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.origin !== 'http://127.0.0.1:41731') foreign.push(request.url());
  });
  await page.goto('/tests/visual/index.html?lang=en&theme=dark');
  await expect(page.locator('[data-part="attribution"]')).toContainText(
    'OpenStreetMap',
  );
  await expect(page.locator('[data-part="attribution"]')).toContainText(
    'Protomaps',
  );
  await expect(page.locator('.shell')).toHaveAttribute('dir', 'ltr');
  await page.goto('/tests/visual/index.html?lang=ar&theme=dark');
  await expect(page.locator('.shell')).toHaveAttribute('dir', 'rtl');
  await expect(page.locator('[data-part="attribution"]')).toContainText(
    'OpenStreetMap',
  );
  await expect(page.locator('[data-part="attribution"]')).toContainText(
    'Protomaps',
  );
  expect(foreign).toEqual([]);
});

test('the empty page requests no tile', async ({ page }) => {
  const tiles: string[] = [];
  const requests: string[] = [];
  page.on('request', (request) => {
    const url = request.url();
    requests.push(url);
    if (url.includes('pmtiles') || url.includes('/tiles/')) tiles.push(url);
  });
  await page.goto('/');
  await expect(page.getByRole('alert')).toBeVisible();
  expect(tiles).toEqual([]);
  const own = new URL(page.url()).origin;
  for (const url of requests) expect(new URL(url).origin).toBe(own);
});

for (const viewport of VIEWPORTS) {
  test(`drawer placement at ${viewport.width}`, async ({ page }) => {
    await page.setViewportSize({
      width: viewport.width,
      height: viewport.height,
    });
    await page.goto('/tests/visual/index.html?lang=en&theme=dark');
    await page.locator('.brief [data-fact-chip]').click();
    await drawerAtRest(page);
    const box = await page.getByRole('dialog').boundingBox();
    expect(box).not.toBeNull();
    if (viewport.width === 1024) expect(box?.width).toBeGreaterThan(900);
    else expect(box?.width).toBeLessThan(viewport.width);
  });
}

test('list items carry no browser marker', async ({ page }) => {
  await page.goto('/tests/visual/index.html?lang=en&theme=dark');
  await page.locator('.brief [data-fact-chip]').click();
  const types = await page
    .locator('li')
    .evaluateAll((nodes) =>
      nodes.map((node) => getComputedStyle(node).listStyleType),
    );
  expect(types.length).toBeGreaterThan(0);
  for (const type of types) expect(type).toBe('none');
});

test('tab stays inside the dialog in both directions', async ({ page }) => {
  for (const lang of ['en', 'ar'] as const) {
    await page.goto(`/tests/visual/index.html?lang=${lang}&theme=dark`);
    const chip = page.locator('.brief [data-fact-chip]');
    await chip.focus();
    await page.keyboard.press('Enter');
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(page.locator('.brief')).toHaveAttribute('inert', '');
    await expect(page.locator('.stage')).toHaveAttribute('inert', '');
    await expect(dialog.locator('[data-figure="true"]')).toHaveCount(1);
    await expect(dialog.locator('button[data-fact-chip]')).toHaveCount(0);
    await page.keyboard.press('Tab');
    await expect(dialog).toContainText('');
    const inside = await page.evaluate(
      () => document.activeElement?.closest('[role="dialog"]') !== null,
    );
    expect(inside).toBe(true);
    await page.keyboard.press('Shift+Tab');
    const back = await page.evaluate(
      () => document.activeElement?.closest('[role="dialog"]') !== null,
    );
    expect(back).toBe(true);
    const briefFocused = await page.evaluate(
      () => document.activeElement?.closest('.brief') !== null,
    );
    expect(briefFocused).toBe(false);
  }
});

test('the drawer is at the inline end and within the tablet', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/tests/visual/index.html?lang=${lang}&theme=dark`);
    await page.locator('.brief [data-fact-chip]').click();
    await drawerAtRest(page);
    const wide = await page.getByRole('dialog').boundingBox();
    expect(wide).not.toBeNull();
    if (lang === 'en')
      expect((wide?.x ?? 0) + (wide?.width ?? 0)).toBeGreaterThan(1400);
    else expect(wide?.x ?? 999).toBeLessThan(20);
    await page.setViewportSize({ width: 1024, height: 768 });
    const sheet = await page.getByRole('dialog').boundingBox();
    expect(sheet?.height ?? 0).toBeLessThanOrEqual(768);
    expect(sheet?.y ?? -1).toBeGreaterThanOrEqual(0);
  }
});

test('an Arabic drawer isolates a bracketed version', async ({ page }) => {
  await page.goto('/tests/visual/index.html?lang=ar&theme=dark&marked=1');
  await page.locator('.brief [data-fact-chip]').click();
  const value = page.locator('.drawer [data-part="method"] .chain-value');
  await expect(value).toHaveText(/\(v2\)$/);
});

function onInlineEnd(
  box: { x: number; width: number },
  viewport: number,
  lang: 'en' | 'ar',
): boolean {
  if (lang === 'ar') return box.x < 20;
  return box.x + box.width > viewport - 40;
}

test('focus order is close then receipt then close in both languages', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    await page.goto(`/tests/visual/index.html?lang=${lang}&theme=dark`);
    await page.locator('.brief [data-fact-chip]').focus();
    await page.keyboard.press('Enter');
    const close = page.locator('.drawer-close');
    const receipt = page.locator('.drawer [data-part="receipt"]');
    await expect(close).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(receipt).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(close).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(receipt).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(close).toBeFocused();
  }
});

test('a planted wrong-side style fails the inline-end check', async ({
  page,
}) => {
  for (const lang of ['en', 'ar'] as const) {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/tests/visual/index.html?lang=${lang}&theme=dark`);
    await page.locator('.brief [data-fact-chip]').click();
    await drawerAtRest(page);
    await expect
      .poll(async () => {
        const box = await page.getByRole('dialog').boundingBox();
        return box ? onInlineEnd(box, 1440, lang) : false;
      })
      .toBe(true);
    const planted = await page
      .locator('[data-plant="wrong-side"]')
      .boundingBox();
    if (!planted) throw new Error('plant missing');
    expect(onInlineEnd(planted, 1440, lang)).toBe(false);
  }
});

test('opened scenes name no origin and keep the withheld and status words', async ({
  page,
}) => {
  // Decision 0035 items 1 and 2: no origin class word in any language.
  const origin = {
    en: ['Public', 'Synthetic', 'Simulated'],
    ar: [
      '\u0639\u0644\u0646\u064a',
      '\u0627\u0635\u0637\u0646\u0627\u0639\u064a',
      '\u0628\u0627\u0644\u0645\u062d\u0627\u0643\u0627\u0629',
    ],
  } as const;
  const withheld = {
    en: 'Suppressed',
    ar: '\u0645\u062d\u062c\u0648\u0628',
  } as const;
  const statuses = {
    en: {
      observed: 'Observed',
      inferred: 'Inferred',
      still_to_test: 'Still to test',
    },
    ar: {
      observed: 'مرصود',
      inferred: 'مستنتج',
      still_to_test: 'لم يُختبر بعد',
    },
  } as const;
  for (const lang of ['en', 'ar'] as const) {
    await page.goto(`/tests/visual/index.html?lang=${lang}&theme=dark`);
    const closed = await page.locator('body').innerText();
    expect(closed).not.toContain(withheld[lang]);
    for (const mark of [
      'public',
      'synthetic',
      'simulated',
      'suppressed',
    ] as const) {
      await page.goto(
        `/tests/visual/index.html?lang=${lang}&theme=dark&scene=open&mark=${mark}`,
      );
      const dialog = page.getByRole('dialog');
      await expect(dialog).toBeVisible();
      const seen = await dialog.innerText();
      for (const word of origin[lang]) expect(seen).not.toContain(word);
      await expect(page.locator('[data-mark="class"]')).toHaveCount(0);
      await expect(page.locator('[data-input-class]')).toHaveCount(0);
      await expect(
        page.locator('.drawer [data-part="status"] [data-mark="status"]'),
      ).toBeVisible();
      await expect(page.locator('.drawer [data-part="method"]')).toBeVisible();
      const lock = page.locator(
        '.drawer [data-part="withheld"] [data-mark="withheld"]',
      );
      if (mark === 'suppressed') {
        await expect(lock).toBeVisible();
        await expect(lock).toContainText(withheld[lang]);
      } else {
        await expect(lock).toHaveCount(0);
      }
    }
    for (const status of ['observed', 'inferred', 'still_to_test'] as const) {
      await page.goto(
        `/tests/visual/index.html?lang=${lang}&theme=dark&scene=open&status=${status}`,
      );
      await expect(page.getByRole('dialog')).toContainText(
        statuses[lang][status],
      );
    }
  }
});

/** The drawer slides in (drawer-in, --eii-dur-slow): measure its resting place, never a frame of the slide (OI-349). */
async function drawerAtRest(page: Page) {
  await page
    .locator('.drawer')
    .evaluate((node) =>
      Promise.all(node.getAnimations().map((a) => a.finished)),
    );
}

async function inside(page: Page, selector: string) {
  return page.locator(selector).evaluateAll((nodes) =>
    nodes.map((node) => {
      const box = node.getBoundingClientRect();
      return {
        shown: box.width > 0 && box.height > 0,
        within:
          box.left >= -0.5 &&
          box.right <= window.innerWidth + 0.5 &&
          box.top >= -0.5,
      };
    }),
  );
}

for (const size of NAMED_SIZES) {
  for (const lang of ['en', 'ar'] as const) {
    test(`S3-T18 controls hold at ${size.width}x${size.height} (${lang})`, async ({
      page,
    }) => {
      await page.setViewportSize(size);
      await page.goto(
        `/tests/visual/index.html?lang=${lang}&theme=dark&scene=open&mark=suppressed`,
      );
      const dialog = page.getByRole('dialog');
      await expect(dialog).toBeVisible();
      await drawerAtRest(page);
      // EII_SIZE_PLANT=overflow plants a drawer wider than every named size.
      if (process.env.EII_SIZE_PLANT === 'overflow')
        await page.addStyleTag({
          content: '.drawer { min-inline-size: 5000px !important; }',
        });
      for (const selector of [
        '.drawer-close',
        '.drawer [data-part="withheld"] [data-mark="withheld"]',
        '.drawer [data-part="status"] [data-mark="status"]',
        '.drawer [data-part="receipt"]',
      ]) {
        await page.locator(selector).first().scrollIntoViewIfNeeded();
        const boxes = await inside(page, selector);
        expect({ selector, boxes }).toEqual({
          selector,
          boxes: boxes.map(() => ({ shown: true, within: true })),
        });
        expect(boxes.length).toBeGreaterThan(0);
      }
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      expect(overflow).toBeLessThanOrEqual(0);
      await page.goto(
        `/tests/visual/index.html?lang=${lang}&theme=dark&scene=layers`,
      );
      const plate = '[data-layers-scene] [data-part="public-layers"]';
      await expect(page.locator(plate)).toBeVisible();
      await expect(page.locator(`${plate} [data-mark="class"]`)).toHaveCount(0);
      for (const selector of [
        `${plate} [data-part="line-samples"] [data-mark="withheld"]`,
        `${plate} [data-action="source-chain"]`,
        `${plate} [data-feature]`,
      ]) {
        const boxes = await inside(page, selector);
        expect(boxes.length).toBeGreaterThan(0);
        expect({ selector, boxes }).toEqual({
          selector,
          boxes: boxes.map(() => ({ shown: true, within: true })),
        });
      }
      await page.screenshot({
        path: `../.overnight/evidence/S3-T18/sizes/${size.width}x${size.height}-${lang}.png`,
      });
    });
  }
}

test('a carried percent is one platform percentage in both locales', async ({
  page,
}) => {
  await page.goto('/tests/visual/index.html?lang=en&theme=dark');
  const english = await page
    .locator('[data-case="percent-en"] .chip-num')
    .innerText();
  const arabic = await page
    .locator('[data-case="percent"] .chip-num')
    .innerText();
  console.log(`percent en ${JSON.stringify(english)}`);
  console.log(`percent ar ${JSON.stringify(arabic)}`);
  for (const printed of [english, arabic]) {
    expect(printed).not.toContain('1250');
    expect(printed).toContain('12.5');
    expect(printed).not.toMatch(/[٠-٩۰-۹]/);
    expect(printed).toMatch(/%|٪/);
  }
  await expect(page.locator('[data-case="percent-en"] .chip-unit')).toHaveCount(
    0,
  );
  await expect(page.locator('[data-case="percent"] .chip-unit')).toHaveCount(0);
});

test('an Arabic date is not forced left to right', async ({ page }) => {
  await page.goto('/tests/visual/index.html?lang=ar&theme=dark');
  await page.locator('.brief [data-fact-chip]').click();
  const date = page.locator('.drawer [data-kind="calendar_date"] bdi');
  await expect(date.first()).toHaveAttribute('lang', 'ar');
  await expect(date.first()).not.toHaveAttribute('dir', 'ltr');
});

for (const language of ['en', 'ar'] as const) {
  for (const theme of ['dark', 'light'] as const) {
    test(`operational meter placement, contrast and keyboard ${language} ${theme}`, async ({
      page,
    }) => {
      const { operationalMeter: meter } =
        await import('../fixtures/operational-meter');
      const external: string[] = [];
      await page.route('**/*', async (route) => {
        const url = new URL(route.request().url());
        if (url.hostname !== '127.0.0.1') {
          external.push(url.hostname);
          await route.abort();
        } else if (url.pathname === '/api/map-modes') {
          await route.fulfill({
            json: {
              open: { available: true, reason: null },
              satellite: { available: false, reason: 'no_key' },
              photoreal: { available: true, reason: null, meter },
            },
          });
        } else await route.continue();
      });
      for (const viewport of [
        { width: 1024, height: 768 },
        { width: 1440, height: 900 },
      ]) {
        await page.setViewportSize(viewport);
        await page.goto(
          `/tests/visual/index.html?lang=${language}&theme=${theme}`,
        );
        await page.waitForLoadState('networkidle');
        const chip = page.locator(
          '.map-controls [data-fact-chip="operational"]',
        );
        await expect(chip).toHaveAttribute(
          'dir',
          language === 'ar' ? 'rtl' : 'ltr',
        );
        await expect(
          chip.locator('[data-quantity="spend"] .chip-num'),
        ).toHaveText(meter.spend_usd);
        await expect(
          chip.locator('[data-quantity="spend"] .chip-num'),
        ).toHaveAttribute('dir', 'ltr');
        const button = chip.getByRole('button');
        await button.scrollIntoViewIfNeeded();
        const box = await button.boundingBox();
        expect(box?.height).toBeGreaterThanOrEqual(44);
        expect(box?.width).toBeGreaterThanOrEqual(44);
        await button.focus();
        await page.keyboard.press('Enter');
        await expect(chip.getByRole('region')).toBeVisible();
        const audit = await chip.evaluate((node) => {
          const faults: string[] = [];
          const luminance = (color: string) => {
            const rgb = color
              .match(/[\d.]+/g)!
              .slice(0, 3)
              .map(Number)
              .map((part) => {
                const channel = part / 255;
                return channel <= 0.04045
                  ? channel / 12.92
                  : ((channel + 0.055) / 1.055) ** 2.4;
              });
            return rgb[0]! * 0.2126 + rgb[1]! * 0.7152 + rgb[2]! * 0.0722;
          };
          for (const element of [
            node.querySelector('button')!,
            node.querySelector('section')!,
          ]) {
            const style = getComputedStyle(element);
            const a = luminance(style.color),
              b = luminance(style.backgroundColor);
            if ((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) < 4.5)
              faults.push('contrast');
            if (element.scrollWidth > element.clientWidth + 1)
              faults.push('overflow');
          }
          if (
            getComputedStyle(node.querySelector('button')!).outlineStyle ===
            'none'
          )
            faults.push('focus-ring');
          for (const element of node.querySelectorAll('.chip-num')) {
            if (element.closest('[data-fact-chip]') !== node)
              faults.push('numeral-outside-family');
          }
          return faults;
        });
        expect(audit).toEqual([]);
        const overlapsCredits = await chip.evaluate((node) => {
          const panel = node.querySelector('section')!.getBoundingClientRect();
          const credits = node
            .closest('.stage')!
            .querySelector('.stage-credits')!
            .getBoundingClientRect();
          return (
            panel.left < credits.right &&
            panel.right > credits.left &&
            panel.top < credits.bottom &&
            panel.bottom > credits.top
          );
        });
        expect(overlapsCredits).toBe(false);
        await page.screenshot({
          path: `../.overnight/OUT/fix6/design-${language}-${theme}-${viewport.width}.png`,
        });
        await page.keyboard.press('Escape');
        await expect(chip.getByRole('region')).toHaveCount(0);
        await expect(button).toBeFocused();
        await button.tap();
        await expect(chip.getByRole('region')).toBeVisible();
      }
      expect(external).toEqual([]);
    });
  }
}
