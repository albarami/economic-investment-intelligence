/** S3 opening/story transport. Only returned facts and closed user choices cross. */
import {
  catalogue,
  directiveAccepted,
  type AnswerDirective,
  type DirectiveValue,
} from '../brief/catalogue';
import {
  contextAccepted,
  type ContextPayload,
} from '../cards/PublicContextCard';
import {
  createRegistry,
  type FactRegistry,
  type RegistryInput,
} from '../facts/registry';
import type { Fact } from '../facts/types';
import type { Language } from '../i18n';
import type { LayerFeature } from '../stage/layers/payload';
import type { PinBody, PlaceBody, ShapeIdBody } from '../controls/area-request';
import {
  createSameOriginFetch,
  decodeAreaOutline,
  postMakeArea,
  postShape,
  type AreaOutline,
} from './areas';
import { loadRegistryInput } from './release';

export type SelectedArea = PinBody | PlaceBody | ShapeIdBody;
export type StorySelection =
  | { shape_id: string }
  | {
      pin: { lat: number; lon: number };
      mode: string;
      cutoff: number;
    };

/** Named keys are resolved on the server; persist its exact outline as a session shape. */
export async function storySelection(
  selected: SelectedArea,
): Promise<StorySelection> {
  if ('shape_id' in selected) return selected;
  if ('latitude' in selected)
    return {
      pin: { lat: selected.latitude, lon: selected.longitude },
      mode: selected.mode,
      cutoff: selected.cutoff,
    };
  const client = createSameOriginFetch();
  const answer = await postMakeArea(selected, client);
  if (
    answer.kind !== 'envelope' ||
    answer.envelope.status !== 'OK' ||
    !answer.envelope.payload
  )
    throw new Error('area_refused');
  if (answer.envelope.payload.outline.type === 'Circle') {
    const [lon, lat] = answer.envelope.payload.outline.coordinates;
    return { pin: { lat, lon }, mode: selected.mode, cutoff: selected.cutoff };
  }
  const registered = await postShape(
    {
      geometry: {
        type: 'Polygon',
        coordinates: answer.envelope.payload.outline.coordinates as readonly [
          readonly (readonly [number, number])[],
        ],
      },
    },
    client,
  );
  if (!registered.ok) throw new Error('area_refused');
  return { shape_id: registered.shapeId };
}

/** Merge chains, retaining the original fact binding shared by every view. */
export function mergeInputs(inputs: readonly RegistryInput[]): RegistryInput {
  if (
    new Set(
      inputs.flatMap((input) =>
        input.releases.map((release) => release.releaseId),
      ),
    ).size > 1
  )
    throw new Error('chain_conflict');
  function unique<T>(rows: readonly T[], key: (row: T) => string): T[] {
    const held = new Map<string, T>();
    for (const row of rows) {
      const previous = held.get(key(row));
      if (previous && JSON.stringify(previous) !== JSON.stringify(row))
        throw new Error('chain_conflict');
      if (!previous) held.set(key(row), row);
    }
    return [...held.values()];
  }
  return {
    facts: unique(
      inputs.flatMap((i) => i.facts),
      (r) => r.fact.fact_id,
    ),
    releases: unique(
      inputs.flatMap((i) => i.releases),
      (r) => r.releaseId,
    ),
    tables: unique(
      inputs.flatMap((i) => i.tables),
      (r) => r.releaseId + ':' + r.tableName,
    ),
    lineages: unique(
      inputs.flatMap((i) => i.lineages),
      (r) => r.lineageId + ':' + r.factId,
    ),
    sources: unique(
      inputs.flatMap((i) => i.sources),
      (r) => r.sourceId,
    ),
  };
}

/** The accepted rings directive and the outline of its distinct wider area. */
export interface StoryRings {
  directive: AnswerDirective;
  outline: AreaOutline;
}

export interface StoryEvidence {
  input: RegistryInput;
  cards: ContextPayload[];
  accountingPassed: true;
  rings: StoryRings | null;
}

type Frame = { kind: string; data: Record<string, unknown> };
export function readStoryFrames(source: string): Frame[] {
  const frames: Frame[] = [];
  for (const block of source.replace(/\r\n/g, '\n').split('\n\n')) {
    if (!block.trim()) continue;
    const lines = block.split('\n');
    const kind = lines.find((line) => line.startsWith('event: '))?.slice(7);
    const raw = lines
      .filter((line) => line.startsWith('data: '))
      .map((line) => line.slice(6))
      .join('\n');
    if (!kind || !raw) throw new Error('story_refused');
    const data: unknown = JSON.parse(raw);
    if (
      ![
        'plan_step',
        'stage',
        'evidence',
        'receipt',
        'status',
        'narrative',
        'done',
        'error',
      ].includes(kind)
    )
      throw new Error('story_refused');
    if (kind === 'narrative') {
      frames.push({ kind, data: {} });
      continue;
    }
    if (!data || typeof data !== 'object' || Array.isArray(data))
      throw new Error('story_refused');
    frames.push({ kind, data: data as Record<string, unknown> });
  }
  // The structured brief is released only after all accounting checks, template
  // writer status, and the terminal event. Never render narrative text from SSE.
  const receipt = frames.findIndex((frame) => frame.kind === 'receipt');
  const checks = frames[receipt]?.data['Checked before display'];
  const names = [
    'Sources',
    'Assumptions',
    'Nothing invented',
    'Scope',
    'Limits stated',
  ];
  if (
    receipt < 0 ||
    !checks ||
    typeof checks !== 'object' ||
    names.some((name) => (checks as Record<string, unknown>)[name] !== true) ||
    JSON.stringify(frames[receipt]?.data.egress) !== '[]' ||
    !frames.some(
      (frame, index) =>
        index > receipt &&
        frame.kind === 'status' &&
        frame.data.writer === 'template',
    ) ||
    frames.at(-1)?.kind !== 'done' ||
    frames.some(
      (frame, index) =>
        frame.kind === 'error' ||
        (frame.kind === 'narrative' && index < receipt),
    )
  )
    throw new Error('story_refused');
  const brief = frames.at(-1)!.data.brief as
    Record<string, unknown> | undefined;
  if (
    !brief ||
    brief.catalogue_version !== catalogue.version ||
    brief.headline_key !== 'foundation_headline' ||
    brief.decision_template_key !== 'foundation_decision'
  )
    throw new Error('story_refused');
  return frames;
}

/** The fields of a stage frame other than its directive name. */
function stageFrame(
  frames: readonly Frame[],
  name: string,
): Record<string, unknown> | null {
  const frame = frames.find(
    (item) => item.kind === 'stage' && item.data.directive === name,
  );
  if (!frame) return null;
  return Object.fromEntries(
    Object.entries(frame.data).filter(([key]) => key !== 'directive'),
  );
}

/** The stage's rings frame as a closed directive, or null when it is malformed. */
function ringsDirective(frames: readonly Frame[]): AnswerDirective | null {
  const fields = (stageFrame(frames, 'rings') ?? {}) as Record<
    string,
    DirectiveValue
  >;
  return directiveAccepted('rings', fields) ? { name: 'rings', fields } : null;
}

/** The chosen area of a closed fly frame, or null. Its target is exactly
 * {area_id}; the whole frame, with that identifier as the target, must pass the
 * catalogue's fly directive before the identifier is read. */
function flyArea(fields: Record<string, unknown>): string | null {
  const target = fields.target;
  if (!target || typeof target !== 'object') return null;
  const areaId = (target as { area_id?: unknown }).area_id;
  const closed = { ...fields, target: areaId } as Record<
    string,
    DirectiveValue
  >;
  return Object.keys(target).length === 1 && directiveAccepted('fly', closed)
    ? (areaId as string)
    : null;
}

/** The fly directive names the chosen area; the rings directive must hold it.
 * Each whole directive is validated before any identifier is read from it, and
 * each refusal names its reason so a test cannot pass on an earlier guard. */
export function storyArea(frames: readonly Frame[]): string {
  const fly = stageFrame(frames, 'fly');
  if (!fly) throw new Error('story_refused:fly');
  const chosen = flyArea(fly);
  if (!chosen) throw new Error('story_refused:fly_directive');
  if (!stageFrame(frames, 'rings')) throw new Error('story_refused:rings');
  const rings = ringsDirective(frames);
  if (!rings) throw new Error('story_refused:rings_directive');
  if (!(rings.fields.area_ids as readonly string[]).includes(chosen))
    throw new Error('story_refused:rings_chosen');
  return chosen;
}

/** The wider area by its documented role (document 08 section 7, site_check:
 * near, then wider). A drive selection is itself the wider area and a shape has
 * none, so neither has a distinct wider ring; otherwise the chosen area is the
 * near area, first in rings, and the wider area is the second member. */
export function widerArea(
  frames: readonly Frame[],
  selection: StorySelection,
): string | null {
  if (!('pin' in selection) || selection.mode === 'drive') return null;
  const [near, wider] = (ringsDirective(frames)?.fields.area_ids ??
    []) as readonly string[];
  return wider && near === storyArea(frames) && wider !== near ? wider : null;
}

/** Draw a wider ring only for the accepted directive and the outline that the
 * existing make_area route returned for exactly that identifier. */
export async function storyRings(
  frames: readonly Frame[],
  selection: StorySelection,
): Promise<StoryRings | null> {
  const wider = widerArea(frames, selection);
  const directive = ringsDirective(frames);
  if (!wider || !directive) return null;
  const outline = await decodeAreaOutline(wider, createSameOriginFetch());
  return outline ? { directive, outline } : null;
}

export async function runPublicStory(
  activity: string,
  lang: Language,
  selected: SelectedArea,
): Promise<StoryEvidence> {
  const selection = await storySelection(selected);
  const response = await fetch('/api/playbooks/site_check', {
    method: 'POST',
    credentials: 'same-origin',
    redirect: 'error',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ activity, lang, ...selection }),
  });
  if (response.status !== 202) throw new Error('story_refused');
  const started = (await response.json()) as Record<string, unknown>;
  if (
    Object.keys(started).sort().join() !== 'answer_id,events_url' ||
    typeof started.answer_id !== 'string' ||
    started.events_url !== '/api/answers/' + started.answer_id + '/events' ||
    !/^[a-f0-9-]+$/.test(started.answer_id)
  )
    throw new Error('story_refused');
  const stream = await fetch(started.events_url as string, {
    credentials: 'same-origin',
    redirect: 'error',
  });
  if (!stream.ok) throw new Error('story_refused');
  const frames = readStoryFrames(await stream.text());
  const chosenArea = storyArea(frames);
  const inputs: RegistryInput[] = [];
  const cards: ContextPayload[] = [];
  for (const frame of frames.filter((frame) => frame.kind === 'evidence')) {
    const wireFacts = frame.data.facts;
    if (
      !Array.isArray(wireFacts) ||
      wireFacts.some(
        (fact: Fact) =>
          fact.provenance !== 'public' ||
          JSON.stringify(fact.input_classes) !== '["public"]',
      )
    )
      throw new Error('story_refused');
    const family = frame.data.kind;
    if (family !== 'night_lights' && family !== 'population_age_sex') continue;
    if (frame.data.area_id !== chosenArea)
      throw new Error('story_refused:evidence_area');
    const identities = frame.data.fact_ids;
    if (!Array.isArray(identities)) throw new Error('story_refused');
    if (!identities.length) {
      cards.push({ family, state: 'no_data', reason: 'missing_input' });
      continue;
    }
    const first = wireFacts[0] as Fact | undefined;
    if (!first) throw new Error('story_refused');
    const args =
      family === 'night_lights'
        ? { area_id: chosenArea, month_key: first.period }
        : { area_id: chosenArea, split: 'none' };
    const response = await fetch('/api/tools/' + family, {
      method: 'POST',
      credentials: 'same-origin',
      redirect: 'error',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(args),
    });
    if (!response.ok) throw new Error('story_refused');
    const body = (await response.json()) as {
      tool: string;
      status: string;
      facts: Fact[];
    };
    if (
      body.tool !== family ||
      body.status !== 'OK' ||
      !Array.isArray(body.facts) ||
      JSON.stringify(body.facts.map((fact) => fact.fact_id).sort()) !==
        JSON.stringify([...identities].sort())
    )
      throw new Error('story_refused');
    const input = await loadRegistryInput(body.facts);
    inputs.push(input);
    const registry = createRegistry(input);
    for (const fact of body.facts) {
      const resolved = registry.resolve(fact.fact_id);
      if (resolved.status !== 'ready') throw new Error('story_refused');
      const payload: ContextPayload =
        family === 'night_lights'
          ? { family, state: 'ready', factId: fact.fact_id }
          : {
              family,
              state: 'ready',
              factId: fact.fact_id,
              ageBand:
                resolved.binding.qualifiers?.age_band === 'all'
                  ? null
                  : (resolved.binding.qualifiers?.age_band ?? null),
              sex: 'none',
            };
      if (!contextAccepted(payload, registry)) throw new Error('story_refused');
      cards.push(payload);
    }
  }
  const input = mergeInputs(inputs);
  const rings = await storyRings(frames, selection);
  return { input, cards, accountingPassed: true, rings };
}

/** Card C37 is selected by returned place keys; never joined to a people estimate. */
export async function loadBusyness(
  placeKey: string,
): Promise<{ input: RegistryInput; cards: ContextPayload[] }> {
  const response = await fetch('/api/tools/venue_busyness', {
    method: 'POST',
    credentials: 'same-origin',
    redirect: 'error',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ place_keys: [placeKey] }),
  });
  if (!response.ok) throw new Error('card_refused');
  const body = (await response.json()) as {
    tool: string;
    status: string;
    facts: Fact[];
    payload: { entries: Record<string, unknown>[] } | null;
  };
  if (
    body.tool !== 'venue_busyness' ||
    !['OK', 'NO_DATA'].includes(body.status) ||
    !Array.isArray(body.facts)
  )
    throw new Error('card_refused');
  const input = await loadRegistryInput(body.facts);
  const registry = createRegistry(input);
  const cards: ContextPayload[] = [];
  for (const entry of body.payload?.entries ?? []) {
    if (entry.status !== 'OK') continue;
    const payload = {
      family: 'venue_busyness',
      state: 'ready',
      factId: entry.fact_id,
      retrievedOn: entry.retrieved_on,
      providerUpdatedOn: entry.provider_updated_on,
      day: entry.weekday,
      hour: entry.hour,
    };
    if (!contextAccepted(payload, registry)) throw new Error('card_refused');
    cards.push(payload);
  }
  if (!cards.length)
    cards.push({
      family: 'venue_busyness',
      state: 'no_data',
      reason: 'missing_input',
    });
  return { input, cards };
}

/** The named layer's Fact uses the documented `place:` public-code namespace.
 * No row key is inferred from a table name or a feature identifier. */
export function listedPlaceKey(
  feature: LayerFeature,
  registry: FactRegistry,
): string | null {
  if (!feature.fact_id || feature.metric_key !== 'place_listing') return null;
  const resolved = registry.resolve(feature.fact_id);
  if (
    resolved.status !== 'ready' ||
    resolved.binding.metricKey !== 'place_listing'
  )
    return null;
  const code = resolved.binding.fact.geography.public_code;
  if (
    resolved.binding.fact.geography.kind !== 'public' ||
    !code?.startsWith('place:')
  )
    return null;
  const key = code.slice('place:'.length);
  return /^[A-Za-z0-9][A-Za-z0-9-]*$/.test(key) ? key : null;
}
