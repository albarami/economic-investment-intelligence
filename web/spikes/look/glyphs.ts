// Custom outline glyphs on a 24 px grid (DES-45, DES-46), drawn once. On the
// wall they are set at 40 px, where the 1.8 unit stroke is 3 px. None depicts
// an eye, a camera, a person or a vehicle. Every glyph sits beside its word.

const NS = 'http://www.w3.org/2000/svg';

type Shape = { tag: 'path' | 'rect' | 'circle'; attrs: Record<string, string> };

const SHAPES: Record<string, Shape[]> = {
  // Seat glyph of a company seat: a building outline with a door.
  seat: [
    {
      tag: 'rect',
      attrs: { x: '4.5', y: '3', width: '15', height: '18', rx: '1.5' },
    },
    {
      tag: 'path',
      attrs: { d: 'M10 21v-4.5h4V21M8.5 7.5h2m3 0h2m-7 4h2m3 0h2' },
    },
  ],
  pause: [{ tag: 'path', attrs: { d: 'M9 6v12M15 6v12' } }],
  play: [{ tag: 'path', attrs: { d: 'M8 5.5v13l10.5-6.5z' } }],
  // A chevron toward the inline end; style.css turns it in Arabic.
  chevron: [{ tag: 'path', attrs: { d: 'M9.5 5.5 16 12l-6.5 6.5' } }],
};

export function glyph(
  name: keyof typeof SHAPES,
  className = 'glyph',
): SVGSVGElement {
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  svg.setAttribute('class', className);
  for (const shape of SHAPES[name] ?? []) {
    const element = document.createElementNS(NS, shape.tag);
    for (const [key, value] of Object.entries(shape.attrs)) {
      element.setAttribute(key, value);
    }
    svg.append(element);
  }
  return svg;
}
