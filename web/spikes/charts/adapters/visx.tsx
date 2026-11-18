import { createRoot } from 'react-dom/client';
import { LinePath } from '@visx/shape';
import { Group } from '@visx/group';
import { scaleLinear } from '@visx/scale';
import { workload } from '../workload';
export function render(host: HTMLElement, input: unknown) {
  const panels = workload(input);
  const root = createRoot(host);
  const x = scaleLinear({ domain: [0, 24], range: [0, 640] });
  const y = scaleLinear({ domain: [0, 100], range: [320, 0] });
  root.render(
    <>
      {panels.map((panel, index) => (
        <svg key={index} width="640" height="320" aria-hidden="true">
          <Group>
            {[panel.lower, ...(panel.upper ? [panel.upper] : [])].map(
              (data, series) => (
                <LinePath
                  key={series}
                  data={data}
                  x={(d) => x(d[0] ?? 0)}
                  y={(d) => y(d[1] ?? 0)}
                  stroke="currentColor"
                />
              ),
            )}
          </Group>
        </svg>
      ))}
    </>,
  );
  return () => root.unmount();
}
