from src.providers.base import BaseProvider

class TGIProvider(BaseProvider):
    """
    Text Generation Inference provider. Start ghcr.io/huggingface/text-generation-inference,
    wait for GET /health, send requests via POST /generate.
    API ref: https://huggingface.github.io/text-generation-inference/
    """
    async def start(self) -> str: raise NotImplementedError
    async def wait_ready(self) -> None: raise NotImplementedError
    async def pull(self, progress_cb) -> None: raise NotImplementedError
    async def send_requests(self, concurrency, duration_s, progress_cb): raise NotImplementedError
    async def stop(self) -> None: raise NotImplementedError
