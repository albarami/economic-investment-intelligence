/** Executed by test_mounted_browser.py against create_app, never Vite. */
import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const origin = process.env.EII_TEST_ORIGIN;
assert.match(origin ?? '', /^http:\/\/127\.0\.0\.1:\d+$/);
const browser = await chromium.launch({ headless: true });
try {
  for (const lang of ['en', 'ar']) {
    for (const theme of ['dark', 'light']) {
      const context = await browser.newContext({ serviceWorkers: 'block' });
      const forbidden = [];
      const chains = new Map();
      const emitted = new Set();
      const page = await context.newPage();
      context.on('request', (request) => {
        const url = new URL(request.url());
        if (!['blob:', 'data:'].includes(url.protocol) && url.origin !== origin)
          forbidden.push(request.url());
      });
      // Deny egress; same-origin API responses are never intercepted or supplied.
      await context.route('**/*', (route) =>
        new URL(route.request().url()).origin === origin
          ? route.continue()
          : route.abort(),
      );
      page.on('response', async (response) => {
        const path = new URL(response.url()).pathname;
        if (path.startsWith('/api/layers/') && response.ok()) {
          for (const fact of (await response.json()).facts)
            emitted.add(fact.fact_id);
        }
        if (path.startsWith('/api/facts/') && response.ok()) {
          const chain = await response.json();
          chains.set(chain.fact_id, chain);
        }
      });
      await page.goto(origin + '/?lang=' + lang + '&theme=' + theme);
      await page.locator('[data-action="guided-story"]').click();
      await page.locator('.layer-inspector > summary').click();
      const chip = page.locator('[data-fact-chip="compact"]').first();
      await chip.waitFor({ state: 'visible' });
      assert.equal(
        await page.locator('.shell').getAttribute('dir'),
        lang === 'ar' ? 'rtl' : 'ltr',
      );
      assert.equal(
        await page.locator('.shell').getAttribute('data-theme'),
        theme,
      );
      assert.equal(await page.locator('.stage').getAttribute('dir'), 'ltr');
      assert.ok(emitted.size > 0);
      assert.deepEqual([...chains.keys()].sort(), [...emitted].sort());
      await chip.focus();
      await page.keyboard.press('Enter');
      const drawer = page.getByRole('dialog');
      await drawer.waitFor({ state: 'visible' });
      const factId = await drawer.getAttribute('data-fact-id');
      assert.ok(emitted.has(factId));
      const chain = chains.get(factId);
      assert.ok(chain);
      assert.ok((await drawer.textContent()).includes(chain.lineage.method));
      assert.ok(
        (await drawer.textContent()).includes(chain.sources[0].publisher),
      );
      assert.ok((await drawer.textContent()).includes(chain.sources[0].sha256));
      const outside = await drawer.evaluate((root) => {
        const clone = root.cloneNode(true);
        clone
          .querySelectorAll('[data-fact-chip]')
          .forEach((chip) => chip.remove());
        return /\p{Nd}/u.test(clone.textContent);
      });
      assert.equal(outside, false);
      await page.keyboard.press('Escape');
      assert.equal(
        await chip.evaluate((node) => node === document.activeElement),
        true,
      );
      function noEgress() {
        assert.deepEqual(forbidden, []);
      }
      noEgress();
      await page.evaluate(
        "fetch('https://invented.invalid/model').catch(() => undefined)",
      );
      assert.throws(noEgress); // Caught external/model requests still fail the guard.
      await context.close();
    }
  }
  console.log(
    'PASS mounted-browser: en/ar dark/light; caught-egress plant rejected',
  );
} finally {
  await browser.close();
}
