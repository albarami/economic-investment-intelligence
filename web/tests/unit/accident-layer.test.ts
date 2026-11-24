/**
 * S3-T12 accident context: each plant changes one input of the mounted
 * invented scene and asserts its own closed code (L-1409).
 */
import { describe, expect, it } from 'vitest';

import {
  ACCIDENT_HTTP,
  accidentScene,
  boundScene,
  chainRegistry,
  NOT_TEXT,
  type MountedChain,
  type SceneParts,
} from '../fixtures/accident-scene';
import type { Fact } from '../../src/facts/types';
import { acceptPayload } from '../../src/stage/layers/refuse';

/** The zone fact of the other mounted row (source zone 52). */
const OTHER_ZONE_FACT =
  ACCIDENT_HTTP.accidents.payload.layers[0]!.features[1]!.source_zone_fact_id;

function verdict(change?: (parts: SceneParts) => void) {
  const { body, registry } = boundScene(change);
  const result = acceptPayload(body.payload, registry);
  return result.ok ? 'ok' : result.code;
}

/** Changes one input of the first row's zone fact or its mounted chain. */
function zoneVerdict(change: (zone: Fact, chain: MountedChain) => void) {
  const body = accidentScene();
  const zoneId = body.payload.layers[0]!.features[0]!.source_zone_fact_id!;
  const chains = structuredClone(ACCIDENT_HTTP.chains);
  change(
    body.facts.find((fact) => fact.fact_id === zoneId)!,
    chains[zoneId]!,
  );
  const result = acceptPayload(body.payload, chainRegistry(body.facts, chains));
  return result.ok ? 'ok' : result.code;
}

describe('accident context beside planned rail', () => {
  it('accepts the mounted outlines and the planned rail context', () => {
    const { body, registry } = boundScene();
    const result = acceptPayload(body.payload, registry);
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const [accidents, rail] = result.draw.layers;
    expect(accidents!.key).toBe('accidents');
    expect(accidents!.filled).toBe(false);
    expect(accidents!.layerType).toBe('GeoJsonLayer');
    expect(accidents!.features.map((f) => f.source_zone)).toEqual(['51', '52']);
    expect(rail!.key).toBe('rail_plan');
    expect(result.draw.visibleHero).toBeNull();
  });

  it.each([
    [
      'outline to point',
      'accident_point_map',
      (p: SceneParts) => {
        p.accident.geometry_kind = 'point';
      },
    ],
    [
      'outline to hex',
      'accident_point_map',
      (p: SceneParts) => {
        p.accident.geometry_kind = 'hex';
      },
    ],
    [
      'outline to fill',
      'outline_filled',
      (p: SceneParts) => {
        p.accident.geometry_kind = 'fill';
      },
    ],
    [
      'filled false to true',
      'outline_filled',
      (p: SceneParts) => {
        p.accidents.filled = true;
      },
    ],
    [
      'geography to another zone',
      'accident_geography_allocation',
      (p: SceneParts) => {
        p.accident.geography_code = 'zone:INVENTED-zone-b';
      },
    ],
    [
      'label to a safety verdict',
      'accident_safety_verdict',
      (p: SceneParts) => {
        p.accident.label_key = 'zone_safe';
      },
    ],
    [
      'label removed',
      'accident_safety_verdict',
      (p: SceneParts) => {
        delete p.accident.label_key;
      },
    ],
    [
      'caveat removed',
      'accident_caveat_missing',
      (p: SceneParts) => {
        p.accident.caveat_keys = [];
      },
    ],
    [
      'count binding removed',
      'legend_count_unbound',
      (p: SceneParts) => {
        delete p.accident.fact_id;
      },
    ],
    // RV1 finding 1: the accident feature holds only its reviewed keys.
    [
      'safety prose in words',
      'accident_field_unexpected',
      (p: SceneParts) => {
        p.accident.words = { permitted_use: 'This zone is safe' };
      },
    ],
    [
      'a status field',
      'accident_field_unexpected',
      (p: SceneParts) => {
        p.accident.status_key = 'safe';
      },
    ],
    // RV1 finding 1 sweep: a presentation field only on its owning layer.
    [
      'permitted use on a rail line',
      'presentation_field_unexpected',
      (p: SceneParts) => {
        p.line.words = { permitted_use: 'Invented use' };
      },
    ],
    [
      'an unreviewed word on a rail line',
      'presentation_field_unexpected',
      (p: SceneParts) => {
        p.line.words = { verdict: 'Invented verdict' };
      },
    ],
    [
      'plot status on a rail line',
      'presentation_field_unexpected',
      (p: SceneParts) => {
        p.line.status_key = 'permitted_empty';
      },
    ],
    [
      'an address on a rail line',
      'presentation_field_unexpected',
      (p: SceneParts) => {
        p.line.address = { zone: 'INVENTED', street: 'A', building: 'B' };
      },
    ],
    // RV1 finding 2: the zone reference binds the count's own release row.
    [
      'source zone removed',
      'accident_zone_unbound',
      (p: SceneParts) => {
        delete p.accident.source_zone;
      },
    ],
    [
      'source zone binding removed',
      'accident_zone_unbound',
      (p: SceneParts) => {
        delete p.accident.source_zone_fact_id;
      },
    ],
    [
      'source zone changed',
      'accident_zone_mismatch',
      (p: SceneParts) => {
        p.accident.source_zone = '52';
      },
    ],
    [
      'source zone bound to another row',
      'accident_zone_mismatch',
      (p: SceneParts) => {
        p.accident.source_zone_fact_id = OTHER_ZONE_FACT;
      },
    ],
    [
      'station planned to operating',
      'station_as_operating',
      (p: SceneParts) => {
        p.station.status_key = 'operating';
      },
    ],
    [
      'line to operating',
      'rail_as_operating',
      (p: SceneParts) => {
        p.line.status_key = 'operating';
      },
    ],
  ] as const)('refuses %s with %s', (_name, code, change) => {
    expect(verdict(change)).toBe(code);
  });

  // CF1 finding 2: each zone reference is a nonempty string before any use;
  // one field and one malformed value at a time, never a thrown error.
  it.each(
    (['source_zone', 'source_zone_fact_id'] as const).flatMap((field) =>
      NOT_TEXT.map(([kind, value]) => [field, kind, value] as const),
    ),
  )('refuses %s as %s with accident_zone_unbound', (field, _kind, value) => {
    expect(
      verdict((p) => {
        (p.accident as unknown as Record<string, unknown>)[field] = value;
      }),
    ).toBe('accident_zone_unbound');
  });

  it.each(['source_zone', 'source_zone_fact_id'] as const)(
    'refuses %s holding its own text in a list with accident_zone_unbound',
    (field) => {
      expect(
        verdict((p) => {
          const row = p.accident as unknown as Record<string, unknown>;
          row[field] = [row[field]];
        }),
      ).toBe('accident_zone_unbound');
    },
  );

  // RV1 finding 2: each condition of the zone binding, one input at a time.
  // Lineage equality fixes the zone's table and release to the count's.
  it('accepts the unchanged zone fact (control)', () => {
    expect(zoneVerdict(() => {})).toBe('ok');
  });

  it.each([
    [
      'another metric',
      (_zone: Fact, chain: MountedChain) => {
        chain.binding.metricKey = 'accident_count';
      },
    ],
    [
      'another provenance',
      (zone: Fact) => {
        // The registry refuses any other class on the count's public
        // lineage (provenance_class) but resolves a suppressed fact as
        // withheld; a withheld zone reference never shows a zone.
        zone.provenance = 'suppressed';
      },
    ],
    [
      'another unit',
      (zone: Fact) => {
        zone.unit = 'calendar_year';
      },
    ],
    [
      'another lineage of the same table',
      (zone: Fact, chain: MountedChain) => {
        chain.lineage.lineageId = 'lin_pub_accident_zone_other';
        zone.lineage_ref = 'lin_pub_accident_zone_other';
      },
    ],
    [
      'another period',
      (zone: Fact) => {
        zone.period = '2023';
      },
    ],
    [
      'another geography',
      (zone: Fact) => {
        zone.geography = {
          kind: 'public',
          public_code: 'zone:INVENTED-zone-b',
        };
      },
    ],
    [
      'another value',
      (zone: Fact) => {
        zone.value = '52';
      },
    ],
  ] as const)('refuses a zone fact with %s', (_name, change) => {
    expect(zoneVerdict(change)).toBe('accident_zone_mismatch');
  });

  it('refuses a zone fact whose chain does not resolve', () => {
    expect(
      zoneVerdict((zone) => {
        zone.release_id = 'rel-INVENTED-other';
      }),
    ).toBe('accident_zone_mismatch');
  });

  it('keeps a planned line whose status is planned', () => {
    expect(
      verdict((p) => {
        p.line.status_key = 'planned';
      }),
    ).toBe('ok');
  });
});

describe('planned rail beside accidents on the map', () => {
  // RV1 finding 4 browser proof: a station drawn at deck's default radius
  // (one metre) is below one pixel and cannot be seen or picked.
  it('draws every planned station at a pixel size', async () => {
    const { overlayFor, COMPANY_POINT_RADIUS_PX } =
      await import('../../src/stage/layers/overlay');
    const { body, registry } = boundScene();
    const overlay = overlayFor(body.payload, null, registry) as unknown as {
      _props: {
        layers: {
          id: string;
          props: { getRadius: unknown; radiusUnits: string };
        }[];
      };
    };
    const stations = overlay._props.layers.find(
      (item) => item.id === 'rail_plan:ScatterplotLayer',
    );
    expect(stations?.props.radiusUnits).toBe('pixels');
    expect(stations?.props.getRadius).toBe(COMPANY_POINT_RADIUS_PX);
  });
});
