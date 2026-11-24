// @vitest-environment jsdom
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { AnswerShell } from '../../src/shell/AnswerShell';
import { getArea, replaceArea, clearArea } from '../../src/state/store';
import {
  registerPort,
  registerFetch,
  releasePort,
  releaseAreaClient,
  submitArea,
} from '../../src/state/area-actions';
import { plainPort } from '../fixtures/plain-port';
let token = 0;
afterEach(() => {
  cleanup();
  releasePort(token);
  releaseAreaClient();
  clearArea();
});
it.each(['polygon', 'pin', 'shape422', 'shape429', 'make422'])(
  'keeps the local %s refusal as presentation only',
  async (kind) => {
    token = registerPort(plainPort(320, 320));
    const calls: string[] = [];
    registerFetch(async (path) => {
      calls.push(path);
      return {
        status: kind === 'shape429' ? 429 : 422,
        json: async () => ({
          error: {
            code: 'INVALID_ARGUMENT',
            message_key: 'invalid_argument',
            error_id: 'INVENTED',
          },
        }),
      };
    });
    const { container } = render(
      <AnswerShell language="en" theme="dark" extractUrl={null} />,
    );
    const area = getArea();
    const polygon = kind.startsWith('shape') || kind === 'polygon';
    act(() =>
      replaceArea({
        ...area,
        session: {
          ...area.session,
          tool: polygon ? 'polygon' : 'radius',
          mode: polygon ? null : 'distance',
          cutoff: polygon ? null : 500,
          pin: kind === 'pin' ? null : { latitude: 1, longitude: 1 },
          closed: kind !== 'polygon',
          vertices:
            kind === 'polygon'
              ? []
              : [
                  { id: 'a', latitude: 0, longitude: 0 },
                  { id: 'b', latitude: 0, longitude: 1 },
                  { id: 'c', latitude: 1, longitude: 1 },
                ],
        },
      }),
    );
    await act(async () => {
      await submitArea();
    });
    expect(getArea().presented).toMatchObject({
      status: 'INVALID_ARGUMENT',
      caveatKeys: [],
      outline: null,
      showRefusal: true,
      showLayers: false,
    });
    expect(getArea().filtered).toBeNull();
    expect(container.querySelector('[data-part="refusal"]')).not.toBeNull();
    if (kind === 'polygon' || kind === 'pin') expect(calls).toEqual([]);
  },
);
