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
    return WorkerRegisterResponse(redis_url=settings.redis_url, heartbeat_interval_s=5)

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
