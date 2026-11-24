import js from '@eslint/js';
import { defineConfig, globalIgnores } from 'eslint/config';
import reactHooks from 'eslint-plugin-react-hooks';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import numeralsOnlyInFactChip, {
  FACT_CHIP_FILES,
} from './eslint-rules/numerals-only-in-fact-chip.mjs';

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
  {
    files: ['**/*.{ts,tsx}'],
    ignores: [
      ...FACT_CHIP_FILES,
      'tests/**',
      '**/fixtures/**',
      '**/*.test.ts',
      '**/*.test.tsx',
      '**/*.spec.ts',
      '**/*.spec.tsx',
      'spikes/performance/**',
    ],
    plugins: {
      eii: {
        rules: {
          'numerals-only-in-fact-chip': numeralsOnlyInFactChip,
        },
      },
    },
    rules: {
      'eii/numerals-only-in-fact-chip': 'error',
    },
  },
  {
    files: ['src/**/*.{ts,tsx}', 'vite.config.ts'],
    ignores: FACT_CHIP_FILES,
    languageOptions: {
      parserOptions: {
        projectService: {
          allowDefaultProject: ['src/api/*.tsx', 'src/ext/*.tsx'],
          defaultProject: 'tsconfig.json',
          maximumDefaultProjectFileMatchCount_THIS_WILL_SLOW_DOWN_LINTING: 16,
        },
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
]);
