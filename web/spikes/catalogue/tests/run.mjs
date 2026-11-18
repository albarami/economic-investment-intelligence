import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const cwd = fileURLToPath(new URL('../../../', import.meta.url));
const env = { PATH: process.env.PATH, PYTHONDONTWRITEBYTECODE: '1' };
for (const args of [
  [
    'node_modules/typescript/bin/tsc',
    '--noEmit',
    '-p',
    'spikes/catalogue/tsconfig.json',
  ],
  [
    '--experimental-strip-types',
    '--test',
    '--test-concurrency=2',
    'spikes/catalogue/tests/guards.node-test.mjs',
    'scripts/tests/catalogue-isolation.node-test.mjs',
  ],
  ['--experimental-strip-types', 'spikes/catalogue/verify-evidence.mjs'],
]) {
  const result = spawnSync(process.execPath, args, {
    cwd,
    env,
    stdio: 'inherit',
  });
  if (result.status !== 0) {
    process.exitCode = result.status ?? 1;
    break;
  }
}
