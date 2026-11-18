import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const originalCases = JSON.parse(
  fs.readFileSync(new URL('../fixtures/cases.json', import.meta.url), 'utf8'),
);
export const cases = [
  ...originalCases,
  ...JSON.parse(
    fs.readFileSync(
      new URL('../fixtures/paired-cases.json', import.meta.url),
      'utf8',
    ),
  ),
];
export function oracle(requests) {
  const result = spawnSync(
    'python3',
    ['-B', fileURLToPath(new URL('../oracle.py', import.meta.url))],
    {
      input: JSON.stringify(requests),
      encoding: 'utf8',
      env: { PATH: process.env.PATH, PYTHONDONTWRITEBYTECODE: '1' },
      maxBuffer: 16 * 1024 * 1024,
    },
  );
  if (result.status !== 0) throw new Error(`oracle exit ${result.status}`);
  return JSON.parse(result.stdout);
}
export const valid = cases.find((row) => row.id === 'valid');
