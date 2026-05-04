import json
import redis.asyncio as aioredis

class MetricsPublisher:
    def __init__(self, r: aioredis.Redis, run_id: str):
        self.r = r
        self.run_id = run_id
        self._steps_key = f"run:{run_id}:steps"
        self._metrics_key = f"run:{run_id}:metrics:series"
        self._latest_key = f"run:{run_id}:metrics:latest"
        self._avg_key = f"run:{run_id}:metrics:running_avg"
        self._events_key = f"events:run:{run_id}"

    async def emit_step(self, step_name: str, step_status: str, progress_pct: float | None = None,
                        message: str | None = None, details: dict | None = None):
        entry = {"step_name": step_name, "step_status": step_status}
        if progress_pct is not None:
            entry["progress_pct"] = str(progress_pct)
        if message:
            entry["message"] = message
        if details:
            entry["details"] = json.dumps(details)
        await self.r.xadd(self._steps_key, entry)
        await self.r.publish(self._events_key, json.dumps({"type": "step", "payload": entry}))

    async def emit_metric(self, t_offset_ms: int, concurrency: int, latency_ms: float,
                          throughput_tps: float, ttft_ms: float, tps: float,
                          cpu_pct: float = 0, gpu_pct: float = 0, ram_mb: float = 0, vram_mb: float = 0):
        entry = {
            "t_offset_ms": str(t_offset_ms), "concurrency": str(concurrency),
            "latency_ms": str(latency_ms), "throughput_tps": str(throughput_tps),
            "ttft_ms": str(ttft_ms), "tps": str(tps),
            "cpu_pct": str(cpu_pct), "gpu_pct": str(gpu_pct),
            "ram_mb": str(ram_mb), "vram_mb": str(vram_mb),
        }
        await self.r.xadd(self._metrics_key, entry)
        await self.r.hset(self._latest_key, mapping=entry)
        await self.r.publish(self._events_key, json.dumps({"type": "metric", "payload": entry}))

    async def emit_status(self, status: str):
        await self.r.publish(self._events_key, json.dumps({"type": "status", "status": status}))
