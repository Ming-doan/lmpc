"""Stub adapter for testing — no Docker, immediate mock results."""
from __future__ import annotations

import asyncio
import random
from typing import Any

from lmpc_worker.adapters.base import (
    ContainerSpec,
    PlatformAdapter,
    ReadinessInfo,
    RequestResult,
)


class StubAdapter(PlatformAdapter):
    name = "stub"

    def build_container_spec(self, model: dict[str, Any], args: dict[str, Any]) -> ContainerSpec:
        return ContainerSpec(image="stub", port=0)

    async def wait_until_ready(self, base_url: str, timeout_s: int) -> ReadinessInfo:
        await asyncio.sleep(0.05)
        return ReadinessInfo(
            ready=True,
            container_start_ms=50.0,
            model_load_ms=100.0,
            platform_version="stub-0.1",
        )

    async def send_request(
        self,
        client: Any,
        base_url: str,
        prompt: str,
        max_tokens: int,
        stream: bool = True,
    ) -> RequestResult:
        await asyncio.sleep(0.1)
        output_tokens = random.randint(20, min(max_tokens, 200))
        ttft = round(random.uniform(30, 120), 2)
        e2e = round(ttft + output_tokens * random.uniform(5, 15), 2)
        tpot = round((e2e - ttft) / max(output_tokens - 1, 1), 2)
        return RequestResult(
            ttft_ms=ttft,
            tpot_ms=tpot,
            e2e_ms=e2e,
            input_tokens=len(prompt.split()),
            output_tokens=output_tokens,
            success=True,
            http_status=200,
        )


ADAPTERS: dict[str, PlatformAdapter] = {
    "stub": StubAdapter(),
}
