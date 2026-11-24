export type Lang = 'en' | 'ar';
export type Unit = 'count' | 'share';
export const LOCALES: Record<Lang, string>;
export function formatValue(value: number, unit: Unit, lang: Lang): string;
export function formatRange(low: number, high: number, lang: Lang): string;
export function dateParts(
  iso: string,
  lang: Lang,
): { day: string; month: string; year: string };
export function formatDate(iso: string, lang: Lang): string;
