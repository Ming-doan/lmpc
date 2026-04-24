Scaffold a full-stack LLM speed benchmarking app. Do not implement business logic
beyond what's needed to prove the wiring works — I'll fill that in. Create all
files and a working `docker compose up` dev loop.

# Stack
- Backend API: Python 3.12, FastAPI, SQLAlchemy 2.x (async), Alembic, asyncpg,
  redis-py (async), pydantic v2, uvicorn. JWT session auth via cookie. Using uv
- Worker: Python 3.12, separate service. Uses docker SDK (`docker` package) to
  spawn sibling inference containers via the mounted host Docker socket.
  Consumes from Redis list `queue:benchmarks` with reliable-queue pattern
  (BRPOPLPUSH into `queue:benchmarks:processing`). Using uv
- Frontend: Next.js 14 (app router), TypeScript, TailwindCSS, shadcn/ui,
  TanStack Query. SSE client for live run dashboard. Using pnpm
- Datastores: Postgres 16, Redis 7.
- Orchestration: docker-compose for dev, with `/var/run/docker.sock` mounted
  into the worker service so it can spawn sibling containers. Add an
  `nvidia` deploy block behind a profile so GPU is optional for local dev.
- Worker registration: Worker starts with only `API_URL` + `WORKER_SECRET`.
  On startup it POSTs machine info to `POST /internal/workers/register`; API
  returns `redis_url`. Worker uses that URL for all queue/stream ops. Worker
  can run on a separate GPU machine — no direct Redis/Postgres env vars needed.

# Repo layout
```
/
├── docker-compose.yml
├── docker-compose.gpu.yml        # overlay: adds nvidia runtime to worker
├── .env.example
├── README.md
├── apps/
│   ├── api/                      # FastAPI backend
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   └── src/
│   │       ├── main.py
│   │       ├── config.py
│   │       ├── db.py             # async engine + session
│   │       ├── redis_client.py
│   │       ├── auth/             # login, session, password hashing (argon2)
│   │       ├── models/           # SQLAlchemy models matching the DBML below
│   │       ├── schemas/          # pydantic request/response models
│   │       ├── routers/
│   │       │   ├── auth.py
│   │       │   ├── runs.py       # POST /runs (admin), GET /runs (public),
│   │       │   │                 # GET /runs/{id}, POST /runs/{id}/cancel,
│   │       │   │                 # GET /runs/{id}/events (SSE)
│   │       │   ├── models.py     # GET /models/search?source=hf|ollama&q=
│   │       │   ├── internal.py   # POST /internal/workers/register (returns redis_url),
│   │       │   │                 # POST /internal/workers/{id}/heartbeat
│   │       │   │                 # Auth: WORKER_SECRET header, not cookie
│   │       │   └── health.py
│   │       ├── services/
│   │       │   ├── queue.py      # LPUSH to queue:benchmarks
│   │       │   ├── sse.py        # XREAD + PUBSUB fanout to client
│   │       │   └── gpu.py        # nvidia-smi parse; model-size fit check
│   │       └── sse.py
│   ├── worker/                   # Benchmark worker
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   └── src/
│   │       ├── main.py           # main loop: BRPOPLPUSH → run_benchmark()
│   │       ├── runner.py         # orchestrates the 6-step state machine
│   │       ├── providers/
│   │       │   ├── base.py       # abstract: start(), wait_ready(), pull(),
│   │       │   │                 # send_requests(), stop()
│   │       │   ├── ollama.py
│   │       │   ├── vllm.py
│   │       │   ├── sglang.py
│   │       │   └── tgi.py
│   │       ├── metrics/
│   │       │   ├── collector.py  # samples request latency/ttft/tps
│   │       │   ├── resources.py  # cpu/gpu/ram/vram sampler (psutil + pynvml)
│   │       │   └── publisher.py  # XADD streams, HSET latest, PUBLISH events
│   │       ├── docker_mgr.py     # spawn sibling container, port alloc,
│   │       │                     # --gpus all passthrough, cleanup
│   │       └── persist.py        # on finalize: bulk insert snapshots,
│   │                             # update benchmark_runs.avg_*
│   └── web/                      # Next.js frontend
│       ├── package.json
│       ├── Dockerfile
│       ├── next.config.js
│       └── src/
│           ├── app/
│           │   ├── (public)/
│           │   │   ├── page.tsx              # leaderboard, lazy-loaded
│           │   │   └── runs/[id]/page.tsx    # public run detail
│           │   ├── (admin)/
│           │   │   ├── login/page.tsx
│           │   │   ├── new/page.tsx          # create-run form
│           │   │   └── runs/[id]/page.tsx    # live dashboard w/ SSE
│           │   └── api/ (proxy routes if needed)
│           ├── components/
│           │   ├── Leaderboard.tsx
│           │   ├── RunForm.tsx
│           │   ├── StepsTimeline.tsx
│           │   ├── MetricTiles.tsx           # avg + running latency/tps/ttft
│           │   └── MetricCharts.tsx          # time-series, recharts
│           ├── hooks/
│           │   └── useRunStream.ts           # EventSource → step + metric
│           └── lib/api.ts
├── packages/
│   └── shared/                   # OpenAPI-generated TS client for the API
└── scripts/
    ├── seed_admin.py             # create first admin from env vars
    └── dev_reset.sh
```

# Database
Generate SQLAlchemy models + an initial Alembic migration matching this DBML
exactly (tables: admins, sessions, secrets, benchmark_runs, benchmark_steps,
benchmark_metric_snapshots, benchmark_results, models_cache):

<paste the DBML from above>

# Redis keys
Implement helpers in `apps/api/src/redis_client.py` and
`apps/worker/src/metrics/publisher.py` for these keys:

<paste the Redis schema from above>

# Endpoints (minimum viable)
- `POST /auth/login` → cookie session
- `POST /auth/logout`
- `GET  /runs?cursor=...&limit=20` → public leaderboard, keyset paginated on
  completed_at DESC, only `is_public=true AND status='completed'`
- `POST /runs` (admin) → validate config, insert row with status='queued',
  LPUSH run_id to `queue:benchmarks`, return run_id
- `GET  /runs/{id}` → run + results + last 500 snapshots
- `POST /runs/{id}/cancel` (admin) → SET `run:{id}:cancel` 1
- `GET  /runs/{id}/events` (SSE) → on connect, XRANGE the steps + metrics
  streams from 0 to replay, then XREAD BLOCK to tail new entries. Also forward
  PUBSUB on `events:run:{id}`. Set `X-Accel-Buffering: no`.
- `GET  /models/search` → proxy HF `/api/models` or Ollama `/api/tags`

# Worker state machine
Implement `runner.py` as an explicit state machine emitting a step event for
each transition:
  picked → starting_container → pulling_model → warming → evaluating → finalizing → cleanup → completed
On any failure: → failed with error_code + error_message, then cleanup.
Poll `run:{id}:cancel` between states; if set, transition to cleanup → cancelled.

For `evaluating`: run concurrency sweep from config (default [1, 10, 50, 100]).
Emit a metric sample every ~1 second via the publisher. Store per-request
timings in memory and compute per-concurrency aggregates at the end.

# Dockerfiles / compose
- docker-compose.yml defines: postgres, redis, api, worker, web.
- worker service mounts `/var/run/docker.sock:/var/run/docker.sock` and sets
  `DOCKER_HOST=unix:///var/run/docker.sock`. It joins a shared docker network
  (`llmbench_net`) so spawned inference containers are reachable by name from
  the worker without publishing ports.
- docker-compose.gpu.yml overlay adds `runtime: nvidia` and
  `NVIDIA_VISIBLE_DEVICES=all` to the worker, and ensures spawned child
  containers are created with `device_requests=[{count:-1, capabilities:[['gpu']]}]`.
- .env.example with: POSTGRES_*, REDIS_URL, JWT_SECRET, SESSION_COOKIE_NAME,
  ADMIN_BOOTSTRAP_EMAIL, ADMIN_BOOTSTRAP_PASSWORD, HF_TOKEN, SECRETS_ENCRYPTION_KEY,
  WORKER_SECRET (shared between API and worker).
- Worker env vars: API_URL, WORKER_SECRET, DOCKER_HOST. No REDIS_URL or POSTGRES_DSN
  — worker gets redis_url from /internal/workers/register on startup.

# Conventions
- async everywhere in FastAPI; no sync DB calls.
- Structured logging with `structlog`, JSON in prod, console in dev.
- Lint/format: ruff + black for Python, eslint + prettier for TS.
- Minimal tests: one pytest per service that boots the app and hits /health.

# Deliverable
Generate every file above with enough implementation to:
1. `docker compose up` starts postgres+redis+api+worker+web.
2. `scripts/seed_admin.py` creates an admin.
3. Admin logs in, submits a run config, sees a placeholder run go through all
   state transitions on a stub provider (`providers/stub.py` that just sleeps
   and emits fake metrics).
4. Public leaderboard shows the completed run.

Leave real provider implementations (ollama/vllm/sglang/tgi) as TODO stubs with
clear docstrings describing the API shape — I will implement them.