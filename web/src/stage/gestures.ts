/**
 * MapLibre handler names read from the installed 6.17.0 typings
 * (DragPanHandler.disable and the Map handler fields) and recorded
 * in web/REFERENCE_NOTES.md. The handle never returns the map object.
 */

export const GESTURE_HANDLER_NAMES = [
  'dragPan',
  'scrollZoom',
  'boxZoom',
  'dragRotate',
  'doubleClickZoom',
  'touchZoomRotate',
  'touchPitch',
  'keyboard',
] as const;

export type GestureHandlerName = (typeof GESTURE_HANDLER_NAMES)[number];

export interface GestureHandler {
  disable(): void;
  enable(): void;
}

export type GestureBag = Record<GestureHandlerName, GestureHandler>;

export function suspendNamed(handlers: GestureBag): void {
  for (const name of GESTURE_HANDLER_NAMES) handlers[name].disable();
}

export function restoreNamed(handlers: GestureBag): void {
  for (const name of GESTURE_HANDLER_NAMES) handlers[name].enable();
}
