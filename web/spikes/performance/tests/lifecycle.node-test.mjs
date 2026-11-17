import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { test } from 'node:test';
import { waitForResponse } from './response-deadline.mjs';
import { temporaryFolder } from './temporary-folder.mjs';

test(
  'an externally killed owner leaves no temporary folder',
  { timeout: 5000 },
  async () => {
    const parent = temporaryFolder('invented-lifecycle-');
    const source = `
    import { temporaryFolder } from ${JSON.stringify(new URL('./temporary-folder.mjs', import.meta.url).href)};
    const folder = temporaryFolder('invented-child-');
    process.stdout.write(folder + '\\n');
    setInterval(() => {}, 1000);
  `;
    const child = spawn(
      process.execPath,
      ['--input-type=module', '-e', source],
      {
        detached: true,
        env: { ...process.env, TMPDIR: parent },
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    );
    try {
      let text = '';
      for await (const chunk of child.stdout) {
        text += chunk;
        if (text.includes('\n')) break;
      }
      const folder = text.trim();
      assert.ok(folder.startsWith(parent));
      assert.ok(fs.existsSync(folder));
      const ended = once(child, 'exit');
      process.kill(-child.pid, 'SIGKILL');
      await ended;
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          clearInterval(poll);
          reject(new Error('temporary folder survived owner termination'));
        }, 2000);
        const poll = setInterval(() => {
          if (!fs.existsSync(folder)) {
            clearInterval(poll);
            clearTimeout(timer);
            resolve();
          }
        }, 10);
      });
      assert.deepEqual(fs.readdirSync(parent), []);
    } finally {
      child.kill('SIGKILL');
      fs.rmSync(parent, { recursive: true, force: true });
    }
  },
);

test('an empty send rejects and cancels its waiting client', async () => {
  let cancelled = 0;
  await assert.rejects(
    waitForResponse(() => () => cancelled++, 25),
    /response-timeout/,
  );
  assert.equal(cancelled, 1);
});

test('a completed response clears its deadline and preserves its value', async () => {
  assert.equal(
    await waitForResponse((done) => done('invented'), 25),
    'invented',
  );
  await assert.rejects(
    waitForResponse((_done, fail) => fail(new Error('invented failure')), 25),
    /invented failure/,
  );
});

test('the trace HTTP client bounds a response that never ends', async () => {
  const source = fs.readFileSync(
    new URL('./trace.node-test.mjs', import.meta.url),
    'utf8',
  );
  const body = source.slice(
    source.indexOf('function ask('),
    source.indexOf("test('production mode"),
  );
  const ask = new Function('http', 'waitForResponse', body + '\nreturn ask;')(
    http,
    (start) => waitForResponse(start, 25),
  );
  const server = http.createServer((_request, response) => {
    response.writeHead(200);
    response.write('invented incomplete body');
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    await assert.rejects(
      ask(`http://127.0.0.1:${server.address().port}`, {
        path: '/',
        method: 'GET',
      }),
      /response-timeout/,
    );
  } finally {
    server.closeAllConnections();
    server.close();
  }
});
