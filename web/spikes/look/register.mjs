// The establishment register the look page reads. The server uses
// EII_REGISTER_FILE when that setting is present, and otherwise the
// committed stand-in of the same columns. A row carries only the published
// fields. Nothing here prints a row.
import fs from 'node:fs';
import path from 'node:path';
import { latLngToCell } from 'h3-js';
import {
  ESTABLISHMENT_OPTIONAL,
  ESTABLISHMENT_REQUIRED,
} from './release-shape.mjs';

// Greater Doha and Lusail, west, south, east, north. The same frame as the
// lit layer in release-build.mjs.
export const FRAME = [51.33, 25.18, 51.62, 25.48];
export const RESOLUTION = 9;
export const STAND_IN = [
  'web',
  'spikes',
  'look',
  'register',
  'establishments.csv',
];

const REQUIRED = ESTABLISHMENT_REQUIRED;
const OPTIONAL = ESTABLISHMENT_OPTIONAL;
const COLUMNS = [...REQUIRED, ...OPTIONAL];
const NUMBER_FIELDS = new Set(['lon', 'lat', 'branches', 'employees']);
const WHOLE_FIELDS = new Set(['branches', 'employees']);

function refuse(detail) {
  throw new Error(`register refused: ${detail}`);
}

// Round 5g, finding 22: the date of the register count. The stand-in's is
// the "Date written" of register/README.md; a register file named by
// EII_REGISTER_FILE needs EII_REGISTER_DATE, the collection date its own
// README states, and is refused without it. There is no default.
export const STAND_IN_DATE = '2026-11-13';

export function registerPeriod(located, env = process.env) {
  if (located.standIn) return STAND_IN_DATE;
  const date = env.EII_REGISTER_DATE;
  if (typeof date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(date))
    refuse('EII_REGISTER_DATE is absent or not YYYY-MM-DD');
  const [year, month, day] = date.split('-').map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day)
    refuse('EII_REGISTER_DATE is not a calendar date');
  return date;
}

export function locateRegister(repositoryRoot, env = process.env) {
  const set = env.EII_REGISTER_FILE;
  if (typeof set === 'string' && set !== '') {
    if (!fs.existsSync(set))
      return { ok: false, detail: 'register file is absent' };
    return { ok: true, file: set, standIn: false };
  }
  const file = path.join(repositoryRoot, ...STAND_IN);
  if (!fs.existsSync(file)) return { ok: false, detail: 'stand-in absent' };
  return { ok: true, file, standIn: true };
}

function cells(line) {
  return line.split(',');
}

export function parseRegister(text) {
  const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/);
  const header = cells(lines[0] ?? '');
  if (header.length === 0 || header[0] === '') refuse('no header');
  for (const name of header) {
    if (!COLUMNS.includes(name)) refuse(`${name} is not a published field`);
  }
  for (const name of REQUIRED) {
    if (!header.includes(name)) refuse(`missing ${name}`);
  }
  const rows = [];
  const seen = new Set();
  for (let index = 1; index < lines.length; index += 1) {
    const raw = lines[index] ?? '';
    if (raw.trim() === '') continue;
    const values = cells(raw);
    if (values.length !== header.length)
      refuse(`row ${index} has the wrong width`);
    const row = {};
    for (const name of COLUMNS) row[name] = '';
    for (const name of WHOLE_FIELDS) row[name] = null;
    for (let column = 0; column < header.length; column += 1) {
      const name = header[column];
      const value = (values[column] ?? '').trim();
      if (NUMBER_FIELDS.has(name)) {
        if (value === '') {
          if (WHOLE_FIELDS.has(name)) row[name] = null;
          else refuse(`row ${index} missing ${name}`);
          continue;
        }
        const number = Number(value);
        if (!Number.isFinite(number)) refuse(`row ${index} ${name}`);
        if (WHOLE_FIELDS.has(name) && !Number.isInteger(number))
          refuse(`row ${index} ${name}`);
        row[name] = number;
      } else {
        row[name] = value;
      }
    }
    for (const name of REQUIRED) {
      if (name === 'lon' || name === 'lat') continue;
      if (typeof row[name] !== 'string' || row[name].trim() === '') {
        refuse(`row ${index} missing ${name}`);
      }
    }
    if (row.lon < -180 || row.lon > 180 || row.lat < -90 || row.lat > 90) {
      refuse(`row ${index} coordinates`);
    }
    if (seen.has(row.row_key)) refuse(`row ${index} repeats a key`);
    seen.add(row.row_key);
    rows.push(row);
  }
  return rows;
}

function inside(lon, lat, frame) {
  return (
    lon >= frame[0] && lon <= frame[2] && lat >= frame[1] && lat <= frame[3]
  );
}

// The count of establishments per H3 cell. Points outside the frame are
// left out of the lit layer; they are not given a cell.
export function countsByCell(rows, options) {
  const resolution = options.resolution;
  const frame = options.frame;
  const counts = new Map();
  for (const row of rows) {
    if (!inside(row.lon, row.lat, frame)) continue;
    const cell = latLngToCell(row.lat, row.lon, resolution);
    counts.set(cell, (counts.get(cell) ?? 0) + 1);
  }
  return counts;
}

export function countsByType(rows) {
  const counts = new Map();
  for (const row of rows) {
    const type = row.business_type;
    counts.set(type, (counts.get(type) ?? 0) + 1);
  }
  return counts;
}

// Firms per square kilometre: the cell's count divided by its area, rounded
// to an integer. A zero result stays dark. Order is the cell id, so the
// release is deterministic.
export function cellsFromCounts(counts, options) {
  const cellsOut = [];
  for (const [cell, count] of counts) {
    if (!(count > 0)) continue;
    const size = options.area(cell, 'km2');
    if (!(size > 0)) continue;
    const value = Math.round(count / size);
    if (value <= 0) continue;
    cellsOut.push([cell, value, options.classOf(value)]);
  }
  cellsOut.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  return cellsOut;
}
