import {
  transformDependency,
  verifyAssets,
  verifyReplacements,
  browserModules,
} from './scripts/photoreal-assets.mjs';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig, type Plugin } from 'vite';

const HERE = path.dirname(fileURLToPath(import.meta.url));

const FONT_LICENCES = [
  ['photoreal-loaders.txt', '@loaders.gl/draco/LICENSE'],
  ['mapbox-gl-rtl-text.txt', '@mapbox/mapbox-gl-rtl-text/LICENSE.md'],
  ['ibm-plex-sans.txt', '@fontsource/ibm-plex-sans/LICENSE'],
  ['ibm-plex-sans-arabic.txt', '@fontsource/ibm-plex-sans-arabic/LICENSE'],
] as const;

function fontLicences(): Plugin {
  return {
    name: 'eii-font-licences',
    apply: 'build',
    generateBundle() {
      for (const [name, relative] of FONT_LICENCES) {
        const file = path.join(HERE, 'node_modules', relative);
        const source = fs.readFileSync(file, 'utf8');
        this.emitFile({
          type: 'asset',
          fileName: `licences/${name}`,
          source,
        });
      }
    },
  };
}

const matched = new Set<string>();

export default defineConfig({
  build: {
    // DES-24, FE-97: every bundled font ships as a file the application
    // serves, beside its licence text under dist/licences/, never inlined
    // as a data URL inside the CSS.
    assetsInlineLimit(filePath: string) {
      return /\.(woff2?|ttf|otf)$/.test(filePath) ? false : undefined;
    },
  },
  plugins: [
    react(),
    fontLicences(),
    {
      name: 'qualified-photoreal-assets',
      enforce: 'pre',
      buildStart() {
        matched.clear();
        verifyAssets((relative) =>
          fs.readFileSync(path.join(HERE, 'node_modules', relative)),
        );
      },
      transform(code, id) {
        return transformDependency(code, id, HERE, matched);
      },
      generateBundle(_options, bundle) {
        verifyReplacements(matched);
        this.emitFile({
          type: 'asset',
          fileName: 'photoreal-modules.json',
          source: JSON.stringify(browserModules(bundle)),
        });
      },
    },
  ],
});
