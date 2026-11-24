import type { ChainRecord } from './release-shape.mjs';
export const VERSION: string;
export const PIPELINE: { name: string; version: string };
export const REGISTER_PIPELINE: { name: string; version: string };
export const METHODS: Record<
  string,
  { version: string; implementation: string }
>;
export const GENERATORS: Record<
  string,
  { version: string; implementation: string }
>;
export function validGenerator(value: unknown): boolean;
export function completeChain(chain: unknown): chain is ChainRecord;
export function completeFactChain(fact: {
  provenance: string;
  origin?: string;
  chain: unknown;
}): boolean;
