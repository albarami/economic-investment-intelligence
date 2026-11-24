import { describe, expect, it } from 'vitest';

import {
  ARROW_STEP_PX,
  applyGesture,
  idleSession,
  step,
  type MapPort,
  type SessionEvent,
} from '../../src/controls/draw-session';
import { plainPort } from '../fixtures/plain-port';

function recording(
  width = 320,
  height = 320,
): {
  port: MapPort;
  seen: string[];
} {
  const base = plainPort(width, height);
  const seen: string[] = [];
  return {
    seen,
    port: {
      ...base,
      suspendGestures() {
        seen.push('suspend');
      },
      restoreGestures() {
        seen.push('restore');
      },
      centre() {
        seen.push('centre');
        return { longitude: 0.5, latitude: 0.5 };
      },
    },
  };
}

describe('drawing session', () => {
  function triangle() {
    const { port } = recording();
    let session = step(
      idleSession(),
      { type: 'select-tool', tool: 'polygon' },
      port,
    ).session;
    for (const [x, y] of [
      [40, 40],
      [120, 40],
      [120, 120],
    ] as const) {
      session = step(
        session,
        { type: 'pointer', x, y, pointerType: 'touch' },
        port,
      ).session;
    }
    return { session, port };
  }

  it('Q1: a tap after dragging an open polygon knob adds a vertex', () => {
    const { session, port } = triangle();
    const dragged = step(
      session,
      { type: 'drag-knob', index: 1, x: 130, y: 50 },
      port,
    ).session;
    const tapped = step(
      dragged,
      { type: 'pointer', x: 40, y: 200, pointerType: 'touch' },
      port,
    ).session;
    expect(tapped.vertices).toHaveLength(4);
    expect(tapped.vertices[1]).toEqual(dragged.vertices[1]);
    expect(tapped.vertices[3]).toMatchObject(port.unproject({ x: 40, y: 200 }));
  });

  it('Q2: a tap after closing a ring leaves its vertices unchanged', () => {
    const { session, port } = triangle();
    const closed = step(
      session,
      { type: 'pointer', x: 40, y: 40, pointerType: 'touch' },
      port,
    ).session;
    const tapped = step(
      closed,
      { type: 'pointer', x: 250, y: 250, pointerType: 'touch' },
      port,
    ).session;
    expect(closed.closed).toBe(true);
    expect(tapped.vertices).toEqual(closed.vertices);
  });

  it('keyboard focus alone never selects a knob for a later tap move', () => {
    const { session, port } = triangle();
    const focused = step(
      session,
      { type: 'focus-knob', index: 1 },
      port,
    ).session;
    expect(focused.selectedKnob).toBeNull();
    const tapped = step(
      focused,
      { type: 'pointer', x: 40, y: 200, pointerType: 'touch' },
      port,
    ).session;
    expect(tapped.vertices).toHaveLength(4);
    expect(tapped.vertices[1]).toEqual(focused.vertices[1]);
  });

  it.each([
    { type: 'drag-knob', index: 1, x: 130, y: 50 },
    { type: 'enter' },
    { type: 'pointer', x: 40, y: 40, pointerType: 'touch' },
    { type: 'escape' },
    { type: 'select-tool', tool: 'radius' },
    { type: 'pointer', x: 40, y: 200, pointerType: 'touch' },
    { type: 'arrow', key: 'ArrowRight' },
  ] satisfies SessionEvent[])('clears tap selection on %j', (event) => {
    const { session, port } = triangle();
    const focused = step(
      session,
      { type: 'focus-knob', index: 1 },
      port,
    ).session;
    const selected = step(
      focused,
      { type: 'select-knob', index: 1 },
      port,
    ).session;
    expect(selected.selectedKnob).toBe(1);
    const next = step(selected, event, port).session;
    expect(next.selectedKnob).toBeNull();
    if (event.type === 'pointer' && event.x === 40 && event.y === 200) {
      expect(next.vertices).toHaveLength(3);
      expect(next.vertices[1]).toMatchObject(port.unproject({ x: 40, y: 200 }));
      const placed = step(
        next,
        { type: 'pointer', x: 250, y: 250, pointerType: 'touch' },
        port,
      ).session;
      expect(placed.vertices).toHaveLength(4);
      expect(placed.vertices[1]).toEqual(next.vertices[1]);
    }
  });

  it('suspends on a tool and restores on Escape without moving the centre', () => {
    const { port, seen } = recording();
    const selected = step(
      idleSession(),
      { type: 'select-tool', tool: 'polygon' },
      port,
    );
    applyGesture(selected.gesture, port);
    expect(selected.session.phase).toBe('drawing');
    expect(seen).toEqual(['suspend']);
    const before = { ...selected.session };
    const moved = step(
      selected.session,
      { type: 'arrow', key: 'ArrowRight' },
      port,
    );
    expect(moved.session.crosshairX).toBe(before.crosshairX + ARROW_STEP_PX);
    expect(seen).toEqual(['suspend']);
    const escaped = step(moved.session, { type: 'escape' }, port);
    applyGesture(escaped.gesture, port);
    expect(escaped.session.phase).toBe('idle');
    expect(seen).toEqual(['suspend', 'restore']);
  });

  it('places and closes a polygon from the keyboard and from touch', () => {
    const { port } = recording();
    let session = step(
      idleSession(),
      { type: 'select-tool', tool: 'polygon' },
      port,
    ).session;
    session = step(session, { type: 'enter' }, port).session;
    session = step(session, { type: 'arrow', key: 'ArrowRight' }, port).session;
    session = step(session, { type: 'enter' }, port).session;
    session = step(session, { type: 'arrow', key: 'ArrowDown' }, port).session;
    session = step(session, { type: 'enter' }, port).session;
    expect(session.vertices).toHaveLength(3);
    session = step(session, { type: 'focus-knob', index: 0 }, port).session;
    session = step(session, { type: 'enter' }, port).session;
    expect(session.closed).toBe(true);
    expect(session.phase).toBe('editing');

    let touch = step(
      idleSession(),
      { type: 'select-tool', tool: 'polygon' },
      port,
    ).session;
    for (const point of [
      { x: 40, y: 40 },
      { x: 120, y: 40 },
      { x: 120, y: 120 },
    ]) {
      touch = step(
        touch,
        { type: 'pointer', ...point, pointerType: 'touch' },
        port,
      ).session;
    }
    touch = step(
      touch,
      { type: 'pointer', x: 40, y: 40, pointerType: 'touch' },
      port,
    ).session;
    expect(touch.closed).toBe(true);
    expect(touch.vertices).toHaveLength(3);
  });

  it('moves a focused knob by arrow and by drag', () => {
    const { port } = recording();
    let session = step(
      idleSession(),
      { type: 'select-tool', tool: 'polygon' },
      port,
    ).session;
    session = step(
      session,
      { type: 'pointer', x: 40, y: 40, pointerType: 'pen' },
      port,
    ).session;
    session = step(session, { type: 'focus-knob', index: 0 }, port).session;
    const before = session.vertices[0];
    session = step(session, { type: 'arrow', key: 'ArrowRight' }, port).session;
    expect(session.vertices[0]?.longitude).toBeGreaterThan(
      before?.longitude ?? 0,
    );
    session = step(
      session,
      { type: 'drag-knob', index: 0, x: 80, y: 90 },
      port,
    ).session;
    expect(session.vertices[0]?.longitude).toBe(
      port.unproject({ x: 80, y: 90 }).longitude,
    );
    expect(session.vertices[0]?.latitude).toBe(
      port.unproject({ x: 80, y: 90 }).latitude,
    );
    expect(session.vertices[0]?.id).toBe(before?.id);
  });

  it('places a radius pin from Enter and does not require a mouse pointer', () => {
    const { port } = recording();
    let session = step(
      idleSession(),
      { type: 'select-tool', tool: 'radius' },
      port,
    ).session;
    session = step(session, { type: 'enter' }, port).session;
    expect(session.pin).not.toBeNull();
    session = step(
      session,
      { type: 'preset', mode: 'distance', cutoff: 1000 },
      port,
    ).session;
    expect(session.mode).toBe('distance');
    expect(session.cutoff).toBe(1000);
  });

  it('suspends again when a tool is chosen after submission or refusal', () => {
    const { port, seen } = recording();
    const drawing = step(
      idleSession(),
      { type: 'select-tool', tool: 'radius' },
      port,
    );
    applyGesture(drawing.gesture, port);
    const submitted = step(drawing.session, { type: 'submit' }, port);
    applyGesture(submitted.gesture, port);
    const again = step(
      submitted.session,
      { type: 'select-tool', tool: 'travel' },
      port,
    );
    applyGesture(again.gesture, port);
    const refused = step(again.session, { type: 'refuse' }, port);
    applyGesture(refused.gesture, port);
    const third = step(
      refused.session,
      { type: 'select-tool', tool: 'polygon' },
      port,
    );
    applyGesture(third.gesture, port);
    expect(seen).toEqual([
      'suspend',
      'restore',
      'suspend',
      'restore',
      'suspend',
    ]);
  });
});
