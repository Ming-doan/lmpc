from redis.asyncio import Redis, from_url
from src.config import settings

_redis: Redis | None = None

async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(settings.redis_url, decode_responses=True)
    return _redis

async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None

# Key helpers
def key_run_state(run_id: str) -> str: return f"run:{run_id}:state"
def key_run_cancel(run_id: str) -> str: return f"run:{run_id}:cancel"
def key_run_lock(run_id: str) -> str: return f"run:{run_id}:lock"
def key_run_steps(run_id: str) -> str: return f"run:{run_id}:steps"
def key_run_metrics_series(run_id: str) -> str: return f"run:{run_id}:metrics:series"
def key_run_metrics_latest(run_id: str) -> str: return f"run:{run_id}:metrics:latest"
def key_run_metrics_running_avg(run_id: str) -> str: return f"run:{run_id}:metrics:running_avg"
def key_events_run(run_id: str) -> str: return f"events:run:{run_id}"
def key_queue_benchmarks() -> str: return "queue:benchmarks"
def key_queue_processing() -> str: return "queue:benchmarks:processing"
def key_queue_dead() -> str: return "queue:benchmarks:dead"
def key_worker_heartbeat(worker_id: str) -> str: return f"worker:{worker_id}:heartbeat"
def key_worker_info(worker_id: str) -> str: return f"worker:{worker_id}:info"
def key_worker_active_run(worker_id: str) -> str: return f"worker:{worker_id}:active_run"
