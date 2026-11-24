import { defineConfig } from '@playwright/test';
import opening from './playwright.opening.config';

/** Planted cases of the remote-check runner, on the opening fixture only. */
export default defineConfig({
  ...opening,
  outputDir: '../.overnight/tmp/S3-T20-remote-check-plants',
  testMatch: ['e2e/remote-check-plants.spec.ts'],
  timeout: 150_000,
});
