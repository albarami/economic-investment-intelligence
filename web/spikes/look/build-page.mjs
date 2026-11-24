import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'vite';

const HERE = path.dirname(fileURLToPath(import.meta.url));

// Builds the look page with its own Vite configuration into a new temporary
// folder and returns that folder. Nothing is written under web/.
export async function buildPage() {
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-look-'));
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

export function removePage(outDir) {
  if (outDir) fs.rmSync(outDir, { recursive: true, force: true });
}
