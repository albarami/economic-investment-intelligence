import { readFileSync } from 'node:fs';

export const REVIEW_PENDING = 'pending native review';
export const REVIEW_APPROVED = 'approved';
export const REVIEW_STATES = [REVIEW_PENDING, REVIEW_APPROVED];
export const REMOTE_FONT = 'https://assets.invalid/font.woff2';
export const FIRST_LABEL_ID = 'labels';
export const LICENCE_PATHS = [
  '/licences/ibm-plex-sans-OFL.txt',
  '/licences/ibm-plex-sans-arabic-OFL.txt',
  '/licences/noto-sans-OFL.txt',
  '/licences/noto-sans-arabic-OFL.txt',
];
export const BASELINE_IDS = [
  'arabic-labels',
  'english-labels',
  'hexagons-below-labels',
];
export const IMAGE_FILES = [
  'arabic-labels.png',
  'english-labels.png',
  'hexagons-below-labels.png',
];
export const EVIDENCE_FILES = [
  ...IMAGE_FILES,
  'run.json',
  'network.json',
  'asset-manifest.json',
  'visual-review.md',
];
export const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self'",
  "font-src 'self'",
  "img-src 'self' data: blob:",
  "worker-src 'self' blob:",
  "connect-src 'self'",
  "child-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
].join('; ');

const NAMES_URL = new URL('./names.json', import.meta.url);

export function loadNames() {
  return JSON.parse(readFileSync(NAMES_URL, 'utf8'));
}

export function arabicNames() {
  return loadNames().places.map((place) => place.nameAr);
}

function verdict(ok, detail, state = '') {
  return { ok, detail, state };
}

export function judgeCsp(header) {
  if (header === null || header === undefined || header === '') {
    return verdict(false, 'missing content-security-policy');
  }
  if (!header.includes("default-src 'self'")) {
    return verdict(false, 'content-security-policy is not restricted to self');
  }
  return verdict(true, '');
}

export function requestDecision(url, origin) {
  if (url.startsWith('data:') || url.startsWith('blob:')) return 'local';
  if (url.startsWith('http://') || url.startsWith('https://')) {
    try {
      return new URL(url).origin === origin ? 'same-origin' : 'blocked';
    } catch {
      return 'blocked';
    }
  }
  return 'same-origin';
}

export function judgeRequests(urls, origin) {
  const rows = urls.map((url) => ({
    url,
    decision: requestDecision(url, origin),
  }));
  const blocked = rows.filter((row) => row.decision === 'blocked');
  if (blocked.length > 0) {
    return {
      ok: false,
      detail: `non-same-origin request: ${blocked[0].url}`,
      rows,
      state: '',
    };
  }
  return { ok: true, detail: '', rows, state: '' };
}

export function judgeLicences(texts) {
  if (texts.length !== LICENCE_PATHS.length) {
    return verdict(false, 'missing font licence text');
  }
  for (const text of texts) {
    if (!text.includes('SIL Open Font License')) {
      return verdict(false, 'missing font licence text');
    }
  }
  return verdict(true, '');
}

export function judgeBeforeId(beforeId, firstLabelId) {
  if (!firstLabelId) return verdict(false, 'missing first label id');
  if (beforeId !== firstLabelId) {
    return verdict(false, 'beforeId is not the first label layer');
  }
  return verdict(true, '');
}

export function judgeWebGpu(source) {
  if (!source.includes('visgl:webgl-only')) {
    return verdict(false, 'WebGL-only export condition is missing');
  }
  if (/\bwebgpu\s*:\s*true\b/i.test(source)) {
    return verdict(false, 'WebGPU is enabled');
  }
  return verdict(true, '');
}

export function judgeRtlPlugin(source) {
  if (source.includes('setRTLTextPlugin')) {
    return verdict(false, 'right-to-left plugin call');
  }
  return verdict(true, '');
}

export function judgeFonts(families, omittedArabic) {
  if (omittedArabic || !families.includes('Noto Sans Arabic Regular')) {
    return verdict(false, 'Arabic font face is absent');
  }
  if (!families.includes('Noto Sans Regular')) {
    return verdict(false, 'Latin font face is absent');
  }
  return verdict(true, '');
}

export function judgeDigits(text) {
  if (/[\u0660-\u0669\u06F0-\u06F9]/.test(text)) {
    return verdict(false, 'Arabic-Indic digit');
  }
  return verdict(true, '');
}

export function judgeLetterSpacing(value) {
  if (value !== '0px' && value !== '0' && value !== 'normal') {
    return verdict(false, 'Arabic letter spacing is not zero');
  }
  return verdict(true, '');
}

export function judgeDirection(direction, bearing, mirrored) {
  if (direction !== 'rtl')
    return verdict(false, 'Arabic document direction is not rtl');
  if (bearing !== 0 || mirrored) return verdict(false, 'the map is mirrored');
  return verdict(true, '');
}

export function judgeNames(places) {
  const states = new Set();
  for (const place of places) {
    if (!REVIEW_STATES.includes(place.review)) {
      return verdict(false, `unreviewed string: ${place.nameAr}`);
    }
    states.add(place.review);
  }
  if (states.size !== 1) {
    return verdict(
      false,
      'visual review must be pending native review or approved',
    );
  }
  return verdict(true, '', [...states][0]);
}

function reviewState(text) {
  const line = text.split('\n').find((item) => item.startsWith('Verdict: '));
  if (!line) return '';
  return line.slice('Verdict: '.length).trim();
}

export function judgeReview(text) {
  if (text === null || text === undefined || text === '') {
    return verdict(false, 'missing visual review record');
  }
  const state = reviewState(text);
  if (!REVIEW_STATES.includes(state)) {
    return verdict(
      false,
      'visual review must be pending native review or approved',
    );
  }
  const required = [
    ...arabicNames(),
    ...BASELINE_IDS.map((id) => `${id}-chromium-linux.png`),
  ];
  for (const item of required) {
    const match = text
      .split('\n')
      .find((line) => line.includes(item) && line.includes(state));
    if (!match) {
      return verdict(false, `visual review is missing ${item}`);
    }
  }
  return verdict(true, '', state);
}

export function judgeHash(input) {
  if (input.expected !== input.actual) {
    return verdict(
      false,
      `changed image whose hash does not match: ${input.file}`,
    );
  }
  return verdict(true, '');
}

export function judgeNetwork(records) {
  if (!Array.isArray(records))
    return verdict(false, 'network record is missing');
  let planted = false;
  for (const row of records) {
    if (row.url === REMOTE_FONT && row.decision === 'blocked') planted = true;
    if (
      (row.url.startsWith('http://') || row.url.startsWith('https://')) &&
      row.decision !== 'blocked'
    ) {
      return verdict(false, `non-same-origin request: ${row.url}`);
    }
  }
  if (!planted)
    return verdict(false, `missing blocked request: ${REMOTE_FONT}`);
  return verdict(true, '');
}
