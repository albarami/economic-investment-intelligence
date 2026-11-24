import { useEffect, useMemo, useRef, useState } from 'react';
import {
  composeLayers,
  loadPublicLayer,
  type PublicLayerKey,
  type PublicLayerResult,
} from '../api/public-layer';
import { bodyRefusal, refusalState, type RefusalState } from '../api/refusal';
import { RefusalNotice } from './RefusalNotice';
import { loadBasemapUrl } from '../api/release';
import {
  loadBusyness,
  listedPlaceKey,
  mergeInputs,
  runPublicStory,
  type StoryEvidence,
} from '../api/public-opening';
import { createRegistry, type RegistryInput } from '../facts/registry';
import type { ContextPayload } from '../cards/PublicContextCard';
import { text, type Language } from '../i18n';
import { PublicOpening } from '../journeys/PublicOpening';
import { PublicStory } from '../journeys/PublicStory';
import { SegmentText } from '../stage/layers/Segments';
import { resetArea, selectedAreaRequest } from '../state/area-actions';
import { useArea } from '../state/store';
import { AnswerShell } from '../shell/AnswerShell';

function requestParam(name: string): string | null {
  const search = globalThis.location?.search;
  if (typeof search !== 'string') return null;
  return new URLSearchParams(search).get(name);
}
export const PUBLIC_LAYERS = [
  'zone_electricity_growth',
  'public_places',
  'night_lights',
  'land_prices',
  'parcels',
  'rail_plan',
  'health_centres',
  'zoning',
  'commercial_points',
  'address_points',
  'landmarks',
  'fdi_projects',
  'property_prices',
  'company_points',
  'accidents',
  'fc_firms_per_tower',
] as const;
type LayerKey = PublicLayerKey | 'fc_firms_per_tower';
/** S3-T12: recorded accidents are read beside the planned rail context. */
const CONTEXT_LAYERS: Partial<Record<LayerKey, readonly LayerKey[]>> = {
  accidents: ['rail_plan'],
};
/** S3-T12: the access result is pending (PO-S3-B8-ACCESS); never a figure. */
const ACCESS_PENDING: ReadonlySet<LayerKey> = new Set(['accidents']);

export function MountedPublicShell({ extractUrl }: { extractUrl: string }) {
  const [mounted, setMounted] = useState<PublicLayerResult | null>(null);
  const [mountedExtract, setMountedExtract] = useState<string | null>(null);
  const [language, setLanguage] = useState<Language>(
    requestParam('lang') === 'ar' ? 'ar' : 'en',
  );
  const theme = requestParam('theme') === 'light' ? 'light' : 'dark';
  const [scene, setScene] = useState<'opening' | 'area'>('opening');
  const [layer, setLayer] = useState<LayerKey>('zone_electricity_growth');
  const [layerFailed, setLayerFailed] = useState<RefusalState | null>(null);
  const [basemapFailed, setBasemapFailed] = useState<RefusalState | null>(null);
  const [story, setStory] = useState<
    | (StoryEvidence & { selection: ReturnType<typeof selectedAreaRequest> })
    | null
  >(null);
  const [busyness, setBusyness] = useState<{
    input: RegistryInput;
    cards: ContextPayload[];
    refusal?: RefusalState;
  } | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState<RefusalState | null>(null);
  const generation = useRef(0);
  const layerGeneration = useRef(0);
  const area = useArea();
  useEffect(() => {
    let active = true;
    void loadBasemapUrl()
      .then((url) => {
        if (!active) return;
        if (url !== null && url !== extractUrl)
          throw bodyRefusal('chain_refused', 200, 'stage.error');
        setMountedExtract(url);
        setBasemapFailed(null);
      })
      .catch((error: unknown) => {
        if (active) {
          setMountedExtract(null);
          setBasemapFailed(refusalState(error, 'stage.error'));
        }
      });
    return () => {
      active = false;
    };
  }, [extractUrl]);
  useEffect(() => {
    const token = ++layerGeneration.current;
    void Promise.all(
      [layer, ...(CONTEXT_LAYERS[layer] ?? [])].map((key) =>
        loadPublicLayer(key),
      ),
    )
      .then((results) => composeLayers(results))
      .then((result) => {
        if (token !== layerGeneration.current) return;
        setMounted(result);
        setLayerFailed(null);
      })
      .catch((error: unknown) => {
        if (token !== layerGeneration.current) return;
        setMounted(null);
        setLayerFailed(refusalState(error, 'layers.unavailable'));
      });
    return () => {
      layerGeneration.current += 1;
    };
  }, [layer]);
  const currentStory =
    story &&
    area.presented?.showLayers &&
    story.selection === selectedAreaRequest()
      ? story
      : null;
  const input = useMemo(
    () =>
      mergeInputs([
        ...(mounted ? [mounted.input] : []),
        ...(currentStory ? [currentStory.input] : []),
        ...(busyness ? [busyness.input] : []),
      ]),
    [mounted, currentStory, busyness],
  );
  const registry = useMemo(() => createRegistry(input), [input]);
  function reset() {
    generation.current += 1;
    resetArea();
    setStory(null);
    setBusyness(null);
    setPending(false);
    setFailed(null);
    setScene('opening');
    setLayer('zone_electricity_growth');
  }
  async function run(activity: string) {
    const selection = selectedAreaRequest();
    if (!selection) return;
    const token = ++generation.current;
    setPending(true);
    setFailed(null);
    setStory(null);
    try {
      const answer = await runPublicStory(activity, language, selection);
      if (token === generation.current && selection === selectedAreaRequest())
        setStory({ ...answer, selection });
    } catch (error) {
      if (token === generation.current)
        setFailed(refusalState(error, 'story.unavailable'));
    } finally {
      if (token === generation.current) setPending(false);
    }
  }
  if (basemapFailed)
    return (
      <div lang={language} dir={language === 'ar' ? 'rtl' : 'ltr'}>
        <RefusalNotice language={language} refusal={basemapFailed} />
      </div>
    );
  return (
    <div className="opening-app" data-opening-scene={scene}>
      <AnswerShell
        language={language}
        theme={theme}
        extractUrl={mountedExtract}
        sourceLayers={mounted?.payload ?? null}
        layerNotice={
          mounted
            ? {
                noData: mounted.reason,
                accessPending: ACCESS_PENDING.has(layer),
              }
            : null
        }
        registry={registry}
        quiet={scene === 'opening'}
        rings={currentStory?.rings ?? null}
        renderBrief={(onOpen, clearDrawer) => (
          <>
            <div className="opening-language">
              <button
                type="button"
                data-action="language"
                lang={language === 'en' ? 'ar' : 'en'}
                onClick={() => {
                  const next = language === 'en' ? 'ar' : 'en';
                  setLanguage(next);
                  history.replaceState(
                    null,
                    '',
                    '/?lang=' + next + '&theme=' + theme,
                  );
                }}
              >
                {text(language, 'language.switch')}
              </button>
            </div>
            {scene === 'opening' ? (
              <PublicOpening
                language={language}
                onStart={() => setScene('area')}
              />
            ) : (
              <>
                <PublicStory
                  language={language}
                  registry={registry}
                  cards={[
                    ...(currentStory?.cards ?? []),
                    ...(busyness?.cards ?? []),
                  ]}
                  pending={pending}
                  failed={false}
                  onRun={(activity) => {
                    void run(activity);
                  }}
                  onOpen={onOpen}
                  onReset={() => {
                    clearDrawer();
                    reset();
                  }}
                />
                {failed ? (
                  <RefusalNotice language={language} refusal={failed} />
                ) : null}
                {busyness?.refusal ? (
                  <RefusalNotice
                    language={language}
                    refusal={busyness.refusal}
                  />
                ) : null}
                <label className="layer-chooser">
                  {text(language, 'layers.select')}
                  <select
                    value={layer}
                    onChange={(event) => {
                      setMounted(null);
                      setLayer(event.target.value as LayerKey);
                      setLayerFailed(null);
                    }}
                  >
                    {PUBLIC_LAYERS.map((key) => (
                      <option key={key} value={key}>
                        {text(language, `layers.name.${key}`)}
                      </option>
                    ))}
                  </select>
                </label>
                {layerFailed ? (
                  <RefusalNotice language={language} refusal={layerFailed} />
                ) : null}
                {mounted?.payload.layers.flatMap((row) =>
                  row.key === 'public_places'
                    ? row.features
                        .filter((feature) => listedPlaceKey(feature, registry))
                        .map((feature) => (
                          <button
                            type="button"
                            key={feature.feature_id}
                            data-busyness-place={
                              listedPlaceKey(feature, registry) ?? undefined
                            }
                            onClick={() => {
                              const token = generation.current;
                              void loadBusyness(
                                listedPlaceKey(feature, registry)!,
                              )
                                .then((result) => {
                                  if (token === generation.current)
                                    setBusyness(result);
                                })
                                .catch((error: unknown) => {
                                  if (token === generation.current)
                                    setFailed(
                                      refusalState(error, 'story.unavailable'),
                                    );
                                });
                            }}
                          >
                            {text(language, 'story.busyness')}
                            <bdi className="busyness-place">
                              <SegmentText
                                language={language}
                                segments={feature.name_segments ?? []}
                              />
                            </bdi>
                          </button>
                        ))
                    : [],
                )}
              </>
            )}
          </>
        )}
      />
    </div>
  );
}
