"""Worker lifecycle endpoints (worker → BE) and admin worker management (FE → BE)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_worker
from app.core.security import generate_token, hash_token, require_admin
from app.models.run import BenchmarkRun
from app.models.worker import Worker
from app.schemas.runs import RunOut
from app.schemas.workers import (
    WorkerHeartbeatRequest,
    WorkerHeartbeatResponse,
    WorkerOut,
    WorkerRegisterRequest,
    WorkerRegisterResponse,
    WorkerStatusUpdate,
)
from app.services.queue import extend_lease, poll_for_job

log = structlog.get_logger()
router = APIRouter(prefix="/workers", tags=["workers"])
limiter = Limiter(key_func=get_remote_address)

VALID_TRANSITIONS: dict[str, set[str]] = {
    "claimed": {"running", "failed", "cancelled"},
    "running": {"completed", "failed", "timeout", "cancelled"},
}


@router.post("/register", response_model=WorkerRegisterResponse, status_code=201)
@limiter.limit("5/minute")
async def register_worker(
    request: Request,
    body: WorkerRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> WorkerRegisterResponse:
    existing = await db.execute(select(Worker).where(Worker.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Worker name already registered")

    token = generate_token()
    worker = Worker(
        name=body.name,
        hostname=body.hostname,
        specs=body.specs,
        capabilities=body.capabilities,
        api_token_hash=hash_token(token),
        status="pending",
        approved=False,
    )
    db.add(worker)
    await db.commit()
    await db.refresh(worker)
    log.info("worker.registered", worker_id=str(worker.id), name=worker.name)
    return WorkerRegisterResponse(worker_id=worker.id, api_token=token, status="pending")


@router.post("/heartbeat", response_model=WorkerHeartbeatResponse)
async def heartbeat(
    body: WorkerHeartbeatRequest,
    worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
) -> WorkerHeartbeatResponse:
    now = datetime.now(tz=timezone.utc)
    await db.execute(
        update(Worker)
        .where(Worker.id == worker.id)
        .values(status=body.status, last_heartbeat_at=now)
    )
    if body.current_run_id:
        await extend_lease(body.current_run_id, db)
    await db.commit()
    return WorkerHeartbeatResponse(ok=True)


@router.post("/jobs/poll")
async def poll_job(
    worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
) -> dict:
    job = await poll_for_job(worker, db)
    if job is None:
        return {"job": None}

    await db.refresh(job, ["config"])
    await db.refresh(job.config, ["platform", "model", "prompt_set"])

    return {
        "job": {
            "run_id": str(job.id),
            "iteration": job.iteration,
            "platform": job.config.platform.name,
            "platform_image": job.config.platform.default_image,
            "platform_port": job.config.platform.default_port,
            "model_name": job.config.model.name,
            "model_hf_id": job.config.model.hf_id,
            "prompt_set": job.config.prompt_set.prompts,
            "platform_args": job.config.platform_args or {},
            "benchmark_args": job.config.benchmark_args,
        }
    }


@router.post("/jobs/{run_id}/status")
async def update_job_status(
    run_id: uuid.UUID,
    body: WorkerStatusUpdate,
    worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(BenchmarkRun).where(BenchmarkRun.id == run_id, BenchmarkRun.worker_id == worker.id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    allowed = VALID_TRANSITIONS.get(run.status, set())
    if body.status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from {run.status!r} to {body.status!r}",
        )

    run.status = body.status
    if body.started_at:
        run.started_at = body.started_at
    if body.completed_at:
        run.completed_at = body.completed_at
    if body.container_id:
        run.container_id = body.container_id
    if body.error:
        run.error_message = body.error
    if body.image_digest:
        run.image_digest = body.image_digest
    if body.platform_version:
        run.platform_version = body.platform_version

    await db.commit()
    return {"ok": True}


@router.post("/jobs/{run_id}/results")
async def submit_results(
    run_id: uuid.UUID,
    body: dict,
    worker: Worker = Depends(get_current_worker),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.run import BenchmarkResult, MetricSample, RequestTrace

    result = await db.execute(
        select(BenchmarkRun).where(BenchmarkRun.id == run_id, BenchmarkRun.worker_id == worker.id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    aggregates = body.get("aggregates", {})
    br = BenchmarkResult(run_id=run_id, **aggregates)
    db.add(br)

    for trace in body.get("request_traces", []):
        db.add(RequestTrace(run_id=run_id, **trace))

    for sample in body.get("metric_samples", []):
        db.add(MetricSample(run_id=run_id, worker_id=worker.id, **sample))

    await db.commit()
    log.info("results.submitted", run_id=str(run_id))
    return {"ok": True}


# ── Admin endpoints ────────────────────────────────────────────────────────────

@router.get("", response_model=list[WorkerOut], dependencies=[Depends(require_admin)])
async def list_workers(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[Worker]:
    stmt = select(Worker)
    if status:
        stmt = stmt.where(Worker.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{worker_id}/approve", dependencies=[Depends(require_admin)])
async def approve_worker(worker_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(
        update(Worker).where(Worker.id == worker_id).values(approved=True, status="online")
    )
    await db.commit()
    return {"ok": True}


@router.post("/{worker_id}/reject", dependencies=[Depends(require_admin)])
async def reject_worker(worker_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(
        update(Worker).where(Worker.id == worker_id).values(approved=False, status="disabled")
    )
    await db.commit()
    return {"ok": True}
