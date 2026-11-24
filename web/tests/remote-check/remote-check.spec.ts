/**
 * The pinned browser runner of `./eii remote-check` (S3-T20). The command
 * names the origin and the result file by environment; the origin is never
 * printed and never written. Item failures are data: the run fails only
 * when no complete result file could be written.
 */
import { test } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { readSelection, resultDocument, resultExact } from './decide';
import { observe } from './observe';

test('remote check', async ({ page }) => {
  const origin = process.env.EII_REMOTE_CHECK_ORIGIN ?? '';
  const target = process.env.EII_REMOTE_CHECK_RESULT ?? '';
  if (!path.isAbsolute(target) || !URL.canParse(origin))
    throw new Error('remote_check_environment');
  if (new URL(origin).origin !== origin)
    throw new Error('remote_check_environment');
  const selection = readSelection(
    readFileSync(new URL('./selection.json', import.meta.url), 'utf8'),
  );
  const result = resultDocument(await observe(page, origin, selection), origin);
  if (!resultExact(result)) throw new Error('remote_check_result');
  writeFileSync(target, JSON.stringify(result) + '\n', {
    encoding: 'utf8',
    flag: 'wx',
  });
});
