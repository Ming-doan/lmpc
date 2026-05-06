"""Container lifecycle management for one benchmark run."""
from __future__ import annotations

import asyncio
import os
import pathlib
from typing import Any

import structlog

from lmpc_worker.adapters.base import ContainerSpec

log = structlog.get_logger()

_LOG_DIR = pathlib.Path("/var/log/lmpc")


def _docker():
    import docker  # type: ignore
    return docker.from_env()


class DockerRunner:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._container: Any = None
        self._network_name = f"lmpc-bench-{run_id}"
        self._log_task: asyncio.Task | None = None

    async def pull_image(self, image: str) -> str:
        """Pull image and return its digest."""
        log.info("docker.pull", image=image)
        def _pull():
            client = _docker()
            client.images.pull(image)
            img = client.images.get(image)
            digests = img.attrs.get("RepoDigests", [])
            return digests[0] if digests else img.id

        return await asyncio.to_thread(_pull)

    async def start_container(self, spec: ContainerSpec) -> str:
        """Create network and start sibling container. Returns container_id."""
        def _start():
            client = _docker()

            # create isolated network
            try:
                client.networks.create(self._network_name, driver="bridge")
            except Exception:
                pass  # already exists

            kwargs: dict[str, Any] = {
                "image": spec.image,
                "environment": spec.env,
                "ports": {f"{spec.port}/tcp": spec.port},
                "network": self._network_name,
                "detach": True,
                "remove": False,
            }

            if spec.volumes:
                binds = []
                for v in spec.volumes:
                    # expand ~ in host path
                    parts = v.split(":", 1)
                    host = os.path.expanduser(parts[0])
                    binds.append(f"{host}:{parts[1]}" if len(parts) > 1 else host)
                kwargs["volumes"] = binds

            if spec.command:
                kwargs["command"] = spec.command

            if spec.gpu:
                kwargs["device_requests"] = [
                    {"Driver": "nvidia", "Count": -1, "Capabilities": [["gpu"]]}
                ]

            container = client.containers.run(**kwargs)
            return container.id

        container_id = await asyncio.to_thread(_start)
        self._container_id = container_id
        log.info("docker.started", container_id=container_id[:12])
        return container_id

    async def get_platform_version(self, container_id: str) -> str:
        """Try to read a version string from the running container."""
        def _version():
            client = _docker()
            container = client.containers.get(container_id)
            try:
                result = container.exec_run("sh -c 'cat /version.txt 2>/dev/null || echo unknown'")
                return result.output.decode().strip()
            except Exception:
                return "unknown"

        return await asyncio.to_thread(_version)

    async def stream_logs(self, container_id: str) -> None:
        """Background task — stream container logs to /var/log/lmpc/{run_id}.log."""
        def _stream():
            try:
                _LOG_DIR.mkdir(parents=True, exist_ok=True)
                log_path = _LOG_DIR / f"{self.run_id}.log"
                client = _docker()
                container = client.containers.get(container_id)
                with log_path.open("wb") as f:
                    for chunk in container.logs(stream=True, follow=True):
                        f.write(chunk)
                        f.flush()
            except Exception as exc:
                log.debug("docker.log_stream.ended", error=str(exc))

        self._log_task = asyncio.create_task(asyncio.to_thread(_stream))

    async def stop_and_remove(self, container_id: str) -> None:
        """Stop container, remove it, tear down network."""
        if self._log_task:
            self._log_task.cancel()

        def _cleanup():
            client = _docker()
            try:
                container = client.containers.get(container_id)
                container.stop(timeout=10)
                container.remove(force=True)
            except Exception as exc:
                log.warning("docker.remove.error", error=str(exc))

            try:
                net = client.networks.get(self._network_name)
                net.remove()
            except Exception:
                pass

        await asyncio.to_thread(_cleanup)
        log.info("docker.removed", container_id=container_id[:12])
