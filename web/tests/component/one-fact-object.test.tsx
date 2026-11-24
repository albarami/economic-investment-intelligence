// @vitest-environment jsdom
/**
 * S3-T10: the answer, the comparison and the evidence and method levels
 * read one fact object by id for each number; a withheld fact shows its
 * reason, never zero. Invented fixtures only.
 */
import { cleanup, fireEvent, render, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { Brief } from '../../src/brief/Brief';
import { catalogue, type AnswerDraft } from '../../src/brief/catalogue';
import { PublicContextCard } from '../../src/cards/PublicContextCard';
import { FactChip } from '../../src/facts/FactChip';
import { SourceChainDrawer } from '../../src/facts/SourceChainDrawer';
import { formatFactValue } from '../../src/facts/formatters';
import { createRegistry, type FactRegistry } from '../../src/facts/registry';
import { text, type Language } from '../../src/i18n';
import { completeInput, factId } from '../fixtures/facts';
import { contextInput, contextPayloads } from '../fixtures/public-context';

afterEach(cleanup);

const LANGUAGES = ['en', 'ar'] as const;
/** A value no formatter step may round away unnoticed. */
const PRECISE = 7.3456;
/** A hidden value no withheld view may expose. */
const HIDDEN = 7391;
const ZERO = /(?:^|[^\p{N}])[0٠](?:$|[^\p{N}])/u;

function draft(id: string): AnswerDraft {
  return {
    catalogueVersion: catalogue.version,
    accountingPassed: true,
    subject: 'area',
    componentKey: 'foundation_note',
    props: [],
    directive: null,
    slots: [{ factId: id, provenance: 'public', metric: 'people' }],
  };
}

function shown(root: ParentNode, id: string): string[] {
  return [
    ...root.querySelectorAll(`[data-fact-chip][data-fact-id="${id}"]`),
  ].map((chip) => chip.querySelector('.chip-num')?.textContent ?? '');
}

function expected(
  registry: FactRegistry,
  id: string,
  language: Language,
): string {
  const resolved = registry.resolve(id);
  if (resolved.status !== 'ready') throw new Error('ready fixture required');
  const fact = resolved.binding.fact;
  const formatted = formatFactValue(fact.value, fact.unit, language);
  if (!formatted.ok) throw new Error('formattable fixture required');
  return formatted.text;
}

function openLevel(root: HTMLElement, index: number): HTMLElement {
  const control = root.querySelectorAll<HTMLButtonElement>(
    '[data-context-level] > button',
  )[index]!;
  if (control.getAttribute('aria-expanded') !== 'true')
    fireEvent.click(control);
  return document.getElementById(control.getAttribute('aria-controls')!)!;
}

describe.each(LANGUAGES)('one fact object per number in %s', (language) => {
  it('the answer and the evidence and method drawer show one formatted value of one object', () => {
    const input = completeInput();
    const id = factId(0);
    const registry = createRegistry(input);
    const resolved = registry.resolve(id);
    expect(resolved.status).toBe('ready');
    if (resolved.status !== 'ready') return;
    // No copy: the registry hands back the very object it was given.
    expect(resolved.binding.fact).toBe(input.facts[0]!.fact);
    expect(registry.resolve(id)).not.toBe(resolved);
    const view = render(
      <>
        <Brief
          language={language}
          registry={registry}
          draft={draft(id)}
          onOpen={() => undefined}
        />
        <SourceChainDrawer
          factId={id}
          registry={registry}
          language={language}
          onClose={() => undefined}
        />
      </>,
    );
    const values = shown(view.container, id);
    expect(values).toHaveLength(2);
    expect(new Set(values)).toEqual(
      new Set([expected(registry, id, language)]),
    );
    const drawer = view.container.querySelector('[role="dialog"]')!;
    expect(drawer.getAttribute('data-fact-id')).toBe(id);
    expect(drawer.textContent).toContain(resolved.lineage.method);
    expect(drawer.textContent).toContain(resolved.lineage.methodVersion);
  });

  it('every level of a context card reads the same fact by id with no re-rounding', () => {
    const input = contextInput();
    const payload = contextPayloads[0]!;
    if (payload.state !== 'ready') throw new Error('ready fixture required');
    input.facts[0]!.fact.value = PRECISE;
    const registry = createRegistry(input);
    const resolved = registry.resolve(payload.factId);
    if (resolved.status !== 'ready') throw new Error('ready fixture required');
    expect(resolved.binding.fact).toBe(input.facts[0]!.fact);
    const view = render(
      <>
        <PublicContextCard
          payload={payload}
          registry={registry}
          language={language}
          onOpen={() => undefined}
        />
        <SourceChainDrawer
          factId={payload.factId}
          registry={registry}
          language={language}
          onClose={() => undefined}
        />
      </>,
    );
    const card = view.container.querySelector('article')!;
    const levels = [0, 1, 2].map((index) => openLevel(card, index));
    for (const region of levels)
      expect(region.getAttribute('data-fact-id')).toBe(payload.factId);
    const values = shown(view.container, payload.factId);
    expect(values).toHaveLength(2);
    const once = expected(registry, payload.factId, language);
    expect(new Set(values)).toEqual(new Set([once]));
    expect(once).toContain('3456');
    const evidence = levels[2]!;
    expect(evidence.textContent).toContain(resolved.lineage.method);
    expect(evidence.textContent).toContain(resolved.table.tableName);
  });
});

describe.each(LANGUAGES)('a withheld fact in %s', (language) => {
  function withheldRegistry() {
    const input = completeInput();
    input.facts[0]!.fact.provenance = 'suppressed';
    input.facts[0]!.fact.value = HIDDEN;
    return createRegistry(input);
  }

  function expectReasonNotZero(root: HTMLElement) {
    const chip = root.querySelector<HTMLElement>(
      '[data-fact-chip][data-state="withheld"]',
    );
    expect(chip).not.toBeNull();
    const reason = text(language, 'chip.withheld');
    expect(chip!.textContent).toBe(reason);
    expect(chip!.textContent).not.toMatch(ZERO);
    expect(root.textContent).not.toContain(String(HIDDEN));
    expect(root.textContent).not.toContain('٧٣٩١');
  }

  it('the value chip of the answer shows the reason, never zero', () => {
    const view = render(
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={withheldRegistry()}
        language={language}
        onOpen={() => undefined}
      />,
    );
    expectReasonNotZero(view.container);
    const button = within(view.container).getByRole('button');
    expect(button.getAttribute('aria-label')).toContain(
      text(language, 'chip.withheld'),
    );
  });

  it('the evidence and method drawer shows the same reason, never zero', () => {
    const view = render(
      <SourceChainDrawer
        factId={factId(0)}
        registry={withheldRegistry()}
        language={language}
        onClose={() => undefined}
      />,
    );
    expectReasonNotZero(view.container);
    expect(
      view.container.querySelector('[data-mark="withheld"]'),
    ).not.toBeNull();
  });
});
