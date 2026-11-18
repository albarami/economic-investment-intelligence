import { createHash } from 'node:crypto';
import { judge } from './trace.mjs';
const closed = (object, keys) =>
  object !== null &&
  typeof object === 'object' &&
  !Array.isArray(object) &&
  Object.keys(object).sort().join() === [...keys].sort().join();
const fail = (failure) => ({ ok: false, failure });
export function checkMatrix(records, identity) {
  if (!Array.isArray(records)) return fail('missing-matrix');
  const expected = new Set();
  for (const library of ['echarts', 'plot', 'visx'])
    for (const chart of ['hourly', 'comparison', 'range'])
      for (const language of ['en', 'ar'])
        for (const device of ['laptop', 'phone'])
          for (const run of [1, 2, 3])
            expected.add([library, chart, language, device, run].join(':'));
  for (const record of records) {
    if (
      !closed(record, [
        'library',
        'chart',
        'language',
        'device',
        'run',
        'raw',
        'capture',
      ])
    )
      return fail('record-shape');
    const key = [
      record.library,
      record.chart,
      record.language,
      record.device,
      record.run,
    ].join(':');
    if (!expected.delete(key)) return fail('unknown-or-duplicate-cell');
    if (typeof record.raw !== 'string') return fail('raw-shape');
    let trace;
    try {
      trace = JSON.parse(record.raw);
    } catch {
      return fail('malformed-json');
    }
    const capture = record.capture;
    if (
      !closed(capture, [
        'sha256',
        'ownerAttested',
        'device',
        'browser',
        'viewport',
      ])
    )
      return fail('capture-shape');
    const digest = createHash('sha256').update(record.raw).digest('hex');
    if (capture.sha256 !== digest) return fail('capture-digest');
    if (
      capture.ownerAttested !== true ||
      capture.device !== record.device ||
      trace?.device !== record.device ||
      capture.browser !== trace?.browser ||
      JSON.stringify(capture.viewport) !== JSON.stringify(trace?.viewport)
    )
      return fail('capture-binding');
    const verdict = judge(trace, identity);
    if (!verdict.ok) return verdict;
  }
  if (expected.size) return fail('incomplete-matrix');
  return { ok: true };
}
