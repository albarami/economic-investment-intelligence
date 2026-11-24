/**
 * Fixture entry for the built credit-place scan (S3-T16 box 8).
 * Mounts the production Stage with an injected map starter. The scan
 * supplies the runtime credit on the window before this file runs.
 */
import { createRoot } from 'react-dom/client';

import { Stage } from '../../src/stage/Stage';

const ROOT_ID = 'credit-place-root';
const CREDIT_GLOBAL = '__EII_CREDIT_PLACE__';

type CreditReport = (value: string) => void;

function runtimeCredit(): string {
  const holder = window as unknown as Record<string, unknown>;
  const value = holder[CREDIT_GLOBAL];
  return typeof value === 'string' ? value : '';
}

function startMap(container: HTMLElement, style: unknown) {
  void container;
  void style;
  return {
    bind() {
      return undefined;
    },
    unbind() {
      return undefined;
    },
    project() {
      return { x: 0, y: 0 };
    },
    unproject() {
      return { longitude: 0, latitude: 0 };
    },
    suspendGestures() {
      return undefined;
    },
    restoreGestures() {
      return undefined;
    },
    centre() {
      return { longitude: 0, latitude: 0 };
    },
    bindView() {
      return undefined;
    },
    unbindView() {
      return undefined;
    },
    remove() {
      return undefined;
    },
    mountOverlay() {
      return undefined;
    },
    setMode(mode: string, report: CreditReport) {
      if (mode === 'satellite') report(runtimeCredit());
      return Promise.resolve();
    },
  };
}

const root = document.getElementById(ROOT_ID);
if (!root) throw new Error('credit-place-root-missing');

createRoot(root).render(
  <Stage
    language="en"
    theme="dark"
    extractUrl="/SYN-map.pmtiles"
    mapStarter={startMap}
  />,
);
