// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => {
  cleanup();
});

import { catalogue, type AnswerDraft } from '../../src/brief/catalogue';
import { FactChip } from '../../src/facts/FactChip';
import { text as catalogueText } from '../../src/i18n';
import type { MissingLink } from '../../src/facts/types';
import {
  EvidenceMark,
  STATUS_SHAPE,
  WITHHELD_SHAPE,
  WithheldMark,
  markIdentified,
  shapesCollide,
} from '../../src/facts/ProvenanceMark';
import { SourceChainDrawer } from '../../src/facts/SourceChainDrawer';
import { AnswerShell } from '../../src/shell/AnswerShell';
import { reviewMarks } from '../../src/i18n';
import {
  calendarFact,
  chainCuts,
  completeInput,
  completeRegistry,
  factId,
  makeBinding,
  makeFact,
  makeLineage,
  makeSource,
  registryFrom,
} from '../fixtures/facts';

const DIGIT = /\p{Nd}/u;
const CLASS_WORD =
  /Public|Synthetic|Simulated|Suppressed|عام|العام|عامة|العامة|علني|العلني|علنية|العلنية|اصطناعي|الاصطناعي|اصطناعية|الاصطناعية|محاكاة|المحاكاة|بالمحاكاة|محجوب|المحجوب|محجوبة|المحجوبة/;

function buttonOf(view: { container: HTMLElement }): HTMLElement {
  return within(view.container).getByRole('button');
}

function digitsOutsideChips(root: ParentNode): string[] {
  const found: string[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    const value = node.textContent ?? '';
    if (DIGIT.test(value)) {
      const parent = node.parentElement;
      if (!parent?.closest('[data-fact-chip]')) found.push(value);
    }
    node = walker.nextNode();
  }
  return found;
}

describe('incomplete lineage', () => {
  it('renders no digit when the only source row is missing', () => {
    const input = completeInput();
    const registry = registryFrom({ ...input, sources: [] });
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
    expect(DIGIT.test(view.container.textContent ?? '')).toBe(false);
  });

  it.each(chainCuts())('renders no digit when $name is missing', (cut) => {
    const view = render(
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={registryFrom(cut.input)}
        language="en"
        onOpen={() => undefined}
      />,
    );
    expect(DIGIT.test(view.container.textContent ?? '')).toBe(false);
  });
});

describe('chip family', () => {
  it('renders a real zero and refuses a missing fact without a zero', () => {
    const zero = registryFrom({
      ...completeInput(),
      facts: [makeBinding({ fact: makeFact({ value: 0 }) })],
    });
    const shown = render(
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={zero}
        language="en"
        onOpen={() => undefined}
      />,
    );
    expect(buttonOf(shown).textContent).toContain('0');
    const empty = render(
      <FactChip
        variant="value"
        size="standard"
        factId={factId(3)}
        registry={zero}
        language="en"
        onOpen={() => undefined}
      />,
    );
    expect(buttonOf(empty).textContent).toContain('No data');
    expect(DIGIT.test(buttonOf(empty).textContent ?? '')).toBe(false);
  });

  it('keeps the same digits in both languages for a count and a date', () => {
    const registry = completeRegistry();
    for (const language of ['en', 'ar'] as const) {
      const view = render(
        <FactChip
          variant="value"
          size="hero"
          factId={factId(0)}
          registry={registry}
          language={language}
          onOpen={() => undefined}
        />,
      );
      expect(buttonOf(view).textContent).toContain('48');
    }
    const dated = calendarFact('calendar_date', '2024-03-14');
    const english = render(
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={dated}
        language="en"
        onOpen={() => undefined}
      />,
    );
    const arabic = render(
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={dated}
        language="ar"
        onOpen={() => undefined}
      />,
    );
    expect(buttonOf(english).textContent).toMatch(/March/);
    expect(buttonOf(arabic).textContent).toMatch(/مارس/);
    expect(buttonOf(english).textContent).toContain('2024');
    expect(buttonOf(arabic).textContent).toContain('2024');
  });

  it('opens from a click or Enter on each value size and on compact', () => {
    const registry = completeRegistry();
    const sizes = ['hero', 'large', 'standard', 'inline'] as const;
    for (const size of sizes) {
      const onOpen = vi.fn();
      const view = render(
        <FactChip
          variant="value"
          size={size}
          factId={factId(0)}
          registry={registry}
          language="en"
          onOpen={onOpen}
        />,
      );
      const button = buttonOf(view);
      fireEvent.click(button);
      fireEvent.keyDown(button, { key: 'Enter' });
      expect(onOpen).toHaveBeenCalledTimes(2);
      expect(onOpen).toHaveBeenCalledWith(factId(0));
      expect(CLASS_WORD.test(button.getAttribute('aria-label') ?? '')).toBe(
        false,
      );
      view.unmount();
    }
    const onOpen = vi.fn();
    const compact = render(
      <FactChip
        variant="compact"
        factId={factId(0)}
        registry={registry}
        language="en"
        onOpen={onOpen}
      />,
    );
    fireEvent.keyDown(buttonOf(compact), { key: 'Enter' });
    expect(onOpen).toHaveBeenCalledWith(factId(0));
  });

  it('shows a range under an estimated count and an error when a companion is missing', () => {
    const low = factId(1);
    const high = factId(2);
    const ready = registryFrom({
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({ value: 48 }),
          presentation: 'estimated_count',
          rangeLowId: low,
          rangeHighId: high,
        }),
        makeBinding({ fact: makeFact({ fact_id: low, value: 40 }) }),
        makeBinding({ fact: makeFact({ fact_id: high, value: 50 }) }),
      ],
    });
    const view = render(
      <FactChip
        variant="value"
        size="large"
        factId={factId(0)}
        registry={ready}
        language="en"
        onOpen={() => undefined}
      />,
    );
    expect(buttonOf(view).textContent).toContain('40\u201350');
    const broken = registryFrom({
      ...completeInput(),
      facts: [
        makeBinding({
          presentation: 'estimated_count',
          rangeLowId: low,
          rangeHighId: high,
        }),
      ],
    });
    const refused = render(
      <FactChip
        variant="compact"
        factId={factId(0)}
        registry={broken}
        language="en"
        onOpen={() => undefined}
      />,
    );
    expect(DIGIT.test(refused.container.textContent ?? '')).toBe(false);
  });

  it('renders no digit when the unit is unknown', () => {
    const registry = registryFrom({
      ...completeInput(),
      facts: [makeBinding({ fact: makeFact({ unit: 'not-a-unit' }) })],
    });
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
    expect(view.container.querySelector('[data-state="error"]')).toBeTruthy();
    expect(DIGIT.test(view.container.textContent ?? '')).toBe(false);
  });

  it('leaves a withheld value empty and still opens the chain', () => {
    const registry = registryFrom({
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({ provenance: 'suppressed', value: 48 }),
        }),
      ],
    });
    const onOpen = vi.fn();
    const view = render(
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={registry}
        language="en"
        onOpen={onOpen}
      />,
    );
    const button = buttonOf(view);
    expect(DIGIT.test(button.textContent ?? '')).toBe(false);
    expect(button.textContent ?? '').not.toMatch(
      /privacy|protected|suppressed/i,
    );
    fireEvent.click(button);
    expect(onOpen).toHaveBeenCalledWith(factId(0));
  });

  it('tags an input chip and renders a reference without a class mark', () => {
    const input = render(
      <FactChip
        variant="input"
        language="en"
        value=""
        onChange={() => undefined}
        presets={[]}
      />,
    );
    expect(within(input.container).getByLabelText('Your inputs')).toBeTruthy();
    expect(input.container.querySelector('[data-fact-id]')).toBeNull();
    const reference = render(
      <FactChip
        variant="reference"
        language="en"
        kind="published_text"
        value="v1"
        recordId="method-row"
      />,
    );
    expect(reference.container.textContent).toContain('v1');
    expect(reference.container.querySelector('[data-mark]')).toBeNull();
  });
});

describe('source chain', () => {
  it.each(['en', 'ar'] as const)(
    'keeps numerals in returned source metadata inside reference chips (%s)',
    (language) => {
      const input = completeInput();
      input.lineages[0]!.method = 'invented.method2026';
      input.sources[0]!.publisher = 'INVENTED-publisher2026';
      input.sources[0]!.datasetOrPage = 'INVENTED-dataset2026';
      input.sources[0]!.licenceOrTerms = 'INVENTED-terms2026';
      const view = render(
        <SourceChainDrawer
          factId={factId(0)}
          registry={registryFrom(input)}
          language={language}
          onClose={() => undefined}
        />,
      );
      expect(view.container.textContent).toContain('INVENTED-dataset2026');
      expect(digitsOutsideChips(view.container)).toEqual([]);
    },
  );
  it('titles the drawer Source chain in both languages', () => {
    for (const language of ['en', 'ar'] as const) {
      const view = render(
        <SourceChainDrawer
          factId={factId(0)}
          registry={completeRegistry()}
          language={language}
          onClose={() => undefined}
        />,
      );
      const title = within(view.container).getByRole('heading', { level: 2 });
      expect(title.textContent).toBe('Source chain');
      expect(title.getAttribute('lang')).toBe('en');
      expect(title.getAttribute('dir')).toBe('ltr');
      view.unmount();
    }
  });

  it('lists the chain and the receipt only when an address is injected', () => {
    const registry = completeRegistry();
    const open = render(
      <SourceChainDrawer
        factId={factId(0)}
        registry={registry}
        language="en"
        receiptHref="/privacy-receipt"
        onClose={() => undefined}
      />,
    );
    const parts = [...open.container.querySelectorAll('[data-part]')].map(
      (node) => node.getAttribute('data-part'),
    );
    expect(parts).toEqual([
      'label',
      'chip',
      'status',
      'why',
      'fact',
      'table',
      'method',
      'source',
      'coverage',
      'caveat',
      'reliability',
      'receipt',
    ]);
    expect(within(open.container).getByRole('link').getAttribute('href')).toBe(
      '/privacy-receipt',
    );
    expect(digitsOutsideChips(open.container)).toEqual([]);
    open.unmount();
    const closed = render(
      <SourceChainDrawer
        factId={factId(0)}
        registry={registry}
        language="en"
        onClose={() => undefined}
      />,
    );
    expect(closed.container.querySelector('[data-part="receipt"]')).toBeNull();
  });

  it('names a missing link and shows no digit', () => {
    const registry = registryFrom({ ...completeInput(), sources: [] });
    const view = render(
      <SourceChainDrawer
        factId={factId(0)}
        registry={registry}
        language="en"
        onClose={() => undefined}
      />,
    );
    expect(
      view.container.querySelector('[data-missing="source"]'),
    ).toBeTruthy();
    expect(DIGIT.test(view.container.textContent ?? '')).toBe(false);
  });

  it('keeps the withheld shape apart from every status shape', () => {
    expect(shapesCollide(STATUS_SHAPE)).toBe(false);
    expect(shapesCollide({ ...STATUS_SHAPE, withheld: WITHHELD_SHAPE })).toBe(
      false,
    );
    expect(shapesCollide({ ...STATUS_SHAPE, withheld: 'disc' })).toBe(true);
  });
});

describe('shell', () => {
  function draft(): AnswerDraft {
    return {
      catalogueVersion: catalogue.version,
      accountingPassed: true,
      subject: 'area' as const,
      componentKey: 'foundation_note',
      props: [] as string[],
      directive: null,
      slots: [
        {
          factId: factId(0),
          provenance: 'public' as const,
          metric: 'people',
        },
      ],
    };
  }

  it('returns focus to the chip and keeps review marks off the page', () => {
    const registry = completeRegistry();
    const row = draft();
    const view = render(
      <AnswerShell
        language="ar"
        theme="dark"
        extractUrl={null}
        registry={registry}
        draft={row}
      />,
    );
    expect(view.container.textContent ?? '').not.toContain(
      'pending-native-review',
    );
    expect(
      reviewMarks().every((mark) => mark === 'pending-native-review'),
    ).toBe(true);
    const chip = view.container.querySelector('.brief [data-fact-chip]');
    if (!(chip instanceof HTMLElement)) throw new Error('missing chip');
    chip.focus();
    fireEvent.click(chip);
    const close = within(view.container).getByRole('button', { name: 'إغلاق' });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(document.activeElement).toBe(chip);
    expect(view.container.querySelector('.brief')?.hasAttribute('inert')).toBe(
      false,
    );
  });

  it('does not start a map when the extract is absent', () => {
    const starter = vi.fn();
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const view = render(
      <AnswerShell
        language="en"
        theme="light"
        extractUrl={null}
        mapStarter={starter}
      />,
    );
    expect(
      view.container.querySelector('[data-state="asset-absent"]'),
    ).toBeTruthy();
    expect(starter).not.toHaveBeenCalled();
    expect(
      fetchSpy.mock.calls.every(
        ([path, options]) =>
          path === '/api/map-modes' && options?.cache === 'no-store',
      ),
    ).toBe(true);
    fetchSpy.mockRestore();
  });

  it('withdraws an ungated or wrongly slotted answer', () => {
    const registry = completeRegistry();
    const base = draft();
    const cases = [
      { ...base, accountingPassed: false },
      { ...base, catalogueVersion: 'abc' },
      { ...base, componentKey: 'unknown_card' },
      { ...base, props: ['extra'] },
      {
        ...base,
        directive: { name: 'missing', fields: {} },
      },
      {
        ...base,
        subject: 'place_public' as const,
        slots: [
          {
            factId: factId(0),
            provenance: 'synthetic' as const,
            metric: 'people',
          },
        ],
      },
      {
        ...base,
        subject: 'fdi_project' as const,
        slots: [
          {
            factId: factId(0),
            provenance: 'simulated' as const,
            metric: 'people',
          },
        ],
      },
      {
        ...base,
        subject: 'register_company' as const,
        slots: [
          {
            factId: factId(0),
            provenance: 'synthetic' as const,
            metric: 'wage',
          },
        ],
      },
    ];
    for (const row of cases) {
      const view = render(
        <AnswerShell
          language="en"
          theme="dark"
          extractUrl={null}
          registry={registry}
          draft={row}
        />,
      );
      expect(view.container.querySelector('[data-fact-chip]')).toBeNull();
      expect(
        view.container.querySelector('[data-state="default"]'),
      ).toBeTruthy();
      view.unmount();
    }
    const counted = registryFrom({
      ...completeInput(),
      facts: [
        makeBinding({
          metricKey: 'employee_count',
          fact: makeFact({
            provenance: 'synthetic',
            input_classes: ['synthetic'],
          }),
        }),
      ],
      lineages: [makeLineage({ inputClasses: ['synthetic'] })],
      sources: [
        makeSource({ kind: 'synthetic_feed', inputClass: 'synthetic' }),
      ],
    });
    const allowed = render(
      <AnswerShell
        language="en"
        theme="dark"
        extractUrl={null}
        registry={counted}
        draft={{
          ...base,
          subject: 'register_company',
          slots: [
            {
              factId: factId(0),
              provenance: 'synthetic',
              metric: 'employee_count',
            },
          ],
        }}
      />,
    );
    expect(allowed.container.querySelector('[data-fact-chip]')).toBeTruthy();
  });
});

function DrawerHost({
  registry,
  id,
}: {
  registry: ReturnType<typeof completeRegistry>;
  id: string;
}) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div>
      <FactChip
        variant="value"
        size="standard"
        factId={id}
        registry={registry}
        language="en"
        onOpen={setOpen}
      />
      {open ? (
        <SourceChainDrawer
          factId={open}
          registry={registry}
          language="en"
          onClose={() => setOpen(null)}
        />
      ) : null}
    </div>
  );
}

describe('F10 chip and chain plants', () => {
  it('catches a raw numeral outside a chip', () => {
    const view = render(
      <div>
        <p>4</p>
        <span data-fact-chip="value">4</span>
      </div>,
    );
    expect(digitsOutsideChips(view.container)).toEqual(['4']);
  });

  it('gives the withheld mark and every status mark a word and a shape', () => {
    const withheld = render(<WithheldMark language="en" />);
    const lock = withheld.container.querySelector('[data-mark="withheld"]');
    expect(lock?.getAttribute('data-shape')).toBe(WITHHELD_SHAPE);
    expect(lock?.querySelector('.mark-word')?.textContent).toBe('Suppressed');
    expect(lock?.querySelector('.mark-glyph')).toBeTruthy();
    withheld.unmount();
    const statuses = ['observed', 'inferred', 'still_to_test'] as const;
    for (const status of statuses) {
      const view = render(<EvidenceMark status={status} language="en" />);
      const mark = view.container.querySelector('[data-mark="status"]');
      expect(mark?.getAttribute('data-shape')).toBe(STATUS_SHAPE[status]);
      expect(mark?.querySelector('.mark-word')?.textContent).not.toBe('');
      expect(mark?.querySelector('.mark-glyph')).toBeTruthy();
      view.unmount();
    }
  });

  it('opens the same fact from either range bound', () => {
    const low = factId(1);
    const high = factId(2);
    const registry = registryFrom({
      ...completeInput(),
      facts: [
        makeBinding({
          fact: makeFact({ value: 48 }),
          presentation: 'estimated_count',
          rangeLowId: low,
          rangeHighId: high,
        }),
        makeBinding({ fact: makeFact({ fact_id: low, value: 40 }) }),
        makeBinding({ fact: makeFact({ fact_id: high, value: 50 }) }),
      ],
    });
    const onOpen = vi.fn();
    const view = render(
      <FactChip
        variant="value"
        size="large"
        factId={factId(0)}
        registry={registry}
        language="en"
        onOpen={onOpen}
      />,
    );
    const range = view.container.querySelector('.chip-range');
    expect(range).toBeTruthy();
    if (range) fireEvent.click(range);
    fireEvent.keyDown(buttonOf(view), { key: 'Enter' });
    expect(onOpen).toHaveBeenCalledTimes(2);
    expect(onOpen).toHaveBeenNthCalledWith(1, factId(0));
    expect(onOpen).toHaveBeenNthCalledWith(2, factId(0));
  });

  it('opens the drawer from a refused chip and from an error chip', () => {
    const refused = registryFrom({
      ...completeInput(),
      facts: [makeBinding({ fact: makeFact({ lineage_ref: 'missing' }) })],
    });
    const error = registryFrom({
      ...completeInput(),
      facts: [makeBinding({ fact: makeFact({ unit: 'not-a-unit' }) })],
    });
    for (const registry of [refused, error]) {
      const view = render(<DrawerHost registry={registry} id={factId(0)} />);
      fireEvent.click(buttonOf(view));
      expect(view.container.querySelector('[role="dialog"]')).toBeTruthy();
      view.unmount();
    }
  });

  it('formats month, year and published text in both languages', () => {
    const cases = [
      calendarFact('calendar_month', '2024-03'),
      calendarFact('calendar_year', '2024'),
      calendarFact('published_text', 'code-1'),
    ];
    for (const registry of cases) {
      for (const language of ['en', 'ar'] as const) {
        const view = render(
          <FactChip
            variant="value"
            size="standard"
            factId={factId(0)}
            registry={registry}
            language={language}
            onOpen={() => undefined}
          />,
        );
        expect(
          view.container.querySelector('[data-state="ready"]'),
        ).toBeTruthy();
        expect(buttonOf(view).textContent).not.toBe('');
        view.unmount();
      }
    }
  });
});

const LINK_INPUT: Record<MissingLink, () => ReturnType<typeof completeInput>> =
  {
    fact: () => ({
      ...completeInput(),
      facts: [makeBinding({ fact: makeFact({ release_id: '' }) })],
    }),
    release: () => ({ ...completeInput(), releases: [] }),
    table: () => ({ ...completeInput(), tables: [] }),
    lineage: () => ({ ...completeInput(), lineages: [] }),
    method: () => ({
      ...completeInput(),
      lineages: [makeLineage({ method: '' })],
    }),
    method_version: () => ({
      ...completeInput(),
      lineages: [makeLineage({ methodVersion: '' })],
    }),
    source: () => ({ ...completeInput(), sources: [] }),
    publisher: () => ({
      ...completeInput(),
      sources: [makeSource({ publisher: '' })],
    }),
    dataset_or_page: () => ({
      ...completeInput(),
      sources: [makeSource({ datasetOrPage: '' })],
    }),
    licence_or_terms: () => ({
      ...completeInput(),
      sources: [makeSource({ licenceOrTerms: '' })],
    }),
    retrieval_date: () => ({
      ...completeInput(),
      sources: [makeSource({ retrievalDate: '' })],
    }),
    hash: () => ({
      ...completeInput(),
      sources: [makeSource({ sha256: '' })],
    }),
    release_identity: () => ({
      ...completeInput(),
      releases: [
        {
          releaseId:
            'b1c2d3e4f5a6b7c8b1c2d3e4f5a6b7c8b1c2d3e4f5a6b7c8b1c2d3e4f5a6b7c8',
        },
      ],
    }),
    input_class_source: () => ({
      ...completeInput(),
      lineages: [makeLineage({ inputClasses: ['public', 'synthetic'] })],
    }),
    source_kind: () => ({
      ...completeInput(),
      sources: [makeSource({ kind: 'synthetic_feed', inputClass: 'public' })],
    }),
    provenance_class: () => ({
      ...completeInput(),
      facts: [makeBinding({ fact: makeFact({ provenance: 'simulated' }) })],
    }),
    companion: () => ({
      ...completeInput(),
      facts: [makeBinding({ presentation: 'forecast' })],
    }),
  };

describe('N6 missing links, colour and range bounds', () => {
  it('renders every missing-link sentence in both languages with no digit', () => {
    const links = Object.keys(LINK_INPUT) as MissingLink[];
    for (const link of links) {
      const registry = registryFrom(LINK_INPUT[link]());
      for (const language of ['en', 'ar'] as const) {
        const view = render(
          <SourceChainDrawer
            factId={factId(0)}
            registry={registry}
            language={language}
            onClose={() => undefined}
          />,
        );
        const sentence = catalogueText(language, `drawer.link.${link}`);
        expect(view.container.textContent).toContain(sentence);
        expect(DIGIT.test(view.container.textContent ?? '')).toBe(false);
        view.unmount();
      }
    }
  });

  it('rejects a colour-only mark and keeps a shaped word', () => {
    const view = render(
      <div>
        <WithheldMark language="en" />
        <span data-mark="withheld" style={{ color: 'red' }} />
      </div>,
    );
    const marks = [...view.container.querySelectorAll('[data-mark]')];
    const real = marks[0];
    const planted = marks[1];
    expect(
      markIdentified(
        real?.getAttribute('data-shape') ?? null,
        real?.querySelector('.mark-word')?.textContent ?? '',
      ),
    ).toBe(true);
    expect(
      markIdentified(
        planted?.getAttribute('data-shape') ?? null,
        planted?.querySelector('.mark-word')?.textContent ?? '',
      ),
    ).toBe(false);
  });
});
