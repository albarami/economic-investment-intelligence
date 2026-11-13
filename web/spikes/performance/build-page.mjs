import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'vite';

const HERE = path.dirname(fileURLToPath(import.meta.url));

export async function buildPage() {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-perf-'));
  try {
    await build({
      configFile: path.join(HERE, 'vite.config.ts'),
      build: { outDir, emptyOutDir: true },
      logLevel: 'silent',
    });
  } catch (error) {
    fs.rmSync(outDir, { recursive: true, force: true });
    throw error;
  }
  return outDir;
}
