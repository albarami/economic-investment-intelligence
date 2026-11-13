// Invented contract fixture; its frame totals are independent literal arithmetic.
export function mutationTrace() {
  return {
    contract: 'eii.performance-trace',
    version: 1,
    provenance: 'Synthetic',
    seed: 1,
    layerSet: 'hexagons-particles',
    profile: 'gate',
    codeCommit: 'synthetic-commit',
    lockSha256: `sha256:${'ab'.repeat(32)}`,
    userAgent: 'Synthetic Windows Chrome',
    webglRenderer: 'Synthetic hardware adapter',
    window: { width: 1600, height: 900 },
    canvas: { cssWidth: 1920, cssHeight: 1080 },
    drawingBuffer: { width: 1920, height: 1080 },
    devicePixelRatio: 2,
    cap: { value: 1, label: 'ASSUMPTION' },
    counts: { hexagons: 110000, particles: 50000 },
    timestamps: Array.from({ length: 3001 }, (_, index) => 100 + index * 10),
    summary: {
      frameCount: 3000,
      durationMs: 30000,
      percentiles: { p50: 10, p95: 10, p99: 10 },
      shareUnderBudget: 1,
    },
    camera: { completed: true },
    animation: { active: true },
    interruptions: {
      visibilityLost: false,
      resized: false,
      contextLost: false,
    },
  };
}
export function mutationCapture() {
  return {
    role: 'owner',
    host: 'windows-native',
    browser: 'chrome',
    tracePath: 'web/spikes/performance/evidence/synthetic.json',
    sha256: `sha256:${'cd'.repeat(32)}`,
  };
}
