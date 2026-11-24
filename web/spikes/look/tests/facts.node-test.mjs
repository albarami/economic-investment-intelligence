import assert from 'node:assert/strict';
import { test } from 'node:test';
import { LOCALES, formatDate, formatRange, formatValue } from '../facts.mjs';

const BIDI_CONTROLS = /[؜‎‏‪-‮⁦-⁩]/;
const ARABIC_INDIC = /[٠-٩۰-۹]/;

test('the pinned locales name the Latin numbering system for Arabic', () => {
  assert.equal(LOCALES.en, 'en-QA');
  assert.equal(LOCALES.ar, 'ar-QA-u-nu-latn');
});

test('a grouped count is identical in both languages', () => {
  assert.equal(formatValue(1240, 'count', 'en'), '1,240');
  assert.equal(formatValue(1240, 'count', 'ar'), '1,240');
});

test('a share is a percentage with Western digits in both languages', () => {
  assert.equal(formatValue(0.38, 'share', 'en'), '38%');
  assert.equal(formatValue(0.38, 'share', 'ar'), '38%');
});

test('no Arabic-Indic digit and no bidirectional control is emitted', () => {
  for (const lang of ['en', 'ar']) {
    for (const [value, unit] of [
      [48600, 'count'],
      [0.38, 'share'],
      [186, 'count'],
    ]) {
      const text = formatValue(value, unit, lang);
      assert.equal(ARABIC_INDIC.test(text), false, text);
      assert.equal(BIDI_CONTROLS.test(text), false, JSON.stringify(text));
    }
  }
});

test('a range is one run with the lower bound first and an en dash', () => {
  assert.equal(formatRange(40, 120, 'en'), '40–120');
  assert.equal(formatRange(40, 120, 'ar'), '40–120');
  assert.equal(formatRange(300, 700, 'ar'), formatRange(300, 700, 'en'));
});

test('an unknown unit is refused rather than guessed', () => {
  assert.throws(() => formatValue(3, 'metres', 'en'), /unknown unit/);
});

test('the interface adds no decimals the fact does not carry', () => {
  assert.equal(formatValue(186, 'count', 'en'), '186');
});

// Round 5g, finding 22: the date of the register count, the month as a word
// and Western digits in both languages.
test('a date reads day, month word and year with Western digits in both languages', () => {
  assert.equal(formatDate('2026-11-13', 'en'), '13 November 2026');
  const arabic = formatDate('2026-11-13', 'ar');
  assert.doesNotMatch(arabic, ARABIC_INDIC);
  assert.doesNotMatch(arabic, BIDI_CONTROLS);
  assert.match(arabic, /^13 \p{L}+ 2026$/u);
  assert.throws(() => formatDate('2026-02-30', 'en'), /date/);
});
