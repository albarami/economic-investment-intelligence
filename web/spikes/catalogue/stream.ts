import type { Context, Dispatcher, Oracle } from './native-dispatch.ts';

export function bufferedStream(
  dispatch: Dispatcher,
  context: Context,
  oracle: Oracle,
  timeline: string[],
  decode: (raw: string) => string = (raw) => raw,
) {
  const chunks: Uint8Array[] = [];
  let phase: 'buffering' | 'validating' | 'done' | 'cancelled' = 'buffering';
  return {
    push(chunk: Uint8Array) {
      if (phase !== 'buffering') return false;
      chunks.push(chunk.slice());
      return true;
    },
    cancel() {
      phase = 'cancelled';
      chunks.length = 0;
      timeline.push('cancelled');
    },
    async finish() {
      if (phase !== 'buffering') return false;
      phase = 'validating';
      timeline.push('complete');
      const size = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
      const all = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {
        all.set(chunk, offset);
        offset += chunk.length;
      }
      let raw: string;
      try {
        raw = new TextDecoder('utf-8', { fatal: true }).decode(all);
      } catch {
        phase = 'done';
        timeline.push('invalid-utf8');
        return false;
      }
      try {
        raw = decode(raw);
      } catch {
        phase = 'done';
        timeline.push('invalid-envelope');
        return false;
      }
      const result = await dispatch.prepare(raw, context, oracle);
      if ((phase as string) === 'cancelled') return false;
      timeline.push('validated');
      phase = 'done';
      if (!result.receipt) return false;
      dispatch.commit(result.receipt);
      timeline.push('committed');
      return true;
    },
  };
}
