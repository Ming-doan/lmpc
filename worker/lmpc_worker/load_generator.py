"""Concurrent load generator — sends N requests with bounded concurrency."""
from __future__ import annotations

import asyncio

import httpx
import structlog

from lmpc_worker.adapters.base import PlatformAdapter, RequestResult

log = structlog.get_logger()


async def run_load(
    adapter: PlatformAdapter,
    base_url: str,
    prompts: list[str],
    num_requests: int,
    concurrency: int,
    max_tokens: int,
) -> list[RequestResult]:
    """Send num_requests to adapter, at most concurrency in flight at once.

    Prompts are drawn round-robin. Returns results in completion order.
    """
    if not prompts:
        prompts = ["Hello, how are you?"]

    semaphore = asyncio.Semaphore(concurrency)
    results: list[tuple[int, RequestResult]] = []

    async with httpx.AsyncClient(timeout=120.0) as client:

        async def _one(idx: int) -> None:
            prompt = prompts[idx % len(prompts)]
            async with semaphore:
                try:
                    result = await adapter.send_request(
                        client=client,
                        base_url=base_url,
                        prompt=prompt,
                        max_tokens=max_tokens,
                    )
                except Exception as exc:
                    log.warning("load.request.error", idx=idx, error=str(exc))
                    result = RequestResult(
                        ttft_ms=0, tpot_ms=0, e2e_ms=0,
                        input_tokens=0, output_tokens=0,
                        success=False, error=str(exc),
                    )
                results.append((idx, result))

        await asyncio.gather(*[_one(i) for i in range(num_requests)])

    # return in request-index order
    results.sort(key=lambda x: x[0])
    return [r for _, r in results]
