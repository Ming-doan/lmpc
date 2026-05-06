from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_admin
from app.models.run_config import RunConfig
from app.schemas.configs import RunConfigCreate, RunConfigOut

router = APIRouter(prefix="/configs", tags=["configs"])


@router.get("", response_model=list[RunConfigOut], dependencies=[Depends(require_admin)])
async def list_configs(db: AsyncSession = Depends(get_db)) -> list[RunConfig]:
    result = await db.execute(select(RunConfig).order_by(RunConfig.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=RunConfigOut, dependencies=[Depends(require_admin)], status_code=201)
async def create_config(body: RunConfigCreate, db: AsyncSession = Depends(get_db)) -> RunConfig:
    config = RunConfig(**body.model_dump())
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.get("/{config_id}", response_model=RunConfigOut, dependencies=[Depends(require_admin)])
async def get_config(config_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> RunConfig:
    config = await db.get(RunConfig, config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    return config
