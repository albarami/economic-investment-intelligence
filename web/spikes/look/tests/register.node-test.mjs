import assert from 'node:assert/strict';
import { test } from 'node:test';
import { latLngToCell } from 'h3-js';
import { classOf } from '../release-build.mjs';
import {
  FRAME,
  RESOLUTION,
  cellsFromCounts,
  countsByCell,
  countsByType,
  parseRegister,
} from '../register.mjs';

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
  'lon',
  'lat',
].join(',');

function line(overrides = {}) {
  const row = {
    row_key: 'row-palm-oven',
    name_ar: 'فرن النخيل',
    name_en: 'Palm Oven',
    establishment_type: 'shop',
    establishment_subtype: '',
    legal_form: 'sole',
    business_type: 'bakery',
    business_category: '',
    classification: '',
    registration_status: 'active',
    registration_issue_date: '',
    registration_expiry_date: '',
    licence_status: '',
    licence_issue_date: '',
    licence_expiry_date: '',
    branches: '',
    municipality: 'Doha',
    zone: '',
    lon: '51.53',
    lat: '25.32',
    ...overrides,
  };
  return HEADER.split(',')
    .map((key) => row[key])
    .join(',');
}

test('a register row keeps only the published fields', () => {
  const rows = parseRegister(`${HEADER}\n${line({ branches: '2' })}`);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].name_en, 'Palm Oven');
  assert.equal(rows[0].business_type, 'bakery');
  assert.equal(rows[0].branches, 2);
  assert.equal(rows[0].lon, 51.53);
  assert.equal(Object.hasOwn(rows[0], 'score'), false);
});

test('a column that is not a published field is refused', () => {
  assert.throws(
    () => parseRegister(`${HEADER},score\n${line()},9`),
    /not a published field/,
  );
});

test('a row missing a required field is refused without its values', () => {
  const broken = line({ name_ar: '' });
  assert.throws(() => parseRegister(`${HEADER}\n${broken}`), /name_ar/);
});

test('counts are establishments per H3 cell inside the Greater Doha frame', () => {
  const inside = latLngToCell(25.32, 51.53, RESOLUTION);
  const text = [
    HEADER,
    line({ row_key: 'row-one', lon: '51.53', lat: '25.32' }),
    line({
      row_key: 'row-two',
      lon: '51.53',
      lat: '25.32',
      business_type: 'grocery',
    }),
    line({ row_key: 'row-far', lon: '50.8', lat: '25.0', name_en: 'Far Gate' }),
  ].join('\n');
  const rows = parseRegister(text);
  const counts = countsByCell(rows, { resolution: RESOLUTION, frame: FRAME });
  assert.equal(counts.get(inside), 2);
  assert.equal(counts.size, 1);
  assert.deepEqual(
    countsByType(rows),
    new Map([
      ['bakery', 2],
      ['grocery', 1],
    ]),
  );
});

test('density is the count divided by the cell area, classed on the fixed breaks', () => {
  const cell = latLngToCell(25.32, 51.53, RESOLUTION);
  const cells = cellsFromCounts(new Map([[cell, 10]]), {
    area: () => 0.1,
    classOf,
  });
  assert.deepEqual(cells, [[cell, 100, classOf(100)]]);
  assert.deepEqual(
    cellsFromCounts(new Map([[cell, 0]]), { area: () => 0.1, classOf }),
    [],
  );
});

// The owner's decision of 2026-11-13: the company card shows the number of
// employees as one more field. No wage or other labour field is accepted.
test('the employee count is kept as a whole number, and a wage column is refused', () => {
  const header = `${HEADER},employees`;
  const rows = parseRegister(`${header}\n${line()},12`);
  assert.equal(rows[0].employees, 12);
  const blank = parseRegister(`${header}\n${line()},`);
  assert.equal(blank[0].employees, null);
  assert.throws(
    () => parseRegister(`${header}\n${line()},twelve`),
    /employees/,
  );
  assert.throws(
    () => parseRegister(`${header},wage\n${line()},12,9000`),
    /wage is not a published field/,
  );
});

test('a release establishment carries its employee count and nothing on wages', async () => {
  const { validateRelease } = await import('../release-shape.mjs');
  const { assemble } = await import('../release-build.mjs');
  const rows = parseRegister(`${HEADER},employees\n${line()},7`);
  const release = assemble(
    [],
    { present: false, missing: 'x' },
    {
      establishments: rows,
      period: '2026-11-13',
    },
  );
  assert.equal(release.establishments[0].employees, 7);
  const planted = JSON.parse(JSON.stringify(release));
  planted.establishments[0].wage_bill = 1;
  assert.throws(() => validateRelease(planted), /wage_bill/);
});

// Round 5g, finding 15 (rules 7 and 23): the card's counts are released facts
// with a chain to the register file, never bare identifiers.
test('the employees and branches of each establishment are released facts with a chain', async () => {
  const { assemble } = await import('../release-build.mjs');
  const rows = parseRegister(`${HEADER},employees\n${line()},7`);
  const release = assemble(
    [],
    { present: false, missing: 'x' },
    { establishments: rows, period: '2026-11-13' },
  );
  const byId = new Map(release.facts.map((fact) => [fact.id, fact]));
  const employees = byId.get('row-palm-oven-employees');
  assert.ok(employees, 'no employees fact');
  assert.equal(employees.value, 7);
  assert.equal(employees.unit, 'count');
  assert.equal(employees.unit_key, 'unit.employees');
  assert.equal(employees.geography_key, 'fact.establishment');
  assert.equal(employees.chain.table, 'chain.tableLabour');
  assert.equal(employees.chain.method, 'chain.methodEmployees');
  assert.equal(employees.chain.method_version, '1.0.0');
  assert.equal(employees.origin, 'synthetic');
  const branches = byId.get('row-palm-oven-branches');
  if (rows[0].branches === null) assert.equal(branches, undefined);
  else {
    assert.equal(branches.value, rows[0].branches);
    assert.equal(branches.chain.method, 'chain.methodBranches');
  }
});
