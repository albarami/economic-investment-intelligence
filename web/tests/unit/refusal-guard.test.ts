import { readFileSync, readdirSync } from 'node:fs';
import { expect, it } from 'vitest';
import refusalRule, {
  refusalViolations,
  catalogueParity,
} from '../../eslint-rules/refusal-reasons.mjs';
import en from '../../src/i18n/en.json';
import ar from '../../src/i18n/ar.json';

it('guards the API and mounted shell, including the reverted D34 catch', () => {
  for (const file of [
    ...readdirSync('src/api')
      .filter((name) => /\.(?:ts|mjs)$/.test(name))
      .map((name) => 'src/api/' + name),
    'src/app/MountedPublicShell.tsx',
  ])
    expect(refusalViolations(readFileSync(file, 'utf8'))).toEqual([]);
  const plant = `loadPublicLayer(layer).catch(() => { setMounted(null); setLayerFailed(true); });`;
  expect(refusalViolations(plant)).toEqual([1]);
});
it.each([
  'try { work(); } catch { setFailed(true); }',
  'try { work(); } catch (error) { return null; }',
  'work().catch(error => setFailed(true));',
  'work().catch(error => { setFailed(Boolean(error)); });',
  'work().catch(error => { log("refusalState(error)"); setFailed(true); });',
])('rejects a discarded catch: %s', (source) => {
  expect(refusalViolations(source)).toHaveLength(1);
});
it.each([
  'try { work(); } catch (error) { setFailed(refusalState(error, "story.unavailable")); }',
  'work().catch(error => setFailed(refusalState(error, "layers.unavailable")));',
  'try { work(); } catch (error) { throw error; }',
])('accepts a projected or rethrown catch: %s', (source) => {
  expect(refusalViolations(source)).toEqual([]);
});
it('requires bilingual keys, including an English-only key plant', () => {
  expect(catalogueParity(en.strings, ar.strings)).toEqual([]);
  expect(
    catalogueParity(
      { ...en.strings, 'INVENTED.onlyEnglish': 'unavailable' },
      ar.strings,
    ),
  ).toContain('INVENTED.onlyEnglish');
});
it('wires the guard into lint and bilingual parity into the normal web check', () => {
  expect(readFileSync('eslint.config.js', 'utf8')).toContain(
    "'refusal/closed-reason': 'error'",
  );
  expect(readFileSync('scripts/check-answer.mjs', 'utf8')).toContain(
    '...refusalCatalogueProblems(web)',
  );
});

it('runs the planted D34 catch through the actual lint listener', () => {
  const reports: unknown[] = [];
  refusalRule
    .create({
      sourceCode: {
        text: 'loadPublicLayer(layer).catch(() => setLayerFailed(true));',
      },
      report: (report: unknown) => reports.push(report),
    })
    .Program();
  expect(reports).toEqual([
    { loc: { line: 1, column: 0 }, messageId: 'carry' },
  ]);
});
