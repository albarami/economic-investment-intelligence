import { useEffect, useMemo, useRef, useState } from 'react';
import { loadPublicLayer, type PublicLayerKey } from '../api/public-layer';
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
  'fc_firms_per_tower',
] as const;
type LayerKey = PublicLayerKey | 'fc_firms_per_tower';

export function MountedPublicShell({ extractUrl }: { extractUrl: string }) {
  const [mounted, setMounted] = useState<Awaited<
    ReturnType<typeof loadPublicLayer>
  > | null>(null);
  const [mountedExtract, setMountedExtract] = useState<string | null>(null);
  const [language, setLanguage] = useState<Language>(
    requestParam('lang') === 'ar' ? 'ar' : 'en',
  );
  const theme = requestParam('theme') === 'light' ? 'light' : 'dark';
  const [scene, setScene] = useState<'opening' | 'area'>('opening');
  const [layer, setLayer] = useState<LayerKey>('zone_electricity_growth');
  const [layerFailed, setLayerFailed] = useState(false);
  const [story, setStory] = useState<
    | (StoryEvidence & { selection: ReturnType<typeof selectedAreaRequest> })
    | null
  >(null);
  const [busyness, setBusyness] = useState<{
    input: RegistryInput;
    cards: ContextPayload[];
  } | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const generation = useRef(0);
  const layerGeneration = useRef(0);
  const area = useArea();
  useEffect(() => {
    let active = true;
    void loadBasemapUrl()
      .then((url) => {
        if (active) setMountedExtract(url === extractUrl ? url : null);
      })
      .catch(() => {
        if (active) setMountedExtract(null);
      });
    return () => {
      active = false;
    };
  }, [extractUrl]);
  useEffect(() => {
    const token = ++layerGeneration.current;
    void loadPublicLayer(layer)
      .then((result) => {
        if (token !== layerGeneration.current) return;
        setMounted(result);
        setLayerFailed(false);
      })
      .catch(() => {
        if (token !== layerGeneration.current) return;
        setMounted(null);
        setLayerFailed(true);
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
    setFailed(false);
    setScene('opening');
    setLayer('zone_electricity_growth');
  }
  async function run(activity: string) {
    const selection = selectedAreaRequest();
    if (!selection) return;
    const token = ++generation.current;
    setPending(true);
    setFailed(false);
    setStory(null);
    try {
      const answer = await runPublicStory(activity, language, selection);
      if (token === generation.current && selection === selectedAreaRequest())
        setStory({ ...answer, selection });
    } catch {
      if (token === generation.current) setFailed(true);
    } finally {
      if (token === generation.current) setPending(false);
    }
  }
  return (
    <div className="opening-app" data-opening-scene={scene}>
      <AnswerShell
        language={language}
        theme={theme}
        extractUrl={mountedExtract}
        sourceLayers={mounted?.payload ?? null}
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
                  failed={failed}
                  onRun={(activity) => {
                    void run(activity);
                  }}
                  onOpen={onOpen}
                  onReset={() => {
                    clearDrawer();
                    reset();
                  }}
                />
                <label className="layer-chooser">
                  {text(language, 'layers.select')}
                  <select
                    value={layer}
                    onChange={(event) => {
                      setMounted(null);
                      setLayer(event.target.value as LayerKey);
                      setLayerFailed(false);
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
                  <p role="alert">{text(language, 'layers.unavailable')}</p>
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
                                .catch(() => {
                                  if (token === generation.current)
                                    setFailed(true);
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
