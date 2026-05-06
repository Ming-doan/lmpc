import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, Outlet, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { StatusBadge } from '../components/StatusBadge'

const STATUSES = ['completed', 'running', 'claimed', 'queued', 'failed', 'cancelled']
const ACTIVE = new Set(['running', 'claimed', 'queued'])

function fmt(ms: number | null) {
  return ms != null ? `${ms.toFixed(0)} ms` : '—'
}

function duration(run: { started_at: string | null; completed_at: string | null }) {
  if (!run.started_at) return '—'
  const end = run.completed_at ? new Date(run.completed_at) : new Date()
  const sec = Math.floor((end.getTime() - new Date(run.started_at).getTime()) / 1000)
  return sec < 60 ? `${sec}s` : `${Math.floor(sec / 60)}m ${sec % 60}s`
}

export function RunsPage() {
  const { id: selectedId } = useParams()
  const navigate = useNavigate()
  const [filter, setFilter] = useState<string>('all')
  const [selected, setSelected] = useState<Set<string>>(new Set())

  const { data: runs = [], isLoading } = useQuery({
    queryKey: ['runs', filter],
    queryFn: () => api.getRuns(filter !== 'all' ? { status: filter } : {}),
    refetchInterval: (query) => {
      const data = query.state.data as typeof runs | undefined
      return data?.some(r => ACTIVE.has(r.status)) ? 3000 : 10000
    },
  })

  function toggleSelect(id: string, e: React.MouseEvent) {
    e.stopPropagation()
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const canCompare = selected.size >= 2

  return (
    <div className="flex h-[calc(100vh-52px)] overflow-hidden">
      {/* left: runs list */}
      <div className={`flex flex-col overflow-hidden ${selectedId ? 'w-1/2 border-r border-gray-200' : 'w-full'}`}>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <h1 className="font-serif text-2xl font-bold text-secondary">Benchmark Runs</h1>
          <p className="mb-4 mt-1 text-sm text-gray-500">Click a row to inspect. Select two or more to compare.</p>

          {/* filter chips */}
          <div className="mb-3 flex flex-wrap gap-2">
            {['all', ...STATUSES].map(s => (
              <button
                key={s}
                onClick={() => setFilter(s)}
                className={`rounded border px-3 py-1 text-xs font-semibold transition-colors ${
                  filter === s
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-gray-300 bg-white text-gray-600 hover:border-gray-400'
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          {canCompare && (
            <div className="mb-3 flex justify-end">
              <Link
                to={`/compare?run_ids=${[...selected].join(',')}`}
                className="btn-primary text-sm"
              >
                ⇄ Compare {selected.size} selected
              </Link>
            </div>
          )}

          {isLoading ? (
            <p className="text-sm text-gray-400">Loading…</p>
          ) : (
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="w-8 py-2" />
                  <th className="py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Platform</th>
                  <th className="py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Model</th>
                  <th className="py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Status</th>
                  <th className="py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Duration</th>
                  <th className="py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Iter</th>
                  <th className="py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Queued</th>
                </tr>
              </thead>
              <tbody>
                {runs.map(run => (
                  <tr
                    key={run.id}
                    onClick={() => navigate(selectedId === run.id ? '/' : `/runs/${run.id}`)}
                    className={`cursor-pointer border-b border-gray-100 transition-colors hover:bg-primary/5 ${
                      selectedId === run.id ? 'bg-primary/5' : ''
                    }`}
                  >
                    <td className="py-2.5 pl-1" onClick={e => toggleSelect(run.id, e)}>
                      <span className={`inline-flex h-4 w-4 items-center justify-center rounded border transition-colors ${
                        selected.has(run.id) ? 'border-primary bg-primary text-white' : 'border-gray-300'
                      }`}>
                        {selected.has(run.id) && <span className="text-xs">✓</span>}
                      </span>
                    </td>
                    <td className="py-2.5 font-medium">{run.config?.name ?? run.config_id.slice(0, 8)}</td>
                    <td className="py-2.5 text-xs text-gray-500">{run.config?.model_id ?? '—'}</td>
                    <td className="py-2.5"><StatusBadge status={run.status} /></td>
                    <td className="py-2.5 text-xs text-gray-500">{duration(run)}</td>
                    <td className="py-2.5 text-xs text-gray-500">#{run.iteration}</td>
                    <td className="py-2.5 text-xs text-gray-500">
                      {new Date(run.queued_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
                {runs.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-sm text-gray-400">
                      No runs yet. <Link to="/new" className="text-primary underline">Create one →</Link>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* right: detail panel (outlet) */}
      {selectedId && (
        <div className="w-1/2 overflow-y-auto bg-white/95 backdrop-blur-md">
          <Outlet />
        </div>
      )}
    </div>
  )
}
