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
