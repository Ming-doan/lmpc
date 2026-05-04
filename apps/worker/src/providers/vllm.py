from src.providers.base import BaseProvider

class VllmProvider(BaseProvider):
    """
    vLLM provider. Start vllm/vllm-openai container, wait for GET /health,
    send requests via OpenAI-compatible POST /v1/completions.
    API ref: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html
    """
    async def start(self) -> str: raise NotImplementedError
    async def wait_ready(self) -> None: raise NotImplementedError
    async def pull(self, progress_cb) -> None: raise NotImplementedError
    async def send_requests(self, concurrency, duration_s, progress_cb): raise NotImplementedError
    async def stop(self) -> None: raise NotImplementedError
