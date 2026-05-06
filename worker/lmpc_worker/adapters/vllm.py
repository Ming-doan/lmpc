"""vLLM adapter — vllm/vllm-openai:latest, port 8000."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

from lmpc_worker.adapters.base import ContainerSpec, ReadinessInfo
from lmpc_worker.adapters.openai_compat import OpenAICompatibleAdapter

log = structlog.get_logger()

_DEFAULT_IMAGE = "vllm/vllm-openai:latest"
_PORT = 8000


class VLLMAdapter(OpenAICompatibleAdapter):
    name = "vllm"

    def build_container_spec(self, model: dict[str, Any], args: dict[str, Any]) -> ContainerSpec:
        image = args.get("image", _DEFAULT_IMAGE)
        model_id = model.get("hf_id") or model.get("name", "")
        gpu_util = args.get("gpu_memory_utilization", 0.9)
        max_model_len = args.get("max_model_len", 4096)

        command = [
            "--model", model_id,
            "--gpu-memory-utilization", str(gpu_util),
            "--max-model-len", str(max_model_len),
        ]
        if args.get("extra_args"):
            command.extend(args["extra_args"])

        return ContainerSpec(
            image=image,
            port=_PORT,
            env={"HUGGING_FACE_HUB_TOKEN": args.get("hf_token", "")},
            volumes=[
                f"{args.get('hf_cache', '~/.cache/huggingface')}:/root/.cache/huggingface",
            ],
            command=command,
            gpu=True,
        )

    async def wait_until_ready(self, base_url: str, timeout_s: int) -> ReadinessInfo:
        t0 = time.perf_counter()
        deadline = t0 + timeout_s

        async with httpx.AsyncClient() as client:
            while time.perf_counter() < deadline:
                try:
                    r = await client.get(f"{base_url}/health", timeout=5.0)
                    if r.status_code == 200:
                        elapsed = (time.perf_counter() - t0) * 1000
                        return ReadinessInfo(
                            ready=True,
                            container_start_ms=round(elapsed, 1),
                            model_load_ms=round(elapsed, 1),
                            platform_version=await self._get_version(client, base_url),
                        )
                except Exception:
                    pass
                await asyncio.sleep(2.0)

        return ReadinessInfo(ready=False)

    async def _get_version(self, client: httpx.AsyncClient, base_url: str) -> str:
        try:
            r = await client.get(f"{base_url}/version", timeout=5.0)
            return r.json().get("version", "vllm/unknown")
        except Exception:
            return "vllm/unknown"
