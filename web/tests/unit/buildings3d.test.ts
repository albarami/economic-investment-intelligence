// @vitest-environment jsdom
/** Invented buildings SYN-B-*; heights are hand-made decimal texts. */
import { ScatterplotLayer, SolidPolygonLayer } from '@deck.gl/layers';
import { describe, expect, it } from 'vitest';

import {
  BUILDINGS_LAYER,
  SHADOWS_LAYER,
  buildingLayers,
  footprintDistance,
  footprintInView,
  ownHeight,
  readBuildingHeights,
  shadowSelection,
  verifyBuildingLayers,
  type BuildingRow,
  type ShadowView,
} from '../../src/stage/buildings3d';
import { ClockLight } from '../../src/stage/clock-light';
import { heightsBody } from '../fixtures/building-heights';
import { clockTimestamp } from '../../src/stage/clock';

function square(lon: number, lat: number): [number, number][] {
  const d = 0.0001;
  return [
    [lon - d, lat - d],
    [lon + d, lat - d],
    [lon + d, lat + d],
    [lon - d, lat + d],
  ];
}

function building(
  key: string,
  lon: number,
  lat: number,
  height: string | null,
  source: BuildingRow['height_source'] = height === null ? 'none' : 'recorded',
): BuildingRow {
  return {
    building_key: key,
    footprint: square(lon, lat),
    height_m: height,
    height_source: source,
  };
}

const VIEW: ShadowView = {
  centre: [51.5, 25.3],
  bounds: [51.4, 25.2, 51.6, 25.4],
};

type Body = ReturnType<typeof heightsBody>;

function changed(change: (body: Body) => void): unknown {
  const body = heightsBody();
  change(body);
  return body;
}

function rowWith(field: string, value: unknown) {
  return changed((body) => {
    (body.buildings[0] as Record<string, unknown>)[field] = value;
  });
}

type Entry = Record<string, unknown>;
function entry(body: Body, index: number): Entry {
  return body.fallback_errors[index] as Entry;
}
function factOf(body: Body, index: number): Entry {
  return body.facts[index]!.fact as Entry;
}

describe('readBuildingHeights: the read is accepted whole or refused with one reason', () => {
  it('accepts the fixed read the route serves, with a registry of its own chain', () => {
    const result = readBuildingHeights(heightsBody());
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.read.buildings).toHaveLength(4);
    const first = result.read.fallback_errors[0] as Record<string, string>;
    expect(result.read.registry.resolve(first.pairs_fact_id!).status).toBe(
      'ready',
    );
  });
  it.each([
    ['not an object', null, 'heights_shape'],
    [
      'buildings missing',
      changed((body) => {
        delete (body as Partial<Body>).buildings;
      }),
      'heights_shape',
    ],
    [
      'an unknown top key',
      changed((body) => {
        (body as Record<string, unknown>).extra = [];
      }),
      'heights_shape',
    ],
    ['empty key', rowWith('building_key', ''), 'heights_shape'],
    [
      'two-point footprint',
      rowWith('footprint', [
        [1, 2],
        [3, 4],
      ]),
      'heights_shape',
    ],
    [
      'unknown source',
      rowWith('height_source', 'statistic'),
      'height_source_unknown',
    ],
    [
      'none with a height',
      rowWith('height_source', 'none'),
      'height_source_mismatch',
    ],
    ['zero height', rowWith('height_m', '0.00'), 'height_not_positive'],
    ['negative height', rowWith('height_m', '-4'), 'height_not_positive'],
    ['numeric height', rowWith('height_m', 30), 'height_not_positive'],
    [
      'overflowing height text',
      rowWith('height_m', '9'.repeat(400)),
      'height_not_positive',
    ],
    [
      'duplicate key',
      changed((body) => {
        body.buildings[1]!.building_key = body.buildings[0]!.building_key;
      }),
      'duplicate_building_key',
    ],
    [
      'missing fallback',
      changed((body) => {
        body.fallback_errors.pop();
      }),
      'fallback_error_shape',
    ],
    [
      'statistics with reason null',
      changed((body) => {
        entry(body, 0).reason = null;
      }),
      'fallback_error_shape',
    ],
    [
      'no pairs with an extra key',
      changed((body) => {
        entry(body, 1).pairs_fact_id = 'f_0';
      }),
      'fallback_error_shape',
    ],
    [
      'an unknown reason',
      changed((body) => {
        entry(body, 1).reason = 'not_measured';
      }),
      'fallback_reason_unknown',
    ],
    [
      'statistics with an unknown extra key',
      changed((body) => {
        entry(body, 0).note = 'x';
      }),
      'fallback_error_shape',
    ],
    [
      'a statistic slot missing',
      changed((body) => {
        delete entry(body, 0).median_abs_fact_id;
      }),
      'fallback_error_shape',
    ],
    [
      'a numeric fact id',
      changed((body) => {
        entry(body, 0).mean_abs_fact_id = 7;
      }),
      'fallback_error_shape',
    ],
    [
      'a lineage with an unknown key',
      changed((body) => {
        (body.lineage as Record<string, unknown>).extra = 'x';
      }),
      'heights_chain',
    ],
    [
      'a source without a publisher',
      changed((body) => {
        body.sources[0]!.publisher = '';
      }),
      'heights_chain',
    ],
    [
      'a fact binding with an unknown qualifier',
      changed((body) => {
        (body.facts[0]!.binding.qualifiers as Record<string, unknown>).hour =
          '1';
      }),
      'heights_chain',
    ],
    [
      'swapped mean signed and mean absolute slots',
      changed((body) => {
        const row = entry(body, 0);
        [row.mean_signed_fact_id, row.mean_abs_fact_id] = [
          row.mean_abs_fact_id,
          row.mean_signed_fact_id,
        ];
      }),
      'fallback_fact_binding',
    ],
    [
      "a slot pointing at another fallback's statistic",
      changed((body) => {
        entry(body, 0).pairs_fact_id = entry(body, 2).pairs_fact_id;
        entry(body, 2).pairs_fact_id = body.facts[0]!.fact.fact_id;
      }),
      'fallback_fact_binding',
    ],
    [
      'a pair count in metres',
      changed((body) => {
        factOf(body, 0).unit = 'metres';
      }),
      'fallback_fact_binding',
    ],
    [
      'a ready fact of an unrelated table',
      changed((body) => {
        body.lineage.tableName = 'pub_place';
      }),
      'fallback_fact_binding',
    ],
    [
      'a ready fact of another method',
      changed((body) => {
        body.lineage.method = 'MTH-001';
      }),
      'fallback_fact_binding',
    ],
    [
      'a spare fact no slot names',
      changed((body) => {
        const spare = structuredClone(body.facts[0]!);
        spare.fact.fact_id = 'f_' + 'e'.repeat(32);
        body.facts.push(spare);
      }),
      'fallback_fact_binding',
    ],
    [
      'a fractional pair count',
      changed((body) => {
        factOf(body, 0).value = 2.5;
      }),
      'fallback_fact_binding',
    ],
  ])('refuses %s', (_name, value, reason) => {
    expect(readBuildingHeights(value)).toEqual({ ok: false, reason });
  });
});

describe('ownHeight: only a positive finite height, never any other value', () => {
  it.each([
    ['an overflowing text', '9'.repeat(400)],
    ['a zero text', '0.00'],
  ])('gives none for %s even on an unchecked row', (_name, height) => {
    expect(ownHeight(building('SYN-B-0020', 51.5, 25.3, height))).toBeNull();
  });
});

describe('shadowSelection: buildings in view with a height, nearest the centre over the cap', () => {
  const rows = [
    building('SYN-B-0001', 51.5, 25.3, '30.00'),
    building('SYN-B-0002', 51.52, 25.3, '12.00', 'floor_count'),
    building('SYN-B-0003', 51.501, 25.3, '21.00', '3dglobfp'),
    building('SYN-B-0004', 51.5, 25.3, null),
    building('SYN-B-0005', 51.9, 25.3, '6.00', 'wsf3d'),
  ];
  it('keeps every in-view building with a height under the cap, words off', () => {
    const selection = shadowSelection(rows, VIEW, 3);
    expect(selection.casting.map((row) => row.building_key)).toEqual([
      'SYN-B-0001',
      'SYN-B-0003',
      'SYN-B-0002',
    ]);
    expect(selection.limited).toBe(false);
  });
  it('over the cap keeps the nearest to the view centre and is limited', () => {
    const selection = shadowSelection(rows, VIEW, 2);
    expect(selection.casting.map((row) => row.building_key)).toEqual([
      'SYN-B-0001',
      'SYN-B-0003',
    ]);
    expect(selection.limited).toBe(true);
  });
  it('breaks a distance tie by building key, whatever the input order', () => {
    const tied = [
      building('SYN-B-0009', 51.51, 25.3, '9.00'),
      building('SYN-B-0008', 51.49, 25.3, '8.00'),
    ];
    expect(shadowSelection(tied, VIEW, 1).casting[0]?.building_key).toBe(
      'SYN-B-0008',
    );
    expect(
      shadowSelection([...tied].reverse(), VIEW, 1).casting[0]?.building_key,
    ).toBe('SYN-B-0008');
  });
  it('empty input and a view with no building cast nothing and are not limited', () => {
    expect(shadowSelection([], VIEW, 1)).toEqual({
      casting: [],
      limited: false,
    });
    expect(shadowSelection([rows[4]!], VIEW, 1)).toEqual({
      casting: [],
      limited: false,
    });
  });
  it('keeps a footprint touching the view edge, drops one just beyond, and a cap of the count is unlimited', () => {
    // Binary-exact vertices: the footprint's west side lies on the view's east edge.
    const edge: BuildingRow[] = [
      {
        ...building('SYN-B-0010', 0, 0, '5.00'),
        footprint: [
          [51.5, 25.25],
          [51.75, 25.25],
          [51.75, 25.5],
          [51.5, 25.5],
        ],
      },
    ];
    const view: ShadowView = {
      centre: [51.375, 25.25],
      bounds: [51.25, 25, 51.5, 25.375],
    };
    expect(shadowSelection(edge, view, 1)).toEqual({
      casting: edge,
      limited: false,
    });
    const beyond: ShadowView = {
      ...view,
      bounds: [51.25, 25, 51.4375, 25.375],
    };
    expect(shadowSelection(edge, beyond, 1)).toEqual({
      casting: [],
      limited: false,
    });
  });
  it('keeps a footprint that crosses the view though its vertex average lies outside', () => {
    const crossing: BuildingRow = {
      ...building('SYN-B-0011', 0, 0, '40.00'),
      // A long slab across the view; its vertex average lies east of the view.
      // No vertex lies in the view and no view corner lies in it: only edges cross.
      footprint: [
        [51.3, 25.3],
        [52.5, 25.3],
        [52.5, 25.301],
        [51.3, 25.301],
      ],
    };
    expect(shadowSelection([crossing], VIEW, 1).casting).toEqual([crossing]);
  });
  it('treats a closed ring exactly as its open ring', () => {
    const open = building('SYN-B-0012', 51.55, 25.35, '15.00');
    const closed: BuildingRow = {
      ...open,
      building_key: 'SYN-B-0013',
      footprint: [...open.footprint, open.footprint[0]!],
    };
    expect(footprintDistance(closed.footprint, VIEW.centre)).toBe(
      footprintDistance(open.footprint, VIEW.centre),
    );
    expect(footprintInView(closed.footprint, VIEW.bounds)).toBe(true);
    // A closed ring whose average is pulled outside by the repeated vertex.
    const slab: BuildingRow = {
      ...building('SYN-B-0014', 0, 0, '9.00'),
      footprint: [
        [51.7, 25.3],
        [51.59, 25.3],
        [51.7, 25.31],
        [51.7, 25.3],
      ],
    };
    expect(shadowSelection([slab], VIEW, 1).casting).toEqual([slab]);
  });
  it('keeps a triangle that holds the whole view and drops an L whose notch holds it', () => {
    const triangle: BuildingRow = {
      ...building('SYN-B-0015', 0, 0, '60.00'),
      footprint: [
        [50, 24],
        [53, 24],
        [51.5, 27],
      ],
    };
    const shape: BuildingRow = {
      ...building('SYN-B-0016', 0, 0, '8.00'),
      // Its bounding box covers the view; the view sits in the notch.
      footprint: [
        [51.3, 25.1],
        [51.35, 25.1],
        [51.35, 25.45],
        [51.7, 25.45],
        [51.7, 25.5],
        [51.3, 25.5],
      ],
    };
    expect(shadowSelection([triangle, shape], VIEW, 2).casting).toEqual([
      triangle,
    ]);
    expect(footprintDistance(triangle.footprint, VIEW.centre)).toBe(0);
  });
  it.each([
    ['a NaN centre', { centre: [Number.NaN, 25.3], bounds: VIEW.bounds }],
    [
      'an infinite edge',
      { centre: VIEW.centre, bounds: [51.4, 25.2, Infinity, 25.4] },
    ],
    [
      'west east of east',
      { centre: VIEW.centre, bounds: [51.6, 25.2, 51.4, 25.4] },
    ],
    [
      'south north of north',
      { centre: VIEW.centre, bounds: [51.4, 25.4, 51.6, 25.2] },
    ],
  ])('refuses a view with %s', (_name, view) => {
    expect(() =>
      shadowSelection(rows, view as unknown as ShadowView, 2),
    ).toThrow('shadow_view_invalid');
  });
  it.each([0, -1, 1.5, Number.NaN])('refuses the cap %s', (cap) => {
    expect(() => shadowSelection(rows, VIEW, cap)).toThrow(
      'shadow_cap_invalid',
    );
  });
  it('holds its invariants over a seeded generator of views and caps', () => {
    let seed = 4242;
    const next = () => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return seed / 2147483648;
    };
    for (let round = 0; round < 200; round += 1) {
      const count = Math.floor(next() * 12);
      const generated = Array.from({ length: count }, (_, index) =>
        building(
          `SYN-B-G${round}-${index}`,
          51.35 + next() * 0.3,
          25.15 + next() * 0.3,
          next() < 0.3 ? null : `${1 + Math.floor(next() * 90)}.00`,
        ),
      );
      const cap = 1 + Math.floor(next() * 6);
      const selection = shadowSelection(generated, VIEW, cap);
      // Independent oracle for axis-aligned squares: interval overlap for
      // view, and the clamped box distance for the nearest point.
      const [w, south, e, n] = VIEW.bounds;
      const [cx, cy] = VIEW.centre;
      const shrink = Math.cos((cy * Math.PI) / 180);
      const box = (row: BuildingRow) => {
        const xs = row.footprint.map((point) => point[0]);
        const ys = row.footprint.map((point) => point[1]);
        return [
          Math.min(...xs),
          Math.min(...ys),
          Math.max(...xs),
          Math.max(...ys),
        ];
      };
      const expected = generated
        .filter((row) => {
          const [x0, y0, x1, y1] = box(row) as [number, number, number, number];
          return (
            ownHeight(row) !== null &&
            x0 <= e &&
            x1 >= w &&
            y0 <= n &&
            y1 >= south
          );
        })
        .map((row) => {
          const [x0, y0, x1, y1] = box(row) as [number, number, number, number];
          const dx = Math.max(x0 - cx, 0, cx - x1) * shrink;
          const dy = Math.max(y0 - cy, 0, cy - y1);
          return { row, distance: dx * dx + dy * dy };
        })
        .sort(
          (a, b) =>
            a.distance - b.distance ||
            (a.row.building_key < b.row.building_key ? -1 : 1),
        );
      expect(selection.casting.map((row) => row.building_key)).toEqual(
        expected.slice(0, cap).map((item) => item.row.building_key),
      );
      expect(selection.limited).toBe(expected.length > cap);
      expect(selection.casting.every((row) => ownHeight(row) !== null)).toBe(
        true,
      );
      const shuffled = shadowSelection([...generated].reverse(), VIEW, cap);
      expect(shuffled.casting).toEqual(selection.casting);
    }
  });
});

describe('building layers: own height only, shadows under the cap', () => {
  const rows = [
    building('SYN-B-0001', 51.5, 25.3, '30.00'),
    building('SYN-B-0002', 51.52, 25.3, '12.00', 'floor_count'),
    building('SYN-B-0003', 51.501, 25.3, '21.00', '3dglobfp'),
    building('SYN-B-0004', 51.5, 25.3, null),
  ];
  it('extrudes each building to its own height and never a heightless one', () => {
    const selection = shadowSelection(rows, VIEW, 2);
    const layers = buildingLayers(rows, selection);
    expect(() => verifyBuildingLayers(layers, 2)).not.toThrow();
    const [rest, shadows] = layers as [
      SolidPolygonLayer<BuildingRow>,
      SolidPolygonLayer<BuildingRow>,
    ];
    expect(rest.id).toBe(BUILDINGS_LAYER);
    expect(shadows.id).toBe(SHADOWS_LAYER);
    expect(
      (rest.props.data as BuildingRow[]).map((row) => row.building_key),
    ).toEqual(['SYN-B-0002']);
    expect(
      (shadows.props as unknown as { shadowEnabled: boolean }).shadowEnabled,
    ).toBe(true);
    expect(
      (rest.props as unknown as { shadowEnabled: boolean }).shadowEnabled,
    ).toBe(false);
    const elevation = shadows.props.getElevation as (
      row: BuildingRow,
    ) => number;
    expect(elevation(rows[0]!)).toBe(30);
  });
  it('plant: an extrusion by a data value fails', () => {
    const planted = new SolidPolygonLayer<BuildingRow & { value: number }>({
      id: BUILDINGS_LAYER,
      data: [{ ...rows[1]!, value: 48 }],
      extruded: true,
      getPolygon: (row) => row.footprint,
      getElevation: (row) => row.value,
      ...({ shadowEnabled: false } as object),
    });
    expect(() => verifyBuildingLayers([planted], 2)).toThrow(
      'extrusion_not_own_height',
    );
  });
  it('plant: a building without a height that casts a shadow fails', () => {
    const planted = new SolidPolygonLayer<BuildingRow>({
      id: SHADOWS_LAYER,
      data: [rows[3]!],
      extruded: true,
      getPolygon: (row) => row.footprint,
      getElevation: () => 10,
    });
    expect(() => verifyBuildingLayers([planted], 2)).toThrow(
      'shadow_without_height',
    );
  });
  it('plant: a view over the cap that draws more shadows than the cap fails', () => {
    const planted = buildingLayers(rows, {
      casting: rows.slice(0, 3),
      limited: true,
    });
    expect(() => verifyBuildingLayers(planted, 2)).toThrow('shadow_over_cap');
  });
  it('plant: a renamed extrusion by a data value is refused as unexpected', () => {
    const planted = new SolidPolygonLayer<BuildingRow & { value: number }>({
      id: 'towers:value',
      data: [{ ...rows[1]!, value: 48 }],
      extruded: true,
      getPolygon: (row) => row.footprint,
      getElevation: (row) => row.value,
    });
    expect(() => verifyBuildingLayers([planted], 2)).toThrow(
      'building_layer_unexpected',
    );
  });
  it('refuses a building layer given twice', () => {
    const [rest] = buildingLayers(rows, shadowSelection(rows, VIEW, 2));
    expect(() => verifyBuildingLayers([rest!, rest!], 2)).toThrow(
      'building_layer_unexpected',
    );
  });
  it('refuses a building layer of another type', () => {
    const planted = new ScatterplotLayer<BuildingRow>({
      id: SHADOWS_LAYER,
      data: [rows[0]!],
      getPosition: () => [51.5, 25.3],
    });
    expect(() => verifyBuildingLayers([planted], 2)).toThrow(
      'building_layer_type',
    );
  });
  it.each([0, -1, 1.5, Number.NaN, Infinity])(
    'refuses the cap %s at the verifier itself',
    (cap) => {
      const layers = buildingLayers(rows, shadowSelection(rows, VIEW, 2));
      expect(() => verifyBuildingLayers(layers, cap)).toThrow(
        'shadow_cap_invalid',
      );
    },
  );
  it("turns the sun light's experimental shadow on only when asked", () => {
    const timestamp = clockTimestamp('2026-06-01', 0.5)!;
    expect(new ClockLight(timestamp, () => undefined).shadow).toBe(false);
    expect(new ClockLight(timestamp, () => undefined, true).shadow).toBe(true);
  });
});

describe('the clock overlay takes verified building layers only', () => {
  const rows = [
    building('SYN-B-0001', 51.5, 25.3, '30.00'),
    building('SYN-B-0002', 51.52, 25.3, '12.00', 'floor_count'),
  ];
  it('refuses layers over the cap and lights shadows only with buildings', async () => {
    const { attachClock } = await import('../../src/stage/layers/overlay');
    const { MapLibreOverlay } = await import('@deck.gl/maplibre');
    const overlay = new MapLibreOverlay({ interleaved: true, layers: [] });
    const clock = attachClock(overlay, []);
    const timestamp = clockTimestamp('2026-06-01', 0.5)!;
    clock.setClock(timestamp);
    const light = () => {
      const effect = (overlay as unknown as { _props: { effects: unknown[] } })
        ._props.effects[0] as unknown as {
        directionalLights: { shadow: boolean }[];
      };
      return effect.directionalLights[0]?.shadow;
    };
    expect(light()).toBe(false);
    const over = buildingLayers(rows, { casting: rows, limited: false });
    expect(() => clock.setBuildings(over, 1)).toThrow('shadow_over_cap');
    clock.setBuildings(buildingLayers(rows, shadowSelection(rows, VIEW, 1)), 1);
    expect(light()).toBe(true);
  });
  it.each([
    [
      'an unexpected layer',
      () => [
        new SolidPolygonLayer<BuildingRow>({
          id: 'towers:value',
          data: rows,
          getPolygon: (row) => row.footprint,
        }),
      ],
      1,
      'building_layer_unexpected',
    ],
    [
      'a NaN cap',
      () => buildingLayers(rows, shadowSelection(rows, VIEW, 1)),
      Number.NaN,
      'shadow_cap_invalid',
    ],
  ])(
    'setBuildings refuses %s and keeps what it showed',
    async (_name, layers, cap, reason) => {
      const { attachClock } = await import('../../src/stage/layers/overlay');
      const { MapLibreOverlay } = await import('@deck.gl/maplibre');
      const overlay = new MapLibreOverlay({ interleaved: true, layers: [] });
      const clock = attachClock(overlay, []);
      expect(() => clock.setBuildings(layers(), cap)).toThrow(reason);
      const shown = (
        overlay as unknown as { _props: { layers: { id: string }[] } }
      )._props.layers;
      expect(shown.some((layer) => layer.id.startsWith('buildings:'))).toBe(
        false,
      );
    },
  );
});
