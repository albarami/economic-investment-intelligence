// @vitest-environment jsdom
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { overlayFor } from '../../src/stage/layers/overlay';
import { Stage } from '../../src/stage/Stage';
import type { MapStarter } from '../../src/stage/Stage';
import { factId } from '../fixtures/facts';
import { layerRegistry, sceneRegistry } from '../fixtures/layer-registry';
import {
  CHAIN_ID,
  NIGHT_PARENT,
  SAMPLE_CREDITS,
  basePayload,
  category,
  plain,
} from '../fixtures/layers';
import { numeralsOutsideChips } from '../fixtures/numerals';
import type { LayerPayload } from '../../src/stage/layers/payload';
import '../../src/styles/answer.css';

const ANSWER_CSS = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), '../../src/styles/answer.css'),
  'utf8',
);

function applyAnswerCss(): void {
  const style = document.createElement('style');
  style.dataset.answerCss = 'applied';
  style.textContent = ANSWER_CSS;
  document.head.appendChild(style);
}

afterEach(() => {
  cleanup();
});

function nightScene(): LayerPayload {
  return basePayload({
    layers: [
      {
        key: 'night_lights',
        visible: true,
        source_chain_fact_id: CHAIN_ID,
        source_id: 'src_night',
        features: [
          {
            feature_id: 'feat_night',
            metric_key: 'radiance_class',
            provenance: 'public',
            subject: 'statistic',
            geometry_kind: 'hex',
            cell: NIGHT_PARENT,
            resolution: 8,
            fact_id: CHAIN_ID,
            class_id: 'band_high',
          },
        ],
      },
    ],
    sources: [
      {
        sourceId: 'src_night',
        attribution: [plain('Sample night acknowledgement')],
        retrievalDate: '2024-03-14',
        publisher: [
          plain('Sample Night Press'),
          {
            kind: 'reference',
            referenceKind: 'published_text',
            value: '7',
            recordId: 'night-press',
          },
        ],
        datasetOrPage: 'Sample night page',
        licenceOrTerms: 'Terms recorded for this sample',
      },
    ],
    night: {
      month: '2024-03',
      direction: 'higher',
      class_id: 'band_high',
      unit: 'radiance_nw_cm2_sr',
      caveat_key: 'night_lights_not_activity',
    },
  });
}

describe('fix pass 3 screen', () => {
  it('F8 renders the night unit, month, direction, class and acknowledgement', () => {
    const view = render(
      <PublicLayers
        payload={nightScene()}
        language="en"
        registry={layerRegistry([
          { id: CHAIN_ID, metric: 'radiance_class', table: 'pub_night_lights' },
        ])}
        onOpenChain={() => undefined}
      />,
    );
    const legend = view.container.querySelector('[data-part="night-legend"]');
    expect(
      legend?.querySelector('[data-legend="unit"]')?.textContent,
    ).toContain('nanowatts per square centimetre per steradian');
    expect(
      legend?.querySelector('[data-fact-chip="reference"]')?.textContent,
    ).toContain('March');
    expect(
      legend?.querySelector('[data-legend="direction"]')?.textContent,
    ).toBe('higher');
    expect(legend?.querySelector('[data-legend="class"]')?.textContent).toBe(
      'highest',
    );
    expect(legend?.textContent).toContain('Sample night acknowledgement');
  });

  it('F10 renders the source publisher beside its attribution', () => {
    const view = render(
      <PublicLayers
        payload={nightScene()}
        language="en"
        registry={layerRegistry([
          { id: CHAIN_ID, metric: 'radiance_class', table: 'pub_night_lights' },
        ])}
        onOpenChain={() => undefined}
      />,
    );
    const credit = view.container.querySelector('[data-credit="night_lights"]');
    expect(credit?.textContent).toContain('Sample night acknowledgement');
    const publisher = credit?.querySelector(
      '[data-credit-field="source-publisher"]',
    );
    expect(publisher?.textContent).toContain('Sample Night Press');
    expect(
      publisher?.querySelector('[data-fact-chip="reference"]')?.textContent,
    ).toContain('7');
    expect(numeralsOutsideChips(credit ?? view.container)).toEqual([]);
  });

  it('F3 opens the chain of an accepted layer before any feature is selected', () => {
    const open = { id: '' };
    const payload = basePayload();
    const view = render(
      <PublicLayers
        payload={payload}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={(id) => {
          open.id = id;
        }}
      />,
    );
    expect(
      view.container.querySelector('[data-part="feature-panel"]'),
    ).toBeNull();
    fireEvent.click(
      view.container.querySelector(
        '[data-action="source-chain"][data-scope="layer"]',
      )!,
    );
    expect(open.id).toBe(CHAIN_ID);
  });

  it('F3 selects a drawn feature from its overlay row and shows the apportionment', () => {
    const payload = basePayload({
      layers: [
        {
          key: 'property_prices',
          visible: true,
          source_chain_fact_id: CHAIN_ID,
          source_id: 'src_places',
          features: [
            {
              feature_id: 'feat_sale',
              metric_key: 'district_sale',
              provenance: 'public',
              subject: 'statistic',
              geometry_kind: 'fill',
              fact_id: CHAIN_ID,
              apportioned_from: 'sample_parent',
              evidence_status: 'inferred',
              method_id: 'method_apportion_v1',
              geography_code: 'gx_sample_aleph',
              ring: [
                [51.5, 25.3],
                [51.6, 25.3],
                [51.6, 25.4],
                [51.5, 25.3],
              ],
            },
          ],
        },
      ],
    });
    const registry = layerRegistry([
      { id: CHAIN_ID, metric: 'district_sale', table: 'pub_property_sale' },
    ]);
    const view = render(
      <PublicLayers
        payload={payload}
        language="en"
        registry={registry}
        onOpenChain={() => undefined}
      />,
    );
    const overlay = overlayFor(payload, null, registry);
    const held = overlay as {
      _props: {
        layers: {
          props: {
            onClick?: (info: { object?: unknown }) => void;
          };
        }[];
      };
    };
    const geo = held._props.layers.find((layer) => layer.props.onClick);
    const props = geo?.props as unknown as Record<
      symbol,
      { data?: { features?: unknown[] } }
    >;
    const original = props?.[Symbol.for('asyncPropOriginal')];
    const resolved = props?.[Symbol.for('asyncPropResolved')];
    const data = original?.data ?? resolved?.data;
    const row = data?.features?.[0];
    act(() => {
      geo?.props.onClick?.({ object: row });
    });
    const panel = view.container.querySelector('[data-part="apportion"]');
    expect(panel?.textContent).toContain('method_apportion_v1');
    expect(panel?.textContent).toContain('gx_sample_aleph');
    expect(numeralsOutsideChips(panel ?? view.container)).toEqual([]);
  });

  it('F5 shows a typed announced date, count years and all four filters', () => {
    const payload = basePayload({
      layers: [
        {
          key: 'fdi_projects',
          visible: true,
          source_chain_fact_id: CHAIN_ID,
          source_id: 'src_fdi',
          features: [
            {
              feature_id: 'feat_fdi_aleph',
              metric_key: 'fdi_sector',
              provenance: 'public',
              subject: 'fdi_project',
              geometry_kind: 'point',
              place_key: 'gx_sample_aleph',
              capex_fact_id: factId(2),
              jobs_fact_id: factId(3),
              year: '2024',
              caveat_keys: ['fdi_estimates'],
              words: {
                company: 'Sample Announcement House',
                sector: 'Sample sector',
                source_country: 'Sample land',
                location_text: 'Sample quarter',
                project_key: 'sample_key',
                source_country_iso3: 'SAM',
                sub_sector: 'Sample sub',
                business_function: 'Sample function',
                project_type: 'Sample type',
                capex_unit: 'Sample unit',
                municipality_code: 'sample_muni',
                place_key: 'gx_sample_aleph',
              },
              announced: {
                referenceKind: 'calendar_date',
                value: '2024-03-14',
                recordId: 'announced-date',
              },
              filter: {
                sector: 'sample_sector',
                source_country: 'sample_land',
                period: 'sample_period',
                stated_location: 'sample_quarter',
              },
            } as LayerPayload['layers'][number]['features'][number],
            {
              feature_id: 'feat_fdi_beth',
              metric_key: 'fdi_sector',
              provenance: 'public',
              subject: 'fdi_project',
              geometry_kind: 'point',
              place_key: null,
              year: '2024',
              caveat_keys: ['fdi_estimates'],
              words: { company: 'Sample Other House', sector: 'Other sector' },
              filter: {
                sector: 'other_sector',
                source_country: 'other_land',
                period: 'other_period',
                stated_location: 'other_quarter',
              },
            },
          ],
        },
      ],
      sources: [
        {
          sourceId: 'src_fdi',
          attribution: [plain('Sample investment credit')],
          retrievalDate: '2024-03-14',
          publisher: [plain('Sample Agency')],
          datasetOrPage: 'Sample dashboard',
          licenceOrTerms: 'Terms recorded for this sample',
        },
      ],
      credits: SAMPLE_CREDITS,
      count_facts: [{ fact_id: CHAIN_ID, year: '2024' }],
      filter_options: {
        sector: ['sample_sector'],
        source_country: ['sample_land'],
        period: ['sample_period'],
        stated_location: ['sample_quarter'],
      },
    });
    const view = render(
      <PublicLayers
        payload={payload}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    const announced = view.container.querySelector('[data-field="announced"]');
    expect(
      announced?.querySelector('[data-fact-chip="reference"]')?.textContent,
    ).toContain('2024');
    expect(numeralsOutsideChips(announced ?? view.container)).toEqual([]);
    const count = view.container.querySelector(
      `[data-count-fact="${CHAIN_ID}"]`,
    );
    expect(
      count
        ?.querySelector('[data-fact-chip="reference"]')
        ?.getAttribute('data-record'),
    ).toBe(`${CHAIN_ID}-year`);
    for (const choice of [
      'sample_sector',
      'sample_land',
      'sample_period',
      'sample_quarter',
    ]) {
      fireEvent.click(
        view.container.querySelector(`[data-choice="${choice}"]`)!,
      );
      expect(
        view.container.querySelector('[data-project="feat_fdi_beth"]'),
        choice,
      ).toBeNull();
      expect(
        view.container.querySelector('[data-project="feat_fdi_aleph"]'),
        choice,
      ).toBeTruthy();
      fireEvent.click(
        view.container.querySelector(`[data-choice="${choice}"]`)!,
      );
    }
    expect(view.container.querySelector('[data-filtered-count]')).toBeNull();
    expect(view.container.querySelector('[data-mark="yes"]')).toBeTruthy();
  });

  it('F6 renders a split with its source, year and digit categories inside chips', () => {
    const categories = [
      category('group_b'),
      [
        {
          kind: 'reference' as const,
          referenceKind: 'published_text' as const,
          value: '7',
          recordId: 'cat-west',
        },
      ],
      [
        {
          kind: 'reference' as const,
          referenceKind: 'published_text' as const,
          value: '\u0663',
          recordId: 'cat-indic',
        },
      ],
    ];
    const payload = basePayload({
      sources: [
        {
          ...basePayload().sources[0]!,
          year: '2024',
          categories,
          geographyCode: 'sample_geo',
          publisher: [plain('Sample Split Press')],
        },
      ],
      split_chip: {
        provenance: 'public',
        evidence_status: 'observed',
        source_id: 'src_places',
        year: '2024',
        categories,
        geography_code: 'sample_geo',
        source_geography: 'sample_geo',
      },
    });
    const view = render(
      <PublicLayers
        payload={payload}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    const split = view.container.querySelector('[data-part="split-chip"]');
    expect(split?.textContent).toContain('Sample Split Press');
    expect(split?.textContent).toContain('group_b');
    expect(
      split?.querySelector('[data-fact-chip="reference"]')?.textContent,
    ).toContain('2024');
    expect(numeralsOutsideChips(split ?? view.container)).toEqual([]);
    expect(view.container.querySelector('[data-layer="split"]')).toBeNull();
  });

  it('F7 keeps identifier and category numerals inside fact chips', () => {
    const payload = basePayload();
    const feature = payload.layers[0]!.features[0]!;
    feature.feature_id = 'feat_7\u0663';
    (feature as { name_segments?: unknown }).name_segments = [
      {
        kind: 'reference',
        referenceKind: 'published_text',
        value: '7',
        recordId: 'name-west',
      },
      {
        kind: 'reference',
        referenceKind: 'published_text',
        value: '\u0663',
        recordId: 'name-indic',
      },
    ];
    const view = render(
      <PublicLayers
        payload={payload}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    expect(view.container.textContent).not.toContain('feat_7');
    expect(numeralsOutsideChips(view.container)).toEqual([]);
    expect(
      view.container.querySelector('[data-record="name-west"]')?.textContent,
    ).toContain('7');
    expect(
      view.container.querySelector('[data-record="name-indic"]'),
    ).toBeTruthy();
  });

  it('F9 sets Arabic direction on a refusal and places it logically', () => {
    const view = render(
      <PublicLayers
        payload={basePayload({
          layers: [{ ...basePayload().layers[0]!, key: 'presence' }],
        })}
        language="ar"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    const plate = view.container.querySelector('[data-part="public-layers"]');
    expect(plate?.getAttribute('dir')).toBe('rtl');
    expect(plate?.getAttribute('lang')).toBe('ar');
    expect(plate?.classList.contains('layer-plate')).toBe(true);
    const refusal = plate?.querySelector('[data-part="layer-refusal"]');
    expect(refusal).toBeTruthy();
    applyAnswerCss();
    const placed = getComputedStyle(plate as Element);
    expect(placed.insetInlineEnd).not.toBe('');
    expect(placed.insetInlineEnd).not.toBe('auto');
  });

  it('F4 shows a refusal and mounts no overlay when the registry is missing', async () => {
    const mounts: unknown[] = [];
    let started = 0;
    const starter: MapStarter = () => {
      started += 1;
      return {
        remove() {
          return undefined;
        },
        mountOverlay(overlay) {
          mounts.push(overlay);
        },
        bind() {},
        unbind() {},
        project() {
          return { x: 0, y: 0 };
        },
        unproject() {
          return { longitude: 0, latitude: 0 };
        },
        suspendGestures() {},
        restoreGestures() {},
        centre() {
          return { longitude: 0, latitude: 0 };
        },
        bindView() {},
        unbindView() {},
      };
    };
    const view = render(
      <Stage
        language="ar"
        theme="light"
        extractUrl="local.pmtiles"
        mapStarter={starter}
        layerPayload={basePayload()}
        registry={null}
      />,
    );
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(started).toBe(1);
    expect(mounts).toEqual([]);
    const refusal = view.container.querySelector(
      '[data-refusal="registry_absent"]',
    );
    expect(refusal).toBeTruthy();
    expect(refusal?.closest('[dir="rtl"]')).toBeTruthy();
    expect(view.container.querySelector('.stage')?.getAttribute('dir')).toBe(
      'ltr',
    );
  });

  it('F4 mounts no geometry when a binding is invalid', async () => {
    const mounts: { layers: unknown[] }[] = [];
    const starter: MapStarter = () => ({
      remove() {
        return undefined;
      },
      mountOverlay(overlay) {
        const held = overlay as { _props?: { layers?: unknown[] } };
        mounts.push({ layers: held._props?.layers ?? [] });
      },
      bind() {},
      unbind() {},
      project() {
        return { x: 0, y: 0 };
      },
      unproject() {
        return { longitude: 0, latitude: 0 };
      },
      suspendGestures() {},
      restoreGestures() {},
      centre() {
        return { longitude: 0, latitude: 0 };
      },
      bindView() {},
      unbindView() {},
    });
    const registry = layerRegistry([
      { id: CHAIN_ID, metric: 'place_listing', table: 'pub_other' },
    ]);
    const view = render(
      <Stage
        language="en"
        theme="light"
        extractUrl="local.pmtiles"
        mapStarter={starter}
        layerPayload={basePayload()}
        registry={registry}
      />,
    );
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(mounts.every((mount) => mount.layers.length === 0)).toBe(true);
    expect(
      view.container.querySelector('[data-refusal="measure_on_named_feature"]'),
    ).toBeTruthy();
  });
});
