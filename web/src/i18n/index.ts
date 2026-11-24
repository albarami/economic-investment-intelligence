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

const FIRM_COUNT_METRIC = 'firms_per_tower';

export function unitLabel(
  language: Language,
  unit: string,
  metricKey: string,
): string | null {
  if (unit === 'count' && metricKey === FIRM_COUNT_METRIC) {
    return text(language, 'unit.firms');
  }
  return unitWord(language, unit);
}

export function reviewMarks(): readonly string[] {
  return Object.values(ar.review);
}
