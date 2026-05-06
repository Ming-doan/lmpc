"""Integration tests: no double-claim, janitor lease reclaim."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.models.platform import Platform
from app.models.model import Model
from app.models.prompt_set import PromptSet
from app.models.run_config import RunConfig
from app.models.run import BenchmarkRun
from app.models.worker import Worker
from app.core.security import hash_token
from app.services.queue import claim_next_job
from app.services.janitor import _tick


async def _make_worker(db, name: str, platforms: list[str]) -> Worker:
    w = Worker(
        name=name,
        hostname="test",
        specs={},
        capabilities={"platforms": platforms},
        api_token_hash=hash_token(uuid.uuid4().hex),
        status="online",
        approved=True,
    )
    db.add(w)
    await db.flush()
    return w


async def _make_run(db, config_id: uuid.UUID) -> BenchmarkRun:
    run = BenchmarkRun(config_id=config_id, iteration=1, priority=0)
    db.add(run)
    await db.flush()
    return run


async def _seed_catalog(db) -> uuid.UUID:
    platform = Platform(name="stub", display_name="Stub")
    db.add(platform)
    await db.flush()

    model = Model(name="test-model")
    db.add(model)
    await db.flush()

    ps = PromptSet(name="test-ps", prompts=[{"id": "p1", "prompt": "hello", "max_new_tokens": 10}])
    db.add(ps)
    await db.flush()

    config = RunConfig(
        name="test-config",
        platform_id=platform.id,
        model_id=model.id,
        prompt_set_id=ps.id,
        benchmark_args={"concurrency": 1, "num_requests": 1},
    )
    db.add(config)
    await db.flush()
    return config.id


@pytest.mark.asyncio
async def test_no_double_claim(db_session):
    config_id = await _seed_catalog(db_session)
    run = await _make_run(db_session, config_id)
    w1 = await _make_worker(db_session, "w1", ["stub"])
    w2 = await _make_worker(db_session, "w2", ["stub"])
    await db_session.commit()

    results = await asyncio.gather(
        claim_next_job(w1, db_session),
        claim_next_job(w2, db_session),
    )
    claimed = [r for r in results if r is not None]
    assert len(claimed) == 1, "Only one worker should claim the run"


@pytest.mark.asyncio
async def test_janitor_reclaims_expired_lease(db_session):
    config_id = await _seed_catalog(db_session)
    run = await _make_run(db_session, config_id)
    w = await _make_worker(db_session, "w-janitor", ["stub"])
    await db_session.commit()

    # Simulate a claimed run with an already-expired lease
    expired = datetime.now(tz=timezone.utc) - timedelta(seconds=10)
    await db_session.execute(
        update(BenchmarkRun)
        .where(BenchmarkRun.id == run.id)
        .values(status="claimed", worker_id=w.id, leased_until=expired, attempt=1)
    )
    await db_session.commit()

    await _tick(db_session)

    await db_session.refresh(run)
    assert run.status == "queued"
    assert run.worker_id is None
