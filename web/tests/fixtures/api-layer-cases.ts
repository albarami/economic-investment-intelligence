import { execFileSync } from 'node:child_process';

import type { RegistryInput } from '../../src/facts/types';
import type { LayerPayload } from '../../src/stage/layers/payload';

export type ApiLayerCase = {
  status: number;
  body: { payload: LayerPayload };
  registry: RegistryInput;
};

/** An actual API response on every run, not a separately hand-authored payload. */
export function apiLayerCases(): Record<string, ApiLayerCase> {
  return JSON.parse(
    execFileSync(
      'uv',
      [
        'run',
        '--locked',
        'python',
        '-m',
        'product.tests.public_layer_render_fixture',
      ],
      {
        cwd: '..',
        env: {
          ...process.env,
          UV_OFFLINE: '1',
          PYTHONPATH: 'scripts:scripts/tests',
        },
        encoding: 'utf8',
      },
    )
      .trim()
      .split('\n')
      .at(-1)!,
  ) as Record<string, ApiLayerCase>;
}
