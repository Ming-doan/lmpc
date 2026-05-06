"""Main poll-execute loop."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog

from lmpc_worker.adapters.stub import ADAPTERS
from lmpc_worker.client import BackendClient

log = structlog.get_logger()


async def _heartbeat_loop(client: BackendClient, run_id: str, interval: int = 30) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            await client.heartbeat("busy", current_run_id=run_id)
        except Exception as exc:
            log.warning("heartbeat.error", error=str(exc))


async def execute_job(job: dict[str, Any], client: BackendClient) -> dict:
    platform_name = job.get("platform", "stub")
    adapter = ADAPTERS.get(platform_name) or ADAPTERS["stub"]

    prompts = job.get("prompt_set", [])
    benchmark_args = job.get("benchmark_args", {})
    num_requests = benchmark_args.get("num_requests", len(prompts)) or len(prompts)
    max_tokens = benchmark_args.get("max_tokens", 256)

    results = []
    for i in range(num_requests):
        p = prompts[i % len(prompts)] if prompts else {"prompt": "Hello", "max_new_tokens": 64}
        result = await adapter.send_request(
            client=None,
            base_url="",
            prompt=p.get("prompt", ""),
            max_tokens=p.get("max_new_tokens", max_tokens),
        )
        results.append(result)

    ttfts = [r.ttft_ms for r in results if r.success]
    e2es = [r.e2e_ms for r in results if r.success]
    tpots = [r.tpot_ms for r in results if r.success]
    total_out = sum(r.output_tokens for r in results)
    successes = sum(1 for r in results if r.success)

    def pct(vals: list[float], p: float) -> float | None:
        if not vals:
            return None
        vals_sorted = sorted(vals)
        idx = int(len(vals_sorted) * p / 100)
        return round(vals_sorted[min(idx, len(vals_sorted) - 1)], 2)

    aggregates = {
        "ttft_p50": pct(ttfts, 50), "ttft_p90": pct(ttfts, 90),
        "ttft_p95": pct(ttfts, 95), "ttft_p99": pct(ttfts, 99),
        "ttft_mean": round(sum(ttfts) / len(ttfts), 2) if ttfts else None,
        "tpot_p50": pct(tpots, 50), "tpot_p99": pct(tpots, 99),
        "tpot_mean": round(sum(tpots) / len(tpots), 2) if tpots else None,
        "e2e_p50": pct(e2es, 50), "e2e_p99": pct(e2es, 99),
        "e2e_mean": round(sum(e2es) / len(e2es), 2) if e2es else None,
        "total_requests": len(results),
        "successful_requests": successes,
        "failed_requests": len(results) - successes,
        "total_output_tokens": total_out,
    }

    traces = [
        {
            "request_idx": i,
            "started_at": datetime.now(tz=timezone.utc).isoformat(),
            "ttft_ms": r.ttft_ms,
            "tpot_ms": r.tpot_ms,
            "e2e_ms": r.e2e_ms,
            "output_tokens": r.output_tokens,
            "input_tokens": r.input_tokens,
            "success": r.success,
            "http_status": r.http_status,
            "error": r.error,
        }
        for i, r in enumerate(results)
    ]

    return {"aggregates": aggregates, "request_traces": traces, "metric_samples": []}


async def run_poll_loop(client: BackendClient, shutdown: asyncio.Event) -> None:
    while not shutdown.is_set():
        try:
            await client.heartbeat("online")
            job = await client.poll()

            if job is None:
                continue

            run_id = job["run_id"]
            log.info("job.claimed", run_id=run_id)

            heartbeat_task = asyncio.create_task(_heartbeat_loop(client, run_id))
            try:
                await client.update_status(
                    run_id,
                    status="running",
                    started_at=datetime.now(tz=timezone.utc).isoformat(),
                )
                payload = await execute_job(job, client)
                await client.submit_results(run_id, payload)
                await client.update_status(
                    run_id,
                    status="completed",
                    completed_at=datetime.now(tz=timezone.utc).isoformat(),
                )
                log.info("job.completed", run_id=run_id)
            except Exception as exc:
                log.exception("job.failed", run_id=run_id, error=str(exc))
                try:
                    await client.update_status(run_id, status="failed", error=str(exc))
                except Exception:
                    pass
            finally:
                heartbeat_task.cancel()

        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.warning("poll_loop.error", error=str(exc))
            await asyncio.sleep(5)
