import { FactChip } from '../../facts/FactChip';
import type { FactRegistry } from '../../facts/registry';
import { text, type Language } from '../../i18n';
import type { ClassBreakGroup } from './payload';
import { rampToken } from './ramp';

const SWATCH_EDGE = '12px';

const CLASS_TEXT = {
  band_low: 'layers.night.class.band_low',
  band_mid_low: 'layers.night.class.band_mid_low',
  band_mid: 'layers.night.class.band_mid',
  band_mid_high: 'layers.night.class.band_mid_high',
  band_high: 'layers.night.class.band_high',
} as const;

export function ClassLegend({
  group,
  language,
  registry,
  onOpenChain,
}: {
  group: ClassBreakGroup;
  language: Language;
  registry: FactRegistry;
  onOpenChain: (id: string) => void;
}) {
  return (
    <section data-part="class-legend" data-group={group.group_key ?? undefined}>
      {group.group_key ? (
        <FactChip
          variant="reference"
          kind="published_text"
          value={group.group_key}
          recordId={group.group_key}
          language={language}
        />
      ) : null}
      <ul>
        {group.breaks.map((band) => (
          <li key={band.class_id} data-class={band.class_id}>
            <span
              data-swatch={band.class_id}
              data-ramp={rampToken(band.class_id) ?? ''}
              style={{
                display: 'inline-block',
                width: SWATCH_EDGE,
                height: SWATCH_EDGE,
                background: `var(${rampToken(band.class_id)})`,
              }}
            />
            <span>{text(language, CLASS_TEXT[band.class_id])}</span>
            <FactChip
              variant="compact"
              factId={band.fact_id}
              registry={registry}
              language={language}
              onOpen={onOpenChain}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}
