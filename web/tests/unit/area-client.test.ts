import { describe, expect, it } from 'vitest';

import {
  MAKE_AREA_PATH,
  SHAPES_PATH,
  nullAnchorIsOk,
  postMakeArea,
  postShape,
  postResolve,
  readResolveEnvelope,
  RESOLVE_PATH,
  type FetchLike,
} from '../../src/api/areas';
import { presentAnswer } from '../../src/controls/present';
import * as areas from '../../src/api/areas';

const SHAPE_ID = 'ab'.repeat(32);

const candidate = {
  kind: 'place',
  key: 'INVENTED-garden',
  label_en: 'INVENTED-Garden',
  label_ar: 'حديقة مخترعة',
  source: 'gazetteer',
  match: 'exact',
};
function resolved(
  payload: unknown = { candidates: [candidate] },
  status = 'OK',
) {
  return {
    tool: 'resolve',
    call_id: 'INVENTED-call',
    release_id: 'rel-draw',
    engine: 'embedded',
    status,
    payload,
    facts: [],
    blocks: [],
    caveat_keys: [],
  };
}

function fetchOf(status: number, body: unknown): FetchLike {
  return async (path) => {
    void path;
    return { status, json: async () => body };
  };
}

describe('area client', () => {
  it.each(['en', 'ar'] as const)(
    'posts %s text only to local resolve and keeps the selected key',
    async (lang) => {
      const seen: unknown[] = [];
      const body = {
        text: lang === 'en' ? candidate.label_en : candidate.label_ar,
        lang,
        kind: 'place' as const,
      };
      const answer = await postResolve(body, async (path, init) => {
        seen.push({ path, method: init.method, body: JSON.parse(init.body) });
        return { status: 200, json: async () => resolved() };
      });
      expect(seen).toEqual([{ path: RESOLVE_PATH, method: 'POST', body }]);
      expect(
        answer.kind === 'envelope' &&
          answer.envelope.payload?.candidates[0]?.key,
      ).toBe(candidate.key);
    },
  );

  it.each(['INVENTED Garden 4', 'حديقة ٤', 'حديقة ۴'])(
    'refuses raw numeral label %s at the plain-label guard',
    (label) => {
      expect(
        readResolveEnvelope(
          resolved({ candidates: [{ ...candidate, label_en: label }] }),
        ).kind,
      ).toBe('refused');
      expect(
        readResolveEnvelope(
          resolved({ candidates: [{ ...candidate, label_ar: label }] }),
        ).kind,
      ).toBe('refused');
    },
  );

  it('refuses extra candidate fields, foreign kinds and sources, empty and over-cap payloads and facts', () => {
    for (const bad of [
      { ...candidate, extra: 'INVENTED' },
      { ...candidate, latitude: 1 },
      { ...candidate, source: 'activity_spine' },
      { ...candidate, kind: 'company' },
      { ...candidate, key: 'register:INVENTED' },
      { ...candidate, match: 'guessed' },
    ])
      expect(readResolveEnvelope(resolved({ candidates: [bad] })).kind).toBe(
        'refused',
      );
    expect(readResolveEnvelope(resolved({ candidates: [] })).kind).toBe(
      'refused',
    );
    expect(
      readResolveEnvelope(resolved({ candidates: Array(6).fill(candidate) }))
        .kind,
    ).toBe('refused');
    expect(
      readResolveEnvelope({ ...resolved(), facts: [{ value: 1 }] }).kind,
    ).toBe('refused');
    expect(readResolveEnvelope({ ...resolved(), extra: true }).kind).toBe(
      'refused',
    );
  });

  it.each(['NO_DATA', 'OUT_OF_SCOPE'])(
    'keeps %s without a fallback or candidate',
    async (status) => {
      const answer = await postResolve(
        { text: 'INVENTED', lang: 'en', kind: 'both' },
        fetchOf(200, resolved(null, status)),
      );
      expect(answer.kind === 'envelope' && answer.envelope.status).toBe(status);
      expect(answer.kind === 'envelope' && answer.envelope.payload).toBeNull();
      expect(
        readResolveEnvelope(resolved({ candidates: [candidate] }, status)).kind,
      ).toBe('refused');
    },
  );

  it('accepts the closed activity shape and sanitized refusals only', () => {
    const activity = {
      ...candidate,
      kind: 'activity',
      source: 'activity_spine',
      commerce_code: 'INVENTED-code',
      isic_class: '',
      place_category: '',
      not_mappable: true,
    };
    expect(readResolveEnvelope(resolved({ candidates: [activity] })).kind).toBe(
      'envelope',
    );
    expect(
      readResolveEnvelope(
        resolved({ candidates: [{ ...activity, not_mappable: 'yes' }] }),
      ).kind,
    ).toBe('refused');
    expect(readResolveEnvelope(resolved(null, 'UNMAPPABLE')).kind).toBe(
      'refused',
    );
    const refusal = {
      error: {
        code: 'INVALID_ARGUMENT',
        message_key: 'invalid_argument',
        error_id: 'INVENTED',
      },
    };
    expect(readResolveEnvelope(refusal, 422)).toEqual({
      kind: 'refused',
      code: 'INVALID_ARGUMENT',
      httpStatus: 422,
    });
    expect(
      readResolveEnvelope(
        { error: { ...refusal.error, detail: 'INVENTED' } },
        422,
      ),
    ).toEqual({ kind: 'refused', code: 'malformed', httpStatus: 422 });
  });
  it('exposes the offline resolve client on the existing typed tool path', () => {
    expect(typeof Reflect.get(areas, 'postResolve')).toBe('function');
  });
  it('posts a shape to the shapes path and make_area with only a shape id', async () => {
    const seen: { path: string; body: unknown }[] = [];
    const fetchLike: FetchLike = async (path, init) => {
      seen.push({ path, body: JSON.parse(init.body) });
      if (path === SHAPES_PATH) {
        return { status: 201, json: async () => ({ shape_id: SHAPE_ID }) };
      }
      return {
        status: 200,
        json: async () => ({
          tool: 'make_area',
          call_id: 'INVENTED-call',
          engine: 'embedded',
          blocks: [],
          facts: [],
          caveat_keys: [],
          status: 'OK',
          release_id: 'rel-draw',
          payload: {
            area_id: 'area-draw',
            outline: {
              type: 'Polygon',
              coordinates: [
                [
                  [0, 0],
                  [1, 0],
                  [1, 1],
                  [0, 1],
                  [0, 0],
                ],
              ],
            },
            units: { cells: ['unit-a', 'unit-b'] },
            snap_report: { opaque: true },
            record: {
              anchor_cell: null,
              traffic: 'free_flow',
              shape: 'polygon',
            },
          },
        }),
      };
    };
    const posted = await postShape(
      {
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [0, 0],
              [1, 0],
              [0, 1],
              [0, 0],
            ],
          ],
        },
      },
      fetchLike,
    );
    expect(posted).toEqual({ ok: true, shapeId: SHAPE_ID });
    const envelope = await postMakeArea({ shape_id: SHAPE_ID }, fetchLike);
    expect(seen.map((call) => call.path)).toEqual([
      SHAPES_PATH,
      MAKE_AREA_PATH,
    ]);
    expect(seen[1]?.body).toEqual({ shape_id: SHAPE_ID });
    expect(nullAnchorIsOk(envelope)).toBe(true);
    expect(
      envelope.kind === 'envelope'
        ? envelope.envelope.payload?.units.cells
        : undefined,
    ).toEqual(['unit-a', 'unit-b']);
    const presented = presentAnswer(envelope, {
      kind: 'polygon',
      mode: null,
      cutoff: null,
      ownRing: [],
      pin: null,
    });
    expect(presented.showRefusal).toBe(false);
    expect(presented.line).toBe('accent');
  });

  it('treats a missing payload status as a governed reason with no outline', async () => {
    const envelope = await postMakeArea(
      { shape_id: SHAPE_ID },
      fetchOf(200, {
        tool: 'make_area',
        call_id: 'INVENTED-call',
        engine: 'embedded',
        blocks: [],
        facts: [],
        caveat_keys: [],
        status: 'NO_DATA',
        release_id: 'rel-draw',
        payload: null,
      }),
    );
    expect(
      envelope.kind === 'envelope' && envelope.envelope.payload,
    ).toBeNull();
    const presented = presentAnswer(envelope, {
      kind: 'pin',
      mode: 'distance',
      cutoff: 250,
      ownRing: [],
      pin: { latitude: 0.2, longitude: 0.2 },
    });
    expect(presented.showRefusal).toBe(true);
    expect(presented.outline).toBeNull();
    expect(presented.showLayers).toBe(false);
    expect(presented.line).toBe('none');
  });

  it('refuses a shapes-route rejection and a malformed success', async () => {
    const geometry = {
      geometry: {
        type: 'Polygon' as const,
        coordinates: [
          [
            [0, 0],
            [1, 0],
            [0, 1],
            [0, 0],
          ],
        ] as readonly [readonly (readonly [number, number])[]],
      },
    };
    const rejected = await postShape(
      geometry,
      fetchOf(422, { shape_id: SHAPE_ID }),
    );
    expect(rejected).toEqual({ ok: false, status: 422 });
    const malformed = await postShape(
      geometry,
      fetchOf(201, { shape_id: 12, outline: { type: 'Polygon' } }),
    );
    expect(malformed.ok).toBe(false);
    if (malformed.ok) return;
    expect(malformed.status).toBe(201);
  });
});
