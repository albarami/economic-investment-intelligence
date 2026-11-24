import { FactChip } from '../facts/FactChip';
/**
 * The map column. With no extract the page draws land and sea and
 * does not construct a map or request a tile.
 */
import { useEffect, useRef, useState, type ReactElement } from 'react';

import { direction, text, type Language } from '../i18n';
import { directiveAccepted, type AnswerDirective } from '../brief/catalogue';
import { extractStyle, type BasemapRequest } from './basemap';
import type { MapHandle, OverlayMount, CameraState } from './map-boot';
import { portFromHandle } from './live-port';
import {
  publishViewRevision,
  registerPort,
  releasePort,
  setFrame,
  usePort,
} from '../state/area-actions';
import type { LayerPayload } from './layers/payload';
import { LayerPlate, PublicLayers } from './layers/PublicLayers';
import type { FactRegistry } from '../facts/registry';
import {
  parseModes,
  modeFailureReason,
  selectedMode,
  type MapMode,
  type MapModes,
} from './map-modes';
import { requestLocal } from '../api/address-search.mjs';
import { MapModeSwitch } from './MapModeSwitch';
import { clockDay, clockTimestamp } from './clock';
import { ClockScrubber } from './ClockScrubber';
import { Swipe, type ComparisonInput } from './Swipe';
import { useArea } from '../state/store';
import type { AreaOutline } from '../api/areas';
import { ContextRing, contextRingVertices } from '../controls/ContextRing';

const UNAVAILABLE: MapModes = {
  open: { available: true, reason: null },
  satellite: { available: false, reason: 'network' },
  photoreal: { available: false, reason: 'network', meter: null },
};

export type StagePhase =
  'loading' | 'ready' | 'paused' | 'error' | 'asset-absent';

export type MapStarter = (
  container: HTMLElement,
  style: ReturnType<typeof extractStyle>,
) => MapHandle | Promise<MapHandle>;

export function Stage({
  language,
  theme,
  extractUrl,
  paused = false,
  directive = null,
  mapStarter,
  inert = false,
  layerPayload = null,
  registry = null,
  onOpenChain,
  overlayFactory,
  comparison = null,
  dayBasis,
  canvas = null,
  contextRing = null,
  quiet = false,
  compactControls = false,
}: {
  comparison?: ComparisonInput | null;
  dayBasis?: string;
  language: Language;
  theme: 'dark' | 'light';
  extractUrl: string | null;
  paused?: boolean;
  directive?: AnswerDirective | null;
  mapStarter?: MapStarter;
  inert?: boolean;
  layerPayload?: LayerPayload | null;
  registry?: FactRegistry | null;
  onOpenChain?: (factId: string) => void;
  overlayFactory?: (
    payload: LayerPayload,
    registry: FactRegistry | null,
  ) => OverlayMount;
  canvas?: ReactElement | null;
  /** The resolved outline of the rings directive's distinct wider area. */
  contextRing?: AreaOutline | null;
  quiet?: boolean;
  compactControls?: boolean;
}) {
  const [reportedModes, setModes] = useState<MapModes>(UNAVAILABLE);
  const modes: MapModes = reportedModes;
  const [fraction, setFraction] = useState('0');
  const currentFraction = useRef('0');
  const [requested, setRequested] = useState<MapMode>('open');
  const mode = selectedMode(requested, modes);
  const needsMap = extractUrl !== null || mode !== 'open';
  const [credit, setCredit] = useState({ mode: 'open' as MapMode, text: '' });
  const activeHandle = useRef<MapHandle | null>(null);
  const savedView = useRef<CameraState | null>(null);
  const selectedArea = useArea();
  const focusedOutline = useRef(selectedArea.presented?.outline ?? null);
  const drawnOn = useRef<MapHandle | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void requestLocal('/api/map-modes', {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then(async (response) =>
        response.ok ? parseModes(await response.json()) : null,
      )
      .then((value) => {
        if (!controller.signal.aborted) setModes(value ?? UNAVAILABLE);
      })
      .catch(() => {
        if (!controller.signal.aborted) setModes(UNAVAILABLE);
      });
    return () => controller.abort();
  }, []);
  const controlContent = (
    <div className="map-controls" dir={direction(language)}>
      {!quiet ? (
        <MapModeSwitch
          language={language}
          modes={modes}
          selected={mode}
          onChange={setRequested}
        />
      ) : null}
      {!quiet ? (
        <FactChip
          variant="operational"
          language={language}
          meter={modes.photoreal.meter}
          reason={modes.photoreal.reason}
        />
      ) : null}
      {needsMap && !quiet ? (
        <ClockScrubber
          language={language}
          dayBasis={dayBasis}
          fraction={fraction}
          onFractionChange={(value) => {
            currentFraction.current = value;
            setFraction(value);
          }}
          onChange={(timestamp) => activeHandle.current?.setClock?.(timestamp)}
        />
      ) : null}
      {comparison && registry ? (
        <Swipe
          language={language}
          comparison={comparison}
          registry={registry}
          onOpen={onOpenChain ?? (() => undefined)}
        />
      ) : null}
      {compactControls ? (
        <div
          className="camera-controls"
          role="group"
          aria-label={text(language, 'map.pan')}
        >
          {(
            [
              'north',
              'west',
              'east',
              'south',
              'zoomIn',
              'zoomOut',
              'recentre',
            ] as const
          ).map((command) => (
            <button
              key={command}
              type="button"
              data-camera={command}
              disabled={!needsMap || paused}
              onClick={() => activeHandle.current?.camera?.(command)}
            >
              {text(language, `map.${command}`)}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
  const controls = compactControls ? (
    <details className="map-control-panel" dir={direction(language)}>
      <summary>{text(language, 'map.controls')}</summary>
      {controlContent}
    </details>
  ) : (
    controlContent
  );
  const host = useRef<HTMLDivElement>(null);
  const requestKey = `${theme}|${language}|${extractUrl ?? ''}`;
  const [result, setResult] = useState<{
    key: string;
    phase: 'loading' | 'ready' | 'error';
    handle?: MapHandle;
  }>({ key: '', phase: 'loading' });
  const live = needsMap && !paused;
  const phase: StagePhase = !live
    ? !needsMap
      ? 'asset-absent'
      : 'paused'
    : result.key === requestKey
      ? result.phase
      : 'loading';
  const accepted =
    directive !== null && directiveAccepted(directive.name, directive.fields);
  // One gate binds the ring, its legend and data-directive="rings" together:
  // an accepted rings directive, a drawable ring and an available port.
  const port = usePort();
  const vertices =
    accepted && directive.name === 'rings'
      ? contextRingVertices(contextRing)
      : null;
  const ring =
    vertices && port ? (
      <ContextRing language={language} vertices={vertices} port={port} />
    ) : null;
  const bound =
    directive === null
      ? 'none'
      : ring
        ? 'rings'
        : accepted
          ? 'unbound'
          : 'rejected';

  // A drawn wider ring is framed with the chosen area inside it.
  const ringOutline = ring ? contextRing : null;
  useEffect(() => {
    const outline = selectedArea.presented?.outline ?? null;
    if (outline === null) {
      focusedOutline.current = null;
      return;
    }
    const framed = ringOutline ?? outline;
    if (phase !== 'ready' || framed === focusedOutline.current) return;
    activeHandle.current?.focusArea?.(framed);
    focusedOutline.current = framed;
  }, [selectedArea.presented?.outline, ringOutline, phase]);

  useEffect(() => {
    if (!needsMap || paused) return;
    const node = host.current;
    if (!node) return;
    let removed = false;
    let handle: MapHandle | undefined;
    const held = {
      token: 0,
      refresh: null as (() => void) | null,
    };
    const request: BasemapRequest = { theme, language, extractUrl };
    const style = extractStyle(request);
    const begin = mapStarter ?? loadStarter();
    const key = requestKey;
    void Promise.resolve()
      .then(() => begin(node, style))
      .then((next) => {
        if (removed) {
          next.remove();
          return;
        }
        handle = next;
        activeHandle.current = next;
        if (savedView.current) next.restoreCamera?.(savedView.current);
        held.token = registerPort(
          portFromHandle(next, () => {
            setRequested('open');
            currentFraction.current = '0';
            setFraction('0');
            const resetClock = clockTimestamp(clockDay(dayBasis), 0);
            if (resetClock !== null) next.setClock?.(resetClock);
          }),
        );
        const measure = (): void => {
          const width = node.clientWidth > 0 ? node.clientWidth : 320;
          const height = node.clientHeight > 0 ? node.clientHeight : 320;
          setFrame(width, height);
        };
        measure();
        held.refresh = () => {
          publishViewRevision();
          measure();
        };
        next.bindView(held.refresh);
        const initialClock = clockTimestamp(
          clockDay(dayBasis),
          Number(currentFraction.current),
        );
        if (initialClock !== null) next.setClock?.(initialClock);
        setResult({ key, phase: 'ready', handle: next });
      })
      .catch(() => {
        if (!removed) {
          setResult({ key, phase: 'error' });
          setModes((previous) => ({
            ...previous,
            photoreal: {
              ...previous.photoreal,
              available: false,
              reason: 'renderer_unavailable',
            },
          }));
        }
      });
    return () => {
      removed = true;
      savedView.current = handle?.cameraState?.() ?? savedView.current;
      activeHandle.current = null;
      if (held.refresh) handle?.unbindView(held.refresh);
      releasePort(held.token);
      handle?.remove();
    };
  }, [
    extractUrl,
    requestKey,
    needsMap,
    dayBasis,
    paused,
    theme,
    language,
    mapStarter,
  ]);

  // Answers replace the overlay on the existing map. Camera, projection and
  // the focused drawing controls survive a new layer payload.
  useEffect(() => {
    const handle = result.handle;
    if (!handle || handle !== activeHandle.current || phase !== 'ready') return;
    const visiblePayload = quiet ? null : layerPayload;
    const drawn = !!visiblePayload && !!registry;
    if (!drawn && drawnOn.current !== handle) return;
    let current = true;
    const style = extractStyle({ theme, language, extractUrl });
    void Promise.resolve()
      .then(() =>
        visiblePayload && registry
          ? overlayFactory
            ? overlayFactory(visiblePayload, registry)
            : loadOverlay(visiblePayload, style, registry)
          : loadEmptyOverlay(style),
      )
      .then((overlay) => {
        if (current && handle === activeHandle.current) {
          handle.mountOverlay(overlay);
          drawnOn.current = drawn ? handle : null;
        }
      })
      .catch(() => {
        if (current && handle === activeHandle.current)
          setResult({ key: requestKey, phase: 'error' });
      });
    return () => {
      current = false;
    };
  }, [
    layerPayload,
    quiet,
    registry,
    overlayFactory,
    phase,
    requestKey,
    theme,
    language,
    extractUrl,
    result.handle,
  ]);

  useEffect(() => {
    const handle = result.handle;
    if (!handle || handle !== activeHandle.current || phase !== 'ready') return;
    let current = true;
    void handle
      .setMode?.(mode, (value) => {
        if (current) setCredit({ mode, text: value });
      })
      .catch((error: unknown) => {
        if (current) {
          setRequested('open');
          setModes((previous) => ({
            ...previous,
            [mode]: {
              ...previous[mode],
              available: false,
              reason: modeFailureReason(error),
            },
          }));
        }
      });
    return () => {
      current = false;
    };
  }, [mode, phase, requestKey, result.handle]);

  useEffect(() => {
    const handle = result.handle;
    if (!handle || handle !== activeHandle.current || phase !== 'ready') return;
    const controller = new AbortController();
    const unsubscribe = handle.onModeError?.((failed, reason = 'network') => {
      setRequested('open');
      setModes((previous) => ({
        ...previous,
        [failed]: { ...previous[failed], available: false, reason },
      }));
      void requestLocal('/api/map-modes', {
        cache: 'no-store',
        signal: controller.signal,
      })
        .then(async (response) =>
          response.ok ? parseModes(await response.json()) : null,
        )
        .then((next) => {
          if (!controller.signal.aborted && next)
            setModes({
              ...next,
              [failed]:
                reason === 'renderer_unavailable' || next[failed].available
                  ? { ...next[failed], available: false, reason }
                  : next[failed],
            });
        })
        .catch(() => undefined);
    });
    return () => {
      controller.abort();
      unsubscribe?.();
    };
  }, [phase, requestKey, result.handle]);

  if (phase === 'asset-absent') {
    return (
      <section
        className="stage stage-plain"
        lang={language}
        dir="ltr"
        data-state="asset-absent"
        data-directive={bound}
        aria-label={text(language, 'shell.stage')}
        inert={inert ? true : undefined}
      >
        <div className="stage-sea" data-part="sea">
          <span className="visually-hidden">{text(language, 'stage.sea')}</span>
        </div>
        <div className="stage-land" data-part="land">
          <span className="visually-hidden">
            {text(language, 'stage.land')}
          </span>
        </div>
        {controls}
        <MapCredits
          language={language}
          mode={mode}
          credit={credit.mode === mode ? credit.text : ''}
        />
        <LayerChrome
          language={language}
          collapsible={compactControls}
          payload={quiet ? null : layerPayload}
          registry={registry}
          onOpenChain={onOpenChain}
        />
        {canvas}
        {ring}
      </section>
    );
  }

  return (
    <section
      className="stage"
      lang={language}
      dir="ltr"
      data-state={phase}
      data-directive={bound}
      aria-label={text(language, 'shell.stage')}
      inert={inert ? true : undefined}
    >
      <div ref={host} className="stage-host" />
      {!compactControls || phase !== 'ready' ? (
        <p className="stage-status">{text(language, phaseKey(phase))}</p>
      ) : null}
      {controls}
      <MapCredits
        language={language}
        mode={mode}
        credit={credit.mode === mode ? credit.text : ''}
      />
      <LayerChrome
        language={language}
        collapsible={compactControls}
        payload={quiet ? null : layerPayload}
        registry={registry}
        onOpenChain={onOpenChain}
      />
      {canvas}
      {ring}
    </section>
  );
}

function LayerChrome({
  collapsible,
  language,
  payload,
  registry,
  onOpenChain,
}: {
  language: Language;
  collapsible?: boolean;
  payload: LayerPayload | null;
  registry: FactRegistry | null;
  onOpenChain?: (factId: string) => void;
}) {
  if (!payload) return null;
  if (!registry) {
    return (
      <LayerPlate language={language}>
        <p data-part="layer-refusal" data-refusal="registry_absent">
          {text(language, 'layers.refused.registry')}
        </p>
      </LayerPlate>
    );
  }
  const content = (
    <PublicLayers
      payload={payload}
      language={language}
      registry={registry}
      onOpenChain={onOpenChain ?? (() => undefined)}
    />
  );
  return collapsible ? (
    <details className="layer-inspector" dir={direction(language)}>
      <summary>{text(language, 'layers.choose')}</summary>
      {content}
    </details>
  ) : (
    content
  );
}

export function MapCredits({
  language,
  mode = 'open',
  credit = '',
}: {
  language: Language;
  mode?: MapMode;
  credit?: string;
}) {
  if (mode === 'photoreal')
    return (
      <p
        className="stage-credits"
        data-part="attribution"
        dir={direction(language)}
      >
        {credit ? (
          <FactChip
            variant="reference"
            kind="published_text"
            value={credit}
            recordId="map-photoreal-credit"
            language={language}
          />
        ) : null}
      </p>
    );
  return (
    <div
      className="stage-credits"
      data-part="attribution"
      dir={direction(language)}
    >
      <p>{text(language, 'stage.attribution')}</p>
      {mode === 'satellite' && credit ? (
        <details>
          <summary>{text(language, 'mapModes.credits')}</summary>
          <p dir="auto">
            <FactChip
              variant="reference"
              kind="published_text"
              value={credit}
              recordId="map-satellite-credit"
              language={language}
            />
          </p>
        </details>
      ) : null}
    </div>
  );
}

function phaseKey(
  phase: Exclude<StagePhase, 'asset-absent'>,
): 'stage.loading' | 'stage.ready' | 'stage.paused' | 'stage.error' {
  if (phase === 'ready') return 'stage.ready';
  if (phase === 'paused') return 'stage.paused';
  if (phase === 'error') return 'stage.error';
  return 'stage.loading';
}

async function loadEmptyOverlay(
  style: ReturnType<typeof extractStyle>,
): Promise<OverlayMount> {
  const overlay = await import('./layers/overlay');
  return overlay.overlayFor(
    null,
    overlay.firstLabelLayerId(style),
    undefined,
    true,
  );
}

async function loadOverlay(
  payload: LayerPayload | null,
  style: ReturnType<typeof extractStyle>,
  registry: FactRegistry | null,
): Promise<OverlayMount> {
  const overlay = await import('./layers/overlay');
  return overlay.overlayFor(
    payload,
    overlay.firstLabelLayerId(style),
    registry ?? undefined,
    true,
  );
}

function loadStarter(): MapStarter {
  return async (container, style) => {
    const boot = await import('./map-boot');
    return boot.startMap(container, style);
  };
}
