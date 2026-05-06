# lmpc — LLM Platform Comparison

Benchmarking platform that runs identical workloads against multiple LLM serving stacks on a fleet of self-registered GPU workers and compares them on latency, throughput, resource use, and energy efficiency.

## Supported platforms

| Platform | Image | API style |
|----------|-------|-----------|
| **Ollama** | `ollama/ollama:latest` | OpenAI-compatible |
| **vLLM** | `vllm/vllm-openai:latest` | OpenAI-compatible |
| **SGLang** | `lmsysorg/sglang:latest` | OpenAI-compatible |
| **TGI** | `ghcr.io/huggingface/text-generation-inference:latest` | OpenAI-compatible |
| **LM Studio** | host-based | OpenAI-compatible |
| **Triton-LLM** | `nvcr.io/nvidia/tritonserver:<tag>-trtllm-python-py3` | OpenAI-compatible |

## Technology

```
React frontend  ←→  FastAPI backend  ←→  PostgreSQL + TimescaleDB
                          ↑
                    HTTPS long-poll
                          ↑
                    Worker (Python)
                          ↓
                    Platform container (vLLM / Ollama / …)
```

Workers never accept inbound connections — they always initiate. The backend is the single source of truth.

**Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, asyncpg, React 18, Vite, Tailwind CSS, TanStack Query, ECharts, Docker.

## Quick start

### 1. Start the backend + database + frontend

```bash
cp .env.example .env          # edit APP_TOKEN at minimum
docker compose up --build
```

Visit **http://localhost:5173** — the dashboard opens on the Runs page.

### 2. Run database migrations and seed

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/seed.py
```

This seeds 6 platforms, 10 models (Qwen2.5, Llama, Mistral, Phi, Gemma), and a default 20-prompt benchmark set.

### 3. Register a worker (on a GPU machine)

```bash
# copy docker-compose.worker.yml to the GPU host, then:
LMPC_API_URL=http://<your-backend-ip>:8080 docker compose -f docker-compose.worker.yml up --build
```

The worker registers itself and prints: `Registered. Awaiting admin approval. Re-run after approval.`

Approve it in the Workers page (`/workers`), then restart the worker — it begins polling for jobs.

### 4. Submit a benchmark run

1. Go to **New Run** (`/new`) and authenticate with your `APP_TOKEN`.
2. Pick platform → model → prompt set → load parameters → submit.
3. Watch the run appear in the **Runs** table. Click the row to open the detail panel.
4. Select two completed runs and click **Compare** to overlay metrics.

## Key commands

| Task | Command |
|------|---------|
| Start dev stack | `docker compose up` |
| Apply migrations | `docker compose exec backend alembic upgrade head` |
| Seed data | `docker compose exec backend python scripts/seed.py` |
| Generate frontend types | `cd frontend && pnpm gen:types` |
| Start worker (local) | `cd worker && uv run lmpc-worker` |
| Backend logs | `docker compose logs -f backend` |
| Worker logs | `docker compose -f docker-compose.worker.yml logs -f worker` |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_TOKEN` | `dev-token` | Admin token for protected endpoints and the UI |
| `DATABASE_URL` | — | PostgreSQL asyncpg URL |
| `JWT_SECRET` | `dev-only-change-me` | Reserved for future JWT auth |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed frontend origins |
| `LMPC_API_URL` | `http://localhost:8080` | Worker → backend URL |
| `LMPC_WORKER_NAME` | hostname | Worker display name |
| `LMPC_PLATFORMS` | `mock,ollama,vllm` | Comma-separated platforms the worker can run |
| `VITE_API_URL` | `http://localhost:8080` | Frontend → backend URL |

## Metrics collected

- **Latency**: TTFT, TPOT, E2E at p50/p90/p95/p99 + mean + stddev
- **Throughput**: output tokens/s, goodput RPS (SLO: TTFT p99 < 500 ms, TPOT p99 < 100 ms)
- **Resources**: GPU util %, GPU mem MB, GPU power W, CPU %, RAM MB (1 Hz samples)
- **Efficiency**: energy joules (trapezoidal), tokens per joule
- **Cold start**: container start ms, model load ms
