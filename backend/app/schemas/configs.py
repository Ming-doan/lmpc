from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RunConfigCreate(BaseModel):
    name: str
    platform_id: int
    model_id: int
    prompt_set_id: int
    platform_args: dict[str, Any] | None = None
    benchmark_args: dict[str, Any] = {}
    created_by: str | None = None


class RunConfigOut(BaseModel):
    id: uuid.UUID
    name: str
    platform_id: int
    model_id: int
    prompt_set_id: int
    platform_args: dict[str, Any] | None
    benchmark_args: dict[str, Any]
    created_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
