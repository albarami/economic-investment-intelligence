// A chart-only requestAnimationFrame loop cannot establish presented marks,
// linked Fact-chip/table completion, parse attribution or full-story memory.
// Refuse collection until those instrumentation contracts are reviewed.
export function startRecording(): never {
  throw new Error('blocked-native-instrumentation-contract');
}
