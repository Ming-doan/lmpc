"""Ollama adapter — ollama/ollama:latest, port 11434."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

from lmpc_worker.adapters.base import ContainerSpec, ReadinessInfo
from lmpc_worker.adapters.openai_compat import OpenAICompatibleAdapter

log = structlog.get_logger()

_DEFAULT_IMAGE = "ollama/ollama:latest"
_PORT = 11434


class OllamaAdapter(OpenAICompatibleAdapter):
    name = "ollama"

    def build_container_spec(self, model: dict[str, Any], args: dict[str, Any]) -> ContainerSpec:
        image = args.get("image", _DEFAULT_IMAGE)
        return ContainerSpec(
            image=image,
            port=_PORT,
            env={},
            volumes=[
                f"{args.get('ollama_home', '~/.ollama')}:/root/.ollama",
            ],
            command=[],
            gpu=True,
        )

    async def wait_until_ready(self, base_url: str, timeout_s: int) -> ReadinessInfo:
        t0 = time.perf_counter()
        deadline = t0 + timeout_s

        # wait for container HTTP to respond
        async with httpx.AsyncClient() as client:
            while time.perf_counter() < deadline:
                try:
                    r = await client.get(f"{base_url}/api/tags", timeout=5.0)
                    if r.status_code == 200:
                        break
                except Exception:
                    pass
                await asyncio.sleep(1.0)
            else:
                return ReadinessInfo(ready=False)

        container_start_ms = (time.perf_counter() - t0) * 1000

        # pull model — counts as model_load_ms
        model_name = self._model_name  # set by execute_job before calling
        t_pull = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/api/pull",
                    json={"name": model_name, "stream": True},
                ) as resp:
                    async for _ in resp.aiter_lines():
                        pass
        except Exception as exc:
            log.warning("ollama.pull.error", error=str(exc))

        model_load_ms = (time.perf_counter() - t_pull) * 1000

        return ReadinessInfo(
            ready=True,
            container_start_ms=round(container_start_ms, 1),
            model_load_ms=round(model_load_ms, 1),
            platform_version="ollama/latest",
        )

    # allow execute_job to inject model name before readiness check
    def set_model(self, model_name: str) -> None:
        self._model_name = model_name
