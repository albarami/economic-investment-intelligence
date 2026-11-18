import type { bufferedStream } from './stream.ts';
export type PlainEvent = {
  run: string;
  seq: number;
  kind: string;
  data?: string;
};
export function eventMachine(stream: ReturnType<typeof bufferedStream>) {
  let next = 0;
  let state = 'idle';
  return async (event: PlainEvent) => {
    const expectedKeys =
      event.kind === 'chunk'
        ? ['run', 'seq', 'kind', 'data']
        : ['run', 'seq', 'kind'];
    if (
      JSON.stringify(Object.keys(event)) !== JSON.stringify(expectedKeys) ||
      event.run !== 'fixture' ||
      event.seq !== next ||
      state === 'terminal'
    )
      throw new Error('EVENT');
    next += 1;
    if (event.kind === 'start' && state === 'idle') {
      state = 'running';
      return;
    }
    if (state !== 'running') throw new Error('EVENT');
    if (event.kind === 'chunk' && typeof event.data === 'string') {
      stream.push(new TextEncoder().encode(event.data));
      return;
    }
    state = 'terminal';
    if (event.kind === 'cancel') {
      stream.cancel();
      return;
    }
    if (event.kind === 'finish') {
      await stream.finish();
      return;
    }
    throw new Error('EVENT');
  };
}
