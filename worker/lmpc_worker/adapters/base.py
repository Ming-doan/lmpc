from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContainerSpec:
    image: str
    port: int
    env: dict[str, str] = field(default_factory=dict)
    volumes: list[str] = field(default_factory=list)
    command: list[str] = field(default_factory=list)
    gpu: bool = False


@dataclass
class ReadinessInfo:
    ready: bool
    model_load_ms: float = 0.0
    container_start_ms: float = 0.0
    platform_version: str = ""


@dataclass
class RequestResult:
    ttft_ms: float
    tpot_ms: float
    e2e_ms: float
    input_tokens: int
    output_tokens: int
    success: bool
    error: str | None = None
    http_status: int | None = None


class PlatformAdapter(ABC):
    name: str

    @abstractmethod
    def build_container_spec(self, model: dict[str, Any], args: dict[str, Any]) -> ContainerSpec: ...

    @abstractmethod
    async def wait_until_ready(self, base_url: str, timeout_s: int) -> ReadinessInfo: ...

    @abstractmethod
    async def send_request(
        self,
        client: Any,
        base_url: str,
        prompt: str,
        max_tokens: int,
        stream: bool = True,
    ) -> RequestResult: ...
