import type { FactChipProps } from '../../src/facts/FactChip';
import type { FactRegistry } from '../../src/facts/registry';
import { operationalMeter as meter } from './operational-meter';
declare const registry: FactRegistry;
const onOpen = () => undefined;
export const valid: FactChipProps = {
  variant: 'operational',
  language: 'en',
  meter,
  reason: null,
};
export const wrongValue: FactChipProps = {
  variant: 'value',
  size: 'inline',
  language: 'en',
  // @ts-expect-error Operational quantities cannot enter a release-fact value chip.
  factId: meter,
  registry,
  onOpen,
};
export const wrongCompact: FactChipProps = {
  variant: 'compact',
  language: 'en',
  // @ts-expect-error Operational quantities cannot enter a compact release-fact chip.
  factId: meter,
  registry,
  onOpen,
};
export const wrongOperational: FactChipProps = {
  variant: 'operational',
  language: 'en',
  // @ts-expect-error The operational form cannot take a fact identifier.
  meter: 'SYN-fact',
  reason: null,
};
export const extraFact: FactChipProps = {
  variant: 'operational',
  language: 'en',
  meter,
  reason: null,
  // @ts-expect-error A release-fact identifier is never an extra operational prop.
  factId: 'SYN-fact',
};
export const extraMeter: FactChipProps = {
  variant: 'compact',
  language: 'en',
  factId: 'SYN-fact',
  registry,
  onOpen,
  // @ts-expect-error A meter cannot accompany an otherwise valid release-fact binding.
  meter,
};
