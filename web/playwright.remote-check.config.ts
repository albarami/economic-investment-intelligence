import { tmpdir } from 'node:os';
import path from 'node:path';
import { defineConfig } from '@playwright/test';
import opening from './playwright.opening.config';

const result = process.env.EII_REMOTE_CHECK_RESULT ?? '';

/**
 * The browser runner of `./eii remote-check`: one case, with the pinned
 * browser and the settings of the opening tests. It leaves no file inside
 * the repository: its own output folder lies beside the result file the
 * command names.
 */
export default defineConfig({
  ...opening,
  testDir: './tests/remote-check',
  testMatch: ['remote-check.spec.ts'],
  outputDir: path.join(
    path.isAbsolute(result) ? path.dirname(result) : tmpdir(),
    'remote-check-runner-output',
  ),
  timeout: 170_000,
});
