"""Read-only catalog: platforms, models, prompt sets."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import require_admin
from app.models.model import Model
from app.models.platform import Platform
from app.models.prompt_set import PromptSet
from app.schemas.catalog import ModelCreate, ModelOut, PlatformOut, PromptSetOut

router = APIRouter(tags=["catalog"])


@router.get("/platforms", response_model=list[PlatformOut])
async def list_platforms(db: AsyncSession = Depends(get_db)) -> list[Platform]:
    result = await db.execute(select(Platform).order_by(Platform.name))
    return list(result.scalars().all())


@router.get("/models", response_model=list[ModelOut])
async def list_models(db: AsyncSession = Depends(get_db)) -> list[Model]:
    result = await db.execute(select(Model).order_by(Model.name))
    return list(result.scalars().all())


@router.post("/models", response_model=ModelOut, dependencies=[Depends(require_admin)], status_code=201)
async def create_model(body: ModelCreate, db: AsyncSession = Depends(get_db)) -> Model:
    model = Model(
        name=body.name,
        hf_id=body.hf_id,
        size_b=body.size_b,
        quantization=body.quantization,
        context_length=body.context_length,
        metadata_=body.metadata_,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@router.get("/prompt-sets", response_model=list[PromptSetOut])
async def list_prompt_sets(db: AsyncSession = Depends(get_db)) -> list[PromptSet]:
    result = await db.execute(select(PromptSet).order_by(PromptSet.name))
    return list(result.scalars().all())


@router.get("/compare")
async def compare_runs(run_ids: str, db: AsyncSession = Depends(get_db)) -> dict:
    from app.models.run import BenchmarkResult, BenchmarkRun
    from sqlalchemy.orm import selectinload

    ids = [rid.strip() for rid in run_ids.split(",") if rid.strip()]
    if not ids:
        raise HTTPException(status_code=422, detail="Provide at least one run_id")

    result = await db.execute(
        select(BenchmarkRun)
        .options(selectinload(BenchmarkRun.result), selectinload(BenchmarkRun.config))
        .where(BenchmarkRun.id.in_(ids))
    )
    runs = list(result.scalars().all())

    return {
        "runs": [
            {
                "run_id": str(r.id),
                "status": r.status,
                "iteration": r.iteration,
                "result": (
                    {
                        "ttft_p99": r.result.ttft_p99,
                        "tpot_p99": r.result.tpot_p99,
                        "e2e_p99": r.result.e2e_p99,
                        "output_tps_mean": r.result.output_tps_mean,
                        "goodput_rps": r.result.goodput_rps,
                        "energy_joules": r.result.energy_joules,
                        "tokens_per_joule": r.result.tokens_per_joule,
                    }
                    if r.result
                    else None
                ),
            }
            for r in runs
        ]
    }
