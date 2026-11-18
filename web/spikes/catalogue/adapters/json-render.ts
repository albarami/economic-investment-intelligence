import { createElement } from 'react';
import { validateSpec } from '@json-render/core';
import { Renderer, JSONUIProvider } from '@json-render/react';
import { note } from './native.ts';
import type { Selection } from '../native-dispatch.ts';

export const adapter = {
  encode: (raw: string) => JSON.stringify({ brief: raw }),
  decode: (envelope: string) => {
    const value = JSON.parse(envelope) as { brief: string };
    if (Object.keys(value).length !== 1 || typeof value.brief !== 'string')
      throw new Error('JSON_RENDER_ENVELOPE');
    return value.brief;
  },
  render(selection: Selection) {
    const spec = {
      root: 'note',
      elements: { note: { type: 'CatalogueNote', props: {}, children: [] } },
    };
    if (!validateSpec(spec, { checkOrphans: true }).valid)
      throw new Error('JSON_RENDER_SPEC');
    const registry = { CatalogueNote: () => note(selection) };
    return createElement(JSONUIProvider, {
      registry,
      children: createElement(Renderer, { spec, registry }),
    });
  },
};
