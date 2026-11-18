import { plot, line } from '@observablehq/plot';
import { workload } from '../workload';
export function render(host: HTMLElement, input: unknown) {
  const nodes = workload(input).map((panel) => {
    const node = plot({
      width: 640,
      height: 320,
      margin: 0,
      x: { axis: null, domain: [0, 24] },
      y: { axis: null, domain: [0, 100] },
      marks: [panel.lower, ...(panel.upper ? [panel.upper] : [])].map((data) =>
        line(data, { x: (d: number[]) => d[0], y: (d: number[]) => d[1] }),
      ),
    });
    host.append(node);
    return node;
  });
  return () => nodes.forEach((node) => node.remove());
}
