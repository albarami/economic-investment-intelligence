import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { browserHome } from './browser-home.mjs';
import { installsSystemLibraries } from './system-libraries.mjs';

const web = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
process.env.PLAYWRIGHT_BROWSERS_PATH = browserHome(import.meta.url);
const cli = path.join(web, 'node_modules', '@playwright', 'test', 'cli.js');

function run(args) {
  const result = spawnSync(process.execPath, [cli, ...args], {
    cwd: web,
    env: process.env,
    stdio: 'inherit',
  });
  return result.status === null ? 1 : result.status;
}

const downloaded = run(['install', '--only-shell', 'chromium']);
if (downloaded !== 0) process.exit(downloaded);
// System libraries are installed with administrator rights, so only the hosted
// runner does it. On any other machine this command changes nothing outside
// the repository; a missing library then fails the browser tests by name.
if (!installsSystemLibraries(process.env.CI)) {
  console.log(
    'system libraries are installed in the CI environment only; none was installed here',
  );
  process.exit(0);
}
process.exit(run(['install-deps', 'chromium']));
