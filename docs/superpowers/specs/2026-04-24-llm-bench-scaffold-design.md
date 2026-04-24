# LLM Bench — Scaffold Design
Date: 2026-04-24
Scope: Option A — thin wiring, prove `docker compose up` dev loop works end-to-end

---

## 1. Goal

Scaffold a full-stack LLM speed benchmarking app where:
- Admin logs in, submits a run config
- A stub provider walks through all 8 state transitions with realistic delays
- SSE dashboard shows live step + metric events
- Public leaderboard shows the completed run

No real inference providers yet. Business logic is filled in later.

---

## 2. Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.12, FastAPI, SQLAlchemy 2.x async, Alembic, asyncpg, redis-py async, pydantic v2, uvicorn, uv |
| Worker | Python 3.12, docker SDK, redis-py async, uv |
| Frontend | Next.js 14 app router, TypeScript, TailwindCSS, shadcn/ui (dark theme), TanStack Query, recharts |
| Datastores | Postgres 16, Redis 7 |
| Orchestration | docker-compose (dev), docker-compose.gpu.yml (overlay) |

---

## 3. Architecture

```
┌─────────────┐    HTTP/SSE    ┌─────────────┐    asyncpg    ┌──────────────┐
│  Next.js 14 │ ◄────────────► │  FastAPI    │ ◄────────────► │  Postgres 16 │
│  (web:3000) │                │  (api:8000) │               └──────────────┘
└─────────────┘                └──────┬──────┘
                                      │ redis-py async
                               ┌──────▼──────┐
                               │   Redis 7   │
                               └──────┬──────┘
                                      │ BRPOPLPUSH (reliable queue)
                               ┌──────▼──────┐    docker SDK    ┌──────────────────┐
                               │   Worker    │ ────────────────► │ Sibling inference │
                               │  (any host) │                   │ containers        │
                               └─────────────┘                   └──────────────────┘
```

- **API** is the single control plane: auth, CRUD, SSE streaming, worker registration
- **Worker** connects only to API on startup, receives `redis_url` from registration response
- **Worker** can run on a separate GPU machine — only needs `API_URL` + `WORKER_SECRET`
- **Web** is a pure consumer — no server-side logic beyond Next.js routing

---

## 4. Worker Registration Flow

1. Worker starts with env vars: `API_URL`, `WORKER_SECRET`, `DOCKER_HOST`
2. On startup: POST `/internal/workers/register` with machine info `{worker_id, gpu_model, vram_mb, cpu, ram_mb}`
3. API authenticates via `WORKER_SECRET` header, inserts/upserts into `workers` table, returns `{redis_url, heartbeat_interval_s}`
4. Worker uses `redis_url` for all queue/stream ops
5. Worker POSTs `/internal/workers/{id}/heartbeat` every 5s; API refreshes `worker:{id}:heartbeat` TTL in Redis and updates `workers.last_heartbeat` in Postgres

---

## 5. Data Flow — Run Lifecycle

1. Admin `POST /runs` → validate config → insert `benchmark_runs` (`status=queued`) → LPUSH `run_id` to `queue:benchmarks` → return `{run_id}`
2. Worker BRPOPLPUSH `run_id` into `queue:benchmarks:processing`, SET `worker:{id}:active_run` NX
3. Worker walks state machine, emitting at each transition:
   - XADD to `run:{id}:steps` stream
   - PUBLISH to `events:run:{id}` pubsub channel
4. Every ~1s during `evaluating`: XADD to `run:{id}:metrics:series`, HSET `run:{id}:metrics:latest`
5. On `finalizing`: bulk insert snapshots → update `benchmark_runs.avg_*`
6. Worker removes `run_id` from `queue:benchmarks:processing`, clears `worker:{id}:active_run`

---

## 6. SSE Streaming

Endpoint: `GET /runs/{id}/events`

1. On connect: XRANGE replay `run:{id}:steps` and `run:{id}:metrics:series` from `0`
2. Then: concurrent XREAD BLOCK tail on both streams + subscribe to `events:run:{id}` pubsub
3. Forward all as SSE events typed `step`, `metric`, or `status`
4. Header: `X-Accel-Buffering: no`

---

## 7. API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | — | Cookie session (token stored hashed in `sessions` table) |
| POST | `/auth/logout` | cookie | Clear session |
| GET | `/runs` | — | Public leaderboard, keyset paginated `completed_at DESC` |
| POST | `/runs` | cookie | Create run, enqueue |
| GET | `/runs/{id}` | — | Run + results + last 500 snapshots |
| POST | `/runs/{id}/cancel` | cookie | SET `run:{id}:cancel 1` |
| GET | `/runs/{id}/events` | — | SSE stream |
| GET | `/models/search` | — | Proxy HF or Ollama model list |
| GET | `/health` | — | `{status, db, redis}` |
| POST | `/internal/workers/register` | WORKER_SECRET header | Register worker, return `redis_url` |
| POST | `/internal/workers/{id}/heartbeat` | WORKER_SECRET header | Refresh liveness |

---

## 8. Worker State Machine

```
queued → picked → starting_container → pulling_model → warming → evaluating → finalizing → cleanup → completed

Any state → failed → cleanup → failed
Cancel poll → cleanup → cancelled
```

**Stub provider timing:**
- `starting_container`: sleep 2s
- `pulling_model`: 10 progress ticks × 300ms (0%→100%)
- `warming`: sleep 1s
- `evaluating`: concurrency levels `[1, 10, 50, 100]`, each 3s with metric sample every 1s (randomized plausible values)
- `finalizing`: sleep 1s
- `cleanup`: sleep 0.5s

Worker polls `run:{id}:cancel` between every state transition.

---

## 9. Database Tables

From `DB_SCHEMA.txt` — 9 tables total:
`workers`, `admins`, `sessions`, `secrets`, `benchmark_runs`, `benchmark_steps`, `benchmark_metric_snapshots`, `benchmark_results`, `models_cache`

Single Alembic migration `0001_initial.py` creates all tables.

---

## 10. Redis Keys

From `QUEUE_SCHEMA.txt` — key groups:
- Queue: `queue:benchmarks`, `queue:benchmarks:processing`, `queue:benchmarks:dead`
- Run state: `run:{id}:state`, `run:{id}:cancel`, `run:{id}:lock`
- Streams: `run:{id}:steps`, `run:{id}:metrics:series`
- Hashes: `run:{id}:metrics:latest`, `run:{id}:metrics:running_avg`
- Pubsub: `events:run:{id}`
- Worker: `worker:{id}:heartbeat` (TTL 15s), `worker:{id}:info`, `worker:{id}:active_run`

---

## 11. Docker Compose

**docker-compose.yml** — 5 services: `postgres`, `redis`, `api`, `worker`, `web`
- `api` depends on postgres + redis healthy
- `worker` depends on api healthy; mounts `/var/run/docker.sock`; env: `API_URL`, `WORKER_SECRET`
- `web` depends on api; env: `NEXT_PUBLIC_API_URL=http://localhost:8000`
- All services share `llmbench_net` bridge network
- Spawned inference containers join `llmbench_inference_net` (local to worker host)

**docker-compose.gpu.yml** — overlay adds `runtime: nvidia` + `NVIDIA_VISIBLE_DEVICES=all` to worker only

---

## 12. Scripts

- `scripts/seed_admin.py` — reads `ADMIN_BOOTSTRAP_EMAIL` + `ADMIN_BOOTSTRAP_PASSWORD`, inserts admin with argon2 hash
- `scripts/dev_reset.sh` — drop+recreate DB, flush Redis, run migrations, seed

---

## 13. Frontend Pages (dark theme)

| Route | Description |
|-------|-------------|
| `/` | Public leaderboard — TanStack Query infinite scroll, sorted `completed_at DESC` |
| `/login` | Admin login form |
| `/new` | Create-run form (admin) |
| `/runs/[id]` (admin) | Live dashboard: StepsTimeline + MetricTiles + MetricCharts via SSE |
| `/runs/[id]` (public) | Read-only run detail |

Key components: `Leaderboard`, `RunForm`, `StepsTimeline`, `MetricTiles`, `MetricCharts`, `useRunStream` hook

---

## 14. Conventions

- async everywhere in FastAPI; no sync DB calls
- structlog: JSON in prod, console in dev
- Python lint: ruff + black; TS lint: eslint + prettier
- One pytest per service hitting `/health` to prove boot
- Real provider implementations (ollama/vllm/sglang/tgi) left as TODO stubs with docstrings
