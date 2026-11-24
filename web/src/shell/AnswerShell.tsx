/**
 * Stage, Brief and the source-chain drawer. No fixture is mounted here.
 */
import { useEffect, useId, useRef, useState, type ReactElement } from 'react';

import { Brief } from '../brief/Brief';
import type { AnswerDraft } from '../brief/catalogue';
import type { FetchLike } from '../api/areas';
import type { StoryRings } from '../api/public-opening';
import { createSameOriginFetch } from '../api/areas';
import type { Presented } from '../controls/present';
import { AreaOutline } from '../controls/AreaOutline';
import { AreaSummary } from '../controls/AreaSummary';
import { DrawTools } from '../controls/DrawTools';
import { SourceChainDrawer } from '../facts/SourceChainDrawer';
import type { FactRegistry } from '../facts/registry';
import { direction, text, type Language } from '../i18n';
import {
  adoptAreaClient,
  registerLayers,
  releaseOwnedClient,
} from '../state/area-actions';
import { useArea } from '../state/store';
import { Stage, type MapStarter } from '../stage/Stage';
import type { LayerNotice, LayerPayload } from '../stage/layers/payload';

export function AnswerShell({
  language,
  theme,
  extractUrl,
  registry = null,
  draft = null,
  receiptHref,
  paused = false,
  mapStarter,
  sourceLayers = null,
  layerNotice = null,
  areaClient = null,
  renderBrief,
  quiet = false,
  rings = null,
}: {
  language: Language;
  theme: 'dark' | 'light';
  extractUrl: string | null;
  registry?: FactRegistry | null;
  draft?: AnswerDraft | null;
  receiptHref?: string;
  paused?: boolean;
  mapStarter?: MapStarter;
  /** Layers the Stage already holds. Null when this base has none. */
  sourceLayers?: LayerPayload | null;
  /** A closed absence and the pending access panel beside the layers. */
  layerNotice?: LayerNotice | null;
  /** Stand-in for a shell test. Production leaves this unset. */
  areaClient?: FetchLike | null;
  renderBrief?: (
    open: (factId: string) => void,
    clearDrawer: () => void,
  ) => ReactElement;
  quiet?: boolean;
  /** A story's accepted rings directive with its resolved wider outline. */
  rings?: StoryRings | null;
}) {
  const area = useArea();
  const [opener, setOpener] = useState<HTMLElement | null>(null);
  const returnFocus = useRef(false);
  // The open fact and the registry it came from: a chip of a read with its
  // own chain (the building heights) opens that chain, never the shell's.
  const [openChain, setOpenChain] = useState<{
    id: string;
    registry: FactRegistry | null;
  } | null>(null);
  const openId = openChain?.id ?? null;
  const [expanded, setExpanded] = useState(false);
  const sheetControl = useRef<HTMLButtonElement>(null);
  const controlFocused = useRef(false);
  const briefId = useId();

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = direction(language);
    document.documentElement.dataset.theme = theme;
  }, [language, theme]);

  useEffect(() => {
    const adopted = adoptAreaClient(areaClient ?? createSameOriginFetch());
    if (sourceLayers) registerLayers(sourceLayers);
    return () => {
      if (adopted) releaseOwnedClient();
      if (sourceLayers) registerLayers(null);
    };
  }, [areaClient, sourceLayers]);

  useEffect(() => {
    const phone = window.matchMedia?.('(max-width: 767px)');
    if (!phone) return;
    const onResize = () => {
      // The phone control disappears on larger screens. Keep focus on the answer.
      if (
        !phone.matches &&
        (document.activeElement === sheetControl.current ||
          controlFocused.current)
      ) {
        controlFocused.current = false;
        document.getElementById(briefId)?.focus();
      }
    };
    phone.addEventListener('change', onResize);
    return () => phone.removeEventListener('change', onResize);
  }, [briefId]);

  function open(factId: string, from?: FactRegistry) {
    setOpener(
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null,
    );
    setOpenChain({ id: factId, registry: from ?? registry });
  }

  function close() {
    returnFocus.current = true;
    setOpenChain(null);
  }

  useEffect(() => {
    if (openId !== null || !returnFocus.current) return;
    returnFocus.current = false;
    opener?.focus();
  }, [openId, opener]);

  return (
    <div
      className="shell"
      data-sheet-expanded={expanded}
      data-theme={theme}
      lang={language}
      dir={direction(language)}
    >
      <div className="stage-column" inert={openId !== null ? true : undefined}>
        <Stage
          language={language}
          theme={theme}
          extractUrl={extractUrl}
          paused={paused}
          directive={draft?.directive ?? rings?.directive ?? null}
          contextRing={draft?.directive ? null : (rings?.outline ?? null)}
          mapStarter={mapStarter}
          inert={openId !== null}
          layerPayload={shownLayers(
            area.presented,
            area.filtered,
            sourceLayers,
          )}
          layerNotice={layerNotice}
          registry={registry}
          onOpenChain={open}
          canvas={<AreaOutline language={language} />}
          quiet={quiet}
          compactControls={Boolean(renderBrief)}
        />
        {!renderBrief ? <DrawTools language={language} /> : null}
        {renderBrief && !quiet ? (
          <details
            className="drawing-disclosure"
            dir={direction(language)}
            onClick={(event) => {
              if (
                event.target instanceof Element &&
                event.target.closest(
                  '[data-tool],[data-part="preset"],[data-part="use-area"],[data-part="cancel-area"]',
                )
              )
                event.currentTarget.open = false;
            }}
          >
            <summary>{text(language, 'draw.tools')}</summary>
            <DrawTools language={language} />
          </details>
        ) : null}
      </div>
      <div
        className="answer-sheet"
        data-expanded={expanded}
        inert={openId !== null}
        onKeyDown={(event) => {
          if (event.key !== 'Escape' || !expanded || openId !== null) return;
          if (
            window.matchMedia &&
            !window.matchMedia('(max-width: 767px)').matches
          )
            return;
          event.preventDefault();
          setExpanded(false);
          sheetControl.current?.focus();
        }}
      >
        <button
          ref={sheetControl}
          type="button"
          className="sheet-toggle"
          aria-expanded={expanded}
          aria-controls={briefId}
          onFocus={() => {
            controlFocused.current = true;
          }}
          onBlur={() => {
            // CSS can hide and blur the control before the media event. Retain
            // that handoff until onResize; ordinary phone focus moves clear it.
            if (
              !window.matchMedia ||
              window.matchMedia('(max-width: 767px)').matches
            ) {
              controlFocused.current = false;
            }
          }}
          onClick={() => setExpanded((value) => !value)}
        >
          {text(language, expanded ? 'sheet.collapse' : 'sheet.expand')}
        </button>
        <div className="brief-column">
          {renderBrief ? (
            renderBrief(open, () => setOpenChain(null))
          ) : (
            <Brief
              id={briefId}
              language={language}
              registry={registry}
              draft={draft}
              onOpen={open}
              inert={openId !== null}
            />
          )}
          {!quiet ? <AreaSummary language={language} /> : null}
        </div>
      </div>
      {openChain?.registry ? (
        <SourceChainDrawer
          factId={openChain.id}
          registry={openChain.registry}
          language={language}
          receiptHref={receiptHref}
          onClose={close}
        />
      ) : null}
    </div>
  );
}

function shownLayers(
  presented: Presented | null,
  filtered: LayerPayload | null,
  sourceLayers: LayerPayload | null,
): LayerPayload | null {
  if (presented?.showLayers) return filtered;
  return sourceLayers;
}
