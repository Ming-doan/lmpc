"""Shared OpenAI-compatible send_request implementation for all real adapters."""
from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from lmpc_worker.adapters.base import PlatformAdapter, RequestResult

log = structlog.get_logger()


class OpenAICompatibleAdapter(PlatformAdapter):
    """Intermediate base: implements send_request once via /v1/chat/completions streaming.

    Subclasses override build_container_spec and wait_until_ready only.
    """

    async def send_request(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        prompt: str,
        max_tokens: int,
        stream: bool = True,
    ) -> RequestResult:
        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": getattr(self, "_model_name", "default"),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": stream,
        }

        t_send = time.perf_counter()
        t_first: float | None = None
        t_last: float = t_send
        output_text = ""
        input_tokens: int = 0
        output_tokens: int = 0

        try:
            if stream:
                async with client.stream("POST", url, json=payload, timeout=120.0) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            import json
                            chunk = json.loads(data)
                        except Exception:
                            continue

                        now = time.perf_counter()
                        if t_first is None:
                            t_first = now

                        t_last = now
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        output_text += delta.get("content", "")

                        # grab token counts from usage if present (some platforms send it on last chunk)
                        usage = chunk.get("usage")
                        if usage:
                            input_tokens = usage.get("prompt_tokens", input_tokens)
                            output_tokens = usage.get("completion_tokens", output_tokens)
            else:
                resp = await client.post(url, json={**payload, "stream": False}, timeout=120.0)
                resp.raise_for_status()
                body = resp.json()
                now = time.perf_counter()
                t_first = now
                t_last = now
                output_text = body["choices"][0]["message"]["content"]
                usage = body.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

        except httpx.HTTPStatusError as exc:
            return RequestResult(
                ttft_ms=0, tpot_ms=0, e2e_ms=0,
                input_tokens=0, output_tokens=0,
                success=False, http_status=exc.response.status_code,
                error=str(exc),
            )
        except Exception as exc:
            return RequestResult(
                ttft_ms=0, tpot_ms=0, e2e_ms=0,
                input_tokens=0, output_tokens=0,
                success=False, error=str(exc),
            )

        if t_first is None:
            t_first = t_last

        ttft_ms = (t_first - t_send) * 1000
        e2e_ms = (t_last - t_send) * 1000

        # fall back to word-split approximation only when platform omits usage
        if output_tokens == 0:
            output_tokens = max(len(output_text.split()), 1)
        if input_tokens == 0:
            input_tokens = max(len(prompt.split()), 1)

        tpot_ms = (t_last - t_first) * 1000 / max(output_tokens - 1, 1)

        return RequestResult(
            ttft_ms=round(ttft_ms, 2),
            tpot_ms=round(tpot_ms, 2),
            e2e_ms=round(e2e_ms, 2),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            success=True,
            http_status=200,
        )
