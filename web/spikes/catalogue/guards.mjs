import path from 'node:path';
import { collectReferences } from '../../scripts/import-tokenizer.mjs';

export function checkGraph(entries, read) {
  const failures = [];
  const seen = new Set();
  function visit(file) {
    if (seen.has(file)) return;
    seen.add(file);
    if (file.startsWith('spikes/catalogue/')) {
      failures.push(`SPIKE_IMPORT:${file}`);
      return;
    }
    const source = read(file);
    if (typeof source !== 'string') {
      failures.push(`MISSING_IMPORT:${file}`);
      return;
    }
    const found = collectReferences(source);
    if (found.nonLiteral.length) failures.push(`NONLITERAL_IMPORT:${file}`);
    for (const { specifier } of found.references) {
      if (!specifier.startsWith('.')) continue;
      const next = path.posix.normalize(
        path.posix.join(path.posix.dirname(file), specifier),
      );
      if (next.startsWith('spikes/catalogue/'))
        failures.push(`SPIKE_IMPORT:${file}`);
      else if (/\.[cm]?[jt]sx?$/.test(next)) visit(next);
      else if (!path.posix.extname(next)) {
        let resolved = null;
        for (const extension of [
          '.ts',
          '.tsx',
          '.mjs',
          '.js',
          '/index.ts',
          '/index.tsx',
        ]) {
          const candidate = next + extension;
          try {
            if (typeof read(candidate) === 'string') {
              resolved = candidate;
              break;
            }
          } catch (error) {
            if (error.code !== 'ENOENT') throw error;
          }
        }
        if (resolved) visit(resolved);
        else failures.push(`MISSING_IMPORT:${next}`);
      }
    }
  }
  for (const entry of entries) visit(entry);
  return failures;
}
