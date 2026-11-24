/**
 * RuleTester cases for eii/numerals-only-in-fact-chip.
 * The node suite under scripts/tests spawns this file.
 */
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { ESLint, RuleTester } from 'eslint';
import tseslint from 'typescript-eslint';

import rule from './numerals-only-in-fact-chip.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

const DIGITS = ['4', '\u0664', '\u06F4'];

const RENDERED_ATTRIBUTES = [
  'title',
  'alt',
  'placeholder',
  'label',
  'aria-label',
  'aria-description',
  'aria-valuetext',
];

const BANNED = [
  ['Intl.NumberFormat', 'const formatted = new Intl.NumberFormat("en");\n'],
  ['Intl.DateTimeFormat', 'const formatted = new Intl.DateTimeFormat("en");\n'],
  ['toLocaleString', 'const formatted = value.toLocaleString();\n'],
  ['toFixed', 'const formatted = value.toFixed();\n'],
  ['toPrecision', 'const formatted = value.toPrecision();\n'],
];

const syntax = new RuleTester({
  languageOptions: {
    parser: tseslint.parser,
    parserOptions: { ecmaFeatures: { jsx: true } },
  },
});

const invalid = [];

for (const filename of [
  'src/facts/SourceChainDrawer.tsx',
  'src/facts/ProvenanceMark.tsx',
  'src/facts/DrawerLike.tsx',
  'src/facts/nested/FactChip.tsx',
  'src/facts/formatters.tsx',
]) {
  for (const digit of DIGITS) {
    invalid.push({
      filename,
      code: `export const view = <p>${digit}</p>;\n`,
      errors: [{ messageId: 'jsx-text' }],
    });
  }
}

for (const digit of DIGITS) {
  invalid.push({
    filename: 'src/app/jsx-text.tsx',
    code: `export const view = <p>${digit}</p>;\n`,
    errors: [{ messageId: 'jsx-text' }],
  });
  invalid.push({
    filename: 'src/app/jsx-child.tsx',
    code: `export const view = <p>{"${digit}"}</p>;\n`,
    errors: [{ messageId: 'jsx-string' }],
  });
  invalid.push({
    filename: 'src/app/jsx-template.tsx',
    code: `export const view = <p>{\`${digit}\`}</p>;\n`,
    errors: [{ messageId: 'jsx-string' }],
  });
  for (const attribute of RENDERED_ATTRIBUTES) {
    invalid.push({
      filename: 'src/app/jsx-attr.tsx',
      code: `export const view = <p ${attribute}="${digit}" />;\n`,
      errors: [{ messageId: 'jsx-string' }],
    });
  }
}

invalid.push(
  {
    filename: 'src/app/literal-number.tsx',
    code: 'export const view = <p>{4}</p>;\n',
    errors: [{ messageId: 'jsx-number' }],
  },
  {
    filename: 'src/app/literal-bigint.tsx',
    code: 'export const view = <p>{4n}</p>;\n',
    errors: [{ messageId: 'jsx-number' }],
  },
);

for (const [, code] of BANNED) {
  invalid.push({
    filename: 'src/app/banned.ts',
    code,
    errors: [{ messageId: 'banned-call' }],
  });
}

invalid.push(
  {
    filename: 'src/app/text-layer.tsx',
    code: 'export const layer = new TextLayer({});\n',
    errors: [{ messageId: 'text-layer' }],
  },
  {
    filename: 'src/app/text-layer-alias.tsx',
    code:
      'import { TextLayer as Labels } from "@deck.gl/layers";\n' +
      'const Alias = Labels;\n' +
      'export const layer = new Alias({});\n',
    errors: [{ messageId: 'text-layer' }],
  },
  {
    filename: 'src/app/text-field.tsx',
    code: 'export const style = { "text-field": ["get", "housenumber"] };\n',
    errors: [{ messageId: 'text-field' }],
  },
);

const valid = [
  {
    filename: 'src/app/svg.tsx',
    code: 'export const view = <svg viewBox="0 0 12 12"><rect x="1" width="4" d="M0 0" /></svg>;\n',
  },
  {
    filename: 'src/app/coordinates.ts',
    code: 'export const point = [51.52, 25.28];\nexport const index = point[0];\n',
  },
  {
    filename: 'src/app/key.tsx',
    code: 'export const view = <div key="2" data-index="3" />;\n',
  },
  {
    filename: 'src/app/name-field.ts',
    code: 'export const style = { "text-field": ["coalesce", ["get", "name:en"], ["get", "name:ar"], ["get", "name"]] };\n',
  },
  {
    filename: 'src/facts/formatters.ts',
    code: 'export const formatted = new Intl.NumberFormat("en");\n',
  },
  {
    filename: 'src/facts/FactChip.tsx',
    code: 'export const view = <p>4</p>;\n',
  },
  {
    filename: 'src/facts/NumericInput.tsx',
    code: 'export const view = <input aria-label="4" />;\n',
  },
  {
    filename: 'tests/unit/sample.test.tsx',
    code: 'export const view = <p>4</p>;\n',
  },
  {
    filename: 'spikes/performance/main.tsx',
    code: 'export const view = <p>4</p>;\n',
  },
];

syntax.run('eii/numerals-only-in-fact-chip', rule, { valid, invalid });

const untyped = new RuleTester({
  languageOptions: {
    parser: tseslint.parser,
    parserOptions: { ecmaFeatures: { jsx: true } },
  },
});

untyped.run('eii/numerals-only-in-fact-chip without services', rule, {
  valid: [],
  invalid: [
    {
      filename: 'probe-untyped.tsx',
      code: 'const label = "Doha";\nexport const view = <p>{label}</p>;\n',
      errors: [{ messageId: 'missing-services' }],
    },
  ],
});

const typed = new RuleTester({
  languageOptions: {
    parser: tseslint.parser,
    parserOptions: {
      ecmaFeatures: { jsx: true },
      projectService: {
        allowDefaultProject: ['*.tsx', '*.ts'],
      },
      tsconfigRootDir: ROOT,
    },
  },
});

typed.run('eii/numerals-only-in-fact-chip types', rule, {
  valid: [
    {
      filename: 'probe-label.tsx',
      code: 'const label: string = "Doha";\nexport const view = <p>{label}</p>;\n',
    },
  ],
  invalid: [
    {
      filename: 'probe-meter.tsx',
      code: 'declare const meter: { billable_requests: number };\nexport const view = <p>{meter.billable_requests}</p>;\n',
      errors: [{ messageId: 'jsx-number' }],
    },
    {
      filename: 'probe-count.tsx',
      code: 'const count: number = 4;\nexport const view = <p>{count}</p>;\n',
      errors: [{ messageId: 'jsx-number' }],
    },
    {
      filename: 'probe-bigint.tsx',
      code: 'const count: bigint = 4n;\nexport const view = <p>{count}</p>;\n',
      errors: [{ messageId: 'jsx-number' }],
    },
    {
      filename: 'probe-template.tsx',
      code: 'const count: number = 4;\nexport const view = <p>{`${count}`}</p>;\n',
      errors: [{ messageId: 'jsx-number' }],
    },
    {
      filename: 'probe-attr.tsx',
      code: 'const count: number = 4;\nexport const view = <p title={count} />;\n',
      errors: [{ messageId: 'jsx-number' }],
    },
    {
      filename: 'probe-units.tsx',
      code: 'const units: { cells: string[] } = { cells: [] };\nexport const view = <p>{units.cells.length}</p>;\n',
      errors: [{ messageId: 'jsx-number' }],
    },
  ],
});

// Exercise the real config too: a path ignore can bypass an otherwise sound rule.
const eslint = new ESLint({ cwd: ROOT });
const drawerResults = await eslint.lintText('export const view = <p>4</p>;\n', {
  filePath: path.join(ROOT, 'src/facts/SourceChainDrawer.tsx'),
});
assert.ok(
  drawerResults.some((result) =>
    result.messages.some(
      (message) =>
        message.ruleId === 'eii/numerals-only-in-fact-chip' &&
        message.messageId === 'jsx-text',
    ),
  ),
  JSON.stringify(drawerResults.flatMap((result) => result.messages)),
);
