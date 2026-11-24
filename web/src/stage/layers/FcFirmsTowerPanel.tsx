/**
 * One panel for a selected tower or district fill.
 */
import { useState, type ReactElement } from 'react';

import { FactChip } from '../../facts/FactChip';
import type { FactRegistry } from '../../facts/registry';
import { text, type Language } from '../../i18n';
import { CompanyCard } from '../../views/CompanyCard';
import { FcFirmsLegend } from './FcFirmsLegend';
import type { FcCompanyRow, FcFirmsSection, LayerFeature } from './payload';

export function FcFirmsTowerPanel({
  language,
  registry,
  feature,
  companies,
  onOpenChain,
}: {
  language: Language;
  registry: FactRegistry;
  feature: LayerFeature;
  companies: readonly FcCompanyRow[];
  onOpenChain: (factId: string) => void;
}): ReactElement {
  const district = feature.geometry_kind === 'fill';
  const rows = district
    ? []
    : companies.filter((row) => row.feature_id === feature.feature_id);
  const [openId, setOpenId] = useState('');
  const open = rows.find((row) => row.row_id === openId);
  return (
    <section
      data-part="fc-firms-tower-panel"
      data-form={district ? 'district' : 'tower'}
    >
      {feature.fact_id ? (
        <FactChip
          variant="value"
          size="standard"
          factId={feature.fact_id}
          registry={registry}
          language={language}
          onOpen={onOpenChain}
        />
      ) : null}
      {district ? (
        <p data-note="district-level">{text(language, 'layers.fc.district')}</p>
      ) : (
        <ul>
          {rows.map((row) => (
            <li key={row.row_id}>
              <button
                type="button"
                data-company={row.row_id}
                onClick={() => setOpenId(row.row_id)}
              >
                <bdi>
                  {row.fields.find((field) => field.key === 'trade_name')?.text}
                </bdi>
              </button>
            </li>
          ))}
        </ul>
      )}
      {open ? <CompanyCard row={open} language={language} /> : null}
    </section>
  );
}

export function FcFirmsChrome({
  language,
  registry,
  section,
  sourceFactId,
  hero,
  selected,
  onOpenChain,
}: {
  language: Language;
  registry: FactRegistry;
  section: FcFirmsSection | null;
  sourceFactId: string;
  hero: string | null | undefined;
  selected: LayerFeature | undefined;
  onOpenChain: (factId: string) => void;
}): ReactElement | null {
  if (!section && !selected) return null;
  return (
    <>
      {hero === 'fc_firms_per_tower' && section ? (
        <FcFirmsLegend
          language={language}
          registry={registry}
          section={section}
          sourceFactId={sourceFactId}
          onOpenChain={onOpenChain}
        />
      ) : null}
      {selected ? (
        <FcFirmsTowerPanel
          language={language}
          registry={registry}
          feature={selected}
          companies={section?.companies ?? []}
          onOpenChain={onOpenChain}
        />
      ) : null}
    </>
  );
}
