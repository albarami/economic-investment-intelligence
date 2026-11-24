/** PUB-110: the fallback building-height credits while those heights are drawn. */
import { text, type Language } from '../i18n';
import { SegmentText } from './layers/Segments';
import {
  heightCredits,
  type HeightCreditInputs,
  type HeightSource,
} from './map-credits';

export function HeightCredits({
  language,
  drawn,
  inputs,
}: {
  language: Language;
  drawn: readonly HeightSource[];
  inputs: HeightCreditInputs;
}) {
  const credits = heightCredits(language, drawn, inputs);
  if (credits.kind === 'refused') {
    return (
      <p data-height-credit-refused={credits.reason}>
        {text(language, 'credits.heights.refused')}
      </p>
    );
  }
  return credits.lines.map((line) => (
    <p key={line.sourceId} data-credit={line.sourceId}>
      <SegmentText segments={line.segments} language={language} />
      {line.link ? (
        <>
          {' '}
          <a href={line.link}>{text(language, 'credits.landingPage')}</a>
        </>
      ) : null}
    </p>
  ));
}
