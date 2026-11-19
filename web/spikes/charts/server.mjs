import { preview } from 'vite';
const server = await preview({
  configFile: 'spikes/charts/vite.config.ts',
  preview: { host: '127.0.0.1', port: 0, strictPort: false, open: false },
});
server.printUrls();
