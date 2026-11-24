import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  test: {
    include: [
      'tests/unit/**/*.test.ts',
      'tests/component/**/*.test.tsx',
      'tests/question_lab/**/*.test.tsx',
    ],
    setupFiles: ['tests/setup/no-provider.ts'],
  },
});
