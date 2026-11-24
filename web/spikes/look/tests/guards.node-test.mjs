import { releaseFacts } from '../release-build.mjs';
import assert from 'node:assert/strict';
import { test } from 'node:test';
import zlib from 'node:zlib';
import {
  CAPTURE_FILES,
  CLASS_WORDS,
  OFF_SCREEN_WORDS,
  VARIANTS,
  decodePng,
  encodeGreyPng,
  findMarkers,
  greyscale,
  judgeAttribution,
  judgeCatalogue,
  judgeChipChains,
  judgeClassWords,
  judgeCoreClear,
  judgeDensity,
  judgeDigitWidths,
  judgeDocument,
  judgeInside,
  judgeLabelLanguage,
  judgeLabelsClear,
  judgeLitLayers,
  judgeMarks,
  judgeMotion,
  judgeNoOverlap,
  judgeNumerals,
  judgeTextFloor,
  pngSize,
} from '../guards.mjs';

test('a numeral inside a Fact chip passes', () => {
  const verdict = judgeNumerals([
    { text: '1,240', inChip: true, where: 'bdi' },
    { text: 'Firm density', inChip: false, where: 'p' },
  ]);
  assert.equal(verdict.ok, true, verdict.detail);
});

test('a planted numeral outside a Fact chip fails and names its place', () => {
  const verdict = judgeNumerals([
    { text: 'Scene 0', inChip: false, where: 'p.legend' },
  ]);
  assert.equal(verdict.ok, false);
  assert.match(verdict.detail, /p\.legend/);
});

test('Arabic-Indic and extended digits count as numerals', () => {
  for (const text of ['١٢٠', '۱۲۰']) {
    const verdict = judgeNumerals([{ text, inChip: false, where: 'p' }]);
    assert.equal(verdict.ok, false, text);
  }
});

test('the class words of ruling L-111 are listed in both languages', () => {
  for (const word of [
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
  ]) {
    assert.ok(CLASS_WORDS.en.includes(word), word);
  }
  for (const word of ['عام', 'اصطناعي', 'محاكاة', 'محجوب', 'خيالية']) {
    assert.ok(CLASS_WORDS.ar.includes(word), word);
  }
});

test('the screen text of the page passes the class-word scan', () => {
  const screen = [
    'EII Viewing as: Company A Dark Light Pause motion العربية Reset',
    'Firms per sq km By release unit Lighter means more firms. Show as table',
    'Firm density Firm density peaks in one compact core.',
    'A count of firms is not a count of jobs or of people. More evidence',
    '© OpenStreetMap contributors · Protomaps',
    'العرض بصفة: الشركة أ داكن فاتح إيقاف الحركة English إعادة الضبط',
    'المنشآت لكل كم مربع حسب وحدة الإصدار عرض في جدول كثافة المنشآت',
    'تبلغ كثافة المنشآت ذروتها في نواة واحدة متماسكة.',
    'عدد المنشآت ليس عدد الوظائف ولا عدد السكان. مزيد من الأدلة',
  ].join(' ');
  const verdict = judgeClassWords(screen);
  assert.equal(verdict.ok, true, verdict.detail);
});

test('each planted class word fails, in either language and any case', () => {
  for (const word of CLASS_WORDS.en) {
    for (const form of [
      word,
      word.toUpperCase(),
      `${word[0].toUpperCase()}${word.slice(1)}`,
    ]) {
      const verdict = judgeClassWords(`Firms (${form}) per sq km`);
      assert.equal(verdict.ok, false, form);
    }
  }
  for (const word of CLASS_WORDS.ar) {
    for (const form of [word, `ال${word}`, `وال${word}`]) {
      const verdict = judgeClassWords(`بيانات ${form} هنا`);
      assert.equal(verdict.ok, false, form);
    }
  }
});

function mark(overrides = {}) {
  return {
    where: 'bdi.chip-num',
    textDecoration: 'none solid rgb(230, 234, 235)',
    borderStyle: 'none',
    backgroundImage: 'none',
    ...overrides,
  };
}

test('plain elements carry no class mark', () => {
  const verdict = judgeMarks([mark(), mark({ borderStyle: 'solid' })]);
  assert.equal(verdict.ok, true, verdict.detail);
});

test('a planted underline, dotted edge or pattern fails', () => {
  for (const planted of [
    { textDecoration: 'underline dotted rgb(1, 2, 3)' },
    { textDecoration: 'underline solid rgb(1, 2, 3)' },
    { borderStyle: 'none none dashed' },
    { borderStyle: 'dotted' },
    { backgroundImage: 'radial-gradient(circle, red, blue)' },
    { backgroundImage: 'repeating-linear-gradient(45deg, red, blue)' },
    { backgroundImage: 'url("hatch.png")' },
  ]) {
    const verdict = judgeMarks([mark(planted)]);
    assert.equal(verdict.ok, false, JSON.stringify(planted));
  }
});

function litLayer(step, paint = {}) {
  return JSON.stringify({
    id: `lit-${step}`,
    type: 'fill',
    paint: { 'fill-color': '#000', ...paint },
  });
}

test('a lit layer of five plain fills passes', () => {
  const verdict = judgeLitLayers([1, 2, 3, 4, 5].map((step) => litLayer(step)));
  assert.equal(verdict.ok, true, verdict.detail);
});

test('a planted texture on the lit layer fails', () => {
  const layers = [1, 2, 3, 4, 5].map((step) => litLayer(step));
  layers[1] = litLayer(2, { 'fill-pattern': 'dots' });
  assert.equal(judgeLitLayers(layers).ok, false);
  assert.equal(judgeLitLayers(layers.slice(0, 4)).ok, false);
});

const CHAIN = releaseFacts([['8943a1d8b6bffff', 80, 2]])[0].chain;
const FACTS = [
  {
    id: 'densest-unit',
    provenance: 'synthetic',
    origin: 'synthetic',
    chain: CHAIN,
  },
  { id: 'break-1', provenance: 'synthetic', origin: 'synthetic', chain: CHAIN },
];

test('chips that resolve to released facts with chains pass', () => {
  const verdict = judgeChipChains(
    [
      { variant: 'value', ids: ['densest-unit'] },
      { variant: 'compact', ids: ['break-1'] },
      { variant: 'reference', ids: [] },
    ],
    FACTS,
    ['densest-unit', 'break-1'],
  );
  assert.equal(verdict.ok, true, verdict.detail);
});

test('a chip without a released fact, class or chain fails', () => {
  const cases = [
    [[{ variant: 'value', ids: ['missing'] }], FACTS],
    [
      [{ variant: 'value', ids: ['densest-unit'] }],
      [{ id: 'densest-unit', provenance: '', chain: CHAIN }],
    ],
    [
      [{ variant: 'value', ids: ['densest-unit'] }],
      [{ id: 'densest-unit', provenance: 'synthetic', chain: null }],
    ],
    [
      [{ variant: 'value', ids: ['densest-unit'] }],
      [
        {
          id: 'densest-unit',
          provenance: 'synthetic',
          chain: { table: 'a', method: '', source: 'c' },
        },
      ],
    ],
    [[{ variant: 'refused', ids: [] }], FACTS],
    [[{ variant: 'value', ids: [] }], FACTS],
  ];
  for (const [chips, facts] of cases) {
    assert.equal(judgeChipChains(chips, facts, []).ok, false);
  }
  const missing = judgeChipChains(
    [{ variant: 'value', ids: ['densest-unit'] }],
    FACTS,
    ['densest-unit', 'break-1'],
  );
  assert.equal(missing.ok, false);
  assert.match(missing.detail, /break-1/);
});

test('the attribution must be visible and name both sources', () => {
  const text = '© OpenStreetMap contributors · Protomaps';
  assert.equal(judgeAttribution({ text, visible: true }).ok, true);
  assert.equal(judgeAttribution({ text, visible: false }).ok, false);
  assert.equal(
    judgeAttribution({ text: '© OpenStreetMap', visible: true }).ok,
    false,
  );
});

test('the Arabic route must be rtl and ar', () => {
  assert.equal(judgeDocument({ lang: 'ar', dir: 'rtl' }, 'ar').ok, true);
  assert.equal(judgeDocument({ lang: 'ar', dir: 'ltr' }, 'ar').ok, false);
  assert.equal(judgeDocument({ lang: 'en', dir: 'rtl' }, 'ar').ok, false);
  assert.equal(judgeDocument({ lang: 'en', dir: 'ltr' }, 'en').ok, true);
});

test('reduced motion must show the end state at once', () => {
  assert.equal(judgeMotion({ reduced: true, litMode: 'instant' }).ok, true);
  assert.equal(judgeMotion({ reduced: true, litMode: 'staged' }).ok, false);
  assert.equal(judgeMotion({ reduced: false, litMode: 'staged' }).ok, true);
  assert.equal(judgeMotion({ reduced: false, litMode: 'instant' }).ok, false);
});

test('the wall density holds one headline, three chips and one caveat', () => {
  const good = { headlines: 1, valueChips: 3, caveats: 1 };
  assert.equal(judgeDensity(good).ok, true);
  assert.equal(judgeDensity({ ...good, headlines: 2 }).ok, false);
  assert.equal(judgeDensity({ ...good, valueChips: 4 }).ok, false);
  assert.equal(judgeDensity({ ...good, caveats: 0 }).ok, false);
  assert.equal(
    judgeDensity({ ...good, valueChips: 0, chips: 4 }).detail,
    'the answer card holds more than three chips of any kind',
  );
  assert.equal(
    judgeDensity({ ...good, valueChips: 0 }).detail,
    'the Brief holds no Fact chip',
  );
});

test('ten digits of one width pass and a wider digit fails', () => {
  const even = Array.from({ length: 10 }, () => 38.4);
  assert.equal(judgeDigitWidths([{ name: 'large', widths: even }]).ok, true);
  const odd = [...even];
  odd[1] = 30;
  assert.equal(judgeDigitWidths([{ name: 'large', widths: odd }]).ok, false);
  assert.equal(
    judgeDigitWidths([{ name: 'large', widths: even.slice(0, 9) }]).ok,
    false,
  );
});

test('labels must read the interface language only', () => {
  const ar = '["coalesce",["get","name:ar"],["get","name"]]';
  const en = '["coalesce",["get","name:en"],["get","name"]]';
  assert.equal(judgeLabelLanguage([ar], 'ar').ok, true);
  assert.equal(judgeLabelLanguage([en], 'en').ok, true);
  assert.equal(judgeLabelLanguage([en], 'ar').ok, false);
  assert.equal(
    judgeLabelLanguage(
      ['["coalesce",["get","name:ar"],["get","name:en"]]'],
      'ar',
    ).ok,
    false,
  );
});

test('text below the wall floor fails', () => {
  assert.equal(judgeTextFloor([{ size: 28, where: 'p' }], 28).ok, true);
  const verdict = judgeTextFloor([{ size: 14, where: 'span' }], 28);
  assert.equal(verdict.ok, false);
  assert.match(verdict.detail, /14 px/);
});

test('a plate outside the safe area fails', () => {
  const frame = { x: 96, y: 54, width: 1728, height: 972 };
  const inside = { name: 'brief', x: 1118, y: 142, width: 706, height: 600 };
  assert.equal(judgeInside([inside], frame).ok, true);
  const outside = { ...inside, x: 1200 };
  assert.equal(judgeInside([outside], frame).ok, false);
});

test('overlapping plates fail', () => {
  const a = { name: 'legend', x: 96, y: 700, width: 560, height: 300 };
  const b = { name: 'brief', x: 1118, y: 142, width: 706, height: 600 };
  assert.equal(judgeNoOverlap([a, b]).ok, true);
  assert.equal(judgeNoOverlap([a, { ...b, x: 600, y: 800 }]).ok, false);
});

test('a map label clear of every plate passes; one under a plate fails and is named', () => {
  assert.equal(judgeLabelsClear([]).ok, true);
  const verdict = judgeLabelsClear([{ label: 'Doha', plate: 'topbar-start' }]);
  assert.equal(verdict.ok, false);
  assert.match(verdict.detail, /"Doha" touches the topbar-start plate/);
});

test('a bright cell outside the legend passes; one under it fails', () => {
  const legend = { name: 'legend', x: 96, y: 700, width: 560, height: 300 };
  assert.equal(judgeCoreClear([{ x: 900, y: 600 }], [legend]).ok, true);
  assert.equal(judgeCoreClear([{ x: 656.5, y: 600 }], [legend]).ok, true);
  const under = judgeCoreClear([{ x: 300, y: 800 }], [legend]);
  assert.equal(under.ok, false);
  assert.match(under.detail, /under the legend plate/);
  assert.equal(judgeCoreClear([{ x: 96, y: 700 }], [legend]).ok, false);
});

function catalogue(overrides = {}) {
  return {
    reviewMark: 'pending native review',
    strings: {
      reset: {
        en: 'Reset',
        ar: 'إعادة الضبط',
        review: 'pending native review',
      },
      ...overrides,
    },
  };
}

test('a clean catalogue passes', () => {
  const verdict = judgeCatalogue(catalogue());
  assert.equal(verdict.ok, true, verdict.detail);
});

test('a numeral in the catalogue fails', () => {
  const verdict = judgeCatalogue(
    catalogue({
      x: { en: 'Scene 1', ar: 'مشهد', review: 'pending native review' },
    }),
  );
  assert.equal(verdict.ok, false);
  assert.match(verdict.detail, /numeral/);
});

test('an Arabic string without its review mark fails', () => {
  const verdict = judgeCatalogue(
    catalogue({ x: { en: 'Reset', ar: 'إعادة الضبط', review: '' } }),
  );
  assert.equal(verdict.ok, false);
  assert.match(verdict.detail, /review/);
});

test('an Arabic string marked approved by a model fails', () => {
  const verdict = judgeCatalogue(
    catalogue({ x: { en: 'Reset', ar: 'إعادة الضبط', review: 'approved' } }),
  );
  assert.equal(verdict.ok, false);
});

test('a missing language fails', () => {
  const verdict = judgeCatalogue(
    catalogue({ x: { en: 'Reset', review: 'pending native review' } }),
  );
  assert.equal(verdict.ok, false);
});

test('each word that stays off screen fails', () => {
  assert.ok(OFF_SCREEN_WORDS.includes('likely'));
  assert.ok(OFF_SCREEN_WORDS.includes('forecast'));
  for (const word of OFF_SCREEN_WORDS) {
    const verdict = judgeCatalogue(
      catalogue({
        x: {
          en: `This is ${word} here`,
          ar: 'نص',
          review: 'pending native review',
        },
      }),
    );
    assert.equal(verdict.ok, false, word);
  }
});

test('production markers are found in text', () => {
  assert.deepEqual(findMarkers('a /en/_look b'), ['/en/_look']);
  assert.deepEqual(findMarkers('nothing'), []);
});

// The round-4 seven and, since round 5 (P2), the home in the four variants.
test('four variants, the seven captures and the four home captures are named', () => {
  assert.deepEqual(
    VARIANTS.map((item) => `${item.lang}-${item.theme}`),
    ['en-dark', 'en-light', 'ar-dark', 'ar-light'],
  );
  assert.deepEqual(CAPTURE_FILES, [
    'en-dark.png',
    'en-light.png',
    'ar-dark.png',
    'ar-light.png',
    'en-dark-greyscale.png',
    'ar-dark-greyscale.png',
    'en-dark-buildings.png',
    'home-en-dark.png',
    'home-en-light.png',
    'home-ar-dark.png',
    'home-ar-light.png',
  ]);
});

function crcTable() {
  const table = [];
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table.push(c >>> 0);
  }
  return table;
}

function chunk(type, data, table) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  let c = 0xffffffff;
  for (const byte of body) c = table[(c ^ byte) & 0xff] ^ (c >>> 8);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE((c ^ 0xffffffff) >>> 0);
  return Buffer.concat([length, body, crc]);
}

function rgbPng(width, height, pixels, filter) {
  const table = crcTable();
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 2;
  const rows = [];
  for (let y = 0; y < height; y += 1) {
    const row = Buffer.alloc(1 + width * 3);
    row[0] = filter;
    for (let x = 0; x < width; x += 1) {
      const [r, g, b] = pixels[y * width + x];
      const left = x > 0 ? pixels[y * width + x - 1] : [0, 0, 0];
      const delta = filter === 1 ? left : [0, 0, 0];
      row[1 + x * 3] = (r - delta[0]) & 0xff;
      row[2 + x * 3] = (g - delta[1]) & 0xff;
      row[3 + x * 3] = (b - delta[2]) & 0xff;
    }
    rows.push(row);
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', header, table),
    chunk('IDAT', zlib.deflateSync(Buffer.concat(rows)), table),
    chunk('IEND', Buffer.alloc(0), table),
  ]);
}

test('a PNG header gives its size', () => {
  const png = rgbPng(3, 2, new Array(6).fill([10, 20, 30]), 0);
  assert.deepEqual(pngSize(png), { width: 3, height: 2 });
});

test('a PNG with the sub filter decodes to its pixels', () => {
  const pixels = [
    [255, 0, 0],
    [0, 255, 0],
    [0, 0, 255],
    [16, 21, 28],
  ];
  const decoded = decodePng(rgbPng(2, 2, pixels, 1));
  assert.equal(decoded.width, 2);
  assert.equal(decoded.channels, 3);
  assert.deepEqual([...decoded.data.subarray(0, 6)], [255, 0, 0, 0, 255, 0]);
  assert.deepEqual([...decoded.data.subarray(9, 12)], [16, 21, 28]);
});

test('greyscale follows relative luminance and keeps lightness order', () => {
  const decoded = decodePng(
    rgbPng(
      4,
      1,
      [
        [0, 0, 0],
        [255, 255, 255],
        [0x2f, 0x4a, 0x5e],
        [0xeb, 0xe3, 0xb0],
      ],
      0,
    ),
  );
  const grey = greyscale(decoded);
  assert.equal(grey[0], 0);
  assert.equal(grey[1], 255);
  assert.ok(grey[2] < grey[3]);
});

test('a greyscale PNG round-trips through the decoder', () => {
  const grey = Uint8Array.from([0, 64, 128, 255, 12, 200]);
  const png = encodeGreyPng(3, 2, grey);
  const decoded = decodePng(png);
  assert.equal(decoded.channels, 1);
  assert.deepEqual([...decoded.data], [...grey]);
});
