import { expect, test, type Page } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import {
  DISTANCE_PRESETS,
  DRIVE_PRESETS,
  WALK_PRESETS,
  type AreaPreset,
} from '../../src/controls/presets';
import { formatFactValue } from '../../src/facts/formatters';
import { text, unitWord } from '../../src/i18n';
import type { AuditOrder } from './opening-audit';
import { auditReport } from './opening-audit';
import {
  answerReadoutProblems,
  circleExtentProblem,
  drawProblems,
  drawReport,
  drawSpec,
  type AnswerReadout,
} from './draw-audit';

/**
 * S3-T13 box 5: the area-drawing flow measured in both languages, both
 * themes, on a phone and a desktop size. Contrast, clipping, overlap,
 * direction, DOM reading order and visible focus are measured on each
 * screen; no pixel baseline is used.
 */

const SIZES = [
  { width: 390, height: 844 },
  { width: 1280, height: 800 },
] as const;
const EVIDENCE = path.resolve('../.overnight/tmp/S3-T13-captures');

const TOOLS = ['polygon', 'radius', 'travel'] as const;
const DISTANCE = ['distance-a', 'distance-b', 'distance-c'] as const;
const TRAVEL = [
  'walk-a',
  'walk-b',
  'walk-c',
  'drive-a',
  'drive-b',
  'drive-c',
] as const;

function order(...keys: readonly string[]): readonly AuditOrder[] {
  return [{ scope: '.draw-tools button', expected: keys }];
}

const POLYGON_EDITING: readonly AuditOrder[] = [
  {
    scope: '.draw-tools button',
    expected: [...TOOLS, 'use-area', 'cancel-area'],
  },
  {
    scope: '.area-overlay [data-part="knob"]',
    attribute: 'data-index',
    expected: ['0', '1', '2'],
  },
];
const POLYGON_ANSWER = order(...TOOLS, 'use-area');
const RADIUS_DRAWING = order(...TOOLS, ...DISTANCE, 'use-area', 'cancel-area');
const RADIUS_ANSWER = order(...TOOLS, ...DISTANCE, 'use-area');
const TRAVEL_DRAWING = order(...TOOLS, ...TRAVEL, 'use-area', 'cancel-area');
const TRAVEL_ANSWER = order(...TOOLS, ...TRAVEL, 'use-area');

const MODE_KEY = {
  distance: 'draw.mode.distance',
  walk: 'draw.mode.walk',
  drive: 'draw.mode.drive',
} as const;

interface PresetReading {
  id: string;
  mode: AreaPreset['mode'];
  value: number;
  unit: string;
  recordId: string;
}

function presetById(id: string): AreaPreset {
  const found = [...DISTANCE_PRESETS, ...WALK_PRESETS, ...DRIVE_PRESETS].find(
    (item) => item.id === id,
  );
  if (!found) throw new Error(`missing preset ${id}`);
  return found;
}

function readoutOf(lang: 'en' | 'ar', preset: PresetReading): AnswerReadout {
  const formatted = formatFactValue(preset.value, preset.unit, lang);
  if (!formatted.ok) throw new Error(`preset ${preset.id} did not format`);
  const unit = unitWord(lang, preset.unit);
  if (!unit) throw new Error(`preset ${preset.id} has no unit word`);
  return {
    modeText: text(lang, MODE_KEY[preset.mode]),
    valueText: formatted.text,
    unitText: unit,
    recordId: preset.recordId,
  };
}

function readoutFor(lang: 'en' | 'ar', id: string): AnswerReadout {
  return readoutOf(lang, presetById(id));
}

/** The tool panel sits at the inline start, so taps aim at the other side. */
function freeSide(lang: 'en' | 'ar') {
  return lang === 'ar' ? { low: 0.12, high: 0.3 } : { low: 0.7, high: 0.88 };
}

async function openDraw(page: Page, lang: 'en' | 'ar', theme: string) {
  await page.goto(`/tests/visual/draw.html?lang=${lang}&theme=${theme}`);
  await expect(page.locator('.draw-tools')).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
}

async function tapOverlay(page: Page, fx: number, fy: number) {
  const box = await page.locator('.area-overlay').boundingBox();
  expect(box).not.toBeNull();
  if (!box) return;
  await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy);
}

async function openRadiusDrawing(page: Page) {
  await page.setViewportSize({ width: 1280, height: 800 });
  await openDraw(page, 'ar', 'dark');
  await page.locator('[data-tool="radius"]').click();
  await tapOverlay(page, 0.2, 0.3);
  await page.locator('[data-preset="distance-b"]').click();
}

async function openRadiusAnswer(page: Page) {
  await openRadiusDrawing(page);
  const summary = page.locator('[data-part="area-summary"]');
  await page.locator('[data-part="use-area"]').click();
  await expect(summary).toHaveAttribute('data-shape', 'radius');
  await summary.scrollIntoViewIfNeeded();
  return summary;
}

async function audit(
  page: Page,
  order: readonly AuditOrder[],
  tag: string,
  screen: string,
) {
  const report = await drawReport(page, order);
  mkdirSync(EVIDENCE, { recursive: true });
  writeFileSync(
    path.join(EVIDENCE, `draw-contrast-${screen}-${tag}.json`),
    JSON.stringify(report.contrast, null, 2) + '\n',
  );
  await page.screenshot({
    path: path.join(EVIDENCE, `draw-${screen}-${tag}.png`),
  });
  expect(report.problems).toEqual([]);
}

for (const size of SIZES)
  for (const lang of ['en', 'ar'] as const)
    for (const theme of ['dark', 'light'] as const) {
      const tag = `${size.width}x${size.height}-${lang}-${theme}`;
      test(`draw audit ${tag}`, async ({ page }) => {
        await page.setViewportSize(size);
        const side = freeSide(lang);
        const mid = (side.low + side.high) / 2;
        const summary = page.locator('[data-part="area-summary"]');

        await openDraw(page, lang, theme);
        await page.locator('[data-tool="polygon"]').click();
        await tapOverlay(page, side.high, 0.22);
        await tapOverlay(page, side.low, 0.22);
        await tapOverlay(page, side.low, 0.42);
        await page.locator('[data-part="knob"][data-index="0"]').click();
        await expect(page.locator('[data-closed="yes"]')).toHaveCount(1);
        expect(await drawProblems(page, POLYGON_EDITING)).toEqual([]);
        await page.locator('[data-part="use-area"]').click();
        await expect(summary).toBeVisible();
        await expect(summary).toHaveAttribute('data-shape', 'polygon');
        await expect(page.locator('[data-line="accent"]')).toBeVisible();
        await summary.scrollIntoViewIfNeeded();
        await expect(page.locator('[data-part="no-mode"]')).toHaveText(
          text(lang, 'draw.summary.noMode'),
        );
        await expect(page.locator('[data-part="no-mode"]')).toBeInViewport();
        await audit(page, POLYGON_ANSWER, tag, 'polygon');

        await openDraw(page, lang, theme);
        await page.locator('[data-tool="radius"]').click();
        await tapOverlay(page, mid, 0.3);
        await page.locator('[data-preset="distance-b"]').click();
        expect(await drawProblems(page, RADIUS_DRAWING)).toEqual([]);
        await page.locator('[data-part="use-area"]').click();
        await expect(summary).toHaveAttribute('data-shape', 'radius');
        expect(await circleExtentProblem(page)).toEqual([]);
        await summary.scrollIntoViewIfNeeded();
        expect(
          await answerReadoutProblems(page, readoutFor(lang, 'distance-b')),
        ).toEqual([]);
        await audit(page, RADIUS_ANSWER, tag, 'radius');

        await openDraw(page, lang, theme);
        await page.locator('[data-tool="travel"]').click();
        await tapOverlay(page, mid, 0.3);
        await page.locator('[data-preset="walk-a"]').click();
        expect(await drawProblems(page, TRAVEL_DRAWING)).toEqual([]);
        await page.locator('[data-part="use-area"]').click();
        await expect(summary).toHaveAttribute('data-shape', 'walk');
        expect(await circleExtentProblem(page)).toEqual([]);
        await summary.scrollIntoViewIfNeeded();
        expect(
          await answerReadoutProblems(page, readoutFor(lang, 'walk-a')),
        ).toEqual([]);
        await audit(page, TRAVEL_ANSWER, tag, 'walk');

        await openDraw(page, lang, theme);
        await page.locator('[data-tool="travel"]').click();
        await tapOverlay(page, mid, 0.3);
        await page.locator('[data-preset="drive-b"]').click();
        expect(await drawProblems(page, TRAVEL_DRAWING)).toEqual([]);
        await page.locator('[data-part="use-area"]').click();
        await expect(summary).toHaveAttribute('data-shape', 'drive');
        expect(await circleExtentProblem(page)).toEqual([]);
        await expect(page.locator('[data-part="free-flow"]')).toBeVisible();
        await summary.scrollIntoViewIfNeeded();
        expect(
          await answerReadoutProblems(page, readoutFor(lang, 'drive-b')),
        ).toEqual([]);
        await audit(page, TRAVEL_ANSWER, tag, 'drive');
      });
    }

test('planted draw violations fail their own guards, then restore green', async ({
  page,
}) => {
  await openRadiusDrawing(page);
  const summary = page.locator('[data-part="area-summary"]');
  expect(await drawProblems(page, RADIUS_DRAWING)).toEqual([]);

  const tool = page.locator('[data-tool="polygon"]');
  await tool.evaluate((node) => {
    node.style.color = 'rgb(24,32,43)';
    node.style.backgroundColor = 'rgb(24,32,43)';
  });
  expect(await drawProblems(page, RADIUS_DRAWING)).toContain('contrast');
  await tool.evaluate((node) => {
    node.style.color = '';
    node.style.backgroundColor = '';
  });
  expect(await drawProblems(page, RADIUS_DRAWING)).toEqual([]);

  const tools = page.locator('.draw-tools');
  await tools.evaluate((node) => node.setAttribute('dir', 'ltr'));
  expect(await drawProblems(page, RADIUS_DRAWING)).toContain(
    'wrong-group-direction',
  );
  await tools.evaluate((node) => node.setAttribute('dir', 'rtl'));
  expect(await drawProblems(page, RADIUS_DRAWING)).toEqual([]);

  await tools.evaluate((node) => (node.style.insetInlineStart = '-240px'));
  let found = await drawProblems(page, RADIUS_DRAWING);
  expect(found).toContain('draw-outside-container');
  expect(found).toContain('draw-outside-viewport');
  // Arabic lays the brief column on the left; a panel pinned to the left
  // viewport edge sits on top of it.
  await tools.evaluate((node) => {
    node.style.insetInlineStart = 'auto';
    node.style.position = 'fixed';
    node.style.left = '0';
    node.style.right = 'auto';
    node.style.top = '0';
    node.style.zIndex = '99';
  });
  expect(await drawProblems(page, RADIUS_DRAWING)).toContain('draw-overlap');
  await tools.evaluate((node) => node.removeAttribute('style'));
  expect(await drawProblems(page, RADIUS_DRAWING)).toEqual([]);

  const useArea = page.locator('[data-part="use-area"]');
  await useArea.evaluate((node) => {
    const parent = node.parentElement!;
    parent.insertBefore(node, parent.querySelector('[data-part="presets"]'));
  });
  expect(await drawProblems(page, RADIUS_DRAWING)).toContain(
    'draw-reading-order',
  );
  await useArea.evaluate((node) => {
    const parent = node.parentElement!;
    parent.insertBefore(
      node,
      parent.querySelector('[data-part="cancel-area"]'),
    );
  });
  expect(await drawProblems(page, RADIUS_DRAWING)).toEqual([]);

  await useArea.evaluate((node) => {
    node.style.cssText =
      `position:fixed;left:${innerWidth + 20}px;top:0;` +
      'min-width:0;min-height:0;width:4px;height:4px;padding:0;border:0';
  });
  found = await drawProblems(page, RADIUS_DRAWING);
  expect(found).toContain('control-overflow');
  expect(found).toContain('small-target');
  await useArea.evaluate((node) => node.removeAttribute('style'));
  expect(await drawProblems(page, RADIUS_DRAWING)).toEqual([]);

  await page.evaluate(() => {
    const overflow = document.createElement('div');
    overflow.style.width = '5000px';
    overflow.style.height = '1px';
    document.body.append(overflow);
  });
  expect(await drawProblems(page, RADIUS_DRAWING)).toContain('page-overflow');
  await page.evaluate(() => document.body.lastElementChild?.remove());
  expect(await drawProblems(page, RADIUS_DRAWING)).toEqual([]);

  await page.locator('[data-part="use-area"]').click();
  await expect(summary).toHaveAttribute('data-shape', 'radius');
  const line = summary.locator('p').first();
  const words = await line.innerText();
  await line.evaluate((node) => {
    node.style.height = '4px';
    node.style.overflow = 'hidden';
  });
  expect(await drawProblems(page, RADIUS_ANSWER)).toContain('clipped-copy');
  await line.evaluate((node) => {
    node.style.height = '';
    node.style.overflow = '';
  });
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);

  await line.evaluate((node) => (node.style.letterSpacing = '2px'));
  expect(await drawProblems(page, RADIUS_ANSWER)).toContain('arabic-type');
  await line.evaluate((node) => (node.style.letterSpacing = ''));
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);

  await line.evaluate((node) => {
    node.textContent += ' 123 Synthetic';
    node.setAttribute('aria-label', 'INVENTED 9');
  });
  found = await drawProblems(page, RADIUS_ANSWER);
  expect(found).toContain('loose-numeral');
  expect(found).toContain('origin-word');
  expect(found).toContain('accessible-numeral');
  await line.evaluate((node, words) => {
    node.textContent = words;
    node.removeAttribute('aria-label');
  }, words);
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);

  await page.evaluate(() => {
    const style = document.createElement('style');
    style.dataset.plant = 'focus';
    style.textContent =
      '.draw-tools button:focus-visible,.sheet-toggle:focus-visible{outline:none!important}';
    document.head.append(style);
  });
  found = await drawProblems(page, RADIUS_ANSWER);
  expect(found.some((name) => name === 'focus-hidden')).toBe(true);
  await page.evaluate(() =>
    document.querySelector('style[data-plant="focus"]')?.remove(),
  );
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
});

test('an unknown preset id is refused', () => {
  expect(() => presetById('not-a-preset')).toThrow(
    /^missing preset not-a-preset$/,
  );
});

test('a preset value that does not format is refused', () => {
  const preset = { ...presetById('distance-b'), value: Number.NaN };
  expect(() => readoutOf('en', preset)).toThrow(
    /^preset distance-b did not format$/,
  );
});

test('a preset unit with no word is refused', () => {
  const preset = { ...presetById('distance-b'), unit: 'years' };
  expect(() => readoutOf('en', preset)).toThrow(
    /^preset distance-b has no unit word$/,
  );
});

test('answer headline contrast is its own plant', async ({ page }) => {
  await openRadiusAnswer(page);
  const headline = page.locator('.brief h1');
  await headline.evaluate((node) => {
    node.style.color = 'rgb(24,32,43)';
    node.style.backgroundColor = 'rgb(24,32,43)';
  });
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual(['contrast']);
  await headline.evaluate((node) => {
    node.style.color = '';
    node.style.backgroundColor = '';
  });
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
});

test('arabic chip letter-spacing is its own plant', async ({ page }) => {
  await openRadiusAnswer(page);
  const chipText = page.locator(
    '[data-part="area-summary"] [data-fact-chip] .chip-num',
  );
  await chipText.evaluate((node) => {
    node.style.letterSpacing = '2px';
  });
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual(['arabic-type']);
  await chipText.evaluate((node) => {
    node.style.letterSpacing = '';
  });
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
});

test('a removed mode word is mode-missing', async ({ page }) => {
  const summary = await openRadiusAnswer(page);
  const radiusReadout = readoutFor('ar', 'distance-b');
  const modeWord = page.locator('[data-part="mode-word"]');
  const modeHtml = await modeWord.evaluate((node) => node.outerHTML);
  await modeWord.evaluate((node) => node.remove());
  expect(await answerReadoutProblems(page, radiusReadout)).toEqual([
    'mode-missing',
  ]);
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
  await summary.evaluate((node, html) => {
    node.insertAdjacentHTML('afterbegin', html);
  }, modeHtml);
  expect(await answerReadoutProblems(page, radiusReadout)).toEqual([]);
});

test('a removed cutoff chip is cutoff-missing', async ({ page }) => {
  const summary = await openRadiusAnswer(page);
  const radiusReadout = readoutFor('ar', 'distance-b');
  const chip = page.locator(
    `[data-part="area-summary"] [data-fact-chip="input"][data-record="${radiusReadout.recordId}"]`,
  );
  const chipHtml = await chip.evaluate((node) => node.outerHTML);
  await chip.evaluate((node) => node.remove());
  expect(await answerReadoutProblems(page, radiusReadout)).toEqual([
    'cutoff-missing',
  ]);
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
  await summary.evaluate((node, html) => {
    node.insertAdjacentHTML('beforeend', html);
  }, chipHtml);
  expect(await answerReadoutProblems(page, radiusReadout)).toEqual([]);
});

test('a 500 cut-off shown as 1500 is cutoff-missing', async ({ page }) => {
  await openRadiusAnswer(page);
  const radiusReadout = readoutFor('ar', 'distance-b');
  const numeral = page.locator(
    `[data-part="area-summary"] [data-fact-chip="input"][data-record="${radiusReadout.recordId}"] .chip-num`,
  );
  await expect(numeral).toHaveText(radiusReadout.valueText);
  expect(radiusReadout.valueText).toBe('500');
  await numeral.evaluate((node) => {
    node.textContent = '1500';
  });
  expect(await answerReadoutProblems(page, radiusReadout)).toEqual([
    'cutoff-missing',
  ]);
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
  await numeral.evaluate((node, value) => {
    node.textContent = value;
  }, radiusReadout.valueText);
  expect(await answerReadoutProblems(page, radiusReadout)).toEqual([]);
});

test('a changed cutoff unit is cutoff-missing', async ({ page }) => {
  await openRadiusAnswer(page);
  const radiusReadout = readoutFor('ar', 'distance-b');
  const unit = page.locator(
    `[data-part="area-summary"] [data-fact-chip="input"][data-record="${radiusReadout.recordId}"] .chip-unit`,
  );
  const unitText = await unit.innerText();
  await unit.evaluate((node) => {
    node.textContent = 'km';
  });
  expect(await answerReadoutProblems(page, radiusReadout)).toEqual([
    'cutoff-missing',
  ]);
  await unit.evaluate((node, value) => {
    node.textContent = value;
  }, unitText);
  expect(await answerReadoutProblems(page, radiusReadout)).toEqual([]);
});

const HIDDEN_READOUT_PLANTS = [
  {
    part: '[data-part="mode-word"]',
    style: 'visibility',
    problem: 'mode-missing',
  },
  {
    part: '[data-part="mode-word"]',
    style: 'opacity',
    problem: 'mode-missing',
  },
  { part: '.chip-num', style: 'visibility', problem: 'cutoff-missing' },
  { part: '.chip-unit', style: 'opacity', problem: 'cutoff-missing' },
] as const;

for (const plant of HIDDEN_READOUT_PLANTS) {
  test(`a readout part ${plant.part} hidden by ${plant.style} is ${plant.problem}`, async ({
    page,
  }) => {
    await openRadiusAnswer(page);
    const radiusReadout = readoutFor('ar', 'distance-b');
    const scope =
      plant.part === '[data-part="mode-word"]'
        ? '[data-part="area-summary"]'
        : `[data-part="area-summary"] [data-fact-chip="input"][data-record="${radiusReadout.recordId}"]`;
    const node = page.locator(`${scope} ${plant.part}`);
    await node.evaluate((element, style) => {
      if (style === 'visibility') element.style.visibility = 'hidden';
      else element.style.opacity = '0';
    }, plant.style);
    expect(await answerReadoutProblems(page, radiusReadout)).toEqual([
      plant.problem,
    ]);
    await node.evaluate((element) => {
      element.style.visibility = '';
      element.style.opacity = '';
    });
    expect(await answerReadoutProblems(page, radiusReadout)).toEqual([]);
  });
}

async function expectOutlinePlant(
  page: Page,
  plant: (node: Element) => void,
  restore: (node: Element) => void,
) {
  const outline = page.locator('[data-outline="circle"]');
  await outline.evaluate(plant);
  expect(await circleExtentProblem(page)).toEqual(['outline-extent']);
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
  await outline.evaluate(restore);
  expect(await circleExtentProblem(page)).toEqual([]);
}

test('a dot-sized circle outline is outline-extent', async ({ page }) => {
  await openRadiusAnswer(page);
  await expectOutlinePlant(
    page,
    (node) => {
      if (!(node instanceof SVGElement)) return;
      node.style.transform = 'scale(0.02)';
      node.style.transformOrigin = 'center';
    },
    (node) => {
      if (!(node instanceof SVGElement)) return;
      node.style.transform = '';
      node.style.transformOrigin = '';
    },
  );
});

test('an off-viewport circle outline is outline-extent', async ({ page }) => {
  await openRadiusAnswer(page);
  await expectOutlinePlant(
    page,
    (node) => {
      if (!(node instanceof SVGElement)) return;
      node.style.transform = 'translate(-4000px, -4000px)';
    },
    (node) => {
      if (!(node instanceof SVGElement)) return;
      node.style.transform = '';
    },
  );
});

const HIDDEN_STROKE_PLANTS = [
  ['visibility', 'hidden'],
  ['opacity', '0'],
  ['stroke-opacity', '0'],
  ['stroke-width', '0'],
  ['stroke', 'transparent'],
  ['display', 'none'],
] as const;

for (const [property, value] of HIDDEN_STROKE_PLANTS) {
  test(`circle outline strokes with ${property} ${value} are outline-extent`, async ({
    page,
  }) => {
    await openRadiusAnswer(page);
    const outline = page.locator('[data-outline="circle"]');
    await outline.evaluate(
      (node, [name, setting]) => {
        for (const shape of node.querySelectorAll<SVGElement>(
          'circle, path, polyline, polygon, line',
        ))
          shape.style.setProperty(name, setting);
      },
      [property, value] as const,
    );
    expect(await circleExtentProblem(page)).toEqual(['outline-extent']);
    expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
    await outline.evaluate((node, name) => {
      for (const shape of node.querySelectorAll<SVGElement>(
        'circle, path, polyline, polygon, line',
      ))
        shape.style.removeProperty(name);
    }, property);
    expect(await circleExtentProblem(page)).toEqual([]);
  });
}

test('a hidden circle outline is outline-extent', async ({ page }) => {
  await openRadiusAnswer(page);
  await expectOutlinePlant(
    page,
    (node) => {
      if (!(node instanceof SVGElement)) return;
      node.style.visibility = 'hidden';
    },
    (node) => {
      if (!(node instanceof SVGElement)) return;
      node.style.visibility = '';
    },
  );
});

test('a transparent circle outline is outline-extent', async ({ page }) => {
  await openRadiusAnswer(page);
  await expectOutlinePlant(
    page,
    (node) => {
      if (!(node instanceof SVGElement)) return;
      node.style.opacity = '0';
    },
    (node) => {
      if (!(node instanceof SVGElement)) return;
      node.style.opacity = '';
    },
  );
});

test('an unstroked circle outline is outline-extent', async ({ page }) => {
  await openRadiusAnswer(page);
  await expectOutlinePlant(
    page,
    (node) => {
      for (const shape of node.querySelectorAll('polyline, path, line')) {
        if (shape instanceof SVGElement) shape.style.stroke = 'none';
      }
    },
    (node) => {
      for (const shape of node.querySelectorAll('polyline, path, line')) {
        if (shape instanceof SVGElement) shape.style.stroke = '';
      }
    },
  );
});

test('a missing circle outline is outline-extent', async ({ page }) => {
  await openRadiusAnswer(page);
  const outline = page.locator('[data-outline="circle"]');
  const html = await outline.evaluate((node) => node.outerHTML);
  await outline.evaluate((node) => node.remove());
  expect(await circleExtentProblem(page)).toEqual(['outline-extent']);
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
  await page.locator('.area-lines').evaluate((node, markup) => {
    node.insertAdjacentHTML('beforeend', markup);
  }, html);
  expect(await circleExtentProblem(page)).toEqual([]);
});

test('accessible class words are their own plant', async ({ page }) => {
  await openRadiusAnswer(page);
  const radiusReadout = readoutFor('ar', 'distance-b');
  const headline = page.locator('.brief h1');
  const chip = page.locator(
    `[data-part="area-summary"] [data-fact-chip="input"][data-record="${radiusReadout.recordId}"]`,
  );
  const classWords = [
    ['aria-label', 'Synthetic'],
    ['aria-description', 'علني'],
    ['title', 'Simulated'],
    ['alt', 'اصطناعي'],
  ] as const;
  for (const [name, value] of classWords) {
    await headline.evaluate(
      (node, planted) => node.setAttribute(planted.name, planted.value),
      { name, value },
    );
    expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([
      'accessible-origin',
    ]);
    await headline.evaluate(
      (node, attribute) => node.removeAttribute(attribute),
      name,
    );
    expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
  }
  await chip.evaluate((node) => node.setAttribute('aria-label', 'Synthetic'));
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([
    'accessible-origin',
  ]);
  await chip.evaluate((node) => node.setAttribute('aria-label', '500'));
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
  await chip.evaluate((node) => node.removeAttribute('aria-label'));
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
  await headline.evaluate((node) =>
    node.setAttribute('aria-label', 'SyntheticX'),
  );
  expect(await drawProblems(page, RADIUS_ANSWER)).toEqual([]);
  await headline.evaluate((node) => node.removeAttribute('aria-label'));
});

test('a focus spec restores the control that was active', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/tests/visual/draw.html?lang=en&theme=dark');
  const tool = page.locator('[data-tool="polygon"]');
  await expect(tool).toBeVisible();
  await tool.focus();
  await auditReport(page, drawSpec(order(...TOOLS)));
  await expect(tool).toBeFocused();
});
