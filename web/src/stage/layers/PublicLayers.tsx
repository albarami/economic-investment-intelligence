import { useEffect, useState, type ReactElement } from 'react';

import { FactChip } from '../../facts/FactChip';
import type { FactRegistry } from '../../facts/registry';
import { EvidenceMark, WithheldMark } from '../../facts/ProvenanceMark';
import { direction, text, type Language } from '../../i18n';
import { unimplementedReason } from './checks';
import { ClassLegend } from './ClassLegend';
import { FcFirmsChrome } from './FcFirmsTowerPanel';
import { FdiBlock } from './FdiPanel';
import { CompanyCard } from '../../views/CompanyCard';
import type { ClassBreakGroup, LayerFeature, LayerPayload } from './payload';
import { rampToken } from './ramp';
import { acceptPayload } from './refuse';
import { bindSelection } from './selection';
import {
  activeUse,
  chooseUse,
  forUse,
  landGroupKeys,
  useLandUse,
} from './land-use';
import { SegmentText } from './Segments';

const NOT_RANKED_TEXT = {
  below_ranking_floor: 'layers.not_ranked.below_ranking_floor',
  no_denominator: 'layers.not_ranked.no_denominator',
  missing_input: 'layers.not_ranked.missing_input',
} as const;

const NIGHT_CLASS = {
  band_low: 'layers.night.class.band_low',
  band_mid_low: 'layers.night.class.band_mid_low',
  band_mid: 'layers.night.class.band_mid',
  band_mid_high: 'layers.night.class.band_mid_high',
  band_high: 'layers.night.class.band_high',
} as const;

const NIGHT_DIRECTION = {
  higher: 'direction.higher',
  lower: 'direction.lower',
  equal: 'direction.equal',
} as const;

export function PublicLayers({
  payload,
  language,
  registry,
  onOpenChain,
}: {
  payload: LayerPayload;
  language: Language;
  registry: FactRegistry;
  onOpenChain: (factId: string) => void;
}) {
  const accepted = acceptPayload(payload, registry);
  const useChoice = useLandUse();
  const [selected, setSelected] = useState(payload.selected_feature_id ?? '');
  useEffect(() => {
    bindSelection(setSelected);
    return () => bindSelection(null);
  }, []);
  if (!accepted.ok) {
    const reason =
      accepted.code === 'not_implemented' && accepted.layerKey
        ? unimplementedReason(accepted.layerKey)
        : 'layers.refused';
    return (
      <LayerPlate language={language}>
        <p data-part="layer-refusal" data-refusal={accepted.code}>
          {text(language, reason)}
        </p>
      </LayerPlate>
    );
  }
  const draw = accepted.draw;
  const groups = landGroupKeys(draw.layers);
  const active = activeUse(groups, useChoice);
  const shown = forUse(draw.layers, active);
  const landGroup = shown.find((layer) => layer.key === 'land_prices')
    ?.classBreaks[0];
  const rows = shown.flatMap((layer) =>
    layer.features.map((feature) => ({ layer, feature })),
  );
  const notRankedRows = draw.layers.flatMap((layer) =>
    layer.notRanked.map((entry) => ({ layer, entry })),
  );
  const selectedNotRanked = notRankedRows.find(
    (row) => row.entry.feature_id === selected,
  );
  const selectedFeature = rows.find(
    (row) => row.feature.feature_id === selected,
  );
  const places =
    selectedFeature?.layer.key === 'public_places' ||
    selectedFeature?.layer.key === 'commercial_points';
  return (
    <LayerPlate language={language} labels={draw.labelsDrawn}>
      <p data-part="boundaries">{text(language, 'layers.boundaries.absent')}</p>
      <ul data-part="line-samples">
        {draw.lineSamples.map((sample) => (
          <li
            key={sample.stateKey}
            className="layer-sample"
            data-pattern={sample.pattern}
            data-colour={sample.colour}
          >
            <WithheldMark language={language} />
          </li>
        ))}
      </ul>
      {draw.listingsNote ? (
        <p data-note="listings">
          {text(language, 'layers.listings.incomplete')}
        </p>
      ) : null}
      {draw.layers.map((layer) =>
        layer.sourceIds.map((sourceId) => {
          const source = payload.sources.find(
            (row) => row.sourceId === sourceId,
          );
          if (!source) return null;
          return (
            <p
              key={`${layer.key}:${sourceId}`}
              data-credit={layer.key}
              data-source={sourceId}
              data-retrieved={source.retrievalDate}
            >
              <SegmentText segments={source.attribution} language={language} />
              <span data-credit-field="source-publisher">
                <SegmentText segments={source.publisher} language={language} />
              </span>
              <FactChip
                variant="reference"
                language={language}
                kind="calendar_date"
                value={source.retrievalDate}
                recordId={layer.sourceChainFactId}
              />
              {source.sourceRelease ? (
                <FactChip
                  variant="reference"
                  language={language}
                  kind={source.sourceRelease.referenceKind}
                  value={source.sourceRelease.value}
                  recordId={source.sourceRelease.recordId}
                />
              ) : null}
            </p>
          );
        }),
      )}
      {draw.night ? (
        <NightLegend
          language={language}
          night={draw.night}
          attribution={draw.nightAttribution}
          group={
            draw.layers.find((layer) => layer.key === 'night_lights')
              ?.classBreaks[0]
          }
          registry={registry}
          onOpenChain={onOpenChain}
        />
      ) : null}
      {groups.length ? (
        <div
          role="group"
          data-part="land-use"
          aria-label={text(language, 'layers.guide.use')}
        >
          {groups.map((key) => (
            <button
              key={key}
              type="button"
              data-use={key}
              aria-pressed={key === active}
              onClick={() => chooseUse(key)}
              onKeyDown={(event) => {
                if (event.key !== 'Enter' && event.key !== ' ') return;
                event.preventDefault();
                chooseUse(key);
              }}
            >
              <FactChip
                variant="reference"
                language={language}
                kind="published_text"
                value={key}
                recordId={key}
              />
            </button>
          ))}
        </div>
      ) : null}
      {landGroup ? (
        <section data-part="land-price-legend" data-group={active ?? undefined}>
          <p data-legend="guide">{text(language, 'layers.guide.name')}</p>
          <ClassLegend
            group={landGroup}
            language={language}
            registry={registry}
            onOpenChain={onOpenChain}
          />
        </section>
      ) : null}
      {draw.visibleHero === 'zone_electricity_growth' ? (
        <section data-part="hero-legend">
          <p>{text(language, 'layers.hero.name')}</p>
          {draw.layers
            .find((layer) => layer.key === 'zone_electricity_growth')
            ?.classBreaks.map((group, index) => (
              <ClassLegend
                key={index}
                group={group}
                language={language}
                registry={registry}
                onOpenChain={onOpenChain}
              />
            ))}
          <ul>
            {Object.entries(NOT_RANKED_TEXT)
              .filter(([reason]) =>
                notRankedRows.some((row) => row.entry.reason_key === reason),
              )
              .map(([reason, key]) => (
                <li key={reason}>{text(language, key)}</li>
              ))}
          </ul>
        </section>
      ) : null}
      {notRankedRows.map(({ entry }) => (
        <button
          key={entry.feature_id}
          type="button"
          data-not-ranked={entry.feature_id}
          onClick={() => setSelected(entry.feature_id)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            event.preventDefault();
            setSelected(entry.feature_id);
          }}
        >
          <SegmentText segments={entry.name_segments} language={language} />
          {text(language, 'layers.not_ranked.name')}
        </button>
      ))}
      {!selectedFeature && selectedNotRanked ? (
        <section
          data-part="not-ranked-panel"
          data-zone={selectedNotRanked.entry.feature_id}
          data-reason={selectedNotRanked.entry.reason_key}
        >
          <SegmentText
            segments={selectedNotRanked.entry.name_segments}
            language={language}
          />
          <p>
            {text(
              language,
              NOT_RANKED_TEXT[selectedNotRanked.entry.reason_key],
            )}
          </p>
          <button
            type="button"
            data-action="source-chain"
            onClick={() =>
              onOpenChain(selectedNotRanked.layer.sourceChainFactId)
            }
          >
            {text(language, 'layers.chain.action')}
          </button>
        </section>
      ) : null}
      <FcFirmsChrome
        language={language}
        registry={registry}
        section={draw.fcFirms ?? null}
        sourceFactId={
          draw.layers.find((layer) => layer.key === 'fc_firms_per_tower')
            ?.sourceChainFactId ?? ''
        }
        hero={draw.visibleHero}
        selected={
          selectedFeature?.layer.key === 'fc_firms_per_tower'
            ? selectedFeature.feature
            : undefined
        }
        onOpenChain={onOpenChain}
      />
      {draw.layers.some(
        (layer) =>
          layer.key === 'rail_plan' &&
          layer.features.some(
            (feature) =>
              feature.geometry_kind === 'point' &&
              feature.status_key === 'planned',
          ),
      ) ? (
        <p data-legend="station">{text(language, 'layers.station.planned')}</p>
      ) : null}
      {rows.map(({ feature }) => (
        <button
          key={feature.feature_id}
          type="button"
          data-feature={feature.feature_id}
          aria-label={accessibleName(feature, language)}
          onClick={() => setSelected(feature.feature_id)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            event.preventDefault();
            setSelected(feature.feature_id);
          }}
        >
          <FeatureName feature={feature} language={language} />
        </button>
      ))}
      {draw.fdiListed.length > 0 ? (
        <FdiBlock
          language={language}
          registry={registry}
          listed={draw.fdiListed}
          marks={draw.fdiMarks}
          features={
            draw.layers.find((layer) => layer.key === 'fdi_projects')
              ?.features ?? []
          }
          credits={draw.credits}
          countFacts={payload.count_facts ?? []}
          filterOptions={payload.filter_options}
          selectedId={selected}
          onOpenChain={onOpenChain}
        />
      ) : null}
      {selectedFeature && selectedFeature.layer.key !== 'fc_firms_per_tower' ? (
        <section
          data-part={places ? 'places-panel' : 'feature-panel'}
          data-layer={selectedFeature.layer.key}
        >
          {places ? (
            <p data-note="listings">
              {text(language, 'layers.listings.incomplete')}
            </p>
          ) : null}
          <p data-label="name">
            <FeatureName
              feature={selectedFeature.feature}
              language={language}
            />
          </p>
          {selectedFeature.layer.key === 'company_points' ? (
            <RegisterCompanyCard
              payload={payload}
              featureId={selectedFeature.feature.feature_id}
              language={language}
            />
          ) : null}
          {selectedFeature.feature.words?.permitted_use ? (
            <p data-label="permitted">
              <bdi>{selectedFeature.feature.words.permitted_use}</bdi>
            </p>
          ) : null}
          {selectedFeature.layer.key === 'rail_plan' &&
          selectedFeature.feature.geometry_kind === 'point' ? (
            <p data-label="station">
              {text(language, 'layers.station.planned')}
            </p>
          ) : null}
          {selectedFeature.feature.status_key === 'permitted_empty' ? (
            <p data-label="plot">
              {text(language, 'layers.plot.label')}
              <span data-caveat="plot">
                {text(language, 'layers.plot.caveat')}
              </span>
            </p>
          ) : null}
          {selectedFeature.feature.metric_key === 'parcel_area' &&
          selectedFeature.feature.fact_id ? (
            <FactChip
              variant="value"
              size="standard"
              factId={selectedFeature.feature.fact_id}
              registry={registry}
              language={language}
              onOpen={onOpenChain}
            />
          ) : null}
          <AddressNumbers
            language={language}
            address={
              selectedFeature.feature.address ??
              (selectedFeature.layer.key === 'address_points'
                ? payload.address_numbers
                : undefined)
            }
          />
          {selectedFeature.feature.fact_id &&
          selectedFeature.feature.metric_key !== 'parcel_area' ? (
            <FactChip
              variant="value"
              size="standard"
              factId={selectedFeature.feature.fact_id}
              registry={registry}
              language={language}
              onOpen={onOpenChain}
            />
          ) : null}
          {selectedFeature.feature.apportioned_from ? (
            <p
              data-part="apportion"
              data-geography={selectedFeature.feature.geography_code}
            >
              <EvidenceMark status="inferred" language={language} />
              <span>{text(language, 'layers.apportion.method')}</span>
              <FactChip
                variant="reference"
                language={language}
                kind="published_text"
                value={selectedFeature.feature.method_id ?? ''}
                recordId="apportion-method"
              />
              <span>{text(language, 'layers.apportion.geography')}</span>
              <FactChip
                variant="reference"
                language={language}
                kind="published_text"
                value={selectedFeature.feature.geography_code ?? ''}
                recordId="apportion-geography"
              />
            </p>
          ) : null}
          <button
            type="button"
            data-action="source-chain"
            onClick={() =>
              onOpenChain(
                selectedFeature.feature.fact_id ??
                  selectedFeature.layer.sourceChainFactId,
              )
            }
          >
            {text(language, 'layers.chain.action')}
          </button>
        </section>
      ) : null}
      {payload.visitor_fact_id ? (
        <section data-part="visitor-counts">
          <p>{text(language, 'layers.visitor.title')}</p>
          <FactChip
            variant="compact"
            factId={payload.visitor_fact_id}
            registry={registry}
            language={language}
            onOpen={onOpenChain}
          />
        </section>
      ) : null}
      {payload.estimated_people_fact_id ? (
        <section data-part="estimated-people">
          <FactChip
            variant="compact"
            factId={payload.estimated_people_fact_id}
            registry={registry}
            language={language}
            onOpen={onOpenChain}
          />
        </section>
      ) : null}
      {draw.layers.map((layer) => (
        <button
          key={`chain-${layer.key}`}
          type="button"
          data-action="source-chain"
          data-scope="layer"
          data-layer={layer.key}
          onClick={() => onOpenChain(layer.sourceChainFactId)}
        >
          {text(language, 'layers.chain.action')}
        </button>
      ))}
      {payload.split_chip && draw.splitCategories ? (
        <section data-part="split-chip">
          <span data-split-source={payload.split_chip.source_id}>
            <SegmentText
              segments={
                payload.sources.find(
                  (row) => row.sourceId === payload.split_chip?.source_id,
                )?.publisher ?? []
              }
              language={language}
            />
          </span>
          <FactChip
            variant="reference"
            language={language}
            kind="calendar_year"
            value={payload.split_chip.year}
            recordId="split-year"
          />
          <ul>
            {draw.splitCategories.map((category, index) => (
              <li key={index}>
                <SegmentText segments={category} language={language} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </LayerPlate>
  );
}

type PlateChild =
  ReactElement | null | false | undefined | readonly PlateChild[];

export function LayerPlate({
  language,
  labels,
  children,
}: {
  language: Language;
  labels?: boolean;
  children: PlateChild;
}) {
  return (
    <div
      className="layer-plate"
      data-part="public-layers"
      lang={language}
      dir={direction(language)}
      data-labels={
        labels === undefined ? undefined : labels ? 'shown' : 'hidden'
      }
    >
      {children}
    </div>
  );
}

function accessibleName(
  feature: LayerFeature,
  language: Language,
): string | undefined {
  if (feature.words?.name) return feature.words.name;
  if (feature.name_segments && feature.name_segments.length > 0)
    return undefined;
  if (feature.words?.company && feature.words.company.trim() !== '') {
    return feature.words.company;
  }
  return text(language, 'layers.feature.unnamed');
}

function FeatureName({
  feature,
  language,
}: {
  feature: LayerFeature;
  language: Language;
}) {
  if (feature.words?.name) return <bdi>{feature.words.name}</bdi>;
  if (feature.name_segments && feature.name_segments.length > 0) {
    return <SegmentText segments={feature.name_segments} language={language} />;
  }
  if (feature.words?.company && feature.words.company.trim() !== '') {
    return <bdi>{feature.words.company}</bdi>;
  }
  return <bdi>{text(language, 'layers.feature.unnamed')}</bdi>;
}

function NightLegend({
  language,
  night,
  attribution,
  group,
  registry,
  onOpenChain,
}: {
  language: Language;
  night: NonNullable<LayerPayload['night']>;
  attribution: LayerPayload['sources'][number]['attribution'];
  group: ClassBreakGroup | undefined;
  registry: FactRegistry;
  onOpenChain: (id: string) => void;
}) {
  const classKey = NIGHT_CLASS[night.class_id as keyof typeof NIGHT_CLASS];
  const directionKey =
    NIGHT_DIRECTION[night.direction as keyof typeof NIGHT_DIRECTION];
  const token = rampToken(night.class_id) ?? '';
  return (
    <div data-part="night-legend">
      <span data-legend="unit">
        {text(language, 'unit.radiance_nw_cm2_sr')}
      </span>
      <FactChip
        variant="reference"
        language={language}
        kind="calendar_month"
        value={night.month}
        recordId={night.month}
      />
      {directionKey ? (
        <span data-legend="direction">{text(language, directionKey)}</span>
      ) : null}
      {classKey ? (
        <span data-legend="class" data-ramp={token}>
          {text(language, classKey)}
        </span>
      ) : null}
      <p data-caveat={night.caveat_key}>
        {text(language, 'layers.night.caveat')}
      </p>
      {group ? (
        <ClassLegend
          group={group}
          language={language}
          registry={registry}
          onOpenChain={onOpenChain}
        />
      ) : null}
      <p data-credit="night_lights">
        <SegmentText segments={attribution} language={language} />
      </p>
    </div>
  );
}

function AddressNumbers({
  language,
  address,
}: {
  language: Language;
  address: { zone: string; street: string; building: string } | undefined;
}) {
  if (!address) return null;
  return (
    <section data-part="address-panel">
      <FactChip
        variant="reference"
        language={language}
        kind="published_text"
        value={address.zone}
        recordId="address-zone"
      />
      <FactChip
        variant="reference"
        language={language}
        kind="published_text"
        value={address.street}
        recordId="address-street"
      />
      <FactChip
        variant="reference"
        language={language}
        kind="published_text"
        value={address.building}
        recordId="address-building"
      />
    </section>
  );
}

/** A tap on an establishment point opens that register company's card. */
function RegisterCompanyCard({
  payload,
  featureId,
  language,
}: {
  payload: LayerPayload;
  featureId: string;
  language: Language;
}): ReactElement | null {
  const card = payload.company_cards?.find(
    (row) => row.feature_id === featureId,
  );
  if (!card) return null;
  return (
    <CompanyCard
      row={card}
      language={language}
      employeeCount={card.employee_count}
    />
  );
}
