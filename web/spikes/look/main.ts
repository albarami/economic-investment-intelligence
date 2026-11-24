import 'maplibre-gl/dist/maplibre-gl.css';
import '@fontsource/ibm-plex-sans/latin-400.css';
import '@fontsource/ibm-plex-sans/latin-500.css';
import '@fontsource/ibm-plex-sans/latin-600.css';
import '@fontsource/ibm-plex-sans-arabic/arabic-400.css';
import '@fontsource/ibm-plex-sans-arabic/arabic-500.css';
import '@fontsource/ibm-plex-sans-arabic/arabic-600.css';
import './tokens.css';
import './style.css';
import {
  CLUSTER_LAYER,
  FIRM_SOURCE,
  POINT_LAYER,
  POINT_RADIUS,
  mountEstablishments,
} from './establishments';
import { compactChip, rangeChip, referenceChip } from './fact-chip';
import { bind, dir, lang, refresh, setLang, t, type Lang } from './i18n';
import { mountPhotoreal } from './photoreal-mode';
import { readRelease, type Loaded } from './release';
import { Marker } from 'maplibre-gl';
import {
  buildShell,
  type Question,
  type Screen,
  type Shell,
  type Theme,
} from './shell';
import {
  LABEL_LAYERS,
  LIT_PREFIX,
  mountStage,
  type Free,
  type Stage,
} from './stage';
import { durationMs, token, tokenNumber } from './tokens';

const root = document.documentElement;
const params = new URLSearchParams(window.location.search);
const plant = params.get('plant') ?? '';
const systemReduced = window.matchMedia('(prefers-reduced-motion: reduce)');

const look: LookDiagnostics = {
  ready: false,
  failure: '',
  lang: 'en',
  theme: 'dark',
  mapTheme: 'dark',
  reduced: false,
  moving: false,
  litMode: '',
  lit: false,
  flipping: false,
  fontsReady: false,
  basemap: false,
  bearing: 0,
  pitch: 0,
  zoom: 0,
  units: 0,
  litLevels: () => [],
  litLayers: () => [],
  labelFields: () => [],
  labels: () => [],
  labelsUnder: () => [],
  brightCorners: () => [],
  litUnder: () => 0,
  districtNames: () => [],
  planted: false,
  rendered: async () => undefined,
  showBuildings: async () => undefined,
  screen: 'home',
  settled: false,
  fold: { brief: 'open', legend: 'open' },
  camera: async () => undefined,
  district: () => null,
  layers: () => [],
  sourceFeatures: () => 0,
};
window.__look = look;

let shell: Shell;
let stage: Stage;
let loaded: Loaded;
let paused = false;
// P2: the page opens on the home; ?answer=operate opens the answer screen
// of "Where should we operate?" directly (the captures and the tests).
let screen: Screen = params.get('answer') === 'operate' ? 'answer' : 'home';
let districtPlate: { element: HTMLElement; marker: Marker } | null = null;
let opening = false;
let openingToken = 0;
const animations: Animation[] = [];

function reduced(): boolean {
  if (plant === 'ignore-reduced-motion') return false;
  return paused || systemReduced.matches;
}

function routeLang(): Lang {
  return window.location.pathname.startsWith('/ar/') ? 'ar' : 'en';
}

function routeTheme(): Theme {
  return params.get('theme') === 'light' ? 'light' : 'dark';
}

// DES-139: a window that is not 1920 x 1080 CSS pixels shows the same
// composition, zoomed to fit; the wall itself is drawn at zoom 1.
function fitWall(): void {
  const zoom = Math.min(
    window.innerWidth / tokenNumber('--eii-wall-width'),
    window.innerHeight / tokenNumber('--eii-wall-height'),
  );
  root.style.setProperty('--eii-wall-zoom', String(zoom));
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function frame(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => resolve());
  });
}

function updateMotionState(): void {
  look.reduced = reduced();
  look.moving = opening || stage?.map.isMoving() === true;
  root.dataset.motion = look.reduced ? 'reduced' : 'full';
}

async function fontsReady(): Promise<void> {
  const loads: Promise<FontFace[]>[] = [];
  for (const weight of ['400', '500', '600']) {
    loads.push(document.fonts.load(`${weight} 28px "IBM Plex Sans"`, 'Aa'));
    loads.push(
      document.fonts.load(`${weight} 31px "IBM Plex Sans Arabic"`, 'عام'),
    );
  }
  await Promise.all(loads);
  await document.fonts.ready;
  look.fontsReady = true;
}

// DES-60: the City framing is computed from the free part of the Stage:
// below the top bar and clear of the Brief. The legend stands inside that
// part, at its lower inline-start corner; ruling L-119 item 1: the camera
// keeps every unit of the two highest classes out from under it, with one
// gap of margin. Ruling L-119 item 5: the top of the free part leaves one
// map label's height above the units as well, so that a place label at the
// north edge of the lit layer (Lusail) keeps clear of the top bar.
function free(): Free {
  const gap = tokenNumber('--eii-space-5');
  const zoom =
    Number.parseFloat(root.style.getPropertyValue('--eii-wall-zoom')) || 1;
  const bar = (shell.topbar[0] as HTMLElement).getBoundingClientRect();
  const brief = shell.brief.getBoundingClientRect();
  const key = shell.legend.getBoundingClientRect();
  const margin = gap * zoom;
  const avoid = [
    {
      left: key.left - margin,
      top: key.top - margin,
      right: key.right + margin,
      bottom: key.bottom + margin,
    },
  ];
  const safe = tokenNumber('--eii-safe-inline') * zoom;
  const top = bar.bottom + margin + tokenNumber('--eii-map-label-size') * zoom;
  const bottom = tokenNumber('--eii-safe-block') * zoom;
  // Ruling L-143 item 3: the City framing stops at a city scale, and keeps
  // the major place names clear of every plate on the Stage, with one gap
  // of margin. The planted case lets it search to street zoom, as before the
  // cap.
  const cap =
    plant === 'city-uncapped' ? 15 : tokenNumber('--eii-city-max-zoom');
  // Round 5e, E2: the four sides beyond the screen's edges count as plates
  // too, so every major place name stands wholly inside the screen.
  const far = Number.POSITIVE_INFINITY;
  const beyond = [
    { left: -far, top: -far, right: 0, bottom: far },
    { left: window.innerWidth, top: -far, right: far, bottom: far },
    { left: -far, top: -far, right: far, bottom: 0 },
    { left: -far, top: window.innerHeight, right: far, bottom: far },
  ];
  const plates = [...shell.topbar, shell.brief, shell.legend, shell.attribution]
    .map((element) => element.getBoundingClientRect())
    .filter((box) => box.width > 0 && box.height > 0)
    .map(({ left, top, right, bottom }) => ({ left, top, right, bottom }))
    .concat(beyond)
    .map((box) => ({
      left: box.left - margin,
      top: box.top - margin,
      right: box.right + margin,
      bottom: box.bottom + margin,
    }));
  const parts = { top, bottom, avoid, cap, plates };
  if (dir() === 'rtl') {
    return { ...parts, left: brief.right + margin, right: safe };
  }
  return {
    ...parts,
    left: safe,
    right: window.innerWidth - brief.left + margin,
  };
}

// Round 5g, G3: the planted buildings view pans until the bright corner
// nearest the middle of the screen sits at the middle of the legend.
function plantBrightOnLegend(): void {
  const corners = stage.brightCorners();
  const nearest = corners.reduce<{ x: number; y: number } | null>(
    (best, corner) => {
      const middle = {
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
      };
      if (best === null) return corner;
      const away = Math.hypot(corner.x - middle.x, corner.y - middle.y);
      const held = Math.hypot(best.x - middle.x, best.y - middle.y);
      return away < held ? corner : best;
    },
    null,
  );
  if (nearest === null) return;
  const lngLat = stage.map.unproject([nearest.x, nearest.y]);
  const box = shell.legend.getBoundingClientRect();
  const target = {
    x: (box.left + box.right) / 2,
    y: (box.top + box.bottom) / 2,
  };
  const middle = {
    x: stage.map.getCanvas().clientWidth / 2,
    y: stage.map.getCanvas().clientHeight / 2,
  };
  for (let step = 0; step < 8; step += 1) {
    const point = stage.map.project(lngLat);
    const dx = point.x - target.x;
    const dy = point.y - target.y;
    if (Math.hypot(dx, dy) < 1) break;
    stage.map.jumpTo({
      center: stage.map.unproject([middle.x + dx, middle.y + dy]),
    });
  }
}

function track(animation: Animation): Animation {
  animations.push(animation);
  return animation;
}

function answering(): boolean {
  return screen === 'answer';
}

// The camera of the screen: "City" for the answer, the skyline otherwise.
function place(mode: 'jump' | 'ease' | 'fly'): Promise<void> {
  if (answering()) return stage.frame(free(), mode);
  return stage.skyline(free(), mode === 'ease' ? 'fly' : mode);
}

function finishOpening(): void {
  openingToken += 1;
  stage.map.stop();
  stage.finishLightUp();
  for (const animation of animations.splice(0)) animation.finish();
  shell.brief.style.opacity = '';
  if (opening) void place('jump');
  if (answering() && stage.litLevels().some((level) => level < 1)) {
    stage.lightUp('instant', () => undefined);
  }
  stage.setPoints(answering());
  opening = false;
  plateWaits = false;
  look.lit = answering();
  look.settled = true;
  showData();
  updateMotionState();
}

// The data layer and its legend belong to the answer (P2): the home shows
// the real map alone.
function showData(): void {
  const on = answering();
  shell.legend.dataset.hide = on ? 'false' : 'true';
  showPlate();
  look.screen = screen;
  root.dataset.screen = screen;
  updateFold();
}

// V7: past district zoom the Brief and the legend fold to a slim strip and
// come back at city zoom. While the camera moves they hold their last state
// between the two zooms (no flicker); a camera at rest folds them from the
// fold zoom alone, so the City framing always lands open.
let folded = false;

// Round 5e, E1: the district plate is a word of the answer. Under motion it
// waits through the flight and the lighting and enters with the card
// (DES-12: the camera, the data and the words never move together); its
// entrance is tracked, so the end of the opening, which the captures wait
// for, has ended it too.
let plateWaits = false;
function showPlate(): void {
  districtPlate?.element.toggleAttribute(
    'hidden',
    !answering() || folded || plateWaits,
  );
}
function enterPlate(): void {
  plateWaits = false;
  showPlate();
  const element = districtPlate?.element;
  if (element === undefined || element.hidden) return;
  track(
    element.animate([{ opacity: 0 }, { opacity: 1 }], {
      duration: durationMs('--eii-dur-slow'),
      easing: token('--eii-ease-enter'),
    }),
  );
}

function updateFold(resting = true): void {
  const zoom = stage.map.getZoom();
  if (!answering()) folded = false;
  else if (plant === 'fold-stuck') folded = false;
  else if (zoom >= tokenNumber('--eii-fold-zoom')) folded = true;
  else if (resting || zoom <= tokenNumber('--eii-unfold-zoom')) folded = false;
  if (folded) root.dataset.fold = 'street';
  else delete root.dataset.fold;
  if (plant === 'legend-bare' || plant === 'fold-hides-table') plantFold();
  const state = folded ? 'folded' : 'open';
  look.fold = { brief: state, legend: state };
  showPlate();
}

// Round 5g: round 5's street fold, which hid the legend's breaks and its
// direction ('legend-bare') or its table ('fold-hides-table').
function plantFold(): void {
  const parts =
    plant === 'legend-bare'
      ? ['.legend-breaks', '.legend-direction']
      : ['.legend-table'];
  for (const selector of parts) {
    const part = shell.legend.querySelector<HTMLElement>(selector);
    if (part !== null) part.style.display = folded ? 'none' : '';
  }
}

function landCard(): void {
  enterPlate();
  shell.brief.style.opacity = '';
  track(
    shell.brief.animate(
      [
        { opacity: 0, translate: `0 ${token('--eii-space-4')}` },
        { opacity: 1, translate: '0 0' },
      ],
      {
        duration: durationMs('--eii-dur-slow'),
        easing: token('--eii-ease-enter'),
      },
    ),
  );
}

function enter(plate: HTMLElement, delay: number): void {
  track(
    plate.animate(
      [
        { opacity: 0, translate: `0 calc(-1 * ${token('--eii-space-4')})` },
        { opacity: 1, translate: '0 0' },
      ],
      {
        duration: durationMs('--eii-dur-slow'),
        delay,
        easing: token('--eii-ease-enter'),
        fill: 'backwards',
      },
    ),
  );
}

// Scene 0 of section 11: the real country holds for a moment, the camera
// flies to the city (--eii-dur-fly-long), then the lit layer fades in class
// by class from low to high (the one signature moment), then the card lands.
// The three steps never overlap (DES-12), and Pause motion, Reset or the
// system's reduced motion end the opening at its last frame.
async function runOpening(): Promise<void> {
  plateWaits = !reduced();
  showData();
  if (reduced()) {
    look.litMode = 'instant';
    await place('jump');
    if (answering()) stage.lightUp('instant', () => undefined);
    finishOpening();
    return;
  }
  const mine = (openingToken += 1);
  opening = true;
  look.lit = false;
  look.litMode = 'staged';
  updateMotionState();
  shell.brief.style.opacity = '0';
  const stagger = durationMs('--eii-stagger');
  const plates = answering()
    ? [...shell.topbar, shell.legend, shell.attribution]
    : [...shell.topbar, shell.attribution];
  plates.forEach((plate, index) => enter(plate, index * stagger));
  stage.country();
  await wait(durationMs('--eii-dur-fly-medium'));
  if (mine !== openingToken) return;
  await place('fly');
  if (mine !== openingToken) return;
  if (answering()) {
    await new Promise<void>((resolve) => {
      stage.lightUp('staged', resolve);
    });
    if (mine !== openingToken) return;
  }
  landCard();
  await wait(durationMs('--eii-dur-slow'));
  if (mine !== openingToken) return;
  finishOpening();
}

// P2: a question of the home. "Where should we operate?" asks for a place;
// the other three open a quiet state that is not yet answered.
function ask(question: Question): void {
  if (opening) finishOpening();
  if (question === 'operate' && plant === 'place-skipped') {
    void answer();
    return;
  }
  screen = question === 'operate' ? 'place' : 'notyet';
  shell.setScreen(screen, question);
  if (plant === 'notyet-blank' && screen === 'notyet') {
    shell.brief
      .querySelector<HTMLElement>('[data-card="notyet"]')
      ?.toggleAttribute('hidden', true);
  }
  showData();
  shell.brief
    .querySelector<HTMLElement>(
      `[data-card="${screen}"] .question, [data-card="${screen}"] [data-control="back"]`,
    )
    ?.focus();
}

// The place is chosen: the camera flies out to the city first, then the
// layer lights class by class, then the answer lands (DES-12: the camera and
// the data never move together). Under reduced motion it is a cut.
async function answer(): Promise<void> {
  if (opening) finishOpening();
  const mine = (openingToken += 1);
  screen = 'answer';
  shell.setScreen('answer', 'operate');
  if (reduced()) {
    await place('jump');
    finishOpening();
    shell.card.querySelector<HTMLElement>('[data-control="more"]')?.focus();
    return;
  }
  opening = true;
  plateWaits = true;
  look.lit = false;
  look.settled = false;
  shell.brief.style.opacity = '0';
  updateMotionState();
  await place('fly');
  if (mine !== openingToken) return;
  showData();
  enter(shell.legend, 0);
  await new Promise<void>((resolve) => {
    stage.lightUp('staged', resolve);
  });
  if (mine !== openingToken) return;
  stage.setPoints(true);
  landCard();
  await wait(durationMs('--eii-dur-slow'));
  if (mine !== openingToken) return;
  finishOpening();
  shell.card.querySelector<HTMLElement>('[data-control="more"]')?.focus();
}

// Back: from the answer the data goes out and the camera returns to the
// skyline; from a question it returns to the home at once.
function back(): void {
  if (opening) finishOpening();
  const from = screen;
  screen = 'home';
  shell.closeDrawer();
  shell.showTable(false);
  shell.setScreen('home', 'operate');
  if (from === 'answer') {
    stage.finishLightUp();
    if (plant !== 'back-keeps-data') {
      for (const step of [1, 2, 3, 4, 5]) stage.setClass(step, 0);
      stage.setPoints(false);
    }
    look.lit = false;
    void place(reduced() ? 'jump' : 'fly');
  }
  showData();
  shell.brief.querySelector<HTMLElement>('.question')?.focus();
}

function setTheme(theme: Theme): void {
  if (root.dataset.theme === theme) return;
  root.dataset.themeChange = '';
  root.dataset.theme = theme;
  const url = new URL(window.location.href);
  url.searchParams.set('theme', theme);
  window.history.replaceState(null, '', url);
  stage.restyle({ theme, reduced: reduced() });
  refresh();
  shell.setTheme(theme);
  look.theme = theme;
  look.mapTheme = theme;
  window.setTimeout(
    () => {
      delete root.dataset.themeChange;
    },
    durationMs(reduced() ? '--eii-dur-fast' : '--eii-dur-scene'),
  );
}

function toggleMotion(): void {
  paused = !paused;
  shell.setPaused(paused);
  if (paused && opening) finishOpening();
  if (paused) stage.map.stop();
  updateMotionState();
}

// DES-118: words fade out, the layout mirrors, words fade in; the numerals
// of every chip stay opaque and the Stage does not move; its labels change
// language without a reload (FE-59).
async function flip(): Promise<void> {
  if (look.flipping) return;
  look.flipping = true;
  const next: Lang = lang() === 'en' ? 'ar' : 'en';
  const fast = durationMs('--eii-dur-fast');
  if (!reduced()) {
    root.dataset.flip = 'out';
    await wait(fast);
  }
  setLang(next);
  root.lang = next;
  root.dir = dir();
  refresh();
  document.title = t('doc.title');
  window.history.replaceState(
    null,
    '',
    `/${next}/_look${window.location.search}`,
  );
  stage.restyle({ lang: next, reduced: reduced() });
  await frame();
  delete root.dataset.flip;
  if (!reduced()) await wait(fast);
  look.lang = next;
  look.flipping = false;
}

// DES-135 and the audits' F1 and F9: Reset first ends the opening, so no
// layer is left half lit and the Brief is never left hidden; it closes the
// source chain and the table view; then the camera returns to "City",
// as a cut under reduced motion.
function reset(): void {
  if (opening) finishOpening();
  shell.closeDrawer();
  shell.showTable(false);
  void place(reduced() ? 'jump' : 'ease');
}

function applyPlants(): void {
  // Exercise the range variant with release facts in the browser proof.
  if (plant === 'range-chip') {
    shell.legend
      .querySelector('.legend-breaks')
      ?.replaceChildren(
        rangeChip(
          loaded.fact('break-1'),
          loaded.fact('break-2'),
          shell.openDrawer,
        ),
      );
  }
  if (plant === 'stray-numeral') {
    const stray = document.createElement('p');
    stray.textContent = 'Scene 0';
    shell.legend.append(stray);
  }
  if (plant === 'class-word') {
    const word = document.createElement('p');
    word.textContent = lang() === 'ar' ? 'بيانات اصطناعية' : 'Synthetic data';
    shell.card.append(word);
  }
  if (plant === 'class-mark') {
    const number =
      shell.card.querySelector<HTMLElement>('[data-num]') ??
      shell.legend.querySelector<HTMLElement>('[data-num]');
    if (number !== null) number.style.textDecoration = 'underline dotted';
  }
  if (plant === 'no-attribution') shell.attribution.hidden = true;
  // Round 5g, finding 23: round 5's opaque top swatch.
  if (plant === 'swatch-opaque') {
    const top = shell.legend.querySelector<HTMLElement>(
      '.legend-scale .legend-swatch[data-step="5"]',
    );
    if (top !== null) top.style.backgroundColor = 'var(--eii-seq-5)';
  }
  // Round 5g, finding 22: a legend that names no date of the count.
  if (plant === 'legend-no-period')
    shell.legend.querySelector('.legend-period')?.remove();
  // Round 5g, finding 24: a fourth chip on the answer card.
  if (plant === 'fourth-chip') {
    while (shell.card.querySelectorAll('[data-chip]').length < 4)
      shell.card.append(compactChip(loaded.fact('break-1'), shell.openDrawer));
  }
  // Round 5g, finding 9: round 5's plate, one string tagged English.
  if (plant === 'attribution-one-string') {
    shell.attribution.lang = 'en';
    shell.attribution.dir = 'ltr';
    shell.attribution.textContent = `${t('attribution.credits')} · ${t('attribution.heights', 'en')}`;
  }
  if (plant === 'remote-asset') {
    const image = new Image();
    image.src = 'https://assets.invalid/look.png';
  }
}

// The two plants that need the settled map: a framing that carries a place
// label under the top bar's first plate, and a legend moved over the
// bright core. Without the extract there is neither label nor core.
async function applyMapPlants(): Promise<void> {
  if (plant === 'label-under-plate' || plant === 'label-off-edge') {
    await stage.rendered();
    const shown = stage.map.queryRenderedFeatures({ layers: LABEL_LAYERS });
    const geometry = shown[0]?.geometry;
    if (geometry?.type === 'Point') {
      // Ruling L-143 item 4: the pan comes from the plate's rectangle and the
      // label's projected point. Under pitch a screen shift is not an exact
      // pan, so the camera moves again until the point sits within a pixel
      // of the plate's middle. Round 5e, E2: the second plant moves the
      // label's point onto the screen's left edge, half the name off it.
      const [lng, lat] = geometry.coordinates as [number, number];
      const plate = (shell.topbar[0] as HTMLElement).getBoundingClientRect();
      const target =
        plant === 'label-off-edge'
          ? { x: 0, y: stage.map.project([lng, lat]).y }
          : {
              x: (plate.left + plate.right) / 2,
              y: (plate.top + plate.bottom) / 2,
            };
      const middle = {
        x: stage.map.getCanvas().clientWidth / 2,
        y: stage.map.getCanvas().clientHeight / 2,
      };
      for (let step = 0; step < 8; step += 1) {
        const point = stage.map.project([lng, lat]);
        const dx = point.x - target.x;
        const dy = point.y - target.y;
        if (Math.hypot(dx, dy) < 1) break;
        stage.map.jumpTo({
          center: stage.map.unproject([middle.x + dx, middle.y + dy]),
        });
      }
      await stage.rendered();
    }
  }
  if (plant === 'home-lit' && !answering()) {
    stage.lightUp('instant', () => undefined);
  }
  // Round 5f, F2: round 5's order, the establishment points moved to the top
  // of the style, over every label.
  if (plant === 'points-over-labels') {
    for (const id of [CLUSTER_LAYER, POINT_LAYER]) {
      if (stage.map.getLayer(id) !== undefined) stage.map.moveLayer(id);
    }
    // A firm layer under a name the fixed list never had, drawn last.
    if (
      stage.map.getSource(FIRM_SOURCE) !== undefined &&
      stage.map.getLayer('establishments-ring') === undefined
    ) {
      stage.map.addLayer({
        id: 'establishments-ring',
        type: 'circle',
        source: FIRM_SOURCE,
        paint: {
          'circle-radius': POINT_RADIUS,
          'circle-color': token('--eii-map-point'),
        },
      });
    }
  }
  if (plant === 'points-on-ramp') {
    for (const id of [CLUSTER_LAYER, POINT_LAYER]) {
      if (stage.map.getLayer(id) !== undefined)
        stage.map.setPaintProperty(id, 'circle-color', token('--eii-seq-5'));
    }
  }
  if (plant === 'no-point-key')
    shell.legend.querySelector('.legend-points')?.remove();
  if (plant === 'bracket-wraps') {
    const mark = shell.legend.querySelector<HTMLElement>('.legend-span-mark');
    if (mark !== null) {
      mark.style.whiteSpace = 'normal';
      mark.style.flexWrap = 'wrap';
      mark.style.justifyContent = 'flex-start';
      const word = mark.textContent ?? '';
      mark.textContent = `${word} ${word} ${word} ${word}`;
    }
  }
  if (plant === 'legend-over-core') {
    const corner = stage.brightCorners()[0];
    if (corner !== undefined) {
      const box = shell.legend.getBoundingClientRect();
      shell.legend.style.translate = `${corner.x - (box.left + box.right) / 2}px ${corner.y - (box.top + box.bottom) / 2}px`;
    }
  }
  look.planted = true;
}

// Round 5g: the establishment plants. 'types-everywhere' offers the type
// control at every zoom (round 5's control); 'types-no-heading' takes the
// list's heading away; 'card-reference-employees' sets the number of
// employees in an identifier chip; 'points-on-ramp' and 'no-point-key' act
// on the settled map (applyMapPlants).
function applyPointPlants(): void {
  const types = shell.legend.querySelector<HTMLElement>(
    '[data-control="types"]',
  );
  if (plant === 'types-everywhere' && types !== null) {
    const show = () => {
      types.hidden = false;
    };
    stage.map.on('zoom', show);
    show();
  }
  if (plant === 'types-no-heading' && types !== null) {
    types.addEventListener('click', () => {
      shell.legend.querySelector('.type-counts-title')?.remove();
    });
  }
  if (plant === 'card-reference-employees') {
    const openPoint = look.openPoint;
    look.openPoint = (key) => {
      openPoint?.(key);
      const row = shell.overlay.querySelector(
        '[data-part="point-card"] [data-field="field.employees"]',
      );
      const chip = row?.querySelector('[data-chip]');
      if (chip instanceof HTMLElement)
        chip.replaceWith(referenceChip(chip.textContent ?? ''));
    };
  }
}

// P1: a quiet plate on the map names the lit district (an area name from the
// basemap's own labels, never a building or business, and no figure). From
// district zoom the map's own labels name it, and the plate folds away.
function mountDistrict(): { element: HTMLElement; marker: Marker } | null {
  const place = loaded.release.district;
  if (place === null) return null;
  const element = document.createElement('p');
  element.className = 'district-plate';
  element.dataset.part = 'district';
  bind(() => {
    element.textContent = place[lang()];
    element.lang = lang();
    element.dir = dir();
  });
  element.hidden = screen !== 'answer';
  // Round 5e, E1: the planted band of round 5d, a plate in the map's flow
  // that fills the map's width with its name off the screen.
  if (plant === 'district-stretched') {
    element.style.position = 'relative';
    element.style.inlineSize = 'auto';
  }
  const marker = new Marker({ element, anchor: 'bottom' })
    .setLngLat([place.lon, place.lat])
    .addTo(stage.map);
  return { element, marker };
}

async function start(): Promise<void> {
  const language = routeLang();
  const theme = routeTheme();
  setLang(language);
  root.lang = language;
  root.dir = dir();
  root.dataset.theme = theme;
  look.lang = language;
  look.theme = theme;
  look.mapTheme = theme;
  updateMotionState();
  fitWall();
  window.addEventListener('resize', fitWall);
  systemReduced.addEventListener('change', () => {
    if (reduced() && opening) finishOpening();
    updateMotionState();
  });
  await fontsReady();
  document.title = t('doc.title');
  loaded = readRelease();
  if (plant === 'chainless-fact') {
    const first = loaded.facts[0];
    if (first !== undefined) first.chain = null;
  }
  look.basemap = loaded.release.basemap.present;
  shell = buildShell(
    {
      theme: setTheme,
      motion: toggleMotion,
      language: () => {
        void flip();
      },
      reset,
      question: ask,
      place: () => {
        void answer();
      },
      back,
    },
    loaded,
  );
  shell.setScreen(screen, 'operate');
  shell.setTheme(theme);
  const container = document.querySelector('#stage');
  if (!(container instanceof HTMLElement))
    throw new Error('stage container is absent');
  document.body.insertBefore(shell.overlay, container);
  bind(() => container.setAttribute('aria-label', t('stage.label')));
  applyPlants();
  const startLit = reduced() && screen === 'answer' ? 1 : 0;
  stage = await mountStage(container, loaded.release, {
    theme,
    lang: language,
    lit: [startLit, startLit, startLit, startLit, startLit],
    reduced: reduced(),
    points: screen === 'answer',
  });
  districtPlate = mountDistrict();
  stage.map.on('move', () => updateFold(false));
  stage.map.on('moveend', () => updateFold(true));
  mountEstablishments(
    stage.map,
    loaded,
    shell.legend,
    shell.overlay,
    shell.openDrawer,
  );
  applyPointPlants();
  if (plant === 'card-no-employees') {
    const openPoint = look.openPoint;
    look.openPoint = (key) => {
      openPoint?.(key);
      shell.overlay.querySelector('[data-field="field.employees"]')?.remove();
    };
  }
  const end = shell.topbar[1];
  if (end !== undefined) mountPhotoreal(stage.map, end, shell.attribution);
  bind(() =>
    stage.map.getCanvas().setAttribute('aria-label', t('stage.label')),
  );
  stage.map.on('movestart', updateMotionState);
  stage.map.on('moveend', updateMotionState);
  look.units = stage.units;
  look.litLevels = () => stage.litLevels();
  look.litLayers = () =>
    (stage.map.getStyle().layers ?? [])
      .filter((layer) => layer.id.startsWith(LIT_PREFIX))
      .map((layer) => JSON.stringify(layer));
  look.labelFields = () =>
    LABEL_LAYERS.filter((id) => stage.map.getLayer(id) !== undefined).map(
      (id) => JSON.stringify(stage.map.getLayoutProperty(id, 'text-field')),
    );
  look.labels = () => stage.labels();
  look.labelsUnder = (rects) => stage.labelsUnder(rects);
  look.brightCorners = () => stage.brightCorners();
  look.rendered = () => stage.rendered();
  look.camera = async (view) => {
    finishOpening();
    // The jump folds the plates (moveend is synchronous). The fit then
    // slides the view by the free part those plates leave, in the page's
    // direction. The planted case keeps the bare camera.
    await stage.camera(view);
    if (plant !== 'street-unpadded') {
      stage.fitPlates(free);
      await stage.rendered();
    }
    updateFold();
    await frame();
  };
  look.district = () => {
    const point = stage.district();
    const place = loaded.release.district;
    if (point === null || place === null) return null;
    return { name: place[lang()], ...point };
  };
  look.layers = () =>
    (stage.map.getStyle().layers ?? []).map((layer) => JSON.stringify(layer));
  look.exactZoom = () => stage.map.getZoom();
  look.sourceFeatures = (source, layer) =>
    stage.map.querySourceFeatures(source, { sourceLayer: layer }).length;
  look.showBuildings = async () => {
    finishOpening();
    await stage.showBuildings(free);
    if (plant === 'buildings-core-under-plate') plantBrightOnLegend();
  };
  look.litUnder = (rects) => stage.litUnder(rects);
  look.districtNames = () => stage.districtNames();
  for (const [name, read] of [
    ['bearing', () => stage.map.getBearing()],
    ['pitch', () => stage.map.getPitch()],
    ['zoom', () => stage.map.getZoom()],
  ] as const) {
    Object.defineProperty(look, name, {
      enumerable: true,
      get: () => Math.round(read() * 1000) / 1000,
    });
  }
  await frame();
  root.dataset.ready = '';
  look.ready = true;
  await runOpening();
  await applyMapPlants();
}

start().catch((error: unknown) => {
  look.failure =
    error instanceof Error ? error.message : 'the look page failed';
  root.dataset.ready = '';
});
