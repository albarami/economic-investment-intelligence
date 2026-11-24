import { useState } from 'react';
import type { ContextPayload } from '../cards/PublicContextCard';
import { ContextCards } from './ContextCards';
import { Brief } from '../brief/Brief';
import { fragmentField } from '../brief/catalogue';
import { FactChip } from '../facts/FactChip';
import type { FactRegistry } from '../facts/registry';
import { text, type Language } from '../i18n';
import { useArea } from '../state/store';
import { selectedAreaRequest, submitPlaceArea } from '../state/area-actions';
import {
  DISTANCE_PRESETS,
  WALK_PRESETS,
  DRIVE_PRESETS,
} from '../controls/presets';
import { ResolvePicker } from './ResolvePicker';
import type { ActivityCandidate, PlaceCandidate } from '../api/areas';

export function PublicStory({
  language,
  registry,
  cards,
  pending,
  failed,
  onRun,
  onOpen,
  onReset,
}: {
  language: Language;
  registry: FactRegistry | null;
  cards: readonly ContextPayload[];
  pending: boolean;
  failed: boolean;
  onRun: (activity: string) => void;
  onOpen: (factId: string) => void;
  onReset: () => void;
}) {
  const area = useArea();
  const [activity, setActivity] = useState<ActivityCandidate | null>(null);
  const [place, setPlace] = useState<PlaceCandidate | null>(null);
  const [pickerEpoch, setPickerEpoch] = useState(0);
  return (
    <section className="public-story" data-scene="area">
      <h1>{text(language, 'opening.action.site')}</h1>
      {activity ? (
        <p data-part="activity-selected">
          <span className="selection-caption">
            {text(language, 'story.activityLabel')}
          </span>
          <bdi>{language === 'ar' ? activity.label_ar : activity.label_en}</bdi>
        </p>
      ) : null}
      {place ? (
        <p data-part="place-selected">
          <span className="selection-caption">
            {text(language, 'story.placeLabel')}
          </span>
          <bdi>{language === 'ar' ? place.label_ar : place.label_en}</bdi>
        </p>
      ) : null}
      <details
        className="story-selection"
        key={cards.length ? 'result' : 'selection'}
        open={!cards.length}
        onToggle={(event) => {
          if (!event.currentTarget.open) setPickerEpoch((epoch) => epoch + 1);
        }}
      >
        <summary>{text(language, 'story.selection')}</summary>
        <ResolvePicker
          language={language}
          kind="activity"
          onSelect={(candidate) => {
            if (candidate.kind === 'activity') setActivity(candidate);
          }}
        />
        <ResolvePicker
          key={pickerEpoch}
          language={language}
          kind="place"
          onSelect={(candidate) => {
            if (candidate.kind === 'place') setPlace(candidate);
          }}
        />
        <p className="story-caption">
          {text(language, 'layers.boundaries.absent')}
        </p>
        {place ? (
          <div className="named-presets" data-part="named-presets">
            {[...DISTANCE_PRESETS, ...WALK_PRESETS, ...DRIVE_PRESETS].map(
              (preset) => (
                <button
                  type="button"
                  key={preset.id}
                  data-place-preset={preset.id}
                  onClick={() => {
                    void submitPlaceArea(place.key, preset.id);
                  }}
                >
                  <span>
                    {text(
                      language,
                      preset.mode === 'distance'
                        ? 'draw.radius'
                        : preset.mode === 'walk'
                          ? 'draw.mode.walk'
                          : 'draw.mode.drive',
                    )}
                  </span>
                  <FactChip
                    variant="input"
                    language={language}
                    kind="preset"
                    value={preset.value}
                    unit={preset.unit}
                    recordId={preset.recordId}
                  />
                </button>
              ),
            )}
          </div>
        ) : null}
      </details>
      <button
        type="button"
        data-action="story-next"
        disabled={!activity || !area.presented?.showLayers || pending}
        onClick={() => {
          if (activity && selectedAreaRequest()) onRun(activity.commerce_code);
        }}
      >
        {text(language, 'story.next')}
      </button>
      {pending ? <p role="status">{text(language, 'story.loading')}</p> : null}
      {failed ? (
        <p role="alert">{text(language, 'story.unavailable')}</p>
      ) : null}
      {registry && cards.length ? (
        <>
          <Brief
            language={language}
            registry={registry}
            draft={null}
            onOpen={onOpen}
          />
          <ContextCards
            language={language}
            registry={registry}
            cards={cards}
            onOpen={onOpen}
            chosenArea
          />
          <p data-fragment="foundation_decision">
            {fragmentField(
              'foundation_decision',
              language === 'ar' ? 'cheapest_test_ar' : 'cheapest_test_en',
            )}
          </p>
        </>
      ) : null}
      <button type="button" data-action="story-reset" onClick={onReset}>
        {text(language, 'story.reset')}
      </button>
    </section>
  );
}
