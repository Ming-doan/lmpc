from src.providers.base import BaseProvider

class SGlangProvider(BaseProvider):
    """
    SGLang provider. Start lmsysorg/sglang container, wait for GET /health_generate,
    send requests via POST /generate (RadixAttention backend).
    API ref: https://sgl-project.github.io/references/sampling_params.html
    """
    async def start(self) -> str: raise NotImplementedError
    async def wait_ready(self) -> None: raise NotImplementedError
    async def pull(self, progress_cb) -> None: raise NotImplementedError
    async def send_requests(self, concurrency, duration_s, progress_cb): raise NotImplementedError
    async def stop(self) -> None: raise NotImplementedError
