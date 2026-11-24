import { describe, expect, it } from 'vitest';
import * as requests from '../../src/controls/area-request';

import {
  assembleDriveBody,
  assemblePinBody,
  assemblePlaceBody,
  assembleShapeBody,
  driveBodyExact,
} from '../../src/controls/area-request';

const PIN = { latitude: 0.2, longitude: 0.3 };

describe('drive body fields', () => {
  it.each(['district:INVENTED-null', 'zone:INVENTED_zone', 'municipality:7'])(
    'preserves administrative gazetteer key %s without a pin',
    (key) => {
      expect(assemblePlaceBody(key, 'distance-a')).toEqual({
        place_key: key,
        mode: 'distance',
        cutoff: 250,
      });
    },
  );
  it('carries the exact selected key and only an existing closed preset', () => {
    expect(assemblePlaceBody('INVENTED-null', 'distance-a')).toEqual({
      place_key: 'INVENTED-null',
      mode: 'distance',
      cutoff: 250,
    });
    expect(assemblePlaceBody('INVENTED-garden', 'walk-b')).toEqual({
      place_key: 'INVENTED-garden',
      mode: 'walk',
      cutoff: 10,
    });
    expect(assemblePlaceBody('INVENTED-garden', 'drive-c')).toEqual({
      place_key: 'INVENTED-garden',
      mode: 'drive',
      cutoff: 15,
    });
    expect(assemblePlaceBody('activity:INVENTED', 'distance-a')).toBeNull();
    expect(assemblePlaceBody('INVENTED-garden', 'INVENTED-preset')).toBeNull();
  });
  it('exposes the selected key plus closed preset assembler', () => {
    expect(typeof Reflect.get(requests, 'assemblePlaceBody')).toBe('function');
  });
  it.each([
    'district:',
    'district:../INVENTED',
    'register:INVENTED',
    'district:' + '7'.repeat(8),
    'zone:INVENTED-' + '7'.repeat(11),
  ])('refuses unsafe key %s before posting', (key) => {
    expect(assemblePlaceBody(key, 'distance-a')).toBeNull();
  });
  it('holds exactly latitude, longitude, mode and cutoff', () => {
    const body = assembleDriveBody(PIN, 10);
    expect(Object.keys(body).sort()).toEqual([
      'cutoff',
      'latitude',
      'longitude',
      'mode',
    ]);
    expect(body).toEqual({
      latitude: PIN.latitude,
      longitude: PIN.longitude,
      mode: 'drive',
      cutoff: 10,
    });
    expect(driveBodyExact(body)).toBe(true);
  });

  it('rejects a drive body that carries situation or an hour field', () => {
    const valid = assembleDriveBody(PIN, 10);
    expect(driveBodyExact(valid)).toBe(true);
    const poisoned = { ...valid, situation: 'weekday_lunch' };
    expect(driveBodyExact(poisoned)).toBe(false);
    expect(
      driveBodyExact({ ...assembleDriveBody(PIN, 5), hour_key: 'h' }),
    ).toBe(false);
    expect(
      driveBodyExact({ ...assembleDriveBody(PIN, 15), summer: true }),
    ).toBe(false);
    expect(
      driveBodyExact({ ...assembleDriveBody(PIN, 10), day_key: 'd' }),
    ).toBe(false);
  });

  it('refuses a cutoff outside the closed lists', () => {
    expect(assemblePinBody(PIN, 'drive', 20).ok).toBe(false);
    expect(assemblePinBody(PIN, 'distance', 1000).ok).toBe(true);
  });

  it('rejects a nested pin and an unknown mode', () => {
    const nested = { pin: PIN, mode: 'drive' as const, cutoff: 10 };
    expect(driveBodyExact(nested)).toBe(false);
    const body = assembleDriveBody(PIN, 10);
    expect(Object.keys(body).sort()).toEqual([
      'cutoff',
      'latitude',
      'longitude',
      'mode',
    ]);
    expect(body).toEqual({
      latitude: PIN.latitude,
      longitude: PIN.longitude,
      mode: 'drive',
      cutoff: 10,
    });
    expect(assemblePinBody(PIN, 'sail' as 'drive', 10).ok).toBe(false);
  });

  it('closes a polygon ring by repeating the first vertex', () => {
    const shaped = assembleShapeBody([
      { longitude: 0.1, latitude: 0.1 },
      { longitude: 0.4, latitude: 0.1 },
      { longitude: 0.4, latitude: 0.4 },
    ]);
    expect(shaped.ok).toBe(true);
    if (!shaped.ok) return;
    const ring = shaped.body.geometry.coordinates[0];
    expect(ring?.[0]).toEqual(ring?.[ring.length - 1]);
    expect(shaped.body.geometry.type).toBe('Polygon');
  });

  it('refuses a ring of fewer than three vertices', () => {
    expect(assembleShapeBody([PIN, { latitude: 0.4, longitude: 0.4 }]).ok).toBe(
      false,
    );
  });
});
