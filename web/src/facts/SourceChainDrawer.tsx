/**
 * One fact's source chain. The receipt address is injected.
 * Dates, codes and hashes render through the reference chip.
 * The chain names the producing method and its version and the real
 * sources; it never names a data origin class (decision 0035 items 1, 2
 * and 4). A withheld fact keeps its lock and its word.
 */
import { useEffect, useRef } from 'react';

import { text, type Language, type StringKey } from '../i18n';
import { FactChip } from './FactChip';
import { EvidenceMark, WithheldMark } from './ProvenanceMark';
import type { FactRegistry } from './registry';
import type { MissingLink, Reliability, Resolution } from './types';

const MISSING_KEY: Record<MissingLink, StringKey> = {
  fact: 'drawer.link.fact',
  release: 'drawer.link.release',
  table: 'drawer.link.table',
  lineage: 'drawer.link.lineage',
  method: 'drawer.link.method',
  method_version: 'drawer.link.method_version',
  source: 'drawer.link.source',
  publisher: 'drawer.link.publisher',
  dataset_or_page: 'drawer.link.dataset_or_page',
  licence_or_terms: 'drawer.link.licence_or_terms',
  retrieval_date: 'drawer.link.retrieval_date',
  hash: 'drawer.link.hash',
  release_identity: 'drawer.link.release_identity',
  input_class_source: 'drawer.link.input_class_source',
  source_kind: 'drawer.link.source_kind',
  provenance_class: 'drawer.link.provenance_class',
  companion: 'drawer.link.companion',
};

export function SourceChainDrawer({
  factId,
  registry,
  language,
  receiptHref,
  onClose,
}: {
  factId: string;
  registry: FactRegistry;
  language: Language;
  receiptHref?: string;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const resolution = registry.resolve(factId);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key !== 'Tab') return;
      const root = dialogRef.current;
      if (!root) return;
      const items = [...root.querySelectorAll<HTMLElement>('a[href], button')];
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (!first || !last) return;
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !root.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (active === last || !root.contains(active))
      ) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <aside
      ref={dialogRef}
      className="drawer"
      role="dialog"
      aria-modal="true"
      aria-labelledby="source-chain-title"
      data-fact-id={factId}
    >
      <div className="drawer-top">
        <h2 id="source-chain-title" lang="en" dir="ltr">
          {text(language, 'drawer.title')}
        </h2>
        <button
          ref={closeRef}
          type="button"
          className="drawer-close"
          onClick={onClose}
        >
          {text(language, 'drawer.close')}
        </button>
      </div>
      {resolution.status === 'ready' ? (
        <ReadyChain
          factId={factId}
          resolution={resolution}
          registry={registry}
          language={language}
          receiptHref={receiptHref}
        />
      ) : (
        <p data-part="missing">
          {resolution.status === 'refused'
            ? text(language, MISSING_KEY[resolution.missing])
            : text(language, 'drawer.missing')}
          {resolution.status === 'refused' ? (
            <span data-missing={resolution.missing} />
          ) : null}
        </p>
      )}
    </aside>
  );
}

function Pair({
  label,
  value,
  recordId,
  language,
}: {
  label: string;
  value: string;
  recordId: string;
  language: Language;
}) {
  return (
    <span className="chain-pair">
      <span className="chain-label">{label}</span>
      <bdi className="chain-value">
        <FactChip
          variant="reference"
          kind="published_text"
          value={value}
          recordId={recordId}
          language={language}
        />
      </bdi>
    </span>
  );
}

function ReadyChain({
  factId,
  resolution,
  registry,
  language,
  receiptHref,
}: {
  factId: string;
  resolution: Extract<Resolution, { status: 'ready' }>;
  registry: FactRegistry;
  language: Language;
  receiptHref?: string;
}) {
  const fact = resolution.binding.fact;
  const label = language === 'ar' ? fact.label_ar : fact.label_en;
  return (
    <div className="drawer-body">
      <div className="drawer-block">
        <p data-part="label">{label}</p>
        <div data-part="chip">
          <FactChip
            variant="value"
            size="large"
            factId={factId}
            registry={registry}
            language={language}
            onOpen={() => undefined}
            figure
          />
        </div>
        {fact.provenance === 'suppressed' ? (
          <p data-part="withheld">
            <WithheldMark language={language} />
          </p>
        ) : null}
        <p data-part="status">
          <EvidenceMark status={fact.evidence_status} language={language} />
        </p>
      </div>
      <ol data-part="why" className="thread">
        <li data-part="fact">{text(language, 'drawer.fact')}</li>
        <li data-part="table">
          <span className="chain-label">
            {text(language, 'drawer.release')}
          </span>
          <FactChip
            variant="reference"
            language={language}
            kind="published_text"
            value={resolution.table.tableName}
            recordId={resolution.table.tableName}
          />
        </li>
        <li data-part="method">
          <Pair
            label={text(language, 'drawer.method')}
            value={resolution.lineage.method}
            recordId={resolution.lineage.lineageId}
            language={language}
          />
          <FactChip
            variant="reference"
            language={language}
            kind="published_text"
            value={resolution.lineage.methodVersion}
            recordId={resolution.lineage.methodVersion}
          />
        </li>
        {resolution.sources.map((source) => (
          <li key={source.sourceId} data-part="source">
            <Pair
              label={text(language, 'drawer.publisher')}
              value={source.publisher}
              recordId={source.sourceId}
              language={language}
            />
            <Pair
              label={text(language, 'drawer.dataset')}
              value={source.datasetOrPage}
              recordId={source.sourceId}
              language={language}
            />
            <Pair
              label={text(language, 'drawer.licence')}
              value={source.licenceOrTerms}
              recordId={source.sourceId}
              language={language}
            />
            <span className="chain-label">
              {text(language, 'drawer.retrieved')}
            </span>
            <FactChip
              variant="reference"
              language={language}
              kind="calendar_date"
              value={source.retrievalDate}
              recordId={source.sourceId}
            />
            <span className="chain-label">{text(language, 'drawer.hash')}</span>
            <FactChip
              variant="reference"
              language={language}
              kind="published_text"
              value={source.sha256}
              recordId={source.sourceId}
            />
          </li>
        ))}
      </ol>
      <div className="drawer-block">
        <p data-part="coverage">
          {fact.coverage_keys.map((key) => (
            <span key={key}>{sentence(language, 'coverage', key)}</span>
          ))}
        </p>
        <p data-part="caveat">
          {fact.caveat_keys.map((key) => (
            <span key={key}>{sentence(language, 'caveat', key)}</span>
          ))}
        </p>
        <p data-part="reliability">
          {text(language, reliabilityKey(fact.reliability))}
        </p>
        {receiptHref ? (
          <a data-part="receipt" href={receiptHref}>
            {text(language, 'drawer.receipt')}
          </a>
        ) : null}
      </div>
    </div>
  );
}

const RELIABILITY_KEY: Record<Reliability, StringKey> = {
  standard: 'drawer.reliability.standard',
  low_count: 'drawer.reliability.low_count',
  not_applicable: 'drawer.reliability.not_applicable',
};

function reliabilityKey(value: Reliability): StringKey {
  return RELIABILITY_KEY[value];
}

function sentence(
  language: Language,
  kind: 'coverage' | 'caveat',
  key: string,
): string {
  const full = `${kind}.${key}` as 'coverage.rows_kept' | 'caveat.limits_named';
  if (full === 'coverage.rows_kept' || full === 'caveat.limits_named')
    return text(language, full);
  return '';
}
