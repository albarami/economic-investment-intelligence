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

/**
 * S3-T10 box 9: the plugin stays until the pinned minor version is shown not
 * to need it. Removal is allowed only beside an approved native review that
 * names the exact pinned major.minor of maplibre-gl; a review of another
 * version, or an approval with no version, does not release the plugin.
 */
function pluginReleased(boot: string, review: string, pinned: string): boolean {
  const plugin = /setRTLTextPlugin\s*\(\s*rtlPluginUrl\s*,\s*true\s*\)/.test(
    boot,
  );
  if (plugin) return true;
  const minor = /^(\d+)\.(\d+)\.\d+$/.exec(pinned);
  if (!minor) return false;
  const version = `${minor[1]}\\.${minor[2]}`;
  return (
    /^Verdict: APPROVED$/m.test(review) &&
    new RegExp(
      `^Plugin not needed: maplibre-gl ${version}(?:\\.\\d+)?$`,
      'm',
    ).test(review)
  );
}

it('keeps the plugin unless the pinned minor version has its approved record', () => {
  const boot = readFileSync('src/stage/map-boot.ts', 'utf8');
  const review = readFileSync(
    'spikes/glyphs/evidence/visual-review.md',
    'utf8',
  );
  const pkg = JSON.parse(readFileSync('package.json', 'utf8')) as {
    dependencies: Record<string, string>;
  };
  const pinned = pkg.dependencies['maplibre-gl'] ?? '';
  expect(pinned).toMatch(/^\d+\.\d+\.\d+$/);
  expect(pkg.dependencies['@mapbox/mapbox-gl-rtl-text']).toMatch(
    /^\d+\.\d+\.\d+$/,
  );
  expect(pluginReleased(boot, review, pinned)).toBe(true);
});

it('refuses each incomplete release record once the plugin is gone', () => {
  const gone = "import { Map } from 'maplibre-gl';";
  const approved = 'Verdict: APPROVED\nPlugin not needed: maplibre-gl 6.17\n';
  expect(pluginReleased(gone, approved, '6.17.0')).toBe(true);
  expect(pluginReleased(gone, approved, '6.18.0')).toBe(false);
  expect(pluginReleased(gone, 'Verdict: APPROVED\n', '6.17.0')).toBe(false);
  expect(
    pluginReleased(
      gone,
      'Verdict: pending native review\nPlugin not needed: maplibre-gl 6.17\n',
      '6.17.0',
    ),
  ).toBe(false);
  expect(pluginReleased(gone, approved, '6.17')).toBe(false);
  expect(
    pluginReleased(
      'setRTLTextPlugin(rtlPluginUrl, true)',
      'Verdict: pending native review\n',
      '6.17.0',
    ),
  ).toBe(true);
});
