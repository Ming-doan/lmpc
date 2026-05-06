"""Main poll-execute loop."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import structlog

from lmpc_worker.adapters import ADAPTERS
from lmpc_worker.adapters.mock import MockAdapter
from lmpc_worker.adapters.ollama import OllamaAdapter
from lmpc_worker.client import BackendClient
from lmpc_worker.docker_runner import DockerRunner
from lmpc_worker.load_generator import run_load
from lmpc_worker.metric_collector import MetricCollector

log = structlog.get_logger()


async def _heartbeat_loop(client: BackendClient, run_id: str, interval: int = 30) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            await client.heartbeat("busy", current_run_id=run_id)
        except Exception as exc:
            log.warning("heartbeat.error", error=str(exc))


def _pct(vals: list[float], p: float) -> float | None:
    if not vals:
        return None
    return round(float(np.percentile(vals, p)), 2)


def _mean(vals: list[float]) -> float | None:
    if not vals:
        return None
    return round(float(np.mean(vals)), 2)


def _stddev(vals: list[float]) -> float | None:
    if not vals:
        return None
    return round(float(np.std(vals)), 2)


async def execute_job(job: dict[str, Any], client: BackendClient) -> dict:
    run_id: str = job["run_id"]
    worker_id: str = job.get("worker_id", "")
    platform_name: str = job.get("platform", "mock")
    model: dict = job.get("model", {})
    prompts: list[str] = [p.get("prompt", "") for p in job.get("prompt_set", [])]
    benchmark_args: dict = job.get("benchmark_args", {})
    platform_args: dict = job.get("platform_args", {})

    num_requests: int = benchmark_args.get("num_requests", 20)
    concurrency: int = benchmark_args.get("concurrency", 4)
    max_tokens: int = benchmark_args.get("max_tokens", 256)
    warmup_requests: int = benchmark_args.get("warmup_requests", 3)
    slo_ttft_ms: float = benchmark_args.get("slo_ttft_ms", 500.0)
    slo_tpot_ms: float = benchmark_args.get("slo_tpot_ms", 100.0)

    adapter = ADAPTERS.get(platform_name, ADAPTERS["mock"])
    is_mock = isinstance(adapter, MockAdapter)

    # inject model name for adapters that need it for readiness (Ollama pull)
    if hasattr(adapter, "set_model"):
        model_name = model.get("hf_id") or model.get("name", "default")
        adapter.set_model(model_name)  # type: ignore[attr-defined]

    if is_mock:
        # mock path: no Docker, immediate synthetic results
        log.info("job.mock_run", run_id=run_id)
        await _run_mock(adapter, prompts, num_requests, max_tokens, warmup_requests)
        results = await run_load(adapter, "", prompts, num_requests, concurrency, max_tokens)
        return _build_payload(
            results=results,
            metric_samples=[],
            image_digest="mock",
            container_start_ms=50.0,
            model_load_ms=100.0,
            platform_version="mock-0.1",
            concurrency=concurrency,
            wall_time_s=num_requests * 0.1 / concurrency,
            slo_ttft_ms=slo_ttft_ms,
            slo_tpot_ms=slo_tpot_ms,
        )

    # real Docker path
    runner = DockerRunner(run_id)
    spec = adapter.build_container_spec(model, platform_args)
    base_url = f"http://localhost:{spec.port}"

    log.info("job.pull_image", run_id=run_id, image=spec.image)
    image_digest = await runner.pull_image(spec.image)

    log.info("job.start_container", run_id=run_id)
    t_container = time.perf_counter()
    container_id = await runner.start_container(spec)
    container_start_ms = (time.perf_counter() - t_container) * 1000

    try:
        log.info("job.wait_ready", run_id=run_id)
        readiness = await adapter.wait_until_ready(base_url, timeout_s=600)
        if not readiness.ready:
            raise RuntimeError("Platform did not become ready within timeout")

        model_load_ms = readiness.model_load_ms
        platform_version = readiness.platform_version

        await runner.stream_logs(container_id)

        # warmup (discard results)
        if warmup_requests > 0:
            log.info("job.warmup", run_id=run_id, n=warmup_requests)
            await run_load(adapter, base_url, prompts, warmup_requests, concurrency, max_tokens)

        collector = MetricCollector(container_id, run_id, worker_id)
        await collector.start()

        log.info("job.load", run_id=run_id, num_requests=num_requests, concurrency=concurrency)
        t_wall = time.perf_counter()
        results = await run_load(adapter, base_url, prompts, num_requests, concurrency, max_tokens)
        wall_time_s = time.perf_counter() - t_wall

        metric_samples = await collector.stop()

    finally:
        await runner.stop_and_remove(container_id)

    return _build_payload(
        results=results,
        metric_samples=metric_samples,
        image_digest=image_digest,
        container_start_ms=container_start_ms,
        model_load_ms=model_load_ms,
        platform_version=platform_version,
        concurrency=concurrency,
        wall_time_s=wall_time_s,
        slo_ttft_ms=slo_ttft_ms,
        slo_tpot_ms=slo_tpot_ms,
    )


async def _run_mock(adapter, prompts, num_requests, max_tokens, warmup_requests) -> None:
    for i in range(warmup_requests):
        prompt = prompts[i % len(prompts)] if prompts else "Hello"
        await adapter.send_request(None, "", prompt, max_tokens)


def _build_payload(
    *,
    results,
    metric_samples: list[dict],
    image_digest: str,
    container_start_ms: float,
    model_load_ms: float,
    platform_version: str,
    concurrency: int,
    wall_time_s: float,
    slo_ttft_ms: float,
    slo_tpot_ms: float,
) -> dict:
    from datetime import datetime, timezone

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    ttfts = [r.ttft_ms for r in successes]
    tpots = [r.tpot_ms for r in successes]
    e2es = [r.e2e_ms for r in successes]
    total_out = sum(r.output_tokens for r in successes)
    total_in = sum(r.input_tokens for r in successes)

    output_tps = total_out / wall_time_s if wall_time_s > 0 else 0
    rps = len(successes) / wall_time_s if wall_time_s > 0 else 0

    # goodput: requests passing SLO / wall time
    good = sum(
        1 for r in successes
        if r.ttft_ms < slo_ttft_ms and r.tpot_ms < slo_tpot_ms
    )
    goodput_rps = good / wall_time_s if wall_time_s > 0 else 0

    # energy via trapezoidal integration over power samples
    energy_joules = 0.0
    tokens_per_joule = None
    if metric_samples:
        powers = [s.get("gpu_power_watts", 0.0) for s in metric_samples]
        times_s = list(range(len(powers)))  # 1 Hz → seconds
        if len(powers) > 1:
            energy_joules = float(np.trapz(powers, times_s))
        if energy_joules > 0:
            tokens_per_joule = round(total_out / energy_joules, 4)

    # peak resource usage
    gpu_mems = [s.get("gpu_mem_used_mb", 0) for s in metric_samples]
    gpu_utils = [s.get("gpu_util_pct", 0) for s in metric_samples]
    ram_peaks = [s.get("ram_used_mb", 0) for s in metric_samples]
    cpu_vals = [s.get("cpu_pct", 0) for s in metric_samples]
    power_vals = [s.get("gpu_power_watts", 0) for s in metric_samples]

    aggregates = {
        "ttft_p50": _pct(ttfts, 50), "ttft_p90": _pct(ttfts, 90),
        "ttft_p95": _pct(ttfts, 95), "ttft_p99": _pct(ttfts, 99),
        "ttft_mean": _mean(ttfts), "ttft_stddev": _stddev(ttfts),
        "tpot_p50": _pct(tpots, 50), "tpot_p90": _pct(tpots, 90),
        "tpot_p95": _pct(tpots, 95), "tpot_p99": _pct(tpots, 99),
        "tpot_mean": _mean(tpots), "tpot_stddev": _stddev(tpots),
        "e2e_p50": _pct(e2es, 50), "e2e_p90": _pct(e2es, 90),
        "e2e_p95": _pct(e2es, 95), "e2e_p99": _pct(e2es, 99),
        "e2e_mean": _mean(e2es), "e2e_stddev": _stddev(e2es),
        "output_tps_mean": round(output_tps, 4),
        "output_tps_per_user": round(output_tps / max(concurrency, 1), 4),
        "total_tps_mean": round((total_out + total_in) / wall_time_s, 4) if wall_time_s > 0 else 0,
        "requests_per_sec": round(rps, 4),
        "goodput_rps": round(goodput_rps, 4),
        "total_requests": len(results),
        "successful_requests": len(successes),
        "failed_requests": len(failures),
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "peak_gpu_mem_mb": max(gpu_mems) if gpu_mems else None,
        "avg_gpu_util_pct": _mean(gpu_utils),
        "peak_gpu_util_pct": max(gpu_utils) if gpu_utils else None,
        "peak_ram_mb": max(ram_peaks) if ram_peaks else None,
        "avg_cpu_pct": _mean(cpu_vals),
        "avg_power_watts": _mean(power_vals),
        "energy_joules": round(energy_joules, 4),
        "tokens_per_joule": tokens_per_joule,
        "container_start_ms": round(container_start_ms, 1),
        "model_load_ms": round(model_load_ms, 1),
        "first_ready_ms": round(container_start_ms + model_load_ms, 1),
        "computed_at": datetime.now(tz=timezone.utc).isoformat(),
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

    return {
        "aggregates": aggregates,
        "request_traces": traces,
        "metric_samples": metric_samples,
        "image_digest": image_digest,
        "platform_version": platform_version,
    }


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

                # attach reproducibility fields to status update
                await client.update_status(
                    run_id,
                    status="running",
                    image_digest=payload.pop("image_digest", None),
                    platform_version=payload.pop("platform_version", None),
                )

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
