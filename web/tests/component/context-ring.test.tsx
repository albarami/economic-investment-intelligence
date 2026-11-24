// @vitest-environment jsdom
// S3-T26 A5 (findings 2 and 4): one gate binds the dashed ring, its legend and
// data-directive="rings" to an accepted rings directive and a resolved outline.
import { cleanup, render } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import type { AnswerDirective } from '../../src/brief/catalogue';
import type { AreaOutline } from '../../src/api/areas';
import { Stage } from '../../src/stage/Stage';
import { registerPort, releasePort } from '../../src/state/area-actions';
import { plainPort } from '../fixtures/plain-port';

let token = 0;
afterEach(() => {
  cleanup();
  releasePort(token);
});
const polygon: AreaOutline = {
  type: 'Polygon',
  coordinates: [
    [
      [0, 0],
      [0, 1],
      [1, 1],
      [0, 0],
    ],
  ],
};
const circle: AreaOutline = {
  type: 'Circle',
  coordinates: [0, 0],
  radius_m: 500,
};
const rings = (fields: Record<string, unknown>): AnswerDirective =>
  ({ name: 'rings', fields }) as AnswerDirective;
const accepted = rings({ area_ids: ['INVENTED-near', 'INVENTED-wider'] });
const LEGEND = {
  en: 'The dashed line marks the wider context area.',
  ar: 'الخط المتقطّع يحدّد منطقة السياق الأوسع.',
};

function stage(
  directive: AnswerDirective | null,
  outline: AreaOutline | null,
  language: 'en' | 'ar' = 'en',
  port = true,
) {
  if (port) token = registerPort(plainPort(320, 320));
  const { container } = render(
    <Stage
      language={language}
      theme="dark"
      extractUrl={null}
      directive={directive}
      contextRing={outline}
    />,
  );
  const section = container.querySelector('.stage')!;
  return {
    bound: section.getAttribute('data-directive'),
    ring: container.querySelectorAll('[data-part="context-ring"]'),
    legend: container.querySelector('[data-part="context-area"]'),
  };
}

it.each(['en', 'ar'] as const)(
  'draws the dashed ring with its legend for an accepted directive (%s)',
  (language) => {
    for (const outline of [polygon, circle]) {
      const shown = stage(accepted, outline, language);
      expect(shown.bound).toBe('rings');
      expect(shown.ring).toHaveLength(1);
      expect(
        shown.ring[0]!.querySelector('.context-ring-line')!.getAttribute(
          'points',
        ),
      ).toMatch(/,/);
      expect(shown.legend?.textContent).toBe(LEGEND[language]);
      expect(shown.legend?.getAttribute('dir')).toBe(
        language === 'ar' ? 'rtl' : 'ltr',
      );
      expect(shown.legend?.textContent).not.toMatch(/[0-9٠-٩]/);
      cleanup();
      releasePort(token);
    }
  },
);

it.each<[string, AnswerDirective | null, AreaOutline | null, string]>([
  ['no directive', null, polygon, 'none'],
  ['no resolved outline', accepted, null, 'unbound'],
  [
    'three ring ids',
    rings({ area_ids: ['INVENTED-a', 'INVENTED-b', 'INVENTED-c'] }),
    polygon,
    'rejected',
  ],
  [
    'an extra field',
    rings({ area_ids: ['INVENTED-a'], extra: 'INVENTED' }),
    polygon,
    'rejected',
  ],
  ['a missing field', rings({}), polygon, 'rejected'],
  [
    'another accepted directive',
    { name: 'layer', fields: { layer: 'INVENTED-layer', visible: true } },
    polygon,
    'unbound',
  ],
])('draws no ring or legend for %s', (_name, directive, outline, bound) => {
  const shown = stage(directive, outline);
  expect(shown.bound).toBe(bound);
  expect(shown.ring).toHaveLength(0);
  expect(shown.legend).toBeNull();
});

it('draws neither ring nor legend for an outline of fewer than two points', () => {
  const point: AreaOutline = { type: 'Polygon', coordinates: [[[0, 0]]] };
  const shown = stage(accepted, point);
  expect(shown.ring).toHaveLength(0);
  expect(shown.legend).toBeNull();
});

// S3-T26 A5 fix round 2 (F2): the bound state, the ring and the legend follow
// one drawable ring and an available port, all three together.
it.each<[string, AreaOutline, boolean]>([
  ['a short outline', { type: 'Polygon', coordinates: [[[0, 0]]] }, true],
  ['an empty outline', { type: 'Polygon', coordinates: [] }, true],
  [
    'a closed ring with no area',
    {
      type: 'Polygon',
      coordinates: [
        [
          [0, 0],
          [0, 0],
          [0, 0],
          [0, 0],
        ],
      ],
    },
    true,
  ],
  ['an absent port', polygon, false],
])('binds nothing for %s', (_name, outline, port) => {
  const shown = stage(accepted, outline, 'en', port);
  expect([shown.bound, shown.ring.length, shown.legend]).toEqual([
    'unbound',
    0,
    null,
  ]);
});
