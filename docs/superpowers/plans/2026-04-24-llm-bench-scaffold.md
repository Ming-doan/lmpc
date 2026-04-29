# LLM Bench Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold a full-stack LLM benchmarking app where `docker compose up` boots all 5 services, an admin can submit a run, a stub worker walks all 8 state transitions with fake metrics, SSE dashboard shows live events, and the public leaderboard shows the completed run.

**Architecture:** FastAPI API is the single control plane (auth, CRUD, SSE, worker registration). Worker connects to API on startup to get `redis_url`, then processes jobs from `queue:benchmarks` via BRPOPLPUSH. Next.js web is a pure consumer talking to the API via HTTP/SSE.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2 async + Alembic + asyncpg + redis-py async + argon2-cffi + structlog + uv | Next.js 14 app router + TypeScript + TailwindCSS + shadcn/ui + TanStack Query + recharts + pnpm | Postgres 16 + Redis 7 | Docker Compose

---

## File Map

### Infrastructure
- `docker-compose.yml` — 5 services: postgres, redis, api, worker, web
- `docker-compose.gpu.yml` — overlay: nvidia runtime on worker
- `.env.example` — all required env vars

### API (`apps/api/`)
- `pyproject.toml` — deps: fastapi, uvicorn, sqlalchemy[asyncio], alembic, asyncpg, redis, pydantic, argon2-cffi, structlog, httpx, python-multipart
- `Dockerfile`
- `alembic.ini` + `migrations/env.py` + `migrations/versions/0001_initial.py`
- `src/config.py` — pydantic-settings Settings
- `src/main.py` — FastAPI app, lifespan, router mounts, structlog setup
- `src/db.py` — async engine, session factory, `get_db` dep
- `src/redis_client.py` — async Redis client, key constants, helper methods
- `src/auth/deps.py` — `get_current_admin` cookie session dep
- `src/auth/utils.py` — argon2 hash/verify, token generation
- `src/models/` — one file per table group: `admin.py`, `run.py`, `worker.py`, `cache.py`
- `src/schemas/` — `auth.py`, `runs.py`, `workers.py`
- `src/routers/auth.py` — POST /auth/login, POST /auth/logout
- `src/routers/runs.py` — GET /runs, POST /runs, GET /runs/{id}, POST /runs/{id}/cancel, GET /runs/{id}/events (SSE)
- `src/routers/models.py` — GET /models/search
- `src/routers/internal.py` — POST /internal/workers/register, POST /internal/workers/{id}/heartbeat
- `src/routers/health.py` — GET /health
- `src/services/queue.py` — LPUSH to queue:benchmarks
- `src/services/sse.py` — XRANGE replay + XREAD BLOCK tail + PUBSUB fanout
- `tests/test_health.py`

### Worker (`apps/worker/`)
- `pyproject.toml` — deps: httpx, redis, structlog, docker
- `Dockerfile`
- `src/main.py` — startup registration, BRPOPLPUSH loop
- `src/runner.py` — 8-state state machine, cancel polling
- `src/providers/base.py` — abstract provider interface
- `src/providers/stub.py` — sleeps + fake metrics; real providers are TODO stubs
- `src/providers/ollama.py`, `vllm.py`, `sglang.py`, `tgi.py` — TODO stubs
- `src/metrics/publisher.py` — XADD streams, HSET latest/running_avg, PUBLISH events
- `src/docker_mgr.py` — spawn/stop sibling containers via Docker SDK
- `src/persist.py` — bulk insert snapshots + update benchmark_runs.avg_* on finalize
- `tests/test_health.py`

### Web (`apps/web/`)
- `package.json` — next 14, typescript, tailwindcss, shadcn/ui, @tanstack/react-query, recharts, axios
- `Dockerfile`
- `next.config.js`
- `src/lib/api.ts` — axios instance, typed API helpers
- `src/app/layout.tsx` — root layout, QueryClientProvider, dark theme
- `src/app/(public)/page.tsx` — leaderboard page
- `src/app/(public)/runs/[id]/page.tsx` — public run detail
- `src/app/(admin)/login/page.tsx`
- `src/app/(admin)/new/page.tsx` — create-run form
- `src/app/(admin)/runs/[id]/page.tsx` — live dashboard
- `src/components/Leaderboard.tsx`
- `src/components/RunForm.tsx`
- `src/components/StepsTimeline.tsx`
- `src/components/MetricTiles.tsx`
- `src/components/MetricCharts.tsx`
- `src/hooks/useRunStream.ts` — EventSource → step + metric state

### Scripts
- `scripts/seed_admin.py` — insert admin from ADMIN_BOOTSTRAP_EMAIL + ADMIN_BOOTSTRAP_PASSWORD
- `scripts/dev_reset.sh` — drop DB, flush Redis, run migrations, seed

---

## Task 1: Infrastructure & Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `docker-compose.gpu.yml`
- Create: `.env.example`

- [ ] **Step 1: Write docker-compose.yml**

```yaml
# docker-compose.yml
version: "3.9"

networks:
  llmbench_net:
    driver: bridge

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-llmbench}
      POSTGRES_USER: ${POSTGRES_USER:-llmbench}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-llmbench}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-llmbench}"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - llmbench_net

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
    networks:
      - llmbench_net

  api:
    build: ./apps/api
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-llmbench}:${POSTGRES_PASSWORD:-llmbench}@postgres:5432/${POSTGRES_DB:-llmbench}
      REDIS_URL: redis://redis:6379
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
    networks:
      - llmbench_net

  worker:
    build: ./apps/worker
    env_file: .env
    environment:
      API_URL: http://api:8000
      DOCKER_HOST: unix:///var/run/docker.sock
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      api:
        condition: service_healthy
    networks:
      - llmbench_net

  web:
    build: ./apps/web
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    ports:
      - "3000:3000"
    depends_on:
      api:
        condition: service_healthy
    networks:
      - llmbench_net

volumes:
  pgdata:
```

- [ ] **Step 2: Write docker-compose.gpu.yml**

```yaml
# docker-compose.gpu.yml
services:
  worker:
    runtime: nvidia
    environment:
      NVIDIA_VISIBLE_DEVICES: all
```

- [ ] **Step 3: Write .env.example**

```bash
# .env.example
POSTGRES_DB=llmbench
POSTGRES_USER=llmbench
POSTGRES_PASSWORD=changeme

REDIS_URL=redis://redis:6379

JWT_SECRET=change-me-in-prod
SESSION_COOKIE_NAME=llmbench_session
SESSION_TTL_HOURS=24

ADMIN_BOOTSTRAP_EMAIL=admin@example.com
ADMIN_BOOTSTRAP_PASSWORD=changeme

HF_TOKEN=hf_...
SECRETS_ENCRYPTION_KEY=32-byte-base64-encoded-key

WORKER_SECRET=shared-worker-secret
WORKER_ID=worker-01
```

- [ ] **Step 4: Copy .env.example to .env**

```bash
cp .env.example .env
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml docker-compose.gpu.yml .env.example
git commit -m "feat: add docker-compose and env scaffold"
```

---

## Task 2: API — Project Setup & Config

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/Dockerfile`
- Create: `apps/api/src/config.py`

- [ ] **Step 1: Write pyproject.toml**

```toml
# apps/api/pyproject.toml
[project]
name = "llmbench-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "sqlalchemy[asyncio]>=2.0",
    "alembic>=1.13",
    "asyncpg>=0.29",
    "redis>=5.0",
    "pydantic-settings>=2.2",
    "argon2-cffi>=23.1",
    "structlog>=24.1",
    "httpx>=0.27",
    "python-multipart>=0.0.9",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I"]
```

- [ ] **Step 2: Write Dockerfile**

```dockerfile
# apps/api/Dockerfile
FROM python:3.12-slim
RUN pip install uv
WORKDIR /app
COPY pyproject.toml .
RUN uv pip install --system -e .
COPY . .
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 3: Write config.py**

```python
# apps/api/src/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    jwt_secret: str
    session_cookie_name: str = "llmbench_session"
    session_ttl_hours: int = 24
    worker_secret: str
    hf_token: str = ""
    log_format: str = "console"  # "json" in prod

settings = Settings()
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/
git commit -m "feat: api project setup and config"
```

---

## Task 3: API — Database Models & Migration

**Files:**
- Create: `apps/api/alembic.ini`
- Create: `apps/api/migrations/env.py`
- Create: `apps/api/migrations/versions/0001_initial.py`
- Create: `apps/api/src/db.py`
- Create: `apps/api/src/models/admin.py`
- Create: `apps/api/src/models/worker.py`
- Create: `apps/api/src/models/run.py`
- Create: `apps/api/src/models/cache.py`
- Create: `apps/api/src/models/__init__.py`

- [ ] **Step 1: Write db.py**

```python
# apps/api/src/db.py
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from src.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 2: Write models/admin.py**

```python
# apps/api/src/models/admin.py
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.db import Base

class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admins.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class Secret(Base):
    __tablename__ = "secrets"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    __table_args__ = ({"schema": None},)
```

- [ ] **Step 3: Write models/worker.py**

```python
# apps/api/src/models/worker.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from src.db import Base

class Worker(Base):
    __tablename__ = "workers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    secret_hash: Mapped[str] = mapped_column(String, nullable=False)
    gpu_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gpu_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vram_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cpu: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ram_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String, nullable=False, default="online")
```

- [ ] **Step 4: Write models/run.py**

```python
# apps/api/src/models/run.py
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.db import Base

class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    model_source: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    hardware: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    worker_id: Mapped[Optional[str]] = mapped_column(ForeignKey("workers.id"), nullable=True)
    inference_container_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    inference_endpoint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    avg_latency_ms: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    avg_throughput_tps: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    avg_ttft_ms: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    avg_tps: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class BenchmarkStep(Base):
    __tablename__ = "benchmark_steps"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("benchmark_runs.id"), nullable=False)
    step_name: Mapped[str] = mapped_column(String, nullable=False)
    step_status: Mapped[str] = mapped_column(String, nullable=False)
    progress_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class BenchmarkMetricSnapshot(Base):
    __tablename__ = "benchmark_metric_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("benchmark_runs.id"), nullable=False)
    t_offset_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    concurrency: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    throughput_tps: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    ttft_ms: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    tps: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    cpu_pct: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    gpu_pct: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    ram_mb: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    vram_mb: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)

class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("benchmark_runs.id"), nullable=False)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False)
    requests_total: Mapped[int] = mapped_column(Integer, nullable=False)
    requests_success: Mapped[int] = mapped_column(Integer, nullable=False)
    requests_failed: Mapped[int] = mapped_column(Integer, nullable=False)
    ttft_ms_p50: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    ttft_ms_p95: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    ttft_ms_p99: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    tpot_ms_p50: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    tpot_ms_p95: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    throughput_tps: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    per_req_tps_p50: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    input_tokens_avg: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    output_tokens_avg: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    duration_s: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    raw: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
```

- [ ] **Step 5: Write models/cache.py**

```python
# apps/api/src/models/cache.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, BigInteger, Numeric, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from src.db import Base

class ModelsCache(Base):
    __tablename__ = "models_cache"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    params_billions: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    quantization: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    context_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
```

- [ ] **Step 6: Write models/__init__.py**

```python
# apps/api/src/models/__init__.py
from .admin import Admin, Session, Secret
from .worker import Worker
from .run import BenchmarkRun, BenchmarkStep, BenchmarkMetricSnapshot, BenchmarkResult
from .cache import ModelsCache

__all__ = [
    "Admin", "Session", "Secret", "Worker",
    "BenchmarkRun", "BenchmarkStep", "BenchmarkMetricSnapshot", "BenchmarkResult",
    "ModelsCache",
]
```

- [ ] **Step 7: Initialize Alembic and write migration**

```bash
cd apps/api && uv run alembic init migrations
```

Replace `migrations/env.py` target_metadata section:

```python
# apps/api/migrations/env.py  (key additions at top and in run_migrations_online)
import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from alembic import context
from src.db import Base
from src.models import *  # noqa: F401, F403  — registers all models
from src.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

Create `migrations/versions/0001_initial.py`:

```python
# apps/api/migrations/versions/0001_initial.py
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table("admins",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table("sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_table("secrets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("encrypted_value", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "label"),
    )
    op.create_table("workers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("secret_hash", sa.String(), nullable=False),
        sa.Column("gpu_model", sa.String(), nullable=True),
        sa.Column("gpu_count", sa.Integer(), nullable=True),
        sa.Column("vram_mb", sa.Integer(), nullable=True),
        sa.Column("cpu", sa.String(), nullable=True),
        sa.Column("ram_mb", sa.Integer(), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="online"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table("benchmark_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_source", sa.String(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("hardware", postgresql.JSONB(), nullable=True),
        sa.Column("worker_id", sa.String(), nullable=True),
        sa.Column("inference_container_id", sa.String(), nullable=True),
        sa.Column("inference_endpoint", sa.String(), nullable=True),
        sa.Column("avg_latency_ms", sa.Numeric(), nullable=True),
        sa.Column("avg_throughput_tps", sa.Numeric(), nullable=True),
        sa.Column("avg_ttft_ms", sa.Numeric(), nullable=True),
        sa.Column("avg_tps", sa.Numeric(), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default="true", nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runs_leaderboard", "benchmark_runs", ["is_public", "completed_at"])
    op.create_index("ix_runs_status", "benchmark_runs", ["status"])
    op.create_index("ix_runs_provider_model", "benchmark_runs", ["provider", "model_id"])

    op.create_table("benchmark_steps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_name", sa.String(), nullable=False),
        sa.Column("step_status", sa.String(), nullable=False),
        sa.Column("progress_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["benchmark_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_steps_run_created", "benchmark_steps", ["run_id", "created_at"])

    op.create_table("benchmark_metric_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("t_offset_ms", sa.Integer(), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Numeric(), nullable=True),
        sa.Column("throughput_tps", sa.Numeric(), nullable=True),
        sa.Column("ttft_ms", sa.Numeric(), nullable=True),
        sa.Column("tps", sa.Numeric(), nullable=True),
        sa.Column("cpu_pct", sa.Numeric(), nullable=True),
        sa.Column("gpu_pct", sa.Numeric(), nullable=True),
        sa.Column("ram_mb", sa.Numeric(), nullable=True),
        sa.Column("vram_mb", sa.Numeric(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["benchmark_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table("benchmark_results",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("requests_total", sa.Integer(), nullable=False),
        sa.Column("requests_success", sa.Integer(), nullable=False),
        sa.Column("requests_failed", sa.Integer(), nullable=False),
        sa.Column("ttft_ms_p50", sa.Numeric(), nullable=True),
        sa.Column("ttft_ms_p95", sa.Numeric(), nullable=True),
        sa.Column("ttft_ms_p99", sa.Numeric(), nullable=True),
        sa.Column("tpot_ms_p50", sa.Numeric(), nullable=True),
        sa.Column("tpot_ms_p95", sa.Numeric(), nullable=True),
        sa.Column("throughput_tps", sa.Numeric(), nullable=True),
        sa.Column("per_req_tps_p50", sa.Numeric(), nullable=True),
        sa.Column("input_tokens_avg", sa.Numeric(), nullable=True),
        sa.Column("output_tokens_avg", sa.Numeric(), nullable=True),
        sa.Column("duration_s", sa.Numeric(), nullable=True),
        sa.Column("raw", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["benchmark_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "concurrency"),
    )
    op.create_table("models_cache",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("params_billions", sa.Numeric(), nullable=True),
        sa.Column("quantization", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("context_length", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "model_id"),
    )

def downgrade() -> None:
    for tbl in ["models_cache", "benchmark_results", "benchmark_metric_snapshots",
                "benchmark_steps", "benchmark_runs", "workers", "secrets", "sessions", "admins"]:
        op.drop_table(tbl)
```

- [ ] **Step 8: Commit**

```bash
git add apps/api/
git commit -m "feat: api db models and initial alembic migration"
```

---

## Task 4: API — Auth & Redis Client

**Files:**
- Create: `apps/api/src/auth/utils.py`
- Create: `apps/api/src/auth/deps.py`
- Create: `apps/api/src/auth/__init__.py`
- Create: `apps/api/src/redis_client.py`

- [ ] **Step 1: Write auth/utils.py**

```python
# apps/api/src/auth/utils.py
import hashlib, secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()

def hash_password(password: str) -> str:
    return _ph.hash(password)

def verify_password(password: str, hash: str) -> bool:
    try:
        return _ph.verify(hash, password)
    except VerifyMismatchError:
        return False

def generate_token() -> str:
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
```

- [ ] **Step 2: Write auth/deps.py**

```python
# apps/api/src/auth/deps.py
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from src.db import get_db
from src.models.admin import Admin, Session as AdminSession
from src.auth.utils import hash_token

async def get_current_admin(
    llmbench_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> Admin:
    if not llmbench_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    token_hash = hash_token(llmbench_session)
    result = await db.execute(
        select(AdminSession).where(
            AdminSession.token_hash == token_hash,
            AdminSession.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    result = await db.execute(select(Admin).where(Admin.id == session.admin_id))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return admin
```

- [ ] **Step 3: Write redis_client.py**

```python
# apps/api/src/redis_client.py
from redis.asyncio import Redis, from_url
from src.config import settings

_redis: Redis | None = None

async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(settings.redis_url, decode_responses=True)
    return _redis

async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None

# Key helpers
def key_run_state(run_id: str) -> str: return f"run:{run_id}:state"
def key_run_cancel(run_id: str) -> str: return f"run:{run_id}:cancel"
def key_run_lock(run_id: str) -> str: return f"run:{run_id}:lock"
def key_run_steps(run_id: str) -> str: return f"run:{run_id}:steps"
def key_run_metrics_series(run_id: str) -> str: return f"run:{run_id}:metrics:series"
def key_run_metrics_latest(run_id: str) -> str: return f"run:{run_id}:metrics:latest"
def key_run_metrics_running_avg(run_id: str) -> str: return f"run:{run_id}:metrics:running_avg"
def key_events_run(run_id: str) -> str: return f"events:run:{run_id}"
def key_queue_benchmarks() -> str: return "queue:benchmarks"
def key_queue_processing() -> str: return "queue:benchmarks:processing"
def key_queue_dead() -> str: return "queue:benchmarks:dead"
def key_worker_heartbeat(worker_id: str) -> str: return f"worker:{worker_id}:heartbeat"
def key_worker_info(worker_id: str) -> str: return f"worker:{worker_id}:info"
def key_worker_active_run(worker_id: str) -> str: return f"worker:{worker_id}:active_run"
```

- [ ] **Step 4: Write auth/__init__.py**

```python
# apps/api/src/auth/__init__.py
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/auth/ apps/api/src/redis_client.py
git commit -m "feat: api auth utils and redis client"
```

---

## Task 5: API — Routers & Services

**Files:**
- Create: `apps/api/src/schemas/auth.py`
- Create: `apps/api/src/schemas/runs.py`
- Create: `apps/api/src/schemas/workers.py`
- Create: `apps/api/src/schemas/__init__.py`
- Create: `apps/api/src/routers/health.py`
- Create: `apps/api/src/routers/auth.py`
- Create: `apps/api/src/routers/runs.py`
- Create: `apps/api/src/routers/models.py`
- Create: `apps/api/src/routers/internal.py`
- Create: `apps/api/src/services/queue.py`
- Create: `apps/api/src/services/sse.py`
- Create: `apps/api/src/main.py`

- [ ] **Step 1: Write schemas**

```python
# apps/api/src/schemas/auth.py
from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
```

```python
# apps/api/src/schemas/runs.py
import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel

class RunCreate(BaseModel):
    provider: str
    model_id: str
    model_source: str
    config: dict[str, Any] = {}

class RunSummary(BaseModel):
    id: uuid.UUID
    status: str
    provider: str
    model_id: str
    avg_latency_ms: Optional[float]
    avg_throughput_tps: Optional[float]
    avg_ttft_ms: Optional[float]
    avg_tps: Optional[float]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}

class RunDetail(RunSummary):
    config: dict
    hardware: Optional[dict]
    error_code: Optional[str]
    error_message: Optional[str]
    started_at: Optional[datetime]
```

```python
# apps/api/src/schemas/workers.py
from typing import Optional
from pydantic import BaseModel

class WorkerRegisterRequest(BaseModel):
    worker_id: str
    gpu_model: Optional[str] = None
    gpu_count: Optional[int] = None
    vram_mb: Optional[int] = None
    cpu: Optional[str] = None
    ram_mb: Optional[int] = None

class WorkerRegisterResponse(BaseModel):
    redis_url: str
    heartbeat_interval_s: int = 5
```

```python
# apps/api/src/schemas/__init__.py
```

- [ ] **Step 2: Write health router**

```python
# apps/api/src/routers/health.py
from fastapi import APIRouter
from sqlalchemy import text
from src.db import AsyncSessionLocal
from src.redis_client import get_redis

router = APIRouter()

@router.get("/health")
async def health():
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    try:
        r = await get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok" if db_ok and redis_ok else "degraded", "db": db_ok, "redis": redis_ok}
```

- [ ] **Step 3: Write auth router**

```python
# apps/api/src/routers/auth.py
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db import get_db
from src.models.admin import Admin, Session as AdminSession
from src.auth.utils import verify_password, generate_token, hash_token
from src.schemas.auth import LoginRequest
from src.config import settings

router = APIRouter(prefix="/auth")

@router.post("/login")
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Admin).where(Admin.email == body.email))
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = generate_token()
    session = AdminSession(
        admin_id=admin.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    await db.commit()
    response.set_cookie(settings.session_cookie_name, token, httponly=True, samesite="lax")
    return {"ok": True}

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(settings.session_cookie_name)
    return {"ok": True}
```

- [ ] **Step 4: Write queue service**

```python
# apps/api/src/services/queue.py
from src.redis_client import get_redis, key_queue_benchmarks

async def enqueue_run(run_id: str) -> None:
    r = await get_redis()
    await r.lpush(key_queue_benchmarks(), run_id)
```

- [ ] **Step 5: Write SSE service**

```python
# apps/api/src/services/sse.py
import asyncio, json
from collections.abc import AsyncGenerator
from src.redis_client import get_redis, key_run_steps, key_run_metrics_series, key_events_run

async def run_event_stream(run_id: str) -> AsyncGenerator[str, None]:
    r = await get_redis()
    # Replay historical steps
    steps = await r.xrange(key_run_steps(run_id), "-", "+")
    for _, data in steps:
        yield f"event: step\ndata: {json.dumps(data)}\n\n"
    # Replay historical metrics
    metrics = await r.xrange(key_run_metrics_series(run_id), "-", "+")
    for _, data in metrics:
        yield f"event: metric\ndata: {json.dumps(data)}\n\n"

    # Tail new events via pubsub
    pubsub = r.pubsub()
    await pubsub.subscribe(key_events_run(run_id))
    last_step_id = "$"
    last_metric_id = "$"
    try:
        while True:
            # Poll streams
            step_entries = await r.xread({key_run_steps(run_id): last_step_id}, block=100, count=10)
            for _, entries in (step_entries or []):
                for entry_id, data in entries:
                    last_step_id = entry_id
                    yield f"event: step\ndata: {json.dumps(data)}\n\n"
            metric_entries = await r.xread({key_run_metrics_series(run_id): last_metric_id}, block=100, count=10)
            for _, entries in (metric_entries or []):
                for entry_id, data in entries:
                    last_metric_id = entry_id
                    yield f"event: metric\ndata: {json.dumps(data)}\n\n"
            # Forward pubsub
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.01)
            if msg and msg["type"] == "message":
                payload = json.loads(msg["data"])
                evt_type = payload.get("type", "status")
                yield f"event: {evt_type}\ndata: {json.dumps(payload)}\n\n"
                if payload.get("status") in ("completed", "failed", "cancelled"):
                    break
            await asyncio.sleep(0.05)
    finally:
        await pubsub.unsubscribe(key_events_run(run_id))
```

- [ ] **Step 6: Write runs router**

```python
# apps/api/src/routers/runs.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from src.db import get_db
from src.models.run import BenchmarkRun
from src.schemas.runs import RunCreate, RunSummary, RunDetail
from src.auth.deps import get_current_admin
from src.services.queue import enqueue_run
from src.services.sse import run_event_stream
from src.redis_client import get_redis, key_run_cancel

router = APIRouter(prefix="/runs")

@router.get("", response_model=list[RunSummary])
async def list_runs(cursor: str | None = None, limit: int = 20, db: AsyncSession = Depends(get_db)):
    q = select(BenchmarkRun).where(
        BenchmarkRun.is_public == True,
        BenchmarkRun.status == "completed",
    ).order_by(desc(BenchmarkRun.completed_at)).limit(limit)
    if cursor:
        q = q.where(BenchmarkRun.completed_at < cursor)
    result = await db.execute(q)
    return result.scalars().all()

@router.post("", status_code=201)
async def create_run(body: RunCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_admin)):
    run = BenchmarkRun(
        provider=body.provider,
        model_id=body.model_id,
        model_source=body.model_source,
        config=body.config,
        status="queued",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    await enqueue_run(str(run.id))
    return {"run_id": str(run.id)}

@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BenchmarkRun).where(BenchmarkRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404)
    return run

@router.post("/{run_id}/cancel")
async def cancel_run(run_id: uuid.UUID, _=Depends(get_current_admin)):
    r = await get_redis()
    await r.set(key_run_cancel(str(run_id)), "1")
    return {"ok": True}

@router.get("/{run_id}/events")
async def run_events(run_id: uuid.UUID):
    return StreamingResponse(
        run_event_stream(str(run_id)),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
```

- [ ] **Step 7: Write models router**

```python
# apps/api/src/routers/models.py
from fastapi import APIRouter, Query
import httpx
from src.config import settings

router = APIRouter(prefix="/models")

@router.get("/search")
async def search_models(source: str = Query("hf"), q: str = Query("")):
    if source == "hf":
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://huggingface.co/api/models",
                params={"search": q, "limit": 20},
                headers={"Authorization": f"Bearer {settings.hf_token}"} if settings.hf_token else {},
            )
        return r.json()
    elif source == "ollama":
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:11434/api/tags")
        return r.json()
    return {"models": []}
```

- [ ] **Step 8: Write internal router**

```python
# apps/api/src/routers/internal.py
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db import get_db
from src.models.worker import Worker
from src.auth.utils import hash_password
from src.schemas.workers import WorkerRegisterRequest, WorkerRegisterResponse
from src.redis_client import get_redis, key_worker_heartbeat, key_worker_info
from src.config import settings

router = APIRouter(prefix="/internal")

async def verify_worker_secret(x_worker_secret: str = Header(...)):
    if x_worker_secret != settings.worker_secret:
        raise HTTPException(status_code=403, detail="Invalid worker secret")

@router.post("/workers/register", response_model=WorkerRegisterResponse)
async def register_worker(
    body: WorkerRegisterRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_worker_secret),
):
    result = await db.execute(select(Worker).where(Worker.id == body.worker_id))
    worker = result.scalar_one_or_none()
    if worker:
        worker.gpu_model = body.gpu_model
        worker.vram_mb = body.vram_mb
        worker.cpu = body.cpu
        worker.ram_mb = body.ram_mb
        worker.status = "online"
    else:
        worker = Worker(
            id=body.worker_id,
            secret_hash=hash_password(settings.worker_secret),
            gpu_model=body.gpu_model,
            gpu_count=body.gpu_count,
            vram_mb=body.vram_mb,
            cpu=body.cpu,
            ram_mb=body.ram_mb,
        )
        db.add(worker)
    await db.commit()
    r = await get_redis()
    await r.hset(key_worker_info(body.worker_id), mapping={
        "gpu_model": body.gpu_model or "",
        "vram_mb": body.vram_mb or 0,
        "cpu": body.cpu or "",
        "ram_mb": body.ram_mb or 0,
    })
    return WorkerRegisterResponse(redis_url=settings.redis_url)

@router.post("/workers/{worker_id}/heartbeat")
async def worker_heartbeat(
    worker_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_worker_secret),
):
    r = await get_redis()
    await r.setex(key_worker_heartbeat(worker_id), 15, "1")
    result = await db.execute(select(Worker).where(Worker.id == worker_id))
    worker = result.scalar_one_or_none()
    if worker:
        worker.last_heartbeat = datetime.now(timezone.utc)
        await db.commit()
    return {"ok": True}
```

- [ ] **Step 9: Write main.py**

```python
# apps/api/src/main.py
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.redis_client import get_redis, close_redis
from src.routers import health, auth, runs, models, internal
from src.config import settings

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer() if settings.log_format == "console" else structlog.processors.JSONRenderer(),
    ]
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_redis()
    yield
    await close_redis()

app = FastAPI(title="LLM Bench API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(runs.router)
app.include_router(models.router)
app.include_router(internal.router)
```

- [ ] **Step 10: Commit**

```bash
git add apps/api/src/
git commit -m "feat: api routers, schemas, services"
```

---

## Task 6: API — Health Test

**Files:**
- Create: `apps/api/tests/__init__.py`
- Create: `apps/api/tests/test_health.py`

- [ ] **Step 1: Write test**

```python
# apps/api/tests/test_health.py
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

@pytest.mark.anyio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ("ok", "degraded")
```

Add to `pyproject.toml`:
```toml
[project.optional-dependencies]
test = ["pytest", "pytest-anyio", "httpx"]
```

- [ ] **Step 2: Run test (needs running DB + Redis, or mock)**

```bash
cd apps/api && uv run pytest tests/test_health.py -v
```

Expected: PASS (degraded is acceptable without services)

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/
git commit -m "test: api health endpoint"
```

---

## Task 7: Worker — Project Setup & Main Loop

**Files:**
- Create: `apps/worker/pyproject.toml`
- Create: `apps/worker/Dockerfile`
- Create: `apps/worker/src/main.py`
- Create: `apps/worker/src/config.py`

- [ ] **Step 1: Write pyproject.toml**

```toml
# apps/worker/pyproject.toml
[project]
name = "llmbench-worker"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "redis>=5.0",
    "structlog>=24.1",
    "docker>=7.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]
```

- [ ] **Step 2: Write Dockerfile**

```dockerfile
# apps/worker/Dockerfile
FROM python:3.12-slim
RUN pip install uv
WORKDIR /app
COPY pyproject.toml .
RUN uv pip install --system -e .
COPY . .
CMD ["python", "-m", "src.main"]
```

- [ ] **Step 3: Write config.py**

```python
# apps/worker/src/config.py
import os

API_URL = os.environ["API_URL"]
WORKER_SECRET = os.environ["WORKER_SECRET"]
WORKER_ID = os.environ.get("WORKER_ID", "worker-01")
DOCKER_HOST = os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock")
```

- [ ] **Step 4: Write main.py**

```python
# apps/worker/src/main.py
import asyncio, socket, structlog
import httpx
import redis.asyncio as aioredis
from src.config import API_URL, WORKER_SECRET, WORKER_ID

log = structlog.get_logger()

async def register() -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{API_URL}/internal/workers/register",
            json={"worker_id": WORKER_ID, "cpu": socket.gethostname()},
            headers={"x-worker-secret": WORKER_SECRET},
        )
        r.raise_for_status()
        data = r.json()
        return data["redis_url"]

async def heartbeat_loop():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await client.post(
                    f"{API_URL}/internal/workers/{WORKER_ID}/heartbeat",
                    headers={"x-worker-secret": WORKER_SECRET},
                )
            except Exception as e:
                log.warning("heartbeat_failed", error=str(e))
            await asyncio.sleep(5)

async def main():
    log.info("worker_starting", worker_id=WORKER_ID)
    redis_url = await register()
    log.info("registered", redis_url=redis_url)
    r = aioredis.from_url(redis_url, decode_responses=True)

    asyncio.create_task(heartbeat_loop())

    from src.runner import run_benchmark
    while True:
        run_id = await r.brpoplpush("queue:benchmarks", "queue:benchmarks:processing", timeout=0)
        if run_id:
            log.info("run_picked", run_id=run_id)
            try:
                await run_benchmark(run_id, r, API_URL, WORKER_SECRET, WORKER_ID)
            except Exception as e:
                log.error("run_failed", run_id=run_id, error=str(e))
            finally:
                await r.lrem("queue:benchmarks:processing", 1, run_id)

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Commit**

```bash
git add apps/worker/
git commit -m "feat: worker setup and main loop"
```

---

## Task 8: Worker — Metrics Publisher & State Machine

**Files:**
- Create: `apps/worker/src/metrics/__init__.py`
- Create: `apps/worker/src/metrics/publisher.py`
- Create: `apps/worker/src/providers/__init__.py`
- Create: `apps/worker/src/providers/base.py`
- Create: `apps/worker/src/providers/stub.py`
- Create: `apps/worker/src/providers/ollama.py`
- Create: `apps/worker/src/providers/vllm.py`
- Create: `apps/worker/src/providers/sglang.py`
- Create: `apps/worker/src/providers/tgi.py`
- Create: `apps/worker/src/runner.py`

- [ ] **Step 1: Write metrics/publisher.py**

```python
# apps/worker/src/metrics/publisher.py
import json
import redis.asyncio as aioredis

class MetricsPublisher:
    def __init__(self, r: aioredis.Redis, run_id: str):
        self.r = r
        self.run_id = run_id
        self._steps_key = f"run:{run_id}:steps"
        self._metrics_key = f"run:{run_id}:metrics:series"
        self._latest_key = f"run:{run_id}:metrics:latest"
        self._avg_key = f"run:{run_id}:metrics:running_avg"
        self._events_key = f"events:run:{run_id}"

    async def emit_step(self, step_name: str, step_status: str, progress_pct: float | None = None,
                        message: str | None = None, details: dict | None = None):
        entry = {"step_name": step_name, "step_status": step_status}
        if progress_pct is not None:
            entry["progress_pct"] = str(progress_pct)
        if message:
            entry["message"] = message
        if details:
            entry["details"] = json.dumps(details)
        await self.r.xadd(self._steps_key, entry)
        await self.r.publish(self._events_key, json.dumps({"type": "step", "payload": entry}))

    async def emit_metric(self, t_offset_ms: int, concurrency: int, latency_ms: float,
                          throughput_tps: float, ttft_ms: float, tps: float,
                          cpu_pct: float = 0, gpu_pct: float = 0, ram_mb: float = 0, vram_mb: float = 0):
        entry = {
            "t_offset_ms": str(t_offset_ms), "concurrency": str(concurrency),
            "latency_ms": str(latency_ms), "throughput_tps": str(throughput_tps),
            "ttft_ms": str(ttft_ms), "tps": str(tps),
            "cpu_pct": str(cpu_pct), "gpu_pct": str(gpu_pct),
            "ram_mb": str(ram_mb), "vram_mb": str(vram_mb),
        }
        await self.r.xadd(self._metrics_key, entry)
        await self.r.hset(self._latest_key, mapping=entry)
        await self.r.publish(self._events_key, json.dumps({"type": "metric", "payload": entry}))

    async def emit_status(self, status: str):
        await self.r.publish(self._events_key, json.dumps({"type": "status", "status": status}))
```

- [ ] **Step 2: Write providers/base.py**

```python
# apps/worker/src/providers/base.py
from abc import ABC, abstractmethod

class BaseProvider(ABC):
    """
    Abstract inference provider. Implement one class per backend (ollama, vllm, sglang, tgi).
    All methods are async. The runner calls them in order: start → wait_ready → pull → evaluate → stop.
    """
    @abstractmethod
    async def start(self) -> str:
        """Start the inference container. Returns endpoint URL (e.g. http://host:8000/v1)."""

    @abstractmethod
    async def wait_ready(self) -> None:
        """Block until the server is accepting requests. Raise on timeout."""

    @abstractmethod
    async def pull(self, progress_cb) -> None:
        """Pull/load the model. Call progress_cb(pct: float) every 300ms."""

    @abstractmethod
    async def send_requests(self, concurrency: int, duration_s: float, progress_cb) -> list[dict]:
        """
        Run requests at given concurrency for duration_s seconds.
        Returns list of {latency_ms, ttft_ms, tps, tokens_in, tokens_out}.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop and remove the inference container."""
```

- [ ] **Step 3: Write providers/stub.py**

```python
# apps/worker/src/providers/stub.py
import asyncio, random
from src.providers.base import BaseProvider

class StubProvider(BaseProvider):
    async def start(self) -> str:
        await asyncio.sleep(2)
        return "http://stub:8000/v1"

    async def wait_ready(self) -> None:
        pass

    async def pull(self, progress_cb) -> None:
        for i in range(10):
            await asyncio.sleep(0.3)
            await progress_cb(float(i + 1) * 10)

    async def send_requests(self, concurrency: int, duration_s: float, progress_cb) -> list[dict]:
        results = []
        elapsed = 0.0
        while elapsed < duration_s:
            await asyncio.sleep(1)
            elapsed += 1
            sample = {
                "latency_ms": random.uniform(50 * concurrency, 200 * concurrency),
                "ttft_ms": random.uniform(20, 80),
                "tps": random.uniform(30, 120),
                "tokens_in": 128,
                "tokens_out": 256,
            }
            results.append(sample)
            await progress_cb(sample)
        return results

    async def stop(self) -> None:
        await asyncio.sleep(0.5)
```

- [ ] **Step 4: Write TODO provider stubs**

```python
# apps/worker/src/providers/ollama.py
from src.providers.base import BaseProvider

class OllamaProvider(BaseProvider):
    """
    Ollama provider. Start ollama container, pull model via POST /api/pull,
    send requests via POST /api/generate with stream:false.
    API ref: https://github.com/ollama/ollama/blob/main/docs/api.md
    """
    async def start(self) -> str: raise NotImplementedError
    async def wait_ready(self) -> None: raise NotImplementedError
    async def pull(self, progress_cb) -> None: raise NotImplementedError
    async def send_requests(self, concurrency, duration_s, progress_cb): raise NotImplementedError
    async def stop(self) -> None: raise NotImplementedError
```

```python
# apps/worker/src/providers/vllm.py
from src.providers.base import BaseProvider

class VllmProvider(BaseProvider):
    """
    vLLM provider. Start vllm/vllm-openai container, wait for GET /health,
    send requests via OpenAI-compatible POST /v1/completions.
    API ref: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html
    """
    async def start(self) -> str: raise NotImplementedError
    async def wait_ready(self) -> None: raise NotImplementedError
    async def pull(self, progress_cb) -> None: raise NotImplementedError
    async def send_requests(self, concurrency, duration_s, progress_cb): raise NotImplementedError
    async def stop(self) -> None: raise NotImplementedError
```

```python
# apps/worker/src/providers/sglang.py
from src.providers.base import BaseProvider

class SGlangProvider(BaseProvider):
    """
    SGLang provider. Start lmsysorg/sglang container, wait for GET /health_generate,
    send requests via POST /generate (RadixAttention backend).
    API ref: https://sgl-project.github.io/references/sampling_params.html
    """
    async def start(self) -> str: raise NotImplementedError
    async def wait_ready(self) -> None: raise NotImplementedError
    async def pull(self, progress_cb) -> None: raise NotImplementedError
    async def send_requests(self, concurrency, duration_s, progress_cb): raise NotImplementedError
    async def stop(self) -> None: raise NotImplementedError
```

```python
# apps/worker/src/providers/tgi.py
from src.providers.base import BaseProvider

class TGIProvider(BaseProvider):
    """
    Text Generation Inference provider. Start ghcr.io/huggingface/text-generation-inference,
    wait for GET /health, send requests via POST /generate.
    API ref: https://huggingface.github.io/text-generation-inference/
    """
    async def start(self) -> str: raise NotImplementedError
    async def wait_ready(self) -> None: raise NotImplementedError
    async def pull(self, progress_cb) -> None: raise NotImplementedError
    async def send_requests(self, concurrency, duration_s, progress_cb): raise NotImplementedError
    async def stop(self) -> None: raise NotImplementedError
```

- [ ] **Step 5: Write runner.py**

```python
# apps/worker/src/runner.py
import asyncio, time, statistics, structlog
import httpx
import redis.asyncio as aioredis
from src.metrics.publisher import MetricsPublisher
from src.providers.stub import StubProvider

log = structlog.get_logger()

PROVIDER_MAP = {"stub": StubProvider}

async def update_run_status(api_url: str, secret: str, run_id: str, status: str, **kwargs):
    # Directly update via internal API call — keeps worker stateless of DB
    # In this scaffold we just log; full implementation patches benchmark_runs via a dedicated endpoint
    log.info("run_status_update", run_id=run_id, status=status, **kwargs)

async def run_benchmark(run_id: str, r: aioredis.Redis, api_url: str, secret: str, worker_id: str):
    pub = MetricsPublisher(r, run_id)
    start_time = time.time()

    def t_offset() -> int:
        return int((time.time() - start_time) * 1000)

    # Check cancel helper
    async def check_cancel() -> bool:
        return await r.exists(f"run:{run_id}:cancel") == 1

    provider = StubProvider()  # TODO: read provider from run config via API

    try:
        # picked
        await pub.emit_step("worker_pick", "completed", message=f"Picked by {worker_id}")

        if await check_cancel():
            await pub.emit_step("cleanup", "started")
            await provider.stop()
            await pub.emit_step("cleanup", "completed")
            await pub.emit_status("cancelled")
            return

        # starting_container
        await pub.emit_step("container_start", "started")
        endpoint = await provider.start()
        await pub.emit_step("container_start", "completed", details={"endpoint": endpoint})

        if await check_cancel():
            await provider.stop()
            await pub.emit_status("cancelled")
            return

        # pulling_model
        await pub.emit_step("pull_model", "started")
        async def pull_progress(pct: float):
            await pub.emit_step("pull_model", "progress", progress_pct=pct)
        await provider.pull(pull_progress)
        await pub.emit_step("pull_model", "completed")

        if await check_cancel():
            await provider.stop()
            await pub.emit_status("cancelled")
            return

        # warming
        await pub.emit_step("warmup", "started")
        await provider.wait_ready()
        await pub.emit_step("warmup", "completed")

        # evaluating — concurrency sweep
        concurrency_levels = [1, 10, 50, 100]
        all_results = {}
        for concurrency in concurrency_levels:
            if await check_cancel():
                break
            await pub.emit_step("evaluating", "started", details={"concurrency": concurrency})
            samples = []
            async def metric_progress(sample: dict):
                samples.append(sample)
                await pub.emit_metric(
                    t_offset(), concurrency,
                    latency_ms=sample["latency_ms"], throughput_tps=sample["tps"] * concurrency,
                    ttft_ms=sample["ttft_ms"], tps=sample["tps"],
                )
            results = await provider.send_requests(concurrency, duration_s=3, progress_cb=metric_progress)
            all_results[concurrency] = results
            await pub.emit_step("evaluating", "completed", details={"concurrency": concurrency})

        # finalizing
        await pub.emit_step("finalizing", "started")
        await asyncio.sleep(1)
        # Compute summary metrics
        all_samples = [s for samples in all_results.values() for s in samples]
        if all_samples:
            avg_latency = statistics.mean(s["latency_ms"] for s in all_samples)
            avg_tps = statistics.mean(s["tps"] for s in all_samples)
            avg_ttft = statistics.mean(s["ttft_ms"] for s in all_samples)
        await pub.emit_step("finalizing", "completed")

        # cleanup
        await pub.emit_step("cleanup", "started")
        await provider.stop()
        await pub.emit_step("cleanup", "completed")
        await pub.emit_status("completed")

    except Exception as e:
        log.error("run_error", run_id=run_id, error=str(e))
        await pub.emit_step("cleanup", "failed", message=str(e))
        await pub.emit_status("failed")
        try:
            await provider.stop()
        except Exception:
            pass
```

- [ ] **Step 6: Commit**

```bash
git add apps/worker/src/
git commit -m "feat: worker state machine, stub provider, metrics publisher"
```

---

## Task 9: Scripts

**Files:**
- Create: `scripts/seed_admin.py`
- Create: `scripts/dev_reset.sh`

- [ ] **Step 1: Write seed_admin.py**

```python
# scripts/seed_admin.py
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

async def main():
    email = os.environ["ADMIN_BOOTSTRAP_EMAIL"]
    password = os.environ["ADMIN_BOOTSTRAP_PASSWORD"]
    db_url = os.environ["DATABASE_URL"]

    import sys; sys.path.insert(0, "apps/api")
    from src.models.admin import Admin
    from src.auth.utils import hash_password
    from src.db import Base

    engine = create_async_engine(db_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        result = await db.execute(select(Admin).where(Admin.email == email))
        if result.scalar_one_or_none():
            print(f"Admin {email} already exists")
            return
        admin = Admin(email=email, password_hash=hash_password(password))
        db.add(admin)
        await db.commit()
        print(f"Admin {email} created")

asyncio.run(main())
```

- [ ] **Step 2: Write dev_reset.sh**

```bash
#!/usr/bin/env bash
# scripts/dev_reset.sh — drop DB, flush Redis, run migrations, seed admin
set -euo pipefail

echo "==> Dropping and recreating database..."
docker compose exec -T postgres psql -U "${POSTGRES_USER:-llmbench}" -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-llmbench};"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-llmbench}" -c "CREATE DATABASE ${POSTGRES_DB:-llmbench};"

echo "==> Flushing Redis..."
docker compose exec -T redis redis-cli FLUSHALL

echo "==> Running migrations..."
docker compose exec -T api uv run alembic upgrade head

echo "==> Seeding admin..."
docker compose exec -T api uv run python /app/scripts/seed_admin.py

echo "Done."
```

```bash
chmod +x scripts/dev_reset.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/
git commit -m "feat: seed_admin and dev_reset scripts"
```

---

## Task 10: Frontend — Project Setup

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/next.config.js`
- Create: `apps/web/Dockerfile`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/tailwind.config.ts`
- Create: `apps/web/postcss.config.js`
- Create: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/app/layout.tsx`
- Create: `apps/web/src/app/providers.tsx`

- [ ] **Step 1: Write package.json**

```json
{
  "name": "llmbench-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "14.2.3",
    "react": "^18",
    "react-dom": "^18",
    "@tanstack/react-query": "^5.28",
    "axios": "^1.6",
    "recharts": "^2.12",
    "clsx": "^2.1",
    "tailwind-merge": "^2.3",
    "lucide-react": "^0.368"
  },
  "devDependencies": {
    "typescript": "^5",
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "tailwindcss": "^3.4",
    "postcss": "^8",
    "autoprefixer": "^10",
    "eslint": "^8",
    "eslint-config-next": "14.2.3",
    "prettier": "^3"
  }
}
```

- [ ] **Step 2: Write next.config.js**

```js
// apps/web/next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};
module.exports = nextConfig;
```

- [ ] **Step 3: Write Dockerfile**

```dockerfile
# apps/web/Dockerfile
FROM node:20-alpine AS deps
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

FROM node:20-alpine AS builder
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
CMD ["node", "server.js"]
EXPOSE 3000
```

- [ ] **Step 4: Write tailwind.config.ts + postcss.config.js**

```ts
// apps/web/tailwind.config.ts
import type { Config } from "tailwindcss";
const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
export default config;
```

```js
// apps/web/postcss.config.js
module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

- [ ] **Step 5: Write lib/api.ts**

```ts
// apps/web/src/lib/api.ts
import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  withCredentials: true,
});

export interface RunSummary {
  id: string;
  status: string;
  provider: string;
  model_id: string;
  avg_latency_ms: number | null;
  avg_throughput_tps: number | null;
  avg_ttft_ms: number | null;
  avg_tps: number | null;
  completed_at: string | null;
  created_at: string;
}

export interface RunDetail extends RunSummary {
  config: Record<string, unknown>;
  hardware: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
}

export const getRuns = (cursor?: string) =>
  api.get<RunSummary[]>("/runs", { params: { cursor, limit: 20 } }).then((r) => r.data);

export const getRun = (id: string) =>
  api.get<RunDetail>(`/runs/${id}`).then((r) => r.data);

export const createRun = (body: { provider: string; model_id: string; model_source: string; config: Record<string, unknown> }) =>
  api.post<{ run_id: string }>("/runs", body).then((r) => r.data);

export const login = (email: string, password: string) =>
  api.post("/auth/login", { email, password }).then((r) => r.data);

export const logout = () => api.post("/auth/logout");

export const cancelRun = (id: string) => api.post(`/runs/${id}/cancel`);

export default api;
```

- [ ] **Step 6: Write app/providers.tsx and layout.tsx**

```tsx
// apps/web/src/app/providers.tsx
"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
```

```tsx
// apps/web/src/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = { title: "LLM Bench", description: "LLM speed benchmarking" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

Create `apps/web/src/app/globals.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 7: Commit**

```bash
cd apps/web && pnpm install
git add apps/web/
git commit -m "feat: web project setup, api client, layout"
```

---

## Task 11: Frontend — Pages & Components

**Files:**
- Create: `apps/web/src/hooks/useRunStream.ts`
- Create: `apps/web/src/components/Leaderboard.tsx`
- Create: `apps/web/src/components/RunForm.tsx`
- Create: `apps/web/src/components/StepsTimeline.tsx`
- Create: `apps/web/src/components/MetricTiles.tsx`
- Create: `apps/web/src/components/MetricCharts.tsx`
- Create: `apps/web/src/app/(public)/page.tsx`
- Create: `apps/web/src/app/(public)/runs/[id]/page.tsx`
- Create: `apps/web/src/app/(admin)/login/page.tsx`
- Create: `apps/web/src/app/(admin)/new/page.tsx`
- Create: `apps/web/src/app/(admin)/runs/[id]/page.tsx`

- [ ] **Step 1: Write useRunStream.ts**

```ts
// apps/web/src/hooks/useRunStream.ts
"use client";
import { useEffect, useRef, useState } from "react";

export interface StepEvent {
  step_name: string;
  step_status: string;
  progress_pct?: string;
  message?: string;
}

export interface MetricEvent {
  t_offset_ms: string;
  concurrency: string;
  latency_ms: string;
  throughput_tps: string;
  ttft_ms: string;
  tps: string;
}

export function useRunStream(runId: string) {
  const [steps, setSteps] = useState<StepEvent[]>([]);
  const [metrics, setMetrics] = useState<MetricEvent[]>([]);
  const [status, setStatus] = useState<string>("connecting");
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const es = new EventSource(`${apiUrl}/runs/${runId}/events`);
    esRef.current = es;

    es.addEventListener("step", (e) => {
      setSteps((prev) => [...prev, JSON.parse(e.data)]);
    });
    es.addEventListener("metric", (e) => {
      setMetrics((prev) => [...prev.slice(-500), JSON.parse(e.data)]);
    });
    es.addEventListener("status", (e) => {
      const payload = JSON.parse(e.data);
      setStatus(payload.status || "unknown");
    });
    es.onerror = () => setStatus("error");

    return () => es.close();
  }, [runId]);

  return { steps, metrics, status };
}
```

- [ ] **Step 2: Write StepsTimeline.tsx**

```tsx
// apps/web/src/components/StepsTimeline.tsx
import type { StepEvent } from "@/hooks/useRunStream";

export default function StepsTimeline({ steps }: { steps: StepEvent[] }) {
  return (
    <div className="space-y-2">
      {steps.map((s, i) => (
        <div key={i} className="flex items-center gap-3 text-sm">
          <span className={`w-2 h-2 rounded-full ${s.step_status === "completed" ? "bg-green-400" : s.step_status === "failed" ? "bg-red-400" : "bg-yellow-400"}`} />
          <span className="font-mono text-gray-300">{s.step_name}</span>
          <span className="text-gray-500">{s.step_status}</span>
          {s.progress_pct && <span className="text-gray-400">{s.progress_pct}%</span>}
          {s.message && <span className="text-gray-500 truncate">{s.message}</span>}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Write MetricTiles.tsx**

```tsx
// apps/web/src/components/MetricTiles.tsx
import type { MetricEvent } from "@/hooks/useRunStream";

export default function MetricTiles({ latest }: { latest: MetricEvent | null }) {
  if (!latest) return <div className="text-gray-500">Waiting for metrics...</div>;
  const tiles = [
    { label: "Latency", value: `${parseFloat(latest.latency_ms).toFixed(0)} ms` },
    { label: "Throughput", value: `${parseFloat(latest.throughput_tps).toFixed(1)} tok/s` },
    { label: "TTFT", value: `${parseFloat(latest.ttft_ms).toFixed(0)} ms` },
    { label: "TPS", value: `${parseFloat(latest.tps).toFixed(1)}` },
    { label: "Concurrency", value: latest.concurrency },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {tiles.map(({ label, value }) => (
        <div key={label} className="bg-gray-800 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-white">{value}</div>
          <div className="text-xs text-gray-400 mt-1">{label}</div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Write MetricCharts.tsx**

```tsx
// apps/web/src/components/MetricCharts.tsx
"use client";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import type { MetricEvent } from "@/hooks/useRunStream";

export default function MetricCharts({ metrics }: { metrics: MetricEvent[] }) {
  const data = metrics.map((m) => ({
    t: Math.round(parseFloat(m.t_offset_ms) / 1000),
    latency: parseFloat(m.latency_ms).toFixed(1),
    tps: parseFloat(m.tps).toFixed(1),
    ttft: parseFloat(m.ttft_ms).toFixed(1),
  }));

  return (
    <div className="space-y-6">
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <XAxis dataKey="t" label={{ value: "s", position: "insideRight" }} />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="latency" stroke="#60a5fa" dot={false} name="Latency ms" />
        </LineChart>
      </ResponsiveContainer>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <XAxis dataKey="t" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="tps" stroke="#34d399" dot={false} name="TPS" />
          <Line type="monotone" dataKey="ttft" stroke="#f59e0b" dot={false} name="TTFT ms" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 5: Write Leaderboard.tsx**

```tsx
// apps/web/src/components/Leaderboard.tsx
"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { getRuns } from "@/lib/api";

export default function Leaderboard() {
  const { data: runs, isLoading } = useQuery({ queryKey: ["runs"], queryFn: () => getRuns() });

  if (isLoading) return <div className="text-gray-500">Loading...</div>;

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-gray-700 text-gray-400">
          <th className="text-left py-2">Model</th>
          <th className="text-left py-2">Provider</th>
          <th className="text-right py-2">Latency ms</th>
          <th className="text-right py-2">Tok/s</th>
          <th className="text-right py-2">TTFT ms</th>
          <th className="text-right py-2">Completed</th>
        </tr>
      </thead>
      <tbody>
        {(runs || []).map((run) => (
          <tr key={run.id} className="border-b border-gray-800 hover:bg-gray-800/50">
            <td className="py-2">
              <Link href={`/runs/${run.id}`} className="text-blue-400 hover:underline">
                {run.model_id}
              </Link>
            </td>
            <td className="py-2 text-gray-400">{run.provider}</td>
            <td className="py-2 text-right">{run.avg_latency_ms?.toFixed(0) ?? "—"}</td>
            <td className="py-2 text-right">{run.avg_throughput_tps?.toFixed(1) ?? "—"}</td>
            <td className="py-2 text-right">{run.avg_ttft_ms?.toFixed(0) ?? "—"}</td>
            <td className="py-2 text-right text-gray-400">
              {run.completed_at ? new Date(run.completed_at).toLocaleDateString() : "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 6: Write RunForm.tsx**

```tsx
// apps/web/src/components/RunForm.tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRun } from "@/lib/api";

export default function RunForm() {
  const router = useRouter();
  const [form, setForm] = useState({ provider: "stub", model_id: "stub-model", model_source: "ollama" });
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const { run_id } = await createRun({ ...form, config: { concurrency_levels: [1, 10, 50, 100] } });
      router.push(`/runs/${run_id}`);
    } catch {
      setError("Failed to create run. Are you logged in?");
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4 max-w-md">
      <div>
        <label className="block text-sm text-gray-400 mb-1">Provider</label>
        <input className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white"
          value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })} />
      </div>
      <div>
        <label className="block text-sm text-gray-400 mb-1">Model ID</label>
        <input className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white"
          value={form.model_id} onChange={(e) => setForm({ ...form, model_id: e.target.value })} />
      </div>
      <div>
        <label className="block text-sm text-gray-400 mb-1">Source</label>
        <select className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white"
          value={form.model_source} onChange={(e) => setForm({ ...form, model_source: e.target.value })}>
          <option value="huggingface">HuggingFace</option>
          <option value="ollama">Ollama</option>
        </select>
      </div>
      {error && <div className="text-red-400 text-sm">{error}</div>}
      <button type="submit" className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded">
        Start Benchmark
      </button>
    </form>
  );
}
```

- [ ] **Step 7: Write pages**

```tsx
// apps/web/src/app/(public)/page.tsx
import Leaderboard from "@/components/Leaderboard";

export default function HomePage() {
  return (
    <main className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">LLM Speed Leaderboard</h1>
      <Leaderboard />
    </main>
  );
}
```

```tsx
// apps/web/src/app/(public)/runs/[id]/page.tsx
import { getRun } from "@/lib/api";

export default async function PublicRunPage({ params }: { params: { id: string } }) {
  const run = await getRun(params.id);
  return (
    <main className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">{run.model_id}</h1>
      <p className="text-gray-400 mb-6">{run.provider} · {run.status}</p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          ["Avg Latency", `${run.avg_latency_ms?.toFixed(0) ?? "—"} ms`],
          ["Avg Throughput", `${run.avg_throughput_tps?.toFixed(1) ?? "—"} tok/s`],
          ["Avg TTFT", `${run.avg_ttft_ms?.toFixed(0) ?? "—"} ms`],
          ["Avg TPS", run.avg_tps?.toFixed(1) ?? "—"],
        ].map(([label, value]) => (
          <div key={label} className="bg-gray-800 rounded-lg p-4">
            <div className="text-xl font-bold">{value}</div>
            <div className="text-xs text-gray-400 mt-1">{label}</div>
          </div>
        ))}
      </div>
    </main>
  );
}
```

```tsx
// apps/web/src/app/(admin)/login/page.tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(form.email, form.password);
      router.push("/new");
    } catch {
      setError("Invalid credentials");
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center">
      <form onSubmit={submit} className="bg-gray-900 p-8 rounded-xl space-y-4 w-80">
        <h1 className="text-xl font-bold">Admin Login</h1>
        <input type="email" placeholder="Email" required
          className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white"
          value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <input type="password" placeholder="Password" required
          className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-white"
          value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        {error && <div className="text-red-400 text-sm">{error}</div>}
        <button type="submit" className="w-full bg-blue-600 hover:bg-blue-500 text-white py-2 rounded">
          Login
        </button>
      </form>
    </main>
  );
}
```

```tsx
// apps/web/src/app/(admin)/new/page.tsx
import RunForm from "@/components/RunForm";

export default function NewRunPage() {
  return (
    <main className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">New Benchmark Run</h1>
      <RunForm />
    </main>
  );
}
```

```tsx
// apps/web/src/app/(admin)/runs/[id]/page.tsx
"use client";
import { useRunStream } from "@/hooks/useRunStream";
import StepsTimeline from "@/components/StepsTimeline";
import MetricTiles from "@/components/MetricTiles";
import MetricCharts from "@/components/MetricCharts";
import { cancelRun } from "@/lib/api";

export default function AdminRunPage({ params }: { params: { id: string } }) {
  const { steps, metrics, status } = useRunStream(params.id);
  const latest = metrics.length > 0 ? metrics[metrics.length - 1] : null;

  return (
    <main className="container mx-auto px-4 py-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Run {params.id.slice(0, 8)}…</h1>
          <p className="text-gray-400">Status: <span className="text-yellow-400">{status}</span></p>
        </div>
        {!["completed", "failed", "cancelled"].includes(status) && (
          <button onClick={() => cancelRun(params.id)} className="bg-red-700 hover:bg-red-600 text-white px-4 py-2 rounded">
            Cancel
          </button>
        )}
      </div>
      <MetricTiles latest={latest} />
      <div>
        <h2 className="text-lg font-semibold mb-3">Steps</h2>
        <StepsTimeline steps={steps} />
      </div>
      <div>
        <h2 className="text-lg font-semibold mb-3">Metrics</h2>
        <MetricCharts metrics={metrics} />
      </div>
    </main>
  );
}
```

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/
git commit -m "feat: web pages and components"
```

---

## Task 12: End-to-End Smoke Test

- [ ] **Step 1: Start services**

```bash
docker compose up --build -d
```

Expected: all 5 services start. Watch logs:
```bash
docker compose logs -f api worker
```

- [ ] **Step 2: Run migrations**

```bash
docker compose exec api uv run alembic upgrade head
```

Expected: `Running upgrade  -> 0001`

- [ ] **Step 3: Seed admin**

```bash
docker compose exec -e ADMIN_BOOTSTRAP_EMAIL=admin@example.com \
  -e ADMIN_BOOTSTRAP_PASSWORD=changeme \
  -e DATABASE_URL=postgresql+asyncpg://llmbench:llmbench@postgres:5432/llmbench \
  api uv run python /app/scripts/seed_admin.py
```

Expected: `Admin admin@example.com created`

- [ ] **Step 4: Check health**

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok","db":true,"redis":true}`

- [ ] **Step 5: Login and create run**

```bash
curl -c cookies.txt -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"changeme"}'

curl -b cookies.txt -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"provider":"stub","model_id":"stub-model","model_source":"ollama","config":{}}'
```

Expected: `{"run_id":"<uuid>"}`

- [ ] **Step 6: Watch SSE events**

```bash
RUN_ID=<uuid from above>
curl -N http://localhost:8000/runs/$RUN_ID/events
```

Expected: stream of `event: step` and `event: metric` lines, ending with `event: status` `completed`

- [ ] **Step 7: Check leaderboard**

```bash
curl http://localhost:8000/runs
```

Expected: JSON array with the completed run

- [ ] **Step 8: Open web UI**

Open `http://localhost:3000` in browser. Verify:
- Leaderboard shows completed run
- Login at `/login` with admin credentials
- Create new run at `/new` — redirects to live dashboard at `/runs/<id>`
- Dashboard shows steps timeline updating in real time, metric tiles and charts

- [ ] **Step 9: Final commit**

```bash
git add .
git commit -m "chore: verified end-to-end docker compose up flow"
```

---

## Appendix: Quick Reference

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Web | http://localhost:3000 |

| Command | Purpose |
|---------|---------|
| `docker compose up --build` | Start all services |
| `docker compose exec api uv run alembic upgrade head` | Run migrations |
| `docker compose exec api uv run pytest` | Run API tests |
| `bash scripts/dev_reset.sh` | Full reset (drop DB, flush Redis, migrate, seed) |
| `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up` | GPU mode |
