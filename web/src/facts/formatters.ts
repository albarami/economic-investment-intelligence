/**
 * Grouping, unit pattern and calendar words. No rounding, rescaling,
 * compaction or conversion. The lint rule keeps every formatting call here.
 */
import { text } from '../i18n';
import type { Language } from './types';

export type TextRole = 'fact' | 'reference' | 'operational';
export type SignMode = 'auto' | 'always';

export type FormatResult =
  | { ok: true; text: string }
  | { ok: false; reason: 'unknown-unit' | 'bad-value' };

const NUMERIC_UNITS = new Set([
  'count',
  'qar_per_month',
  'qar',
  'qar_thousand',
  'qar_million',
  'qar_per_kg',
  'qar_per_m2',
  'usd_million',
  'announced_jobs',
  'decimal_degree',
  'kwh',
  'riders',
  'ratio',
  'percent',
  'index',
  'relative_index',
  'metres',
  'kilometres',
  'square_metre',
  'minutes',
  'covers_per_day',
  'people_per_km2',
  'tonnage',
  'rank',
  'radiance_nw_cm2_sr',
  'qar_per_ft2',
  'years',
]);

const INTEGER_UNITS = new Set(['count', 'rank']);

const CODE_UNITS = new Set(['wage_band', 'size_band', 'volume_band']);

const DIRECTIONS = new Set(['higher', 'lower', 'equal']);

const WAGE_BAND = /^B(0[1-9]|1[0-2])(\.\.B(0[1-9]|1[0-2]))?$/;
const SIZE_BAND = /^(no_payroll|s[0-9]{2}_([0-9]{2}|plus))$/;
const VOLUME_BAND = /^vb[0-9]+$/;
const PUBLISHED_MARKS =
  /[\u0660-\u0669\u06F0-\u06F9\u200B-\u200F\u2028-\u202E\u2060-\u2069\uFEFF]/;
const NON_WESTERN_DIGIT = /\p{Nd}/u;
const EXACT_DIGIT_RUN = /(^|[^0-9])([0-9]{8}|[0-9]{11})([^0-9]|$)/;
const SCIENTIFIC = /^(-?)(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/i;

const BIDI = /[\u200e\u200f\u202a-\u202e\u2066-\u2069]/g;

const MONTH_LENGTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

function localeOf(language: Language): string {
  return language === 'ar' ? 'ar-QA-u-nu-latn' : 'en-QA';
}

/**
 * The grammatical form a count takes in the chip's language (Arabic: zero,
 * one, two, few, many or other). It chooses a word, never a shown number.
 */
export function countForm(
  value: unknown,
  language: Language,
): Intl.LDMLPluralRule {
  return typeof value === 'number'
    ? new Intl.PluralRules(localeOf(language)).select(value)
    : 'other';
}

function stripBidi(value: string): string {
  return value.replace(BIDI, '');
}

function fractionDigits(value: number): number | null {
  if (!Number.isFinite(value)) return null;
  const rendered = JSON.stringify(value);
  const match = SCIENTIFIC.exec(rendered);
  if (!match) return null;
  const fraction = match[3]?.length ?? 0;
  const exponent = match[4] === undefined ? 0 : Number(match[4]);
  const digits = fraction - exponent;
  if (!Number.isInteger(digits)) return null;
  return digits < 0 ? 0 : digits;
}

function publishedTextOk(value: string): boolean {
  if (value.length < 1 || value.length > 200) return false;
  if (!/[0-9]/.test(value)) return false;
  if (NON_WESTERN_DIGIT.test(value.replace(/[0-9]/g, ''))) return false;
  if (!/^\S(.*\S)?$/.test(value)) return false;
  if (PUBLISHED_MARKS.test(value)) return false;
  for (const char of value) {
    const code = char.codePointAt(0) ?? 0;
    if (code <= 0x1f || (code >= 0x7f && code <= 0x9f)) return false;
  }
  if (EXACT_DIGIT_RUN.test(value)) return false;
  return true;
}

function bandOk(unit: string, value: string): boolean {
  if (unit === 'wage_band') return WAGE_BAND.test(value);
  if (unit === 'size_band') return SIZE_BAND.test(value);
  return VOLUME_BAND.test(value);
}

function leap(year: number): boolean {
  if (year % 400 === 0) return true;
  if (year % 100 === 0) return false;
  return year % 4 === 0;
}

function validDay(year: number, month: number, day: number): boolean {
  if (month < 1 || month > 12 || day < 1) return false;
  const length = MONTH_LENGTH[month - 1] ?? 0;
  const cap = month === 2 && leap(year) ? length + 1 : length;
  return day <= cap;
}

function formatNumber(
  value: number,
  language: Language,
  digits: number,
  grouping: boolean,
  sign: SignMode,
): string {
  const formatted = new Intl.NumberFormat(localeOf(language), {
    numberingSystem: 'latn',
    useGrouping: grouping,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: sign,
  }).format(value);
  return stripBidi(formatted).replaceAll('-', '\u2212');
}

function formatPercent(
  value: number,
  language: Language,
  digits: number,
  grouping: boolean,
  sign: SignMode,
): string {
  const formatted = new Intl.NumberFormat(localeOf(language), {
    numberingSystem: 'latn',
    style: 'unit',
    unit: 'percent',
    unitDisplay: 'narrow',
    useGrouping: grouping,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: sign,
  }).format(value);
  return stripBidi(formatted).replaceAll('-', '\u2212');
}

function formatCalendar(
  language: Language,
  year: number,
  month: number | null,
  day: number | null,
): string {
  const options: Intl.DateTimeFormatOptions = {
    calendar: 'gregory',
    numberingSystem: 'latn',
    timeZone: 'UTC',
    year: 'numeric',
  };
  if (month !== null) options.month = 'long';
  if (day !== null) options.day = 'numeric';
  const stamp = Date.UTC(year, month === null ? 0 : month - 1, day ?? 1);
  const formatted = new Intl.DateTimeFormat(localeOf(language), options).format(
    stamp,
  );
  return stripBidi(formatted);
}

export function formatFactValue(
  value: number | string | null,
  unit: string,
  language: Language,
  role: TextRole = 'fact',
  sign: SignMode = 'auto',
): FormatResult {
  // Operational USD stays byte-identical to the server's exact decimal.
  if (role === 'operational' && unit === 'usd') {
    return typeof value === 'string' &&
      /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(value)
      ? { ok: true, text: value }
      : { ok: false, reason: 'bad-value' };
  }
  if (value === null) return { ok: false, reason: 'bad-value' };
  if (unit === 'published_text') {
    if (typeof value !== 'string' || value.length === 0)
      return { ok: false, reason: 'bad-value' };
    if (role === 'fact' && !publishedTextOk(value))
      return { ok: false, reason: 'bad-value' };
    return { ok: true, text: value };
  }
  if (
    unit === 'calendar_date' ||
    unit === 'calendar_month' ||
    unit === 'calendar_year'
  )
    return formatCalendarUnit(value, unit, language);
  if (unit === 'direction') {
    if (typeof value !== 'string' || !DIRECTIONS.has(value))
      return { ok: false, reason: 'bad-value' };
    const key = `direction.${value}` as
      'direction.higher' | 'direction.lower' | 'direction.equal';
    return { ok: true, text: text(language, key) };
  }
  if (CODE_UNITS.has(unit)) {
    if (typeof value !== 'string' || !bandOk(unit, value))
      return { ok: false, reason: 'bad-value' };
    return { ok: true, text: value };
  }
  if (!NUMERIC_UNITS.has(unit)) return { ok: false, reason: 'unknown-unit' };
  if (typeof value !== 'number') return { ok: false, reason: 'bad-value' };
  if (INTEGER_UNITS.has(unit) && !Number.isInteger(value))
    return { ok: false, reason: 'bad-value' };
  const digits = fractionDigits(value);
  if (digits === null) return { ok: false, reason: 'bad-value' };
  if (unit === 'percent') {
    return {
      ok: true,
      text: formatPercent(value, language, digits, true, sign),
    };
  }
  return { ok: true, text: formatNumber(value, language, digits, true, sign) };
}

function formatCalendarUnit(
  value: number | string,
  unit: string,
  language: Language,
): FormatResult {
  if (typeof value !== 'string') return { ok: false, reason: 'bad-value' };
  if (unit === 'calendar_year') {
    const match = /^([1-9][0-9]{3})$/.exec(value);
    if (!match) return { ok: false, reason: 'bad-value' };
    return {
      ok: true,
      text: formatCalendar(language, Number(match[1]), null, null),
    };
  }
  if (unit === 'calendar_month') {
    const match = /^([1-9][0-9]{3})-(0[1-9]|1[0-2])$/.exec(value);
    if (!match) return { ok: false, reason: 'bad-value' };
    return {
      ok: true,
      text: formatCalendar(language, Number(match[1]), Number(match[2]), null),
    };
  }
  const match =
    /^([1-9][0-9]{3})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$/.exec(value);
  if (!match) return { ok: false, reason: 'bad-value' };
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!validDay(year, month, day)) return { ok: false, reason: 'bad-value' };
  return { ok: true, text: formatCalendar(language, year, month, day) };
}

/** Lower bound first. The caller names the bounds; this does not compare them. */
export function formatRange(
  low: number,
  high: number,
  unit: string,
  language: Language,
): FormatResult {
  const left = formatFactValue(low, unit, language);
  const right = formatFactValue(high, unit, language);
  if (!left.ok) return left;
  if (!right.ok) return right;
  return { ok: true, text: `${left.text}\u2013${right.text}` };
}

export function formatUiOrdinal(
  value: number,
  language: Language,
): FormatResult {
  if (!Number.isInteger(value)) return { ok: false, reason: 'bad-value' };
  return { ok: true, text: formatNumber(value, language, 0, true, 'auto') };
}

/** The sunlight control's day basis; its displayed date remains a reference chip. */
export function calendarDayInQatar(now: Date): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Qatar',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}
