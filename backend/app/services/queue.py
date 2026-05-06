"""Job queue service — long-poll and claim logic."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run import BenchmarkRun
from app.models.run_config import RunConfig
from app.models.platform import Platform
from app.models.worker import Worker

_jobs_available: asyncio.Event = asyncio.Event()

LEASE_SECONDS = 60
POLL_TIMEOUT = 25.0


def notify_jobs_available() -> None:
    _jobs_available.set()


async def claim_next_job(worker: Worker, db: AsyncSession) -> BenchmarkRun | None:
    """Select and claim the highest-priority queued run the worker supports."""
    capabilities = worker.capabilities or {}
    supported = capabilities.get("platforms", [])

    async with db.begin_nested():
        stmt = (
            select(BenchmarkRun)
            .join(BenchmarkRun.config)
            .join(RunConfig.platform)
            .where(
                BenchmarkRun.status == "queued",
                Platform.name.in_(supported) if supported else True,
            )
            .order_by(BenchmarkRun.priority.desc(), BenchmarkRun.queued_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()

        if run is None:
            return None

        now = datetime.now(tz=timezone.utc)
        run.status = "claimed"
        run.worker_id = worker.id
        run.claimed_at = now
        run.leased_until = now + timedelta(seconds=LEASE_SECONDS)
        run.attempt = (run.attempt or 0) + 1

    return run


async def poll_for_job(worker: Worker, db: AsyncSession) -> BenchmarkRun | None:
    """Long-poll up to POLL_TIMEOUT seconds for a new job."""
    # Try immediately first
    job = await claim_next_job(worker, db)
    if job:
        return job

    # Wait for a notification then try once more
    _jobs_available.clear()
    try:
        await asyncio.wait_for(_jobs_available.wait(), timeout=POLL_TIMEOUT)
    except asyncio.TimeoutError:
        pass

    return await claim_next_job(worker, db)


async def extend_lease(run_id: uuid.UUID, db: AsyncSession) -> None:
    now = datetime.now(tz=timezone.utc)
    await db.execute(
        update(BenchmarkRun)
        .where(BenchmarkRun.id == run_id, BenchmarkRun.status.in_(["claimed", "running"]))
        .values(leased_until=now + timedelta(seconds=LEASE_SECONDS))
    )
    await db.commit()
