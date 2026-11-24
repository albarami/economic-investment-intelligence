// @vitest-environment jsdom
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import type { FetchLike } from '../../src/api/areas';
import { plainPort } from '../fixtures/plain-port';
import { AnswerShell } from '../../src/shell/AnswerShell';
import {
  lastPostedDriveBody,
  registerFetch,
  registerLayers,
  registerPort,
  releaseAreaClient,
  releasePort,
  submitArea,
} from '../../src/state/area-actions';
import { clearArea, getArea } from '../../src/state/store';
import type {
  LayerFeature,
  LayerPayload,
} from '../../src/stage/layers/payload';

const SHAPE_ID = 'cd'.repeat(32);
const RING = [
  [0, 0],
  [1, 0],
  [1, 1],
  [0, 1],
  [0, 0],
] as const;

function point(id: string, position?: readonly [number, number]): LayerFeature {
  return {
    feature_id: id,
    metric_key: 'place_listing',
    provenance: 'public',
    subject: 'place',
    geometry_kind: 'point',
    position,
  };
}

function layers(): LayerPayload {
  return {
    layers: [
      {
        key: 'public_places',
        visible: true,
        source_chain_fact_id: 'fact-places',
        source_id: 'src-places',
        features: [point('inside', [0.2, 0.2]), point('outside', [2, 2])],
      },
    ],
    sources: [],
    gazetteer_points: [],
  };
}

function envelope(status: string, outline: unknown) {
  return {
    tool: 'make_area',
    call_id: 'INVENTED-call',
    engine: 'embedded',
    blocks: [],
    facts: [],
    caveat_keys: [],
    status,

    release_id: 'rel-draw',
    payload:
      status === 'OK'
        ? {
            area_id: 'area-draw',
            point_feature_ids: { public_places: ['inside'] },
            outline,
            units: { cells: ['unit-a', 'unit-b'] },
            snap_report: { opaque: true },
            record: {
              anchor_cell: null,
              traffic: 'free_flow',
              shape: 'polygon',
            },
          }
        : null,
  };
}

function installFetch(status: string, outline: unknown): { calls: string[] } {
  const calls: string[] = [];
  const fetchLike: FetchLike = async (path, init) => {
    calls.push(`${path}:${init.body}`);
    if (path.endsWith('/shapes')) {
      return { status: 201, json: async () => ({ shape_id: SHAPE_ID }) };
    }
    return { status: 200, json: async () => envelope(status, outline) };
  };
  registerFetch(fetchLike);
  return { calls };
}

function mount(language: 'en' | 'ar' = 'en') {
  return render(
    <AnswerShell language={language} theme="dark" extractUrl={null} />,
  );
}

describe('area drawing', () => {
  let token = 0;

  beforeEach(() => {
    clearArea();
    token = registerPort(plainPort(320, 320));
    registerLayers(layers());
  });

  afterEach(() => {
    cleanup();
    clearArea();
    releasePort(token);
    releaseAreaClient();
  });

  it('keeps the tool group outside the left-to-right stage', () => {
    const { container } = mount('ar');
    const stage = container.querySelector('.stage');
    const tools = container.querySelector('.draw-tools');
    expect(stage?.getAttribute('dir')).toBe('ltr');
    expect(tools?.getAttribute('dir')).toBe('rtl');
    expect(stage?.contains(tools ?? null)).toBe(false);
    expect(container.querySelector('.stage .draw-tools')).toBeNull();
  });

  it('draws a polygon from the keyboard and filters public features to the outline', async () => {
    const { calls } = installFetch('OK', {
      type: 'Polygon',
      coordinates: [RING],
    });
    const { container } = mount();
    fireEvent.click(screen.getByRole('button', { name: 'Polygon' }));
    const hair = () => screen.getByRole('button', { name: 'Crosshair' });
    fireEvent.keyDown(hair(), { key: 'Enter' });
    fireEvent.keyDown(hair(), { key: 'ArrowRight' });
    fireEvent.keyDown(hair(), { key: 'Enter' });
    fireEvent.keyDown(hair(), { key: 'ArrowDown' });
    fireEvent.keyDown(hair(), { key: 'Enter' });
    const first = screen.getAllByRole('button', { name: 'Vertex' })[0];
    expect(first).toBeDefined();
    fireEvent.focus(first as HTMLElement);
    fireEvent.keyDown(first as HTMLElement, { key: 'Enter' });
    expect(container.querySelector('[data-closed="yes"]')).not.toBeNull();
    await act(async () => {
      await submitArea();
    });
    expect(calls.some((call) => call.startsWith('/api/areas/shapes'))).toBe(
      true,
    );
    const make = calls.find((call) => call.startsWith('/api/tools/make_area'));
    expect(make?.includes('situation')).toBe(false);
    expect(container.querySelector('[data-line="accent"]')).not.toBeNull();
    expect(container.querySelector('circle')).toBeNull();
    expect(
      container.querySelector('[data-part="no-mode"]')?.textContent,
    ).toContain('no mode');
    expect(
      container.querySelector('.brief-column [data-part="area-summary"]'),
    ).not.toBeNull();
    expect(
      getArea().filtered?.layers[0]?.features.map(
        (feature) => feature.feature_id,
      ),
    ).toEqual(['inside']);
    expect(container.textContent?.includes('opaque')).toBe(false);
    expect(container.textContent?.includes('unit-a')).toBe(false);
  });

  it('places vertices from touch and closes on the first knob', () => {
    mount();
    fireEvent.click(screen.getByRole('button', { name: 'Polygon' }));
    const overlay = document.querySelector('.area-overlay');
    expect(overlay).not.toBeNull();
    for (const point of [
      { clientX: 40, clientY: 40 },
      { clientX: 120, clientY: 40 },
      { clientX: 120, clientY: 120 },
    ]) {
      fireEvent.pointerDown(overlay as Element, {
        isPrimary: true,
        pointerType: 'touch',
        button: 0,
        ...point,
      });
    }
    expect(getArea().session.vertices).toHaveLength(3);
    fireEvent.click(
      screen.getAllByRole('button', { name: 'Vertex' })[0] as HTMLElement,
    );
    expect(getArea().session.closed).toBe(true);
  });

  it('shows the distance chips, including 1 km, only through a fact chip', () => {
    const { container } = mount();
    expect(container.querySelector('[data-fact-chip]')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Radius' }));
    const chips = container.querySelectorAll(
      '[data-part="preset"] [data-fact-chip]',
    );
    expect(chips).toHaveLength(3);
    expect(chips[2]?.querySelector('.chip-num')?.textContent).toBe('1');
    expect(chips[2]?.querySelector('.chip-unit')?.textContent).toBe('km');
    expect(chips[2]?.querySelector('.chip-tag')?.textContent).toBe(
      'Your inputs',
    );
  });

  it('posts a flat drive body of latitude, longitude, mode and cutoff', async () => {
    installFetch('OK', {
      type: 'Circle',
      coordinates: [0.5, 0.5],
      radius_m: 250,
    });
    const { container } = mount();
    fireEvent.click(screen.getByRole('button', { name: 'Travel time' }));
    fireEvent.keyDown(screen.getByRole('button', { name: 'Crosshair' }), {
      key: 'Enter',
    });
    fireEvent.click(
      container.querySelector('[data-preset="drive-a"]') as Element,
    );
    await act(async () => {
      await submitArea();
    });
    const body = lastPostedDriveBody();
    expect(
      body && typeof body === 'object' ? Object.keys(body).sort() : [],
    ).toEqual(['cutoff', 'latitude', 'longitude', 'mode']);
    expect(JSON.stringify(body).includes('situation')).toBe(false);
    expect(JSON.stringify(body).includes('hour_key')).toBe(false);
    const flow = container.querySelector('[data-part="free-flow"]');
    expect(flow?.textContent).toBe('Free-flow drive');
    expect(flow?.textContent?.match(/\p{Nd}/u)).toBeNull();
    expect(container.querySelector('[data-outline="circle"]')).not.toBeNull();
    expect(container.querySelector('circle')).toBeNull();
    expect(
      container.querySelector('[data-part="mode-word"]')?.textContent,
    ).toBe('Drive');
  });

  it('draws no circle and no outline when a pin is refused', async () => {
    installFetch('OUT_OF_SCOPE', null);
    const { container } = mount();
    fireEvent.click(screen.getByRole('button', { name: 'Radius' }));
    fireEvent.keyDown(screen.getByRole('button', { name: 'Crosshair' }), {
      key: 'Enter',
    });
    fireEvent.click(
      container.querySelector('[data-preset="distance-a"]') as Element,
    );
    await act(async () => {
      await submitArea();
    });
    expect(container.querySelector('[data-part="pin"]')).not.toBeNull();
    expect(container.querySelector('[data-part="outline"]')).toBeNull();
    expect(container.querySelector('circle')).toBeNull();
    expect(
      container.querySelector('[data-part="refusal"]')?.textContent,
    ).toContain('outside the mapped land');
    expect(
      container.querySelectorAll('[data-part="preset"]').length,
    ).toBeGreaterThan(0);
  });

  it('shows a governed no-data reason and no outline', async () => {
    installFetch('NO_DATA', null);
    const { container } = mount();
    fireEvent.click(screen.getByRole('button', { name: 'Radius' }));
    fireEvent.keyDown(screen.getByRole('button', { name: 'Crosshair' }), {
      key: 'Enter',
    });
    fireEvent.click(
      container.querySelector('[data-preset="distance-b"]') as Element,
    );
    await act(async () => {
      await submitArea();
    });
    expect(container.querySelector('[data-part="outline"]')).toBeNull();
    expect(container.querySelector('[data-status="NO_DATA"]')).not.toBeNull();
    expect(getArea().filtered).toBeNull();
  });

  it('draws the strong line for a refused polygon and not for a refused pin', async () => {
    const { calls } = installFetch('INVALID_ARGUMENT', null);
    const { container } = mount();
    fireEvent.click(screen.getByRole('button', { name: 'Polygon' }));
    fireEvent.keyDown(screen.getByRole('button', { name: 'Crosshair' }), {
      key: 'Enter',
    });
    await act(async () => {
      await submitArea();
    });
    expect(calls).toEqual([]);
    expect(container.querySelector('[data-line="strong"]')).not.toBeNull();
    expect(
      container.querySelector('[data-part="summary-reason"]')?.textContent,
    ).toContain('Add vertices');
  });
});
