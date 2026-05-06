# lmpc — LLM Platform Comparison: Implementation Spec

---

## Mission

Build `lmpc`, a benchmarking platform that runs identical workloads against multiple LLM serving stacks (Ollama, LMStudio, vLLM, SGLang, TGI, Triton-LLM) on a fleet of self-registered worker machines and compares them on latency, throughput, resource use, and energy efficiency.

## Architecture

```
┌──────────────┐    ┌────────────────┐    ┌────────────────┐
│  React FE    │◄──►│   FastAPI BE   │◄──►│  Postgres +    │
│  (admin +    │    │  (REST + auth) │    │  TimescaleDB   │
│   dashboard) │    └────────┬───────┘    └────────────────┘
└──────────────┘             │
                             │ HTTPS (long-poll)
                             ▼
                    ┌────────────────────┐
                    │  Worker (Python)   │  ← runs on any machine,
                    │  - registers       │    outbound-only network
                    │  - polls for jobs  │
                    │  - launches sibling│
                    │    container       │
                    │  - load-generates  │
                    │  - reports metrics │
                    └─────────┬──────────┘
                              │ docker.sock
                              ▼
                    ┌────────────────────┐
                    │  Platform-under-   │  ← short-lived,
                    │  test container    │    one per run
                    │  (vllm/ollama/...) │
                    └────────────────────┘
```

Workers never accept inbound connections — they always initiate. Backend is the single source of truth.

## Tech stack (pin these versions)

- **Backend**: Python 3.12, uv, FastAPI 0.115+, SQLAlchemy 2.x, Alembic, Pydantic v2, asyncpg
- **Worker**: Python 3.12, uv, httpx, docker SDK (`docker` package), pynvml, psutil
- **DB**: Postgres 16 with TimescaleDB 2.x extension, pgcrypto
- **Frontend**: React 18, pnpm, TypeScript 5, Vite, TanStack Query, Tailwind, shadcn/ui, Apache ECharts (`echarts-for-react`), React-Router
- **Infra**: Docker Compose for dev; one network `lmpc-net` shared by BE/DB/FE; workers run separately on host-network or own machines

## Agent skills for implement
- **Brainstorming**: `/brainstorming` -  Think about the requirements, draft an specs, plans. `/writing-plans` - Writing implementation plans after brainstorm
- **Backend**: `/fastapi` - FastAPI best-practice coding pattern, convensions
- **Docker**: `/multi-stage-dockerfile` - Best-practice, production grade dockerfile
- **Frontend**: `/vercel-react-best-practices` - React best-practice coding pattern, convensions. `/impeccable` - Use to create perfect UI/UX

## Repo layout

```
lmpc/
├── backend/
│   ├── app/
│   │   ├── api/v1/{workers,runs,configs,platforms,models,results}.py
│   │   ├── core/{config,security,db,deps}.py
│   │   ├── models/      # SQLAlchemy ORM
│   │   ├── schemas/     # Pydantic
│   │   ├── services/    # business logic
│   │   ├── janitor.py   # background lease reclaim
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── worker/
│   ├── lmpc_worker/
│   │   ├── adapters/
│   │   │   ├── base.py          # PlatformAdapter abstract class
│   │   │   ├── ollama.py
│   │   │   ├── vllm.py
│   │   │   ├── sglang.py
│   │   │   ├── tgi.py
│   │   │   ├── lmstudio.py
│   │   │   └── triton.py
│   │   ├── load_generator.py    # async httpx workers
│   │   ├── metric_collector.py  # pynvml + psutil sampler
│   │   ├── docker_runner.py     # sibling container lifecycle
│   │   ├── client.py            # backend API client
│   │   ├── registration.py
│   │   ├── poller.py            # main loop
│   │   └── main.py
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/{Dashboard,Workers,Runs,NewRun,RunDetail,Compare}.tsx
│   │   ├── components/charts/   # ECharts wrappers
│   │   ├── api/                 # generated from OpenAPI
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── db/
│   ├── schema.dbml
│   └── init.sql                 # CREATE EXTENSION + hypertables
├── docs/
│   └── SPECS.md                 # <!-- You are here -->
├── docker-compose.yml
├── docker-compose.worker.yml    # separate file: worker runs anywhere
├── .env.example                 # App credentials
└── README.md
```

---

## Phase 1 — Database & migrations

1. Author the schema from the DBML provided in chat. Translate to SQLAlchemy 2.x models with `Mapped[...]` typing.
2. Initial Alembic migration creates all tables.
3. Second migration: `CREATE EXTENSION IF NOT EXISTS timescaledb;`, `CREATE EXTENSION IF NOT EXISTS pgcrypto;`, then `SELECT create_hypertable('metric_samples', 'time')` and `SELECT create_hypertable('request_traces', 'started_at')`. Use `if_not_exists => TRUE`.
4. Seed script populates `platforms` (ollama, vllm, sglang, tgi, lmstudio, triton) and a default `prompt_sets` row with ~20 varied prompts (short Q&A, code, summarization, long context).

**Acceptance**: `alembic upgrade head` works against fresh Postgres; seed script idempotent; `\d+ metric_samples` shows hypertable.

---

## Phase 2 — Backend: workers, queue, leasing

Implement these endpoints. All protected endpoints take `Authorization: Bearer <token>` by using APP_TOKEN.
All authenticated endpoints take `Authorization: Bearer <token>` with generated api token

### Worker lifecycle (worker → BE)

- `POST /api/v1/workers/register` — body: `{name, hostname, specs, capabilities}`. Returns `{worker_id, api_token, status: "pending"}`. Status stays `pending` until admin approves. The token is the only copy — store hash only.
- `POST /api/v1/workers/heartbeat` — auth'd. Body: `{status: "online"|"busy", current_run_id?}`. Updates `last_heartbeat_at`. If worker holds a leased run, also extends `leased_until` by 60s.
- `POST /api/v1/workers/jobs/poll` — auth'd. Long-poll up to 25 seconds. Inside a transaction:
    ```sql
    SELECT * FROM benchmark_runs
    WHERE status = 'queued'
      AND (
        SELECT capabilities->'platforms' FROM workers WHERE id = :worker_id
      ) ? (SELECT name FROM platforms WHERE id = config_id_resolved.platform_id)
    ORDER BY priority DESC, queued_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1;
    ```
    Then `UPDATE … SET status='claimed', worker_id=:wid, claimed_at=now(), leased_until=now()+interval '60 seconds'`. Return the full run + resolved config + platform + model + prompt set.
- `POST /api/v1/workers/jobs/{run_id}/status` — auth'd. Body: `{status, started_at?, completed_at?, container_id?, error?, image_digest?, platform_version?}`. Validate transitions: claimed→running→{completed,failed,timeout}.
- `POST /api/v1/workers/jobs/{run_id}/results` — auth'd. Body: `{aggregates: {...benchmark_results columns...}, request_traces: [...], metric_samples: [...]}`. Single transaction, batch-insert traces and samples (use `COPY` or executemany).

### Admin endpoints (FE → BE)

- `GET /api/v1/workers` — protected, list all, filter by status.
- `POST /api/v1/workers/{id}/approve` and `/reject`. protected
- `GET/POST /api/v1/configs` — CRUD run configs. protected
- `POST /api/v1/runs` — create one or more `benchmark_runs` from a config. Body: `{config_id, iterations: 3, priority: 0}`. Creates N rows. protected
- `GET /api/v1/runs?status=&platform=&model=` — list with filters.
- `GET /api/v1/runs/{id}` — full detail incl. results.
- `GET /api/v1/runs/{id}/traces` and `/metrics` — paginated.
- `POST /api/v1/runs/{id}/cancel` — sets status to `cancelled`; worker checks status on heartbeat and aborts. protected
- `GET /api/v1/compare?run_ids=a,b,c` — returns aligned data structure for comparison charts.

### Janitor (background asyncio task)

Every 30s: `UPDATE benchmark_runs SET status='queued', worker_id=NULL, leased_until=NULL, attempt=attempt+1 WHERE status IN ('claimed','running') AND leased_until < now() AND attempt < max_attempts`. Mark `failed` if `attempt >= max_attempts`. Also: mark workers `offline` where `last_heartbeat_at < now() - interval '90 seconds'`.

**Acceptance**: write integration tests with two simulated workers polling; assert no double-claim; kill one mid-job, assert janitor reclaims after lease expiry.

---

## Phase 3 — Worker: registration, polling, lifecycle

- On startup: read `LMPC_API_URL`, `LMPC_WORKER_NAME` from env. If `~/.lmpc/token` exists, use it; else POST `/register`, save token, exit with message "Awaiting approval. Re-run after approval."
- Once approved: main loop
  ```python
  while not shutdown:
      await heartbeat()
      job = await poll_for_job()  # 25s long-poll
      if job:
          await heartbeat_loop_in_background()  # every 30s
          await run_benchmark(job)  # see Phase 5
          await report_results(job)
  ```
- Graceful shutdown: catch SIGTERM, finish current job or release lease (`status: failed, error: "worker shutdown"`), exit.

**Acceptance**: register one worker, approve via direct DB edit, observe it polling. Kill it during a benchmark, see lease reclaimed.

---

## Phase 4 — Platform adapters

Define `PlatformAdapter` ABC:

```python
class PlatformAdapter(ABC):
    name: str
    @abstractmethod
    def build_container_spec(self, model: Model, args: dict) -> ContainerSpec: ...
    @abstractmethod
    async def wait_until_ready(self, base_url: str, timeout_s: int) -> ReadinessInfo: ...
    @abstractmethod
    async def send_request(self, client, base_url, prompt, max_tokens, stream=True) -> RequestResult: ...
    # RequestResult includes ttft_ms, tpot_ms, e2e_ms, input_tokens, output_tokens, success, error
```

Implement adapters with these defaults (override via `platform_args`):

- **Mock**: testing purpose adapters, mock IO waiting, mock result streaming.
- **Ollama**: image `ollama/ollama:latest`, port 11434, OpenAI-compatible API at `/v1/chat/completions`. Note: model is pulled on first request — measure as part of `model_load_ms`, not `container_start_ms`.
- **vLLM**: image `vllm/vllm-openai:latest`, port 8000, args include `--model`, `--gpu-memory-utilization`, `--max-model-len`. OpenAI-compatible.
- **SGLang**: image `lmsysorg/sglang:latest`, port 30000, OpenAI-compatible at `/v1/chat/completions`.
- **TGI**: image `ghcr.io/huggingface/text-generation-inference:latest`, port 80. Has its own `/generate_stream` endpoint, also OpenAI-compatible at `/v1/chat/completions` in newer versions — prefer the OpenAI endpoint for fairness.
- **LMStudio**: typically run on host, not container. Adapter assumes user provides `base_url`. Container path optional.
- **Triton-LLM**: image `nvcr.io/nvidia/tritonserver:<tag>-trtllm-python-py3`, port 8000. Requires pre-built model repository — adapter takes a `model_repo_path` arg.

For all: streaming SSE/chunked response measurement. TTFT = `time(first_chunk) - time(request_sent)`. TPOT = `(time(last_chunk) - time(first_chunk)) / (output_tokens - 1)`.

**Critical**: token counts must come from the platform's response (when available) rather than re-tokenizing locally — re-tokenizing introduces ambiguity across model families.

Loads adapters in list:

```python
adapters: list[PlatformAdapter] = [
    OllamaAdapter(),
    ...
]
```

---

## Phase 5 — Benchmark execution

`run_benchmark(job)` orchestrates:

1. **Setup**: pull image (record digest), create docker network if not exists, start sibling container with model cache volume mounted, GPU passthrough.
2. **Readiness wait**: poll until adapter's `wait_until_ready` succeeds; record `container_start_ms`, `model_load_ms`.
3. **Warmup**: send `warmup_requests` (default 3) sequential requests, discard results.
4. **Metric collector start**: launch background task sampling at 1Hz: psutil for CPU/RAM, pynvml for GPU, docker stats for container. Push to in-memory deque.
5. **Load generation**: `concurrency` workers each send `num_requests / concurrency` requests, drawing prompts from the prompt set. Use `asyncio.gather`. Each request → `RequestResult` appended to a list.
6. **Teardown**: stop metric collector, stop and remove container, remove network if empty.
7. **Aggregate**: compute percentiles (numpy), success rate, peaks, energy = ∫watts·dt (trapezoidal). Compute `goodput_rps` using SLO from `benchmark_args` (default `ttft_p99 < 500ms AND tpot_p99 < 100ms`).
8. **Report**: POST results to backend.

Log container stdout/stderr to local file `/var/log/lmpc/{run_id}.log` for debugging; backend can later fetch via a separate endpoint if needed.

**Acceptance**: full end-to-end run for vLLM + a small model (e.g. `Qwen2.5-0.5B-Instruct`) from FE click to dashboard chart.

---

## Phase 6 — Frontend

Fonts (from Google fonts):
1. **Noto Serif** — Grand heading, emphasized title
2. **Inter** — Content, text, button, labels, etc

Theme, Colors, Style:
1. **Theme**
- Primary Light mode, Off-white surfaces
- Near black buttons
2. **Color**
- Primary: #8100D1, Secondary: #15173D
3. **UI Style**
- Border radius: 2px
- Background blur effect

5 screens, all consuming the same TanStack Query setup:

0. **Layout**
- navbar with app name, view workers, create new runs
1. **Workers** (protected)
- list with status badges, last heartbeat, specs (collapsed), approve/reject actions for `pending`.
- path: {host}/workers
2. **New Run** (protected)
- form: pick platform → model → prompt set → concurrency/iterations/max_tokens → optional platform_args JSON editor (Monaco) → submit. Show command preview.
- path: {host}/new
3. **Runs** (Entry page, public)
- table with status, platform, model, worker, started, duration. Filter chips. Click row → detail. Select 2 rows, show compare button
- path: {host}/
4. **Run Detail** (public)
- open as side panel in **Runs**, width 50% screen
- top: status + reproducibility metadata. Tabs: Summary (aggregate cards), Latency (TTFT/TPOT/E2E distribution + per-request scatter), Resources (time-series chart of GPU util, GPU mem, CPU, power), Logs (container stdout). Use `echarts-for-react`.
5. **Compare** (public)
- multi-select runs (pinning system), side-by-side cards + overlay charts: TTFT-p99-vs-concurrency, output-tps-vs-concurrency, energy-per-1k-tokens bar.
- path: {host}/compare?run_ids=a,b,c
6. **Authenticate**
- when user open protected page, check `TOKEN` in cookie storage. If not, show modal to provide app token -> save token for later uses

OpenAPI client generation: backend exports schema, run `openapi-typescript` to generate types in `frontend/src/api/types.ts`.

---

## Phase 7 — Docker Compose

`docker-compose.yml` (dev stack — DB, BE, FE):
```yaml
services:
  db:
    image: timescale/timescaledb:latest-pg16
    environment: { POSTGRES_PASSWORD: lmpc, POSTGRES_DB: lmpc }
    volumes: [db-data:/var/lib/postgresql/data]
    ports: ["5432:5432"]
  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:lmpc@db:5432/lmpc
      JWT_SECRET: dev-only-change-me
    ports: ["8080:8080"]
    depends_on: [db]
  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    environment: { VITE_API_URL: http://localhost:8080 }
volumes: { db-data: }
```

`docker-compose.worker.yml` (runs separately, on the GPU host):
```yaml
services:
  worker:
    build: ./worker
    environment:
      LMPC_API_URL: ${LMPC_API_URL}
      LMPC_WORKER_NAME: ${HOSTNAME}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ~/.cache/huggingface:/root/.cache/huggingface
      - ~/.ollama:/root/.ollama
      - ./worker-data:/data
    deploy:
      resources:
        reservations:
          devices: [{driver: nvidia, count: all, capabilities: [gpu]}]
    restart: unless-stopped
```

---

## Cross-cutting requirements

- **Observability**: structured JSON logs (loguru or stdlib + json formatter) with `run_id`, `worker_id`, `request_idx` fields. Tracing optional but ready for OpenTelemetry hooks.
- **Config**: Pydantic `BaseSettings` from env on both BE and worker. No magic strings.
- **Tests**: pytest for backend (use testcontainers for Postgres). For worker, mock the Docker SDK and httpx with `respx`. Aim for >70% coverage on services and adapters.
- **Migrations**: every schema change is an Alembic revision; never edit existing revisions.
- **Type-checking**: `mypy --strict` on backend; `tsc --noEmit` on frontend in CI.
- **Security**: tokens hashed with sha256; rate-limit `/register` (e.g. 5/min/IP); CORS allow-list from env.
- **Determinism**: every benchmark run records image digest, platform version (queried from container), git SHA of lmpc itself, model file hash if available.

## Definition of done

- One-command boot: `docker compose up` starts BE/FE/DB; visit `localhost:5173`.
- Worker registers from a separate machine with one command, appears as `pending`, admin approves.
- Submit a vLLM + Qwen2.5-0.5B run with concurrency=4, iterations=3 → 3 rows in `benchmark_runs` → worker picks them up sequentially → results stream into Run Detail page → Compare page can overlay against an Ollama run of same model.
- Killing the worker mid-run results in lease reclaim within 90s and the run re-queued.
- Two workers polling simultaneously never both claim the same run (proven by integration test with 1000-run queue).

## Build order recap

Phase 1 → 2 → 3 (you can demo polling without benchmarks yet) → 4 → 5 (now end-to-end works via curl/HTTPie) → 6 → 7. Don't start Phase 6 before Phase 5 produces real data — frontends built against fixtures end up wrong.

## Documentation

Write document in README.md, include: app introduction, technology flow, support platforms, quick commands