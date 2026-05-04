import asyncio
import statistics
import time
import structlog
import httpx
import redis.asyncio as aioredis
from src.metrics.publisher import MetricsPublisher
from src.providers.stub import StubProvider

log = structlog.get_logger()


async def update_run_status(api_url: str, secret: str, run_id: str, **kwargs):
    try:
        async with httpx.AsyncClient() as client:
            await client.patch(
                f"{api_url}/internal/runs/{run_id}/status",
                json=kwargs,
                headers={"x-worker-secret": secret},
                timeout=10,
            )
    except Exception as e:
        log.warning("run_status_update_failed", run_id=run_id, error=str(e))


async def run_benchmark(run_id: str, r: aioredis.Redis, api_url: str, secret: str, worker_id: str):
    pub = MetricsPublisher(r, run_id)
    start_time = time.time()

    def t_offset() -> int:
        return int((time.time() - start_time) * 1000)

    async def check_cancel() -> bool:
        return await r.exists(f"run:{run_id}:cancel") == 1

    provider = StubProvider()
    current_step = "picked"

    try:
        # picked
        await pub.emit_status("picked")
        await pub.emit_step("worker_pick", "completed", message=f"Picked by {worker_id}")
        await update_run_status(api_url, secret, run_id, status="picked", worker_id=worker_id)

        if await check_cancel():
            await pub.emit_status("cleanup")
            await pub.emit_step("cleanup", "started")
            await provider.stop()
            await pub.emit_step("cleanup", "completed")
            await pub.emit_status("cancelled")
            return

        # starting_container
        current_step = "starting_container"
        await pub.emit_status("starting_container")
        await pub.emit_step("container_start", "started")
        endpoint = await provider.start()
        await pub.emit_step("container_start", "completed", details={"endpoint": endpoint})

        if await check_cancel():
            await pub.emit_status("cleanup")
            await pub.emit_step("cleanup", "started")
            await provider.stop()
            await pub.emit_step("cleanup", "completed")
            await pub.emit_status("cancelled")
            return

        # pulling_model
        current_step = "pulling_model"
        await pub.emit_status("pulling_model")
        await pub.emit_step("pull_model", "started")

        async def pull_progress(pct: float):
            await pub.emit_step("pull_model", "progress", progress_pct=pct)

        await provider.pull(pull_progress)
        await pub.emit_step("pull_model", "completed")

        if await check_cancel():
            await pub.emit_status("cleanup")
            await pub.emit_step("cleanup", "started")
            await provider.stop()
            await pub.emit_step("cleanup", "completed")
            await pub.emit_status("cancelled")
            return

        # warming
        current_step = "warming"
        await pub.emit_status("warming")
        await pub.emit_step("warmup", "started")
        await provider.wait_ready()
        await pub.emit_step("warmup", "completed")

        if await check_cancel():
            await pub.emit_status("cleanup")
            await pub.emit_step("cleanup", "started")
            await provider.stop()
            await pub.emit_step("cleanup", "completed")
            await pub.emit_status("cancelled")
            return

        # evaluating — concurrency sweep
        current_step = "evaluating"
        concurrency_levels = [1, 10, 50, 100]
        all_results: dict[int, list[dict]] = {}
        cancelled = False
        for concurrency in concurrency_levels:
            if await check_cancel():
                cancelled = True
                break
            await pub.emit_status("evaluating")
            await pub.emit_step("evaluating", "started", details={"concurrency": concurrency})
            samples: list[dict] = []

            async def metric_progress(sample: dict, _c: int = concurrency):
                samples.append(sample)
                await pub.emit_metric(
                    t_offset(), _c,
                    latency_ms=sample["latency_ms"],
                    throughput_tps=sample["tps"] * _c,
                    ttft_ms=sample["ttft_ms"],
                    tps=sample["tps"],
                )

            await provider.send_requests(concurrency, duration_s=3, progress_cb=metric_progress)
            all_results[concurrency] = samples
            await pub.emit_step("evaluating", "completed", details={"concurrency": concurrency})

        if cancelled:
            await pub.emit_status("cleanup")
            await pub.emit_step("cleanup", "started")
            await provider.stop()
            await pub.emit_step("cleanup", "completed")
            await pub.emit_status("cancelled")
            return

        # finalizing
        current_step = "finalizing"
        await pub.emit_status("finalizing")
        await pub.emit_step("finalizing", "started")
        await asyncio.sleep(1)
        await pub.emit_step("finalizing", "completed")

        # cleanup
        current_step = "cleanup"
        await pub.emit_status("cleanup")
        await pub.emit_step("cleanup", "started")
        await provider.stop()
        await pub.emit_step("cleanup", "completed")
        await pub.emit_status("completed")

        # Compute aggregated metrics from all_results
        all_samples = [s for samples in all_results.values() for s in samples]
        avg_latency = statistics.mean(s["latency_ms"] for s in all_samples) if all_samples else None
        avg_tps = statistics.mean(s["tps"] for s in all_samples) if all_samples else None
        avg_ttft = statistics.mean(s["ttft_ms"] for s in all_samples) if all_samples else None
        await update_run_status(
            api_url, secret, run_id,
            status="completed",
            worker_id=worker_id,
            avg_latency_ms=avg_latency,
            avg_tps=avg_tps,
            avg_ttft_ms=avg_ttft,
            avg_throughput_tps=avg_tps,
        )

    except Exception as e:
        log.error("run_error", run_id=run_id, step=current_step, error=str(e))
        await pub.emit_step(current_step, "failed", message=str(e))
        await pub.emit_status("failed")
        await update_run_status(api_url, secret, run_id, status="failed", error_message=str(e), worker_id=worker_id)
        try:
            await pub.emit_step("cleanup", "started")
            await provider.stop()
            await pub.emit_step("cleanup", "completed")
        except Exception:
            pass
        await pub.emit_status("failed")
