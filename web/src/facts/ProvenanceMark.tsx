/**
 * The withheld mark and the evidence-status marks. Colour is not the
 * identity: each mark is a shape beside a word. No mark names a data
 * origin (decision 0035 items 1 and 2): the withheld mark shows the
 * suppression state, never the class of a figure that is shown.
 */
import type { EvidenceStatus } from './types';
import type { Language } from '../i18n';
import { text } from '../i18n';

/** The suppression treatment: grey hatch with lock and its word. */
export const WITHHELD_SHAPE = 'lock';

export const STATUS_SHAPE = {
  observed: 'disc',
  inferred: 'ring',
  still_to_test: 'diamond',
} as const;

export type StatusShape = (typeof STATUS_SHAPE)[EvidenceStatus];

export function markIdentified(shape: string | null, word: string): boolean {
  return shape !== null && shape.length > 0 && word.trim().length > 0;
}

export function shapesCollide(map: Record<string, string>): boolean {
  const values = Object.values(map);
  return new Set(values).size !== values.length;
}

function Glyph({ shape }: { shape: string }) {
  const common = {
    viewBox: '0 0 24 24',
    className: 'mark-glyph',
    'aria-hidden': true as const,
  };
  if (shape === 'lock') {
    return (
      <svg {...common}>
        <path d="M8 11 V8 a4 4 0 0 1 8 0 V11 H8 Z M6 11 H18 V21 H6 Z" />
      </svg>
    );
  }
  if (shape === 'disc') {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="8" />
      </svg>
    );
  }
  if (shape === 'ring') {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="7" fill="none" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <path d="M12 2 L22 12 L12 22 L2 12 Z" />
    </svg>
  );
}

export function WithheldMark({ language }: { language: Language }) {
  return (
    <span className="mark" data-mark="withheld" data-shape={WITHHELD_SHAPE}>
      <Glyph shape={WITHHELD_SHAPE} />
      <span className="mark-word">
        {text(language, 'drawer.class.suppressed')}
      </span>
    </span>
  );
}

export function EvidenceMark({
  status,
  language,
}: {
  status: EvidenceStatus;
  language: Language;
}) {
  const shape = STATUS_SHAPE[status];
  const word = text(language, `drawer.status.${status}`);
  return (
    <span className="mark" data-mark="status" data-shape={shape}>
      <Glyph shape={shape} />
      <span className="mark-word">{word}</span>
    </span>
  );
}
