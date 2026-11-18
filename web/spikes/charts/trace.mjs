const finite = (v) => typeof v === 'number' && Number.isFinite(v) && v >= 0;
const fail = (failure) => ({ ok: false, failure });
// Timing-policy unit checker, deliberately not a native-evidence authenticator.
export function judge(trace, identity) {
  if (!trace || Array.isArray(trace) || typeof trace !== 'object')
    return fail('shape');
  const keys = [
    'identity',
    'device',
    'browser',
    'viewport',
    'owner',
    'capture',
    'active',
    'latencies',
    'frames',
    'crossfade',
    'heapGrowth',
    'storyLoops',
    'summary',
  ];
  if (Object.keys(trace).sort().join() !== keys.sort().join())
    return fail('shape');
  if (JSON.stringify(trace.identity) !== JSON.stringify(identity))
    return fail('identity');
  if (
    !['laptop', 'phone'].includes(trace.device) ||
    typeof trace.browser !== 'string' ||
    /headless|automation/i.test(trace.browser) ||
    !trace.browser ||
    trace.owner !== true ||
    !trace.capture
  )
    return fail('native');
  if (
    !Array.isArray(trace.viewport) ||
    trace.viewport.length !== 2 ||
    !trace.viewport.every((v) => finite(v) && v > 0)
  )
    return fail('viewport');
  if (
    trace.active !== true ||
    !Array.isArray(trace.latencies) ||
    trace.latencies.length !== 200 ||
    !trace.latencies.every(finite) ||
    !Array.isArray(trace.frames) ||
    !trace.frames.length ||
    !trace.frames.every((v) => finite(v) && v > 0)
  )
    return fail('workload');
  const sorted = [...trace.latencies].sort((a, b) => a - b);
  const p95 = sorted[Math.ceil(sorted.length * 0.95) - 1];
  if (
    !trace.summary ||
    Object.keys(trace.summary).join() !== 'p95' ||
    trace.summary.p95 !== p95
  )
    return fail('summary');
  if (!(p95 < 100)) return fail('latency');
  const duration = trace.frames.reduce((a, b) => a + b, 0);
  if (duration < 30000 || !((trace.frames.length * 1000) / duration > 30))
    return fail('playback');
  if (trace.frames.some((v) => v > 33)) return fail('frame');
  if (!finite(trace.crossfade) || trace.crossfade > 800)
    return fail('crossfade');
  if (
    !finite(trace.heapGrowth) ||
    trace.heapGrowth >= 50 ||
    trace.storyLoops !== 3
  )
    return fail('full-story-memory');
  return { ok: true, p95 };
}
