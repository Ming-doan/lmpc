"""LMStudio adapter — host-based, no container lifecycle."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from lmpc_worker.adapters.base import ContainerSpec, ReadinessInfo
from lmpc_worker.adapters.openai_compat import OpenAICompatibleAdapter


class LMStudioAdapter(OpenAICompatibleAdapter):
    name = "lmstudio"

    def build_container_spec(self, model: dict[str, Any], args: dict[str, Any]) -> ContainerSpec:
        raise NotImplementedError(
            "LMStudio runs on the host, not in a container. "
            "Start LMStudio manually, load your model, enable the local server, "
            "then set platform_args.base_url to the LMStudio server URL "
            "(default: http://localhost:1234)."
        )

    async def wait_until_ready(self, base_url: str, timeout_s: int) -> ReadinessInfo:
        t0 = time.perf_counter()
        deadline = t0 + timeout_s

        async with httpx.AsyncClient() as client:
            while time.perf_counter() < deadline:
                try:
                    r = await client.get(f"{base_url}/v1/models", timeout=5.0)
                    if r.status_code == 200:
                        elapsed = (time.perf_counter() - t0) * 1000
                        return ReadinessInfo(
                            ready=True,
                            container_start_ms=0.0,
                            model_load_ms=round(elapsed, 1),
                            platform_version="lmstudio/host",
                        )
                except Exception:
                    pass
                await asyncio.sleep(2.0)

        return ReadinessInfo(ready=False)
