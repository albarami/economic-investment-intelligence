export type Verdict = { ok: boolean; detail: string };
export type NumeralItem = { text: string; inChip: boolean; where: string };
export type MarkItem = {
  where: string;
  textDecoration: string;
  borderStyle: string;
  backgroundImage: string;
};
export type ChipFound = { variant: string; ids: string[] };
export type FactFound = {
  id: string;
  provenance: string;
  origin?: string;
  chain: import('./release-shape.mjs').ChainRecord | null;
};
export type Rect = {
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
};
export type Decoded = {
  width: number;
  height: number;
  channels: number;
  data: Uint8Array;
};

export const CSP: string;
export function judgeCsp(header: string | null): Verdict;
export function judgeDigits(text: string): Verdict;
export function judgeRequests(urls: string[], origin: string): Verdict;

export const ROUTES: string[];
export const VARIANTS: { lang: 'en' | 'ar'; theme: 'dark' | 'light' }[];
export const CAPTURE_FILES: string[];
export const PRODUCTION_MARKERS: string[];
export const REVIEW_PENDING: string;
export const CLASSES: string[];
export const CLASS_WORDS: { en: string[]; ar: string[] };
export const OFF_SCREEN_WORDS: string[];

export function findMarkers(text: string): string[];
export function judgeNumerals(items: NumeralItem[]): Verdict;
export function judgeClassWords(text: string): Verdict;
export function judgeMarks(items: MarkItem[]): Verdict;
export function judgeLitLayers(layers: string[]): Verdict;
export function judgeChipChains(
  chips: ChipFound[],
  facts: FactFound[],
  expected: string[],
): Verdict;
export function judgeAttribution(found: {
  text: string;
  visible: boolean;
}): Verdict;
export function judgeDocument(
  root: { lang: string; dir: string },
  lang: 'en' | 'ar',
): Verdict;
export function judgeMotion(state: {
  reduced: boolean;
  litMode: string;
}): Verdict;
export function judgeDensity(counts: {
  headlines: number;
  valueChips: number;
  chips?: number;
  caveats: number;
}): Verdict;
export function judgeDigitWidths(
  sizes: { name: string; widths: number[] }[],
): Verdict;
export function judgeLabelLanguage(
  fields: string[],
  lang: 'en' | 'ar',
): Verdict;
export function judgeTextFloor(
  items: { size: number; where: string }[],
  floor: number,
): Verdict;
export function judgeInside(
  rects: Rect[],
  frame: { x: number; y: number; width: number; height: number },
): Verdict;
export function judgeNoOverlap(rects: Rect[]): Verdict;
export type LabelHit = { label: string; plate: string };
export function judgeLabelsClear(hits: LabelHit[]): Verdict;
export type ScreenPoint = { x: number; y: number };
export function judgeCoreClear(points: ScreenPoint[], rects: Rect[]): Verdict;
export function judgeCatalogue(catalogue: unknown): Verdict;

// Round 5: the street cameras (V9), the folding plates (V7), the building
// and road layers (V1, V4), the screens (P2) and the company card.
export type StreetCamera = {
  name: string;
  center: [number, number];
  zoom: number;
  pitch: number;
  bearing: number;
};
export const STREET_CAMERAS: StreetCamera[];
export const STREET_FILES: string[];
export const FOLD_ZOOM: number;
export const UNFOLD_ZOOM: number;
export type MapLayer = {
  id: string;
  type: string;
  source?: string;
  minzoom?: number;
  filter?: unknown;
  layout?: Record<string, unknown>;
  paint?: Record<string, unknown>;
};
export function judgeBuildingLayers(layers: MapLayer[]): Verdict;
export function judgeRoadLabels(layers: MapLayer[]): Verdict;
// Round 5g: every layer of the establishment source, under every label.
export const FIRM_SOURCE: string;
export const NAME_LAYERS: string[];
export function judgePointsUnderLabels(
  layers: { id: string; type: string; source?: string }[],
): Verdict;
export function judgeUniqueNames(texts: string[]): Verdict;
export type BracketLabel = {
  lines: number;
  lang: string;
  textLeft: number;
  textRight: number;
  bracketLeft: number;
  bracketRight: number;
};
export function judgeBracketLabel(state: BracketLabel): Verdict;
export type StreetCover = { camera: string; en: number; ar: number };
export function judgeStreetCover(rows: StreetCover[]): Verdict;
export type FoldState = {
  zoom: number;
  brief: 'open' | 'folded';
  legend: 'open' | 'folded';
};
export function judgeFold(states: FoldState[]): Verdict;
export function judgeCityFrame(state: FoldState, cap: number): Verdict;
export type FoldedLegend = {
  zoom: number;
  breaks: number;
  direction: string;
  table: { shown: boolean; rows: number } | null;
};
export function judgeFoldedLegend(state: FoldedLegend): Verdict;
export type AttributionRuns = {
  note: { lang: string; size: number } | null;
  creditLines: number;
  creditText: string;
};
export function judgeAttributionRuns(
  state: AttributionRuns,
  lang: string,
  size: number,
): Verdict;

// Round 5e: the district plate of P1 (E1) and the major place names inside
// the screen (E2).
export const DISTRICT_PLATE_STRETCH: number;
export const DISTRICT_PLATE_REACH: number;
export type ScreenBox = { x: number; y: number; width: number; height: number };
export type DistrictPlateFound = {
  name: string;
  text: string;
  shown: boolean;
  running: number;
  plate: ScreenBox;
  textBox: ScreenBox;
  point: { x: number; y: number };
  viewport: { width: number; height: number };
};
export function judgeDistrictPlate(found: DistrictPlateFound): Verdict;
export const EDGE_MARGIN: number;
export function edgeStrips(
  width: number,
  height: number,
  margin?: number,
): Rect[];
export function judgeLabelsInside(hits: LabelHit[]): Verdict;
export type ScreenState = {
  screen: string;
  cards: string[];
  lit: number[];
  legend: boolean;
  numerals: number;
  questions: number;
  back: boolean;
};
export function judgeScreen(state: ScreenState, want: string): Verdict;
export const CARD_FIELDS: string[];
export function judgeCard(
  found: { field: string; value: string }[],
  row: { employees: number | null },
): Verdict;
export function pngSize(buffer: Uint8Array): { width: number; height: number };
export function decodePng(buffer: Uint8Array): Decoded;
export function greyscale(decoded: Decoded): Uint8Array;
export function encodeGreyPng(
  width: number,
  height: number,
  grey: Uint8Array,
): Uint8Array;
// Round 5g, finding 22: the date of the count in the legend head.
export function judgeLegendPeriod(
  state: { shown: boolean; chips: string[] },
  want: string,
): Verdict;
// Round 5g, finding 15: the counts of a card are chained value chips.
export const CARD_COUNT_FIELDS: string[];
export const CARD_REFERENCE_FIELDS: string[];
export function judgeCardChips(
  rows: { field: string; chip: string | null; fact: string | null }[],
  facts: FactFound[],
): Verdict;
// Round 5g, findings 1, 18 and 19: the establishment paints and the ramp.
export function judgePointColours(
  paints: Record<string, unknown>,
  ramp: string[],
): Verdict;
export function judgePointKey(
  state: { zoom: number; point: boolean; cluster: boolean },
  clusterZoom: number,
  pointZoom: number,
): Verdict;
export function judgeTypeControl(
  state: {
    zoom: number;
    control: boolean;
    list: boolean;
    title: string;
    rows: { slug: string; name: string; fact: string }[];
  },
  pointZoom: number,
  want: { title: string; names: Record<string, string> },
): Verdict;
export function judgeSwatches(swatches: number[][], cells: number[][]): Verdict;
