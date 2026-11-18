import { createElement } from 'react';
import { checkWording, wording } from '../wording.ts';
import type { Selection } from '../native-dispatch.ts';

export function note(selection: Selection) {
  return createElement(
    'output',
    null,
    checkWording(
      selection.withheld ? wording.withheld : wording.valid,
      selection.withheld,
    ),
  );
}
export const adapter = {
  encode: (raw: string) => raw,
  decode: (raw: string) => raw,
  render: note,
};
