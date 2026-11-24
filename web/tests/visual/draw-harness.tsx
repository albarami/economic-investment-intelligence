/**
 * Browser harness for area drawing. Production never imports this file.
 * The fetch stand-in is invented. It is not a route.
 */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-sans-arabic/400.css';
import '@fontsource/ibm-plex-sans-arabic/500.css';
import '@fontsource/ibm-plex-sans-arabic/600.css';
import '../../src/styles/tokens.css';
import '../../src/styles/answer.css';
import type { FetchLike } from '../../src/api/areas';
import { catalogue } from '../../src/brief/catalogue';
import { AnswerShell } from '../../src/shell/AnswerShell';
import { registerPort } from '../../src/state/area-actions';
import { completeRegistry, factId } from '../fixtures/facts';
import { readablePortFromMeasure } from '../fixtures/plain-port';
import { rememberRequest } from './request-log';

registerPort(
  readablePortFromMeasure(() => {
    const node = document.querySelector('.stage');
    const width =
      node instanceof HTMLElement && node.clientWidth > 0
        ? node.clientWidth
        : 320;
    const height =
      node instanceof HTMLElement && node.clientHeight > 0
        ? node.clientHeight
        : 320;
    return { width, height };
  }),
);

const SHAPE_ID = 'ef'.repeat(32);
/** Travel has no isochrone in this stand-in. The ring is a readable circle. */
const TRAVEL_RING_M = 500;

let geometry: unknown = null;

interface StandInBody {
  geometry?: unknown;
  latitude?: unknown;
  longitude?: unknown;
  mode?: unknown;
  cutoff?: unknown;
}

function circleOutline(body: StandInBody): {
  type: 'Circle';
  coordinates: [number, number];
  radius_m: number;
} {
  const longitude = typeof body.longitude === 'number' ? body.longitude : 0.5;
  const latitude = typeof body.latitude === 'number' ? body.latitude : 0.5;
  const radius =
    body.mode === 'distance' && typeof body.cutoff === 'number'
      ? body.cutoff
      : TRAVEL_RING_M;
  return {
    type: 'Circle',
    coordinates: [longitude, latitude],
    radius_m: radius,
  };
}

const standIn: FetchLike = async (path, init) => {
  const body = JSON.parse(init.body) as StandInBody;
  if (path.endsWith('/shapes')) {
    rememberRequest(document.documentElement, 'shapeRequest', init.body);
    geometry = body.geometry ?? null;
    return { status: 201, json: async () => ({ shape_id: SHAPE_ID }) };
  }
  rememberRequest(document.documentElement, 'areaRequest', init.body);
  const outline = geometry ?? circleOutline(body);
  return {
    status: 200,
    json: async () => ({
      tool: 'make_area',
      call_id: 'INVENTED-call',
      engine: 'embedded',
      blocks: [],
      facts: [],
      caveat_keys: [],
      status: 'OK',
      release_id: 'rel-draw',
      payload: {
        area_id: 'area-draw',
        outline,
        units: {},
        snap_report: { opaque: true },
        record: {
          anchor_cell: null,
          traffic: 'free_flow',
          shape: geometry ? 'polygon' : 'circle',
        },
      },
    }),
  };
};

const params = new URLSearchParams(window.location.search);
const language = params.get('lang') === 'ar' ? 'ar' : 'en';
const theme = params.get('theme') === 'light' ? 'light' : 'dark';
const drawer = params.get('drawer') === '1';
const root = document.getElementById('root');
if (!root) throw new Error('drawing harness root is missing');

createRoot(root).render(
  <StrictMode>
    <AnswerShell
      language={language}
      theme={theme}
      extractUrl={null}
      areaClient={standIn}
      registry={drawer ? completeRegistry() : null}
      draft={
        drawer
          ? {
              catalogueVersion: catalogue.version,
              accountingPassed: true,
              subject: 'area',
              componentKey: 'foundation_note',
              props: [],
              directive: null,
              slots: [
                {
                  factId: factId(0),
                  provenance: 'public',
                  metric: 'people',
                },
              ],
            }
          : null
      }
    />
  </StrictMode>,
);
