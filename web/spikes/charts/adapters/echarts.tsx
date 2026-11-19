import { init, use as registerCharts } from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { workload } from '../workload';
registerCharts([LineChart, GridComponent, CanvasRenderer]);
export function render(host: HTMLElement, input: unknown) {
  const panels = workload(input);
  const charts = panels.map((panel) => {
    const element = document.createElement('div');
    element.style.width = '640px';
    element.style.height = '320px';
    host.append(element);
    const chart = init(element);
    chart.setOption({
      animation: false,
      tooltip: { show: false },
      grid: { left: 0, right: 0, top: 0, bottom: 0 },
      xAxis: { show: false, min: 0, max: 24 },
      yAxis: { show: false, min: 0, max: 100 },
      series: [panel.lower, ...(panel.upper ? [panel.upper] : [])].map(
        (data) => ({
          type: 'line',
          data,
          showSymbol: false,
          label: { show: false },
        }),
      ),
    });
    return { chart, element };
  });
  return () =>
    charts.forEach(({ chart, element }) => {
      chart.dispose();
      element.remove();
    });
}
