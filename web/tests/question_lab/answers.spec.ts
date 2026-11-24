/** Full per-answer matrix; actual S3 opening fixture, with no API interception.
 * Capture execution waits for local browser assets and approved CI baselines.
 * Software rendering establishes no native stage/phone performance result.
 */
import { test, expect } from '../e2e/opening-fixture';
import { openingReport } from '../audit/opening-audit';
import { QUESTION_LAB_SIZES } from './matrix';
import { installLabClock } from './clock';
import { baselineProblems } from './baselines.mjs';
import {
  registerLabCaptures,
  type LabRun,
  type LabShot,
  type ReferenceRecord,
} from './contract';
import {
  answerArea,
  answerFactId,
  nightLightsReferences,
  readReleaseDump,
  releaseReferences,
  type ReleaseReferences,
} from './references';
import { CARD_STYLES } from './styles';
import { MAKE_AREA_PATH } from '../../src/api/areas';
import { contextFamilies } from '../../src/cards/public-context-contract';
import type { Locator, Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';

interface LabCase {
  identity: string;
  mode: 'polygon' | 'distance' | 'walk' | 'drive';
  pin: number;
  expected_value: number | null;
  refusal: string | null;
}

// Tooling reads the shared input; no web import crosses the serving boundary.
const cases = JSON.parse(
  readFileSync(path.resolve('../evals/question_lab/cases.v1.json'), 'utf8'),
) as { cases: LabCase[] };

const BASELINES = path.resolve('tests/question_lab/baselines');
const packet = process.env.EII_QUESTION_LAB_PACKET;
if (packet && !/^evals\/question_lab\/runs\/run-[a-f0-9]{32}$/.test(packet))
  throw new Error('packet_path');
const OUTPUT = path.resolve(
  '..',
  packet ?? 'evals/question_lab/runs/not-started',
  'captures',
);
const manifestPath = path.join(BASELINES, 'manifest.json');
const manifest = existsSync(manifestPath)
  ? JSON.parse(readFileSync(manifestPath, 'utf8'))
  : null;

// Each capture is recorded only through the shared capture
// matrix: the en test stores its card markup, the paired ar test runs the
// en/ar contract against it, the capture JSON (with its parity diagnostic)
// is written through the sink, and any recorded problem fails the test.

// The trusted reference records come from the release the fixture serves,
// read from its `work` folder on disk in Node (never from the page), once
// per worker. The answer fact's record id is DAT-93 over those release
// values and the area id the server issued, read from the network in Node.
const NIGHT = contextFamilies.night_lights;
const releases = new Map<string, ReleaseReferences>();
function trustedRelease(work: string): ReleaseReferences {
  let refs = releases.get(work);
  if (refs === undefined) {
    refs = releaseReferences(readReleaseDump(work, NIGHT.table), NIGHT.table);
    releases.set(work, refs);
  }
  return refs;
}
const issuedAreas = new WeakMap<Page, Promise<string | null>[]>();
const EVIDENCE_OPEN = new Set(['evidence', 'drawer', 'refusal']);

async function trustedReferences(
  { page, mounted }: Fixtures,
  run: LabRun<LabCase>,
  state: string,
): Promise<ReferenceRecord[]> {
  const issued = await Promise.all(issuedAreas.get(page) ?? []);
  const refs = trustedRelease(mounted.work);
  return nightLightsReferences(
    refs,
    answerFactId(refs, NIGHT.metric, answerArea(issued, run.question.mode)),
    EVIDENCE_OPEN.has(state),
  );
}

type Fixtures = { page: Page; mounted: { origin: string; work: string } };

// This check fails before app construction; an absent baseline is never created.
test.beforeAll(() => {
  expect(packet).toBeTruthy();
  expect(baselineProblems(BASELINES, manifest)).toEqual([]);
});

/** Reference preparation: forbid every request that leaves the mounted
 * fixture (the typed ask route stays local) and collect the area ids the
 * server issues for this page, in order. */
async function prepareLabReferences({
  page,
  mounted,
}: Fixtures): Promise<string[]> {
  const forbidden: string[] = [];
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    if (
      (url.protocol === 'http:' || url.protocol === 'https:') &&
      (url.origin !== mounted.origin || url.pathname === '/api/ask')
    ) {
      forbidden.push('forbidden_request');
      await route.abort('blockedbyclient');
    } else await route.continue();
  });
  const areas: Promise<string | null>[] = [];
  issuedAreas.set(page, areas);
  page.on('response', (response) => {
    const url = new URL(response.url());
    if (url.origin !== mounted.origin || url.pathname !== MAKE_AREA_PATH)
      return;
    areas.push(
      response
        .json()
        .then((body: { status?: unknown; payload?: { area_id?: unknown } }) =>
          body.status === 'OK' && typeof body.payload?.area_id === 'string'
            ? body.payload.area_id
            : null,
        ),
    );
  });
  return forbidden;
}

/** Story setup: the fixed clock, reduced motion, this run's language and
 * theme, the invented activity and the case's map anchor. */
async function openStory({ page, mounted }: Fixtures, run: LabRun<LabCase>) {
  const { question, width, height, language } = run;
  await page.setViewportSize({ width, height });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.addInitScript(installLabClock, '2026-03-01T12:00:00Z');
  await page.goto(`${mounted.origin}/?lang=${language}&theme=${run.theme}`);
  await page.locator('.stage[data-state="ready"]').waitFor();
  await page.evaluate(() => document.fonts.ready);
  await page.locator('[data-action="guided-story"]').click();
  await page
    .locator('[data-picker="activity"] input')
    .fill(language === 'ar' ? 'حرفة مخترعة' : 'INVENTED-Craft');
  await page.locator('[data-picker="activity"] button[type="submit"]').click();
  await page.locator('[data-picker="activity"] [data-candidate]').click();
  await page.evaluate((anchor) => {
    const map = Reflect.get(globalThis, 'eiiMap') as {
      jumpTo: (input: object) => void;
    };
    map.jumpTo({ center: [anchor, anchor], zoom: 14 });
  }, question.pin);
}

/** Draw the case's invented area with its tool and preset, submit it and
 * advance to the answer card, which is returned. */
async function drawInventedArea(
  page: Page,
  question: LabCase,
): Promise<Locator> {
  await page.locator('.drawing-disclosure > summary').click();
  const tool =
    question.mode === 'polygon'
      ? 'polygon'
      : question.mode === 'distance'
        ? 'radius'
        : 'travel';
  await page.locator(`[data-tool="${tool}"]`).click();
  if (question.mode !== 'polygon') {
    await page.locator('.drawing-disclosure > summary').click();
    await page
      .locator(
        `[data-preset="${question.mode === 'distance' ? 'distance-b' : question.mode === 'walk' ? 'walk-c' : 'drive-c'}"]`,
      )
      .click();
  }
  const overlay = page.locator('[data-part="area-overlay"]');
  const box = await overlay.boundingBox();
  if (!box) throw new Error('map_overlay_missing');
  const x = box.width / 2,
    y = box.height / 2;
  if (question.mode === 'polygon') {
    for (const [dx, dy] of [
      [-100, 80],
      [100, 80],
      [0, -100],
    ])
      await overlay.click({ position: { x: x + dx!, y: y + dy! } });
    await page.locator('[data-part="knob"]').first().click();
  } else await overlay.click({ position: { x, y } });
  await page.locator('.drawing-disclosure > summary').click();
  await page.locator('[data-part="use-area"]').click();
  await expect(page.locator('[data-action="story-next"]')).toBeEnabled();
  await page.locator('[data-action="story-next"]').click();
  const card = page.locator('[data-context-family="night_lights"]');
  await expect(card).toBeVisible();
  return card;
}

/** The context-state capture sequence, in its contract order: verify the
 * answer chip, record answer, comparison and evidence, then the drawer
 * and, for a refusal case, the refusal screen. */
async function captureContextStates(
  page: Page,
  run: LabRun<LabCase>,
  card: Locator,
): Promise<void> {
  const chip = card.locator('[data-fact-chip="value"]');
  await expect(chip.locator('.chip-num')).toHaveText(
    String(
      run.question.expected_value ??
        (run.question.pin < 1.1
          ? 4
          : run.question.pin < 1.6
            ? 7
            : run.question.pin < 2.1
              ? 10
              : 5),
    ),
  );
  mkdirSync(OUTPUT, { recursive: true });
  await run.capture('answer');
  for (const level of ['comparison', 'evidence']) {
    await card.locator(`[data-context-level="${level}"] > button`).click();
    await run.capture(level);
  }
  await chip.click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await run.capture('drawer');
  await page.keyboard.press('Escape');
  await expect(chip).toBeFocused();
  // These inputs have actual typed API refusals, not a free-text UI.
  // Keep unsupported refusal screens visibly uncovered, even when the
  // ordinary context capture above passed all layout proxies.
  if (run.question.refusal) {
    expect(run.question.refusal, 'refusal_ui_uncovered').toBe('missing_layer');
    await page
      .locator('.layer-chooser select')
      .selectOption('fc_firms_per_tower');
    await expect(page.getByRole('alert')).toBeVisible();
    await run.capture('refusal');
  }
}

async function drive(fixtures: Fixtures, run: LabRun<LabCase>) {
  const { page } = fixtures;
  const forbidden = await prepareLabReferences(fixtures);
  await openStory(fixtures, run);
  const card = await drawInventedArea(page, run.question);
  await captureContextStates(page, run, card);
  await page.locator('[data-action="story-reset"]').click();
  await expect(page.locator('[data-scene="opening"]')).toBeVisible();
  await expect(page.locator('[data-context-family]')).toHaveCount(0);
  expect(forbidden).toEqual([]);
}

async function snapshot(
  fixtures: Fixtures,
  run: LabRun<LabCase>,
  state: string,
): Promise<LabShot> {
  const { page } = fixtures;
  const report = await openingReport(page);
  expect(report.problems).toEqual([]);
  const png = await page.screenshot({
    path: path.join(OUTPUT, run.stem + '-' + state + '.png'),
  });
  const cardNode = page.locator('[data-context-family]').first();
  const cardHtml =
    (await cardNode.count()) === 0
      ? null
      : await cardNode.evaluate((node) => node.outerHTML);
  return {
    cardHtml,
    trusted:
      cardHtml === null ? [] : await trustedReferences(fixtures, run, state),
    fields: {
      question_id: run.question.identity,
      language: run.language,
      theme: run.theme,
      size: `${run.width}x${run.height}`,
      state,
      scope: 'typed_ui_context',
      sealed: false,
      path: 'captures/' + run.stem + '-' + state + '.png',
      sha256: createHash('sha256').update(png).digest('hex'),
      report,
      card_html: cardHtml,
      refusal_execution: run.question.refusal
        ? 'waiting:typed_route_companion'
        : 'not_applicable',
    },
  };
}

registerLabCaptures<LabCase, Fixtures>({
  cases: cases.cases,
  sizes: QUESTION_LAB_SIZES,
  themes: ['dark', 'light'],
  styles: CARD_STYLES,
  register: (title, body) =>
    test(title, ({ page, mounted }) => body({ page, mounted })),
  drive,
  snapshot,
  sink: (name, json) => writeFileSync(path.join(OUTPUT, name), json),
  compare: async ({ page }, name) => {
    await expect(page).toHaveScreenshot(name);
  },
});
