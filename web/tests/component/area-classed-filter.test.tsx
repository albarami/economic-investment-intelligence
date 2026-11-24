// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { areaScene } from '../fixtures/area-source-layers';
import { routeRegistry } from '../fixtures/public-route-registry';
import { AnswerShell } from '../../src/shell/AnswerShell';
import {
  registerPort,
  releasePort,
  releaseAreaClient,
} from '../../src/state/area-actions';
import { clearArea, getArea } from '../../src/state/store';
import { plainPort } from '../fixtures/plain-port';
import { resetUseChoice } from '../../src/stage/layers/land-use';
let token = 0;
afterEach(() => {
  cleanup();
  clearArea();
  releasePort(token);
  releaseAreaClient();
  resetUseChoice();
  vi.unstubAllGlobals();
});
for (const key of ['land_prices', 'zone_electricity_growth', 'zoning'] as const)
  for (const empty of key === 'land_prices' ? [false, true] : [false])
    it(`keeps ${key} whole through mounted ${empty ? 'empty circle' : 'polygon'} submission`, async () => {
      clearArea();
      token = registerPort(plainPort(320, 320));
      const body = areaScene(key);
      const outline = empty
        ? { type: 'Circle', coordinates: [0.7, 0.7], radius_m: 250 }
        : {
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
          };
      vi.stubGlobal('fetch', async (path: string) => ({
        status: path.endsWith('/shapes') ? 201 : 200,
        json: async () =>
          path.endsWith('/shapes')
            ? { shape_id: 'ab'.repeat(32) }
            : {
                tool: 'make_area',
                call_id: 'INVENTED-call',
                release_id: 'INVENTED-release',
                engine: 'embedded',
                status: 'OK',
                blocks: [],
                facts: [],
                caveat_keys: [],
                payload: {
                  area_id: 'INVENTED-area',
                  outline,
                  point_feature_ids: { public_places: empty ? [] : ['inside'] },
                  units: {},
                  snap_report: null,
                  record: {
                    anchor_cell: null,
                    traffic: 'free_flow',
                    shape: empty ? 'circle' : 'polygon',
                  },
                },
              },
      }));
      const view = render(
        <AnswerShell
          language="en"
          theme="dark"
          extractUrl={null}
          registry={routeRegistry(body)}
          sourceLayers={body.payload}
        />,
      );
      fireEvent.click(
        screen.getByRole('button', { name: empty ? 'Radius' : 'Polygon' }),
      );
      const hair = () => screen.getByRole('button', { name: 'Crosshair' });
      fireEvent.keyDown(hair(), { key: 'Enter' });
      if (empty)
        fireEvent.click(
          view.container.querySelector('[data-preset="distance-a"]')!,
        );
      if (!empty) {
        fireEvent.keyDown(hair(), { key: 'ArrowRight' });
        fireEvent.keyDown(hair(), { key: 'Enter' });
        fireEvent.keyDown(hair(), { key: 'ArrowDown' });
        fireEvent.keyDown(hair(), { key: 'Enter' });
        const first = screen.getAllByRole('button', { name: 'Vertex' })[0]!;
        fireEvent.focus(first);
        fireEvent.keyDown(first, { key: 'Enter' });
      }
      fireEvent.click(screen.getByRole('button', { name: 'Use this area' }));
      await waitFor(() => expect(getArea().filtered).not.toBeNull());
      expect(
        view.container.querySelector('[data-part="layer-refusal"]'),
      ).toBeNull();
      expect(
        view.container.querySelector('[data-feature="inside"]') !== null,
      ).toBe(!empty);
      expect(
        view.container.querySelector('[data-feature="outside"]'),
      ).toBeNull();
      expect(getArea().filtered!.layers[1]).toEqual(body.payload.layers[1]);
      if (key === 'zone_electricity_growth')
        for (const zone of body.payload.layers[1]!.not_ranked!) {
          const button = view.container.querySelector(
            `[data-not-ranked="${zone.feature_id}"]`,
          )!;
          expect(button).not.toBeNull();
          act(() => fireEvent.click(button));
          expect(
            view.container
              .querySelector('[data-part="not-ranked-panel"]')
              ?.getAttribute('data-reason'),
          ).toBe(zone.reason_key);
        }
      const features = body.payload.layers[1]!.features.filter(
        (f) => key !== 'land_prices' || f.class_group === 'invented_commercial',
      );
      for (const feature of features)
        expect(
          view.container.querySelector(
            `[data-feature="${feature.feature_id}"]`,
          ),
        ).not.toBeNull();
      for (const group of body.payload.layers[1]!.class_breaks ?? [])
        if (
          group.group_key === null ||
          group.group_key === 'invented_commercial'
        )
          for (const band of group.breaks)
            expect(
              view.container.querySelector(`[data-fact-id="${band.fact_id}"]`),
            ).not.toBeNull();
    });
