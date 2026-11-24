/** Pixel fixture clock; performance.now and native performance runs are separate. */
export function installLabClock(iso: string): void {
  const NativeDate = Date;
  const stamp = NativeDate.parse(iso);
  if (!Number.isFinite(stamp)) throw new Error('fixture_clock');
  globalThis.Date = new Proxy(NativeDate, {
    construct(target, args, newTarget) {
      return Reflect.construct(target, args.length ? args : [stamp], newTarget);
    },
    apply(target) {
      return new target(stamp).toString();
    },
    get(target, key) {
      return key === 'now' ? () => stamp : Reflect.get(target, key);
    },
  });
}
