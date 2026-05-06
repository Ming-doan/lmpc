"""Idempotent seed script — safe to run multiple times."""
import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:lmpc@localhost:5432/lmpc")

PLATFORMS = [
    {"name": "ollama",   "display_name": "Ollama",        "adapter_class": "OllamaAdapter",  "default_image": "ollama/ollama:latest",                                             "default_port": 11434},
    {"name": "vllm",     "display_name": "vLLM",          "adapter_class": "VllmAdapter",    "default_image": "vllm/vllm-openai:latest",                                          "default_port": 8000},
    {"name": "sglang",   "display_name": "SGLang",        "adapter_class": "SglangAdapter",  "default_image": "lmsysorg/sglang:latest",                                           "default_port": 30000},
    {"name": "tgi",      "display_name": "TGI",           "adapter_class": "TgiAdapter",     "default_image": "ghcr.io/huggingface/text-generation-inference:latest",              "default_port": 80},
    {"name": "lmstudio", "display_name": "LM Studio",     "adapter_class": "LmStudioAdapter","default_image": None,                                                               "default_port": 1234},
    {"name": "triton",   "display_name": "Triton-LLM",    "adapter_class": "TritonAdapter",  "default_image": "nvcr.io/nvidia/tritonserver:24.01-trtllm-python-py3",              "default_port": 8000},
]

MODELS = [
    {"name": "Qwen2.5-0.5B-Instruct",  "hf_id": "Qwen/Qwen2.5-0.5B-Instruct",  "size_b": 0.5,  "quantization": None,   "context_length": 32768},
    {"name": "Qwen2.5-1.5B-Instruct",  "hf_id": "Qwen/Qwen2.5-1.5B-Instruct",  "size_b": 1.5,  "quantization": None,   "context_length": 32768},
    {"name": "Qwen2.5-7B-Instruct",    "hf_id": "Qwen/Qwen2.5-7B-Instruct",    "size_b": 7.0,  "quantization": None,   "context_length": 32768},
    {"name": "Qwen2.5-14B-Instruct",   "hf_id": "Qwen/Qwen2.5-14B-Instruct",   "size_b": 14.0, "quantization": None,   "context_length": 32768},
    {"name": "Llama-3.2-1B-Instruct",  "hf_id": "meta-llama/Llama-3.2-1B-Instruct",  "size_b": 1.0,  "quantization": None, "context_length": 131072},
    {"name": "Llama-3.2-3B-Instruct",  "hf_id": "meta-llama/Llama-3.2-3B-Instruct",  "size_b": 3.0,  "quantization": None, "context_length": 131072},
    {"name": "Llama-3.1-8B-Instruct",  "hf_id": "meta-llama/Llama-3.1-8B-Instruct",  "size_b": 8.0,  "quantization": None, "context_length": 131072},
    {"name": "Mistral-7B-Instruct-v0.3","hf_id": "mistralai/Mistral-7B-Instruct-v0.3","size_b": 7.0, "quantization": None, "context_length": 32768},
    {"name": "Phi-3.5-mini-instruct",   "hf_id": "microsoft/Phi-3.5-mini-instruct",   "size_b": 3.8, "quantization": None,  "context_length": 131072},
    {"name": "gemma-2-2b-it",           "hf_id": "google/gemma-2-2b-it",               "size_b": 2.0, "quantization": None,  "context_length": 8192},
]

DEFAULT_PROMPTS = [
    # Short Q&A
    {"id": "qa_01", "prompt": "What is the capital of France?",                                                      "max_new_tokens": 50},
    {"id": "qa_02", "prompt": "Explain Newton's second law in one sentence.",                                         "max_new_tokens": 60},
    {"id": "qa_03", "prompt": "What does CPU stand for?",                                                             "max_new_tokens": 30},
    {"id": "qa_04", "prompt": "Who wrote the play Hamlet?",                                                           "max_new_tokens": 30},
    {"id": "qa_05", "prompt": "What is the boiling point of water in Celsius?",                                       "max_new_tokens": 30},
    {"id": "qa_06", "prompt": "How many planets are in the solar system?",                                             "max_new_tokens": 30},
    # Code
    {"id": "code_01", "prompt": "Write a Python function that returns the nth Fibonacci number using recursion.",      "max_new_tokens": 150},
    {"id": "code_02", "prompt": "Write a SQL query to find the top 5 customers by total order value.",                 "max_new_tokens": 120},
    {"id": "code_03", "prompt": "Implement a binary search algorithm in JavaScript.",                                  "max_new_tokens": 150},
    {"id": "code_04", "prompt": "Write a bash one-liner to find all .py files modified in the last 24 hours.",         "max_new_tokens": 80},
    {"id": "code_05", "prompt": "Create a TypeScript interface for a REST API response that includes pagination.",      "max_new_tokens": 120},
    # Summarization
    {"id": "sum_01", "prompt": "Summarize the key advantages of transformer architecture in neural networks.",         "max_new_tokens": 200},
    {"id": "sum_02", "prompt": "Summarize the main differences between REST and GraphQL APIs.",                        "max_new_tokens": 200},
    {"id": "sum_03", "prompt": "Briefly summarize the CAP theorem and its implications for distributed systems.",      "max_new_tokens": 180},
    {"id": "sum_04", "prompt": "Summarize how HTTPS works in 3-4 sentences.",                                          "max_new_tokens": 150},
    {"id": "sum_05", "prompt": "Summarize the key features introduced in Python 3.12.",                                "max_new_tokens": 200},
    # Long context
    {"id": "long_01", "prompt": "Explain in detail the differences between process isolation and thread isolation in operating systems, covering memory, scheduling, synchronization primitives, and failure modes.", "max_new_tokens": 400},
    {"id": "long_02", "prompt": "Describe the complete lifecycle of an HTTP request from the moment a user types a URL in the browser to when the page is rendered, covering DNS, TCP, TLS, HTTP/2, and browser rendering.", "max_new_tokens": 500},
    {"id": "long_03", "prompt": "Compare and contrast microservices and monolithic architectures, discussing deployment complexity, team ownership, data consistency, and observability.", "max_new_tokens": 450},
    {"id": "long_04", "prompt": "Explain how gradient descent and its variants (SGD, Adam, RMSProp) work, and discuss the trade-offs between batch size, learning rate, and convergence speed.", "max_new_tokens": 500},
]


async def seed() -> None:
    engine = create_async_engine(DATABASE_URL, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        for p in PLATFORMS:
            await session.execute(
                text(
                    """
                    INSERT INTO platforms (name, display_name, adapter_class, default_image, default_port)
                    VALUES (:name, :display_name, :adapter_class, :default_image, :default_port)
                    ON CONFLICT (name) DO NOTHING
                    """
                ),
                p,
            )

        for m in MODELS:
            await session.execute(
                text(
                    """
                    INSERT INTO models (name, hf_id, size_b, quantization, context_length)
                    VALUES (:name, :hf_id, :size_b, :quantization, :context_length)
                    ON CONFLICT (name) DO NOTHING
                    """
                ),
                m,
            )

        import json
        await session.execute(
            text(
                """
                INSERT INTO prompt_sets (name, description, prompts, version)
                VALUES (:name, :description, :prompts::jsonb, :version)
                ON CONFLICT (name) DO NOTHING
                """
            ),
            {
                "name": "default",
                "description": "Default benchmark prompt set: short Q&A, code, summarization, long-context",
                "prompts": json.dumps(DEFAULT_PROMPTS),
                "version": 1,
            },
        )

        await session.commit()

    await engine.dispose()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
