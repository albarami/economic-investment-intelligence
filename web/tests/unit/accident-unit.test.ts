/**
 * CF1 finding 1: an accident count is labelled as road accidents, never as
 * people, with the Arabic counted noun agreeing with the count (zero, one,
 * two, few, many, other). The oracle below is the written Arabic rule, kept
 * apart from the code under test, over every count from zero to 1,200.
 */
import { describe, expect, it } from 'vitest';

import { countForm } from '../../src/facts/formatters';
import { text, unitLabel, type Language } from '../../src/i18n';

const WORDS = {
  en: { one: 'road accident', plural: 'road accidents' },
  ar: {
    zero: 'حادث مروري',
    one: 'حادث مروري',
    two: 'حادثان مروريان',
    few: 'حوادث مرورية',
    many: 'حادثًا مروريًا',
    other: 'حادث مروري',
  },
} as const;

/** The Arabic agreement rule of a whole count, written out. */
function arabicForm(n: number): keyof typeof WORDS.ar {
  const tail = n % 100;
  if (n === 0) return 'zero';
  if (n === 1) return 'one';
  if (n === 2) return 'two';
  if (tail >= 3 && tail <= 10) return 'few';
  if (tail >= 11 && tail <= 99) return 'many';
  return 'other';
}

function expected(language: Language, n: number): string {
  if (language === 'ar') return WORDS.ar[arabicForm(n)];
  return n === 1 ? WORDS.en.one : WORDS.en.plural;
}

const COUNTS = Array.from({ length: 1201 }, (_, n) => n);

describe('the accident count unit (CF1 finding 1)', () => {
  for (const language of ['en', 'ar'] as const)
    it(`agrees with every count from zero to 1,200 in ${language}`, () => {
      for (const n of COUNTS)
        expect(
          unitLabel(
            language,
            'count',
            'accident_count',
            countForm(n, language),
          ),
          String(n),
        ).toBe(expected(language, n));
    });

  it('reads the boundaries of each Arabic form', () => {
    const shown = [0, 1, 2, 3, 10, 11, 99, 100, 101, 102, 103, 111, 1000].map(
      (n) => unitLabel('ar', 'count', 'accident_count', countForm(n, 'ar')),
    );
    expect(shown).toEqual([
      'حادث مروري',
      'حادث مروري',
      'حادثان مروريان',
      'حوادث مرورية',
      'حوادث مرورية',
      'حادثًا مروريًا',
      'حادثًا مروريًا',
      'حادث مروري',
      'حادث مروري',
      'حادث مروري',
      'حوادث مرورية',
      'حادثًا مروريًا',
      'حادث مروري',
    ]);
  });

  it('never labels an accident count as people', () => {
    for (const language of ['en', 'ar'] as const)
      for (const n of COUNTS)
        expect(
          unitLabel(
            language,
            'count',
            'accident_count',
            countForm(n, language),
          ),
        ).not.toBe(text(language, 'unit.count'));
  });

  it('reads a value that is not a number as the general form', () => {
    for (const value of ['5', null, Number.NaN] as const)
      expect(countForm(value, 'ar')).toBe('other');
  });

  it('keeps the firms label and the people label of other counts', () => {
    for (const language of ['en', 'ar'] as const) {
      expect(unitLabel(language, 'count', 'firms_per_tower', 'few')).toBe(
        text(language, 'unit.firms'),
      );
      expect(unitLabel(language, 'count', 'venue_visits', 'few')).toBe(
        text(language, 'unit.count'),
      );
    }
  });
});
