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
