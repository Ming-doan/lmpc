"""Worker registration and approval-wait flow."""
from __future__ import annotations

import asyncio
import sys

import httpx
import structlog

from lmpc_worker.config import settings

log = structlog.get_logger()


def _collect_specs() -> dict:
    import platform as _platform

    specs: dict = {
        "os": _platform.system(),
        "python": _platform.python_version(),
    }
    try:
        import psutil
        specs["cpu"] = _platform.processor()
        specs["cpu_cores"] = psutil.cpu_count(logical=False)
        specs["ram_gb"] = round(psutil.virtual_memory().total / 1024**3, 1)
    except Exception:
        pass

    try:
        import pynvml
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        gpus = []
        for i in range(count):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            gpus.append({
                "name": pynvml.nvmlDeviceGetName(h),
                "vram_gb": round(mem.total / 1024**3, 1),
            })
        specs["gpu"] = gpus
    except Exception:
        specs["gpu"] = []

    return specs


async def register_or_load() -> str:
    token_path = settings.LMPC_TOKEN_PATH

    if token_path.exists():
        token = token_path.read_text().strip()
        log.info("worker.token_loaded", path=str(token_path))
        return token

    specs = _collect_specs()
    payload = {
        "name": settings.LMPC_WORKER_NAME,
        "hostname": settings.LMPC_WORKER_NAME,
        "specs": specs,
        "capabilities": {"platforms": settings.LMPC_PLATFORMS},
    }

    async with httpx.AsyncClient(base_url=settings.LMPC_API_URL, timeout=10.0) as client:
        r = await client.post("/api/v1/workers/register", json=payload)
        r.raise_for_status()
        data = r.json()

    token = data["api_token"]
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token)
    log.info("worker.registered", worker_id=data["worker_id"])
    print(
        f"\nRegistered as worker '{settings.LMPC_WORKER_NAME}' (id={data['worker_id']}).\n"
        "Awaiting admin approval. Re-run after approval.\n"
    )
    sys.exit(0)


async def wait_for_approval(client) -> None:
    """Poll heartbeat until the backend confirms status=online."""
    log.info("worker.waiting_for_approval")
    while True:
        try:
            r = await client._http.post(
                "/api/v1/workers/heartbeat", json={"status": "online"}
            )
            if r.status_code == 200:
                log.info("worker.approved")
                return
            if r.status_code == 403:
                log.info("worker.pending_approval")
        except httpx.HTTPError as exc:
            log.warning("worker.heartbeat_error", error=str(exc))
        await asyncio.sleep(10)
