import asyncio
import socket
import structlog
import httpx
import redis.asyncio as aioredis
from src.config import API_URL, WORKER_SECRET, WORKER_ID

log = structlog.get_logger()

async def register() -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{API_URL}/internal/workers/register",
            json={"worker_id": WORKER_ID, "cpu": socket.gethostname()},
            headers={"x-worker-secret": WORKER_SECRET},
        )
        r.raise_for_status()
        data = r.json()
        return data["redis_url"]

async def heartbeat_loop():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await client.post(
                    f"{API_URL}/internal/workers/{WORKER_ID}/heartbeat",
                    headers={"x-worker-secret": WORKER_SECRET},
                )
            except Exception as e:
                log.warning("heartbeat_failed", error=str(e))
            await asyncio.sleep(5)

async def main():
    log.info("worker_starting", worker_id=WORKER_ID)
    redis_url = await register()
    log.info("registered", redis_url=redis_url)
    r = aioredis.from_url(redis_url, decode_responses=True)

    asyncio.create_task(heartbeat_loop())

    from src.runner import run_benchmark
    while True:
        run_id = await r.brpoplpush("queue:benchmarks", "queue:benchmarks:processing", timeout=0)
        if run_id:
            log.info("run_picked", run_id=run_id)
            try:
                await run_benchmark(run_id, r, API_URL, WORKER_SECRET, WORKER_ID)
            except Exception as e:
                log.error("run_failed", run_id=run_id, error=str(e))
            finally:
                await r.lrem("queue:benchmarks:processing", 1, run_id)

if __name__ == "__main__":
    asyncio.run(main())
