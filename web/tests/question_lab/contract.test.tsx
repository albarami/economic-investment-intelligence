// @vitest-environment jsdom
/** S3-T21 box 8 / decision 0044 item 8(iv): the shared cross-surface
 * parity contract executed for cards and layout, with the speech and
 * ranking entry points the later executors call. Plants live in this
 * test only; the real catalogue files are never edited.
 */
import { cleanup, fireEvent, render } from '@testing-library/react';
import { JSDOM } from 'jsdom';
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import path from 'node:path';
import { afterAll, afterEach, expect, it } from 'vitest';
import { PublicContextCard } from '../../src/cards/PublicContextCard';
import { formatFactValue } from '../../src/facts/formatters';
import { catalogue, fragmentField } from '../../src/brief/catalogue';
import enJson from '../../src/i18n/en.json';
import arJson from '../../src/i18n/ar.json';
import {
  contextInput,
  contextPayloads,
  contextRegistry,
} from '../fixtures/public-context';
import {
  capturedCardsParity,
  cardsParity,
  catalogueSource,
  layoutParity,
  rankingParity,
  recordCapture,
  registerLabCaptures,
  sourceProblems,
  speechParity,
  type LabCase,
  type LabRun,
  type ReferenceKind,
  type ReferenceRecord,
  type SurfaceLine,
} from './contract';
import {
  answerArea,
  answerFactId,
  bridgeDump,
  chainReferences,
  nightLightsReferences,
  readReleaseDump,
  ReferenceSourceError,
  releaseReferences,
  runPython,
  type ReleaseDump,
  type ReleaseReferences,
} from './references';
import { CARD_STYLES } from './styles';

afterEach(cleanup);

type Payload = (typeof contextPayloads)[number];

function renderPair(payload: Payload) {
  const registry = contextRegistry();
  const containers = (['en', 'ar'] as const).map((language) => {
    const view = render(
      <PublicContextCard
        payload={payload}
        registry={registry}
        language={language}
        onOpen={() => undefined}
      />,
    );
    for (const level of ['comparison', 'evidence'])
      fireEvent.click(
        view.container.querySelector(
          `[data-context-level="${level}"] > button`,
        )!,
      );
    return view.container;
  });
  return {
    en: containers[0]!,
    ar: containers[1]!,
    refs: fixtureReferences(payload),
  };
}

/** The trusted reference records of one shipped card, read from the
 * fixture's own input rows (never from the rendered card): each reference
 * chip's record id, kind and raw value, in each record's chip order. */
function fixtureReferences(payload: Payload): ReferenceRecord[] {
  const input = contextInput();
  const fact = input.facts.find(
    (binding) => binding.fact.fact_id === payload.factId,
  )!.fact;
  const lineage = input.lineages.find(
    (row) => row.lineageId === fact.lineage_ref,
  )!;
  const refs: ReferenceRecord[] = [];
  const add = (record: string, kind: ReferenceKind, value: string) =>
    refs.push({ record, kind, value });
  if (payload.family === 'night_lights')
    add(payload.factId, 'calendar_month', String(fact.period));
  if (payload.family === 'population_age_sex') {
    add(payload.factId, 'calendar_year', String(fact.period));
    if (payload.ageBand !== null)
      add(payload.factId, 'published_text', payload.ageBand);
  }
  if (payload.family === 'venue_busyness') {
    add(payload.factId, 'published_text', payload.hour);
    add(payload.factId, 'calendar_date', payload.retrievedOn);
    if (payload.providerUpdatedOn !== null)
      add(payload.factId, 'calendar_date', payload.providerUpdatedOn);
  }
  return [
    ...refs,
    ...chainReferences({
      factId: fact.fact_id,
      tableName: lineage.tableName,
      lineageId: lineage.lineageId,
      method: lineage.method,
      methodVersion: lineage.methodVersion,
      sources: lineage.sourceIds.map((sourceId) =>
        input.sources.find((row) => row.sourceId === sourceId)!,
      ),
    }),
  ];
}

function template(key: string, language: 'en' | 'ar'): string {
  return fragmentField(key, `template_${language}`) ?? '';
}

it('S3-T21 the parity source holds both languages for every key and no English-only catalogue template', () => {
  expect(sourceProblems(catalogueSource())).toEqual([]);
});

it('S3-T21 the contract source enumerates the whole catalogue domain', () => {
  const entries = catalogueSource();
  const keys = new Set(entries.map((entry) => entry.key));
  for (const key of Object.keys(enJson.strings))
    expect(keys.has(`i18n:${key}`)).toBe(true);
  for (const key of Object.keys(arJson.strings))
    expect(keys.has(`i18n:${key}`)).toBe(true);
  for (const item of [
    ...catalogue.fragments,
    ...catalogue.questions,
    ...catalogue.claims,
  ]) {
    const itemKey = (item as { key?: unknown }).key;
    expect(typeof itemKey).toBe('string');
    const stems = entries.filter((entry) =>
      entry.key.split(':').slice(1).join(':').startsWith(`${itemKey}#`),
    );
    expect(stems.length).toBeGreaterThan(0);
    for (const stem of stems) {
      if (stem.en !== '') expect(stem.ar).not.toBe('');
      if (stem.ar !== '') expect(stem.en).not.toBe('');
    }
  }
});

it('S3-T21 the sanctioned identical bilingual values stay green', () => {
  const entries = catalogueSource();
  for (const key of [
    'i18n:drawer.title',
    'i18n:stage.attribution',
    'i18n:unit.percent',
  ]) {
    const entry = entries.find((item) => item.key === key);
    expect(entry?.en).toBe(entry?.ar);
  }
  expect(sourceProblems(entries)).toEqual([]);
});

for (const payload of contextPayloads) {
  it(`S3-T21 cross-surface card and layout parity: ${payload.family}`, () => {
    const pair = renderPair(payload);
    expect(cardsParity(pair.en, pair.ar, pair.refs)).toEqual([]);
    expect(layoutParity(pair.en, pair.ar, pair.refs, CARD_STYLES)).toEqual([]);
  });
}

it('S3-T21 a planted English-only string on a card fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  const caveat = pair.ar.querySelector('[data-caveat] bdi')!;
  caveat.textContent = template('night_lights_not_activity', 'en');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain(
    'english-in-arabic',
  );
});

it('S3-T21 a catalogue key missing in ar fails the source contract', () => {
  const missingFragment = catalogueSource().map((entry) =>
    entry.key === 'fragment:context_source#template'
      ? { ...entry, ar: '' }
      : entry,
  );
  expect(sourceProblems(missingFragment)).toContain('missing-language');
  const missingString = catalogueSource().map((entry) =>
    entry.key === 'i18n:chip.open' ? { ...entry, ar: '' } : entry,
  );
  expect(sourceProblems(missingString)).toContain('missing-language');
});

it('S3-T21 an English-only catalogue template fails the source contract', () => {
  const broken = catalogueSource().map((entry) =>
    entry.key === 'fragment:context_source#template'
      ? { ...entry, ar: entry.en }
      : entry,
  );
  expect(sourceProblems(broken)).toContain('english-only');
});

it('S3-T21 an English-only i18n value fails the source contract', () => {
  const broken = catalogueSource().map((entry) =>
    entry.key === 'i18n:chip.open' ? { ...entry, ar: entry.en } : entry,
  );
  expect(sourceProblems(broken)).toContain('english-only');
});

it('S3-T21 duplicate catalogue identities are rejected', () => {
  const entries = catalogueSource();
  expect(sourceProblems([...entries, entries[0]!])).toContain('duplicate-key');
  const pair = renderPair(contextPayloads[0]!);
  expect(
    cardsParity(pair.en, pair.ar, pair.refs, [...entries, entries[0]!]),
  ).toContain('duplicate-key');
});

it('S3-T21 fragment and claim identities are namespaced by catalogue kind', () => {
  const entries = catalogueSource();
  const fragment = entries.find(
    (entry) => entry.key === 'fragment:night_lights#template',
  );
  const claim = entries.find(
    (entry) => entry.key === 'claim:night_lights#template',
  );
  expect(fragment?.en).toBe('Night-time radiance');
  expect(claim?.en).toBe('Night-time radiance: {value}');
  const enLines: SurfaceLine[] = [
    {
      key: 'fragment:night_lights#template',
      text: template('night_lights', 'en'),
    },
  ];
  const arLines: SurfaceLine[] = [
    {
      key: 'claim:night_lights#template',
      text: template('night_lights', 'ar'),
    },
  ];
  expect(speechParity(enLines, arLines)).toContain('template-mismatch');
});

it('S3-T21 a key missing from the Arabic card fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar.querySelector('[data-caveat]')!.remove();
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('missing-key');
});

it('S3-T21 an extra key on the Arabic card fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  const clone = pair.ar.querySelector('[data-caveat]')!.cloneNode(true);
  pair.ar.querySelector('article')!.append(clone);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('extra-key');
});

it('S3-T21 a Fact-chip slot present in one language only fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar.querySelector('[data-fact-chip]')!.remove();
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('fact-slot');
});

it('S3-T21 a different Arabic component set fails the layout contract', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar.querySelector('[data-context-level="evidence"]')!.remove();
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('component');
});

it('S3-T21 an unmirrored Arabic root direction fails the layout contract', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar.querySelector('article')!.setAttribute('dir', 'ltr');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('direction');
});

it('S3-T21 a reordered Arabic string sequence fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  const article = pair.ar.querySelector('article')!;
  const caveat = pair.ar.querySelector('[data-caveat]')!;
  article.insertBefore(caveat, article.firstChild);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('key-order');
});

it('S3-T21 uncatalogued text on one side only fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  const extra = pair.ar.ownerDocument.createElement('p');
  extra.textContent = 'INVENTED uncatalogued sentence';
  pair.ar.querySelector('article')!.append(extra);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain(
    'uncatalogued-text',
  );
});

it('S3-T21 invented English swapped into an Arabic node fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar.querySelector('[data-caveat] bdi')!.textContent =
    'INVENTED English text';
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain(
    'uncatalogued-text',
  );
});

it('S3-T21 a bare numeral swapped into an Arabic node fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar.querySelector('[data-caveat] bdi')!.textContent = '42';
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('loose-numeral');
});

it('S3-T21 an English aria-label on an Arabic chip fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar
    .querySelector('[data-fact-chip="value"]')!
    .setAttribute('aria-label', 'Open the source chain');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain(
    'english-in-arabic',
  );
});

it('S3-T21 a missing aria-label on an Arabic chip fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar
    .querySelector('[data-fact-chip="value"]')!
    .removeAttribute('aria-label');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('missing-key');
});

it('S3-T21 a mismatched aria-label on an Arabic chip fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar
    .querySelector('[data-fact-chip="value"]')!
    .setAttribute('aria-label', arJson.strings['chip.refused']);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('extra-key');
});

it('S3-T21 an invented aria-label on an Arabic chip fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar
    .querySelector('[data-fact-chip="value"]')!
    .setAttribute('aria-label', 'INVENTED label');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain(
    'uncatalogued-text',
  );
});

it('S3-T21 an Arabic-only physical inline margin fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar
    .querySelector('[data-caveat]')!
    .setAttribute('style', 'margin-left: 0');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('physical-axis');
});

it('S3-T21 a reparented Arabic node fails even when preorder is kept', () => {
  const pair = renderPair(contextPayloads[0]!);
  const article = pair.ar.querySelector('article')!;
  const caveat = article.querySelector('[data-caveat]')!;
  article
    .querySelector('[data-context-level="evidence"] > div')!
    .append(caveat);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('component');
});

it('S3-T21 an identical wrong nested lang on both cards fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar])
    side.querySelector('.chip-num')!.setAttribute('lang', 'fr');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('direction');
});

it('S3-T21 a direction-scoped rule fails as a separate layout', () => {
  const pair = renderPair(contextPayloads[0]!);
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      '[dir="rtl"] .card { margin-inline-start: 1rem; }',
    ]),
  ).toContain('separate-layout');
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      ':lang(ar) .card { padding: 0; }',
    ]),
  ).toContain('separate-layout');
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      ':lang(ar) .card { letter-spacing: 0; }',
    ]),
  ).toEqual([]);
});

it('S3-T21 paired lab captures run through the contract like the browser path does', () => {
  const pair = renderPair(contextPayloads[0]!);
  const enDoc = new JSDOM(pair.en.querySelector('article')!.outerHTML).window
    .document;
  const arDoc = new JSDOM(pair.ar.querySelector('article')!.outerHTML).window
    .document;
  expect(cardsParity(enDoc, arDoc, pair.refs)).toEqual([]);
  expect(layoutParity(enDoc, arDoc, pair.refs, CARD_STYLES)).toEqual([]);
});

it('S3-T21 a physical axis property fails the layout contract', () => {
  const pair = renderPair(contextPayloads[0]!);
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, ['.plant { margin-left: 0; }']),
  ).toContain('physical-axis');
});

it('S3-T21 speech and ranking entry points execute the contract in one call each', () => {
  const enLines: SurfaceLine[] = [
    {
      key: 'fragment:context_source#template',
      text: template('context_source', 'en'),
      factIds: ['f_abc3d4e5f6a7b8c3d4e5f6a7b8c3d4'],
    },
  ];
  const arLines: SurfaceLine[] = [
    {
      key: 'fragment:context_source#template',
      text: template('context_source', 'ar'),
      factIds: ['f_abc3d4e5f6a7b8c3d4e5f6a7b8c3d4'],
    },
  ];
  expect(speechParity(enLines, arLines)).toEqual([]);
  expect(rankingParity(enLines, arLines)).toEqual([]);
});

it('S3-T21 a fact moved between aligned lines fails', () => {
  const enLines: SurfaceLine[] = [
    {
      key: 'fragment:context_source#template',
      text: template('context_source', 'en'),
      factIds: ['f_abc3d4e5f6a7b8c3d4e5f6a7b8c3d4'],
    },
    {
      key: 'fragment:night_lights_not_activity#template',
      text: template('night_lights_not_activity', 'en'),
    },
  ];
  const arLines: SurfaceLine[] = [
    {
      key: 'fragment:context_source#template',
      text: template('context_source', 'ar'),
    },
    {
      key: 'fragment:night_lights_not_activity#template',
      text: template('night_lights_not_activity', 'ar'),
      factIds: ['f_abc3d4e5f6a7b8c3d4e5f6a7b8c3d4'],
    },
  ];
  expect(speechParity(enLines, arLines)).toContain('fact-slot');
});

it('S3-T21 a chip moved between card lines fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  const chip = pair.ar.querySelectorAll('[data-fact-chip="reference"]')[1]!;
  pair.ar.querySelector('[data-caveat]')!.append(chip);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('fact-slot');
});

it('S3-T21 an English-only spoken line fails as English in Arabic and a template mismatch', () => {
  const enLines: SurfaceLine[] = [
    {
      key: 'fragment:context_source#template',
      text: template('context_source', 'en'),
    },
  ];
  const arLines: SurfaceLine[] = [
    {
      key: 'fragment:context_source#template',
      text: template('context_source', 'en'),
    },
  ];
  const problems = speechParity(enLines, arLines);
  expect(problems).toContain('english-in-arabic');
  expect(problems).toContain('template-mismatch');
});

it('S3-T21 an unknown declared key fails', () => {
  const enLines: SurfaceLine[] = [
    {
      key: 'fragment:context_source#template',
      text: template('context_source', 'en'),
    },
  ];
  const arLines: SurfaceLine[] = [
    { key: 'fragment:INVENTED#template', text: 'نص' },
  ];
  expect(speechParity(enLines, arLines)).toContain('unknown-key');
});

it('S3-T21 a spoken headline that drops a fact fails', () => {
  const enLines: SurfaceLine[] = [
    {
      key: 'fragment:context_source#template',
      text: template('context_source', 'en'),
      factIds: ['f_abc3d4e5f6a7b8c3d4e5f6a7b8c3d4'],
    },
  ];
  const arLines: SurfaceLine[] = [
    {
      key: 'fragment:context_source#template',
      text: template('context_source', 'ar'),
    },
  ];
  expect(speechParity(enLines, arLines)).toContain('fact-slot');
});

it('S3-T21 an English unit inside an Arabic Fact chip fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar.querySelector('.chip-unit')!.textContent =
    enJson.strings['unit.radiance_nw_cm2_sr']!;
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain(
    'english-in-arabic',
  );
});

it('S3-T21 invented text inside an Arabic Fact chip fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar.querySelector('.chip-unit')!.textContent = 'INVENTED unit word';
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain(
    'uncatalogued-text',
  );
});

it('S3-T21 a numeral inside an Arabic chip text node fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar.querySelector('.chip-unit')!.textContent = 'نانوواط 42';
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('loose-numeral');
});

it('S3-T21 a shared dir on both chip buttons does not exempt catalogue text', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar])
    side.querySelector('[data-fact-chip="value"]')!.setAttribute('dir', 'auto');
  pair.ar.querySelector('.chip-unit')!.textContent =
    enJson.strings['unit.radiance_nw_cm2_sr']!;
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain(
    'english-in-arabic',
  );
});

it('S3-T21 a shared dir on both chip buttons does not exempt accessible labels', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar])
    side.querySelector('[data-fact-chip="value"]')!.setAttribute('dir', 'auto');
  pair.ar
    .querySelector('[data-fact-chip="value"]')!
    .removeAttribute('aria-label');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('attr-slot');
});

it('S3-T21 a nested isolate claim inside a value chip does not exempt text', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar])
    side.querySelector('.chip-root')!.setAttribute('dir', 'auto');
  pair.ar.querySelector('.chip-unit')!.textContent =
    enJson.strings['unit.radiance_nw_cm2_sr']!;
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain(
    'english-in-arabic',
  );
});

it('S3-T21 changing both values of a sanctioned identical entry fails', () => {
  const broken = catalogueSource().map((entry) =>
    entry.key === 'i18n:drawer.title'
      ? {
          ...entry,
          en: 'INVENTED shared sentence',
          ar: 'INVENTED shared sentence',
        }
      : entry,
  );
  expect(sourceProblems(broken)).toContain('english-only');
});

it('S3-T21 an aria-label moved to title on an Arabic chip fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  const chip = pair.ar.querySelector('[data-fact-chip="value"]')!;
  const label = chip.getAttribute('aria-label')!;
  chip.removeAttribute('aria-label');
  chip.setAttribute('title', label);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('attr-slot');
});

it('S3-T21 an aria-label relocated to another Arabic element fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  const chip = pair.ar.querySelector('[data-fact-chip="value"]')!;
  const label = chip.getAttribute('aria-label')!;
  chip.removeAttribute('aria-label');
  pair.ar.querySelector('h2')!.setAttribute('aria-label', label);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('attr-slot');
});

it('S3-T21 an Arabic chip aria-label missing its unit constituent fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar
    .querySelector('[data-fact-chip="value"]')!
    .setAttribute('aria-label', arJson.strings['chip.open']!);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('attr-slot');
});

it('S3-T21 a changed numeral inside an Arabic chip aria-label fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  const chip = pair.ar.querySelector('[data-fact-chip="value"]')!;
  chip.setAttribute(
    'aria-label',
    chip.getAttribute('aria-label')!.replace('7', '9'),
  );
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('attr-slot');
});

it('S3-T21 a numeral inside a non-chip Arabic attribute fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar
    .querySelector('h2')!
    .setAttribute('title', `${arJson.strings['chip.open']} 42`);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('loose-numeral');
});

it('S3-T21 an Arabic chip aria-label residual gaining a unit symbol fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  const chip = pair.ar.querySelector('[data-fact-chip="value"]')!;
  chip.setAttribute(
    'aria-label',
    chip.getAttribute('aria-label')!.replace('7', '7%'),
  );
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('attr-slot');
});

it('S3-T21 a residual changed on both labels at once still fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar]) {
    const chip = side.querySelector('[data-fact-chip="value"]')!;
    chip.setAttribute(
      'aria-label',
      chip.getAttribute('aria-label')!.replace('7', '7%'),
    );
  }
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('attr-slot');
});

it('S3-T21 English language on the Arabic card root fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar.querySelector('article')!.setAttribute('lang', 'en');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('direction');
});

it('S3-T21 identical English language and direction on prose fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar]) {
    side.querySelector('[data-caveat]')!.setAttribute('lang', 'en');
    side.querySelector('[data-caveat]')!.setAttribute('dir', 'ltr');
  }
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('direction');
});

it('S3-T21 root language and direction relocated to a nested heading fail', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const [side, lang, dir] of [
    [pair.en, 'en', 'ltr'],
    [pair.ar, 'ar', 'rtl'],
  ] as const) {
    const article = side.querySelector('article')!;
    article.removeAttribute('lang');
    article.removeAttribute('dir');
    const heading = side.querySelector('h2')!;
    heading.setAttribute('lang', lang);
    heading.setAttribute('dir', dir);
  }
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('direction');
});

it('S3-T21 root language and direction relocated to a nested section fail', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const [side, lang, dir] of [
    [pair.en, 'en', 'ltr'],
    [pair.ar, 'ar', 'rtl'],
  ] as const) {
    const article = side.querySelector('article')!;
    article.removeAttribute('lang');
    article.removeAttribute('dir');
    const section = side.querySelector('[data-context-level="answer"]')!;
    section.setAttribute('lang', lang);
    section.setAttribute('dir', dir);
  }
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('direction');
});

it('S3-T21 a DOM surface with no configured root fails', () => {
  const enDoc = new JSDOM(`<div><p>${enJson.strings['chip.open']}</p></div>`)
    .window.document;
  const arDoc = new JSDOM(`<div><p>${arJson.strings['chip.open']}</p></div>`)
    .window.document;
  expect(cardsParity(enDoc, arDoc, [])).toContain('direction');
});

it('S3-T21 a language-conditioned spacing token fails as a separate layout', () => {
  const pair = renderPair(contextPayloads[0]!);
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      ':lang(ar) .card { --eii-space-3: 0px; }',
    ]),
  ).toContain('separate-layout');
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      '.public-context-card { gap: var(--eii-font-gap, 12px); }',
      ':lang(ar) .public-context-card { --eii-font-gap: 0px; }',
    ]),
  ).toContain('separate-layout');
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      ':lang(ar) .card { --eii-num-gap: 0; }',
    ]),
  ).toContain('separate-layout');
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      '.card { width: var(--eii-type-body); }',
      ':lang(ar) .card { --eii-type-body: 36px; }',
    ]),
  ).toContain('separate-layout');
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      ':lang(ar) .card { direction: ltr; }',
    ]),
  ).toContain('separate-layout');
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      ':lang(ar) .card { --eii-type-body: 400 36px/58px var(--eii-font-arabic); }',
    ]),
  ).toEqual([]);
});

/** Round-5 plants: one per CF3 counterexample and one more per class,
 * each a one-input change of a clean shipped pair. */
function relocateRoot(pair: { en: Element; ar: Element }): void {
  for (const side of [pair.en, pair.ar]) {
    const article = side.querySelector('article')!;
    const wrapper = side.ownerDocument.createElement('div');
    wrapper.setAttribute('lang', article.getAttribute('lang')!);
    wrapper.setAttribute('dir', article.getAttribute('dir')!);
    article.removeAttribute('lang');
    article.removeAttribute('dir');
    wrapper.append(...article.childNodes);
    article.append(wrapper);
  }
}

it('S3-T21 CF3-1 a shared chip-num class on both chip roots does not exempt an English unit', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar])
    side.querySelector('.chip-root')!.classList.add('chip-num');
  pair.ar.querySelector('.chip-unit')!.textContent =
    enJson.strings['unit.radiance_nw_cm2_sr']!;
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain(
    'english-in-arabic',
  );
});

it('S3-T21 round 5: an isolate enclosing the unit on both sides does not exempt it', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar]) {
    const num = side.querySelector('[data-fact-chip="value"] .chip-num')!;
    num.append(side.querySelector('.chip-unit')!);
  }
  pair.ar.querySelector('.chip-unit')!.textContent =
    enJson.strings['unit.radiance_nw_cm2_sr']!;
  const problems = cardsParity(pair.en, pair.ar, pair.refs);
  expect(problems).toContain('english-in-arabic');
  expect(problems).toContain('chip-variant');
});

it('S3-T21 round 5: a catalogue string passed as opaque isolate data fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar])
    side.querySelector('[data-kind="published_text"] .chip-num')!.textContent =
      enJson.strings['chip.open']!;
  const problems = cardsParity(pair.en, pair.ar, pair.refs);
  expect(problems).toContain('isolate-content');
  expect(problems).toContain('english-in-arabic');
});

it('S3-T21 round 5: an English date inside an Arabic calendar isolate fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  const en = pair.en.querySelector('[data-kind="calendar_month"] .chip-num')!;
  pair.ar.querySelector('[data-kind="calendar_month"] .chip-num')!.textContent =
    en.textContent;
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain(
    'english-in-arabic',
  );
});

it('S3-T21 round 5: a numeric isolate holding words instead of a value fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar]) {
    const chip = side.querySelector('[data-fact-chip="value"]')!;
    chip.querySelector('.chip-num')!.textContent = 'seven';
    chip.setAttribute(
      'aria-label',
      chip.getAttribute('aria-label')!.replace('7', 'seven'),
    );
  }
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('isolate-content');
});

it('S3-T21 round 5: opaque isolate data changed on one side fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar.querySelector('[data-kind="published_text"] .chip-num')!.textContent =
    'INVENTED other record';
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('fact-slot');
});

it('S3-T21 CF3-2 root language and direction moved to an enclosing inner wrapper fail', () => {
  const pair = renderPair(contextPayloads[0]!);
  relocateRoot(pair);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('direction');
});

it('S3-T21 round 5: a duplicate enclosing surface root fails', () => {
  const rendered = renderPair(contextPayloads[0]!);
  // Detached copies keep the rendered tree intact for cleanup.
  const pair = {
    en: rendered.en.cloneNode(true) as Element,
    ar: rendered.ar.cloneNode(true) as Element,
    refs: rendered.refs,
  };
  for (const side of [pair.en, pair.ar]) {
    const article = side.querySelector('article')!;
    const outer = article.cloneNode(false) as Element;
    article.replaceWith(outer);
    outer.append(article);
  }
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('direction');
});

it('S3-T21 round 5: a mirrored language pair outside the surface root fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.en.setAttribute('lang', 'en');
  pair.en.setAttribute('dir', 'ltr');
  pair.ar.setAttribute('lang', 'ar');
  pair.ar.setAttribute('dir', 'rtl');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('direction');
});

it('S3-T21 round 5: catalogue text outside the surface root fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const [side, language] of [
    [pair.en, 'en'],
    [pair.ar, 'ar'],
  ] as const) {
    const outside = side.ownerDocument.createElement('p');
    outside.textContent = (language === 'en' ? enJson : arJson).strings[
      'chip.open'
    ]!;
    side.append(outside);
  }
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('direction');
});

function editLabels(
  pair: { en: Element; ar: Element },
  edit: (label: string) => string,
) {
  for (const side of [pair.en, pair.ar]) {
    const chip = side.querySelector('[data-fact-chip="value"]')!;
    chip.setAttribute('aria-label', edit(chip.getAttribute('aria-label')!));
  }
}

it('S3-T21 CF3-3 the value removed from both chip labels fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  editLabels(pair, (label) => label.replace('7', ''));
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('attr-slot');
});

it('S3-T21 round 5: the value duplicated in both chip labels fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  editLabels(pair, (label) => `7 ${label}`);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('attr-slot');
});

it('S3-T21 round 5: the unit dropped from both chip labels fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.en
    .querySelector('[data-fact-chip="value"]')!
    .setAttribute('aria-label', `7 ${enJson.strings['chip.open']}`);
  pair.ar
    .querySelector('[data-fact-chip="value"]')!
    .setAttribute('aria-label', `7، ${arJson.strings['chip.open']}`);
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('attr-slot');
});

it('S3-T21 round 5: every one-character edit of the Arabic chip label fails', () => {
  // A seeded generator over the label's edit space: deletion, insertion
  // and replacement at every position; only the unchanged label passes.
  const pair = renderPair(contextPayloads[0]!);
  const chip = pair.ar.querySelector('[data-fact-chip="value"]')!;
  const label = chip.getAttribute('aria-label')!;
  const alphabet = ['7', ' ', '،', '9', 'x', 'ن', '%', ' '];
  let seed = 5202611;
  const next = () => (seed = (seed * 1103515245 + 12345) % 2147483648);
  for (let trial = 0; trial < 60; trial += 1) {
    const at = next() % (label.length + 1);
    const glyph = alphabet[next() % alphabet.length]!;
    const kind = next() % 3;
    const edited =
      kind === 0
        ? label.slice(0, at) + label.slice(at + 1)
        : kind === 1
          ? label.slice(0, at) + glyph + label.slice(at)
          : label.slice(0, at) + glyph + label.slice(at + 1);
    chip.setAttribute('aria-label', edited);
    const problems = cardsParity(pair.en, pair.ar, pair.refs);
    if (edited === label) expect(problems).toEqual([]);
    else expect(problems).toContain('attr-slot');
  }
});

it('S3-T21 CF3-4 a language-varied token consumed by geometry through an alias fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      '.card { --gap: var(--eii-type-body); width: var(--gap); }',
      ':lang(ar) .card { --eii-type-body: 36px; }',
    ]),
  ).toContain('separate-layout');
});

it('S3-T21 round 5: a two-hop fallback alias across stylesheets fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      ':root { --a: var(--unset, var(--eii-font-arabic)); }',
      '@media (min-width: 1px) { .card { --b: var(--a); } }',
      '.card { padding-inline: var(--b); }',
      ':lang(ar) .card { --eii-font-arabic: serif; }',
    ]),
  ).toContain('separate-layout');
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      ':root { --a: var(--unset, var(--eii-font-arabic)); }',
      '.card { --b: var(--a); font-family: var(--b); }',
      ':lang(ar) .card { --eii-font-arabic: serif; }',
    ]),
  ).toEqual([]);
});

it('S3-T21 round 5: alias chains of every depth reach geometry and fail', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (let depth = 1; depth <= 6; depth += 1) {
    const chain = Array.from({ length: depth }, (_, index) =>
      index === 0
        ? `--hop0: var(--eii-type-body);`
        : `--hop${index}: var(--none${index}, var(--hop${index - 1}));`,
    );
    const sheets = [
      // Declared dependent-first, so only a fixpoint closure reaches it.
      `.card { ${chain.reverse().join(' ')} }`,
      `.card { block-size: var(--hop${depth - 1}); }`,
      ':lang(ar) .card { --eii-type-body: 36px; }',
    ];
    expect(layoutParity(pair.en, pair.ar, pair.refs, sheets)).toContain(
      'separate-layout',
    );
    expect(
      layoutParity(pair.en, pair.ar, pair.refs, [
        sheets[0]!,
        `.card { font: var(--hop${depth - 1}); }`,
        sheets[2]!,
      ]),
    ).toEqual([]);
  }
});

it('S3-T21 round 5 self-review: a catalogue sentence inside opaque isolate data fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar])
    side.querySelector('[data-kind="published_text"] .chip-num')!.textContent =
      `${template('night_lights_not_activity', 'en')}.`;
  const problems = cardsParity(pair.en, pair.ar, pair.refs);
  expect(problems).toContain('isolate-content');
  expect(problems).toContain('english-in-arabic');
});

it('S3-T21 round 5 self-review: geometry nested inside a :lang block fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      ':lang(ar) { .card { width: 0; } }',
    ]),
  ).toContain('separate-layout');
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      '.card { inline-size: var(--w); }',
      ':lang(ar) { .card { --w: 0; } }',
    ]),
  ).toContain('separate-layout');
});

it('S3-T21 round 5 self-review: an upper-case VAR reference to a varied token fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      '.card { --gap: VAR(--eii-type-body); width: Var(--gap); }',
      ':lang(ar) .card { --eii-type-body: 36px; }',
    ]),
  ).toContain('separate-layout');
});

function plantedArPair() {
  const pair = renderPair(contextPayloads[0]!);
  const enHtml = pair.en.querySelector('article')!.outerHTML;
  const cleanAr = pair.ar.querySelector('article')!.outerHTML;
  pair.ar.querySelector('[data-caveat] bdi')!.textContent =
    'INVENTED English text';
  return {
    enHtml,
    cleanAr,
    plantedAr: pair.ar.querySelector('article')!.outerHTML,
  };
}

function runCapture(
  pairedCards: Map<string, string>,
  pairKey: string,
  language: 'en' | 'ar',
  cardHtml: string | null,
) {
  const emitted: string[] = [];
  let failure: unknown = null;
  try {
    recordCapture(
      {
        pairedCards,
        pairKey,
        language,
        cardHtml,
        trusted: fixtureReferences(contextPayloads[0]!),
        styles: CARD_STYLES,
        fields: { question_id: 'q-invented', card_html: cardHtml },
      },
      (json) => emitted.push(json),
    );
  } catch (error) {
    failure = error;
  }
  return { emitted, failure };
}

it('S3-T21 CF3-5 the shared capture operation records the planted diagnostic and fails', () => {
  const { enHtml, cleanAr, plantedAr } = plantedArPair();
  const pairedCards = new Map<string, string>();
  const en = runCapture(pairedCards, 'q-answer', 'en', enHtml);
  expect(en.failure).toBeNull();
  expect(en.emitted).toHaveLength(1);
  expect(JSON.parse(en.emitted[0]!)).not.toHaveProperty('parity_problems');
  const clean = runCapture(pairedCards, 'q-answer', 'ar', cleanAr);
  expect(clean.failure).toBeNull();
  expect(JSON.parse(clean.emitted[0]!).parity_problems).toEqual([]);
  const planted = runCapture(pairedCards, 'q-answer', 'ar', plantedAr);
  expect(planted.emitted).toHaveLength(1);
  const record = JSON.parse(planted.emitted[0]!);
  expect(record.question_id).toBe('q-invented');
  expect(record.card_html).toBe(plantedAr);
  expect(record.parity_problems).toContain('uncatalogued-text');
  expect(String(planted.failure)).toContain('uncatalogued-text');
  // An unpaired or missing card records its own diagnostic and fails.
  const unpaired = runCapture(new Map(), 'q-none', 'ar', plantedAr);
  expect(JSON.parse(unpaired.emitted[0]!).parity_problems).toEqual([
    'parity:pair-missing',
  ]);
  expect(String(unpaired.failure)).toContain('parity:pair-missing');
  const missing = runCapture(pairedCards, 'q-answer', 'ar', null);
  expect(JSON.parse(missing.emitted[0]!).parity_problems).toEqual([
    'parity:card-missing',
  ]);
  expect(String(missing.failure)).toContain('parity:card-missing');
});

it('S3-B12 r10: a state with no card in either language fails closed, not open', () => {
  // No card-less state is declared in evals/question_lab/cases.v1.json,
  // so under the lead's ruling every lab state must show a card in both
  // languages and two null cards are a defect, never a silent pass.
  const { enHtml, cleanAr } = plantedArPair();
  const pairedCards = new Map<string, string>();
  const en = runCapture(pairedCards, 'q-answer', 'en', null);
  expect(en.failure).toBeNull();
  expect(en.emitted).toHaveLength(1);
  expect(JSON.parse(en.emitted[0]!)).not.toHaveProperty('parity_problems');
  const bothNull = runCapture(pairedCards, 'q-answer', 'ar', null);
  expect(bothNull.emitted).toHaveLength(1);
  expect(JSON.parse(bothNull.emitted[0]!).parity_problems).toEqual([
    'parity:card-missing',
    'parity:pair-missing',
  ]);
  expect(String(bothNull.failure)).toBe(
    'Error: parity_problems: parity:card-missing, parity:pair-missing',
  );
  // Each neighbouring cell of the changed branch keeps its own exact
  // code: the ar card renders (pair still absent), then the en card
  // renders (pair present, ar card gone).
  const arOnly = runCapture(pairedCards, 'q-answer', 'ar', cleanAr);
  expect(JSON.parse(arOnly.emitted[0]!).parity_problems).toEqual([
    'parity:pair-missing',
  ]);
  expect(String(arOnly.failure)).toBe(
    'Error: parity_problems: parity:pair-missing',
  );
  runCapture(pairedCards, 'q-answer', 'en', enHtml);
  const arNull = runCapture(pairedCards, 'q-answer', 'ar', null);
  expect(JSON.parse(arNull.emitted[0]!).parity_problems).toEqual([
    'parity:card-missing',
  ]);
  expect(String(arNull.failure)).toBe(
    'Error: parity_problems: parity:card-missing',
  );
});

it('S3-T21 CF3-5 the browser capture records only through the shared matrix', () => {
  const spec = readFileSync('tests/question_lab/answers.spec.ts', 'utf8');
  expect(spec).toMatch(
    /import \{\s*registerLabCaptures,[^}]*\} from '[.][/]contract';/,
  );
  expect(spec.match(/registerLabCaptures\b/g)).toHaveLength(2);
  expect(spec).toMatch(
    /sink: \(name, json\) => writeFileSync\(path\.join\(OUTPUT, name\), json\)/,
  );
  // The matrix receives every case, size and theme and registers each
  // test unfiltered, so no language can be dropped before it runs.
  expect(spec).toMatch(
    /registerLabCaptures<LabCase, Fixtures>\(\{\s*cases: cases\.cases,\s*sizes: QUESTION_LAB_SIZES,\s*themes: \['dark', 'light'\],\s*styles: CARD_STYLES,\s*register: \(title, body\) =>\s*test\(title, \(\{ page, mounted \}\) => body\(\{ page, mounted \}\)\),\s*drive,\s*snapshot,/,
  );
  // Nothing else in the spec records, serializes or touches the diagnostic.
  for (const bypass of [
    'recordCapture',
    'capturedCardsParity',
    'parity_problems',
    'parityCapture',
    'enforceParity',
    'JSON.stringify',
    'allSettled',
  ])
    expect(spec).not.toContain(bypass);
  // Enforcement is never swallowed.
  expect(spec).not.toMatch(/\btry\b|\bcatch\b|\.finally\(/);
  expect(spec.match(/writeFileSync\(/g)).toHaveLength(1);
});

/** Round-6 plants: one per CF4 counterexample and one more per refusal
 * branch, each a one-input change of a clean shipped pair. */
const PUBLISHED = '[data-kind="published_text"] .chip-num';
const CALENDAR = '[data-kind="calendar_month"] .chip-num';

function setBoth(
  pair: { en: Element; ar: Element },
  selector: string,
  text: string,
) {
  for (const side of [pair.en, pair.ar])
    side.querySelector(selector)!.textContent = text;
}

it('S3-T21 CF4-1 a whitespace variant of the action in opaque data fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  setBoth(pair, PUBLISHED, 'Open  the  source  chain');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('fact-slot');
});

it('S3-T21 CF4-1 a single catalogue word in opaque data on both sides fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  setBoth(pair, PUBLISHED, 'Source');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('fact-slot');
});

it('S3-T21 round 6: a reference chip with no trusted record fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar])
    side
      .querySelector('[data-kind="published_text"]')!
      .setAttribute('data-record', 'INVENTED-record');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain(
    'reference-unbound',
  );
});

it('S3-T21 round 6: a trusted record of another kind does not bind', () => {
  const pair = renderPair(contextPayloads[0]!);
  // The retrieval date read as published text formats, so only the kind
  // check keeps it from binding.
  const refs = pair.refs.map((ref) =>
    ref.kind === 'calendar_date'
      ? { ...ref, kind: 'published_text' as const }
      : ref,
  );
  expect(cardsParity(pair.en, pair.ar, refs)).toContain('reference-unbound');
});

it('S3-T21 round 6: a trusted record whose value does not format does not bind', () => {
  const pair = renderPair(contextPayloads[0]!);
  const refs = pair.refs.map((ref) =>
    ref.kind === 'calendar_month' ? { ...ref, value: 'INVENTED' } : ref,
  );
  expect(cardsParity(pair.en, pair.ar, refs)).toContain('reference-unbound');
});

it('S3-T21 round 6: a trusted record no chip rendered fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  const refs = [
    ...pair.refs,
    {
      record: pair.refs[0]!.record,
      kind: 'published_text' as const,
      value: 'x',
    },
  ];
  expect(cardsParity(pair.en, pair.ar, refs)).toEqual(['reference-missing']);
});

it('S3-T21 round 6: a bound published value colliding with catalogue words passes', () => {
  const pair = renderPair(contextPayloads[0]!);
  const first = pair.en.querySelector(PUBLISHED)!.textContent!;
  const collision = enJson.strings['chip.open']!;
  setBoth(pair, PUBLISHED, collision);
  const refs = pair.refs.map((ref) =>
    ref.value === first ? { ...ref, value: collision } : ref,
  );
  expect(cardsParity(pair.en, pair.ar, refs)).toEqual([]);
});

it('S3-T21 CF4-2 an emptied Arabic calendar isolate fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  pair.ar.querySelector(CALENDAR)!.textContent = '';
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('isolate-content');
});

it('S3-T21 CF4-2 another valid Arabic month in the calendar isolate fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  const other = formatFactValue('2024-02', 'calendar_month', 'ar', 'reference');
  expect(other.ok).toBe(true);
  pair.ar.querySelector(CALENDAR)!.textContent = other.ok ? other.text : '';
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toContain('fact-slot');
});

it('S3-T21 round 6: every sampled one-character edit of a bound isolate fails', () => {
  // A seeded generator over deletion, insertion and replacement in the
  // Arabic calendar and opaque isolates; only the unchanged text passes.
  const pair = renderPair(contextPayloads[0]!);
  const alphabet = [' ', '٢', '2', 'ن', 'a', '-', ' '];
  let seed = 6202611;
  const next = () => (seed = (seed * 1103515245 + 12345) % 2147483648);
  for (const selector of [CALENDAR, PUBLISHED]) {
    const node = pair.ar.querySelector(selector)!;
    const text = node.textContent!;
    for (let trial = 0; trial < 40; trial += 1) {
      const at = next() % (text.length + 1);
      const glyph = alphabet[next() % alphabet.length]!;
      const kind = next() % 3;
      const edited =
        kind === 0
          ? text.slice(0, at) + text.slice(at + 1)
          : kind === 1
            ? text.slice(0, at) + glyph + text.slice(at)
            : text.slice(0, at) + glyph + text.slice(at + 1);
      node.textContent = edited;
      const problems = cardsParity(pair.en, pair.ar, pair.refs);
      if (edited === text) expect(problems).toEqual([]);
      else expect(problems).toContain('fact-slot');
    }
    node.textContent = text;
  }
});

it('S3-T21 CF4-3 element-free DOM captures need the surface root', () => {
  const doc = new JSDOM('').window.document;
  expect(
    cardsParity(doc.createDocumentFragment(), doc.createDocumentFragment(), []),
  ).toEqual(['direction']);
  const enOnly = doc.createDocumentFragment();
  enOnly.append(enJson.strings['chip.open']!);
  const arOnly = doc.createDocumentFragment();
  arOnly.append(arJson.strings['chip.open']!);
  expect(cardsParity(enOnly, arOnly, [])).toEqual(['direction']);
});

it('S3-T21 CF4-4 an escaped property name in a :lang rule fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      ':lang(ar) .card { w\\69 dth: 0; }',
    ]),
  ).toContain('css-escape');
});

it('S3-T21 CF4-4 a non-ASCII alias of a language-varied token fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      '.card { --مسافة: var(--eii-type-body); width: var(--مسافة); }',
      ':lang(ar) .card { --eii-type-body: 36px; }',
    ]),
  ).toContain('css-non-ascii');
});

it('S3-T21 round 6: CSS the reader does not support is refused', () => {
  const pair = renderPair(contextPayloads[0]!);
  const layout = (css: string) =>
    layoutParity(pair.en, pair.ar, pair.refs, [css]);
  for (const css of [
    '@supports (display: grid) { .card { width: 0; } }',
    '@import "invented.css";',
    '.card::before { width: 0; }',
    '.card:nth-child(2) { width: 0; }',
    '.card[data-x~="y"] { width: 0; }',
    '.card { width 0; }',
    'width: 0;',
    '.card { width: 0;',
    '.card { width: 0; } }',
    '.card { --x: (a;b:c); }',
    '.card { width: 0; } "open',
    '.card { width: 0; } /* open comment',
    '@keyframes k { middle { opacity: 0; } }',
    '.card > > p { width: 0; }',
    '.card ..x { width: 0; }',
    ':lang(ar ar) .card { letter-spacing: 0; }',
    '.card, { width: 0; }',
    '.card:hover(x) { width: 0; }',
    '.card:has .x { width: 0; }',
    '.card|x { width: 0; }',
    '.card: p { width: 0; }',
    '.card:checked { width: 0; }',
  ])
    expect(layout(css), css).toContain('css-unsupported');
  expect(layout('.card { content: "\\201C"; }')).toContain('css-escape');
  // A string may hold non-ASCII text; it is not an identifier.
  expect(layout(".card { quotes: '«' '»'; }")).toEqual([]);
});

it('S3-T21 round 6: custom-property names keep their case', () => {
  const pair = renderPair(contextPayloads[0]!);
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      ':lang(ar) .card { --EII-TYPE-BODY: 0px; }',
    ]),
  ).toContain('separate-layout');
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      '.card { width: var(--EII-type-body); }',
      ':lang(ar) .card { --eii-type-body: 36px; }',
    ]),
  ).toEqual([]);
});

it('S3-T21 round 6: a sampled escape or non-ASCII letter anywhere in a rule is refused', () => {
  const pair = renderPair(contextPayloads[0]!);
  const clean = '.card > p:focus-visible { inline-size: var(--eii-space-3); }';
  expect(layoutParity(pair.en, pair.ar, pair.refs, [clean])).toEqual([]);
  let seed = 6202612;
  const next = () => (seed = (seed * 1103515245 + 12345) % 2147483648);
  for (let trial = 0; trial < 60; trial += 1) {
    const at = next() % (clean.length + 1);
    const [glyph, code] =
      next() % 2 === 0 ? ['\\', 'css-escape'] : ['م', 'css-non-ascii'];
    const css = clean.slice(0, at) + glyph + clean.slice(at);
    expect(layoutParity(pair.en, pair.ar, pair.refs, [css]), css).toContain(
      code,
    );
  }
});

function inlineBoth(pair: { en: Element; ar: Element }, style: string) {
  for (const side of [pair.en, pair.ar])
    side.querySelector('article')!.setAttribute('style', style);
}

// CF5 / CF4-5: the plants run on the exact stylesheet input the browser
// capture uses, whose language-conditioned token definitions come from the
// application's own `tokens.css`; no artificial `:lang` sheet is supplied.
it('S3-T21 CF5 the card stylesheet input is the application token sheet plus the card sheets', () => {
  const main = readFileSync('src/main.tsx', 'utf8');
  const loaded = [
    ...main.matchAll(/^import '[.][/](styles[/][a-z-]+[.]css)';$/gm),
  ].map((use) => 'src/' + use[1]!);
  expect(loaded).toEqual(['src/styles/tokens.css', 'src/styles/answer.css']);
  expect(CARD_STYLES).toEqual([
    ...loaded.map((file) => readFileSync(file, 'utf8')),
    readFileSync('src/cards/public-context.css', 'utf8'),
  ]);
  const spec = readFileSync('tests/question_lab/answers.spec.ts', 'utf8');
  expect(spec).toMatch(/^import [{] CARD_STYLES [}] from '[.][/]styles';$/m);
  expect(spec).not.toMatch(/[.]css'/);
});

it('S3-T21 CF5 a captured inline geometry consumer of a shipped varied token fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  inlineBoth(pair, 'inline-size:var(--eii-type-body)');
  expect(cardsParity(pair.en, pair.ar, pair.refs)).toEqual([]);
  expect(layoutParity(pair.en, pair.ar, pair.refs, CARD_STYLES)).toContain(
    'separate-layout',
  );
});

it('S3-T21 CF5 a captured inline alias of a shipped varied token consumed by geometry fails', () => {
  const pair = renderPair(contextPayloads[0]!);
  inlineBoth(pair, '--w: var(--eii-type-body); inline-size: var(--w)');
  expect(layoutParity(pair.en, pair.ar, pair.refs, CARD_STYLES)).toContain(
    'separate-layout',
  );
  inlineBoth(pair, '--w: var(--eii-type-body); font-size: var(--w)');
  expect(layoutParity(pair.en, pair.ar, pair.refs, CARD_STYLES)).toEqual([]);
});

it('S3-T21 CF5 the captured articles with the shipped styles and no plant stay clean', () => {
  for (const payload of contextPayloads) {
    const pair = renderPair(payload);
    expect(layoutParity(pair.en, pair.ar, pair.refs, CARD_STYLES)).toEqual([]);
    inlineBoth(pair, 'inline-size:var(--eii-space-3)');
    expect(layoutParity(pair.en, pair.ar, pair.refs, CARD_STYLES)).toEqual([]);
  }
});

// A token declared only by bare `:root` rules and, after them, by rules
// whose selector list is exactly `:root` plus bare `:lang(...)` branches
// (the same list every time, an integer pixel length) has the same value
// at the root and at every element of those languages, so it is not
// language-varied. Each negative case changes one input of that clean
// control and keeps the rest.
const PAIRED_ROOT = ':root { --r: 4px; }';
const PAIRED = '@media (max-width: 1599px) { :root, :lang(en) { --r: 3px; } }';
const PAIRED_USE = '.card { outline-width: var(--r); inline-size: var(--r); }';

it('S3-T21 CF5 a root-paired literal token is not language-varied', () => {
  const pair = renderPair(contextPayloads[0]!);
  expect(
    layoutParity(pair.en, pair.ar, pair.refs, [
      PAIRED_ROOT,
      PAIRED,
      PAIRED_USE,
    ]),
  ).toEqual([]);
});

for (const [name, sheets] of [
  ['a bare :lang rule', [PAIRED_ROOT, ':lang(en) { --r: 3px; }', PAIRED_USE]],
  [
    'a non-bare branch',
    [PAIRED_ROOT, ':root, :lang(en) .card { --r: 3px; }', PAIRED_USE],
  ],
  ['a later bare :root rule', [PAIRED, PAIRED_ROOT, PAIRED_USE]],
  [
    'a second paired list',
    [PAIRED_ROOT, PAIRED, ':root, :lang(ar) { --r: 5px; }', PAIRED_USE],
  ],
  [
    'an !important value',
    [PAIRED_ROOT, ':root, :lang(en) { --r: 3px !important; }', PAIRED_USE],
  ],
  [
    'a referencing value',
    [PAIRED_ROOT, ':root, :lang(en) { --r: var(--eii-space-1); }', PAIRED_USE],
  ],
  [
    'a nested rule',
    [PAIRED_ROOT, '.card { :root, :lang(en) { --r: 3px; } }', PAIRED_USE],
  ],
  [
    'a media query nested in a rule',
    [
      PAIRED_ROOT,
      '.card { @media (max-width: 1px) { :root, :lang(en) { --r: 3px; } } }',
      PAIRED_USE,
    ],
  ],
  [
    'another declaring rule',
    [PAIRED_ROOT, PAIRED, '.card { --r: 9px; }', PAIRED_USE],
  ],
] as const)
  it(`S3-T21 CF5 a root-paired token with ${name} is a separate layout`, () => {
    const pair = renderPair(contextPayloads[0]!);
    expect(layoutParity(pair.en, pair.ar, pair.refs, sheets)).toContain(
      'separate-layout',
    );
  });

it('S3-T21 CF5 a captured inline declaration of a root-paired token makes it varied', () => {
  const pair = renderPair(contextPayloads[0]!);
  const sheets = [PAIRED_ROOT, PAIRED, PAIRED_USE];
  inlineBoth(pair, '--r: 3px');
  expect(layoutParity(pair.en, pair.ar, pair.refs, sheets)).toContain(
    'separate-layout',
  );
});

// CF6: `attr()` and every other value outside the integer-pixel grammar
// stays language-varied. Each case changes only the paired value of the
// clean control above.
const OUTSIDE_PAIRED = [
  'attr(data-width px, 64px)',
  'calc(100% - 4px)',
  'calc(4px)',
  'env(safe-area-inset-top)',
  'currentcolor',
  'inherit',
  'unset',
  'revert',
  '1em',
  '1rem',
  '10%',
  '1ch',
  '1vw',
  'mod(4, 2)',
  '4.5px',
  '4PX',
  '-4px',
  '0',
  '4ms',
] as const;

for (const value of OUTSIDE_PAIRED)
  it(`S3-T21 CF6 a root-paired value ${value} stays language-varied`, () => {
    const pair = renderPair(contextPayloads[0]!);
    expect(
      layoutParity(pair.en, pair.ar, pair.refs, [
        PAIRED_ROOT,
        `@media (max-width: 1599px) { :root, :lang(en) { --r: ${value}; } }`,
        PAIRED_USE,
      ]),
    ).toEqual(['separate-layout']);
  });

const ATTR_ROOT = ':root { --r: 4px; }';
const ATTR_LANG = ':root, :lang(en) { --r: attr(data-width px, 64px); }';
const ATTR_USE = '.public-context-card { inline-size: var(--r); }';

function widthPair() {
  const pair = renderPair(contextPayloads[0]!);
  for (const side of [pair.en, pair.ar])
    side.querySelector('article')!.setAttribute('data-width', '128');
  return pair;
}

function articleHtml(root: Element): string {
  return root.querySelector('article')!.outerHTML;
}

function attrSheets(direct: boolean): string[] {
  return [...CARD_STYLES, ATTR_ROOT, ATTR_LANG, ...(direct ? [ATTR_USE] : [])];
}

it('S3-T21 CF6 a direct attr() consumer of a root-paired token is a separate layout', () => {
  const pair = widthPair();
  expect(layoutParity(pair.en, pair.ar, pair.refs, attrSheets(true))).toEqual([
    'separate-layout',
  ]);
});

it('S3-T21 CF6 an inline alias of an attr() root-paired token is a separate layout', () => {
  const pair = widthPair();
  inlineBoth(pair, '--w: var(--r); inline-size: var(--w)');
  expect(layoutParity(pair.en, pair.ar, pair.refs, attrSheets(false))).toEqual([
    'separate-layout',
  ]);
});

it('S3-T21 CF6 the captured path refuses a direct attr() consumer', () => {
  const pair = widthPair();
  expect(
    capturedCardsParity(
      articleHtml(pair.en),
      articleHtml(pair.ar),
      pair.refs,
      attrSheets(true),
    ),
  ).toEqual(['separate-layout']);
});

it('S3-T21 CF6 the captured path refuses an inline alias of attr()', () => {
  const pair = widthPair();
  inlineBoth(pair, '--w: var(--r); inline-size: var(--w)');
  expect(
    capturedCardsParity(
      articleHtml(pair.en),
      articleHtml(pair.ar),
      pair.refs,
      attrSheets(false),
    ),
  ).toEqual(['separate-layout']);
});

// Soundness over the whole rule space: a seeded generator draws one to
// four rules declaring `--r` and an independent cascade oracle evaluates
// them on every root-to-leaf chain of languages (all selectors here have
// equal specificity, so source order decides within the normal and the
// `!important` layer). Values are drawn from inside the integer-pixel
// grammar and from outside it (`attr()`, keywords, relative units). An
// outside value is bound to the element where its declaration applied:
// a descendant that inherits it keeps the ancestor's result, and a
// matching `:lang` rule evaluates it again. Whenever the contract does
// not refuse a geometry consumer of `--r`, swapping en and ar on any
// chain changes no value.
const FORMS = [
  [':root', (lang: string, root: boolean) => root],
  [':root, :lang(en)', (lang: string, root: boolean) => root || lang === 'en'],
  [':root, :lang(ar)', (lang: string, root: boolean) => root || lang === 'ar'],
  [':lang(en)', (lang: string) => lang === 'en'],
  [':lang(ar)', (lang: string) => lang === 'ar'],
  ['.card', (lang: string, root: boolean, card: boolean) => card],
] as const;
const INSIDE_GRAMMAR = ['1px', '2px', '3px'] as const;
const OUTSIDE_GRAMMAR = [
  'attr(data-width px, 64px)',
  'inherit',
  'unset',
  'revert',
  'currentcolor',
  '1em',
  '1rem',
  '10%',
  '1ch',
  '1vw',
  'calc(100% - 4px)',
  'env(safe-area-inset-top)',
  'mod(4, 2)',
] as const;
type Drawn = {
  form: number;
  value: string;
  bound: boolean;
  important: boolean;
};

function cascade(rules: Drawn[], chain: string[]): string[] {
  const values: string[] = [];
  let inherited = 'initial';
  chain.forEach((_own, depth) => {
    const lang =
      chain
        .slice(0, depth + 1)
        .filter(Boolean)
        .at(-1) ?? '';
    const hits = rules.filter((rule) =>
      FORMS[rule.form]![1](lang, depth === 0, depth === 1),
    );
    const win = [
      ...hits.filter((r) => !r.important),
      ...hits.filter((r) => r.important),
    ].at(-1);
    if (win !== undefined)
      inherited = win.bound ? `${win.value}@${depth}` : win.value;
    values.push(inherited);
  });
  return values;
}

function languageDependent(rules: Drawn[]): boolean {
  const langs = ['', 'en', 'ar'];
  const swap = (lang: string) => ({ en: 'ar', ar: 'en' })[lang] ?? lang;
  for (const root of ['en', 'ar'])
    for (const a of langs)
      for (const b of langs)
        for (const c of langs) {
          const chain = [root, a, b, c];
          if (
            cascade(rules, chain).join() !==
            cascade(rules, chain.map(swap)).join()
          )
            return true;
        }
  return false;
}

it('S3-T21 CF5 property: the root-paired exemption never clears a language-dependent token', () => {
  const pair = renderPair(contextPayloads[0]!);
  let seed = 2026112305;
  // The high bits: the low bits of this generator cycle with a short period.
  const next = (n: number) =>
    Math.floor((seed = (seed * 1103515245 + 12345) % 2147483648) / 65536) % n;
  const seen = { cleared: 0, dependent: 0 };
  for (let trial = 0; trial < 400; trial += 1) {
    const rules = Array.from({ length: 1 + next(4) }, (): Drawn => {
      const bound = next(2) === 0;
      const pool = bound ? OUTSIDE_GRAMMAR : INSIDE_GRAMMAR;
      return {
        form: next(FORMS.length),
        value: pool[next(pool.length)]!,
        bound,
        important: next(5) === 0,
      };
    });
    const sheets = [
      ...rules.map(
        (r) =>
          `${FORMS[r.form]![0]} { --r: ${r.value}${r.important ? ' !important' : ''}; }`,
      ),
      '.card { inline-size: var(--r); }',
    ];
    const dependent = languageDependent(rules);
    if (dependent) seen.dependent += 1;
    if (
      !layoutParity(pair.en, pair.ar, pair.refs, sheets).includes(
        'separate-layout',
      )
    ) {
      seen.cleared += 1;
      expect(dependent, sheets.join(' ')).toBe(false);
    }
  }
  expect(seen.cleared).toBeGreaterThan(20);
  expect(seen.dependent).toBeGreaterThan(20);
});

it('S3-T21 round 6: an inline style the reader cannot read is refused', () => {
  const pair = renderPair(contextPayloads[0]!);
  inlineBoth(pair, 'w\\69 dth: var(--eii-type-body)');
  expect(layoutParity(pair.en, pair.ar, pair.refs, CARD_STYLES)).toContain(
    'css-escape',
  );
  inlineBoth(pair, '.card { width: 0 }');
  expect(layoutParity(pair.en, pair.ar, pair.refs, CARD_STYLES)).toContain(
    'css-unsupported',
  );
});

type MatrixFixtures = { label: string };

/** The browser capture matrix run offline: one invented question, one
 * size and theme; the en and ar tests capture the given card markup. */
function offlineMatrix(
  cards: { en: string | null; ar: string | null },
  drive: (run: LabRun<LabCase>) => Promise<void>,
) {
  const tests: { title: string; body: (f: MatrixFixtures) => Promise<void> }[] =
    [];
  const sunk: { name: string; json: Record<string, unknown> }[] = [];
  registerLabCaptures<LabCase, MatrixFixtures>({
    cases: [{ identity: 'q-invented', refusal: null }],
    sizes: [[390, 844]],
    themes: ['dark'],
    styles: CARD_STYLES,
    register: (title, body) => tests.push({ title, body }),
    drive: (_fixtures, run) => drive(run),
    snapshot: async (_fixtures, run, state) => ({
      cardHtml: cards[run.language],
      trusted: fixtureReferences(contextPayloads[0]!),
      fields: { question_id: run.question.identity, state },
    }),
    sink: (name, json) => sunk.push({ name, json: JSON.parse(json) }),
    compare: async () => undefined,
  });
  return { tests, sunk };
}

const ALL_STATES = async (run: LabRun<LabCase>) => {
  for (const state of ['answer', 'comparison', 'evidence', 'drawer'])
    await run.capture(state);
};

async function settle(body: Promise<void>): Promise<unknown> {
  return body.then(
    () => null,
    (error: unknown) => error,
  );
}

it('S3-T21 CF4-6 the browser matrix records Arabic output and propagates its failure', async () => {
  const { enHtml, cleanAr, plantedAr } = plantedArPair();
  const clean = offlineMatrix({ en: enHtml, ar: cleanAr }, ALL_STATES);
  expect(clean.tests.map((test) => test.title)).toEqual([
    'q-invented 390x844 en dark',
    'q-invented 390x844 ar dark',
  ]);
  for (const test of clean.tests)
    expect(await settle(test.body({ label: test.title }))).toBeNull();
  expect(clean.sunk.map((entry) => entry.name)).toHaveLength(8);
  const planted = offlineMatrix({ en: enHtml, ar: plantedAr }, ALL_STATES);
  const [enTest, arTest] = planted.tests;
  expect(await settle(enTest!.body({ label: 'en' }))).toBeNull();
  const failure = await settle(arTest!.body({ label: 'ar' }));
  expect(String(failure)).toMatch(
    /^Error: parity_problems: .*uncatalogued-text/,
  );
  const arSunk = planted.sunk.filter((entry) => entry.name.includes('-ar-'));
  expect(arSunk.map((entry) => entry.name)).toEqual([
    'q-invented-390x844-ar-dark-answer.json',
  ]);
  expect(arSunk[0]!.json.parity_problems).toContain('uncatalogued-text');
});

it('S3-T21 CF4-6 a driver that skips Arabic or absorbs a failed record fails', async () => {
  const { enHtml, plantedAr } = plantedArPair();
  const skipping = offlineMatrix({ en: enHtml, ar: plantedAr }, async (run) => {
    if (run.language === 'en') await ALL_STATES(run);
  });
  expect(await settle(skipping.tests[0]!.body({ label: 'en' }))).toBeNull();
  expect(String(await settle(skipping.tests[1]!.body({ label: 'ar' })))).toBe(
    'Error: capture_states: ',
  );
  const absorbing = offlineMatrix(
    { en: enHtml, ar: plantedAr },
    async (run) => {
      await Promise.allSettled([ALL_STATES(run)]);
    },
  );
  expect(await settle(absorbing.tests[0]!.body({ label: 'en' }))).toBeNull();
  expect(String(await settle(absorbing.tests[1]!.body({ label: 'ar' })))).toBe(
    'Error: capture_states: ',
  );
});

it('S3-B12 r10: the browser matrix fails closed when no card renders in either language', async () => {
  // The offline equivalent of the browser plant: both languages report
  // no card, so no pair is ever stored and the ar record step must not
  // pass silently.
  const vanished = offlineMatrix({ en: null, ar: null }, ALL_STATES);
  const [enTest, arTest] = vanished.tests;
  expect(await settle(enTest!.body({ label: 'en' }))).toBeNull();
  expect(vanished.sunk).toHaveLength(4);
  for (const entry of vanished.sunk) {
    expect(entry.name).toContain('-en-');
    expect(entry.json).not.toHaveProperty('parity_problems');
  }
  const failure = await settle(arTest!.body({ label: 'ar' }));
  expect(String(failure)).toBe(
    'Error: parity_problems: parity:card-missing, parity:pair-missing',
  );
  expect(vanished.sunk).toHaveLength(5);
  const arSunk = vanished.sunk.filter((entry) => entry.name.includes('-ar-'));
  expect(arSunk.map((entry) => entry.name)).toEqual([
    'q-invented-390x844-ar-dark-answer.json',
  ]);
  expect(arSunk[0]!.json.parity_problems).toEqual([
    'parity:card-missing',
    'parity:pair-missing',
  ]);
});

it('S3-T21 a missing ranking line in ar fails', () => {
  const enLines: SurfaceLine[] = [
    {
      key: 'fragment:context_source#template',
      text: template('context_source', 'en'),
    },
  ];
  expect(rankingParity(enLines, [])).toContain('missing-key');
});

/** S3-B12 round 7: the trusted reference source of the browser lab. The
 * disk cases build the invented release the opening fixture serves with
 * its own builder and read it back through the reader; the row cases
 * change ONE input of a valid release dump and assert the named reason. */
const LAB_ROOT = path.resolve('..');
const LAB_TMP = path.join(LAB_ROOT, '.overnight/tmp');
const NIGHT_TABLE = 'pub_night_lights';

function python(code: string, ...args: string[]): string {
  const run = runPython(code, args, 'scripts/tests');
  expect(run.status, run.stderr).toBe(0);
  return run.stdout;
}

let labWork: string | null = null;
/** One fixture `work` folder per file run, laid out as the opening
 * fixture's: `work/release` written by `build_fixture(resolver=True)`. */
function fixtureWork(): string {
  if (labWork === null) {
    mkdirSync(LAB_TMP, { recursive: true });
    labWork = mkdtempSync(path.join(LAB_TMP, 'references-'));
    python(
      'import sys\nfrom pathlib import Path\nfrom public_release_fixture import build_fixture\nbuild_fixture(Path(sys.argv[1]), resolver=True)',
      path.join(labWork, 'release'),
    );
  }
  return labWork;
}
afterAll(() => {
  if (labWork !== null) rmSync(labWork, { recursive: true, force: true });
});

const FIXTURE_SOURCE = {
  sourceId: 'ntl_blackmarble',
  publisher: 'INVENTED-publisher',
  datasetOrPage: 'INVENTED-ntl_blackmarble',
  licenceOrTerms: 'INVENTED-licence',
  retrievalDate: '2026-01-02',
  sha256: 'ab'.repeat(32),
};

it(
  'S3-B12 r7: the reader reads the fixture release through the checked server reader',
  { timeout: 240_000 },
  () => {
    const work = fixtureWork();
    const refs = releaseReferences(
      readReleaseDump(work, NIGHT_TABLE),
      NIGHT_TABLE,
    );
    expect(refs.releaseId).toMatch(/^[0-9a-f]{64}$/);
    expect(refs.period).toBe('2026-03');
    expect(refs.chain).toEqual({
      tableName: NIGHT_TABLE,
      lineageId: 'lin_pub_night_lights',
      method: 'invented.module.hold',
      methodVersion: 'v1',
      sources: [FIXTURE_SOURCE],
    });
  },
);

it(
  'S3-B12 r7 plant: a release record removed from the fixture copy makes the reader throw',
  { timeout: 240_000 },
  () => {
    const copy = path.join(
      mkdtempSync(path.join(LAB_TMP, 'references-plant-')),
      'work',
    );
    try {
      cpSync(path.join(fixtureWork(), 'release'), path.join(copy, 'release'), {
        recursive: true,
      });
      // Rewrite fact_lineage without the night-lights record; nothing else.
      python(
        "import sys, duckdb\np = sys.argv[1]\nduckdb.sql(f\"COPY (SELECT * FROM '{p}' WHERE table_name <> 'pub_night_lights') TO '{p}.new' (FORMAT parquet)\")\nimport os\nos.replace(p + '.new', p)",
        path.join(copy, 'release/tables/fact_lineage.parquet'),
      );
      expect(() => readReleaseDump(copy, NIGHT_TABLE)).toThrow(
        'reference_source:release:digest_mismatch',
      );
    } finally {
      rmSync(path.dirname(copy), { recursive: true, force: true });
    }
  },
);

it(
  'S3-B12 r7 plant: a work folder with no release makes the reader throw',
  { timeout: 240_000 },
  () => {
    const empty = mkdtempSync(path.join(LAB_TMP, 'references-empty-'));
    try {
      expect(() => readReleaseDump(empty, NIGHT_TABLE)).toThrow(
        'reference_source:release:release_missing',
      );
    } finally {
      rmSync(empty, { recursive: true, force: true });
    }
  },
);

it(
  'S3-B12 r7 plant: a bridge that fails makes the reader throw',
  { timeout: 240_000 },
  () => {
    expect(() => readReleaseDump(fixtureWork(), 'INVENTED_table')).toThrow(
      'reference_source:bridge_failed',
    );
  },
);

it(
  'S3-B12 r7: the reader output does not depend on the page',
  { timeout: 240_000 },
  () => {
    const work = fixtureWork();
    const before = releaseReferences(
      readReleaseDump(work, NIGHT_TABLE),
      NIGHT_TABLE,
    );
    // A rendered page whose every reference chip is rewritten and re-keyed.
    const pair = renderPair(contextPayloads[0]!);
    for (const side of [pair.en, pair.ar])
      for (const chip of side.querySelectorAll(
        '[data-fact-chip="reference"]',
      )) {
        chip.setAttribute('data-record', 'INVENTED-record');
        chip.querySelector('.chip-num')!.textContent = 'INVENTED';
      }
    const after = releaseReferences(
      readReleaseDump(work, NIGHT_TABLE),
      NIGHT_TABLE,
    );
    expect(after).toEqual(before);
    // Structurally: the reader names no page, DOM or capture input at all.
    const source = readFileSync('tests/question_lab/references.ts', 'utf8');
    // Code only: the doc comments may say "page".
    const code = source.replace(/\/\*[\s\S]*?\*\/|\/\/.*$/gm, '');
    expect(code).not.toMatch(
      /@playwright|jsdom|(?<!\.)\bdocument\b|\bwindow\b|\bpage\b|\bcardHtml\b|HTML|textContent|querySelector|locator|evaluate/,
    );
    expect(
      [...source.matchAll(/^import .* from (['"])(.+)\1;$/gm)].map((m) => m[2]),
    ).toEqual(['node:crypto', 'node:child_process', 'node:path', './contract']);
  },
);

it('S3-B12 r7 plants: each bridge output refusal names its reason', () => {
  const good = JSON.stringify({
    release_id: 'x',
    fact_lineage: [],
    source_registry: [],
    periods: [],
  });
  expect(bridgeDump(0, good)).toEqual(JSON.parse(good));
  expect(() => bridgeDump(1, good)).toThrow(
    new ReferenceSourceError('bridge_failed'),
  );
  expect(() => bridgeDump(null, good)).toThrow(
    new ReferenceSourceError('bridge_failed'),
  );
  expect(() => bridgeDump(0, good.slice(1))).toThrow(
    new ReferenceSourceError('bridge_output'),
  );
  expect(() => bridgeDump(0, '[]')).toThrow(
    new ReferenceSourceError('bridge_output'),
  );
  expect(() => bridgeDump(0, 'null')).toThrow(
    new ReferenceSourceError('bridge_output'),
  );
  expect(() => bridgeDump(0, '{"refused":"digest_mismatch"}')).toThrow(
    new ReferenceSourceError('release:digest_mismatch'),
  );
});

/** A valid release dump of invented rows, shaped as the bridge prints. */
function validDump(): ReleaseDump {
  return {
    release_id: 'cd'.repeat(32),
    fact_lineage: [
      {
        lineage_id: 'lin_x',
        table_name: NIGHT_TABLE,
        source_id: 'src_b',
        transform: 'm.x@v2',
      },
      {
        lineage_id: 'lin_x',
        table_name: NIGHT_TABLE,
        source_id: 'src_a',
        transform: 'm.x@v2',
      },
      {
        lineage_id: 'lin_other',
        table_name: 'pub_other',
        source_id: 'src_a',
        transform: 'o@v1',
      },
    ],
    source_registry: ['src_a', 'src_b', 'src_c'].map((id) => ({
      source_id: id,
      kind: 'public_dataset',
      publisher: `P-${id}`,
      title: `T-${id}`,
      licence: `L-${id}`,
      retrieved_on: '2026-01-02',
      sha256: 'ef'.repeat(32),
    })),
    periods: ['2026-01', '2026-03', '2026-02'],
  };
}

it('S3-B12 r7: a valid dump yields the latest period and the sorted chain', () => {
  const refs = releaseReferences(validDump(), NIGHT_TABLE);
  expect(refs.period).toBe('2026-03');
  expect(refs.chain.lineageId).toBe('lin_x');
  expect([refs.chain.method, refs.chain.methodVersion]).toEqual(['m.x', 'v2']);
  expect(refs.chain.sources.map((s) => s.sourceId)).toEqual(['src_a', 'src_b']);
  expect(refs.chain.sources[0]).toEqual({
    sourceId: 'src_a',
    publisher: 'P-src_a',
    datasetOrPage: 'T-src_a',
    licenceOrTerms: 'L-src_a',
    retrievalDate: '2026-01-02',
    sha256: 'ef'.repeat(32),
  });
});

type DumpPlant = [string, (dump: ReleaseDump) => void];
const lineage = (dump: ReleaseDump) =>
  dump.fact_lineage as Record<string, unknown>[];
const registry = (dump: ReleaseDump) =>
  dump.source_registry as Record<string, unknown>[];
const DUMP_PLANTS: DumpPlant[] = [
  ['release_id', (d) => void (d.release_id = 'CD'.repeat(32))],
  ['dump_shape', (d) => void (d.fact_lineage = {})],
  ['dump_shape', (d) => void (d.source_registry = [null])],
  ['lineage_missing', (d) => void (d.fact_lineage = lineage(d).slice(2))],
  [
    'lineage_missing',
    (d) =>
      void lineage(d)
        .slice(0, 2)
        .forEach((row) => (row.lineage_id = '')),
  ],
  ['lineage_ambiguous', (d) => void (lineage(d)[1]!.lineage_id = 'lin_y')],
  ['lineage_table', (d) => void (lineage(d)[2]!.lineage_id = 'lin_x')],
  ['transform', (d) => void (lineage(d)[0]!.transform = 'm.x')],
  ['transform', (d) => void (lineage(d)[0]!.transform = '@v2')],
  ['transform', (d) => void (lineage(d)[0]!.transform = 'm.x@')],
  ['transform', (d) => void (lineage(d)[0]!.transform = 7)],
  ['transform', (d) => void (lineage(d)[1]!.transform = 'm.x@v3')],
  ['source_missing', (d) => void (d.source_registry = registry(d).slice(1))],
  ['source_missing', (d) => void (lineage(d)[0]!.source_id = ' ')],
  ['source_duplicate', (d) => void registry(d).push({ ...registry(d)[1]! })],
  ['source_field', (d) => void (registry(d)[0]!.publisher = ' ')],
  ['source_field', (d) => void (registry(d)[1]!.title = 3)],
  ['source_field', (d) => void delete registry(d)[0]!.licence],
  ['source_field', (d) => void (registry(d)[0]!.sha256 = '')],
  ['source_field', (d) => void (registry(d)[0]!.retrieved_on = '2026-1-02')],
  [
    'source_field',
    (d) => void (registry(d)[0]!.retrieved_on = '2026-01-02 00:00:00'),
  ],
  ['period_missing', (d) => void (d.periods = [])],
  ['period_missing', (d) => void (d.periods = null)],
  ['period_shape', (d) => void (d.periods = ['2026-03', '2026-3'])],
  ['period_shape', (d) => void (d.periods = ['2026-13'])],
  ['period_shape', (d) => void (d.periods = [202603])],
];

for (const [reason, plant] of DUMP_PLANTS)
  it(`S3-B12 r7 plant: ${reason} (${plant.toString().slice(12, 70)})`, () => {
    const dump = validDump();
    plant(dump);
    expect(() => releaseReferences(dump, NIGHT_TABLE)).toThrow(
      new ReferenceSourceError(reason),
    );
  });

it('S3-B12 r7 property: row order and unrelated rows never change the references', () => {
  const expected = releaseReferences(validDump(), NIGHT_TABLE);
  let seed = 7;
  const next = () => (seed = (seed * 1103515245 + 12345) % 2 ** 31);
  const shuffle = <T,>(items: T[]) =>
    items
      .map((item) => [next(), item] as const)
      .sort((a, b) => a[0] - b[0])
      .map(([, item]) => item);
  for (let round = 0; round < 200; round += 1) {
    const dump = validDump();
    dump.fact_lineage = shuffle([
      ...lineage(dump),
      ...Array.from({ length: next() % 4 }, (_, i) => ({
        lineage_id: `lin_u${i}`,
        table_name: `pub_u${i}`,
        source_id: 'src_c',
        transform: 'u@v1',
      })),
    ]);
    dump.source_registry = shuffle(registry(dump));
    dump.periods = shuffle([...(dump.periods as string[])]);
    expect(releaseReferences(dump, NIGHT_TABLE)).toEqual(expected);
  }
});

it(
  'S3-B12 r7 oracle: the answer fact id equals eii_core DAT-93 over generated areas',
  { timeout: 240_000 },
  () => {
    const releaseId = '0123456789abcdef'.repeat(4);
    const refs = { ...releaseReferences(validDump(), NIGHT_TABLE), releaseId };
    let seed = 11;
    const next = () => (seed = (seed * 1103515245 + 12345) % 2 ** 31);
    const hex = (n: number) =>
      Array.from({ length: n }, () => '0123456789abcdef'[next() % 16]).join('');
    const prefix = `ma1/${releaseId.slice(0, 16)}`;
    const cases = Array.from({ length: 40 }, (_, i) => ({
      area:
        i % 2 === 0
          ? `${prefix}/polygon/${hex(64)}`
          : `${prefix}/walk/${next() % 60}/${next()}/${(next() % 1e6).toString().padStart(6, '0')}/${(next() % 1e6).toString().padStart(6, '0')}`,
      period: `20${10 + (next() % 20)}-${String(1 + (next() % 12)).padStart(2, '0')}`,
    }));
    const oracle = JSON.parse(
      python(
        'import json, sys\nfrom eii_core.facts import fact_id\nprint(json.dumps([fact_id(release_id=sys.argv[1], metric_key="night_lights_radiance", geography={"kind": "area_shape", "area_id": c["area"]}, period=c["period"], qualifiers={}) for c in json.loads(sys.argv[2])]))',
        releaseId,
        JSON.stringify(cases),
      ),
    ) as string[];
    expect(
      cases.map((c) =>
        answerFactId(
          { ...refs, period: c.period },
          'night_lights_radiance',
          c.area,
        ),
      ),
    ).toEqual(oracle);
  },
);

it('S3-B12 r7: the answer area is the one issued area of the typed mode', () => {
  const prefix = 'ma1/0123456789abcdef';
  const distance = `${prefix}/distance/500/1/1.000000/1.000000`;
  const ring = `${prefix}/drive/10/1/1.000000/1.000000`;
  expect(answerArea([distance, null, ring, distance], 'distance')).toBe(
    distance,
  );
  expect(answerArea([distance, ring], 'drive')).toBe(ring);
  expect(() => answerArea([distance, ring], 'walk')).toThrow(
    new ReferenceSourceError('area_missing'),
  );
  expect(() => answerArea([], 'distance')).toThrow(
    new ReferenceSourceError('area_missing'),
  );
  expect(() =>
    answerArea(
      [distance, `${prefix}/distance/800/1/1.000000/1.000000`],
      'distance',
    ),
  ).toThrow(new ReferenceSourceError('area_ambiguous'));
});

it('S3-B12 r7 plant: an area of another release is refused', () => {
  const refs = releaseReferences(validDump(), NIGHT_TABLE);
  expect(() =>
    answerFactId(
      refs,
      'night_lights_radiance',
      `ma1/${'0'.repeat(16)}/polygon/${'a'.repeat(64)}`,
    ),
  ).toThrow(new ReferenceSourceError('area_release'));
});

/** The release-shaped records of the shipped night-lights card, from the
 * fixture's own input rows: they bind the rendered card exactly. */
function nightRefs(): { refs: ReleaseReferences; factId: string } {
  const payload = contextPayloads[0]!;
  const input = contextInput();
  const fact = input.facts.find((b) => b.fact.fact_id === payload.factId)!.fact;
  const line = input.lineages.find(
    (row) => row.lineageId === fact.lineage_ref,
  )!;
  return {
    factId: fact.fact_id,
    refs: {
      releaseId: fact.release_id,
      period: String(fact.period),
      chain: {
        tableName: line.tableName,
        lineageId: line.lineageId,
        method: line.method,
        methodVersion: line.methodVersion,
        sources: line.sourceIds.map((id) =>
          input.sources.find((row) => row.sourceId === id)!,
        ),
      },
    },
  };
}

it('S3-B12 r7: the composed records bind every chip of an open card and of its answer level', () => {
  expect(contextPayloads[0]!.family).toBe('night_lights');
  const { refs, factId } = nightRefs();
  const open = renderPair(contextPayloads[0]!);
  expect(
    cardsParity(open.en, open.ar, nightLightsReferences(refs, factId, true)),
  ).toEqual([]);
  // Closed evidence: only the answer level's month is required.
  for (const side of [open.en, open.ar])
    fireEvent.click(
      side.querySelector('[data-context-level="evidence"] > button')!,
    );
  expect(
    cardsParity(open.en, open.ar, nightLightsReferences(refs, factId, false)),
  ).toEqual([]);
  expect(
    cardsParity(open.en, open.ar, nightLightsReferences(refs, factId, true)),
  ).toEqual(['reference-missing']);
});

it('S3-B12 r7 plant: a page reference text changed by one character is refused', () => {
  const { refs, factId } = nightRefs();
  const pair = renderPair(contextPayloads[0]!);
  const isolate = [...pair.ar.querySelectorAll(PUBLISHED)].at(-1)!;
  isolate.textContent = isolate.textContent!.slice(0, -1) + 'c';
  expect(
    cardsParity(pair.en, pair.ar, nightLightsReferences(refs, factId, true)),
  ).toEqual(['fact-slot']);
});

it('S3-B12 r7 plant: with the reader replaced by an empty list the card refuses', () => {
  const pair = renderPair(contextPayloads[0]!);
  expect(cardsParity(pair.en, pair.ar, [])).toEqual(['reference-unbound']);
});
