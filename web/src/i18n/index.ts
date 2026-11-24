import ar from './ar.json' with { type: 'json' };
import en from './en.json' with { type: 'json' };

export type Language = 'en' | 'ar';

export type StringKey = keyof typeof en.strings;

const TABLES = {
  en: en.strings,
  ar: ar.strings,
} as const;

export function direction(language: Language): 'ltr' | 'rtl' {
  return language === 'ar' ? 'rtl' : 'ltr';
}

export function text(language: Language, key: StringKey): string {
  const table = TABLES[language];
  const value = table[key];
  if (typeof value !== 'string') {
    throw new Error(`Missing string ${key}`);
  }
  return value;
}

export function unitWord(language: Language, unit: string): string | null {
  const key = `unit.${unit}` as StringKey;
  if (!(key in en.strings)) return null;
  return text(language, key);
}

/** S3-T12: a count of recorded road accidents, whose noun agrees with it. */
const ACCIDENT_COUNT_METRIC = 'accident_count';
/** Counts of things other than people name their own unit. */
const COUNT_UNITS: Readonly<Record<string, StringKey>> = {
  firms_per_tower: 'unit.firms',
  building_height_pairs: 'unit.buildings',
};

export function unitLabel(
  language: Language,
  unit: string,
  metricKey: string,
  form: Intl.LDMLPluralRule = 'other',
): string | null {
  if (unit === 'count' && Object.hasOwn(COUNT_UNITS, metricKey))
    return text(language, COUNT_UNITS[metricKey] as StringKey);
  if (unit === 'count' && metricKey === ACCIDENT_COUNT_METRIC) {
    return text(language, `unit.accidents.${form}`);
  }
  return unitWord(language, unit);
}

export function reviewMarks(): readonly string[] {
  return Object.values(ar.review);
}
