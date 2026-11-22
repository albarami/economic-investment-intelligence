import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  mergeInputs,
  readStoryFrames,
  storySelection,
  runPublicStory,
  widerArea,
  loadBusyness,
  listedPlaceKey,
} from '../../src/api/public-opening';
import { loadRegistryInput } from '../../src/api/release';
import { catalogue } from '../../src/brief/catalogue';
import { createRegistry } from '../../src/facts/registry';
import { completeInput, factId, tableWire } from '../fixtures/facts';
import { contextInput } from '../fixtures/public-context';
import type { Fact } from '../../src/facts/types';
import type { ContextPayload } from '../../src/cards/PublicContextCard';
import type { LayerFeature } from '../../src/stage/layers/payload';

const checks = {
  Sources: true,
  Assumptions: true,
  'Nothing invented': true,
  Scope: true,
  'Limits stated': true,
};
function frames(): { kind: string; data: unknown }[] {
  return [
    { kind: 'evidence', data: { kind: 'night_lights', facts: [] } },
    {
      kind: 'receipt',
      data: { 'Checked before display': { ...checks }, egress: [] },
    },
    { kind: 'status', data: { writer: 'template' } },
    { kind: 'narrative', data: 'never rendered prose' },
    {
      kind: 'done',
      data: {
        brief: {
          catalogue_version: catalogue.version,
          headline_key: 'foundation_headline',
          decision_template_key: 'foundation_decision',
        },
      },
    },
  ];
}
function stream(items: ReturnType<typeof frames>) {
  return items
    .map(
      (frame) =>
        `event: ${frame.kind}\r\ndata: ${JSON.stringify(frame.data)}\r\n\r\n`,
    )
    .join('');
}
afterEach(() => vi.unstubAllGlobals());

describe('Public opening accounting boundary', () => {
  it('accepts the template stream only after the receipt and done', () => {
    expect(
      readStoryFrames(stream(frames())).map((frame) => frame.kind),
    ).toContain('done');
  });
  it.each([
    'Sources',
    'Assumptions',
    'Nothing invented',
    'Scope',
    'Limits stated',
  ])('refuses a planted failed %s check', (check) => {
    const broken = stream(frames()).replace(
      `"${check}":true`,
      `"${check}":false`,
    );
    expect(() => readStoryFrames(broken)).toThrow('story_refused');
  });
  it.each([
    'early',
    'egress',
    'model',
    'incomplete',
    'catalogue',
    'unknown-event',
    'error',
    'headline',
    'decision',
    'nonterminal-brief',
  ])('refuses planted %s frames', (plant) => {
    let broken = stream(frames());
    if (plant === 'early')
      broken = 'event: narrative\ndata: "early"\n\n' + broken;
    if (plant === 'egress')
      broken = broken.replace('"egress":[]', '"egress":["attempt"]');
    if (plant === 'model')
      broken = broken.replace('"writer":"template"', '"writer":"model"');
    if (plant === 'incomplete') broken = stream(frames().slice(0, -1));
    if (plant === 'catalogue')
      broken = broken.replace(catalogue.version, 'INVENTED-foreign');
    if (plant === 'unknown-event')
      broken = broken.replace('event: evidence', 'event: tool_argument');
    if (plant === 'error')
      broken = broken.replace('event: evidence', 'event: error');
    if (plant === 'headline')
      broken = broken.replace('foundation_headline', 'INVENTED-headline');
    if (plant === 'decision')
      broken = broken.replace('foundation_decision', 'INVENTED-decision');
    if (plant === 'nonterminal-brief')
      broken = broken.replace('event: done', 'event: status');
    expect(() => readStoryFrames(broken)).toThrow('story_refused');
  });
  it('shares one original fact binding across the merged registry', () => {
    const input = completeInput();
    const combined = mergeInputs([input, input]);
    expect(combined.facts).toHaveLength(input.facts.length);
    const registry = createRegistry(combined);
    const answer = registry.resolve(input.facts[0]!.fact.fact_id);
    expect(answer.status).toBe('ready');
    if (answer.status === 'ready') expect(answer.binding).toBe(input.facts[0]);
  });
  it('rejects conflicting facts rather than choosing a version', () => {
    const input = completeInput();
    const changed = structuredClone(input);
    changed.facts[0]!.fact.value = 999;
    expect(() => mergeInputs([input, changed])).toThrow('chain_conflict');
  });
  it('rejects a story and map from different releases', () => {
    const original = completeInput();
    const foreign = structuredClone(original);
    foreign.releases[0]!.releaseId = 'INVENTED-foreign';
    expect(() => mergeInputs([original, foreign])).toThrow('chain_conflict');
  });
  it.each(['distance', 'walk', 'drive'] as const)(
    'keeps the explicitly chosen %s mode and cutoff',
    async (mode) => {
      const selected = {
        latitude: 1,
        longitude: 2,
        mode,
        cutoff: mode === 'distance' ? 500 : 15,
      };
      expect(await storySelection(selected)).toEqual({
        pin: { lat: 1, lon: 2 },
        mode,
        cutoff: selected.cutoff,
      });
    },
  );
  it('keeps a registered selected shape instead of a default pin', async () => {
    expect(await storySelection({ shape_id: 'shape-INVENTED' })).toEqual({
      shape_id: 'shape-INVENTED',
    });
  });
});

/** Complete HTTP chains, independent from the evidence/tool identity comparison. */
function transport() {
  const input = contextInput();
  const fact = input.facts[0]!.fact;
  // The story's population card is the all-sexes reading (split none).
  input.facts[2]!.qualifiers = { age_band: '20', sex: 'none' };
  const items = frames();
  items[0] = {
    kind: 'evidence',
    data: {
      kind: 'night_lights',
      facts: [fact],
      fact_ids: [fact.fact_id],
      area_id: 'INVENTED-area',
    },
  };
  items.unshift(
    {
      kind: 'stage',
      data: {
        directive: 'fly',
        target: { area_id: 'INVENTED-area' },
        zoom: 'street',
      },
    },
    {
      kind: 'stage',
      data: {
        directive: 'rings',
        area_ids: ['INVENTED-area', 'INVENTED-wider'],
      },
    },
  );
  const reply = {
    startStatus: 202,
    started: {
      answer_id: 'abc-def',
      events_url: '/api/answers/abc-def/events',
    },
    items,
    toolFacts: [fact],
    populationFacts: [input.facts[2]!.fact],
    entries: [
      {
        status: 'OK',
        fact_id: input.facts[1]!.fact.fact_id,
        retrieved_on: '2026-01-01',
        provider_updated_on: null,
        weekday: 'monday',
        hour: '9',
      },
    ],
    makeArea: null as null | (() => Response),
  };
  const release = {
    release_id: fact.release_id,
    release_kind: 'public_only',
    rules_version_id: 'INVENTED-rules',
    tables: input.tables,
    artefacts: input.artefacts,
    hour_keys: [],
    day_keys: [],
    month_keys: [],
    basemap_url: null,
  };
  const fetch = vi.fn(async (path: string) => {
    if (path === '/api/playbooks/site_check')
      return new Response(JSON.stringify(reply.started), {
        status: reply.startStatus,
      });
    if (
      path === '/api/answers/abc-def/events' ||
      path === '/api/answers/def-abc/events'
    )
      return new Response(stream(reply.items));
    if (path === '/api/tools/night_lights')
      return Response.json({
        tool: 'night_lights',
        status: 'OK',
        facts: reply.toolFacts,
      });
    if (path === '/api/tools/population_age_sex')
      return Response.json({
        tool: 'population_age_sex',
        status: 'OK',
        facts: reply.populationFacts,
      });
    if (path === '/api/tools/venue_busyness')
      return Response.json({
        tool: 'venue_busyness',
        status: 'OK',
        facts: input.facts.map((row) => row.fact),
        payload: { entries: reply.entries },
      });
    if (path === '/api/release') return Response.json(release);
    if (path === '/api/tools/make_area' && reply.makeArea)
      return reply.makeArea();
    const binding = input.facts.find(
      (row) => path === '/api/facts/' + row.fact.fact_id + '/lineage',
    );
    if (!binding) throw new Error('unexpected_fixture_route');
    return Response.json({
      fact_id: binding.fact.fact_id,
      release_id: binding.fact.release_id,
      lineage: tableWire(
        input.lineages.find(
          (row) => row.lineageId === binding.fact.lineage_ref,
        )!,
      ),
      sources: input.sources,
      binding: {
        metricKey: binding.metricKey,
        presentation: binding.presentation,
        qualifiers: binding.qualifiers ?? {},
      },
    });
  });
  vi.stubGlobal('fetch', fetch);
  return { input, fact, reply, fetch };
}
const selected = { shape_id: 'INVENTED-shape' };

describe('runPublicStory refusals', () => {
  it('returns the exact accounted fact with its complete chain', async () => {
    const { fact, fetch } = transport();
    const answer = await runPublicStory('INVENTED-activity', 'en', selected);
    expect(answer.accountingPassed).toBe(true);
    expect(answer.cards).toEqual([
      { family: 'night_lights', state: 'ready', factId: fact.fact_id },
    ]);
    expect(createRegistry(answer.input).resolve(fact.fact_id).status).toBe(
      'ready',
    );
    expect(fetch.mock.calls.map(([path]) => path)).toContain(
      '/api/facts/' + fact.fact_id + '/lineage',
    );
  });
  it.each(['status', 'extra-key', 'foreign-events'])(
    'refuses a planted start %s',
    async (plant) => {
      const { reply } = transport();
      if (plant === 'status') reply.startStatus = 200;
      if (plant === 'extra-key')
        Object.assign(reply.started, { extra: 'INVENTED' });
      if (plant === 'foreign-events')
        reply.started.events_url = '/api/answers/def-abc/events';
      await expect(
        runPublicStory('INVENTED-activity', 'en', selected),
      ).rejects.toThrow('story_refused');
    },
  );
  it.each(['provenance', 'input-classes'])(
    'refuses non-Public %s even in evidence without a displayed card',
    async (plant) => {
      const { reply, fact } = transport();
      const nonPublic: Fact = {
        ...fact,
        ...(plant === 'provenance'
          ? { provenance: 'synthetic' }
          : { input_classes: ['public', 'synthetic'] }),
      };
      reply.items.unshift({
        kind: 'evidence',
        data: { kind: 'utility_momentum', facts: [nonPublic] },
      });
      await expect(
        runPublicStory('INVENTED-activity', 'en', selected),
      ).rejects.toThrow('story_refused');
    },
  );
  it.each(['replacement', 'addition', 'omission'])(
    'refuses a chain-valid tool fact-set %s outside the accounted identities',
    async (plant) => {
      const { input, reply, fact } = transport();
      const other = {
        ...input.facts[0]!,
        fact: { ...fact, fact_id: factId(3) },
      };
      input.facts.push(other);
      reply.toolFacts =
        plant === 'replacement'
          ? [other.fact]
          : plant === 'addition'
            ? [fact, other.fact]
            : [];
      const checked = createRegistry(await loadRegistryInput(reply.toolFacts));
      for (const emitted of reply.toolFacts)
        expect(checked.resolve(emitted.fact_id).status).toBe('ready');
      await expect(
        runPublicStory('INVENTED-activity', 'en', selected),
      ).rejects.toThrow('story_refused');
    },
  );
  it('refuses a chain-valid story card of the wrong metric before returning cards', async () => {
    const { input } = transport();
    input.facts[0]!.metricKey = 'population_grid_people';
    await expect(
      runPublicStory('INVENTED-activity', 'en', selected),
    ).rejects.toThrow('story_refused');
  });
  it('requests the card for the fly area and keeps a no-data card of that area', async () => {
    const { reply, fetch } = transport();
    reply.items.splice(3, 0, {
      kind: 'evidence',
      data: {
        kind: 'population_age_sex',
        facts: [],
        fact_ids: [],
        area_id: 'INVENTED-area',
      },
    });
    const answer = await runPublicStory('INVENTED-activity', 'en', selected);
    expect(answer.cards).toContainEqual({
      family: 'population_age_sex',
      state: 'no_data',
      reason: 'missing_input',
    });
    const card = fetch.mock.calls.find(
      ([path]) => path === '/api/tools/night_lights',
    ) as unknown as [string, { body: string }];
    expect(JSON.parse(card[1].body).area_id).toBe('INVENTED-area');
  });
  // S3-T26 A5 round 2: each refusal branch, one changed input, its own reason.
  type Item = ReturnType<typeof frames>[number];
  const stage = (items: Item[], directive: string) =>
    items.find(
      (item) =>
        item.kind === 'stage' &&
        (item.data as { directive: string }).directive === directive,
    )!;
  const data = (item: Item) => item.data as Record<string, unknown>;
  const card = (items: Item[]) =>
    data(items.find((item) => item.kind === 'evidence')!);
  it.each<[string, string, (items: Item[]) => void]>([
    [
      'missing fly',
      'story_refused:fly',
      (items) => items.splice(items.indexOf(stage(items, 'fly')), 1),
    ],
    [
      'non-string fly area',
      'story_refused:fly_directive',
      (items) => (data(stage(items, 'fly')).target = { area_id: 7 }),
    ],
    [
      'empty fly area',
      'story_refused:fly_directive',
      (items) => (data(stage(items, 'fly')).target = { area_id: '' }),
    ],
    [
      'fly target with an extra key',
      'story_refused:fly_directive',
      (items) =>
        (data(stage(items, 'fly')).target = {
          area_id: 'INVENTED-area',
          extra: 'INVENTED',
        }),
    ],
    [
      'fly without a target',
      'story_refused:fly_directive',
      (items) => delete data(stage(items, 'fly')).target,
    ],
    [
      'fly target that is text',
      'story_refused:fly_directive',
      (items) => (data(stage(items, 'fly')).target = 'INVENTED-area'),
    ],
    [
      'fly without zoom',
      'story_refused:fly_directive',
      (items) => delete data(stage(items, 'fly')).zoom,
    ],
    [
      'fly with an unknown zoom',
      'story_refused:fly_directive',
      (items) => (data(stage(items, 'fly')).zoom = 'INVENTED'),
    ],
    [
      'unknown fly field',
      'story_refused:fly_directive',
      (items) => (data(stage(items, 'fly')).extra = 'INVENTED'),
    ],
    [
      'missing rings',
      'story_refused:rings',
      (items) => items.splice(items.indexOf(stage(items, 'rings')), 1),
    ],
    [
      'non-array rings',
      'story_refused:rings_directive',
      (items) => (data(stage(items, 'rings')).area_ids = 'INVENTED-area'),
    ],
    [
      'non-string ring member',
      'story_refused:rings_directive',
      (items) => (data(stage(items, 'rings')).area_ids = ['INVENTED-area', 7]),
    ],
    [
      'third ring member',
      'story_refused:rings_directive',
      (items) =>
        (data(stage(items, 'rings')).area_ids = [
          'INVENTED-area',
          'INVENTED-wider',
          'INVENTED-third',
        ]),
    ],
    [
      'unknown rings field',
      'story_refused:rings_directive',
      (items) => (data(stage(items, 'rings')).extra = 'INVENTED'),
    ],
    [
      'empty rings',
      'story_refused:rings_directive',
      (items) => (data(stage(items, 'rings')).area_ids = []),
    ],
    [
      'rings without the fly area',
      'story_refused:rings_chosen',
      (items) => (data(stage(items, 'rings')).area_ids = ['INVENTED-wider']),
    ],
  ])('refuses a planted %s with its reason', async (_name, reason, plant) => {
    const { reply, fetch } = transport();
    plant(reply.items);
    await expect(
      runPublicStory('INVENTED-activity', 'en', selected),
    ).rejects.toThrow(new RegExp('^' + reason + '$'));
    expect(
      fetch.mock.calls.some(([path]) => path.startsWith('/api/tools/')),
    ).toBe(false);
  });
  // S3-T26 A5 round 3 (R2-F2): a passing control of each family and state;
  // each negative case changes only the card's area_id from its own control.
  const populated = (fact: Fact) => ({
    facts: [fact],
    fact_ids: [fact.fact_id],
  });
  const empty = { facts: [], fact_ids: [] };
  const population = contextInput().facts[2]!.fact;
  const controls: [string, Record<string, unknown>, ContextPayload][] = [
    [
      'populated night-lights',
      {},
      { family: 'night_lights', state: 'ready', factId: factId(0) },
    ],
    [
      'no-data night-lights',
      empty,
      { family: 'night_lights', state: 'no_data', reason: 'missing_input' },
    ],
    [
      'populated population',
      { kind: 'population_age_sex', ...populated(population) },
      {
        family: 'population_age_sex',
        state: 'ready',
        factId: population.fact_id,
        ageBand: '20',
        sex: 'none',
      },
    ],
    [
      'no-data population',
      { kind: 'population_age_sex', ...empty },
      {
        family: 'population_age_sex',
        state: 'no_data',
        reason: 'missing_input',
      },
    ],
  ];
  it.each(controls)(
    'accepts the %s control of the chosen area',
    async (_name, change, expected) => {
      const { reply } = transport();
      Object.assign(card(reply.items), change);
      const answer = await runPublicStory('INVENTED-activity', 'en', selected);
      expect(answer.cards).toEqual([expected]);
    },
  );
  it.each(controls)(
    'refuses the %s control with only its area changed',
    async (_name, change) => {
      const { reply, fetch } = transport();
      Object.assign(card(reply.items), change);
      card(reply.items).area_id = 'INVENTED-wider';
      await expect(
        runPublicStory('INVENTED-activity', 'en', selected),
      ).rejects.toThrow(/^story_refused:evidence_area$/);
      expect(
        fetch.mock.calls.some(([path]) => path.startsWith('/api/tools/')),
      ).toBe(false);
    },
  );
  it('loads a valid busyness observation with its row citation', async () => {
    transport();
    const result = await loadBusyness('INVENTED-venue');
    expect(result.cards).toEqual([
      {
        family: 'venue_busyness',
        state: 'ready',
        factId: factId(1),
        retrievedOn: '2026-01-01',
        providerUpdatedOn: null,
        day: 'monday',
        hour: '9',
      },
    ]);
  });
  it('refuses a busyness entry bound to a chain-valid night-lights fact', async () => {
    const { reply, fact } = transport();
    reply.entries[0]!.fact_id = fact.fact_id;
    await expect(loadBusyness('INVENTED-venue')).rejects.toThrow(
      'card_refused',
    );
  });
});

describe('listed place namespace', () => {
  it.each([
    ['public', 'place:INVENTED-venue-a', 'INVENTED-venue-a'],
    ['public', 'zone:INVENTED-a', null],
    ['national', 'place:INVENTED-venue-a', null],
    ['public', 'place:../x', null],
  ] as const)(
    'accepts only a public place key: %s / %s',
    (kind, public_code, expected) => {
      const input = completeInput();
      input.facts[0]!.metricKey = 'place_listing';
      input.facts[0]!.fact.geography = { kind, public_code };
      const feature: LayerFeature = {
        feature_id: 'INVENTED-feature',
        geometry_kind: 'point',
        metric_key: 'place_listing',
        provenance: 'public',
        subject: 'place',
        fact_id: input.facts[0]!.fact.fact_id,
      };
      expect(listedPlaceKey(feature, createRegistry(input))).toBe(expected);
    },
  );
});

// S3-T26 A5 (finding 1): near and wider by their documented roles.
describe('wider area by role', () => {
  const story = (fly: string, rings: unknown[], extra = {}) => [
    {
      kind: 'stage',
      data: { directive: 'fly', target: { area_id: fly }, zoom: 'street' },
    },
    { kind: 'stage', data: { directive: 'rings', area_ids: rings, ...extra } },
  ];
  const walk = { pin: { lat: 1, lon: 2 }, mode: 'walk', cutoff: 5 };
  const distance = { ...walk, mode: 'distance', cutoff: 500 };
  const drive = { ...walk, mode: 'drive', cutoff: 15 };
  const shape = { shape_id: 'INVENTED-shape' };
  it.each<
    [
      string,
      ReturnType<typeof story>,
      Parameters<typeof widerArea>[1],
      string | null,
    ]
  >([
    ['walk near then wider', story('N', ['N', 'W']), walk, 'W'],
    ['distance near then wider', story('N', ['N', 'W']), distance, 'W'],
    [
      'drive: the chosen area is the wider one',
      story('W', ['N', 'W']),
      drive,
      null,
    ],
    [
      'drive listed first is still the wider one',
      story('W', ['W', 'N']),
      drive,
      null,
    ],
    ['drive alone', story('W', ['W']), drive, null],
    ['shape only', story('S', ['S']), shape, null],
    ['shape with a second member', story('S', ['S', 'X']), shape, null],
    ['walk without a wider area', story('N', ['N']), walk, null],
    ['walk with the roles reversed', story('N', ['W', 'N']), walk, null],
    ['walk with a duplicated member', story('N', ['N', 'N']), walk, null],
  ])('%s', (_name, items, selection, expected) => {
    expect(widerArea(items, selection)).toBe(expected);
  });
});

// S3-T26 A5 (finding 3): exactly {area_id}; only a matching OK outline counts.
describe('wider outline request', () => {
  const outline = {
    type: 'Polygon',
    coordinates: [
      [
        [0, 0],
        [0, 1],
        [1, 1],
        [0, 0],
      ],
    ],
  };
  const envelope = (status: string, payload: unknown) =>
    Response.json({
      tool: 'make_area',
      call_id: 'INVENTED-call',
      release_id: 'INVENTED-release',
      engine: 'embedded',
      status,
      blocks: [],
      facts: [],
      caveat_keys: [],
      payload,
    });
  const ok = (areaId: string) =>
    envelope('OK', {
      area_id: areaId,
      outline,
      record: { anchor_cell: null, traffic: 'free_flow', shape: 'drive' },
      units: {},
      snap_report: null,
      point_feature_ids: null,
    });
  const walk = { latitude: 1, longitude: 2, mode: 'walk', cutoff: 5 };
  const requests = (fetch: ReturnType<typeof transport>['fetch']) =>
    fetch.mock.calls.filter(([path]) => path === '/api/tools/make_area');
  it('draws the wider area of an accepted directive from its own outline', async () => {
    const { reply, fetch } = transport();
    reply.makeArea = () => ok('INVENTED-wider');
    const answer = await runPublicStory('INVENTED-activity', 'en', walk);
    expect(answer.rings).toEqual({
      directive: {
        name: 'rings',
        fields: { area_ids: ['INVENTED-area', 'INVENTED-wider'] },
      },
      outline,
    });
    const sent = requests(fetch) as unknown as [string, { body: string }][];
    expect(sent).toHaveLength(1);
    expect(JSON.parse(sent[0]![1].body)).toEqual({ area_id: 'INVENTED-wider' });
  });
  it.each<[string, () => Response]>([
    ['an OK answer for another area', () => ok('INVENTED-area')],
    ['a malformed envelope', () => Response.json({ tool: 'make_area' })],
    ['an OK answer without a payload', () => envelope('OK', null)],
    ['NO_DATA', () => envelope('NO_DATA', null)],
    ['OUT_OF_SCOPE', () => envelope('OUT_OF_SCOPE', null)],
    ['SUPPRESSED', () => envelope('SUPPRESSED', null)],
    [
      'INVALID_ARGUMENT',
      () =>
        Response.json(
          {
            error: {
              code: 'INVALID_ARGUMENT',
              message_key: 'errors.invalid_argument',
              error_id: 'INVENTED-error',
            },
          },
          { status: 422 },
        ),
    ],
    ['a body that is not JSON', () => new Response('INVENTED')],
  ])('leaves no ring for %s', async (_name, answer) => {
    const { reply, fetch } = transport();
    reply.makeArea = answer;
    const story = await runPublicStory('INVENTED-activity', 'en', walk);
    expect(story.rings).toBeNull();
    expect(story.cards).toHaveLength(1);
    expect(requests(fetch)).toHaveLength(1);
  });
  it('asks for no outline when a drive selection is itself the wider area', async () => {
    const { reply, fetch } = transport();
    reply.makeArea = () => ok('INVENTED-wider');
    const story = await runPublicStory('INVENTED-activity', 'en', {
      ...walk,
      mode: 'drive',
      cutoff: 15,
    });
    expect(story.rings).toBeNull();
    expect(requests(fetch)).toHaveLength(0);
  });
});

// D0 new merge cases, independent of the pre-existing table-path assertions.
it('retains a manifest artefact while merging the same snapshot twice', () => {
  const input = completeInput();
  const artefact = {
    releaseId: input.releases[0]!.releaseId,
    path: 'artefacts/SYN-height.json',
    sha256: 'ab'.repeat(32),
  };
  Object.assign(input, { artefacts: [artefact] });
  expect(mergeInputs([input, input]).artefacts).toEqual([artefact]);
});
it('refuses one path with two hashes as chain_conflict', () => {
  const input = completeInput();
  Object.assign(input, {
    artefacts: [
      {
        releaseId: input.releases[0]!.releaseId,
        path: 'artefacts/SYN-height.json',
        sha256: 'ab'.repeat(32),
      },
    ],
  });
  const changed = structuredClone(input);
  Object.assign(changed.artefacts[0]!, { sha256: 'cd'.repeat(32) });
  expect(() => mergeInputs([input, changed])).toThrow(/^chain_conflict$/);
});
