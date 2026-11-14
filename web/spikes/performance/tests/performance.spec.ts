import { expect, test, type Page } from '@playwright/test';
import {
  ARABIC_REDUCED,
  FULL,
  FULL_STREET_LOAD,
  GATE_BLANK_RENDERER,
  GATE_SLOW_SCENE,
  HEX_NONBLANK,
  PARTICLE_NONBLANK,
  PAUSE_SCENE,
  PIXEL_CAP,
  RENAMED_PROFILE,
  ROAD_PAUSE_PLANT,
  ROAD_TRACE_SCENE,
  SMALL,
  TRACE_CONTRACT,
} from './canvas-mode.mjs';
import {
  foreignBeforeCommit,
  refuseForeignAfterReady,
} from './foreign-request.mjs';
import { clickPause } from './pause-click';
import { prepareCanvas } from './small-map';

const HEXAGONS = 110000;
const PARTICLES = 50000;
const WALL_WIDTH = 1920;
const WALL_HEIGHT = 1080;

type Spike = NonNullable<Window['__spike']>;

async function ready(page: Page): Promise<Spike> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let value: Spike;
  try {
    value = await Promise.race([
      page.evaluate(
        () =>
          new Promise<Spike>((resolve) => {
            const read = () => {
              const spike = window.__spike;
              if (spike?.phase === 'done' || spike?.phase === 'failed') {
                resolve(structuredClone(spike));
              } else {
                requestAnimationFrame(read);
              }
            };
            read();
          }),
      ),
      new Promise<never>((_, reject) => {
        timer = setTimeout(
          () => reject(new Error('spike readiness timed out')),
          170000,
        );
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
  if (value === undefined) throw new Error('spike diagnostics are absent');
  return value;
}

async function tracePosts(page: Page): Promise<number> {
  const response = await page.request.get('/__perf/posts');
  expect(response.ok()).toBe(true);
  return Number(await response.text());
}

async function open(
  page: Page,
  path: string,
  canvas: string = FULL,
): Promise<Spike> {
  await prepareCanvas(page, canvas);
  const seen: string[] = [];
  let settled = false;
  let rejectForeign: (error: Error) => void = () => {};
  const foreignStop = new Promise<never>((_, reject) => {
    rejectForeign = reject;
  });
  // A foreign request rejects before the scene render finishes. The text stays.
  page.on('request', (request) => {
    const url = request.url();
    seen.push(url);
    if (settled) return;
    const foreign = foreignBeforeCommit(url, page.url());
    if (foreign !== '') {
      settled = true;
      rejectForeign(new Error(`non-same-origin request: ${foreign}`));
    }
  });
  const pending = (async () => {
    await page.goto(path);
    return ready(page);
  })();
  void pending.catch(() => undefined);
  try {
    const spike = await Promise.race([pending, foreignStop]);
    const origin = new URL(page.url()).origin;
    refuseForeignAfterReady(seen, origin);
    return spike;
  } finally {
    settled = true;
  }
}

test('the smoke orbit draws both layers and records a trace', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const see = () => {
      const text = document.querySelector('#renderer')?.textContent ?? '';
      if (text.length > 0 && window.__spike?.phase === 'renderer') {
        window.__rendererSeenBeforeOrbit = true;
      }
    };
    const arm = () => {
      if (!document.documentElement) return;
      new MutationObserver(see).observe(document.documentElement, {
        subtree: true,
        childList: true,
        characterData: true,
      });
    };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', arm);
    } else {
      arm();
    }
  });
  const spike = await open(page, '/en/_perf?profile=smoke', TRACE_CONTRACT);
  expect(spike.phase).toBe('done');
  expect(spike.failure).toBe('');
  expect(spike.hexagonInstances).toBe(HEXAGONS);
  expect(spike.particleInstances).toBe(PARTICLES);
  expect(spike.hex).toBe(true);
  expect(spike.particle).toBe(true);
  expect(spike.bearingEnd).not.toBe(spike.bearingStart);
  expect(spike.positionEnd).not.toBe(spike.positionStart);
  expect(spike.cssWidth).toBe(WALL_WIDTH);
  expect(spike.cssHeight).toBe(WALL_HEIGHT);
  expect(spike.bufferWidth).toBe(WALL_WIDTH);
  expect(spike.bufferHeight).toBe(WALL_HEIGHT);
  expect(spike.textPixelRatio).toBe(2);
  expect(spike.cap).toBe(1);
  expect(spike.devicePixelRatio).toBe(2);
  expect(spike.webglRenderer.length).toBeGreaterThan(0);
  expect(spike.submitFailure).toBe('');
  expect(spike.qualification).toBe('smoke-profile');
  expect(spike.savedPath.length).toBeGreaterThan(0);
  expect(spike.shareUnderBudget).not.toBeNull();
  expect(spike).not.toHaveProperty('framesPerSecond');
  await expect(page.locator('#pending')).toHaveText(
    'native frame-rate gate pending',
  );
  await expect(page.locator('#notice')).toHaveText(
    'Synthetic fixture. Invented extent. No place name.',
  );
  await expect(page.locator('#renderer')).toHaveText(spike.webglRenderer);
  expect(await page.evaluate(() => window.__rendererSeenBeforeOrbit)).toBe(
    true,
  );
});

test('the Arabic route uses the Arabic notice', async ({ page }) => {
  const spike = await open(page, '/ar/_perf?profile=smoke', SMALL);
  await expect(page.locator('#renderer')).toHaveText(spike.webglRenderer);
  await expect(page.locator('#notice')).toHaveText(
    'عرض اصطناعي. امتداد مخترع. بلا اسم مكان.',
  );
  await expect(page.locator('html')).toHaveAttribute('lang', 'ar');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
});

test('isolating hexagons leaves the hex canvas nonblank', async ({ page }) => {
  const spike = await open(
    page,
    '/en/_perf?profile=smoke&isolate=hexagons',
    HEX_NONBLANK,
  );
  expect(spike.hexagonInstances).toBe(HEXAGONS);
  expect(spike.particleInstances).toBe(0);
  expect(spike.hex).toBe(true);
  expect(spike.particle).toBe(false);
});

test('isolating particles leaves the particle canvas nonblank', async ({
  page,
}) => {
  const spike = await open(
    page,
    '/en/_perf?profile=smoke&isolate=particles',
    PARTICLE_NONBLANK,
  );
  expect(spike.hexagonInstances).toBe(0);
  expect(spike.particleInstances).toBe(PARTICLES);
  expect(spike.particle).toBe(true);
  expect(spike.hex).toBe(false);
});

test('omitting one hexagon lowers the drawn count', async ({ page }) => {
  const spike = await open(
    page,
    '/en/_perf?profile=smoke&plant=omit-hexagon',
    SMALL,
  );
  expect(spike.hexagonInstances).toBe(HEXAGONS - 1);
  expect(spike.hex).toBe(true);
  expect(spike.particle).toBe(true);
});

test('hiding the hexagon layer reports no hexagon instances', async ({
  page,
}) => {
  const spike = await open(
    page,
    '/en/_perf?profile=smoke&plant=hide-hexagons',
    SMALL,
  );
  expect(spike.hexagonInstances).toBe(0);
  expect(spike.hex).toBe(false);
});

test('omitting one particle lowers the drawn count', async ({ page }) => {
  const spike = await open(
    page,
    '/en/_perf?profile=smoke&plant=omit-particle',
    SMALL,
  );
  expect(spike.particleInstances).toBe(PARTICLES - 1);
  expect(spike.particle).toBe(true);
  expect(spike.hex).toBe(true);
});

test('hiding the particle layer reports no particle instances', async ({
  page,
}) => {
  const spike = await open(
    page,
    '/en/_perf?profile=smoke&plant=hide-particles',
    SMALL,
  );
  expect(spike.particleInstances).toBe(0);
  expect(spike.particle).toBe(false);
});

test('a frozen clock leaves the first particle in place', async ({ page }) => {
  const spike = await open(page, '/en/_perf?profile=smoke&plant=freeze', SMALL);
  expect(spike.positionEnd).toBe(spike.positionStart);
});

test('an empty timestamp list is refused by name', async ({ page }) => {
  const spike = await open(
    page,
    '/en/_perf?profile=smoke&plant=no-samples',
    SMALL,
  );
  expect(spike.submitFailure).toBe('empty-timestamps');
});

test('a blank renderer is refused by name', async ({ page }) => {
  const spike = await open(
    page,
    '/en/_perf?plant=missing-renderer',
    GATE_BLANK_RENDERER,
  );
  expect(spike.webglRenderer).toBe('');
  expect(spike.profile).toBe('gate');
  expect(spike.qualification).toBe('missing-renderer');
});

test('an unknown field is refused by name', async ({ page }) => {
  const spike = await open(
    page,
    '/en/_perf?profile=smoke&plant=fail-submit',
    SMALL,
  );
  expect(spike.submitFailure).toBe('unknown-field');
});

test('ignoring the cap is qualified as the wrong cap', async ({ page }) => {
  const spike = await open(
    page,
    '/en/_perf?profile=smoke&plant=ignore-cap',
    PIXEL_CAP,
  );
  expect(spike.cap).toBe(spike.textPixelRatio);
  expect(spike.cap).toBe(2);
  expect(spike.bufferWidth).toBe(WALL_WIDTH * spike.cap);
  expect(spike.qualification).toBe('wrong-cap');
});

test('a renamed profile is qualified by name', async ({ page }) => {
  const spike = await open(
    page,
    '/en/_perf?profile=smoke&plant=rename-profile',
    RENAMED_PROFILE,
  );
  expect(spike.profile).toBe('tuned');
  expect(spike.qualification).toBe('unknown-profile');
});

test('the ordinary page helper rejects a remote asset', async ({ page }) => {
  await expect(
    open(page, '/en/_perf?profile=smoke&plant=remote-asset'),
  ).rejects.toThrow(/assets\.invalid/);
  expect(await page.evaluate(() => window.__spike?.phase ?? '')).not.toBe(
    'done',
  );
});

test('a remote image does not load', async ({ page }) => {
  const failed: string[] = [];
  page.on('requestfailed', (request) => {
    if (request.url().includes('assets.invalid')) failed.push(request.url());
  });
  await prepareCanvas(page, SMALL);
  await page.goto('/en/_perf?profile=smoke&plant=remote-asset');
  const spike = await ready(page);
  expect(spike.phase).toBe('done');
  expect(failed.length).toBeGreaterThan(0);
});

test('the no-webgl2 plant names the failure without a map', async ({
  page,
}) => {
  const spike = await open(page, '/en/_perf?profile=smoke&plant=no-webgl2');
  expect(spike.phase).toBe('failed');
  expect(spike.failure).toBe('webgl2-unavailable');
  await expect(page.locator('#map-failure')).toHaveText('webgl2-unavailable');
});

async function expectEarlyRefusal(
  page: Page,
  path: string,
  refusal: string,
  renderer: string,
): Promise<void> {
  const before = await tracePosts(page);
  const seen: string[] = [];
  page.on('request', (request) => {
    seen.push(request.url());
  });
  await page.goto(path);
  await expect(page.locator('#map-failure')).toHaveText(refusal, {
    timeout: 8000,
  });
  await expect(page.locator('#renderer')).toHaveText(renderer);
  const after = await tracePosts(page);
  expect(after).toBe(before);
  refuseForeignAfterReady(seen, new URL(page.url()).origin);
  expect(
    seen.filter((url) => new URL(url).pathname === '/__perf/trace'),
  ).toEqual([]);
  const spike = await page.evaluate(() => window.__spike);
  if (spike === undefined) throw new Error('spike diagnostics are absent');
  expect(spike.phase).toBe('failed');
  expect(spike.profile).toBe('gate');
  expect(spike.hexagonInstances).toBe(0);
  expect(spike.particleInstances).toBe(0);
  expect(spike.bearingEnd).toBe(spike.bearingStart);
  expect(spike.savedPath).toBe('');
  expect(spike.submitFailure).toBe('');
  expect(await page.locator('#map canvas').count()).toBe(0);
}

test('a planted software renderer is refused before the orbit', async ({
  page,
}) => {
  await expectEarlyRefusal(
    page,
    '/en/_perf?plant=software-renderer',
    'refused: software-renderer',
    'Microsoft Basic Render Driver',
  );
});

test('a planted remote renderer is refused before the orbit', async ({
  page,
}) => {
  await expectEarlyRefusal(
    page,
    '/en/_perf?plant=remote-renderer',
    'refused: remote-renderer',
    'Microsoft Remote Display Adapter',
  );
});

test('a planted capped empty canvas is refused before the layers load', async ({
  page,
}) => {
  await expectEarlyRefusal(
    page,
    '/en/_perf?plant=capped-frame-rate',
    'refused: capped-frame-rate 30',
    'Synthetic passing adapter',
  );
});

test('a planted slow full scene with an empty canvas at 60 is stored', async ({
  page,
}) => {
  const before = await tracePosts(page);
  await prepareCanvas(page, GATE_SLOW_SCENE);
  await page.goto('/en/_perf?plant=slow-scene');
  await expect(page.locator('#renderer')).toHaveText(
    'Synthetic passing adapter',
    { timeout: 8000 },
  );
  const spike = await ready(page);
  expect(spike.phase).toBe('done');
  expect(spike.failure).toBe('');
  expect(spike.profile).toBe('gate');
  expect(spike.hexagonInstances).toBe(HEXAGONS);
  expect(spike.particleInstances).toBe(PARTICLES);
  expect(spike.bearingEnd).not.toBe(spike.bearingStart);
  expect(spike.positionEnd).not.toBe(spike.positionStart);
  expect(spike.shareUnderBudget).toBe(0);
  expect(spike.submitFailure).toBe('');
  expect(spike.savedPath.length).toBeGreaterThan(0);
  expect(spike.qualification).not.toBe('');
  expect(spike.qualification).not.toBe('pass');
  expect(spike.qualification).not.toBe('capped-frame-rate');
  await expect(page.locator('#map-failure')).toBeHidden();
  const after = await tracePosts(page);
  expect(after).toBe(before + 1);
});

// S1-T11: share only scenes with identical initial language, motion and load.
import roadData from '../road-data.json' with { type: 'json' };
import { LAYER_SETS, ROAD_LOADS, VOLUME_BANDS } from '../config.mjs';
const ROAD_SET = Object.keys(ROAD_LOADS)[0]!;
const ROAD_LARGE = Object.keys(ROAD_LOADS)[1]!;
const roadUrl = (extra = '') =>
  `/en/_perf?profile=smoke&layers=${ROAD_SET}${extra}`;

async function framesAfter(page: Page, frames: number): Promise<Spike> {
  return page.evaluate(async (count) => {
    while ((window.__spike?.motionFrames ?? 0) <= count + 2) {
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => resolve()),
      );
    }
    return structuredClone(window.__spike!);
  }, frames);
}

type RoadScene = { page: Page; spike: Spike };
type PauseObservation = { paused: Spike; after: Spike; resumed: Spike };

function sharedRoadScene(
  name: string,
  canvas: string,
  language: string,
  reduced: boolean,
  register: (scene: () => RoadScene) => void,
): void {
  test.describe(name, () => {
    let page: Page;
    let spike: Spike;
    test.beforeAll(async ({ browser }, info) => {
      const started = performance.now();
      const { baseURL, viewport, deviceScaleFactor } = info.project.use;
      page = await browser.newPage({ baseURL, viewport, deviceScaleFactor });
      if (reduced) await page.emulateMedia({ reducedMotion: 'reduce' });
      const path = `/${language}/_perf?profile=smoke&layers=${ROAD_SET}`;
      spike = await open(page, path, canvas);
      console.log(
        'MEASURED shared scene setup ms',
        name,
        performance.now() - started,
      );
    });
    test.afterAll(async () => {
      if (!page) return;
      const started = performance.now();
      await page.close();
      console.log(
        'MEASURED shared scene close ms',
        name,
        performance.now() - started,
      );
    });
    // Default mode keeps each test independently runnable and does not skip
    // later tests after a failure. A restarted worker rebuilds this fixture.
    register(() => ({ page, spike }));
  });
}

async function observePause(
  page: Page,
  pause: () => Promise<void>,
): Promise<PauseObservation> {
  await pause();
  const { paused, after } = await page.evaluate(async () => {
    const frame = () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => resolve());
      });
    while (window.__spike?.paused !== true) await frame();
    const paused = structuredClone(window.__spike);
    while ((window.__spike?.motionFrames ?? 0) <= paused.motionFrames + 2) {
      await frame();
    }
    return { paused, after: structuredClone(window.__spike!) };
  });
  // Keep the clock-freeze assertion meaningful: do not start at the last hour.
  expect(paused.hoursShown.length).toBeLessThan(roadData.hours.length);
  await clickPause(page);
  const resumed = await page.evaluate(
    async ({ elapsed, position }) => {
      while (!(
        (window.__spike?.motionElapsed ?? 0) > elapsed &&
        window.__spike?.currentPosition !== position
      )) {
        await new Promise<void>((resolve) =>
          requestAnimationFrame(() => resolve()),
        );
      }
      return structuredClone(window.__spike!);
    },
    { elapsed: paused.motionElapsed, position: paused.currentPosition },
  );
  return { paused, after, resumed };
}

function visibilityTest(
  scene: () => RoadScene,
  language: string,
  motion: string,
  pause?: () => Promise<void>,
): void {
  test(`roads mark and legend are visible ${language} ${motion}`, async () => {
    test.setTimeout(600000);
    const { page } = scene();
    const button = page.locator('#pause-motion');
    const label = language === 'ar' ? 'إيقاف الحركة مؤقتًا' : 'Pause motion';
    await expect(button).toHaveText(label);
    if (motion === 'paused') {
      await (pause ? pause() : clickPause(page));
      await Promise.all([
        expect(button).toHaveAttribute('aria-pressed', 'true'),
        expect(button).toHaveText(label),
      ]);
    }
    await Promise.all([
      expect(page.locator('#road-legend')).toBeVisible(),
      expect(page.locator('#road-mark')).toBeVisible(),
      expect(page.locator('#road-mark')).toHaveText(
        language === 'ar' ? 'محاكاة' : 'Simulated',
      ),
    ]);
  });
}

sharedRoadScene(
  'uninterrupted English road scene',
  ROAD_TRACE_SCENE,
  'en',
  false,
  (scene) => {
    test('roads carry the Simulated word and dash style in the interleaved overlay', async () => {
      const { page } = scene();
      test.setTimeout(600000);
      await Promise.all([
        expect(page.locator('#road-mark')).toHaveText('Simulated'),
        expect(page.locator('#road-mark')).toBeVisible(),
        expect(page.locator('#road-legend')).toBeVisible(),
        expect(page.locator('#road-sample')).toHaveCSS(
          'border-top-style',
          'dashed',
        ),
      ]);
      expect(
        await page.evaluate(() =>
          Reflect.get(window.__spike ?? {}, 'roadDashEnabled'),
        ),
      ).toBe(true);
    });

    test('roads draw the configured full fixture and first load with both original layers', async () => {
      test.setTimeout(600000);
      const spike = scene().spike;
      expect(spike.roadInstances).toBe(LAYER_SETS[ROAD_SET]!.roads);
      expect(spike.road).toBe(true);
      expect(spike.hexagonInstances).toBe(LAYER_SETS[ROAD_SET]!.hexagons);
      expect(spike.particleInstances).toBe(LAYER_SETS[ROAD_SET]!.particles);
    });

    test('roads short orbit posts a well-formed smoke trace', async () => {
      test.setTimeout(600000);
      const spike = scene().spike;
      expect(spike.phase).toBe('done');
      expect(spike.submitFailure).toBe('');
      expect(spike.qualification).toBe('smoke-profile');
      expect(spike.savedPath).toContain(ROAD_SET);
    });

    test('roads playback visits each stored hour and holds the recorded bands across the load cycle', async () => {
      const { page } = scene();
      test.setTimeout(600000);
      await page.waitForFunction(
        (hours) => window.__spike?.roadStates.at(-1)?.hour === hours.at(-1),
        roadData.hours,
        { timeout: 170000 },
      );
      const spike = (await page.evaluate(() => window.__spike))!;
      expect(spike.hoursShown).toEqual(roadData.hours);
      const links = roadData.roads.links;
      const indexes = [
        ...Array.from({ length: links.length * 2 }, (_, index) => index),
        ...Array.from(
          { length: links.length },
          (_, index) => LAYER_SETS[ROAD_SET]!.roads! - links.length + index,
        ),
      ];
      const expected = (hour: number) =>
        indexes.map((index) => {
          const fixture =
            index < links.length
              ? index
              : (index - links.length) % links.length;
          return (
            roadData.rows.find(
              (row) =>
                row.hour === hour && row.link_id === links[fixture]!.link_id,
            )?.volume_band ?? VOLUME_BANDS[0]
          );
        });
      for (const state of spike.roadStates) {
        expect(roadData.hours).toContain(state.hour);
        expect(roadData.hours).toContain(state.nextHour);
        expect(state.bands).toEqual(expected(state.hour));
        expect(state.nextBands).toEqual(expected(state.nextHour));
        expect(state.trigger).toBe(state.hour);
        expect(state.stableData).toBe(true);
      }
      expect(
        new Set(spike.roadStates.map((state) => JSON.stringify(state.bands)))
          .size,
      ).toBeGreaterThan(1);
      expect(spike.hourStepsMs.length).toBe(roadData.hours.length - 1);
      console.log(
        'MEASURED headless stored-hour steps ms',
        JSON.stringify(spike.hourStepsMs),
      );
    });
    visibilityTest(scene, 'en', 'playing');
  },
);

sharedRoadScene('English pause scene', PAUSE_SCENE, 'en', false, (scene) => {
  let firstPause: Promise<void> | undefined;
  const pause = () => {
    // Both consumers start from this fixture's first pause, including when
    // either test is selected alone or the worker restarts after a failure.
    expect(scene().spike.phase).toBe('done');
    expect(scene().spike.paused).toBe(false);
    expect(scene().spike.reducedMotion).toBe(false);
    return (firstPause ??= clickPause(scene().page));
  };
  // Assert the live paused DOM before the clock test resumes the scene.
  // Only the input action is shared; visibility assertions are never cached.
  visibilityTest(scene, 'en', 'paused', pause);
  let observation: Promise<PauseObservation> | undefined;
  const paused = () => (observation ??= observePause(scene().page, pause));
  test('roads Pause motion freezes the hour clock and resumes it on a second press', async () => {
    test.setTimeout(600000);
    const { paused: before, after, resumed } = await paused();
    expect(before.paused).toBe(true);
    expect(after.motionElapsed).toBe(before.motionElapsed);
    expect(after.hoursShown).toEqual(before.hoursShown);
    expect(resumed.paused).toBe(false);
  });
  test('roads Pause motion freezes particles and resumes them on a second press', async () => {
    test.setTimeout(600000);
    const { paused: before, after, resumed } = await paused();
    expect(before.paused).toBe(true);
    expect(after.currentPosition).toBe(before.currentPosition);
    expect(resumed.currentPosition).not.toBe(before.currentPosition);
  });
});

sharedRoadScene('English reduced-motion scene', SMALL, 'en', true, (scene) => {
  test('roads reduced motion never starts hour playback or particles', async () => {
    const { page } = scene();
    test.setTimeout(600000);
    const spike = scene().spike;
    const after = await framesAfter(page, spike.motionFrames);
    expect(after.motionFrames).toBeGreaterThan(spike.motionFrames + 2);
    expect(after.reducedMotion).toBe(true);
    expect(after.motionElapsed).toBe(0);
    expect(after.hoursShown).toEqual(roadData.hours.slice(0, 1));
    expect(after.currentPosition).toBe(spike.positionStart);
  });
  visibilityTest(scene, 'en', 'reduced');
});

sharedRoadScene('Arabic road scene', SMALL, 'ar', false, (scene) => {
  test('roads have the Arabic provenance word and dashed legend on the Arabic route', async () => {
    const { page } = scene();
    test.setTimeout(600000);
    const spike = scene().spike;
    expect(spike.phase).toBe('done');
    await Promise.all([
      expect(page.locator('#road-mark')).toHaveText(
        roadData.header.provenance === 'Simulated' ? 'محاكاة' : 'invalid',
      ),
      expect(page.locator('#road-sample')).toHaveCSS(
        'border-top-style',
        'dashed',
      ),
      expect(page.locator('#road-mark')).toBeVisible(),
      expect(page.locator('#road-legend')).toBeVisible(),
    ]);
    expect(spike.roadDashEnabled).toBe(true);
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  });
  visibilityTest(scene, 'ar', 'playing');
  visibilityTest(scene, 'ar', 'paused');
});

sharedRoadScene(
  'Arabic reduced-motion scene',
  ARABIC_REDUCED,
  'ar',
  true,
  (scene) => {
    visibilityTest(scene, 'ar', 'reduced');
  },
);

test('roads paused playback plant is refused by name', async ({ page }) => {
  test.setTimeout(600000);
  const spike = await open(
    page,
    roadUrl('&plant=pause-playback'),
    ROAD_PAUSE_PLANT,
  );
  expect(spike.qualification).toBe('road-playback-stopped');
});

test('roads missing dash plant removes the actual extension', async ({
  page,
}) => {
  test.setTimeout(600000);
  const spike = await open(page, roadUrl('&plant=omit-road-dash'), SMALL);
  expect(spike.roadDashEnabled).toBe(false);
});

test('roads missing link plant lowers the drawn count', async ({ page }) => {
  test.setTimeout(600000);
  const spike = await open(page, roadUrl('&plant=omit-road'), SMALL);
  expect(spike.roadInstances).toBe(LAYER_SETS[ROAD_SET]!.roads! - 1);
  expect(spike.road).toBe(true);
  expect(spike.qualification).toBe('reduced-counts');
});

test('roads hidden layer plant reports zero drawn road links', async ({
  page,
}) => {
  test.setTimeout(600000);
  const spike = await open(page, roadUrl('&plant=hide-roads'), SMALL);
  expect(spike.roadInstances).toBe(0);
  expect(spike.road).toBe(false);
  expect(spike.qualification).toBe('reduced-counts');
});

test('roads ordinary helper refuses the remote request plant', async ({
  page,
}) => {
  test.setTimeout(600000);
  await expect(open(page, roadUrl('&plant=remote-asset'))).rejects.toThrow(
    /assets\.invalid/,
  );
  expect(await page.evaluate(() => window.__spike?.phase ?? '')).not.toBe(
    'done',
  );
});

test('roads full street load draws every link and carries the Simulated mark', async ({
  page,
}) => {
  test.setTimeout(600000);
  const spike = await open(
    page,
    `/en/_perf?profile=smoke&layers=${ROAD_LARGE}`,
    FULL_STREET_LOAD,
  );
  expect(spike.phase).toBe('done');
  expect(spike.roadInstances).toBe(LAYER_SETS[ROAD_LARGE]!.roads);
  expect(spike.road).toBe(true);
  expect(spike.hexagonInstances).toBe(LAYER_SETS[ROAD_LARGE]!.hexagons);
  expect(spike.particleInstances).toBe(LAYER_SETS[ROAD_LARGE]!.particles);
  await Promise.all([
    expect(page.locator('#road-mark')).toBeVisible(),
    expect(page.locator('#road-legend')).toBeVisible(),
  ]);
  expect(spike.roadDashEnabled).toBe(true);
  await Promise.all([
    expect(page.locator('#road-mark')).toHaveText('Simulated'),
    expect(page.locator('#road-mark')).toBeVisible(),
    expect(page.locator('#road-legend')).toBeVisible(),
    expect(page.locator('#road-sample')).toHaveCSS(
      'border-top-style',
      'dashed',
    ),
  ]);
});
