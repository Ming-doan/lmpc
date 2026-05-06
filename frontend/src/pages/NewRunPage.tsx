import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, type CreateConfigBody } from '../api/client'
import { AuthModal } from '../components/AuthModal'
import { useAuth } from '../hooks/useAuth'

type Step = 1 | 2 | 3

const DEFAULT_BENCH = { concurrency: 4, num_requests: 100, max_tokens: 512, warmup_requests: 3 }

export function NewRunPage() {
  const { isAuthenticated, setToken } = useAuth()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [step, setStep] = useState<Step>(1)
  const [platformId, setPlatformId] = useState<number | null>(null)
  const [modelId, setModelId] = useState<number | null>(null)
  const [promptSetId, setPromptSetId] = useState<number | null>(null)
  const [configName, setConfigName] = useState('')
  const [benchArgs, setBenchArgs] = useState(DEFAULT_BENCH)
  const [platformArgsJson, setPlatformArgsJson] = useState('{}')
  const [iterations, setIterations] = useState(3)
  const [jsonError, setJsonError] = useState('')

  const { data: platforms = [] } = useQuery({ queryKey: ['platforms'], queryFn: api.getPlatforms, enabled: isAuthenticated })
  const { data: models = [] } = useQuery({ queryKey: ['models'], queryFn: api.getModels, enabled: isAuthenticated })
  const { data: promptSets = [] } = useQuery({ queryKey: ['prompt-sets'], queryFn: api.getPromptSets, enabled: isAuthenticated })

  const selectedPlatform = platforms.find(p => p.id === platformId)
  const selectedModel = models.find(m => m.id === modelId)
  const selectedPS = promptSets.find(p => p.id === promptSetId)

  const createConfig = useMutation({
    mutationFn: (body: CreateConfigBody) => api.createConfig(body),
  })
  const createRuns = useMutation({
    mutationFn: ({ configId }: { configId: string }) =>
      api.createRuns({ config_id: configId, iterations, priority: 0 }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['runs'] })
      navigate('/')
    },
  })

  if (!isAuthenticated) return <AuthModal onAuth={setToken} />

  async function submit() {
    let platformArgs: Record<string, unknown> = {}
    try {
      platformArgs = JSON.parse(platformArgsJson)
    } catch {
      setJsonError('Invalid JSON in platform args')
      return
    }

    const cfg = await createConfig.mutateAsync({
      name: configName || `${selectedPlatform?.name ?? 'run'}-${Date.now()}`,
      platform_id: platformId!,
      model_id: modelId!,
      prompt_set_id: promptSetId!,
      platform_args: platformArgs,
      benchmark_args: benchArgs,
    })
    await createRuns.mutateAsync({ configId: cfg.id })
  }

  const canStep2 = platformId !== null && modelId !== null && promptSetId !== null
  const canStep3 = canStep2
  const canSubmit = canStep3 && !jsonError

  const cmdPreview = `lmpc run --platform ${selectedPlatform?.name ?? '?'} --model ${selectedModel?.name ?? '?'} --concurrency ${benchArgs.concurrency} --iterations ${iterations} --max-tokens ${benchArgs.max_tokens}`

  const steps = [
    { n: 1, label: 'Platform & Model' },
    { n: 2, label: 'Load Params' },
    { n: 3, label: 'Review' },
  ]

  return (
    <div className="mx-auto max-w-2xl px-6 py-8">
      <h1 className="font-serif text-2xl font-bold text-secondary">New Benchmark Run</h1>
      <p className="mb-6 mt-1 text-sm text-gray-500">Configure and submit a new benchmark job.</p>

      {/* step indicator */}
      <div className="mb-8 flex items-center gap-0">
        {steps.map((s, i) => (
          <div key={s.n} className="flex items-center">
            <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-colors ${
              step === s.n ? 'bg-secondary text-white' : step > s.n ? 'bg-primary text-white' : 'bg-gray-200 text-gray-500'
            }`}>
              {step > s.n ? '✓' : s.n}
            </div>
            <span className={`ml-2 text-xs font-medium ${step === s.n ? 'text-secondary' : 'text-gray-400'}`}>{s.label}</span>
            {i < steps.length - 1 && <div className="mx-4 h-px w-12 bg-gray-300" />}
          </div>
        ))}
      </div>

      <div className="card space-y-5">
        {step === 1 && (
          <>
            <div>
              <label className="label">Platform</label>
              <div className="flex flex-wrap gap-2">
                {platforms.map(p => (
                  <button
                    key={p.id}
                    onClick={() => setPlatformId(p.id)}
                    className={`rounded border px-3 py-1.5 text-sm font-semibold transition-colors ${
                      platformId === p.id
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-gray-300 text-gray-600 hover:border-gray-400'
                    }`}
                  >
                    {p.display_name || p.name}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="label">Model</label>
              <select className="input" value={modelId ?? ''} onChange={e => setModelId(Number(e.target.value) || null)}>
                <option value="">Select model…</option>
                {models.map(m => (
                  <option key={m.id} value={m.id}>{m.name} {m.size_b ? `(${m.size_b}B)` : ''}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Prompt Set</label>
              <select className="input" value={promptSetId ?? ''} onChange={e => setPromptSetId(Number(e.target.value) || null)}>
                <option value="">Select prompt set…</option>
                {promptSets.map(ps => (
                  <option key={ps.id} value={ps.id}>{ps.name} ({ps.prompts.length} prompts)</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Config Name (optional)</label>
              <input className="input" placeholder="Auto-generated if empty" value={configName} onChange={e => setConfigName(e.target.value)} />
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Concurrency</label>
                <input className="input" type="number" min={1} value={benchArgs.concurrency}
                  onChange={e => setBenchArgs(p => ({ ...p, concurrency: Number(e.target.value) }))} />
              </div>
              <div>
                <label className="label">Iterations</label>
                <input className="input" type="number" min={1} value={iterations}
                  onChange={e => setIterations(Number(e.target.value))} />
              </div>
              <div>
                <label className="label">Requests per iteration</label>
                <input className="input" type="number" min={1} value={benchArgs.num_requests}
                  onChange={e => setBenchArgs(p => ({ ...p, num_requests: Number(e.target.value) }))} />
              </div>
              <div>
                <label className="label">Max tokens</label>
                <input className="input" type="number" min={1} value={benchArgs.max_tokens}
                  onChange={e => setBenchArgs(p => ({ ...p, max_tokens: Number(e.target.value) }))} />
              </div>
              <div>
                <label className="label">Warmup requests</label>
                <input className="input" type="number" min={0} value={benchArgs.warmup_requests}
                  onChange={e => setBenchArgs(p => ({ ...p, warmup_requests: Number(e.target.value) }))} />
              </div>
            </div>
            <div>
              <label className="label">Platform args (JSON)</label>
              <textarea
                className={`input font-mono text-xs ${jsonError ? 'border-red-400' : ''}`}
                rows={4}
                value={platformArgsJson}
                onChange={e => { setPlatformArgsJson(e.target.value); setJsonError('') }}
              />
              {jsonError && <p className="mt-1 text-xs text-red-600">{jsonError}</p>}
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <div>
              <p className="label text-primary mb-2">Summary</p>
              <div className="space-y-1 text-sm text-gray-700">
                <div><span className="font-semibold">Platform:</span> {selectedPlatform?.display_name ?? '—'}</div>
                <div><span className="font-semibold">Model:</span> {selectedModel?.name ?? '—'}</div>
                <div><span className="font-semibold">Prompt set:</span> {selectedPS?.name ?? '—'} ({selectedPS?.prompts.length} prompts)</div>
                <div><span className="font-semibold">Concurrency:</span> {benchArgs.concurrency}</div>
                <div><span className="font-semibold">Requests / iter:</span> {benchArgs.num_requests}</div>
                <div><span className="font-semibold">Max tokens:</span> {benchArgs.max_tokens}</div>
                <div><span className="font-semibold">Iterations:</span> {iterations} <span className="text-gray-400">(→ {iterations} runs created)</span></div>
              </div>
            </div>
            <div>
              <p className="label mb-1">Command preview</p>
              <code className="block rounded border border-gray-200 bg-gray-50 p-3 text-xs text-gray-700 break-all">
                {cmdPreview}
              </code>
            </div>
          </>
        )}
      </div>

      {/* nav buttons */}
      <div className="mt-5 flex justify-between">
        <button
          onClick={() => step > 1 ? setStep((step - 1) as Step) : navigate('/')}
          className="btn-outline"
        >
          {step === 1 ? 'Cancel' : '← Back'}
        </button>
        {step < 3 ? (
          <button
            onClick={() => setStep((step + 1) as Step)}
            disabled={step === 1 ? !canStep2 : !canStep3}
            className="btn"
          >
            Next →
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={!canSubmit || createConfig.isPending || createRuns.isPending}
            className="btn"
          >
            {createConfig.isPending || createRuns.isPending ? 'Submitting…' : `Submit ${iterations} run${iterations !== 1 ? 's' : ''} →`}
          </button>
        )}
      </div>
    </div>
  )
}
