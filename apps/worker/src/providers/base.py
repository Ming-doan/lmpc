from abc import ABC, abstractmethod

class BaseProvider(ABC):
    """
    Abstract inference provider. Implement one class per backend (ollama, vllm, sglang, tgi).
    All methods are async. The runner calls them in order: start → wait_ready → pull → evaluate → stop.
    """
    @abstractmethod
    async def start(self) -> str:
        """Start the inference container. Returns endpoint URL (e.g. http://host:8000/v1)."""

    @abstractmethod
    async def wait_ready(self) -> None:
        """Block until the server is accepting requests. Raise on timeout."""

    @abstractmethod
    async def pull(self, progress_cb) -> None:
        """Pull/load the model. Call progress_cb(pct: float) every 300ms."""

    @abstractmethod
    async def send_requests(self, concurrency: int, duration_s: float, progress_cb) -> list[dict]:
        """
        Run requests at given concurrency for duration_s seconds.
        Returns list of {latency_ms, ttft_ms, tps, tokens_in, tokens_out}.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop and remove the inference container."""
