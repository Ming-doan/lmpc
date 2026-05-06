"""TGI adapter — ghcr.io/huggingface/text-generation-inference:latest, port 80."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from lmpc_worker.adapters.base import ContainerSpec, ReadinessInfo
from lmpc_worker.adapters.openai_compat import OpenAICompatibleAdapter

_DEFAULT_IMAGE = "ghcr.io/huggingface/text-generation-inference:latest"
_PORT = 80


class TGIAdapter(OpenAICompatibleAdapter):
    name = "tgi"

    def build_container_spec(self, model: dict[str, Any], args: dict[str, Any]) -> ContainerSpec:
        image = args.get("image", _DEFAULT_IMAGE)
        model_id = model.get("hf_id") or model.get("name", "")

        return ContainerSpec(
            image=image,
            port=_PORT,
            env={
                "MODEL_ID": model_id,
                "HUGGING_FACE_HUB_TOKEN": args.get("hf_token", ""),
                "MAX_INPUT_LENGTH": str(args.get("max_input_length", 2048)),
                "MAX_TOTAL_TOKENS": str(args.get("max_total_tokens", 4096)),
            },
            volumes=[
                f"{args.get('hf_cache', '~/.cache/huggingface')}:/data",
            ],
            command=[],
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
                        version = await self._get_version(client, base_url)
                        return ReadinessInfo(
                            ready=True,
                            container_start_ms=round(elapsed, 1),
                            model_load_ms=round(elapsed, 1),
                            platform_version=version,
                        )
                except Exception:
                    pass
                await asyncio.sleep(2.0)

        return ReadinessInfo(ready=False)

    async def _get_version(self, client: httpx.AsyncClient, base_url: str) -> str:
        try:
            r = await client.get(f"{base_url}/info", timeout=5.0)
            return f"tgi/{r.json().get('version', 'unknown')}"
        except Exception:
            return "tgi/unknown"
