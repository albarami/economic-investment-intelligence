// @vitest-environment jsdom
/**
 * S3-T12, design amendment 4: a drawn selection and the area filter never
 * change an accident outline, its source zone, its period or its bound count.
 */
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';

import { boundScene } from '../fixtures/accident-scene';
import { plainPort } from '../fixtures/plain-port';
import { AnswerShell } from '../../src/shell/AnswerShell';
import {
  registerPort,
  releaseAreaClient,
  releasePort,
} from '../../src/state/area-actions';
import { clearArea, getArea } from '../../src/state/store';

let token = 0;
afterEach(() => {
  cleanup();
  clearArea();
  releasePort(token);
  releaseAreaClient();
  vi.unstubAllGlobals();
});

const SQUARE = {
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

// Inside part of zone a only, and a membership that names no accident key.
for (const membership of [{}, { accidents: ['accidents:51:2024'] }])
  it(`keeps each accident outline whole under a drawn polygon: ${JSON.stringify(membership)}`, async () => {
    clearArea();
    token = registerPort(plainPort(320, 320));
    const { body, registry } = boundScene();
    const before = structuredClone(body.payload.layers[0]!);
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
                outline: SQUARE,
                point_feature_ids: membership,
                units: {},
                snap_report: null,
                record: {
                  anchor_cell: null,
                  traffic: 'free_flow',
                  shape: 'polygon',
                },
              },
            },
    }));
    const view = render(
      <AnswerShell
        language="en"
        theme="dark"
        extractUrl={null}
        registry={registry}
        sourceLayers={body.payload}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Polygon' }));
    const hair = () => screen.getByRole('button', { name: 'Crosshair' });
    fireEvent.keyDown(hair(), { key: 'Enter' });
    fireEvent.keyDown(hair(), { key: 'ArrowRight' });
    fireEvent.keyDown(hair(), { key: 'Enter' });
    fireEvent.keyDown(hair(), { key: 'ArrowDown' });
    fireEvent.keyDown(hair(), { key: 'Enter' });
    const first = screen.getAllByRole('button', { name: 'Vertex' })[0]!;
    fireEvent.focus(first);
    fireEvent.keyDown(first, { key: 'Enter' });
    fireEvent.click(screen.getByRole('button', { name: 'Use this area' }));
    await waitFor(() => expect(getArea().filtered).not.toBeNull());
    // The filtered accident layer is the source layer, field for field.
    expect(getArea().filtered!.layers[0]).toEqual(before);
    expect(
      view.container.querySelector('[data-part="layer-refusal"]'),
    ).toBeNull();
    for (const feature of before.features) {
      const button = view.container.querySelector(
        `[data-feature="${feature.feature_id}"]`,
      )!;
      act(() => fireEvent.click(button));
      const panel = view.container.querySelector(
        '[data-part="feature-panel"][data-layer="accidents"]',
      )!;
      expect(
        panel
          .querySelector('[data-fact-chip="value"]')!
          .getAttribute('data-fact-id'),
      ).toBe(feature.fact_id);
      const context = panel.querySelector('[data-part="accident-context"]')!;
      expect(context.getAttribute('data-zone')).toBe(feature.source_zone);
      expect(context.getAttribute('data-period')).toBe(
        body.facts.find((fact) => fact.fact_id === feature.fact_id)!.period,
      );
      const resolved = registry.resolve(feature.fact_id!);
      expect(resolved.status).toBe('ready');
      if (resolved.status === 'ready')
        expect(resolved.binding.fact.geography).toEqual({
          kind: 'public',
          public_code: feature.geography_code,
        });
    }
  });
