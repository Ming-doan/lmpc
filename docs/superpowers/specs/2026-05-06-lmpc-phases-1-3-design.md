# lmpc — Phases 1–3 Design

**Date:** 2026-05-06  
**Scope:** Phase 1 (DB & migrations), Phase 2 (Backend API), Phase 3 (Worker registration & polling)  
**Deferred:** Phases 4–7 (platform adapters, benchmark execution, frontend, Docker Compose)

---

## 1. Repository Layout

```
lmpc/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # routers: workers, runs, configs, platforms, models, results
│   │   ├── core/            # config.py, security.py, db.py, deps.py
│   │   ├── models/          # SQLAlchemy ORM (Mapped[...])
│   │   ├── schemas/         # Pydantic v2
│   │   ├── services/        # queue.py, janitor.py
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml       # uv, Python 3.12
│   └── Dockerfile
├── worker/
│   ├── lmpc_worker/
│   │   ├── adapters/        # base.py (ABC), stub.py
│   │   ├── client.py        # httpx backend API client
│   │   ├── registration.py
│   │   ├── poller.py
│   │   └── main.py
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── db/
│   ├── schema.dbml
│   └── init.sql
├── docs/
└── docker-compose.yml       # db + backend only
```

`backend/` and `worker/` are independent uv projects. No shared Python package — the worker duplicates only the minimal job-response schema it needs.

---

## 2. Phase 1 — Database & Migrations

### 2.1 Alembic revisions

| Revision | Description |
|----------|-------------|
| `0001_initial` | All tables from `db/schema.dbml` |
| `0002_timescale` | Extensions + hypertables |

**0001_initial** creates:
- `workers`, `platforms`, `models`, `prompt_sets`
- `run_configs`, `benchmark_runs`, `benchmark_results`
- `request_traces`, `metric_samples`, `audit_logs`

All UUIDs use `gen_random_uuid()` (pgcrypto). All indexes from the DBML are included.

**0002_timescale** runs:
```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
SELECT create_hypertable('metric_samples', 'time',
  chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
SELECT create_hypertable('request_traces', 'started_at',
  chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
```
Uses `execute_if_not_created` pattern in Alembic to skip if already applied.

### 2.2 SQLAlchemy models

- All models use `Mapped[T]` / `mapped_column()` syntax (SQLAlchemy 2.x)
- `JSONB` columns typed as `Mapped[dict[str, Any]]`
- Relationships declared but lazy-loaded by default (async-safe: `selectin` where needed)
- Base: `DeclarativeBase` subclass in `app/models/base.py`

### 2.3 Seed script

`backend/scripts/seed.py` — idempotent, `INSERT … ON CONFLICT DO NOTHING`:
- 6 platform rows: `ollama`, `vllm`, `sglang`, `tgi`, `lmstudio`, `triton`
- 1 default `prompt_sets` row with 20 prompts (mix of: short Q&A ×6, code ×5, summarization ×5, long-context ×4)

---

## 3. Phase 2 — Backend API

### 3.1 Config (`app/core/config.py`)

```python
class Settings(BaseSettings):
    DATABASE_URL: str
    APP_TOKEN: str
    JWT_SECRET: str = "change-me"   # unused until Phase 6
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    LOG_LEVEL: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env")
```

### 3.2 Auth (`app/core/security.py`)

Two auth paths:

| Path | Mechanism |
|------|-----------|
| Admin (FE → BE) | `Authorization: Bearer <APP_TOKEN>` — `secrets.compare_digest` |
| Worker (worker → BE) | `Authorization: Bearer <token>` — SHA-256 hash lookup in `workers` table |

FastAPI dependencies:
- `Depends(require_admin)` — raises 401 if APP_TOKEN mismatch
- `Depends(require_worker)` — returns `Worker` ORM row or raises 401

### 3.3 Worker lifecycle endpoints

All at `/api/v1/workers/`:

| Method + Path | Auth | Description |
|---------------|------|-------------|
| `POST /register` | none (rate-limited 5/min/IP via slowapi) | Create worker row, return token once |
| `POST /heartbeat` | worker | Update `last_heartbeat_at`; extend lease if active run |
| `POST /jobs/poll` | worker | 25s long-poll, claim job with `FOR UPDATE SKIP LOCKED` |
| `POST /jobs/{run_id}/status` | worker | Validate + apply status transition |
| `POST /jobs/{run_id}/results` | worker | Batch-insert traces/samples, upsert results |

`/register` response includes `worker_id`, `api_token` (only copy ever returned), `heartbeat_interval_s: 30`.

State transitions enforced:
```
queued → claimed → running → completed
                           → failed
                           → timeout
```

### 3.4 Admin endpoints

All at `/api/v1/`, protected by `require_admin`:

| Method + Path | Description |
|---------------|-------------|
| `GET /workers` | List all, optional `?status=` filter |
| `POST /workers/{id}/approve` | Set `approved=true`, `status=online` |
| `POST /workers/{id}/reject` | Set `approved=false`, `status=disabled` |
| `GET /configs` | List run configs |
| `POST /configs` | Create run config |
| `GET /configs/{id}` | Get single config |
| `POST /runs` | Create N `benchmark_runs` rows from config |
| `GET /runs` | List with `?status=&platform=&model=` filters |
| `GET /runs/{id}` | Full run detail including results |
| `GET /runs/{id}/traces` | Paginated request traces |
| `GET /runs/{id}/metrics` | Paginated metric samples |
| `POST /runs/{id}/cancel` | Set status → `cancelled` |
| `GET /compare` | `?run_ids=a,b,c` — aligned comparison payload |

### 3.5 Long-poll (`app/services/queue.py`)

```python
_jobs_available = asyncio.Event()

async def notify_jobs_available():
    _jobs_available.set()

async def wait_for_job(worker, db, timeout=25.0):
    try:
        await asyncio.wait_for(_jobs_available.wait(), timeout)
    except asyncio.TimeoutError:
        pass
    _jobs_available.clear()
    return await claim_next_job(worker, db)
```

`notify_jobs_available()` called by `POST /runs` after inserting rows. Works within a single process (single-replica dev). Multi-replica migration path: replace with `pg_notify` + asyncpg listener.

### 3.6 Janitor (`app/services/janitor.py`)

Asyncio background task started in `app/main.py` `lifespan`:
- Runs every 30s
- Reclaims expired leases: `status IN ('claimed','running') AND leased_until < now() AND attempt < max_attempts` → reset to `queued`, increment `attempt`, call `notify_jobs_available()`
- Marks as `failed` if `attempt >= max_attempts`
- Marks workers `offline` where `last_heartbeat_at < now() - interval '90 seconds'`

### 3.7 Observability

- Structured JSON logging via `structlog`
- Every log record includes `run_id` and `worker_id` where applicable
- Correlation via FastAPI middleware that injects a `request_id` into context

---

## 4. Phase 3 — Worker

### 4.1 Config (`lmpc_worker/config.py`)

```python
class WorkerSettings(BaseSettings):
    LMPC_API_URL: str
    LMPC_WORKER_NAME: str = socket.gethostname()
    LMPC_TOKEN_PATH: Path = Path.home() / ".lmpc" / "token"
    LMPC_PLATFORMS: list[str] = ["stub"]   # comma-separated in env
    LMPC_LOG_LEVEL: str = "INFO"
```

### 4.2 Startup (`lmpc_worker/registration.py`)

1. If `LMPC_TOKEN_PATH` exists → load token
2. Else → `POST /api/v1/workers/register` with `{name, hostname, specs, capabilities}`
   - `specs`: collected via `psutil` (CPU, RAM) + `pynvml` if available
   - `capabilities.platforms`: from `LMPC_PLATFORMS` env var (comma-separated), default `["stub"]`
   - Save token to `LMPC_TOKEN_PATH`
   - Print "Registered. Awaiting admin approval. Re-run after approval." and exit
3. Poll `/heartbeat` until worker status is `online`; retry every 10s fixed interval

### 4.3 Main loop (`lmpc_worker/poller.py`)

```python
while not shutdown:
    await heartbeat()
    job = await poll()          # 25s long-poll
    if job:
        heartbeat_task = asyncio.create_task(heartbeat_loop(30))
        try:
            result = await execute(job)   # Phase 3: stub adapter
        finally:
            heartbeat_task.cancel()
        await report_results(job, result)
```

### 4.4 Adapters (`lmpc_worker/adapters/`)

**`base.py`** — `PlatformAdapter` ABC:
```python
class PlatformAdapter(ABC):
    name: str
    @abstractmethod
    def build_container_spec(self, model, args) -> ContainerSpec: ...
    @abstractmethod
    async def wait_until_ready(self, base_url, timeout_s) -> ReadinessInfo: ...
    @abstractmethod
    async def send_request(self, client, base_url, prompt, max_tokens, stream=True) -> RequestResult: ...
```

`RequestResult`: `ttft_ms`, `tpot_ms`, `e2e_ms`, `input_tokens`, `output_tokens`, `success`, `error`.

**`stub.py`** — mock adapter for Phase 3 testing; sleeps 0.1s per request, returns plausible random metrics.

Adapter registry:
```python
ADAPTERS: dict[str, PlatformAdapter] = {"stub": StubAdapter()}
```

### 4.5 Graceful shutdown

`SIGTERM` / `SIGINT` handler sets `shutdown = True`. If mid-job, worker posts `status=failed, error="worker shutdown"` before exiting. Uses `asyncio.run()` with the signal handler registered inside the event loop.

---

## 5. Cross-Cutting

### 5.1 Auth decisions summary

| Consumer | Token type | Stored as |
|----------|-----------|-----------|
| Admin / FE | `APP_TOKEN` env var | plaintext in env |
| Worker | per-worker random 32-byte hex | SHA-256 hash in `workers.api_token_hash` |

`JWT_SECRET` is in `Settings` for Phase 6 (frontend cookie auth). Unused in Phases 1–3.

### 5.2 Rate limiting

`slowapi` on `POST /api/v1/workers/register`: 5 requests/min/IP. No other endpoints rate-limited in this phase.

### 5.3 Tests

- **Backend**: pytest + `testcontainers-python` (real Postgres with TimescaleDB image). Test targets: queue service (no double-claim), janitor (lease reclaim), state machine transitions.
- **Worker**: `pytest` + `respx` for httpx mocking. Test targets: registration flow, poll loop, graceful shutdown.

### 5.4 docker-compose.yml (Phases 1–3)

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
      APP_TOKEN: dev-token
      JWT_SECRET: dev-only-change-me
    ports: ["8080:8080"]
    depends_on: [db]
volumes: { db-data: }
```

---

## 6. Out of Scope (Phases 4–7)

- Real platform adapters (Ollama, vLLM, SGLang, TGI, LMStudio, Triton)
- Benchmark execution orchestration (docker runner, metric collector, load generator)
- Frontend (React + Vite)
- Full Docker Compose with frontend service
- OpenAPI client generation
