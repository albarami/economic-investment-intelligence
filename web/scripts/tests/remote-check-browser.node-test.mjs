import { browserSuite } from '../browser-suite.mjs';

browserSuite(
  'S3-T20 remote-check runner: control, planted cases and result file',
  'playwright.remote-check-plants.config.ts',
);
