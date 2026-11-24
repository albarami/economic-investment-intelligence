/**
 * Browser harness for the answer specs. Production never imports this file.
 */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-sans-arabic/400.css';
import '@fontsource/ibm-plex-sans-arabic/500.css';
import '@fontsource/ibm-plex-sans-arabic/600.css';
import '../../src/styles/tokens.css';
import '../../src/styles/answer.css';
import { catalogue } from '../../src/brief/catalogue';
import { FactChip } from '../../src/facts/FactChip';
import { PublicContextCard } from '../../src/cards/PublicContextCard';
import {
  contextInput,
  contextPayloads,
  contextRegistry,
} from '../fixtures/public-context';
import { SourceChainDrawer } from '../../src/facts/SourceChainDrawer';
import { PublicLayers } from '../../src/stage/layers/PublicLayers';
import { sceneRegistry } from '../fixtures/layer-registry';
import type { LayerPayload } from '../../src/stage/layers/payload';
import type { FactRegistry } from '../../src/facts/registry';
import { AnswerShell } from '../../src/shell/AnswerShell';
import {
  completeInput,
  completeRegistry,
  factId,
  makeBinding,
  makeFact,
  makeLineage,
  makeSource,
  registryFrom,
} from '../fixtures/facts';

const params = new URLSearchParams(window.location.search);
const language = params.get('lang') === 'ar' ? 'ar' : 'en';
const theme = params.get('theme') === 'light' ? 'light' : 'dark';
const scene = params.get('scene');
const marked = params.get('marked') === '1';

/**
 * Separate withheld negative fixture; never a production Public success.
 * `plant=withheld-zero` shows the withheld record as a Public zero, a card
 * shown from withheld data, which the context-card specs must reject.
 */
function withheldContextRegistry() {
  const input = contextInput();
  const shown = params.get('plant') === 'withheld-zero';
  input.facts[0]!.fact.provenance = shown ? 'public' : 'suppressed';
  input.facts[0]!.fact.value = shown ? 0 : 987;
  return registryFrom(input);
}

/** The context scene records the fact a Source control opened. */
function recordOpen(id: string) {
  document.body.dataset.contextOpened = id;
}

const root = document.getElementById('root');
if (root === null) throw new Error('missing root');

const digits = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];

function mixedRegistry(): FactRegistry {
  const input = completeInput();
  const low = factId(1);
  const high = factId(2);
  return registryFrom({
    ...input,
    facts: [
      ...input.facts,
      makeBinding({ fact: makeFact({ fact_id: low, value: 12 }) }),
      makeBinding({ fact: makeFact({ fact_id: high, value: 40 }) }),
      makeBinding({
        fact: makeFact({ fact_id: factId(3), value: 24 }),
        presentation: 'estimated_count',
        rangeLowId: low,
        rangeHighId: high,
      }),
      makeBinding({
        fact: makeFact({ fact_id: factId(4), value: -6 }),
        presentation: 'change',
      }),
      makeBinding({
        fact: makeFact({ fact_id: factId(5), value: 12.5, unit: 'percent' }),
      }),
      makeBinding({
        fact: makeFact({ fact_id: factId(6), value: 18, unit: 'qar' }),
      }),
    ],
  });
}

const mixed = mixedRegistry();

function markedRegistry(): FactRegistry {
  const input = completeInput();
  return registryFrom({
    ...input,
    lineages: [makeLineage({ method: 'sample_method (v2)' })],
  });
}

const silence: (id: string) => void = () => undefined;

/**
 * The one-layer payload of the component fixtures, written out here: the
 * shared layer fixture reads source files and cannot load in a browser.
 */
function layerScene(): LayerPayload {
  return {
    layers: [
      {
        key: 'public_places',
        visible: true,
        source_chain_fact_id: factId(0),
        source_id: 'src_places',
        features: [
          {
            feature_id: 'feat_place_aleph',
            metric_key: 'place_listing',
            provenance: 'public',
            subject: 'place',
            geometry_kind: 'point',
            fact_id: factId(0),
          },
        ],
      },
    ],
    sources: [
      {
        sourceId: 'src_places',
        attribution: [{ kind: 'plain', text: 'Sample overture credit' }],
        retrievalDate: '2024-03-14',
        publisher: [{ kind: 'plain', text: 'Sample Publisher' }],
        datasetOrPage: 'Sample places page',
        licenceOrTerms: 'Terms recorded for this sample',
      },
    ],
    gazetteer_points: ['gx_sample_aleph'],
  };
}

function classRegistry(
  provenance: 'public' | 'synthetic' | 'simulated' | 'suppressed',
  status: 'observed' | 'inferred' | 'still_to_test',
) {
  const inputClass = provenance === 'suppressed' ? 'public' : provenance;
  const kind =
    inputClass === 'public'
      ? 'public_dataset'
      : inputClass === 'synthetic'
        ? 'synthetic_feed'
        : 'simulation_output';
  return registryFrom({
    ...completeInput(),
    facts: [
      makeBinding({
        fact: makeFact({
          provenance,
          evidence_status: status,
          input_classes: [inputClass],
          value: provenance === 'suppressed' ? null : 3,
        }),
      }),
    ],
    lineages: [makeLineage({ inputClasses: [inputClass] })],
    sources: [makeSource({ kind, inputClass })],
  });
}

function States() {
  const refused = registryFrom({
    ...completeInput(),
    facts: [makeBinding({ fact: makeFact({ lineage_ref: 'missing' }) })],
  });
  const loading = registryFrom({
    ...completeInput(),
    facts: [makeBinding({ loading: true })],
  });
  const composite = registryFrom({
    ...completeInput(),
    facts: [
      makeBinding({
        fact: makeFact({ input_classes: ['public', 'synthetic'] }),
      }),
    ],
    lineages: [
      makeLineage({
        inputClasses: ['public', 'synthetic'],
        sourceIds: ['src_alpha', 'src_beta'],
      }),
    ],
    sources: [
      makeSource({
        sourceId: 'src_alpha',
        kind: 'public_dataset',
        inputClass: 'public',
      }),
      makeSource({
        sourceId: 'src_beta',
        kind: 'synthetic_feed',
        inputClass: 'synthetic',
      }),
    ],
  });
  return (
    <section className="states" data-scene="states">
      <FactChip
        variant="value"
        size="hero"
        factId={factId(0)}
        registry={completeRegistry()}
        language={language}
        onOpen={silence}
      />
      <FactChip
        variant="value"
        size="standard"
        factId="fact_absent"
        registry={completeRegistry()}
        language={language}
        onOpen={silence}
      />
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={loading}
        language={language}
        onOpen={silence}
      />
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={refused}
        language={language}
        onOpen={silence}
      />
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={classRegistry('synthetic', 'observed')}
        language={language}
        onOpen={silence}
      />
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={classRegistry('simulated', 'inferred')}
        language={language}
        onOpen={silence}
      />
      <FactChip
        variant="value"
        size="standard"
        factId={factId(0)}
        registry={classRegistry('suppressed', 'still_to_test')}
        language={language}
        onOpen={silence}
      />
      <FactChip
        variant="value"
        size="inline"
        factId={factId(0)}
        registry={composite}
        language={language}
        onOpen={silence}
      />
    </section>
  );
}

function OpenedDrawer() {
  const mark = params.get('mark');
  const statusName = params.get('status');
  const provenance =
    mark === 'synthetic' || mark === 'simulated' || mark === 'suppressed'
      ? mark
      : 'public';
  const status =
    statusName === 'inferred' || statusName === 'still_to_test'
      ? statusName
      : 'observed';
  return (
    <SourceChainDrawer
      factId={factId(0)}
      registry={classRegistry(provenance, status)}
      language={language}
      receiptHref="https://example.invalid/receipt"
      onClose={silence}
    />
  );
}

createRoot(root).render(
  <StrictMode>
    <AnswerShell
      language={language}
      theme={theme}
      extractUrl={null}
      registry={marked ? markedRegistry() : completeRegistry()}
      receiptHref="https://example.invalid/receipt"
      draft={{
        catalogueVersion: catalogue.version,
        accountingPassed: true,
        subject: 'area',
        componentKey: 'foundation_note',
        props: [],
        directive: null,
        slots: [{ factId: factId(0), provenance: 'public', metric: 'people' }],
      }}
    />
    {scene === 'states' ? <States /> : null}
    {scene === 'context' && params.get('plant') === 'line-height' ? (
      <style data-plant="line-height">
        {'.public-context-card { line-height: 1.7; }'}
      </style>
    ) : null}
    {scene === 'context' ? (
      <section
        data-context-scene
        lang={language}
        dir={language === 'ar' ? 'rtl' : 'ltr'}
        data-theme={theme}
        style={{
          position: 'relative',
          zIndex: 1,
          marginInline: 'auto',
          inlineSize: 'min(90vw, 48rem)',
          display: 'grid',
          gap: '1rem',
        }}
      >
        {contextPayloads.map((payload) => (
          <PublicContextCard
            key={payload.family}
            payload={payload}
            language={language}
            registry={
              params.get('mark') === 'suppressed'
                ? withheldContextRegistry()
                : contextRegistry()
            }
            onOpen={recordOpen}
          />
        ))}
      </section>
    ) : null}
    {scene === 'open' ? <OpenedDrawer /> : null}
    {scene === 'layers' ? (
      <section
        data-layers-scene
        lang={language}
        dir={language === 'ar' ? 'rtl' : 'ltr'}
        data-theme={theme}
        style={{ position: 'fixed', inset: 0, zIndex: 1 }}
      >
        <PublicLayers
          payload={layerScene()}
          language={language}
          registry={sceneRegistry()}
          onOpenChain={silence}
        />
      </section>
    ) : null}
    <div
      data-plant="wrong-side"
      style={{
        position: 'fixed',
        insetInlineStart: 0,
        insetInlineEnd: 'auto',
        inlineSize: '448px',
        blockSize: '8px',
        opacity: 0,
        pointerEvents: 'none',
      }}
    />
    <section className="mixed-set">
      <p data-case="range" lang="ar" dir="rtl">
        المدى الظاهر{' '}
        <FactChip
          variant="value"
          size="inline"
          factId={factId(3)}
          registry={mixed}
          language="ar"
          onOpen={silence}
        />
      </p>
      <p data-case="negative" lang="ar" dir="rtl">
        التغير المسجل{' '}
        <FactChip
          variant="value"
          size="inline"
          factId={factId(4)}
          registry={mixed}
          language="ar"
          onOpen={silence}
        />
      </p>
      <p data-case="percent-en" lang="en" dir="ltr">
        <FactChip
          variant="value"
          size="inline"
          factId={factId(5)}
          registry={mixed}
          language="en"
          onOpen={silence}
        />
      </p>
      <p data-case="percent" lang="ar" dir="rtl">
        النسبة المعروضة{' '}
        <FactChip
          variant="value"
          size="inline"
          factId={factId(5)}
          registry={mixed}
          language="ar"
          onOpen={silence}
        />
      </p>
      <p data-case="currency" lang="ar" dir="rtl">
        المبلغ الظاهر{' '}
        <FactChip
          variant="value"
          size="inline"
          factId={factId(6)}
          registry={mixed}
          language="ar"
          onOpen={silence}
        />
      </p>
      <p data-case="place" lang="ar" dir="rtl">
        الاسم اللاتيني <bdi>Sample Reach</bdi>
      </p>
    </section>
    <p className="chip-num" data-measure="digits" lang="en" dir="ltr">
      {digits.map((digit) => (
        <span key={digit} data-digit={digit}>
          {digit}
        </span>
      ))}
    </p>
  </StrictMode>,
);
