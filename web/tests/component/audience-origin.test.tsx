// @vitest-environment jsdom
/**
 * S3-T18: no audience origin label, accessible text included, on every
 * surface of the map foundation that has landed (decision 0035 items 1, 2
 * and 4). Guards and plants live in ../fixtures/audience-origin.ts.
 * `EII_ORIGIN_PLANT=visible|accessible|texture|hidden-count` plants one
 * violation into the real surfaces to show its guard red.
 */
import { readFileSync } from 'node:fs';
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { catalogue, type AnswerDraft } from '../../src/brief/catalogue';
import { Brief } from '../../src/brief/Brief';
import { PublicContextCard } from '../../src/cards/PublicContextCard';
import { DrawTools } from '../../src/controls/DrawTools';
import { FactChip } from '../../src/facts/FactChip';
import { SourceChainDrawer } from '../../src/facts/SourceChainDrawer';
import type { FactRegistry } from '../../src/facts/registry';
import type { Provenance } from '../../src/facts/types';
import ar from '../../src/i18n/ar.json';
import en from '../../src/i18n/en.json';
import { AnswerShell } from '../../src/shell/AnswerShell';
import { registerPort, releasePort } from '../../src/state/area-actions';
import { clearArea } from '../../src/state/store';
import { ClockScrubber } from '../../src/stage/ClockScrubber';
import { MapModeSwitch } from '../../src/stage/MapModeSwitch';
import { MapCredits } from '../../src/stage/Stage';
import { Swipe } from '../../src/stage/Swipe';
import { unimplementedReason } from '../../src/stage/layers/checks';
import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { LAYER_ENTRIES } from '../../src/stage/layers/registry';
import {
  environmentPlant,
  exposedCounts,
  originLabels,
  originStyles,
  plantInto,
  sourceText,
  type Finding,
  type Language,
  type Plant,
} from '../fixtures/audience-origin';
import {
  completeInput,
  factId,
  makeBinding,
  makeFact,
  makeLineage,
  makeSource,
  registryFrom,
} from '../fixtures/facts';
import { fcPayload, fcRegistry } from '../fixtures/fc-firms';
import { sceneRegistry } from '../fixtures/layer-registry';
import {
  CHAIN_ID,
  SAMPLE_CREDITS,
  basePayload,
  category,
  plain,
} from '../fixtures/layers';
import {
  contextInput,
  contextPayloads,
  contextRegistry,
} from '../fixtures/public-context';
import { plainPort } from '../fixtures/plain-port';

let portToken = 0;
beforeEach(() => {
  clearArea();
  portToken = registerPort(plainPort(320, 320));
});
afterEach(() => {
  cleanup();
  clearArea();
  releasePort(portToken);
});

const LANGUAGES = ['en', 'ar'] as const;
const PLANT = environmentPlant();
const HIDDEN = 7391;

/** Invented Public credits, one of them carrying the word Public itself. */
const CREDIT = makeSource({
  publisher: 'Public Works Register Office',
  datasetOrPage: 'Invented page of counts',
  licenceOrTerms: 'Invented open terms',
});
const LINEAGE = makeLineage({
  method: 'aleph_count_method',
  methodVersion: 'v3',
});

function classInput(provenance: Provenance) {
  const inputClass = provenance === 'suppressed' ? 'public' : provenance;
  const kind =
    inputClass === 'public'
      ? 'public_dataset'
      : inputClass === 'synthetic'
        ? 'synthetic_feed'
        : 'simulation_output';
  return {
    ...completeInput(),
    facts: [
      makeBinding({
        fact: makeFact({
          provenance,
          input_classes: [inputClass],
          value: provenance === 'suppressed' ? HIDDEN : 48,
          label_en: 'People in the drawn area',
          label_ar: 'الأشخاص في المنطقة المرسومة',
        }),
      }),
    ],
    lineages: [{ ...LINEAGE, inputClasses: [inputClass] }],
    sources: [{ ...CREDIT, kind, inputClass }],
  } as const;
}

function classRegistry(provenance: Provenance): FactRegistry {
  return registryFrom(classInput(provenance));
}

const ALLOWED = sourceText(
  CREDIT,
  LINEAGE,
  makeSource(),
  makeLineage(),
  basePayload(),
  layerScene(),
  splitScene(),
  fcPayload(),
  contextInput(),
);

function draft(): AnswerDraft {
  return {
    catalogueVersion: catalogue.version,
    accountingPassed: true,
    subject: 'area' as const,
    componentKey: 'foundation_note',
    props: [] as string[],
    directive: null,
    slots: [
      { factId: factId(0), provenance: 'public' as const, metric: 'people' },
    ],
  };
}

function layerScene() {
  return basePayload({
    layers: [
      basePayload().layers[0]!,
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
              company: 'Aleph Announcement House',
              sector: 'Aleph sector',
              source_country: 'Aleph land',
              location_text: 'Aleph quarter',
            },
          },
        ],
      },
    ],
    credits: SAMPLE_CREDITS,
    count_fact_ids: [CHAIN_ID],
    count_facts: [{ fact_id: CHAIN_ID, year: '2024' }],
    visitor_fact_id: CHAIN_ID,
    estimated_people_fact_id: CHAIN_ID,
  });
}

/** The published split of layers.fix3 F6, with invented categories. */
function splitScene() {
  const categories = [category('group_b'), category('group_a')];
  return basePayload({
    sources: [
      {
        ...basePayload().sources[0]!,
        year: '2024',
        categories,
        geographyCode: 'sample_geo',
        publisher: [plain('Aleph Split Press')],
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
}

function scenarioRegistry(): FactRegistry {
  return registryFrom({
    ...completeInput(),
    facts: [0, 1].map((index) =>
      makeBinding({
        fact: makeFact({
          fact_id: factId(index),
          value: index === 0 ? 48 : 52,
          geography: { kind: 'user_scenario', area_id: 'SYN-area' },
          input_classes: ['public', 'user_input'],
        }),
      }),
    ),
    lineages: [makeLineage({ inputClasses: ['public', 'user_input'] })],
    sources: [makeSource({ kind: 'reviewed_config' })],
  });
}

const MODES = {
  open: { available: true, reason: null },
  satellite: { available: false, reason: 'offline' },
  photoreal: { available: false, reason: 'cap_reached' },
} as const;

/** Every landed surface of S3-T18's scope, by name. */
const SURFACES: Record<
  string,
  (language: Language) => ReturnType<typeof render>
> = {
  'entry: Stage, Brief, chips, drawing tools and legend plate': (language) =>
    render(
      <AnswerShell
        language={language}
        theme="dark"
        extractUrl={null}
        registry={sceneRegistry()}
        draft={draft(sceneRegistry())}
        sourceLayers={layerScene()}
      />,
    ),
  'disclosure, answer level: Brief': (language) =>
    render(
      <Brief
        language={language}
        registry={classRegistry('public')}
        draft={draft()}
        onOpen={() => undefined}
      />,
    ),
  'disclosure, evidence level: source drawer of a Public fact': (language) =>
    drawer('public', language),
  'disclosure, evidence level: source drawer of a backend Synthetic fact': (
    language,
  ) => drawer('synthetic', language),
  'disclosure, evidence level: source drawer of a backend Simulated fact': (
    language,
  ) => drawer('simulated', language),
  'disclosure, evidence level: source drawer of a withheld fact': (language) =>
    drawer('suppressed', language),
  'disclosure, comparison level: baseline and reset': (language) =>
    render(
      <Swipe
        language={language}
        comparison={{
          kind: 'scenario',
          baselineFactId: factId(0),
          changedFactId: factId(1),
        }}
        registry={scenarioRegistry()}
        onOpen={() => undefined}
      />,
    ),
  'legends, captions and credits: Public layers with the FDI card': (
    language,
  ) =>
    render(
      <PublicLayers
        payload={layerScene()}
        language={language}
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    ),
  'legends: a published split chip': (language) =>
    render(
      <PublicLayers
        payload={splitScene()}
        language={language}
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    ),
  'legends: firms by tower': (language) =>
    render(
      <PublicLayers
        payload={fcPayload()}
        language={language}
        registry={fcRegistry()}
        onOpenChain={() => undefined}
      />,
    ),
  'refused layer plate': (language) =>
    render(
      <PublicLayers
        payload={basePayload({
          layers: [
            {
              key: 'crowd_density',
              visible: true,
              source_chain_fact_id: CHAIN_ID,
              source_id: 'src_places',
              features: [],
            },
          ],
        })}
        language={language}
        registry={sceneRegistry()}
        onOpenChain={() => undefined}
      />,
    ),
  'context cards': (language) =>
    render(
      <div>
        {contextPayloads.map((payload) => (
          <PublicContextCard
            key={payload.family}
            payload={payload}
            language={language}
            registry={contextRegistry()}
            onOpen={() => undefined}
          />
        ))}
      </div>,
    ),
  'map modes and their credits': (language) =>
    render(
      <div>
        <MapModeSwitch
          language={language}
          modes={MODES}
          selected="open"
          onChange={() => undefined}
        />
        <MapCredits
          language={language}
          mode="satellite"
          credit="Example imagery credit"
        />
      </div>,
    ),
  'sunlight clock': (language) =>
    render(
      <ClockScrubber
        language={language}
        fraction=""
        onFractionChange={() => undefined}
        onChange={() => undefined}
      />,
    ),
  'drawing tools': (language) => render(<DrawTools language={language} />),
};

function drawer(provenance: Provenance, language: Language) {
  return render(
    <SourceChainDrawer
      factId={factId(0)}
      registry={classRegistry(provenance)}
      language={language}
      receiptHref="https://example.invalid/receipt"
      onClose={() => undefined}
    />,
  );
}

function rooted(view: ReturnType<typeof render>, language: Language) {
  plantInto(view.container, PLANT, language, HIDDEN);
  return view.container;
}

describe('no audience origin label on any landed surface', () => {
  for (const [name, mount] of Object.entries(SURFACES)) {
    for (const language of LANGUAGES) {
      it(`${name} (${language}) shows no origin word, visible or accessible`, () => {
        const root = rooted(mount(language), language);
        expect(described(originLabels(root, ALLOWED))).toEqual([]);
      });
      it(`${name} (${language}) carries no origin-driven style or texture`, () => {
        const root = rooted(mount(language), language);
        expect(described(originStyles(root))).toEqual([]);
      });
    }
  }

  function openedDrawer(language: Language) {
    const view = render(
      <AnswerShell
        language={language}
        theme="light"
        extractUrl={null}
        registry={classRegistry('public')}
        draft={draft()}
      />,
    );
    const chip = view.container.querySelector<HTMLElement>(
      '.brief [data-fact-chip]',
    );
    expect(chip).not.toBeNull();
    fireEvent.click(chip!);
    expect(view.container.querySelector('.drawer')).not.toBeNull();
    return rooted(view, language);
  }

  for (const language of LANGUAGES) {
    it(`the drawer opened from a Brief chip (${language}) shows no origin word, visible or accessible`, () => {
      expect(described(originLabels(openedDrawer(language), ALLOWED))).toEqual(
        [],
      );
    });
    it(`the drawer opened from a Brief chip (${language}) carries no origin-driven style or texture`, () => {
      expect(described(originStyles(openedDrawer(language)))).toEqual([]);
    });
  }

  it('no audience string table holds a provenance-class word or origin key', () => {
    for (const table of [en.strings, ar.strings]) {
      for (const [key, value] of Object.entries(table)) {
        if (key === 'drawer.class.suppressed') continue;
        expect(key).not.toMatch(/^drawer\.class\.|^drawer\.inputs$/);
        expect({ key, word: originLabels(textElement(value)) }).toEqual({
          key,
          word: [],
        });
      }
    }
  });

  it('a refused non-Public layer says no origin, by the pending reason', () => {
    for (const entry of LAYER_ENTRIES) {
      if (entry.className.includes('Public')) continue;
      expect(unimplementedReason(entry.key)).toBe('layers.refused.pending');
    }
  });
});

function described(findings: readonly Finding[]): string[] {
  return findings.map((finding) => `${finding.where}: ${finding.text}`);
}

function textElement(value: string): Element {
  const element = document.createElement('p');
  element.textContent = value;
  return element;
}

describe('a withheld fact shows neither zero nor its hidden count', () => {
  for (const language of LANGUAGES) {
    it(`chip and drawer (${language})`, () => {
      const registry = classRegistry('suppressed');
      const view = render(
        <div>
          <FactChip
            variant="value"
            size="standard"
            factId={factId(0)}
            registry={registry}
            language={language}
            onOpen={() => undefined}
          />
          <SourceChainDrawer
            factId={factId(0)}
            registry={registry}
            language={language}
            onClose={() => undefined}
          />
        </div>,
      );
      const root = rooted(view, language);
      expect(described(exposedCounts(root, HIDDEN))).toEqual([]);
    });
  }
});

describe('the withheld state, method and credits remain (positive controls)', () => {
  for (const language of LANGUAGES) {
    const table = language === 'ar' ? ar.strings : en.strings;
    it(`the withheld chip keeps its hatch box and the drawer its lock and word (${language})`, () => {
      const view = drawer('suppressed', language);
      const mark = view.container.querySelector(
        '[data-part="withheld"] [data-mark="withheld"]',
      );
      expect(mark?.getAttribute('data-shape')).toBe('lock');
      expect(mark?.textContent).toContain(table['drawer.class.suppressed']);
      cleanup();
      const chip = render(
        <FactChip
          variant="value"
          size="standard"
          factId={factId(0)}
          registry={classRegistry('suppressed')}
          language={language}
          onOpen={() => undefined}
        />,
      );
      expect(
        chip.container.querySelector('[data-state="withheld"] .chip-withheld'),
      ).not.toBeNull();
    });

    it(`the drawer keeps the producing method and version, the Public credit and the evidence status (${language})`, () => {
      for (const provenance of ['public', 'synthetic', 'simulated'] as const) {
        const view = drawer(provenance, language);
        const text = view.container.textContent ?? '';
        expect(text).toContain('aleph_count_method');
        expect(
          view.container.querySelector(
            '[data-part="method"] > [data-fact-chip="reference"]',
          )?.textContent,
        ).toContain('v3');
        expect(text).toContain('Public Works Register Office');
        expect(text).toContain('Invented page of counts');
        expect(text).toContain('Invented open terms');
        expect(
          view.container.querySelector(
            '[data-part="status"] [data-mark="status"]',
          ),
        ).not.toBeNull();
        expect(
          view.container.querySelector('[data-part="withheld"]'),
        ).toBeNull();
        expect(
          view.container.querySelector('[data-part="coverage"]')?.textContent,
        ).toBe(table['coverage.rows_kept']);
        expect(
          view.container.querySelector('[data-part="reliability"]'),
        ).not.toBeNull();
        cleanup();
      }
    });

    it(`layer credits, the split's publisher, the FDI estimate wording and the withheld swatch remain (${language})`, () => {
      const view = render(
        <div>
          <PublicLayers
            payload={layerScene()}
            language={language}
            registry={sceneRegistry()}
            onOpenChain={() => undefined}
          />
          <PublicLayers
            payload={splitScene()}
            language={language}
            registry={sceneRegistry()}
            onOpenChain={() => undefined}
          />
        </div>,
      );
      const root = view.container;
      expect(
        root.querySelector('[data-credit-field="source-publisher"]'),
      ).not.toBeNull();
      expect(
        root.querySelector('[data-credit-field="publisher"]')?.textContent,
      ).toBe('Sample Agency');
      expect(
        root.querySelector('[data-part="split-chip"]')?.textContent,
      ).toContain('Aleph Split Press');
      expect(root.textContent).toContain(table['layers.fdi.announced']);
      const swatches = root.querySelectorAll(
        '[data-part="public-layers"]:first-child [data-part="line-samples"] li',
      );
      expect(swatches).toHaveLength(1);
      expect(swatches[0]?.getAttribute('data-pattern')).toBe('hatch-lock');
      expect(
        swatches[0]?.querySelector('[data-mark="withheld"]')?.textContent,
      ).toContain(table['drawer.class.suppressed']);
    });

    it(`an estimated count keeps its range (${language})`, () => {
      const registry = registryFrom({
        ...completeInput(),
        facts: [
          makeBinding({
            fact: makeFact({ value: 48 }),
            presentation: 'estimated_count',
            rangeLowId: factId(1),
            rangeHighId: factId(2),
          }),
          makeBinding({ fact: makeFact({ fact_id: factId(1), value: 40 }) }),
          makeBinding({ fact: makeFact({ fact_id: factId(2), value: 56 }) }),
        ],
      });
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
        view.container.querySelector('.chip-range')?.textContent,
      ).toContain(table['chip.range']);
    });

    it(`the non-drag controls remain (${language})`, () => {
      const swipe = render(
        <Swipe
          language={language}
          comparison={{
            kind: 'scenario',
            baselineFactId: factId(0),
            changedFactId: factId(1),
          }}
          registry={scenarioRegistry()}
          onOpen={() => undefined}
        />,
      );
      expect(
        swipe.getByRole('button', { name: table['comparison.reset'] }),
      ).toBeTruthy();
      expect(
        swipe.getByRole('group', { name: table['comparison.baseline'] }).hidden,
      ).toBe(false);
      expect(swipe.container.querySelector('input[type="range"]')).toBeNull();
      cleanup();
      const clock = render(
        <ClockScrubber
          language={language}
          fraction=""
          onFractionChange={() => undefined}
          onChange={() => undefined}
        />,
      );
      expect(clock.getByRole('slider').getAttribute('step')).toBe('any');
      expect(clock.getByRole('textbox')).toBeTruthy();
      expect(clock.container.textContent).toContain(table['clock.input']);
      cleanup();
      const tools = render(<DrawTools language={language} />);
      expect(
        tools.getByRole('group', { name: table['draw.tools'] }),
      ).toBeTruthy();
    });
  }

  it('the entry surface mounts the stage, legend plate, drawing tools and Brief together', () => {
    const view =
      SURFACES['entry: Stage, Brief, chips, drawing tools and legend plate']!(
        'en',
      );
    for (const selector of [
      '.stage',
      '[data-part="public-layers"]',
      '[data-part="line-samples"]',
      '[data-project="feat_fdi_aleph"]',
      '.draw-tools [role="group"]',
      '.brief',
    ])
      expect({
        selector,
        found: view.container.querySelector(selector) !== null,
      }).toEqual({
        selector,
        found: true,
      });
  });

  it('the right-to-left text plugin stays registered before a map starts', () => {
    const boot = readFileSync('src/stage/map-boot.ts', 'utf8');
    expect(boot).toContain('@mapbox/mapbox-gl-rtl-text');
    expect(boot).toMatch(/setRTLTextPlugin\(rtlPluginUrl, true\)/);
  });

  it('backend facts keep their provenance and input classes after rendering', () => {
    for (const provenance of [
      'public',
      'synthetic',
      'simulated',
      'suppressed',
    ] as const) {
      const registry = classRegistry(provenance);
      drawer(provenance, 'en');
      const resolved = registry.resolve(factId(0));
      expect(resolved.status).toBe('ready');
      if (resolved.status !== 'ready') continue;
      expect(resolved.binding.fact.provenance).toBe(provenance);
      expect(resolved.lineage.inputClasses.length).toBeGreaterThan(0);
      expect(resolved.lineage.method).toBe('aleph_count_method');
      expect(resolved.lineage.methodVersion).toBe('v3');
      cleanup();
    }
  });

  it('source validation still refuses a generated input class without its feed', () => {
    const input = classInput('synthetic');
    const registry = registryFrom({
      ...input,
      sources: [{ ...CREDIT, kind: 'public_dataset', inputClass: 'public' }],
    });
    const resolved = registry.resolve(factId(0));
    expect(resolved.status).toBe('refused');
  });
});

describe('each planted violation fails only its own guard', () => {
  const surface = (language: Language) =>
    render(
      <AnswerShell
        language={language}
        theme="dark"
        extractUrl={null}
        registry={classRegistry('suppressed')}
        draft={draft()}
        sourceLayers={layerScene()}
      />,
    );
  const cases: [Exclude<Plant, ''>, string][] = [
    ['visible', 'origin-label'],
    ['accessible', 'origin-label'],
    ['texture', 'origin-style'],
    ['hidden-count', 'hidden-count'],
  ];
  for (const language of LANGUAGES) {
    for (const [plant, guard] of cases) {
      it(`${plant} (${language}) is caught by ${guard} alone`, () => {
        const view = surface(language);
        const root = view.container;
        const before = {
          label: originLabels(root, ALLOWED).length,
          style: originStyles(root).length,
          count: exposedCounts(root, HIDDEN).length,
        };
        plantInto(root, plant, language, HIDDEN);
        const after = {
          label: originLabels(root, ALLOWED).length,
          style: originStyles(root).length,
          count: exposedCounts(root, HIDDEN).length,
        };
        expect(after).toEqual({
          label: before.label + (guard === 'origin-label' ? 1 : 0),
          style: before.style + (guard === 'origin-style' ? 1 : 0),
          count: before.count + (guard === 'hidden-count' ? 1 : 0),
        });
        if (plant === 'accessible') {
          const found = originLabels(root, ALLOWED).at(-1);
          expect(found?.where).toMatch(/@aria-label$/);
        }
      });
    }
  }

  it('a genuine Public credit is not an origin label, but the same word as app text is', () => {
    const credit = textElement('Public Works Register Office');
    expect(originLabels(credit, ALLOWED)).toEqual([]);
    const label = textElement('Public');
    expect(originLabels(label, ALLOWED)).toHaveLength(1);
  });

  it('a backend class value never enters the source allowance', () => {
    const allowance = sourceText({
      provenance: 'Simulated',
      inputClass: 'synthetic',
      publisher: 'Aleph Publisher',
    });
    expect([...allowance]).toEqual(['Aleph Publisher']);
    expect(originLabels(textElement('Simulated'), allowance)).toHaveLength(1);
  });

  it('withheld wording and unrelated words are not origin labels', () => {
    for (const value of [
      'Suppressed',
      'محجوب',
      'includes estimates of publicly announced projects',
      'Published visitor counts',
    ]) {
      expect(originLabels(textElement(value))).toEqual([]);
    }
  });

  it('an Arabic origin word with diacritics is still caught', () => {
    expect(originLabels(textElement('اصطِناعيّ'))).toHaveLength(1);
  });

  it('a hidden count in Arabic-Indic digits with a separator is caught', () => {
    const element = textElement('');
    element.setAttribute('aria-label', '٧٬٣٩١');
    expect(exposedCounts(element, HIDDEN)).toHaveLength(1);
    const zero = textElement('0');
    expect(exposedCounts(zero, HIDDEN)).toHaveLength(1);
  });
});
