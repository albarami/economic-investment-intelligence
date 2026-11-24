import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { judgeCatalogue } from '../guards.mjs';

const SPIKE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function read(name) {
  return fs.readFileSync(path.join(SPIKE, name), 'utf8');
}

function sourceFiles(extensions) {
  const found = [];
  const pending = [SPIKE];
  while (pending.length > 0) {
    const current = pending.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (['tests', 'node_modules', 'dist', 'public'].includes(entry.name))
          continue;
        pending.push(full);
      } else if (extensions.some((ext) => entry.name.endsWith(ext))) {
        found.push(full);
      }
    }
  }
  return found.sort();
}

// docs/11_DESIGN_DIRECTION.md section "4.1 Tokens", copied value for value.
const COLOUR_TOKENS = {
  '--eii-bg': ['#10151C', '#D8D5CE'],
  '--eii-surface-1': ['#18202B', '#E2DFD9'],
  '--eii-surface-2': ['#212B38', '#EBE9E4'],
  '--eii-surface-3': ['#2B3747', '#EBE9E4'],
  '--eii-line': ['#445266', '#AFACA4'],
  '--eii-line-strong': ['#8492A3', '#6A675F'],
  '--eii-text': ['#E6EAEB', '#14181D'],
  '--eii-text-2': ['#C2CAD3', '#363D46'],
  '--eii-text-3': ['#9AA5B1', '#4E5660'],
  '--eii-accent': ['#E69F00', '#A85400'],
  '--eii-role-work': ['#56B4E9', '#0072B2'],
  '--eii-role-live': ['#009E73', '#00735A'],
  '--eii-role-visit': ['#CC79A7', '#9C3F7A'],
  '--eii-housing-family': ['#009E73', '#00735A'],
  '--eii-housing-labour': ['#5EBF9A', '#0E6B4C'],
  '--eii-seq-1': ['#2F4A5E', '#CBC48E'],
  '--eii-seq-2': ['#3F6F86', '#93AD9B'],
  '--eii-seq-3': ['#5E97A6', '#63899A'],
  '--eii-seq-4': ['#9CC4BB', '#3F6680'],
  '--eii-seq-5': ['#EBE3B0', '#27425A'],
  '--eii-map-land': ['#1E2630', '#E4E1DB'],
  '--eii-map-water': ['#121B24', '#C3CED6'],
  '--eii-map-road-minor': ['#27313D', '#D6D2CA'],
  '--eii-map-road-major': ['#3A4757', '#C2BEB5'],
  '--eii-map-building': ['#364252', '#D3CFC7'],
  '--eii-map-boundary': ['#66758A', '#75716A'],
  '--eii-map-label-1': ['#D5DBE0', '#22282F'],
  '--eii-map-label-2': ['#A3AEBA', '#4E5660'],
  '--eii-scrim': ['rgba(16,21,28,0.72)', 'rgba(20,24,29,0.40)'],
};

// Sections "5.1 Families and scale" (wall column), "6. Space, grid,
// elevation and icons" and "7. Motion".
const SHARED_TOKENS = {
  '--eii-space-1': '4px',
  '--eii-space-2': '8px',
  '--eii-space-3': '12px',
  '--eii-space-4': '16px',
  '--eii-space-5': '24px',
  '--eii-space-6': '32px',
  '--eii-space-7': '48px',
  '--eii-space-8': '64px',
  '--eii-space-9': '96px',
  '--eii-radius-s': '6px',
  '--eii-radius-m': '12px',
  '--eii-radius-l': '20px',
  '--eii-dur-fast': '150ms',
  '--eii-dur-base': '250ms',
  '--eii-dur-slow': '400ms',
  '--eii-dur-scene': '800ms',
  '--eii-dur-fly-short': '1200ms',
  '--eii-dur-fly-medium': '2500ms',
  '--eii-dur-fly-long': '3500ms',
  '--eii-ease-enter': 'cubic-bezier(0.16,1,0.3,1)',
  '--eii-ease-exit': 'cubic-bezier(0.7,0,0.84,0)',
  '--eii-ease-move': 'cubic-bezier(0.65,0,0.35,1)',
  '--eii-stagger': '60ms',
  '--eii-dash-speed': '24px',
};

const LATIN_TYPE = {
  '--eii-type-display': '600 72px/80px',
  '--eii-type-title': '600 40px/48px',
  '--eii-type-body': '400 32px/44px',
  '--eii-type-label': '500 28px/36px',
  '--eii-type-caption': '400 28px/36px',
  '--eii-num-hero': '500 120px/120px',
  '--eii-num-large': '600 64px/68px',
  '--eii-num-standard': '600 40px/48px',
};

// DES-28: Arabic at 1.12 times the Latin size, rounded, line height 1.6 times.
const ARABIC_TYPE = {
  '--eii-type-display': '600 81px/130px',
  '--eii-type-title': '600 45px/72px',
  '--eii-type-body': '400 36px/58px',
  '--eii-type-label': '500 31px/50px',
  '--eii-type-caption': '400 31px/50px',
};

function block(css, selectorPart) {
  const start = css.indexOf(selectorPart);
  assert.notEqual(start, -1, `no block for ${selectorPart}`);
  const open = css.indexOf('{', start);
  const close = css.indexOf('}', open);
  const body = css.slice(open + 1, close);
  const values = {};
  for (const match of body.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    values[match[1]] = match[2].trim();
  }
  return values;
}

// Case, spaces and trailing decimal zeros carry no meaning (the formatter
// writes 0.40 as 0.4).
function normal(value) {
  return value
    .replace(/\s+/g, '')
    .toLowerCase()
    .replace(/\.(\d*?)0+(?=\D|$)/g, (_, digits) =>
      digits === '' ? '' : `.${digits}`,
    );
}

function typePart(value) {
  return value.split(/\s+var\(/)[0].trim();
}

test('both themes carry the tokens of section 4.1 exactly', () => {
  const css = read('tokens.css');
  const dark = block(css, "[data-theme='dark']");
  const light = block(css, "[data-theme='light']");
  for (const [name, [darkValue, lightValue]] of Object.entries(COLOUR_TOKENS)) {
    assert.equal(normal(dark[name] ?? ''), normal(darkValue), `dark ${name}`);
    assert.equal(
      normal(light[name] ?? ''),
      normal(lightValue),
      `light ${name}`,
    );
  }
});

test('space, radius and motion tokens carry the values of sections 6 and 7', () => {
  const shared = block(read('tokens.css'), ':root {');
  for (const [name, value] of Object.entries(SHARED_TOKENS)) {
    assert.equal(normal(shared[name] ?? ''), normal(value), name);
  }
});

test('the type scale is the wall column, and Arabic is 1.12 times at 1.6', () => {
  const css = read('tokens.css');
  const latin = block(css, ':lang(en)');
  const arabic = block(css, ':lang(ar) {');
  for (const [name, value] of Object.entries(LATIN_TYPE)) {
    assert.equal(typePart(latin[name] ?? ''), value, `Latin ${name}`);
  }
  for (const [name, value] of Object.entries(ARABIC_TYPE)) {
    assert.equal(typePart(arabic[name] ?? ''), value, `Arabic ${name}`);
  }
  for (const name of Object.keys(LATIN_TYPE)) {
    assert.match(latin[name] ?? '', /var\(--eii-font-latin\)$/, name);
  }
  for (const name of Object.keys(ARABIC_TYPE)) {
    assert.match(arabic[name] ?? '', /var\(--eii-font-arabic\)$/, name);
  }
  const shared = block(css, ':root {');
  assert.match(shared['--eii-font-latin'] ?? '', /^'IBM Plex Sans',/);
  assert.match(shared['--eii-font-arabic'] ?? '', /^'IBM Plex Sans Arabic',/);
});

// The OpenAI audit's F4 and the xAI audit's F6: Arabic sizes are scoped by
// :lang(ar), so a Latin run on the Arabic page keeps Latin metrics, and each
// stack names the other script's face before any system face.
test('script metrics are scoped by :lang and the font stacks are chained', () => {
  const css = read('tokens.css');
  assert.equal(css.includes("[lang='ar']"), false);
  assert.equal(css.includes(':root[lang'), false);
  assert.match(css, /:root,\s*:lang\(en\) \{/);
  const shared = block(css, ':root {');
  assert.match(
    shared['--eii-font-latin'] ?? '',
    /^'IBM Plex Sans', 'IBM Plex Sans Arabic', sans-serif$/,
  );
  assert.match(
    shared['--eii-font-arabic'] ?? '',
    /^'IBM Plex Sans Arabic', 'IBM Plex Sans', sans-serif$/,
  );
});

test('the style sheets draw no class mark (rulings L-111 to L-114)', () => {
  for (const name of ['style.css', 'tokens.css']) {
    const css = read(name).replace(/\/\*[\s\S]*?\*\//g, '');
    const found = css.match(
      /radial-gradient|repeating-linear-gradient|linear-gradient|\bdotted\b|\bdashed\b|underline|fill-pattern|watermark/,
    );
    assert.equal(found, null, `${name}: ${found?.[0]}`);
  }
});

function luminance(hex) {
  const value = hex.replace('#', '');
  const channels = [0, 2, 4].map((at) => {
    const c = parseInt(value.slice(at, at + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function ratio(a, b) {
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (high + 0.05) / (low + 0.05);
}

test('contrast of DES-15 holds in both themes', () => {
  const surfaces = [
    '--eii-bg',
    '--eii-surface-1',
    '--eii-surface-2',
    '--eii-surface-3',
  ];
  const ground = ['--eii-map-land', '--eii-map-water'];
  const rules = [
    [['--eii-text', '--eii-text-2'], surfaces, 7],
    [['--eii-text-3'], surfaces, 4.5],
    [['--eii-line-strong'], surfaces, 3],
    [['--eii-accent'], [...surfaces, ...ground], 3],
    [
      ['--eii-role-work', '--eii-role-live', '--eii-role-visit'],
      [...surfaces, ...ground],
      3,
    ],
    [['--eii-map-boundary'], ground, 3],
    [['--eii-map-label-1', '--eii-map-label-2'], ground, 4.5],
  ];
  for (const theme of [0, 1]) {
    for (const [inks, grounds, floor] of rules) {
      for (const ink of inks) {
        for (const under of grounds) {
          const value = ratio(
            COLOUR_TOKENS[ink][theme],
            COLOUR_TOKENS[under][theme],
          );
          assert.ok(
            value >= floor,
            `${theme === 0 ? 'dark' : 'light'} ${ink} on ${under}: ${value.toFixed(2)}`,
          );
        }
      }
    }
  }
});

function lightness(hex) {
  const y = luminance(hex);
  const f = y > 216 / 24389 ? Math.cbrt(y) : ((24389 / 27) * y + 16) / 116;
  return 116 * f - 16;
}

test('the ramp lightness is monotonic with steps of at least ten (DES-20)', () => {
  for (const [theme, direction] of [
    [0, 1],
    [1, -1],
  ]) {
    const values = [1, 2, 3, 4, 5].map((step) =>
      lightness(COLOUR_TOKENS[`--eii-seq-${step}`][theme]),
    );
    for (let index = 1; index < values.length; index += 1) {
      const step = (values[index] - values[index - 1]) * direction;
      assert.ok(step >= 10, `theme ${theme} step ${index}: ${step}`);
    }
  }
});

test('component styles carry no literal colour, size or duration (DES-02)', () => {
  const css = read('style.css');
  const literal = css.match(
    /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|\b\d*\.?\d+(px|ms|s|rem|em|pt)\b/,
  );
  assert.equal(literal, null, literal ? literal[0] : '');
});

test('component styles use logical properties only (FE-65)', () => {
  const css = read('style.css');
  const physical = css.match(
    /\b(margin|padding|border)-(left|right)\b|(^|[\s;{])(left|right)\s*:|text-align\s*:\s*(left|right)|float\s*:\s*(left|right)/m,
  );
  assert.equal(physical, null, physical ? physical[0] : '');
});

test('page scripts carry no literal colour', () => {
  for (const file of sourceFiles(['.ts'])) {
    const text = fs.readFileSync(file, 'utf8');
    const literal = text.match(/['"`]#[0-9a-fA-F]{3,8}\b|\brgba?\(/);
    assert.equal(literal, null, `${path.basename(file)}: ${literal?.[0]}`);
  }
});

test('only the facts module formats a number (DES-30)', () => {
  for (const file of sourceFiles(['.ts', '.mjs'])) {
    if (path.basename(file) === 'facts.mjs') continue;
    const text = fs.readFileSync(file, 'utf8');
    const call = text.match(
      /Intl\.(NumberFormat|DateTimeFormat|PluralRules)|toLocaleString|toFixed|toPrecision/,
    );
    assert.equal(call, null, `${path.basename(file)}: ${call?.[0]}`);
  }
});

test('page sources hold no other host and no digit run of eight or eleven', () => {
  for (const file of sourceFiles(['.ts', '.mjs', '.html', '.css', '.json'])) {
    const text = fs.readFileSync(file, 'utf8');
    for (const match of text.matchAll(/https?:\/\/[^\s'"`)]+/g)) {
      // The planted remote asset, the loopback server, and the SVG namespace
      // (an identifier that is never requested).
      assert.ok(
        match[0].startsWith('https://assets.invalid/') ||
          match[0].startsWith('http://127.0.0.1') ||
          match[0] === 'http://www.w3.org/2000/svg',
        `${path.basename(file)}: ${match[0]}`,
      );
    }
    assert.equal(
      /(^|\D)(\d{8}|\d{11})(\D|$)/.test(text),
      false,
      path.basename(file),
    );
  }
});

test('the string catalogue is closed, bilingual, pending review and numeral-free', () => {
  const catalogue = JSON.parse(read('catalogue.json'));
  const verdict = judgeCatalogue(catalogue);
  assert.equal(verdict.ok, true, verdict.detail);
  assert.equal(catalogue.reviewMark, 'pending native review');
});

test('every catalogue key the page uses exists, and every key is used', () => {
  const catalogue = JSON.parse(read('catalogue.json'));
  const keys = new Set(Object.keys(catalogue.strings));
  const asked = new Set();
  const quoted = new Set();
  for (const file of sourceFiles(['.ts', '.mjs'])) {
    const text = fs.readFileSync(file, 'utf8');
    for (const match of text.matchAll(/\bt\(\s*'([a-zA-Z0-9_.-]+)'/g)) {
      asked.add(match[1]);
    }
    for (const match of text.matchAll(/'([a-zA-Z][a-zA-Z0-9_.-]*)'/g)) {
      quoted.add(match[1]);
    }
  }
  for (const key of asked) assert.ok(keys.has(key), `missing key ${key}`);
  for (const key of keys) assert.ok(quoted.has(key), `unused key ${key}`);
});

// Round 5g, finding 10 (DES-61, DES-20): the lowest class keeps the unit
// opacity of every other class in both themes, so it stays readable against
// the land; the light theme's 0.45 (P3) blended to about 1.14:1.
function blend(hex, under, alpha) {
  const channel = (value, at) => parseInt(value.slice(at + 1, at + 3), 16);
  const mixed = [0, 2, 4].map((at) =>
    Math.round(alpha * channel(hex, at) + (1 - alpha) * channel(under, at)),
  );
  return `#${mixed.map((c) => c.toString(16).padStart(2, '0')).join('')}`;
}

test('the lowest class keeps the unit opacity and about 1.3:1 on the land in both themes', () => {
  const css = read('tokens.css');
  for (const [theme, selector] of [
    [0, "[data-theme='dark']"],
    [1, "[data-theme='light']"],
  ]) {
    const values = block(css, selector);
    const shared = block(css, ':root {');
    const unit = Number(
      values['--eii-unit-opacity'] ?? shared['--eii-unit-opacity'],
    );
    const lowest = Number(values['--eii-unit-opacity-1']);
    assert.equal(lowest, unit, `${selector}: lowest class opacity ${lowest}`);
    const drawn = blend(
      COLOUR_TOKENS['--eii-seq-1'][theme],
      COLOUR_TOKENS['--eii-map-land'][theme],
      lowest,
    );
    const value = ratio(drawn, COLOUR_TOKENS['--eii-map-land'][theme]);
    assert.ok(
      value >= 1.29,
      `${selector}: class 1 on the land ${value.toFixed(3)}`,
    );
  }
});

// Round 5g, finding 3 (DES-28, RTL-031): the map's label sizes take the
// Arabic factor of the page's type in the :lang(ar) block.
test('the Arabic map label sizes are 1.12 times the Latin ones, rounded', () => {
  const css = read('tokens.css');
  const latin = block(css, ':root {');
  const arabic = block(css, ':lang(ar) {');
  for (const name of [
    '--eii-map-label-size',
    '--eii-map-district-size',
    '--eii-map-road-label-size',
  ]) {
    const base = Number.parseFloat(latin[name] ?? '');
    assert.ok(Number.isFinite(base), `Latin ${name}`);
    assert.equal(
      arabic[name],
      `${Math.round(base * 1.12)}px`,
      `Arabic ${name}`,
    );
  }
});
