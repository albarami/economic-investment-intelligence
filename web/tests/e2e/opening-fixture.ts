/** Built production bundle and actual API; no intercepted API, tile or lineage. */
import { test as base, expect, request } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import path from 'node:path';
import { createServer } from 'node:net';
import { assertNoProviderAttempts } from './no-provider-attempts';
import { startServerGroup, stopServerGroup } from './opening-server.mjs';

const WEB = process.cwd();
const ROOT = path.resolve(WEB, '..');
type Fixture = { origin: string; work: string };
export const test = base.extend<Record<string, never>, { mounted: Fixture }>({
  mounted: [
    async ({ playwright: browserDriver }, provide) => {
      void browserDriver;
      const tmp = path.join(ROOT, '.overnight/tmp');
      mkdirSync(tmp, { recursive: true });
      const work = mkdtempSync(path.join(tmp, 'opening-'));
      const build = spawnSync(
        'npx',
        [
          '--no-install',
          'vite',
          'build',
          '--outDir',
          path.join(work, 'web'),
          '--emptyOutDir',
        ],
        { cwd: WEB, encoding: 'utf8', timeout: 30_000 },
      );
      expect(build.status, build.stdout + build.stderr).toBe(0);
      const port = await new Promise<number>((resolve, reject) => {
        const socket = createServer();
        socket.once('error', reject);
        socket.listen(0, '127.0.0.1', () => {
          const address = socket.address();
          socket.close(() =>
            resolve(typeof address === 'object' && address ? address.port : 0),
          );
        });
      });
      const proc = startServerGroup(
        'uv',
        [
          'run',
          '--locked',
          'python',
          '-m',
          'product.tests.public_opening_server',
          '--work',
          work,
          '--port',
          String(port),
          '--web',
          path.join(work, 'web'),
        ],
        {
          cwd: ROOT,
          env: {
            PATH: process.env.PATH ?? '',
            HOME: process.env.HOME ?? '',
            TMPDIR: path.join(ROOT, '.overnight/tmp'),
            UV_CACHE_DIR:
              process.env.UV_CACHE_DIR ??
              path.join(ROOT, '.overnight/tmp/uv-cache'),
            PYTHONPATH: 'scripts/tests',
            EII_DECISION_PROVIDER: 'none',
            UV_OFFLINE: '1',
          },
          stdio: ['ignore', 'pipe', 'pipe'],
        },
      );
      let output = '';
      proc.stdout.on('data', (chunk) => {
        output += String(chunk);
      });
      proc.stderr.on('data', (chunk) => {
        output += String(chunk);
      });
      const origin = `http://127.0.0.1:${port}`;
      const probe = await request.newContext();
      try {
        const deadline = Date.now() + 30_000;
        for (;;) {
          if (proc.exitCode !== null)
            throw new Error('fixture failed: ' + output);
          try {
            if ((await probe.get(origin + '/api/release')).ok()) break;
          } catch {
            /* startup only */
          }
          expect(Date.now(), output).toBeLessThan(deadline);
          await new Promise((resolve) => setTimeout(resolve, 100));
        }
        await provide({ origin, work });
        assertNoProviderAttempts(work);
      } finally {
        await probe.dispose();
        await stopServerGroup(proc);
        rmSync(work, { recursive: true, force: true });
      }
    },
    { scope: 'worker' },
  ],
});
export { expect };
