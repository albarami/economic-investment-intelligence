import { defineConfig, mergeConfig } from 'vite';
import base from '../../vite.config';
const outDir = process.env.EII_PHOTOREAL_TEST_DIST;
if (!outDir) throw new Error('EII_PHOTOREAL_TEST_DIST is not set');
export default mergeConfig(
  base,
  defineConfig({
    build: {
      outDir,
      emptyOutDir: true,
      rollupOptions: { input: 'tests/photoreal/index.html' },
    },
  }),
);
