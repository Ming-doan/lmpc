import asyncio
import json
from collections.abc import AsyncGenerator
from src.redis_client import get_redis, key_run_steps, key_run_metrics_series, key_events_run


async def run_event_stream(run_id: str) -> AsyncGenerator[str, None]:
    r = await get_redis()
    # Replay historical steps
    steps = await r.xrange(key_run_steps(run_id), "-", "+")
    for _, data in steps:
        yield f"event: step\ndata: {json.dumps(data)}\n\n"
    # Replay historical metrics
    metrics = await r.xrange(key_run_metrics_series(run_id), "-", "+")
    for _, data in metrics:
        yield f"event: metric\ndata: {json.dumps(data)}\n\n"

    last_step_id = "$"
    last_metric_id = "$"

    # Tail new events via pubsub
    pubsub = r.pubsub()
    await pubsub.subscribe(key_events_run(run_id))
    try:
        while True:
            step_entries = await r.xread({key_run_steps(run_id): last_step_id}, block=100, count=10)
            for _, entries in (step_entries or []):
                for entry_id, data in entries:
                    last_step_id = entry_id
                    yield f"event: step\ndata: {json.dumps(data)}\n\n"
            metric_entries = await r.xread({key_run_metrics_series(run_id): last_metric_id}, block=100, count=10)
            for _, entries in (metric_entries or []):
                for entry_id, data in entries:
                    last_metric_id = entry_id
                    yield f"event: metric\ndata: {json.dumps(data)}\n\n"
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.01)
            if msg and msg["type"] == "message":
                payload = json.loads(msg["data"])
                evt_type = payload.get("type", "status")
                yield f"event: {evt_type}\ndata: {json.dumps(payload)}\n\n"
                if payload.get("status") in ("completed", "failed", "cancelled"):
                    break
            await asyncio.sleep(0.05)
    finally:
        await pubsub.unsubscribe(key_events_run(run_id))
