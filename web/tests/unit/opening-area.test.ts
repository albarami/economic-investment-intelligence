import { afterEach, expect, it } from 'vitest';
import {
  registerFetch,
  registerLayers,
  releaseAreaClient,
  resetArea,
  submitPlaceArea,
  dispatch,
  selectedAreaRequest,
} from '../../src/state/area-actions';
import { getArea } from '../../src/state/store';
import type { LayerPayload } from '../../src/stage/layers/payload';

afterEach(() => {
  resetArea();
  registerLayers(null);
  releaseAreaClient();
});

it('rebinds a changed layer to the exact selected-area membership without resubmission', async () => {
  registerFetch(async () => ({
    status: 200,
    json: async () => ({
      tool: 'make_area',
      status: 'OK',
      call_id: 'INVENTED-call',
      engine: 'embedded',
      release_id: 'INVENTED-release',
      blocks: [],
      facts: [],
      caveat_keys: [],
      payload: {
        area_id: 'area-INVENTED',
        units: {},
        snap_report: null,
        record: { anchor_cell: null, traffic: 'free_flow', shape: 'polygon' },
        outline: {
          type: 'Polygon',
          coordinates: [
            [
              [0, 0],
              [1, 0],
              [1, 1],
              [0, 0],
            ],
          ],
        },
        point_feature_ids: { public_places: ['inside'] },
      },
    }),
  }));
  await submitPlaceArea('INVENTED-place', 'walk-a');
  const layer: LayerPayload = {
    sources: [],
    gazetteer_points: [],
    layers: [
      {
        key: 'public_places',
        source_chain_fact_id: 'f-INVENTED',
        source_id: 'src-INVENTED',
        visible: true,
        features: ['inside', 'outside'].map((feature_id) => ({
          feature_id,
          geometry_kind: 'point',
          metric_key: 'place_listing',
          provenance: 'public',
          subject: 'place',
          position: [0.5, 0.5],
        })),
      },
    ],
  };
  registerLayers(layer);
  expect(
    getArea().filtered?.layers[0]?.features.map(
      (feature) => feature.feature_id,
    ),
  ).toEqual(['inside']);
});

function accepted() {
  return {
    status: 200,
    json: async () => ({
      tool: 'make_area',
      status: 'OK',
      call_id: 'INVENTED-call',
      engine: 'embedded',
      release_id: 'INVENTED-release',
      blocks: [],
      facts: [],
      caveat_keys: [],
      payload: {
        area_id: 'area-INVENTED',
        units: {},
        snap_report: null,
        record: { anchor_cell: null, traffic: 'free_flow', shape: 'polygon' },
        outline: {
          type: 'Polygon',
          coordinates: [
            [
              [0, 0],
              [1, 0],
              [1, 1],
              [0, 0],
            ],
          ],
        },
        point_feature_ids: {},
      },
    }),
  };
}

it.each(['escape', 'select-tool'] as const)(
  '%s forgets the request of an accepted area',
  async (type) => {
    registerFetch(async () => accepted());
    await submitPlaceArea('INVENTED-place-a', 'walk-a');
    expect(selectedAreaRequest()).toEqual({
      place_key: 'INVENTED-place-a',
      mode: 'walk',
      cutoff: 5,
    });
    dispatch(type === 'escape' ? { type } : { type, tool: 'polygon' });
    expect(selectedAreaRequest()).toBeNull();
  },
);

it('a late area answer cannot remember an escaped selection before the next accepted area', async () => {
  let finish!: (reply: ReturnType<typeof accepted>) => void;
  registerFetch(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const pendingA = submitPlaceArea('INVENTED-place-a', 'walk-a');
  dispatch({ type: 'escape' });
  finish(accepted());
  await pendingA;
  expect(selectedAreaRequest()).toBeNull();
  // Submissions are serialized by the existing lock: B is accepted after A settles.
  registerFetch(async () => accepted());
  await submitPlaceArea('INVENTED-place-b', 'walk-a');
  expect(selectedAreaRequest()).toEqual({
    place_key: 'INVENTED-place-b',
    mode: 'walk',
    cutoff: 5,
  });
});
