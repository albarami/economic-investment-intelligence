/** Missing or unapproved pixel evidence is a failure, never a refresh request. */
import { existsSync, readFileSync, lstatSync } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

export function baselineProblems(root, manifest) {
  if (
    !manifest ||
    manifest.origin !== 'CI' ||
    manifest.review !== 'APPROVED' ||
    !Array.isArray(manifest.entries) ||
    manifest.entries.length === 0
  )
    return ['pixel:approved_CI_baselines_required'];
  const problems = [];
  const seen = new Set();
  for (const entry of manifest.entries) {
    if (
      typeof entry.path !== 'string' ||
      !/^[a-f0-9]{64}$/.test(entry.sha256) ||
      path.isAbsolute(entry.path) ||
      entry.path.split(/[\\/]/).includes('..') ||
      !entry.path.endsWith('.png') ||
      seen.has(entry.path)
    ) {
      problems.push('pixel:manifest');
      continue;
    }
    seen.add(entry.path);
    let file = root;
    for (const part of entry.path.split('/')) {
      file = path.join(file, part);
      if (!existsSync(file) || lstatSync(file).isSymbolicLink()) {
        problems.push('pixel:missing_or_link');
        break;
      }
    }
    if (!existsSync(file) || !lstatSync(file).isFile()) {
      problems.push('pixel:missing_or_link');
      continue;
    }
    if (
      createHash('sha256').update(readFileSync(file)).digest('hex') !==
      entry.sha256
    )
      problems.push('pixel:hash');
  }
  return [...new Set(problems)];
}
