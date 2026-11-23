/*
 * Shared utilities of the check scripts: the usage error, the internal-error
 * formatter, the dist walk and the line lookup. Both host scanners import
 * them, so their error and path behavior cannot drift apart.
 */
import fs from 'node:fs';
import path from 'node:path';

export function usage(message) {
  const error = new Error(message);
  error.usage = true;
  return error;
}

export function formatInternal(error) {
  const code = error.code || error.name;
  let message = String(error.message).split('\n')[0];
  const prefix = `${code}: `;
  if (message.startsWith(prefix)) message = message.slice(prefix.length);
  message = message.replace(/\s*'[^']*'/g, '');
  message = message.replace(/[\s,]+$/g, '');
  return `FAIL internal-error: ${code}: ${message}`;
}

export function lineAt(text, index) {
  let line = 1;
  for (let cursor = 0; cursor < index; cursor += 1) {
    if (text[cursor] === '\n') line += 1;
  }
  return line;
}

export function relativePath(root, full) {
  return path.relative(root, full).split(path.sep).join('/');
}

export function walk(dir, visit) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isSymbolicLink()) {
      let info;
      try {
        info = fs.statSync(full);
      } catch (error) {
        visit({ full, error });
        continue;
      }
      if (info.isDirectory()) continue;
      visit({ full });
      continue;
    }
    if (entry.isDirectory()) {
      walk(full, visit);
      continue;
    }
    if (entry.isFile()) visit({ full });
  }
}
