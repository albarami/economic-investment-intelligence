/** W2: only the recorded product fixtures supply page assignment values. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { format } from 'prettier';
const FIXTURE = new URL(
  '../../../product/tests/fixtures/areas_spike/assignment/',
  import.meta.url,
);
export async function buildRoadData(fixture = FIXTURE) {
  const recorded = JSON.parse(
    fs.readFileSync(new URL('hourly_rows.json', fixture), 'utf8'),
  );
  const roads = JSON.parse(
    fs.readFileSync(new URL('hourly_roads.json', fixture), 'utf8'),
  );
  for (const [index, row] of recorded.rows.entries()) {
    if (row.day_type !== 'weekday' || row.summer !== false) {
      throw new Error(`row ${index}: expected weekday and summer false`);
    }
  }
  const hours = [...new Set(recorded.rows.map((row) => row.hour))].sort(
    (a, b) => a - b,
  );
  return format(
    JSON.stringify({
      header: recorded.header,
      roads,
      hours,
      rows: recorded.rows,
    }),
    { parser: 'json' },
  );
}
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  fs.writeFileSync(
    new URL('./road-data.json', import.meta.url),
    await buildRoadData(),
  );
}
