/**
 * Isolated Vite build of the credit-place Stage fixture.
 * Not the application build. The scan sets EII_CREDIT_PLACE_OUT.
 */
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const outDir = process.env.EII_CREDIT_PLACE_OUT;

if (!outDir) throw new Error('credit-place-out-missing');

export default defineConfig({
  plugins: [react()],
  build: {
    outDir,
    emptyOutDir: true,
    cssCodeSplit: false,
    sourcemap: false,
    reportCompressedSize: false,
    rollupOptions: {
      input: path.join(HERE, 'credit-place-stage-entry.tsx'),
      output: {
        format: 'iife',
        name: 'CreditPlaceStage',
        inlineDynamicImports: true,
        entryFileNames: 'credit-place-stage.js',
      },
    },
  },
  logLevel: 'error',
});
