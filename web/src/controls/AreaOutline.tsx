/**
 * Vertex overlay and the returned outline, inside the left-to-right Stage.
 * A refused pin draws no circle. The strong line is only a refused polygon.
 */
import {
  useEffect,
  useRef,
  type KeyboardEvent,
  type PointerEvent,
} from 'react';

import type { PinInput } from './area-request';
import type { MapPort } from './draw-session';
import { circleBoundary } from '../stage/layers/area-filter';
import { text, type Language } from '../i18n';
import {
  dispatch,
  restoreOnUnmount,
  setFrame,
  usePort,
  useViewRevision,
} from '../state/area-actions';
import { useArea } from '../state/store';

export function AreaOutline({ language }: { language: Language }) {
  const host = useRef<HTMLDivElement>(null);
  const crosshair = useRef<HTMLButtonElement>(null);
  const area = useArea();
  const session = area.session;
  const presented = area.presented;

  useEffect(() => {
    const node = host.current;
    const width = node?.clientWidth ?? 0;
    const height = node?.clientHeight ?? 0;
    setFrame(width > 0 ? width : 320, height > 0 ? height : 320);
    return () => restoreOnUnmount();
  }, []);

  useEffect(() => {
    if (session.phase !== 'drawing' && session.phase !== 'editing') return;
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      dispatch({ type: 'escape' });
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [session.phase]);

  useEffect(() => {
    if (session.phase === 'drawing' && session.focusedKnob === null) {
      crosshair.current?.focus();
    }
  }, [
    session.phase,
    session.tool,
    session.vertices.length,
    session.focusedKnob,
  ]);

  const port = usePort();
  useViewRevision();
  const drawing = session.phase === 'drawing' || session.phase === 'editing';
  const ring = outlineRing(presented?.outline ?? null);
  const strong = presented?.line === 'strong' ? presented.ownRing : [];
  const accent = presented?.line === 'accent' && ring ? ring : [];
  const circle =
    presented?.line === 'accent' && presented.outline?.type === 'Circle'
      ? circleBoundary(
          presented.outline.coordinates,
          presented.outline.radius_m,
        ).map(([longitude, latitude]) => ({ longitude, latitude }))
      : [];
  const progress =
    drawing && session.vertices.length > 1 ? closedRing(session) : [];

  return (
    <div
      ref={host}
      className={drawing ? 'area-overlay is-live' : 'area-overlay'}
      data-part="area-overlay"
      data-phase={session.phase}
      data-closed={session.closed ? 'yes' : 'no'}
      onPointerDown={(event) => {
        if (!drawing || event.button !== 0 || !event.isPrimary) return;
        if (
          event.target instanceof Element &&
          event.target.closest('.draw-knob')
        ) {
          return;
        }
        placePointer(event);
      }}
    >
      <svg className="area-lines" aria-hidden="true">
        {accent.length > 0 && port ? (
          <g data-part="outline" data-line="accent">
            <polyline
              className="area-line-casing"
              points={toPoints(accent, port)}
            />
            <polyline
              className="area-line-accent"
              points={toPoints(accent, port)}
            />
          </g>
        ) : null}
        {circle.length > 0 && port ? (
          <g data-part="outline" data-line="accent" data-outline="circle">
            <polyline
              className="area-line-casing"
              points={toPoints(circle, port)}
            />
            <polyline
              className="area-line-accent"
              points={toPoints(circle, port)}
            />
          </g>
        ) : null}
        {strong.length > 0 && port ? (
          <g data-part="outline" data-line="strong">
            <polyline
              className="area-line-strong"
              points={toPoints(strong, port)}
            />
          </g>
        ) : null}
        {progress.length > 1 && port ? (
          <polyline
            data-part="progress-ring"
            className="area-line-accent"
            points={toPoints(progress, port)}
          />
        ) : null}
      </svg>
      {port
        ? session.vertices.map((vertex, index) => {
            const screen = port.project(vertex);
            return (
              <button
                key={vertex.id}
                type="button"
                className="draw-knob"
                data-part="knob"
                data-index={index}
                style={{
                  insetInlineStart: `${screen.x}px`,
                  insetBlockStart: `${screen.y}px`,
                }}
                aria-label={text(language, 'draw.vertex')}
                onClick={(event) => {
                  const node = event.currentTarget;
                  if (node.dataset.suppressClick === 'yes') {
                    delete node.dataset.suppressClick;
                    return;
                  }
                  dispatch({ type: 'focus-knob', index });
                  dispatch({ type: 'select-knob', index });
                  if (
                    index === 0 &&
                    session.vertices.length >= 3 &&
                    !session.closed
                  ) {
                    dispatch({ type: 'enter' });
                  }
                }}
                onFocus={() => dispatch({ type: 'focus-knob', index })}
                onKeyDown={(event) => onControlKey(event)}
                onPointerDown={(event) => beginDrag(event)}
                onPointerMove={(event) => dragKnob(event, index)}
                onPointerUp={(event) => endDrag(event)}
                onPointerCancel={(event) => endDrag(event)}
                onLostPointerCapture={(event) => endDrag(event)}
              />
            );
          })
        : null}
      {presented?.showPin && area.ownPin && port ? (
        <span
          className="draw-pin"
          data-part="pin"
          style={pinStyle(area.ownPin, port)}
          aria-label={text(language, 'draw.pin')}
        />
      ) : null}
      {drawing ? (
        <button
          ref={crosshair}
          type="button"
          className="draw-crosshair"
          data-part="crosshair"
          style={{
            insetInlineStart: `${session.crosshairX}px`,
            insetBlockStart: `${session.crosshairY}px`,
          }}
          aria-label={text(language, 'draw.crosshair')}
          onFocus={() => dispatch({ type: 'focus-knob-clear' })}
          onKeyDown={(event) => onControlKey(event)}
        />
      ) : null}
    </div>
  );
}

function placePointer(event: PointerEvent<HTMLDivElement>): void {
  const rect = event.currentTarget.getBoundingClientRect();
  const kind =
    event.pointerType === 'touch'
      ? 'touch'
      : event.pointerType === 'pen'
        ? 'pen'
        : 'mouse';
  dispatch({
    type: 'pointer',
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
    pointerType: kind,
  });
}

function beginDrag(event: PointerEvent<HTMLButtonElement>): void {
  event.stopPropagation();
  if (event.button !== 0 || !event.isPrimary) return;
  const node = event.currentTarget;
  delete node.dataset.dragged;
  delete node.dataset.suppressClick;
  node.dataset.activePointer = String(event.pointerId);
  if (typeof node.setPointerCapture === 'function') {
    node.setPointerCapture(event.pointerId);
  }
}

function endDrag(event: PointerEvent<HTMLButtonElement>): void {
  const node = event.currentTarget;
  if (node.dataset.activePointer !== String(event.pointerId)) return;
  if (node.dataset.dragged === 'yes') node.dataset.suppressClick = 'yes';
  delete node.dataset.dragged;
  delete node.dataset.activePointer;
  if (
    typeof node.hasPointerCapture === 'function' &&
    node.hasPointerCapture(event.pointerId) &&
    typeof node.releasePointerCapture === 'function'
  ) {
    node.releasePointerCapture(event.pointerId);
  }
}

function dragKnob(event: PointerEvent<HTMLButtonElement>, index: number): void {
  const node = event.currentTarget;
  if (node.dataset.activePointer !== String(event.pointerId)) return;
  const overlay = event.currentTarget.closest('.area-overlay');
  if (!(overlay instanceof HTMLElement)) return;
  const rect = overlay.getBoundingClientRect();
  node.dataset.dragged = 'yes';
  if (typeof node.setPointerCapture === 'function') {
    node.setPointerCapture(event.pointerId);
  }
  dispatch({
    type: 'drag-knob',
    index,
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  });
}

function onControlKey(event: KeyboardEvent<HTMLButtonElement>): void {
  if (
    event.key === 'ArrowUp' ||
    event.key === 'ArrowDown' ||
    event.key === 'ArrowLeft' ||
    event.key === 'ArrowRight'
  ) {
    event.preventDefault();
    dispatch({ type: 'arrow', key: event.key });
    return;
  }
  if (event.key === 'Enter') {
    event.preventDefault();
    dispatch({ type: 'enter' });
  }
}

function closedRing(session: {
  vertices: readonly PinInput[];
  closed: boolean;
}): readonly PinInput[] {
  if (!session.closed) return session.vertices;
  const first = session.vertices[0];
  if (!first) return session.vertices;
  return [...session.vertices, first];
}

export function outlineRing(
  outline: { type: string; coordinates: unknown } | null,
): readonly PinInput[] | null {
  if (!outline || outline.type !== 'Polygon') return null;
  const rings = outline.coordinates;
  if (!Array.isArray(rings)) return null;
  const ring = rings[0];
  if (!Array.isArray(ring)) return null;
  const points: PinInput[] = [];
  for (const pair of ring) {
    if (!Array.isArray(pair)) continue;
    const longitude = pair[0];
    const latitude = pair[1];
    if (typeof longitude !== 'number' || typeof latitude !== 'number') continue;
    points.push({ longitude, latitude });
  }
  return points;
}

export function toPoints(vertices: readonly PinInput[], port: MapPort): string {
  return vertices
    .map((vertex) => {
      const screen = port.project(vertex);
      return `${screen.x},${screen.y}`;
    })
    .join(' ');
}

function pinStyle(
  pin: PinInput,
  port: MapPort,
): {
  insetInlineStart: string;
  insetBlockStart: string;
} {
  const screen = port.project(pin);
  return {
    insetInlineStart: `${screen.x}px`,
    insetBlockStart: `${screen.y}px`,
  };
}
