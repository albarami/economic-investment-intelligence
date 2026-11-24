// @vitest-environment jsdom
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import hero from '../fixtures/hero-layer.json';
import { routeRegistry } from '../fixtures/public-route-registry';
import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { publishSelection } from '../../src/stage/layers/selection';
import type { LayerPayload } from '../../src/stage/layers/payload';
import type { Fact } from '../../src/facts/types';
const body = hero as unknown as { facts: Fact[]; payload: LayerPayload };
afterEach(cleanup);
describe('selected excluded zone', () => {
  for (const [name, reason] of [
    ['floor', 'below_ranking_floor'],
    ['zero', 'no_denominator'],
    ['missing', 'missing_input'],
  ]) {
    it.each(['click', 'Enter', ' ', 'pick'])(
      `${name} selects its own reason with %s`,
      (action) => {
        const { container } = render(
          <PublicLayers
            payload={body.payload}
            registry={routeRegistry(body)}
            language="en"
            onOpenChain={() => {}}
          />,
        );
        const id = 'zone:INVENTED-zone-' + name;
        const button = container.querySelector(`[data-not-ranked="${id}"]`)!;
        expect(button).not.toBeNull();
        if (action === 'pick') act(() => publishSelection(id));
        else if (action === 'click') fireEvent.click(button);
        else {
          (button as HTMLElement).focus();
          fireEvent.keyDown(button, { key: action });
        }
        const panel = container.querySelector(
          '[data-part="not-ranked-panel"]',
        )!;
        expect(panel?.getAttribute('data-zone')).toBe(id);
        expect(panel?.getAttribute('data-reason')).toBe(reason);
        const sentences = {
          below_ranking_floor: 'Below the ranking floor.',
          no_denominator: 'No baseline denominator is available.',
          missing_input: 'The source series is missing.',
        };
        expect(panel?.textContent).toContain(
          sentences[reason as keyof typeof sentences],
        );
        for (const [key, sentence] of Object.entries(sentences))
          if (key !== reason)
            expect(panel?.textContent).not.toContain(sentence);
        expect(panel?.querySelector('[data-fact-id]')).toBeNull();
        expect(panel?.textContent).not.toMatch(/[0-9]/);
      },
    );
  }
});
