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
from app.models.platform import Platform
from app.models.model import Model
from app.schemas.runs import (
    BenchmarkResultOut,
    ConfigSummary,
    CreateRunsRequest,
    MetricSampleOut,
    RequestTraceOut,
    RunOut,
)
from app.services.queue import notify_jobs_available

log = structlog.get_logger()
router = APIRouter(prefix="/runs", tags=["runs"])


def _attach_config_summary(run: BenchmarkRun) -> RunOut:
    out = RunOut.model_validate(run)
    if run.config:
        platform_name: str | None = None
        model_name: str | None = None
        try:
            platform_name = run.config.platform.name if run.config.platform else None
        except Exception:
            pass
        try:
            model_name = run.config.model.name if run.config.model else None
        except Exception:
            pass
        out.config = ConfigSummary(
            id=run.config.id,
            name=run.config.name,
            platform_name=platform_name,
            model_name=model_name,
        )
    return out


@router.post("", response_model=list[RunOut], dependencies=[Depends(require_admin)], status_code=201)
async def create_runs(body: CreateRunsRequest, db: AsyncSession = Depends(get_db)) -> list[RunOut]:
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
    return [RunOut.model_validate(r) for r in runs]


@router.get("", response_model=list[RunOut])
async def list_runs(
    status: str | None = None,
    platform: str | None = None,
    model: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[RunOut]:
    stmt = (
        select(BenchmarkRun)
        .options(
            selectinload(BenchmarkRun.config).selectinload(RunConfig.platform),
            selectinload(BenchmarkRun.config).selectinload(RunConfig.model),
        )
        .join(BenchmarkRun.config)
    )
    if status:
        stmt = stmt.where(BenchmarkRun.status == status)
    if platform:
        stmt = stmt.join(RunConfig.platform).where(Platform.name == platform)
    if model:
        stmt = stmt.join(RunConfig.model).where(Model.name == model)
    stmt = stmt.order_by(BenchmarkRun.queued_at.desc())

    result = await db.execute(stmt)
    runs = list(result.scalars().all())
    return [_attach_config_summary(r) for r in runs]


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> RunOut:
    result = await db.execute(
        select(BenchmarkRun)
        .options(
            selectinload(BenchmarkRun.config).selectinload(RunConfig.platform),
            selectinload(BenchmarkRun.config).selectinload(RunConfig.model),
        )
        .where(BenchmarkRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return _attach_config_summary(run)


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
