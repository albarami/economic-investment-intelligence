/** Verify the browser runner actually registers every drawing flow in both languages. */
import { execFileSync } from 'node:child_process';
import { describe, expect, it } from 'vitest';

describe('drawing browser coverage', () => {
  it('registers keyboard, editing and touch flows for en and ar', () => {
    const listing = execFileSync(
      process.execPath,
      [
        'node_modules/@playwright/test/cli.js',
        'test',
        '--config=playwright.answer.config.ts',
        'tests/visual/draw.spec.ts',
        '--list',
      ],
      { encoding: 'utf8' },
    );
    for (const language of ['ar', 'en']) {
      for (const flow of [
        'keyboard draws a polygon',
        'touch places vertices',
        'keyboard edits a polygon vertex',
        'keyboard completes a radius',
        'touch completes a radius',
        'tap moves a vertex and Cancel clears the drawing',
      ]) {
        expect(listing).toMatch(new RegExp(`${language}: ${flow}`));
      }
    }
  }, 15_000);
});
