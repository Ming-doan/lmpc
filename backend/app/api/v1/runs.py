from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.security import require_admin
from app.models.run import BenchmarkResult, BenchmarkRun, MetricSample, RequestTrace
from app.models.run_config import RunConfig
from app.schemas.runs import (
    BenchmarkResultOut,
    CreateRunsRequest,
    MetricSampleOut,
    RequestTraceOut,
    RunOut,
)
from app.services.queue import notify_jobs_available

log = structlog.get_logger()
router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=list[RunOut], dependencies=[Depends(require_admin)], status_code=201)
async def create_runs(body: CreateRunsRequest, db: AsyncSession = Depends(get_db)) -> list[BenchmarkRun]:
    config = await db.get(RunConfig, body.config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")

    runs = [
        BenchmarkRun(config_id=body.config_id, iteration=i + 1, priority=body.priority)
        for i in range(body.iterations)
    ]
    db.add_all(runs)
    await db.commit()
    for r in runs:
        await db.refresh(r)

    notify_jobs_available()
    log.info("runs.created", count=len(runs), config_id=str(body.config_id))
    return runs


@router.get("", response_model=list[RunOut])
async def list_runs(
    status: str | None = None,
    platform: str | None = None,
    model: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[BenchmarkRun]:
    stmt = select(BenchmarkRun).options(selectinload(BenchmarkRun.config))
    if status:
        stmt = stmt.where(BenchmarkRun.status == status)
    result = await db.execute(stmt)
    runs = list(result.scalars().all())

    if platform or model:
        filtered = []
        for r in runs:
            if platform and r.config and r.config.platform_id:
                pass  # platform filter applied below via join in future
            filtered.append(r)
        return filtered
    return runs


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> BenchmarkRun:
    run = await db.get(BenchmarkRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/cancel", dependencies=[Depends(require_admin)])
async def cancel_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    run = await db.get(BenchmarkRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=409, detail=f"Run already in terminal state: {run.status}")
    run.status = "cancelled"
    await db.commit()
    return {"ok": True}


@router.get("/{run_id}/result", response_model=BenchmarkResultOut)
async def get_result(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> BenchmarkResult:
    result = await db.get(BenchmarkResult, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Results not available yet")
    return result


@router.get("/{run_id}/traces", response_model=list[RequestTraceOut])
async def get_traces(
    run_id: uuid.UUID,
    offset: int = 0,
    limit: int = 500,
    db: AsyncSession = Depends(get_db),
) -> list[RequestTrace]:
    result = await db.execute(
        select(RequestTrace)
        .where(RequestTrace.run_id == run_id)
        .order_by(RequestTrace.started_at)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{run_id}/metrics", response_model=list[MetricSampleOut])
async def get_metrics(
    run_id: uuid.UUID,
    offset: int = 0,
    limit: int = 1000,
    db: AsyncSession = Depends(get_db),
) -> list[MetricSample]:
    result = await db.execute(
        select(MetricSample)
        .where(MetricSample.run_id == run_id)
        .order_by(MetricSample.time)
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())
