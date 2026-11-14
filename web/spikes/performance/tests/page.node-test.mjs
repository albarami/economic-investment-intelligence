import assert from 'node:assert/strict';
import { test } from 'node:test';
import { pageHarness } from './page-harness.mjs';
import data from '../road-data.json' with { type: 'json' };
import { HOUR_HOLD_MS, SCENE_MS, LAYER_SETS } from '../config.mjs';

test('page selects the road payload, mark, reference labels and uninterrupted trace fields', async () => {
  const h = await pageHarness();
  assert.equal(
    h.input.roads.length,
    LAYER_SETS['hexagons-particles-roads'].roads,
  );
  assert.equal(h.nodes.get('#road-mark').textContent, 'Simulated');
  assert.equal(h.nodes.get('#road-legend').hidden, false);
  assert.equal(h.nodes.get('#pause-motion').hidden, false);
  h.frame(0);
  h.frame(HOUR_HOLD_MS + SCENE_MS / 2);
  assert.equal(h.window.__spike.roadStates.length, 2);
  assert.equal(
    h.nodes.get('#hour-current').textContent,
    String(data.hours[0]).padStart(2, '0') + ':00',
  );
  assert.equal(
    h.nodes.get('#hour-next').textContent,
    String(data.hours[1]).padStart(2, '0') + ':00',
  );
  assert.equal(h.nodes.get('#hour-current').style.opacity, '0.5');
  assert.equal(h.nodes.get('#hour-next').style.opacity, '0.5');
  h.frame(HOUR_HOLD_MS + SCENE_MS);
  assert.equal(h.window.__spike.roadStates.length, 3);
  assert.equal(h.window.__spike.roadStates.at(-1).hour, data.hours[1]);
  assert.equal(h.window.__spike.hourStepsMs.length, 1);
  assert.equal(h.window.__spike.hourStepsMs[0], HOUR_HOLD_MS + SCENE_MS);
  await h.finish([0, HOUR_HOLD_MS + SCENE_MS]);
  const trace = h.requests[0];
  assert.equal(trace.layerSet, 'hexagons-particles-roads');
  assert.deepEqual(trace.counts, LAYER_SETS[trace.layerSet]);
  assert.equal(trace.animation.playbackActive, true);
  assert.equal(trace.animation.reducedMotion, false);
  assert.deepEqual(trace.animation.hoursShown, data.hours.slice(0, 2));
  assert.equal(h.window.__spike.qualification, 'smoke-profile');
  h.tick(HOUR_HOLD_MS + SCENE_MS + 1);
  assert.ok(h.window.__spike.motionFrames > 3);
});

test('page Pause motion wires both clocks, resumes, and retains the trace interruption', async () => {
  const h = await pageHarness();
  h.frame(0);
  h.frame(10);
  h.nodes.get('#pause-motion').onclick();
  const position = h.window.__spike.currentPosition;
  h.frame(20);
  h.frame(30);
  assert.equal(h.window.__spike.currentPosition, position);
  assert.equal(h.window.__spike.motionElapsed, 10);
  assert.equal(h.window.__spike.paused, true);
  assert.equal(h.nodes.get('#pause-motion').textContent, 'Pause motion');
  assert.equal(h.nodes.get('#pause-motion').attributes['aria-pressed'], 'true');
  h.nodes.get('#pause-motion').onclick();
  h.frame(40);
  h.frame(50);
  assert.notEqual(h.window.__spike.currentPosition, position);
  assert.ok(h.window.__spike.motionElapsed > 10);
  assert.equal(
    h.window.__spike.currentPosition,
    h.window.__spike.motionElapsed + 2,
  );
  assert.equal(h.nodes.get('#pause-motion').textContent, 'Pause motion');
  await h.finish([0, 50]);
  assert.equal(h.requests[0].animation.playbackActive, false);
});

test('page respects initial and changed reduced motion and the Arabic mark', async () => {
  const h = await pageHarness('', true, true);
  assert.equal(h.nodes.get('#road-mark').textContent, 'محاكاة');
  h.frame(0);
  h.frame(HOUR_HOLD_MS + SCENE_MS);
  assert.equal(h.window.__spike.motionElapsed, 0);
  assert.equal(h.window.__spike.currentPosition, 1);
  assert.equal(h.window.__spike.reducedMotion, true);
  h.media.change({ matches: false });
  h.frame(HOUR_HOLD_MS + SCENE_MS + 1);
  assert.ok(h.window.__spike.motionElapsed > 0);
  h.media.change({ matches: true });
  h.frame(HOUR_HOLD_MS + SCENE_MS + 2);
  await h.finish([0, 50]);
  assert.equal(h.requests[0].animation.playbackActive, false);
  assert.equal(h.requests[0].animation.reducedMotion, true);
});

test('page plants omit a link and begin with paused playback', async () => {
  const missing = await pageHarness('&plant=omit-road');
  assert.equal(
    missing.input.roads.length,
    LAYER_SETS['hexagons-particles-roads'].roads - 1,
  );
  const paused = await pageHarness('&plant=pause-playback');
  paused.frame(0);
  paused.frame(10);
  await paused.finish([0, 10]);
  assert.equal(paused.requests[0].animation.playbackActive, false);
  assert.equal(paused.window.__spike.qualification, 'road-playback-stopped');
});

test('continuing after the orbit keeps the original animation-frame clock origin', async () => {
  const h = await pageHarness();
  h.frame(0);
  h.frame(HOUR_HOLD_MS + SCENE_MS);
  const origin = 100;
  const absoluteLast = origin + HOUR_HOLD_MS + SCENE_MS;
  h.setClock(absoluteLast + SCENE_MS);
  await h.finish([origin, absoluteLast]);
  h.tick(absoluteLast + SCENE_MS / 2);
  assert.equal(
    h.window.__spike.motionElapsed,
    HOUR_HOLD_MS + SCENE_MS + SCENE_MS / 2,
  );
  assert.equal(h.window.__spike.roadStates.at(-1).hour, data.hours[1]);
});

for (const arabic of [false, true]) {
  test(`pause keeps its label and holds camera arabic=${arabic}`, async () => {
    const h = await pageHarness('', false, arabic);
    const button = h.nodes.get('#pause-motion');
    const label = arabic ? 'إيقاف الحركة مؤقتًا' : 'Pause motion';
    assert.equal(button.textContent, label);
    h.frame(0);
    h.frame(10);
    const bearing = h.scene.bearing();
    button.onclick();
    h.frame(20);
    assert.equal(h.scene.bearing(), bearing);
    assert.equal(button.textContent, label);
    assert.equal(button.attributes['aria-pressed'], 'true');
    button.onclick();
    h.frame(30);
    assert.notEqual(h.scene.bearing(), bearing);
    assert.equal(button.textContent, label);
    assert.equal(button.attributes['aria-pressed'], 'false');
  });
}
test('reduced motion holds the camera from load', async () => {
  const h = await pageHarness('', true);
  h.frame(0);
  h.frame(100);
  assert.equal(h.scene.bearing(), 0);
});
