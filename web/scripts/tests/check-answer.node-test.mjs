import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';

import {
  REQUIRED_LEXICONS,
  inspectAnswer,
  lexiconFiles,
  lexiconScanner,
  lexiconTerms,
  unscannedLexicons,
} from '../check-answer.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.resolve(HERE, '../..');
const ROOT = path.resolve(WEB, '..');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'eii-answer-check-'));
after(() => fs.rmSync(tmp, { recursive: true, force: true }));

const LEXICONS = path.join(ROOT, 'product', 'assistant', 'lexicons');

function writeTree(name, mutate) {
  const web = path.join(tmp, name, 'web');
  const root = path.join(tmp, name);
  const lexicons = path.join(root, 'product', 'assistant', 'lexicons');
  fs.mkdirSync(lexicons, { recursive: true });
  for (const file of fs.readdirSync(LEXICONS))
    fs.copyFileSync(path.join(LEXICONS, file), path.join(lexicons, file));
  fs.mkdirSync(path.join(web, 'src', 'i18n'), { recursive: true });
  fs.mkdirSync(path.join(web, 'src', 'brief'), { recursive: true });
  fs.mkdirSync(path.join(web, 'src', 'styles'), { recursive: true });
  fs.mkdirSync(path.join(web, 'node_modules', '@fontsource', 'ibm-plex-sans'), {
    recursive: true,
  });
  fs.mkdirSync(
    path.join(web, 'node_modules', '@fontsource', 'ibm-plex-sans-arabic'),
    { recursive: true },
  );
  fs.copyFileSync(
    path.join(WEB, 'src', 'i18n', 'en.json'),
    path.join(web, 'src', 'i18n', 'en.json'),
  );
  fs.copyFileSync(
    path.join(WEB, 'src', 'i18n', 'ar.json'),
    path.join(web, 'src', 'i18n', 'ar.json'),
  );
  fs.copyFileSync(
    path.join(WEB, 'src', 'brief', 'catalogue.generated.json'),
    path.join(web, 'src', 'brief', 'catalogue.generated.json'),
  );
  fs.copyFileSync(
    path.join(WEB, 'src', 'styles', 'answer.css'),
    path.join(web, 'src', 'styles', 'answer.css'),
  );
  fs.writeFileSync(
    path.join(web, 'node_modules', '@fontsource', 'ibm-plex-sans', 'LICENSE'),
    'licence\n',
  );
  fs.writeFileSync(
    path.join(
      web,
      'node_modules',
      '@fontsource',
      'ibm-plex-sans-arabic',
      'LICENSE',
    ),
    'licence\n',
  );
  mutate(web, root);
  return { web, root };
}

test('the answer tree passes', () => {
  const problems = inspectAnswer({ root: ROOT, web: WEB });
  assert.deepEqual(problems, []);
});

test('a numeral in the string catalogue fails', () => {
  const { web, root } = writeTree('numeral', (dir) => {
    const file = path.join(dir, 'src', 'i18n', 'en.json');
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    parsed.strings['chip.loading'] = 'Loading 1';
    fs.writeFileSync(file, JSON.stringify(parsed));
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.some((item) => item.startsWith('numeral:')));
});

test('a disable comment naming the numeral rule fails', () => {
  const { web, root } = writeTree('disable', (dir) => {
    fs.mkdirSync(path.join(dir, 'src', 'app'), { recursive: true });
    fs.writeFileSync(
      path.join(dir, 'src', 'app', 'plant.ts'),
      '/* eslint-disable eii/numerals-only-in-fact-chip */\nexport const view = 1;\n',
    );
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.some((item) => item.startsWith('disable:')));
});

test('an off-screen word fails', () => {
  const { web, root } = writeTree('off', (dir) => {
    const file = path.join(dir, 'src', 'i18n', 'en.json');
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    parsed.strings['chip.open'] = 'The best reading';
    fs.writeFileSync(file, JSON.stringify(parsed));
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.some((item) => item.startsWith('off-screen:')));
});

test('a class word outside the drawer keys fails', () => {
  const { web, root } = writeTree('class', (dir) => {
    const file = path.join(dir, 'src', 'i18n', 'en.json');
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    parsed.strings['chip.open'] = 'Public figure';
    fs.writeFileSync(file, JSON.stringify(parsed));
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.some((item) => item.startsWith('class-word:')));
});

for (const [language, word] of [
  ['en', 'Synthetic'],
  ['ar', '\u0628\u0627\u0644\u0645\u062d\u0627\u0643\u0627\u0629'],
]) {
  test(`an origin class word under a drawer class key fails (${language})`, () => {
    const { web, root } = writeTree(`origin-${language}`, (dir) => {
      const file = path.join(dir, 'src', 'i18n', `${language}.json`);
      const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
      parsed.strings['drawer.class.synthetic'] = word;
      fs.writeFileSync(file, JSON.stringify(parsed));
    });
    const problems = inspectAnswer({ root, web });
    assert.ok(problems.includes('class-word:drawer.class.synthetic'));
  });
}

test('a physical axis in the answer style fails', () => {
  const { web, root } = writeTree('axis', (dir) => {
    fs.appendFileSync(
      path.join(dir, 'src', 'styles', 'answer.css'),
      '\n.plant { margin-left: 0; }\n',
    );
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.includes('physical-axis'));
});

test('a catalogue with an unknown key fails', () => {
  const { web, root } = writeTree('catalogue', (dir) => {
    const file = path.join(dir, 'src', 'brief', 'catalogue.generated.json');
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    parsed.extra = true;
    fs.writeFileSync(file, JSON.stringify(parsed));
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.includes('catalogue-keys'));
});

test('a dist without the font licence texts fails', () => {
  const { web, root } = writeTree('licence', (dir) => {
    fs.mkdirSync(path.join(dir, 'dist'), { recursive: true });
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.some((item) => item.startsWith('font-dist:')));
  assert.ok(problems.includes('font-dist:mapbox-gl-rtl-text.txt'));
});

test('a lexicon file that is not scanned is a failure', () => {
  const missed = unscannedLexicons(['kept.yaml', 'missed.yaml'], ['kept.yaml']);
  assert.deepEqual(missed, ['missed.yaml']);
  const { web, root } = writeTree('lexicon', (dir, repo) => {
    const folder = path.join(repo, 'product', 'assistant', 'lexicons');
    fs.mkdirSync(folder, { recursive: true });
    fs.writeFileSync(path.join(folder, 'planted.yaml'), 'zzplantword\n');
    const file = path.join(dir, 'src', 'i18n', 'en.json');
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    parsed.strings['chip.open'] = 'zzplantword';
    fs.writeFileSync(file, JSON.stringify(parsed));
  });
  assert.equal(lexiconFiles(root).length, fs.readdirSync(LEXICONS).length + 1);
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.some((item) => item.startsWith('lexicon-hit:')));
});

test('a missing string catalogue fails', () => {
  const { web, root } = writeTree('missing', (dir) => {
    fs.rmSync(path.join(dir, 'src', 'i18n', 'en.json'));
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.includes('strings-missing'));
});

const ARABIC_CLASS = [
  'العام',
  'عامة',
  'العامة',
  'علني',
  'العلني',
  'علنية',
  'العلنية',
  'الاصطناعي',
  'اصطناعية',
  'الاصطناعية',
  'المحاكاة',
  'بالمحاكاة',
  'المحجوب',
  'محجوبة',
  'المحجوبة',
];

for (const term of ARABIC_CLASS) {
  test(`a closed-face Arabic class form fails: ${term}`, () => {
    const { web, root } = writeTree(`class-${term}`, (dir) => {
      const file = path.join(dir, 'src', 'i18n', 'ar.json');
      const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
      parsed.strings['chip.open'] = term;
      fs.writeFileSync(file, JSON.stringify(parsed));
    });
    const problems = inspectAnswer({ root, web });
    assert.ok(problems.some((item) => item.startsWith('class-word:')));
  });
}

for (const term of [
  'odds',
  'chance',
  'probability',
  'confidence',
  'likely',
  'will',
  'spending power',
  'income present',
  'purchasing power',
]) {
  test(`an off-screen phrase fails: ${term}`, () => {
    const { web, root } = writeTree(`off-${term}`, (dir) => {
      const file = path.join(dir, 'src', 'i18n', 'en.json');
      const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
      parsed.strings['chip.open'] = `A ${term} note`;
      fs.writeFileSync(file, JSON.stringify(parsed));
    });
    const problems = inspectAnswer({ root, web });
    assert.ok(problems.some((item) => item.startsWith('off-screen:')));
  });
}

test('a footfall phrase fails', () => {
  const { web, root } = writeTree('footfall', (dir) => {
    const file = path.join(dir, 'src', 'i18n', 'en.json');
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    parsed.strings['chip.open'] = 'footfall of Sample';
    fs.writeFileSync(file, JSON.stringify(parsed));
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.some((item) => item.startsWith('footfall:')));
});

test('a forecast word on an ordinary key fails and an allowed key does not', () => {
  const denied = writeTree('forecast-denied', (dir) => {
    const file = path.join(dir, 'src', 'i18n', 'en.json');
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    parsed.strings['chip.open'] = 'A forecast note';
    fs.writeFileSync(file, JSON.stringify(parsed));
  });
  const deniedProblems = inspectAnswer(denied);
  assert.ok(deniedProblems.some((item) => item.startsWith('forecast:')));
  const allowed = writeTree('forecast-allowed', (dir) => {
    const file = path.join(dir, 'src', 'i18n', 'en.json');
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    parsed.strings['series_forecast.note'] = 'A forecast note';
    fs.writeFileSync(file, JSON.stringify(parsed));
  });
  const allowedProblems = inspectAnswer(allowed);
  assert.equal(
    allowedProblems.some((item) => item.startsWith('forecast:')),
    false,
  );
});

test('an Arabic numeral in the Arabic catalogue fails', () => {
  const { web, root } = writeTree('ar-numeral', (dir) => {
    const file = path.join(dir, 'src', 'i18n', 'ar.json');
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    parsed.strings['chip.loading'] = 'تحميل \u0661';
    fs.writeFileSync(file, JSON.stringify(parsed));
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.some((item) => item.startsWith('numeral:')));
});

test('a malformed catalogue fails', () => {
  const { web, root } = writeTree('bad-json', (dir) => {
    fs.writeFileSync(
      path.join(dir, 'src', 'brief', 'catalogue.generated.json'),
      '{',
    );
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.includes('catalogue-unreadable'));
});

test('a catalogue version that is not a hash fails', () => {
  const { web, root } = writeTree('bad-version', (dir) => {
    const file = path.join(dir, 'src', 'brief', 'catalogue.generated.json');
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    parsed.version = 'not-a-hash';
    fs.writeFileSync(file, JSON.stringify(parsed));
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.includes('catalogue-version'));
});

test('a missing generated catalogue fails', () => {
  const { web, root } = writeTree('no-catalogue', (dir) => {
    fs.rmSync(path.join(dir, 'src', 'brief', 'catalogue.generated.json'));
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.includes('catalogue-missing'));
});

test('a missing style input fails', () => {
  const { web, root } = writeTree('no-style', (dir) => {
    fs.rmSync(path.join(dir, 'src', 'styles', 'answer.css'));
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.includes('style-missing'));
});

test('a missing font source fails', () => {
  const { web, root } = writeTree('no-font', (dir) => {
    fs.rmSync(
      path.join(dir, 'node_modules', '@fontsource', 'ibm-plex-sans', 'LICENSE'),
    );
  });
  const problems = inspectAnswer({ root, web });
  assert.ok(problems.some((item) => item.startsWith('font-source:')));
});

// AI-38 numeral lexicons (S3-T09 decision 0064 item 43). Each plant must be
// refused by the lexicon scan that `npm run check` runs over en.json and ar.json.

function plantString(name, language, key, value) {
  return writeTree(name, (dir) => {
    const file = path.join(dir, 'src', 'i18n', `${language}.json`);
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    parsed.strings[key] = value;
    fs.writeFileSync(file, JSON.stringify(parsed));
  });
}

function lexiconText(name) {
  return fs.readFileSync(path.join(LEXICONS, name), 'utf8');
}

test('the English and Arabic numeral lexicons are present, versioned and scanned', () => {
  const present = lexiconFiles(ROOT).map((file) => path.basename(file));
  for (const name of [...REQUIRED_LEXICONS, 'numerals.third.txt']) {
    assert.ok(present.includes(name), name);
    assert.match(
      lexiconText(name),
      /^# AI-38 .* Version \d+, \d{4}-\d{2}-\d{2}\./u,
    );
    assert.ok(lexiconTerms(lexiconText(name)).length > 0, name);
  }
  assert.match(
    lexiconText('numerals.ar.txt'),
    /Pending native review \(OI-09/u,
  );
  assert.deepEqual(lexiconScanner(ROOT).problems, []);
});

test('the English lexicon holds every AI-38 group', () => {
  const terms = new Set(lexiconTerms(lexiconText('numerals.en.txt')));
  for (const term of [
    'zero',
    'one',
    'nineteen',
    'ninety',
    'hundred',
    'thousand',
    'million',
    'first',
    'once',
    'twice',
    'thrice',
    'second',
    'nineteenth',
    'twentieth',
    'ninetieth',
    'hundredth',
    'thousandth',
    'half',
    'quarter',
    'tenths',
    'double',
    'triple',
    'tenfold',
    'percent',
    'per cent',
    'percentage',
    '%',
  ])
    assert.ok(terms.has(term), term);
});

test('every English lexicon term planted in a sentence is refused', () => {
  const scanner = lexiconScanner(ROOT);
  for (const term of lexiconTerms(lexiconText('numerals.en.txt'))) {
    for (const form of [
      term,
      term.toUpperCase(),
      `${term[0]?.toUpperCase()}${term.slice(1)}`,
    ])
      assert.ok(
        scanner.hits('chip.open', `A ${form} note`).includes(term),
        `${form} passed`,
      );
  }
});

test('every Arabic lexicon term is refused bare, with clitics, endings and diacritics', () => {
  const scanner = lexiconScanner(ROOT);
  for (const term of lexiconTerms(lexiconText('numerals.ar.txt'))) {
    const forms = [
      term,
      `\u0648${term}`,
      `\u0627\u0644${term}`,
      `\u0628\u0627\u0644${term}`,
      `\u0644\u0644${term}`,
      `${term}\u0627\u062a`,
      term.split('').join('\u064e'),
      term.replace(/\u0627/gu, '\u0623'),
    ];
    for (const form of forms)
      assert.ok(
        scanner
          .hits('chip.open', `\u0646\u0635 ${form} \u0647\u0646\u0627`)
          .includes(term),
        `${form} passed`,
      );
  }
});

test('every third-language number word is refused in either catalogue', () => {
  const scanner = lexiconScanner(ROOT);
  const terms = lexiconTerms(lexiconText('numerals.third.txt'));
  assert.ok(terms.length >= 20);
  for (const term of terms)
    assert.ok(scanner.hits('chip.open', `A ${term} note`).includes(term), term);
});

for (const [language, value] of [
  ['en', 'Two areas side by side'],
  ['en', 'The first area'],
  ['en', 'Twice the area'],
  ['en', 'Half the area'],
  ['en', 'Ten percent of the area'],
  [
    'ar',
    '\u0627\u0644\u0645\u0646\u0637\u0642\u0629 \u0627\u0644\u062b\u0627\u0644\u062b\u0629',
  ],
  ['ar', '\u0646\u0635\u0641 \u0633\u0627\u0639\u0629'],
  ['ar', '\u062e\u0645\u0633\u0629 \u0628\u0627\u0644\u0645\u0626\u0629'],
]) {
  test(`a planted lexicon word fails the check (${language}: ${value})`, () => {
    const tree = plantString(
      `lex-${language}-${value.length}-${value.charCodeAt(0)}`,
      language,
      'chip.open',
      value,
    );
    const problems = inspectAnswer(tree);
    assert.ok(
      problems.some((item) =>
        item.startsWith(`lexicon-hit:${language}.json:chip.open:`),
      ),
      problems.join(','),
    );
  });
}

for (const [language, value] of [
  ['en', 'Trois zones'],
  ['en', 'Zwei Gebiete'],
  ['en', 'Dos zonas'],
  ['en', 'iki alan'],
  ['ar', '\u067e\u0646\u062c \u0645\u0646\u0637\u0642\u0629'],
  ['ar', '\u06cc\u06a9 \u0645\u0646\u0637\u0642\u0629'],
  ['en', '\u0924\u0940\u0928 areas'],
]) {
  test(`a planted third-language number word fails (${language}: ${value})`, () => {
    const name = `third-${language}-${value.codePointAt(0)}`;
    const planted = plantString(name, language, 'chip.open', value);
    assert.ok(
      inspectAnswer(planted).some((item) =>
        item.startsWith(`lexicon-hit:${language}.json:chip.open:`),
      ),
    );
    fs.rmSync(
      path.join(
        planted.root,
        'product',
        'assistant',
        'lexicons',
        'numerals.third.txt',
      ),
    );
    assert.equal(
      inspectAnswer(planted).some((item) => item.startsWith('lexicon-hit:')),
      false,
      'the third-language lexicon is the deciding guard',
    );
  });
}

test('a whole word is required: an English number inside a longer word passes', () => {
  const scanner = lexiconScanner(ROOT);
  for (const value of [
    'None of the phone content is often done',
    'Someone tone',
  ])
    assert.deepEqual(scanner.hits('chip.open', value), []);
});

test('the Arabic radius compound passes and the bare half still fails', () => {
  const scanner = lexiconScanner(ROOT);
  const radius = '\u0646\u0635\u0641 \u0642\u0637\u0631';
  assert.deepEqual(scanner.hits('draw.radius', radius), []);
  assert.deepEqual(scanner.hits('draw.radius', `\u0628${radius}`), []);
  assert.ok(
    scanner.hits(
      'draw.radius',
      '\u0646\u0635\u0641 \u0627\u0644\u0645\u0646\u0637\u0642\u0629',
    ).length > 0,
  );
});

test('a unit word holds only its own term, and only under its own key', () => {
  const scanner = lexiconScanner(ROOT);
  assert.deepEqual(scanner.hits('unit.usd_million', 'Million US dollars'), []);
  assert.deepEqual(scanner.hits('unit.percent', '%'), []);
  assert.ok(
    scanner.hits('chip.open', 'Million US dollars').includes('million'),
  );
  assert.ok(scanner.hits('unit.percent', 'percent').includes('percent'));
  assert.ok(scanner.hits('unit.usd_million', 'Two million').includes('two'));
  const planted = plantString(
    'unit-moved',
    'en',
    'chip.open',
    'USD per thousand requests',
  );
  assert.ok(
    inspectAnswer(planted).includes('lexicon-hit:en.json:chip.open:thousand'),
  );
});

for (const name of REQUIRED_LEXICONS) {
  test(`a missing ${name} fails`, () => {
    const tree = writeTree(`no-${name}`, (_dir, root) => {
      fs.rmSync(path.join(root, 'product', 'assistant', 'lexicons', name));
    });
    assert.ok(inspectAnswer(tree).includes(`lexicon-missing:${name}`));
  });
}

test('a lexicon with no term fails', () => {
  const tree = writeTree('empty-lexicon', (_dir, root) => {
    fs.writeFileSync(
      path.join(root, 'product', 'assistant', 'lexicons', 'numerals.en.txt'),
      '# AI-38 numeral lexicon, English. Version 1, 2026-11-21.\n',
    );
  });
  assert.ok(inspectAnswer(tree).includes('lexicon-empty:numerals.en.txt'));
});
