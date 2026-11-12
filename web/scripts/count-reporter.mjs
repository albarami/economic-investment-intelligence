// Counting reporter for the test runner (scripts/run_tests.py).
// It writes one JSON line for each test that ran, for each skipped suite and
// for each file that registers no test (other suites are not counted), and
// then the line {"end":true}. A file without the end line is incomplete.
import { resolve } from 'node:path';

const NO_TEST_REASON = 'the file registers no test';
const reasonOf = (value) => (typeof value === 'string' ? value : '');
const line = (record) => `${JSON.stringify(record)}\n`;

export default async function* countReporter(source) {
  for await (const event of source) {
    if (event.type !== 'test:pass' && event.type !== 'test:fail') continue;
    const { data } = event;
    if (data.details?.type === 'suite') {
      if (data.skip) {
        yield line({ s: 'skip', n: data.name, r: reasonOf(data.skip) });
      }
      continue;
    }
    if (data.details?.error?.failureType === 'subtestsFailed') continue;
    if (data.todo) {
      yield line({ s: 'skip', n: data.name, r: reasonOf(data.todo) });
    } else if (data.skip) {
      yield line({ s: 'skip', n: data.name, r: reasonOf(data.skip) });
    } else if (event.type === 'test:fail') {
      yield line({ s: 'fail', n: data.name, r: '' });
    } else if (data.nesting === 0 && resolve(data.name) === data.file) {
      yield line({ s: 'skip', n: data.name, r: NO_TEST_REASON });
    } else {
      yield line({ s: 'pass', n: data.name, r: '' });
    }
  }
  yield line({ end: true });
}
