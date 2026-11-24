// @vitest-environment jsdom
/** S3-T14 levels. EII_WITHHELD_PLANT=zero or empty corrupts the rendered fixture. */
import { readFileSync } from 'node:fs';
import { cleanup, fireEvent, render, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import { fragmentField } from '../../src/brief/catalogue';
import { PublicContextCard } from '../../src/cards/PublicContextCard';
import { createRegistry } from '../../src/facts/registry';
import { formatFactValue } from '../../src/facts/formatters';
import { exposedCounts } from '../fixtures/audience-origin';
import {
  contextInput,
  contextPayloads,
  contextRegistry,
} from '../fixtures/public-context';

afterEach(cleanup);

const labels = {
  en: ['Answer', 'Comparison', 'Evidence and method'],
  ar: ['الإجابة', 'المقارنة', 'الأدلة والمنهج'],
} as const;
const comparison = {
  night_lights: {
    en: 'No benchmark is available for this figure in this release.',
    ar: 'لا يتوفر معيار مرجعي لهذه القيمة في هذا الإصدار.',
  },
  venue_busyness: {
    en: 'This relative index is not a level to compare between venues.',
    ar: 'هذا المؤشر النسبي ليس مستوى للمقارنة بين الأماكن.',
  },
  population_age_sex: {
    en: 'This figure is display only and is not used for comparison.',
    ar: 'هذه القيمة للعرض فقط ولا تستخدم للمقارنة.',
  },
};

function toggle(root: HTMLElement, label: string) {
  const control = within(root).getByRole('button', { name: label });
  control.focus();
  expect(document.activeElement).toBe(control);
  fireEvent.click(control);
  const region = document.getElementById(
    control.getAttribute('aria-controls') ?? '',
  );
  expect(region).not.toBeNull();
  expect(control.getAttribute('aria-expanded')).toBe('true');
  return region!;
}

function noLooseNumerals(root: HTMLElement) {
  const clone = root.cloneNode(true) as HTMLElement;
  clone.querySelectorAll('[data-fact-chip]').forEach((chip) => chip.remove());
  expect(clone.textContent).not.toMatch(/\p{N}/u);
}

for (const language of ['en', 'ar'] as const) {
  for (const payload of contextPayloads) {
    if (payload.state !== 'ready') throw new Error('ready fixture required');

    it(`L1 L6 ${payload.family} has ordered named level controls in ${language}`, () => {
      const view = render(
        <PublicContextCard
          payload={payload}
          registry={contextRegistry()}
          language={language}
          onOpen={() => undefined}
        />,
      );
      const controls = view.container.querySelectorAll(
        '[data-context-level] > button',
      );
      expect([...controls].map((node) => node.textContent)).toEqual(
        labels[language],
      );
      const article = view.container.querySelector('article')!;
      expect(article.lang).toBe(language);
      expect(article.dir).toBe(language === 'ar' ? 'rtl' : 'ltr');
      const answer = within(article).getByRole('button', {
        name: labels[language][0],
      });
      expect(answer.getAttribute('aria-expanded')).toBe('true');
      fireEvent.click(answer);
      expect(answer.getAttribute('aria-expanded')).toBe('false');
      const reopened = toggle(article, labels[language][0]);
      expect(
        reopened.querySelector('[data-fact-id]')?.getAttribute('data-fact-id'),
      ).toBe(payload.factId);
      for (const label of labels[language].slice(1)) toggle(article, label);
    });

    it(`L2 ${payload.family} comparison is a closed number-free sentence in ${language}`, () => {
      const view = render(
        <PublicContextCard
          payload={payload}
          registry={contextRegistry()}
          language={language}
          onOpen={() => undefined}
        />,
      );
      const sentence = comparison[payload.family][language];
      expect(
        fragmentField(
          `context_compare_${payload.family}`,
          language === 'ar' ? 'template_ar' : 'template_en',
        ),
      ).toBe(sentence);
      const region = toggle(view.container, labels[language][1]);
      expect(region.textContent).toBe(sentence);
      expect(region.querySelector('[data-fact-chip]')).toBeNull();
      expect(region.textContent).not.toMatch(/\p{N}/u);
    });

    it(`L3 ${payload.family} evidence follows the same fact and dated sources in ${language}`, () => {
      const input = contextInput();
      // Deliberately use numerals in every citation field, including method.
      input.sources[0]!.publisher = 'Sample Publisher 2';
      input.sources[0]!.datasetOrPage = 'Sample dataset 3';
      input.sources[0]!.licenceOrTerms = 'Sample terms 4';
      input.lineages.forEach((lineage) => {
        lineage.method = 'sample_method_v5';
      });
      const registry = createRegistry(input);
      const onOpen = vi.fn();
      const view = render(
        <PublicContextCard
          payload={payload}
          registry={registry}
          language={language}
          onOpen={onOpen}
        />,
      );
      const region = toggle(view.container, labels[language][2]);
      expect(region.getAttribute('data-fact-id')).toBe(payload.factId);
      const resolved = registry.resolve(payload.factId);
      expect(resolved.status).toBe('ready');
      if (resolved.status !== 'ready')
        throw new Error('complete fixture required');
      for (const field of [
        resolved.lineage.method,
        resolved.lineage.methodVersion,
        resolved.table.tableName,
      ]) {
        expect(region.textContent).toContain(field);
      }
      for (const source of resolved.sources) {
        for (const field of [
          source.publisher,
          source.datasetOrPage,
          source.licenceOrTerms,
          source.sha256,
        ]) {
          expect(region.textContent).toContain(field);
        }
        const date = formatFactValue(
          source.retrievalDate,
          'calendar_date',
          language,
          'reference',
        );
        expect(date.ok).toBe(true);
        if (!date.ok) throw new Error('valid fixture date required');
        expect(
          region.querySelector('[data-kind="calendar_date"]')?.textContent,
        ).toBe(date.text);
      }
      fireEvent.click(
        view.container.querySelector('[data-fact-chip="value"]')!,
      );
      expect(onOpen).toHaveBeenCalledWith(payload.factId);
      noLooseNumerals(view.container);
    });

    it(`L4 L5 ${payload.family} withheld reason never becomes zero in ${language}`, () => {
      const input = contextInput();
      const binding = input.facts.find(
        (item) => item.fact.fact_id === payload.factId,
      )!;
      binding.fact.provenance = 'suppressed';
      binding.fact.value = 7391;
      const registry = createRegistry(input);
      const view = render(
        <PublicContextCard
          payload={payload}
          registry={registry}
          language={language}
          onOpen={() => undefined}
        />,
      );
      const withheld = view.container.querySelector('[data-state="withheld"]');
      expect(withheld).not.toBeNull();
      expect(
        view.container.querySelector(
          '[data-mark="withheld"][data-shape="lock"]',
        ),
      ).not.toBeNull();
      expect(
        view.container.querySelector('[data-pattern="hatch-lock"]'),
      ).not.toBeNull();
      expect(view.container.textContent).toContain(
        language === 'ar' ? 'قواعد الإفصاح' : 'disclosure rules',
      );
      if (process.env.EII_WITHHELD_PLANT === 'zero') {
        // Same DOM-corruption pattern as S3-T18, confined to this test fixture.
        withheld!.replaceChildren(
          document.createTextNode(language === 'ar' ? '٠' : '0'),
        );
      } else if (process.env.EII_WITHHELD_PLANT === 'empty') {
        withheld!.replaceChildren();
      }
      expect(withheld!.querySelector('.chip-withheld')).not.toBeNull();
      expect(exposedCounts(view.container, 7391)).toEqual([]);
      toggle(view.container, labels[language][1]);
      toggle(view.container, labels[language][2]);
      expect(exposedCounts(view.container, 7391)).toEqual([]);
      noLooseNumerals(view.container);
    });
  }

  for (const family of [
    'night_lights',
    'venue_busyness',
    'population_age_sex',
  ] as const) {
    for (const reason of family === 'venue_busyness'
      ? (['missing_input', 'no_forecast'] as const)
      : (['missing_input'] as const)) {
      it(`L4 ${family} NO_DATA ${reason} keeps template reason across levels in ${language}`, () => {
        const view = render(
          <PublicContextCard
            payload={{ family, state: 'no_data', reason }}
            registry={contextRegistry()}
            language={language}
            onOpen={() => undefined}
          />,
        );
        const expected = fragmentField(
          reason === 'no_forecast' ? 'context_no_forecast' : 'context_no_data',
          language === 'ar' ? 'template_ar' : 'template_en',
        )!;
        expect(view.container.textContent).toContain(expected);
        expect(
          view.container.querySelector('[data-state="NO_DATA"]'),
        ).not.toBeNull();
        toggle(view.container, labels[language][1]);
        const evidence = toggle(view.container, labels[language][2]);
        expect(evidence.textContent).toContain(expected);
        expect(
          view.container.querySelector('[data-fact-chip="value"]'),
        ).toBeNull();
        expect(view.container.querySelector('.chip-num')).toBeNull();
        noLooseNumerals(view.container);
      });
    }
  }
}

it('L6 levels preserve the existing logical layout and Arabic leading tokens', () => {
  const css = readFileSync('src/cards/public-context.css', 'utf8');
  expect(css).toContain('font: var(--eii-type-body)');
  expect(css).toContain('text-align: start');
  expect(css).not.toMatch(
    /(?:margin|padding|border)-(?:left|right)|text-align:\s*(?:left|right)/,
  );
});
