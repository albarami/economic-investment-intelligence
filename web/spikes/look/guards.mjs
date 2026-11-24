// Pure judges for the look page. The browser suite collects what the page
// rendered; these functions decide. Each has planted cases in
// tests/guards.node-test.mjs.
import zlib from 'node:zlib';
import { completeFactChain } from './lineage.mjs';

export {
  CSP,
  judgeCsp,
  judgeDigits,
  judgeRequests,
} from '../glyphs/guards.mjs';

export const ROUTES = ['/en/_look', '/ar/_look'];
export const VARIANTS = [
  { lang: 'en', theme: 'dark' },
  { lang: 'en', theme: 'light' },
  { lang: 'ar', theme: 'dark' },
  { lang: 'ar', theme: 'light' },
];
export const CAPTURE_FILES = [
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
];
// V9 of round 5: the four street cameras of the brief, each in both themes
// and both languages, written into .overnight/OUT/look/street/.
export const STREET_CAMERAS = [
  { name: 'a', center: [51.5369, 25.2546], zoom: 15.3, pitch: 0, bearing: 0 },
  {
    name: 'b',
    center: [51.5369, 25.2546],
    zoom: 15.8,
    pitch: 55,
    bearing: -20,
  },
  { name: 'c', center: [51.527, 25.322], zoom: 14, pitch: 0, bearing: 0 },
  { name: 'd', center: [51.53, 25.322], zoom: 15.4, pitch: 55, bearing: -25 },
];
export const STREET_FILES = STREET_CAMERAS.flatMap((camera) =>
  VARIANTS.map(
    (variant) => `${camera.name}-${variant.lang}-${variant.theme}.png`,
  ),
);
// V7: past district zoom the Brief and the legend fold; at city zoom they
// are open. Between the two the page holds its last state while the camera
// moves, and opens them once it rests.
export const FOLD_ZOOM = 13.5;
export const UNFOLD_ZOOM = 12;
export const PRODUCTION_MARKERS = [...ROUTES, 'eii-look-proof'];
export const REVIEW_PENDING = 'pending native review';
export const CLASSES = ['public', 'synthetic', 'simulated', 'suppressed'];

// Rulings L-111 to L-114 (change C1 of the brief): words that name or mark
// the class of data, or call the page a proof, a sample or invented, and
// never reach the screen. English and Arabic are kept here, in one place.
export const CLASS_WORDS = {
  en: [
    'public',
    'private',
    'protected',
    'suppressed',
    'synthetic',
    'simulated',
    'fictional',
    'invented',
    'fixture',
    'fixtures',
    'demonstrator',
    'demonstration',
    'proof',
    'sample',
    'generated',
    'demo',
  ],
  ar: [
    'عام',
    'عامة',
    'خاص',
    'خاصة',
    'محمي',
    'محمية',
    'محجوب',
    'محجوبة',
    'اصطناعي',
    'اصطناعية',
    'محاكاة',
    'محاكى',
    'خيالي',
    'خيالية',
    'مخترع',
    'مخترعة',
    'مختلق',
    'مختلقة',
    'تجريبي',
    'تجريبية',
    'توضيحي',
    'توضيحية',
    'افتراضي',
    'افتراضية',
    'إثبات',
    'عينة',
    'مولدة',
    'مُولَّدة',
  ],
};

// DES-117 and FE-40: words that stay off screen.
export const OFF_SCREEN_WORDS = [
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
  'footfall of',
  'forecast',
];

const NUMERAL = /\p{Nd}/u;

function pass() {
  return { ok: true, detail: '' };
}

function fail(detail) {
  return { ok: false, detail };
}

export function findMarkers(text) {
  return PRODUCTION_MARKERS.filter((marker) => text.includes(marker));
}

export function judgeNumerals(items) {
  for (const item of items) {
    if (NUMERAL.test(item.text) && !item.inChip) {
      return fail(
        `numeral outside a Fact chip: ${item.where}: ${item.text.trim()}`,
      );
    }
  }
  return pass();
}

function wordPattern(word) {
  return new RegExp(`(^|[^\\p{L}])${word}([^\\p{L}]|$)`, 'iu');
}

// Arabic words are also found with the article and the joined particles
// wa, fa, bi, li and ka before them.
function arabicPattern(word) {
  return new RegExp(`(^|[^\\p{L}])(و|ف|ب|ل|ك)?(ال)?${word}([^\\p{L}]|$)`, 'u');
}

export function judgeClassWords(text) {
  for (const word of CLASS_WORDS.en) {
    if (wordPattern(word).test(text))
      return fail(`class word on screen: ${word}`);
  }
  for (const word of CLASS_WORDS.ar) {
    if (arabicPattern(word).test(text))
      return fail(`class word on screen: ${word}`);
  }
  return pass();
}

// No element may carry a class mark: an underline of any style, a dotted or
// dashed border, or a patterned background (dots, dashes, hatch).
export function judgeMarks(items) {
  for (const item of items) {
    if (item.textDecoration.includes('underline')) {
      return fail(`underline on ${item.where}`);
    }
    if (/dotted|dashed/.test(item.borderStyle)) {
      return fail(`dotted or dashed edge on ${item.where}`);
    }
    if (/gradient|url\(/.test(item.backgroundImage)) {
      return fail(`patterned background on ${item.where}`);
    }
  }
  return pass();
}

// The lit layer is a plain fill: no pattern, no dash, no extrusion.
export function judgeLitLayers(layers) {
  if (layers.length !== 5) return fail('the lit layer is not five classes');
  for (const text of layers) {
    const layer = JSON.parse(text);
    if (layer.type !== 'fill') return fail(`${layer.id} is not a fill`);
    const paint = layer.paint ?? {};
    for (const key of ['fill-pattern', 'line-dasharray']) {
      if (key in paint) return fail(`${layer.id} carries ${key}`);
    }
  }
  return pass();
}

// V1 and V2 of round 5: every footprint of the open buildings archive from
// zoom 13 (no filter, so nothing is thinned), raised from zoom 14 by its own
// height attribute (never one slab height).
export function judgeBuildingLayers(layers) {
  const flat = layers.find((layer) => layer.type === 'fill');
  const raised = layers.find((layer) => layer.type === 'fill-extrusion');
  if (flat === undefined || raised === undefined)
    return fail('the flat or the raised building layer is missing');
  for (const layer of [flat, raised]) {
    if (layer.source !== 'buildings')
      return fail(`${layer.id} does not read the open buildings archive`);
    if ('filter' in layer) return fail(`${layer.id} thins the footprints`);
  }
  if ((flat.minzoom ?? 0) > 13) return fail('footprints start after zoom 13');
  if ((raised.minzoom ?? 0) > 14) return fail('extrusion starts after zoom 14');
  const height = JSON.stringify(raised.paint?.['fill-extrusion-height']);
  if (!height?.includes('["get","height"]'))
    return fail("the extrusion does not read each footprint's height");
  return pass();
}

// V4 of round 5: main roads named from zoom 12, secondary streets from 14,
// every named street from 15, each as a line label.
export function judgeRoadLabels(layers) {
  const tiers = [
    ['label-road-main', 12],
    ['label-road-secondary', 14],
    ['label-road-street', 15],
  ];
  for (const [id, zoom] of tiers) {
    const layer = layers.find((item) => item.id === id);
    if (layer === undefined) return fail(`${id} is missing`);
    if ((layer.minzoom ?? 0) > zoom) return fail(`${id} starts after ${zoom}`);
    if (layer.layout?.['symbol-placement'] !== 'line')
      return fail(`${id} is not set along its road`);
  }
  return pass();
}

// Round 5f, F2, widened in round 5g: every layer that draws a firm lies
// under every label. The map draws the style's layers in order, first drawn
// lowest, and a circle takes no part in the labels' collisions, so a firm
// layer after a label layer covers its names. The firm layers are whichever
// layers read the establishment source, not a fixed list of ids, so a ring
// or a cluster under a new name is judged too. `layers` are the style's
// layers in drawing order; the place and district names must be among them.
export const FIRM_SOURCE = 'establishments';
export const NAME_LAYERS = ['label-district', 'label-place'];

export function judgePointsUnderLabels(layers) {
  const ids = layers.map((layer) => layer.id);
  const points = layers.filter((layer) => layer.source === FIRM_SOURCE);
  if (points.length === 0) return fail('no establishment layer is drawn');
  for (const id of NAME_LAYERS) {
    if (!ids.includes(id)) return fail(`the label layer ${id} is missing`);
  }
  for (const layer of points) {
    const covered = layers
      .slice(0, ids.indexOf(layer.id))
      .filter((item) => item.type === 'symbol')
      .map((item) => item.id);
    if (covered.length > 0)
      return fail(
        `the establishment layer ${layer.id} is drawn above the label layers ${covered.join(', ')}`,
      );
  }
  return pass();
}

// Round 5g, G4: the densest-areas bracket label is one line. In Arabic it
// sits on the high end of the bracket, which is drawn left to right in both
// languages. A planted label that wraps, or that leaves the high end, fails.
const BRACKET_EDGE = 2;

export function judgeBracketLabel(state) {
  if (state.lines !== 1) {
    return fail(
      state.lines === 2
        ? 'the densest-areas label wraps onto two lines'
        : `the densest-areas label wraps to ${state.lines} lines`,
    );
  }
  if (state.lang === 'ar') {
    if (Math.abs(state.textRight - state.bracketRight) > BRACKET_EDGE)
      return fail(
        'the Arabic label does not sit at the high end of its bracket',
      );
  } else if (Math.abs(state.textLeft - state.bracketLeft) > BRACKET_EDGE) {
    return fail('the label does not sit at the start of its bracket');
  }
  return pass();
}

// Round 5g, G5: at each street camera the folded plates cover no more lit
// units in Arabic than in English. `rows` count the lit units whose centres
// fall inside a plate.
export function judgeStreetCover(rows) {
  for (const row of rows) {
    if (row.ar > row.en)
      return fail(
        `camera ${row.camera} covers ${row.ar} lit units in Arabic and ${row.en} in English`,
      );
  }
  return pass();
}

// Round 5g, G2: one spelling of a district name in a view. Comparison ignores
// case, so two English forms of one name fail. An empty string is not a name.
export function judgeUniqueNames(texts) {
  const seen = new Set();
  for (const text of texts) {
    const key = String(text).trim().toLowerCase();
    if (key === '') continue;
    if (seen.has(key)) return fail(`the name ${text} is drawn twice`);
    seen.add(key);
  }
  return pass();
}

// V7 of round 5: folded at street zoom, open at city zoom.
export function judgeFold(states) {
  for (const state of states) {
    const want =
      state.zoom >= FOLD_ZOOM
        ? 'folded'
        : state.zoom <= UNFOLD_ZOOM
          ? 'open'
          : null;
    if (want === null) continue;
    for (const part of ['brief', 'legend']) {
      if (state[part] !== want)
        return fail(`at zoom ${state.zoom} the ${part} is ${state[part]}`);
    }
  }
  return pass();
}

// Round 5g, findings 4, 17, 21 and 25 (DES-19, DES-20, DES-68): at street
// zoom the folded legend keeps its four breaks and its direction in words,
// and "Show as table" shows the five-row table. Only the scope line folds.
export function judgeFoldedLegend(state) {
  if (state.zoom < FOLD_ZOOM) return pass();
  if (state.breaks < 4)
    return fail(`the folded legend shows ${state.breaks} of the four breaks`);
  if (state.direction.trim() === '')
    return fail('the folded legend states no direction in words');
  if (state.table !== null && (!state.table.shown || state.table.rows !== 5))
    return fail(
      `the folded legend shows ${state.table.shown ? state.table.rows : 'no'} table rows after "Show as table"`,
    );
  return pass();
}

// Round 5g, finding 9 (WCAG 3.1.2, DES-28): the map credits stay one Latin
// line with no separator left at a line end; the note on building heights
// is a run in the page's language at that language's caption size.
export function judgeAttributionRuns(state, lang, size) {
  if (state.note === null)
    return fail('the attribution has no note in the page language');
  if (state.note.lang !== lang)
    return fail(
      `the attribution note is tagged ${state.note.lang}, not ${lang}`,
    );
  if (state.note.size !== size)
    return fail(
      `the attribution note is set at ${state.note.size}px, not ${size}px`,
    );
  if (state.creditLines !== 1)
    return fail(`the attribution credits wrap to ${state.creditLines} lines`);
  if (state.creditText.trim().endsWith('·'))
    return fail('a separator ends the attribution credits');
  return pass();
}

// Ruling L-143 item 3: the City framing rests at a city scale. Its cap (the
// token `--eii-city-max-zoom`) sits at or below the unfold zoom, the camera
// rests at or below the cap, and the answer opens with both plates open.
export function judgeCityFrame(state, cap) {
  if (!Number.isFinite(cap)) return fail('the City framing has no cap');
  if (cap > UNFOLD_ZOOM)
    return fail(`the city cap ${cap} is past the unfold zoom ${UNFOLD_ZOOM}`);
  if (!(state.zoom <= cap))
    return fail(
      `the City framing rests at zoom ${state.zoom}, past the city cap ${cap}`,
    );
  for (const part of ['brief', 'legend']) {
    if (state[part] !== 'open')
      return fail(`at the City framing the ${part} is ${state[part]}`);
  }
  return pass();
}

// Round 5e, E1: the quiet plate of P1 that names the lit district. It sizes
// to its name (at most DISTRICT_PLATE_STRETCH times the name's own width),
// reads the district's name, shows the whole name on the screen, stands just
// above its cell (the cell's point under the plate, at most
// DISTRICT_PLATE_REACH px below its lower edge: the leader's length), and has
// ended its entrance. `found` is what the page drew.
export const DISTRICT_PLATE_STRETCH = 2;
export const DISTRICT_PLATE_REACH = 64;

export function judgeDistrictPlate(found) {
  const { name, text, plate, textBox, point, viewport } = found;
  if (!found.shown) return fail('the district plate is not shown');
  if (text !== name)
    return fail(`the district plate reads "${text}" and not "${name}"`);
  if (!(plate.width <= DISTRICT_PLATE_STRETCH * textBox.width))
    return fail(
      `the district plate is ${Math.round(plate.width)} px wide for a name of ${Math.round(textBox.width)} px`,
    );
  if (
    textBox.x < 0 ||
    textBox.y < 0 ||
    textBox.x + textBox.width > viewport.width ||
    textBox.y + textBox.height > viewport.height
  )
    return fail("the district plate's name is cut by the screen's edge");
  const below = point.y - (plate.y + plate.height);
  if (
    point.x < plate.x ||
    point.x > plate.x + plate.width ||
    below < 0 ||
    below > DISTRICT_PLATE_REACH
  )
    return fail('the district plate is not just above its cell');
  if (found.running > 0)
    return fail("the district plate's entrance has not ended");
  return pass();
}

// Round 5e, E2: a major place label is wholly inside the screen, EDGE_MARGIN
// px clear of each edge, or not drawn. The page asks the map for the labels
// that meet one of these four strips along the screen's edges.
export const EDGE_MARGIN = 8;

export function edgeStrips(width, height, margin = EDGE_MARGIN) {
  return [
    { name: 'left', x: 0, y: 0, width: margin, height },
    { name: 'right', x: width - margin, y: 0, width: margin, height },
    { name: 'top', x: 0, y: 0, width, height: margin },
    { name: 'bottom', x: 0, y: height - margin, width, height: margin },
  ];
}

export function judgeLabelsInside(hits) {
  const first = hits[0];
  if (first === undefined) return pass();
  return fail(
    `map label "${first.label}" is cut by the ${first.plate} edge of the screen or lies within ${EDGE_MARGIN} px of it`,
  );
}

// P2 of round 5: one card at a time; the data layer, its legend and every
// numeral belong to the answer alone; the home asks its four questions; every
// other screen has a way back (never a broken screen).
export function judgeScreen(state, want) {
  const shown = state.cards.join(', ') || 'no card';
  if (
    state.screen !== want ||
    state.cards.length !== 1 ||
    state.cards[0] !== want
  )
    return fail(
      `the page shows ${shown} on the ${state.screen} screen, not ${want}`,
    );
  if (want === 'answer') {
    if (state.lit.length === 0 || state.lit.some((level) => level < 1))
      return fail('the answer is not lit');
    if (!state.legend) return fail('the answer has no legend');
  } else {
    if (state.lit.some((level) => level > 0))
      return fail(`the ${want} screen lights the data layer`);
    if (state.legend) return fail(`the ${want} screen shows the legend`);
    if (state.numerals > 0) return fail(`the ${want} screen shows a numeral`);
  }
  if (want === 'home' && state.questions !== 4)
    return fail(`the home asks ${state.questions} questions, not four`);
  if (want !== 'home' && !state.back)
    return fail(`the ${want} screen has no way back`);
  return pass();
}

// The company card (the owner's decision of 2026-11-13): the published fields
// of the register only, with the number of employees among them; no wage and
// no other labour figure.
export const CARD_FIELDS = [
  'field.business',
  'field.category',
  'field.kind',
  'field.subtype',
  'field.legal',
  'field.classification',
  'field.registration',
  'field.registrationIssue',
  'field.registrationExpiry',
  'field.licence',
  'field.licenceIssue',
  'field.licenceExpiry',
  'field.branches',
  'field.employees',
  'field.municipality',
  'field.zone',
];

// Round 5g, finding 15 (rules 7 and 23): the counts of a card are value chips
// of released facts with a complete chain; a reference chip stands only for
// the record dates, the zone and the classification codes.
export const CARD_COUNT_FIELDS = ['field.employees', 'field.branches'];
export const CARD_REFERENCE_FIELDS = [
  'field.registrationIssue',
  'field.registrationExpiry',
  'field.licenceIssue',
  'field.licenceExpiry',
  'field.zone',
  'field.classification',
];

export function judgeCardChips(rows, facts) {
  for (const row of rows) {
    if (CARD_COUNT_FIELDS.includes(row.field)) {
      if (row.chip !== 'value' || row.fact === null)
        return fail(`${row.field} is not a value chip of a released fact`);
      const chained = judgeChipChains(
        [{ variant: 'value', ids: [row.fact] }],
        facts,
        [],
      );
      if (!chained.ok) return chained;
    } else if (
      row.chip === 'reference' &&
      !CARD_REFERENCE_FIELDS.includes(row.field)
    ) {
      return fail(`${row.field} carries a reference chip`);
    }
  }
  return pass();
}

// Round 5g, findings 1, 18 and 19 (dataviz: no value ramp for a category,
// never cycle): no establishment paint takes a colour of the density ramp,
// and the type expression gives no two of its outputs one colour.
function colours(value) {
  if (typeof value === 'string')
    return /^(#|rgb|hsl)/i.test(value) ? [value.toLowerCase()] : [];
  if (Array.isArray(value)) return value.flatMap(colours);
  return [];
}

function outputs(expression) {
  if (!Array.isArray(expression)) return [];
  if (expression[0] === 'case')
    return expression.filter(
      (_, index) =>
        index > 0 && (index % 2 === 0 || index === expression.length - 1),
    );
  if (expression[0] === 'match')
    return expression.filter(
      (_, index) =>
        index > 2 && (index % 2 === 1 || index === expression.length - 1),
    );
  return [];
}

export function judgePointColours(paints, ramp) {
  const forbidden = new Set(ramp.map((colour) => colour.toLowerCase()));
  for (const [name, value] of Object.entries(paints)) {
    for (const colour of colours(value)) {
      if (forbidden.has(colour))
        return fail(
          `the ${name} paint takes the density ramp colour ${colour}`,
        );
    }
  }
  const outs = outputs(paints.types).flatMap(colours);
  if (new Set(outs).size !== outs.length)
    return fail('the type expression gives a repeated colour to two outputs');
  return pass();
}

export function judgeCard(found, row) {
  for (const item of found) {
    if (!CARD_FIELDS.includes(item.field))
      return fail(`${item.field} is not a published field`);
  }
  if (row.employees === null) return pass();
  const employees = found.find((item) => item.field === 'field.employees');
  if (employees === undefined)
    return fail('the card does not show the number of employees');
  if (employees.value.replace(/\D/g, '') !== String(row.employees))
    return fail(
      `the card shows ${employees.value} employees, not ${row.employees}`,
    );
  return pass();
}

// Every chip resolves, in the page's data, to facts of the release with a
// class and a complete chain, and the expected facts are all on screen.
export function judgeChipChains(chips, facts, expected) {
  const byId = new Map(facts.map((fact) => [fact.id, fact]));
  const seen = new Set();
  for (const chip of chips) {
    if (chip.variant === 'refused') return fail('a chip refused its fact');
    if (chip.variant === 'reference') continue;
    if (chip.ids.length === 0) return fail('a chip names no fact');
    for (const id of chip.ids) {
      const fact = byId.get(id);
      if (fact === undefined) return fail(`chip fact ${id} is not released`);
      if (!CLASSES.includes(fact.provenance)) {
        return fail(`fact ${id} has no class`);
      }
      if (!completeFactChain(fact)) {
        return fail(`fact ${id} has no complete source chain`);
      }
      seen.add(id);
    }
  }
  for (const id of expected) {
    if (!seen.has(id)) return fail(`fact ${id} has no chip on screen`);
  }
  return pass();
}

export function judgeAttribution(found) {
  if (!found.visible) return fail('the map attribution is not visible');
  if (
    !found.text.includes('OpenStreetMap') ||
    !found.text.includes('Protomaps')
  )
    return fail(
      'the map attribution does not name OpenStreetMap and Protomaps',
    );
  return pass();
}

export function judgeDocument(root, lang) {
  const dir = lang === 'ar' ? 'rtl' : 'ltr';
  if (root.lang !== lang) return fail(`document language is not ${lang}`);
  if (root.dir !== dir) return fail(`document direction is not ${dir}`);
  return pass();
}

export function judgeMotion(state) {
  if (state.reduced) {
    if (state.litMode !== 'instant') {
      return fail('reduced motion still stages the opening');
    }
    return pass();
  }
  if (state.litMode !== 'staged') return fail('the opening was not staged');
  return pass();
}

export function judgeDensity(counts) {
  if (counts.headlines !== 1)
    return fail('the Brief needs exactly one headline');
  // Round 5g, finding 24: chips of every kind count on the answer card.
  if (counts.chips !== undefined && counts.chips > 3)
    return fail('the answer card holds more than three chips of any kind');
  if (counts.valueChips > 3)
    return fail('the Brief holds more than three Fact chips (DES-140)');
  if (counts.valueChips < 1) return fail('the Brief holds no Fact chip');
  if (counts.caveats !== 1) return fail('the Brief needs exactly one caveat');
  return pass();
}

// Round 5g, finding 22 (DES-68): the legend head names the date of the
// count in exactly one reference chip.
export function judgeLegendPeriod(state, want) {
  if (!state.shown) return fail('the legend names no date of the count');
  if (state.chips.length !== 1)
    return fail(`the legend's date line holds ${state.chips.length} chips`);
  if (state.chips[0] !== want)
    return fail(`the legend's date reads ${state.chips[0]}, not ${want}`);
  return pass();
}

// DES-31: the ten digits have one advance width at each numeral size.
export function judgeDigitWidths(sizes) {
  for (const size of sizes) {
    const first = size.widths[0];
    if (size.widths.length !== 10) return fail(`${size.name}: not ten digits`);
    for (const width of size.widths) {
      if (Math.abs(width - first) > 0.01) {
        return fail(`${size.name}: digits differ in width`);
      }
    }
  }
  return pass();
}

// DES-56: the map's labels read the interface language only.
export function judgeLabelLanguage(fields, lang) {
  const other = lang === 'ar' ? 'name:en' : 'name:ar';
  for (const field of fields) {
    if (!field.includes(`name:${lang}`))
      return fail(`a label does not read name:${lang}`);
    if (field.includes(other)) return fail(`a label reads ${other}`);
  }
  return pass();
}

export function judgeTextFloor(items, floor) {
  for (const item of items) {
    if (item.size < floor) {
      return fail(`text below ${floor} px: ${item.where} at ${item.size} px`);
    }
  }
  return pass();
}

export function judgeInside(rects, frame) {
  const right = frame.x + frame.width;
  const bottom = frame.y + frame.height;
  for (const rect of rects) {
    const inside =
      rect.x >= frame.x - 0.5 &&
      rect.y >= frame.y - 0.5 &&
      rect.x + rect.width <= right + 0.5 &&
      rect.y + rect.height <= bottom + 0.5;
    if (!inside) return fail(`${rect.name} leaves the safe area`);
  }
  return pass();
}

export function judgeNoOverlap(rects) {
  for (let i = 0; i < rects.length; i += 1) {
    for (let j = i + 1; j < rects.length; j += 1) {
      const a = rects[i];
      const b = rects[j];
      const apart =
        a.x + a.width <= b.x + 0.5 ||
        b.x + b.width <= a.x + 0.5 ||
        a.y + a.height <= b.y + 0.5 ||
        b.y + b.height <= a.y + 0.5;
      if (!apart) return fail(`${a.name} overlaps ${b.name}`);
    }
  }
  return pass();
}

// Ruling L-119 item 5: no map label under or touching a plate. `hits` are
// the labels whose placed collision boxes (text and its padding) meet a
// plate's rectangle, as the map itself reports them.
export function judgeLabelsClear(hits) {
  const first = hits[0];
  if (first === undefined) return pass();
  return fail(`map label "${first.label}" touches the ${first.plate} plate`);
}

// Ruling L-119 item 1: the legend covers no bright cell. `points` are the
// screen corners of the cells of the two highest classes.
export function judgeCoreClear(points, rects) {
  for (const rect of rects) {
    for (const point of points) {
      const under =
        point.x >= rect.x &&
        point.x <= rect.x + rect.width &&
        point.y >= rect.y &&
        point.y <= rect.y + rect.height;
      if (under) {
        return fail(
          `a cell of the two highest classes lies under the ${rect.name} plate`,
        );
      }
    }
  }
  return pass();
}

export function judgeCatalogue(catalogue) {
  if (catalogue.reviewMark !== REVIEW_PENDING) {
    return fail('the catalogue review mark is not pending native review');
  }
  for (const [key, entry] of Object.entries(catalogue.strings ?? {})) {
    if (typeof entry.en !== 'string' || entry.en.trim() === '') {
      return fail(`${key} has no English string`);
    }
    if (typeof entry.ar !== 'string' || entry.ar.trim() === '') {
      return fail(`${key} has no Arabic string`);
    }
    if (entry.review !== REVIEW_PENDING) {
      return fail(`${key}: Arabic review mark is not ${REVIEW_PENDING}`);
    }
    for (const text of [entry.en, entry.ar]) {
      if (NUMERAL.test(text)) return fail(`${key} holds a numeral`);
      for (const word of OFF_SCREEN_WORDS) {
        if (wordPattern(word).test(text)) {
          return fail(`${key} holds a word that stays off screen: ${word}`);
        }
      }
    }
  }
  return pass();
}

const SIGNATURE = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

export function pngSize(buffer) {
  for (const [index, byte] of SIGNATURE.entries()) {
    if (buffer[index] !== byte) throw new Error('not a PNG file');
  }
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
}

function paeth(a, b, c) {
  const p = a + b - c;
  const pa = Math.abs(p - a);
  const pb = Math.abs(p - b);
  const pc = Math.abs(p - c);
  if (pa <= pb && pa <= pc) return a;
  if (pb <= pc) return b;
  return c;
}

const CHANNELS = { 0: 1, 2: 3, 6: 4 };

export function decodePng(buffer) {
  const { width, height } = pngSize(buffer);
  let offset = 8;
  let depth = 0;
  let colourType = -1;
  let interlace = 0;
  const parts = [];
  while (offset < buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.toString('ascii', offset + 4, offset + 8);
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') {
      depth = data[8];
      colourType = data[9];
      interlace = data[12];
    } else if (type === 'IDAT') {
      parts.push(data);
    } else if (type === 'IEND') {
      break;
    }
    offset += 12 + length;
  }
  const channels = CHANNELS[colourType];
  if (depth !== 8 || channels === undefined || interlace !== 0) {
    throw new Error('only 8-bit grey, RGB or RGBA PNG without interlace');
  }
  const raw = zlib.inflateSync(Buffer.concat(parts));
  const stride = width * channels;
  const out = new Uint8Array(stride * height);
  for (let y = 0; y < height; y += 1) {
    const filter = raw[y * (stride + 1)];
    const row = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    for (let x = 0; x < stride; x += 1) {
      const left = x >= channels ? out[y * stride + x - channels] : 0;
      const up = y > 0 ? out[(y - 1) * stride + x] : 0;
      const corner =
        x >= channels && y > 0 ? out[(y - 1) * stride + x - channels] : 0;
      let value = row[x];
      if (filter === 1) value += left;
      else if (filter === 2) value += up;
      else if (filter === 3) value += (left + up) >> 1;
      else if (filter === 4) value += paeth(left, up, corner);
      else if (filter !== 0) throw new Error(`unknown PNG filter ${filter}`);
      out[y * stride + x] = value & 0xff;
    }
  }
  return { width, height, channels, data: out };
}

function linear(value) {
  const c = value / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function encoded(y) {
  const c = y <= 0.0031308 ? 12.92 * y : 1.055 * y ** (1 / 2.4) - 0.055;
  return Math.round(Math.min(1, Math.max(0, c)) * 255);
}

const LINEAR = Array.from({ length: 256 }, (_, value) => linear(value));

// Relative luminance (WCAG 2.2), encoded back to sRGB, so that the grey copy
// keeps the lightness order the ramp is tested for (DES-20, DES-64).
export function greyscale(decoded) {
  const { width, height, channels, data } = decoded;
  const out = new Uint8Array(width * height);
  for (let index = 0; index < width * height; index += 1) {
    const at = index * channels;
    if (channels === 1) {
      out[index] = data[at];
      continue;
    }
    const y =
      0.2126 * LINEAR[data[at]] +
      0.7152 * LINEAR[data[at + 1]] +
      0.0722 * LINEAR[data[at + 2]];
    out[index] = encoded(y);
  }
  return out;
}

function chunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(zlib.crc32(body) >>> 0);
  return Buffer.concat([length, body, crc]);
}

export function encodeGreyPng(width, height, grey) {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 0;
  const rows = Buffer.alloc((width + 1) * height);
  for (let y = 0; y < height; y += 1) {
    rows[y * (width + 1)] = 0;
    rows.set(grey.subarray(y * width, (y + 1) * width), y * (width + 1) + 1);
  }
  return Buffer.concat([
    Buffer.from(SIGNATURE),
    chunk('IHDR', header),
    chunk('IDAT', zlib.deflateSync(rows)),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

// Round 5g, findings 18 and 19 (DES-68): the legend keys the marks the map
// shows: the dot from the point zoom, the circle from the cluster zoom below
// it, neither at the City framing.
export function judgePointKey(state, clusterZoom, pointZoom) {
  if (state.zoom >= pointZoom) {
    if (!state.point) return fail('no legend key for the dots');
  } else if (state.zoom >= clusterZoom) {
    if (!state.cluster) return fail('no legend key for the circles');
  } else if (state.point || state.cluster) {
    return fail('a key for marks the map does not show');
  }
  return pass();
}

// Round 5g, findings 11 and 16: the type control is offered only where the
// single points are drawn; its list has a heading and names each type from
// the catalogue, with the count chip of that type.
export function judgeTypeControl(state, pointZoom, want) {
  if (state.zoom < pointZoom && (state.control || state.list))
    return fail('the type control is offered below the point zoom');
  if (state.zoom >= pointZoom && !state.control)
    return fail('the type control is not offered at the point zoom');
  if (!state.list) return pass();
  if (state.title !== want.title) return fail('the type list has no heading');
  for (const row of state.rows) {
    if (row.name !== want.names[row.slug])
      return fail(`the type ${row.slug} is not named from the catalogue`);
    if (row.fact !== `type-${row.slug}`)
      return fail(`the type ${row.slug} has no count chip of its own`);
  }
  return pass();
}

// Round 5g, finding 23 (DES-61): the legend's swatches match the lit cells,
// each class's fill at its opacity over the land, within two levels a
// channel.
export function judgeSwatches(swatches, cells) {
  if (swatches.length !== cells.length)
    return fail(
      `the legend has ${swatches.length} swatches for ${cells.length} classes`,
    );
  for (const [index, swatch] of swatches.entries()) {
    const cell = cells[index];
    if (swatch.some((channel, at) => Math.abs(channel - cell[at]) > 2))
      return fail(
        `swatch ${index + 1} is rgb(${swatch.join(', ')}), the cells rgb(${cell.join(', ')})`,
      );
  }
  return pass();
}
