// The one place on the look page that turns a value into digits (DES-30,
// docs/10_FRONTEND.md section "5. The Fact chip rule"). It formats what a fact
// carries: grouping and the unit pattern only. It never rounds, compares or
// converts a value, and it adds no decimals.

export const LOCALES = { en: 'en-QA', ar: 'ar-QA-u-nu-latn' };

const BIDI_CONTROLS = /[؜‎‏‪-‮⁦-⁩]/g;

const STYLES = {
  count: { style: 'decimal', useGrouping: true, maximumFractionDigits: 20 },
  share: { style: 'percent', useGrouping: true, maximumFractionDigits: 20 },
};

function formatter(unit, lang) {
  const style = STYLES[unit];
  if (style === undefined) throw new Error(`unknown unit: ${unit}`);
  const locale = LOCALES[lang];
  if (locale === undefined) throw new Error(`unknown language: ${lang}`);
  return new Intl.NumberFormat(locale, { ...style, numberingSystem: 'latn' });
}

// Isolation is done by markup (DES-38), so control characters that Intl may
// insert are removed here.
function clean(text) {
  return text.replace(BIDI_CONTROLS, '');
}

export function formatValue(value, unit, lang) {
  return clean(formatter(unit, lang).format(value));
}

export function formatRange(low, high, lang) {
  return clean(formatter('count', lang).formatRange(low, high));
}

// Round 5g, finding 22: the date of a count (YYYY-MM-DD), day, month word and
// year in the Gregorian calendar with Western digits, in that order in both
// languages (en-QA alone would put the month first). A date is a reference,
// not a fact value: it is never rounded, compared or converted.
export function dateParts(iso, lang) {
  const locale = LOCALES[lang];
  if (locale === undefined) throw new Error(`unknown language: ${lang}`);
  const date = new Date(`${iso}T00:00:00Z`);
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(iso) ||
    Number.isNaN(date.getTime()) ||
    date.toISOString().slice(0, 10) !== iso
  )
    throw new Error(`not a calendar date: ${iso}`);
  const parts = new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    calendar: 'gregory',
    numberingSystem: 'latn',
    timeZone: 'UTC',
  }).formatToParts(date);
  const part = (type) =>
    clean(parts.find((item) => item.type === type)?.value ?? '');
  return { day: part('day'), month: part('month'), year: part('year') };
}

export function formatDate(iso, lang) {
  const { day, month, year } = dateParts(iso, lang);
  return `${day} ${month} ${year}`;
}
