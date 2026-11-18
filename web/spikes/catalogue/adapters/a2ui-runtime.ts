import { createElement } from 'react';
import type { ComponentProps } from 'react';
import { A2uiSurface } from '@a2ui/react';

// A real browser and a validated application-owned surface are required.
// Never replace HTMLElement with a test shim to claim renderer parity.
export function renderSurface(
  surface: ComponentProps<typeof A2uiSurface>['surface'],
) {
  return createElement(A2uiSurface, { surface });
}
