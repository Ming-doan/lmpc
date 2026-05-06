"""Background janitor — reclaims expired leases and marks workers offline."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal
from app.models.run import BenchmarkRun
from app.models.worker import Worker
from app.services.queue import notify_jobs_available

log = structlog.get_logger()

JANITOR_INTERVAL = 30
WORKER_OFFLINE_AFTER = 90


async def _tick(db: AsyncSession) -> None:
    now = datetime.now(tz=timezone.utc)

    # Reclaim runs whose lease expired and still have attempts left
    reclaim = await db.execute(
        update(BenchmarkRun)
        .where(
            BenchmarkRun.status.in_(["claimed", "running"]),
            BenchmarkRun.leased_until < now,
            BenchmarkRun.attempt < BenchmarkRun.max_attempts,
        )
        .values(
            status="queued",
            worker_id=None,
            leased_until=None,
            claimed_at=None,
        )
        .returning(BenchmarkRun.id)
    )
    reclaimed = reclaim.fetchall()

    # Mark as failed when max attempts exhausted
    await db.execute(
        update(BenchmarkRun)
        .where(
            BenchmarkRun.status.in_(["claimed", "running"]),
            BenchmarkRun.leased_until < now,
            BenchmarkRun.attempt >= BenchmarkRun.max_attempts,
        )
        .values(status="failed", error_code="max_attempts_exceeded")
    )

    # Mark workers offline after silence
    cutoff = now - timedelta(seconds=WORKER_OFFLINE_AFTER)
    await db.execute(
        update(Worker)
        .where(
            Worker.status.in_(["online", "busy"]),
            Worker.last_heartbeat_at < cutoff,
        )
        .values(status="offline")
    )

    await db.commit()

    if reclaimed:
        log.info("janitor.reclaimed", count=len(reclaimed))
        notify_jobs_available()


async def run_janitor() -> None:
    log.info("janitor.started")
    while True:
        await asyncio.sleep(JANITOR_INTERVAL)
        try:
            async with AsyncSessionLocal() as db:
                await _tick(db)
        except Exception:
            log.exception("janitor.error")
