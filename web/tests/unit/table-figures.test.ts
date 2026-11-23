import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

/*
 * Figures in tables (DES-31, DES-35; document 10, section 8): every table
 * cell that shows a number through the Fact chip family keeps tabular
 * lining figures and the start-edge alignment the design names, and one
 * rule serves Arabic and English, because numerals never mirror.
 */
const css = readFileSync('src/styles/answer.css', 'utf8');

function ruleBody(selectors: RegExp): string | undefined {
  return css.match(selectors)?.[1];
}

it('aligns figures in table cells through the Fact chip family', () => {
  const cell = ruleBody(/td \.chip,\nth \.chip \{([^}]*)\}/);
  expect(cell).toContain('text-align: start');
  expect(cell).not.toMatch(/text-align:\s*(left|right)/);

  const numeral = ruleBody(/td \.chip-num,\nth \.chip-num \{([^}]*)\}/);
  expect(numeral).toContain('font-variant-numeric: tabular-nums');
  expect(numeral).toContain("font-feature-settings: 'tnum' 1");
});

it('serves both languages with one logical rule', () => {
  for (const selectors of [
    /td \.chip,\nth \.chip \{([^}]*)\}/,
    /td \.chip-num,\nth \.chip-num \{([^}]*)\}/,
  ]) {
    const match = css.match(selectors);
    expect(match, String(selectors)).not.toBeNull();
    expect(match?.[0] ?? '').not.toMatch(/\[dir|\[lang|:lang/);
  }
});
