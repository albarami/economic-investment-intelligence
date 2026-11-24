// @vitest-environment jsdom
/**
 * S3-T16 in the mounted shell: a building statistic's Fact chip opens the
 * chain of the heights read itself (its method and its sources), never the
 * shell's registry, whether the shell holds another registry or none.
 * Invented buildings SYN-B-* and `.invalid` sources from the route fixture.
 */
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import type { FactRegistry } from '../../src/facts/registry';
import type { Language } from '../../src/i18n';
import { AnswerShell } from '../../src/shell/AnswerShell';
import { heightsBody } from '../fixtures/building-heights';
import { fakeMap, serve } from '../fixtures/building-stage';
import { completeRegistry } from '../fixtures/facts';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const CASES: readonly (readonly [Language, string])[] = [
  ['en', 'other'],
  ['ar', 'other'],
  ['en', 'none'],
  ['ar', 'none'],
];

it.each(CASES)(
  'a building error chip opens the heights chain (%s, shell registry %s)',
  async (language, shellRegistry) => {
    const body = heightsBody();
    serve(body);
    const map = fakeMap();
    const registry: FactRegistry | null =
      shellRegistry === 'other' ? completeRegistry() : null;
    const view = render(
      <AnswerShell
        language={language}
        theme="dark"
        extractUrl="/SYN-map.pmtiles"
        mapStarter={() => map.handle}
        registry={registry}
      />,
    );
    const selector =
      '[data-part="fallback-panel"] [data-fallback="wsf3d"] button[data-fact-chip]';
    await waitFor(() =>
      expect(view.container.querySelectorAll(selector).length).toBe(4),
    );
    const chip = view.container.querySelectorAll<HTMLElement>(selector)[2]!;
    fireEvent.click(chip);
    const drawer = await waitFor(() => {
      const found = view.container.querySelector('[role="dialog"]');
      expect(found).not.toBeNull();
      return found!;
    });
    expect(drawer.querySelector('[data-part="missing"]')).toBeNull();
    expect(drawer.querySelector('[data-part="method"]')?.textContent).toContain(
      'MTH-125',
    );
    const sources = [...drawer.querySelectorAll('[data-part="source"]')].map(
      (row) => row.textContent ?? '',
    );
    expect(sources).toHaveLength(body.sources.length);
    for (const source of body.sources) {
      expect(sources.some((row) => row.includes(source.publisher))).toBe(true);
    }
  },
);
