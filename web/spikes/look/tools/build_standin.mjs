// Writes the committed invented establishment stand-in and prints its
// SHA-256. Every name is made up. The CSV and the README beside it stay;
// this script is how they were produced.
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { cellArea, cellToLatLng, latLngToCell } from 'h3-js';
import { cellsFromCounts, countsByCell, parseRegister } from '../register.mjs';
import { FRAME, RESOLUTION, classOf } from '../release-build.mjs';

const OUT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../register/establishments.csv',
);

const FIRST = [
  ['Palm', 'نخيل'],
  ['Harbour', 'ميناء'],
  ['Lane', 'زقاق'],
  ['Quiet', 'هدوء'],
  ['Cedar', 'أرز'],
  ['Pearl', 'لؤلؤ'],
  ['Stone', 'حجر'],
  ['River', 'نهر'],
  ['Garden', 'بستان'],
  ['Morning', 'صباح'],
  ['Linen', 'كتان'],
  ['Wheat', 'قمح'],
  ['Marble', 'رخام'],
  ['Breeze', 'نسيم'],
  ['Orchard', 'حديقة'],
  ['Fountain', 'نافورة'],
  ['Lantern', 'فانوس'],
  ['Basket', 'سلة'],
  ['Copper', 'نحاس'],
  ['Silver', 'فضة'],
];
const SECOND = [
  ['Oven', 'فرن'],
  ['Thread', 'خيط'],
  ['Ledger', 'دفتر'],
  ['Loaf', 'رغيف'],
  ['Needle', 'إبرة'],
  ['Shelf', 'رف'],
  ['Mill', 'طاحونة'],
  ['Well', 'بئر'],
  ['Loom', 'نول'],
  ['Gate', 'بوابة'],
  ['Yard', 'ساحة'],
  ['Porch', 'رواق'],
  ['Press', 'مكبس'],
  ['Kiln', 'أتون'],
  ['Vat', 'حوض'],
  ['Crate', 'صندوق'],
  ['Spool', 'بكرة'],
  ['Bench', 'دكة'],
  ['Counter', 'منضدة'],
  ['Hearth', 'موقد'],
];
const THIRD = [
  'north',
  'south',
  'east',
  'west',
  'upper',
  'lower',
  'inner',
  'outer',
  'near',
  'wide',
  'small',
  'tall',
];
const TYPES = ['bakery', 'grocery', 'tailor', 'pharmacy', 'workshop'];
const HEADER = [
  'row_key',
  'name_ar',
  'name_en',
  'establishment_type',
  'establishment_subtype',
  'legal_form',
  'business_type',
  'business_category',
  'classification',
  'registration_status',
  'registration_issue_date',
  'registration_expiry_date',
  'licence_status',
  'licence_issue_date',
  'licence_expiry_date',
  'branches',
  'municipality',
  'zone',
  'employees',
  'lon',
  'lat',
];

// A fixed generator (mulberry32), so the stand-in is the same on every run.
function generator(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
// The seed is the date the stand-in was made, written with separators so
// that no bare run of eight digits stands in a source file (rule 9).
const random = generator(2026_11_13);

// Invented centres of activity on land in Greater Doha and Lusail: a centre,
// a spread in metres and a number of rows. The spread is cut at one and a
// half times its value, and each centre keeps its points west of a line
// drawn by hand inland of the coast (`east`), so that no point sits in the
// sea. These are this generator's own choices, not read from any map file.
const anchors = [
  {
    lon: 51.5312,
    lat: 25.3226,
    spread: 120,
    count: 130,
    east: 51.535,
    type: 'bakery',
    snap: true,
  },
  {
    lon: 51.5285,
    lat: 25.3238,
    spread: 420,
    count: 100,
    east: 51.5335,
    type: 'tailor',
  },
  {
    lon: 51.5205,
    lat: 25.3285,
    spread: 520,
    count: 60,
    east: 51.5315,
    type: 'tailor',
  },
  {
    lon: 51.5245,
    lat: 25.2845,
    spread: 260,
    count: 80,
    east: 51.5335,
    type: 'grocery',
  },
  {
    lon: 51.5005,
    lat: 25.2835,
    spread: 560,
    count: 90,
    east: 51.515,
    type: 'pharmacy',
  },
  {
    lon: 51.4955,
    lat: 25.3045,
    spread: 560,
    count: 50,
    east: 51.51,
    type: 'workshop',
  },
  {
    lon: 51.4485,
    lat: 25.3125,
    spread: 760,
    count: 45,
    east: 51.47,
    type: 'grocery',
  },
  {
    lon: 51.4575,
    lat: 25.2555,
    spread: 760,
    count: 45,
    east: 51.48,
    type: 'tailor',
  },
  {
    lon: 51.5545,
    lat: 25.2645,
    spread: 600,
    count: 50,
    east: 51.566,
    type: 'workshop',
  },
  {
    lon: 51.5335,
    lat: 25.3715,
    spread: 230,
    count: 70,
    east: 51.5375,
    type: 'bakery',
  },
  {
    lon: 51.5325,
    lat: 25.3745,
    spread: 520,
    count: 40,
    east: 51.5375,
    type: 'grocery',
  },
  {
    lon: 51.5145,
    lat: 25.4185,
    spread: 620,
    count: 40,
    east: 51.53,
    type: 'pharmacy',
  },
];

function gaussian() {
  const u = Math.max(random(), 1e-12);
  const v = random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

const METRE = 1 / 111320;
const placed = [];
for (const listed of anchors) {
  // A core centre sits on the middle of its release unit, so that the
  // densest unit is one unit rather than two halves.
  const [snapLat, snapLon] = listed.snap
    ? cellToLatLng(latLngToCell(listed.lat, listed.lon, RESOLUTION))
    : [listed.lat, listed.lon];
  const anchor = { ...listed, lon: snapLon, lat: snapLat };
  let made = 0;
  for (
    let tries = 0;
    made < anchor.count && tries < anchor.count * 40;
    tries += 1
  ) {
    const dx = gaussian();
    const dy = gaussian();
    if (Math.hypot(dx, dy) > 1.5) continue;
    const lat = anchor.lat + dy * anchor.spread * METRE;
    const lon =
      anchor.lon +
      (dx * anchor.spread * METRE) / Math.cos((anchor.lat * Math.PI) / 180);
    if (lon > anchor.east) continue;
    const type =
      random() < 0.55
        ? anchor.type
        : TYPES[Math.floor(random() * TYPES.length)];
    placed.push({ type, point: [lon, lat] });
    made += 1;
  }
  if (made < anchor.count) throw new Error(`centre held ${made}`);
}

// Invented employee counts: most shops are small, a few are larger.
function employees() {
  const draw = random();
  if (draw < 0.6) return 2 + Math.floor(random() * 9);
  if (draw < 0.9) return 11 + Math.floor(random() * 30);
  return 41 + Math.floor(random() * 120);
}

function fixed6(value) {
  const scaled = Math.round(value * 1000000);
  const negative = scaled < 0;
  const abs = Math.abs(scaled);
  const whole = Math.trunc(abs / 1000000);
  const fraction = String(abs % 1000000).padStart(6, '0');
  return `${negative ? '-' : ''}${whole}.${fraction}`;
}

const seen = new Set();
const lines = [HEADER.join(',')];
placed.forEach((item, index) => {
  const first = FIRST[index % FIRST.length];
  const second = SECOND[Math.floor(index / FIRST.length) % SECOND.length];
  let third = 0;
  let key = '';
  while (third < THIRD.length) {
    key =
      `row-${first[0]}-${second[0]}-${THIRD[(index + third) % THIRD.length]}`.toLowerCase();
    if (!seen.has(key)) break;
    third += 1;
  }
  if (seen.has(key)) throw new Error('names ran out');
  seen.add(key);
  const month = String((index % 12) + 1).padStart(2, '0');
  const day = String((index % 27) + 1).padStart(2, '0');
  const year = 2016 + (index % 8);
  const issued = `${year}-${month}-${day}`;
  const expires = `${year + 2}-${month}-${day}`;
  const [lon, lat] = item.point;
  const municipality = lat >= 25.39 ? 'Lusail' : 'Doha';
  const fields = {
    row_key: key,
    name_ar: `${first[1]} ${second[1]}`,
    name_en: `${first[0]} ${second[0]}`,
    establishment_type: 'shop',
    establishment_subtype: '',
    legal_form: index % 3 === 0 ? 'sole' : 'limited',
    business_type: item.type,
    business_category: '',
    classification: '',
    registration_status: 'active',
    registration_issue_date: issued,
    registration_expiry_date: expires,
    licence_status: 'active',
    licence_issue_date: issued,
    licence_expiry_date: expires,
    branches: '',
    municipality,
    zone: '',
    employees: String(employees()),
    lon: fixed6(lon),
    lat: fixed6(lat),
  };
  lines.push(HEADER.map((name) => fields[name]).join(','));
});

const text = `${lines.join('\n')}\n`;
fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, text);
const rows = parseRegister(text);
const cells = cellsFromCounts(
  countsByCell(rows, { resolution: RESOLUTION, frame: FRAME }),
  { area: cellArea, classOf },
);
const steps = new Set(cells.map((cell) => cell[2]));
if (!steps.has(3) || !steps.has(4) || !steps.has(5)) {
  throw new Error(`classes ${[...steps].join(',')}`);
}
const hash = createHash('sha256').update(text).digest('hex');
console.log(`rows ${rows.length}`);
console.log(`cells ${cells.length}`);
console.log(`sha256 ${hash}`);
