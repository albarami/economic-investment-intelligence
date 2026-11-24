/** Closed refusal words must have a string in both application catalogues. */
export function catalogueParity(en, ar) {
  return [...new Set([...Object.keys(en), ...Object.keys(ar)])].filter(
    (key) => typeof en[key] !== 'string' || typeof ar[key] !== 'string',
  );
}
