import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { StatusBadge } from '../components/StatusBadge'
import { LatencyChart } from '../components/charts/LatencyChart'
import { ResourceChart } from '../components/charts/ResourceChart'

type Tab = 'summary' | 'latency' | 'resources' | 'logs'

function Metric({ label, value, unit }: { label: string; value: number | null | undefined; unit?: string }) {
  return (
    <div className="rounded border border-gray-100 bg-gray-50 p-3">
      <div className="font-mono text-lg font-bold text-secondary tabular-nums">
        {value != null ? value.toFixed(value < 10 ? 2 : 0) : '—'}
        {value != null && unit && <span className="ml-1 text-xs font-normal text-gray-500">{unit}</span>}
      </div>
      <div className="mt-0.5 text-xs uppercase tracking-wider text-gray-400">{label}</div>
    </div>
  )
}

export function RunDetailPanel() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('summary')

  const { data: run } = useQuery({
    queryKey: ['run', id],
    queryFn: () => api.getRun(id!),
    refetchInterval: r => (r.state.data?.status && ['running', 'claimed', 'queued'].includes(r.state.data.status) ? 3000 : false),
    enabled: !!id,
  })

  const { data: result } = useQuery({
    queryKey: ['run-result', id],
    queryFn: () => api.getRunResult(id!),
    enabled: !!id && run?.status === 'completed',
  })

  const { data: traces = [] } = useQuery({
    queryKey: ['run-traces', id],
    queryFn: () => api.getRunTraces(id!),
    enabled: tab === 'latency' && !!id && run?.status === 'completed',
  })

  const { data: metrics = [] } = useQuery({
    queryKey: ['run-metrics', id],
    queryFn: () => api.getRunMetrics(id!),
    enabled: tab === 'resources' && !!id && run?.status === 'completed',
  })

  if (!run) return <div className="p-6 text-sm text-gray-400">Loading…</div>

  const tabs: { key: Tab; label: string }[] = [
    { key: 'summary', label: 'Summary' },
    { key: 'latency', label: 'Latency' },
    { key: 'resources', label: 'Resources' },
    { key: 'logs', label: 'Logs' },
  ]

  return (
    <div className="flex h-full flex-col">
      {/* header */}
      <div className="flex items-start gap-3 border-b border-gray-200 px-5 py-4">
        <div className="flex-1 min-w-0">
          <h2 className="font-serif text-base font-semibold text-secondary truncate">
            Run #{run.id.slice(0, 8)} · Iteration {run.iteration}
          </h2>
          <p className="mt-0.5 text-xs text-gray-500">
            {run.started_at ? new Date(run.started_at).toLocaleString() : 'Not started'}
          </p>
        </div>
        <StatusBadge status={run.status} />
        <button
          onClick={() => navigate('/')}
          className="text-gray-400 hover:text-gray-700 text-xl leading-none"
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      {/* tabs */}
      <div className="flex border-b border-gray-200">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t.key
                ? 'border-primary text-primary'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* body */}
      <div className="flex-1 overflow-y-auto p-5">
        {tab === 'summary' && (
          <div className="space-y-5">
            <div>
              <p className="label text-primary mb-2">Latency</p>
              <div className="grid grid-cols-3 gap-2">
                <Metric label="TTFT p99" value={result?.ttft_p99} unit="ms" />
                <Metric label="TPOT p99" value={result?.tpot_p99} unit="ms" />
                <Metric label="E2E p99" value={result?.e2e_p99} unit="ms" />
                <Metric label="TTFT mean" value={result?.ttft_mean} unit="ms" />
                <Metric label="TPOT mean" value={result?.tpot_mean} unit="ms" />
                <Metric label="E2E mean" value={result?.e2e_mean} unit="ms" />
              </div>
            </div>
            <div>
              <p className="label text-primary mb-2">Throughput</p>
              <div className="grid grid-cols-3 gap-2">
                <Metric label="Output TPS" value={result?.output_tps_mean} unit="tok/s" />
                <Metric label="Goodput" value={result?.goodput_rps} unit="rps" />
                <Metric label="Success rate" value={
                  result && result.total_requests
                    ? (((result.successful_requests ?? 0) / result.total_requests) * 100)
                    : null
                } unit="%" />
              </div>
            </div>
            <div>
              <p className="label text-primary mb-2">Resources</p>
              <div className="grid grid-cols-3 gap-2">
                <Metric label="Peak GPU mem" value={result?.peak_gpu_mem_mb} unit="MB" />
                <Metric label="Avg GPU util" value={result?.avg_gpu_util_pct} unit="%" />
                <Metric label="Avg power" value={result?.avg_power_watts} unit="W" />
                <Metric label="Energy" value={result?.energy_joules} unit="J" />
                <Metric label="Tok / joule" value={result?.tokens_per_joule} />
              </div>
            </div>
            <div>
              <p className="label text-primary mb-2">Reproducibility</p>
              <div className="rounded border border-gray-100 bg-gray-50 p-3 text-xs leading-relaxed text-gray-600 space-y-1">
                <div><span className="font-semibold">Status:</span> {run.status}</div>
                <div><span className="font-semibold">Config:</span> {run.config_id}</div>
                {run.error_message && (
                  <div className="text-red-600"><span className="font-semibold">Error:</span> {run.error_message}</div>
                )}
                <div><span className="font-semibold">Container start:</span> {result?.container_start_ms != null ? `${result.container_start_ms} ms` : '—'}</div>
                <div><span className="font-semibold">Model load:</span> {result?.model_load_ms != null ? `${result.model_load_ms} ms` : '—'}</div>
              </div>
            </div>
          </div>
        )}

        {tab === 'latency' && (
          <div>
            <p className="label text-primary mb-3">Per-request scatter</p>
            {traces.length > 0
              ? <LatencyChart traces={traces} />
              : <p className="text-sm text-gray-400">No trace data yet.</p>}
          </div>
        )}

        {tab === 'resources' && (
          <div>
            <p className="label text-primary mb-3">System metrics (1 Hz)</p>
            {metrics.length > 0
              ? <ResourceChart samples={metrics} />
              : <p className="text-sm text-gray-400">No metric samples yet.</p>}
          </div>
        )}

        {tab === 'logs' && (
          <div className="rounded border border-gray-200 bg-gray-50 p-4 text-xs text-gray-500">
            <p className="font-semibold text-gray-700 mb-1">Container logs</p>
            <p>Logs are written to the worker host at:</p>
            <code className="mt-1 block font-mono text-gray-600">/var/log/lmpc/{id}.log</code>
            <p className="mt-2 text-gray-400">Remote log fetching is not yet available in this phase.</p>
          </div>
        )}
      </div>
    </div>
  )
}
