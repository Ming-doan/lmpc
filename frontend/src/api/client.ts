const API_BASE = import.meta.env.VITE_API_URL ?? ''

function getToken(): string | null {
  return localStorage.getItem('lmpc_token')
}

function buildHeaders(extra?: HeadersInit): HeadersInit {
  const token = getToken()
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(extra ?? {}),
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: buildHeaders(init?.headers),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  // catalog
  getPlatforms: () => request<Platform[]>('/api/v1/platforms'),
  getModels: () => request<Model[]>('/api/v1/models'),
  getPromptSets: () => request<PromptSet[]>('/api/v1/prompt-sets'),

  // runs
  getRuns: (params?: { status?: string; model?: string }) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString()
    return request<Run[]>(`/api/v1/runs${qs ? `?${qs}` : ''}`)
  },
  getRun: (id: string) => request<Run>(`/api/v1/runs/${id}`),
  getRunResult: (id: string) => request<RunResult>(`/api/v1/runs/${id}/result`),
  getRunTraces: (id: string, offset = 0, limit = 500) =>
    request<Trace[]>(`/api/v1/runs/${id}/traces?offset=${offset}&limit=${limit}`),
  getRunMetrics: (id: string, offset = 0, limit = 1000) =>
    request<MetricSample[]>(`/api/v1/runs/${id}/metrics?offset=${offset}&limit=${limit}`),
  createRuns: (body: { config_id: string; iterations: number; priority: number }) =>
    request<Run[]>('/api/v1/runs', { method: 'POST', body: JSON.stringify(body) }),
  cancelRun: (id: string) =>
    request<Run>(`/api/v1/runs/${id}/cancel`, { method: 'POST' }),
  compareRuns: (ids: string[]) =>
    request<CompareResult>(`/api/v1/compare?run_ids=${ids.join(',')}`),

  // configs
  getConfigs: () => request<Config[]>('/api/v1/configs'),
  createConfig: (body: CreateConfigBody) =>
    request<Config>('/api/v1/configs', { method: 'POST', body: JSON.stringify(body) }),

  // workers
  getWorkers: (status?: string) => {
    const qs = status ? `?status=${status}` : ''
    return request<Worker[]>(`/api/v1/workers${qs}`)
  },
  approveWorker: (id: string) =>
    request<Worker>(`/api/v1/workers/${id}/approve`, { method: 'POST' }),
  rejectWorker: (id: string) =>
    request<Worker>(`/api/v1/workers/${id}/reject`, { method: 'POST' }),
}

// ---- inline types (until openapi-typescript is run) ----

export interface Platform {
  id: number
  name: string
  display_name: string
  adapter_class: string
  default_image: string | null
  default_port: number | null
  description: string | null
}

export interface Model {
  id: number
  name: string
  hf_id: string | null
  size_b: number | null
  quantization: string | null
  context_length: number | null
}

export interface PromptSet {
  id: number
  name: string
  description: string | null
  prompts: Array<{ prompt: string; max_new_tokens?: number }>
  version: number
}

export interface Config {
  id: string
  name: string
  platform_id: number
  model_id: number
  prompt_set_id: number
  platform_args: Record<string, unknown>
  benchmark_args: Record<string, unknown>
  created_at: string
}

export interface CreateConfigBody {
  name: string
  platform_id: number
  model_id: number
  prompt_set_id: number
  platform_args: Record<string, unknown>
  benchmark_args: Record<string, unknown>
}

export interface RunConfig {
  id: string
  name: string
  platform_name: string | null
  model_name: string | null
}

export interface Run {
  id: string
  config_id: string
  iteration: number
  status: string
  priority: number
  queued_at: string
  started_at: string | null
  completed_at: string | null
  worker_id: string | null
  error_message: string | null
  config?: RunConfig
}

export interface RunResult {
  run_id: string
  ttft_p50: number | null
  ttft_p90: number | null
  ttft_p95: number | null
  ttft_p99: number | null
  ttft_mean: number | null
  tpot_p50: number | null
  tpot_p90: number | null
  tpot_p95: number | null
  tpot_p99: number | null
  tpot_mean: number | null
  e2e_p50: number | null
  e2e_p90: number | null
  e2e_p95: number | null
  e2e_p99: number | null
  e2e_mean: number | null
  output_tps_mean: number | null
  goodput_rps: number | null
  total_requests: number | null
  successful_requests: number | null
  failed_requests: number | null
  total_output_tokens: number | null
  peak_gpu_mem_mb: number | null
  avg_gpu_util_pct: number | null
  avg_power_watts: number | null
  energy_joules: number | null
  tokens_per_joule: number | null
  container_start_ms: number | null
  model_load_ms: number | null
}

export interface Trace {
  request_idx: number
  started_at: string
  ttft_ms: number | null
  tpot_ms: number | null
  e2e_ms: number | null
  input_tokens: number | null
  output_tokens: number | null
  success: boolean
  error: string | null
}

export interface MetricSample {
  time: string
  cpu_pct: number | null
  ram_used_mb: number | null
  gpu_util_pct: number | null
  gpu_mem_used_mb: number | null
  gpu_power_watts: number | null
}

export interface Worker {
  id: string
  name: string
  hostname: string
  status: string
  approved: boolean
  specs: Record<string, unknown>
  capabilities: Record<string, unknown>
  registered_at: string
  last_heartbeat_at: string | null
}

export interface CompareResult {
  runs: Array<{
    run_id: string
    status: string
    iteration: number
    result: {
      ttft_p99: number | null
      tpot_p99: number | null
      e2e_p99: number | null
      output_tps_mean: number | null
      goodput_rps: number | null
      energy_joules: number | null
      tokens_per_joule: number | null
    } | null
  }>
}
