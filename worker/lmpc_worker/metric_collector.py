"""1 Hz system metric sampler — CPU, RAM, GPU, container I/O."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import psutil
import structlog

log = structlog.get_logger()

try:
    import pynvml  # type: ignore
    pynvml.nvmlInit()
    _NVML = True
except Exception:
    _NVML = False


def _sample_gpu() -> list[dict[str, Any]]:
    if not _NVML:
        return []
    samples = []
    try:
        count = pynvml.nvmlDeviceGetCount()
        for i in range(count):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0  # mW → W
            except Exception:
                power = 0.0
            try:
                clock = pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_SM)
            except Exception:
                clock = 0
            samples.append({
                "gpu_index": i,
                "gpu_util_pct": util.gpu,
                "gpu_mem_used_mb": mem.used // (1024 * 1024),
                "gpu_mem_total_mb": mem.total // (1024 * 1024),
                "gpu_temp_c": temp,
                "gpu_power_watts": round(power, 2),
                "gpu_sm_clock_mhz": clock,
            })
    except Exception as exc:
        log.debug("gpu.sample.error", error=str(exc))
    return samples


def _sample_container_stats(container_id: str) -> dict[str, float]:
    try:
        import docker  # type: ignore
        client = docker.from_env()
        container = client.containers.get(container_id)
        stats = container.stats(stream=False)

        # network I/O
        net = stats.get("networks", {})
        rx = sum(v.get("rx_bytes", 0) for v in net.values()) / (1024 * 1024)
        tx = sum(v.get("tx_bytes", 0) for v in net.values()) / (1024 * 1024)

        # disk I/O
        bio = stats.get("blkio_stats", {}).get("io_service_bytes_recursive") or []
        read_mb = sum(b["value"] for b in bio if b.get("op") == "Read") / (1024 * 1024)
        write_mb = sum(b["value"] for b in bio if b.get("op") == "Write") / (1024 * 1024)

        return {"net_rx_mbps": rx, "net_tx_mbps": tx,
                "disk_read_mbps": read_mb, "disk_write_mbps": write_mb}
    except Exception:
        return {}


class MetricCollector:
    def __init__(self, container_id: str, run_id: str, worker_id: str) -> None:
        self.container_id = container_id
        self.run_id = run_id
        self.worker_id = worker_id
        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> list[dict]:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        samples: list[dict] = []
        while not self._queue.empty():
            samples.append(self._queue.get_nowait())
        return samples

    async def _loop(self) -> None:
        while True:
            t_start = time.monotonic()
            now = datetime.now(tz=timezone.utc).isoformat()

            mem = psutil.virtual_memory()
            cpu_pct = psutil.cpu_percent(interval=None)
            gpu_rows = await asyncio.to_thread(_sample_gpu)
            io = await asyncio.to_thread(_sample_container_stats, self.container_id)

            base = {
                "time": now,
                "run_id": self.run_id,
                "worker_id": self.worker_id,
                "cpu_pct": cpu_pct,
                "ram_used_mb": mem.used // (1024 * 1024),
                "ram_pct": mem.percent,
                **io,
            }

            if gpu_rows:
                for gpu in gpu_rows:
                    await self._queue.put({**base, **gpu})
            else:
                await self._queue.put({**base, "gpu_index": 0})

            elapsed = time.monotonic() - t_start
            await asyncio.sleep(max(0, 1.0 - elapsed))
