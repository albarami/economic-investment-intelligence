// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { cleanup, fireEvent, render } from '@testing-library/react';
import type { PropsWithChildren } from 'react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { createRegistry } from '../../src/facts/registry';
import { FactChip } from '../../src/facts/FactChip';
import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { apiLayerCases } from '../fixtures/api-layer-cases';
import { fcPayload, fcRegistry } from '../fixtures/fc-firms';
import land from '../fixtures/land-price-layer.json';
import { operationalMeter } from '../fixtures/operational-meter';
import { routeRegistry } from '../fixtures/public-route-registry';
import type { Fact } from '../../src/facts/types';
import type { LayerPayload } from '../../src/stage/layers/payload';

const LANGUAGES = ['en', 'ar'] as const;
const THEMES = ['light', 'dark'] as const;
const ANSWER_CSS = readFileSync('src/styles/answer.css', 'utf8');
let answerStyle: HTMLStyleElement;

beforeEach(() => {
  answerStyle = document.createElement('style');
  answerStyle.textContent = ANSWER_CSS;
  document.head.append(answerStyle);
});

afterEach(() => {
  cleanup();
  answerStyle.remove();
});

function expectAlignedFigureCell(cell: Element, name: string): void {
  const style = getComputedStyle(cell);
  expect(
    style.fontVariantNumeric.includes('tabular-nums'),
    `${name}: figure-cell-missing-tabular-nums`,
  ).toBe(true);
  expect(style.textAlign, `${name}: figure-cell-missing-text-align-end`).toBe(
    'end',
  );
  const parentStyle = cell.parentElement
    ? getComputedStyle(cell.parentElement)
    : null;
  const gridEndPlacement =
    style.justifySelf === 'end' &&
    parentStyle?.display === 'grid' &&
    parentStyle.inlineSize === '100%';
  const flexEndPlacement =
    style.display === 'flex' &&
    style.inlineSize === '100%' &&
    ['flex-end', 'space-between'].includes(style.justifyContent);
  const endEdgePlacement = gridEndPlacement || flexEndPlacement;
  expect(
    endEdgePlacement,
    `${name}: figure-cell-missing-end-edge-placement`,
  ).toBe(true);
  const valueChip = cell.querySelector('[data-fact-chip="value"]');
  if (valueChip?.parentElement) {
    const valueStyle = getComputedStyle(valueChip);
    const valueOrder = Number(valueStyle.order);
    const valueIsLast = [...valueChip.parentElement.children]
      .filter((sibling) => sibling !== valueChip)
      .every((sibling) => valueOrder > Number(getComputedStyle(sibling).order));
    const valueEndPlacement =
      valueIsLast && valueStyle.justifyContent === 'flex-end';
    expect(valueEndPlacement, `${name}: figure-cell-value-not-end-item`).toBe(
      true,
    );
  }
}

function expectAlignedFigureCells(
  cells: readonly Element[],
  surface: string,
): void {
  expect(cells.length, `${surface}: no figure cells found`).toBeGreaterThan(0);
  cells.forEach((cell, index) =>
    expectAlignedFigureCell(cell, `${surface} cell ${index + 1}`),
  );
}

function Direction({
  language,
  theme,
  children,
}: PropsWithChildren<{
  language: 'en' | 'ar';
  theme: 'light' | 'dark';
}>) {
  return (
    <div
      lang={language}
      dir={language === 'ar' ? 'rtl' : 'ltr'}
      data-theme={theme}
    >
      {children}
    </div>
  );
}

describe.each(LANGUAGES)('table figure alignment in %s', (language) => {
  it.each(THEMES)('class-break figures in %s theme', (theme) => {
    const body = land as unknown as { facts: Fact[]; payload: LayerPayload };
    const view = render(
      <Direction language={language} theme={theme}>
        <PublicLayers
          payload={body.payload}
          registry={routeRegistry(body)}
          language={language}
          onOpenChain={() => undefined}
        />
      </Direction>,
    );
    expectAlignedFigureCells(
      [
        ...view.container.querySelectorAll(
          '[data-part="class-legend"] li[data-class] [data-fact-chip="compact"]',
        ),
      ],
      'class-break legend',
    );
  });

  it.each(THEMES)('firms-by-tower figures in %s theme', (theme) => {
    const view = render(
      <Direction language={language} theme={theme}>
        <PublicLayers
          payload={fcPayload()}
          registry={fcRegistry()}
          language={language}
          onOpenChain={() => undefined}
        />
      </Direction>,
    );
    expectAlignedFigureCells(
      [
        ...view.container.querySelectorAll(
          '[data-part="fc-firms-legend"] li[data-class] [data-fact-chip="compact"]',
        ),
      ],
      'firms-by-tower legend',
    );
  });

  it.each(THEMES)('FDI field figures in %s theme', (theme) => {
    const route = apiLayerCases().fdi!;
    const view = render(
      <Direction language={language} theme={theme}>
        <PublicLayers
          payload={route.body.payload}
          registry={createRegistry(route.registry)}
          language={language}
          onOpenChain={() => undefined}
        />
      </Direction>,
    );
    const cells = [
      ...view.container.querySelectorAll(
        '[data-fdi-fields="all"] [data-field]',
      ),
    ].filter((cell) => cell.querySelector('[data-fact-chip="value"]') !== null);
    expectAlignedFigureCells(cells, 'FDI field grid');
  });

  it.each(THEMES)('operational figures in %s theme', (theme) => {
    const view = render(
      <Direction language={language} theme={theme}>
        <FactChip
          variant="operational"
          language={language}
          meter={operationalMeter}
          reason={null}
        />
      </Direction>,
    );
    fireEvent.click(view.getByRole('button'));
    expectAlignedFigureCells(
      [...view.container.querySelectorAll('.operational-quantity')],
      'operational definition list',
    );
  });
});

it('plant: an unclassed figure cell fails with the exact tabular-figures reason', () => {
  const view = render(
    <button type="button" className="chip" data-testid="unclassed-figure-cell">
      <bdi className="chip-num">12</bdi>
    </button>,
  );
  expect(() =>
    expectAlignedFigureCell(
      view.getByTestId('unclassed-figure-cell'),
      'unclassed plant',
    ),
  ).toThrowError('unclassed plant: figure-cell-missing-tabular-nums');
});

it('plant: a value chip with a following sibling fails with the exact value-end reason', () => {
  const view = render(
    <span
      className="figure-cell"
      data-testid="trailing-sibling-figure-cell"
      style={{
        display: 'flex',
        inlineSize: '100%',
        justifyContent: 'flex-end',
      }}
    >
      <span
        className="chip"
        data-fact-chip="value"
        style={{ order: 0, justifyContent: 'flex-end' }}
      >
        <bdi className="chip-num">12</bdi>
      </span>
      <span data-label="announced">Announced estimates</span>
    </span>,
  );
  expect(() =>
    expectAlignedFigureCell(
      view.getByTestId('trailing-sibling-figure-cell'),
      'trailing-sibling plant',
    ),
  ).toThrowError('trailing-sibling plant: figure-cell-value-not-end-item');
});

it('plant: a start-packed figure cell fails with the exact end-edge reason', () => {
  const view = render(
    <button
      type="button"
      className="chip figure-cell"
      data-testid="start-packed-figure-cell"
      style={{
        inlineSize: '100%',
        justifyContent: 'flex-start',
        justifySelf: 'start',
      }}
    >
      <bdi className="chip-num">12</bdi>
    </button>,
  );
  expect(() =>
    expectAlignedFigureCell(
      view.getByTestId('start-packed-figure-cell'),
      'start-packed plant',
    ),
  ).toThrowError('start-packed plant: figure-cell-missing-end-edge-placement');
});
