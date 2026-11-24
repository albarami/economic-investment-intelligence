/**
 * Narrow port built inside the Stage from the live map handle.
 * Only project and unproject cross, with the gesture calls.
 * The map object stays on the stage side of the handle.
 * There is no screen-fraction projection in production.
 */
import type { MapPort } from '../controls/draw-session';
import type { MapHandle } from './map-boot';

/** Camera hop for a located address: a small circle fitted like an outline. */
const LOCATE_RADIUS_M = 300;

export function portFromHandle(
  handle: MapHandle,
  resetControls: () => void = () => undefined,
): MapPort {
  return {
    recentre() {
      resetControls();
      handle.camera?.('recentre');
    },
    focusPoint(point) {
      handle.focusArea?.({
        type: 'Circle',
        coordinates: [point.longitude, point.latitude],
        radius_m: LOCATE_RADIUS_M,
      });
    },
    project(vertex) {
      return handle.project(vertex);
    },
    unproject(point) {
      return handle.unproject(point);
    },
    suspendGestures() {
      handle.suspendGestures();
    },
    restoreGestures() {
      handle.restoreGestures();
    },
    centre() {
      return handle.centre();
    },
  };
}
