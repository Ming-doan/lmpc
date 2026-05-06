"""httpx client for the lmpc backend API."""
from __future__ import annotations

from typing import Any

import httpx

from lmpc_worker.config import settings


class BackendClient:
    def __init__(self, token: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=settings.LMPC_API_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=35.0,
        )

    async def heartbeat(self, status: str, current_run_id: str | None = None) -> dict:
        payload: dict[str, Any] = {"status": status}
        if current_run_id:
            payload["current_run_id"] = current_run_id
        r = await self._http.post("/api/v1/workers/heartbeat", json=payload)
        r.raise_for_status()
        return r.json()

    async def poll(self) -> dict | None:
        r = await self._http.post("/api/v1/workers/jobs/poll")
        r.raise_for_status()
        data = r.json()
        return data.get("job")

    async def update_status(self, run_id: str, **kwargs: Any) -> None:
        r = await self._http.post(f"/api/v1/workers/jobs/{run_id}/status", json=kwargs)
        r.raise_for_status()

    async def submit_results(self, run_id: str, payload: dict) -> None:
        r = await self._http.post(f"/api/v1/workers/jobs/{run_id}/results", json=payload)
        r.raise_for_status()

    async def aclose(self) -> None:
        await self._http.aclose()
