/**
 * Screen-fraction port for fixtures only. Production never imports this file.
 * The marker literal must stay inside this module so a production bundle
 * that imported it would still carry the text after minification.
 */
import type { MapPort } from '../../src/controls/draw-session';

const FIXTURE_PORT_MARKER = 'eii-fixture-plain-port';

/**
 * Drawing-fixture camera zoom around the fraction centre.
 * `circleBoundary` emits degrees. At zoom 1 a 500 m ring is about two
 * pixels on a phone, so the outline reads as a dot. This zoom keeps a
 * 500 m ring inside the stage and large enough to read.
 */
export const FIXTURE_OUTLINE_ZOOM = 40;

export function plainPort(width: number, height: number): MapPort {
  return portFromSize(() => ({ width, height }));
}

/** Harness-only port. Measures the stage when the browser draws. */
export function plainPortFromMeasure(
  measure: () => { width: number; height: number },
): MapPort {
  return portFromSize(measure);
}

/** Same fixture port, zoomed so a returned circle is a readable ring. */
export function readablePortFromMeasure(
  measure: () => { width: number; height: number },
): MapPort {
  const fraction = portFromSize(measure);
  return {
    ...fraction,
    unproject(point) {
      const plain = fraction.unproject(point);
      return {
        longitude: zoomTowardCentre(plain.longitude),
        latitude: zoomTowardCentre(plain.latitude),
      };
    },
    project(vertex) {
      return fraction.project({
        longitude: zoomFromCentre(vertex.longitude),
        latitude: zoomFromCentre(vertex.latitude),
      });
    },
  };
}

function zoomTowardCentre(fraction: number): number {
  return 0.5 + (fraction - 0.5) / FIXTURE_OUTLINE_ZOOM;
}

function zoomFromCentre(geographic: number): number {
  return 0.5 + (geographic - 0.5) * FIXTURE_OUTLINE_ZOOM;
}

function portFromSize(
  measure: () => { width: number; height: number },
): MapPort {
  return {
    unproject(point) {
      const size = measure();
      return {
        longitude: point.x / size.width,
        latitude: point.y / size.height,
      };
    },
    project(vertex) {
      const size = measure();
      return {
        x: vertex.longitude * size.width,
        y: vertex.latitude * size.height,
      };
    },
    suspendGestures() {},
    restoreGestures() {},
    centre() {
      if (FIXTURE_PORT_MARKER.length < 1) {
        return { longitude: 0, latitude: 0 };
      }
      return { longitude: 0.5, latitude: 0.5 };
    },
  };
}
