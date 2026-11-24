import { describe, expect, it } from 'vitest';
import en from '../../src/i18n/en.json';
import ar from '../../src/i18n/ar.json';

const OPENING_KEYS = [
  'opening.question',
  'opening.guided',
  'opening.action.site',
  'story.next',
  'story.reset',
  'language.switch',
  'draw.namedPlace',
  'draw.moveVertex',
  'map.pan',
  'map.zoomIn',
  'map.zoomOut',
  'map.recentre',
];

export function parity(
  left: Record<string, string>,
  right: Record<string, string>,
) {
  return (
    Object.keys(left).sort().join() === Object.keys(right).sort().join() &&
    OPENING_KEYS.every((key) => Boolean(left[key]) && Boolean(right[key]))
  );
}

describe('bilingual opening catalogue', () => {
  it('has every opening/control key in both languages', () => {
    expect(parity(en.strings, ar.strings)).toBe(true);
  });
  it('rejects a planted missing Arabic key', () => {
    const broken: Record<string, string> = { ...ar.strings };
    delete broken['opening.question'];
    expect(parity(en.strings, broken)).toBe(false);
  });
  it('contains no numeral in the application string tables', () => {
    for (const value of [
      ...Object.values(en.strings),
      ...Object.values(ar.strings),
    ])
      expect(value).not.toMatch(/\p{Nd}/u);
  });
});
