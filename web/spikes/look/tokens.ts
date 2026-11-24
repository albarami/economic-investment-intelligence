// Reads the design tokens of tokens.css at run time, so that the map, the
// watermark and the motion use the same values as the page (DES-02).

export function token(name: string): string {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  if (value === '') throw new Error(`missing token ${name}`);
  return value;
}

export function tokenNumber(name: string): number {
  const value = Number.parseFloat(token(name));
  if (!Number.isFinite(value)) throw new Error(`token ${name} is not a number`);
  return value;
}

export function durationMs(name: string): number {
  const value = token(name);
  if (value.endsWith('ms')) return Number.parseFloat(value);
  if (value.endsWith('s')) return Number.parseFloat(value) * 1000;
  throw new Error(`token ${name} is not a duration`);
}

// The font of a type token without its line height, for a 2D canvas.
export function canvasFont(name: string, element: Element): string {
  const value = getComputedStyle(element).getPropertyValue(name).trim();
  return value.replace(/\/\s*[\d.]+px/, '');
}

export type Easing = (t: number) => number;

// A cubic Bézier easing from a token such as --eii-ease-enter.
export function easing(name: string): Easing {
  const match = token(name).match(/cubic-bezier\(([^)]+)\)/);
  if (match === null) throw new Error(`token ${name} is not a cubic Bézier`);
  const [x1, y1, x2, y2] = (match[1] ?? '')
    .split(',')
    .map((part) => Number.parseFloat(part));
  if ([x1, y1, x2, y2].some((part) => part === undefined || Number.isNaN(part)))
    throw new Error(`token ${name} is not a cubic Bézier`);
  const curve = (a: number, b: number, t: number) =>
    3 * a * (1 - t) ** 2 * t + 3 * b * (1 - t) * t ** 2 + t ** 3;
  return (progress: number) => {
    if (progress <= 0) return 0;
    if (progress >= 1) return 1;
    let low = 0;
    let high = 1;
    let t = progress;
    for (let step = 0; step < 24; step += 1) {
      t = (low + high) / 2;
      if (curve(x1 as number, x2 as number, t) < progress) low = t;
      else high = t;
    }
    return curve(y1 as number, y2 as number, t);
  };
}
