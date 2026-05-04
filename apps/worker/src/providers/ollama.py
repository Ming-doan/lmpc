from src.providers.base import BaseProvider

class OllamaProvider(BaseProvider):
    """
    Ollama provider. Start ollama container, pull model via POST /api/pull,
    send requests via POST /api/generate with stream:false.
    API ref: https://github.com/ollama/ollama/blob/main/docs/api.md
    """
    async def start(self) -> str: raise NotImplementedError
    async def wait_ready(self) -> None: raise NotImplementedError
    async def pull(self, progress_cb) -> None: raise NotImplementedError
    async def send_requests(self, concurrency, duration_s, progress_cb): raise NotImplementedError
    async def stop(self) -> None: raise NotImplementedError
