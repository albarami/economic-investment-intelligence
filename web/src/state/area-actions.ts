/**
 * Applies a drawing event, then posts the typed body when the person submits.
 */
import type { FetchLike, AreaAnswer } from '../api/areas';
import { postMakeArea, postShape } from '../api/areas';
import {
  assembleDriveBody,
  assemblePinBody,
  assemblePlaceBody,
  assembleShapeBody,
  assembleShapeIdBody,
  driveBodyExact,
} from '../controls/area-request';
import {
  applyGesture,
  idleSession,
  step,
  type MapPort,
  type SessionEvent,
} from '../controls/draw-session';
import { presentAnswer } from '../controls/present';
import { filterPublicToOutline } from '../stage/layers/area-filter';
import { resetUseChoice } from '../stage/layers/land-use';
import type { LayerPayload } from '../stage/layers/payload';
import { useSyncExternalStore } from 'react';

import { clearArea, getArea, replaceArea } from './store';

let port: MapPort | null = null;
let portToken = 0;
let fetchImpl: FetchLike | null = null;
let clientOwned = false;
let layers: LayerPayload | null = null;
let selectedPoints: import('../api/areas').PublicPointIds | null = null;
let lastDriveBody: unknown = null;
let submitLock = false;
let requestGeneration = 0;
let selectedRequest: import('../api/public-opening').SelectedArea | null = null;

export function selectedAreaRequest() {
  return selectedRequest;
}
/** Set by a touch or pen Use pointerup; cleared by that gesture's click. */
let compatibilityClick = false;
const portListeners = new Set<() => void>();
let viewRevision = 0;
const viewListeners = new Set<() => void>();

export function registerPort(next: MapPort): number {
  portToken += 1;
  port = next;
  notifyPort();
  return portToken;
}

export function releasePort(token: number): void {
  if (token === 0 || token !== portToken) return;
  port?.restoreGestures();
  port = null;
  portToken = 0;
  notifyPort();
}

export function activePort(): MapPort | null {
  return port;
}

export function usePort(): MapPort | null {
  return useSyncExternalStore(subscribePort, activePort, activePort);
}

function subscribePort(listener: () => void): () => void {
  portListeners.add(listener);
  return () => portListeners.delete(listener);
}

function notifyPort(): void {
  for (const listener of portListeners) listener();
}

export function useViewRevision(): number {
  return useSyncExternalStore(
    subscribeView,
    readViewRevision,
    readViewRevision,
  );
}

function readViewRevision(): number {
  return viewRevision;
}

function subscribeView(listener: () => void): () => void {
  viewListeners.add(listener);
  return () => viewListeners.delete(listener);
}

/** Bumps the overlay after a map camera or resize event. No drawing event. */
export function publishViewRevision(): void {
  viewRevision += 1;
  for (const listener of viewListeners) listener();
}

export function registerFetch(next: FetchLike): void {
  fetchImpl = next;
  clientOwned = false;
}

/** Installs the application client only when nothing is registered yet. */
export function adoptAreaClient(next: FetchLike): boolean {
  if (fetchImpl) return false;
  fetchImpl = next;
  clientOwned = true;
  return true;
}

export function releaseOwnedClient(): void {
  if (!clientOwned) return;
  fetchImpl = null;
  clientOwned = false;
  compatibilityClick = false;
}

export function releaseAreaClient(): void {
  fetchImpl = null;
  clientOwned = false;
  compatibilityClick = false;
}

/** A new pointer gesture on Use. Drops a click arm from an earlier gesture. */
export function beginUsePointer(): void {
  compatibilityClick = false;
}

/**
 * Touch or pen pointerup on Use. Arms the compatibility click, then submits.
 * A mouse pointerup does not submit.
 */
export function submitUsePointer(pointerType: string): void {
  if (pointerType === 'mouse') return;
  compatibilityClick = true;
  void submitArea();
}

/**
 * Click on Use. A touch or pen compatibility click submits only through the
 * pointerup above. While the lock is held the click still enters submitArea,
 * which rejects it. Keyboard activation has detail 0 and always submits.
 */
export function submitUseClick(detail: number): void {
  if (detail === 0 || !compatibilityClick) {
    void submitArea();
    return;
  }
  compatibilityClick = false;
  if (submitLock) void submitArea();
}

export function registerLayers(next: LayerPayload | null): void {
  layers = next;
  const current = getArea();
  if (current.presented?.showLayers && current.presented.outline) {
    replaceArea({
      ...current,
      filtered: next
        ? filterPublicToOutline(next, current.presented.outline, selectedPoints)
        : null,
    });
  }
}

export function lastPostedDriveBody(): unknown {
  return lastDriveBody;
}

export function dispatch(event: SessionEvent): void {
  if (event.type === 'escape' || event.type === 'select-tool')
    requestGeneration += 1;
  if (event.type === 'escape' || event.type === 'select-tool')
    selectedRequest = null;
  const active = port;
  if (!active) return;
  const area = getArea();
  const result = step(area.session, event, active);
  if (
    result.session !== area.session &&
    event.type !== 'focus-knob' &&
    event.type !== 'focus-knob-clear' &&
    event.type !== 'escape' &&
    event.type !== 'select-tool'
  )
    requestGeneration += 1;
  applyGesture(result.gesture, active);
  replaceArea({ ...area, session: result.session });
}

export function restoreOnUnmount(): void {
  port?.restoreGestures();
}

export function setFrame(width: number, height: number): void {
  if (width < 1 || height < 1) return;
  const area = getArea();
  const fresh =
    area.session.phase === 'idle' && area.session.vertices.length === 0;
  replaceArea({
    ...area,
    session: {
      ...area.session,
      frameWidth: width,
      frameHeight: height,
      crosshairX: fresh ? width / 2 : area.session.crosshairX,
      crosshairY: fresh ? height / 2 : area.session.crosshairY,
    },
  });
}

export async function submitArea(): Promise<void> {
  if (submitLock) return;
  const active = port;
  const fetchLike = fetchImpl;
  if (!active || !fetchLike) return;
  submitLock = true;
  const generation = ++requestGeneration;
  const session = getArea().session;
  try {
    applyGesture('restore', active);
    if (session.tool === 'polygon') {
      await submitPolygon(fetchLike, generation);
      return;
    }
    await submitPin(fetchLike, generation);
  } catch {
    publish(
      {
        kind: 'refused',
        httpStatus: 422,
        code: 'INVALID_ARGUMENT',
      },
      session,
      generation,
    );
  } finally {
    submitLock = false;
  }
}

/** S3-T10's picker supplies only a selected gazetteer key and closed preset id. */
export async function submitPlaceArea(
  placeKey: string,
  presetId: string,
): Promise<void> {
  const body = assemblePlaceBody(placeKey, presetId);
  if (submitLock || !fetchImpl || !body) return;
  submitLock = true;
  const generation = ++requestGeneration;
  const session: ReturnType<typeof getArea>['session'] = {
    ...getArea().session,
    tool: body.mode === 'distance' ? 'radius' : 'travel',
    mode: body.mode,
    cutoff: body.cutoff,
    pin: null,
    vertices: [],
    closed: false,
  };
  try {
    port?.restoreGestures();
    const answer = await postMakeArea(body, fetchImpl);
    rememberSelection(answer, body, generation);
    publish(answer, session, generation, true);
  } catch {
    publish(
      { kind: 'refused', httpStatus: 422, code: 'INVALID_ARGUMENT' },
      session,
      generation,
      true,
    );
  } finally {
    submitLock = false;
  }
}

async function submitPolygon(
  fetchLike: FetchLike,
  generation: number,
): Promise<void> {
  const session = getArea().session;
  const shaped = assembleShapeBody(session.vertices);
  if (!shaped.ok || !session.closed) {
    replaceArea({
      ...getArea(),
      session: { ...session, phase: 'refused' },
      presented: {
        status: 'INVALID_ARGUMENT',
        caveatKeys: [],
        line: 'strong',
        outline: null,
        ownRing: session.vertices,
        showPin: false,
        showRefusal: true,
        showSummary: true,
        showLayers: false,
        anchorCell: null,
        shapeKind: 'polygon',
        mode: null,
        cutoff: null,
        freeFlow: false,
      },
      filtered: null,
    });
    return;
  }
  const posted = await postShape(shaped.body, fetchLike);
  if (generation !== requestGeneration) return;
  if (!posted.ok) {
    const envelope: AreaAnswer = {
      kind: 'refused',
      httpStatus: posted.status,
      code: 'shape_refused',
    };
    publish(envelope, session, generation);
    return;
  }
  const envelope = await postMakeArea(
    assembleShapeIdBody(posted.shapeId),
    fetchLike,
  );
  rememberSelection(envelope, assembleShapeIdBody(posted.shapeId), generation);
  publish(envelope, session, generation);
}

async function submitPin(
  fetchLike: FetchLike,
  generation: number,
): Promise<void> {
  const session = getArea().session;
  if (!session.pin || !session.mode || session.cutoff === null) {
    replaceArea({
      ...getArea(),
      session: { ...session, phase: 'refused' },
      presented: {
        status: 'INVALID_ARGUMENT',
        caveatKeys: [],
        line: 'none',
        outline: null,
        ownRing: [],
        showPin: session.pin !== null,
        showRefusal: true,
        showSummary: true,
        showLayers: false,
        anchorCell: null,
        shapeKind:
          session.mode === 'walk'
            ? 'walk'
            : session.mode === 'drive'
              ? 'drive'
              : 'radius',
        mode: session.mode,
        cutoff: session.cutoff,
        freeFlow: false,
      },
      filtered: null,
    });
    return;
  }
  const assembled = assemblePinBody(session.pin, session.mode, session.cutoff);
  if (!assembled.ok) return;
  if (assembled.body.mode === 'drive' && !driveBodyExact(assembled.body))
    return;
  if (assembled.body.mode === 'drive') {
    lastDriveBody = assembleDriveBody(session.pin, session.cutoff);
  }
  const envelope = await postMakeArea(assembled.body, fetchLike);
  rememberSelection(envelope, assembled.body, generation);
  publish(envelope, session, generation);
}

function rememberSelection(
  answer: AreaAnswer,
  request: import('../api/public-opening').SelectedArea,
  generation: number,
) {
  if (generation !== requestGeneration) return;
  selectedRequest =
    answer.kind === 'envelope' && answer.envelope.status === 'OK'
      ? request
      : null;
}

function publish(
  envelope: AreaAnswer,
  session: ReturnType<typeof getArea>['session'],
  generation: number,
  namedPlace = false,
): void {
  if (generation !== requestGeneration) return;
  const presented = presentAnswer(envelope, {
    kind: namedPlace ? 'place' : session.tool === 'polygon' ? 'polygon' : 'pin',
    mode: session.mode,
    cutoff: session.cutoff,
    ownRing: session.vertices,
    pin: session.pin,
  });
  const outline = presented.outline;
  selectedPoints =
    envelope.kind === 'envelope'
      ? (envelope.envelope.payload?.point_feature_ids ?? null)
      : null;
  const filtered =
    presented.showLayers && outline && layers
      ? filterPublicToOutline(
          layers,
          outline,
          envelope.kind === 'envelope'
            ? (envelope.envelope.payload?.point_feature_ids ?? null)
            : null,
        )
      : null;
  replaceArea({
    session: {
      ...session,
      phase: presented.showRefusal ? 'refused' : 'submitted',
    },
    presented,
    filtered,
    ownPin: session.pin,
  });
}

export function resetArea(): void {
  requestGeneration += 1;
  resetUseChoice();
  selectedRequest = null;
  selectedPoints = null;
  lastDriveBody = null;
  compatibilityClick = false;
  port?.restoreGestures();
  port?.recentre?.();
  clearArea();
  if (port) {
    replaceArea({
      ...getArea(),
      session: idleSession(
        getArea().session.frameWidth,
        getArea().session.frameHeight,
      ),
    });
  }
}
