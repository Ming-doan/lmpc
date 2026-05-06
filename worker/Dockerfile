# ── builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install uv --no-cache-dir

COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project

COPY lmpc_worker/ lmpc_worker/

# ── runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

RUN groupadd -r lmpc && useradd -r -g lmpc -G docker lmpc 2>/dev/null || \
    groupadd -r lmpc && useradd -r -g lmpc lmpc

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/lmpc_worker /app/lmpc_worker

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER lmpc

CMD ["python", "-m", "lmpc_worker.main"]
