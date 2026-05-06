import ReactECharts from 'echarts-for-react'
import type { Trace } from '../../api/client'

interface Props {
  traces: Trace[]
}

export function LatencyChart({ traces }: Props) {
  const success = traces.filter(t => t.success)

  const option = {
    grid: { top: 32, right: 16, bottom: 48, left: 56 },
    tooltip: { trigger: 'item', formatter: (p: { value: [number, number]; seriesName: string }) => `${p.seriesName}: ${p.value[1]?.toFixed(1)}ms` },
    legend: { data: ['TTFT', 'TPOT', 'E2E'], bottom: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'value', name: 'Request #', nameLocation: 'middle', nameGap: 30, axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', name: 'ms', nameLocation: 'middle', nameGap: 40, axisLabel: { fontSize: 10 } },
    series: [
      {
        name: 'TTFT',
        type: 'scatter',
        symbolSize: 4,
        data: success.map(t => [t.request_idx, t.ttft_ms]),
        itemStyle: { color: '#8100D1', opacity: 0.7 },
      },
      {
        name: 'TPOT',
        type: 'scatter',
        symbolSize: 4,
        data: success.map(t => [t.request_idx, t.tpot_ms]),
        itemStyle: { color: '#15173D', opacity: 0.7 },
      },
      {
        name: 'E2E',
        type: 'scatter',
        symbolSize: 4,
        data: success.map(t => [t.request_idx, t.e2e_ms]),
        itemStyle: { color: '#64748b', opacity: 0.5 },
      },
    ],
  }

  return <ReactECharts option={option} style={{ height: 220 }} />
}
