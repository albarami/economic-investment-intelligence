import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { expect, it } from 'vitest';
import { readEnvelope } from '../../src/api/areas';
import type { LayerPayload } from '../../src/stage/layers/payload';
import { filterPublicToOutline } from '../../src/stage/layers/area-filter';

it('filters the serving layer with membership returned by the actual API', () => {
  const root = resolve(import.meta.dirname, '../../..');
  const exchange = JSON.parse(
    execFileSync(
      '.venv/bin/python',
      ['-m', 'product.tests.test_area_membership_http'],
      {
        cwd: root,
        env: {
          ...process.env,
          PYTHONPATH:
            '.:scripts:scripts/tests:core/src:custodian/src:product/src:gateway/src',
        },
        encoding: 'utf8',
      },
    ),
  ) as { layer: LayerPayload; envelope: unknown };
  const answer = readEnvelope(exchange.envelope);
  expect(answer.kind).toBe('envelope');
  if (answer.kind !== 'envelope') throw new Error('refused typed API envelope');
  const area = answer.envelope.payload;
  expect(area).not.toBeNull();
  if (!area) throw new Error('missing area');
  const filtered = filterPublicToOutline(
    exchange.layer,
    area.outline,
    area.point_feature_ids,
  );
  expect(
    filtered.layers[0]!.features.map((feature) => feature.feature_id).sort(),
  ).toEqual(area.point_feature_ids?.public_places);
  expect(filtered.layers[0]!.features.length).toBeGreaterThan(0);
  const absent = filterPublicToOutline(exchange.layer, area.outline, null);
  expect(absent.layers[0]!.features).toEqual([]);
});
