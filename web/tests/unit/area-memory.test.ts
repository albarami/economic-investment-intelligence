import { describe, expect, it } from 'vitest';

import {
  addressSnapshot,
  clearArea,
  commitView,
  getArea,
  guardStorageWrite,
  holdsCoordinateText,
  replaceArea,
} from '../../src/state/store';

describe('area memory', () => {
  it('keeps vertices out of the address and out of browser storage', () => {
    clearArea();
    const area = getArea();
    replaceArea({
      ...area,
      session: {
        ...area.session,
        vertices: [
          { latitude: 0.2, longitude: 0.3 },
          { latitude: 0.4, longitude: 0.5 },
          { latitude: 0.4, longitude: 0.2 },
        ],
        mode: 'distance',
        cutoff: 250,
      },
    });
    const snap = addressSnapshot(getArea());
    expect(snap).toEqual({ mode: 'distance', cutoff: 250, shapeId: null });
    expect(JSON.stringify(snap).includes('latitude')).toBe(false);
    expect(holdsCoordinateText(JSON.stringify(snap))).toBe(false);
    const writes: string[] = [];
    const storage = {
      setItem(_key: string, value: string) {
        writes.push(value);
      },
    };
    expect(
      guardStorageWrite(
        storage,
        'area',
        JSON.stringify(getArea().session.vertices),
      ),
    ).toBe(false);
    expect(writes).toEqual([]);
    const committed = commitView(storage, { search: '?mode=distance' });
    expect(committed.search).toBe('?mode=distance');
    expect(writes).toEqual([]);
    clearArea();
  });
});
