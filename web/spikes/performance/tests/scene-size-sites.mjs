export const FULL_TOKENS = new Set([
  'FULL',
  'TRACE_CONTRACT',
  'HEX_NONBLANK',
  'PARTICLE_NONBLANK',
  'GATE_BLANK_RENDERER',
  'PIXEL_CAP',
  'RENAMED_PROFILE',
  'GATE_SLOW_SCENE',
  'ROAD_TRACE_SCENE',
  'ROAD_PAUSE_PLANT',
  'FULL_STREET_LOAD',
  'PAUSE_SCENE',
  'ARABIC_REDUCED',
]);

export const ALIASES = [...FULL_TOKENS].filter((name) => name !== 'FULL');

const lostFull = 'size-dependent scene lost its full canvas';
const lostSmall = 'small-map scene lost its listed canvas';

export const FULL_SITES = [
  site(
    'open',
    'TRACE_CONTRACT',
    "'/en/_perf?profile=smoke'",
    'trace contract',
    'the smoke orbit draws both layers and records a trace',
  ),
  site(
    'open',
    'HEX_NONBLANK',
    "'/en/_perf?profile=smoke&isolate=hexagons'",
    'hex nonblank',
    'isolating hexagons leaves the hex canvas nonblank',
  ),
  site(
    'open',
    'PARTICLE_NONBLANK',
    "'/en/_perf?profile=smoke&isolate=particles'",
    'particle nonblank',
    'isolating particles leaves the particle canvas nonblank',
  ),
  site(
    'open',
    'GATE_BLANK_RENDERER',
    "'/en/_perf?plant=missing-renderer'",
    'blank renderer',
    'a blank renderer is refused by name',
  ),
  site(
    'open',
    'PIXEL_CAP',
    "'/en/_perf?profile=smoke&plant=ignore-cap'",
    'pixel cap',
    'ignoring the cap is qualified as the wrong cap',
  ),
  site(
    'open',
    'RENAMED_PROFILE',
    "'/en/_perf?profile=smoke&plant=rename-profile'",
    'renamed profile',
    'a renamed profile is qualified by name',
  ),
  site(
    'prepareCanvas',
    'GATE_SLOW_SCENE',
    '',
    'slow scene',
    'a planted slow full scene with an empty canvas at 60 is stored',
  ),
  site(
    'sharedRoadScene',
    'ROAD_TRACE_SCENE',
    'uninterrupted English road scene',
    'road trace',
    '',
  ),
  site(
    'open',
    'ROAD_PAUSE_PLANT',
    "roadUrl('&plant=pause-playback')",
    'paused playback',
    'roads paused playback plant is refused by name',
  ),
  site(
    'open',
    'FULL',
    "'/en/_perf?profile=smoke&plant=remote-asset'",
    'remote asset refusal',
    'the ordinary page helper rejects a remote asset',
  ),
  site(
    'open',
    'FULL',
    "'/en/_perf?profile=smoke&plant=no-webgl2'",
    'no webgl2',
    'the no-webgl2 plant names the failure without a map',
  ),
  site(
    'open',
    'FULL',
    "roadUrl('&plant=remote-asset')",
    'road remote refusal',
    'roads ordinary helper refuses the remote request plant',
  ),
  site(
    'open',
    'FULL_STREET_LOAD',
    '`/en/_perf?profile=smoke&layers=${ROAD_LARGE}`',
    'full street load',
    'roads full street load draws every link and carries the Simulated mark',
  ),
  site(
    'sharedRoadScene',
    'PAUSE_SCENE',
    'English pause scene',
    'english pause',
    '',
  ),
  site(
    'sharedRoadScene',
    'ARABIC_REDUCED',
    'Arabic reduced-motion scene',
    'arabic reduced',
    '',
  ),
];

export const SMALL_SITES = [
  site(
    'open',
    'SMALL',
    "'/ar/_perf?profile=smoke'",
    'arabic notice',
    'the Arabic route uses the Arabic notice',
  ),
  site(
    'open',
    'SMALL',
    "'/en/_perf?profile=smoke&plant=omit-hexagon'",
    'omit hexagon',
    'omitting one hexagon lowers the drawn count',
  ),
  site(
    'open',
    'SMALL',
    "'/en/_perf?profile=smoke&plant=hide-hexagons'",
    'hide hexagons',
    'hiding the hexagon layer reports no hexagon instances',
  ),
  site(
    'open',
    'SMALL',
    "'/en/_perf?profile=smoke&plant=omit-particle'",
    'omit particle',
    'omitting one particle lowers the drawn count',
  ),
  site(
    'open',
    'SMALL',
    "'/en/_perf?profile=smoke&plant=hide-particles'",
    'hide particles',
    'hiding the particle layer reports no particle instances',
  ),
  site(
    'open',
    'SMALL',
    "'/en/_perf?profile=smoke&plant=freeze'",
    'freeze',
    'a frozen clock leaves the first particle in place',
  ),
  site(
    'open',
    'SMALL',
    "'/en/_perf?profile=smoke&plant=no-samples'",
    'empty timestamps',
    'an empty timestamp list is refused by name',
  ),
  site(
    'open',
    'SMALL',
    "'/en/_perf?profile=smoke&plant=fail-submit'",
    'unknown field',
    'an unknown field is refused by name',
  ),
  site(
    'prepareCanvas',
    'SMALL',
    '',
    'remote image',
    'a remote image does not load',
  ),
  site(
    'sharedRoadScene',
    'SMALL',
    'English reduced-motion scene',
    'english reduced',
    '',
  ),
  site('sharedRoadScene', 'SMALL', 'Arabic road scene', 'arabic road', ''),
  site(
    'open',
    'SMALL',
    "roadUrl('&plant=omit-road-dash')",
    'omit road dash',
    'roads missing dash plant removes the actual extension',
  ),
  site(
    'open',
    'SMALL',
    "roadUrl('&plant=omit-road')",
    'omit road',
    'roads missing link plant lowers the drawn count',
  ),
  site(
    'open',
    'SMALL',
    "roadUrl('&plant=hide-roads')",
    'hide roads',
    'roads hidden layer plant reports zero drawn road links',
  ),
];

export const LATE_SIZE = [
  ['.cssWidth', 'cssWidth'],
  ['.cssHeight', 'cssHeight'],
  ['.bufferWidth', 'bufferWidth'],
  ['.bufferHeight', 'bufferHeight'],
  ['WALL_WIDTH', 'WALL_WIDTH'],
  ['WALL_HEIGHT', 'WALL_HEIGHT'],
  ['.textPixelRatio', 'textPixelRatio'],
  ['.devicePixelRatio', 'devicePixelRatio'],
  ['.cap', 'cap'],
  ["'smoke-profile'", 'smoke-profile'],
  ["'wrong-cap'", 'wrong-cap'],
  ["'unknown-profile'", 'unknown-profile'],
  ["'road-playback-stopped'", 'road-playback-stopped'],
  ["'gate'", 'gate'],
];

function site(name, canvas, path, label, title) {
  const missing = canvas === 'SMALL' ? lostSmall : lostFull;
  return { key: `${name}|${canvas}|${path}|${title}`, label, missing };
}
