/** Decision 0042 item 7: a pinned-version demonstration or a retained plugin. */
import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';
it('retains the plugin until the pinned renderer has an approved shaping demonstration', () => {
  const boot = readFileSync('src/stage/map-boot.ts', 'utf8');
  const review = readFileSync(
    'spikes/glyphs/evidence/visual-review.md',
    'utf8',
  );
  const plugin = /setRTLTextPlugin\s*\(/.test(boot);
  const demonstration = /Verdict: APPROVED/.test(review);
  expect(plugin || demonstration).toBe(true);
});

it('loads the pinned asset lazily before constructing a map', () => {
  const boot = readFileSync('src/stage/map-boot.ts', 'utf8');
  expect(boot).toContain(
    "from '../../node_modules/@mapbox/mapbox-gl-rtl-text/dist/mapbox-gl-rtl-text.js?url'",
  );
  expect(boot).toContain('setRTLTextPlugin(rtlPluginUrl, true)');
  expect(boot.indexOf('setRTLTextPlugin(rtlPluginUrl, true)')).toBeLessThan(
    boot.indexOf('new Map('),
  );
});
