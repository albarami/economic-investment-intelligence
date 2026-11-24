/**
 * Place scan for the map credit (TST-263's place rule, S3-T16 box 8).
 * A credit may appear only inside the collapsed map credits: a closed
 * details element inside the attribution place. Rendered text is matched
 * across descendant text nodes after HTML entities are decoded, and the
 * built check renders the production Stage rather than a source pattern.
 */
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { pageCreditPlace, renderBuiltStage } from './credit-place-dom.mjs';

export { pageCreditPlace, placeCredit } from './credit-place-dom.mjs';

const SATELLITE_PLACE = 'map-satellite-credit';
const PLACE_WINDOW = 2000;
const FIXTURE_CONFIG = 'tests/credit-place/credit-place-stage.build.mjs';
const BUILT_SCRIPT = 'credit-place-stage.js';

/**
 * @param {string} bundle
 * @param {string} credit
 * @returns {{ inside: number, outside: number, place: boolean }}
 */
export function bundleCreditPlace(bundle, credit) {
  const spans = collapsedSpans(bundle);
  const hits = { inside: 0, outside: 0, place: spans.length > 0 };
  if (credit.length === 0) return hits;
  let from = 0;
  while (from < bundle.length) {
    const at = bundle.indexOf(credit, from);
    if (at < 0) break;
    const allowed = spans.some(([start, end]) => at >= start && at < end);
    if (allowed) hits.inside += 1;
    else hits.outside += 1;
    from = at + credit.length;
  }
  return hits;
}

/**
 * @param {string} page
 * @param {string} bundle
 * @param {string} credit
 * @returns {'credit-place-ok' | 'credit-place-missing' | 'credit-outside-collapsed'}
 */
export function judgeCreditPlace(page, bundle, credit) {
  const rendered = pageCreditPlace(page, credit);
  const built = bundleCreditPlace(bundle, credit);
  if (rendered.outside > 0 || built.outside > 0)
    return 'credit-outside-collapsed';
  if (!built.place || built.inside === 0 || rendered.inside === 0)
    return 'credit-place-missing';
  return 'credit-place-ok';
}

/**
 * Build the Stage fixture and judge the satellite credit in its rendered DOM.
 * A hand-written page is not the deciding document.
 * @param {{ webRoot: string, outDir: string, credit: string }} options
 * @returns {Promise<'credit-place-ok' | 'credit-place-missing' | 'credit-outside-collapsed'>}
 */
export async function judgeBuiltStage(options) {
  const vite = path.join(options.webRoot, 'node_modules/vite/bin/vite.js');
  const built = spawnSync(
    process.execPath,
    [
      vite,
      'build',
      '--config',
      path.join(options.webRoot, FIXTURE_CONFIG),
      '--outDir',
      options.outDir,
      '--emptyOutDir',
      '--logLevel',
      'error',
    ],
    {
      cwd: options.webRoot,
      encoding: 'utf8',
      env: {
        PATH: process.env.PATH,
        HOME: process.env.HOME,
        EII_CREDIT_PLACE_OUT: options.outDir,
      },
    },
  );
  if (built.status !== 0) {
    throw new Error(
      `credit-place-build-failed\n${built.stdout}\n${built.stderr}`,
    );
  }
  const scriptPath = path.join(options.outDir, BUILT_SCRIPT);
  if (!fs.existsSync(scriptPath)) {
    const listed = fs.readdirSync(options.outDir).join(',');
    throw new Error(`credit-place-script-missing:${listed}`);
  }
  return renderBuiltStage(fs.readFileSync(scriptPath, 'utf8'), options.credit);
}

/**
 * @param {string} source
 * @returns {Array<[number, number]>}
 */
function collapsedSpans(source) {
  /** @type {Array<[number, number]>} */
  const spans = [];
  let from = 0;
  while (from < source.length) {
    const at = source.indexOf(SATELLITE_PLACE, from);
    if (at < 0) break;
    const start = source.lastIndexOf('details', at);
    if (start >= 0 && at - start <= PLACE_WINDOW) {
      spans.push([start, at + SATELLITE_PLACE.length]);
    }
    from = at + SATELLITE_PLACE.length;
  }
  return spans;
}

/**
 * @param {string[]} argv
 */
export function scanArguments(argv) {
  /** @type {{ page?: string, bundle?: string, credit?: string }} */
  const values = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    const next = argv[index + 1];
    if (token === '--page' && next) values.page = next;
    if (token === '--bundle' && next) values.bundle = next;
    if (token === '--credit' && next) values.credit = next;
  }
  if (!values.page || !values.bundle || !values.credit) return null;
  return {
    page: fs.readFileSync(values.page, 'utf8'),
    bundle: fs.readFileSync(values.bundle, 'utf8'),
    credit: values.credit,
  };
}

function invokedDirectly() {
  const entry = process.argv[1];
  if (!entry) return false;
  return import.meta.url === pathToFileURL(path.resolve(entry)).href;
}

if (invokedDirectly()) {
  const read = scanArguments(process.argv.slice(2));
  if (!read) {
    process.stdout.write('credit-place-missing\n');
    process.exit(1);
  }
  const verdict = judgeCreditPlace(read.page, read.bundle, read.credit);
  process.stdout.write(`${verdict}\n`);
  process.exit(verdict === 'credit-place-ok' ? 0 : 1);
}
