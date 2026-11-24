import { useEffect, useId, useRef, useState } from 'react';
import {
  createSameOriginFetch,
  postResolve,
  type ResolveCandidate,
} from '../api/areas';
import {
  postAddressSearch,
  requestLocal,
  type AddressSearchHit,
} from '../api/address-search.mjs';
import { FactChip } from '../facts/FactChip';
import { text, type Language } from '../i18n';
import { parseModes } from '../stage/map-modes';
import { activePort } from '../state/area-actions';

/**
 * Offline gazetteer/activity picker. Candidates are typed; labels cannot
 * contain numerals. While the server reports the keyed imagery route
 * (the satellite availability of /api/map-modes), the place picker also
 * offers the live address search on submit: the typed text goes only to
 * the local server, the returned label is shown as opaque published
 * text, and the map flies to its point. Nothing of the result is stored.
 */
export function ResolvePicker({
  language,
  kind,
  onSelect,
}: {
  language: Language;
  kind: 'place' | 'activity';
  onSelect: (candidate: ResolveCandidate) => void;
}) {
  const id = useId();
  const [query, setQuery] = useState('');
  const [candidates, setCandidates] = useState<readonly ResolveCandidate[]>([]);
  const [state, setState] = useState<'idle' | 'loading' | 'no_data' | 'shown'>(
    'idle',
  );
  const [keyed, setKeyed] = useState(false);
  const [addressResult, setAddressResult] = useState<AddressSearchHit | null>(
    null,
  );
  const generation = useRef(0);

  useEffect(
    () => () => {
      generation.current += 1;
    },
    [],
  );

  function runAddressSearch(token: number, text: string) {
    void postAddressSearch(text, language)
      .then((outcome) => {
        if (token !== generation.current) return;
        if (outcome.state === 'gazetteer_only') {
          setKeyed(false);
          return;
        }
        const first = outcome.results[0];
        if (!first) return;
        setAddressResult(first);
        activePort()?.focusPoint?.(first.point);
      })
      .catch(() => undefined);
  }

  function offerAddressSearch(token: number, text: string) {
    void requestLocal('/api/map-modes', { cache: 'no-store' })
      .then(async (response) =>
        response.ok ? parseModes(await response.json()) : null,
      )
      .then((modes) => {
        if (token !== generation.current) return;
        const available = modes?.satellite.available === true;
        setKeyed(available);
        if (available) runAddressSearch(token, text);
      })
      .catch(() => undefined);
  }

  function resolveGazetteer(token: number) {
    void postResolve(
      { text: query, lang: language, kind },
      createSameOriginFetch(),
    )
      .then((answer) => {
        if (token !== generation.current) return;
        if (answer.kind !== 'envelope' || answer.envelope.status !== 'OK') {
          setState('no_data');
          return;
        }
        setCandidates(
          answer.envelope.payload?.candidates.filter(
            (item) => item.kind === kind,
          ) ?? [],
        );
        setState('shown');
      })
      .catch(() => {
        if (token === generation.current) setState('no_data');
      });
  }

  return (
    <form
      className="resolve-picker"
      data-picker={kind}
      onSubmit={(event) => {
        event.preventDefault();
        const token = ++generation.current;
        setCandidates([]);
        setAddressResult(null);
        setState('loading');
        if (kind === 'place') offerAddressSearch(token, query);
        resolveGazetteer(token);
      }}
    >
      <label htmlFor={id}>
        {text(language, kind === 'place' ? 'draw.namedPlace' : 'draw.activity')}
      </label>
      <input
        id={id}
        value={query}
        autoComplete="off"
        onChange={(event) => {
          generation.current += 1;
          setQuery(event.target.value);
          setCandidates([]);
          setAddressResult(null);
          setState('idle');
        }}
      />
      <button type="submit" disabled={!query.trim() || state === 'loading'}>
        {text(language, 'draw.find')}
      </button>
      {kind === 'place' && !keyed ? (
        <p>{text(language, 'draw.gazetteerOnly')}</p>
      ) : null}
      {state === 'no_data' && addressResult === null ? (
        <p role="status">{text(language, 'draw.noMatch')}</p>
      ) : null}
      {addressResult ? (
        <p data-part="address-result" role="status">
          <span className="selection-caption">
            {text(language, 'draw.addressResult')}
          </span>
          <FactChip
            variant="reference"
            kind="published_text"
            value={addressResult.label}
            recordId="address-search-result"
            language={language}
          />
        </p>
      ) : null}
      <div className="picker-results">
        {candidates.map((candidate) => (
          <button
            type="button"
            key={candidate.key}
            data-candidate={candidate.key}
            onClick={() => {
              onSelect(candidate);
              generation.current += 1;
              setCandidates([]);
              setQuery('');
              setAddressResult(null);
              setState('idle');
            }}
          >
            <bdi>
              {language === 'ar' ? candidate.label_ar : candidate.label_en}
            </bdi>
          </button>
        ))}
      </div>
    </form>
  );
}
