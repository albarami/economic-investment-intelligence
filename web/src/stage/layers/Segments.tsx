/**
 * Renders a typed segment list. It does not scan or split a string.
 */
import { FactChip } from '../../facts/FactChip';
import type { Language } from '../../i18n';
import type { TextSegment } from './payload';

export function SegmentText({
  segments,
  language,
}: {
  segments: readonly TextSegment[];
  language: Language;
}) {
  return segments.map((segment, index) => {
    if (segment.kind === 'plain') {
      return <bdi key={index}>{segment.text}</bdi>;
    }
    return (
      <FactChip
        key={index}
        variant="reference"
        language={language}
        kind={segment.referenceKind}
        value={segment.value}
        recordId={segment.recordId}
      />
    );
  });
}
