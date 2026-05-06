from lmpc_worker.adapters.base import PlatformAdapter
from lmpc_worker.adapters.mock import MockAdapter
from lmpc_worker.adapters.ollama import OllamaAdapter
from lmpc_worker.adapters.vllm import VLLMAdapter
from lmpc_worker.adapters.sglang import SGLangAdapter
from lmpc_worker.adapters.tgi import TGIAdapter
from lmpc_worker.adapters.lmstudio import LMStudioAdapter
from lmpc_worker.adapters.triton import TritonAdapter

ADAPTERS: dict[str, PlatformAdapter] = {
    "mock":     MockAdapter(),
    "ollama":   OllamaAdapter(),
    "vllm":     VLLMAdapter(),
    "sglang":   SGLangAdapter(),
    "tgi":      TGIAdapter(),
    "lmstudio": LMStudioAdapter(),
    "triton":   TritonAdapter(),
}

__all__ = ["ADAPTERS", "PlatformAdapter"]
