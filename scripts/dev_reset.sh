#!/usr/bin/env bash
# Drop DB, flush Redis, run migrations, seed admin
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
