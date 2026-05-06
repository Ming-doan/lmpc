from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WorkerRegisterRequest(BaseModel):
    name: str
    hostname: str | None = None
    specs: dict[str, Any] = {}
    capabilities: dict[str, Any] = {}


class WorkerRegisterResponse(BaseModel):
    worker_id: uuid.UUID
    api_token: str
    status: str
    heartbeat_interval_s: int = 30


class WorkerHeartbeatRequest(BaseModel):
    status: str
    current_run_id: uuid.UUID | None = None


class WorkerHeartbeatResponse(BaseModel):
    ok: bool


class WorkerOut(BaseModel):
    id: uuid.UUID
    name: str
    hostname: str | None
    status: str
    approved: bool
    specs: dict[str, Any]
    capabilities: dict[str, Any] | None
    registered_at: datetime
    last_heartbeat_at: datetime | None

    model_config = {"from_attributes": True}


class WorkerStatusUpdate(BaseModel):
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    container_id: str | None = None
    error: str | None = None
    image_digest: str | None = None
    platform_version: str | None = None
