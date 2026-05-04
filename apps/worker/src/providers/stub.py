import asyncio
import random
from src.providers.base import BaseProvider

class StubProvider(BaseProvider):
    async def start(self) -> str:
        await asyncio.sleep(2)
        return "http://stub:8000/v1"

    async def wait_ready(self) -> None:
        pass

    async def pull(self, progress_cb) -> None:
        for i in range(10):
            await asyncio.sleep(0.3)
            await progress_cb(float(i + 1) * 10)

    async def send_requests(self, concurrency: int, duration_s: float, progress_cb) -> list[dict]:
        results = []
        elapsed = 0.0
        while elapsed < duration_s:
            await asyncio.sleep(1)
            elapsed += 1
            sample = {
                "latency_ms": random.uniform(50 * concurrency, 200 * concurrency),
                "ttft_ms": random.uniform(20, 80),
                "tps": random.uniform(30, 120),
                "tokens_in": 128,
                "tokens_out": 256,
            }
            results.append(sample)
            await progress_cb(sample)
        return results

    async def stop(self) -> None:
        await asyncio.sleep(0.5)
