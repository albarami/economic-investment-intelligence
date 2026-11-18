import { EventType } from '@ag-ui/core';
import { EventSchemas } from '@ag-ui/core/schemas';
import type { PlainEvent } from '../transport.ts';
export const transport = {
  encode: (event: PlainEvent) => ({
    type: EventType.CUSTOM,
    name: 'eii_catalogue',
    value: event,
  }),
  decode(input: unknown): PlainEvent {
    const parsed = EventSchemas.parse(input);
    if (
      parsed.type !== EventType.CUSTOM ||
      parsed.name !== 'eii_catalogue' ||
      JSON.stringify(Object.keys(input as object)) !==
        JSON.stringify(['type', 'name', 'value'])
    )
      throw new Error('AG_UI_EVENT');
    return parsed.value as PlainEvent;
  },
};
