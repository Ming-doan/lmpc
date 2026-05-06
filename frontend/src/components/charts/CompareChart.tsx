import ReactECharts from 'echarts-for-react'
import type { CompareResult } from '../../api/client'

interface Props {
  data: CompareResult
  labels: string[]
}

function bar(name: string, values: (number | null)[], color: string) {
  return {
    name,
    type: 'bar' as const,
    data: values.map(v => v ?? 0),
    itemStyle: { color },
    barMaxWidth: 40,
    label: { show: true, position: 'top' as const, fontSize: 10, formatter: (p: { value: number }) => p.value.toFixed(1) },
  }
}

export function CompareChart({ data, labels }: Props) {
  const runs = data.runs

  const ttftP99 = runs.map(r => r.result?.ttft_p99 ?? null)
  const tpotP99 = runs.map(r => r.result?.tpot_p99 ?? null)
  const outputTps = runs.map(r => r.result?.output_tps_mean ?? null)
  const energy = runs.map(r => r.result?.energy_joules ?? null)

  const grid = { top: 40, right: 16, bottom: 64, left: 56 }
  const xAxis = { type: 'category' as const, data: labels, axisLabel: { fontSize: 10, interval: 0, rotate: 20 } }
  const yAxisMs = { type: 'value' as const, name: 'ms', nameLocation: 'middle' as const, nameGap: 40, axisLabel: { fontSize: 10 } }
  const legend = { bottom: 0, textStyle: { fontSize: 10 } }
  const tooltip = { trigger: 'axis' as const }

  const latencyOption = {
    grid, tooltip, legend,
    xAxis,
    yAxis: yAxisMs,
    series: [
      bar('TTFT p99 (ms)', ttftP99, '#8100D1'),
      bar('TPOT p99 (ms)', tpotP99, '#15173D'),
    ],
  }

  const tpsOption = {
    grid, tooltip, legend: { ...legend, data: ['Output TPS'] },
    xAxis,
    yAxis: { ...yAxisMs, name: 'tok/s' },
    series: [bar('Output TPS', outputTps, '#8100D1')],
  }

  const energyOption = {
    grid, tooltip, legend: { ...legend, data: ['Energy (J)'] },
    xAxis,
    yAxis: { ...yAxisMs, name: 'joules' },
    series: [bar('Energy (J)', energy, '#f59e0b')],
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="card">
        <p className="label mb-2">Latency p99</p>
        <ReactECharts option={latencyOption} style={{ height: 220 }} />
      </div>
      <div className="card">
        <p className="label mb-2">Output Throughput</p>
        <ReactECharts option={tpsOption} style={{ height: 220 }} />
      </div>
      <div className="card">
        <p className="label mb-2">Energy</p>
        <ReactECharts option={energyOption} style={{ height: 220 }} />
      </div>
    </div>
  )
}
