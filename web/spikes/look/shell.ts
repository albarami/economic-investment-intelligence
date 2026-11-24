// The regions of the wall around the Stage, as docs/11_DESIGN_DIRECTION.md
// section 14 sets them: the top bar (wordmark and badge at the inline-start,
// the controls at the inline-end), the legend plate at the lower
// inline-start of the Stage (DES-68 as ruled in L-119 item 1: the map does
// not mirror, and in Arabic the upper corner covered Doha's core), the Brief
// at the inline-end with one card (DES-140), the source chain over the Brief
// column (DES-95) and the map attribution at the inline-end of the Stage
// footer row (DES-53). Every word comes from the catalogue; every numeral
// from the Fact chip family.
import {
  compactChip,
  periodChip,
  referenceChip,
  valueChip,
  type Fact,
} from './fact-chip';
import { glyph } from './glyphs';
import { SHARE_FROM_STEP } from './release-shape.mjs';
import { bind, bindText, lang, refresh, t } from './i18n';
import {
  BREAK_FACTS,
  HERO_FACT,
  SUPPORTING_FACTS,
  type Loaded,
} from './release';

export type Theme = 'dark' | 'light';

export type Handlers = {
  theme: (theme: Theme) => void;
  motion: () => void;
  language: () => void;
  reset: () => void;
  question: (id: Question) => void;
  place: () => void;
  back: () => void;
};

// P2 of round 5: the four questions of the home. Only "Where should we
// operate?" has an answer screen in this round.
export const QUESTIONS = ['market', 'operate', 'supply', 'grow'] as const;
export type Question = (typeof QUESTIONS)[number];
export type Screen = 'home' | 'place' | 'notyet' | 'answer';
const QUESTION_KEYS: Record<Question, string> = {
  market: 'q.market',
  operate: 'q.operate',
  supply: 'q.supply',
  grow: 'q.grow',
};

export type Shell = {
  overlay: HTMLElement;
  topbar: HTMLElement[];
  legend: HTMLElement;
  brief: HTMLElement;
  card: HTMLElement;
  attribution: HTMLElement;
  setTheme: (theme: Theme) => void;
  setPaused: (paused: boolean) => void;
  openDrawer: (fact: Fact, ...additional: Fact[]) => void;
  closeDrawer: () => void;
  drawerOpen: () => boolean;
  showTable: (table: boolean) => void;
  setScreen: (screen: Screen, question: Question) => void;
};

function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className = '',
  data: Record<string, string> = {},
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className !== '') node.className = className;
  for (const [key, value] of Object.entries(data)) node.dataset[key] = value;
  return node;
}

function words<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className: string,
  read: () => string,
): HTMLElementTagNameMap[K] {
  const node = element(tag, className);
  bindText(node, read);
  return node;
}

function control(name: string, read: () => string): HTMLButtonElement {
  const button = element('button', 'control', { control: name });
  button.type = 'button';
  bindText(button, read);
  return button;
}

function theme(): Theme {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}

function topbar(handlers: Handlers) {
  const start = element('header', 'topbar topbar-start plate', {
    plate: 'topbar-start',
  });
  const wordmark = element('p', 'wordmark');
  bind(() => {
    wordmark.textContent = t('wordmark');
    wordmark.lang = 'en';
  });
  const divider = element('span', 'topbar-divider');
  divider.setAttribute('aria-hidden', 'true');
  // DES-80 as amended by ruling L-111: the seat glyph and the seat's name.
  const badge = element('p', 'badge', { part: 'badge' });
  badge.append(
    glyph('seat'),
    words('span', 'badge-prefix', () => t('badge.prefix')),
    words('span', 'badge-seat', () => t('badge.seat')),
  );
  start.append(wordmark, divider, badge);

  const end = element('nav', 'topbar topbar-end plate', {
    plate: 'topbar-end',
  });
  const group = element('div', 'segmented');
  group.setAttribute('role', 'group');
  bind(() => group.setAttribute('aria-label', t('theme.label')));
  const dark = control('theme-dark', () => t('theme.dark'));
  const light = control('theme-light', () => t('theme.light'));
  dark.addEventListener('click', () => handlers.theme('dark'));
  light.addEventListener('click', () => handlers.theme('light'));
  group.append(dark, light);
  const setTheme = (current: Theme) => {
    dark.setAttribute('aria-pressed', String(current === 'dark'));
    light.setAttribute('aria-pressed', String(current === 'light'));
  };

  let paused = false;
  const motion = element('button', 'control', { control: 'motion' });
  motion.type = 'button';
  const motionWords = element('span', 'control-words');
  motionWords.dataset.word = '';
  const motionGlyph = element('span', 'control-glyph');
  motionGlyph.setAttribute('aria-hidden', 'true');
  const paint = () => {
    motionGlyph.replaceChildren(glyph(paused ? 'play' : 'pause'));
    motionWords.textContent = t(paused ? 'motion.resume' : 'motion.pause');
    motionWords.lang = lang();
  };
  bind(paint);
  motion.setAttribute('aria-pressed', 'false');
  motion.append(motionGlyph, motionWords);
  motion.addEventListener('click', handlers.motion);
  const setPaused = (value: boolean) => {
    paused = value;
    motion.setAttribute('aria-pressed', String(value));
    paint();
  };

  // DES-143: the other language, named in its own script.
  const language = element('button', 'control control-language', {
    control: 'language',
  });
  language.type = 'button';
  bind(() => {
    language.textContent = t('language.other');
    language.lang = lang() === 'en' ? 'ar' : 'en';
  });
  language.addEventListener('click', handlers.language);
  const reset = control('reset', () => t('reset'));
  reset.addEventListener('click', handlers.reset);
  end.append(group, motion, language, reset);
  return { start, end, setTheme, setPaused };
}

function legend(loaded: Loaded, open: (fact: Fact) => void) {
  const plate = element('section', 'legend plate', { plate: 'legend' });
  const title = words('h2', 'legend-title', () => t('legend.title'));
  title.id = 'legend-title';
  plate.setAttribute('aria-labelledby', title.id);
  const scope = words('p', 'legend-scope', () => t('legend.scope'));
  // Round 5g, finding 22 (DES-68): the legend names the date of the count,
  // in one reference chip inside the catalogue's sentence.
  const period = element('p', 'legend-period');
  bind(() => {
    const [before, after] = t('legend.period').split('{date}');
    period.replaceChildren(
      before ?? '',
      periodChip(loaded.release.period),
      after ?? '',
    );
    period.lang = lang();
  });
  const head = element('div', 'legend-head');
  head.append(title, scope, period);

  const breaks = BREAK_FACTS.map((id) => loaded.fact(id));
  const scaleView = element('div', 'legend-view');
  const scale = element('div', 'legend-scale');
  scale.setAttribute('aria-hidden', 'true');
  for (const step of [1, 2, 3, 4, 5]) {
    const swatch = element('span', 'legend-swatch');
    swatch.dataset.step = String(step);
    scale.append(swatch);
  }
  const marks = element('div', 'legend-breaks');
  for (const fact of breaks) marks.append(compactChip(fact, open));
  // Round 5g, finding 24: the classes the card's share counts, from the
  // break where they start to the end of the scale, named as the card names
  // them.
  const span = element('div', 'legend-span');
  const spanMark = words('span', 'legend-span-mark', () => t('legend.densest'));
  spanMark.style.gridColumn = `${SHARE_FROM_STEP} / -1`;
  span.append(spanMark);
  scaleView.append(scale, marks, span);

  const table = element('table', 'legend-table');
  table.hidden = true;
  const headRow = element('tr');
  const empty = element('th');
  empty.setAttribute('aria-hidden', 'true');
  const spanHead = element('th');
  spanHead.setAttribute('aria-hidden', 'true');
  headRow.append(
    empty,
    words('th', '', () => t('legend.table.class')),
    words('th', '', () => t('legend.title')),
    spanHead,
  );
  const bands = [
    'legend.band.lowest',
    'legend.band.low',
    'legend.band.middle',
    'legend.band.high',
    'legend.band.highest',
  ];
  const body = element('tbody');
  for (const [index, key] of bands.entries()) {
    const row = element('tr');
    const swatchCell = element('td');
    const swatch = element('span', 'legend-swatch legend-swatch-row');
    swatch.dataset.step = String(index + 1);
    swatchCell.append(swatch);
    const range = element('td', 'legend-range');
    const low = breaks[index - 1];
    const high = breaks[index];
    if (low === undefined && high !== undefined) {
      range.append(
        words('span', '', () => t('legend.under')),
        compactChip(high, open),
      );
    } else if (low !== undefined && high === undefined) {
      range.append(
        compactChip(low, open),
        words('span', '', () => t('legend.over')),
      );
    } else if (low !== undefined && high !== undefined) {
      // P3 (the merged audit's F2): each bound is its own chip and opens its
      // own fact; the dash between them is not a numeral.
      const dash = element('span', 'legend-dash');
      dash.textContent = '–';
      dash.setAttribute('aria-hidden', 'true');
      range.append(compactChip(low, open), dash, compactChip(high, open));
    }
    row.append(
      swatchCell,
      words('td', '', () => t(key)),
      range,
    );
    if (index + 1 === SHARE_FROM_STEP) {
      const densest = words('td', 'legend-densest', () => t('legend.densest'));
      densest.rowSpan = bands.length - SHARE_FROM_STEP + 1;
      row.append(densest);
    }
    body.append(row);
  }
  const thead = element('thead');
  thead.append(headRow);
  table.append(thead, body);

  // DES-19: every legend states the direction in words.
  const direction = words('p', 'legend-direction', () =>
    t(theme() === 'light' ? 'legend.direction.light' : 'legend.direction.dark'),
  );
  let tableShown = false;
  const toggle = control('table', () =>
    t(tableShown ? 'legend.table.hide' : 'legend.table.show'),
  );
  const showTable = (value: boolean) => {
    tableShown = value;
    table.hidden = !value;
    scaleView.hidden = value;
    direction.hidden = value;
    toggle.textContent = t(value ? 'legend.table.hide' : 'legend.table.show');
  };
  toggle.addEventListener('click', () => showTable(!tableShown));
  const foot = element('div', 'legend-foot');
  foot.append(direction, toggle);
  plate.append(head, scaleView, table, foot);
  return { plate, showTable };
}

// The source chain of one fact (DES-95, DES-96): its large chip, then a
// neutral why-path from the fact to its table, method, source and release,
// and the map's own source. It is read from the fact's chain in the
// release; a fact without a chain never reaches it (FE-41).
function factChain(fact: Fact, releaseId: string): HTMLElement {
  const section = element('section', 'fact-chain', { chainFact: fact.id });
  const head = element('div', 'drawer-head');
  head.append(valueChip(fact, 'large', null));
  const chain = fact.chain;
  const thread = element('ol', 'thread');
  const rows: [string, () => HTMLElement][] = [
    ['drawer.identifier', () => referenceChip(fact.id)],
    [
      'drawer.table',
      () => {
        const cell = element('span', 'thread-value');
        cell.append(
          words('span', '', () => t(chain?.table ?? 'chip.refused')),
          referenceChip(releaseId),
        );
        return cell;
      },
    ],
    [
      'drawer.method',
      () => {
        const cell = element('span', 'thread-value');
        cell.append(
          words('span', '', () => t(chain?.method ?? 'chip.refused')),
          referenceChip(chain?.method_version ?? ''),
        );
        return cell;
      },
    ],
    [
      'drawer.source',
      () => {
        const cell = element('span', 'thread-value');
        cell.append(
          words('span', '', () => t(chain?.generator.name ?? 'chip.refused')),
          referenceChip(chain?.generator.version ?? ''),
        );
        const more = control('source-inputs', () => t('card.more'));
        more.addEventListener('click', () => showInput(0));
        cell.append(more);
        return cell;
      },
    ],
    [
      'drawer.map',
      () => {
        // The licence line is a Latin run, isolated left to right in both
        // languages (DES-38); the estimate sentence follows in the page's
        // language (FE-52).
        const cell = element('span', 'thread-stack');
        const source = element('bdi', 'thread-source');
        source.dir = 'ltr';
        source.lang = 'en';
        bind(() => {
          source.textContent = t('drawer.mapSource');
        });
        cell.append(
          source,
          words('span', '', () => t('drawer.heights')),
        );
        return cell;
      },
    ],
  ];
  for (const [key, value] of rows) {
    const row = element('li', 'thread-row');
    row.dataset.row = key;
    const node = element('span', 'thread-node');
    node.setAttribute('aria-hidden', 'true');
    const cell = element('span', 'thread-value');
    cell.append(value());
    row.append(
      node,
      words('span', 'thread-label', () => t(key)),
      cell,
    );
    thread.append(row);
  }
  const summary = element('div', 'chain-summary');
  summary.append(thread);
  const inputs = (chain?.inputs ?? []).map((input, index) => {
    const page = element('div', 'chain-input', { row: 'drawer.source' });
    const source = element('bdi', 'thread-source');
    source.dir = 'auto';
    if (input.provenance === 'public') {
      source.append(
        referenceChip(input.publisher),
        referenceChip(input.dataset),
        referenceChip(input.source),
        referenceChip(input.licence),
        periodChip(input.retrieved),
      );
    } else {
      source.append(
        referenceChip(input.dataset),
        words('span', '', () => t(input.generator.name)),
        referenceChip(input.generator.version),
      );
    }
    source.append(referenceChip(input.sha256));
    const controls = element('div', 'drawer-input-controls');
    const back = control('source-summary', () => t('drawer.back'));
    back.addEventListener('click', () => {
      showInput(index - 1);
      if (index === 0)
        summary
          .querySelector<HTMLElement>('[data-control="source-inputs"]')
          ?.focus();
    });
    controls.append(back);
    if (index + 1 < (chain?.inputs.length ?? 0)) {
      const more = control('source-next', () => t('card.more'));
      more.addEventListener('click', () => showInput(index + 1));
      controls.append(more);
    }
    page.append(source, controls);
    page.hidden = true;
    return page;
  });
  // DES-36: source links are paged, never shrunk or scrolled on the wall.
  const showInput = (selected: number) => {
    summary.hidden = selected >= 0;
    inputs.forEach((page, index) => {
      page.hidden = index !== selected;
    });
    if (selected >= 0)
      inputs[selected]
        ?.querySelector<HTMLElement>('[data-control="source-summary"]')
        ?.focus();
  };
  section.append(head, summary, ...inputs);
  return section;
}

function evidenceDrawer(close: () => void): HTMLElement {
  const drawer = element('section', 'drawer', { plate: 'drawer' });
  const title = words('h2', 'drawer-title', () => t('drawer.title'));
  title.tabIndex = -1;
  title.id = 'drawer-title';
  drawer.setAttribute('aria-labelledby', title.id);
  const back = control('back', () => t('drawer.back'));
  back.addEventListener('click', close);
  const top = element('div', 'drawer-top');
  top.append(title, back);
  drawer.append(top);
  return drawer;
}

function sourceChain(
  facts: Fact[],
  releaseId: string,
  close: () => void,
): HTMLElement {
  const drawer = evidenceDrawer(close);
  drawer.dataset.drawerFact = facts[0]?.id ?? '';
  const chains = facts.map((fact) => factChain(fact, releaseId));
  if (facts.length > 1) {
    // DES-36 and DES-95: one fact at a time, with both range bounds
    // explicitly available, without stacking a scrolling wall panel.
    const choices = element('div', 'drawer-facts');
    choices.setAttribute('role', 'group');
    bind(() => choices.setAttribute('aria-label', t('drawer.range')));
    const buttons = facts.map((fact, index) => {
      const button = compactChip(fact, () => show(index));
      button.dataset.control = 'range-fact';
      return button;
    });
    const show = (selected: number) => {
      drawer.dataset.drawerFact = facts[selected]?.id ?? '';
      chains.forEach((chain, index) => {
        chain.hidden = index !== selected;
      });
      buttons.forEach((button, index) =>
        button.setAttribute('aria-pressed', String(index === selected)),
      );
    };
    choices.append(...buttons);
    drawer.append(choices);
    show(0);
  }
  drawer.append(...chains);
  return drawer;
}

function coverageReason(close: () => void): HTMLElement {
  const drawer = evidenceDrawer(close);
  for (const key of [
    'coverage.reason',
    'coverage.rule',
    'coverage.alternative',
  ])
    drawer.append(words('p', 'card-caveat', () => t(key)));
  return drawer;
}

function questionRow(read: () => string, data: Record<string, string>) {
  const item = element('li', 'question-item');
  const button = element('button', 'question', data);
  button.type = 'button';
  const label = words('span', 'question-words', read);
  button.append(label, glyph('chevron', 'glyph question-glyph'));
  item.append(button);
  return { item, button };
}

function backControl(handlers: Handlers): HTMLButtonElement {
  const back = control('back', () => t('drawer.back'));
  back.addEventListener('click', handlers.back);
  return back;
}

// The lit district's name in the page's language (P1), from the basemap's
// own labels through the release; without it the headline names no place.
function headline(loaded: Loaded): string {
  if (loaded.release.coverage === 'not_measured')
    return t('coverage.notMeasured');
  const place = loaded.release.district;
  if (place === null) return t('card.headlineCore');
  return t('card.headline').replace('{place}', place[lang()]);
}

function brief(loaded: Loaded, overlay: HTMLElement, handlers: Handlers) {
  const plate = element('aside', 'brief plate', { plate: 'brief' });
  plate.id = 'brief';
  plate.tabIndex = -1;
  bind(() => plate.setAttribute('aria-label', t('brief.label')));

  // P2: the home starts from a decision, with no data layer and no numeral.
  const home = element('article', 'card card-home', { card: 'home' });
  const homeTitle = words('h1', 'home-headline', () => t('home.headline'));
  homeTitle.dataset.part = 'home-headline';
  const value = words('p', 'home-value', () => t('home.value'));
  const list = element('ul', 'questions');
  bind(() => list.setAttribute('aria-label', t('home.label')));
  for (const id of QUESTIONS) {
    const row = questionRow(() => t(QUESTION_KEYS[id]), { question: id });
    row.button.addEventListener('click', () => handlers.question(id));
    list.append(row.item);
  }
  home.append(homeTitle, value, list);

  const where = element('article', 'card card-home', { card: 'place' });
  const whereEyebrow = words('p', 'card-eyebrow', () => t('q.operate'));
  const whereTitle = words('h1', 'home-headline', () => t('home.where'));
  const places = element('ul', 'questions');
  const frame = questionRow(() => t('place.frame'), { place: 'frame' });
  frame.button.addEventListener('click', handlers.place);
  places.append(frame.item);
  const whereFoot = element('footer', 'card-footer');
  whereFoot.append(backControl(handlers));
  where.append(whereEyebrow, whereTitle, places, whereFoot);

  let asked: Question = 'operate';
  const notyet = element('article', 'card', { card: 'notyet' });
  const notyetEyebrow = words('p', 'card-eyebrow', () =>
    t(QUESTION_KEYS[asked]),
  );
  const notyetTitle = words('h1', 'card-headline', () => t('notyet.headline'));
  const notyetLine = words('p', 'card-caveat', () => t('notyet.line'));
  const notyetFoot = element('footer', 'card-footer');
  notyetFoot.append(backControl(handlers));
  notyet.append(notyetEyebrow, notyetTitle, notyetLine, notyetFoot);

  const card = element('article', 'card', { card: 'answer' });
  const eyebrow = words('p', 'card-eyebrow', () => t('q.operate'));
  const title = words('h1', 'card-headline', () => headline(loaded));
  title.dataset.part = 'headline';
  title.id = 'card-headline';
  card.setAttribute('aria-labelledby', title.id);

  let opener: HTMLElement | null = null;
  let drawer: HTMLElement | null = null;
  // P3 (the merged audit's F1): focus returns to the opener only when it was
  // inside the source chain; a control elsewhere (Reset) keeps its focus.
  const closeDrawer = () => {
    if (drawer === null) return;
    const inside = drawer.contains(document.activeElement);
    drawer.remove();
    drawer = null;
    plate.inert = false;
    plate.dataset.covered = 'false';
    if (inside && opener?.isConnected === true) opener.focus();
  };
  const showDrawer = (build: (close: () => void) => HTMLElement) => {
    const active = document.activeElement;
    closeDrawer();
    opener = active instanceof HTMLElement ? active : null;
    drawer = build(closeDrawer);
    drawer.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      closeDrawer();
    });
    plate.inert = true;
    plate.dataset.covered = 'true';
    overlay.append(drawer);
    drawer.querySelector<HTMLElement>('h2')?.focus();
  };
  const openDrawer = (fact: Fact, ...additional: Fact[]) =>
    showDrawer((close) =>
      sourceChain([fact, ...additional], loaded.release.release_id, close),
    );

  const hero = element('div', 'card-hero');
  const available = loaded.release.coverage === 'available';
  if (available)
    hero.append(valueChip(loaded.fact(HERO_FACT), 'large', openDrawer));
  const facts = element('div', 'card-facts');
  if (available) {
    for (const id of SUPPORTING_FACTS)
      facts.append(valueChip(loaded.fact(id), 'standard', openDrawer));
  }
  const caveat = words('p', 'card-caveat', () =>
    t(available ? 'card.caveat' : 'coverage.notMeasured'),
  );
  caveat.dataset.part = 'caveat';
  const footer = element('footer', 'card-footer');
  const more = control('more', () => t('card.more'));
  more.addEventListener('click', () => openDrawer(loaded.fact(HERO_FACT)));
  if (available) footer.append(more);
  else {
    const why = control('coverage-why', () => t('coverage.why'));
    why.addEventListener('click', () => showDrawer(coverageReason));
    footer.append(why);
  }
  footer.append(backControl(handlers));
  card.append(eyebrow, title, hero, facts, caveat, footer);

  const cards: Record<Screen, HTMLElement> = {
    home,
    place: where,
    notyet,
    answer: card,
  };
  plate.append(home, where, notyet, card);
  const setScreen = (screen: Screen, question: Question) => {
    asked = question;
    plate.dataset.screen = screen;
    for (const [name, node] of Object.entries(cards)) {
      node.hidden = name !== screen;
    }
    refresh();
  };
  setScreen('home', 'operate');
  return {
    plate,
    card,
    openDrawer,
    closeDrawer,
    drawerOpen: () => drawer !== null,
    setScreen,
  };
}

export function buildShell(handlers: Handlers, loaded: Loaded): Shell {
  const overlay = element('div', 'overlay');
  const skip = element('a', 'skip');
  skip.href = '#brief';
  bindText(skip, () => t('skip.brief'));
  const top = topbar(handlers);
  const answer = brief(loaded, overlay, handlers);
  const key = legend(loaded, answer.openDrawer);
  // Round 5g, finding 9: the credits are one Latin run that keeps its own
  // language and direction; the note on building heights is in the page's
  // language. The paragraph inherits the page's (as the drawer's map row).
  const attribution = element('p', 'attribution plate', {
    plate: 'attribution',
    part: 'attribution',
  });
  const credits = element('bdi', 'attribution-credits');
  credits.dir = 'ltr';
  credits.lang = 'en';
  bind(() => {
    credits.textContent = t('attribution.credits');
  });
  const heights = words('span', 'attribution-heights', () =>
    t('attribution.heights'),
  );
  attribution.append(credits, heights);
  overlay.append(
    skip,
    top.start,
    top.end,
    key.plate,
    answer.plate,
    attribution,
  );
  return {
    overlay,
    topbar: [top.start, top.end],
    legend: key.plate,
    brief: answer.plate,
    card: answer.card,
    attribution,
    setTheme: top.setTheme,
    setPaused: top.setPaused,
    openDrawer: answer.openDrawer,
    closeDrawer: answer.closeDrawer,
    drawerOpen: answer.drawerOpen,
    showTable: key.showTable,
    setScreen: answer.setScreen,
  };
}
