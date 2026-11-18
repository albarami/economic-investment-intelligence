import type { PlainEvent } from '../transport.ts';
export const transport = {
  encode: (event: PlainEvent) => event,
  decode: (event: PlainEvent) => event,
};
