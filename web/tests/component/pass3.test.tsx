// @vitest-environment jsdom
import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { catalogue } from '../../src/brief/catalogue';
import { FactChip } from '../../src/facts/FactChip';
import { createRegistry } from '../../src/facts/registry';
import { AnswerShell } from '../../src/shell/AnswerShell';
import {
  completeInput,
  factId,
  makeBinding,
  makeLineage,
  makeSource,
} from '../fixtures/facts';

afterEach(() => {
  cleanup();
});

const DIGIT = /\p{Nd}/u;

function registryWith(sourceIds: string[], inputClasses: 'public'[]) {
  const input = completeInput();
  return createRegistry({
    ...input,
    lineages: [makeLineage({ sourceIds, inputClasses })],
    sources: sourceIds.length === 0 ? [] : [makeSource()],
  });
}

describe('a lineage with an empty source list', () => {
  it('does not become ready when both lists are empty', () => {
    const registry = registryWith([], []);
    const resolution = registry.resolve(factId(0));
    expect(resolution.status).toBe('refused');
    if (resolution.status === 'refused') {
      expect(resolution.missing).toBe('source');
    }
    const view = render(
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={registry}
        language="en"
        onOpen={() => undefined}
      />,
    );
    expect(view.container.querySelector('[data-state="refused"]')).toBeTruthy();
    expect(DIGIT.test(view.container.textContent ?? '')).toBe(false);
  });

  it('does not become ready when one list is empty', () => {
    const sourcesOnly = registryWith(['src_alpha'], []);
    const sourcesResolution = sourcesOnly.resolve(factId(0));
    expect(sourcesResolution.status).toBe('refused');
    if (sourcesResolution.status === 'refused') {
      expect(sourcesResolution.missing).toBe('input_class_source');
    }
    const classesOnly = registryWith([], ['public']);
    const classesResolution = classesOnly.resolve(factId(0));
    expect(classesResolution.status).toBe('refused');
    if (classesResolution.status === 'refused') {
      expect(classesResolution.missing).toBe('source');
    }
    const view = render(
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={sourcesOnly}
        language="en"
        onOpen={() => undefined}
      />,
    );
    expect(view.container.querySelector('[data-state="refused"]')).toBeTruthy();
    expect(DIGIT.test(view.container.textContent ?? '')).toBe(false);
  });
});

describe('map attribution', () => {
  it('shows OpenStreetMap and Protomaps in both directions', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    for (const language of ['en', 'ar'] as const) {
      const view = render(
        <AnswerShell language={language} theme="dark" extractUrl={null} />,
      );
      const credits = view.container.querySelector('[data-part="attribution"]');
      const shown = credits?.textContent ?? '';
      expect(shown).toContain('OpenStreetMap');
      expect(shown).toContain('Protomaps');
      expect(credits?.closest('.stage')).toBeTruthy();
      expect(view.container.querySelector('.shell')?.getAttribute('dir')).toBe(
        language === 'ar' ? 'rtl' : 'ltr',
      );
      view.unmount();
    }
    expect(
      fetchSpy.mock.calls.every(
        ([path, options]) =>
          path === '/api/map-modes' && options?.cache === 'no-store',
      ),
    ).toBe(true);
    fetchSpy.mockRestore();
  });
});

describe('register company answer', () => {
  function draft(
    provenance: 'public' | 'synthetic' | 'simulated',
    metric: string,
  ) {
    return {
      catalogueVersion: catalogue.version,
      accountingPassed: true,
      subject: 'register_company' as const,
      componentKey: 'foundation_note',
      props: [] as string[],
      directive: null,
      slots: [{ factId: factId(0), provenance, metric }],
    };
  }

  it('shows a chip for a public card fact', () => {
    const view = render(
      <AnswerShell
        language="en"
        theme="dark"
        extractUrl={null}
        registry={createRegistry({
          ...completeInput(),
          facts: [makeBinding({ metricKey: 'card' })],
        })}
        draft={draft('public', 'card')}
      />,
    );
    expect(view.container.querySelector('[data-fact-chip]')).toBeTruthy();
  });

  it('shows no chip for a synthetic wage', () => {
    const view = render(
      <AnswerShell
        language="en"
        theme="dark"
        extractUrl={null}
        registry={createRegistry(completeInput())}
        draft={draft('synthetic', 'wage')}
      />,
    );
    expect(view.container.querySelector('[data-fact-chip]')).toBeNull();
  });

  it('shows no chip for an employee count of the wrong class', () => {
    const view = render(
      <AnswerShell
        language="en"
        theme="dark"
        extractUrl={null}
        registry={createRegistry(completeInput())}
        draft={draft('simulated', 'employee_count')}
      />,
    );
    expect(view.container.querySelector('[data-fact-chip]')).toBeNull();
  });
});
