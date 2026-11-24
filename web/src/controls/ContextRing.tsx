/**
 * The distinct wider context area of a story's accepted rings directive: one
 * dashed ring and its legend line, drawn together or not at all.
 */
import { readableOutline, type AreaOutline as Outline } from '../api/areas';
import { direction, text, type Language } from '../i18n';
import { circleBoundary } from '../stage/layers/area-filter';
import { useViewRevision } from '../state/area-actions';
import type { PinInput } from './area-request';
import type { MapPort } from './draw-session';
import { outlineRing, toPoints } from './AreaOutline';

/** The drawable vertices of a readable outline, or null. The Stage binds the
 * rings state, the ring and its legend to this one value. */
export function contextRingVertices(
  outline: Outline | null,
): readonly PinInput[] | null {
  if (!outline || !readableOutline(outline)) return null;
  if (outline.type === 'Polygon') return outlineRing(outline);
  return circleBoundary(outline.coordinates, outline.radius_m).map(
    ([longitude, latitude]) => ({ longitude, latitude }),
  );
}

export function ContextRing({
  language,
  vertices,
  port,
}: {
  language: Language;
  vertices: readonly PinInput[];
  port: MapPort;
}) {
  useViewRevision();
  const points = toPoints(vertices, port);
  return (
    <>
      <svg className="area-overlay area-lines" aria-hidden="true">
        <g data-part="context-ring">
          <polyline className="context-ring-casing" points={points} />
          <polyline className="context-ring-line" points={points} />
        </g>
      </svg>
      <p
        className="context-legend"
        data-part="context-area"
        lang={language}
        dir={direction(language)}
      >
        <svg className="context-sample" aria-hidden="true">
          <line
            className="context-ring-line"
            x1="0"
            y1="50%"
            x2="100%"
            y2="50%"
          />
        </svg>
        {text(language, 'story.widerArea')}
      </p>
    </>
  );
}
