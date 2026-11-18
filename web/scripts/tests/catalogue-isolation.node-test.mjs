import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const web = fileURLToPath(new URL('../../', import.meta.url));
test('catalogue import graph refuses direct and transitive spike imports', async () => {
  const { checkGraph } = await import('../../spikes/catalogue/guards.mjs');
  const read = (name) => fs.readFileSync(path.join(web, name), 'utf8');
  function scripts(folder) {
    return fs
      .readdirSync(path.join(web, folder), { withFileTypes: true })
      .flatMap((entry) => {
        const name = `${folder}/${entry.name}`;
        return entry.isDirectory()
          ? scripts(name)
          : /\.[cm]?[jt]sx?$/.test(name)
            ? [name]
            : [];
      });
  }
  assert.deepEqual(checkGraph(scripts('src'), read), []);
  const sources = {
    'src/main.tsx': "import './middle.ts';",
    'src/middle.ts': "export * from '../spikes/catalogue/native-dispatch.ts';",
  };
  assert.ok(checkGraph(['src/main.tsx'], (name) => sources[name]).length > 0);
  assert.deepEqual(
    checkGraph(['src/main.tsx'], () => 'export const clean = true;'),
    [],
  );
});

test('catalogue import graph follows extensionless edges and refuses dynamic paths', async () => {
  const { checkGraph } = await import('../../spikes/catalogue/guards.mjs');
  const sources = {
    'src/main.tsx': "import './middle';",
    'src/middle.ts': "import '../spikes/catalogue/native-dispatch.ts';",
  };
  assert.ok(checkGraph(['src/main.tsx'], (name) => sources[name]).length > 0);
  assert.ok(
    checkGraph(['src/main.tsx'], () => 'import(destination);').length > 0,
  );
});
