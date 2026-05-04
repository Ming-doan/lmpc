import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel

class RunCreate(BaseModel):
    provider: str
    model_id: str
    model_source: str
    config: dict[str, Any] = {}

class RunSummary(BaseModel):
    id: uuid.UUID
    status: str
    provider: str
    model_id: str
    avg_latency_ms: Optional[float]
    avg_throughput_tps: Optional[float]
    avg_ttft_ms: Optional[float]
    avg_tps: Optional[float]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}

class RunDetail(RunSummary):
    config: dict
    hardware: Optional[dict]
    error_code: Optional[str]
    error_message: Optional[str]
    started_at: Optional[datetime]
