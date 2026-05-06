"""Triton-LLM adapter — nvcr.io/nvidia/tritonserver, port 8000."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from lmpc_worker.adapters.base import ContainerSpec, ReadinessInfo
from lmpc_worker.adapters.openai_compat import OpenAICompatibleAdapter

_DEFAULT_TAG = "24.12-trtllm-python-py3"
_PORT = 8000


class TritonAdapter(OpenAICompatibleAdapter):
    name = "triton"

    def build_container_spec(self, model: dict[str, Any], args: dict[str, Any]) -> ContainerSpec:
        tag = args.get("tag", _DEFAULT_TAG)
        image = args.get("image", f"nvcr.io/nvidia/tritonserver:{tag}")

        model_repo = args.get("model_repo_path")
        if not model_repo:
            raise ValueError(
                "Triton requires platform_args.model_repo_path pointing to a "
                "pre-built TensorRT-LLM model repository. "
                "See: https://github.com/triton-inference-server/tensorrtllm_backend"
            )

        return ContainerSpec(
            image=image,
            port=_PORT,
            env={},
            volumes=[f"{model_repo}:/models"],
            command=[
                "tritonserver",
                "--model-repository=/models",
                "--grpc-port=8001",
                "--http-port=8000",
                "--metrics-port=8002",
            ],
            gpu=True,
        )

    async def wait_until_ready(self, base_url: str, timeout_s: int) -> ReadinessInfo:
        t0 = time.perf_counter()
        deadline = t0 + timeout_s

        async with httpx.AsyncClient() as client:
            while time.perf_counter() < deadline:
                try:
                    r = await client.get(f"{base_url}/v2/health/ready", timeout=5.0)
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
            r = await client.get(f"{base_url}/v2", timeout=5.0)
            return f"triton/{r.json().get('version', 'unknown')}"
        except Exception:
            return "triton/unknown"
