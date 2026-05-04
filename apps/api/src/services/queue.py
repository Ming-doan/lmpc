from src.redis_client import get_redis, key_queue_benchmarks

async def enqueue_run(run_id: str) -> None:
    r = await get_redis()
    await r.lpush(key_queue_benchmarks(), run_id)
