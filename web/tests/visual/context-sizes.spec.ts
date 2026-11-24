/**
 * S3-T14 box 8: the three Public context cards at decision 0049's named
 * sizes, in both languages and both themes. EII_CONTEXT_PLANT selects one
 * planted violation that must turn these specs red:
 *   withheld-zero      the withheld fixture shown as a Public zero;
 *   drag-only          level controls that answer only to a pointer drag;
 *   english-weekday    the venue weekday left in English;
 *   mixed-prose        an English word added to a caveat, or an Arabic
 *                      word in the English view;
 *   hidden-comparison  the open comparison body hidden by a stylesheet;
 *   hidden-evidence    the open evidence body hidden by a stylesheet.
 *   closed-shown       a closed level body shown by a stylesheet.
 */
import { expect, test, type Locator, type Page } from '@playwright/test';

import { fragmentField } from '../../src/brief/catalogue';
import {
  contextFamilies,
  type ContextFamily,
} from '../../src/cards/public-context-contract';
import { text, type StringKey } from '../../src/i18n';
import { NAMED_SIZES } from '../fixtures/viewports';

const PLANT = process.env.EII_CONTEXT_PLANT ?? '';
const LANGUAGES = ['en', 'ar'] as const;
const THEMES = ['dark', 'light'] as const;
const ARABIC = /\p{Script=Arabic}/u;
const LEVELS = ['answer', 'comparison', 'evidence'] as const;
const HIDDEN: Record<string, string> = {
  'hidden-comparison': 'comparison',
  'hidden-evidence': 'evidence',
};
const EVIDENCE = [
  'drawer.release',
  'drawer.method',
  'drawer.publisher',
  'drawer.dataset',
  'drawer.licence',
  'drawer.retrieved',
  'drawer.hash',
];
/** Catalogue keys of the fixture's answer words, after the level control. */
const ANSWER_WORDS: Record<ContextFamily, readonly string[]> = {
  night_lights: [],
  venue_busyness: [
    'context_monday',
    'context_retrieved',
    'context_update_not_stated',
  ],
  population_age_sex: ['context_age_band', 'context_female'],
};
const WITHHELD_WORDS = ['drawer.class.suppressed', 'context_withheld_reason'];

type Language = (typeof LANGUAGES)[number];
type Theme = (typeof THEMES)[number];

/** The localized catalogue text of a fragment key or an interface string. */
function say(lang: Language, key: string): string {
  return (
    fragmentField(key, lang === 'ar' ? 'template_ar' : 'template_en') ??
    text(lang, key as StringKey)
  );
}

/**
 * Expected application words of one card in reading order. Fact chips
 * (values and source attribution) are not application prose.
 */
function expectedWords(
  family: ContextFamily,
  lang: Language,
  withheld: boolean,
  open: boolean,
): string[] {
  const spec = contextFamilies[family];
  const keys = [
    family,
    'context_level_answer',
    ...(withheld ? WITHHELD_WORDS : ANSWER_WORDS[family]),
    'context_source',
    'context_level_comparison',
    ...(open ? [spec.comparison] : []),
    'context_level_evidence',
    ...(open && withheld ? ['context_withheld_reason'] : []),
    ...(open ? EVIDENCE : []),
    spec.caveat,
  ];
  return keys.map((key) => say(lang, key));
}

/** The words a level's open region must show. */
function regionWords(family: ContextFamily, lang: Language, level: string) {
  if (level === 'answer') return say(lang, 'context_source');
  if (level === 'comparison')
    return say(lang, contextFamilies[family].comparison);
  return say(lang, 'drawer.release');
}

async function openScene(
  page: Page,
  lang: Language,
  theme: Theme,
  withheld: boolean,
) {
  const mark = withheld ? '&mark=suppressed' : '';
  const plant = PLANT === 'withheld-zero' ? '&plant=withheld-zero' : '';
  await page.goto(
    `/tests/visual/index.html?scene=context&lang=${lang}&theme=${theme}${mark}${plant}`,
  );
  await page.evaluate(() => document.fonts.ready);
  const cards = page.locator('[data-context-scene]');
  await expect(cards.locator('article')).toHaveCount(3);
  if (PLANT === 'drag-only') await plantDragOnly(cards);
  if (PLANT in HIDDEN)
    await page.addStyleTag({
      content: `[data-context-level="${HIDDEN[PLANT]}"] > [role="region"] { display: none !important; }`,
    });
  if (PLANT === 'closed-shown')
    await page.addStyleTag({
      content:
        '[data-context-level] > [role="region"][hidden] { display: block !important; min-block-size: 1px; }',
    });
  return cards;
}

/** A control that toggles only after a pointer moves while pressed. */
async function plantDragOnly(cards: Locator) {
  await cards.evaluate((scene) => {
    for (const control of scene.querySelectorAll(
      '[data-context-level] > button',
    )) {
      let start: number | null = null;
      let dragged = false;
      control.addEventListener('pointerdown', (event) => {
        start = (event as PointerEvent).clientX;
        dragged = false;
      });
      control.addEventListener('pointermove', (event) => {
        if (start !== null)
          dragged ||= Math.abs((event as PointerEvent).clientX - start) > 12;
      });
      control.addEventListener(
        'click',
        (event) => {
          if (!dragged) event.stopImmediatePropagation();
          start = null;
        },
        true,
      );
    }
  });
}

/** Text of a node with every Fact chip removed: the application's words. */
function prose(node: Locator) {
  return node.evaluate((element) => {
    if (element.closest('[data-fact-chip]')) return '';
    const clone = element.cloneNode(true) as HTMLElement;
    clone.querySelectorAll('[data-fact-chip]').forEach((chip) => chip.remove());
    return clone.textContent ?? '';
  });
}

/** The region a level control names in aria-controls. */
async function regionOf(card: Locator, control: Locator) {
  const id = await control.getAttribute('aria-controls');
  expect(id, 'aria-controls').toBeTruthy();
  return card.locator(`[id="${id}"]`);
}

/** The region shows its words when open and is hidden when closed. */
async function regionFollows(
  control: Locator,
  region: Locator,
  words: string,
  label: string,
) {
  if ((await control.getAttribute('aria-expanded')) === 'true') {
    await expect(region, `${label} region shown`).toBeVisible();
    await expect(
      region.getByText(words, { exact: true }),
      `${label} words shown`,
    ).toBeVisible();
  } else {
    await expect(region, `${label} region hidden`).toBeHidden();
  }
}

/** Every control is a single tap and a key press, and opens its level. */
async function levelsBySingleTap(page: Page, card: Locator, lang: Language) {
  const family = (await card.getAttribute(
    'data-context-family',
  )) as ContextFamily;
  for (const level of LEVELS) {
    const label = say(lang, `context_level_${level}`);
    const words = regionWords(family, lang, level);
    const control = card.getByRole('button', { name: label, exact: true });
    const region = await regionOf(card, control);
    const initial = await control.getAttribute('aria-expanded');
    const toggled = initial === 'true' ? 'false' : 'true';
    await regionFollows(control, region, words, label);
    await control.tap();
    await expect(control, `${label} tap`).toHaveAttribute(
      'aria-expanded',
      toggled,
    );
    await regionFollows(control, region, words, label);
    await control.focus();
    await page.keyboard.press('Enter');
    await expect(control, `${label} Enter`).toHaveAttribute(
      'aria-expanded',
      initial!,
    );
    await regionFollows(control, region, words, label);
    if (initial === 'false') await control.tap();
    await expect(control).toHaveAttribute('aria-expanded', 'true');
    await regionFollows(control, region, words, label);
  }
}

async function fitsInside(page: Page, cards: Locator) {
  const boxes = await cards.locator('article').evaluateAll((nodes) =>
    nodes.map((node) => {
      const box = node.getBoundingClientRect();
      return {
        noScroll: node.scrollWidth <= node.clientWidth,
        within: box.left >= -0.5 && box.right <= window.innerWidth + 0.5,
      };
    }),
  );
  expect(boxes).toEqual(boxes.map(() => ({ noScroll: true, within: true })));
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow, 'page overflow').toBeLessThanOrEqual(0);
}

async function targetsReadable(cards: Locator) {
  const small = await cards.locator('button').evaluateAll((nodes) =>
    nodes
      .map((node) => node.getBoundingClientRect())
      .filter((box) => box.height < 44 || box.width < 44)
      .map((box) => `${box.width}x${box.height}`),
  );
  expect(small, 'targets under 44 px').toEqual([]);
}

/** The planted wrong-language words, set after the levels are open. */
async function plantWords(cards: Locator, lang: Language) {
  if (PLANT === 'english-weekday')
    await cards
      .locator('.context-meta > bdi')
      .evaluate((node) => (node.textContent = 'Monday'));
  if (PLANT === 'mixed-prose')
    await cards
      .locator('[data-caveat] > bdi')
      .first()
      .evaluate(
        (node, word) => (node.textContent += word),
        lang === 'ar' ? ' activity' : ' نشاط',
      );
}

/** Application text nodes of a card in reading order, Fact chips excluded. */
function applicationWords(card: Locator) {
  return card.evaluate((article) => {
    const walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT);
    const found: string[] = [];
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (node.parentElement?.closest('[data-fact-chip]')) continue;
      const words = (node.textContent ?? '').trim();
      if (words !== '') found.push(words);
    }
    return found;
  });
}

/**
 * Every application text node is the expected catalogue text of the chosen
 * language, in order; numerals only in chips; direction follows the language.
 */
async function wordsInLanguage(
  cards: Locator,
  lang: Language,
  withheld: boolean,
  open: boolean,
) {
  await plantWords(cards, lang);
  for (const card of await cards.locator('article').all()) {
    const family = (await card.getAttribute(
      'data-context-family',
    )) as ContextFamily;
    expect(await prose(card)).not.toMatch(/\p{N}/u);
    expect(await applicationWords(card), `${family} ${lang} words`).toEqual(
      expectedWords(family, lang, withheld && family === 'night_lights', open),
    );
    expect(
      await card.evaluate((node) => getComputedStyle(node).direction),
    ).toBe(lang === 'ar' ? 'rtl' : 'ltr');
  }
}

for (const size of NAMED_SIZES) {
  for (const lang of LANGUAGES) {
    const name = `${size.width}x${size.height} ${lang}`;

    test(`S3-T14 context cards hold at ${name}, light and dark`, async ({
      page,
    }) => {
      await page.setViewportSize(size);
      const surfaces: string[] = [];
      for (const theme of THEMES) {
        const cards = await openScene(page, lang, theme, false);
        await expect(cards).toHaveAttribute('data-theme', theme);
        await expect(cards.locator('[data-fact-chip="value"]')).toHaveCount(3);
        for (const card of await cards.locator('article').all()) {
          await levelsBySingleTap(page, card, lang);
          const source = card.getByRole('button', {
            name: say(lang, 'context_source'),
            exact: true,
          });
          await source.tap();
          await expect(page.locator('body')).toHaveAttribute(
            'data-context-opened',
            (await card
              .locator('[data-context-level="answer"] > [data-fact-id]')
              .getAttribute('data-fact-id'))!,
          );
        }
        await fitsInside(page, cards);
        await targetsReadable(cards);
        await wordsInLanguage(cards, lang, false, true);
        surfaces.push(
          await cards
            .locator('article')
            .first()
            .evaluate((node) => getComputedStyle(node).backgroundColor),
        );
        await cards.screenshot({
          path: `../.overnight/evidence/S3-T14/sizes/${size.width}x${size.height}-${lang}-${theme}.png`,
        });
      }
      expect(new Set(surfaces).size, 'light and dark surfaces').toBe(2);
    });

    test(`S3-T14 withheld card keeps its reason at ${name}, light and dark`, async ({
      page,
    }) => {
      await page.setViewportSize(size);
      for (const theme of THEMES) {
        const cards = await openScene(page, lang, theme, true);
        const card = cards.locator('[data-context-family="night_lights"]');
        await expect(card.locator('[data-mark="withheld"]')).toBeVisible();
        await expect(
          card.locator('[data-fact-chip="value"] .chip-num'),
        ).toHaveCount(0);
        const reason = card.locator('.context-withheld p');
        await expect(reason).toBeVisible();
        const words = (await reason.innerText()).trim();
        if (lang === 'ar') expect(words).toMatch(ARABIC);
        else expect(words).not.toMatch(ARABIC);
        expect(await card.innerText()).not.toMatch(/987|(?<![0-9])0(?![0-9])/);
        await expect(cards.locator('[data-fact-chip="value"]')).toHaveCount(2);
        await fitsInside(page, cards);
        await wordsInLanguage(cards, lang, true, false);
      }
    });
  }
}
