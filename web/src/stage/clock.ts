import { calendarDayInQatar } from '../facts/formatters';

/** Geometry clock, independent of every stored-hour fact and layer payload. */
export function clockDay(dayBasis?: string, now = new Date()): string {
  return dayBasis ?? calendarDayInQatar(now);
}

export function clockTimestamp(day: string, fraction: number): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return null;
  const start = Date.parse(`${day}T00:00:00Z`);
  if (!Number.isFinite(start)) return null;
  if (new Date(start).toISOString().slice(0, 10) !== day) return null;
  if (!Number.isFinite(fraction) || fraction < 0 || fraction > 1) return null;
  // Asia/Qatar civil day, UTC offset in the product's modern day basis.
  const localStart = Date.parse(`${day}T00:00:00+03:00`);
  return localStart + fraction * 24 * 60 * 60 * 1000;
}
