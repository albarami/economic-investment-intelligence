// The optional photoreal mode. The control stays hidden unless the page's
// own server reports that a key is configured. The browser only ever calls
// the page's origin; the server adds the key.
import { MapLibreOverlay } from '@deck.gl/maplibre';
import type { Map as MapLibreMap } from 'maplibre-gl';
import { bind, lang, t } from './i18n';
import {
  PER_VIEW_BUDGET,
  SCREEN_SPACE_ERROR,
  aggregateCopyrights,
  budgetedTileFetch,
  copyrightFromTile,
  holdView,
} from './photoreal.mjs';
import { token } from './tokens';

const BASEMAP_SOURCE = 'protomaps';
// The open buildings archive is part of the open basemap: hidden as well.
const BUILDINGS_SOURCE = 'buildings';
const MAX_PITCH = 55;
const PHOTOREAL_PITCH = 60;

function logo(): SVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 74 24');
  svg.setAttribute('width', '74');
  svg.setAttribute('height', '24');
  svg.setAttribute('role', 'img');
  const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
  title.textContent = 'Google';
  const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  text.setAttribute('y', '18');
  text.setAttribute('font-size', '18');
  text.setAttribute('font-family', 'IBM Plex Sans, sans-serif');
  const colours = [
    token('--eii-mark-blue'),
    token('--eii-mark-red'),
    token('--eii-mark-yellow'),
    token('--eii-mark-blue'),
    token('--eii-mark-green'),
    token('--eii-mark-red'),
  ];
  for (const [index, letter] of [...'Google'].entries()) {
    const span = document.createElementNS(
      'http://www.w3.org/2000/svg',
      'tspan',
    );
    span.setAttribute('fill', colours[index] ?? token('--eii-mark-blue'));
    span.textContent = letter;
    text.append(span);
  }
  svg.append(title, text);
  return svg;
}

export function mountPhotoreal(
  map: MapLibreMap,
  end: HTMLElement,
  attribution: HTMLElement,
): void {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'control';
  button.dataset.control = 'photoreal';
  button.hidden = true;
  button.dataset.word = '';
  button.setAttribute('aria-pressed', 'false');
  let on = false;
  const paintLabel = () => {
    button.textContent = t(on ? 'photoreal.hide' : 'photoreal.show');
    button.lang = lang();
  };
  bind(paintLabel);
  end.append(button);

  const credit = document.createElement('p');
  credit.className = 'photoreal-credit';
  credit.dataset.part = 'photoreal-credit';
  credit.hidden = true;
  credit.lang = 'en';
  credit.dir = 'ltr';
  attribution.insertAdjacentElement('afterend', credit);

  let overlay: MapLibreOverlay | null = null;
  let hidden: string[] = [];
  const notices: string[] = [];
  let tileset: {
    options: { loadTiles: boolean; maximumScreenSpaceError: number };
  } | null = null;
  const fetchWithinBudget = budgetedTileFetch({
    transport: (url, init) => requestBytes(url, init),
    used: async () => {
      const body = await requestJson('/photoreal/status');
      return typeof body.session === 'number' ? body.session : PER_VIEW_BUDGET;
    },
    onHold: () => {
      if (tileset) holdView(tileset);
    },
  });

  const showCredit = () => {
    credit.replaceChildren(logo());
    const line = document.createElement('span');
    const ordered = aggregateCopyrights(notices);
    line.textContent =
      ordered.length === 0 ? t('photoreal.credit') : ordered.join(' · ');
    credit.append(line);
    credit.hidden = false;
  };

  const hideBasemap = () => {
    hidden = [];
    for (const layer of map.getStyle().layers ?? []) {
      const source = 'source' in layer ? layer.source : undefined;
      if (
        source === BASEMAP_SOURCE ||
        source === BUILDINGS_SOURCE ||
        layer.id === 'background' ||
        layer.id === 'coast'
      ) {
        map.setLayoutProperty(layer.id, 'visibility', 'none');
        hidden.push(layer.id);
      }
    }
  };

  const restore = () => {
    for (const id of hidden) {
      if (map.getLayer(id) !== undefined) {
        map.setLayoutProperty(id, 'visibility', 'visible');
      }
    }
    hidden = [];
    overlay?.finalize();
    overlay = null;
    map.setMaxPitch(MAX_PITCH);
    credit.hidden = true;
    credit.replaceChildren();
    on = false;
    button.setAttribute('aria-pressed', 'false');
    paintLabel();
  };

  button.addEventListener('click', async () => {
    if (overlay !== null) {
      restore();
      return;
    }
    const { Tile3DLayer } = await import('@deck.gl/geo-layers');
    hideBasemap();
    notices.length = 0;
    overlay = new MapLibreOverlay({
      interleaved: true,
      layers: [
        new Tile3DLayer({
          id: 'photoreal',
          data: `${window.location.origin}/photoreal/root.json`,
          loadOptions: {
            fetch: fetchWithinBudget,
            tileset: { maximumScreenSpaceError: SCREEN_SPACE_ERROR },
          },
          onTilesetLoad: (loaded) => {
            tileset = loaded as NonNullable<typeof tileset>;
          },
          onTileLoad: (tile) => {
            notices.push(...copyrightFromTile(tile));
            showCredit();
          },
          onTileError: () => {
            showCredit();
          },
        }),
      ],
    });
    map.addControl(overlay);
    // The skyline views of the photoreal mode look at sixty degrees; the
    // open map keeps DES-49's fifty-five.
    map.setMaxPitch(PHOTOREAL_PITCH);
    on = true;
    button.setAttribute('aria-pressed', 'true');
    paintLabel();
    showCredit();
  });

  // The capture command of the photoreal mode drives it through these.
  if (window.__look !== undefined) {
    window.__look.photoreal = {
      toggle: () => button.click(),
      state: () => {
        const set = tileset as {
          options: { loadTiles: boolean };
          isLoaded?: () => boolean;
        } | null;
        return {
          on,
          loaded: set?.isLoaded?.() === true,
          held: set !== null && set.options.loadTiles === false,
        };
      },
    };
  }
  const request = new XMLHttpRequest();
  request.open('GET', '/photoreal/status');
  request.onload = () => {
    if (request.status < 200 || request.status >= 300) return;
    try {
      const body = JSON.parse(request.responseText) as { available?: boolean };
      if (body.available === true) button.hidden = false;
    } catch {
      /* a bad status body leaves the control hidden */
    }
  };
  request.send();
}

function requestJson(url: string): Promise<{ session?: number }> {
  return new Promise((resolve) => {
    const request = new XMLHttpRequest();
    request.open('GET', url);
    request.onload = () => {
      try {
        resolve(JSON.parse(request.responseText) as { session?: number });
      } catch {
        resolve({});
      }
    };
    request.onerror = () => resolve({});
    request.send();
  });
}

function requestBytes(url: string, init?: RequestInit): Promise<Response> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open('GET', String(url));
    request.responseType = 'arraybuffer';
    const abort = () => request.abort();
    init?.signal?.addEventListener('abort', abort);
    request.onload = () => {
      init?.signal?.removeEventListener('abort', abort);
      const headers = new Headers();
      const type = request.getResponseHeader('content-type');
      if (type !== null) headers.set('content-type', type);
      const bytes = request.response;
      resolve(
        new Response(bytes instanceof ArrayBuffer ? bytes : null, {
          status: request.status,
          headers,
        }),
      );
    };
    request.onerror = () => {
      init?.signal?.removeEventListener('abort', abort);
      reject(new Error('tile request failed'));
    };
    request.onabort = () => {
      init?.signal?.removeEventListener('abort', abort);
      reject(new Error('tile request aborted'));
    };
    request.send();
  });
}
