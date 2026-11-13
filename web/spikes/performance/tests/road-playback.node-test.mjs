import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createPlayback } from '../road-playback.ts';
import { roadLayer } from '../road-layer.ts';
import { generateRoads } from '../roads.mjs';
import data from '../road-data.json' with { type: 'json' };
import {
  HOUR_HOLD_MS,
  SCENE_MS,
  ROAD_DASH,
  ROAD_COLORS,
  VOLUME_BANDS,
  ROAD_WIDTHS,
} from '../config.mjs';

test('playback pauses, resumes, preserves all stored states and never starts when reduced', () => {
  const player = createPlayback(false);
  player.tick(0);
  player.tick(HOUR_HOLD_MS);
  assert.equal(player.elapsed, HOUR_HOLD_MS);
  player.toggle();
  player.tick(HOUR_HOLD_MS + SCENE_MS);
  player.tick(HOUR_HOLD_MS + SCENE_MS + 1);
  assert.equal(player.elapsed, HOUR_HOLD_MS);
  assert.equal(player.interrupted, true);
  player.toggle();
  player.tick(HOUR_HOLD_MS + SCENE_MS + 2);
  player.tick(HOUR_HOLD_MS + SCENE_MS + 3);
  assert.equal(player.elapsed, HOUR_HOLD_MS + 1);
  assert.equal(player.paused, false);
  const reduced = createPlayback(true);
  reduced.tick(0);
  reduced.tick(HOUR_HOLD_MS + SCENE_MS);
  assert.equal(reduced.elapsed, 0);
  assert.equal(reduced.interrupted, true);
  const slow = createPlayback(false);
  slow.tick(0);
  for (let index = 1; index < data.hours.length; index++)
    slow.tick(index * (HOUR_HOLD_MS + SCENE_MS) * 2);
  assert.deepEqual(slow.hoursShown, data.hours);
  assert.equal(slow.state.ended, true);
  const count = slow.hoursShown.length;
  slow.tick(data.hours.length * (HOUR_HOLD_MS + SCENE_MS) * 2);
  assert.equal(slow.hoursShown.length, count);
});

test('the actual path layer keeps data, class widths, hour triggers and static dash style', () => {
  const roads = generateRoads(data, 0);
  for (const hour of data.hours) {
    const layer = roadLayer(roads, hour, 1, 0, '');
    assert.equal(layer.props.data, roads);
    assert.equal(layer.props.updateTriggers.getColor, hour);
    assert.equal(layer.props.widthUnits, 'pixels');
    assert.deepEqual(layer.props.getDashArray, ROAD_DASH);
    assert.equal(layer.props.extensions[0].opts.dash, true);
    assert.equal(layer.props.dashJustified, true);
    assert.equal(layer.props.dashGapPickable, false);
    assert.equal(layer.props.visible, true);
    for (const road of roads) {
      assert.deepEqual(layer.props.getPath(road), road.path);
      assert.equal(layer.props.getWidth(road), ROAD_WIDTHS[road.roadClass]);
      assert.ok(layer.props.getWidth(road) > 0);
      assert.equal(layer.props.getColor(road)[3], 255);
      const row = data.rows.find(
        (row) => row.hour === hour && row.link_id === road.fixtureLink,
      );
      assert.deepEqual(
        layer.props.getColor(road),
        ROAD_COLORS[VOLUME_BANDS.indexOf(row?.volume_band ?? VOLUME_BANDS[0])],
      );
    }
  }
  assert.equal(
    roadLayer(roads, data.hours[0], 1, 0, 'omit-road-dash').props.extensions
      .length,
    0,
  );
  assert.equal(
    roadLayer(roads, data.hours[0], 1, 0, 'hide-roads').props.visible,
    false,
  );
  assert.equal(roadLayer(roads, data.hours[0], 0.5, 1, '').props.opacity, 0.5);
  assert.notEqual(
    roadLayer(roads, data.hours[0], 1, 0, '').id,
    roadLayer(roads, data.hours[0], 1, 1, '').id,
  );
});

test('every configured band has its own colour and both opacity slots reuse the payload', () => {
  const roads = generateRoads(data, 0);
  assert.equal(
    new Set(ROAD_COLORS.map((color) => JSON.stringify(color))).size,
    VOLUME_BANDS.length,
  );
  for (const band of VOLUME_BANDS) {
    const road = { ...roads[0], bands: { [data.hours[0]]: band } };
    const layer = roadLayer([road], data.hours[0], 1, 0, '');
    assert.deepEqual(
      layer.props.getColor(road),
      ROAD_COLORS[VOLUME_BANDS.indexOf(band)],
    );
  }
  assert.equal(roadLayer(roads, data.hours[0], 0, 1, '').props.data, roads);
});

test('after the final stored hour the particle clock can still pause and resume', () => {
  const player = createPlayback(false);
  const step = HOUR_HOLD_MS + SCENE_MS;
  for (let index = 0; index <= data.hours.length + 1; index++)
    player.tick(index * step);
  const held = player.elapsed;
  player.toggle();
  player.tick((data.hours.length + 2) * step);
  assert.equal(player.elapsed, held);
  player.toggle();
  player.tick((data.hours.length + 3) * step);
  player.tick((data.hours.length + 4) * step);
  assert.ok(player.elapsed > held);
  assert.equal(player.state.index, data.hours.length - 1);
  assert.equal(player.state.ended, true);
  assert.deepEqual(player.hoursShown, data.hours);
});

test('a zero-opacity endpoint stays allocated but is not drawn', () => {
  const roads = generateRoads(data, 0);
  const hidden = roadLayer(roads, data.hours[0], 0, 1, '');
  assert.equal(hidden.props.data, roads);
  assert.equal(hidden.props.visible, false);
  assert.equal(roadLayer(roads, data.hours[0], 0.5, 1, '').props.visible, true);
});

test('every payload class has positive width and every band is opaque', () => {
  for (const link of data.roads.links)
    assert.ok(ROAD_WIDTHS[link.road_class] > 0);
  for (const color of ROAD_COLORS) assert.equal(color[3], 255);
});
