// @vitest-environment jsdom
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { unimplementedReason } from '../../src/stage/layers/checks';
import { overlayFor } from '../../src/stage/layers/overlay';
import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { LAYER_ENTRIES } from '../../src/stage/layers/registry';
import { factId } from '../fixtures/facts';
import { sceneRegistry } from '../fixtures/layer-registry';
import {
  CHAIN_ID,
  SAMPLE_CREDITS,
  basePayload,
  plain,
} from '../fixtures/layers';
import ar from '../../src/i18n/ar.json';
import en from '../../src/i18n/en.json';

afterEach(() => {
  cleanup();
});

const credits = SAMPLE_CREDITS;

function scene() {
  return basePayload({
    layers: [
      basePayload().layers[0]!,
      {
        key: 'commercial_points',
        visible: true,
        source_chain_fact_id: CHAIN_ID,
        source_id: 'src_places',
        features: [
          {
            feature_id: 'feat_poi',
            metric_key: 'poi_category',
            provenance: 'public',
            subject: 'business',
            geometry_kind: 'point',
            fact_id: factId(1),
          },
        ],
      },
      {
        key: 'fdi_projects',
        visible: true,
        source_chain_fact_id: CHAIN_ID,
        source_id: 'src_places',
        features: [
          {
            feature_id: 'feat_fdi_aleph',
            metric_key: 'fdi_capex',
            provenance: 'public',
            subject: 'fdi_project',
            geometry_kind: 'point',
            place_key: null,
            fact_id: factId(2),
            capex_fact_id: factId(2),
            year: '2024',
            caveat_keys: ['fdi_estimates'],
            words: {
              company: 'Sample Announcement House',
              sector: 'Sample sector',
              source_country: 'Sample land',
              location_text: 'Sample quarter',
            },
          },
        ],
      },
    ],
    credits,
    count_fact_ids: [CHAIN_ID],
    count_facts: [{ fact_id: CHAIN_ID, year: '2024' }],
    visitor_fact_id: CHAIN_ID,
    estimated_people_fact_id: CHAIN_ID,
  });
}

describe('public layer screen', () => {
  it('shows the listings note, FDI card and separate visitor counts', () => {
    const open = { id: '' };
    const view = render(
      <PublicLayers
        payload={scene()}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={(id) => {
          open.id = id;
        }}
      />,
    );
    expect(
      view.container.querySelectorAll('[data-note="listings"]').length,
    ).toBe(1);
    expect(view.container.textContent).toContain(
      'Open listings are incomplete',
    );
    expect(
      view.container
        .querySelector('[data-project="feat_fdi_aleph"]')
        ?.getAttribute('data-mark'),
    ).toBe('no');
    expect(view.container.querySelector('[data-filter="sector"]')).toBeTruthy();
    expect(
      view.container.querySelector('[data-filter="source_country"]'),
    ).toBeTruthy();
    expect(view.container.querySelector('[data-filter="period"]')).toBeTruthy();
    expect(
      view.container.querySelector('[data-filter="stated_location"]'),
    ).toBeTruthy();
    expect(view.container.querySelector('input')).toBeNull();
    expect(view.container.textContent).toContain(
      'includes estimates of publicly announced projects',
    );
    expect(view.container.textContent).toContain(
      'does not capture all investment projects',
    );
    expect(view.container.textContent).toContain('announced estimates');
    expect(
      view.container.querySelector('[data-credit-field="publisher"]')
        ?.textContent,
    ).toBe('Sample Agency');
    expect(
      view.container.querySelector('[data-part="visitor-counts"]'),
    ).toBeTruthy();
    expect(
      view.container.querySelector(
        '[data-part="visitor-counts"] [data-part="estimated-people"]',
      ),
    ).toBeNull();
    fireEvent.click(
      view.container.querySelector('[data-feature="feat_place_aleph"]')!,
    );
    expect(
      view.container.querySelector('[data-part="places-panel"]'),
    ).toBeTruthy();
    expect(open.id).toBe('');
    fireEvent.click(
      view.container.querySelector('[data-action="source-chain"]')!,
    );
    expect(open.id).toBe(CHAIN_ID);
  });

  it('F12 sets Arabic direction and isolates a published name', () => {
    const view = render(
      <PublicLayers
        payload={scene()}
        language="ar"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    expect(
      view.container
        .querySelector('[data-part="public-layers"]')
        ?.getAttribute('dir'),
    ).toBe('rtl');
    const name = view.container.querySelector('[data-field="company"] bdi');
    expect(name).toBeTruthy();
    expect(name?.textContent).toContain('Sample Announcement House');
  });

  it('F11 keeps a dated credit numeral inside a reference chip', () => {
    const payload = scene();
    payload.sources = [
      {
        ...payload.sources[0]!,
        attribution: [
          plain('Sample credit '),
          {
            kind: 'reference',
            referenceKind: 'calendar_date',
            value: '2024-03-14',
            recordId: 'credit-date',
          },
        ],
      },
    ];
    payload.credits = {
      ...credits,
      publisher: [
        plain('Edition '),
        {
          kind: 'reference',
          referenceKind: 'published_text',
          value: '2',
          recordId: 'edition',
        },
      ],
      gatherer: [
        plain('Sample gatherer '),
        {
          kind: 'reference',
          referenceKind: 'published_text',
          value: '10.1000/sample',
          recordId: 'doi',
        },
      ],
    };
    const view = render(
      <PublicLayers
        payload={payload}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    const regions = view.container.querySelectorAll(
      '[data-credit], [data-credit-field="publisher"], [data-credit-field="gatherer"]',
    );
    expect(regions.length).toBeGreaterThan(0);
    for (const region of regions) {
      const leaves = region.querySelectorAll('*');
      const targets = leaves.length > 0 ? leaves : [region];
      for (const node of targets) {
        if (node.children.length > 0) continue;
        const content = node.textContent ?? '';
        if (!/[0-9\u0660-\u0669\u06F0-\u06F9]/u.test(content)) continue;
        const chip = node.closest('[data-fact-chip]');
        expect(chip?.getAttribute('data-fact-chip'), content).toBe('reference');
      }
    }
  });

  it('F9 shows a catalogue reason for a layer that is not built', () => {
    const view = render(
      <PublicLayers
        payload={basePayload({
          layers: [{ ...basePayload().layers[0]!, key: 'presence' }],
        })}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    const reason = view.container.querySelector('[data-part="layer-refusal"]');
    // Decision 0035 item 1: the refusal names no data origin.
    expect(reason?.textContent).toContain('has no map in this version');
    expect(reason?.textContent).not.toContain('published source');
    expect(reason?.textContent ?? '').not.toMatch(/S[0-9]-T|OI-/u);
  });

  it('F4 selects a station from the keyboard and shows its source chain', () => {
    const open = { id: '' };
    const payload = basePayload({
      layers: [
        {
          key: 'rail_plan',
          visible: true,
          source_chain_fact_id: CHAIN_ID,
          source_id: 'src_places',
          features: [
            {
              feature_id: 'feat_station',
              metric_key: 'rail_feature',
              provenance: 'public',
              subject: 'gis_feature',
              geometry_kind: 'point',
              status_key: 'planned',
              fact_id: factId(4),
              words: { name: 'Sample Halt' },
            },
          ],
        },
      ],
    });
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
    const button = view.container.querySelector(
      '[data-feature="feat_station"]',
    );
    expect(button?.getAttribute('aria-label')).toContain('Sample Halt');
    fireEvent.keyDown(button!, { key: 'Enter' });
    expect(
      view.container.querySelector('[data-label="station"]')?.textContent,
    ).toContain('Planned');
    fireEvent.click(
      view.container.querySelector('[data-action="source-chain"]')!,
    );
    expect(open.id).toBe(factId(4));
    expect(view.container.querySelector('[data-part="apportion"]')).toBeNull();
  });

  // RV1 finding 1: a presentation word or status renders on its owning layer.
  it.each([
    ['zoning', 'permitted_use', { words: { permitted_use: 'Invented use' } }],
    ['parcels', 'plot_state', { status_key: 'permitted_empty' }],
  ] as const)(
    'renders the %s presentation on its own layer',
    (key, metric, field) => {
      const payload = basePayload({
        layers: [
          {
            key,
            visible: true,
            source_chain_fact_id: CHAIN_ID,
            source_id: 'src_places',
            features: [
              {
                feature_id: 'feat_owned',
                metric_key: metric,
                provenance: 'public',
                subject: 'gis_feature',
                geometry_kind: 'outline',
                ...field,
              },
            ],
          },
        ],
      });
      const view = render(
        <PublicLayers
          payload={payload}
          language="en"
          registry={sceneRegistry()}
          onOpenChain={() => undefined}
        />,
      );
      fireEvent.click(
        view.container.querySelector('[data-feature="feat_owned"]')!,
      );
      const label = key === 'zoning' ? 'permitted' : 'plot';
      expect(
        view.container.querySelector(`[data-label="${label}"]`)?.textContent,
      ).toContain(
        key === 'zoning' ? 'Invented use' : en.strings['layers.plot.label'],
      );
    },
  );

  it('F7 shows capex and jobs together and hides by a supplied sector', () => {
    const payload = scene();
    const feature = payload.layers[2]!.features[0]!;
    feature.words = {
      ...feature.words,
      project_key: 'sample_key',
      company: 'Sample Announcement House',
      source_country: 'Sample land',
      source_country_iso3: 'SAM',
      sector: 'Sample sector',
      sub_sector: 'Sample sub',
      business_function: 'Sample function',
      project_type: 'Sample type',
      capex_unit: 'Sample unit',
      location_text: 'Sample quarter',
      municipality_code: 'sample_muni',
      place_key: 'gx_missing',
    };
    feature.capex_fact_id = factId(2);
    feature.jobs_fact_id = factId(3);
    (feature as { filter?: { sector: string } }).filter = {
      sector: 'sample_sector',
    };
    payload.layers[2]!.features.push({
      ...feature,
      feature_id: 'feat_fdi_beth',
      filter: { sector: 'other_sector' },
    } as (typeof payload.layers)[number]['features'][number]);
    payload.filter_options = {
      sector: ['sample_sector', 'other_sector'],
      source_country: [],
      period: [],
      stated_location: [],
    } as never;
    const view = render(
      <PublicLayers
        payload={payload}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    expect(
      view.container.querySelector(
        '[data-field="capex_value"] [data-fact-chip]',
      ),
    ).toBeTruthy();
    expect(
      view.container.querySelector('[data-field="jobs"] [data-fact-chip]'),
    ).toBeTruthy();
    expect(
      view.container.querySelectorAll('[data-part="fdi-credits"]').length,
    ).toBeGreaterThanOrEqual(3);
    expect(
      view.container.querySelector('[data-choice="sample_sector"]')
        ?.textContent,
    ).toBe('sample_sector');
    fireEvent.click(
      view.container.querySelector('[data-choice="sample_sector"]')!,
    );
    expect(
      view.container.querySelector('[data-project="feat_fdi_beth"]'),
    ).toBeNull();
    expect(
      view.container.querySelector('[data-project="feat_fdi_aleph"]'),
    ).toBeTruthy();
    expect(view.container.querySelector('[data-filtered-count]')).toBeNull();
  });

  it('F6 shows a record credit only while that source is drawn', () => {
    const shared = {
      retrievalDate: '2024-03-14',
      publisher: [plain('Sample Publisher')],
      datasetOrPage: 'Sample places page',
      licenceOrTerms: 'Terms recorded for this sample',
    };
    const both = basePayload({
      layers: [
        {
          key: 'public_places',
          visible: true,
          source_chain_fact_id: CHAIN_ID,
          source_id: 'src_ovt',
          features: [
            {
              feature_id: 'feat_ovt',
              metric_key: 'place_listing',
              provenance: 'public',
              subject: 'place',
              geometry_kind: 'point',
              fact_id: CHAIN_ID,
              source_id: 'src_ovt',
            },
            {
              feature_id: 'feat_fsq',
              metric_key: 'place_listing',
              provenance: 'public',
              subject: 'place',
              geometry_kind: 'point',
              fact_id: CHAIN_ID,
              source_id: 'src_fsq',
            },
          ],
        },
      ],
      sources: [
        {
          ...shared,
          sourceId: 'src_ovt',
          attribution: [plain('Sample overture credit')],
        },
        {
          ...shared,
          sourceId: 'src_fsq',
          attribution: [plain('Sample foursquare credit')],
          sourceRelease: {
            referenceKind: 'calendar_date',
            value: '2024-06-01',
            recordId: 'fsq-release',
          },
        },
      ],
    });
    const on = render(
      <PublicLayers
        payload={both}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    expect(on.container.textContent).toContain('Sample overture credit');
    expect(on.container.textContent).toContain('Sample foursquare credit');
    expect(
      on.container.querySelector('[data-record="fsq-release"]'),
    ).toBeTruthy();
    cleanup();
    const overtureOnly = basePayload({
      ...both,
      layers: [
        {
          ...both.layers[0]!,
          features: [both.layers[0]!.features[0]!],
        },
      ],
    });
    const off = render(
      <PublicLayers
        payload={overtureOnly}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    expect(off.container.textContent).toContain('Sample overture credit');
    expect(off.container.textContent).not.toContain('Sample foursquare credit');
    expect(
      off.container.querySelector('[data-record="fsq-release"]'),
    ).toBeNull();
  });

  it('F9 gives every unbuilt key its own catalogue reason', () => {
    for (const entry of LAYER_ENTRIES.filter((item) => !item.implemented)) {
      const view = render(
        <PublicLayers
          payload={basePayload({
            layers: [{ ...basePayload().layers[0]!, key: entry.key }],
          })}
          language="en"
          registry={sceneRegistry()}
          onOpenChain={() => undefined}
        />,
      );
      const reason = view.container.querySelector(
        '[data-part="layer-refusal"]',
      );
      expect(reason?.textContent, entry.key).toBe(
        en.strings[unimplementedReason(entry.key)],
      );
      expect(reason?.textContent ?? '', entry.key).not.toMatch(/S[0-9]-T|OI-/u);
      cleanup();
    }
  });

  it('F4 map pick opens the same panel as the keyboard control', () => {
    const payload = scene();
    const view = render(
      <PublicLayers
        payload={payload}
        language="en"
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    );
    const overlay = overlayFor(payload, null, sceneRegistry());
    const held = overlay as {
      _props: {
        layers: {
          props: {
            onClick?: (info: { object?: { featureId?: string } }) => void;
          };
        }[];
      };
    };
    const pick = held._props.layers.find((layer) => layer.props.onClick);
    act(() => {
      pick?.props.onClick?.({ object: { featureId: 'feat_place_aleph' } });
    });
    expect(
      view.container.querySelector('[data-part="places-panel"]'),
    ).toBeTruthy();
  });

  it('keeps new Arabic strings marked for native review', () => {
    expect(Object.keys(ar.review).sort()).toEqual(
      Object.keys(en.strings).sort(),
    );
    for (const key of Object.keys(en.strings)) {
      if (!key.startsWith('layers.') && key !== 'unit.radiance_nw_cm2_sr')
        continue;
      expect(ar.review[key as keyof typeof ar.review]).toBe(
        'pending-native-review',
      );
    }
  });
});
