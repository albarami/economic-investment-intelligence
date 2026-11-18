// Lossless buffer envelope only; the browser runtime is a separate entry.
export const adapter = {
  encode: (raw: string) => JSON.stringify({ version: 'v0.9', brief: raw }),
  decode: (envelope: string) => {
    const value = JSON.parse(envelope) as { version: string; brief: string };
    if (
      value.version !== 'v0.9' ||
      Object.keys(value).length !== 2 ||
      typeof value.brief !== 'string'
    )
      throw new Error('A2UI_ENVELOPE');
    return value.brief;
  },
};
