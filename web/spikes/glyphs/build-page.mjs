import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SPIKE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(SPIKE, '..', '..');

export function buildPage() {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-glyphs-'));
  const viteBin = path.join(WEB, 'node_modules', 'vite', 'bin', 'vite.js');
  const result = spawnSync(
    process.execPath,
    [
      viteBin,
      'build',
      '--config',
      path.join(SPIKE, 'vite.config.ts'),
      '--outDir',
      outDir,
    ],
    { cwd: SPIKE, env: process.env, encoding: 'utf8' },
  );
  if (result.status !== 0 || !fs.existsSync(path.join(outDir, 'index.html'))) {
    fs.rmSync(outDir, { recursive: true, force: true });
    const detail = (result.stderr || result.stdout || 'spike page build failed')
      .trim()
      .split('\n')
      .slice(-20)
      .join('\n');
    return { ok: false, outDir: '', detail };
  }
  return { ok: true, outDir, detail: '' };
}

export function removePage(outDir) {
  if (outDir) fs.rmSync(outDir, { recursive: true, force: true });
}
