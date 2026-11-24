/** Full per-answer matrix; actual S3 opening fixture, with no API interception.
 * Capture execution waits for local browser assets and approved CI baselines.
 * Software rendering establishes no native stage/phone performance result.
 */
import { test, expect } from '../e2e/opening-fixture';
import { openingReport } from '../audit/opening-audit';
import { QUESTION_LAB_SIZES } from './matrix';
import { installLabClock } from './clock';
import { baselineProblems } from './baselines.mjs';
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

// This check fails before app construction; an absent baseline is never created.
test.beforeAll(() => {
  expect(packet).toBeTruthy();
  expect(baselineProblems(BASELINES, manifest)).toEqual([]);
});

for (const question of cases.cases)
  for (const [width, height] of QUESTION_LAB_SIZES)
    for (const language of ['en', 'ar'] as const)
      for (const theme of ['dark', 'light'] as const) {
        test(`${question.identity} ${width}x${height} ${language} ${theme}`, async ({
          page,
          mounted,
        }) => {
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
          await page.setViewportSize({ width, height });
          await page.emulateMedia({ reducedMotion: 'reduce' });
          await page.addInitScript(installLabClock, '2026-03-01T12:00:00Z');
          await page.goto(`${mounted.origin}/?lang=${language}&theme=${theme}`);
          await page.locator('.stage[data-state="ready"]').waitFor();
          await page.evaluate(() => document.fonts.ready);
          await page.locator('[data-action="guided-story"]').click();
          await page
            .locator('[data-picker="activity"] input')
            .fill(language === 'ar' ? 'حرفة مخترعة' : 'INVENTED-Craft');
          await page
            .locator('[data-picker="activity"] button[type="submit"]')
            .click();
          await page
            .locator('[data-picker="activity"] [data-candidate]')
            .click();
          await page.evaluate((anchor) => {
            const map = Reflect.get(globalThis, 'eiiMap') as {
              jumpTo: (input: object) => void;
            };
            map.jumpTo({ center: [anchor, anchor], zoom: 14 });
          }, question.pin);
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
          await expect(
            page.locator('[data-action="story-next"]'),
          ).toBeEnabled();
          await page.locator('[data-action="story-next"]').click();
          const card = page.locator('[data-context-family="night_lights"]');
          await expect(card).toBeVisible();
          const chip = card.locator('[data-fact-chip="value"]');
          await expect(chip.locator('.chip-num')).toHaveText(
            String(
              question.expected_value ??
                (question.pin < 1.1
                  ? 4
                  : question.pin < 1.6
                    ? 7
                    : question.pin < 2.1
                      ? 10
                      : 5),
            ),
          );
          const stem = `${question.identity}-${width}x${height}-${language}-${theme}`;
          mkdirSync(OUTPUT, { recursive: true });
          async function capture(state: string) {
            const report = await openingReport(page);
            expect(report.problems).toEqual([]);
            const png = await page.screenshot({
              path: path.join(OUTPUT, stem + '-' + state + '.png'),
            });
            writeFileSync(
              path.join(OUTPUT, stem + '-' + state + '.json'),
              JSON.stringify(
                {
                  question_id: question.identity,
                  language,
                  theme,
                  size: `${width}x${height}`,
                  state,
                  scope: 'typed_ui_context',
                  sealed: false,
                  path: 'captures/' + stem + '-' + state + '.png',
                  sha256: createHash('sha256').update(png).digest('hex'),
                  report,
                  refusal_execution: question.refusal
                    ? 'waiting:typed_route_companion'
                    : 'not_applicable',
                },
                null,
                2,
              ) + '\n',
            );
            await expect(page).toHaveScreenshot(stem + '-' + state + '.png');
          }
          await capture('answer');
          for (const level of ['comparison', 'evidence']) {
            await card
              .locator(`[data-context-level="${level}"] > button`)
              .click();
            await capture(level);
          }
          await chip.click();
          await expect(page.getByRole('dialog')).toBeVisible();
          await capture('drawer');
          await page.keyboard.press('Escape');
          await expect(chip).toBeFocused();
          // These inputs have actual typed API refusals, not a free-text UI.
          // Keep unsupported refusal screens visibly uncovered, even when the
          // ordinary context capture above passed all layout proxies.
          if (question.refusal) {
            expect(question.refusal, 'refusal_ui_uncovered').toBe(
              'missing_layer',
            );
            await page
              .locator('.layer-chooser select')
              .selectOption('fc_firms_per_tower');
            await expect(page.getByRole('alert')).toBeVisible();
            await capture('refusal');
          }
          await page.locator('[data-action="story-reset"]').click();
          await expect(page.locator('[data-scene="opening"]')).toBeVisible();
          await expect(page.locator('[data-context-family]')).toHaveCount(0);
          expect(forbidden).toEqual([]);
        });
      }
