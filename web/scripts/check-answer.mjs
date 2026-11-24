/**
 * FE-40 companion checks for the answer surface.
 * Missing inputs fail. A lexicon file that is not scanned fails.
 */
import fs from 'node:fs';
import path from 'node:path';

const OFF_SCREEN = [
  'best',
  'odds',
  'chance',
  'probability',
  'confidence',
  'likely',
  'will',
  'spending power',
  'income present',
  'purchasing power',
];

const CLASS_WORDS = [
  'public',
  'private',
  'protected',
  'suppressed',
  'synthetic',
  'simulated',
  'fictional',
  'invented',
  'fixture',
  'demonstrator',
  'عام',
  'العام',
  'عامة',
  'العامة',
  'علني',
  'العلني',
  'علنية',
  'العلنية',
  'اصطناعي',
  'الاصطناعي',
  'اصطناعية',
  'الاصطناعية',
  'محاكاة',
  'المحاكاة',
  'بالمحاكاة',
  'محجوب',
  'المحجوب',
  'محجوبة',
  'المحجوبة',
];

const CATALOGUE_KEYS = [
  'claims',
  'components',
  'directives',
  'fragments',
  'questions',
  'version',
];

const LICENCE_FILES = [
  'mapbox-gl-rtl-text.txt',
  'ibm-plex-sans.txt',
  'ibm-plex-sans-arabic.txt',
];

const FONT_SOURCES = [
  ['@fontsource/ibm-plex-sans', 'LICENSE'],
  ['@fontsource/ibm-plex-sans-arabic', 'LICENSE'],
];

export function lexiconFiles(root) {
  const dir = path.join(root, 'product', 'assistant', 'lexicons');
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter(
      (name) =>
        name.endsWith('.txt') ||
        name.endsWith('.yaml') ||
        name.endsWith('.yml'),
    )
    .map((name) => path.join(dir, name))
    .sort();
}

export function unscannedLexicons(present, scanned) {
  const seen = new Set(scanned);
  return present.filter((file) => !seen.has(file));
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function walkStrings(value, key, visit) {
  if (typeof value === 'string') {
    visit(key, value);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) walkStrings(item, key, visit);
    return;
  }
  if (value && typeof value === 'object') {
    for (const [child, item] of Object.entries(value))
      walkStrings(item, child, visit);
  }
}

function word(pattern, value) {
  return new RegExp(
    `(?:^|[^\\p{L}\\p{N}])(?:${pattern})(?=$|[^\\p{L}\\p{N}])`,
    'iu',
  ).test(value);
}

function digitsOutsidePlaceholders(value) {
  const stripped = value.replace(/\{[A-Za-z_]+\}/g, '');
  return /\p{Nd}/u.test(stripped);
}

function catalogueProblems(file) {
  const problems = [];
  if (!fs.existsSync(file)) return ['catalogue-missing'];
  let parsed;
  try {
    parsed = readJson(file);
  } catch {
    return ['catalogue-unreadable'];
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
    return ['catalogue-shape'];
  const keys = Object.keys(parsed);
  if (
    keys.length !== CATALOGUE_KEYS.length ||
    CATALOGUE_KEYS.some((key) => !(key in parsed))
  )
    problems.push('catalogue-keys');
  if (
    typeof parsed.version !== 'string' ||
    !/^[0-9a-f]{64}$/.test(parsed.version)
  )
    problems.push('catalogue-version');
  return problems;
}

function stringProblems(file) {
  const problems = [];
  if (!fs.existsSync(file)) return ['strings-missing'];
  const parsed = readJson(file);
  const strings = parsed.strings;
  if (!strings || typeof strings !== 'object') return ['strings-shape'];
  walkStrings(strings, '', (key, value) => {
    if (digitsOutsidePlaceholders(value)) problems.push(`numeral:${key}`);
    if (value === 'pending-native-review')
      problems.push(`review-rendered:${key}`);
    // Only the withheld-state word may carry a class word (decision 0035
    // items 1 and 2): no origin class word is rendered, under any key.
    const withheldKey = key === 'drawer.class.suppressed';
    if (!withheldKey) {
      for (const term of CLASS_WORDS) {
        if (word(term, value)) problems.push(`class-word:${key}`);
      }
    }
    for (const term of OFF_SCREEN) {
      if (word(term.replace(' ', '\\s+'), value))
        problems.push(`off-screen:${key}`);
    }
    if (/footfall of\s+\S+/iu.test(value)) problems.push(`footfall:${key}`);
    const forecastAllowed =
      key.includes('series_forecast') || key.includes('denial');
    if (!forecastAllowed && word('forecast', value))
      problems.push(`forecast:${key}`);
  });
  return problems;
}

/** AI-38 lexicons that must be present: English and Arabic number words. */
export const REQUIRED_LEXICONS = ['numerals.en.txt', 'numerals.ar.txt'];

/**
 * Unit words that only the Fact chip family renders beside its value
 * (`unitLabel` and the operational meter's price quantity in FactChip),
 * each with the lexicon terms it may hold. The same term under any other
 * key, or another term under these keys, still fails.
 */
export const UNIT_TERMS = new Map([
  ['unit.percent', ['%']],
  ['unit.usd_million', ['million', 'مليون']],
  ['operational.priceUnit', ['thousand', 'ألف']],
]);

const ARABIC_SCRIPT = /[\u0600-\u06FF]/u;
const ARABIC_PROCLITIC = '(?:[وف])?(?:(?:[بكل])?ال|لل|[بكل])?';
const ARABIC_ENDING = '(?:ا|ان|ين|ة|ات)?';

/** Removes Arabic diacritics and tatweel and unifies the alef forms. */
export function normaliseArabic(value) {
  return value
    .replace(/[\u064B-\u065F\u0670\u0640]/gu, '')
    .replace(/[أإآٱ]/gu, 'ا');
}

function escapeTerm(term) {
  return term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Whole-word matcher for one lexicon term; Arabic terms take clitics. */
export function lexiconMatcher(term) {
  if (ARABIC_SCRIPT.test(term)) {
    const core = escapeTerm(normaliseArabic(term)).replace(/\s+/g, '\\s+');
    const pattern = new RegExp(
      `(?:^|[^\\p{L}\\p{N}])${ARABIC_PROCLITIC}${core}${ARABIC_ENDING}(?=$|[^\\p{L}\\p{N}])`,
      'u',
    );
    return (value) => pattern.test(normaliseArabic(value));
  }
  const core = escapeTerm(term).replace(/\s+/g, '\\s+');
  const pattern = new RegExp(
    `(?:^|[^\\p{L}\\p{N}])${core}(?=$|[^\\p{L}\\p{N}])`,
    'iu',
  );
  return (value) => pattern.test(value);
}

function lines(text) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0 && !line.startsWith('#'));
}

/**
 * Lexicon terms: one per line; blank lines and # comments are skipped.
 * A line that starts with ! names a fixed compound that is not a number
 * (for example the Arabic word for radius); it is not a term.
 */
export function lexiconTerms(text) {
  return lines(text).filter((line) => !line.startsWith('!'));
}

/** The fixed compounds of a lexicon, each removed before terms match. */
export function lexiconCompounds(text) {
  return lines(text)
    .filter((line) => line.startsWith('!'))
    .map((line) => line.slice(1).trim())
    .filter((line) => line.length > 0);
}

/** Removes each whole fixed compound, with Arabic proclitics, from a value. */
export function withoutCompounds(value, compounds) {
  let out = normaliseArabic(value);
  for (const compound of compounds) {
    const core = escapeTerm(normaliseArabic(compound)).replace(/\s+/g, '\\s+');
    const lead = ARABIC_SCRIPT.test(compound) ? ARABIC_PROCLITIC : '';
    const pattern = new RegExp(
      `(^|[^\\p{L}\\p{N}])${lead}${core}(?=$|[^\\p{L}\\p{N}])`,
      'giu',
    );
    out = out.replace(pattern, '$1 ');
  }
  return out;
}

/**
 * Reads every lexicon of the folder and returns its problems and a scanner
 * that lists the lexicon terms one string value holds under one key.
 */
export function lexiconScanner(root) {
  const present = lexiconFiles(root);
  const problems = [];
  for (const name of REQUIRED_LEXICONS) {
    if (!present.some((file) => path.basename(file) === name))
      problems.push(`lexicon-missing:${name}`);
  }
  const scanned = [];
  const terms = [];
  const compounds = [];
  for (const file of present) {
    const text = fs.readFileSync(file, 'utf8');
    const found = lexiconTerms(text);
    if (found.length === 0) {
      problems.push(`lexicon-empty:${path.basename(file)}`);
      continue;
    }
    compounds.push(...lexiconCompounds(text));
    scanned.push(file);
    for (const term of found) terms.push({ term, test: lexiconMatcher(term) });
  }
  const missed = unscannedLexicons(present, scanned);
  for (const file of missed) {
    const name = path.basename(file);
    if (!problems.includes(`lexicon-empty:${name}`))
      problems.push(`lexicon-unscanned:${name}`);
  }
  const hits = (key, value) => {
    const allowed = UNIT_TERMS.get(key) ?? [];
    const cleaned = withoutCompounds(value, compounds);
    return terms
      .filter(({ term, test }) => !allowed.includes(term) && test(cleaned))
      .map(({ term }) => term);
  };
  return { problems, terms: terms.map(({ term }) => term), hits };
}

function lexiconProblems(root, catalogues) {
  const scanner = lexiconScanner(root);
  const problems = [...scanner.problems];
  for (const file of catalogues) {
    if (!fs.existsSync(file)) continue;
    const strings = readJson(file).strings;
    if (!strings || typeof strings !== 'object') continue;
    walkStrings(strings, '', (key, value) => {
      for (const term of scanner.hits(key, value))
        problems.push(`lexicon-hit:${path.basename(file)}:${key}:${term}`);
    });
  }
  return problems;
}

function disableProblems(web) {
  const problems = [];
  const roots = [path.join(web, 'src'), path.join(web, 'eslint.config.js')];
  const files = [];
  for (const root of roots) {
    if (!fs.existsSync(root)) continue;
    if (fs.statSync(root).isFile()) files.push(root);
    else collect(root, files);
  }
  for (const file of files) {
    if (!/\.(?:ts|tsx|js|mjs)$/.test(file)) continue;
    const text = fs.readFileSync(file, 'utf8');
    if (
      text.includes('eslint-disable') &&
      text.includes('numerals-only-in-fact-chip')
    )
      problems.push(`disable:${path.relative(web, file)}`);
  }
  return problems;
}

function collect(dir, files) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    if (name === 'node_modules' || name === 'dist') continue;
    const info = fs.statSync(full);
    if (info.isDirectory()) collect(full, files);
    else files.push(full);
  }
}

export function physicalAxis(text) {
  if (/(?:^|[^-\w])(?:left|right)\s*:/m.test(text)) return ['physical-axis'];
  if (
    /\b(?:margin|padding|border|inset|scroll-margin|scroll-padding)-(?:left|right)\b/.test(
      text,
    )
  )
    return ['physical-axis'];
  return [];
}

function styleProblems(file) {
  if (!fs.existsSync(file)) return ['style-missing'];
  return physicalAxis(fs.readFileSync(file, 'utf8'));
}

function licenceProblems(web) {
  const problems = [];
  for (const [folder, name] of FONT_SOURCES) {
    const file = path.join(web, 'node_modules', folder, name);
    if (!fs.existsSync(file)) problems.push(`font-source:${folder}`);
  }
  const dist = path.join(web, 'dist');
  if (fs.existsSync(dist)) {
    for (const name of LICENCE_FILES) {
      const file = path.join(dist, 'licences', name);
      if (!fs.existsSync(file)) problems.push(`font-dist:${name}`);
    }
  }
  return problems;
}

export function inspectAnswer({ root, web }) {
  const problems = [
    ...catalogueProblems(
      path.join(web, 'src', 'brief', 'catalogue.generated.json'),
    ),
    ...stringProblems(path.join(web, 'src', 'i18n', 'en.json')),
    ...stringProblems(path.join(web, 'src', 'i18n', 'ar.json')),
    ...styleProblems(path.join(web, 'src', 'styles', 'answer.css')),
    ...disableProblems(web),
    ...licenceProblems(web),
    ...lexiconProblems(root, [
      path.join(web, 'src', 'i18n', 'en.json'),
      path.join(web, 'src', 'i18n', 'ar.json'),
    ]),
  ];
  return problems;
}

function parseArgs(argv) {
  let root = null;
  let web = null;
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--root' || arg === '--web') {
      const value = argv[index + 1];
      if (value === undefined) throw new Error(`missing value for ${arg}`);
      if (arg === '--root') root = value;
      else web = value;
      index += 1;
      continue;
    }
    throw new Error(`unknown argument ${arg}`);
  }
  const here = process.cwd();
  return {
    web: web ?? here,
    root: root ?? path.resolve(web ?? here, '..'),
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const problems = inspectAnswer(args);
  if (problems.length > 0) {
    for (const problem of problems) process.stderr.write(`${problem}\n`);
    process.exitCode = 1;
  }
}

const invoked =
  process.argv[1] && path.resolve(process.argv[1]).endsWith('check-answer.mjs');
if (invoked) main();
