import { useQuery } from '@tanstack/react-query'
import { useSearchParams, Link } from 'react-router-dom'
import { api } from '../api/client'
import { StatusBadge } from '../components/StatusBadge'
import { CompareChart } from '../components/charts/CompareChart'

function Metric({ label, value, unit }: { label: string; value: number | null | undefined; unit?: string }) {
  return (
    <div>
      <div className="font-mono text-base font-bold tabular-nums">
        {value != null ? value.toFixed(value < 10 ? 2 : 0) : '—'}
        {value != null && unit && <span className="ml-1 text-xs font-normal text-gray-400">{unit}</span>}
      </div>
      <div className="text-xs uppercase tracking-wider text-gray-400">{label}</div>
    </div>
  )
}

export function ComparePage() {
  const [params, setParams] = useSearchParams()
  const runIds = (params.get('run_ids') ?? '').split(',').filter(Boolean)

  const { data, isLoading } = useQuery({
    queryKey: ['compare', runIds.join(',')],
    queryFn: () => api.compareRuns(runIds),
    enabled: runIds.length > 0,
  })

  const { data: allRuns = [] } = useQuery({
    queryKey: ['runs'],
    queryFn: () => api.getRuns(),
  })

  function pinRun(id: string) {
    if (runIds.includes(id)) return
    setParams({ run_ids: [...runIds, id].join(',') })
  }
  function unpinRun(id: string) {
    setParams({ run_ids: runIds.filter(r => r !== id).join(',') })
  }

  const labels = data?.runs.map(r => r.run_id.slice(0, 8)) ?? []

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6 flex items-start gap-4">
        <div>
          <h1 className="font-serif text-2xl font-bold text-secondary">Compare Runs</h1>
          <p className="mt-1 text-sm text-gray-500">Side-by-side performance comparison. Pin additional runs using the selector below.</p>
        </div>
        <Link to="/" className="btn-outline ml-auto text-sm">← Back to Runs</Link>
      </div>

      {runIds.length === 0 && (
        <div className="card py-10 text-center text-sm text-gray-400">
          No runs selected. Go to <Link to="/" className="text-primary underline">Runs</Link> and select rows to compare.
        </div>
      )}

      {runIds.length > 0 && isLoading && <p className="text-sm text-gray-400">Loading…</p>}

      {data && (
        <>
          {/* per-run cards */}
          <div className="mb-6 grid gap-4" style={{ gridTemplateColumns: `repeat(${Math.min(data.runs.length, 3)}, 1fr)` }}>
            {data.runs.map(r => (
              <div key={r.run_id} className="card relative">
                <button
                  onClick={() => unpinRun(r.run_id)}
                  className="absolute right-3 top-3 text-xs text-gray-300 hover:text-red-500"
                  title="Unpin"
                >
                  ✕
                </button>
                <div className="mb-3 flex items-center gap-2">
                  <span className="font-mono text-sm font-semibold">{r.run_id.slice(0, 8)}</span>
                  <StatusBadge status={r.status} />
                </div>
                {r.result ? (
                  <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                    <Metric label="TTFT p99" value={r.result.ttft_p99} unit="ms" />
                    <Metric label="TPOT p99" value={r.result.tpot_p99} unit="ms" />
                    <Metric label="Output TPS" value={r.result.output_tps_mean} unit="tok/s" />
                    <Metric label="Goodput" value={r.result.goodput_rps} unit="rps" />
                    <Metric label="Energy" value={r.result.energy_joules} unit="J" />
                    <Metric label="Tok/joule" value={r.result.tokens_per_joule} />
                  </div>
                ) : (
                  <p className="text-xs text-gray-400">No results yet ({r.status})</p>
                )}
              </div>
            ))}
          </div>

          {/* charts */}
          <CompareChart data={data} labels={labels} />
        </>
      )}

      {/* run picker to add more */}
      {allRuns.length > 0 && (
        <div className="mt-8">
          <p className="label mb-2">Pin additional run</p>
          <div className="flex flex-wrap gap-2">
            {allRuns
              .filter(r => !runIds.includes(r.id))
              .map(r => (
                <button
                  key={r.id}
                  onClick={() => pinRun(r.id)}
                  className="rounded border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-600 hover:border-primary hover:text-primary"
                >
                  {r.id.slice(0, 8)} · {r.status}
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
