/**
 * Legend line samples. The legend shows the suppression treatment only:
 * a grey hatch with a lock and its word. No sample is chosen by a data
 * origin class (decision 0035 items 1 and 2).
 */

export interface LineSample {
  stateKey: 'withheld';
  pattern: 'hatch-lock';
  colour: string;
  treatment: 'sample';
}

const SAMPLE_COLOUR = 'var(--eii-map-boundary)';

export function legendLineSamples(): readonly LineSample[] {
  return [
    {
      stateKey: 'withheld',
      pattern: 'hatch-lock',
      colour: SAMPLE_COLOUR,
      treatment: 'sample',
    },
  ];
}
