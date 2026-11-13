import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const INSTALL = 'npm --prefix web run spike:glyphs:install-browser';
const SHELL_NAMES = new Set([
  'chrome-headless-shell',
  'chrome-headless-shell.exe',
]);

export function browserHome(moduleUrl) {
  let dir = path.dirname(fileURLToPath(moduleUrl));
  for (let step = 0; step < 8; step += 1) {
    if (
      fs.existsSync(path.join(dir, 'pins.toml')) &&
      fs.existsSync(path.join(dir, 'web', 'package.json'))
    ) {
      return path.join(dir, 'data', 'tools', 'playwright');
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error('repository root was not found');
}

export function shellInstalled(home) {
  if (!fs.existsSync(home)) return false;
  const pending = [home];
  while (pending.length > 0) {
    const current = pending.pop();
    let entries;
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch (error) {
      if (error && typeof error === 'object' && 'code' in error) return false;
      throw error;
    }
    for (const entry of entries) {
      if (entry.isDirectory()) pending.push(path.join(current, entry.name));
      else if (entry.isFile() && SHELL_NAMES.has(entry.name)) return true;
    }
  }
  return false;
}
