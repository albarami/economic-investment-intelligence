import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const root = fileURLToPath(new URL('.', import.meta.url));

// The look page is development-only, like the other spikes: it has its own
// root and its own build, and the production build of web/ does not read it.
// The font licence texts are served from the glyph spike's public folder.
export default defineConfig({
  root,
  publicDir: fileURLToPath(new URL('../glyphs/public', import.meta.url)),
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  resolve: {
    conditions: ['visgl:webgl-only'],
  },
});
