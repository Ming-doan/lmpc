# lmpc — Phases 4–7 Design

**Date:** 2026-05-06
**Scope:** Phase 4 (Platform Adapters), Phase 5 (Benchmark Execution), Phase 6 (Frontend), Phase 7 (Docker Compose)
**Decisions:** Adapter C (shared OpenAI base), Run Detail C (nested route `/runs/:id`), New Run B (3-step wizard), Implementation A (strict sequential)

---

## 1. Phase 4 — Platform Adapters

### 1.1 Class hierarchy

```
PlatformAdapter (ABC, base.py)
└── OpenAICompatibleAdapter (openai_compat.py)
    ├── OllamaAdapter    (ollama.py)
    ├── VLLMAdapter      (vllm.py)
    ├── SGLangAdapter    (sglang.py)
    ├── TGIAdapter       (tgi.py)
    ├── LMStudioAdapter  (lmstudio.py)
    └── TritonAdapter    (triton.py)
MockAdapter (mock.py — replaces stub.py, registry key "mock")
```

### 1.2 `OpenAICompatibleAdapter` (`adapters/openai_compat.py`)

Concrete intermediate class. Implements `send_request` once for all subclasses:

- Opens a streaming httpx request to `{base_url}/v1/chat/completions` with `stream=True`
- Records `t_send = time.perf_counter()` before the request
- On first SSE chunk: `ttft_ms = (time.perf_counter() - t_send) * 1000`
- Accumulates chunks, records `t_last` on each
- `tpot_ms = (t_last - t_first_chunk) / max(output_tokens - 1, 1) * 1000`
- `e2e_ms = (t_last - t_send) * 1000`
- Token counts sourced from response `usage` field when present; falls back to `len(response_text.split())` approximation only when platform omits `usage`
- Returns `RequestResult(ttft_ms, tpot_ms, e2e_ms, input_tokens, output_tokens, success, http_status, error)`

Subclasses must not override `send_request`. They override only:
- `build_container_spec(model, args) -> ContainerSpec`
- `wait_until_ready(base_url, timeout_s) -> ReadinessInfo`

`ContainerSpec` gains a `gpu: bool` field used by `DockerRunner` to pass `--gpus all`.

### 1.3 Per-adapter specs

| Adapter | Image | Port | Readiness endpoint | Notes |
|---------|-------|------|--------------------|-------|
| `OllamaAdapter` | `ollama/ollama:latest` | 11434 | `GET /api/tags` | Model pull via `POST /api/pull` counted in `model_load_ms`, not `container_start_ms` |
| `VLLMAdapter` | `vllm/vllm-openai:latest` | 8000 | `GET /health` | Args: `--model`, `--gpu-memory-utilization`, `--max-model-len` |
| `SGLangAdapter` | `lmsysorg/sglang:latest` | 30000 | `GET /health` | Standard OpenAI-compatible path |
| `TGIAdapter` | `ghcr.io/huggingface/text-generation-inference:latest` | 80 | `GET /health` | Prefers `/v1/chat/completions` |
| `LMStudioAdapter` | host-based | from `platform_args.base_url` | `GET /v1/models` | `build_container_spec` raises `NotImplementedError` with setup instructions |
| `TritonAdapter` | `nvcr.io/nvidia/tritonserver:<tag>-trtllm-python-py3` | 8000 | `GET /v2/health/ready` | Requires `platform_args.model_repo_path`; tag from `platform_args.tag` |

### 1.4 Adapter registry (`adapters/__init__.py`)

```python
ADAPTERS: dict[str, PlatformAdapter] = {
    "mock":     MockAdapter(),
    "ollama":   OllamaAdapter(),
    "vllm":     VLLMAdapter(),
    "sglang":   SGLangAdapter(),
    "tgi":      TGIAdapter(),
    "lmstudio": LMStudioAdapter(),
    "triton":   TritonAdapter(),
}
```

### 1.5 MockAdapter (`adapters/mock.py`)

Renamed from `stub.py`. Registry key updated `"stub"` → `"mock"`. Behaviour unchanged: 50 ms container start, 100 ms per request, plausible random latencies.

---

## 2. Phase 5 — Benchmark Execution

### 2.1 `docker_runner.py` — `DockerRunner`

Owns container lifecycle for one run. All blocking Docker SDK calls are wrapped in `asyncio.to_thread`.

**Methods:**

| Method | Description |
|--------|-------------|
| `async pull_image(image) -> str` | Pulls image, returns digest from `docker inspect` |
| `async start_container(spec, run_id) -> str` | Creates `lmpc-bench-{run_id}` network; starts container with model-cache volume + `--gpus all` if `spec.gpu`; returns `container_id` |
| `async get_platform_version(container_id) -> str` | Execs version command inside container |
| `async stream_logs(container_id, run_id)` | Streams container stdout/stderr to `/var/log/lmpc/{run_id}.log` as background task |
| `async stop_and_remove(container_id, run_id)` | Stops container, removes it, removes network if empty |

### 2.2 `metric_collector.py` — `MetricCollector`

Background asyncio task. Sampling rate: 1 Hz.

**Sources:**
- `psutil.cpu_percent()`, `psutil.virtual_memory()` — CPU + RAM
- `pynvml`: GPU util, mem used/total, temp, power — skipped gracefully if unavailable or no GPU
- Docker SDK container stats stream — I/O numbers (disk, net)

**Interface:**
```python
collector = MetricCollector(container_id, run_id, worker_id)
await collector.start()          # launches background task
# ... benchmark runs ...
samples = await collector.stop() # cancels task, returns list[dict]
```

Samples pushed to `asyncio.Queue`; `stop()` drains the queue and returns all samples.

### 2.3 `load_generator.py` — `run_load()`

Pure async function, no class:

```python
async def run_load(
    adapter: PlatformAdapter,
    base_url: str,
    prompts: list[str],
    num_requests: int,
    concurrency: int,
    max_tokens: int,
) -> list[RequestResult]
```

- Creates `concurrency` asyncio tasks via `asyncio.gather`
- Each task is semaphore-gated (semaphore size = `concurrency`)
- Prompts drawn round-robin across requests
- Returns flat list of `RequestResult` in completion order

### 2.4 `poller.py` — `execute_job()` rewrite

Orchestration pipeline:

```
1.  runner.pull_image(image)                    → image_digest
2.  POST /jobs/{run_id}/status  status=running
3.  t0 = now()
4.  runner.start_container(spec, run_id)        → container_id
    container_start_ms = now() - t0
5.  adapter.wait_until_ready(base_url, timeout) → model_load_ms, platform_version
6.  asyncio.create_task(runner.stream_logs(...))
7.  run_load(..., n=warmup_requests)            → discard
8.  collector.start()
9.  results = run_load(..., n=num_requests)     → list[RequestResult]
10. samples = collector.stop()                  → list[MetricSample]
11. runner.stop_and_remove(container_id, run_id)
12. aggregate(results, samples)                 → payload
13. POST /jobs/{run_id}/results  payload
```

**Aggregation (numpy):**
- Percentiles: p50, p90, p95, p99 for ttft, tpot, e2e
- `goodput_rps`: requests where `ttft_ms < 500 AND tpot_ms < 100` divided by total wall time
- `energy_joules`: trapezoidal integration of `gpu_power_watts` samples over time (`numpy.trapz`)
- `tokens_per_joule`: total output tokens / energy_joules

**`pyproject.toml` additions:** `numpy`, `docker` promoted from optional to required.

---

## 3. Phase 6 — Frontend

### 3.1 Stack

| Tool | Version | Purpose |
|------|---------|---------|
| React | 18 | UI framework |
| Vite | 5 | Build tool + dev server |
| TypeScript | 5 | Type safety |
| pnpm | 9 | Package manager |
| React Router | v6 | Client-side routing |
| TanStack Query | v5 | Server state, caching |
| Tailwind CSS | 3 | Utility styling |
| shadcn/ui | latest | Component primitives |
| echarts-for-react | latest | Charts |
| openapi-typescript | latest | Type generation from OpenAPI schema |

Fresh `frontend/` directory — no Next.js.

### 3.2 Design tokens

| Token | Value |
|-------|-------|
| Font heading | Noto Serif (Google Fonts) |
| Font body | Inter (Google Fonts) |
| Primary | `#8100D1` |
| Secondary | `#15173D` |
| Surface | off-white `#f5f5f0` |
| Button | near-black `#1a1a2e` |
| Border radius | `2px` |
| Backdrop blur | `backdrop-filter: blur(12px)` on nav + detail panel |

### 3.3 Routing

```
/                    → <RunsPage>               public
/runs/:id            → <RunsPage> + <RunDetailPanel>  public (nested outlet)
/workers             → <WorkersPage>            protected
/new                 → <NewRunPage>             protected
/compare?run_ids=…   → <ComparePage>            public
```

Protected routes render `<AuthModal>` as a blocking overlay when `localStorage.lmpc_token` is absent. No redirect — modal sits over the intended page and disappears after successful token entry.

### 3.4 File structure

```
frontend/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── src/
    ├── main.tsx
    ├── App.tsx              # QueryClientProvider + RouterProvider
    ├── api/
    │   ├── client.ts        # fetch wrapper, injects Authorization header
    │   └── types.ts         # openapi-typescript generated
    ├── hooks/
    │   ├── useAuth.ts       # read/write lmpc_token from localStorage
    │   └── useRunStream.ts  # SSE hook for live run status
    ├── components/
    │   ├── AuthModal.tsx
    │   ├── StatusBadge.tsx
    │   └── charts/
    │       ├── LatencyChart.tsx   # TTFT/TPOT/E2E box + scatter
    │       ├── ResourceChart.tsx  # GPU/CPU/power time-series
    │       └── CompareChart.tsx   # side-by-side bars
    └── pages/
        ├── RunsPage.tsx          # table + filter chips + <Outlet>
        ├── RunDetailPanel.tsx    # 50% panel, tabs: Summary/Latency/Resources/Logs
        ├── WorkersPage.tsx       # list + approve/reject buttons
        ├── NewRunPage.tsx        # 3-step wizard
        └── ComparePage.tsx       # pinned runs, overlay charts
```

### 3.5 Screen details

**Runs (`/`):**
- Filter chips: All / Completed / Running / Queued / Failed
- Table columns: checkbox, Platform, Model, Status (animated badge), Worker, Duration, TTFT p99
- Row click → navigate to `/runs/:id` (panel opens)
- Select 2 checkboxes → "Compare" button appears → navigates to `/compare?run_ids=a,b`
- TanStack Query polls `GET /api/v1/runs` every 5s while any run is in non-terminal state

**Run Detail Panel (`/runs/:id`):**
- Rendered as right-side outlet at 50% viewport width
- Header: platform/model name, run ID, status badge, ✕ close (navigates back to `/`)
- Tabs:
  - **Summary**: metric tiles (TTFT p99, TPOT p99, E2E p99, output TPS, goodput RPS, success rate) + reproducibility metadata
  - **Latency**: TTFT/TPOT/E2E distribution chart + per-request scatter (ECharts)
  - **Resources**: GPU util, GPU mem, CPU, power time-series (ECharts)
  - **Logs**: scrollable container stdout/stderr. Worker writes logs to `/var/log/lmpc/{run_id}.log` locally; no backend fetch endpoint in this phase. Tab shows a "Logs available on worker host only" placeholder with the run ID for manual retrieval.

**Workers (`/workers`):** Protected. Table: name, hostname, status badge, last heartbeat, specs (collapsed accordion), approve/reject buttons for `pending` rows.

**New Run (`/new`):** Protected. 3-step wizard:
1. Platform chips (`GET /api/v1/platforms`) + Model dropdown (`GET /api/v1/models`) + Prompt Set dropdown (`GET /api/v1/prompt-sets`)
2. Concurrency / Iterations / Max Tokens inputs + optional `platform_args` JSON textarea
3. Review: command preview string → "Submit N runs" → `POST /api/v1/runs`

**Compare (`/compare?run_ids=…`):** Reads run IDs from query string, calls `GET /api/v1/compare?run_ids=…`. Three ECharts: TTFT-p99 bar, output TPS bar, energy-per-1k-tokens bar. "Pin run" appends an ID to the query string.

### 3.6 Auth

`useAuth` hook:
- `getToken()` → `localStorage.getItem('lmpc_token')`
- `setToken(t)` → `localStorage.setItem('lmpc_token', t)`
- `clearToken()` → `localStorage.removeItem('lmpc_token')`

`<ProtectedRoute>` wraps children, renders `<AuthModal>` when no token. `api/client.ts` reads token on every request — no global state needed.

### 3.7 Type generation

```json
// package.json script
"gen:types": "openapi-typescript http://localhost:8080/openapi.json -o src/api/types.ts"
```

Run once after backend is up. Committed to repo.

---

## 4. Phase 7 — Docker Compose

### 4.1 `docker-compose.yml` (adds frontend)

```yaml
frontend:
  build: ./frontend
  ports: ["5173:5173"]
  environment:
    VITE_API_URL: http://localhost:8080
  depends_on: [backend]
```

### 4.2 `frontend/Dockerfile`

Two-stage:
- **Builder**: `node:20-alpine`, installs pnpm, runs `pnpm install && pnpm build`
- **Runtime**: `nginx:alpine`, copies `dist/` to `/usr/share/nginx/html`, adds `nginx.conf` with `try_files $uri /index.html` for SPA routing, exposes port 5173

### 4.3 `docker-compose.worker.yml`

No changes required — already matches the spec.

### 4.4 Supporting files

| File | Change |
|------|--------|
| `.env.example` | Add `VITE_API_URL=http://localhost:8080` |
| `frontend/.dockerignore` | Excludes `node_modules`, `.env*`, `dist` |
| `.gitignore` | Add `.superpowers/` if not present |

---

## 5. Build order

Phase 4 → Phase 5 → Phase 6 → Phase 7. Do not start Phase 6 until Phase 5 produces real benchmark data.

## 6. Out of scope

- Audit log endpoints (`audit_logs` table exists but no API surface)
- Monaco editor (replaced with plain JSON textarea in New Run wizard)
- OpenTelemetry tracing hooks
- Multi-replica backend (long-poll uses asyncio.Event; pg_notify migration deferred)
