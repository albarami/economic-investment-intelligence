/**
 * Drawing session. Vertices are typed points. No area is computed.
 * Arrow step is one named constant in screen pixels and is never displayed.
 * ASSUMPTION: 16 screen pixels per arrow press. Escape returns to idle.
 */
import type { AreaMode, PinInput } from './area-request';

/** Screen pixels per arrow press. Never displayed. ASSUMPTION. */
export const ARROW_STEP_PX = 16;

const KNOB_HIT_PX = 22;

export type ToolName = 'polygon' | 'radius' | 'travel';
export type Phase = 'idle' | 'drawing' | 'editing' | 'submitted' | 'refused';
export type PointerKind = 'mouse' | 'touch' | 'pen';

/** A vertex id stays put when the point moves, so focus and capture do too. */
export interface Vertex extends PinInput {
  id: string;
}

export interface Session {
  tool: ToolName | null;
  phase: Phase;
  vertices: readonly Vertex[];
  vertexSerial: number;
  closed: boolean;
  pin: PinInput | null;
  mode: AreaMode | null;
  cutoff: number | null;
  crosshairX: number;
  crosshairY: number;
  focusedKnob: number | null;
  selectedKnob: number | null;
  frameWidth: number;
  frameHeight: number;
}

export type SessionEvent =
  | { type: 'select-tool'; tool: ToolName }
  | {
      type: 'arrow';
      key: 'ArrowUp' | 'ArrowDown' | 'ArrowLeft' | 'ArrowRight';
    }
  | { type: 'enter' }
  | { type: 'pointer'; x: number; y: number; pointerType: PointerKind }
  | { type: 'preset'; mode: AreaMode; cutoff: number }
  | { type: 'escape' }
  | { type: 'focus-knob'; index: number }
  | { type: 'select-knob'; index: number }
  | { type: 'focus-knob-clear' }
  | { type: 'drag-knob'; index: number; x: number; y: number }
  | { type: 'submit' }
  | { type: 'refuse' };

export interface MapPort {
  recentre?(): void;
  /** Fly the camera to a located point. Absent where the port has no map. */
  focusPoint?(point: PinInput): void;
  unproject(point: { x: number; y: number }): PinInput;
  project(vertex: PinInput): { x: number; y: number };
  suspendGestures(): void;
  restoreGestures(): void;
  centre(): { longitude: number; latitude: number };
}

export type GestureCall = 'suspend' | 'restore' | 'none';

export function idleSession(width = 320, height = 320): Session {
  return {
    tool: null,
    phase: 'idle',
    vertices: [],
    vertexSerial: 0,
    closed: false,
    pin: null,
    mode: null,
    cutoff: null,
    crosshairX: width / 2,
    crosshairY: height / 2,
    focusedKnob: null,
    selectedKnob: null,
    frameWidth: width,
    frameHeight: height,
  };
}

export function step(
  session: Session,
  event: SessionEvent,
  port: MapPort,
): { session: Session; gesture: GestureCall } {
  const next = reduce(session, event, port);
  return {
    session: next,
    gesture: gestureFor(session.phase, next.phase, event.type),
  };
}

export function applyGesture(gesture: GestureCall, port: MapPort): void {
  if (gesture === 'suspend') port.suspendGestures();
  if (gesture === 'restore') port.restoreGestures();
}

function inactive(phase: Phase): boolean {
  return phase === 'idle' || phase === 'submitted' || phase === 'refused';
}

function gestureFor(
  before: Phase,
  after: Phase,
  event: SessionEvent['type'],
): GestureCall {
  if (event === 'escape' || event === 'submit') return 'restore';
  if (after === 'idle' || after === 'refused' || after === 'submitted') {
    if (before === 'drawing' || before === 'editing') return 'restore';
  }
  if (inactive(before) && (after === 'drawing' || after === 'editing')) {
    return 'suspend';
  }
  return 'none';
}

function reduce(session: Session, event: SessionEvent, port: MapPort): Session {
  if (event.type === 'escape')
    return idleSession(session.frameWidth, session.frameHeight);
  if (event.type === 'select-tool') {
    return {
      ...idleSession(session.frameWidth, session.frameHeight),
      tool: event.tool,
      phase: 'drawing',
    };
  }
  if (session.phase !== 'drawing' && session.phase !== 'editing')
    return session;
  if (event.type === 'arrow') return moveArrow(session, event.key, port);
  if (event.type === 'enter') return onEnter(session, port);
  if (event.type === 'pointer') return onPointer(session, event, port);
  if (event.type === 'preset') {
    return { ...session, mode: event.mode, cutoff: event.cutoff };
  }
  if (event.type === 'focus-knob')
    return { ...session, focusedKnob: event.index };
  if (event.type === 'select-knob')
    return { ...session, selectedKnob: event.index };
  if (event.type === 'focus-knob-clear')
    return session.focusedKnob === null
      ? session
      : { ...session, focusedKnob: null };
  if (event.type === 'drag-knob') return dragKnob(session, event, port);
  if (event.type === 'submit') return { ...session, phase: 'submitted' };
  if (event.type === 'refuse') return { ...session, phase: 'refused' };
  return session;
}

function moveArrow(
  session: Session,
  key: 'ArrowUp' | 'ArrowDown' | 'ArrowLeft' | 'ArrowRight',
  port: MapPort,
): Session {
  const dx =
    key === 'ArrowLeft'
      ? -ARROW_STEP_PX
      : key === 'ArrowRight'
        ? ARROW_STEP_PX
        : 0;
  const dy =
    key === 'ArrowUp'
      ? -ARROW_STEP_PX
      : key === 'ArrowDown'
        ? ARROW_STEP_PX
        : 0;
  if (session.focusedKnob !== null) {
    const vertex = session.vertices[session.focusedKnob];
    if (!vertex) return session;
    const screen = port.project(vertex);
    return dragKnob(
      session,
      {
        index: session.focusedKnob,
        x: clamp(screen.x + dx, session.frameWidth),
        y: clamp(screen.y + dy, session.frameHeight),
      },
      port,
    );
  }
  return {
    ...session,
    crosshairX: clamp(session.crosshairX + dx, session.frameWidth),
    crosshairY: clamp(session.crosshairY + dy, session.frameHeight),
  };
}

function onEnter(session: Session, port: MapPort): Session {
  if (
    session.tool === 'polygon' &&
    session.focusedKnob === 0 &&
    session.vertices.length >= 3
  ) {
    return {
      ...session,
      closed: true,
      phase: 'editing',
      focusedKnob: 0,
      selectedKnob: null,
    };
  }
  return placeAt(session, session.crosshairX, session.crosshairY, port);
}

function onPointer(
  session: Session,
  event: { x: number; y: number; pointerType: PointerKind },
  port: MapPort,
): Session {
  const hit = hitKnob(session, port, event.x, event.y);
  if (hit === 0 && session.vertices.length >= 3) {
    return {
      ...session,
      closed: true,
      phase: 'editing',
      focusedKnob: 0,
      selectedKnob: null,
    };
  }
  if (hit !== null) return { ...session, focusedKnob: hit };
  if (session.selectedKnob !== null) {
    return {
      ...dragKnob(
        session,
        { index: session.selectedKnob, x: event.x, y: event.y },
        port,
      ),
      focusedKnob: null,
    };
  }
  return placeAt(session, event.x, event.y, port);
}

function placeAt(
  session: Session,
  x: number,
  y: number,
  port: MapPort,
): Session {
  if (session.closed)
    return session.selectedKnob === null
      ? session
      : { ...session, selectedKnob: null };
  const point = port.unproject({ x, y });
  if (session.tool === 'polygon') {
    const vertexSerial = session.vertexSerial + 1;
    const vertex: Vertex = {
      ...point,
      id: `vtx-${vertexSerial}`,
    };
    return {
      ...session,
      vertexSerial,
      vertices: [...session.vertices, vertex],
      focusedKnob: null,
      selectedKnob: null,
      crosshairX: x,
      crosshairY: y,
    };
  }
  return {
    ...session,
    pin: point,
    crosshairX: x,
    crosshairY: y,
    focusedKnob: null,
    selectedKnob: null,
  };
}

function dragKnob(
  session: Session,
  event: { index: number; x: number; y: number },
  port: MapPort,
): Session {
  const next = session.vertices.map((vertex, index) =>
    index === event.index
      ? { ...vertex, ...port.unproject({ x: event.x, y: event.y }) }
      : vertex,
  );
  return {
    ...session,
    vertices: next,
    focusedKnob: event.index,
    selectedKnob: null,
  };
}

function hitKnob(
  session: Session,
  port: MapPort,
  x: number,
  y: number,
): number | null {
  for (let index = 0; index < session.vertices.length; index += 1) {
    const vertex = session.vertices[index];
    if (!vertex) continue;
    const screen = port.project(vertex);
    const dx = screen.x - x;
    const dy = screen.y - y;
    if (dx * dx + dy * dy <= KNOB_HIT_PX * KNOB_HIT_PX) return index;
  }
  return null;
}

function clamp(value: number, limit: number): number {
  if (value < 0) return 0;
  if (value > limit) return limit;
  return value;
}
