import ReactECharts from 'echarts-for-react'
import type { MetricSample } from '../../api/client'

interface Props {
  samples: MetricSample[]
}

export function ResourceChart({ samples }: Props) {
  const times = samples.map((_, i) => i)

  const option = {
    grid: { top: 32, right: 16, bottom: 48, left: 56 },
    tooltip: { trigger: 'axis' },
    legend: { data: ['GPU Util %', 'GPU Mem MB', 'CPU %', 'Power W'], bottom: 0, textStyle: { fontSize: 10 } },
    xAxis: { type: 'category', data: times, name: 'seconds', nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 10 } },
    yAxis: [
      { type: 'value', name: '% / W', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 } },
      { type: 'value', name: 'MB', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 } },
    ],
    series: [
      {
        name: 'GPU Util %',
        type: 'line',
        smooth: true,
        data: samples.map(s => s.gpu_util_pct ?? 0),
        itemStyle: { color: '#8100D1' },
        lineStyle: { width: 1.5 },
        showSymbol: false,
      },
      {
        name: 'CPU %',
        type: 'line',
        smooth: true,
        data: samples.map(s => s.cpu_pct ?? 0),
        itemStyle: { color: '#15173D' },
        lineStyle: { width: 1.5 },
        showSymbol: false,
      },
      {
        name: 'Power W',
        type: 'line',
        smooth: true,
        data: samples.map(s => s.gpu_power_watts ?? 0),
        itemStyle: { color: '#f59e0b' },
        lineStyle: { width: 1.5 },
        showSymbol: false,
      },
      {
        name: 'GPU Mem MB',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: samples.map(s => s.gpu_mem_used_mb ?? 0),
        itemStyle: { color: '#64748b' },
        lineStyle: { width: 1.5, type: 'dashed' },
        showSymbol: false,
      },
    ],
  }

  return <ReactECharts option={option} style={{ height: 220 }} />
}
