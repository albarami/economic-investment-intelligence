import js from '@eslint/js';
import { defineConfig, globalIgnores } from 'eslint/config';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';

// FE-11: all API access goes through src/api/.
const apiOnly = {
  checkGlobalObject: true,
  globals: [
    {
      name: 'fetch',
      message: 'FE-11: call the backend only through src/api/.',
    },
    {
      name: 'EventSource',
      message: 'FE-11: open event streams only through src/api/.',
    },
  ],
};

export default defineConfig([
  globalIgnores([
    'dist/',
    'node_modules/',
    'spikes/glyphs/dist/',
    'spikes/performance/dist/',
  ]),
  {
    files: ['**/*.{js,mjs,cjs,jsx}'],
    extends: [js.configs.recommended],
    languageOptions: {
      globals: globals.node,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
  },
  {
    files: ['**/*.{ts,mts,cts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
    ],
  },
  {
    files: ['**/*.{js,mjs,cjs,jsx,ts,mts,cts,tsx}'],
    ignores: ['src/api/**'],
    languageOptions: { globals: globals.browser },
    rules: { 'no-restricted-globals': ['error', apiOnly] },
  },
]);
