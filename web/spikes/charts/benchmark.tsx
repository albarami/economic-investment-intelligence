import { createRoot } from 'react-dom/client';
export function mountBenchmark(
  host: HTMLElement,
  render: (target: HTMLElement, input: unknown) => () => void,
  input: unknown,
) {
  const shell = document.createElement('div');
  const chart = document.createElement('div');
  host.append(shell, chart);
  const root = createRoot(shell);
  root.render(<section aria-label="Chart spike" />);
  const dispose = render(chart, input);
  return () => {
    dispose();
    root.unmount();
    shell.remove();
    chart.remove();
  };
}
