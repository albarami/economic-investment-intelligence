// @vitest-environment jsdom
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from '../../src/app/App';
import { releaseAreaClient, submitArea } from '../../src/state/area-actions';
import { clearArea, getArea } from '../../src/state/store';

describe('stage plate when no map is constructed', () => {
  afterEach(() => {
    cleanup();
    clearArea();
    releaseAreaClient();
    vi.unstubAllGlobals();
  });

  it('cannot submit a drawing when the map is absent', async () => {
    const calls: string[] = [];
    vi.stubGlobal('fetch', async (input: string) => {
      calls.push(input);
      return { status: 200, json: async () => ({}) };
    });
    clearArea();
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Guided story' }));
    expect(screen.queryByRole('button', { name: 'Use this area' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Polygon' })).toBeNull();
    expect(screen.getByText('Drawing waits for the map.')).toBeTruthy();
    await submitArea();
    expect(calls).toEqual([
      '/api/map-modes',
      '/api/release',
      '/api/layers/zone_electricity_growth',
    ]);
    expect(getArea().session.phase).toBe('idle');
    expect(getArea().session.vertices).toEqual([]);
  });
});
