import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { StatusBadge } from '../components/StatusBadge'
import { AuthModal } from '../components/AuthModal'
import { useAuth } from '../hooks/useAuth'

function ago(iso: string | null) {
  if (!iso) return '—'
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

export function WorkersPage() {
  const { token, isAuthenticated, setToken } = useAuth()
  const qc = useQueryClient()
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const { data: workers = [], isLoading } = useQuery({
    queryKey: ['workers'],
    queryFn: () => api.getWorkers(),
    refetchInterval: 10000,
    enabled: isAuthenticated,
  })

  const approve = useMutation({
    mutationFn: (id: string) => api.approveWorker(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workers'] }),
  })
  const reject = useMutation({
    mutationFn: (id: string) => api.rejectWorker(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workers'] }),
  })

  if (!isAuthenticated) return <AuthModal onAuth={setToken} />

  function toggleExpand(id: string) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <h1 className="font-serif text-2xl font-bold text-secondary">Workers</h1>
      <p className="mb-6 mt-1 text-sm text-gray-500">Registered benchmark workers. Approve to allow job polling.</p>

      {isLoading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : workers.length === 0 ? (
        <div className="card text-center text-sm text-gray-400 py-10">
          No workers registered yet. Run the worker on a GPU machine to register.
        </div>
      ) : (
        <div className="space-y-3">
          {workers.map(w => (
            <div key={w.id} className="card">
              <div className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-secondary">{w.name}</span>
                    <StatusBadge status={w.status} />
                    {!w.approved && (
                      <span className="badge badge-pending">awaiting approval</span>
                    )}
                  </div>
                  <div className="mt-0.5 text-xs text-gray-500">
                    {w.hostname} · heartbeat {ago(w.last_heartbeat_at)} · registered {new Date(w.registered_at).toLocaleDateString()}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {((w.capabilities as { platforms?: string[] }).platforms ?? []).map(p => (
                      <span key={p} className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">{p}</span>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {w.status === 'pending' && (
                    <>
                      <button
                        onClick={() => approve.mutate(w.id)}
                        disabled={approve.isPending}
                        className="btn text-sm py-1 px-3"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => reject.mutate(w.id)}
                        disabled={reject.isPending}
                        className="btn-outline text-sm py-1 px-3 border-red-300 text-red-600 hover:bg-red-600"
                      >
                        Reject
                      </button>
                    </>
                  )}
                  <button
                    onClick={() => toggleExpand(w.id)}
                    className="text-xs text-gray-400 hover:text-gray-600"
                  >
                    {expanded.has(w.id) ? '▲ hide' : '▼ specs'}
                  </button>
                </div>
              </div>

              {expanded.has(w.id) && (
                <pre className="mt-3 overflow-x-auto rounded border border-gray-100 bg-gray-50 p-3 text-xs text-gray-600">
                  {JSON.stringify(w.specs, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
